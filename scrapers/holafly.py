"""holafly scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


HOLAFLY_SLUG_TO_HEBREW = {
    "albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "antigua-and-barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "belize": "\u05d1\u05dc\u05d9\u05d6",
    "benin": "\u05d1\u05e0\u05d9\u05df",
    "bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "bonaire": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4",
    "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada": "\u05e7\u05e0\u05d3\u05d4",
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "chad": "\u05e6'\u05d0\u05d3",
    "chile": "\u05e6'\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df",
    "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic": "\u05e6'\u05db\u05d9\u05d4",
    "democratic-republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9",
    "faroe-islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france": "\u05e6\u05e8\u05e4\u05ea",
    "french-guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "french-polynesia": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon": "\u05d2\u05d1\u05d5\u05df",
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
    "guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iran": "\u05d0\u05d9\u05e8\u05d0\u05df",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kosovo": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau": "\u05de\u05e7\u05d0\u05d5",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali": "\u05de\u05d0\u05dc\u05d9",
    "malta": "\u05de\u05dc\u05d8\u05d4",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "nepal": "\u05e0\u05e4\u05d0\u05dc",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "north-macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8",
    "republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "russia": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saint-barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "spain": "\u05e1\u05e4\u05e8\u05d3",
    "sri-lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "sudan": "\u05e1\u05d5\u05d3\u05df",
    "suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-and-caicos": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "yemen": "\u05ea\u05d9\u05de\u05df",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


# Key durations to keep from Holafly's 1-90 day range
_HOLAFLY_KEY_DAYS = {1, 3, 5, 7, 10, 15, 20, 30, 60, 90}


def scrape_holafly_global(_page=None, usd_rate=None):
    """Scrape Holafly eSIM plans via Shopify product JSON API (no Playwright needed).
    All Holafly plans offer unlimited data. Filters to key durations only."""
    import urllib.request, json as _json, time as _time

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    all_plans = []
    success_count = 0

    for slug, country_heb in HOLAFLY_SLUG_TO_HEBREW.items():
        try:
            url = f"https://holafly-esim.myshopify.com/products/esim-{slug}.json"
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = _json.loads(resp.read())

            variants = data.get("product", {}).get("variants", [])
            for v in variants:
                sku = v.get("sku", "")
                # Parse days from SKU: esim-{country}-{N}-day(s)
                m = re.search(r"-(\d+)-days?$", sku)
                if not m:
                    continue
                days = int(m.group(1))
                if days not in _HOLAFLY_KEY_DAYS:
                    continue

                price_usd = core._parse_price(str(v.get("price", "")))
                if price_usd is None:
                    continue

                price_ils = round(price_usd * usd_rate, 2)
                plan_name = f"{country_heb} \u2013 \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4 \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(core._make_global_plan(
                    "holafly", plan_name, price_ils, "USD", price_usd,
                    data_gb=None,  # unlimited
                    days=days, esim=True, extras=[country_heb]
                ))

            success_count += 1
            _time.sleep(0.2)

        except Exception as exc:
            logger.warning(f"Holafly {slug}: {exc}")
            continue

    logger.info(f"Holafly global: {len(all_plans)} plans from {success_count}/{len(HOLAFLY_SLUG_TO_HEBREW)} countries")
    return all_plans


HOLAFLY_REGIONS = {
    "esim-asia":                    "\u05d0\u05e1\u05d9\u05d4",
    "esim-europe":                  "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "esim-south-america":           "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "esim-northamerica":            "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "oceania":                      "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "esim-caribbean":               "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "sudeste-asiatico":             "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "china-hong-kong-macau":        "\u05e1\u05d9\u05df + \u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2 + \u05de\u05e7\u05d0\u05d5",
    "japon-corea":                  "\u05d9\u05e4\u05df \u05d5\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "japon-china":                  "\u05d9\u05e4\u05df \u05d5\u05e1\u05d9\u05df",
    "escandinavia":                 "\u05e1\u05e7\u05e0\u05d3\u05d9\u05e0\u05d1\u05d9\u05d4",
    "centroamerica":                "\u05de\u05e8\u05db\u05d6 \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "balkans":                      "\u05d1\u05dc\u05e7\u05df",
    "europa-oriental":              "\u05de\u05d6\u05e8\u05d7 \u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
}


# Middle East & Africa don't have Shopify API — hardcoded key prices (USD)
_HOLAFLY_NON_SHOPIFY_REGIONS = {
    "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df": {  # המזרח התיכון
        1: 9.90, 3: 25.90, 5: 36.90, 7: 42.90, 10: 52.90,
        15: 79.90, 20: 106.90, 30: 161.90, 60: 256.90, 90: 322.90,
    },
    "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4": {  # אפריקה
        1: 9.90, 3: 25.90, 5: 36.90, 7: 42.90, 10: 52.90,
        15: 79.90, 20: 106.90, 30: 161.90, 60: 256.90, 90: 322.90,
    },
}


def scrape_holafly_regions(_page=None, usd_rate=None):
    """Scrape Holafly regional eSIM plans via Shopify product JSON API (no Playwright needed).
    All Holafly regional plans offer unlimited data. Filters to key durations only."""
    import urllib.request, json as _json, time as _time

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    all_plans = []
    success_count = 0

    for slug, region_heb in HOLAFLY_REGIONS.items():
        try:
            url = f"https://holafly-esim.myshopify.com/products/{slug}.json"
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = _json.loads(resp.read())

            variants = data.get("product", {}).get("variants", [])
            for v in variants:
                sku = v.get("sku") or ""
                title = v.get("title") or ""
                m = re.search(r"(\d+)-days?", sku)
                if not m:
                    m = re.search(r"(\d+)\s*d[ií]as?", title)
                if not m:
                    continue
                days = int(m.group(1))
                if days not in _HOLAFLY_KEY_DAYS:
                    continue

                price_usd = core._parse_price(str(v.get("price", "")))
                if price_usd is None:
                    continue

                price_ils = round(price_usd * usd_rate, 2)
                plan_name = f"{region_heb} \u2013 \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4 \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(core._make_global_plan(
                    "holafly", plan_name, price_ils, "USD", price_usd,
                    data_gb=None,  # unlimited
                    days=days, esim=True, extras=[region_heb]
                ))

            success_count += 1
            _time.sleep(0.2)

        except Exception as exc:
            logger.warning(f"Holafly region {slug}: {exc}")
            continue

    # Add non-Shopify regions (Middle East & Africa) from hardcoded prices
    for region_heb, prices in _HOLAFLY_NON_SHOPIFY_REGIONS.items():
        for days, price_usd in prices.items():
            price_ils = round(price_usd * usd_rate, 2)
            plan_name = f"{region_heb} \u2013 \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4 \u2013 {days} \u05d9\u05de\u05d9\u05dd"
            all_plans.append(core._make_global_plan(
                "holafly", plan_name, price_ils, "USD", price_usd,
                data_gb=None, days=days, esim=True, extras=[region_heb]
            ))
        success_count += 1

    logger.info(f"Holafly regions: {len(all_plans)} plans from {success_count}/{len(HOLAFLY_REGIONS) + len(_HOLAFLY_NON_SHOPIFY_REGIONS)} regions")
    return all_plans
