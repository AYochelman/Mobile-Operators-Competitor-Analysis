"""airalo scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


def scrape_airalo_global(page, usd_rate):
    """Scrape Airalo global eSIM packages via REST API (no Playwright needed).
    Uses x-client-version: version2 header to get all operators (Discover + Discover+).
    """
    import urllib.request as _req
    import json as _json
    plans = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.airalo.com/global-esim",
            "x-client-version": "version2",
            "accept-language": "en",
        }
        request = _req.Request(
            "https://www.airalo.com/api/v4/regions/world",
            headers=headers
        )
        with _req.urlopen(request, timeout=15) as resp:
            data = _json.loads(resp.read().decode())

        packages = data.get("packages", [])
        seen = set()
        for pkg in packages:
            try:
                slug = pkg.get("slug", "")
                if slug in seen:
                    continue
                seen.add(slug)

                # Price: always in USD
                price_obj = pkg.get("price", {})
                usd = float(price_obj.get("amount", 0))
                if usd <= 0:
                    continue
                price_ils = round(usd * usd_rate, 2)

                # Data amount (stored in MB in 'amount' field)
                if pkg.get("is_unlimited"):
                    gb = None
                else:
                    mb = pkg.get("amount", 0)
                    gb = round(mb / 1024, 2) if mb else None

                days    = pkg.get("day")
                minutes = pkg.get("voice")    # None for data-only plans
                sms     = pkg.get("text")     # None for data-only plans

                # Operator name: "Discover" or "Discover+"
                operator_title = pkg.get("operator", {}).get("title", "Discover")

                # Build plan name including operator to distinguish the two
                gb_label  = f"{int(gb)}GB" if gb and gb == int(gb) else (f"{gb}GB" if gb else "ללא הגבלה")
                day_label = f"{days}d" if days else ""
                name = f"Airalo {operator_title} {gb_label} {day_label}".strip()

                # Extras
                operator = pkg.get("operator", {})
                country_count = len(operator.get("countries", []))
                extras = []
                if country_count:
                    extras.append(f"{country_count}+ מדינות")
                extras.append("eSIM בלבד")

                plans.append(core._make_global_plan(
                    "airalo", name, price_ils, "USD", usd,
                    gb, days, minutes=minutes, sms=sms, esim=True,
                    extras=extras
                ))
            except Exception as e:
                logger.debug(f"Airalo package parse error: {e}")
                continue
    except Exception as e:
        logger.error(f"Airalo API failed: {e}", exc_info=True)

    logger.info(f"Airalo global: {len(plans)} plans")
    return plans


AIRALO_SLUG_TO_HEBREW = {
    "afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria": "\u05d0\u05dc\u05d2\u0027\u05d9\u05e8\u05d9\u05d4",
    "andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "antigua-and-barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4\u0020\u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2\u0027\u05df",
    "azores": "\u05d4\u05d0\u05d9\u05d9\u05dd\u0020\u05d4\u05d0\u05d6\u05d5\u05e8\u05d9\u05d9\u05dd",
    "bahamas": "\u05d0\u05d9\u05d9\u0020\u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "belize": "\u05d1\u05dc\u05d9\u05d6",
    "benin": "\u05d1\u05e0\u05d9\u05df",
    "bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bhutan": "\u05d1\u05d4\u05d5\u05d8\u05df",
    "bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "bonaire": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4\u0020\u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands": "\u05d0\u05d9\u05d9\u0020\u05d4\u05d1\u05ea\u05d5\u05dc\u05d4\u0020\u0028\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4\u0029",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4\u0020\u05e4\u05d0\u05e1\u05d5",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada": "\u05e7\u05e0\u05d3\u05d4",
    "canary-islands": "\u05d0\u05d9\u05d9\u0020\u05e7\u05e0\u05e8\u05d9",
    "cape-verde": "\u05db\u05e3\u0020\u05d5\u05e8\u05d3\u05d4",
    "cayman-islands": "\u05d0\u05d9\u05d9\u0020\u05e7\u05d9\u05d9\u05de\u05df",
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4\u0020\u05d4\u05de\u05e8\u05db\u05d6\u002d\u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "chad": "\u05e6\u0027\u05d0\u05d3",
    "chile": "\u05e6\u0027\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df",
    "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4\u0020\u05e8\u05d9\u05e7\u05d4",
    "cote-divoire": "\u05d7\u05d5\u05e3\u0020\u05d4\u05e9\u05e0\u05d4\u05d1",
    "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic": "\u05e6\u0027\u05db\u05d9\u05d4",
    "democratic-republic-of-the-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4\u0020\u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea\u0020\u05e9\u05dc\u0020\u05e7\u05d5\u05e0\u05d2\u05d5",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4\u0020\u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc\u0020\u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "faroe-islands": "\u05d0\u05d9\u05d9\u0020\u05e4\u05d0\u05e8\u05d5",
    "fiji": "\u05e4\u05d9\u05d2\u0027\u05d9",
    "finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france": "\u05e6\u05e8\u05e4\u05ea",
    "french-guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4\u0020\u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon": "\u05d2\u05d1\u05d5\u05df",
    "gambia": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "ghana": "\u05d2\u05d0\u05e0\u05d4",
    "gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "greece": "\u05d9\u05d5\u05d5\u05df",
    "greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "guam": "\u05d2\u05d5\u05d0\u05dd",
    "guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4\u0020\u05d1\u05d9\u05e1\u05d0\u05d5",
    "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2\u0020\u05e7\u05d5\u05e0\u05d2",
    "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man": "\u05d4\u05d0\u05d9\u0020\u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "jamaica": "\u05d2\u0027\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2\u0027\u05e8\u05d6\u05d9",
    "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "lebanon": "\u05dc\u05d1\u05e0\u05d5\u05df",
    "lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macao": "\u05de\u05e7\u05d0\u05d5",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "madeira": "\u05de\u05d3\u05d9\u05d9\u05e8\u05d4",
    "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali": "\u05de\u05d0\u05dc\u05d9",
    "malta": "\u05de\u05dc\u05d8\u05d4",
    "marie-galante": "\u05de\u05d0\u05e8\u05d9\u002d\u05d2\u05d0\u05dc\u05d0\u05e0\u05d8",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "nepal": "\u05e0\u05e4\u05d0\u05dc",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "new-zealand": "\u05e0\u05d9\u05d5\u0020\u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d2\u0027\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "northern-cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df\u0020\u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palestine-state-of": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4\u0020\u05d2\u05d9\u05e0\u05d0\u05d4\u0020\u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "puerto-rico-us": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5\u0020\u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8",
    "congo": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saba": "\u05e1\u05d0\u05d1\u05d4",
    "saint-barthelemy": "\u05e1\u05df\u0020\u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8\u0020\u05e7\u05d9\u05d8\u05e1\u0020\u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8\u0020\u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martinfrench-part": "\u05e1\u05df\u0020\u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8\u0020\u05d5\u05d9\u05e0\u05e1\u05e0\u05d8\u0020\u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "saudi-arabia": "\u05e2\u05e8\u05d1\u0020\u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "scotland": "\u05e1\u05e7\u05d5\u05d8\u05dc\u05e0\u05d3",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "seychelles": "\u05d0\u05d9\u05d9\u0020\u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4\u0020\u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-eustatius": "\u05e1\u05d9\u05e0\u05d8\u0020\u05d0\u05d5\u05e1\u05d8\u05d8\u05d9\u05d5\u05e1",
    "sint-maartendutch-part": "\u05e1\u05d9\u05e0\u05d8\u0020\u05de\u05d0\u05e8\u05d8\u05df",
    "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd\u0020\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd\u0020\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "spain": "\u05e1\u05e4\u05e8\u05d3",
    "sri-lanka": "\u05e1\u05e8\u05d9\u0020\u05dc\u05e0\u05e7\u05d4",
    "suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "tajikistan": "\u05d8\u05d2\u0027\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "timor-leste": "\u05d8\u05d9\u05de\u05d5\u05e8\u0020\u05dc\u05e1\u05d8\u05d4",
    "togo": "\u05d8\u05d5\u05d2\u05d5",
    "tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3\u0020\u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-and-caicos-islands": "\u05d0\u05d9\u05d9\u0020\u05d8\u05d5\u05e8\u05e7\u05e1\u0020\u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3\u0020\u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea\u0020\u05d4\u05d1\u05e8\u05d9\u05ea",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "vatican-city": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "virgin-islands": "\u05d0\u05d9\u05d9\u0020\u05d4\u05d1\u05ea\u05d5\u05dc\u05d4\u0020\u0028\u05d0\u05e8\u05d4\u0022\u05d1\u0029",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
    "zimbabwe": "\u05d6\u05d9\u05de\u05d1\u05d1\u05d5\u05d0\u05d4",
    "mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "sudan": "\u05e1\u05d5\u05d3\u05df",
    "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
}


AIRALO_REGION_TO_HEBREW = {
    "africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "africa-safari": "\u05e1\u05e4\u05d0\u05e8\u05d9 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "asia": "\u05d0\u05e1\u05d9\u05d4",
    "caribbean-islands": "\u05d0\u05d9\u05d9 \u05d4\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "eu-plus-uk": "\u05d4\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05d9\u05e8\u05d5\u05e4\u05d9 \u05d5\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "latin-america": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "middle-east-and-north-africa": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "north-america": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "oceania": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
}


def scrape_airalo_local(_page=None, usd_rate=None):
    """Scrape Airalo per-country local eSIM packages via REST API."""
    import urllib.request as _req
    import json as _json
    import time as _time
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/json",
        "x-client-version": "version2",
        "accept-language": "en",
    }
    all_plans = []
    for slug, country_heb in AIRALO_SLUG_TO_HEBREW.items():
        try:
            req = _req.Request(
                "https://www.airalo.com/api/v4/countries/{}".format(slug),
                headers=headers,
            )
            with _req.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
            packages = data.get("packages", [])
            for pkg in packages:
                try:
                    price_obj = pkg.get("price", {})
                    usd = float(price_obj.get("amount", 0))
                    if usd <= 0:
                        continue
                    price_ils = round(usd * usd_rate, 2)

                    if pkg.get("is_unlimited"):
                        gb = None
                        gb_label = "ללא הגבלה"  # ללא הגבלה
                    else:
                        mb = pkg.get("amount", 0)
                        gb = round(mb / 1024, 2) if mb else None
                        if gb is None:
                            continue
                        if gb >= 1:
                            gb_label = "{}GB".format(int(gb) if gb == int(gb) else gb)
                        else:
                            gb_label = "{}MB".format(round(gb * 1024))

                    days    = pkg.get("day")
                    minutes = pkg.get("voice")
                    sms     = pkg.get("text")

                    if not days:
                        continue

                    name = "{} – {} – {} ימים".format(
                        country_heb, gb_label, days
                    )
                    if minutes:
                        name += " – {} דקות".format(minutes)
                    if sms:
                        name += " – {} SMS".format(sms)

                    all_plans.append(core._make_global_plan(
                        "airalo_local", name, price_ils, "USD", usd,
                        gb, days, minutes=minutes, sms=sms, esim=True,
                        extras=[country_heb],
                    ))
                except Exception as e:
                    logger.debug("Airalo local pkg parse error ({}): {}".format(slug, e))
                    continue
            _time.sleep(0.15)
        except Exception as e:
            logger.warning("Airalo local {} failed: {}".format(slug, e))
            continue

    logger.info("Airalo local: {} plans from {} countries".format(
        len(all_plans), len(AIRALO_SLUG_TO_HEBREW)
    ))
    return all_plans


def scrape_airalo_regional(_page=None, usd_rate=None):
    """Scrape Airalo regional eSIM packages (Africa, Asia, Europe, etc.) via REST API."""
    import urllib.request as _req
    import json as _json
    import time as _time
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/json",
        "x-client-version": "version2",
        "accept-language": "en",
    }
    all_plans = []
    try:
        req = _req.Request("https://www.airalo.com/api/v4/regions", headers=headers)
        with _req.urlopen(req, timeout=15) as resp:
            regions = _json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("Airalo regional: failed to fetch regions list: {}".format(e))
        return all_plans

    for region in regions:
        slug = region.get("slug", "")
        region_heb = AIRALO_REGION_TO_HEBREW.get(slug)
        if not region_heb:
            continue
        try:
            req2 = _req.Request(
                "https://www.airalo.com/api/v4/regions/{}".format(slug),
                headers=headers,
            )
            with _req.urlopen(req2, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
            packages = data.get("packages", [])
            seen = set()
            for pkg in packages:
                try:
                    price_obj = pkg.get("price", {})
                    usd = float(price_obj.get("amount", 0))
                    if usd <= 0:
                        continue
                    price_ils = round(usd * usd_rate, 2)

                    if pkg.get("is_unlimited"):
                        gb = None
                        gb_label = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"
                    else:
                        mb = pkg.get("amount", 0)
                        gb = round(mb / 1024, 2) if mb else None
                        if gb is None:
                            continue
                        if gb >= 1:
                            gb_label = "{}GB".format(int(gb) if gb == int(gb) else gb)
                        else:
                            gb_label = "{}MB".format(round(gb * 1024))

                    days    = pkg.get("day")
                    minutes = pkg.get("voice")
                    sms     = pkg.get("text")
                    if not days:
                        continue

                    dedup = (gb, days, minutes, sms)
                    if dedup in seen:
                        continue
                    seen.add(dedup)

                    name = "Airalo {} \u2013 {} \u2013 {} \u05d9\u05de\u05d9\u05dd".format(
                        region_heb, gb_label, days
                    )
                    if minutes:
                        name += " \u2013 {} \u05d3\u05e7\u05d5\u05ea".format(minutes)
                    if sms:
                        name += " \u2013 {} SMS".format(sms)

                    all_plans.append(core._make_global_plan(
                        "airalo_regional", name, price_ils, "USD", usd,
                        gb, days, minutes=minutes, sms=sms, esim=True,
                        extras=[region_heb, "eSIM \u05d1\u05dc\u05d1\u05d3"],
                    ))
                except Exception as e:
                    logger.debug("Airalo regional pkg parse error ({}): {}".format(slug, e))
                    continue
            _time.sleep(0.2)
        except Exception as e:
            logger.warning("Airalo regional {} failed: {}".format(slug, e))
            continue

    logger.info("Airalo regional: {} plans from {} regions".format(
        len(all_plans), len(AIRALO_REGION_TO_HEBREW)
    ))
    return all_plans
