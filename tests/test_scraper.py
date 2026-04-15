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
    p, browser, page = _browser_page()
    try:
        plans = scrape_019(page)
    finally:
        browser.close(); p.stop()
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
    """scrape_all_global merges results from both sequential and parallel groups."""
    import scraper

    seq_plan = {"carrier": "tuki", "plan_name": "T", "price": 10,
                "data_gb": 1, "days": 7, "extras": []}
    par_plan = {"carrier": "saily", "plan_name": "S", "price": 20,
                "data_gb": 2, "days": 30, "extras": []}

    def _fake_seq(page, *a, **kw):
        return [seq_plan]

    def _fake_par(*a, **kw):
        return [par_plan]

    for fn in ["scrape_tuki_global", "scrape_tuki_regions", "scrape_tuki_local",
               "scrape_globalesim_global", "scrape_globalesim_regions",
               "scrape_airalo_global", "scrape_pelephone_globalsim",
               "scrape_esimo_global", "scrape_simtlv_global", "scrape_world8_global"]:
        monkeypatch.setattr(scraper, fn, _fake_seq)

    for fn in ["scrape_xphone_global", "scrape_saily_global", "scrape_saily_regions",
               "scrape_esimio_destinations", "scrape_esimio_regions",
               "scrape_holafly_global", "scrape_holafly_regions",
               "scrape_sparks_global", "scrape_voye_global",
               "scrape_orbit_global", "scrape_travelsim"]:
        monkeypatch.setattr(scraper, fn, _fake_par)

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

    plans = scraper.scrape_all_global()

    # 10 sequential × 1 plan + 11 parallel × 1 plan = 21 plans
    assert len(plans) == 21
    carriers = {p["carrier"] for p in plans}
    assert "tuki" in carriers
    assert "saily" in carriers
