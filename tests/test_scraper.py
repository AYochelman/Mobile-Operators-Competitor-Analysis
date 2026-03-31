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
