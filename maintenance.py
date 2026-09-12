"""
Scheduled SQLite maintenance for data/plans.db.

The DB grew 43 MB -> 141 MB between 2026-06 and 2026-09 with nothing ever
deleting rows: *_changes accumulate every scraper flap forever, and
archive_snapshots keeps one compressed catalog per carrier per day. This module
turns the one-time scripts/db_compress_and_prune.py into a standing schedule:

  daily   build_price_history_daily()  - after each scrape, aggregate today's
                                          min/avg/max price per (type, carrier)
                                          and per (type, destination) market-wide
                                          into price_history_daily.
                                          Charts/analytics can read this table
                                          instead of replaying the change log.
  weekly  prune_change_logs()          - delete *_changes rows older than
                                          `changes_retention_days` (default 180).
          prune_personal_data()        - retention for analytics beacons (hashed
                                          IP + UA, 13 months), user_activity (180d),
                                          hotel_leads (24 months), finished
                                          reminders (90d) - see PERSONAL_RETENTION.
          thin_archive_snapshots()     - OPTIONAL (config `archive_thin_after_days`,
                                          default off): beyond N days keep only
                                          one snapshot per week per carrier/type.
  monthly vacuum()                     - reclaim freed pages (first Sunday).

config.json knobs (all optional):
  changes_retention_days      180
  archive_thin_after_days     null  (e.g. 90 = daily for 90d, then weekly)
  archive_keep_weekday        0     (0=Sunday .. 6=Saturday, the snapshot day kept)
  db_vacuum_enabled           true
  maintenance_dry_run         false (log what would be deleted, delete nothing)

Manual: python -c "import maintenance as m; print(m.run_weekly(dry_run=True))"
        GET /api/maintenance/run-now?api_key=...&job=weekly|daily|backfill&dry_run=true
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import db

logger = logging.getLogger(__name__)

CHANGE_TABLES = ("changes", "abroad_changes", "global_changes", "content_changes", "reseller_changes")

# plan table -> (plan_type, destination expression)
_LIVE_SOURCES = {
    "plans":         ("domestic", False),
    "abroad_plans":  ("abroad",   True),
    "global_plans":  ("global",   True),
    "content_plans": ("content",  False),
}


def _conn(db_path=None, busy_ms=120000):
    conn = db._connect(db_path)
    conn.execute(f"PRAGMA busy_timeout={int(busy_ms)}")
    return conn


def _log(conn, job, details):
    conn.execute("INSERT INTO maintenance_log (ran_at, job, details) VALUES (?, ?, ?)",
                 (datetime.now().isoformat(timespec="seconds"), job, json.dumps(details, ensure_ascii=False)))


def _mb(path):
    return round(os.path.getsize(path) / 1048576, 1) if os.path.exists(path) else 0.0


# ── change-log retention ─────────────────────────────────────────────────────
def prune_change_logs(retention_days=180, db_path=None, dry_run=False):
    """Delete rows older than retention_days from every *_changes table.
    Returns {table: deleted_count}. Never touches rows without a parseable
    changed_at (they are counted under 'unparseable')."""
    cutoff = (datetime.now() - timedelta(days=int(retention_days))).strftime("%Y-%m-%dT%H:%M:%S")
    out = {"cutoff": cutoff, "dry_run": bool(dry_run)}
    conn = _conn(db_path)
    try:
        for t in CHANGE_TABLES:
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE changed_at < ?", (cutoff,)).fetchone()[0]
            except sqlite3.OperationalError:
                continue  # table not present in this DB
            out[t] = int(n)
            if n and not dry_run:
                conn.execute(f"DELETE FROM {t} WHERE changed_at < ?", (cutoff,))
        if not dry_run:
            _log(conn, "prune", out)
        conn.commit()
    finally:
        conn.close()
    return out


# ── archive thinning (opt-in) ────────────────────────────────────────────────
def thin_archive_snapshots(after_days, keep_weekday=0, db_path=None, dry_run=False):
    """Beyond `after_days`, keep one archive_snapshots row per (carrier, plan_type)
    per ISO week: the row on `keep_weekday` (0=Sunday) or, if that day is
    missing, the earliest row of that week. Returns counts."""
    if not after_days:
        return {"skipped": "archive_thin_after_days not set"}
    cutoff = (datetime.now() - timedelta(days=int(after_days))).strftime("%Y-%m-%d")
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT id, carrier, plan_type, snapshot_date FROM archive_snapshots "
            "WHERE snapshot_date < ? ORDER BY carrier, plan_type, snapshot_date", (cutoff,)
        ).fetchall()
        keep, drop = set(), []
        groups = {}
        for rid, carrier, ptype, sdate in rows:
            d = datetime.strptime(sdate, "%Y-%m-%d")
            # week bucket anchored on the kept weekday (sqlite %w: 0=Sunday)
            wd = int(d.strftime("%w"))
            week_start = d - timedelta(days=(wd - keep_weekday) % 7)
            groups.setdefault((carrier, ptype, week_start.date()), []).append((rid, wd, sdate))
        for key, items in groups.items():
            on_day = [i for i in items if i[1] == keep_weekday]
            chosen = on_day[0] if on_day else items[0]
            keep.add(chosen[0])
            drop.extend(i[0] for i in items if i[0] != chosen[0])
        out = {"cutoff": cutoff, "candidates": len(rows), "kept": len(keep), "deleted": len(drop),
               "dry_run": bool(dry_run)}
        if drop and not dry_run:
            conn.executemany("DELETE FROM archive_snapshots WHERE id = ?", [(i,) for i in drop])
            _log(conn, "thin_archive", out)
        conn.commit()
    finally:
        conn.close()
    return out


# ── personal-data retention ──────────────────────────────────────────────────
# Tables that hold hashed IPs / user agents / contact details. Nothing deleted
# them before 2026-09-11; the privacy policy now states these periods, so keep
# the two in sync (config.json knobs override the defaults).
PERSONAL_RETENTION = {
    # table: (timestamp column, config knob, default days, extra WHERE)
    "esim_events":      ("created_at", "analytics_retention_days", 395, ""),
    "mobile_events":    ("created_at", "analytics_retention_days", 395, ""),
    "guest_events":     ("created_at", "analytics_retention_days", 395, ""),
    "affiliate_clicks": ("clicked_at", "analytics_retention_days", 395, ""),
    "user_activity":    ("created_at", "activity_retention_days", 180, ""),
    "hotel_leads":      ("created_at", "leads_retention_days", 730, ""),
    # finished reminders (plan_end sent / unsubscribed rows are hard-deleted already)
    "mobile_reminders": ("created_at", "reminders_done_retention_days", 90, " AND done = 1"),
}


def prune_personal_data(config=None, db_path=None, dry_run=False):
    """Delete personal-data rows past their retention period. Returns
    {table: deleted_or_would_delete_count, ...}."""
    config = config or {}
    out = {"dry_run": bool(dry_run)}
    conn = _conn(db_path)
    try:
        for table, (col, knob, default_days, extra) in PERSONAL_RETENTION.items():
            days = int(config.get(knob, default_days))
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
            # created_at is written both as naive local ISO and as UTC ISO ("+00:00")
            # across tables; string comparison on the date prefix is what we need.
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} < ?{extra}", (cutoff,)).fetchone()[0]
            except sqlite3.OperationalError:
                continue
            out[table] = int(n)
            if n and not dry_run:
                conn.execute(f"DELETE FROM {table} WHERE {col} < ?{extra}", (cutoff,))
        if not dry_run:
            _log(conn, "prune_personal", out)
        conn.commit()
    finally:
        conn.close()
    return out


# ── VACUUM ───────────────────────────────────────────────────────────────────
def vacuum(db_path=None):
    """Rewrite the DB file to reclaim freed pages. Needs a brief exclusive lock,
    so it runs at 03:00 on the first Sunday of the month (see run_weekly)."""
    path = db_path or db.DB_PATH
    before = _mb(path)
    t0 = time.time()
    conn = sqlite3.connect(path, timeout=300)
    try:
        conn.execute("PRAGMA busy_timeout=300000")
        conn.execute("VACUUM")
    finally:
        conn.close()
    out = {"before_mb": before, "after_mb": _mb(path), "secs": round(time.time() - t0, 1)}
    conn = _conn(db_path)
    try:
        _log(conn, "vacuum", out)
        conn.commit()
    finally:
        conn.close()
    return out


# ── price_history_daily ──────────────────────────────────────────────────────
def _aggregate(plans, plan_type, dest_from_extras):
    """plans: iterable of (carrier, price, data_gb, extras_json_or_list).

    Two granularities, both small enough to keep forever:
      (carrier, '')       - per-carrier stats across all of its plans
      ('*',  destination) - MARKET stats per destination across every carrier
                            (abroad/global only) + which carrier had the min.
    A full (carrier, destination) matrix was tried first: ~5,700 global pairs
    per day = 570K rows for 5 months = the table alone doubled the DB.
    Returns {(carrier, destination): {min,max,sum,n,min_ppgb,min_carrier}}."""
    acc = {}

    def bump(key, price, gb, carrier):
        a = acc.setdefault(key, {"min": price, "max": price, "sum": 0.0, "n": 0,
                                 "min_ppgb": None, "min_carrier": carrier})
        if price < a["min"]:
            a["min"] = price
            a["min_carrier"] = carrier
        a["max"] = max(a["max"], price)
        a["sum"] += price
        a["n"] += 1
        if gb is not None and gb >= 1:
            ppgb = price / gb
            a["min_ppgb"] = ppgb if a["min_ppgb"] is None else min(a["min_ppgb"], ppgb)

    for carrier, price, data_gb, extras in plans:
        if price is None:
            continue
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        try:
            gb = float(data_gb) if data_gb is not None else None
        except (TypeError, ValueError):
            gb = None
        carrier = carrier or ""
        bump((carrier, ""), price, gb, carrier)
        if dest_from_extras:
            if isinstance(extras, str):
                try:
                    extras = json.loads(extras)
                except ValueError:
                    extras = []
            dest = (extras[0] if isinstance(extras, list) and extras and isinstance(extras[0], str) else "") or ""
            if dest:
                bump(("*", dest), price, gb, carrier)
    return acc


def _upsert_daily(conn, day, plan_type, acc, source):
    rows = [(day, plan_type, carrier, dest, round(a["min"], 2), round(a["sum"] / a["n"], 2),
             round(a["max"], 2), round(a["min_ppgb"], 3) if a["min_ppgb"] is not None else None,
             a["n"], source, a["min_carrier"])
            for (carrier, dest), a in acc.items()]
    conn.executemany("""
        INSERT INTO price_history_daily
            (day, plan_type, carrier, destination, min_price, avg_price, max_price, min_ppgb, plan_count, source, min_carrier)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(day, plan_type, carrier, destination) DO UPDATE SET
            min_carrier = CASE WHEN excluded.min_price < price_history_daily.min_price
                               THEN excluded.min_carrier ELSE price_history_daily.min_carrier END,
            min_price  = MIN(price_history_daily.min_price, excluded.min_price),
            max_price  = MAX(price_history_daily.max_price, excluded.max_price),
            avg_price  = excluded.avg_price,
            min_ppgb   = CASE WHEN price_history_daily.min_ppgb IS NULL THEN excluded.min_ppgb
                              WHEN excluded.min_ppgb IS NULL THEN price_history_daily.min_ppgb
                              ELSE MIN(price_history_daily.min_ppgb, excluded.min_ppgb) END,
            plan_count = excluded.plan_count,
            source     = excluded.source
    """, rows)
    return len(rows)


def build_price_history_daily(day=None, db_path=None):
    """Aggregate the LIVE plan tables into price_history_daily for `day`
    (default today). Idempotent; a second run the same day only lowers mins."""
    day = day or datetime.now().strftime("%Y-%m-%d")
    conn = _conn(db_path)
    written = {}
    try:
        for table, (ptype, dest_from_extras) in _LIVE_SOURCES.items():
            try:
                rows = conn.execute(f"SELECT carrier, price, data_gb, extras FROM {table}").fetchall()
            except sqlite3.OperationalError:
                if table == "content_plans":
                    try:
                        rows = [(r[0], r[1], None, None) for r in
                                conn.execute("SELECT carrier, price FROM content_plans").fetchall()]
                    except sqlite3.OperationalError:
                        continue
                else:
                    continue
            acc = _aggregate(rows, ptype, dest_from_extras)
            written[ptype] = _upsert_daily(conn, day, ptype, acc, "live")
        _log(conn, "price_history", {"day": day, **written})
        conn.commit()
    finally:
        conn.close()
    return {"day": day, **written}


def backfill_price_history_from_archive(from_date=None, db_path=None, overwrite=False):
    """Rebuild price_history_daily from archive_snapshots (one compressed catalog
    per carrier/type/day since 2026-04). Skips days already present unless
    overwrite=True. Content prices in the archive are free-text and skipped."""
    conn = _conn(db_path)
    days_done = 0
    rows_written = 0
    try:
        q = "SELECT carrier, plan_type, snapshot_date, plans_json FROM archive_snapshots"
        params = ()
        if from_date:
            q += " WHERE snapshot_date >= ?"
            params = (from_date,)
        q += " ORDER BY snapshot_date, plan_type, carrier"
        existing = set()
        if not overwrite:
            existing = {(r[0], r[1]) for r in
                        conn.execute("SELECT DISTINCT day, plan_type FROM price_history_daily WHERE source='live'")}
        cur = conn.execute(q)
        seen_days = set()
        for carrier, ptype, sdate, blob in cur:
            if ptype == "content" or (sdate, ptype) in existing:
                continue
            try:
                plans = json.loads(db._archive_decode(blob))
            except Exception as exc:
                logger.warning(f"archive decode failed {carrier}/{ptype}/{sdate}: {exc}")
                continue
            dest_from_extras = ptype in ("abroad", "global")
            acc = _aggregate(((p.get("carrier") or carrier, p.get("price"), p.get("data_gb"), p.get("extras"))
                              for p in plans if isinstance(p, dict)), ptype, dest_from_extras)
            rows_written += _upsert_daily(conn, sdate, ptype, acc, "archive")
            seen_days.add((sdate, ptype))
        days_done = len(seen_days)
        _log(conn, "price_history", {"backfill": True, "from": from_date, "days": days_done, "rows": rows_written})
        conn.commit()
    finally:
        conn.close()
    return {"days": days_done, "rows": rows_written}


def get_price_history_daily(plan_type, carrier=None, destination=None, from_day=None, to_day=None,
                            db_path=None, limit=5000):
    """Read API for charts: list of dicts ordered by day.
    carrier='*' + destination = market-wide series for that destination."""
    sql = "SELECT day, carrier, destination, min_price, avg_price, max_price, min_ppgb, plan_count, min_carrier FROM price_history_daily WHERE plan_type = ?"
    params = [plan_type]
    if carrier:
        sql += " AND carrier = ?"; params.append(carrier)
    if destination is not None:
        sql += " AND destination = ?"; params.append(destination)
    if from_day:
        sql += " AND day >= ?"; params.append(from_day)
    if to_day:
        sql += " AND day <= ?"; params.append(to_day)
    sql += " ORDER BY day ASC, carrier ASC, destination ASC LIMIT ?"
    params.append(int(limit))
    conn = _conn(db_path)
    try:
        cols = ["day", "carrier", "destination", "min_price", "avg_price", "max_price", "min_ppgb", "plan_count", "min_carrier"]
        return [dict(zip(cols, r)) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ── job entry points (APScheduler) ───────────────────────────────────────────
def run_daily(config=None, db_path=None):
    return build_price_history_daily(db_path=db_path)


def run_weekly(config=None, db_path=None, dry_run=None, force_vacuum=False, now=None):
    """Sunday 03:00: prune change logs, optional archive thinning, VACUUM on the
    first Sunday of the month. Returns a report dict (also logged)."""
    config = config or {}
    if dry_run is None:
        dry_run = bool(config.get("maintenance_dry_run", False))
    now = now or datetime.now()
    report = {"dry_run": dry_run, "started": now.isoformat(timespec="seconds")}
    report["prune"] = prune_change_logs(int(config.get("changes_retention_days", 180)), db_path=db_path, dry_run=dry_run)
    report["personal"] = prune_personal_data(config, db_path=db_path, dry_run=dry_run)
    thin_days = config.get("archive_thin_after_days")
    if thin_days:
        report["thin_archive"] = thin_archive_snapshots(int(thin_days), int(config.get("archive_keep_weekday", 0)),
                                                        db_path=db_path, dry_run=dry_run)
    first_sunday = now.weekday() == 6 and now.day <= 7
    if (force_vacuum or first_sunday) and config.get("db_vacuum_enabled", True) and not dry_run:
        try:
            report["vacuum"] = vacuum(db_path=db_path)
        except Exception as exc:
            report["vacuum"] = {"error": str(exc)}
    report["db_mb"] = _mb(db_path or db.DB_PATH)
    logger.info(f"DB maintenance: {json.dumps(report, ensure_ascii=False)}")
    return report
