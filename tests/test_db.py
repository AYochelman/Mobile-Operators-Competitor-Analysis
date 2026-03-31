import os
import pytest
import tempfile
from db import init_db, save_plans, get_plans, save_changes, get_changes

@pytest.fixture
def tmp_db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(db_path=path)
    return path

SAMPLE_PLANS = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,
     "data_gb": 60, "minutes": "unlimited", "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 69,
     "data_gb": 100, "minutes": "unlimited", "extras": []},
    {"carrier": "pelephone", "plan_name": "50GB", "price": 55,
     "data_gb": 50, "minutes": "unlimited", "extras": []},
]

def test_init_creates_tables(tmp_db):
    plans = get_plans(db_path=tmp_db)
    assert plans == []

def test_save_and_get_all_plans(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    plans = get_plans(db_path=tmp_db)
    assert len(plans) == 3

def test_get_plans_filter_by_carrier(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    plans = get_plans(carrier="partner", db_path=tmp_db)
    assert len(plans) == 2
    assert all(p["carrier"] == "partner" for p in plans)

def test_save_plans_upsert(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    updated = [{"carrier": "partner", "plan_name": "60GB", "price": 45,
                "data_gb": 60, "minutes": "unlimited", "extras": []}]
    save_plans(updated, db_path=tmp_db)
    plans = get_plans(carrier="partner", db_path=tmp_db)
    sixty = next(p for p in plans if p["plan_name"] == "60GB")
    assert sixty["price"] == 45  # updated

def test_save_and_get_changes(tmp_db):
    changes = [
        {"carrier": "partner", "plan_name": "60GB",
         "change_type": "price_change", "old_val": "59", "new_val": "49"}
    ]
    save_changes(changes, db_path=tmp_db)
    result = get_changes(db_path=tmp_db)
    assert len(result) == 1
    assert result[0]["change_type"] == "price_change"

def test_get_changes_limit(tmp_db):
    changes = [
        {"carrier": "partner", "plan_name": f"plan{i}",
         "change_type": "new_plan", "old_val": None, "new_val": "49"}
        for i in range(5)
    ]
    save_changes(changes, db_path=tmp_db)
    result = get_changes(limit=3, db_path=tmp_db)
    assert len(result) == 3
