"""esimplus scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module
logger = core.logger


# Maps eSIM Plus slugs that differ from SAILY_SLUG_TO_HEBREW keys
_ESIMPLUS_TO_SAILY = {
    "united-kingdom-of-great-britain": "united-kingdom",
    "usa": "united-states",
    "brunei-darussalam": "brunei",
    "viet-nam": "vietnam",
    "russian-federation": "russia",
    "cte-divoire": "cote-d-ivoire",
    "curaao": "curacao",
    "cabo-verde": "cape-verde",
    "czechia": "czech-republic",
    "macao": "macau",
    "palestine-state-of": "israel",   # db.py _DEST_NORM maps Palestine → Israel
    "runion": "reunion",
    "saint-barthlemy": "saint-barthelemy",
    "saint-vincent-and-the-grenadines": "saint-vincent-and-grenadines",
    "virgin-islands-british": "british-virgin-islands",
    "virgin-islands-us": "us-virgin-islands",
    "bonaire-sint-eustatius-and-saba": "bonaire",
    "congo-democratic-republic-of-the": "democratic-republic-of-congo",
    "land-islands": None,   # skip
    "holy-see": None,       # skip
}


ESIMPLUS_COUNTRY_SLUGS = [
    "albania", "algeria", "andorra", "angola", "anguilla", "antigua-and-barbuda",
    "argentina", "armenia", "aruba", "australia", "austria", "azerbaijan",
    "bahamas", "bahrain", "bangladesh", "barbados", "belarus", "belgium", "belize",
    "benin", "bermuda", "bolivia", "bonaire-sint-eustatius-and-saba",
    "bosnia-and-herzegovina", "botswana", "brazil", "brunei-darussalam", "bulgaria",
    "burkina-faso", "cabo-verde", "cambodia", "cameroon", "canada", "cayman-islands",
    "central-african-republic", "chad", "chile", "china", "colombia", "congo",
    "congo-democratic-republic-of-the", "costa-rica", "cte-divoire", "croatia",
    "cuba", "curaao", "cyprus", "czechia", "denmark", "dominica",
    "dominican-republic", "ecuador", "egypt", "el-salvador", "equatorial-guinea",
    "estonia", "eswatini", "ethiopia", "faroe-islands", "fiji", "finland", "france",
    "french-guiana", "french-polynesia", "gabon", "gambia", "georgia", "germany",
    "ghana", "gibraltar", "greece", "greenland", "grenada", "guadeloupe", "guam",
    "guatemala", "guernsey", "guinea", "guinea-bissau", "guyana", "haiti",
    "honduras", "hong-kong", "hungary", "iceland", "india", "indonesia", "iran",
    "iraq", "ireland", "isle-of-man", "israel", "italy", "jamaica", "japan",
    "jersey", "jordan", "kazakhstan", "kenya", "south-korea", "kyrgyzstan", "laos",
    "latvia", "lebanon", "lesotho", "liberia", "liechtenstein", "lithuania",
    "luxembourg", "macao", "madagascar", "malawi", "malaysia", "mali", "malta",
    "martinique", "mauritania", "mauritius", "mayotte", "mexico", "moldova",
    "monaco", "mongolia", "montenegro", "montserrat", "morocco", "mozambique",
    "myanmar", "namibia", "nauru", "netherlands", "new-zealand", "nicaragua",
    "niger", "nigeria", "north-macedonia", "norway", "oman", "pakistan",
    "palestine-state-of", "panama", "papua-new-guinea", "paraguay", "peru",
    "philippines", "poland", "portugal", "puerto-rico", "qatar", "runion",
    "romania", "russian-federation", "rwanda", "saint-barthlemy",
    "saint-kitts-and-nevis", "saint-lucia", "saint-martin-french-part",
    "saint-vincent-and-the-grenadines", "samoa", "saudi-arabia", "senegal",
    "serbia", "seychelles", "sierra-leone", "singapore", "slovakia", "slovenia",
    "south-africa", "south-sudan", "spain", "sri-lanka", "sudan", "suriname",
    "sweden", "switzerland", "taiwan", "tajikistan", "tanzania", "thailand",
    "togo", "tonga", "trinidad-and-tobago", "tunisia", "turkey",
    "turks-and-caicos-islands", "uganda", "ukraine", "united-arab-emirates",
    "united-kingdom-of-great-britain", "usa", "uruguay", "uzbekistan", "vanuatu",
    "viet-nam", "virgin-islands-british", "virgin-islands-us", "zambia",
    "netherlands-antilles",
    # Multi-country regions (esim-regional page)
    "asia", "africa", "balkans", "europe", "north-america", "oceania", "caribbean",
    "europe-usa", "middle-east", "americas-us-ca",
    # Global packages (esim-global page)
    "global", "global-max", "global-light", "global-standard", "europe-usa-business-hubs",
]


_ESIMPLUS_REGION_HEB = {
    "asia":                     "אסיה",
    "africa":                   "אפריקה",
    "balkans":                  "בלקן",
    "europe":                   "אירופה",
    "north-america":            "צפון אמריקה",
    "oceania":                  "אוקיאניה",
    "caribbean":                "איי הקריביים",
    "europe-usa":               'אירופה וארה"ב',
    "middle-east":              "המזרח התיכון ואפריקה",
    "americas-us-ca":           "האמריקות",
    "global":                   "גלובלי",
    "global-max":               "גלובלי",
    "global-light":             "גלובלי",
    "global-standard":          "גלובלי",
    "europe-usa-business-hubs": 'אירופה וארה"ב',
}


# Plan-name prefix for global variants that share extras[0]="גלובלי"
# Keeps DB plan_name distinct so UPSERT doesn't collide between tiers
_ESIMPLUS_PLAN_PREFIX = {
    "global-max":               "גלובלי Premium",
    "global-light":             "גלובלי Light",
    "global-standard":          "גלובלי Plus",
    "europe-usa-business-hubs": 'אירופה וארה"ב עסקים',
}


def _fetch_esimplus_country(slug, usd_rate):
    import urllib.request as _ur, base64 as _b64
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    # Resolve Hebrew name
    saily_slug = _ESIMPLUS_TO_SAILY.get(slug, slug)
    if saily_slug is None:
        return []
    heb_name = (
        _ESIMPLUS_REGION_HEB.get(slug)
        or core.SAILY_SLUG_TO_HEBREW.get(saily_slug)
        or core.SAILY_SLUG_TO_HEBREW.get(slug)
    )
    try:
        req = _ur.Request(
            f"https://esimplus.me/esim-{slug}",
            headers={"User-Agent": _UA},
        )
        with _ur.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8")
        if heb_name is None:
            title_m = re.search(r"<title>eSIM (?:for )?([^|]+)\|", html)
            heb_name = _html_unescape(title_m.group(1)).strip() if title_m else slug.replace("-", " ").title()
        # Decode paymentCode base64 PHP-serialized objects for exact prices
        codes = re.findall(r"paymentCode=([A-Za-z0-9+/%]+)", html)
        seen = {}
        for code in codes:
            try:
                data_bytes = _b64.b64decode(code + "==")
                p   = re.search(rb"\x00\*\x00price\";d:([\d.]+)", data_bytes)
                d   = re.search(rb"\x00\*\x00dataAmount\";i:(\d+)", data_bytes)
                dur = re.search(rb"\x00\*\x00duration\";i:(\d+)", data_bytes)
                t   = re.search(rb'\x00\*\x00type\";s:\d+:"([^"]+)"', data_bytes)
                if p and d and dur:
                    usd = float(p.group(1))
                    gb = int(d.group(1)) / 1000.0
                    days = int(dur.group(1))
                    plan_type = t.group(1).decode("utf-8") if t else "regular"
                    key = (gb, days, plan_type)
                    if key not in seen or usd < seen[key][0]:
                        seen[key] = (usd, plan_type)
            except Exception:
                continue
        plan_prefix = _ESIMPLUS_PLAN_PREFIX.get(slug, heb_name)
        plans = []
        for (gb, days, plan_type), (usd, _) in seen.items():
            gb_label = int(gb) if gb == int(gb) else gb
            suffix = " (שיחות+SMS)" if plan_type == "legacy" else ""
            plans.append(core._make_global_plan(
                "esimplus", f"{plan_prefix} – ‏{gb_label}GB – ‏{days} ימים{suffix}",
                round(usd * usd_rate, 2), "USD", usd,
                gb, days, extras=[heb_name],
            ))
        return plans
    except Exception as e:
        logger.debug(f"esimplus {slug}: {e}")
        return []


def scrape_esimplus_global(_page=None, usd_rate=None):
    """Scrape eSIM Plus plans via per-country pages (~214 destinations)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _ac
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    all_plans = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_fetch_esimplus_country, slug, usd_rate): slug
            for slug in ESIMPLUS_COUNTRY_SLUGS
        }
        for fut in _ac(futures):
            try:
                all_plans.extend(fut.result() or [])
            except Exception as e:
                logger.debug(f"esimplus: {e}")
    logger.info(f"eSIM Plus: {len(all_plans)} plans from {len(ESIMPLUS_COUNTRY_SLUGS)} destinations")
    return all_plans
