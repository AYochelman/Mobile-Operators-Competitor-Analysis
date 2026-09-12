"""xphone scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


_XPHONE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def scrape_xphone(_page=None):
    """Scrape XPhone domestic plans. Uses own fresh session with UA to bypass AWS WAF.
    Parses plan data from body text since CSS selectors are unavailable under WAF."""
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_XPHONE_UA)
        try:
            _resp = page.goto("https://xphone.co.il/cellularplans/", timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            body = page.evaluate("document.body.innerText") or ""
            if "confirm you are human" in body.lower() or len(body) < 500:
                # Distinguish a site outage (CloudFront 503 + empty body, e.g. the
                # 2026-08-31 xphone.co.il outage) from a real WAF challenge page.
                _st = _resp.status if _resp else None
                if _st and _st >= 500:
                    logger.warning(f"scrape_xphone: site down (HTTP {_st}, body={len(body)} chars). Returning [].")
                else:
                    logger.warning(f"scrape_xphone: WAF block detected (HTTP {_st}). Returning [].")
                return []

            # Parse from body text: plan blocks separated by known plan names
            PLAN_NAMES = [
                "FOREVER PLUS 5G",  # must come before FOREVER PLUS
                "FOREVER PLUS",
                "Young 50GB",
                "צוברים וגולשים 1GB בחו\"ל – 5G",
                "צוברים וגולשים 1GB בחו\"ל",
                "GLOBAL 5G",  # before GLOBAL 5 and GLOBAL 3
                "GLOBAL 5",
                "GLOBAL 3",
            ]

            # Dynamically scrape per-plan PDF URLs from the DOM (immune to WAF — uses JS evaluate)
            # Plan PDFs have no link text; filter out known site-wide PDFs by filename
            PLAN_URLS = {}
            try:
                raw_urls = page.evaluate("""() => {
                    const SKIP = ['reshimat', 'betuhut', 'negishut', 'tnaim_clalim',
                                  'old_tech', 'taarifim', 'loch', 'taarifon'];
                    const seen = new Set();
                    return Array.from(document.querySelectorAll(
                        'a[href*="wp-content/uploads"][href$=".pdf"]'
                    ))
                    .filter(a => !a.innerText.trim())
                    .filter(a => !SKIP.some(s => a.href.toLowerCase().includes(s)))
                    .filter(a => { const h = a.href; if (seen.has(h)) return false; seen.add(h); return true; })
                    .map(a => a.href);
                }""") or []
                for url in raw_urls:
                    ul = url.lower()
                    if 'forever-plus-5g' in ul:
                        PLAN_URLS['FOREVER PLUS 5G'] = url
                    elif 'forever-plus' in ul:
                        PLAN_URLS['FOREVER PLUS'] = url
                    elif 'young' in ul:
                        PLAN_URLS['Young 50GB'] = url
                    elif '%d7%a6' in ul:  # URL-encoded צ (start of צוברים)
                        if '5g-1' in ul:
                            PLAN_URLS['\u05e6\u05d5\u05d1\u05e8\u05d9\u05dd \u05d5\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd 1GB \u05d1\u05d7\u05d5\"\u05dc \u2013 5G'] = url
                        else:
                            PLAN_URLS['\u05e6\u05d5\u05d1\u05e8\u05d9\u05dd \u05d5\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd 1GB \u05d1\u05d7\u05d5\"\u05dc'] = url
                    elif 'global-3' in ul:
                        PLAN_URLS['GLOBAL 3'] = url
                    elif 'global-5gb-5g' in ul:
                        PLAN_URLS['GLOBAL 5G'] = url
                    elif 'global-5gb' in ul:
                        PLAN_URLS['GLOBAL 5'] = url
            except Exception as _exc:
                logger.warning(f"scrape_xphone: DOM PDF extraction failed: {_exc}")
            # Fallback static URLs for any plan not resolved dynamically
            _XPHONE_BASE = "https://xphone.co.il/wp-content/uploads/"
            _STATIC_URLS = {
                "FOREVER PLUS":     _XPHONE_BASE + "FOREVER-PLUS-\u05ea\u05e7\u05e0\u05d5\u05df-\u05ea\u05e0\u05d0\u05d9-\u05ea\u05db\u05e0\u05d9\u05ea-.pdf",
                "FOREVER PLUS 5G":  _XPHONE_BASE + "FOREVER-PLUS-5G-\u05ea\u05e7\u05e0\u05d5\u05df-\u05ea\u05e0\u05d0\u05d9-\u05ea\u05db\u05e0\u05d9\u05ea-.pdf",
                "Young 50GB":       _XPHONE_BASE + "Young-50GB-\u05ea\u05e7\u05e0\u05d5\u05df-\u05ea\u05e0\u05d0\u05d9-\u05ea\u05db\u05e0\u05d9\u05ea-.pdf",
                "\u05e6\u05d5\u05d1\u05e8\u05d9\u05dd \u05d5\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd 1GB \u05d1\u05d7\u05d5\"\u05dc":      _XPHONE_BASE + "\u05ea\u05e7\u05e0\u05d5\u05df-\u05ea\u05e0\u05d0\u05d9-\u05ea\u05db\u05e0\u05d9\u05ea-\u05e6\u05d5\u05d1\u05e8\u05d9\u05dd-\u05d5\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd-1-\u05d2\u05d9\u05d2\u05d4.pdf",
                "\u05e6\u05d5\u05d1\u05e8\u05d9\u05dd \u05d5\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd 1GB \u05d1\u05d7\u05d5\"\u05dc \u2013 5G": _XPHONE_BASE + "\u05ea\u05e7\u05e0\u05d5\u05df-\u05ea\u05e0\u05d0\u05d9-\u05ea\u05db\u05e0\u05d9\u05ea-\u05e6\u05d5\u05d1\u05e8\u05d9\u05dd-\u05d5\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd-1-\u05d2\u05d9\u05d2\u05d4-5G-1.pdf",
                "GLOBAL 3":         _XPHONE_BASE + "\u05ea\u05e7\u05e0\u05d5\u05df-GLOBAL-3GB.pdf",
                "GLOBAL 5":         _XPHONE_BASE + "\u05ea\u05e7\u05e0\u05d5\u05df-GLOBAL-5GB.pdf",
                "GLOBAL 5G":        _XPHONE_BASE + "\u05ea\u05e7\u05e0\u05d5\u05df-GLOBAL-5GB-5G.pdf",
            }
            for name, url in _STATIC_URLS.items():
                PLAN_URLS.setdefault(name, url)

            # Extract block of text for each plan
            plans = []
            for plan_name in PLAN_NAMES:
                start = body.find(plan_name)
                if start == -1:
                    continue
                # End = start of next plan name (or 900 chars max)
                end = len(body)
                for other in PLAN_NAMES:
                    if other == plan_name:
                        continue
                    pos = body.find(other, start + len(plan_name))
                    if pos != -1 and pos < end:
                        end = pos
                block = body[start:min(start + 900, end)]

                # ── Price ──────────────────────────────────────────────────
                # On XPhone, price appears on line BEFORE ₪ (e.g. "34.90\n₪")
                # XPhone has rendered price two ways:
                #   "34.90\n\u20aa"  (newline-separated, original)
                #   "34.90 \u20aa"   (space-separated, observed 2026-05)
                # The newline-only regex caused price=None on the latter, which
                # cascaded into spurious "price dropped to 0\u20aa" change events.
                # `\s*` matches any whitespace (newline / space / nothing).
                price_m = re.search(r'(\d+(?:\.\d+)?)\s*\u20aa', block)
                if not price_m:
                    # Fallback: \u20aa before digits (e.g. "\u20aa34.90")
                    price_m = re.search(r'\u20aa\s*(\d+(?:\.\d+)?)', block)
                if price_m:
                    v = float(price_m.group(1))
                    price = int(v) if v == int(v) else v
                else:
                    price = None

                # ── Domestic GB ─────────────────────────────────────────────
                # Look for "NGB גלישה בישראל" bullet (not the header subtitle)
                gb_israel = re.search(r'(\d+)\s*GB\s+גלישה\s+בישראל', block, re.IGNORECASE)
                if gb_israel:
                    gb = int(gb_israel.group(1))
                elif 'ללא הגבלה' in block:
                    gb = None  # unlimited
                else:
                    gb = None

                # ── Minutes ─────────────────────────────────────────────────
                minutes_m = re.search(r"([\d,]+)\s*דק", block)
                minutes = int(minutes_m.group(1).replace(',', '')) if minutes_m else None

                # ── Extras ──────────────────────────────────────────────────
                SKIP_X = {'להצטרפות', 'לפרטי החבילה', 'לרשימת היעדים', 'בלבד!',
                          'גלישה בישראל', plan_name}
                extras = []
                for line in block.split('\n'):
                    line = line.strip()
                    if (line and line not in SKIP_X
                            and '\u20aa' not in line
                            and 'להצטרפות' not in line
                            and 'לפרטי' not in line
                            and 'לרשימת' not in line
                            and not re.match(r'^[\d.,]+$', line)):
                        extras.append(line)
                seen_e, clean_extras = set(), []
                for e in extras:
                    if e not in seen_e and len(e) > 2:
                        seen_e.add(e); clean_extras.append(e)
                    if len(clean_extras) >= 5: break

                plans.append({"carrier": "xphone", "plan_name": plan_name, "price": price,
                              "data_gb": gb, "minutes": minutes, "extras": clean_extras,
                              "url": PLAN_URLS.get(plan_name)})
            return plans
        finally:
            browser.close()


def scrape_xphone_abroad(_page=None):
    """Scrape XPhone abroad plans from all 3 tabs on xphone.co.il/roaming."""
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_XPHONE_UA)
        try:
            _resp = page.goto("https://xphone.co.il/roaming", timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            body = page.evaluate("document.body.innerText") or ""
            if "confirm you are human" in body.lower() or len(body) < 500:
                # Distinguish a site outage (CloudFront 503 + empty body, e.g. the
                # 2026-08-31 xphone.co.il outage) from a real WAF challenge page.
                _st = _resp.status if _resp else None
                if _st and _st >= 500:
                    logger.warning(f"scrape_xphone_abroad: site down (HTTP {_st}, body={len(body)} chars). Returning [].")
                else:
                    logger.warning(f"scrape_xphone_abroad: WAF block detected (HTTP {_st}). Returning [].")
                return []

            TAB_CONFIGS = [
                {"label": "\u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1\u05dc\u05d1\u05d3",   # גלישה בלבד
                 "destinations": ["\u05d4\u05d5\u05dc\u05e0\u05d3", "\u05de\u05dc\u05d8\u05d4",
                                  "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3", "\u05e9\u05d1\u05d3\u05d9\u05d4",
                                  "\u05d9\u05d5\u05d5\u05df", "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea"],
                 "has_data": True, "has_calls": False},
                {"label": "\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd \u05d5\u05de\u05d3\u05d1\u05e8\u05d9\u05dd",   # גולשים ומדברים
                 "destinations": ["\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
                                  "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4", "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
                                  "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4", "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
                                  "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4", "\u05d9\u05d5\u05d5\u05df",
                                  "\u05e6\u05e8\u05e4\u05ea", "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d9\u05d5\u05d5\u05e0\u05d9\u05ea"],
                 "has_data": True, "has_calls": True},
                {"label": "\u05de\u05d3\u05d1\u05e8\u05d9\u05dd \u05d5\u05de\u05e1\u05de\u05e1\u05d9\u05dd",   # מדברים ומסמסים
                 "destinations": ["\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4", "\u05d9\u05d5\u05d5\u05df"],
                 "has_data": False, "has_calls": True},
            ]

            all_plans = []
            for tab in TAB_CONFIGS:
                # Click the tab button
                for el in page.query_selector_all("button, a, span, div"):
                    if (el.inner_text() or "").strip() == tab["label"]:
                        el.click()
                        page.wait_for_timeout(2000)
                        break

                body = page.evaluate("document.body.innerText") or ""
                # Narrow to the plan cards section only
                sec_s = body.find("\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05dc\u05e4\u05d9 \u05de\u05d3\u05d9\u05e0\u05d4")  # חבילות לפי מדינה
                sec_e = body.find("\u05dc\u05e8\u05db\u05d9\u05e9\u05ea \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05d1\u05d0\u05de\u05e6\u05e2\u05d5\u05ea")  # לרכישת חבילות באמצעות
                section = body[sec_s:sec_e] if sec_s >= 0 and sec_e > sec_s else body

                for dest in tab["destinations"]:
                    start = section.find(dest)
                    if start == -1:
                        continue
                    end = len(section)
                    for other in tab["destinations"]:
                        if other == dest:
                            continue
                        pos = section.find(other, start + len(dest))
                        if pos != -1 and pos < end:
                            end = pos
                    block = section[start:min(start + 400, end)]

                    plan_name = f"{dest} \u2014 {tab['label']}"  # em-dash separator

                    # Price: number immediately before ₪
                    price_m = re.search(r'(\d+(?:\.\d+)?)\s*\n\s*\u20aa', block)
                    if not price_m:
                        price_m = re.search(r'\u20aa\s*(\d+(?:\.\d+)?)', block)
                    if price_m:
                        v = float(price_m.group(1))
                        price = int(v) if v == int(v) else v
                    else:
                        price = None

                    # GB (data tabs only)
                    gb = None
                    if tab["has_data"]:
                        gb_m = re.search(r'(\d+)\s*GB', block, re.IGNORECASE)
                        if gb_m:
                            gb = int(gb_m.group(1))

                    # Days
                    days_m = re.search(r'ל[-\u2013\s]?(\d+)\s+ימים', block)
                    days = int(days_m.group(1)) if days_m else None

                    # Minutes & SMS (calls tabs)
                    minutes, sms = None, None
                    if tab["has_calls"]:
                        min_m = re.search(r'(\d+)[^\u20aa\d]*?דקות', block)
                        minutes = int(min_m.group(1)) if min_m else None
                        sms_m = re.search(r'(\d+)\s+SMS', block)
                        sms = int(sms_m.group(1)) if sms_m else minutes  # fallback = minutes

                    extras = []
                    if minutes:
                        extras.append(f"{minutes} \u05d3\u05e7\u05d5\u05ea \u05d5-{sms} SMS")  # X דקות ו-Y SMS

                    all_plans.append({"carrier": "xphone", "plan_name": plan_name,
                                      "price": price, "days": days, "data_gb": gb,
                                      "minutes": minutes, "sms": sms, "extras": extras})
            return all_plans
        finally:
            browser.close()


def scrape_xphone_global(page=None):
    """Scrape XPhone global eSIM plans (אירופה + גלובלי) from xphone.co.il/roaming."""
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        pg = browser.new_page(user_agent=_XPHONE_UA)
        try:
            _resp = pg.goto("https://xphone.co.il/roaming", timeout=40000, wait_until="domcontentloaded")
            pg.wait_for_timeout(4000)
            body = pg.evaluate("document.body.innerText") or ""
            if "confirm you are human" in body.lower() or len(body) < 500:
                # Distinguish a site outage (CloudFront 503 + empty body, e.g. the
                # 2026-08-31 xphone.co.il outage) from a real WAF challenge page.
                _st = _resp.status if _resp else None
                if _st and _st >= 500:
                    logger.warning(f"scrape_xphone_global: site down (HTTP {_st}, body={len(body)} chars). Returning [].")
                else:
                    logger.warning(f"scrape_xphone_global: WAF block detected (HTTP {_st}). Returning [].")
                return []

            TAB_CONFIGS = [
                {"label": "\u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1\u05dc\u05d1\u05d3",      # גלישה בלבד
                 "has_calls": False},
                {"label": "\u05d2\u05d5\u05dc\u05e9\u05d9\u05dd \u05d5\u05de\u05d3\u05d1\u05e8\u05d9\u05dd",  # גולשים ומדברים
                 "has_calls": True},
            ]
            REGIONS = [
                "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",   # אירופה
                "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",   # גלובלי
            ]
            SEC_GLOBAL = "\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05d2\u05dc\u05d5\u05d1\u05dc\u05d9\u05d5\u05ea"   # חבילות גלובליות
            # End-of-cards marker (contact form text that follows the plan cards)
            SEC_END    = "\u05dc\u05e8\u05db\u05d9\u05e9\u05ea \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05d1\u05d0\u05de\u05e6\u05e2\u05d5\u05ea"  # לרכישת חבילות באמצעות

            all_plans = []

            for tab in TAB_CONFIGS:
                # 1. Click the top-level tab button (גלישה בלבד / גולשים ומדברים)
                for el in pg.query_selector_all("button, a, span, div"):
                    if (el.inner_text() or "").strip() == tab["label"]:
                        el.click()
                        pg.wait_for_timeout(2000)
                        break

                # 2. Click "חבילות גלובליות" sub-nav to show region-based (not destination) plans
                for el in pg.query_selector_all("a, button, span, div"):
                    if (el.inner_text() or "").strip() == SEC_GLOBAL:
                        el.click()
                        pg.wait_for_timeout(2000)
                        break

                body = pg.evaluate("document.body.innerText") or ""

                # Narrow to section between "חבילות גלובליות" header and end-of-cards marker
                sec_s = body.find(SEC_GLOBAL)
                sec_e = body.find(SEC_END, sec_s + len(SEC_GLOBAL))
                if sec_s == -1:
                    logger.warning(f"scrape_xphone_global: global section not found for tab {tab['label']}")
                    continue
                section = body[sec_s: (sec_e if sec_e > sec_s else sec_s + 3000)]

                # Find all region card starts
                card_starts = []
                for region in REGIONS:
                    pos = 0
                    while True:
                        idx = section.find(region, pos)
                        if idx == -1:
                            break
                        card_starts.append((idx, region))
                        pos = idx + len(region)
                card_starts.sort(key=lambda x: x[0])

                for i, (start, region) in enumerate(card_starts):
                    end = card_starts[i + 1][0] if i + 1 < len(card_starts) else min(start + 400, len(section))
                    block = section[start:end]

                    # GB
                    gb_m = re.search(r'(\d+)\s*GB', block, re.IGNORECASE)
                    gb = int(gb_m.group(1)) if gb_m else None

                    # Price: number BEFORE ₪ (format: "120\n₪\nבלבד!")
                    price_m = re.search(r'(\d+(?:\.\d+)?)\s*\n\s*\u20aa', block)
                    if not price_m:
                        price_m = re.search(r'\u20aa\s*\n?\s*(\d+(?:\.\d+)?)', block)
                    if price_m is None:
                        continue
                    v = float(price_m.group(1))
                    price = int(v) if v == int(v) else v

                    # Days
                    days_m = re.search(r'ל[-\u2013\s]?(\d+)\s+\u05d9\u05de\u05d9\u05dd', block)  # ל-N ימים
                    days = int(days_m.group(1)) if days_m else None

                    # Minutes + SMS for calls tabs
                    minutes, sms = None, None
                    if tab["has_calls"]:
                        min_m = re.search(r'(\d+)[^\u20aa\d]*?\u05d3\u05e7\u05d5\u05ea', block)  # N דקות
                        minutes = int(min_m.group(1)) if min_m else None
                        sms_m = re.search(r'(\d+)\s+SMS', block)
                        sms = int(sms_m.group(1)) if sms_m else minutes

                    plan_name = (f"{region} {gb}GB \u2014 {tab['label']}"
                                 if gb else f"{region} \u2014 {tab['label']}")

                    group_key = f"{region} \u2014 {tab['label']}"  # e.g. אירופה — גלישה בלבד
                    # Unify all "גלובלי — *" variants under canonical "גלובלי" region (qualifier stays in plan_name)
                    region_for_extras = "גלובלי" if region == "גלובלי" else group_key
                    extras = [region_for_extras]
                    if minutes:
                        extras.append(f"{minutes} \u05d3\u05e7\u05d5\u05ea \u05d5-{sms} SMS")  # N דקות ו-N SMS

                    all_plans.append(core._make_global_plan(
                        "xphone_global", plan_name, price, "ILS", price,
                        gb, days, minutes=minutes, sms=sms, esim=True, extras=extras
                    ))

            # Dedupe by plan_name (same plan may repeat across page sections)
            seen, deduped = set(), []
            for p in all_plans:
                if p["plan_name"] not in seen:
                    seen.add(p["plan_name"])
                    deduped.append(p)

            logger.info(f"XPhone global: {len(deduped)} plans")
            return deduped
        finally:
            browser.close()
