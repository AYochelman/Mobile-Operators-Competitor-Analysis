"""esimio scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


ESIMIO_SLUG_TO_HEBREW = {
    "afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
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
    "azores": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05d0\u05d6\u05d5\u05e8\u05d9\u05d9\u05dd",
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
    "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "canada": "\u05e7\u05e0\u05d3\u05d4",
    "canary-islands": "\u05d0\u05d9\u05d9 \u05e7\u05e0\u05e8\u05d9",
    "cape-verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "cayman-islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "chad": "\u05e6'\u05d0\u05d3",
    "chile": "\u05e6'\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df",
    "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "congo": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "cuba": "\u05e7\u05d5\u05d1\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "czechia": "\u05e6'\u05db\u05d9\u05d4",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
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
    "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iran": "\u05d0\u05d9\u05e8\u05df",
    "iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau": "\u05de\u05e7\u05d0\u05d5",
    "macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "madeira": "\u05de\u05d3\u05d9\u05d9\u05e8\u05d4",
    "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "malta": "\u05de\u05dc\u05d8\u05d4",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayoette": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "nepal": "\u05e0\u05e4\u05d0\u05dc",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "northern-cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "northern-mariana-islands": "\u05d0\u05d9\u05d9 \u05de\u05e8\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05d9\u05dd",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
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
    "republic-of-the-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "russia": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saba": "\u05e1\u05d0\u05d1\u05d4",
    "saint-barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "san-marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "scotland": "\u05e1\u05e7\u05d5\u05d8\u05dc\u05e0\u05d3",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-eustatius": "\u05e1\u05d9\u05e0\u05d8 \u05d0\u05d5\u05e1\u05d8\u05d8\u05d9\u05d5\u05e1",
    "sint-maarten": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea",
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
    "turks-and-caicos-islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "united-states-of-america": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "vatican": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


def _esimio_packages_to_plans(pkgs, dest_heb, usd_rate):
    """Convert esim.io RSC `packages` entries to MOCA global plan dicts.

    Package shape since the 2026-04 redesign: `data` in bytes, `duration` +
    `durationUnit`, price nested as {"price": 2.2, "currency": "USD", ...}.
    PAYG/unlimited teasers are skipped \u2014 only fixed-GB packages are comparable.
    """
    plans = []
    for pkg in pkgs:
        if pkg.get("isUnlimited"):
            continue
        price_obj = pkg.get("price") or {}
        try:
            data_bytes = float(pkg.get("data") or 0)
            price_usd = float(price_obj.get("price") or 0)
        except (TypeError, ValueError):
            continue
        currency = (price_obj.get("currency") or "USD").upper()
        gb = data_bytes / (1024 ** 3)
        if gb < 1 or price_usd <= 0 or currency != "USD":
            continue
        days = 30
        try:
            if pkg.get("duration") and str(pkg.get("durationUnit") or "DAYS").upper() == "DAYS":
                days = int(pkg["duration"])
        except (TypeError, ValueError):
            pass
        gb = int(gb) if gb == int(gb) else round(gb, 2)
        gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        plan_name = f"{dest_heb} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
        plans.append(core._make_global_plan(
            "esimio", plan_name, round(price_usd * usd_rate, 2), "USD", price_usd,
            gb, days, esim=True, extras=[dest_heb]
        ))
    return plans


def scrape_esimio_destinations(_page=None, usd_rate=None):
    """Scrape eSIM.io per-country plans from all destination pages.

    Since ~2026-04 esim.io runs on the eSIMO Next.js platform (assets from
    statics.esimo.com) \u2014 the old h5 plan cards are gone (only duration-tab labels
    and a PAYG teaser remain), but the full 30-day packages array is server-rendered
    into the RSC flight stream, same encoding as esimo.io. Reuses
    _esimo_extract_packages; pure HTTP, no Playwright. Catalogs/prices differ from
    esimo.io (separate brand), so it stays a distinct provider.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    def fetch_one(slug):
        return core._esimo_extract_packages(
            core._esimo_fetch(f"https://esim.io/destinations/esim-{slug}")
        )

    all_plans = []
    empty, failed = 0, 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): (s, heb) for s, heb in ESIMIO_SLUG_TO_HEBREW.items()}
        for fut in as_completed(futures):
            slug, country_heb = futures[fut]
            try:
                pkgs = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIM.io {slug}: {exc}")
                continue
            if not pkgs:
                empty += 1  # removed destination or page without embedded packages
                continue
            all_plans.extend(_esimio_packages_to_plans(pkgs, country_heb, usd_rate))
    logger.info(
        f"eSIM.io destinations: {len(all_plans)} plans from "
        f"{len(ESIMIO_SLUG_TO_HEBREW)} countries ({empty} empty, {failed} failed)"
    )
    return all_plans


ESIMIO_REGIONS = {
    "esim-europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "esim-africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "esim-asia-pacific": "\u05d0\u05e1\u05d9\u05d4 \u05e4\u05e1\u05d9\u05e4\u05d9\u05e7",
    "esim-balkans": "\u05d1\u05dc\u05e7\u05df",
    "esim-carribean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "esim-latin-america": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "esim-central-asia": "\u05de\u05e8\u05db\u05d6 \u05d0\u05e1\u05d9\u05d4",
    "esim-middle-east": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "esim-north-africa": "\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "esim-north-america": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
}


def scrape_esimio_regions(_page=None, usd_rate=None):
    """Scrape eSIM.io regional eSIM plans (10 regions).

    Same RSC-embedded packages extraction as scrape_esimio_destinations (the old
    h5-card parsing died in the 2026-04 redesign). The /regions/<slug> pages still
    use the original esim-* slugs \u2014 verified against the /regions index links.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    def fetch_one(slug):
        return core._esimo_extract_packages(
            core._esimo_fetch(f"https://esim.io/regions/{slug}")
        )

    all_plans = []
    empty, failed = 0, 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): (s, heb) for s, heb in ESIMIO_REGIONS.items()}
        for fut in as_completed(futures):
            slug, region_heb = futures[fut]
            try:
                pkgs = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIM.io region {slug}: {exc}")
                continue
            if not pkgs:
                empty += 1
                continue
            all_plans.extend(_esimio_packages_to_plans(pkgs, region_heb, usd_rate))
    logger.info(
        f"eSIM.io regions: {len(all_plans)} plans from "
        f"{len(ESIMIO_REGIONS)} regions ({empty} empty, {failed} failed)"
    )
    return all_plans
