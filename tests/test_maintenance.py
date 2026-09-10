import json
import sqlite3
import zlib
from datetime import datetime, timedelta

import pytest

from db import init_db, _connect
import maintenance as m


@pytest.fixture
def dbp(tmp_path):
    p = str(tmp_path / "m.db")
    init_db(db_path=p)
    return p


def _ins_change(p, table, changed_at, carrier="partner", name="P", ctype="price_change"):
    conn = _connect(p)
    col = "service" if table == "content_changes" else "plan_name"
    conn.execute(f"INSERT INTO {table} (carrier, {col}, change_type, old_val, new_val, changed_at) VALUES (?,?,?,?,?,?)",
                 (carrier, name, ctype, "1", "2", changed_at))
    conn.commit(); conn.close()


def _count(p, table):
    conn = _connect(p)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_prune_deletes_only_old_rows(dbp):
    old = (datetime.now() - timedelta(days=200)).isoformat()
    new = (datetime.now() - timedelta(days=10)).isoformat()
    _ins_change(dbp, "global_changes", old)
    _ins_change(dbp, "global_changes", new)
    _ins_change(dbp, "changes", old)
    rep = m.prune_change_logs(180, db_path=dbp, dry_run=True)
    assert rep["global_changes"] == 1 and rep["changes"] == 1
    assert _count(dbp, "global_changes") == 2          # dry run deleted nothing
    rep = m.prune_change_logs(180, db_path=dbp)
    assert rep["global_changes"] == 1
    assert _count(dbp, "global_changes") == 1
    assert _count(dbp, "changes") == 0
    assert _count(dbp, "maintenance_log") == 1


def test_price_history_daily_from_live_tables(dbp):
    conn = _connect(dbp)
    conn.executemany("INSERT INTO plans (carrier, plan_name, price, data_gb, minutes, extras) VALUES (?,?,?,?,?,?)", [
        ("partner", "A", 49, 100, "unlimited", "[]"),
        ("partner", "B", 29, 20, "unlimited", "[]"),
        ("pelephone", "C", 55, 50, "unlimited", "[]"),
    ])
    conn.executemany("INSERT INTO global_plans (carrier, plan_name, price, data_gb, days, extras, currency, original_price, esim) VALUES (?,?,?,?,?,?,?,?,?)", [
        ("saily", "יפן – 5GB – 7 ימים", 30.0, 5, 7, json.dumps(["יפן"]), "USD", 8.1, 1),
        ("saily", "יפן – 10GB – 30 ימים", 50.0, 10, 30, json.dumps(["יפן"]), "USD", 13.5, 1),
        ("saily", "ללא מחיר", None, 10, 30, json.dumps(["יפן"]), "USD", None, 1),
    ])
    conn.commit(); conn.close()
    rep = m.build_price_history_daily(day="2026-09-10", db_path=dbp)
    assert rep["domestic"] == 2 and rep["global"] == 2      # saily row + market row for יפן
    rows = m.get_price_history_daily("domestic", carrier="partner", db_path=dbp)
    assert rows == [{"day": "2026-09-10", "carrier": "partner", "destination": "", "min_price": 29.0,
                     "avg_price": 39.0, "max_price": 49.0, "min_ppgb": 0.49, "plan_count": 2,
                     "min_carrier": "partner"}]
    g = m.get_price_history_daily("global", carrier="saily", db_path=dbp)[0]
    assert g["destination"] == "" and g["min_price"] == 30.0 and g["plan_count"] == 2 and g["min_ppgb"] == 5.0
    mkt = m.get_price_history_daily("global", carrier="*", destination="יפן", db_path=dbp)[0]
    assert mkt["min_price"] == 30.0 and mkt["min_carrier"] == "saily" and mkt["plan_count"] == 2
    # second run the same day only lowers the min (idempotent upsert)
    conn = _connect(dbp); conn.execute("UPDATE plans SET price = 19 WHERE plan_name = 'B'"); conn.commit(); conn.close()
    m.build_price_history_daily(day="2026-09-10", db_path=dbp)
    rows = m.get_price_history_daily("domestic", carrier="partner", db_path=dbp)
    assert len(rows) == 1 and rows[0]["min_price"] == 19.0


def test_backfill_from_archive_snapshots(dbp):
    plans = [{"carrier": "airalo", "plan_name": "x", "price": 40, "data_gb": 3, "days": 7, "extras": ["יוון"]},
             {"carrier": "airalo", "plan_name": "y", "price": 20, "data_gb": 1, "days": 7, "extras": ["יוון"]}]
    blob = zlib.compress(json.dumps(plans).encode("utf-8"))
    conn = _connect(dbp)
    conn.execute("INSERT INTO archive_snapshots (carrier, plan_type, snapshot_date, plans_json, content_hash) VALUES (?,?,?,?,?)",
                 ("airalo", "global", "2026-05-01", blob, "h1"))
    conn.execute("INSERT INTO archive_snapshots (carrier, plan_type, snapshot_date, plans_json, content_hash) VALUES (?,?,?,?,?)",
                 ("airalo", "global", "2026-05-02", json.dumps(plans), "h2"))   # legacy uncompressed row
    conn.commit(); conn.close()
    rep = m.backfill_price_history_from_archive(db_path=dbp)
    assert rep["days"] == 2 and rep["rows"] == 4              # 2 days x (carrier row + market row)
    rows = m.get_price_history_daily("global", carrier="*", destination="יוון", db_path=dbp)
    assert [r["day"] for r in rows] == ["2026-05-01", "2026-05-02"]
    assert rows[0]["min_price"] == 20.0 and rows[0]["max_price"] == 40.0 and rows[0]["min_carrier"] == "airalo"


def test_thin_archive_keeps_one_per_week(dbp):
    conn = _connect(dbp)
    start = datetime(2026, 4, 5)   # a Sunday
    for i in range(21):            # 3 weeks of daily snapshots, all older than cutoff
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        conn.execute("INSERT INTO archive_snapshots (carrier, plan_type, snapshot_date, plans_json, content_hash) VALUES (?,?,?,?,?)",
                     ("partner", "domestic", d, "[]", f"h{i}"))
    conn.commit(); conn.close()
    rep = m.thin_archive_snapshots(after_days=30, keep_weekday=0, db_path=dbp, dry_run=True)
    assert rep["candidates"] == 21 and rep["kept"] == 3 and rep["deleted"] == 18
    assert _count(dbp, "archive_snapshots") == 21
    m.thin_archive_snapshots(after_days=30, keep_weekday=0, db_path=dbp)
    conn = _connect(dbp)
    left = [r[0] for r in conn.execute("SELECT snapshot_date FROM archive_snapshots ORDER BY snapshot_date")]
    conn.close()
    assert left == ["2026-04-05", "2026-04-12", "2026-04-19"]   # the Sundays
    assert m.thin_archive_snapshots(after_days=None, db_path=dbp).get("skipped")


def test_run_weekly_vacuums_only_first_sunday(dbp, monkeypatch):
    calls = []
    monkeypatch.setattr(m, "vacuum", lambda db_path=None: calls.append(1) or {"before_mb": 1, "after_mb": 1})
    m.run_weekly({}, db_path=dbp, now=datetime(2026, 9, 13))   # 2nd Sunday of Sept 2026
    assert calls == []
    m.run_weekly({}, db_path=dbp, now=datetime(2026, 9, 6))    # 1st Sunday
    assert calls == [1]
    m.run_weekly({"db_vacuum_enabled": False}, db_path=dbp, now=datetime(2026, 10, 4))
    assert calls == [1]
    rep = m.run_weekly({"maintenance_dry_run": True}, db_path=dbp, now=datetime(2026, 10, 4))
    assert rep["dry_run"] and calls == [1]
