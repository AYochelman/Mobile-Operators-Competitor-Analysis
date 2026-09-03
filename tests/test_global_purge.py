"""Guarded purge of stale global_plans rows (db.purge_stale_global_rows).

save_global_plans never deletes, so a provider's discontinued tiers/destinations
accumulate forever. The purge deletes them only when the fresh scrape looks
complete for that carrier - judged against the rows + destinations the DB saw
for it within a rolling window - and only rows unseen for longer than the grace
period.
"""
import sqlite3
from datetime import datetime, timedelta

import pytest

from db import (init_db, save_global_plans, get_global_plans,
                purge_stale_global_rows, get_global_changes)

CARRIER = "prov"
OTHER = "other_prov"
KNOBS = dict(grace_hours=48, window_days=30, min_ratio=0.9, min_rows=2)


@pytest.fixture
def tmp_db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(db_path=path)
    return path


def _plan(carrier, name, dest, price=10.0):
    return {"carrier": carrier, "plan_name": f"{dest} – {name}", "price": price,
            "currency": "USD", "original_price": price / 3.7, "days": 7,
            "data_gb": 5, "extras": [dest]}


def _catalog(carrier, n=10):
    """n plans, one per destination (dest_0..dest_{n-1})."""
    return [_plan(carrier, "5GB 7d", f"dest_{i}") for i in range(n)]


def _backdate(db_path, carrier, days, names=None):
    """Age the carrier's rows (all, or just `names`) by `days`."""
    conn = sqlite3.connect(db_path)
    ts = (datetime.now() - timedelta(days=days)).isoformat()
    if names is None:
        conn.execute("UPDATE global_plans SET scraped_at=? WHERE carrier=?", (ts, carrier))
    else:
        for n in names:
            conn.execute("UPDATE global_plans SET scraped_at=? WHERE carrier=? AND plan_name=?",
                         (ts, carrier, n))
    conn.commit()
    conn.close()


def _names(db_path, carrier):
    return {p["plan_name"] for p in get_global_plans(carrier=carrier, db_path=db_path)}


def _seed_catalog(db_path, n=10, age_days=5):
    """A full catalog last seen `age_days` ago: past the 48h grace, inside the
    30-day window (i.e. still part of the completeness baseline)."""
    save_global_plans(_catalog(CARRIER, n), db_path=db_path)
    save_global_plans(_catalog(OTHER, 4), db_path=db_path)
    _backdate(db_path, CARRIER, age_days)
    _backdate(db_path, OTHER, age_days)


def test_full_coverage_purges_dropped_plan(tmp_db):
    _seed_catalog(tmp_db)
    fresh = _catalog(CARRIER, 10)[:9]          # provider dropped dest_9 -> 90% coverage
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db, **KNOBS)

    r = report[CARRIER]
    assert r["decision"] == "purged"
    assert r["purged"] == 1 and r["stale"] == 1 and r["eligible"] == 1
    assert r["baseline_rows"] == 10 and r["ratio_rows"] == 0.9
    assert _names(tmp_db, CARRIER) == {p["plan_name"] for p in fresh}
    # A carrier that did not appear in this scrape is never touched.
    assert OTHER not in report
    assert len(_names(tmp_db, OTHER)) == 4


def test_partial_coverage_does_not_purge(tmp_db):
    _seed_catalog(tmp_db)
    fresh = _catalog(CARRIER, 10)[:5]          # only half the catalog came back
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db, **KNOBS)

    r = report[CARRIER]
    assert r["decision"].startswith("partial-rows (0.50")
    assert r["purged"] == 0
    assert r["stale"] == 5 and r["eligible"] == 5     # eligible by age, blocked by coverage
    assert len(_names(tmp_db, CARRIER)) == 10


def test_empty_scrape_does_not_purge(tmp_db):
    _seed_catalog(tmp_db)
    save_global_plans([], db_path=tmp_db)
    report = purge_stale_global_rows([], db_path=tmp_db, **KNOBS)

    assert report == {}
    assert len(_names(tmp_db, CARRIER)) == 10
    assert len(_names(tmp_db, OTHER)) == 4


def test_old_backlog_ages_out_of_baseline_and_is_purged(tmp_db):
    """The baseline is what the DB saw within the window, not the total row
    count - otherwise a months-old backlog (sparks/tuki/orbit sat at ~51% stale)
    would drag the ratio down and block the purge forever."""
    save_global_plans(_catalog(CARRIER, 20), db_path=tmp_db)
    _backdate(tmp_db, CARRIER, 60)                  # all 20 rows: outside the 30-day window
    fresh = _catalog(CARRIER, 10)
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db, **KNOBS)

    r = report[CARRIER]
    assert r["db_rows"] == 20 and r["baseline_rows"] == 10 and r["ratio_rows"] == 1.0
    assert r["decision"] == "purged" and r["purged"] == 10
    assert len(_names(tmp_db, CARRIER)) == 10


def test_recently_seen_rows_count_in_baseline(tmp_db):
    """A per-country scraper that fetched only half its destinations this run
    (but had them all 5 days ago) is NOT complete, even though nothing in the
    DB is older than the window. Same fixture as the backlog test, aged 5 days."""
    save_global_plans(_catalog(CARRIER, 20), db_path=tmp_db)
    _backdate(tmp_db, CARRIER, 5)
    fresh = _catalog(CARRIER, 10)
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db, **KNOBS)

    r = report[CARRIER]
    assert r["baseline_rows"] == 20 and r["ratio_rows"] == 0.5
    assert r["decision"].startswith("partial-rows") and r["purged"] == 0
    assert len(_names(tmp_db, CARRIER)) == 20


def test_grace_period_spares_recently_seen_rows(tmp_db):
    """A tier that flapped out this run but was seen an hour ago is kept."""
    save_global_plans(_catalog(CARRIER, 10), db_path=tmp_db)
    aged, recent = "dest_8 – 5GB 7d", "dest_9 – 5GB 7d"
    _backdate(tmp_db, CARRIER, 5, names=[aged])          # past grace
    fresh = _catalog(CARRIER, 10)[:8]                      # 8/10 -> use a looser ratio
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db, **{**KNOBS, "min_ratio": 0.8})

    r = report[CARRIER]
    assert r["stale"] == 2 and r["eligible"] == 1 and r["purged"] == 1
    names = _names(tmp_db, CARRIER)
    assert aged not in names                  # aged out -> purged
    assert recent in names                    # inside grace -> spared


def test_destination_coverage_guard(tmp_db):
    """Same row count as the baseline, but the run covers a fraction of the
    destinations the window knows (per-country scraper that got mostly 429s)."""
    save_global_plans(_catalog(CARRIER, 10), db_path=tmp_db)
    _backdate(tmp_db, CARRIER, 5)
    # 10 rows, all for ONE destination (tiers 11..20GB) -> rows 10/20, dests 1/10
    skewed = [_plan(CARRIER, f"{g}GB 7d", "dest_0") for g in range(11, 21)]
    save_global_plans(skewed, db_path=tmp_db)
    report = purge_stale_global_rows(skewed, db_path=tmp_db, **{**KNOBS, "min_ratio": 0.5})

    r = report[CARRIER]
    assert r["ratio_rows"] == 0.5 and r["ratio_dests"] == 0.1
    assert r["decision"].startswith("partial-dests") and r["purged"] == 0
    assert len(_names(tmp_db, CARRIER)) == 20


def test_too_few_rows_guard(tmp_db):
    _seed_catalog(tmp_db)
    fresh = _catalog(CARRIER, 10)[:1]
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db, min_ratio=0.0, min_rows=2,
                                     grace_hours=48)
    assert report[CARRIER]["decision"].startswith("too-few-rows")
    assert len(_names(tmp_db, CARRIER)) == 10


def test_dry_run_and_disabled_override_do_not_delete(tmp_db):
    _seed_catalog(tmp_db)
    fresh = _catalog(CARRIER, 10)[:9]
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db, dry_run=True, **KNOBS)
    assert report[CARRIER]["decision"] == "complete, dry-run"
    assert report[CARRIER]["eligible"] == 1 and report[CARRIER]["purged"] == 0
    report = purge_stale_global_rows(fresh, db_path=tmp_db,
                                     overrides={CARRIER: {"enabled": False}}, **KNOBS)
    assert report[CARRIER]["decision"] == "disabled"
    assert len(_names(tmp_db, CARRIER)) == 10


def test_per_carrier_override_extends_grace(tmp_db):
    """A known-flaky per-country provider needs a longer absence before purge."""
    _seed_catalog(tmp_db, age_days=4)            # 96h old: past 72h, inside 168h
    fresh = _catalog(CARRIER, 10)[:9]
    save_global_plans(fresh, db_path=tmp_db)
    report = purge_stale_global_rows(fresh, db_path=tmp_db,
                                     overrides={CARRIER: {"grace_hours": 168}})
    assert report[CARRIER]["decision"] == "complete, nothing eligible"
    assert len(_names(tmp_db, CARRIER)) == 10


def test_purge_writes_no_change_log_and_cleans_plan_refs(tmp_db):
    _seed_catalog(tmp_db)
    conn = sqlite3.connect(tmp_db)
    conn.executemany(
        "INSERT INTO plan_refs (carrier, plan_name, plan_ref, updated_at) VALUES (?,?,?,?)",
        [(CARRIER, "dest_9 – 5GB 7d", "ref-9", "x"), (CARRIER, "dest_0 – 5GB 7d", "ref-0", "x")])
    conn.commit()
    fresh = _catalog(CARRIER, 10)[:9]
    save_global_plans(fresh, db_path=tmp_db)
    purge_stale_global_rows(fresh, db_path=tmp_db, **KNOBS)

    assert get_global_changes(limit=10, db_path=tmp_db) == []      # no removed_plan noise
    refs = {r[0] for r in conn.execute("SELECT plan_name FROM plan_refs WHERE carrier=?", (CARRIER,))}
    conn.close()
    assert refs == {"dest_0 – 5GB 7d"}
