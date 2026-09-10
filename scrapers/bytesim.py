"""bytesim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# Per-country handles → Hebrew names.  Derived from SAILY_SLUG_TO_HEBREW with
# two handle differences: ByteSim uses "usa" and "uae" instead of the full names.
BYTESIM_HANDLE_TO_HEBREW = {
    k: v for k, v in core.SAILY_SLUG_TO_HEBREW.items()
    if k not in ("united-states", "united-arab-emirates")
}


BYTESIM_HANDLE_TO_HEBREW["usa"] = core.SAILY_SLUG_TO_HEBREW["united-states"]


BYTESIM_HANDLE_TO_HEBREW["uae"] = core.SAILY_SLUG_TO_HEBREW["united-arab-emirates"]


# Zone/regional product handles → Hebrew zone names used as extras[0]
BYTESIM_ZONE_HANDLES = {
    # handle: (plan_label used in plan_name, canonical KNOWN_REGIONS string for extras[0])
    # Global
    "esim-global":                             ("גלובלי ByteSim – 125 מדינות",         "גלובלי"),
    "esim-global-148":                         ("גלובלי ByteSim – 109 מדינות",         "גלובלי"),
    # Europe
    "europe-esim-unlimited-30-countries-lite": ("אירופה – ByteSim MAX (57 מדינות)",    "אירופה"),
    "europe-esim-max":                         ("אירופה – ByteSim UK+ (45 מדינות)",    "אירופה"),
    "europe-esim-lite":                        ("אירופה – ByteSim לייט (42 מדינות)",   "אירופה"),
    "esim-balkans":                            ("בלקן – ByteSim (12 מדינות)",           "בלקן"),
    # Asia
    "esim-asia":                               ("אסיה – ByteSim (25 מדינות)",           "אסיה"),
    "asia-esim-13-countries":                  ("אסיה פסיפיק – ByteSim (15 מדינות)",   "אסיה פסיפיק"),
    "esim-china-hong-kong-macao":              ("סין, הונג קונג ומקאו – ByteSim",      "סין + הונג קונג + מקאו"),
    # Americas
    "esim-north-america":                      ("צפון אמריקה – ByteSim (3 מדינות)",    "צפון אמריקה"),
    "esim-us-canada":                          ("ארה\"ב וקנדה – ByteSim",               "צפון אמריקה"),
    "esim-south-america":                      ("דרום אמריקה – ByteSim (11 מדינות)",   "אמריקה הלטינית"),
    "south-america-lite":                      ("דרום אמריקה – ByteSim לייט (12 מדינות)", "אמריקה הלטינית"),
    "esim-caribbean":                          ("הקריביים – ByteSim",                  "קריביים"),
    # Middle East & Africa
    "esim-middle-east":                        ("המזרח התיכון – ByteSim",               "המזרח התיכון"),
    "esim-africa":                             ("אפריקה – ByteSim",                    "אפריקה"),
}


def _parse_bytesim_option1(opt1):
    """Parse ByteSim plan option1 ('1GB/Day', 'Total 5GB', 'Unlimited Data').
    Returns (data_gb, data_str_heb)."""
    if not opt1:
        return None, "ללא הגבלה"
    opt1 = opt1.strip()
    m = re.match(r'^(\d+(?:\.\d+)?)GB/Day$', opt1, re.I)
    if m:
        gb = float(m.group(1))
        gb_int = int(gb) if gb == int(gb) else gb
        return gb_int, f"{gb_int}GB/יום"
    m = re.match(r'^(\d+(?:\.\d+)?)MB/Day$', opt1, re.I)
    if m:
        mb = float(m.group(1))
        return round(mb / 1024, 4), f"{int(mb)}MB/יום"
    m = re.match(r'^Total\s+(\d+(?:\.\d+)?)GB$', opt1, re.I)
    if m:
        gb = float(m.group(1))
        gb_int = int(gb) if gb == int(gb) else gb
        return gb_int, f"{gb_int}GB"
    if "unlimited" in opt1.lower():
        return None, "ללא הגבלה"
    return None, opt1


_BYTESIM_JS = """() => {
    const s = window.__PRELOAD_STATE__;
    if (!s || !s.product) return null;
    return s.product.variants
        .filter(v => v.available)
        .map(v => ({o1: v.option1, o2: v.option2, price: v.price}));
}"""


_BYTESIM_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _scrape_bytesim_batch(items, carrier_label, usd_rate):
    """Fetch one batch of ByteSim product URLs in a single sequential browser session."""
    core._ensure_event_loop()
    batch_plans = []
    with core.sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_BYTESIM_UA)
        for item in items:
            url, heb_name = item[0], item[1]
            # heb_name may be a (plan_label, region_tag) tuple for zone plans
            if isinstance(heb_name, tuple):
                plan_label, region_tag = heb_name
            else:
                plan_label = region_tag = heb_name
            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
                variants = page.evaluate(_BYTESIM_JS)
                if not variants:
                    continue
                for v in variants:
                    data_gb, data_str = _parse_bytesim_option1(v.get("o1", ""))
                    try:
                        days = int(v["o2"])
                    except (TypeError, ValueError):
                        continue
                    price_cents = v.get("price", 0)
                    if not days or not price_cents:
                        continue
                    price_usd = price_cents / 100.0
                    price_ils = round(price_usd * usd_rate, 2)
                    day_word = "יום" if days == 1 else "ימים"
                    plan_name = f"{plan_label} – {data_str} – {days} {day_word}"
                    batch_plans.append(core._make_global_plan(
                        "bytesim", plan_name, price_ils, "USD", price_usd,
                        data_gb, days, esim=True, extras=[region_tag],
                    ))
            except Exception as exc:
                logger.warning(f"ByteSim {carrier_label} {url}: {exc}")
        browser.close()
    return batch_plans


def _scrape_bytesim_product_list(url_iter, carrier_label, usd_rate):
    """Split url_iter into 4 batches and fetch them in parallel browser sessions.
    Reduces wall time from ~19 min (sequential) to ~5 min (4-way parallel)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    url_list = list(url_iter)
    batch_size = max(1, (len(url_list) + 3) // 4)
    batches = [url_list[i:i + batch_size] for i in range(0, len(url_list), batch_size)]
    all_plans = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_scrape_bytesim_batch, b, carrier_label, usd_rate) for b in batches]
        for fut in _as_completed(futures, timeout=600):
            try:
                all_plans.extend(fut.result())
            except Exception as exc:
                logger.warning(f"ByteSim {carrier_label} batch error: {exc}")
    return all_plans


def scrape_bytesim_global(_page=None, usd_rate=None):
    """Scrape ByteSim per-country eSIM plans (~197 countries)."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    url_iter = [
        (f"https://bytesim.com/products/esim-{handle}", heb)
        for handle, heb in BYTESIM_HANDLE_TO_HEBREW.items()
    ]
    plans = _scrape_bytesim_product_list(url_iter, "countries", usd_rate)
    logger.info(f"ByteSim global: {len(plans)} plans from {len(BYTESIM_HANDLE_TO_HEBREW)} countries")
    return plans


def scrape_bytesim_regions(_page=None, usd_rate=None):
    """Scrape ByteSim zone/regional eSIM plans."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    url_iter = [
        (f"https://bytesim.com/products/{handle}", (plan_label, region_tag))
        for handle, (plan_label, region_tag) in BYTESIM_ZONE_HANDLES.items()
    ]
    plans = _scrape_bytesim_product_list(url_iter, "zones", usd_rate)
    logger.info(f"ByteSim regions: {len(plans)} plans from {len(BYTESIM_ZONE_HANDLES)} zones")
    return plans
