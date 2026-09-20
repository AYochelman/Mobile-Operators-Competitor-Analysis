"""Tests for scripts/backup_supabase.py.

The Supabase free tier keeps no backups, so this script is the only copy of the
accounts and roles. These tests pin the parts that would fail silently: the
value round-trip, the INSERT built for a restore (generated columns must never
be written back), the "refuse to overwrite history with an empty dump" guard,
rotation, and read-back verification.

No database and no psycopg2 are needed - the cursor is faked.
"""

import datetime as _dt
import gzip
import importlib.util
import json
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "backup_supabase", PROJECT_ROOT / "scripts" / "backup_supabase.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bs = _load()


# --------------------------------------------------------------------------
# a cursor that answers the three shapes of query the dump issues
# --------------------------------------------------------------------------
class FakeCursor:
    def __init__(self, tables):
        self.tables = tables
        self._result = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "information_schema.columns" in s:
            schema, table = params
            self._result = list(self.tables[f"{schema}.{table}"]["columns"])
        elif "table_constraints" in s:
            schema, table = params
            self._result = [(c,) for c in self.tables[f"{schema}.{table}"]["pk"]]
        elif s.startswith("SELECT current_database"):
            self._result = [("postgres", "10.0.0.1", "PostgreSQL 15.1 on x86_64-pc-linux-gnu")]
        elif s.startswith("SELECT ") and " FROM " in s:
            qualified = s.split(" FROM ", 1)[1].strip()
            self._result = [tuple(r) for r in self.tables[qualified]["rows"]]
        else:
            raise AssertionError(f"unexpected query: {s}")

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None


class FakeConn:
    def __init__(self, tables):
        self._cur = FakeCursor(tables)
        self.closed = False

    def cursor(self):
        return self._cur

    def close(self):
        self.closed = True


UID = str(uuid.uuid4())
WSID = str(uuid.uuid4())


def _schema():
    """Mirrors the real shape closely enough to exercise every code path:
    a GENERATED column, a jsonb column, a timestamp, and a composite-free PK."""
    return {
        "auth.users": {
            "columns": [
                ("id", "uuid", "NEVER", "NO"),
                ("email", "text", "NEVER", "NO"),
                ("encrypted_password", "text", "NEVER", "NO"),
                ("raw_app_meta_data", "jsonb", "NEVER", "NO"),
                ("created_at", "timestamp with time zone", "NEVER", "NO"),
                ("confirmed_at", "timestamp with time zone", "ALWAYS", "NO"),
            ],
            "pk": ["id"],
            "rows": [(
                uuid.UUID(UID), "alon@example.com", "$2a$10$hash",
                {"provider": "email"}, _dt.datetime(2026, 9, 19, 22, 54), None,
            )],
        },
        "public.workspaces": {
            "columns": [("id", "uuid", "NEVER", "NO"), ("name", "text", "NEVER", "NO")],
            "pk": ["id"],
            "rows": [(uuid.UUID(WSID), "Partner")],
        },
        "auth.identities": {
            "columns": [
                ("id", "uuid", "NEVER", "NO"),
                ("user_id", "uuid", "NEVER", "NO"),
                ("email", "text", "ALWAYS", "NO"),
            ],
            "pk": ["id"],
            "rows": [(uuid.UUID(UID), uuid.UUID(UID), "alon@example.com")],
        },
        "public.user_roles": {
            "columns": [
                ("user_id", "uuid", "NEVER", "NO"),
                ("role", "text", "NEVER", "NO"),
                ("workspace_id", "uuid", "NEVER", "NO"),
            ],
            "pk": ["user_id"],
            "rows": [(uuid.UUID(UID), "super_admin", None)],
        },
    }


@pytest.fixture
def fake_conn(monkeypatch):
    conn = FakeConn(_schema())
    monkeypatch.setattr(bs, "connect", lambda: conn)
    return conn


# --------------------------------------------------------------------------
# value encoding
# --------------------------------------------------------------------------
def test_encode_value_handles_postgres_types():
    uid = uuid.uuid4()
    assert bs.encode_value(uid) == str(uid)
    assert bs.encode_value(_dt.datetime(2026, 9, 20, 16, 48)) == "2026-09-20T16:48:00"
    assert bs.encode_value(None) is None
    assert bs.encode_value({"a": uid}) == {"a": str(uid)}
    assert bs.encode_value([1, "x"]) == [1, "x"]


def test_bytes_round_trip():
    encoded = bs.encode_value(b"\x00\x01binary")
    assert json.dumps(encoded)  # survives JSON
    assert bs.decode_value(encoded) == b"\x00\x01binary"


# --------------------------------------------------------------------------
# dump
# --------------------------------------------------------------------------
def test_dump_table_records_generated_columns(fake_conn):
    table = bs.dump_table(fake_conn.cursor(), "auth.users", include_secrets=True)
    assert table["row_count"] == 1
    assert table["primary_key"] == ["id"]
    # confirmed_at is GENERATED ALWAYS - it must be flagged so a restore skips it.
    assert table["generated"] == ["confirmed_at"]
    assert table["rows"][0]["email"] == "alon@example.com"
    assert table["rows"][0]["created_at"] == "2026-09-19T22:54:00"


def test_no_secrets_blanks_the_password_hash(fake_conn):
    table = bs.dump_table(fake_conn.cursor(), "auth.users", include_secrets=False)
    assert table["rows"][0]["encrypted_password"] == ""
    assert table["rows"][0]["email"] == "alon@example.com"  # identity is kept


def test_run_dump_writes_verifies_and_reports(tmp_path, fake_conn):
    code, warnings = bs.run_dump(tmp_path, keep=30, include_secrets=True,
                                 allow_empty=False, log=lambda *a: None)
    assert code == 0, warnings
    assert warnings == []

    dumps = bs.list_dumps(tmp_path)
    assert len(dumps) == 1
    payload = bs.read_dump(dumps[0])
    assert payload["schema_version"] == bs.SCHEMA_VERSION
    assert set(payload["tables"]) == set(bs.TABLES)
    assert payload["include_secrets"] is True
    # the stable copy the Drive backup picks up
    assert (tmp_path / bs.LATEST_NAME).exists()


def test_latest_copy_is_not_rotated_as_a_dump(tmp_path, fake_conn):
    for _ in range(3):
        bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False, log=lambda *a: None)
    names = [p.name for p in bs.list_dumps(tmp_path)]
    assert bs.LATEST_NAME not in names


# --------------------------------------------------------------------------
# the guard that matters most
# --------------------------------------------------------------------------
def test_empty_project_does_not_overwrite_history(tmp_path, monkeypatch):
    empty = _schema()
    for t in empty.values():
        t["rows"] = []
    monkeypatch.setattr(bs, "connect", lambda: FakeConn(empty))

    code, warnings = bs.run_dump(tmp_path, keep=30, include_secrets=True,
                                 allow_empty=False, log=lambda *a: None)
    assert code == 1
    assert bs.list_dumps(tmp_path) == []          # nothing written
    assert any("0 rows" in w for w in warnings)


def test_allow_empty_overrides_the_guard(tmp_path, monkeypatch):
    empty = _schema()
    for t in empty.values():
        t["rows"] = []
    monkeypatch.setattr(bs, "connect", lambda: FakeConn(empty))
    code, _ = bs.run_dump(tmp_path, keep=30, include_secrets=True,
                          allow_empty=True, log=lambda *a: None)
    assert code == 3                               # written, but flagged
    assert len(bs.list_dumps(tmp_path)) == 1


def test_row_loss_since_the_previous_dump_is_flagged(tmp_path, fake_conn, monkeypatch):
    bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False, log=lambda *a: None)

    shrunk = _schema()
    shrunk["public.workspaces"]["rows"] = []
    monkeypatch.setattr(bs, "connect", lambda: FakeConn(shrunk))
    code, warnings = bs.run_dump(tmp_path, keep=30, include_secrets=True,
                                 allow_empty=False, log=lambda *a: None)
    assert code == 3
    assert any("1 rows previously, 0 now" in w for w in warnings)


def test_missing_super_admin_is_flagged():
    payload = {"tables": {t: {"row_count": 1, "rows": []} for t in bs.TABLES}}
    payload["tables"]["public.user_roles"]["rows"] = [{"role": "viewer"}]
    assert any("super_admin" in w for w in bs.check_payload(payload))


# --------------------------------------------------------------------------
# rotation and verification
# --------------------------------------------------------------------------
def test_rotate_keeps_the_newest(tmp_path):
    for stamp in ["20260101-000000", "20260102-000000", "20260103-000000"]:
        bs.write_dump({"tables": {}}, tmp_path, stamp=stamp)
    removed = bs.rotate(tmp_path, keep=2)
    remaining = [p.name for p in bs.list_dumps(tmp_path)]
    assert len(removed) == 1
    assert remaining == ["supabase-20260103-000000.json.gz", "supabase-20260102-000000.json.gz"]


def test_verify_catches_a_truncated_dump(tmp_path, fake_conn):
    bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False, log=lambda *a: None)
    path = bs.list_dumps(tmp_path)[0]

    payload = bs.read_dump(path)
    payload["tables"]["auth.users"]["rows"] = []      # count says 1, rows say 0
    with gzip.open(path, "wb") as fh:
        fh.write(json.dumps(payload).encode("utf-8"))

    ok, messages = bs.verify_dump(path)
    assert not ok
    assert any("row_count" in m for m in messages)


def test_verify_rejects_an_unreadable_file(tmp_path):
    bad = tmp_path / "supabase-20260101-000000.json.gz"
    bad.write_bytes(b"not gzip at all")
    ok, messages = bs.verify_dump(bad)
    assert not ok
    assert "unreadable" in messages[0]


# --------------------------------------------------------------------------
# restore
# --------------------------------------------------------------------------
def test_insert_skips_generated_columns_and_upserts_on_the_pk():
    table = {
        "columns": ["id", "email", "confirmed_at"],
        "generated": ["confirmed_at"],
        "primary_key": ["id"],
    }
    sql, cols = bs.build_insert("auth.users", table, overwrite=True)
    assert cols == ["id", "email"]
    assert "confirmed_at" not in sql
    assert 'ON CONFLICT ("id") DO UPDATE SET "email" = EXCLUDED."email"' in sql


def test_insert_is_additive_by_default():
    table = {"columns": ["id", "role"], "generated": [], "primary_key": ["id"]}
    sql, _ = bs.build_insert("public.user_roles", table, overwrite=False)
    assert "DO NOTHING" in sql
    assert "DO UPDATE" not in sql


def test_restore_dry_run_touches_no_connection(tmp_path, fake_conn, monkeypatch):
    bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False, log=lambda *a: None)
    path = bs.list_dumps(tmp_path)[0]

    def explode():
        raise AssertionError("a dry run must not open a connection")

    monkeypatch.setattr(bs, "connect", explode)
    lines = []
    assert bs.restore(path, apply=False, overwrite=False, only=None, log=lines.append) == 0
    assert any("DRY RUN" in ln for ln in lines)


# --------------------------------------------------------------------------
# change detection (so 30 retained dumps are 30 distinct states, not 4 days)
# --------------------------------------------------------------------------
def test_an_unchanged_state_does_not_add_a_dump(tmp_path, fake_conn):
    bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False, log=lambda *a: None)
    first = bs.list_dumps(tmp_path)

    lines = []
    code, _ = bs.run_dump(tmp_path, keep=30, include_secrets=True,
                          allow_empty=False, log=lines.append)
    assert code == 0
    assert bs.list_dumps(tmp_path) == first          # history untouched
    assert any("unchanged" in ln for ln in lines)
    assert (tmp_path / bs.LATEST_NAME).exists()      # still fresh for the age check


def test_force_writes_even_when_unchanged(tmp_path, fake_conn):
    bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False, log=lambda *a: None)
    bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False,
                force=True, log=lambda *a: None)
    assert len(bs.list_dumps(tmp_path)) == 2


def test_a_real_change_writes_a_new_dump(tmp_path, fake_conn, monkeypatch):
    bs.run_dump(tmp_path, keep=30, include_secrets=True, allow_empty=False, log=lambda *a: None)

    grown = _schema()
    grown["public.workspaces"]["rows"].append((uuid.uuid4(), "Cellcom"))
    monkeypatch.setattr(bs, "connect", lambda: FakeConn(grown))
    code, warnings = bs.run_dump(tmp_path, keep=30, include_secrets=True,
                                 allow_empty=False, log=lambda *a: None)
    assert code == 0 and warnings == []
    assert len(bs.list_dumps(tmp_path)) == 2


def test_same_state_ignores_the_timestamp():
    a = {"include_secrets": True, "tables": {"t": {"rows": [1]}}, "created_at": "2026-01-01"}
    b = {"include_secrets": True, "tables": {"t": {"rows": [1]}}, "created_at": "2026-09-20"}
    assert bs.same_state(a, b)
    b["include_secrets"] = False
    assert not bs.same_state(a, b)


def test_two_dumps_in_one_second_keep_both_and_stay_ordered(tmp_path):
    a = bs.write_dump({"tables": {}}, tmp_path, stamp="20260920-140741")
    b = bs.write_dump({"tables": {}}, tmp_path, stamp="20260920-140741")
    assert a != b
    # newest first: the collision suffix must not sort behind the bare name
    assert [p.name for p in bs.list_dumps(tmp_path)] == [b.name, a.name]
