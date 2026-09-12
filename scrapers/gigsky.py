"""gigsky scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


# Pure HTTP, no Playwright: GigSky exposes its ENTIRE catalog as one static JSON
# on their CDN (the same file the site's plan picker fetches):
#   https://cdn-prod.gigsky.com/planBundle/...2-plan-bundle-ext.json
# 180 "plan bundles" split by planBundleType into COUNTRY / REGIONAL / WORLD
# (WORLD = the global "World Plan" tiers + the "Cruise + …" packages + ferries).
# Each bundle carries a `plans` array; each plan has dataLimitInKB (0 = unlimited),
# validityPeriodInDays and a `prices` array aligned to currencyCodes — USD is the
# index we bill on. Destinations resolve to canonical Hebrew by reusing the
# existing ESIMO_CODE_TO_HEBREW (ISO alpha-2 → Hebrew) so we don't hand-maintain
# 157 country names; only the handful of multi-code / non-ESIMO bundles need an
# override below.
GIGSKY_PLAN_BUNDLE_URL = (
    "https://cdn-prod.gigsky.com/planBundle/"
    "includeSponsorPlans=false&simType=ACME_GSMA_ESIM_V2&includePlanVariants=true"
    "&lang=en&version=2-plan-bundle-ext.json"
)


# COUNTRY bundles whose countryCodes[0] is NOT the primary country → force the code.
GIGSKY_NAME_TO_CODE = {
    "United States": "US", "Israel": "IL", "Fiji": "FJ",
    "Vanuatu": "VU", "Mayotte": "YT", "Réunion": "RE",
}


# COUNTRY bundles that are not real travel destinations (offshore rigs / inflight) or
# politically redundant (Palestine == Israel coverage on GigSky) → not ingested.
GIGSKY_COUNTRY_SKIP = {
    "North Sea - Offshore", "Gulf of Mexico - Offshore", "Inflight", "Palestine",
}


# Codes GigSky uses that ESIMO_CODE_TO_HEBREW lacks.
GIGSKY_CODE_EXTRA = {
    "AO": "אנגולה",              # Angola
    "PF": "פולינזיה הצרפתית",  # French Polynesia
    "CI": "חוף השנהב",  # Ivory Coast
    "SX": "סינט מארטן",  # Sint Maarten
    "XK": "קוסובו",              # Kosovo
}


GIGSKY_REGION_TO_HEBREW = {
    "Caribbean":        "קריביים",
    "Middle East":      "המזרח התיכון",
    "North America":    "צפון אמריקה",
    "Africa":           "אפריקה",
    "Latin America":    "אמריקה הלטינית",
    "Europe":           "אירופה",
    "Asia Pacific":     "אסיה פסיפיק",
    "Dutch Caribbean":  "האיים הקריביים ההולנדיים",
    "French Caribbean": "האנטילים הצרפתיים",
}


# WORLD bundles → global tiers collapse to "גלובלי"; cruise packages become a
# "קרוז - <region>" label (the "קרוז" prefix drives isCruiseDest + the B2C cruise
# fold, see db._CRUISE_SOURCE_DESTS). Ferries are not ingested (value None).
GIGSKY_WORLD_TO_HEBREW = {
    "World Plan":                   "גלובלי",
    "World Plan Lite":              "גלובלי",
    "Cruise + Americas/Caribbean":  "קרוז - אמריקה וקריביים",
    "Cruise + Asia Pacific":        "קרוז - אסיה פסיפיק",
    "Cruise + Europe":              "קרוז - אירופה",
    "Cruise + World":               "קרוז - עולמי",
    "Cruise + Middle East":         "קרוז - המזרח התיכון",
    "Cruise - At Sea Only":         "קרוז - בים בלבד",
    "European Ferries":             None,
    "Europe Ferries + Land":        None,
}


def _gigsky_dest_hebrew(bundle):
    """Canonical Hebrew destination for a GigSky plan bundle (None → skip)."""
    btype = bundle.get("planBundleType")
    name = bundle.get("planBundleName", "")
    if btype == "REGIONAL":
        return GIGSKY_REGION_TO_HEBREW.get(name)
    if btype == "WORLD":
        return GIGSKY_WORLD_TO_HEBREW.get(name)
    # COUNTRY
    if name in GIGSKY_COUNTRY_SKIP:
        return None
    code = GIGSKY_NAME_TO_CODE.get(name) or (bundle.get("countryCodes") or [None])[0]
    return core.ESIMO_CODE_TO_HEBREW.get(code) or GIGSKY_CODE_EXTRA.get(code)


def _gigsky_gb_str(data_gb):
    if data_gb is None:
        return "בלתי מוגבל"  # בלתי מוגבל
    if data_gb >= 1:
        return f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb:g}GB"
    return f"{round(data_gb * 1024)}MB"


def scrape_gigsky_global(_page=None, usd_rate=None):
    """Scrape the full GigSky eSIM catalog (countries + regions + global + cruise).

    Pure HTTP — one CDN JSON (GIGSKY_PLAN_BUNDLE_URL) holds every plan bundle.
    Skips free trials (freePlan), the recurring "GigSky One" subscription bundles,
    offshore/inflight/Palestine, and ferry bundles. USD is the billed currency.
    """
    import requests
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    try:
        r = requests.get(
            GIGSKY_PLAN_BUNDLE_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
            timeout=40,
        )
        r.raise_for_status()
        payload = r.json() or {}
    except Exception as exc:
        logger.warning(f"GigSky scraper failed: {exc}")
        return []

    currencies = payload.get("currencyCodes") or []
    try:
        usd_idx = currencies.index("USD")
    except ValueError:
        usd_idx = 5  # BRL,CAD,EUR,GBP,JPY,USD
    unlimited_note = "גלישה יומית ללא הגבלה"  # גלישה יומית ללא הגבלה

    plans, seen = [], set()
    for bundle in payload.get("list") or []:
        if bundle.get("isRecurringPlan"):
            continue
        dest = _gigsky_dest_hebrew(bundle)
        if not dest:
            continue
        for p in bundle.get("plans") or []:
            if p.get("freePlan"):
                continue
            prices = p.get("prices") or []
            usd = prices[usd_idx] if usd_idx < len(prices) else None
            try:
                usd = float(usd)
            except (TypeError, ValueError):
                continue
            if usd <= 0:
                continue
            kb = p.get("dataLimitInKB") or 0
            unlimited = (p.get("chargingType") == "UNLIMITED") or kb == 0
            data_gb = None if unlimited else round(kb / 1048576, 4)
            try:
                days = int(p.get("validityPeriodInDays"))
            except (TypeError, ValueError):
                continue
            g = _gigsky_gb_str(data_gb)
            day_unit = "יום" if days == 1 else "ימים"  # יום / ימים
            plan_name = f"{dest} – {g} – {days} {day_unit}"
            if plan_name in seen:      # guard UNIQUE(carrier, plan_name)
                continue
            seen.add(plan_name)
            extras = [dest]
            if unlimited:
                extras.append(unlimited_note)
            plans.append(core._make_global_plan(
                "gigsky", plan_name, round(usd * usd_rate, 2), "USD", usd,
                data_gb=data_gb, days=days, esim=True, extras=extras,
            ))
    logger.info(f"GigSky: {len(plans)} plans")
    return plans
