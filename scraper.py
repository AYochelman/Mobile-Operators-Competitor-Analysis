"""
Playwright scrapers for 5 Israeli cellular carriers.
Uses sync API. All scrape_* functions take a Playwright Page object.
Returns list of plan dicts:
  {"carrier": str, "plan_name": str, "price": int|None,
   "data_gb": int|None, "minutes": str, "extras": list[str]}
"""
from playwright.sync_api import sync_playwright
import re
import logging

logger = logging.getLogger(__name__)


def _parse_price(text):
    """Extract price from string like '₪49', '34.9', '39.90'. Returns float or None (no rounding)."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    val = float(match.group(1))
    # Return int if whole number, float otherwise
    return int(val) if val == int(val) else val


def _parse_gb(text):
    """Extract GB as int from string like '60GB', '1000 GB', '400'. Returns None if unlimited."""
    if not text:
        return None
    text_lower = text.lower().strip()
    if any(w in text_lower for w in ["ללא", "unlimit", "∞"]):
        return None
    match = re.search(r"(\d+)", text_lower)
    return int(match.group(1)) if match else None


def scrape_all():
    """Scrape all 5 carriers sequentially. Returns flat list of plan dicts."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        plans = []
        for fn in [scrape_partner, scrape_pelephone, scrape_hotmobile, scrape_cellcom, scrape_019]:
            try:
                result = fn(page)
                logger.info(f"{fn.__name__}: {len(result)} plans")
                plans.extend(result)
            except Exception as e:
                logger.error(f"{fn.__name__} failed: {e}", exc_info=True)
        browser.close()
    return plans


def scrape_partner(page):
    page.goto("https://www.partner.co.il/n/cellularsale/lobby", timeout=30000, wait_until="networkidle")
    page.wait_for_selector(".plan-wrapper", timeout=15000)
    plans = []
    for card in page.query_selector_all(".plan-wrapper"):
        name_el  = card.query_selector("h3.title")
        price_el = card.query_selector(".plan-banner .price")
        gb_el    = card.query_selector(".plan-banner .size")
        extras   = list(dict.fromkeys(el.inner_text().strip() for el in card.query_selector_all(".plan-advantages p") if el.inner_text().strip()))
        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        gb    = _parse_gb(gb_el.inner_text())       if gb_el    else None
        if name and name != "לא ידוע":
            plans.append({"carrier": "partner", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": "unlimited", "extras": extras})
    return plans


def scrape_pelephone(page):
    page.goto(
        "https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_selector(".border_5 .item", timeout=15000)
    plans = []
    for card in page.query_selector_all(".border_5 .item"):
        name_el  = card.query_selector(".superlative")
        price_el = card.query_selector(".c")
        gb_el    = card.query_selector(".only_gb")
        extras   = [el.inner_text().strip() for el in card.query_selector_all("ul > li") if el.inner_text().strip()]
        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        gb    = _parse_gb(gb_el.inner_text())       if gb_el    else None
        if name and name != "לא ידוע":
            plans.append({"carrier": "pelephone", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": "unlimited", "extras": extras})
    return plans


def scrape_hotmobile(page):
    page.goto("https://www.hotmobile.co.il/saleslobby", timeout=30000, wait_until="networkidle")
    page.wait_for_selector(".package-wrap.js-plan-filter", timeout=15000)
    plans = []
    for card in page.query_selector_all(".package-wrap.js-plan-filter"):
        name_el  = card.query_selector("h1.name")
        price_el = card.query_selector(".current-price")
        extras   = [el.inner_text().strip() for el in card.query_selector_all(".list-item") if el.inner_text().strip()]
        # GB: first .feature-name containing "GB"
        gb_text = None
        for feat in card.query_selector_all(".feature-name"):
            t = feat.inner_text()
            if "GB" in t or "gb" in t.lower():
                gb_text = t
                break
        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        gb    = _parse_gb(gb_text)
        if name and name != "לא ידוע":
            plans.append({"carrier": "hotmobile", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": "unlimited", "extras": extras})
    return plans


def scrape_cellcom(page):
    page.goto("https://cellcom.co.il/production/Private/Cellular/", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    plans = []
    for card in page.query_selector_all(".package"):
        # Only cellular plan cards
        sale_type = card.get_attribute("data-saletype") or ""
        if sale_type and "cellular" not in sale_type.lower():
            continue
        title_el  = card.query_selector(".header .title p")
        price_el  = card.query_selector(".body-package .content")
        extras    = [el.inner_text().strip() for el in card.query_selector_all(".body-package .header-feature .text") if el.inner_text().strip()]
        # Name and GB share the same element — split on newline
        name, gb_text = "לא ידוע", None
        if title_el:
            parts = [p.strip() for p in title_el.inner_text().split("\n") if p.strip()]
            name    = parts[0] if parts else "לא ידוע"
            gb_text = parts[1] if len(parts) > 1 else None
        price = _parse_price(price_el.inner_text().split("\n")[0]) if price_el else None
        gb    = _parse_gb(gb_text)
        if name and name != "לא ידוע":
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": "unlimited", "extras": extras})
    return plans


def scrape_019(page):
    page.goto("https://019mobile.co.il/חבילות-סלולר/", timeout=30000, wait_until="networkidle")
    page.wait_for_selector(".list .item", timeout=15000)
    plans = []
    for card in page.query_selector_all(".list .item:not(.item_hor)"):
        name_el  = card.query_selector("h3.title")
        price_el = card.query_selector(".price")
        gb_el    = card.query_selector(".blist li strong")
        extras   = [el.inner_text().strip() for el in card.query_selector_all(".blist li") if el.inner_text().strip()]
        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        gb    = _parse_gb(gb_el.inner_text())       if gb_el    else None
        if name and name != "לא ידוע":
            plans.append({"carrier": "mobile019", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": "unlimited", "extras": extras})
    return plans
