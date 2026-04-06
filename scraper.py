"""
Playwright scrapers for 5 Israeli cellular carriers.
Uses sync API. All scrape_* functions take a Playwright Page object.
Returns list of plan dicts:
  {"carrier": str, "plan_name": str, "price": int|None,
   "data_gb": int|None, "minutes": str, "extras": list[str]}
"""
from playwright.sync_api import sync_playwright
import re
import logging

logger = logging.getLogger(__name__)


def _parse_price(text):
    """Extract price from string like '₪49', '34.9', '39.90'. Returns float or None (no rounding)."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    val = float(match.group(1))
    # Return int if whole number, float otherwise
    return int(val) if val == int(val) else val


def _parse_minutes(text):
    """Extract minutes count from string like '7,000 דקות שיחה/SMS בארץ'.
    Returns int or None (None = not included / no calls)."""
    if not text:
        return None
    text_clean = text.replace(",", "")
    if any(w in text for w in ["ללא הגבלה", "unlimit", "∞"]):
        return -1  # -1 = unlimited
    match = re.search(r"(\d+)", text_clean)
    return int(match.group(1)) if match else None


def _parse_gb(text):
    """Extract GB from string. Returns None if unlimited, float for MB (<1), int for GB."""
    if not text:
        return None
    text_clean = text.replace(",", "")  # handle 2,500 → 2500
    text_lower = text_clean.lower().strip()
    if any(w in text_lower for w in ["ללא", "unlimit", "∞"]):
        return None
    # MB values → store as fraction of GB (e.g. 100MB → 0.098)
    mb_match = re.search(r"(\d+(?:\.\d+)?)\s*mb", text_lower)
    if mb_match:
        return round(float(mb_match.group(1)) / 1024, 4)
    # GB values
    match = re.search(r"(\d+(?:\.\d+)?)", text_lower)
    if not match:
        return None
    val = float(match.group(1))
    return int(val) if val == int(val) else val


def _parse_days(text):
    """Extract number of days from strings like '4 ימים', 'חבילה ל-30 ימים', 'למשך 8 ימים'."""
    if not text:
        return None
    text_clean = text.replace(",", "").replace("-", " ")
    match = re.search(r"(\d+)\s*(?:יום|ימים)", text_clean)
    return int(match.group(1)) if match else None


def _parse_sms(text):
    """Extract SMS count from string like '300 SMS', '100 הודעות'. Returns int or None."""
    if not text:
        return None
    text_clean = text.replace(",", "")
    if any(w in text for w in ["ללא הגבלה", "unlimit", "∞"]):
        return -1
    match = re.search(r"(\d+)", text_clean)
    return int(match.group(1)) if match else None


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
            page.goto("https://xphone.co.il/cellularplans/", timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            body = page.evaluate("document.body.innerText") or ""

            if "confirm you are human" in body.lower() or len(body) < 500:
                logger.warning("scrape_xphone: WAF block detected. Returning [].")
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
                price_m = re.search(r'(\d+(?:\.\d+)?)\s*\n\s*\u20aa', block)
                if not price_m:
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
                              "data_gb": gb, "minutes": minutes, "extras": clean_extras})
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
            page.goto("https://xphone.co.il/roaming", timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            body = page.evaluate("document.body.innerText") or ""
            if "confirm you are human" in body.lower() or len(body) < 500:
                logger.warning("scrape_xphone_abroad: WAF block detected. Returning [].")
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


_WECOM_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _scrape_wecom_page(page, url, name_prefix, already_navigated=False):
    """Helper: navigate to url (unless already_navigated), find headings starting with name_prefix, parse cards."""
    if not already_navigated:
        page.goto(url, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(2000)
    plans = []

    for h_el in page.query_selector_all('.elementor-heading-title, h2, h3, h4'):
        name = h_el.inner_text().strip()
        if not name.lower().startswith(name_prefix):
            continue

        block_text = h_el.evaluate(r"""el => {
            let p = el;
            for (let i = 0; i < 12; i++) {
                p = p.parentElement;
                if (!p) break;
                const t = (p.innerText || '').trim();
                if ((t.includes('\u20aa') || /\d+\.\d+/.test(t)) && t.length > 20 && t.length < 3000) return t;
            }
            return '';
        }""")

        if not block_text:
            continue

        # Parse price: on We-Com the price appears BEFORE ₪ (e.g. "29.90\n₪\nלחודש")
        price_m = re.search(r'(\d+(?:\.\d+)?)\s*\n\s*\u20aa', block_text)
        if not price_m:
            price_m = re.search(r'\u20aa\s*(\d+(?:\.\d+)?)', block_text)
        if price_m:
            v = float(price_m.group(1))
            price = int(v) if v == int(v) else v
        else:
            price = None

        if name_prefix == 'wefly':
            # Abroad plans: parse GB and days from block
            gb   = _parse_gb(block_text)
            days = _parse_days(block_text)

            # Extras: meaningful lines only (skip noise and redundant lines)
            extras = []
            for line in block_text.split('\n'):
                line = line.strip()
                if (line and line != name
                        and '\u20aa' not in line
                        and 'לחודש' not in line
                        and 'אונליין' not in line
                        and 'פרטי' not in line
                        and 'רשימת' not in line
                        and not re.match(r'^[\d.,\s]+(?:GB|MB)?$', line, re.IGNORECASE)  # skip bare GB numbers
                        and not re.match(r'^[\d.,]+$', line)):
                    extras.append(line)
            seen_e, clean_extras = set(), []
            for e in extras:
                if e not in seen_e and len(e) > 2:
                    seen_e.add(e); clean_extras.append(e)
                if len(clean_extras) >= 4: break

            plans.append({"carrier": "wecom", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": None, "sms": None,
                          "extras": clean_extras})
        else:
            # Domestic plans: all have unlimited domestic data → gb = None always
            gb = None

            # Parse minutes from "X,000 דקות" line
            minutes_m = re.search(r'([\d,]+)\s*דקות', block_text)
            minutes = int(minutes_m.group(1).replace(',', '')) if minutes_m else None

            # Extract extras: include useful bullets from both בארץ and בחו"ל sections
            SKIP_DOMESTIC = {'בארץ:', 'בחו"ל:', 'בחו״ל:', 'השארת פרטים', 'הצטרפות אונליין >',
                             'פרטי החבילה', 'לרשימת המדינות', 'מחירון שיחות והודעות',
                             'מכשירים הנתמכים ב-5G', 'מכשירים הנתמכים ב5G'}
            extras = []
            for line in block_text.split('\n'):
                line = line.strip()
                if not line or line == name:
                    continue
                # Footnote lines (starting with *): strip prefix and include as condition note
                if re.match(r'^\*', line):
                    note = line.lstrip('* ').strip()
                    if note and len(note) > 2:
                        extras.append('* ' + note)
                    continue
                # Skip noisy/navigation lines
                if ('\u20aa' in line or 'לחודש' in line or line in SKIP_DOMESTIC
                        or 'אונליין' in line or 'פרטי' in line or 'מכשירים' in line
                        or 'מחירון' in line or 'רשימת' in line
                        or re.match(r'^[\d.,]+$', line)):
                    continue
                extras.append(line)
            seen_e, clean_extras = set(), []
            for e in extras:
                if e not in seen_e and len(e) > 2:
                    seen_e.add(e); clean_extras.append(e)
                if len(clean_extras) >= 8: break

            plans.append({"carrier": "wecom", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": minutes, "extras": clean_extras})

    seen_names, deduped = set(), []
    for p in plans:
        if p["plan_name"] not in seen_names:
            seen_names.add(p["plan_name"]); deduped.append(p)
    return deduped


def scrape_wecom(_page=None):
    """Scrape We-Com domestic plans. Uses own fresh session with UA."""
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_WECOM_UA)
        try:
            return _scrape_wecom_page(page, "https://we-com.co.il/cellular-packages/", "wecom")
        finally:
            browser.close()


def scrape_wecom_abroad(_page=None):
    """Scrape We-Com abroad (wefly) packages. Uses own fresh session with UA."""
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_WECOM_UA)
        try:
            # Click "show more" to reveal all packages
            page.goto("https://we-com.co.il/roaming/", timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(2000)
            for btn in page.query_selector_all("a, button"):
                txt = (btn.inner_text() or "").strip()
                if "נוספות" in txt or "עוד חבילות" in txt or "לצפייה" in txt:
                    try:
                        btn.scroll_into_view_if_needed()
                        btn.click()
                        page.wait_for_timeout(1500)
                    except Exception:
                        pass
                    break
            return _scrape_wecom_page(page, "https://we-com.co.il/roaming/", "wefly", already_navigated=True)
        finally:
            browser.close()


def scrape_all():
    """Scrape all carriers sequentially. Returns flat list of plan dicts."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        plans = []
        for fn in [scrape_partner, scrape_pelephone, scrape_hotmobile, scrape_cellcom, scrape_xphone, scrape_wecom, scrape_019]:
            try:
                result = fn(page)
                if not result:
                    logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping to avoid false 'removed' alerts.")
                else:
                    logger.info(f"{fn.__name__}: {len(result)} plans")
                    plans.extend(result)
            except Exception as e:
                logger.error(f"{fn.__name__} failed: {e}", exc_info=True)
        browser.close()
    return plans


def scrape_partner(page):
    page.goto("https://www.partner.co.il/n/cellularsale/lobby", timeout=30000, wait_until="networkidle")
    page.wait_for_selector(".plan-wrapper", timeout=15000)
    plans = []
    for card in page.query_selector_all(".plan-wrapper"):
        name_el  = card.query_selector("h3.title")
        price_el = card.query_selector(".plan-banner .price")
        gb_el    = card.query_selector(".plan-banner .size")
        extras   = list(dict.fromkeys(el.inner_text().strip() for el in card.query_selector_all(".plan-advantages p") if el.inner_text().strip()))
        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        gb    = _parse_gb(gb_el.inner_text())       if gb_el    else None
        if name and name != "לא ידוע":
            plans.append({"carrier": "partner", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": None, "extras": extras})
    return plans


def scrape_pelephone(page):
    page.goto(
        "https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_selector(".border_5 .item", timeout=15000)
    plans = []
    for card in page.query_selector_all(".border_5 .item"):
        name_el  = card.query_selector(".superlative")
        price_el = card.query_selector(".c")
        gb_el    = card.query_selector(".only_gb")
        inc_texts = list(dict.fromkeys(
            s.inner_text().strip()
            for s in card.query_selector_all(".mid_white .inc span > span")
            if s.inner_text().strip()
        ))
        free_el = card.query_selector(".free_apps span")
        if free_el:
            fa = free_el.inner_text().strip()
            if fa and fa not in inc_texts:
                inc_texts.append(fa)
        extras = inc_texts
        name  = name_el.inner_text().strip() if name_el else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        gb    = _parse_gb(gb_el.inner_text())       if gb_el    else None
        if name and name != "לא ידוע":
            plans.append({"carrier": "pelephone", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": None, "extras": extras})
    return plans


def scrape_hotmobile(page):
    import json as _json
    page.goto("https://www.hotmobile.co.il/saleslobby", timeout=30000, wait_until="networkidle")
    page.wait_for_selector(".package-wrap.js-plan-filter", timeout=15000)
    plans = []
    # query_selector_all returns ALL elements including display:none (hidden tabs)
    for card in page.query_selector_all(".package-wrap.js-plan-filter"):
        # Prefer data-* attributes on the hidden input — always populated, tab-independent
        details_el = card.query_selector("input[id^='planDetails-']")
        data_name  = details_el.get_attribute("data-poname")  if details_el else None
        data_price = details_el.get_attribute("data-saleprice") if details_el else None

        name_el  = card.query_selector("h1.name")
        price_el = card.query_selector(".current-price")
        name  = (data_name or (name_el.inner_text().strip() if name_el else "")).strip() or "לא ידוע"
        price = _parse_price(data_price) if data_price else (_parse_price(price_el.inner_text()) if price_el else None)

        # GB: read planDetails JSON, pick "גלישה סלולרית בארץ" line (domestic data)
        # Ignores "גלישה בחו"ל" (abroad) lines
        gb_text = None
        extras  = []
        if details_el:
            try:
                details = _json.loads(details_el.get_attribute("value") or "[]")
                extras  = [d.strip() for d in details if d and d.strip()]
                for d in extras:
                    has_number = bool(re.search(r"\d", d))
                    if not has_number:
                        continue
                    if ("גלישה סלולרית בארץ" in d or "גלישה בארץ" in d or
                            "גלישה כל חודש" in d or
                            ("גלישה" in d and "חו" not in d)):
                        gb_text = d
                        break
                # Fallback: any line with GB
                if not gb_text:
                    for d in extras:
                        if "GB" in d and re.search(r"\d", d):
                            gb_text = d
                            break
            except Exception:
                pass
        # Fallback: largest GB from .feature-name visible text
        if not gb_text:
            best_gb, best_text = -1, None
            for feat in card.query_selector_all(".feature-name"):
                t = feat.inner_text()
                parsed = _parse_gb(t)
                if parsed is not None and parsed > best_gb:
                    best_gb, best_text = parsed, t
            gb_text = best_text
        # Fallback extras
        if not extras:
            extras = [el.inner_text().strip() for el in card.query_selector_all(".additional-features .feature") if el.inner_text().strip()]

        gb = _parse_gb(gb_text)
        # Parse minutes from planDetails JSON
        minutes = None
        for d in extras:
            if re.search(r"\d", d) and ("דקות שיחה" in d or "דקות" in d) and "חו" not in d and "לחו" not in d:
                minutes = _parse_minutes(d)
                break
        if name and name != "לא ידוע":
            plans.append({"carrier": "hotmobile", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": minutes, "extras": extras})
    return plans


def scrape_cellcom(page):
    page.goto("https://cellcom.co.il/production/Private/Cellular/Packages/", timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(4000)
    plans = []
    for card in page.query_selector_all(".package"):
        # Only cellular plan cards
        sale_type = card.get_attribute("data-saletype") or ""
        if sale_type and "cellular" not in sale_type.lower():
            continue
        title_el  = card.query_selector(".header .title p")
        price_el  = card.query_selector(".body-package .content")
        feat_els  = card.query_selector_all(".body-package .header-feature .text")
        extras    = [el.inner_text().strip() for el in feat_els if el.inner_text().strip()]
        # Name and GB are in same element separated by newline
        name, gb_text = "לא ידוע", None
        if title_el:
            parts = [p.strip() for p in title_el.inner_text().split("\n") if p.strip()]
            name    = parts[0] if parts else "לא ידוע"
            gb_text = parts[1] if len(parts) > 1 else None
        # Price: first line only (ignore promo text like "לחודשיים הראשונים")
        price = _parse_price(price_el.inner_text().split("\n")[0]) if price_el else None
        gb    = _parse_gb(gb_text)
        # Minutes: look for "דק' /SMS" feature line
        minutes = None
        for feat in extras:
            if "דק" in feat and "חו" not in feat:
                minutes = _parse_minutes(feat)
                break
        if name and name != "לא ידוע":
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": minutes, "extras": extras})
    return plans


def scrape_019(_page=None):
    """
    019 is behind Incapsula WAF.
    Uses playwright-stealth + fresh isolated session to bypass bot detection.
    The _page argument is accepted but ignored (019 needs its own stealth session).
    """
    _STEALTH_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    from playwright_stealth import Stealth
    with Stealth().use_sync(sync_playwright()) as pw:
        browser = pw.chromium.launch(headless=True)
        p019 = browser.new_page()
        try:
            p019.goto(
                "https://019mobile.co.il/חבילות-סלולר/",
                timeout=40000, wait_until="load"
            )
            p019.wait_for_timeout(5000)

            # Guard against Incapsula challenge page (< 10 KB = not real content)
            if len(p019.content()) < 10000:
                logger.warning("scrape_019: Incapsula block detected — page too small. Returning [].")
                return []

            plans = []
            for card in p019.query_selector_all(".item_pack"):
                name_el  = card.query_selector("h3.title")
                price_el = card.query_selector(".price_gb .price") or card.query_selector(".price")
                gb_el    = card.query_selector(".price_gb .gb")

                name = "לא ידוע"
                if name_el:
                    badge = name_el.query_selector(".badge")
                    badge_text = badge.inner_text().strip() if badge else ""
                    name = name_el.inner_text().strip().replace(badge_text, "").strip()

                price = _parse_price(price_el.inner_text().replace("₪", "").strip()) if price_el else None
                gb    = _parse_gb(gb_el.inner_text()) if gb_el else None

                extras = []
                for li_el in card.query_selector_all(".blist li"):
                    text = li_el.inner_text().strip()
                    if not text:
                        continue
                    if gb is None and re.search(r"\d+\s*(GB|MB|gb|mb)", text):
                        gb = _parse_gb(text)
                    extras.append(text)

                if name and name != "לא ידוע":
                    plans.append({"carrier": "mobile019", "plan_name": name, "price": price,
                                  "data_gb": gb, "minutes": None, "extras": extras})
            return plans
        finally:
            browser.close()


# ── Abroad / Roaming scrapers ──────────────────────────────────────────────

def scrape_pelephone_abroad(page):
    page.goto("https://www.pelephone.co.il/digitalsite/heb/abroad/packages/",
              timeout=40000, wait_until="load")
    page.wait_for_timeout(3000)
    more_btn = page.query_selector(".btn_more_packs.more_show")
    if more_btn and more_btn.is_visible():
        more_btn.click()
        page.wait_for_timeout(1500)
    plans = []
    seen = set()
    for card in page.query_selector_all(".package"):
        ttl_el = card.query_selector(".ttl")
        if not ttl_el:
            continue
        period_el = ttl_el.query_selector(".period")
        price_el  = ttl_el.query_selector(".price")
        period_text = period_el.inner_text().strip() if period_el else ""
        price_text  = price_el.inner_text().strip()  if price_el  else ""
        ttl_text = ttl_el.inner_text().strip()
        raw_name = ttl_text.replace(period_text, "").replace(price_text, "").replace("להזמנה", "").replace("›", "")
        raw_name = re.sub(r'₪\d+', '', raw_name)   # strip crossed-out prices like ₪319
        name = re.sub(r'\s+', ' ', raw_name).strip()
        price = _parse_price(price_text)
        days  = _parse_days(period_text)
        gb_el  = card.query_selector(".data .g_d_s .g")
        min_el = card.query_selector(".data .g_d_s .d")
        sms_el = card.query_selector(".data .g_d_s .s")
        gb      = _parse_gb(gb_el.inner_text())       if gb_el  else None
        # Fallback: MB-tier plans store value elsewhere; search entire .data block
        if gb is None:
            data_el = card.query_selector(".data")
            if data_el:
                gb = _parse_gb(data_el.inner_text())
        minutes = _parse_minutes(min_el.inner_text()) if min_el else None
        sms     = _parse_sms(sms_el.inner_text())     if sms_el else None
        extras = []
        for e_el in card.query_selector_all(".data .free_app"):
            t = e_el.inner_text().strip()
            if t:
                extras.append(t)
        if not name:
            continue
        key = (name, days, price)
        if key in seen:
            continue
        seen.add(key)
        plans.append({"carrier": "pelephone", "plan_name": name, "price": price,
                      "days": days, "data_gb": gb, "minutes": minutes,
                      "sms": sms, "extras": extras})
    return plans


def scrape_cellcom_abroad(page):
    """Scrape Cellcom abroad packages via their internal API (returns all 8+ plans)
       plus the Silent Roamers page for additional packages."""
    import urllib.request, urllib.error, json as _json

    plans = []
    seen_names = set()

    # ── Source 1: API (lobby packages) ────────────────────────────────────
    SOC_IDS = ["FMWH998","FMWH267","FMWH0047","FMWH717","FMWH720",
               "HUL4209","FMWH995","HUL4539"]
    try:
        payload = _json.dumps({"SocIdList": SOC_IDS, "BlockId": 20557}).encode()
        req = urllib.request.Request(
            "https://digital-api.cellcom.co.il/api/abroad/GetPackagePopular",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://cellcom.co.il",
                "Referer": "https://cellcom.co.il/AbroadMain/lobby/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())
        for pkg in data.get("Body", []):
            name = (pkg.get("titleEpi") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            price   = pkg.get("price")
            days    = pkg.get("packageDuration")
            details = (pkg.get("packageDetailsList") or [{}])[0]
            d_data  = details.get("data") or {}
            d_voice = details.get("voice") or {}
            d_sms   = details.get("sms") or {}
            gb      = float(d_data["value"]) if d_data.get("value") is not None else None
            if d_data.get("isUnlimited"):
                gb = None
            minutes = int(d_voice["value"]) if d_voice.get("value") is not None else None
            sms     = int(d_sms["value"])   if d_sms.get("value")   is not None else None
            extras  = []
            tag = (pkg.get("tagTextSecondary") or "").strip()
            if tag:
                extras.append(tag)
            app_info = pkg.get("dataForApp") or {}
            if app_info.get("hasDataForApp"):
                extras.append("גלישה חופשית באפליקציות נבחרות")
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": extras})
    except Exception as e:
        logger.error(f"Cellcom abroad API failed: {e}")

    # ── Source 2: Silent Roamers page (DOM) ───────────────────────────────
    try:
        page.goto("https://cellcom.co.il/AbroadMain/Silent_roamers-old/",
                  timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(2000)
        for card in page.query_selector_all(".abroad-package-client"):
            name_el     = card.query_selector(".abroad-package-client__title")
            duration_el = card.query_selector(".abroad-package-client__duration")
            data_el     = card.query_selector(".abroad-package-client__data--bank")
            voice_sms   = card.query_selector_all(".abroad-package-voice-sms__value")
            price_el    = card.query_selector(".abroad-package-client__price-real--bank--container")
            name = name_el.inner_text().strip() if name_el else ""
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            days    = _parse_days(duration_el.inner_text() if duration_el else "")
            gb      = _parse_gb(data_el.inner_text()) if data_el else None
            minutes = _parse_minutes(voice_sms[0].inner_text()) if len(voice_sms) > 0 else None
            sms     = _parse_sms(voice_sms[1].inner_text())     if len(voice_sms) > 1 else None
            price   = None
            if price_el:
                for span in price_el.query_selector_all("span"):
                    t = span.inner_text().strip()
                    if re.match(r'^\d', t):
                        price = _parse_price(t)
                        break
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": []})
    except Exception as e:
        logger.error(f"Cellcom silent roamers scrape failed: {e}")

    return plans


def scrape_partner_abroad(page):
    page.goto("https://www.partner.co.il/n/roamingcellular/lobby",
              timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(2000)
    for btn in page.query_selector_all("button, a"):
        try:
            if btn.is_visible() and "לצפייה בחבילות נוספות" in btn.inner_text():
                btn.click()
                page.wait_for_timeout(1500)
                break
        except Exception:
            pass
    plans = []
    for card in page.query_selector_all(".package-wrapper"):
        name_el     = card.query_selector(".package-name")
        size_el     = card.query_selector(".package-size")
        price_el    = card.query_selector(".price-text")
        desc_items  = [el.inner_text().strip()
                       for el in card.query_selector_all(".description-item .description-text")
                       if el.inner_text().strip()]
        marketing_el = card.query_selector(".marketing-text")
        name  = name_el.inner_text().strip()    if name_el  else "לא ידוע"
        gb    = _parse_gb(size_el.inner_text()) if size_el  else None
        price = _parse_price(price_el.inner_text()) if price_el else None
        days, minutes, sms = None, None, None
        for item in desc_items:
            if "ימים" in item and days is None:
                days = _parse_days(item)
            elif "דקות" in item and minutes is None:
                minutes = _parse_minutes(item)
            elif "הודעות" in item and sms is None:
                sms = _parse_sms(item)
        extras = []
        if marketing_el:
            t = marketing_el.inner_text().strip()
            if t:
                extras.append(t)
        for d in desc_items:
            if "ימים" not in d and "דקות" not in d and "הודעות" not in d:
                extras.append(d)
        if name and name != "לא ידוע":
            plans.append({"carrier": "partner", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": extras})
    return plans


def scrape_hotmobile_abroad(page):
    page.goto("https://www.hotmobile.co.il/roaming", timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(2000)
    for el in page.query_selector_all("a, button, [role='button']"):
        try:
            if el.is_visible() and "לחבילות נוספות" in el.inner_text():
                el.click()
                page.wait_for_timeout(1500)
                break
        except Exception:
            pass
    plans = []
    for card in page.query_selector_all(".lobby2022_dealsItem"):
        name_el     = card.query_selector(".dealsItem_title h3")
        price_el    = card.query_selector(".dealsItem_priceAmount strong")
        duration_el = card.query_selector(".dealsItem_priceDetails")
        detail_lis  = card.query_selector_all(".dealsItem_details li")
        name = name_el.inner_text().strip() if name_el else "לא ידוע"
        price = None
        if price_el:
            price = _parse_price(price_el.inner_text().replace("₪", "").strip())
        days = _parse_days(duration_el.inner_text() if duration_el else "")
        gb = None
        extras = []
        for i, li in enumerate(detail_lis):
            b_el = li.query_selector("b")
            b_text = b_el.inner_text().strip() if b_el else ""
            spans = [s.inner_text().strip() for s in li.query_selector_all("span")]
            span_text = " ".join(spans)
            if i == 0 and b_text and ("GB" in b_text or "MB" in b_text.upper() or "גלישה" in span_text):
                gb = _parse_gb(b_text)
            elif "שיחה" in span_text or "SMS" in span_text or "הודעת" in span_text:
                pass  # pay-per-use rate, skip
            else:
                full = li.inner_text().strip()
                if full:
                    extras.append(full)
        if name and name != "לא ידוע":
            plans.append({"carrier": "hotmobile", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": None,
                          "sms": None, "extras": extras})
    return plans


def scrape_019_abroad(_page=None):
    """019 abroad is behind Incapsula — uses same Stealth session as scrape_019."""
    from playwright_stealth import Stealth
    _STEALTH_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    with Stealth().use_sync(sync_playwright()) as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(
                "https://019mobile.co.il/%d7%92%d7%9c%d7%99%d7%a9%d7%94-%d7%91%d7%97%d7%95%d7%9c-"
                "%d7%97%d7%91%d7%99%d7%9c%d7%94-%d7%9c%d7%97%d7%95%d7%9c-%d7%97%d7%91%d7%99%d7%9c%d7%95%d7%aa-"
                "%d7%90%d7%99%d7%a0%d7%98%d7%a8%d7%a0%d7%98/",
                timeout=40000, wait_until="load"
            )
            page.wait_for_timeout(5000)

            if len(page.content()) < 10000:
                logger.warning("scrape_019_abroad: Incapsula block detected. Returning [].")
                return []

            plans = []
            for card in page.query_selector_all(".item_pack"):
                name_el  = card.query_selector("h3.title")
                price_el = card.query_selector(".price_gb .price")
                gb_el    = card.query_selector(".price_gb .gb")
                blist_els = card.query_selector_all(".blist li")
                name = "לא ידוע"
                if name_el:
                    badge = name_el.query_selector(".badge")
                    badge_text = badge.inner_text().strip() if badge else ""
                    name = name_el.inner_text().strip().replace(badge_text, "").strip()
                price = _parse_price(price_el.inner_text().replace("₪", "").strip()) if price_el else None
                gb = _parse_gb(gb_el.inner_text()) if gb_el else None
                days, minutes = None, None
                extras = []
                for li_el in blist_els:
                    text = li_el.inner_text().strip()
                    if not text:
                        continue
                    if "למשך" in text and "ימים" in text:
                        days = _parse_days(text)
                    elif "דק" in text:
                        strong = li_el.query_selector("strong")
                        minutes = _parse_minutes(strong.inner_text() if strong else text)
                    else:
                        extras.append(text)
                if name and name != "לא ידוע":
                    plans.append({"carrier": "mobile019", "plan_name": name, "price": price,
                                  "days": days, "data_gb": gb, "minutes": minutes,
                                  "sms": None, "extras": extras})
            return plans
        finally:
            browser.close()


# ── Global eSIM scrapers ───────────────────────────────────────────────────

def _get_usd_to_ils():
    """Fetch live USD→ILS exchange rate. Returns float (fallback: 3.7)."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(
            "https://api.exchangerate.host/latest?base=USD&symbols=ILS", timeout=8
        ) as r:
            data = _json.loads(r.read())
            rate = data["rates"]["ILS"]
            logger.info(f"USD→ILS rate: {rate}")
            return float(rate)
    except Exception:
        try:
            import urllib.request, json as _json
            with urllib.request.urlopen(
                "https://open.er-api.com/v6/latest/USD", timeout=8
            ) as r:
                data = _json.loads(r.read())
                rate = data["rates"]["ILS"]
                logger.info(f"USD→ILS rate (fallback): {rate}")
                return float(rate)
        except Exception as e:
            logger.warning(f"Exchange rate fetch failed: {e}. Using 3.7")
            return 3.7


def _get_eur_to_ils():
    """Fetch live EUR→ILS exchange rate. Returns float (fallback: 4.0)."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/EUR", timeout=8
        ) as r:
            data = _json.loads(r.read())
            rate = data["rates"]["ILS"]
            logger.info(f"EUR→ILS rate: {rate}")
            return float(rate)
    except Exception as e:
        logger.warning(f"EUR rate fetch failed: {e}. Using 4.0")
        return 4.0


def _make_global_plan(carrier, name, price_ils, currency, original_price,
                      data_gb, days, minutes=None, sms=None, esim=True, extras=None):
    return {
        "carrier": carrier,
        "plan_name": name,
        "price": round(price_ils, 2) if price_ils is not None else None,
        "currency": currency,
        "original_price": original_price,
        "days": days,
        "data_gb": data_gb,
        "minutes": minutes,
        "sms": sms,
        "esim": esim,
        "extras": extras or [],
    }


def scrape_tuki_global(page, usd_rate):
    page.goto(
        "https://www.tuki-esim.co.il/ds/heb/hp/regional-packages/global/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_timeout(2000)
    plans = []
    for card in page.query_selector_all(".blue5, .blue15, .blue30"):
        gb_el    = card.query_selector(".gb span")
        price_el = card.query_selector(".price span:last-child")
        valid_el = card.query_selector(".valid span")
        if not gb_el or not price_el:
            continue
        gb_text    = gb_el.inner_text().strip()
        price_text = price_el.inner_text().strip()
        valid_text = valid_el.inner_text().strip() if valid_el else ""
        gb      = _parse_gb(gb_text)
        days    = _parse_days(valid_text)
        usd_val = _parse_price(price_text)
        if usd_val is None:
            continue
        price_ils = round(usd_val * usd_rate, 2)
        name = f"Tuki Global {gb_text}"
        if days:
            name += f" {days}d"
        plans.append(_make_global_plan(
            "tuki", name, price_ils, "USD", usd_val,
            gb, days, extras=["139 מדינות", "eSIM בלבד"]
        ))
    logger.info(f"Tuki global: {len(plans)} plans")
    return plans


def scrape_globalesim_global(page):
    page.goto(
        "https://globalesim.co.il/continent/esim-global/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_timeout(2000)
    plans = []
    seen_names = set()

    def scrape_tab(minutes_val):
        for card in page.query_selector_all(".dataInfo_box"):
            name_el  = card.query_selector(".dataInfo_content_top p")
            price_el = card.query_selector(".woocommerce-Price-amount bdi")
            lis = card.query_selector_all("ul li")
            name = name_el.inner_text().strip() if name_el else "לא ידוע"
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            price = None
            if price_el:
                price = _parse_price(price_el.inner_text().replace("₪", "").strip())
            gb, days, countries = None, None, None
            for li in lis:
                t = li.inner_text().strip()
                if "ימים" in t and days is None:
                    days = _parse_days(t)
                elif "מדינות" in t and countries is None:
                    countries = t
                elif ("GB" in t or "גיגה" in t) and gb is None:
                    gb = _parse_gb(t)
            extras = []
            if countries:
                extras.append(countries)
            bonus = card.query_selector(".gift_badge")
            if bonus:
                bt = bonus.inner_text().strip()
                if bt:
                    extras.append(bt)
            plans.append(_make_global_plan(
                "globalesim", name, price, "ILS", price,
                gb, days, minutes=minutes_val, extras=extras
            ))

    # Data-only tab (active by default)
    scrape_tab(None)

    # Calls+Data tab
    tabs = page.query_selector_all(".choose_plan_type_button")
    if len(tabs) > 1:
        tabs[1].click()
        page.wait_for_timeout(1500)
        scrape_tab(50)

    logger.info(f"GlobaleSIM global: {len(plans)} plans")
    return plans


def scrape_airalo_global(page, usd_rate):
    """Scrape Airalo global eSIM packages via REST API (no Playwright needed).
    Uses x-client-version: version2 header to get all operators (Discover + Discover+).
    """
    import urllib.request as _req
    import json as _json
    plans = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.airalo.com/global-esim",
            "x-client-version": "version2",
            "accept-language": "en",
        }
        request = _req.Request(
            "https://www.airalo.com/api/v4/regions/world",
            headers=headers
        )
        with _req.urlopen(request, timeout=15) as resp:
            data = _json.loads(resp.read().decode())

        packages = data.get("packages", [])
        seen = set()
        for pkg in packages:
            try:
                slug = pkg.get("slug", "")
                if slug in seen:
                    continue
                seen.add(slug)

                # Price: always in USD
                price_obj = pkg.get("price", {})
                usd = float(price_obj.get("amount", 0))
                if usd <= 0:
                    continue
                price_ils = round(usd * usd_rate, 2)

                # Data amount (stored in MB in 'amount' field)
                if pkg.get("is_unlimited"):
                    gb = None
                else:
                    mb = pkg.get("amount", 0)
                    gb = round(mb / 1024, 2) if mb else None

                days    = pkg.get("day")
                minutes = pkg.get("voice")    # None for data-only plans
                sms     = pkg.get("text")     # None for data-only plans

                # Operator name: "Discover" or "Discover+"
                operator_title = pkg.get("operator", {}).get("title", "Discover")

                # Build plan name including operator to distinguish the two
                gb_label  = f"{int(gb)}GB" if gb and gb == int(gb) else (f"{gb}GB" if gb else "ללא הגבלה")
                day_label = f"{days}d" if days else ""
                name = f"Airalo {operator_title} {gb_label} {day_label}".strip()

                # Extras
                operator = pkg.get("operator", {})
                country_count = len(operator.get("countries", []))
                extras = []
                if country_count:
                    extras.append(f"{country_count}+ מדינות")
                extras.append("eSIM בלבד")

                plans.append(_make_global_plan(
                    "airalo", name, price_ils, "USD", usd,
                    gb, days, minutes=minutes, sms=sms, esim=True,
                    extras=extras
                ))
            except Exception as e:
                logger.debug(f"Airalo package parse error: {e}")
                continue
    except Exception as e:
        logger.error(f"Airalo API failed: {e}", exc_info=True)

    logger.info(f"Airalo global: {len(plans)} plans")
    return plans


def scrape_pelephone_globalsim(page):
    page.goto(
        "https://www.pelephone.co.il/digitalsite/heb/abroad/global-sim/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_timeout(2000)
    plans = []
    seen_gb_days = set()
    for card in page.query_selector_all(".packs > div[id^='p']"):
        name_el  = card.query_selector(".pack_top .name span")
        name2_el = card.query_selector(".pack_top .name.name2")
        price_el = card.query_selector(".pack_top .price")
        valid_el = card.query_selector(".supperlative")
        txt_el   = card.query_selector(".new_txt")
        esim_el  = card.query_selector(".best_offer img[alt*='\u05e1\u05d9\u05dd'], .best_offer img[alt*='eSIM'], .best_offer img")
        if not price_el:
            continue
        price_text = price_el.inner_text().replace("\u20aa", "").strip()
        price = _parse_price(price_text)
        if price is None:
            continue

        # Detect voice-only plans (name2 class)
        is_voice_plan = name2_el is not None and (not name_el or "\u05d3\u05e7\u05d5\u05ea" in (name2_el.inner_text() or ""))
        if is_voice_plan:
            full_text = name2_el.inner_text().strip()
            m_min = re.search(r"(\d+)", full_text)
            voice_minutes = int(m_min.group(1)) if m_min else 0
            gb = 0
            gb_text = f"{voice_minutes} \u05d3\u05e7\u05d5\u05ea"
            plan_minutes = voice_minutes
            plan_extras = ["\u05d3\u05e7\u05d5\u05ea \u05dc\u05d9\u05e9\u05e8\u05d0\u05dc \u05d5\u05d1\u05d7\u05d5\"\u05dc"]
        else:
            if not name_el:
                continue
            gb_text = name_el.inner_text().strip()
            gb = _parse_gb(gb_text)
            if gb is None:
                continue
            plan_minutes = None
            plan_extras = []

        dedup_key = (gb_text, price)
        if dedup_key in seen_gb_days:
            continue
        seen_gb_days.add(dedup_key)
        days = None
        if valid_el:
            spans = valid_el.query_selector_all("span")
            if len(spans) >= 2:
                num  = spans[0].inner_text().strip()
                unit = spans[1].inner_text().strip()
                if "\u05e9\u05e0" in unit:
                    try: days = int(num) * 365
                    except: pass
                elif "\u05d9\u05d5\u05dd" in unit or "\u05d9\u05de\u05d9\u05dd" in unit:
                    days = _parse_days(f"{num} {unit}")
        if not is_voice_plan and txt_el:
            t = txt_el.inner_text().strip()
            if t:
                m = re.search(r"(\d+)\s*\u05d3\u05e7\u05d5\u05ea", t)
                if m:
                    plan_minutes = int(m.group(1))
                plan_extras.append(t)
        esim = esim_el is not None
        name = f"GlobalSIM {gb_text}"
        plans.append(_make_global_plan(
            "pelephone_global", name, price, "ILS", price,
            gb, days, minutes=plan_minutes, esim=esim, extras=plan_extras
        ))
    logger.info(f"Pelephone GlobalSIM: {len(plans)} plans")
    return plans


def scrape_esimo_global(page, usd_rate):
    import json as _json
    page.goto(
        "https://esimo.io/product/global-esim-only-data",
        timeout=45000, wait_until="domcontentloaded"
    )
    page.wait_for_timeout(4000)
    plans = []
    content = page.content()

    # Next.js embeds data as escaped JSON inside a script tag:
    # \"packages\":[{\"id\":\"...\",\"data\":1,\"validity\":7,\"price\":14.9,...}]
    # The literal string in content is: \"packages\":[ (backslash + quote)
    pkg_idx = content.find('\\"packages\\":[')
    if pkg_idx >= 0:
        bracket_start = content.index('[', pkg_idx)
        depth, end = 0, bracket_start
        for i in range(bracket_start, len(content)):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        pkg_str = content[bracket_start:end]
        # Unescape: \" → "  and \\\\ → \\
        pkg_str = pkg_str.replace('\\"', '"').replace('\\\\', '\\')
        try:
            pkgs = _json.loads(pkg_str)
            for pkg in pkgs:
                gb   = float(pkg.get("data", 0))
                days = int(pkg.get("validity", 0))
                usd  = float(pkg.get("price", 0))
                if gb <= 0 or days <= 0 or usd <= 0:
                    continue
                price_ils = round(usd * usd_rate, 2)
                gb_label = int(gb) if gb == int(gb) else gb
                name = f"eSIMo Global {gb_label}GB {days}d"
                plans.append(_make_global_plan(
                    "esimo", name, price_ils, "USD", usd,
                    gb, days, extras=["גלישה בלבד", "eSIM בלבד", "100+ מדינות"]
                ))
        except Exception as e:
            logger.error(f"eSIMo JSON parse failed: {e}", exc_info=True)

    # Fallback: scrape visible product option buttons
    if not plans:
        for btn in page.query_selector_all("button"):
            txt = btn.inner_text().strip()
            m = re.search(r"([\d.]+)\s*GB[^\d]*([\d]+)\s*(?:Days?|ימים)", txt, re.IGNORECASE)
            p = re.search(r"\$([\d.]+)", txt)
            if m and p:
                gb   = float(m.group(1))
                days = int(m.group(2))
                usd  = float(p.group(1))
                price_ils = round(usd * usd_rate, 2)
                gb_label = int(gb) if gb == int(gb) else gb
                plans.append(_make_global_plan(
                    "esimo", f"eSIMo Global {gb_label}GB {days}d", price_ils, "USD", usd,
                    gb, days, extras=["eSIM בלבד"]
                ))

    logger.info(f"eSIMo global: {len(plans)} plans")
    return plans


def scrape_simtlv_global(page):
    page.goto(
        "https://simtlv.co.il/global-61-30days/?refg=159162",
        timeout=35000, wait_until="networkidle"
    )
    page.wait_for_timeout(2000)
    plans = []
    for card in page.query_selector_all(".elementor-price-table"):
        name_el    = card.query_selector(".elementor-price-table__heading")
        price_el   = card.query_selector(".elementor-price-table__integer-part")
        period_el  = card.query_selector(".elementor-price-table__period")
        sub_el     = card.query_selector(".elementor-price-table__subheading")
        add_el     = card.query_selector(".elementor-price-table__additional_info")
        feat_els   = card.query_selector_all(".elementor-price-table__features-list li span")
        if not name_el or not price_el:
            continue
        name_text = name_el.inner_text().strip()
        price     = _parse_price(price_el.inner_text())
        period    = period_el.inner_text().strip() if period_el else ""
        days      = _parse_days(period)
        gb        = _parse_gb(name_text)
        if gb is None and sub_el:
            gb = _parse_gb(sub_el.inner_text())
        # Detect eSIM from additional_info or buy link
        is_esim = bool(add_el and "esim" in (add_el.inner_text() or "").lower())
        btn_el = card.query_selector(".elementor-price-table__button")
        if btn_el:
            href = btn_el.get_attribute("href") or ""
            if "esim" in href.lower():
                is_esim = True
        extras = ["127 מדינות"]
        for f in feat_els:
            t = f.inner_text().strip()
            if t and t not in extras:
                extras.append(t)
        esim_str = "eSIM" if is_esim else "Physical SIM"
        full_name = f"SimTLV {name_text} ({esim_str})"
        if price and gb:
            plans.append(_make_global_plan(
                "simtlv", full_name, price, "ILS", price,
                gb, days, esim=is_esim, extras=extras
            ))
    logger.info(f"SimTLV global: {len(plans)} plans")
    return plans


def scrape_world8_global(page):
    page.goto("https://world8.co.il/", timeout=35000, wait_until="networkidle")
    page.wait_for_timeout(2000)
    plans = []
    for card in page.query_selector_all(".price-card.popup_btn, .price-card.pricing_content"):
        name_el  = card.query_selector(".price-card--top h3")
        price_li = card.query_selector("li.price span")
        top_lis  = card.query_selector_all("li.top-text")
        text_li  = card.query_selector("li.text")
        badges   = card.query_selector_all(".notification-badge")
        if not name_el or not price_li:
            continue
        name  = name_el.inner_text().strip()
        price = _parse_price(re.sub(r'[^\d.]', '', price_li.inner_text()))
        gb, minutes, sms = None, None, None
        for li in top_lis:
            t = li.inner_text().strip()
            # Each li may contain multiple values like "60 דקות / 60 סמס / 1GB"
            # Parse GB only from explicit GB mention
            gb_m = re.search(r'(\d+(?:\.\d+)?)\s*GB', t, re.IGNORECASE)
            if gb_m and gb is None:
                gb = float(gb_m.group(1))
            min_m = re.search(r'(\d+)\s*דקות', t)
            if min_m and minutes is None:
                minutes = int(min_m.group(1))
            sms_m = re.search(r'(\d+)\s*(?:סמס|SMS)', t, re.IGNORECASE)
            if sms_m and sms is None:
                sms = int(sms_m.group(1))
        validity_text = text_li.inner_text().strip() if text_li else ""
        days = _parse_days(validity_text) if "ימים" in validity_text or "יום" in validity_text else None
        extras = [b.inner_text().strip() for b in badges if b.inner_text().strip()]
        if validity_text and validity_text not in extras:
            extras.append(validity_text)
        extras.append("120+ מדינות")
        if price and (gb or minutes):
            plans.append(_make_global_plan(
                "world8", name, price, "ILS", price,
                gb, days, minutes=minutes, sms=sms, esim=True, extras=extras
            ))
    logger.info(f"World8 global: {len(plans)} plans")
    return plans


def scrape_xphone_global(page=None):
    """Scrape XPhone global eSIM plans (אירופה + גלובלי) from xphone.co.il/roaming."""
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        pg = browser.new_page(user_agent=_XPHONE_UA)
        try:
            pg.goto("https://xphone.co.il/roaming", timeout=40000, wait_until="domcontentloaded")
            pg.wait_for_timeout(4000)
            body = pg.evaluate("document.body.innerText") or ""
            if "confirm you are human" in body.lower() or len(body) < 500:
                logger.warning("scrape_xphone_global: WAF block detected.")
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

                    extras = []
                    if minutes:
                        extras.append(f"{minutes} \u05d3\u05e7\u05d5\u05ea \u05d5-{sms} SMS")  # N דקות ו-N SMS

                    all_plans.append(_make_global_plan(
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


SAILY_SLUG_TO_HEBREW = {
    "afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df", "albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4", "andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4", "antigua-and-barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4", "armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4", "australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4", "azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4", "bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9", "barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4", "belize": "\u05d1\u05dc\u05d9\u05d6",
    "benin": "\u05d1\u05e0\u05d9\u05df", "bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4", "bonaire": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4", "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9", "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4", "cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada": "\u05e7\u05e0\u05d3\u05d4", "cape-verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "cayman-islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6-\u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "chad": "\u05e6'\u05d0\u05d3", "chile": "\u05e6'\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df", "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "cote-d-ivoire": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1", "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5", "cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic": "\u05e6'\u05db\u05d9\u05d4",
    "democratic-republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7", "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "east-timor": "\u05d8\u05d9\u05de\u05d5\u05e8-\u05dc\u05e1\u05d8\u05d4",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8", "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8", "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9", "faroe-islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fiji": "\u05e4\u05d9\u05d2'\u05d9", "finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france": "\u05e6\u05e8\u05e4\u05ea", "french-guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "french-polynesia": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon": "\u05d2\u05d1\u05d5\u05df", "gambia": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4", "germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "ghana": "\u05d2\u05d0\u05e0\u05d4", "gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "greece": "\u05d9\u05d5\u05d5\u05df", "greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4", "guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "guam": "\u05d2\u05d5\u05d0\u05dd", "guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9", "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4", "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9", "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2", "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3", "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4", "iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3", "isle-of-man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc", "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4", "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2'\u05e8\u05d6\u05d9", "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df", "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kosovo": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5", "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df", "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d5\u05d5\u05d9\u05d4", "lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4", "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0", "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau": "\u05de\u05e7\u05d0\u05d5", "macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8", "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4", "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali": "\u05de\u05d0\u05dc\u05d9", "malta": "\u05de\u05dc\u05d8\u05d4",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7", "mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1", "mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5", "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco": "\u05de\u05d5\u05e0\u05e7\u05d5", "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5", "montserrat": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5", "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4", "nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "nepal": "\u05e0\u05e4\u05d0\u05dc", "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3", "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d2\u05d5\u05d0\u05d4", "niger": "\u05e0\u05d9\u05d6'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "northern-mariana-islands": "\u05d0\u05d9\u05d9 \u05de\u05e8\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05d9\u05dd",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4", "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df", "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d2\u05d5\u05d5\u05d0\u05d9", "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd", "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc", "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8", "republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df", "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4", "saint-barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4", "saint-martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4", "san-marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea", "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4", "seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d0\u05d5\u05e0\u05d4", "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-maarten": "\u05e1\u05d9\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df", "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4", "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4", "south-sudan": "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "spain": "\u05e1\u05e4\u05e8\u05d3", "sri-lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "sudan": "\u05e1\u05d5\u05d3\u05df", "suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4", "switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df", "tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4", "thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "togo": "\u05d8\u05d5\u05d2\u05d5", "tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4", "turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-and-caicos-islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4", "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4", "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d0\u05d9",
    "us-virgin-islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d0\u05de\u05e8\u05d9\u05e7\u05e0\u05d9\u05dd",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df", "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4", "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4", "zimbabwe": "\u05d6\u05d9\u05de\u05d1\u05d0\u05d1\u05d5\u05d5\u05d4",
}


def scrape_saily_global(_page=None, usd_rate=None):
    """Scrape Saily eSIM plans from all ~199 country pages."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    all_plans = []
    JS_EXTRACT = """() => {
        const plans = [];
        document.querySelectorAll('[data-testid^="destination-hero-plan-card"]').forEach(card => {
            const gbEl = card.querySelector('[class*="body-md-medium"]');
            const gb = gbEl ? gbEl.textContent.trim() : '';
            let days = '';
            const daysEls = card.querySelectorAll('[class*="body-sm-medium"]');
            for (const el of daysEls) {
                const t = el.textContent.trim();
                if (t.includes('day')) { days = t; break; }
            }
            if (!days) {
                const sel = card.querySelector('select');
                if (sel && sel.options.length > 0) {
                    const opt = sel.options[sel.selectedIndex] || sel.options[0];
                    days = opt ? opt.text.trim() : '';
                }
            }
            const discEl = card.querySelector('[data-testid="pricing-card-discount-price"]');
            const origEl = card.querySelector('[data-testid="pricing-card-original-price"]');
            const priceEl = discEl || origEl;
            const price = priceEl ? priceEl.textContent.trim() : '';
            if (gb && days && price) plans.push({gb, days, price});
        });
        return plans;
    }"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=ua)
        for slug, country_heb in SAILY_SLUG_TO_HEBREW.items():
            try:
                page.goto(f"https://saily.com/esim-{slug}/", timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                raw = page.evaluate(JS_EXTRACT)
                for item in raw:
                    gb_text    = item["gb"]    # "1 GB", "Unlimited GB"
                    days_text  = item["days"]  # "7 days", "30 days"
                    price_text = item["price"] # "US$3.99"
                    gb   = _parse_gb(gb_text)  # None = unlimited
                    m    = re.search(r"(\d+)\s*day", days_text)
                    days = int(m.group(1)) if m else None
                    price_usd = _parse_price(price_text.replace("US$", "").strip())
                    if price_usd is None or days is None:
                        continue
                    price_ils = round(price_usd * usd_rate, 2)
                    if gb is None:
                        gb_str = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"  # ללא הגבלה
                    elif gb >= 1:
                        gb_str = f"{int(gb)}GB"
                    else:
                        gb_str = f"{round(gb * 1024)}MB"
                    plan_name = f"{country_heb} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"  # – N ימים
                    all_plans.append(_make_global_plan(
                        "saily", plan_name, price_ils, "USD", price_usd,
                        gb, days, esim=True, extras=[country_heb]
                    ))
            except Exception as exc:
                logger.warning(f"Saily {slug}: {exc}")
                continue
        browser.close()
    logger.info(f"Saily global: {len(all_plans)} plans from {len(SAILY_SLUG_TO_HEBREW)} countries")
    return all_plans


ESIMIO_SLUG_TO_HEBREW = {
    "afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "antigua-and-barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "azores": "\u05d0\u05d6\u05d5\u05e8\u05d9\u05dd",
    "bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "belize": "\u05d1\u05dc\u05d9\u05d6",
    "benin": "\u05d1\u05e0\u05d9\u05df",
    "bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "bonaire": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "canada": "\u05e7\u05e0\u05d3\u05d4",
    "canary-islands": "\u05d0\u05d9\u05d9 \u05e7\u05e0\u05e8\u05d9",
    "cape-verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "cayman-islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "chad": "\u05e6'\u05d0\u05d3",
    "chile": "\u05e6'\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df",
    "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "congo": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "cuba": "\u05e7\u05d5\u05d1\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "czechia": "\u05e6'\u05db\u05d9\u05d4",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "faroe-islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france": "\u05e6\u05e8\u05e4\u05ea",
    "french-guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "french-polynesia": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon": "\u05d2\u05d1\u05d5\u05df",
    "georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "ghana": "\u05d2\u05d0\u05e0\u05d4",
    "gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "greece": "\u05d9\u05d5\u05d5\u05df",
    "greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "guam": "\u05d2\u05d5\u05d0\u05dd",
    "guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iran": "\u05d0\u05d9\u05e8\u05df",
    "iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d5\u05d5\u05d9\u05d4",
    "lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau": "\u05de\u05e7\u05d0\u05d5",
    "macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "madeira": "\u05de\u05d3\u05d9\u05d9\u05e8\u05d4",
    "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "malta": "\u05de\u05dc\u05d8\u05d4",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayoette": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "montserrat": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "nepal": "\u05e0\u05e4\u05d0\u05dc",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d6'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "northern-cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "northern-mariana-islands": "\u05d0\u05d9\u05d9 \u05de\u05e8\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05d9\u05dd",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d2\u05d5\u05d5\u05d0\u05d9",
    "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8",
    "republic-of-the-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "russia": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saba": "\u05e1\u05d0\u05d1\u05d4",
    "saint-barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "san-marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "scotland": "\u05e1\u05e7\u05d5\u05d8\u05dc\u05e0\u05d3",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-eustatius": "\u05e1\u05d9\u05e0\u05d8 \u05d0\u05d5\u05e1\u05d8\u05d8\u05d9\u05d5\u05e1",
    "sint-maarten": "\u05e1\u05d9\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df",
    "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "spain": "\u05e1\u05e4\u05e8\u05d3",
    "sri-lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "sudan": "\u05e1\u05d5\u05d3\u05df",
    "suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-and-caicos-islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "united-states-of-america": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d0\u05d9",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "vatican": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


def scrape_esimio_destinations(_page=None, usd_rate=None):
    """Scrape eSIM.io per-country plans from all destination pages."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    all_plans = []
    JS_EXTRACT = """() => {
        const results = [];
        const headings = document.querySelectorAll('h5');
        for (const h of headings) {
            const text = h.textContent.trim();
            const m = text.match(/(\\d+(?:\\.\\d+)?)\\s*(GB|MB)\\s*\\/\\s*\\$(\\d+(?:\\.\\d+)?)/i);
            if (!m) continue;
            const amount = parseFloat(m[1]);
            const unit = m[2].toUpperCase();
            const price = parseFloat(m[3]);
            // Skip Pay As You Go (1 MB plans) and free trial (very small amounts)
            if (unit === 'MB' && amount <= 1) continue;
            if (price === 0) continue;
            results.push({amount, unit, price});
        }
        return results;
    }"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=ua)
        for slug, country_heb in ESIMIO_SLUG_TO_HEBREW.items():
            try:
                page.goto(
                    f"https://esim.io/destinations/esim-{slug}",
                    timeout=20000, wait_until="domcontentloaded"
                )
                page.wait_for_timeout(1500)
                raw = page.evaluate(JS_EXTRACT)
                for item in raw:
                    amount = item["amount"]
                    unit = item["unit"]
                    price_usd = item["price"]
                    # Convert MB to GB
                    if unit == "MB":
                        gb = round(amount / 1024, 4)
                    else:
                        gb = int(amount) if amount == int(amount) else amount
                    # Skip plans with less than 1 GB
                    if gb < 1:
                        continue
                    days = 30
                    price_ils = round(price_usd * usd_rate, 2)
                    gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
                    plan_name = f"{country_heb} \u2013 {gb_str} \u2013 30 \u05d9\u05de\u05d9\u05dd"
                    all_plans.append(_make_global_plan(
                        "esimio", plan_name, price_ils, "USD", price_usd,
                        gb, days, esim=True, extras=[country_heb]
                    ))
            except Exception as exc:
                logger.warning(f"eSIM.io {slug}: {exc}")
                continue
        browser.close()
    logger.info(f"eSIM.io destinations: {len(all_plans)} plans from {len(ESIMIO_SLUG_TO_HEBREW)} countries")
    return all_plans


HOLAFLY_SLUG_TO_HEBREW = {
    "albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "antigua-and-barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "belize": "\u05d1\u05dc\u05d9\u05d6",
    "benin": "\u05d1\u05e0\u05d9\u05df",
    "bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "bonaire": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4",
    "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada": "\u05e7\u05e0\u05d3\u05d4",
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6-\u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "chad": "\u05e6'\u05d0\u05d3",
    "chile": "\u05e6'\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df",
    "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic": "\u05e6'\u05db\u05d9\u05d4",
    "democratic-republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9",
    "faroe-islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france": "\u05e6\u05e8\u05e4\u05ea",
    "french-guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "french-polynesia": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon": "\u05d2\u05d1\u05d5\u05df",
    "georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "ghana": "\u05d2\u05d0\u05e0\u05d4",
    "gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "greece": "\u05d9\u05d5\u05d5\u05df",
    "greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "guam": "\u05d2\u05d5\u05d0\u05dd",
    "guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iran": "\u05d0\u05d9\u05e8\u05d0\u05df",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kosovo": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d5\u05d5\u05d9\u05d4",
    "liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau": "\u05de\u05e7\u05d0\u05d5",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali": "\u05de\u05d0\u05dc\u05d9",
    "malta": "\u05de\u05dc\u05d8\u05d4",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "nepal": "\u05e0\u05e4\u05d0\u05dc",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d6'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "north-macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d2\u05d5\u05d5\u05d0\u05d9",
    "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8",
    "republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "russia": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saint-barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d0\u05d5\u05e0\u05d4",
    "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "spain": "\u05e1\u05e4\u05e8\u05d3",
    "sri-lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "sudan": "\u05e1\u05d5\u05d3\u05df",
    "suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-and-caicos": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d0\u05d9",
    "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "yemen": "\u05ea\u05d9\u05de\u05df",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


# Key durations to keep from Holafly's 1-90 day range
_HOLAFLY_KEY_DAYS = {1, 3, 5, 7, 10, 15, 20, 30, 60, 90}


def scrape_holafly_global(_page=None, usd_rate=None):
    """Scrape Holafly eSIM plans via Shopify product JSON API (no Playwright needed).
    All Holafly plans offer unlimited data. Filters to key durations only."""
    import urllib.request, json as _json, time as _time

    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    all_plans = []
    success_count = 0

    for slug, country_heb in HOLAFLY_SLUG_TO_HEBREW.items():
        try:
            url = f"https://holafly-esim.myshopify.com/products/esim-{slug}.json"
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = _json.loads(resp.read())

            variants = data.get("product", {}).get("variants", [])
            for v in variants:
                sku = v.get("sku", "")
                # Parse days from SKU: esim-{country}-{N}-day(s)
                m = re.search(r"-(\d+)-days?$", sku)
                if not m:
                    continue
                days = int(m.group(1))
                if days not in _HOLAFLY_KEY_DAYS:
                    continue

                price_usd = _parse_price(str(v.get("price", "")))
                if price_usd is None:
                    continue

                price_ils = round(price_usd * usd_rate, 2)
                plan_name = f"{country_heb} \u2013 \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4 \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(_make_global_plan(
                    "holafly", plan_name, price_ils, "USD", price_usd,
                    data_gb=None,  # unlimited
                    days=days, esim=True, extras=[country_heb]
                ))

            success_count += 1
            _time.sleep(0.2)

        except Exception as exc:
            logger.warning(f"Holafly {slug}: {exc}")
            continue

    logger.info(f"Holafly global: {len(all_plans)} plans from {success_count}/{len(HOLAFLY_SLUG_TO_HEBREW)} countries")
    return all_plans


SAILY_REGIONS = {
    "africa":                       "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "asia-and-oceania":             "\u05d0\u05e1\u05d9\u05d4 \u05d5\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "caribbean-islands":            "\u05d0\u05d9\u05d9 \u05d4\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "europe":                       "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "global":                       "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "latin-america":                "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "middle-east-and-north-africa": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "north-america":                "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
}


def scrape_saily_regions(_page=None, usd_rate=None):
    """Scrape Saily regional eSIM plans from 8 region pages."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    all_plans = []
    JS_EXTRACT = """() => {
        const plans = [];
        document.querySelectorAll('[data-testid^="destination-hero-plan-card"]').forEach(card => {
            const gbEl = card.querySelector('[class*="body-md-medium"]');
            const gb = gbEl ? gbEl.textContent.trim() : '';
            let days = '';
            const daysEls = card.querySelectorAll('[class*="body-sm-medium"]');
            for (const el of daysEls) {
                const t = el.textContent.trim();
                if (t.includes('day')) { days = t; break; }
            }
            if (!days) {
                const sel = card.querySelector('select');
                if (sel && sel.options.length > 0) {
                    const opt = sel.options[sel.selectedIndex] || sel.options[0];
                    days = opt ? opt.text.trim() : '';
                }
            }
            const discEl = card.querySelector('[data-testid="pricing-card-discount-price"]');
            const origEl = card.querySelector('[data-testid="pricing-card-original-price"]');
            const priceEl = discEl || origEl;
            const price = priceEl ? priceEl.textContent.trim() : '';
            if (gb && days && price) plans.push({gb, days, price});
        });
        return plans;
    }"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=ua)
        for slug, region_heb in SAILY_REGIONS.items():
            try:
                page.goto(f"https://saily.com/esim-{slug}/", timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                raw = page.evaluate(JS_EXTRACT)
                for item in raw:
                    gb_text    = item["gb"]
                    days_text  = item["days"]
                    price_text = item["price"]
                    gb   = _parse_gb(gb_text)
                    m    = re.search(r"(\d+)\s*day", days_text)
                    days = int(m.group(1)) if m else None
                    price_usd = _parse_price(price_text.replace("US$", "").strip())
                    if price_usd is None or days is None:
                        continue
                    price_ils = round(price_usd * usd_rate, 2)
                    if gb is None:
                        gb_str = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"
                    elif gb >= 1:
                        gb_str = f"{int(gb)}GB"
                    else:
                        gb_str = f"{round(gb * 1024)}MB"
                    plan_name = f"{region_heb} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                    all_plans.append(_make_global_plan(
                        "saily", plan_name, price_ils, "USD", price_usd,
                        gb, days, esim=True, extras=[region_heb]
                    ))
            except Exception as exc:
                logger.warning(f"Saily region {slug}: {exc}")
                continue
        browser.close()
    logger.info(f"Saily regions: {len(all_plans)} plans from {len(SAILY_REGIONS)} regions")
    return all_plans


HOLAFLY_REGIONS = {
    "esim-asia":                    "\u05d0\u05e1\u05d9\u05d4",
    "esim-europe":                  "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "esim-south-america":           "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "esim-northamerica":            "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "oceania":                      "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "esim-caribbean":               "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "sudeste-asiatico":             "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "china-hong-kong-macau":        "\u05e1\u05d9\u05df + \u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2 + \u05de\u05e7\u05d0\u05d5",
    "japon-corea":                  "\u05d9\u05e4\u05df \u05d5\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "japon-china":                  "\u05d9\u05e4\u05df \u05d5\u05e1\u05d9\u05df",
    "escandinavia":                 "\u05e1\u05e7\u05e0\u05d3\u05d9\u05e0\u05d1\u05d9\u05d4",
    "centroamerica":                "\u05de\u05e8\u05db\u05d6 \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "balkans":                      "\u05d1\u05dc\u05e7\u05df",
    "europa-oriental":              "\u05de\u05d6\u05e8\u05d7 \u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
}

# Middle East & Africa don't have Shopify API — hardcoded key prices (USD)
_HOLAFLY_NON_SHOPIFY_REGIONS = {
    "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df": {  # המזרח התיכון
        1: 9.90, 3: 25.90, 5: 36.90, 7: 42.90, 10: 52.90,
        15: 79.90, 20: 106.90, 30: 161.90, 60: 256.90, 90: 322.90,
    },
    "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4": {  # אפריקה
        1: 9.90, 3: 25.90, 5: 36.90, 7: 42.90, 10: 52.90,
        15: 79.90, 20: 106.90, 30: 161.90, 60: 256.90, 90: 322.90,
    },
}


def scrape_holafly_regions(_page=None, usd_rate=None):
    """Scrape Holafly regional eSIM plans via Shopify product JSON API (no Playwright needed).
    All Holafly regional plans offer unlimited data. Filters to key durations only."""
    import urllib.request, json as _json, time as _time

    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    all_plans = []
    success_count = 0

    for slug, region_heb in HOLAFLY_REGIONS.items():
        try:
            url = f"https://holafly-esim.myshopify.com/products/{slug}.json"
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = _json.loads(resp.read())

            variants = data.get("product", {}).get("variants", [])
            for v in variants:
                sku = v.get("sku") or ""
                title = v.get("title") or ""
                m = re.search(r"(\d+)-days?", sku)
                if not m:
                    m = re.search(r"(\d+)\s*d[ií]as?", title)
                if not m:
                    continue
                days = int(m.group(1))
                if days not in _HOLAFLY_KEY_DAYS:
                    continue

                price_usd = _parse_price(str(v.get("price", "")))
                if price_usd is None:
                    continue

                price_ils = round(price_usd * usd_rate, 2)
                plan_name = f"{region_heb} \u2013 \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4 \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(_make_global_plan(
                    "holafly", plan_name, price_ils, "USD", price_usd,
                    data_gb=None,  # unlimited
                    days=days, esim=True, extras=[region_heb]
                ))

            success_count += 1
            _time.sleep(0.2)

        except Exception as exc:
            logger.warning(f"Holafly region {slug}: {exc}")
            continue

    # Add non-Shopify regions (Middle East & Africa) from hardcoded prices
    for region_heb, prices in _HOLAFLY_NON_SHOPIFY_REGIONS.items():
        for days, price_usd in prices.items():
            price_ils = round(price_usd * usd_rate, 2)
            plan_name = f"{region_heb} \u2013 \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4 \u2013 {days} \u05d9\u05de\u05d9\u05dd"
            all_plans.append(_make_global_plan(
                "holafly", plan_name, price_ils, "USD", price_usd,
                data_gb=None, days=days, esim=True, extras=[region_heb]
            ))
        success_count += 1

    logger.info(f"Holafly regions: {len(all_plans)} plans from {success_count}/{len(HOLAFLY_REGIONS) + len(_HOLAFLY_NON_SHOPIFY_REGIONS)} regions")
    return all_plans


def scrape_all_global():
    """Scrape global eSIM packages from all 7 providers. Returns flat list of plan dicts."""
    usd_rate = _get_usd_to_ils()
    eur_rate = _get_eur_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=ua)
        plans = []
        jobs = [
            ("scrape_tuki_global",          lambda pg: scrape_tuki_global(pg, usd_rate)),
            ("scrape_globalesim_global",    scrape_globalesim_global),
            ("scrape_airalo_global",        lambda pg: scrape_airalo_global(pg, usd_rate)),
            ("scrape_pelephone_globalsim",  scrape_pelephone_globalsim),
            ("scrape_esimo_global",         lambda pg: scrape_esimo_global(pg, usd_rate)),
            ("scrape_simtlv_global",        scrape_simtlv_global),
            ("scrape_world8_global",        scrape_world8_global),
            ("scrape_xphone_global",        scrape_xphone_global),
            ("scrape_saily_global",         lambda pg: scrape_saily_global(pg, usd_rate)),
            ("scrape_saily_regions",        lambda pg: scrape_saily_regions(pg, usd_rate)),
            ("scrape_esimio_destinations",  lambda pg: scrape_esimio_destinations(pg, usd_rate)),
            ("scrape_holafly_global",       lambda pg: scrape_holafly_global(pg, usd_rate)),
            ("scrape_holafly_regions",      lambda pg: scrape_holafly_regions(pg, usd_rate)),
        ]
        for name, fn in jobs:
            try:
                result = fn(page)
                if not result:
                    logger.warning(f"{name}: returned 0 plans — possible bot-block or selector change. Skipping.")
                else:
                    logger.info(f"{name}: {len(result)} global plans")
                    plans.extend(result)
            except Exception as e:
                logger.error(f"{name} failed: {e}", exc_info=True)
        browser.close()
    return plans


# ── Content Services Scraper ───────────────────────────────────────────────

CONTENT_SERVICES = [
    # ── eSIM שעון ──────────────────────────────────────────────────────────
    {"service": "eSIM שעון", "carrier": "cellcom",
     "url": "https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/smart_watch_esim/",
     "strategy": "cellcom_faq_esim", "free_trial": "חודש חינם"},
    {"service": "eSIM שעון", "carrier": "partner",
     "url": "https://www.partner.co.il/u/esim",
     "strategy": "keyword_scan", "price_keyword": "14.90", "free_trial": "ללא תקופת חינם"},
    {"service": "eSIM שעון", "carrier": "hotmobile",
     "url": "https://hotmobile-sale.online/deals/esim-watch/",
     "strategy": "keyword_scan", "price_keyword": "15.90", "free_trial": "3 חודשים ללא עלות"},
    {"service": "eSIM שעון", "carrier": "pelephone",
     "url": "https://www.pelephone.co.il/ds/heb/eshop/campaigns/esim-watch/",
     "strategy": "keyword_scan", "price_keyword": "19.90", "free_trial": "חודשיים מתנה"},
    # ── סייבר ──────────────────────────────────────────────────────────────
    {"service": "סייבר", "carrier": "pelephone",
     "url": "https://www.pelephone.co.il/ds/heb/content-products/pelephonecyber/",
     "strategy": "keyword_scan", "price_keyword": "הגנת סייבר רישתית", "free_trial": "3 חודשים חינם"},
    {"service": "סייבר", "carrier": "hotmobile",
     "url": "https://campaign.hotmobile.co.il/cyber/",
     "strategy": "keyword_scan", "price_keyword": None, "free_trial": "חודש ראשון חינם"},
    {"service": "סייבר", "carrier": "partner",
     "url": "https://www.partner.co.il/u/cyberguard",
     "strategy": "keyword_scan", "price_keyword": "להצטרפות", "free_trial": "ללא תקופת חינם"},
    {"service": "סייבר", "carrier": "cellcom",
     "url": "https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/Safe_browsing/",
     "strategy": "keyword_scan", "price_keyword": "גלישה בטוחה בנייד", "free_trial": "ללא תקופת חינם"},
    # ── נורטון ─────────────────────────────────────────────────────────────
    {"service": "נורטון", "carrier": "pelephone",
     "url": "https://www.pelephone.co.il/ds/heb/content-products/pelephonecyber/",
     "strategy": "keyword_scan", "price_keyword": "חודש ראשון חינם", "free_trial": "חודש ראשון חינם"},
    {"service": "נורטון", "carrier": "hotmobile",
     "url": "https://www.hotmobile.co.il/Pages/Norton.aspx",
     "strategy": "keyword_scan", "price_keyword": "Norton", "free_trial": "50% הנחה ל-4 חודשים"},
    {"service": "נורטון", "carrier": "partner",
     "url": "https://www.partner.co.il/u/norton-cell",
     "strategy": "keyword_scan", "price_keyword": "החל מ", "free_trial": "ללא תקופת חינם",
     "note": "ל-3 רישיונות"},
    {"service": "נורטון", "carrier": "cellcom",
     "url": "https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/",
     "strategy": "cellcom_hub", "page_keyword": "נורטון מובייל", "free_trial": "ללא תקופת חינם"},
    {"service": "נורטון", "carrier": "wecom",
     "url": "https://we-com.co.il/norton360/",
     "strategy": "keyword_scan", "price_keyword": "7.90", "free_trial": "חודש ראשון מתנה"},
    # ── שיר בהמתנה ─────────────────────────────────────────────────────────
    {"service": "שיר בהמתנה", "carrier": "pelephone",
     "url": "https://www.pelephone.co.il/digitalsite/heb/content-products/songwaiting/lobby/",
     "strategy": "keyword_scan", "price_keyword": 'ואח"כ רק', "free_trial": 'חודש ראשון חינם | הורדת שיר: ₪2.90'},
    {"service": "שיר בהמתנה", "carrier": "hotmobile",
     "url": None, "strategy": "not_available", "free_trial": "—"},
    {"service": "שיר בהמתנה", "carrier": "partner",
     "url": "https://www.partner.co.il/n/funtone/main/home",
     "strategy": "html_scan", "price_keyword": "עלות השירות", "free_trial": 'חודש ראשון חינם | הורדת שיר: ₪5.90'},
    {"service": "שיר בהמתנה", "carrier": "cellcom",
     "url": "https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/",
     "strategy": "cellcom_hub", "page_keyword": "המתנה נעימה", "free_trial": "ללא תקופת חינם"},
    # ── תא קולי ────────────────────────────────────────────────────────────
    {"service": "תא קולי", "carrier": "pelephone",
     "url": "https://www.pelephone.co.il/ds/heb/support/support/voice-mail/",
     "strategy": "keyword_scan", "price_keyword": "כמה עולה השירות?",
     "faq_question": "כמה עולה השירות?", "free_trial": "ללא תקופת חינם"},
    {"service": "תא קולי", "carrier": "hotmobile",
     "url": None, "strategy": "not_available", "free_trial": "—"},
    {"service": "תא קולי", "carrier": "partner",
     "url": "https://www.partner.co.il/n/partnerdigital/voice_mail",
     "strategy": "keyword_scan", "price_keyword": "תא קולי", "free_trial": "ללא תקופת חינם"},
    {"service": "תא קולי", "carrier": "cellcom",
     "url": "https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/",
     "strategy": "cellcom_hub", "page_keyword": "תא קולי אישי", "free_trial": "ללא תקופת חינם"},
]


def _extract_content_price(text, keyword=None, lookback=50):
    """Extract price from text near an optional keyword."""
    search = text
    if keyword:
        idx = text.find(keyword)
        if idx == -1:
            return None
        search = text[max(0, idx - lookback):idx + 700]
    patterns = [
        r'רק\s+(\d+\.?\d*)',
        r'₪\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*₪',
        r'(\d+\.?\d*)\s*ש["\u05f4]ח',
        r'(\d+\.?\d*)\s*שח',
        r'החל מ-(\d+\.?\d*)',
        r'ב-\s*(\d+\.?\d*)\s*₪',
        r'ב-\s*(\d+\.?\d*)\s*ש',
    ]
    for pat in patterns:
        m = re.search(pat, search)
        if m:
            val = float(m.group(1))
            if 1 <= val <= 500:          # sanity check: ₪1–₪500
                return f"₪{m.group(1)}"
    return None


def _cellcom_hub_price(page, page_keyword):
    """Extract price from Cellcom hub page by finding product section and clicking its FAQ."""
    try:
        for pct in [0.2, 0.4, 0.6, 0.8, 1.0]:
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
            page.wait_for_timeout(400)
        page.evaluate(f"""
            () => {{
                const allEls = Array.from(document.querySelectorAll('*'));
                let container = null;
                for (const el of allEls) {{
                    const txt = (el.innerText || '').trim();
                    if (txt.includes('{page_keyword}') && txt.length < 200) {{
                        container = el; break;
                    }}
                }}
                if (!container) return false;
                const section = container.closest(
                    'section, article, div[class*="product"], div[class*="card"], div[class*="item"]'
                ) || container.parentElement;
                if (!section) return false;
                const questions = section.querySelectorAll(
                    '.FAQItemBlock__question, [class*="question"], [class*="faq"] button'
                );
                for (const q of questions) {{
                    const qt = (q.innerText || '').trim();
                    if (qt.includes('מה עלות') || qt.includes('עלות השירות')) {{
                        q.scrollIntoView(); q.click(); return true;
                    }}
                }}
                container.scrollIntoView(); container.click(); return true;
            }}
        """)
        page.wait_for_timeout(2000)
        answer = page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll('.FAQItemBlock__answer, [class*="answer"]'));
                for (const el of els) {
                    const txt = (el.innerText || '').trim();
                    if (txt.includes('₪')) return txt;
                }
                return null;
            }
        """)
        if answer:
            price = _extract_content_price(answer)
            if price:
                return price
        body = page.inner_text("body")
        return _extract_content_price(body, page_keyword, lookback=0)
    except Exception:
        return None


def scrape_all_content():
    """Scrape all content services (eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי).
    Returns list of dicts: {service, carrier, price, free_trial, note, status}
    """
    from datetime import datetime as _dt
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        for entry in CONTENT_SERVICES:
            service    = entry["service"]
            carrier    = entry["carrier"]
            free_trial = entry.get("free_trial", "—")
            note       = entry.get("note", "")

            def _result(price, status):
                return {"service": service, "carrier": carrier, "price": price,
                        "free_trial": free_trial, "note": note, "status": status}

            if entry["strategy"] == "not_available":
                results.append(_result("לא זמין", "לא זמין"))
                logger.info(f"Content {service}/{carrier}: לא זמין")
                continue

            url = entry["url"]
            try:
                page.goto(url, timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(2000)

                # ── Cellcom hub (נורטון / שיר בהמתנה / תא קולי) ──────────
                if entry["strategy"] == "cellcom_hub":
                    price = _cellcom_hub_price(page, entry["page_keyword"])
                    results.append(_result(price or "לא נמצא", "נמצא" if price else "לא נמצא"))

                # ── Cellcom FAQ (eSIM שעון) ───────────────────────────────
                elif entry["strategy"] == "cellcom_faq_esim":
                    for pct in [0.3, 0.6, 1.0]:
                        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
                        page.wait_for_timeout(500)
                    page.evaluate("""
                        () => {
                            const qs = document.querySelectorAll('.FAQItemBlock__question');
                            for (const q of qs) {
                                if ((q.innerText || '').includes('מה עלות השירות')) {
                                    q.scrollIntoView(); q.click(); return true;
                                }
                            }
                        }
                    """)
                    page.wait_for_timeout(2500)
                    answer = page.evaluate("""
                        () => {
                            const as = document.querySelectorAll('.FAQItemBlock__answer');
                            for (const a of as) {
                                const t = (a.innerText || '').trim();
                                if (t.includes('₪')) return t;
                            }
                            return null;
                        }
                    """)
                    price = _extract_content_price(answer) if answer else None
                    results.append(_result(price or "לא נמצא", "נמצא" if price else "לא נמצא"))

                # ── HTML scan for Angular/React SPAs (Partner Funtone) ────
                elif entry["strategy"] == "html_scan":
                    page.wait_for_timeout(7000)
                    html = page.evaluate("() => document.documentElement.innerHTML")
                    stripped = re.sub(r'<[^>]+>', ' ', html)
                    stripped = re.sub(r'\s+', ' ', stripped)
                    price = _extract_content_price(stripped, entry.get("price_keyword"))
                    results.append(_result(price or "לא נמצא", "נמצא" if price else "לא נמצא"))

                # ── keyword_scan (default) ────────────────────────────────
                else:
                    faq_q = entry.get("faq_question")
                    if faq_q:
                        page.evaluate(f"""
                            () => {{
                                const all = Array.from(document.querySelectorAll('*'));
                                const q = all.find(el => {{
                                    const t = (el.innerText || '').trim();
                                    return t === '{faq_q}' && el.children.length === 0;
                                }});
                                if (q) {{ q.scrollIntoView(); q.click(); }}
                            }}
                        """)
                        page.wait_for_timeout(2000)
                    body  = page.inner_text("body")
                    price = _extract_content_price(body, entry.get("price_keyword"))
                    results.append(_result(price or "לא נמצא", "נמצא" if price else "לא נמצא"))

                logger.info(f"Content {service}/{carrier}: {results[-1]['price']}")
            except Exception as e:
                logger.error(f"Content scrape failed {service}/{carrier}: {e}")
                results.append(_result("שגיאה", "שגיאה"))

        browser.close()

    logger.info(f"scrape_all_content: {len(results)} results")
    return results


def scrape_all_abroad():
    """Scrape abroad packages from all 5 carriers. Returns flat list of plan dicts."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        plans = []
        for fn in [scrape_partner_abroad, scrape_pelephone_abroad,
                   scrape_hotmobile_abroad, scrape_cellcom_abroad, scrape_wecom_abroad,
                   scrape_xphone_abroad, scrape_019_abroad]:
            try:
                result = fn(page)
                if not result:
                    logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping.")
                else:
                    logger.info(f"{fn.__name__}: {len(result)} abroad plans")
                    plans.extend(result)
            except Exception as e:
                logger.error(f"{fn.__name__} failed: {e}", exc_info=True)
        browser.close()
    return plans
