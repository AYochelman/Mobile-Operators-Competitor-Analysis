"""Holafly + Breeze read their Shopify listings from the shopify_catalog cache;
the collector fills that cache at the pace the shop allows (about one listing
request per ~20 minutes for our client)."""
import gzip
import json
from datetime import datetime, timedelta, timezone

import pytest

import scraper  # noqa: F401  (loads the scrapers package the way the app does)
import shopify_catalog as sc
from scrapers import breez, holafly


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(sc, "LIVE", False)


def _serve(monkeypatch, catalogs):
    monkeypatch.setattr(sc, "products", lambda key: catalogs.get(key))


# ── Holafly ────────────────────────────────────────────────────────────────

HOLAFLY = [
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
]


def test_holafly_reads_the_cached_listing(monkeypatch):
    _serve(monkeypatch, {"holafly": HOLAFLY})
    by_dest = {}
    for p in holafly.scrape_holafly_global(usd_rate=3.0):
        by_dest.setdefault(p["extras"][0], []).append(p["original_price"])
    assert by_dest == {
        holafly.HOLAFLY_SLUG_TO_HEBREW["france"]: [3.79, 26.9],
        holafly.HOLAFLY_SLUG_TO_HEBREW["kenya"]: [116.9],
        holafly._HOLAFLY_EXTRA_COUNTRIES["esim-iraq"]: [6.9],
    }
    regions = holafly.scrape_holafly_regions(usd_rate=3.0)
    assert {p["extras"][0]: p["original_price"] for p in regions} == {
        holafly.HOLAFLY_REGIONS["esim-europe"]: 36.9,
        holafly.HOLAFLY_REGIONS["africa-actualizado"]: 38.9,
        holafly.HOLAFLY_REGIONS["caribbean-cruise"]: 36.9,      # the unavailable duration is dropped
    }


def test_holafly_without_a_catalog_returns_nothing(monkeypatch):
    # Nothing at all - not even fixed-price rows - so every row ages and the
    # morning freshness check reports the carrier.
    _serve(monkeypatch, {})
    assert holafly.scrape_holafly_global(usd_rate=3.0) == []
    assert holafly.scrape_holafly_regions(usd_rate=3.0) == []


def test_every_holafly_handle_is_asked_once():
    handles = [h for h, _ in holafly._holafly_country_handles()]
    assert len(handles) == len(set(handles))
    assert not set(handles) & set(holafly.HOLAFLY_REGIONS)
    heb = [name for _, name in holafly._holafly_country_handles()]
    assert len(heb) == len(set(heb))      # two handles on one name would collide on plan_name


def test_cruise_products_reach_the_cruise_fold():
    import db
    cruises = [heb for handle, heb in holafly.HOLAFLY_REGIONS.items() if handle.endswith("-cruise")]
    assert len(cruises) == 4
    for heb in cruises:
        assert heb.startswith(db._CRUISE_DEST_HE)        # what the frontend's isCruiseDest matches
        assert heb in db._CRUISE_SOURCE_DESTS            # what the public cruise destination unions


# ── Breeze ─────────────────────────────────────────────────────────────────

BREEZ_COUNTRY = [{"title": "Canada", "variants": [
    {"sku": "esimd_1GB_7D_CA_V2", "price": "4.50", "available": True},
    {"sku": "esimd_ULE_1D_CA_V2", "price": "3.00", "available": True},
]}]
BREEZ_REGIONAL = [{"title": "North America", "variants": [
    {"sku": "esimd_5GB_30D_RNA_V2", "price": "19.00", "available": True},
]}]


def test_breez_needs_both_collections(monkeypatch):
    _serve(monkeypatch, {"breez_country": BREEZ_COUNTRY, "breez_regional": BREEZ_REGIONAL})
    assert sorted(p["original_price"] for p in breez.scrape_breez_global(usd_rate=3.0)) == [3.0, 4.5, 19.0]
    # half a catalog would look like a complete, smaller one
    _serve(monkeypatch, {"breez_country": BREEZ_COUNTRY})
    assert breez.scrape_breez_global(usd_rate=3.0) == []
    _serve(monkeypatch, {"breez_regional": BREEZ_REGIONAL})
    assert breez.scrape_breez_global(usd_rate=3.0) == []


# ── cache ──────────────────────────────────────────────────────────────────

def _write(key, hours_old, products):
    stamp = (datetime.now(timezone.utc) - timedelta(hours=hours_old)).isoformat(timespec="seconds")
    with gzip.open(sc._path(key), "wt", encoding="utf-8") as f:
        json.dump({"key": key, "fetched_at": stamp, "products": products}, f)


def test_cache_serves_only_a_fresh_listing():
    assert sc.products("holafly") is None                 # never collected
    _write("holafly", 2, HOLAFLY)
    assert len(sc.products("holafly")) == len(HOLAFLY)
    _write("holafly", sc.MAX_AGE_HOURS + 1, HOLAFLY)
    assert sc.products("holafly") is None                 # too old to trust


def test_live_mode_fetches_instead_of_reading_the_cache(monkeypatch):
    _write("holafly", 1, HOLAFLY)
    monkeypatch.setattr(sc, "LIVE", True)
    monkeypatch.setattr(sc, "_get_page", lambda key, page: (200, [{"handle": "live"}], None))
    assert sc.products("holafly") == [{"handle": "live"}]
    monkeypatch.setattr(sc, "_get_page", lambda key, page: (429, [], 60))
    with pytest.raises(sc.RateLimited):
        sc.products("holafly")


# ── the patient collector ──────────────────────────────────────────────────

class _Clock:
    def __init__(self):
        self.t = 0.0
        self.events = []          # ("get", key, t) / ("sleep", seconds)

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.events.append(("sleep", seconds))
        self.t += seconds


def _shop(clock, answers):
    """answers: {key: [status, status, ...]} consumed per request; last one repeats."""
    def get_page(key, page):
        clock.events.append(("get", key, clock.t))
        queue = answers[key]
        status = queue.pop(0) if len(queue) > 1 else queue[0]
        if status == 200:
            return 200, [{"handle": f"{key}-p", "title": key, "variants": []}], None
        return status, [], 60
    return get_page


def _gaps_between_requests(clock):
    times = [e[2] for e in clock.events if e[0] == "get"]
    return [b - a for a, b in zip(times, times[1:])]


def test_collect_spaces_the_three_listings(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(sc, "_get_page", _shop(clock, {k: [200] for k in sc.ORDER}))
    out = sc.collect(sleep=clock.sleep, clock=clock.now)
    assert all(v.startswith("collected") for v in out.values()) and list(out) == list(sc.ORDER)
    assert [e[1] for e in clock.events if e[0] == "get"] == list(sc.ORDER)   # 3 requests, no more
    assert _gaps_between_requests(clock) == [sc.AFTER_SUCCESS_GAP] * 2
    assert all(sc.products(k) for k in sc.ORDER)


def test_collect_waits_out_a_429_and_never_asks_faster(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(sc, "_get_page", _shop(clock, {
        "holafly": [200], "breez_country": [429, 429, 200], "breez_regional": [200]}))
    out = sc.collect(sleep=clock.sleep, clock=clock.now)
    assert out["breez_country"].startswith("collected") and "3 requests" in out["breez_country"]
    assert min(_gaps_between_requests(clock)) >= sc.RETRY_GAP
    assert all(sc.products(k) for k in sc.ORDER)


def test_collect_gives_up_at_the_deadline(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(sc, "_get_page", _shop(clock, {k: [429] for k in sc.ORDER}))
    out = sc.collect(max_minutes=30, sleep=clock.sleep, clock=clock.now)
    assert set(out.values()) == {"rate_limited"}
    requests_made = [e for e in clock.events if e[0] == "get"]
    assert len(requests_made) <= 30 * 60 // sc.RETRY_GAP + 1
    assert clock.t <= 30 * 60
    assert sc.products("holafly") is None


def test_collect_skips_what_is_already_fresh(monkeypatch):
    clock = _Clock()
    _write("holafly", 1, HOLAFLY)
    monkeypatch.setattr(sc, "_get_page", _shop(clock, {k: [200] for k in sc.ORDER}))
    out = sc.collect(sleep=clock.sleep, clock=clock.now)
    assert out["holafly"] == "fresh"
    assert [e[1] for e in clock.events if e[0] == "get"] == ["breez_country", "breez_regional"]


def test_collect_asks_for_the_stalest_source_first(monkeypatch):
    # The first request of a run is the one that reliably passes, so it goes to the
    # source that has waited longest - a fixed order starved breez_regional for days.
    clock = _Clock()
    _write("holafly", 6, HOLAFLY)
    _write("breez_country", 7, BREEZ_COUNTRY)
    _write("breez_regional", 100, BREEZ_REGIONAL)
    monkeypatch.setattr(sc, "_get_page", _shop(clock, {k: [200] for k in sc.ORDER}))
    sc.collect(sleep=clock.sleep, clock=clock.now)
    assert [e[1] for e in clock.events if e[0] == "get"] == ["breez_regional", "breez_country", "holafly"]


def test_collect_records_each_run(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(sc, "_get_page", _shop(clock, {k: [200] for k in sc.ORDER}))
    out = sc.collect(sleep=clock.sleep, clock=clock.now)
    tail = sc._log_tail()
    assert len(tail) == 1 and json.loads(tail[0])["results"] == out


def test_collect_follows_a_second_page(monkeypatch):
    clock = _Clock()
    pages = []

    def get_page(key, page):
        pages.append((key, page, clock.t))
        size = sc.PAGE_SIZE if page == 1 else 3
        return 200, [{"handle": f"{key}-{page}-{i}", "title": "x", "variants": []} for i in range(size)], None

    monkeypatch.setattr(sc, "_get_page", get_page)
    out = sc.collect(sleep=clock.sleep, clock=clock.now, keys=("holafly",))
    assert out["holafly"] == f"collected ({sc.PAGE_SIZE + 3} products, 2 requests)"
    assert pages[1][2] - pages[0][2] == sc.AFTER_SUCCESS_GAP      # the second page costs a full wait too
