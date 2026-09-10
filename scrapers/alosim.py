"""alosim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# Destination slug (strip -esim) -> Hebrew via alias -> SAILY_SLUG_TO_HEBREW ->
# aloSIM extras (regions, countries Saily lacks, US sub-national). Palestine
# (state-of-palestine-esim) left unmapped -> skipped. Prices are USD (the IL
# backend sees $).
_ALOSIM_EXTRA = {
    # regions
    "africa-esim": "אפריקה", "asia-esim": "אסיה", "australia-and-nz-esim": "אוסטרליה וניו זילנד",
    "caribbean-esim": "איי הקריביים", "central-america-esim": "מרכז אמריקה",
    "eastern-europe-esim": "מזרח אירופה", "europe-esim": "אירופה", "global-esim": "גלובלי",
    "middle-east-esim": "המזרח התיכון", "north-america-esim": "צפון אמריקה",
    "oceania-esim": "אוקיאניה", "scandinavia-esim": "סקנדינביה", "south-america-esim": "דרום אמריקה",
    "western-europe-esim": "מערב אירופה", "uk-ireland-esim": "בריטניה ואירלנד",
    # countries Saily lacks / naming differences
    "belarus-esim": "בלארוס", "bhutan-esim": "בהוטן", "cabo-verde-esim": "קייפ ורדה",
    "democratic-republic-of-the-congo-esim": "הרפובליקה הדמוקרטית של קונגו",
    "ethiopia-esim": "אתיופיה", "kiribati-esim": "קיריבטי", "lebanon-esim": "לבנון",
    "republic-of-the-congo-esim": "רפובליקת קונגו", "saint-vincent-esim": "סנט וינסנט והגרדינים",
    "the-sudan-esim": "סודן", "timor-leste-esim": "טימור לסטה",
    "turks-and-caicos-esim": "איי טורקס וקאיקוס", "vatican-city-esim": "הוותיקן",
    "french-guiana-and-martinique-esim": "גיאנה הצרפתית ומרטיניק",
    "ivory-coast-cote-divoire-esim": "חוף השנהב", "saint-martin-esim-french": "סן מרטן",
    # sub-national / cities
    "bali": "באלי", "california-esim": "קליפורניה", "florida": "פלורידה", "hawaii": "הוואי",
    "new-york": "ניו יורק", "texas": "טקסס", "halifax-esim": "הליפקס", "toronto": "טורונטו",
}


def _alosim_resolve(slug):
    base = re.sub(r"-esim$", "", slug or "")
    base = core._UBIGI_ALIAS.get(base, base)
    return core.SAILY_SLUG_TO_HEBREW.get(base) or _ALOSIM_EXTRA.get(slug)


def _alosim_page_plans(url, heb, usd_rate):
    import requests, time as _t
    html = None
    for attempt in range(3):  # aloSIM (Wordfence/Cloudflare) rate-limits at scale → retry
        try:
            r = requests.get(url, headers={"User-Agent": core._YESIM_UA}, timeout=30)
            if r.status_code == 200 and "data-package-id" in r.text:
                html = r.text
                break
        except Exception:
            pass
        _t.sleep(1.5 * (attempt + 1))
    if not html:
        return []
    prices = dict(re.findall(r'data-location-package-id="([^"]+)"[^>]*>\s*([\d.]+)\s*<', html))
    pkgs = re.findall(
        r'data-package-id="([^"]+)"[^>]*data-package-type="([^"]*)"[^>]*'
        r'data-package-days-count="(\d+)"[^>]*data-package-gb="([^"]*)"', html)
    out = []
    for pid, ptype, days, gbtext in pkgs:
        ps = prices.get(pid)
        if not ps:
            continue
        try:
            price_usd = round(float(ps), 2)
        except ValueError:
            continue
        if price_usd <= 0:
            continue
        if "unlimited" in (gbtext or "").lower() or ptype == "unlimited":
            gb = None
        else:
            mg = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)", gbtext, re.I)
            if not mg:
                continue
            gb = float(mg.group(1)) / 1024 if mg.group(2).upper() == "MB" else float(mg.group(1))
        price_ils = round(price_usd * usd_rate, 2)
        if gb is None:
            gb_str = "ללא הגבלה"
        elif gb >= 1:
            gb_str = f"{int(gb)}GB"
        else:
            gb_str = f"{round(gb * 1024)}MB"
        out.append((f"{heb} – {gb_str} – {int(days)} ימים", price_ils, price_usd, gb, int(days), heb))
    return out


def scrape_alosim_global(_page=None, usd_rate=None):
    """aloSIM eSIM plans. Enumerate destinations via the WP REST `location` type,
    then parse each destination page's `location-package-v2` blocks (data-attrs +
    price spans joined by package id). Dedups by plan_name keeping the cheapest."""
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    locs = []
    for page in range(1, 5):
        try:
            r = requests.get(f"https://alosim.com/wp-json/wp/v2/location?per_page=100&page={page}&_fields=slug,link",
                             headers={"User-Agent": core._YESIM_UA}, timeout=40)
        except Exception:
            break
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        locs += batch
    targets, unmapped = [], set()
    for l in locs:
        heb = _alosim_resolve(l.get("slug"))
        if heb and l.get("link"):
            targets.append((l["link"], heb))
        elif not heb:
            unmapped.add(l.get("slug"))
    best = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_alosim_page_plans, link, heb, usd_rate): link for (link, heb) in targets}
        for f in as_completed(futs):
            try:
                for (pn, pil, pusd, gb, days, heb) in f.result():
                    if pn not in best or pil < best[pn][0]:
                        best[pn] = (pil, pusd, gb, days, heb)
            except Exception as exc:
                logger.warning(f"aloSIM {futs[f]}: {exc}")
    if unmapped:
        logger.warning(f"aloSIM: skipped unmapped {sorted(unmapped)[:30]}")
    all_plans = [core._make_global_plan("alosim", pn, pil, "USD", pusd, gb, days, esim=True, extras=[heb])
                 for pn, (pil, pusd, gb, days, heb) in best.items()]
    logger.info(f"aloSIM global: {len(all_plans)} plans from {len(targets)} destinations")
    return all_plans
