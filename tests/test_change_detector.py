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
    # pelephone OLD_PLAN removed — pelephone must still appear in NEW for the
    # removal-guard to allow detection (guard skips removal when a carrier
    # returned 0 plans, to avoid Incapsula-block false positives).
    {"carrier": "pelephone", "plan_name": "OTHER_PLAN", "price": 60,
     "data_gb": 100, "extras": []},
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
    # Filter for the specific plan under test — NEW now also contains a
    # pelephone placeholder plan so the removal guard can fire (see
    # test_removal_guard_skips_when_carrier_returned_zero_plans). That
    # placeholder is itself a new_plan, but unrelated to this assertion.
    target = [c for c in new_plans if c["plan_name"] == "ללא הגבלה"]
    assert len(target) == 1
    assert target[0]["new_val"] == 89

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


def test_removal_guard_skips_when_carrier_returned_zero_plans():
    """When a carrier returns 0 plans (e.g. blocked by Incapsula), removed_plan
    must NOT be emitted — otherwise every retry would report a fresh wave of
    fake removals. See change_detector.detect_changes:carriers_with_new_data."""
    old = [
        {"carrier": "pelephone", "plan_name": "P1", "price": 50, "extras": []},
        {"carrier": "pelephone", "plan_name": "P2", "price": 60, "extras": []},
    ]
    new = []  # scraper got blocked
    changes = detect_changes(old, new)
    removed = [c for c in changes if c["change_type"] == "removed_plan"]
    assert removed == [], "removal guard should suppress removals when carrier returned 0 plans"


def test_removal_emitted_when_carrier_returned_other_plans():
    """Conversely, if a carrier did return plans but a specific plan is missing,
    that plan IS a real removal."""
    old = [
        {"carrier": "pelephone", "plan_name": "OLD_PLAN", "price": 50, "extras": []},
    ]
    new = [
        {"carrier": "pelephone", "plan_name": "DIFFERENT_PLAN", "price": 60, "extras": []},
    ]
    changes = detect_changes(old, new)
    removed = [c for c in changes if c["change_type"] == "removed_plan"]
    assert len(removed) == 1
    assert removed[0]["plan_name"] == "OLD_PLAN"
