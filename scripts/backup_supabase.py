"""Back up (and restore) the Supabase Postgres data MOCA depends on.

WHY THIS EXISTS
---------------
The Supabase project runs on the NANO/free tier, which keeps **no automatic
backups** (the project dashboard says "No backups" in plain text). Everything
else MOCA owns is already covered by `scripts/backup_to_drive.ps1` - config.json,
the SQLite plan database and the banner PNGs - but the identity and permission
data lives only in Supabase:

    auth.users        - the accounts themselves, incl. bcrypt password hashes
    auth.identities   - the e-mail identity rows GoTrue needs to sign a user in
    public.user_roles - viewer / admin / super_admin, and the workspace binding
    public.workspaces - the tenants those roles point at

Lose that and nobody can log in, which is not something a SQLite backup can
repair. This script dumps those four tables to a gzipped JSON file that the
Drive backup then carries off the box, and can restore them into an empty (or
partially restored) project.

The dump is SCHEMA-DRIVEN: columns, their types, primary keys and GENERATED
columns are all read from information_schema at dump time and recorded in the
file. That matters because two of these columns are generated
(`auth.users.confirmed_at`, `auth.identities.email`) and must never be written
back - see CLAUDE.md, "User provisioning is direct-DB". Introspecting instead
of hardcoding also means a future Supabase column lands in the backup by
itself.

USAGE
-----
    python scripts/backup_supabase.py                    # dump + rotate
    python scripts/backup_supabase.py --verify           # check the newest dump
    python scripts/backup_supabase.py --list             # what is on disk
    python scripts/backup_supabase.py --restore <file>   # dry run, prints a plan
    python scripts/backup_supabase.py --restore <file> --yes            # insert missing rows
    python scripts/backup_supabase.py --restore <file> --yes --overwrite # upsert every row

Exit codes: 0 = ok, 1 = failed, 3 = completed with warnings.

SENSITIVITY
-----------
The dump contains e-mail addresses and bcrypt password hashes. It is written
next to (and backed up alongside) config.json, which already holds every API
key the system owns, so it inherits that trust boundary. `--no-secrets` blanks
the credential columns, but a dump taken that way CANNOT restore anyone's
login - it is for inspection only, and the file records which kind it is.
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import decimal
import glob
import gzip
import json
import os
import shutil
import subprocess
import sys
import uuid as _uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Dump order == restore order: parents before the rows that reference them.
# auth.identities.user_id -> auth.users.id
# public.user_roles.user_id -> auth.users.id, .workspace_id -> public.workspaces.id
TABLES = [
    "auth.users",
    "public.workspaces",
    "auth.identities",
    "public.user_roles",
]

# Blanked by --no-secrets. Everything here is a credential or a single-use token;
# none of it is needed to understand who exists or what they may do.
SECRET_COLUMNS = {
    "encrypted_password",
    "confirmation_token",
    "recovery_token",
    "email_change_token_new",
    "email_change_token_current",
    "phone_change_token",
    "reauthentication_token",
}

DUMP_PREFIX = "supabase-"
DUMP_SUFFIX = ".json.gz"
LATEST_NAME = f"{DUMP_PREFIX}latest{DUMP_SUFFIX}"
SCHEMA_VERSION = 1

# Markers for values JSON cannot hold natively. Kept explicit so a restore can
# rebuild the exact Python object instead of guessing from the string shape.
_T_BYTES = "__bytes_b64__"


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------
def encode_value(value):
    """Make one Postgres value JSON-safe, losslessly and reversibly."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dt.timedelta):
        return value.total_seconds()
    if isinstance(value, _uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {_T_BYTES: base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, (list, tuple)):
        return [encode_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): encode_value(v) for k, v in value.items()}
    # Anything exotic (ranges, custom types) degrades to its text form rather
    # than failing the whole backup.
    return str(value)


def decode_value(value, data_type=None):
    """Inverse of encode_value, given the column's information_schema type."""
    if isinstance(value, dict) and _T_BYTES in value and len(value) == 1:
        return base64.b64decode(value[_T_BYTES])
    if data_type in ("json", "jsonb") and isinstance(value, (dict, list)):
        # psycopg2 will not adapt a bare dict/list; the caller wraps it in Json.
        return value
    return value


# --------------------------------------------------------------------------
# connection
# --------------------------------------------------------------------------
def connect():
    """Open the Supabase connection the app itself uses.

    Deliberately goes through `app._supabase_conn()` rather than reading
    config.json here: that is the only connection site in the codebase, so the
    backup always follows the same host/pooler settings the running server
    does. Imported lazily so this module stays importable (and testable)
    without Flask or psycopg2 present.
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    import app  # noqa: E402  (intentionally late)

    return app._supabase_conn()


# --------------------------------------------------------------------------
# introspection
# --------------------------------------------------------------------------
def describe_table(cur, schema: str, table: str) -> dict:
    """Read a table's columns, types, generated flags and primary key."""
    cur.execute(
        """
        SELECT column_name, data_type, is_generated, is_identity
          FROM information_schema.columns
         WHERE table_schema = %s AND table_name = %s
         ORDER BY ordinal_position
        """,
        (schema, table),
    )
    rows = cur.fetchall()
    if not rows:
        raise RuntimeError(f"table {schema}.{table} does not exist (or is not visible)")

    columns, types, generated = [], {}, []
    for name, data_type, is_generated, is_identity in rows:
        columns.append(name)
        types[name] = data_type
        # ALWAYS-generated and always-identity columns are rejected by INSERT.
        if (is_generated or "").upper() == "ALWAYS" or (is_identity or "").upper() == "YES":
            generated.append(name)

    cur.execute(
        """
        SELECT kcu.column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON kcu.constraint_name = tc.constraint_name
           AND kcu.table_schema = tc.table_schema
         WHERE tc.table_schema = %s AND tc.table_name = %s
           AND tc.constraint_type = 'PRIMARY KEY'
         ORDER BY kcu.ordinal_position
        """,
        (schema, table),
    )
    primary_key = [r[0] for r in cur.fetchall()]

    return {
        "columns": columns,
        "column_types": types,
        "generated": generated,
        "primary_key": primary_key,
    }


def dump_table(cur, qualified: str, include_secrets: bool) -> dict:
    schema, table = qualified.split(".", 1)
    meta = describe_table(cur, schema, table)
    cols = meta["columns"]
    cur.execute('SELECT {} FROM {}.{}'.format(
        ", ".join('"{}"'.format(c) for c in cols), schema, table))
    rows = []
    for raw in cur.fetchall():
        row = {}
        for col, val in zip(cols, raw):
            if not include_secrets and col in SECRET_COLUMNS:
                row[col] = "" if isinstance(val, str) else None
            else:
                row[col] = encode_value(val)
        rows.append(row)
    meta["row_count"] = len(rows)
    meta["rows"] = rows
    return meta


# --------------------------------------------------------------------------
# dump files
# --------------------------------------------------------------------------
def write_dump(payload: dict, out_dir: Path, stamp: str | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{DUMP_PREFIX}{stamp}{DUMP_SUFFIX}"
    # Two dumps inside the same second must not silently overwrite each other.
    # The "_NN" suffix sorts AFTER the bare name ("_" > "."), so newest-first
    # name ordering in list_dumps() still holds.
    n = 2
    while path.exists():
        path = out_dir / f"{DUMP_PREFIX}{stamp}_{n:02d}{DUMP_SUFFIX}"
        n += 1
    blob = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
    with gzip.open(path, "wb") as fh:
        fh.write(blob)
    _restrict(path)
    latest = out_dir / LATEST_NAME
    shutil.copyfile(path, latest)
    _restrict(latest)
    return path


def _restrict(path: Path) -> None:
    """Best-effort owner-only permissions (a no-op on Windows)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def read_dump(path: Path) -> dict:
    with gzip.open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def list_dumps(out_dir: Path) -> list[Path]:
    """Timestamped dumps, newest first. The `latest` copy is not one of them."""
    found = [
        Path(p) for p in glob.glob(str(out_dir / f"{DUMP_PREFIX}*{DUMP_SUFFIX}"))
        if Path(p).name != LATEST_NAME
    ]
    return sorted(found, key=lambda p: p.name, reverse=True)


def rotate(out_dir: Path, keep: int) -> list[Path]:
    """Delete all but the newest `keep` dumps. Returns what was removed."""
    if keep <= 0:
        return []
    removed = []
    for old in list_dumps(out_dir)[keep:]:
        try:
            old.unlink()
            removed.append(old)
        except OSError:
            pass
    return removed


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
def same_state(payload: dict, previous: dict | None) -> bool:
    """True when nothing that matters has changed since the previous dump.

    The Drive backup runs seven times a day but accounts and roles change a
    few times a year, so writing a file per run would push a month of real
    history out of a 30-file window within days. Comparing the payload instead
    of the clock means each retained dump is a DISTINCT state.
    """
    if not previous:
        return False
    def shape(d):
        return json.dumps(
            {"secrets": d.get("include_secrets", True), "tables": d.get("tables", {})},
            sort_keys=True, ensure_ascii=False)
    return shape(payload) == shape(previous)


def check_payload(payload: dict, previous: dict | None = None) -> list[str]:
    """Sanity-check a freshly built dump. Returns a list of warnings.

    A backup that silently captured nothing is worse than no backup, because it
    also rotates a good one out. So an empty table, or one that lost rows since
    the previous dump, is reported rather than quietly accepted.
    """
    warnings = []
    tables = payload.get("tables", {})
    for name in TABLES:
        if name not in tables:
            warnings.append(f"{name}: missing from the dump")
            continue
        count = tables[name].get("row_count", 0)
        if count == 0:
            warnings.append(f"{name}: 0 rows")
        if previous:
            before = previous.get("tables", {}).get(name, {}).get("row_count")
            if isinstance(before, int) and count < before:
                warnings.append(f"{name}: {before} rows previously, {count} now")

    roles = tables.get("public.user_roles", {}).get("rows", [])
    if roles and not any(r.get("role") == "super_admin" for r in roles):
        warnings.append("public.user_roles: no super_admin row - nobody could administer a restore")
    return warnings


def verify_dump(path: Path) -> tuple[bool, list[str]]:
    """Read a dump back and confirm it is usable. (ok, messages)."""
    messages = []
    try:
        payload = read_dump(path)
    except Exception as exc:
        return False, [f"unreadable: {exc}"]

    if payload.get("schema_version") != SCHEMA_VERSION:
        messages.append(f"schema_version is {payload.get('schema_version')}, expected {SCHEMA_VERSION}")

    ok = True
    for name in TABLES:
        table = payload.get("tables", {}).get(name)
        if table is None:
            messages.append(f"{name}: absent")
            ok = False
            continue
        rows = table.get("rows", [])
        if len(rows) != table.get("row_count"):
            messages.append(f"{name}: row_count {table.get('row_count')} but {len(rows)} rows present")
            ok = False
        cols = set(table.get("columns", []))
        for row in rows[:50]:
            missing = cols - set(row)
            if missing:
                messages.append(f"{name}: a row is missing columns {sorted(missing)}")
                ok = False
                break
        messages.append(f"{name}: {len(rows)} rows, {len(cols)} columns")

    if not payload.get("include_secrets", True):
        messages.append("NOTE: taken with --no-secrets, so it cannot restore logins")
    return ok, messages


# --------------------------------------------------------------------------
# restore
# --------------------------------------------------------------------------
def build_insert(qualified: str, table: dict, overwrite: bool) -> tuple[str, list[str]]:
    """Build the INSERT statement used to restore one table.

    Generated columns are excluded (Postgres rejects them). Without
    --overwrite the statement is additive: existing rows are left alone, so a
    restore into a live project cannot clobber newer data.
    """
    schema, name = qualified.split(".", 1)
    generated = set(table.get("generated", []))
    cols = [c for c in table["columns"] if c not in generated]
    pk = [c for c in table.get("primary_key", []) if c not in generated]

    placeholders = ", ".join(["%s"] * len(cols))
    collist = ", ".join('"{}"'.format(c) for c in cols)
    sql = f'INSERT INTO {schema}."{name}" ({collist}) VALUES ({placeholders})'

    if pk:
        conflict = ", ".join('"{}"'.format(c) for c in pk)
        if overwrite:
            updates = [c for c in cols if c not in pk]
            if updates:
                setlist = ", ".join('"{0}" = EXCLUDED."{0}"'.format(c) for c in updates)
                sql += f" ON CONFLICT ({conflict}) DO UPDATE SET {setlist}"
            else:
                sql += f" ON CONFLICT ({conflict}) DO NOTHING"
        else:
            sql += f" ON CONFLICT ({conflict}) DO NOTHING"
    return sql, cols


def _bind(values: list, cols: list[str], types: dict):
    """Adapt decoded values for psycopg2 (json/jsonb need the Json wrapper)."""
    from psycopg2.extras import Json  # local: only needed on a real restore

    out = []
    for col, val in zip(cols, values):
        data_type = types.get(col)
        decoded = decode_value(val, data_type)
        if data_type in ("json", "jsonb") and isinstance(decoded, (dict, list)):
            decoded = Json(decoded)
        out.append(decoded)
    return out


def restore(path: Path, apply: bool, overwrite: bool, only: list[str] | None, log=print) -> int:
    payload = read_dump(path)
    if not payload.get("include_secrets", True):
        log("WARNING: this dump was taken with --no-secrets. Passwords are blank,")
        log("         so restored accounts will exist but nobody can sign in.")

    wanted = [t for t in TABLES if (not only or t in only) and t in payload.get("tables", {})]
    if not wanted:
        log("nothing to restore (no matching tables in the dump)")
        return 1

    log(f"dump      : {path}")
    log(f"taken at  : {payload.get('created_at', 'unknown')}")
    log(f"mode      : {'UPSERT (overwrite)' if overwrite else 'additive (existing rows kept)'}")
    for name in wanted:
        log(f"  {name}: {payload['tables'][name].get('row_count', 0)} rows")

    if not apply:
        log("")
        log("DRY RUN - nothing was written. Re-run with --yes to apply.")
        return 0

    conn = connect()
    written = 0
    try:
        cur = conn.cursor()
        for name in wanted:
            table = payload["tables"][name]
            sql, cols = build_insert(name, table, overwrite)
            types = table.get("column_types", {})
            for row in table.get("rows", []):
                cur.execute(sql, _bind([row.get(c) for c in cols], cols, types))
                written += cur.rowcount or 0
            log(f"  {name}: applied")
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    log(f"restore complete - {written} rows written")
    return 0


# --------------------------------------------------------------------------
# dump driver
# --------------------------------------------------------------------------
def run_dump(out_dir: Path, keep: int, include_secrets: bool, allow_empty: bool,
             force: bool = False, log=print) -> tuple[int, list[str]]:
    previous_path = list_dumps(out_dir)[:1]
    previous = None
    if previous_path:
        try:
            previous = read_dump(previous_path[0])
        except Exception:
            previous = None

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT current_database(), inet_server_addr()::text, version()")
        dbname, server, version = cur.fetchone()
        tables = {}
        for name in TABLES:
            tables[name] = dump_table(cur, name, include_secrets)
            log(f"  {name}: {tables[name]['row_count']} rows")
    finally:
        conn.close()

    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "database": dbname,
        "server": server,
        "server_version": (version or "").split(" on ")[0],
        "include_secrets": include_secrets,
        "table_order": TABLES,
        "tables": tables,
    }

    warnings = check_payload(payload, previous)
    if warnings and not allow_empty and all(
        payload["tables"][t]["row_count"] == 0 for t in TABLES
    ):
        # Every table empty means the query ran against the wrong place, or the
        # project is gone. Do not write that over a good history.
        log("ERROR: every table came back empty - refusing to write this dump.")
        log("       Re-run with --allow-empty if the project really is empty.")
        return 1, warnings

    if same_state(payload, previous) and not force:
        # Nothing changed. Refresh the stable copy so freshness checks still see
        # a successful run, and leave the history alone.
        latest = out_dir / LATEST_NAME
        if latest.exists():
            os.utime(latest, None)
        elif previous_path:
            shutil.copyfile(previous_path[0], latest)
            _restrict(latest)
        log(f"unchanged since {previous_path[0].name} - no new dump written")
        return (3 if warnings else 0), warnings

    path = write_dump(payload, out_dir)
    size_kb = path.stat().st_size / 1024
    log(f"wrote {path} ({size_kb:.1f} KB)")

    ok, messages = verify_dump(path)
    if not ok:
        for m in messages:
            log(f"  verify: {m}")
        return 1, warnings + ["the dump failed its own read-back check"]

    for removed in rotate(out_dir, keep):
        log(f"rotated out {removed.name}")

    return (3 if warnings else 0), warnings


def notify(subject: str, body: str) -> None:
    """Best-effort alert through the shared multi-channel sender."""
    script = PROJECT_ROOT / "scripts" / "alert.py"
    if not script.exists():
        return
    try:
        subprocess.run([sys.executable, str(script), subject, body],
                       timeout=60, capture_output=True)
    except Exception:
        pass


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Back up / restore the Supabase auth + roles data (the free tier keeps no backups)."
    )
    ap.add_argument("--out-dir", default=str(PROJECT_ROOT / "data" / "supabase_backups"),
                    help="where dumps live (default: data/supabase_backups)")
    ap.add_argument("--keep", type=int, default=30, help="how many dumps to retain (default 30)")
    ap.add_argument("--no-secrets", action="store_true",
                    help="blank password hashes and tokens (the dump can no longer restore logins)")
    ap.add_argument("--force", action="store_true",
                    help="write a new dump even when nothing changed since the last one")
    ap.add_argument("--allow-empty", action="store_true",
                    help="write the dump even if every table is empty")
    ap.add_argument("--notify", action="store_true", help="e-mail/Telegram on failure or warnings")
    ap.add_argument("--list", action="store_true", help="list the dumps on disk and exit")
    ap.add_argument("--verify", nargs="?", const="", metavar="FILE",
                    help="verify a dump (default: the newest one) and exit")
    ap.add_argument("--restore", metavar="FILE", help="restore from a dump (dry run unless --yes)")
    ap.add_argument("--yes", action="store_true", help="actually write during --restore")
    ap.add_argument("--overwrite", action="store_true",
                    help="with --restore: upsert, replacing rows that already exist")
    ap.add_argument("--only", help="with --restore: comma-separated subset of tables")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)

    if args.list:
        dumps = list_dumps(out_dir)
        if not dumps:
            print(f"no dumps in {out_dir}")
            return 0
        for p in dumps:
            print(f"{p.name}  {p.stat().st_size / 1024:8.1f} KB")
        return 0

    if args.verify is not None:
        target = Path(args.verify) if args.verify else (list_dumps(out_dir)[:1] or [None])[0]
        if target is None:
            print(f"no dump to verify in {out_dir}")
            return 1
        ok, messages = verify_dump(target)
        print(f"{'OK  ' if ok else 'FAIL'} {target}")
        for m in messages:
            print(f"  {m}")
        return 0 if ok else 1

    if args.restore:
        only = [t.strip() for t in args.only.split(",")] if args.only else None
        return restore(Path(args.restore), apply=args.yes, overwrite=args.overwrite, only=only)

    print(f"MOCA - Supabase backup  ({_dt.datetime.now():%Y-%m-%d %H:%M})")
    try:
        code, warnings = run_dump(out_dir, args.keep, not args.no_secrets,
                                  args.allow_empty, force=args.force)
    except Exception as exc:
        print(f"ERROR: {exc}")
        if args.notify:
            notify("MOCA Supabase backup FAILED",
                   f"scripts/backup_supabase.py could not dump Supabase.\n\n{exc!r}\n\n"
                   "Nobody can be restored until this works again.")
        return 1

    for w in warnings:
        print(f"WARN: {w}")
    if args.notify and code != 0:
        notify("MOCA Supabase backup " + ("FAILED" if code == 1 else "WARNINGS"),
               "scripts/backup_supabase.py reported:\n\n" + "\n".join(f"- {w}" for w in warnings))
    return code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    sys.exit(main())
