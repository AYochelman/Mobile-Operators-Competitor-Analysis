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

    DETAIL_FIELDS = {
        "days":    "ימים",
        "data_gb": "גלישה",
        "minutes": "דקות",
        "sms":     "SMS",
    }

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
            # Detect changes in detail fields (days, data_gb, minutes, sms)
            changed = []
            for field, label in DETAIL_FIELDS.items():
                old_v = old_plan.get(field)
                new_v = new_plan.get(field)
                if (old_v is not None or new_v is not None) and old_v != new_v:
                    changed.append((label, old_v, new_v))
            if changed:
                old_desc = ", ".join(f"{lb}: {o}" for lb, o, _ in changed)
                new_desc = ", ".join(f"{lb}: {n}" for lb, _, n in changed)
                changes.append({
                    "carrier": key[0], "plan_name": key[1],
                    "change_type": "details_change",
                    "old_val": old_desc, "new_val": new_desc
                })

    # carriers that returned ≥1 plan in the new scrape
    carriers_with_new_data = {p["carrier"] for p in new_plans}

    for key in old_map:
        if key not in new_map:
            # Guard: if scraper returned 0 plans for this carrier, skip removal.
            # This prevents false "removed" badges when Incapsula / bot-detection
            # blocks the scraper and it returns an empty list.
            if key[0] not in carriers_with_new_data:
                continue
            changes.append({
                "carrier": key[0], "plan_name": key[1],
                "change_type": "removed_plan",
                "old_val": old_map[key].get("price"), "new_val": None
            })

    return changes


def detect_content_changes(old_plans, new_plans):
    """
    Compare content service plans.
    Returns list of change dicts:
      {service, carrier, change_type, old_val, new_val}
    change_type: 'price_change' | 'trial_change' | 'new_service'
    """
    old_map = {(p["service"], p["carrier"]): p for p in old_plans}
    changes = []
    bad = ("לא נמצא", "שגיאה", "לא זמין")

    for plan in new_plans:
        key     = (plan["service"], plan["carrier"])
        price   = plan.get("price")
        trial   = plan.get("free_trial")
        old     = old_map.get(key)

        if not old:
            if price and price not in bad:
                changes.append({"service": plan["service"], "carrier": plan["carrier"],
                                 "change_type": "new_service", "old_val": None, "new_val": price})
            continue

        old_price = old.get("price")
        old_trial = old.get("free_trial")

        if old_price and old_price != price and price not in bad:
            changes.append({"service": plan["service"], "carrier": plan["carrier"],
                             "change_type": "price_change",
                             "old_val": old_price, "new_val": price})

        if old_trial and trial and old_trial != trial:
            changes.append({"service": plan["service"], "carrier": plan["carrier"],
                             "change_type": "trial_change",
                             "old_val": old_trial, "new_val": trial})

    return changes
