# Tests for the morning changes-check automation:
#   db.get_recent_changes_summary / db.get_scrape_freshness
#   notifier.format_morning_digest
from datetime import datetime, timedelta

import pytest

from db import (init_db, save_plans, save_changes, save_abroad_changes,
                get_recent_changes_summary, get_scrape_freshness)
from notifier import format_morning_digest


@pytest.fixture
def tmp_db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(db_path=path)
    return path


def test_recent_changes_summary_has_all_categories(tmp_db):
    summary = get_recent_changes_summary(db_path=tmp_db)
    assert set(summary.keys()) == {"domestic", "abroad", "global", "content"}
    assert all(v == [] for v in summary.values())


def test_recent_changes_summary_filters_by_window(tmp_db):
    old_ts = (datetime.now() - timedelta(days=3)).isoformat()
    save_changes([
        {"carrier": "pelephone", "plan_name": "מונדיאל", "change_type": "new_plan",
         "old_val": None, "new_val": "59"},
        {"carrier": "partner", "plan_name": "ישן", "change_type": "removed_plan",
         "old_val": "49", "new_val": None, "changed_at": old_ts},
    ], db_path=tmp_db)
    summary = get_recent_changes_summary(within_hours=26, db_path=tmp_db)
    assert len(summary["domestic"]) == 1
    assert summary["domestic"][0]["plan_name"] == "מונדיאל"


def test_recent_changes_summary_includes_abroad(tmp_db):
    save_abroad_changes([
        {"carrier": "cellcom", "plan_name": "ארה\"ב 10GB", "change_type": "price_change",
         "old_val": "99", "new_val": "89"},
    ], db_path=tmp_db)
    summary = get_recent_changes_summary(db_path=tmp_db)
    assert len(summary["abroad"]) == 1
    assert summary["domestic"] == []


def test_scrape_freshness_counts_and_timestamps(tmp_db):
    save_plans([
        {"carrier": "partner", "plan_name": "60GB", "price": 49,
         "data_gb": 60, "minutes": "unlimited", "extras": []},
        {"carrier": "partner", "plan_name": "100GB", "price": 69,
         "data_gb": 100, "minutes": "unlimited", "extras": []},
    ], db_path=tmp_db)
    fresh = get_scrape_freshness(db_path=tmp_db)
    assert set(fresh.keys()) == {"domestic", "abroad", "global", "content"}
    partner = next(r for r in fresh["domestic"] if r["carrier"] == "partner")
    assert partner["count"] == 2
    assert partner["last_scraped"]  # populated by save_plans
    assert fresh["abroad"] == []


def test_digest_no_changes_is_explicit():
    msg = format_morning_digest({"domestic": [], "abroad": [], "global": [], "content": []})
    assert "לא זוהו שינויים" in msg
    assert "MOCA" in msg


def test_digest_lists_new_plan_with_carrier_name():
    summary = {"domestic": [
        {"carrier": "pelephone", "plan_name": "מונדיאל 2026", "change_type": "new_plan",
         "old_val": None, "new_val": "59", "changed_at": datetime.now().isoformat()},
    ], "abroad": [], "global": [], "content": []}
    msg = format_morning_digest(summary)
    assert "פלאפון" in msg
    assert "מונדיאל 2026" in msg
    assert "חבילה חדשה" in msg
    assert "₪59" in msg


def test_digest_price_change_arrow_direction():
    summary = {"domestic": [
        {"carrier": "partner", "plan_name": "100GB", "change_type": "price_change",
         "old_val": "69", "new_val": "59", "changed_at": datetime.now().isoformat()},
    ], "abroad": [], "global": [], "content": []}
    msg = format_morning_digest(summary)
    assert "↘" in msg  # price went down


def test_digest_caps_lines_per_category():
    many = [
        {"carrier": "partner", "plan_name": f"plan-{i}", "change_type": "removed_plan",
         "old_val": "49", "new_val": None, "changed_at": datetime.now().isoformat()}
        for i in range(20)
    ]
    msg = format_morning_digest({"domestic": many, "abroad": [], "global": [], "content": []})
    assert "ועוד 5" in msg


def test_digest_freshness_warnings_section():
    warnings = [
        {"carrier": "pelephone", "category": "domestic", "count": 0,
         "last_scraped": None, "hours_ago": None},
        {"carrier": "cellcom", "category": "abroad", "count": 5,
         "last_scraped": "2026-06-01T08:00:00", "hours_ago": 72.0},
    ]
    msg = format_morning_digest(
        {"domestic": [], "abroad": [], "global": [], "content": []}, warnings)
    assert "⚠️" in msg
    assert "0 חבילות" in msg
    assert "72 שעות" in msg
