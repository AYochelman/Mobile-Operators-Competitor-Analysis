"""venterrasim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# Israeli travel-eSIM shop. The storefront reads its whole catalogue from one
# public, auth-free endpoint (/api/v1/plans/ — explicitly Allow:ed in the site's
# own robots.txt so Google can render the package lists), so this is a pure-HTTP
# scrape: ~1,000 plans, prices already in ILS, destinations as ISO-3166 alpha-2.
#
# Hebrew destination names reuse ESIMO_CODE_TO_HEBREW (same uppercase ISO keys,
# already-canonical spellings) plus the handful of codes eSIMo doesn't sell.
VENTERRA_CODE_TO_HEBREW = {
    **core.ESIMO_CODE_TO_HEBREW,
    "AO": "אנגולה",
    "BT": "בהוטן",
    "CI": "חוף השנהב",
    "PF": "פולינזיה הצרפתית",
    "SM": "סן מרינו",
    "XK": "קוסובו",
    "ZW": "זימבבואה",
}


# Regional/global bundles, keyed by the API `name` with its trailing
# "<N>GB <M>Days" spec stripped → (plan_name title, canonical extras[0] dest).
# Regions that sell SEVERAL coverage tiers under one label (Europe 33/35/41
# areas, Asia 7/20, South America 6/20) keep the area count in the TITLE: the
# tiers share (gb, days) pairs, so a bare region title would collide under
# UNIQUE(carrier, plan_name), and the title is what VENTERRA_REGION_MAP in
# globalCountries.js keys on to resolve the right country list.
VENTERRA_REGION_NAMES = {
    "Europe (33 areas)":               ("אירופה 33 יעדים", "אירופה"),
    "Europe (35 areas)":               ("אירופה 35 יעדים", "אירופה"),
    "Europe":                          ("אירופה 41 יעדים", "אירופה"),
    "Balkans (5+ areas)":              ("בלקן", "בלקן"),
    "Asia (7 areas)":                  ("אסיה 7 יעדים", "אסיה"),
    "Asia-20":                         ("אסיה 20 יעדים", "אסיה"),
    "Singapore & Malaysia & Thailand": ("סינגפור, מלזיה, תאילנד", "סינגפור, מלזיה, תאילנד"),
    "China (mainland HK Macao)":       ("סין + הונג קונג + מקאו", "סין + הונג קונג + מקאו"),
    "Central Asia (4 areas)":          ("מרכז אסיה", "מרכז אסיה"),
    "North America":                   ("צפון אמריקה", "צפון אמריקה"),
    "South America (6 areas)":         ("דרום אמריקה 6 יעדים", "דרום אמריקה"),
    "South America":                   ("דרום אמריקה 20 יעדים", "דרום אמריקה"),
    "Caribbean (20+ areas)":           ("האיים הקריביים", "האיים הקריביים"),
    "Global (120+ areas)":             ("גלובלי", "גלובלי"),
}


_VENTERRA_SPEC_RE = re.compile(r"\s*[\d.]+\s*GB\s*[\d.]+\s*Days?\s*$", re.I)


def scrape_venterrasim_global(_page=None, usd_rate=None):
    """Scrape the VenterraSIM catalog from its public JSON plans endpoint.

    One request returns every package: `type` is COUNTRY (location_code = a
    single ISO2) or REGIONAL (location_code = a comma-separated ISO2 list, and
    the region is identified by the name prefix via VENTERRA_REGION_NAMES).
    Prices are native ILS — `price_ils` is the live selling price, which is
    what change detection should track; `original_price_ils` is a permanent
    strike-through list price on every row, so it is deliberately ignored.
    """
    import json as _json

    raw = _json.loads(core._esimo_fetch("https://venterrasim.com/api/v1/plans/", timeout=40))
    if not isinstance(raw, list) or not raw:
        logger.warning("VenterraSIM: empty/unexpected catalog payload")
        return []

    best, unmapped = {}, set()
    for p in raw:
        try:
            gb = float(p.get("data_gb") or 0)
            days = int(p.get("duration_days") or 0)
            price = float(p.get("price_ils") or p.get("price") or 0)
        except (TypeError, ValueError):
            continue
        if gb <= 0 or days <= 0 or price <= 0:
            continue

        if (p.get("type") or "").upper() == "REGIONAL":
            key = _VENTERRA_SPEC_RE.sub("", p.get("name") or "").strip()
            td = VENTERRA_REGION_NAMES.get(key)
            if not td:
                unmapped.add(key)
                continue
            title, dest = td
        else:
            code = (p.get("location_code") or "").strip().upper()
            dest = VENTERRA_CODE_TO_HEBREW.get(code)
            if not dest:
                unmapped.add(f"{code}={p.get('country')}")
                continue
            title = dest

        gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        day_unit = "יום" if days == 1 else "ימים"
        plan_name = f"{title} – {gb_str} – {days} {day_unit}"
        if plan_name in best and best[plan_name]["price"] <= price:
            continue  # cheapest duplicate tier wins (UNIQUE(carrier, plan_name))
        best[plan_name] = core._make_global_plan(
            "venterrasim", plan_name, price, "ILS", price,
            data_gb=gb, days=days, esim=True, extras=[dest],
        )
    if unmapped:
        logger.warning(f"VenterraSIM: skipped unmapped destinations {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"VenterraSIM: {len(plans)} plans from {len(raw)} catalog rows")
    return plans
