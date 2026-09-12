"""besim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


BESIM_SLUG_TO_HEBREW = {
    # Africa (per-country, 27)
    "algeria":                  "אלג'יריה",
    "botswana":                 "בוטסואנה",
    "burkina-faso":             "בורקינה פאסו",
    "cameroon":                 "קמרון",
    "central-african-republic": "הרפובליקה המרכז אפריקאית",
    "chad":                     "צ'אד",
    "congo":                    "קונגו",
    "cote-divoire":             "חוף השנהב",
    "egypt":                    "מצרים",
    "gabon":                    "גאבון",
    "kenya":                    "קניה",
    "liberia":                  "ליבריה",
    "madagascar":               "מדגסקר",
    "malawi":                   "מלאווי",
    "mali":                     "מאלי",
    "mozambique":               "מוזמביק",
    "niger":                    "ניג'ר",
    "nigeria":                  "ניגריה",
    "reunion":                  "ראוניון",
    "senegal":                  "סנגל",
    "seychelles":               "איי סישל",
    "south-africa":             "דרום אפריקה",
    "sudan":                    "סודן",
    "tanzania":                 "טנזניה",
    "tunisia":                  "תוניסיה",
    "uganda":                   "אוגנדה",
    "zambia":                   "זמביה",

    # Americas (per-country, 19)
    "argentina":                "ארגנטינה",
    "belize":                   "בליז",
    "bolivia":                  "בוליביה",
    "brazil":                   "ברזיל",
    "canada":                   "קנדה",
    "chile":                    "צ'ילה",
    "colombia":                 "קולומביה",
    "costa-rica":               "קוסטה ריקה",
    "ecuador":                  "אקוודור",
    "el-salvador":              "אל סלבדור",
    "guatemala":                "גואטמלה",
    "honduras":                 "הונדורס",
    "mexico":                   "מקסיקו",
    "nicaragua":                "ניקראגואה",
    "panama":                   "פנמה",
    "paraguay":                 "פראגוואי",
    "peru":                     "פרו",
    "united-states":            "ארצות הברית",
    "uruguay":                  "אורוגוואי",

    # Asia (per-country, 32)
    "armenia":                  "ארמניה",
    "azerbaijan":               "אזרבייג'ן",
    "bahrain":                  "בחריין",
    "bangladesh":               "בנגלדש",
    "brunei-darussalam":        "ברוניי",
    "cambodia":                 "קמבודיה",
    "china":                    "סין",
    "georgia":                  "גאורגיה",
    "hong-kong-china":          "הונג קונג",
    "india":                    "הודו",
    "indonesia":                "אינדונזיה",
    "israel":                   "ישראל",
    "japan":                    "יפן",
    "jordan":                   "ירדן",
    "kazakhstan":               "קזחסטן",
    "kyrgyzstan":               "קירגיזסטן",
    "laos":                     "לאוס",
    "macao-china":              "מקאו",
    "malaysia":                 "מלזיה",
    "mongolia":                 "מונגוליה",
    "nepal":                    "נפאל",
    "oman":                     "עומן",
    "pakistan":                 "פקיסטן",
    "philippines":              "הפיליפינים",
    "qatar":                    "קטר",
    "saudi-arabia":             "ערב הסעודית",
    "singapore":                "סינגפור",
    "south-korea":              "דרום קוריאה",
    "sri-lanka":                "סרי לנקה",
    "thailand":                 "תאילנד",
    "turkey":                   "טורקיה",
    "united-arab-emirates":     "איחוד האמירויות",
    "uzbekistan":               "אוזבקיסטן",
    "vietnam":                  "וייטנאם",

    # Caribbean (per-country, 4)
    "dominican-republic":       "הרפובליקה הדומיניקנית",
    "guadeloupe":               "גוואדלופ",
    "jamaica":                  "ג'מייקה",
    "puerto-rico":              "פוארטו ריקו",

    # Europe (per-country, 45 — Besim groups Morocco under Europe)
    "aland-islands":            "איי אלאנד",
    "albania":                  "אלבניה",
    "andorra":                  "אנדורה",
    "austria":                  "אוסטריה",
    "belarus":                  "בלארוס",
    "belgium":                  "בלגיה",
    "bosnia-and-herzegovina":   "בוסניה והרצגובינה",
    "bulgaria":                 "בולגריה",
    "croatia":                  "קרואטיה",
    "cyprus":                   "קפריסין",
    "czech-republic":           "צ'כיה",
    "denmark":                  "דנמרק",
    "estonia":                  "אסטוניה",
    "finland":                  "פינלנד",
    "france":                   "צרפת",
    "germany":                  "גרמניה",
    "gibraltar":                "גיברלטר",
    "greece":                   "יוון",
    "guernsey":                 "גרנזי",
    "hungary":                  "הונגריה",
    "iceland":                  "איסלנד",
    "ireland":                  "אירלנד",
    "isle-of-man":              "האי מאן",
    "italy":                    "איטליה",
    "jersey":                   "ג'רזי",
    "latvia":                   "לטביה",
    "liechtenstein":            "ליכטנשטיין",
    "lithuania":                "ליטא",
    "luxembourg":               "לוקסמבורג",
    "malta":                    "מלטה",
    "moldova":                  "מולדובה",
    "monaco":                   "מונקו",
    "montenegro":               "מונטנגרו",
    "morocco":                  "מרוקו",
    "netherlands":              "הולנד",
    "north-macedonia":          "מקדוניה הצפונית",
    "norway":                   "נורבגיה",
    "poland":                   "פולין",
    "portugal":                 "פורטוגל",
    "romania":                  "רומניה",
    "russia":                   "רוסיה",
    "serbia":                   "סרביה",
    "slovakia":                 "סלובקיה",
    "slovenia":                 "סלובניה",
    "spain":                    "ספרד",
    "sweden":                   "שבדיה",
    "switzerland":              "שוויץ",
    "ukraine":                  "אוקראינה",
    "united-kingdom":           "בריטניה",

    # Oceania (per-country, 3)
    "australia":                "אוסטרליה",
    "guam":                     "גואם",
    "new-zealand":              "ניו זילנד",
}


# Regional / global bundles. Tuple = (display_label_hebrew, canonical_region_tag).
# region_tag is what goes into extras[0] — uses canonical names from KNOWN_REGIONS so the
# region/destination filters DON'T duplicate. Multiple Asia variants all share extras[0]="אסיה"
# but their distinct sizes appear in plan_name to keep the cards differentiated.
BESIM_REGIONAL_BUNDLES = {
    "africa-25-areas":             ("אפריקה (25+ מדינות)",         "אפריקה"),
    "united_states_canada":        ("ארה\"ב וקנדה",                                   "צפון אמריקה"),
    "south-america-15-areas":      ("דרום אמריקה (15+ מדינות)",           "דרום אמריקה"),
    "north-america-3-areas":       ("צפון אמריקה (3 מדינות)",                 "צפון אמריקה"),
    "thailand-malaysia-singapore": ("תאילנד, מלזיה וסינגפור",                  "דרום מזרח אסיה"),
    "south-korea-china-japan":     ("דרום קוריאה, סין ויפן",            "אסיה"),
    "middle-east-13-areas":        ("המזרח התיכון (13 מדינות)",          "המזרח התיכון"),
    "gulf-region":                 ("מדינות המפרץ",                                "המזרח התיכון"),
    "china-mainland-hk-macao":     ("סין, הונג קונג ומקאו",                  "סין + הונג קונג + מקאו"),
    "asia-7-areas":                ("אסיה (7 מדינות)",                              "אסיה"),
    "asia-12-areas":               ("אסיה (12 מדינות)",                            "אסיה"),
    "asia-20-areas":               ("אסיה (20 מדינות)",                            "אסיה"),
    "asia-21-areas":               ("אסיה (+20 מדינות)",                           "אסיה"),
    "caribbean-20-areas":          ("הקריביים (20+ מדינות)",                  "קריביים"),
    "europe-30-areas":             ("אירופה (30+ מדינות)",                       "אירופה"),
    "europe-40-areas":             ("אירופה (40+ מדינות)",                       "אירופה"),
    "balkans-5-areas":             ("בלקן (5+ מדינות)",                              "בלקן"),
    "global-130-areas":            ("גלובלי (130+ מדינות)",                      "גלובלי"),
    "global-120-areas":            ("גלובלי (120+ מדינות)",                      "גלובלי"),
}


_BESIM_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


# Each plan block on a Besim product page is exactly 3 lines:
#   "1GB"           ← data
#   "Validity 7 days"  ← days. Besim relocalized its product pages from Hebrew to
#                         English (2026-06): the line was "תוקף 7 ימים" before, so
#                         _BESIM_DAYS_RE matches BOTH phrasings to survive a revert.
#   "$1"            ← USD price
# Decimal prices appear inline: "$3.5", "$4.50", "$38.5" — never split across lines.
_BESIM_GB_RE     = re.compile(r"^(\d+(?:\.\d+)?)GB$",  re.I)


_BESIM_MB_RE     = re.compile(r"^(\d+(?:\.\d+)?)MB$",  re.I)


_BESIM_DAYS_RE   = re.compile(r"^(?:תוקף|Validity)\s+(\d+)\s+(?:ימים|days?)$", re.I)


_BESIM_PRICE_RE  = re.compile(r"^\$(\d+(?:\.\d+)?)$")


def _parse_besim_plans(body_text):
    """Parse a Besim product-page body into [(data_gb, days, price_usd), ...].
    Walks the line list looking for the consecutive-3-line pattern."""
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    out = []
    i = 0
    while i + 2 < len(lines):
        m_gb = _BESIM_GB_RE.match(lines[i])
        m_mb = _BESIM_MB_RE.match(lines[i]) if not m_gb else None
        m_d  = _BESIM_DAYS_RE.match(lines[i + 1]) if (m_gb or m_mb) else None
        m_p  = _BESIM_PRICE_RE.match(lines[i + 2]) if m_d else None
        if m_gb and m_d and m_p:
            gb_val = float(m_gb.group(1))
            data_gb = int(gb_val) if gb_val == int(gb_val) else gb_val
            out.append((data_gb, int(m_d.group(1)), float(m_p.group(1))))
            i += 3
            continue
        if m_mb and m_d and m_p:
            mb_val = float(m_mb.group(1))
            out.append((round(mb_val / 1024, 4), int(m_d.group(1)), float(m_p.group(1))))
            i += 3
            continue
        i += 1
    return out


def _besim_format_data(data_gb):
    if data_gb is None:
        return "ללא הגבלה"
    if data_gb >= 1:
        n = int(data_gb) if data_gb == int(data_gb) else data_gb
        return f"{n}GB"
    return f"{round(data_gb * 1024)}MB"


def _scrape_besim_batch(items, usd_rate):
    """Fetch a batch of Besim product URLs in one browser session.
    items: iterable of (url, plan_label_or_country, region_tag) tuples.
    For per-country plans plan_label_or_country == region_tag == hebrew country name."""
    core._ensure_event_loop()
    batch_plans = []
    with core.sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_BESIM_UA)
        for url, plan_label, region_tag in items:
            try:
                # Besim's site is sluggish under parallel load — give it 35s and
                # retry once on timeout before giving up. about:blank between requests
                # avoids "interrupted by another navigation" warnings on slow pages.
                last_err = None
                for attempt in range(2):
                    try:
                        page.goto(url, timeout=35000, wait_until="domcontentloaded")
                        last_err = None
                        break
                    except Exception as e:
                        last_err = e
                        try:
                            page.goto("about:blank", timeout=5000)
                        except Exception:
                            pass
                if last_err is not None:
                    logger.warning(f"Besim {url}: {last_err}")
                    continue
                page.wait_for_timeout(900)
                body = page.inner_text("body")
                triplets = _parse_besim_plans(body)
                for data_gb, days, price_usd in triplets:
                    if days <= 0 or price_usd <= 0:
                        continue
                    price_ils = round(price_usd * usd_rate, 2)
                    data_str = _besim_format_data(data_gb)
                    plan_name = f"{plan_label} – {data_str} – {days} ימים"
                    batch_plans.append(core._make_global_plan(
                        "besim", plan_name, price_ils, "USD", price_usd,
                        data_gb, days, esim=True, extras=[region_tag],
                    ))
            except Exception as exc:
                logger.warning(f"Besim {url}: {exc}")
        browser.close()
    return batch_plans


def _scrape_besim_product_list(items, usd_rate):
    """Split items into 2 parallel browser batches.
    Besim's site throttles under heavy parallel load, so we use 2 workers
    (not 4 like ByteSim) — each batch is ~78 pages × ~3s = ~4 min wall time."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    items = list(items)
    batch_size = max(1, (len(items) + 1) // 2)
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    all_plans = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_scrape_besim_batch, b, usd_rate) for b in batches]
        for fut in _as_completed(futures, timeout=1500):
            try:
                all_plans.extend(fut.result())
            except Exception as exc:
                logger.warning(f"Besim batch error: {exc}")
    return all_plans


def scrape_besim_global(_page=None, usd_rate=None):
    """Scrape Besim per-country eSIM plans from ~130 country pages."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    items = [
        (f"https://besim.co.il/product/{slug}", country_heb, country_heb)
        for slug, country_heb in BESIM_SLUG_TO_HEBREW.items()
    ]
    plans = _scrape_besim_product_list(items, usd_rate)
    logger.info(f"Besim global: {len(plans)} plans from {len(BESIM_SLUG_TO_HEBREW)} countries")
    return plans


def scrape_besim_regions(_page=None, usd_rate=None):
    """Scrape Besim regional + global bundles (19 products)."""
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    items = [
        (f"https://besim.co.il/product/{slug}", plan_label, region_tag)
        for slug, (plan_label, region_tag) in BESIM_REGIONAL_BUNDLES.items()
    ]
    plans = _scrape_besim_product_list(items, usd_rate)
    logger.info(f"Besim regions: {len(plans)} plans from {len(BESIM_REGIONAL_BUNDLES)} bundles")
    return plans
