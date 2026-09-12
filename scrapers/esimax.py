"""esimax scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# Israeli WooCommerce shop (Hebrew product names), USD prices in minor units.
# Site spellings that differ from the canonical names AND aren't already
# _DEST_NORM keys. "קונגו" must be fixed HERE: the site sells BOTH Congos
# (slug republic-of-the-congo vs democratic-republic-of-the-congo), while the
# global _DEST_NORM maps bare "קונגו" to the DRC — wrong for this site.
ESIMAX_NAME_FIX = {
    "גרנסי": "גרנזי",
    "איי אלנד": "איי אולנד",
    "קונגו": "רפובליקת קונגו",
}


# Regional/global products, matched by cleaned product NAME → (plan title, dest).
# dest is the canonical extras[0]; title leads the plan_name. "אירופה 30+"
# keeps its site name as the title to stay distinct from the full 41-country
# "אירופה" product (same dest, different coverage — see ESIMAX_REGION_MAP in
# globalCountries.js). "סין (היבשת)" actually covers mainland+HK+Macao, so it
# uses the canonical combo dest shared with Holafly/ByteSIM/Besim.
ESIMAX_REGION_NAMES = {
    "אירופה": ("אירופה", "אירופה"),
    "אירופה 30+": ("אירופה 30+", "אירופה"),
    "מדינות הבלקן": ("בלקן", "בלקן"),
    "האיים הקריביים": ("האיים הקריביים", "האיים הקריביים"),
    "מרכז אסיה": ("מרכז אסיה", "מרכז אסיה"),
    "אוקיאניה": ("אוקיאניה", "אוקיאניה"),
    "סינגפור מלזיה ותאילנד": ("סינגפור, מלזיה, תאילנד", "סינגפור, מלזיה, תאילנד"),
    "אסיה": ("אסיה", "אסיה"),
    "סין (היבשת)": ("סין + הונג קונג + מקאו", "סין + הונג קונג + מקאו"),
    "המזרח התיכון": ("המזרח התיכון", "המזרח התיכון"),
    "אפריקה": ("אפריקה", "אפריקה"),
    "צפון אמריקה": ("צפון אמריקה", "צפון אמריקה"),
    "דרום אמריקה": ("דרום אמריקה", "דרום אמריקה"),
    "גלובלי": ("גלובלי", "גלובלי"),
}


def scrape_esimax_global(_page=None, usd_rate=None):
    """Scrape the eSIM Max (esimax.io) catalog via the public WooCommerce Store API.

    Two paginated pulls via the shared Woo fetcher: parent products (~179
    variable products — 165 Hebrew country names + 14 regional/global bundles)
    and their variations (~1,100; "נפח גלישה: 10GB, כמות ימים: 30 ימים"
    attribute string + USD price in minor units). The "אירופה 30+" product's
    variations carry an EMPTY attribute string — their GB/days are parsed from
    the variation slug ("אירופה-30-1gb-30-ימים") instead. Duplicate
    (title, size, days) tiers keep the cheapest price.
    """
    import html as _html
    import urllib.parse as _urlparse
    from db import _DEST_NORM

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    def clean_name(raw):
        n = _html.unescape(raw or "").replace("׳", "'").replace("’", "'")
        return re.sub(r"\s+", " ", n).strip()

    parents = core._woo_store_fetch(
        "https://esimax.io/wp-json/wc/store/v1/products", "eSIM Max")

    title_dest_by_parent, unmapped = {}, set()
    for p in parents:
        if p.get("type") != "variable":
            continue
        name = clean_name(p.get("name"))
        if not name or "test" in name.lower():
            continue
        if name in ESIMAX_REGION_NAMES:
            title_dest_by_parent[p["id"]] = ESIMAX_REGION_NAMES[name]
            continue
        dest = ESIMAX_NAME_FIX.get(name, name)
        dest = _DEST_NORM.get(dest, dest)
        if not re.fullmatch(r"[֐-׿][֐-׿ '\"()\-]*", dest):
            unmapped.add(name)  # Latin/odd name — not a destination product
            continue
        title_dest_by_parent[p["id"]] = (dest, dest)

    variations = core._woo_store_fetch(
        "https://esimax.io/wp-json/wc/store/v1/products?type=variation",
        "eSIM Max variations")

    best = {}  # plan_name -> plan dict (cheapest wins)
    for v in variations:
        td = title_dest_by_parent.get(v.get("parent"))
        if not td:
            continue
        title, dest = td
        attrs = v.get("variation") or ""
        m_data = re.search(r"([\d.]+)\s*(GB|MB)", attrs, re.I)
        m_days = re.search(r"(\d+)\s*(?:ימים|יום)", attrs)
        if m_data and m_days:
            val, unit, days = float(m_data.group(1)), m_data.group(2).upper(), int(m_days.group(1))
        else:
            # "אירופה 30+" variations: empty attrs, spec lives in the slug
            slug = _urlparse.unquote(v.get("slug") or "")
            m = re.search(r"([\d.]+)\s*(gb|mb)-(\d+)-ימים", slug, re.I)
            if not m:
                continue
            val, unit, days = float(m.group(1)), m.group(2).upper(), int(m.group(3))
        gb = round(val / 1024, 4) if unit == "MB" else val
        gb_str = (f"{int(val)}" if val == int(val) else f"{val}") + unit
        try:
            prices = v.get("prices") or {}
            minor = int(prices.get("currency_minor_unit") or 2)
            usd = int(prices.get("price")) / (10 ** minor)
        except (TypeError, ValueError):
            continue
        if usd <= 0 or days <= 0:
            continue
        day_unit = "יום" if days == 1 else "ימים"
        plan_name = f"{title} – {gb_str} – {days} {day_unit}"
        if plan_name in best and best[plan_name]["original_price"] <= usd:
            continue  # keep the cheapest duplicate tier (UNIQUE(carrier, plan_name))
        best[plan_name] = core._make_global_plan(
            "esimax", plan_name, round(usd * usd_rate, 2), "USD", round(usd, 2),
            data_gb=gb, days=days, esim=True, extras=[dest],
        )
    if unmapped:
        logger.warning(f"eSIM Max: skipped non-destination products {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"eSIM Max: {len(plans)} plans from {len(title_dest_by_parent)} products")
    return plans
