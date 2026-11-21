"""Budget block of /api/usage/summary: local vs official (Admin Cost API) spend."""
import app
from api import usage


def _setup(monkeypatch, cfg, local, official):
    """local: {since_iso_or_None: cost}; official: total_usd or None (no admin key)."""
    monkeypatch.setattr(app, "load_config", lambda: cfg)
    monkeypatch.setattr(
        app, "get_claude_spend",
        lambda since_iso=None, db_path=None: {
            "cost_usd": local.get(since_iso, 0.0), "calls": 3, "first_call_at": None})
    seen = {}

    def fake_official(starting_at, ending_at=None, force=False):
        seen["starting_at"] = starting_at
        if official is None:
            return {"configured": False, "total_usd": None}
        return {"configured": True, "total_usd": official}

    monkeypatch.setattr(usage, "_fetch_anthropic_cost_usd", fake_official)
    return seen


SUMMARY = {"by_day": [], "total": {"cost_usd": 0}, "window_days": 30}


def test_local_spend_without_admin_key(monkeypatch):
    _setup(monkeypatch, {"claude_budget_usd": 20, "claude_budget_as_of": "2026-06-01"},
           {"2026-06-01T00:00:00+00:00": 5.0}, None)
    b = usage._claude_budget_block(SUMMARY, None)
    assert b["source"] == "local"
    assert b["remaining_usd"] == 15.0
    assert b["computed_at"]


def test_official_spend_wins_for_a_date_baseline(monkeypatch):
    seen = _setup(monkeypatch, {"claude_budget_usd": 20, "claude_budget_as_of": "2026-06-01"},
                  {"2026-06-01T00:00:00+00:00": 5.0}, 8.0)
    b = usage._claude_budget_block(SUMMARY, None)
    assert b["source"] == "anthropic"
    assert b["remaining_usd"] == 12.0
    assert seen["starting_at"] == "2026-06-01T00:00:00Z"


def test_sync_timestamp_does_not_deduct_spend_before_the_sync(monkeypatch):
    ts = "2026-11-21T10:00:00+00:00"
    # 3.0 logged that day, of which 1.0 after the sync; the official day total is 3.5
    # (0.5 from another key) -> 3.5 - 2.0 spent before the sync = 1.5 since the sync
    _setup(monkeypatch, {"claude_budget_usd": 10, "claude_budget_as_of": ts},
           {ts: 1.0, "2026-11-21T00:00:00+00:00": 3.0}, 3.5)
    b = usage._claude_budget_block(SUMMARY, None)
    assert b["source"] == "anthropic"
    assert b["remaining_usd"] == 8.5


def test_sync_timestamp_keeps_local_when_official_lags(monkeypatch):
    ts = "2026-11-21T10:00:00+00:00"
    _setup(monkeypatch, {"claude_budget_usd": 10, "claude_budget_as_of": ts},
           {ts: 1.0, "2026-11-21T00:00:00+00:00": 3.0}, 2.5)
    b = usage._claude_budget_block(SUMMARY, None)
    assert b["source"] == "local"
    assert b["remaining_usd"] == 9.0


def test_no_budget(monkeypatch):
    _setup(monkeypatch, {}, {}, None)
    assert usage._claude_budget_block(SUMMARY, None) == {
        "configured": False, "total_usd": None, "as_of": None}
