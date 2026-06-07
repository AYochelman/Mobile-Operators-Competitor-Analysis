"""
Integration tests for scraper.py — require live internet connection.
Run with: pytest tests/test_scraper.py -m integration -v
Skipped by default in normal test runs.
"""
import pytest
from playwright.sync_api import sync_playwright


def _browser_page():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    return p, browser, page


@pytest.mark.integration
def test_partner_returns_plans():
    from scraper import scrape_partner
    p, browser, page = _browser_page()
    try:
        plans = scrape_partner(page)
    finally:
        browser.close(); p.stop()
    assert len(plans) >= 2
    assert all(pl["carrier"] == "partner" for pl in plans)
    assert all(isinstance(pl["plan_name"], str) and pl["plan_name"] for pl in plans)
    assert any(pl["price"] is not None for pl in plans)


@pytest.mark.integration
def test_pelephone_returns_plans():
    from scraper import scrape_pelephone
    p, browser, page = _browser_page()
    try:
        plans = scrape_pelephone(page)
    finally:
        browser.close(); p.stop()
    assert len(plans) >= 2
    assert all(pl["carrier"] == "pelephone" for pl in plans)
    assert any(pl["price"] is not None for pl in plans)


@pytest.mark.integration
def test_hotmobile_returns_plans():
    from scraper import scrape_hotmobile
    p, browser, page = _browser_page()
    try:
        plans = scrape_hotmobile(page)
    finally:
        browser.close(); p.stop()
    assert len(plans) >= 2
    assert all(pl["carrier"] == "hotmobile" for pl in plans)
    assert any(pl["price"] is not None for pl in plans)


@pytest.mark.integration
def test_cellcom_returns_plans():
    from scraper import scrape_cellcom
    p, browser, page = _browser_page()
    try:
        plans = scrape_cellcom(page)
    finally:
        browser.close(); p.stop()
    assert len(plans) >= 2
    assert all(pl["carrier"] == "cellcom" for pl in plans)
    assert any(pl["price"] is not None for pl in plans)


@pytest.mark.integration
def test_019_returns_plans():
    from scraper import scrape_019
    # scrape_019 ignores any passed page and starts its OWN stealth Playwright
    # session (019 sits behind Incapsula). Opening a sync_playwright here as well
    # would put a second concurrent sync session in the same thread, which raises
    # "Sync API inside the asyncio loop" — so call it with no browser of our own.
    plans = scrape_019()
    assert len(plans) >= 2
    assert all(pl["carrier"] == "mobile019" for pl in plans)
    assert any(pl["price"] is not None for pl in plans)


@pytest.mark.integration
def test_scrape_all_covers_all_carriers():
    from scraper import scrape_all
    plans = scrape_all()
    carriers = {pl["carrier"] for pl in plans}
    assert "partner"   in carriers
    assert "pelephone" in carriers
    assert "hotmobile" in carriers
    assert "cellcom"   in carriers
    assert "mobile019" in carriers
    assert len(plans) >= 10


def test_run_parallel_scraper_success():
    """_run_parallel_scraper returns (name, list) on success."""
    from scraper import _run_parallel_scraper
    name, result = _run_parallel_scraper("test_fn", lambda: [{"carrier": "x"}])
    assert name == "test_fn"
    assert result == [{"carrier": "x"}]


def test_run_parallel_scraper_exception():
    """_run_parallel_scraper returns (name, []) and does not raise on exception."""
    from scraper import _run_parallel_scraper
    def _bad():
        raise RuntimeError("boom")
    name, result = _run_parallel_scraper("bad_fn", _bad)
    assert name == "bad_fn"
    assert result == []


def test_run_parallel_scraper_empty():
    """_run_parallel_scraper returns (name, []) when fn returns empty list."""
    from scraper import _run_parallel_scraper
    name, result = _run_parallel_scraper("empty_fn", lambda: [])
    assert name == "empty_fn"
    assert result == []


def test_scrape_all_global_merges_parallel_and_sequential(monkeypatch):
    """scrape_all_global merges results from both the sequential (shared-page)
    and parallel (self-contained) scraper groups.

    Hermetic by construction: every provider scraper (scrape_*) is stubbed by
    name-pattern — NOT a hardcoded list — so the test never touches the network
    and stays correct as the provider roster grows or shrinks. Each stub returns
    one plan tagged with its own function name, so we can assert that a
    representative of BOTH groups was merged into the final list.
    """
    import scraper

    # Stub every provider scraper to return a single plan tagged with its name.
    # Excludes the orchestrators themselves (scrape_all / scrape_all_global).
    for attr in dir(scraper):
        if not attr.startswith("scrape_") or attr in ("scrape_all", "scrape_all_global"):
            continue
        if not callable(getattr(scraper, attr)):
            continue
        monkeypatch.setattr(
            scraper, attr,
            lambda *a, _n=attr, **k: [{
                "carrier": _n, "plan_name": _n, "price": 1,
                "data_gb": 1, "days": 7, "extras": [],
            }],
        )

    # Fake Playwright so no real browser launches, and stub all FX lookups so no
    # live currency calls happen (the sequential group shares this fake page).
    class _FakePage:
        pass
    class _FakeBrowser:
        def new_page(self, **kw): return _FakePage()
        def close(self): pass
    class _FakeP:
        chromium = type("C", (), {"launch": staticmethod(lambda **kw: _FakeBrowser())})()
    class _FakePW:
        def __enter__(self): return _FakeP()
        def __exit__(self, *a): pass
    monkeypatch.setattr(scraper, "sync_playwright", lambda: _FakePW())
    monkeypatch.setattr(scraper, "_get_usd_to_ils", lambda: 3.7)
    monkeypatch.setattr(scraper, "_get_eur_to_ils", lambda: 4.0)
    monkeypatch.setattr(scraper, "_get_gbp_to_ils", lambda: 4.7)

    plans = scraper.scrape_all_global()
    carriers = {p["carrier"] for p in plans}

    # A representative of each group must be present → both groups were merged.
    assert "scrape_tuki_global" in carriers    # sequential (shared-page) job
    assert "scrape_saily_global" in carriers   # parallel (self-contained) job
    # Both groups together contribute many jobs; the exact count tracks the live
    # roster, so assert a robust lower bound instead of a brittle equality.
    assert len(plans) >= 20
