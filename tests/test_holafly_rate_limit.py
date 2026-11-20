"""Holafly circuit breaker: a site that answers 429 to everything must end the
scraper within a handful of requests instead of sleeping through ~200 URLs."""
import io
import json
import time
import urllib.error
import urllib.request

import pytest

import scraper  # noqa: F401  (loads the scrapers package)
from scrapers import holafly


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(holafly, "_HOLAFLY_MIN_GAP", 0)
    holafly._holafly_429_streak[0] = 0
    holafly._holafly_blocked_until[0] = 0.0
    yield
    holafly._holafly_429_streak[0] = 0
    holafly._holafly_blocked_until[0] = 0.0


def _always_429(calls):
    def fake(req, timeout=None):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests",
                                     {"Retry-After": "60"}, io.BytesIO(b""))
    return fake


def test_total_throttle_stops_after_a_few_requests(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _always_429(calls))
    plans = holafly.scrape_holafly_global(usd_rate=3.7)
    assert plans == []
    assert len(calls) == holafly._HOLAFLY_MAX_429
    # the second scraper sees the cooldown and asks nothing more
    regions = holafly.scrape_holafly_regions(usd_rate=3.7)
    assert len(calls) == holafly._HOLAFLY_MAX_429
    assert regions  # the hardcoded regions are still returned


def test_cooldown_expires(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", _always_429(calls))
    with pytest.raises(holafly.HolaflyRateLimited):
        for _ in range(3):
            holafly._holafly_get_json("https://example.invalid/a.json")
    holafly._holafly_blocked_until[0] = 0.0   # cooldown over

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp(json.dumps({"ok": 1}).encode()))
    assert holafly._holafly_get_json("https://example.invalid/a.json") == {"ok": 1}


def test_occasional_429_is_still_retried(monkeypatch):
    state = {"n": 0}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        state["n"] += 1
        if state["n"] % 2:      # every other answer is a 429
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests",
                                         {"Retry-After": "1"}, io.BytesIO(b""))
        return _Resp(json.dumps({"product": {"variants": []}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    for _ in range(10):
        assert "product" in holafly._holafly_get_json("https://example.invalid/a.json")
    assert holafly._holafly_blocked_until[0] == 0.0
