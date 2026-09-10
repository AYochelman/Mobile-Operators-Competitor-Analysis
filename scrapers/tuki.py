"""tuki scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


def scrape_tuki_global(page, usd_rate):
    page.goto(
        "https://www.tuki-esim.co.il/ds/heb/hp/regional-packages/global/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_timeout(2000)
    plans = []
    for card in page.query_selector_all(".blue5, .blue15, .blue30"):
        gb_el    = card.query_selector(".gb span")
        price_el = card.query_selector(".price span:last-child")
        valid_el = card.query_selector(".valid span")
        if not gb_el or not price_el:
            continue
        gb_text    = gb_el.inner_text().strip()
        price_text = price_el.inner_text().strip()
        valid_text = valid_el.inner_text().strip() if valid_el else ""
        gb      = core._parse_gb(gb_text)
        days    = core._parse_days(valid_text)
        usd_val = core._parse_price(price_text)
        if usd_val is None:
            continue
        price_ils = round(usd_val * usd_rate, 2)
        name = f"Tuki Global {gb_text}"
        if days:
            name += f" {days}d"
        plans.append(core._make_global_plan(
            "tuki", name, price_ils, "USD", usd_val,
            gb, days, extras=["139 מדינות", "eSIM בלבד"]
        ))
    logger.info(f"Tuki global: {len(plans)} plans")
    return plans


TUKI_REGIONS = {
    "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4": {  # אוקיאניה
        (1, 7): 12.0, (3, 30): 33.0, (5, 30): 46.5, (10, 30): 69.3, (20, 30): 115.5,
    },
    "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4": {  # אירופה
        (1, 7): 5.0, (2, 15): 9.5, (3, 30): 13.0, (5, 30): 20.0, (10, 30): 37.0, (20, 30): 49.0, (50, 90): 100.0, (100, 180): 185.0,
    },
    "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea": {  # אמריקה הדרומית
        (1, 7): 15.0, (2, 15): 28.0, (3, 30): 39.0, (5, 30): 60.0,
    },
    "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea": {  # אמריקה הלטינית (Central/Caribbean)
        (1, 7): 6.5, (2, 15): 12.0, (3, 30): 17.0, (5, 30): 25.5, (10, 30): 46.0, (20, 30): 65.0,
    },
    "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4": {  # צפון אמריקה
        (1, 7): 6.5, (2, 15): 12.0, (3, 30): 17.0, (5, 30): 25.5, (10, 30): 46.0,
    },
    "\u05d0\u05e1\u05d9\u05d4": {  # אסיה
        (1, 7): 5.0, (2, 15): 9.5, (3, 30): 13.0, (5, 30): 20.0, (10, 30): 37.0, (20, 30): 49.0, (50, 90): 100.0, (100, 180): 185.0,
    },
    "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4": {  # אפריקה
        (1, 30): 27.0, (2, 30): 38.0, (3, 30): 59.0,
    },
    "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9": {  # גלובלי
        (1, 7): 9.0, (2, 15): 17.0, (3, 30): 24.0, (5, 60): 35.0, (10, 180): 59.0, (20, 365): 69.0,
    },
}


def scrape_tuki_regions(page, usd_rate):
    """Tuki regional eSIM plans — hardcoded prices (USD)."""
    all_plans = []
    for region_heb, plans_data in TUKI_REGIONS.items():
        for (gb, days), price_usd in plans_data.items():
            price_ils = round(price_usd * usd_rate, 2)
            plan_name = f"{region_heb} \u2013 {gb}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
            all_plans.append(core._make_global_plan(
                "tuki", plan_name, price_ils, "USD", price_usd,
                data_gb=gb, days=days, esim=True, extras=[region_heb]
            ))
    logger.info(f"Tuki regions: {len(all_plans)} plans from {len(TUKI_REGIONS)} regions")
    return all_plans


def scrape_tuki_local(page, usd_rate):
    """Scrape Tuki per-country eSIM plans via their JSON API."""
    import urllib.request, json as _json
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124"
    all_plans = []

    try:
        url = "https://www.tuki-esim.co.il/ds/api/globalsim/data/?lcid=1037&pageControlId=21412"
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read().decode("utf-8")
        # Response is JS assignment: datasource.globalsimData={...}
        json_str = raw.split("=", 1)[1]
        data = _json.loads(json_str)

        countries = data.get("countries", [])
        packages = data.get("packages", [])

        # Build package lookup by id
        pkg_by_id = {p["id"]: p for p in packages}

        # Normalize country names to match other providers
        _tuki_name_fix = {
            "\u05d0\u05d9\u05d9 \u05d1\u05d4\u05d0\u05de\u05d4": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",  # איי בהאמה -> איי הבהאמה
            "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d1\u05e8\u05d9\u05d8\u05d9\u05d9\u05dd": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",  # איי הבתולה (בריטניה) -> איי הבתולה (בריטניה)
            "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d0\u05de\u05e8\u05d9\u05e7\u05e0\u05d9\u05dd": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",  # איי הבתולה האמריקנים -> איי הבתולה (ארה"ב)
            "\u05e0\u05d5\u05e8\u05d5\u05d5\u05d2\u05d9\u05d4": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",  # נורווגיה -> נורבגיה
            "\u05e9\u05d5\u05d5\u05d3\u05d9\u05d4": "\u05e9\u05d1\u05d3\u05d9\u05d4",  # שוודיה -> שבדיה
            "\u05e9\u05d5\u05d5\u05d9\u05d9\u05e5": "\u05e9\u05d5\u05d5\u05d9\u05e5",  # שווייץ -> שוויץ
            "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea \u05d4\u05e2\u05e8\u05d1\u05d9\u05d5\u05ea": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",  # איחוד האמירויות -> איחוד האמירויות
            "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טורק וקייקוס -> איי טורקס וקאיקוס
            "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טורקס וקייקוס -> איי טורקס וקאיקוס
            "\u05d0\u05d9\u05d9 \u05d8\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טרקס וקייקוס -> איי טורקס וקאיקוס
        }
        for country in countries:
            raw_name = country.get("nameHeb", "").strip()
            country_heb = _tuki_name_fix.get(raw_name, raw_name)
            pkg_ids = country.get("countryPackagesIds", [])
            if not country_heb or not pkg_ids:
                continue

            for pid in pkg_ids:
                pkg = pkg_by_id.get(pid)
                if not pkg:
                    continue
                try:
                    gb = float(pkg.get("gigaDataByte", 0))
                    days = int(pkg.get("validityPeriodDays", 30))
                    price_usd = float(pkg.get("price", 0))
                except (ValueError, TypeError):
                    continue
                if gb <= 0 or price_usd <= 0:
                    continue

                price_ils = round(price_usd * usd_rate, 2)
                plan_name = f"{country_heb} \u2013 {int(gb)}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(core._make_global_plan(
                    "tuki", plan_name, price_ils, "USD", price_usd,
                    data_gb=gb, days=days, esim=True, extras=[country_heb]
                ))

        logger.info(f"Tuki local: {len(all_plans)} per-country plans from {len(countries)} countries")
    except Exception as e:
        logger.error(f"Tuki local API failed: {e}", exc_info=True)

    return all_plans
