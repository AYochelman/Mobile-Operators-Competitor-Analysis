"""simzol scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module
logger = core.logger


# Small Israeli reseller on the CashCow storefront platform. No API and no
# structured feed, so this walks the site's own sitemap and parses each product
# page. Products are keyed by permalink slug in SIMZOL_PRODUCTS; a page that is
# NOT in the map but sits under the site's eSIM category warns, so a new eSIM
# line gets noticed instead of being silently dropped.
#
# The shop sells both eSIMs and physical travel SIMs. Physical products carry
# esim=False (the public feed maps that to form='sim', which the /esim-deals
# "eSIM" filter chip excludes) plus a "סים פיזי" suffix in plan_name — without
# the suffix the physical USA ladder would collide with the eSIM USA ladder at
# 20/30 days under UNIQUE(carrier, plan_name) and the pricier physical tier
# would be discarded as a "duplicate".
SIMZOL_SITEMAP = "https://www.simzol.co.il/crowlers/sitemap"


# slug (URL-decoded, without the /p/ prefix) → (plan_name title, extras[0] dest,
# esim?, extra perk bullets). Title differs from dest only where two products
# share a destination but not a coverage list — "גלובלי פלטינום" (123 listed
# destinations, unlimited data + calls, sold by trip length) vs the "גלובלי"
# eSIM data packages (83); SIMZOL_REGION_MAP in globalCountries.js keys on the
# title to tell them apart.
SIMZOL_PRODUCTS = {
    "esim":                           ("גלובלי", "גלובלי", True, ()),
    "1_גב_-_ESIM":                    ("גלובלי", "גלובלי", True, ()),
    "3_גב_-_ESIM":                    ("גלובלי", "גלובלי", True, ()),
    "5_גב_-_ESIM":                    ("גלובלי", "גלובלי", True, ()),
    "סים_לגיאורגיה":                  ("גאורגיה", "גאורגיה", True, ()),
    "סים_לדובאי":                     ("איחוד האמירויות", "איחוד האמירויות", True, ()),
    "7-day-usa-esim":                 ("ארצות הברית", "ארצות הברית", True,
                                       ("שיחות מקומיות ללא הגבלה",)),
    "10_ימים_ארהב_ללא_הגבלה__-_ESIM": ("ארצות הברית", "ארצות הברית", True,
                                       ("שיחות מקומיות ללא הגבלה",)),
    "20_ימים_ארהב_ללא_הגבלה__-_ESIM": ("ארצות הברית", "ארצות הברית", True,
                                       ("שיחות מקומיות ללא הגבלה",)),
    "30_ימים_ארהב_ללא_הגבלה__-_ESIM": ("ארצות הברית", "ארצות הברית", True,
                                       ("שיחות מקומיות ללא הגבלה",)),
    # ── physical travel SIMs ──
    "סים_ארהב_-_מבצע":                ("ארצות הברית", "ארצות הברית", False,
                                       ("רשת T-Mobile", "שיחות ו-SMS ללא הגבלה בארצות הברית",
                                        "מספר אמריקאי", "אפשרות לתוספת דקות שיחה לישראל")),
    "סים_גלישה_לאירופה":              ("אירופה", "אירופה", False,
                                       ("גלישה בדור 4G/5G",
                                        "אפשרות לתוספת דקות שיחה ומספר ישראלי ואירופאי")),
    "SIM_Europe_Global":              ("גלובלי פלטינום", "גלובלי", False,
                                       ("שיחות ללא הגבלה", "מספר ישראלי ואירופאי",
                                        "מתאים לראוטר וטאבלט")),
}


# Attribute groups that price optional ADD-ONS rather than the package itself
# (minutes to Israel, a Canada/Mexico rider). Never a data tier.
_SIMZOL_ADDON_RE = re.compile(r"דקות|קנדה|מקסיקו")


_SIMZOL_TAG_RE = re.compile(r"(?s)<(script|style)\b.*?</\1>|<[^>]+>")


_SIMZOL_ESIM_CAT_RE = re.compile(r'href="https://www\.simzol\.co\.il/c/esim"')


def _simzol_page_text(html_src):
    return re.sub(r"[\s ]+", " ", _html_unescape(_SIMZOL_TAG_RE.sub(" ", html_src)))


def _simzol_tiers(html_src, title, text):
    """Yield (data_gb|None, days, price) for one product page.

    CashCow renders a variable product as radio inputs carrying
    data-price/attr_id/data-text, grouped by attr_id. The FIRST group is the
    package ladder; later groups are add-ons. A fixed-price product has no
    ladder at all — its spec lives in the title plus a "למשך N ימים" line.
    """
    groups, order = {}, []
    for m in re.finditer(
            r"data-price='([\d.]+)'[^>]*attr_id='(\d+)'[^>]*data-text='([^']*)'", html_src):
        price, attr_id, label = float(m.group(1)), m.group(2), _html_unescape(m.group(3)).strip()
        if attr_id not in groups:
            groups[attr_id] = []
            order.append(attr_id)
        groups[attr_id].append((label, price))

    ladder = []
    for attr_id in order:
        opts = groups[attr_id]
        if any(_SIMZOL_ADDON_RE.search(lbl) for lbl, _ in opts):
            continue  # minutes / country rider — not a data ladder
        ladder = opts
        break

    m_days_txt = re.search(r"למשך\s*(\d+)\s*(?:ימים|יום)", text)
    fallback_days = int(m_days_txt.group(1)) if m_days_txt else None

    if ladder:
        for label, price in ladder:
            # "1GB גלישה / 7 יום"
            m = re.search(r"([\d.]+)\s*GB\s*גלישה\s*/\s*(\d+)\s*(?:ימים|יום)", label)
            if m:
                yield float(m.group(1)), int(m.group(2)), price
                continue
            # "7 ימים גלישה ללא הגבלה"
            m = re.search(r"(\d+)\s*(?:ימים|יום)\s*גלישה\s*ללא\s*הגבלה", label)
            if m:
                yield None, int(m.group(1)), price
                continue
            # "6 ג'יגה" — duration only stated in the product copy
            m = re.search(r"([\d.]+)\s*(?:GB|ג\"ב|ג'יגה)", label)
            if m and fallback_days:
                yield float(m.group(1)), fallback_days, price
                continue
            # bare "3 ימים" — a trip-length ladder, which on this shop always
            # means an unlimited data+calls SIM (סים עולמי - פלטינום)
            m = re.fullmatch(r"(\d+)\s*(?:ימים|יום)", label)
            if m:
                yield None, int(m.group(1)), price
        return

    # Fixed-price product: spec comes from the title + copy.
    m_price = re.search(r'product:price:amount"\s*content="([\d.]+)"', html_src)
    price = float(m_price.group(1)) if m_price else 0.0
    if price <= 0:
        return
    if "ללא הגבלה" in title:
        m = re.search(r"(\d+)\s*(?:ימים|יום)", title)
        if m:
            yield None, int(m.group(1)), price
        return
    m = re.search(r"([\d.]+)\s*(?:GB|ג\"ב|ג'יגה)", title)
    if m and fallback_days:
        yield float(m.group(1)), fallback_days, price


def scrape_simzol_global(_page=None, usd_rate=None):
    """Scrape the Simzol (simzol.co.il) catalog — pure HTTP, ILS prices."""
    import urllib.parse as _urlparse

    try:
        sitemap = core._esimo_fetch(SIMZOL_SITEMAP, timeout=30)
    except Exception as e:
        logger.warning(f"Simzol: sitemap fetch failed ({e})")
        return []
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sitemap) if "/p/" in u]
    if not urls:
        logger.warning("Simzol: sitemap listed no product pages")
        return []

    best, unmapped, seen = {}, set(), 0
    for url in urls:
        slug = _urlparse.unquote(url.rsplit("/p/", 1)[1])
        try:
            page_html = core._esimo_fetch(url, timeout=30)
        except Exception as e:
            logger.warning(f"Simzol: {slug} fetch failed ({e})")
            continue
        product = SIMZOL_PRODUCTS.get(slug)
        if not product:
            # An unknown page under the eSIM category is a new product worth
            # mapping; anything else is a physical line we chose not to carry.
            if _SIMZOL_ESIM_CAT_RE.search(page_html):
                unmapped.add(slug)
            continue
        title, dest, is_esim, perks = product
        seen += 1
        m_title = re.search(r'<h1[^>]*product-details-title[^>]*>(.*?)</h1>', page_html, re.S)
        page_title = (_html_unescape(re.sub(r"<[^>]+>", "", m_title.group(1))).strip()
                      if m_title else slug)
        text = _simzol_page_text(page_html)

        for gb, days, price in _simzol_tiers(page_html, page_title, text):
            if not days or price <= 0:
                continue
            extras = [dest]
            if gb is None:
                gb_str = "ללא הגבלה"
                extras.append("גלישה ללא הגבלה")
            else:
                gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
            extras.extend(perks)
            day_unit = "יום" if days == 1 else "ימים"
            plan_name = f"{title} – {gb_str} – {days} {day_unit}"
            if not is_esim:
                plan_name += " – סים פיזי"
                extras.append("סים פיזי")
            if plan_name in best and best[plan_name]["price"] <= price:
                continue  # cheapest duplicate tier wins (UNIQUE(carrier, plan_name))
            best[plan_name] = core._make_global_plan(
                "simzol", plan_name, price, "ILS", price,
                data_gb=gb, days=days, esim=is_esim, extras=extras,
            )
    if unmapped:
        logger.warning(f"Simzol: unmapped eSIM products {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"Simzol: {len(plans)} plans from {seen} products")
    return plans
