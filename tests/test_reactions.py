"""Reaction map (reactions.py): flap removal, move-days, pair statistics."""
from datetime import date

import reactions


def _row(carrier, day, kind="new_plan", plan="p", cat="domestic", old=None, new=None):
    return {"category": cat, "carrier": carrier, "plan_name": plan, "change_type": kind,
            "old_val": old, "new_val": new, "changed_at": f"{day}T07:31:00"}


def test_launch_then_removal_within_three_days_is_a_flap():
    rows = [_row("a", "2026-06-01", "removed_plan"), _row("a", "2026-06-02", "new_plan"),
            _row("a", "2026-06-20", "new_plan", plan="other")]
    kept = reactions.drop_flaps(rows)
    assert [r["plan_name"] for r in kept] == ["other"]


def test_price_round_trip_is_a_flap_but_a_real_change_is_kept():
    rows = [_row("a", "2026-06-01", "price_change", old="30", new="35"),
            _row("a", "2026-06-02", "price_change", old="35", new="30"),
            _row("a", "2026-07-01", "price_change", plan="q", old="30", new="25")]
    kept = reactions.drop_flaps(rows)
    assert len(kept) == 1 and kept[0]["plan_name"] == "q"


def test_moves_ignore_extras_changes_global_and_the_hidden_carrier():
    rows = [_row("a", "2026-06-01", "extras_change"),
            _row("a", "2026-06-02", cat="global"),
            _row("b", "2026-06-03"),
            _row("c", "2026-06-04", "price_change", old="10", new="8")]
    moves = reactions.build_moves(rows, hidden_carrier="b")
    assert set(moves) == {"c"}
    assert moves["c"][date(2026, 6, 4)] == {"domestic": ["price_down"]}


def test_pair_counts_rate_and_reliability():
    rows = []
    # Leader "a" moves 5 times, 20 days apart; "b" follows 3 days later 4 times.
    for i, day in enumerate(("2026-06-01", "2026-06-21", "2026-07-11", "2026-07-31", "2026-08-20")):
        rows.append(_row("a", day, plan=f"a{i}"))
    for i, day in enumerate(("2026-06-04", "2026-06-24", "2026-07-14", "2026-08-03")):
        rows.append(_row("b", day, plan=f"b{i}", cat="abroad"))
    out = reactions.reaction_map(rows, days=120, window=14, today=date(2026, 9, 20))
    ab = next(p for p in out["pairs"] if p["leader"] == "a" and p["follower"] == "b")
    assert (ab["leader_moves"], ab["followed"], ab["median_lag"]) == (5, 4, 3)
    assert ab["rate"] == 0.8 and ab["enough"] is True and ab["follower_moves"] == 4
    assert ab["lift"] > 1.5 and 0 < ab["p_value"] < 0.2
    a = next(c for c in out["carriers"] if c["carrier"] == "a")
    assert a["moves"] == 5 and a["by_category"] == {"domestic": 5}
    assert out["total_moves"] == 9


def test_leader_moves_without_a_full_window_after_them_are_not_counted():
    rows = [_row("a", "2026-09-15"), _row("b", "2026-09-01")]
    out = reactions.reaction_map(rows, days=60, window=14, today=date(2026, 9, 20))
    assert not [p for p in out["pairs"] if p["leader"] == "a"]


def test_few_cases_are_never_reliable():
    rows = [_row("a", "2026-06-01"), _row("b", "2026-06-03", plan="x")]
    out = reactions.reaction_map(rows, days=120, window=14, today=date(2026, 9, 20))
    assert out["pairs"] and not out["pairs"][0]["reliable"] and out["reliable_pairs"] == 0


def test_one_follower_move_cannot_count_as_three_follow_ups():
    # Three leader moves in a row all "followed" by the SAME single move of b.
    rows = [_row("a", d, plan=f"a{i}") for i, d in enumerate(
        ("2026-06-01", "2026-06-03", "2026-06-05", "2026-07-01", "2026-07-20"))]
    rows.append(_row("b", "2026-06-08", plan="b0"))
    out = reactions.reaction_map(rows, days=120, window=14, today=date(2026, 9, 20))
    ab = next(p for p in out["pairs"] if p["leader"] == "a" and p["follower"] == "b")
    assert ab["followed"] == 3 and ab["follower_moves"] == 1 and ab["enough"] is False


def test_a_strong_repeated_pattern_is_reliable():
    rows = []
    for i in range(8):
        d = date(2026, 3, 1).toordinal() + i * 21
        rows.append(_row("a", date.fromordinal(d).isoformat(), plan=f"a{i}"))
        rows.append(_row("b", date.fromordinal(d + 2).isoformat(), plan=f"b{i}"))
    out = reactions.reaction_map(rows, days=180, window=4, today=date(2026, 8, 20))
    ab = next(p for p in out["pairs"] if p["leader"] == "a" and p["follower"] == "b")
    assert ab["followed"] == 8 and ab["reliable"] is True and ab["median_lag"] == 2
