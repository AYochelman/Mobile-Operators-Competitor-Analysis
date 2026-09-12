"""simtlv scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


def scrape_simtlv_global(page):
    page.goto(
        "https://simtlv.co.il/global-61-30days/?refg=159162",
        timeout=35000, wait_until="networkidle"
    )
    page.wait_for_timeout(2000)
    plans = []
    for card in page.query_selector_all(".elementor-price-table"):
        name_el    = card.query_selector(".elementor-price-table__heading")
        price_el   = card.query_selector(".elementor-price-table__integer-part")
        period_el  = card.query_selector(".elementor-price-table__period")
        sub_el     = card.query_selector(".elementor-price-table__subheading")
        add_el     = card.query_selector(".elementor-price-table__additional_info")
        feat_els   = card.query_selector_all(".elementor-price-table__features-list li span")
        if not name_el or not price_el:
            continue
        name_text = name_el.inner_text().strip()
        price     = core._parse_price(price_el.inner_text())
        period    = period_el.inner_text().strip() if period_el else ""
        days      = core._parse_days(period)
        gb        = core._parse_gb(name_text)
        if gb is None and sub_el:
            gb = core._parse_gb(sub_el.inner_text())
        # Detect eSIM from additional_info or buy link
        is_esim = bool(add_el and "esim" in (add_el.inner_text() or "").lower())
        btn_el = card.query_selector(".elementor-price-table__button")
        if btn_el:
            href = btn_el.get_attribute("href") or ""
            if "esim" in href.lower():
                is_esim = True
        extras = ["127 מדינות"]
        for f in feat_els:
            t = f.inner_text().strip()
            if t and t not in extras:
                extras.append(t)
        esim_str = "eSIM" if is_esim else "Physical SIM"
        full_name = f"SimTLV {name_text} ({esim_str})"
        if price and gb:
            plans.append(core._make_global_plan(
                "simtlv", full_name, price, "ILS", price,
                gb, days, esim=is_esim, extras=extras
            ))
    logger.info(f"SimTLV global: {len(plans)} plans")
    return plans


# The WooCommerce Store API exposes the whole catalog (~2,400 products) with
# ILS prices. Country pages (/esim/<iso3>) render cards whose data-id equals
# the product id, and every LIVE product follows one of the strict naming
# conventions below; legacy/B2B products (Global Card zones, TopUps, app
# credits, physical SIMs, partner promos) don't match them and are skipped.
# Verified 2026-06-11 against the ita/grc/tha/usa pages: pattern set == page
# card set, no false positives.
#
# SIMTLV_DEST_FIX repairs regex artifacts only: the local pattern strips an
# optional 'ל' prefix ("eSIM לאיטליה" → "איטליה"), which also eats the first
# letter of countries that themselves start with ל ("eSIM לוקסמבורג" →
# "וקסמבורג"). Pure spelling fixes belong in db._DEST_NORM, not here.
SIMTLV_DEST_FIX = {
    "וקסמבורג": "לוקסמבורג",
    "טביה": "לטביה",
    "יטא": "ליטא",
    "יכטנשטיין": "ליכטנשטיין",
    "אוס": "לאוס",
    "סוטו": "לסוטו",
    "יבריה": "ליבריה",
    "רפובליקה הדומיניקנית": "הרפובליקה הדומיניקנית",
    "לרפובליקה הדומיניקנית": "הרפובליקה הדומיניקנית",  # double-ל typo on the site
    "דרום אמריקה ל-11 מדינות": "דרום אמריקה (11 מדינות)",
}


_SIMTLV_RX_UNLIMITED = re.compile(
    r"^eSIM ברשת Tmobile לארצות הברית ללא הגבלה (\d+) יום$"
)


_SIMTLV_RX_EUROPE = re.compile(
    r"^eSIM לאירופה(?: ל-(\d+)(?: מדינות)?)? (\d+(?:\.\d+)?)GB ל-?\s*(\d+) (?:יום|ימים)\s*[–-]\s*כרטיס סים וירטואלי$"
)


_SIMTLV_RX_EUROPE_YR = re.compile(
    r"^eSIM לאירופה ל-(\d+) מדינות (\d+(?:\.\d+)?)GB לשנה\s*[–-]\s*כרטיס סים וירטואלי$"
)


_SIMTLV_RX_GLOBAL_N = re.compile(
    r"^eSIM גלובלי ל-(\d+) מדינות (\d+(?:\.\d+)?)GB ל-?\s*(\d+) (?:יום|ימים)\s*[–-]\s*כרטיס סים וירטואלי$"
)


_SIMTLV_RX_EUR_PKG = re.compile(
    r"^(?:כרטיס|חבילת) eSIM אירופה: (\d+(?:\.\d+)?)GB (ל-\d+ ימים|לשנה|ל-\d+ שנים) ב-(\d+) מדינות$"
)


_SIMTLV_RX_GLOB_PKG = re.compile(
    r"^חבילת eSIM גלובלית: (\d+(?:\.\d+)?)GB (ל-\d+ ימים|לשנה|ל-\d+ שנים) ב-(\d+) מדינות$"
)


_SIMTLV_RX_LOCAL = re.compile(
    # (?i:esim) — the site mixes eSIM/Esim/esim casing on live products
    r"^(?i:esim) ל?(.+?) (\d+(?:\.\d+)?)GB ל-?\s*(\d+) (?:יום|ימים)\s*[–-]\s*כרטיס סים וירטואלי$"
)


def _simtlv_duration(text):
    """'ל-90 ימים' → 90, 'לשנה' → 365, 'ל-5 שנים' → 1825."""
    if text == "לשנה":
        return 365
    m = re.match(r"ל-(\d+) ימים$", text)
    if m:
        return int(m.group(1))
    m = re.match(r"ל-(\d+) שנים$", text)
    if m:
        return int(m.group(1)) * 365
    return None


def _simtlv_classify(name):
    """Classify a normalized catalog product name.

    Returns (dest, gb, days, note) for live store packages, None for
    everything else (legacy/B2B/physical/credit products). gb=None means
    unlimited. Patterns are ordered most-specific-first so the regional
    products don't fall through to the generic local pattern.
    """
    m = _SIMTLV_RX_UNLIMITED.match(name)
    if m:
        return ("ארצות הברית", None, int(m.group(1)), "רשת T-Mobile")
    m = _SIMTLV_RX_EUROPE.match(name)
    if m:
        n = m.group(1)
        dest = f"אירופה ({n} מדינות)" if n else "אירופה"
        return (dest, float(m.group(2)), int(m.group(3)), None)
    m = _SIMTLV_RX_EUROPE_YR.match(name)
    if m:
        return (f"אירופה ({m.group(1)} מדינות)", float(m.group(2)), 365, None)
    m = _SIMTLV_RX_GLOBAL_N.match(name)
    if m:
        return (f"גלובלי ({m.group(1)} מדינות)", float(m.group(2)), int(m.group(3)), None)
    m = _SIMTLV_RX_EUR_PKG.match(name)
    if m:
        return (f"אירופה ({m.group(3)} מדינות)", float(m.group(1)), _simtlv_duration(m.group(2)), None)
    m = _SIMTLV_RX_GLOB_PKG.match(name)
    if m:
        return (f"גלובלי ({m.group(3)} מדינות)", float(m.group(1)), _simtlv_duration(m.group(2)), None)
    m = _SIMTLV_RX_LOCAL.match(name)
    if m:
        dest = m.group(1).strip()
        dest = SIMTLV_DEST_FIX.get(dest, dest)
        return (dest, float(m.group(2)), int(m.group(3)), None)
    return None


def _simtlv_fetch_catalog():
    """SimTLV WooCommerce catalog (~2,400 products), via the shared Woo fetcher."""
    return core._woo_store_fetch("https://simtlv.co.il/wp-json/wc/store/v1/products", "SimTLV")


def scrape_simtlv_esim(_page=None):
    """Scrape SimTLV's full per-country/regional eSIM catalog → ~940 plans.

    Pure HTTP, no Playwright. Complements scrape_simtlv_global (the
    127-country bundles on /global-61-30days) — both run every cycle.
    Per-country plans carry the Hebrew country in extras[0]; regional
    products use the 'אירופה (N מדינות)' / 'גלובלי (N מדינות)' labels the
    dashboard knows. Destinations are canonicalized via db._DEST_NORM
    *before* the plan name is built, so plan_name and extras[0] agree
    (the save path re-applies the same mapping — idempotent).
    """
    import html as _html
    from db import _DEST_NORM
    products = _simtlv_fetch_catalog()
    best = {}  # (dest, gb, days) -> (product_id, price, note)
    for prod in products:
        try:
            raw = prod.get("name") or ""
            name = re.sub(
                r"\s+", " ",
                _html.unescape(raw).replace("״", '"').replace("׳", "'")
            ).strip()
            parsed = _simtlv_classify(name)
            if not parsed:
                continue
            dest, gb, days, note = parsed
            dest = _DEST_NORM.get(dest, dest)
            prices = prod.get("prices") or {}
            minor = int(prices.get("currency_minor_unit") or 2)
            price = int(prices.get("price")) / (10 ** minor)
            pid = int(prod.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not days or price <= 0:
            continue
        key = (dest, gb, days)
        # Same package published under two product ids → keep the newest
        if key not in best or pid > best[key][0]:
            best[key] = (pid, price, note)
    plans = []
    for (dest, gb, days), (pid, price, note) in best.items():
        if gb is None:
            size_str = "ללא הגבלה"
        elif gb >= 1:
            size_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        else:
            size_str = f"{round(gb * 1024)}MB"
        plan_name = f"{dest} – {size_str} – {days} ימים"
        extras = [dest] + ([note] if note else [])
        plans.append(core._make_global_plan(
            "simtlv", plan_name, price, "ILS", price,
            gb, days, esim=True, extras=extras
        ))
    logger.info(f"SimTLV eSIM catalog: {len(plans)} plans from {len(products)} products")
    return plans
