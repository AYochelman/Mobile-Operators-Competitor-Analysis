"""ubigi scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module
logger = core.logger


# English UPPERCASE destination names -> Hebrew: html-unescape + accent-strip +
# slugify, then alias map -> SAILY_SLUG_TO_HEBREW -> Ubigi extras (countries Saily
# lacks + Ubigi regions/combos). Recurring (RBUP) subscriptions are skipped;
# Palestine + @Football Fever are left unmapped (skipped).
_UBIGI_API = "https://cellulardata.ubigi.com/wp-json/wc/store/v1/products?per_page=100&lang=en&page={}"


_UBIGI_ALIAS = {
    "usa": "united-states", "uk": "united-kingdom", "uae": "united-arab-emirates",
    "macao": "macau", "ivory-coast": "cote-d-ivoire",
}


_UBIGI_EXTRA_HEBREW = {
    # countries Saily doesn't cover / naming differences
    "angola": "אנגולה", "belarus": "בלארוס", "bhutan": "בהוטן", "burundi": "בורונדי",
    "comoros": "איי קומורו", "congo": "רפובליקת קונגו", "djibouti": "ג'יבוטי",
    "democratic-republic-of-the-congo": "הרפובליקה הדמוקרטית של קונגו",
    "ethiopia": "אתיופיה", "russia": "רוסיה", "czech-republic": "צ'כיה",
    "new-caledonia": "קלדוניה החדשה", "saint-martin-french-part": "סן מרטן",
    "cote-d-ivoire": "חוף השנהב", "bosnia-herzegovina": "בוסניה והרצגובינה",
    # multi-country combos
    "australia-nzl": "אוסטרליה וניו זילנד", "ile-of-man-channel-islands": "האי מאן ואיי התעלה",
    "macau-hong-kong": "מקאו והונג קונג", "malaysia-singapore": "מלזיה וסינגפור",
    # regions
    "africa": "אפריקה", "americas": "אמריקה", "asia": "אסיה", "caribbean": "איי הקריביים",
    "europe": "אירופה", "europe-extended": "אירופה (מורחב)", "middle-east": "המזרח התיכון",
    "oceania": "אוקיאניה", "world": "גלובלי", "scandinavia-baltic": "סקנדינביה והבלטיות",
    "best-africa": "אפריקה", "best-asia": "אסיה", "best-caribbean": "איי הקריביים",
    "best-latam": "אמריקה הלטינית", "best-middle-east": "המזרח התיכון", "best-world": "גלובלי",
}


def _ubigi_norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", _html_unescape(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _ubigi_resolve(country):
    sl = _ubigi_norm(country)
    sl = _UBIGI_ALIAS.get(sl, sl)
    return core.SAILY_SLUG_TO_HEBREW.get(sl) or _UBIGI_EXTRA_HEBREW.get(sl)


def scrape_ubigi_global(_page=None, usd_rate=None):
    """Ubigi eSIM plans from the open WooCommerce Store REST API (~11 pages, no
    auth). One-time (ONEOFF) plans only; recurring subscriptions skipped. Country/
    GB/days parsed from the `name` ('DEST • 10GB • 30 days'); price = minor units."""
    import requests
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    headers = {"User-Agent": core._YESIM_UA}
    try:
        first = requests.get(_UBIGI_API.format(1), headers=headers, timeout=40)
        total_pages = int(first.headers.get("X-WP-TotalPages", 1))
        items = list(first.json())
    except Exception as exc:
        logger.warning(f"Ubigi API page 1 failed: {exc}")
        return []
    for page in range(2, total_pages + 1):
        try:
            items.extend(requests.get(_UBIGI_API.format(page), headers=headers, timeout=40).json())
        except Exception as exc:
            logger.warning(f"Ubigi API page {page}: {exc}")
    best, unmapped = {}, set()
    for p in items:
        sku = p.get("sku") or ""
        if "ONEOFF" not in sku:
            continue
        name = _html_unescape(p.get("name") or "")
        parts = name.split("•")
        heb = _ubigi_resolve(parts[0].strip())
        if not heb:
            unmapped.add(parts[0].strip())
            continue
        rest = " ".join(parts[1:])
        if re.search(r"unlimited", rest, re.I) or "_FUP" in sku.upper():
            gb = None
        else:
            mg = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)", rest, re.I)
            if not mg:
                continue
            val = float(mg.group(1))
            gb = val / 1024 if mg.group(2).upper() == "MB" else val
        md = re.search(r"(\d+)\s*day", rest, re.I) or re.search(r"_(\d+)D\b", sku)
        if not md:
            continue
        days = int(md.group(1))
        pr = p.get("prices") or {}
        if not pr.get("price") or (pr.get("currency_code") or "USD") != "USD":
            continue
        try:
            price_usd = round(int(pr["price"]) / (10 ** int(pr.get("currency_minor_unit", 2))), 2)
        except (TypeError, ValueError):
            continue
        if price_usd <= 0:
            continue
        price_ils = round(price_usd * usd_rate, 2)
        if gb is None:
            gb_str = "ללא הגבלה"
        elif gb >= 1:
            gb_str = f"{int(gb)}GB"
        else:
            gb_str = f"{round(gb * 1024)}MB"
        plan_name = f"{heb} – {gb_str} – {days} ימים"
        if plan_name not in best or price_ils < best[plan_name][0]:
            best[plan_name] = (price_ils, price_usd, gb, days, heb, plan_name)
    if unmapped:
        logger.warning(f"Ubigi: skipped unmapped {sorted(unmapped)[:30]}")
    all_plans = [core._make_global_plan("ubigi", pn, pil, "USD", pusd, gb, days, esim=True, extras=[heb])
                 for (pil, pusd, gb, days, heb, pn) in best.values()]
    logger.info(f"Ubigi global: {len(all_plans)} plans")
    return all_plans
