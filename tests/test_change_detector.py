from change_detector import detect_changes

OLD = [
    {"carrier": "partner", "plan_name": "60GB", "price": 59,
     "data_gb": 60, "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 79,
     "data_gb": 100, "extras": []},
    {"carrier": "pelephone", "plan_name": "OLD_PLAN", "price": 55,
     "data_gb": 50, "extras": []},
]

NEW = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,       # price dropped
     "data_gb": 60, "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 79,      # unchanged
     "data_gb": 100, "extras": []},
    {"carrier": "partner", "plan_name": "ללא הגבלה", "price": 89, # new plan
     "data_gb": None, "extras": []},
    # pelephone OLD_PLAN removed
]

def test_no_changes_returns_empty():
    assert detect_changes(OLD[:2], OLD[:2]) == []

def test_detects_price_decrease():
    changes = detect_changes(OLD, NEW)
    price_changes = [c for c in changes if c["change_type"] == "price_change"]
    assert len(price_changes) == 1
    assert price_changes[0]["plan_name"] == "60GB"
    assert price_changes[0]["old_val"] == 59
    assert price_changes[0]["new_val"] == 49

def test_detects_new_plan():
    changes = detect_changes(OLD, NEW)
    new_plans = [c for c in changes if c["change_type"] == "new_plan"]
    assert len(new_plans) == 1
    assert new_plans[0]["plan_name"] == "ללא הגבלה"
    assert new_plans[0]["new_val"] == 89

def test_detects_removed_plan():
    changes = detect_changes(OLD, NEW)
    removed = [c for c in changes if c["change_type"] == "removed_plan"]
    assert len(removed) == 1
    assert removed[0]["plan_name"] == "OLD_PLAN"
    assert removed[0]["carrier"] == "pelephone"

def test_detects_extras_change():
    old = [{"carrier": "partner", "plan_name": "60GB", "price": 49,
            "data_gb": 60, "extras": ["TV Basic"]}]
    new = [{"carrier": "partner", "plan_name": "60GB", "price": 49,
            "data_gb": 60, "extras": ["TV Basic", "Roaming"]}]
    changes = detect_changes(old, new)
    assert len(changes) == 1
    assert changes[0]["change_type"] == "extras_change"

def test_unchanged_plan_produces_no_change():
    plans = [{"carrier": "partner", "plan_name": "60GB", "price": 49,
              "data_gb": 60, "extras": []}]
    assert detect_changes(plans, plans) == []
