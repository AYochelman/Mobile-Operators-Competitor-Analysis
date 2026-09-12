"""nisim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# Israeli WooCommerce shop, ILS prices. Product names are Hebrew country names;
# these are the site's spellings that differ from the canonical ones.
NISIM_NAME_FIX = {
    "אזרבייגאן": "אזרבייג'ן",
    "גיאורגיה": "גאורגיה",
    "באהאמאס": "איי הבהאמה",
    "בוסניה הרצגובינה": "בוסניה והרצגובינה",
    "איי הבתולה הבריטים": "איי הבתולה (בריטניה)",
    "טאיוואן": "טייוואן",
    "טוניסיה": "תוניסיה",
}


# Regional/global products (matched by cleaned product NAME — ids churn when the
# shop recreates a product). Values are canonical destination strings that the
# dest picker already knows (dest_bg_map region_keys). Coverage is NOT expanded
# per-country (the site's "רשימת מדינות" accordions are one shared Elementor
# template on every page, so no reliable per-region list exists) — same
# behavior as bytesim's region bundles.
NISIM_REGION_NAMES = {
    "eSIM אירופה": "אירופה",
    "Europe Unlimited – PAPAYA": "אירופה",
    "עולמי eSIM": "גלובלי",
    "אסיה eSIM": "אסיה",
    "אפריקה eSIM": "אפריקה",
    "בלקן eSIM": "בלקן",
    "דרום אמריקה eSIM": "דרום אמריקה",
    "האיים הקריביים eSIM": "האיים הקריביים",
    "אוקיאניה eSIM": "אוקיאניה",
    "אפריקה והמזרח התיכון": "המזרח התיכון ואפריקה",
    "צפון אמריקה": "צפון אמריקה",
}


# test items + family multi-line promos (מבצע כתום/הוט/ישראכרט, קומבינציה)
_NISIM_SKIP_CATS = {"TEST", "test2", "מבצע משפחה"}


def _nisim_fetch_json(path):
    import json as _json
    return _json.loads(core._esimo_fetch(f"https://www.nisim-esim.co.il/wp-json/wc/store/v1/{path}"))


def scrape_nisim_global(_page=None, usd_rate=None):
    """Scrape the Nisim eSIM catalog via the public WooCommerce Store API.

    Two paginated pulls: parent products (name = Hebrew destination, categories
    used to drop test/family-promo items) and their variations
    (type=variation; per-variation ILS price + "Days: 30 ימים, Data: 20GB"
    attribute string). ~92 countries + ~11 regional/global products, ~550 live
    variations. Prices are ILS minor units (/100) — no FX conversion.
    Duplicate (dest, size, days) tiers keep the cheapest price.
    """
    import html as _html

    def fetch_all(query):
        out, page = [], 1
        while True:
            batch = _nisim_fetch_json(f"products?{query}&per_page=100&page={page}")
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return out

    def clean_name(raw):
        n = _html.unescape(raw or "").replace("’", "'").replace("׳", "'")
        return re.sub(r"\s+", " ", n).strip()

    try:
        parents = fetch_all("")
    except Exception as exc:
        logger.warning(f"Nisim eSIM scraper failed (products fetch): {exc}")
        return []

    from db import _DEST_NORM
    dest_by_parent, unmapped = {}, set()
    for p in parents:
        if p.get("type") != "variable":
            continue
        cats = {c.get("name") for c in p.get("categories") or []}
        name = clean_name(p.get("name"))
        if cats & _NISIM_SKIP_CATS or "test" in name.lower():
            continue
        dest = NISIM_REGION_NAMES.get(name)
        if not dest:
            dest = NISIM_NAME_FIX.get(name, name)
            dest = _DEST_NORM.get(dest, dest)
            if not re.fullmatch(r"[֐-׿][֐-׿ '\"()\-]*", dest):
                unmapped.add(name)  # Latin/odd name — not a destination product
                continue
        dest_by_parent[p["id"]] = dest

    try:
        variations = fetch_all("type=variation")
    except Exception as exc:
        logger.warning(f"Nisim eSIM scraper failed (variations fetch): {exc}")
        return []

    best = {}  # plan_name -> plan dict (cheapest wins)
    for v in variations:
        dest = dest_by_parent.get(v.get("parent"))
        if not dest:
            continue
        attrs = v.get("variation") or ""
        # attribute labels vary per product: Days/days/ימים and Data/data/Data Plan
        m_days = re.search(r"(?:days|ימים)\s*:\s*(\d+)", attrs, re.I)
        m_data = re.search(r"data(?:\s*plan)?\s*:\s*([^,]+)", attrs, re.I)
        if not m_days or not m_data:
            continue
        days = int(m_days.group(1))
        data_txt = m_data.group(1).strip()
        if re.search(r"x\s*\d", data_txt, re.I):
            continue  # multi-line family tier (20GB X4) — not a consumer plan
        if "ללא הגבלה" in data_txt or "unlimit" in data_txt.lower():
            gb, gb_str = None, "ללא הגבלה"
        else:
            m_gb = re.match(r"([\d.]+)\s*(GB|MB)", data_txt, re.I)
            if not m_gb:
                continue
            val = float(m_gb.group(1))
            gb = round(val / 1024, 4) if m_gb.group(2).upper() == "MB" else val
            gb_str = f"{m_gb.group(1)}{m_gb.group(2).upper()}"
        try:
            price = int((v.get("prices") or {}).get("price") or 0) / 100.0
        except (TypeError, ValueError):
            continue
        if price <= 0 or days <= 0:
            continue
        day_unit = "יום" if days == 1 else "ימים"
        plan_name = f"{dest} – {gb_str} – {days} {day_unit}"
        if plan_name in best and best[plan_name]["price"] <= price:
            continue  # keep the cheapest duplicate tier (UNIQUE(carrier, plan_name))
        extras = [dest]
        if gb is None:
            extras.append("גלישה ללא הגבלה")
        best[plan_name] = core._make_global_plan(
            "nisim", plan_name, price, "ILS", price,
            data_gb=gb, days=days, esim=True, extras=extras,
        )
    if unmapped:
        logger.warning(f"Nisim eSIM: skipped non-destination products {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"Nisim eSIM: {len(plans)} plans from {len(dest_by_parent)} products")
    return plans
