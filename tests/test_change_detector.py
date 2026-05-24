from change_detector import detect_changes

OLD = [
    {"carrier": "partner", "plan_name": "60GB", "price": 59,
     "data_gb": 60, "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 79,
     "data_gb": 100, "extras": []},
    {"carrier": "pelephone", "plan_name": "OLD_PLAN", "price": 55,
     "data_gb": 50, "extras": []},
    {"carrier": "pelephone", "plan_name": "PELEPHONE_KEEP", "price": 70,
     "data_gb": 60, "extras": []},
]

NEW = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,       # price dropped
     "data_gb": 60, "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 79,      # unchanged
     "data_gb": 100, "extras": []},
    {"carrier": "partner", "plan_name": "ללא הגבלה", "price": 89, # new plan
     "data_gb": None, "extras": []},
    # pelephone OLD_PLAN removed; PELEPHONE_KEEP stays so the carrier has ≥1
    # plan in the new scrape and the removed-plan guard fires for OLD_PLAN.
    {"carrier": "pelephone", "plan_name": "PELEPHONE_KEEP", "price": 70,
     "data_gb": 60, "extras": []},
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


def test_per_group_guard_skips_missing_country():
    # Saily failed to scrape ברוניי this round but Argentina was fine.
    # Without the guard, the ברוניי plan would be falsely marked removed.
    old = [
        {"carrier": "saily", "plan_name": "ברוניי – 1GB – 7 ימים",
         "price": 37.67, "extras": ["ברוניי"]},
        {"carrier": "saily", "plan_name": "ארגנטינה – 1GB – 7 ימים",
         "price": 12.0, "extras": ["ארגנטינה"]},
    ]
    new = [
        {"carrier": "saily", "plan_name": "ארגנטינה – 1GB – 7 ימים",
         "price": 12.0, "extras": ["ארגנטינה"]},
    ]
    removed = [c for c in detect_changes(old, new, per_group_extras=True)
               if c["change_type"] == "removed_plan"]
    assert removed == []


def test_per_group_guard_still_detects_real_removal_within_group():
    # If the group WAS present in the new scrape but a specific plan vanished,
    # we still want the removal to fire (this is a real change, not a partial scrape).
    old = [
        {"carrier": "saily", "plan_name": "ארגנטינה – 1GB – 7 ימים",
         "price": 12.0, "extras": ["ארגנטינה"]},
        {"carrier": "saily", "plan_name": "ארגנטינה – 3GB – 30 ימים",
         "price": 20.0, "extras": ["ארגנטינה"]},
    ]
    new = [
        {"carrier": "saily", "plan_name": "ארגנטינה – 1GB – 7 ימים",
         "price": 12.0, "extras": ["ארגנטינה"]},
    ]
    removed = [c for c in detect_changes(old, new, per_group_extras=True)
               if c["change_type"] == "removed_plan"]
    assert len(removed) == 1
    assert removed[0]["plan_name"] == "ארגנטינה – 3GB – 30 ימים"


def test_per_group_guard_off_keeps_legacy_behavior():
    # Default per_group_extras=False — must keep the existing carrier-level guard.
    old = [
        {"carrier": "saily", "plan_name": "ברוניי – 1GB – 7 ימים",
         "price": 37.67, "extras": ["ברוניי"]},
        {"carrier": "saily", "plan_name": "ארגנטינה – 1GB – 7 ימים",
         "price": 12.0, "extras": ["ארגנטינה"]},
    ]
    new = [
        {"carrier": "saily", "plan_name": "ארגנטינה – 1GB – 7 ימים",
         "price": 12.0, "extras": ["ארגנטינה"]},
    ]
    removed = [c for c in detect_changes(old, new)
               if c["change_type"] == "removed_plan"]
    assert len(removed) == 1
    assert removed[0]["plan_name"] == "ברוניי – 1GB – 7 ימים"
