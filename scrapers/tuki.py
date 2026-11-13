"""tuki scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


_TUKI_API = "https://www.tuki-esim.co.il/ds/api/globalsim/data/?lcid=1037&pageControlId=21412"

# Multi-country zone (API English name) -> the Hebrew region label already stored
# in global_plans, so plan_name keys and their price history carry over.
TUKI_ZONE_TO_HEBREW = {
    "Africa":            "אפריקה",                                      # אפריקה
    "Asia":              "אסיה",                                              # אסיה
    "Central America":   "אמריקה הלטינית",          # אמריקה הלטינית
    "Europe-multi-IMSI": "אירופה",                                      # אירופה
    "GLOBAL":            "גלובלי",                                      # גלובלי
    "North America":     "צפון אמריקה",                    # צפון אמריקה
    "Oceania":           "אוקיאניה",                                # אוקיאניה
    "South America":     "אמריקה הדרומית",          # אמריקה הדרומית
}


def _tuki_fetch_data():
    """Tuki's whole catalog in one public JSON(P) document: countries, zones, packages."""
    import urllib.request, json as _json
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124"
    req = urllib.request.Request(_TUKI_API, headers={"User-Agent": ua})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    # Response is a JS assignment: datasource.globalsimData={...}
    return _json.loads(raw.split("=", 1)[1])


def _tuki_zone_packages(data):
    """{Hebrew region: {(gb, days): usd}} for the multi-country zones of the API."""
    out = {}
    unknown = []
    for zone in data.get("zones", []):
        if len(zone.get("countries") or []) < 2 or zone.get("isHide"):
            continue
        heb = TUKI_ZONE_TO_HEBREW.get(zone.get("name"))
        if not heb:
            unknown.append(zone.get("name"))
            continue
        tiers = {}
        for pkg in data.get("packages", []):
            if pkg.get("locationZoneId") != zone.get("id"):
                continue
            try:
                gb = float(pkg.get("gigaDataByte") or 0)
                days = int(pkg.get("validityPeriodDays") or 0)
                usd = float(pkg.get("price") or 0)
            except (ValueError, TypeError):
                continue
            if gb > 0 and days > 0 and usd > 0:
                tiers[(int(gb) if gb == int(gb) else gb, days)] = usd
        if tiers:
            out[heb] = tiers
    if unknown:
        logger.warning(f"Tuki: unmapped zones {unknown} - add them to TUKI_ZONE_TO_HEBREW")
    return out


def _tuki_regions_live():
    """Live zone price table, or the last-known static one if the API is down."""
    try:
        live = _tuki_zone_packages(_tuki_fetch_data())
        if live:
            return live, True
        logger.warning("Tuki: API returned no zone packages - using the static table")
    except Exception as e:
        logger.warning(f"Tuki zones API failed ({e}) - using the static table")
    return TUKI_REGIONS, False


def scrape_tuki_global(page, usd_rate):
    """Tuki's GLOBAL zone as the "Tuki Global" rows (139-country coverage card).

    Read from the catalog API since 2026-11: the Playwright scrape of the
    regional-packages page returned 0 cards on some runs (17:00 on 2026-11-12),
    leaving these rows to age. `page` is unused and kept for the call signature.
    """
    regions, _live = _tuki_regions_live()
    plans = []
    for (gb, days), usd_val in regions.get("גלובלי", {}).items():  # גלובלי
        plans.append(core._make_global_plan(
            "tuki", f"Tuki Global {gb:g}GB {days}d", round(usd_val * usd_rate, 2), "USD", usd_val,
            float(gb), days, extras=["139 מדינות", "eSIM בלבד"]
        ))
    logger.info(f"Tuki global: {len(plans)} plans")
    return plans


# Fallback only (API down). Last synced with the API 2026-11-12: Tuki dropped the
# 2GB/15-day tier everywhere on 2026-10-25, but this table kept emitting it for
# two more weeks as plans nobody could buy.
TUKI_REGIONS = {
    "אוקיאניה": {  # אוקיאניה
        (1, 7): 12.0, (3, 30): 33.0, (5, 30): 46.5, (10, 30): 69.3, (20, 30): 115.5,
    },
    "אירופה": {  # אירופה
        (1, 7): 5.0, (3, 30): 13.0, (5, 30): 20.0, (10, 30): 37.0, (20, 30): 49.0, (50, 90): 100.0, (100, 180): 185.0,
    },
    "אמריקה הדרומית": {  # אמריקה הדרומית
        (1, 7): 15.0, (3, 30): 39.0, (5, 30): 60.0,
    },
    "אמריקה הלטינית": {  # אמריקה הלטינית (Central/Caribbean)
        (1, 7): 6.5, (3, 30): 17.0, (5, 30): 25.5, (10, 30): 46.0, (20, 30): 65.0,
    },
    "צפון אמריקה": {  # צפון אמריקה
        (1, 7): 6.5, (3, 30): 17.0, (5, 30): 25.5, (10, 30): 46.0,
    },
    "אסיה": {  # אסיה
        (1, 7): 5.0, (3, 30): 13.0, (5, 30): 20.0, (10, 30): 37.0, (20, 30): 49.0, (50, 90): 100.0, (100, 180): 185.0,
    },
    "אפריקה": {  # אפריקה
        (1, 30): 27.0, (3, 30): 59.0,
    },
    "גלובלי": {  # גלובלי
        (1, 7): 9.0, (3, 30): 24.0, (5, 60): 35.0, (10, 180): 59.0, (20, 365): 69.0,
    },
}


def scrape_tuki_regions(page, usd_rate):
    """Tuki regional eSIM plans (USD) from the catalog API's multi-country zones."""
    all_plans = []
    regions, live = _tuki_regions_live()
    for region_heb, plans_data in regions.items():
        for (gb, days), price_usd in plans_data.items():
            price_ils = round(price_usd * usd_rate, 2)
            plan_name = f"{region_heb} – {gb:g}GB – {days} ימים"
            all_plans.append(core._make_global_plan(
                "tuki", plan_name, price_ils, "USD", price_usd,
                data_gb=gb, days=days, esim=True, extras=[region_heb]
            ))
    logger.info(f"Tuki regions: {len(all_plans)} plans from {len(regions)} regions ({'API' if live else 'static table'})")
    return all_plans


def scrape_tuki_local(page, usd_rate):
    """Scrape Tuki per-country eSIM plans via their JSON API."""
    all_plans = []

    try:
        data = _tuki_fetch_data()

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
