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


# The shop does not name every product "esim-<slug>": older ones carry Spanish
# names or typos. Until 2026-11-20 these 19 destinations were asked for under the
# wrong handle, got a 404 and were silently missing from the catalog.
_HOLAFLY_HANDLE_OVERRIDES = {
    "algeria": "esim-argeria",
    "anguilla": "anguila",
    "bahamas": "bahamas",
    "belize": "esim-datos-belice",
    "benin": "bni",
    "bonaire": "bonaire",
    "burkina-faso": "burkina-faso",
    "french-polynesia": "polinesia-francesa",
    "gabon": "gabon",
    "guam": "guam",
    "guinea": "guinea",
    "guyana": "guyana",
    "isle-of-man": "esim-isle-of-men",
    "kazakhstan": "esim-kazakhastan",
    "kenya": "esim-kenia",
    "netherlands-antilles": "antillas-holandesas",
    "niger": "niger",
    "saint-martin": "esim-st-martin",
    "suriname": "surinam",
}

# Destinations Holafly sells that HOLAFLY_SLUG_TO_HEBREW has no slug for: handle -> Hebrew
_HOLAFLY_EXTRA_COUNTRIES = {
    "esim-united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",  # איחוד האמירויות
    "esim-iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",  # עיראק
    "esim-hawaii": "\u05d4\u05d5\u05d5\u05d0\u05d9",  # הוואי
    "monserrat": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",  # מונסראט
    "islas-aland": "\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3",  # איי אולנד
    "esim-st-pierre-and-miquelon": "\u05e1\u05df \u05e4\u05d9\u05d9\u05e8 \u05d5\u05de\u05d9\u05e7\u05dc\u05d5\u05df",  # סן פייר ומיקלון
    "esim-british-cayman-island": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",  # איי קיימן
    "esim-british-virgin-island": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",  # איי הבתולה (בריטניה)
}


def _holafly_country_handles():
    """[(shop handle, Hebrew destination)] for every per-country product."""
    pairs = [(_HOLAFLY_HANDLE_OVERRIDES.get(slug, f"esim-{slug}"), heb)
             for slug, heb in HOLAFLY_SLUG_TO_HEBREW.items()]
    return pairs + list(_HOLAFLY_EXTRA_COUNTRIES.items())


# Key durations to keep from Holafly's 1-90 day range
_HOLAFLY_KEY_DAYS = {1, 3, 5, 7, 10, 15, 20, 30, 60, 90}


# -- Where the catalog comes from ---------------------------------------------
# The scrape makes NO request to Holafly. Shopify allows our client about one
# listing request every ~20 minutes (one budget for every Shopify shop we read),
# so the listing is collected ahead of the scrape by shopify_catalog.collect()
# and read here from its cache. History, for whoever is tempted to go back:
#   - one product JSON per destination (~215 requests a run) got the client
#     throttled on every Shopify shop for days (2026-11);
#   - one live listing request per run worked for Holafly but starved Breeze,
#     which asks in the same minute.
class HolaflyRateLimited(Exception):
    """No usable Holafly catalog for this run (not collected, or too old)."""


def _holafly_catalog_by_handle():
    """{handle: product} for the whole shop. Raises HolaflyRateLimited."""
    import shopify_catalog
    try:
        products = shopify_catalog.products("holafly")
    except shopify_catalog.RateLimited as exc:
        raise HolaflyRateLimited(str(exc)) from exc
    if not products:
        raise HolaflyRateLimited("no fresh catalog in the Shopify cache")
    return {p["handle"]: p for p in products if p.get("handle")}


def scrape_holafly_global(_page=None, usd_rate=None):
    """Scrape Holafly eSIM plans via Shopify product JSON API (no Playwright needed).
    All Holafly plans offer unlimited data. Filters to key durations only."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    all_plans = []
    success_count = 0

    try:
        catalog = _holafly_catalog_by_handle()
    except HolaflyRateLimited as exc:
        logger.warning(f"Holafly global: no catalog this run ({exc})")
        return []
    except Exception as exc:
        logger.warning(f"Holafly global: catalog fetch failed: {exc}")
        return []

    handles = _holafly_country_handles()
    for slug, country_heb in handles:
        try:
            product = catalog.get(slug)
            if not product:
                continue          # not sold (or not listed) by Holafly

            variants = product.get("variants", [])
            for v in variants:
                if v.get("available") is False:
                    continue
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

        except Exception as exc:
            logger.warning(f"Holafly {slug}: {exc}")
            continue

    logger.info(f"Holafly global: {len(all_plans)} plans from {success_count}/{len(handles)} countries")
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
    # Until 2026-11-20 the next two were a price list typed into this file
    # ("no Shopify API") - it had drifted from the shop (7 days: 42.90 vs 38.90)
    # and its rows got a fresh scraped_at on every run, hiding a blocked scraper.
    "medio-oriente-actualizado":    "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",  # המזרח התיכון
    "africa-actualizado":           "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",  # אפריקה
    "world":                        "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",  # גלובלי
    # Cruise (at sea) products. The "\u05e7\u05e8\u05d5\u05d6" prefix is what the frontend's
    # isCruiseDest and db._CRUISE_SOURCE_DESTS key on - keep both in step.
    "europe-cruise": "\u05e7\u05e8\u05d5\u05d6 - \u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",  # קרוז - אירופה
    "mediterranean-cruise": "\u05e7\u05e8\u05d5\u05d6 - \u05d4\u05d9\u05dd \u05d4\u05ea\u05d9\u05db\u05d5\u05df",  # קרוז - הים התיכון
    "caribbean-cruise": "\u05e7\u05e8\u05d5\u05d6 - \u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",  # קרוז - קריביים
    "alaska-cruise": "\u05e7\u05e8\u05d5\u05d6 - \u05d0\u05dc\u05e1\u05e7\u05d4",  # קרוז - אלסקה
}


def scrape_holafly_regions(_page=None, usd_rate=None):
    """Scrape Holafly regional eSIM plans via Shopify product JSON API (no Playwright needed).
    All Holafly regional plans offer unlimited data. Filters to key durations only."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    all_plans = []
    success_count = 0

    try:
        catalog = _holafly_catalog_by_handle()
    except HolaflyRateLimited as exc:
        logger.warning(f"Holafly regions: no catalog this run ({exc})")
        catalog = {}
    except Exception as exc:
        logger.warning(f"Holafly regions: catalog fetch failed: {exc}")
        catalog = {}

    for slug, region_heb in HOLAFLY_REGIONS.items():
        try:
            product = catalog.get(slug)
            if not product:
                continue

            variants = product.get("variants", [])
            for v in variants:
                if v.get("available") is False:
                    continue      # e.g. the Caribbean cruise sells 31 of its 90 durations
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

        except Exception as exc:
            logger.warning(f"Holafly region {slug}: {exc}")
            continue

    logger.info(f"Holafly regions: {len(all_plans)} plans from {success_count}/{len(HOLAFLY_REGIONS)} regions")
    return all_plans
