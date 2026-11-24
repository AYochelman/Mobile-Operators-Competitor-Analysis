"""Competitive reaction map: who moves after whom.

Pure functions over the change log (no Flask, no scraping). A "move" is a day
on which a carrier changed something a customer can see - a price, a launch or
a removal - in any tracked category (domestic rate card, roaming packages,
below-the-line reseller offers, content services). For every ordered pair
(leader, follower) the map counts how many of the leader's moves were followed
by a move of the follower within `window` days, and compares that with how
often the follower moves anyway.

What this is NOT: proof of cause. Two carriers that both move a lot will follow
each other by chance, which is exactly why every cell carries its case count,
the rate expected by chance, a p-value and a `reliable` flag. The market has a
move every two days or so, which makes "B moved within two weeks of A" mostly
what chance predicts - the endpoint says so instead of printing a percentage.

Used by GET /api/history/reactions (api/history.py). Tests: tests/test_reactions.py.
"""
from datetime import date, datetime, timedelta
from math import comb
from statistics import median

CATEGORIES = ("domestic", "abroad", "resellers", "content")
MOVE_TYPES = ("price_change", "new_plan", "removed_plan")
# A plan that disappears and comes back within this many days was a scrape
# hiccup, not a commercial decision (and the other way round).
FLAP_DAYS = 3
MIN_LEADER_MOVES = 5     # below this a leader's row is "not enough data"
MIN_FOLLOWED = 3         # ...and so is a cell with fewer DISTINCT follower moves
# A pair is reported as a pattern only when chance alone would produce it less
# than 1 time in 100. The bar is strict on purpose: ~90 ordered pairs are tested
# at once, so at 5% several would "pass" on noise alone.
P_SIGNIFICANT = 0.01


def _binom_tail(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0 or p >= 1:
        return 1.0
    return min(1.0, sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def _day(ts):
    try:
        return datetime.fromisoformat(str(ts)[:19]).date()
    except (TypeError, ValueError):
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def drop_flaps(rows, flap_days=FLAP_DAYS):
    """Remove launch/removal pairs of the SAME plan that undo each other within
    `flap_days`, and price changes that return to where they started."""
    by_plan = {}
    for i, r in enumerate(rows):
        key = (r.get("category"), r.get("reseller_id"), r.get("carrier"), r.get("plan_name"))
        by_plan.setdefault(key, []).append(i)
    dead = set()
    for idxs in by_plan.values():
        idxs = [i for i in idxs if rows[i].get("change_type") in MOVE_TYPES and _day(rows[i].get("changed_at"))]
        idxs.sort(key=lambda i: str(rows[i]["changed_at"]))
        prev = None
        for i in idxs:
            if prev is not None and prev not in dead:
                a, b = rows[prev], rows[i]
                gap = (_day(b["changed_at"]) - _day(a["changed_at"])).days
                kinds = {a["change_type"], b["change_type"]}
                undo_launch = kinds == {"new_plan", "removed_plan"}
                undo_price = (kinds == {"price_change"} and _num(a.get("old_val")) is not None
                              and _num(a.get("old_val")) == _num(b.get("new_val")))
                if gap <= flap_days and (undo_launch or undo_price):
                    dead.update((prev, i))
                    prev = None
                    continue
            prev = i
    return [r for i, r in enumerate(rows) if i not in dead]


def build_moves(rows, categories=CATEGORIES, hidden_carrier=None):
    """Change-log rows → {carrier: {day: {category: [kinds]}}} of move-days."""
    rows = [r for r in rows
            if r.get("category") in categories and r.get("change_type") in MOVE_TYPES
            and r.get("carrier") and r.get("carrier") != hidden_carrier]
    moves = {}
    for r in drop_flaps(rows):
        d = _day(r.get("changed_at"))
        if d is None:
            continue
        kind = r["change_type"]
        if kind == "price_change":
            o, n = _num(r.get("old_val")), _num(r.get("new_val"))
            if o is None or n is None or o == n:
                continue
            kind = "price_down" if n < o else "price_up"
        moves.setdefault(r["carrier"], {}).setdefault(d, {}).setdefault(r["category"], [])
        if kind not in moves[r["carrier"]][d][r["category"]]:
            moves[r["carrier"]][d][r["category"]].append(kind)
    return moves


def reaction_map(rows, days=180, window=14, today=None, categories=CATEGORIES, hidden_carrier=None):
    """The whole payload for the reaction card.

    Returns {days, window, from, to, total_moves, carriers: [...], pairs: [...],
             reliable_pairs, note}.
      carriers: {carrier, moves, initiated, followed, by_category, last_move}
        initiated = moves with no OTHER carrier moving in the `window` days before
      pairs:    {leader, follower, leader_moves, followed, follower_moves, rate,
                 expected, lift, median_lag, p_value, enough, reliable}
        rate     = followed / leader_moves
        expected = share of all days on which the follower moves within the
                   next `window` days anyway (the chance rate)
        lift     = rate / expected (None when expected is 0)
        enough   = enough cases to test at all
        reliable = enough AND chance alone explains it less than 1 time in 100
    """
    today = today or date.today()
    start = today - timedelta(days=days)
    moves = build_moves(rows, categories=categories, hidden_carrier=hidden_carrier)
    moves = {c: {d: v for d, v in ds.items() if start <= d <= today} for c, ds in moves.items()}
    moves = {c: ds for c, ds in moves.items() if ds}
    all_days = {c: sorted(ds) for c, ds in moves.items()}

    carriers = []
    for c, ds in all_days.items():
        others = sorted(d for o, od in all_days.items() if o != c for d in od)
        initiated = sum(1 for d in ds if not any(0 < (d - x).days <= window for x in others))
        by_cat = {}
        for d in ds:
            for cat in moves[c][d]:
                by_cat[cat] = by_cat.get(cat, 0) + 1
        carriers.append({"carrier": c, "moves": len(ds), "initiated": initiated,
                         "followed": len(ds) - initiated, "by_category": by_cat,
                         "last_move": ds[-1].isoformat()})
    carriers.sort(key=lambda r: (-r["moves"], r["carrier"]))

    pairs = []
    # Every day that still has a full window after it - the leader's countable
    # moves and the chance rate are both measured on these days only.
    horizon = [start + timedelta(days=i) for i in range((today - start).days - window + 1)]
    for a, a_all in all_days.items():
        # A leader move too close to the end of the log has no full window after
        # it yet - counting it as "not followed" would understate every rate.
        a_days = [d for d in a_all if (today - d).days >= window]
        if not a_days:
            continue
        for b, b_days in all_days.items():
            if a == b:
                continue
            lags, used = [], set()
            for d in a_days:
                hit = next((x for x in b_days if 0 < (x - d).days <= window), None)
                if hit is not None:
                    lags.append((hit - d).days)
                    used.add(hit)
            if not lags:
                continue
            # Chance: on what share of ALL days does the follower move within the
            # next `window` days anyway? Measured, so clustered moves count once.
            expected = (sum(1 for d in horizon if any(0 < (x - d).days <= window for x in b_days))
                        / len(horizon)) if horizon else 0.0
            rate = len(lags) / len(a_days)
            enough = len(a_days) >= MIN_LEADER_MOVES and len(used) >= MIN_FOLLOWED
            p_value = _binom_tail(len(lags), len(a_days), expected)
            pairs.append({
                "leader": a, "follower": b, "leader_moves": len(a_days), "followed": len(lags),
                "follower_moves": len(used),
                "rate": round(rate, 3), "expected": round(expected, 3),
                "lift": round(rate / expected, 2) if expected > 0 else None,
                "median_lag": median(lags), "p_value": round(p_value, 4),
                "enough": enough, "reliable": enough and p_value < P_SIGNIFICANT,
            })
    pairs.sort(key=lambda p: (not p["reliable"], not p["enough"], p["p_value"], -p["followed"]))
    return {
        "days": days, "window": window, "from": start.isoformat(), "to": today.isoformat(),
        "total_moves": sum(c["moves"] for c in carriers),
        "carriers": carriers, "pairs": pairs,
        "reliable_pairs": sum(1 for p in pairs if p["reliable"]),
        "tested_pairs": sum(1 for p in pairs if p["enough"]),
        "min_leader_moves": MIN_LEADER_MOVES, "min_followed": MIN_FOLLOWED,
        "p_significant": P_SIGNIFICANT,
    }
