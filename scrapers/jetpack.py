"""jetpack scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


# Slug list derived from sitemap-product.xml (2026-04)
JETPACK_SLUGS = [
    "africa","albania","algeria","andorra","anguilla","antigua-and-barbuda","argentina","armenia","aruba",
    "asia-pacific","australia","austria","azerbaijan","bahamas","bangladesh","barbados","belgium",
    "bosnia-and-herzegovina","brazil","bulgaria","cambodia","canada","caribbean","chad","chile","china",
    "colombia","costa-rica","croatia","cyprus","czech-republic","denmark","dominican-republic","ecuador",
    "egypt","el-salvador","estonia","european-union","finland","france","georgia","germany","ghana",
    "gibraltar","global","greece","guadeloupe","guatemala","guernsey","guyana","honduras","hong-kong",
    "hungary","iceland","india","indonesia","ireland","isle-of-man","israel","italy","japan","jersey",
    "kazakhstan","kuwait","kyrgyzstan","latin-america","latvia","liechtenstein","lithuania","luxembourg",
    "macau","malaysia","malta","mauritius","mexico","middle-east-and-north-africa","moldova","mongolia",
    "morocco","myanmar","netherlands","new-zealand","nicaragua","nigeria","north-america","norway","oman",
    "paraguay","peru","philippines","poland","portugal","puerto-rico","qatar","reunion","romania","russia",
    "san-marino","saudi-arabia","serbia","slovakia","slovenia","south-africa","south-korea","southeast-asia",
    "spain","sri-lanka","sweden","switzerland","taiwan","thailand","tunisia","turkey","ukraine",
    "united-arab-emirates","united-kingdom","united-states-of-america","uruguay","uzbekistan","vatican-city",
    "vietnam",
]


# Multi-country regional slugs → Hebrew region label (extras[0] in plan dict)
JETPACK_REGION_SLUG_TO_HEBREW = {
    "africa":                       "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",                                          # אפריקה
    "asia-pacific":                 "\u05d0\u05e1\u05d9\u05d4 \u05e4\u05e1\u05d9\u05e4\u05d9\u05e7",                  # אסיה פסיפיק
    "caribbean":                    "\u05d4\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",                              # הקריביים
    "european-union":               "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",                                          # אירופה
    "global":                       "\u05db\u05dc\u05dc \u05d4\u05e2\u05d5\u05dc\u05dd",                              # כלל העולם
    "latin-america":                "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea", # אמריקה הלטינית
    "middle-east-and-north-africa": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",  # המזרח התיכון וצפון אפריקה
    "north-america":                "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",                  # צפון אמריקה
    "southeast-asia":               "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",     # דרום מזרח אסיה
}


# Single-country slug → Hebrew (extends SAILY_SLUG_TO_HEBREW for slugs unique to Jetpack)
JETPACK_EXTRA_COUNTRY_HEBREW = {
    "myanmar":                   "\u05de\u05d9\u05d0\u05e0\u05de\u05e8",                  # מיאנמר
    "russia":                    "\u05e8\u05d5\u05e1\u05d9\u05d4",                        # רוסיה
    "united-states-of-america":  "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",  # ארצות הברית
    "vatican-city":              "\u05d5\u05ea\u05d9\u05e7\u05df",                        # ותיקן
}


def _jetpack_country_heb(slug):
    if slug in JETPACK_EXTRA_COUNTRY_HEBREW:
        return JETPACK_EXTRA_COUNTRY_HEBREW[slug]
    if slug in core.SAILY_SLUG_TO_HEBREW:
        return core.SAILY_SLUG_TO_HEBREW[slug]
    # Fallback: titlecase the slug
    return slug.replace("-", " ").title()


def scrape_jetpack_global(_page=None, usd_rate=None):
    """Scrape Jetpack global eSIM plans via content.jetpacglobal.com JSON catalogs."""
    import urllib.request as _ur, urllib.error as _ue, json as _js, time as _time

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    all_plans = []
    fetched = 0
    failed = []

    def _fetch(slug):
        url = f"https://content.jetpacglobal.com/product-detail/catalogs/{slug}-esim.json"
        try:
            req = _ur.Request(url, headers={"User-Agent": _UA})
            with _ur.urlopen(req, timeout=20) as r:
                return _js.loads(r.read())
        except _ue.HTTPError as e:
            logger.warning(f"Jetpack {slug}: HTTP {e.code}")
            return None
        except Exception as e:
            logger.warning(f"Jetpack {slug}: {e}")
            return None

    def _usd_price(prices):
        for p in prices or []:
            if p.get("currency") == "USD":
                try:
                    return float(p.get("value") or p.get("listPrice") or 0)
                except Exception:
                    return None
        return None

    def _gb_part(data_in_gb):
        # -1 or 0 = unlimited
        if data_in_gb is None or data_in_gb == -1 or data_in_gb == 0:
            return None, "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"  # ללא הגבלה
        try:
            gb = float(data_in_gb)
        except Exception:
            return None, "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"
        return gb, (f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB")

    for slug in JETPACK_SLUGS:
        data = _fetch(slug)
        _time.sleep(0.03)
        if not data:
            failed.append(slug)
            continue
        fetched += 1
        catalogs = data.get("catalogs") or []
        is_region = slug in JETPACK_REGION_SLUG_TO_HEBREW
        dest_heb = JETPACK_REGION_SLUG_TO_HEBREW[slug] if is_region else _jetpack_country_heb(slug)

        for p in catalogs:
            usd_val = _usd_price(p.get("prices"))
            if usd_val is None or usd_val <= 0:
                continue
            days = p.get("validityInDays")
            data_gb, gb_str = _gb_part(p.get("dataInGB"))
            price_ils = round(usd_val * usd_rate, 2)
            days_heb = f"{days} \u05d9\u05de\u05d9\u05dd" if days else ""  # days "ימים"
            parts = [dest_heb, gb_str]
            if days_heb:
                parts.append(days_heb)
            plan_name = " \u2013 ".join(parts)
            all_plans.append(core._make_global_plan(
                "jetpack", plan_name, price_ils, "USD", usd_val,
                data_gb=data_gb, days=days, esim=True, extras=[dest_heb],
            ))

    logger.info(f"Jetpack global: {len(all_plans)} plans from {fetched} catalogs "
                f"(failed: {len(failed)})")
    return all_plans
