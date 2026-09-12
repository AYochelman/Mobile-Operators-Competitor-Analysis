"""sparks scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


SPARKS_REGIONS = {
    "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4": {  # אירופה (was אירופה+)
        (1, 60): 3.40, (2, 60): 5.00, (3, 60): 6.50, (5, 60): 8.60,
        (10, 60): 14.70, (15, 60): 21.80, (30, 90): 42.60, (50, 120): 68.30,
    },
    "\u05e9\u05d5\u05d5\u05d9\u05e5+": {  # שוויץ+
        (1, 60): 3.40, (2, 60): 4.20, (3, 60): 4.90, (5, 60): 6.30,
        (10, 60): 9.80, (15, 60): 14.40, (30, 90): 28.30, (50, 120): 46.80,
    },
    "\u05d2\u05d5\u05d5\u05d3\u05dc\u05d5\u05e4": {  # גוודלופ
        (1, 60): 8.50, (2, 60): 10.80, (3, 60): 12.80, (5, 60): 16.90,
        (10, 60): 30.50, (15, 60): 45.10, (30, 90): 89.60, (50, 120): 149.40,
    },
    "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df+": {  # קפריסין+
        (1, 60): 8.50, (2, 60): 10.80, (3, 60): 12.80, (5, 60): 16.90,
        (10, 60): 30.50, (15, 60): 45.10, (30, 90): 89.60, (50, 120): 149.40,
    },
}


SPARKS_COUNTRY_TO_HEBREW_EXTRA = {
    "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "sri-lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "czech-republic": "\u05e6'\u05db\u05d9\u05d4",
    "ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "north-macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "cape-verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    # VOYE-specific names
    "russian-federation": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "macao-china": "\u05de\u05e7\u05d0\u05d5",
    "congo-dem.-rep": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea",
    "congo-democratic-rep": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea",
    "congo-republic": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "french-west-indies": "\u05d4\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05d9\u05dd",
    "cruise": "\u05e7\u05e8\u05d5\u05d6 \u05d1\u05e1\u05e4\u05d9\u05e0\u05d4",
    "uae": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "uk": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "usa": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "caribbean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "global": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "st.-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "cote-d'ivoire-ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "cote-divoire-ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "st.-martin-and-st.-barth-guadeloupe": "\u05e1\u05df \u05de\u05e8\u05d8\u05df \u05d5\u05d2\u05d5\u05d5\u05d3\u05dc\u05d5\u05e4",
}


def scrape_sparks_global(_page=None, usd_rate=None):
    """Scrape Sparks Travel eSIM plans \u2014 regional (hardcoded) + per-country (API)."""
    import urllib.request, json as _json

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    all_plans = []

    # 1. Regional plans (hardcoded)
    for region_heb, plans_data in SPARKS_REGIONS.items():
        for (gb, days), price_usd in plans_data.items():
            price_ils = round(price_usd * usd_rate, 2)
            plan_name = f"{region_heb} \u2013 {gb}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
            all_plans.append(core._make_global_plan(
                "sparks", plan_name, price_ils, "USD", price_usd,
                data_gb=gb, days=days, esim=True, extras=[region_heb]
            ))

    # 2. Per-country plans via API
    try:
        import os
        data_file = os.path.join(os.path.dirname(os.path.abspath(core.__file__)), "sparks_travel_data.json")
        if os.path.exists(data_file):
            with open(data_file, encoding="utf-8") as f:
                data = _json.load(f)

            for country in data.get("countries", []):
                country_name = country.get("country_name", "")
                # Convert to Hebrew using slug
                slug = country_name.lower().replace(" ", "-")
                country_heb = core.SAILY_SLUG_TO_HEBREW.get(slug)
                if not country_heb:
                    country_heb = SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(slug, country_name)

                for plan in country.get("plans", []):
                    gb = plan.get("data_gb")
                    days = plan.get("validity_days", 60)
                    price_usd = plan.get("price_usd")
                    if not gb or not price_usd:
                        continue
                    price_ils = round(price_usd * usd_rate, 2)
                    plan_name = f"{country_heb} \u2013 {int(gb)}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                    all_plans.append(core._make_global_plan(
                        "sparks", plan_name, price_ils, "USD", price_usd,
                        data_gb=gb, days=days, esim=True, extras=[country_heb]
                    ))
        else:
            logger.warning("Sparks data file not found \u2014 only regional plans available")
    except Exception as e:
        logger.warning(f"Sparks per-country: {e}")

    logger.info(f"Sparks global: {len(all_plans)} plans")
    return all_plans
