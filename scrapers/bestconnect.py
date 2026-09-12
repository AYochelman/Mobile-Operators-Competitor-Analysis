"""bestconnect scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


_BC_API_HEADERS = {
    "x-partition-id": "c8468e6f-3041-4320-a813-bcff3ae990cf",
    "authorization": "Basic MTAxOjEwMQ==",
    "x-platform": "3",
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


# Regional slugs not in SAILY_SLUG_TO_HEBREW — checked before the generic lookup
_BC_REGIONAL_HEBREW = {
    "europe-esim":               "אירופה",
    "balkan":                    "בלקן",
    "turkey-and-greek-islands":  "טורקיה ואיי יוון",
}


def _fetch_bestconnect_catalog(slug, eng_name, catalog_id, usd_rate):
    import urllib.request as _ur, json as _json
    try:
        req = _ur.Request(
            f"https://bestconnect.online/api/v1/product/offerings?filters[catalog_id]={catalog_id}",
            headers=_BC_API_HEADERS,
        )
        with _ur.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read())
        # Resolve Hebrew name — regional overrides first, then SAILY lookup
        if slug in _BC_REGIONAL_HEBREW:
            heb_name = _BC_REGIONAL_HEBREW[slug]
        else:
            saily_slug = re.sub(r'-esim$', '', slug)
            heb_name = core.SAILY_SLUG_TO_HEBREW.get(saily_slug, core.SAILY_SLUG_TO_HEBREW.get(slug, eng_name))
        plans = []
        for listing in data.get("listings", []):
            prices = listing.get("prices", [])
            services = listing.get("services", [])
            if not prices or not services:
                continue
            usd = prices[0].get("price")
            days = prices[0].get("validity_days")
            total_mb = services[0].get("total_mb")
            if not (usd and days and total_mb):
                continue
            gb = round(total_mb / 1024, 3)
            gb_label = int(gb) if gb == int(gb) else gb
            plan_name = f"{heb_name} – ‏{gb_label}GB – ‏{int(days)} ימים"
            plans.append(core._make_global_plan(
                "bestconnect", plan_name,
                round(float(usd) * usd_rate, 2), "USD", float(usd),
                gb, int(days), extras=[heb_name],
            ))
        return plans
    except Exception as e:
        logger.debug(f"bestconnect {slug}: {e}")
        return []


def scrape_bestconnect_global(_page=None, usd_rate=None):
    """Scrape Best Connect eSIM plans via REST API (~158 destinations)."""
    import urllib.request as _ur, json as _json
    from concurrent.futures import ThreadPoolExecutor, as_completed as _ac
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    try:
        req = _ur.Request(
            "https://bestconnect.online/api/v1/product/catalogs",
            headers=_BC_API_HEADERS,
        )
        with _ur.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read())
        catalogs = [(l["slug"], l["name"], l["catalog_id"]) for l in data.get("listings", [])]
    except Exception as e:
        logger.error(f"bestconnect: catalog fetch failed: {e}")
        return []
    all_plans = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_fetch_bestconnect_catalog, slug, name, cid, usd_rate): slug
            for slug, name, cid in catalogs
        }
        for fut in _ac(futures):
            try:
                all_plans.extend(fut.result() or [])
            except Exception as e:
                logger.debug(f"bestconnect: {futures[fut]}: {e}")
    logger.info(f"Best Connect: {len(all_plans)} plans from {len(catalogs)} catalogs")
    return all_plans
