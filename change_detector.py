def detect_changes(old_plans, new_plans):
    """
    Compare two lists of plan dicts.
    Returns list of change dicts:
      {carrier, plan_name, change_type, old_val, new_val}
    change_type: 'price_change' | 'new_plan' | 'removed_plan' | 'extras_change'
    """
    old_map = {(p["carrier"], p["plan_name"]): p for p in old_plans}
    new_map = {(p["carrier"], p["plan_name"]): p for p in new_plans}
    changes = []

    for key, new_plan in new_map.items():
        if key not in old_map:
            changes.append({
                "carrier": key[0], "plan_name": key[1],
                "change_type": "new_plan",
                "old_val": None, "new_val": new_plan.get("price")
            })
        else:
            old_plan = old_map[key]
            if old_plan.get("price") != new_plan.get("price"):
                changes.append({
                    "carrier": key[0], "plan_name": key[1],
                    "change_type": "price_change",
                    "old_val": old_plan.get("price"),
                    "new_val": new_plan.get("price")
                })
            old_extras = sorted(old_plan.get("extras") or [])
            new_extras = sorted(new_plan.get("extras") or [])
            if old_extras != new_extras:
                changes.append({
                    "carrier": key[0], "plan_name": key[1],
                    "change_type": "extras_change",
                    "old_val": old_extras, "new_val": new_extras
                })

    for key in old_map:
        if key not in new_map:
            changes.append({
                "carrier": key[0], "plan_name": key[1],
                "change_type": "removed_plan",
                "old_val": old_map[key].get("price"), "new_val": None
            })

    return changes
