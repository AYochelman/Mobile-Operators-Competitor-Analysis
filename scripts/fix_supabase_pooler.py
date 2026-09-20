#!/usr/bin/env python3
"""One-shot repair for the 2026-09-18..20 auth outage: move Flask's Supabase
connection from the IPv6-only direct host to the Session Pooler, verify, and
restart Flask. Run it ONCE on the Windows box that runs Flask, from an
ADMINISTRATOR PowerShell (the restart step kills the elevated Flask process):

    cd "D:\\...MASS MARKET"
    git pull
    python scripts\\fix_supabase_pooler.py

What it does, in order (each step prints what it found and stops on failure,
so the box is never left half-configured):

  1. git pull --ff-only, then check app.py has the pooler-capable
     _supabase_conn (commit a7025e7). Without it no config change can work.
  2. Read config.json - needs supabase_db_password; derives the project ref
     from the current supabase_db_host (db.<ref>.supabase.co).
  3. Find the pooler: Supabase does not expose the region anywhere in this
     repo, so try every aws-{0,1}-<region>.pooler.supabase.com with the
     tenant user postgres.<ref>. A wrong region answers "Tenant or user not
     found" in well under a second; the right one authenticates. Frankfurt
     (eu-central-1) is tried first. `--host` skips the search if you copied
     the host from Dashboard -> Connect -> Session pooler.
  4. Back up config.json, then set supabase_db_host / supabase_db_user /
     supabase_db_port. Same JSON formatting the app itself writes.
  5. Verify in a FRESH python process: app._get_user_context(<email>) must
     answer super_admin (that is the exact call the live server makes).
  6. Kill the process listening on :5000 (what scripts/restart_flask.bat
     does); the watchdog relaunches Flask with the new code + config in ~15s.
     Waits for /api/ping to answer.

Why this is needed at all: the direct host db.<ref>.supabase.co publishes an
AAAA record only, the box has no IPv6 route, so every role lookup failed and
_get_user_context returned viewer for EVERY user. Details: CLAUDE.md ->
Environment Variables -> Supabase Postgres.

--dry-run does steps 1-3 and 5 (against the found host, without writing) and
prints what step 4 would write; it never touches config.json or Flask.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
DEFAULT_REF = "gmfefvjdmgzluwffzrzj"
# Supabase's AWS regions. Israel-based project: Frankfurt first.
REGIONS = [
    "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3", "eu-north-1", "eu-central-2",
    "us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "sa-east-1",
    "ap-south-1", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2", "ap-east-1",
]
PREFIXES = ["aws-0", "aws-1"]

# Windows consoles default to a legacy code page; git may print the Hebrew
# folder name. Never let an encoding error kill the repair half-way.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def say(msg=""):
    print(msg, flush=True)


def die(msg, code=1):
    say(f"\nSTOP: {msg}")
    sys.exit(code)


def step(n, title):
    say(f"\n[{n}/6] {title}")


# ── 1. code ──────────────────────────────────────────────────────────────────
def ensure_code(skip_pull):
    step(1, "Code")
    if not skip_pull:
        r = subprocess.run(["git", "pull", "--ff-only"], cwd=ROOT, capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip()
        say("  git pull: " + (out.splitlines()[-1] if out else "(no output)"))
        if r.returncode != 0:
            die("git pull failed - fix the git state above (uncommitted changes? not on main?) and rerun.\n"
                "   To skip the pull and use the code already on disk: --no-pull")
    app_py = (ROOT / "app.py").read_text(encoding="utf-8", errors="replace")
    if "supabase_db_user" not in app_py:
        die("app.py on this box does not have the pooler-capable _supabase_conn (commit a7025e7).\n"
            "   The pull did not bring it. Check `git log --oneline -3` shows the 2026-09-20 auth commits, "
            "and that you are on main.")
    say("  app.py: pooler-capable _supabase_conn present")


# ── 2. config ────────────────────────────────────────────────────────────────
def read_config():
    step(2, "config.json")
    if not CONFIG.exists():
        die(f"{CONFIG} not found")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    pw = cfg.get("supabase_db_password") or os.environ.get("SUPABASE_DB_PASSWORD", "")
    if not pw:
        die("config.json has no supabase_db_password - nothing to connect with.")
    host = cfg.get("supabase_db_host", "")
    m = re.match(r"^db\.([a-z0-9]+)\.supabase\.co$", host or "")
    ref = m.group(1) if m else None
    say(f"  current supabase_db_host: {host or '(unset)'}")
    say(f"  current supabase_db_user: {cfg.get('supabase_db_user') or '(unset -> postgres)'}")
    return cfg, pw, ref


# ── 3. find the pooler ───────────────────────────────────────────────────────
def try_connect(host, user, pw, timeout=6):
    """Return (ok, reason). reason is one of: ok, wrong_tenant, bad_password, unreachable, other."""
    import psycopg2
    try:
        conn = psycopg2.connect(host=host, port=5432, dbname="postgres", user=user,
                                password=pw, sslmode="require", connect_timeout=timeout)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM auth.users")
        n = cur.fetchone()[0]
        conn.close()
        return True, f"ok ({n} auth.users rows)"
    except Exception as e:  # psycopg2.OperationalError and friends
        msg = str(e).strip().replace("\n", " ")
        low = msg.lower()
        if "tenant or user not found" in low:
            return False, "wrong_tenant"
        if "password authentication failed" in low:
            return False, "bad_password"
        if ("could not translate host name" in low or "timeout" in low or "timed out" in low
                or "network is unreachable" in low or "connection refused" in low
                or "name or service not known" in low):
            return False, "unreachable"
        return False, f"other: {msg[:160]}"


def find_pooler(ref, pw, forced_host=None):
    step(3, "Find the Session Pooler")
    user = f"postgres.{ref}"
    say(f"  tenant user: {user}")
    if forced_host:
        ok, why = try_connect(forced_host, user, pw, timeout=10)
        say(f"  {forced_host}: {why}")
        if not ok:
            die(f"the host you passed did not accept the tenant user. Copy it again from "
                f"Dashboard -> Connect -> Session pooler (it looks like aws-0-<region>.pooler.supabase.com).")
        return forced_host
    say("  searching regions (a dot = wrong region, answered instantly) ...")
    seen_bad_pw = None
    for region in REGIONS:
        for prefix in PREFIXES:
            host = f"{prefix}-{region}.pooler.supabase.com"
            ok, why = try_connect(host, user, pw)
            if ok:
                say(f"\n  FOUND {host}: {why}")
                return host
            if why == "bad_password":
                seen_bad_pw = host
                say(f"\n  {host}: right region, but the password was REJECTED")
                break
            if why == "wrong_tenant" or why == "unreachable":
                print(".", end="", flush=True)
            else:
                say(f"\n  {host}: {why}")
        if seen_bad_pw:
            break
    say()
    if seen_bad_pw:
        die(f"the pooler at {seen_bad_pw} is the right one, but supabase_db_password in config.json is wrong.\n"
            "   Reset it: Dashboard -> Project Settings -> Database -> Reset database password,\n"
            "   put the new value in config.json under supabase_db_password, and rerun this script.")
    die("no pooler host accepted the tenant user in any region.\n"
        "   Either this box has no outbound route to *.pooler.supabase.com right now, or the project ref is not "
        f"'{ref}'.\n   Get the exact host from Dashboard -> Connect -> Session pooler and rerun with:\n"
        "     python scripts\\fix_supabase_pooler.py --host aws-0-<region>.pooler.supabase.com")


# ── 4. write config ──────────────────────────────────────────────────────────
def write_config(cfg, host, ref, dry_run):
    step(4, "Write config.json")
    new = {"supabase_db_host": host, "supabase_db_user": f"postgres.{ref}", "supabase_db_port": 5432}
    for k, v in new.items():
        say(f"  {k} = {v}")
    if dry_run:
        say("  (dry run - not written)")
        return
    backup = CONFIG.with_name(f"config.json.bak-{datetime.now():%Y%m%d-%H%M%S}")
    backup.write_bytes(CONFIG.read_bytes())
    say(f"  backup: {backup.name}")
    cfg.update(new)
    # Same formatting the app itself uses when it writes config.json (app.py).
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    say("  written")


# ── 5. verify like the server does ───────────────────────────────────────────
def verify(email, host, ref, pw, dry_run):
    step(5, f"Verify: app._get_user_context({email!r}) in a fresh process")
    env = dict(os.environ)
    if dry_run:
        # The code reads config.json first and env second - so for a dry run the
        # only way to exercise the found host without writing is to point the
        # config at a copy. Simpler: verify the raw connection + the role query
        # here, which is exactly what _get_user_context runs.
        import psycopg2
        conn = psycopg2.connect(host=host, port=5432, dbname="postgres", user=f"postgres.{ref}",
                                password=pw, sslmode="require", connect_timeout=10)
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(r.role, 'viewer') FROM auth.users u
            LEFT JOIN public.user_roles r ON r.user_id = u.id
            WHERE LOWER(u.email) = %s
        """, (email.lower(),))
        row = cur.fetchone()
        conn.close()
        role = row[0] if row else "(no such user)"
        say(f"  role via pooler: {role}   (dry run - server code not exercised)")
        return role
    code = ("import app, json; "
            f"print(json.dumps(app._get_user_context({email.lower()!r}), default=str))")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env=env)
    out = r.stdout.strip().splitlines()
    tail = r.stderr.strip().splitlines()[-3:]
    for line in tail:
        say("  " + line)
    if r.returncode != 0 or not out:
        die("the verification process failed (see above). config.json was written; the backup is next to it.")
    ctx = json.loads(out[-1])
    role = ctx.get("role")
    say(f"  role: {role}" + (f"   reason: {ctx.get('reason')}" if ctx.get("reason") else ""))
    if ctx.get("reason") == "db_error":
        die("the server code still cannot read Supabase with the new config. Send me the lines above.")
    return role


# ── 6. restart Flask ─────────────────────────────────────────────────────────
def restart_flask(dry_run):
    step(6, "Restart Flask (what scripts/restart_flask.bat does)")
    if dry_run:
        say("  (dry run - not restarted)")
        return
    if os.name != "nt":
        say("  not Windows - skipping; restart Flask however this box runs it")
        return
    r = subprocess.run(["netstat", "-aon"], capture_output=True, text=True)
    pid = None
    # netstat -aon columns: Proto  Local Address  Foreign Address  State  PID
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(":5000"):
            pid = parts[4]
    if not pid:
        say("  nothing is LISTENING on :5000 - Flask is not running. The watchdog task (CellularComparison) "
            "should start it; if it does not, start it yourself. The new config will be read on start.")
        return
    say(f"  Flask PID {pid} - killing so the watchdog relaunches it with the new code + config")
    k = subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)
    if k.returncode != 0:
        die(f"taskkill failed: {(k.stdout + k.stderr).strip()}\n"
            "   'Access is denied' means this PowerShell is not elevated. config.json IS fixed already; "
            "just run scripts\\restart_flask.bat as administrator (or rerun this script elevated).")
    say("  waiting for the watchdog to bring Flask back (up to 90s) ...")
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:5000/api/ping", timeout=3) as resp:
                if resp.status == 200:
                    say("  Flask is back: /api/ping -> 200")
                    return
        except Exception:
            pass
        time.sleep(3)
        print(".", end="", flush=True)
    say("\n  Flask did not answer within 90s. Check the CellularComparison task / scripts/flask_watchdog.log.")


def main():
    ap = argparse.ArgumentParser(description="Move Flask's Supabase connection to the Session Pooler and restart.")
    ap.add_argument("--host", help="pooler host from Dashboard -> Connect -> Session pooler (skips the search)")
    ap.add_argument("--ref", help=f"Supabase project ref (default: from config, else {DEFAULT_REF})")
    ap.add_argument("--email", default="alon.yoch@gmail.com", help="account whose role to verify")
    ap.add_argument("--no-pull", action="store_true", help="skip git pull")
    ap.add_argument("--dry-run", action="store_true", help="find + verify, but write nothing and restart nothing")
    a = ap.parse_args()

    say(f"MOCA - Supabase pooler repair  ({datetime.now():%Y-%m-%d %H:%M})  root={ROOT}")
    ensure_code(a.no_pull)
    cfg, pw, ref_from_cfg = read_config()
    ref = a.ref or ref_from_cfg or DEFAULT_REF
    say(f"  project ref: {ref}")
    host = find_pooler(ref, pw, a.host)
    write_config(cfg, host, ref, a.dry_run)
    role = verify(a.email, host, ref, pw, a.dry_run)
    restart_flask(a.dry_run)
    say()
    if role == "super_admin":
        say(f"DONE. {a.email} resolves to super_admin through {host}.")
        say("Hard-refresh the app (Ctrl+Shift+R). No need to wait a minute - a restarted Flask has an empty cache.")
    else:
        say(f"Connection fixed (host {host}), but {a.email} resolves to {role!r}, not super_admin.")
        say("That is now a user_roles question, not a connection one - run the SQL from the earlier note.")


if __name__ == "__main__":
    main()
