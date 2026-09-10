"""bnesim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# No public API / Store API: each destination page embeds a single schema.org
# <script type="application/ld+json"> Product with an AggregateOffer. The sitemap
# enumerates the 186 destination pages (~176 countries + 10 regions). Anonymous
# requests are priced in EUR; plans are data-only (no minutes/SMS). Destination =
# Product.name ("eSIM <Country>"), mapped to Hebrew via ORBIT_NAME_TO_HEBREW first,
# then the supplements below (regions + countries Orbit lacks) — all validated
# against the live global_plans destinations so they don't flap change-detection.
_BNESIM_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


BNESIM_REGION_TO_HEBREW = {
    "Africa": "אפריקה",
    "Asia": "אסיה",
    "Caribbean": "קריביים",
    "Europe": "אירופה",
    "Global": "גלובלי",
    "Middle East": "המזרח התיכון",
    "Mini Global": "גלובלי מיני",
    "North America": "צפון אמריקה",
    "Oceania": "אוקיאניה",
    "South America": "דרום אמריקה",
}


BNESIM_NAME_TO_HEBREW = {
    "American Samoa": "סמואה האמריקנית",
    "Antigua and Barbuda": "אנטיגואה וברבודה",
    "Bhutan": "בהוטן",
    "Bosnia and Herzegovina": "בוסניה והרצגובינה",
    "Brunei Darussalam": "ברוניי",
    "Democratic Republic of the Congo": "הרפובליקה הדמוקרטית של קונגו",
    "Israel": "ישראל",
    "Macao": "מקאו",
    "Maldives": "האיים המלדיביים",
    "North Macedonia": "מקדוניה הצפונית",
    "Republic of Montenegro": "מונטנגרו",
    "Republic of the Congo": "רפובליקת קונגו",
    "Russian Federation": "רוסיה",
    "Saint Barthelemy": "סן ברתלמי",
    "Saint Kitts and Nevis": "סנט קיטס ונוויס",
    "Saint Martin": "סן מרטן",
    "Saint Vincent and The Grenadines": "סנט וינסנט והגרנדינים",
    "Swaziland": "אסוואטיני",
    "TimorLeste": "מזרח טימור",
    "Trinidad and Tobago": "טרינידד וטובגו",
    "Turks and Caicos Islands": "איי טרקס וקייקוס",
    "Türkiye": "טורקיה",
    "United Republic of Tanzania": "טנזניה",
    "Venezuela": "ונצואלה",
    "Virgin Islands, British": "איי הבתולה הבריטיים",
    "Yemen": "תימן",
}


def _bnesim_parse_offers(html):
    """(product_name, [offer dicts]) from a page's schema.org JSON-LD, else (None, [])."""
    import json as _js
    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", html, re.S):
        try:
            d = _js.loads(block)
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product" and isinstance(d.get("offers"), dict):
            return d.get("name"), (d["offers"].get("offers") or [])
    return None, []


def scrape_bnesim_global(_page=None, eur_rate=None):
    """BNESIM eSIM catalog (186 destination pages) from the schema.org
    Product/AggregateOffer JSON-LD on each bnesim.com/plans/<slug>/ page. Pure HTTP
    (no Playwright); no public API exists. Anonymous pricing is EUR; data-only.
    _page kept for the uniform runner signature (unused)."""
    import requests
    from concurrent.futures import ThreadPoolExecutor
    from db import _DEST_NORM
    if eur_rate is None:
        eur_rate = core._get_eur_to_ils()
    try:
        sm = requests.get("https://www.bnesim.com/sitemap-0.xml", headers=_BNESIM_UA, timeout=30).text
        slugs = sorted(set(re.findall(r"<loc>https://www\.bnesim\.com/plans/([a-z0-9-]+)/</loc>", sm)))
    except Exception as exc:
        logger.warning(f"BNESIM sitemap fetch failed: {exc}")
        return []

    def _fetch(slug):
        try:
            r = requests.get(f"https://www.bnesim.com/plans/{slug}/", headers=_BNESIM_UA, timeout=25)
            r.raise_for_status()
            return _bnesim_parse_offers(r.text)
        except Exception:
            return (None, [])

    best, unmapped = {}, set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(_fetch, slugs))
    for product_name, offers in results:
        if not product_name:
            continue
        dest_en = re.sub(r"^eSIM\s+", "", product_name).strip()
        heb = (core.ORBIT_NAME_TO_HEBREW.get(dest_en)
               or BNESIM_NAME_TO_HEBREW.get(dest_en)
               or BNESIM_REGION_TO_HEBREW.get(dest_en))
        if not heb:
            unmapped.add(dest_en)
            continue
        heb = _DEST_NORM.get(heb, heb)
        for o in offers:
            name = o.get("name") or ""
            try:
                price_eur = float(o.get("price"))
            except (TypeError, ValueError):
                continue
            if price_eur <= 0:
                continue
            dm = re.search(r"(\d+)\s*days", name, re.I)
            if not dm:
                continue  # every real BNESIM offer states a validity ("... N days")
            days = int(dm.group(1))
            if re.search(r"\bunlimited\b", name, re.I):
                gb = None
                size_str = "ללא הגבלה"
            else:
                gm = re.search(r"(\d+(?:\.\d+)?)\s*GB", name, re.I)
                mm = re.search(r"(\d+(?:\.\d+)?)\s*MB", name, re.I)
                if gm:
                    gb = float(gm.group(1))
                    size_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
                elif mm:
                    mb = float(mm.group(1))
                    gb = round(mb / 1024, 4)
                    size_str = f"{int(mb)}MB"
                else:
                    continue
            plan_name = f"{heb} – {size_str} – {days} ימים"
            price_ils = round(price_eur * eur_rate, 2)
            key = (heb, gb, days)
            prev = best.get(key)
            if prev is None or price_eur < prev["_eur"]:
                plan = core._make_global_plan("bnesim", plan_name, price_ils, "EUR", price_eur,
                                         gb, days, esim=True, extras=[heb])
                plan["_eur"] = price_eur
                best[key] = plan
    plans = list(best.values())
    for p in plans:
        p.pop("_eur", None)
    if unmapped:
        logger.warning(f"BNESIM: skipped unmapped destinations {sorted(unmapped)}")
    logger.info(f"BNESIM: {len(plans)} plans from {len(slugs)} destination pages")
    return plans
