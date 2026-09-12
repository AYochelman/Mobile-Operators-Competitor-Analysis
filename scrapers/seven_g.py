"""seven_g scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module
logger = core.logger


SEVEN_G_DESTINATIONS = [
    "Afghanistan", "Africa", "Africa (25+ areas)", "Albania", "Algeria", "Andorra",
    "Anguilla", "Antigua And Barbuda", "Antilles", "Argentina", "Armenia", "Aruba",
    "Asia (12 areas)", "Asia (20 areas)", "Asia (20+ areas)", "Asia (7 areas)",
    "Australia", "Australia & New Zealand", "Austria", "Azerbaijan", "Azores",
    "Bahamas", "Bahrain", "Balkans (5+ areas)", "Bangladesh", "Barbados", "Belarus",
    "Belgium", "Belize", "Benin", "Bermuda", "Bhutan", "Bolivia", "Bonaire",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "British Virgin Islands", "Brunei",
    "Bulgaria", "Burkina Faso", "Burundi", "Cambodia", "Cameroon", "Canada",
    "Canary Islands", "Cape Verde", "Caribbean Islands", "Cayman Islands",
    "Central African Republic", "Central Asia", "Chad", "Chile", "China",
    "China mainland & Japan & South Korea", "Colombia", "Costa Rica",
    "Côte d'Ivoire", "Croatia", "Curaçao", "Cyprus",
    "Czech Republic", "Democratic Republic Of The Congo", "Denmark", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Estonia", "Eswatini",
    "Ethiopia", "Europe (30+ areas)", "Europe (40+ areas)", "Faroe Islands", "Fiji",
    "Finland", "France", "French Guiana", "French Polynesia", "Gabon", "Gambia",
    "GCC", "Georgia", "Germany", "Ghana", "Gibraltar", "Global (120+ areas)",
    "Global (130+ areas)", "Greece", "Greenland", "Grenada", "Guadeloupe", "Guam",
    "Guatemala", "Guinea", "Guinea-Bissau", "Gulf Region", "Guyana", "Haiti",
    "Honduras", "Hong Kong", "Hungary", "Iceland", "India", "Indonesia",
    "Iran (Islamic Republic of)", "Iraq", "Ireland", "Isle of Man", "Israel",
    "Italy", "Jamaica", "Japan", "Jersey", "Jordan", "Kazakhstan", "Kenya",
    "Kosovo", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho",
    "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Macao",
    "Madagascar", "Madeira", "Malawi", "Malaysia", "Maldives", "Mali", "Malta",
    "Marie-Galante", "Martinique", "Mauritius", "Mayotte", "Mexico", "Middle East",
    "Middle East & North Africa", "Middle East and North Africa", "Moldova",
    "Monaco", "Mongolia", "Montenegro", "Montserrat", "Morocco", "Mozambique",
    "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua",
    "Niger", "Nigeria", "North America", "North America (3 areas)",
    "North Macedonia", "Northern Cyprus", "Norway", "Oceania", "Oman", "Pakistan",
    "Palestine, State of", "Panama", "Papua New Guinea", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal", "Puerto Rico", "Qatar",
    "Republic of the Congo", "Réunion", "Romania", "Russia", "Rwanda",
    "Saba", "Saint Barthélemy", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Martin (French Part)", "Saint Vincent and the Grenadines", "Samoa",
    "Saudi Arabia", "Scotland", "Senegal", "Serbia", "Seychelles", "Sierra Leone",
    "Singapore", "Singapore & Malaysia & Thailand", "Sint Eustatius",
    "Sint Maarten (Dutch Part)", "Slovakia", "Slovenia", "South Africa",
    "South America (15+ areas)", "South Korea", "Spain", "Sri Lanka", "Suriname",
    "Sweden", "Switzerland", "Taiwan", "Tajikistan", "Tanzania", "Thailand",
    "Timor - Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey",
    "Turks and Caicos Islands", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu",
    "Vatican City", "Venezuela", "Vietnam", "Virgin Islands (U.S.)", "Zambia",
    "Zimbabwe",
]


_SEVEN_G_SLUG_OVERRIDES = {
    "republic of the congo": "congo",
}


# Canonical Hebrew region labels for extras[0] — keeps plans in the region filter
_SEVEN_G_REGION_HEB = {
    "Africa":                               "אפריקה",
    "Africa (25+ areas)":                   "אפריקה",
    "Asia (12 areas)":                      "אסיה",
    "Asia (20 areas)":                      "אסיה",
    "Asia (20+ areas)":                     "אסיה",
    "Asia (7 areas)":                       "אסיה",
    "Australia & New Zealand":              "אוקיאניה",
    "Balkans (5+ areas)":                   "בלקן",
    "Caribbean Islands":                    "איי הקריביים",
    "Central Asia":                         "מרכז אסיה",
    "China mainland & Japan & South Korea": "אסיה",
    "Europe (30+ areas)":                   "אירופה",
    "Europe (40+ areas)":                   "אירופה",
    "GCC":                                  "המזרח התיכון",
    "Global (120+ areas)":                  "גלובלי",
    "Global (130+ areas)":                  "גלובלי",
    "Gulf Region":                          "המזרח התיכון",
    "Middle East":                          "המזרח התיכון",
    "Middle East & North Africa":           "המזרח התיכון וצפון אפריקה",
    "Middle East and North Africa":         "המזרח התיכון וצפון אפריקה",
    "North America":                        "צפון אמריקה",
    "North America (3 areas)":              "צפון אמריקה",
    "Oceania":                              "אוקיאניה",
    "Singapore & Malaysia & Thailand":      "אסיה",
    "South America (15+ areas)":            "אמריקה הלטינית",
}


# Regions whose slugs can't be derived from the name — map directly to /he/esim/region/{slug}
SEVEN_G_REGION_SLUG_MAP = {
    "Africa":                                "africa",
    "Africa (25+ areas)":                    "af-29",
    "Asia (12 areas)":                       "as-12",
    "Asia (20 areas)":                       "as-20",
    "Asia (20+ areas)":                      "as-21",
    "Asia (7 areas)":                        "as-7",
    "Australia & New Zealand":               "aunz-2",
    "Balkans (5+ areas)":                    "eu-7",
    "Caribbean Islands":                     "caribbean-islands",
    "Central Asia":                          "as-5",
    "China mainland & Japan & South Korea":  "cnjpkr-3",
    "Europe (30+ areas)":                    "eu-30",
    "Europe (40+ areas)":                    "eu-42",
    "GCC":                                   "gcc",
    "Global (120+ areas)":                   "gl-120",
    "Global (130+ areas)":                   "gl-139",
    "Gulf Region":                           "me-6",
    "Middle East":                           "me-13",
    "Middle East & North Africa":            "me-12",
    "Middle East and North Africa":          "middle-east-and-north-africa",
    "North America":                         "north-america",
    "North America (3 areas)":               "na-3",
    "Oceania":                               "oceania",
    "Singapore & Malaysia & Thailand":       "sgmyth-3",
    "South America (15+ areas)":             "sa-18",
}


def _seven_g_slugify(name):
    import unicodedata as _ud
    lower = name.lower()
    if lower in _SEVEN_G_SLUG_OVERRIDES:
        return _SEVEN_G_SLUG_OVERRIDES[lower]
    name = re.sub(r"\s*\([^)]*\)", "", name).strip()
    n = _ud.normalize("NFD", name)
    n = "".join(c for c in n if _ud.category(c) != "Mn")
    n = n.replace("'", "").replace("’", "")
    n = n.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    return slug


def _parse_seven_g_page(html, usd_rate, eng_name, extras_region=None):
    from html.parser import HTMLParser as _HP

    class _TE(_HP):
        def __init__(self):
            super().__init__()
            self.texts = []

        def handle_data(self, d):
            if d.strip():
                self.texts.append(d.strip())

    p = _TE()
    p.feed(html)
    lines = p.texts

    # Hebrew name from title: "eSIM ל{name} – ..."
    heb_name = eng_name
    title_m = re.search(r"<title>([^<]+)</title>", html)
    if title_m:
        m = re.search(r"eSIM [לב](.+?) [–—]", title_m.group(1))
        if m:
            heb_name = _html_unescape(m.group(1)).strip()

    # Parse plan blocks: N GB → M ימים → US$ → price (each plan appears twice)
    seen = {}
    i = 0
    while i < len(lines):
        gb_m = re.match(r"^(\d+(?:\.\d+)?)\s*GB$", lines[i], re.I)
        if gb_m and i + 2 < len(lines):
            day_m = re.match(r"^(\d+)\s*ימים$", lines[i + 1])
            if day_m:
                price = None
                for j in range(i + 2, min(i + 8, len(lines))):
                    if lines[j] == "US$" and j + 1 < len(lines):
                        pm = re.match(r"^(\d+\.?\d*)$", lines[j + 1])
                        if pm:
                            price = float(pm.group(1))
                            break
                    pm = re.match(r"^US\$(\d+\.?\d*)$", lines[j])
                    if pm:
                        price = float(pm.group(1))
                        break
                if price is not None:
                    gb = float(gb_m.group(1))
                    days = int(day_m.group(1))
                    key = (gb, days)
                    if key not in seen or price < seen[key]:
                        seen[key] = price
        i += 1

    plans = []
    for (gb, days), usd in seen.items():
        gb_label = int(gb) if gb == int(gb) else gb
        plans.append(core._make_global_plan(
            "seven_g", f"{heb_name} – ‏{gb_label}GB – ‏{days} ימים",
            round(usd * usd_rate, 2), "USD", usd,
            gb, days, extras=[extras_region if extras_region is not None else heb_name],
        ))
    return plans


def _fetch_seven_g_destination(name, usd_rate):
    import urllib.request as _ur
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    if name in SEVEN_G_REGION_SLUG_MAP:
        url = f"https://7g.app/he/esim/region/{SEVEN_G_REGION_SLUG_MAP[name]}"
        try:
            req = _ur.Request(url, headers={"User-Agent": _UA})
            with _ur.urlopen(req, timeout=15) as r:
                html = r.read().decode("utf-8")
            return _parse_seven_g_page(html, usd_rate, name, extras_region=_SEVEN_G_REGION_HEB.get(name))
        except Exception:
            return []
    slug = _seven_g_slugify(name)
    if not slug:
        return []
    try:
        req = _ur.Request(f"https://7g.app/he/esim/{slug}", headers={"User-Agent": _UA})
        with _ur.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8")
        return _parse_seven_g_page(html, usd_rate, name)
    except Exception:
        return []


def scrape_seven_g_global(_page=None, usd_rate=None):
    """Scrape 7G eSIM plans from all destinations (~190+ countries and regions)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _ac
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    all_plans = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_fetch_seven_g_destination, name, usd_rate): name
            for name in SEVEN_G_DESTINATIONS
        }
        for fut in _ac(futures):
            try:
                all_plans.extend(fut.result() or [])
            except Exception as e:
                logger.debug(f"seven_g: {futures[fut]}: {e}")
    logger.info(f"7G global: {len(all_plans)} plans from {len(SEVEN_G_DESTINATIONS)} destinations")
    return all_plans
