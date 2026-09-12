"""saily scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


SAILY_SLUG_TO_HEBREW = {
    "afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df", "albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4", "andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4", "antigua-and-barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4", "armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4", "australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4", "azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4", "bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9", "barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4", "belize": "\u05d1\u05dc\u05d9\u05d6",
    "benin": "\u05d1\u05e0\u05d9\u05df", "bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4", "bonaire": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4", "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9", "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4", "cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada": "\u05e7\u05e0\u05d3\u05d4", "cape-verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "cayman-islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "chad": "\u05e6'\u05d0\u05d3", "chile": "\u05e6'\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df", "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "cote-d-ivoire": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1", "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5", "cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic": "\u05e6'\u05db\u05d9\u05d4",
    "democratic-republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7", "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "east-timor": "\u05d8\u05d9\u05de\u05d5\u05e8-\u05dc\u05e1\u05d8\u05d4",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8", "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8", "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9", "faroe-islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fiji": "\u05e4\u05d9\u05d2'\u05d9", "finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france": "\u05e6\u05e8\u05e4\u05ea", "french-guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "french-polynesia": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon": "\u05d2\u05d1\u05d5\u05df", "gambia": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4", "germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "ghana": "\u05d2\u05d0\u05e0\u05d4", "gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "greece": "\u05d9\u05d5\u05d5\u05df", "greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4", "guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "guam": "\u05d2\u05d5\u05d0\u05dd", "guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9", "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4", "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9", "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2", "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3", "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4", "iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3", "isle-of-man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc", "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4", "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2'\u05e8\u05d6\u05d9", "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df", "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kosovo": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5", "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df", "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4", "lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4", "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0", "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau": "\u05de\u05e7\u05d0\u05d5", "macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8", "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4", "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali": "\u05de\u05d0\u05dc\u05d9", "malta": "\u05de\u05dc\u05d8\u05d4",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7", "mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1", "mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5", "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco": "\u05de\u05d5\u05e0\u05e7\u05d5", "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5", "montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5", "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4", "nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "nepal": "\u05e0\u05e4\u05d0\u05dc", "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3", "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4", "niger": "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "northern-mariana-islands": "\u05d0\u05d9\u05d9 \u05de\u05e8\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05d9\u05dd",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4", "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df", "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9", "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd", "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc", "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8", "republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df", "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4", "saint-barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4", "saint-martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4", "san-marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea", "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4", "seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4", "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-maarten": "\u05e1\u05df \u05de\u05e8\u05d8\u05df", "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4", "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4", "south-sudan": "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "spain": "\u05e1\u05e4\u05e8\u05d3", "sri-lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "sudan": "\u05e1\u05d5\u05d3\u05df", "suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4", "switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df", "tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4", "thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "togo": "\u05d8\u05d5\u05d2\u05d5", "tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4", "turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-and-caicos-islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4", "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4", "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "us-virgin-islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05de\u05e8\u05d9\u05e7\u05d4)",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df", "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4", "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4", "zimbabwe": "\u05d6\u05d9\u05de\u05d1\u05d1\u05d5\u05d0\u05d4",
}


# ISO 3166-1 alpha-2 -> Hebrew country name for Saily's Partners API
# (covered_countries returns ISO codes, not slugs). Derived from the canonical
# hotelDestinations.js {he, iso} list so extras[0] matches the rest of the system,
# plus a few non-ISO codes Saily uses (AS/HI/S1/SB/SX/BQ).
SAILY_ISO_TO_HEBREW = {
    "AD": "אנדורה",
    "AE": "איחוד האמירויות",
    "AF": "אפגניסטן",
    "AG": "אנטיגואה וברבודה",
    "AI": "אנגווילה",
    "AL": "אלבניה",
    "AM": "ארמניה",
    "AR": "ארגנטינה",
    "AS": "סמואה האמריקנית",
    "AT": "אוסטריה",
    "AU": "אוסטרליה",
    "AW": "ארובה",
    "AZ": "אזרבייג'ן",
    "BA": "בוסניה והרצגובינה",
    "BB": "ברבדוס",
    "BD": "בנגלדש",
    "BE": "בלגיה",
    "BF": "בורקינה פאסו",
    "BG": "בולגריה",
    "BH": "בחריין",
    "BJ": "בנין",
    "BL": "סן ברתלמי",
    "BM": "ברמודה",
    "BN": "ברוניי",
    "BO": "בוליביה",
    "BQ": "בונייר",
    "BR": "ברזיל",
    "BS": "איי הבהאמה",
    "BW": "בוטסואנה",
    "BZ": "בליז",
    "CA": "קנדה",
    "CD": "הרפובליקה הדמוקרטית של קונגו",
    "CF": "הרפובליקה המרכז אפריקאית",
    "CG": "רפובליקת קונגו",
    "CH": "שוויץ",
    "CI": "חוף השנהב",
    "CL": "צ'ילה",
    "CM": "קמרון",
    "CN": "סין",
    "CO": "קולומביה",
    "CR": "קוסטה ריקה",
    "CV": "קייפ ורדה",
    "CW": "קוראסאו",
    "CY": "קפריסין",
    "CZ": "צ'כיה",
    "DE": "גרמניה",
    "DK": "דנמרק",
    "DM": "דומיניקה",
    "DO": "הרפובליקה הדומיניקנית",
    "DZ": "אלג'יריה",
    "EC": "אקוודור",
    "EE": "אסטוניה",
    "EG": "מצרים",
    "ES": "ספרד",
    "FI": "פינלנד",
    "FJ": "פיג'י",
    "FO": "איי פארו",
    "FR": "צרפת",
    "GA": "גאבון",
    "GB": "בריטניה",
    "GD": "גרנדה",
    "GE": "גאורגיה",
    "GF": "גיאנה הצרפתית",
    "GG": "גרנזי",
    "GH": "גאנה",
    "GI": "גיברלטר",
    "GL": "גרינלנד",
    "GM": "גמביה",
    "GN": "גינאה",
    "GP": "גוואדלופ",
    "GR": "יוון",
    "GT": "גואטמלה",
    "GU": "גואם",
    "GW": "גינאה ביסאו",
    "GY": "גיאנה",
    "HI": "הוואי",
    "HK": "הונג קונג",
    "HN": "הונדורס",
    "HR": "קרואטיה",
    "HT": "האיטי",
    "HU": "הונגריה",
    "ID": "אינדונזיה",
    "IE": "אירלנד",
    "IL": "ישראל",
    "IM": "האי מאן",
    "IN": "הודו",
    "IQ": "עיראק",
    "IS": "איסלנד",
    "IT": "איטליה",
    "JE": "ג'רזי",
    "JM": "ג'מייקה",
    "JO": "ירדן",
    "JP": "יפן",
    "KE": "קניה",
    "KG": "קירגיזסטן",
    "KH": "קמבודיה",
    "KN": "סנט קיטס ונוויס",
    "KR": "דרום קוריאה",
    "KW": "כוויית",
    "KY": "איי קיימן",
    "KZ": "קזחסטן",
    "LA": "לאוס",
    "LC": "סנט לוסיה",
    "LI": "ליכטנשטיין",
    "LK": "סרי לנקה",
    "LR": "ליבריה",
    "LS": "לסוטו",
    "LT": "ליטא",
    "LU": "לוקסמבורג",
    "LV": "לטביה",
    "MA": "מרוקו",
    "MC": "מונקו",
    "MD": "מולדובה",
    "ME": "מונטנגרו",
    "MF": "סן מרטן",
    "MG": "מדגסקר",
    "MK": "מקדוניה הצפונית",
    "ML": "מאלי",
    "MN": "מונגוליה",
    "MO": "מקאו",
    "MP": "איי מריאנה הצפוניים",
    "MQ": "מרטיניק",
    "MR": "מאוריטניה",
    "MS": "מונסראט",
    "MT": "מלטה",
    "MU": "מאוריציוס",
    "MV": "האיים המלדיביים",
    "MW": "מלאווי",
    "MX": "מקסיקו",
    "MY": "מלזיה",
    "MZ": "מוזמביק",
    "NA": "נמיביה",
    "NE": "ניג'ר",
    "NG": "ניגריה",
    "NI": "ניקראגואה",
    "NL": "הולנד",
    "NO": "נורבגיה",
    "NP": "נפאל",
    "NR": "נאורו",
    "NZ": "ניו זילנד",
    "OM": "עומאן",
    "PA": "פנמה",
    "PE": "פרו",
    "PF": "פולינזיה הצרפתית",
    "PG": "פפואה גינאה החדשה",
    "PH": "הפיליפינים",
    "PK": "פקיסטן",
    "PL": "פולין",
    "PR": "פוארטו ריקו",
    "PT": "פורטוגל",
    "PY": "פראגוואי",
    "QA": "קטר",
    "RE": "ראוניון",
    "RO": "רומניה",
    "RS": "סרביה",
    "RW": "רואנדה",
    "S1": "האנטילים ההולנדיים",
    "SA": "ערב הסעודית",
    "SB": "איי שלמה",
    "SC": "איי סיישל",
    "SD": "סודן",
    "SE": "שבדיה",
    "SG": "סינגפור",
    "SI": "סלובניה",
    "SK": "סלובקיה",
    "SL": "סיירה ליאונה",
    "SM": "סן מרינו",
    "SN": "סנגל",
    "SR": "סורינאם",
    "SS": "דרום סודן",
    "SV": "אל סלבדור",
    "SX": "סנט מארטן",
    "SZ": "אסוואטיני",
    "TC": "איי טורקס וקאיקוס",
    "TD": "צ'אד",
    "TG": "טוגו",
    "TH": "תאילנד",
    "TJ": "טג'יקיסטן",
    "TL": "טימור לסטה",
    "TN": "תוניסיה",
    "TO": "טונגה",
    "TR": "טורקיה",
    "TT": "טרינידד וטובגו",
    "TW": "טייוואן",
    "TZ": "טנזניה",
    "UA": "אוקראינה",
    "UG": "אוגנדה",
    "US": "ארצות הברית",
    "UY": "אורוגוואי",
    "UZ": "אוזבקיסטן",
    "VC": "סנט וינסנט והגרדינים",
    "VE": "ונצואלה",
    "VG": "איי הבתולה (בריטניה)",
    "VI": "איי הבתולה (ארה\"ב)",
    "VN": "וייטנאם",
    "VU": "ונואטו",
    "WS": "סמואה",
    "XK": "קוסובו",
    "YT": "מאיוט",
    "ZA": "דרום אפריקה",
    "ZM": "זמביה",
    "ZW": "זימבבואה",
}


# Saily Partners API region codes -> Hebrew (multi-country plans carry `region`).
SAILY_API_REGION_TO_HEBREW = {
    "EU":   "אירופה",
    "GLB":  "גלובלי",
    "ASA":  "אסיה ואוקיאניה",
    "NAM":  "צפון אמריקה",
    "CIS":  "חבר העמים",
    "LAT":  "אמריקה הלטינית",
    "MENA": "המזרח התיכון וצפון אפריקה",
    "AFR":  "אפריקה",
}


_SAILY_API_URL = "https://web.saily.com/v3/partners/plans?utm_source=moca"


# Cloudflare in front of web.saily.com fingerprints the client: a plain urllib
# request 403s, but a browser User-Agent + Referer (via requests) passes.
_SAILY_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://partners.saily.com/",
}


_SAILY_API_CACHE = {"ts": 0.0, "items": None}


def _fetch_saily_api(force=False):
    """GET the Saily Partners API once and cache for 10 min (the global and
    regional scrape fns run in the same cycle and share this). Returns items[]."""
    import time
    import requests
    now = time.time()
    if not force and _SAILY_API_CACHE["items"] is not None and now - _SAILY_API_CACHE["ts"] < 600:
        return _SAILY_API_CACHE["items"]
    resp = requests.get(_SAILY_API_URL, headers=_SAILY_API_HEADERS, timeout=30)
    resp.raise_for_status()
    items = (resp.json() or {}).get("items", []) or []
    _SAILY_API_CACHE["ts"] = now
    _SAILY_API_CACHE["items"] = items
    return items


def _saily_api_item_to_plan(item, heb_name, usd_rate):
    """Convert one Saily API plan item into the internal global-plan dict."""
    bal = next((b for b in (item.get("balances") or []) if b.get("type") == "DATA"), None)
    if item.get("is_unlimited") or (bal and bal.get("is_unlimited")):
        gb = None
    elif bal is not None and bal.get("amount") is not None:
        gb = bal["amount"]
    else:
        return None
    dur = item.get("duration") or {}
    if dur.get("unit") != "day" or dur.get("amount") is None:
        return None
    days = dur["amount"]
    # amount_with_tax is in minor units (cents); take the cheapest USD merchant plan.
    usd_mps = [mp for mp in (item.get("merchant_plans") or [])
               if mp.get("price") and mp["price"].get("amount_with_tax") is not None
               and mp["price"].get("currency") == "USD"]
    if not usd_mps:
        return None
    cheapest = min(usd_mps, key=lambda mp: mp["price"]["amount_with_tax"])
    price_usd = round(cheapest["price"]["amount_with_tax"] / 100.0, 2)
    price_ils = round(price_usd * usd_rate, 2)
    # planId for the Saily checkout deep-link: the price `identifier` is the checkout
    # token for THIS merchant plan, consumed by app.py `_saily_checkout_url` via /go.
    plan_ref = cheapest["price"].get("identifier")
    if gb is None:
        gb_str = "ללא הגבלה"
    elif gb >= 1:
        gb_str = f"{int(gb)}GB"
    else:
        gb_str = f"{round(gb * 1024)}MB"
    plan_name = f"{heb_name} – {gb_str} – {days} ימים"
    plan = core._make_global_plan("saily", plan_name, price_ils, "USD", price_usd,
                             gb, days, esim=True, extras=[heb_name])
    if plan_ref:
        plan["plan_ref"] = plan_ref
    return plan


def scrape_saily_global(_page=None, usd_rate=None):
    """Saily single-country eSIM plans via the official Partners API
    (utm_source=moca). Replaces the old per-country Playwright scrape (~199 page
    loads, brittle behind Cloudflare) with one JSON call. _page kept for the
    runner's uniform signature; unused."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    all_plans = []
    unmapped = set()
    try:
        items = _fetch_saily_api()
    except Exception as exc:
        logger.warning(f"Saily API fetch failed (global): {exc}")
        return all_plans
    for item in items:
        cc = item.get("covered_countries") or []
        if len(cc) != 1:
            continue
        heb = SAILY_ISO_TO_HEBREW.get(cc[0])
        if not heb:
            unmapped.add(cc[0])
            continue
        plan = _saily_api_item_to_plan(item, heb, usd_rate)
        if plan:
            all_plans.append(plan)
    if unmapped:
        logger.warning(f"Saily global: skipped unmapped ISO codes {sorted(unmapped)}")
    logger.info(f"Saily global: {len(all_plans)} plans (Partners API, single-country)")
    return all_plans


def scrape_saily_regions(_page=None, usd_rate=None):
    """Saily regional eSIM plans via the official Partners API (utm_source=moca).
    Multi-country items carry a `region` code (EU/GLB/ASA/NAM/CIS/LAT/MENA/AFR).
    Replaces the old per-region Playwright scrape. _page unused (uniform sig)."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    all_plans = []
    unmapped = set()
    try:
        items = _fetch_saily_api()
    except Exception as exc:
        logger.warning(f"Saily API fetch failed (regions): {exc}")
        return all_plans
    for item in items:
        cc = item.get("covered_countries") or []
        if len(cc) <= 1:
            continue
        heb = SAILY_API_REGION_TO_HEBREW.get(item.get("region"))
        if not heb:
            unmapped.add(item.get("region"))
            continue
        plan = _saily_api_item_to_plan(item, heb, usd_rate)
        if plan:
            all_plans.append(plan)
    if unmapped:
        logger.warning(f"Saily regions: skipped unmapped region codes {sorted(unmapped)}")
    logger.info(f"Saily regions: {len(all_plans)} plans (Partners API, regional)")
    return all_plans
