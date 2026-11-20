"""Holafly: the whole shop is read in ONE request shared by both scrapers, and a
site that answers 429 to everything ends the run within a handful of requests."""
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
    holafly._holafly_catalog["by_handle"] = None
    yield
    holafly._holafly_429_streak[0] = 0
    holafly._holafly_blocked_until[0] = 0.0
    holafly._holafly_catalog["by_handle"] = None


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
    # no fixed-price rows any more: a blocked run must leave every row to age,
    # or MAX(scraped_at) keeps saying the carrier is fresh
    assert regions == []


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


def test_one_catalog_request_serves_both_scrapers(monkeypatch):
    calls = []

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    catalog = {"products": [
        {"handle": "esim-france", "variants": [
            {"sku": "esim-france-1-day", "price": "3.79"},
            {"sku": "esim-france-2-days", "price": "7.58"},      # not a key duration
            {"sku": "esim-france-7-days", "price": "26.90"},
        ]},
        {"handle": "esim-europe", "variants": [{"sku": "esim-europe-10-days", "price": "36.90"}]},
        {"handle": "test-ipad", "variants": [{"sku": "x-5-days", "price": "1.00"}]},
        # a handle that is not "esim-<slug>", a destination without a slug, a live region
        {"handle": "esim-kenia", "variants": [{"sku": "esim-kenia-30-days", "price": "116.90"}]},
        {"handle": "esim-iraq", "variants": [{"sku": "esim-iraq-1-day", "price": "6.90"}]},
        {"handle": "africa-actualizado", "variants": [{"sku": "esim-africa-7-days", "price": "38.90"}]},
        {"handle": "caribbean-cruise", "variants": [
            {"sku": "esim-caribbean-cruise-7-days", "price": "36.90", "available": True},
            {"sku": "esim-caribbean-cruise-10-days", "price": "49.90", "available": False},
        ]},
    ]}

    def fake(req, timeout=None):
        calls.append(req.full_url)
        return _Resp(json.dumps(catalog).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    countries = holafly.scrape_holafly_global(usd_rate=3.0)
    regions = holafly.scrape_holafly_regions(usd_rate=3.0)
    assert calls == [holafly._HOLAFLY_CATALOG_URL.format(page=1)]
    by_dest = {}
    for p in countries:
        by_dest.setdefault(p["extras"][0], []).append(p["original_price"])
    assert by_dest == {
        holafly.HOLAFLY_SLUG_TO_HEBREW["france"]: [3.79, 26.9],
        holafly.HOLAFLY_SLUG_TO_HEBREW["kenya"]: [116.9],
        holafly._HOLAFLY_EXTRA_COUNTRIES["esim-iraq"]: [6.9],
    }
    assert {p["extras"][0]: p["original_price"] for p in regions} == {
        holafly.HOLAFLY_REGIONS["esim-europe"]: 36.9,
        holafly.HOLAFLY_REGIONS["africa-actualizado"]: 38.9,
        holafly.HOLAFLY_REGIONS["caribbean-cruise"]: 36.9,      # the unavailable duration is dropped
    }


def test_cruise_products_reach_the_cruise_fold():
    import db
    cruises = [heb for handle, heb in holafly.HOLAFLY_REGIONS.items() if handle.endswith("-cruise")]
    assert len(cruises) == 4
    for heb in cruises:
        assert heb.startswith(db._CRUISE_DEST_HE)        # what the frontend's isCruiseDest matches
        assert heb in db._CRUISE_SOURCE_DESTS            # what the public cruise destination unions


def test_every_handle_is_asked_once():
    handles = [h for h, _ in holafly._holafly_country_handles()]
    assert len(handles) == len(set(handles))
    assert not set(handles) & set(holafly.HOLAFLY_REGIONS)
    heb = [name for _, name in holafly._holafly_country_handles()]
    assert len(heb) == len(set(heb))      # two handles on one name would collide on plan_name
