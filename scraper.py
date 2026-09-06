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
import os
import json as _json
import urllib.request
import asyncio
from datetime import datetime, timezone
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module

logger = logging.getLogger(__name__)


def _ensure_event_loop():
    """Ensure an asyncio event loop exists for the current thread.
    Required by Playwright when called from Flask request handlers or APScheduler threads."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _run_parallel_scraper(name, fn):
    """Thread worker for scrape_all_global: ensure asyncio loop, run fn(), return (name, results).
    fn must be a zero-argument callable that returns a list of plan dicts."""
    _ensure_event_loop()
    try:
        result = fn()
        if not result:
            logger.warning(
                f"{name}: returned 0 plans — possible bot-block or selector change. Skipping."
            )
            return name, []
        logger.info(f"{name}: {len(result)} global plans")
        return name, result
    except Exception as e:
        logger.error(f"{name} failed: {e}", exc_info=True)
        return name, []


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


_WECOM_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# We-Com markets its "גלישה חופשית" plans as unlimited, but every plan carries a
# fair-use GB cap in its terms PDF. The capped plan (wecomBasic) prints "150GB
# גלישה בארץ" on the card; the unlimited-marketed plans (Family / Free 5G / Global 5G)
# print only "גלישה חופשית" on the card and bury a 10,000GB/month fair-use ceiling in
# the PDF. We store that ceiling so We-Com isn't dropped from the ₪/GB executive-summary
# chart (which filters `data_gb > 0`). Competitor "unlimited" plans are likewise stored
# at their fair-use cap (Pelephone 4000GB, Hot Mobile 3000GB, …).
# Verified June 2026 against wecomBasic-V3 / wecomFREE-Family-V3 / wecomFree-5G-Up-V2 /
# wecomGlobal-5G-V2 terms PDFs.
_WECOM_FAIR_USE_GB = 10000

# Canonical landing page for the wefly roaming call-rates ("מחירון שיחות והודעות בחו\"ל").
# Used as the link target when surfacing the "פרטי החבילה" popup (and as a fallback if the
# popup markup ever stops carrying its own href).
_WECOM_OVERSEAS_RATES_URL = "https://we-com.co.il/price-list-for-overseas-customers/"


def _wecom_fetch_html(url):
    """Fetch a We-Com page over plain HTTP with a browser UA.

    The 2026-07 site redesign renders all plan cards server-side as
    <article class="tier-card"> blocks (custom "wecom-theme"), so the wecom
    scrapers no longer need Playwright at all.
    """
    import requests
    r = requests.get(url, headers={"User-Agent": _WECOM_UA}, timeout=30)
    r.raise_for_status()
    return r.text


def _wecom_text_lines(chunk):
    """HTML chunk -> clean, whitespace-normalized text lines."""
    txt = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', chunk)
    txt = re.sub(r'(?i)<br\s*/?>', '\n', txt)
    txt = re.sub(r'(?s)<[^>]+>', '\n', txt)
    txt = _html_unescape(txt)
    lines = []
    for raw in txt.split('\n'):
        ln = re.sub(r'[\s ]+', ' ', raw).strip()
        if ln:
            lines.append(ln)
    return lines


def _wecom_tier_cards(page_html):
    """Split page HTML into its <article class="tier-card"> blocks (2026-07 design)."""
    return [chunk.split('</article>')[0]
            for chunk in re.split(r'<article class="tier-card[^"]*">', page_html)[1:]]


def _wecom_card_name(card_html):
    """The card's display name = first line of the tier-card__sub-headline element."""
    m = re.search(r'class="tier-card__sub-headline">(.*?)</p>', card_html, re.S)
    if not m:
        return None
    lines = _wecom_text_lines(m.group(1))
    return lines[0] if lines else None


def _wecom_card_price(card_html):
    """Parse the tier-card__price-plain element ("29.90 ₪ לחודש" / "₪499")."""
    m = re.search(r'class="tier-card__price-plain">(.*?)</p>', card_html, re.S)
    if not m:
        return None
    pm = re.search(r'(\d+(?:\.\d+)?)', re.sub(r'(?s)<[^>]+>', ' ', m.group(1)))
    if not pm:
        return None
    v = float(pm.group(1))
    return int(v) if v == int(v) else v


# Card lines that are navigation/CTA noise, never plan facts.
_WECOM_CARD_NOISE = {
    'השארת פרטים', 'הצטרפות דרך נציג', 'הצטרפות אונליין', 'פרטי החבילה',
    'סגירה', 'לרכישה', 'לרשימת המדינות', 'לעיקרי התוכנית', 'למחירון',
    'בארץ:', 'בחו"ל:', 'בחו״ל:',
}


def _wecom_popup_info(page_html, popup_id):
    """Return a roaming card's "פרטי החבילה" popup as a "__info__|<lines>" extra.

    Since the 2026-07 redesign the popup bodies are inline in the page HTML
    (<div class="wecom-popup wecom-popup--plan" id="wecom-popup-N">), replacing
    the old JetEngine admin-ajax fetch. PlanCard renders the result as the
    in-card "תנאי התוכנית" modal (abroad has no url column, so this is the only
    terms affordance); the call-rates line becomes a clickable "label|url" link.
    """
    m = re.search(
        r'id="%s".*?class="wecom-popup__content">(.*?)</div>\s*</div>\s*</div>' % re.escape(popup_id),
        page_html, re.S)
    if not m:
        return None
    body = re.sub(r'(?s)<div class="popup-plan-title">.*?</div>', '', m.group(1))
    rate_url = _WECOM_OVERSEAS_RATES_URL
    href = re.search(r'href="([^"]*price-list[^"]*)"', body)
    if href:
        rate_url = _html_unescape(href.group(1))
    lines, seen = [], set()
    for ln in _wecom_text_lines(body):
        if ln in seen:
            continue
        seen.add(ln)
        if ln.lower().startswith('wefly'):        # bare plan-name heading — the card already shows it
            continue
        if 'מחירון' in ln and ln.endswith(':'):  # the "...ללקוחות wecom בחו\"ל:" intro
            continue
        if 'מחירון' in ln:                       # call-rates label -> clickable link
            ln = ln + '|' + rate_url
        lines.append(ln)
    return ('__info__|' + '\n'.join(lines)) if lines else None


def _wecom_card_extras(front_lines, skip_name=None, cap=8):
    """Meaningful card-front lines only (skip CTAs, price fragments, bare numbers)."""
    extras, seen = [], set()
    for ln in front_lines:
        if (ln == skip_name or ln in _WECOM_CARD_NOISE or ln in seen or len(ln) <= 2
                or '₪' in ln or 'לחודש' in ln or re.match(r'^[\d.,]+$', ln)):
            continue
        seen.add(ln)
        extras.append(ln)
        if len(extras) >= cap:
            break
    return extras


def scrape_wecom(_page=None):
    """Scrape We-Com domestic plans (pure HTTP, 2026-07 tier-card design).

    The redesign renamed the rate card to Hebrew display names (חבילה משפחתית,
    חבילה בסיסית, גלישה חופשית 5G, חו״ל כלול 5G); the legacy wecom* product names
    survive only in the terms-PDF filenames (wecomFREE-Family-V3.pdf, ...), which
    we keep as the plan's url ("עיקרי התוכנית").
    """
    page_html = _wecom_fetch_html("https://we-com.co.il/cellular-packages/")
    plans = []
    for card in _wecom_tier_cards(page_html):
        name = _wecom_card_name(card)
        price = _wecom_card_price(card)
        if not name or price is None:
            continue

        pdf_m = re.search(r'href="([^"]+\.pdf)"', card)
        plan_url = _html_unescape(pdf_m.group(1)) if pdf_m else None

        # Card front only (headline + bullets + note) — the collapsible
        # "פרטי החבילה" section repeats the same facts in long form and the
        # terms PDF already carries the fine print.
        front_lines = _wecom_text_lines(card.split('<div class="tier-card__details')[0])
        front_text = '\n'.join(front_lines)

        # Domestic GB (see _WECOM_FAIR_USE_GB above for the data model):
        #  1) explicit cap on the card, e.g. "150GB גלישה בארץ בדור 4" — anchored on
        #     בארץ so a roaming figure ("5GB גלישה בחו״ל") is never grabbed;
        #  2) unlimited-marketed "גלישה חופשית" → fair-use ceiling;
        #  3) otherwise unknown.
        gb_m = re.search(r'(\d[\d,]*)\s*GB[^\n]*?בארץ', front_text)
        if gb_m:
            gb = int(gb_m.group(1).replace(',', ''))
        elif 'חופשית' in front_text:
            gb = _WECOM_FAIR_USE_GB
        else:
            gb = None

        minutes_m = re.search(r'([\d,]+)\s*דקות', front_text)
        minutes = int(minutes_m.group(1).replace(',', '')) if minutes_m else None

        plans.append({"carrier": "wecom", "plan_name": name, "price": price,
                      "data_gb": gb, "minutes": minutes,
                      "extras": _wecom_card_extras(front_lines, skip_name=name),
                      "url": plan_url})

    seen_names, deduped = set(), []
    for p in plans:
        if p["plan_name"] not in seen_names:
            seen_names.add(p["plan_name"]); deduped.append(p)
    return deduped


def scrape_wecom_abroad(_page=None):
    """Scrape We-Com abroad (wefly) packages (pure HTTP, 2026-07 tier-card design).

    The card headlines are now Hebrew ("70GB גלישה בחו\"ל") but the product brand
    is still wefly (popup titles + FAQ), so plan_name keeps the legacy
    wefly{N}GB[Family] keys — preserving price-history/change continuity.
    """
    page_html = _wecom_fetch_html("https://we-com.co.il/roaming/")
    plans = []
    for card in _wecom_tier_cards(page_html):
        headline = _wecom_card_name(card)
        if not headline or 'בחו' not in headline:
            continue
        gb_m = re.search(r'(\d+)\s*GB', headline)
        if not gb_m:
            continue
        gb = int(gb_m.group(1))
        name = "wefly%dGB%s" % (gb, "Family" if 'משפחתית' in headline else "")

        price = _wecom_card_price(card)
        # Card front = everything before the פרטי החבילה / לרשימת המדינות links row.
        front_lines = _wecom_text_lines(card.split('<div class="tier-card__links')[0])
        days = _parse_days('\n'.join(front_lines))
        extras = _wecom_card_extras(front_lines)

        pop_m = re.search(r'href="#(wecom-popup-\d+)"[^>]*>\s*פרטי החבילה', card)
        if pop_m:
            info = _wecom_popup_info(page_html, pop_m.group(1))
            if info:
                extras.append(info)

        plans.append({"carrier": "wecom", "plan_name": name, "price": price,
                      "days": days, "data_gb": gb, "minutes": None, "sms": None,
                      "extras": extras})

    seen_names, deduped = set(), []
    for p in plans:
        if p["plan_name"] not in seen_names:
            seen_names.add(p["plan_name"]); deduped.append(p)
    return deduped


def scrape_neptucom(_page=None):
    """Neptucom plans (neptucom.com) — eSIM-only carrier on Partner/Pelephone infrastructure.
    Static data (site uses PDF-based pricing; last verified April 2026).
    Group A: domestic + international included.
    Group B: domestic only.
    """
    H = "\u05d7\u05d5\"\u05dc"   # חו"ל
    G5 = "\u05ea\u05d5\u05de\u05da \u05d3\u05d5\u05e8 5"  # תומך דור 5 — Wave plans run on 5G infra
    _NEPTUCOM_PDF = "https://neptucom.com/wp-content/uploads/pdfn327/{}.pdf"
    plans = [
        # ── Group A: Domestic + International included ──────────────────
        {
            "carrier": "neptucom", "plan_name": "BreezeWave", "price": 39.0,
            "data_gb": 75, "minutes": "3000",
            "extras": [
                "3,000 SMS",
                f'12GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'50 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "SwellWave", "price": 49.0,
            "data_gb": 100, "minutes": "3000",
            "extras": [
                "3,000 SMS",
                f'5GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9 (60GB \u05dc\u05e9\u05e0\u05d4)',
                f'100 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'50 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05e9\u05e0\u05d4',
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "HighWave", "price": 69.0,
            "data_gb": 100, "minutes": "3000",
            "extras": [
                "3,000 SMS",
                f'32GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'150 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'100 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'100 SMS \u05d9\u05d5\u05e6\u05d0 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                "\u05de\u05e1\u05e4\u05e8 \u05d6\u05e8 \u05e0\u05d5\u05e1\u05e3 \u05dc\u05d1\u05d7\u05d9\u05e8\u05d4",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "ReefWave", "price": 99.0,
            "data_gb": 150, "minutes": "5000",
            "extras": [
                "5,000 SMS",
                f'64GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'200 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'500 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'150 SMS \u05d9\u05d5\u05e6\u05d0 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                "\u05de\u05e1\u05e4\u05e8 \u05d6\u05e8 \u05e0\u05d5\u05e1\u05e3 \u05dc\u05d1\u05d7\u05d9\u05e8\u05d4",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "PeakWave", "price": 129.0,
            "data_gb": 200, "minutes": "5000",
            "extras": [
                "5,000 SMS",
                f'120GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'250 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'1,000 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'250 SMS \u05d9\u05d5\u05e6\u05d0 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                "\u05de\u05e1\u05e4\u05e8 \u05d6\u05e8 \u05e0\u05d5\u05e1\u05e3 \u05dc\u05d1\u05d7\u05d9\u05e8\u05d4",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        # ── Group B: Domestic only ──────────────────────────────────────
        {
            "carrier": "neptucom", "plan_name": "HoodWave", "price": 27.0,
            "data_gb": 25, "minutes": "1000",
            "extras": [
                G5,
                "1,000 SMS",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 19.90 \u20aa",
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "LocalWave", "price": 33.0,
            "data_gb": 75, "minutes": "3000",
            "extras": [
                G5,
                "3,000 SMS",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 19.90 \u20aa",
            ],
        },
    ]
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    for p in plans:
        p.setdefault("scraped_at", ts)
        p.setdefault("url", _NEPTUCOM_PDF.format(p["plan_name"]))
    return plans


def _golan_num(s):
    """First number in a string as float, or None."""
    m = re.search(r'(\d+(?:\.\d+)?)', s or '')
    return float(m.group(1)) if m else None


def _golan_gb_from_text(s):
    """'300GB' -> 300.0 ; '0.5GB' -> 0.5 ; no GB -> None."""
    m = re.search(r'(\d+(?:\.\d+)?)\s*GB', s or '', re.I)
    return float(m.group(1)) if m else None


def _golan_gb_label(v):
    if v is None:
        return None
    return f"{int(v)}GB" if v == int(v) else f"{v}GB"


def _golan_period_to_days(text):
    """Parse the roaming price line: '299 ש"ח ל-30 יום' -> 30 ; 'ליום' -> 1 ; 'לשנה' -> 365."""
    if not text:
        return None
    if 'לשנה' in text:                 # לשנה
        return 365
    m = re.search(r'ל[\-\s]?(\d+)\s*יום', text)  # ל-NN יום
    if m:
        return int(m.group(1))
    if 'ליום' in text:                 # ליום
        return 1
    return None


# JS extractor for golantelecom.co.il/offers (domestic Mass-Market plans).
# Each .offer card carries data-gtm-price (exact price) and two benefit panels:
# .properties.israel (the "בישראל" tab) and .properties.roaming (the "בחול" tab).
# .important_info is the "פרטי המבצע" expandable bullet list.
_GOLAN_DOMESTIC_JS = r"""() => {
    const txt = el => (el ? (el.textContent||'').replace(/\s+/g,' ').trim() : '');
    // Only VISIBLE cards: the page keeps hidden/legacy .offer cards in the DOM (0x0,
    // offsetParent null, no `show-first` ancestor) — e.g. "זוגית" / a discontinued 550GB.
    const visible = c => c.offsetParent !== null && c.getBoundingClientRect().height > 0;
    return Array.from(document.querySelectorAll('.offer')).filter(visible).map(card => {
        const israel = card.querySelector('.properties.israel');
        const roaming = card.querySelector('.properties.roaming');
        const itemBy = (panel, label) => {
            if (!panel) return '';
            for (const it of panel.querySelectorAll('.item')) {
                if (txt(it.querySelector('.right')) === label)
                    return it.querySelector('.left img') ? '[check]' : txt(it.querySelector('.left'));
            }
            return '';
        };
        // בחול tab benefits — keep real items, drop the "תוקף מבצע" validity meta only
        const roamingItems = roaming ? Array.from(roaming.querySelectorAll('.item'))
            .filter(it => !it.classList.contains('sale_validity'))
            .map(it => ({
                right: txt(it.querySelector('.right')),
                left:  it.querySelector('.left img') ? '[check]' : txt(it.querySelector('.left')),
                all:   txt(it),
            }))
            .filter(it => it.all && !/^תוקף מבצע/.test(it.all)) : [];
        // פרטי המבצע — the .important_info bullet list
        const info = card.querySelector('.important_info');
        const importantInfo = info ? Array.from(info.querySelectorAll('li')).map(li => txt(li)).filter(Boolean) : [];
        const titleEl = card.querySelector('.upper h2.title .offer-content') || card.querySelector('.upper h2.title');
        const promoEl = Array.from(card.querySelectorAll('div,span,p')).find(e => {
            const t = e.textContent||''; return /חודש(?:ים|יים)\s*ראשונים/.test(t) && t.length < 120;
        });
        const pdf = card.querySelector('a[href*=".pdf"]');
        return {
            cls: card.className,
            gtmId: card.getAttribute('data-gtm-id'),
            gtmPrice: card.getAttribute('data-gtm-price'),
            gtmTitle: (card.getAttribute('data-gtm-title')||'').replace(/\s+/g,' ').trim(),
            titleText: txt(titleEl),
            promoText: txt(promoEl),
            gbText: itemBy(israel, 'גלישה'),
            callsText: itemBy(israel, 'שיחות'),
            intlMinutes: itemBy(israel, 'שיחות בינלאומיות'),
            subtitle: txt(card.querySelector('.upper .subtitle')),
            roamingItems, importantInfo,
            pdfHref: pdf ? pdf.href : '',
        };
    });
}"""

# JS extractor for golantelecom.co.il/overseas_offers (genuine roaming bundles).
# Each .offer card: .upper .title = "299 ש"ח ל-30 יום" (price + validity); .bottom .title =
# "50GB גלישה + 200 דקות"; two coloured .auto-fit-text lines = superlative (red) + bonus (grey);
# .pcrf-roaming-1 img = free apps; button.country_list[title] = full country list (HTML).
_GOLAN_OVERSEAS_JS = r"""() => {
    const txt = el => (el ? (el.textContent||'').replace(/\s+/g,' ').trim() : '');
    const decode = html => { const d = document.createElement('div'); d.innerHTML = html||''; return d; };
    const RED = ['rgb(237, 27, 47)', '#ed1b2f', 'rgb(237,27,47)'];
    const GRAY = ['rgb(104, 104, 117)', '#686875', 'rgb(104,104,117)'];
    // NB: unlike /offers we keep ALL .offer cards. The page features only 3 (30-day) plans;
    // the rest sit in d-none containers but are the real catalog behind "לכל חבילות חו\"ל"
    // (7/14-day, daily, yearly, מצרים וירדן). Dropping them would lose 9 genuine bundles.
    return Array.from(document.querySelectorAll('.offer')).map(card => {
        const autofit = Array.from(card.querySelectorAll('.bottom .auto-fit-text')).map(el => ({
            text: txt(el),
            color: (el.getAttribute('style')||'').match(/color:\s*([^;]+)/)?.[1]?.trim() || '',
        }));
        const superl = autofit.find(a => RED.includes(a.color))?.text || '';
        const bonus  = autofit.find(a => GRAY.includes(a.color))?.text || '';
        const apps = Array.from(card.querySelectorAll('.pcrf-roaming-1 img, [class*="pcrf"] img'))
            .map(i => (i.getAttribute('alt')||'').replace(/\s*Icon\s*$/i,'').trim()).filter(Boolean);
        let countries = [];
        const btn = card.querySelector('button.country_list, .country_list');
        if (btn) decode(btn.getAttribute('title')).querySelectorAll('.row-value').forEach(rv =>
            (rv.textContent||'').split(',').forEach(c => { const s=c.trim(); if(s) countries.push(s); }));
        // פרטי החבילה — services list (.important_info li, else its paragraph lines)
        const info = card.querySelector('.important_info');
        let services = [];
        if (info) {
            services = Array.from(info.querySelectorAll('li')).map(li => txt(li)).filter(Boolean);
            if (!services.length)
                services = (info.innerText||'').split('\n').map(s=>s.trim())
                    .filter(s => s && !/פרטי החבילה|השירותים הכלולים|לרכישה/.test(s));
        }
        return {
            cls: card.className,
            gtmId: card.getAttribute('data-gtm-id'),
            gtmPrice: card.getAttribute('data-gtm-price'),
            gtmTitle: (card.getAttribute('data-gtm-title')||'').replace(/\s+/g,' ').trim(),
            upperTitle: txt(card.querySelector('.upper .title')),
            mainTitle: txt(card.querySelector('.bottom > .title')),
            subtitle: txt(card.querySelector('.bottom > .subtitle')),
            superlative: superl, bonus, apps, countries, services,
        };
    });
}"""


def _build_golan_domestic(cards):
    """Turn raw .offer card dicts (from _GOLAN_DOMESTIC_JS) into domestic plan dicts.
    Merges the בישראל + בחול tabs and the פרטי המבצע bullets into extras; plans whose
    בחול tab includes browsing get a "NNGB גלישה בחול" extra so the UI shows the חול badge.
    """
    plans, seen = [], set()
    for c in cards:
        price = _golan_num(c.get('gtmPrice'))
        if price is None:
            continue
        title = c.get('titleText') or ''
        gtm = c.get('gtmTitle') or ''
        subtitle = c.get('subtitle') or ''

        # Headline label — DATA ONLY / זוגית / משפחתית / NNNGB (regex skips injected Adoric junk)
        m = re.search(r'(DATA ONLY|זוגית|משפחתית|\d+GB)', f"{title} {gtm}", re.I)
        label = m.group(1) if m else (gtm.split()[0] if gtm else 'חבילה')

        data_gb = _golan_gb_from_text(c.get('gbText'))
        if data_gb is None:
            data_gb = _golan_gb_from_text(subtitle)        # DATA ONLY -> "500GB דור 5"

        name = f"גולן {label}"
        if 'החו"ל כלול' in subtitle or 'החו״ל כלול' in subtitle:
            name += ' – חו"ל כלול'
        if name in seen:
            name += f" ({c.get('gtmId')})"
        seen.add(name)

        # minutes: check-mark = unlimited (None); explicit number (DATA ONLY "50 דקות") = limited
        minutes = None
        calls = c.get('callsText') or ''
        if calls and '[check]' not in calls and _golan_num(calls):
            minutes = int(_golan_num(calls))

        extras = []
        # 1) בחול tab benefits FIRST -> drives the חול badge + shows up top
        for it in c.get('roamingItems', []):
            right, left, allt = it.get('right', ''), it.get('left', ''), it.get('all', '')
            if left and left != '[check]' and right:
                line = f"{left} {right}"                    # "12GB גלישה בחול"
            elif left == '[check]' and right:
                line = right                                # "שיחות מחול לישראל"
            else:
                line = allt
            line = re.sub(r'\s+', ' ', line).strip()
            if line and line not in extras:
                extras.append(line)
        # 2) intl calling minutes (שיחות בינלאומיות)
        if c.get('intlMinutes') and _golan_num(c['intlMinutes']):
            extras.append(f"{int(_golan_num(c['intlMinutes']))} דקות לחו\"ל")
        # 3) פרטי המבצע bullets — drop redundant "גלישה בנפח NNNGB" / CTA noise / dup roaming
        have_intl_gb = any('גלישה בחו' in e for e in extras)
        for s in c.get('importantInfo', []):
            s = re.sub(r'\s+', ' ', s).strip().rstrip('*').strip()
            if not s or len(s) <= 2 or s == 'SMS':
                continue
            if re.match(r'^גלישה בנפח', s):
                continue
            if re.search(r'לתקנון|לחצו כאן|>>', s):
                continue
            if have_intl_gb and 'גלישה בחו' in s:
                continue
            if s not in extras:
                extras.append(s)
        # 4) descriptor (דור 5 / שירות תיקונים / 2 קווים) when it adds something new
        if subtitle and not re.search(r'דק[א-ת\']*\s*לחו|גלישה בחו|הנחה|החו"ל כלול', subtitle):
            if subtitle not in extras:
                extras.append(subtitle)
        full = list(dict.fromkeys(extras))
        extras = full[:7]

        # promo ("3 חודשים ראשונים ב-39 ש״ח" / "חודשיים ראשונים ב-49 ש״ח")
        promo_price = promo_months = None
        for raw in [c.get('promoText'), subtitle] + c.get('importantInfo', []):
            mm = re.search(r'(\d+)\s*חודשים\s*ראשונים\s*ב[\-\s]?(\d+(?:\.\d+)?)', raw or '')
            if mm:
                promo_months, promo_price = int(mm.group(1)), float(mm.group(2)); break
            mm = re.search(r'חודשיים\s*ראשונים\s*ב[\-\s]?(\d+(?:\.\d+)?)', raw or '')
            if mm:
                promo_months, promo_price = 2, float(mm.group(1)); break

        # planInfo popup ("תנאי התוכנית") — full benefit detail + a clickable link to the
        # official terms PDF. Stored as a filtered "__info__|" extra (hidden from bullets).
        pdf = c.get('pdfHref')
        info_lines = list(full)
        if pdf:
            info_lines.append(f'התקנון המלא (PDF)|{pdf}')
        if info_lines:
            extras = extras + ['__info__|' + '\n'.join(info_lines)]

        plans.append({
            'carrier': 'golan', 'plan_name': name, 'price': price,
            'data_gb': data_gb, 'minutes': minutes, 'extras': extras,
            'url': pdf or _GOLAN_OFFERS_URL,
            'promo_price': promo_price, 'promo_months': promo_months,
        })
    return plans


_GOLAN_GENERIC_SUPERL = re.compile(r'מושלמת|הכי|בגדול|בסטייל|לקצב')  # מושלמת/הכי/בגדול/בסטייל/לקצב


def _build_golan_abroad(cards):
    """Turn raw .offer card dicts (from _GOLAN_OVERSEAS_JS) into abroad plan dicts.
    extras[0] is the destination marker ('כלל העולם' for the ~126-country bundles, the
    region name for a country-specific bundle e.g. 'מצרים וירדן'); the per-package country
    list is rendered by getCountriesForAbroadPlan() in the React app.
    """
    plans, seen = [], set()
    for c in cards:
        price = _golan_num(c.get('gtmPrice'))
        if price is None:
            continue
        main = c.get('mainTitle') or c.get('gtmTitle') or ''
        data_gb = _golan_gb_from_text(main)
        mm = re.search(r'\+\s*(\d+)\s*דקות', main)
        minutes = int(mm.group(1)) if mm else None
        days = _golan_period_to_days(c.get('upperTitle') or '')
        countries = c.get('countries') or []
        superl = (c.get('superlative') or '').strip()
        is_world = len(countries) >= 40

        period = ('שנתי' if days == 365 else 'יומי' if days == 1
                  else f"{days} יום" if days else '')
        gbl = _golan_gb_label(data_gb) or ''
        # BiDi-safe name: GB / minutes / period each become a separate " – " segment, which
        # PlanCard wraps in its own <bdi>. Joining them in one string (e.g. "80GB + 300 דק'")
        # lets the Latin "GB" reorder the numbers visually ("300 + 80GB דק'").
        segs = [s for s in [gbl, (f"{minutes} דק'" if minutes else ''), period] if s]
        name = 'גולן חו"ל ' + (' – '.join(segs) if segs else (main or 'חבילה'))
        # destination marker (extras[0]) + name disambiguation for country-specific bundles
        dest = ('כלל העולם' if is_world else
                (superl if superl and not _GOLAN_GENERIC_SUPERL.search(superl) else ' ו'.join(countries)))
        if not is_world and dest and dest not in name:
            name += f" ({dest})"
        if name in seen:
            name += f" ({c.get('gtmId')})"
        seen.add(name)

        extras = [dest]
        if superl and superl != dest:
            extras.append(superl)                          # superlative (e.g. "הכי נמכרת")
        if c.get('bonus'):
            extras.append(c['bonus'])                      # "חבילה שנייה 20GB ..."
        has_apps = bool(c.get('apps'))
        if has_apps:
            extras.append('גלישה חופשית באפליקציות: ' + ' · '.join(c['apps']))
        for s in c.get('services', []):
            s = re.sub(r'\s+', ' ', s).strip().lstrip('•').strip().rstrip('*').strip()
            if not s or len(s) <= 2 or s.startswith('*'):
                continue
            if re.match(r'^\d+(?:\.\d+)?\s*GB גלישה', s):     # duplicates data_gb
                continue
            if re.search(r'תוקף החבילה', s):                    # duplicates days
                continue
            if re.search(r'לתקנון|לחצו כאן|>>', s):              # CTA noise
                continue
            if has_apps and 'גלישה חופשית באפליקציות' in s:
                continue
            if s not in extras:
                extras.append(s)
        full = list(dict.fromkeys([e for e in extras if e]))
        extras = full[:8]

        # planInfo popup ("תנאי התוכנית") — abroad_plans store no url column, so the terms
        # affordance is driven entirely by this "__info__|" extra (full detail + tariff link).
        info_lines = [e for e in full if e != dest]
        info_lines.append('תעריפון חו"ל (PDF)|https://golant.co/roaming_tariffs')
        extras = extras + ['__info__|' + '\n'.join(info_lines)]

        plans.append({
            'carrier': 'golan', 'plan_name': name, 'price': price,
            'days': days, 'data_gb': data_gb, 'minutes': minutes, 'sms': None,
            'extras': extras,
            'url': f"{_GOLAN_OVERSEAS_URL.rsplit('/',1)[0]}/userGuide/step3?packageidChange={c.get('gtmId')}&process=roamingflights",
        })
    return plans


def _golan_open(page, url):
    """Navigate to a Golan offers page, dismiss popups, and expand every
    'פרטי המבצע' / 'פרטי החבילה' toggle so .important_info is in the DOM."""
    page.goto(url, timeout=40000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    _dismiss_popups(page)
    try:
        page.evaluate(r"""() => document.querySelectorAll('.info-text,[class*="info-text"],button,a,span')
            .forEach(e => { const t=(e.textContent||'').trim();
                if (t==='פרטי המבצע' || t==='פרטי החבילה') { try{e.click()}catch(x){} } })""")
        page.wait_for_timeout(900)
    except Exception:
        pass


_GOLAN_OFFERS_URL = "https://www.golantelecom.co.il/offers"
_GOLAN_OVERSEAS_URL = "https://www.golantelecom.co.il/overseas_offers"
_GOLAN_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def scrape_golan(_page=None):
    """Scrape Golan Telecom domestic plans from golantelecom.co.il/offers.
    DOM-based: each .offer card carries data-gtm-price plus structured בישראל / בחול
    benefit panels and a פרטי המבצע bullet list — see _GOLAN_DOMESTIC_JS / _build_golan_domestic.
    """
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_GOLAN_UA)
        try:
            _golan_open(page, _GOLAN_OFFERS_URL)
            plans = _build_golan_domestic(page.evaluate(_GOLAN_DOMESTIC_JS))
            if not plans:
                logger.warning("scrape_golan: 0 plans extracted from golantelecom.co.il/offers")
            return plans
        finally:
            browser.close()


def scrape_golan_abroad(_page=None):
    """Scrape Golan Telecom roaming bundles from golantelecom.co.il/overseas_offers.
    These are genuine overseas packages (e.g. 6GB+100דק' for 14 days, ~126 countries),
    NOT the domestic line-up — stored as abroad_plans so they populate the חול tab with
    real prices, validity, included countries and superlatives. See _build_golan_abroad.
    """
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_GOLAN_UA)
        try:
            _golan_open(page, _GOLAN_OVERSEAS_URL)
            plans = _build_golan_abroad(page.evaluate(_GOLAN_OVERSEAS_JS))
            if not plans:
                logger.warning("scrape_golan_abroad: 0 plans from golantelecom.co.il/overseas_offers")
            return plans
        finally:
            browser.close()


def _parse_rami_levy_body(body_text):
    BLOCK_END = "למידע נוסף"
    SKIP_DETAIL = {'להצטרפות'}

    lines = [l.strip() for l in body_text.split('\n')]
    blocks, cur = [], []
    for l in lines:
        if l == BLOCK_END:
            blocks.append(cur)
            cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)

    plans = []
    for block in blocks:
        non_empty = [l for l in block if l]
        try:
            shekel_idx = next(i for i, l in enumerate(non_empty) if l == '₪')
        except StopIteration:
            continue
        if shekel_idx < 2:
            continue

        price_str = non_empty[shekel_idx - 1]
        plan_name = non_empty[shekel_idx - 2]

        try:
            price = float(price_str.replace(',', ''))
        except ValueError:
            continue

        # Skip header nav items (block 0 has nav text before the first plan)
        if plan_name in {'דלג לתוכן', 'רמי לוי באינטרנט', 'תוכניות', 'סניפים', 'הפעלת סים', 'האזור האישי'}:
            continue

        details_start = shekel_idx + 2  # skip ₪ and לחודש
        detail_lines = non_empty[details_start:]
        extras = [l for l in detail_lines if l not in SKIP_DETAIL]

        gb_val = None
        for l in non_empty:
            m = re.search(r'(\d+)GB', l)
            if m and 'גלישה' in l:
                gb_val = int(m.group(1))
                break

        minutes = None
        for l in non_empty:
            if 'דקות שיחה' in l and 'בתוך רשת' not in l and 'מחוץ לרשת' not in l:
                m = re.search(r'([\d,]+)', l)
                if m:
                    minutes = int(m.group(1).replace(',', ''))
                    break

        plans.append({
            'carrier': 'rami_levy',
            'plan_name': plan_name,
            'price': price,
            'data_gb': gb_val,
            'minutes': minutes,
            'extras': extras,
            'url': 'https://mobile.rami-levy.co.il/Home/Packages',
        })
    return plans


def _parse_rami_levy_abroad_body(body_text):
    BLOCK_END = "למידע נוסף"
    SKIP_DETAIL = {'רכישה'}
    WORLD = "\u05db\u05dc\u05dc \u05d4\u05e2\u05d5\u05dc\u05dd"  # כלל העולם

    lines = [l.strip() for l in body_text.split('\n')]
    blocks, cur = [], []
    for l in lines:
        if l == BLOCK_END:
            blocks.append(cur)
            cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)

    # First pass: extract parsed blocks, second pass: disambiguate names
    parsed = []
    for block in blocks:
        non_empty = [l for l in block if l]
        try:
            shekel_idx = next(i for i, l in enumerate(non_empty) if l == '₪')
        except StopIteration:
            continue
        if shekel_idx < 1:
            continue

        price_str = non_empty[shekel_idx - 1]
        try:
            price = float(price_str.replace(',', ''))
        except ValueError:
            continue

        # Line 2 before ₪ is either data highlight (e.g. "5GB") or plan name
        candidate = non_empty[shekel_idx - 2] if shekel_idx >= 2 else ''
        if re.fullmatch(r'\d+(?:\.\d+)?\s*(?:GB|MB)', candidate, re.I) and shekel_idx >= 3:
            plan_name = non_empty[shekel_idx - 3]
        else:
            plan_name = candidate

        if plan_name in {'דלג לתוכן', 'רמי לוי באינטרנט', 'תוכניות', 'סניפים',
                         'הפעלת סים', 'האזור האישי', 'Bon Voyage'}:
            continue

        details_start = shekel_idx + 1
        detail_lines = [l for l in non_empty[details_start:] if l not in SKIP_DETAIL]

        data_gb = None
        for l in detail_lines:
            m = re.search(r'(\d+(?:\.\d+)?)\s*GB', l, re.I)
            if m and 'גלישה' in l:
                data_gb = float(m.group(1))
                if data_gb == int(data_gb):
                    data_gb = int(data_gb)
                break
            m = re.search(r'(\d+)\s*MB', l, re.I)
            if m and 'גלישה' in l:
                data_gb = int(m.group(1)) / 1024
                break

        minutes = None
        for l in detail_lines:
            if 'דקות שיחה' in l:
                m = re.search(r'([\d,]+)', l)
                if m:
                    minutes = int(m.group(1).replace(',', ''))
                    break

        sms = None
        for l in detail_lines:
            if 'הודעות' in l or 'SMS' in l:
                m = re.search(r'([\d,]+)', l)
                if m:
                    sms = int(m.group(1).replace(',', ''))
                    break

        days = None
        for l in detail_lines:
            if 'תקף ליום אחד' in l or 'מתחדשת כל יום' in l:
                days = 1
                break
            m = re.search(r'תקף ל-(\d+)\s*ימים', l)
            if m:
                days = int(m.group(1))
                break

        parsed.append({
            'plan_name': plan_name,
            'price': price,
            'data_gb': data_gb,
            'minutes': minutes,
            'sms': sms,
            'days': days,
            'detail_lines': detail_lines,
        })

    # Disambiguate duplicate plan names: all instances get a suffix when duplicated
    from collections import Counter
    name_counter = Counter(p['plan_name'] for p in parsed)

    plans = []
    for p in parsed:
        name = p['plan_name']
        if name_counter[name] > 1:
            if p['minutes']:
                name = f"{name} \u2013 {p['minutes']} \u05d3\u05e7\u05f3"
            else:
                name = f"{name} \u2013 {int(p['price'])}\u20aa"
        plans.append({
            'carrier': 'rami_levy',
            'plan_name': name,
            'price': p['price'],
            'data_gb': p['data_gb'],
            'minutes': p['minutes'],
            'sms': p['sms'],
            'days': p['days'],
            'extras': [WORLD] + p['detail_lines'],
            'url': 'https://mobile.rami-levy.co.il/Home/aboard',
        })
    return plans


def _enrich_rami_levy_abroad_info(page, plans):
    """Attach each plan's "למידע נוסף" modal text as a `__info__|` extra — the per-plan
    terms popup PlanCard renders as the "תנאי התוכנית" button. Mirrors the domestic
    scrape_rami_levy enrichment. The roaming page renders every card twice (a visible
    card + a hidden responsive twin), so only the visible `a.more` is clickable; modal
    is matched back to its plan by PRICE, which is unique per plan."""
    # Modal chrome lines to drop: title, close glyphs, "סגור" button.
    _CHROME = {
        "מידע נוסף על התוכנית",  # מידע נוסף על התוכנית (modal title)
        "✕", "✖", "×", "X", "x",                                                                  # close glyphs
        "סגור",                                                                              # סגור
    }
    try:
        price_to_info = {}
        more = page.locator("a.more")
        for i in range(more.count()):
            link = more.nth(i)
            # Card price = the numeric line immediately before the ₪ line (same rule
            # the body parser uses). Hidden twins (offsetParent === null) return null.
            price = link.evaluate("""el => {
                if (el.offsetParent === null) return null;
                let p = el;
                for (let k=0;k<6 && p;k++){ p=p.parentElement; if (p && p.innerText && p.innerText.length>40) break; }
                const lines = (p ? p.innerText : '').split('\\n').map(s=>s.trim()).filter(Boolean);
                const idx = lines.indexOf('₪');
                if (idx > 0) { const v = parseFloat(lines[idx-1].replace(/,/g,'')); return isNaN(v)?null:v; }
                return null;
            }""")
            if price is None:
                continue
            try:
                link.scroll_into_view_if_needed(timeout=4000)
                page.wait_for_timeout(150)
                link.click(timeout=4000)
                page.wait_for_timeout(700)
                raw = page.evaluate("""() => {
                    const cands = document.querySelectorAll('.modal-body, .modal, [role="dialog"], [class*="modal" i]');
                    for (const m of cands){ if (m.offsetParent !== null && m.innerText && m.innerText.trim().length > 20) return m.innerText; }
                    return null;
                }""")
                if raw:
                    info = "\n".join(
                        l.strip() for l in raw.split("\n")
                        if l.strip() and l.strip() not in _CHROME
                    )
                    if info:
                        price_to_info[round(price, 2)] = info
                page.keyboard.press("Escape")
                page.wait_for_timeout(250)
            except Exception as exc:
                logger.warning(f"_enrich_rami_levy_abroad_info: modal capture failed @ {price}: {exc}")
        for pl in plans:
            pr = pl.get("price")
            info = price_to_info.get(round(pr, 2)) if pr is not None else None
            if info:
                pl["plan_info"] = info
                pl["extras"] = list(pl.get("extras", [])) + [f"__info__|{info}"]
    except Exception as exc:
        logger.warning(f"_enrich_rami_levy_abroad_info: skipped ({exc})")


def scrape_rami_levy_abroad(_page=None):
    """Scrape Rami Levy abroad plans. Single plan covers 145 countries."""
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_UA)
        try:
            page.goto(
                "https://mobile.rami-levy.co.il/Home/aboard",
                timeout=40000,
                wait_until="domcontentloaded"
            )
            page.wait_for_timeout(3000)
            _dismiss_popups(page)
            body = page.inner_text("body")
            plans = _parse_rami_levy_abroad_body(body)
            _enrich_rami_levy_abroad_info(page, plans)
            return plans
        finally:
            browser.close()


def scrape_rami_levy(_page=None):
    """Scrape Rami Levy domestic plans + per-plan info modal text."""
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_UA, viewport={"width": 1280, "height": 800})
        try:
            page.goto(
                "https://mobile.rami-levy.co.il/Home/Packages",
                timeout=40000,
                wait_until="networkidle"
            )
            page.wait_for_timeout(3000)
            _dismiss_popups(page)
            body = page.inner_text("body")
            plans = _parse_rami_levy_body(body)

            # Click each "למידע נוסף" link and capture the modal text
            more_links = page.locator('a.more')
            total = more_links.count()
            for i in range(min(total, len(plans))):
                try:
                    link = more_links.nth(i)
                    link.scroll_into_view_if_needed()
                    page.wait_for_timeout(200)
                    link.click()
                    page.wait_for_timeout(700)
                    info_text = page.evaluate("""() => {
                        const modals = document.querySelectorAll('.modal-body, .modal');
                        for (const m of modals) {
                            if (m.offsetParent !== null && m.innerText) return m.innerText;
                        }
                        return null;
                    }""")
                    if info_text:
                        # Strip trailing "סגור" button text
                        info_text = re.sub(r'\s*\u05e1\u05d2\u05d5\u05e8\s*$', '', info_text).strip()
                        plans[i]['plan_info'] = info_text
                        # Marker line preserved through extras/JSON round-trip
                        plans[i]['extras'] = list(plans[i].get('extras', [])) + [f"__info__|{info_text}"]
                    # Close modal
                    try:
                        page.keyboard.press('Escape')
                        page.wait_for_timeout(300)
                    except Exception:
                        pass
                except Exception as exc:
                    logger.warning(f"scrape_rami_levy: failed to capture info for plan {i}: {exc}")
            return plans
        finally:
            browser.close()


def scrape_all():
    """Scrape all carriers. Returns flat list of plan dicts."""
    _ensure_event_loop()
    plans = []

    # Phase 1: scrapers that open their own sync_playwright session — must run OUTSIDE
    # any outer sync_playwright context to avoid nested asyncio event-loop conflict.
    for fn in [scrape_xphone, scrape_wecom, scrape_019, scrape_neptucom, scrape_golan, scrape_rami_levy]:
        try:
            result = fn()
            if not result:
                logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping to avoid false 'removed' alerts.")
            else:
                logger.info(f"{fn.__name__}: {len(result)} plans")
                plans.extend(result)
        except Exception as e:
            logger.error(f"{fn.__name__} failed: {e}", exc_info=True)

    # Phase 2: scrapers that share a single Playwright session
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        for fn in [scrape_partner, scrape_pelephone, scrape_hotmobile, scrape_cellcom]:
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

    # Fetch terms PDF URLs from Partner CMS API (in-page fetch to bypass CORS).
    # The CMS returns a node tree; every plan is a `transverseProductsPlan` node
    # whose `planTerms` property holds the canonical terms-PDF link. Walking the
    # tree (instead of a fragile name-prefix proximity search) means renamed
    # plans still resolve correctly — e.g. "Partner Ace 5G" → "Better Future 5G",
    # which kept the old partner-ace-5g.pdf filename.
    partner_urls = {}
    _PARTNER_PDF_RE = re.compile(r'https?://u\.partner\.co\.il/media/[a-z0-9]+/[^\s"\\]+\.pdf')

    def _collect_partner_terms(node):
        if isinstance(node, dict):
            if node.get('nodeTypeAlias') == 'transverseProductsPlan':
                props = node.get('properties') or {}
                pname = (props.get('planName') or node.get('name') or '').strip()
                terms = props.get('planTerms')
                url = None
                if isinstance(terms, str) and terms.strip():
                    try:
                        arr = _json.loads(terms)
                        if isinstance(arr, list) and arr:
                            url = arr[0].get('url') or arr[0].get('link')
                    except Exception:
                        m = _PARTNER_PDF_RE.search(terms)
                        url = m.group(0) if m else None
                if pname and url:
                    partner_urls[pname] = url
            for v in node.values():
                _collect_partner_terms(v)
        elif isinstance(node, list):
            for v in node:
                _collect_partner_terms(v)

    try:
        raw = page.evaluate("""async () => {
            const r = await fetch(
                'https://u.partner.co.il/umbraco/api/CmsApi/GetPageContent/?pageid=91228&lang=he'
            );
            return r.text();
        }""")
        _collect_partner_terms(_json.loads(raw))
    except Exception as exc:
        logger.warning(f"scrape_partner: failed to fetch terms URLs: {exc}")

    plans = []
    for card in page.query_selector_all(".plan-wrapper"):
        name_el  = card.query_selector("h3.title")
        price_el = card.query_selector(".plan-banner .price")
        gb_el    = card.query_selector(".plan-banner .size")
        extras   = list(dict.fromkeys(el.inner_text().strip() for el in card.query_selector_all(".plan-advantages p") if el.inner_text().strip()))
        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        # Strip any "before-discount" / strikethrough descendants before parsing.
        # Partner occasionally renders a `<del>` or line-through-styled span next
        # to the actual price; _parse_price grabs the first numeric token and
        # would otherwise capture the regular price (e.g. 99.99) instead of the
        # promo price (34.9). One such false reading on 2026-04-01 produced a
        # spurious "99.99 → 34.9" change for Partner Prince.
        price = None
        if price_el:
            try:
                price_text = price_el.evaluate("""el => {
                    const clone = el.cloneNode(true);
                    clone.querySelectorAll(
                        'del, s, strike, .strike, .old-price, .price-old, .before-price, [style*="line-through"]'
                    ).forEach(n => n.remove());
                    return clone.innerText.trim();
                }""")
                price = _parse_price(price_text)
            except Exception:
                price = _parse_price(price_el.inner_text())
        gb    = _parse_gb(gb_el.inner_text())       if gb_el    else None
        # Match the storefront plan name to its terms PDF: exact name first,
        # then a tolerant prefix match for minor title/CMS discrepancies.
        plan_url = partner_urls.get(name)
        if not plan_url:
            for pname, url in partner_urls.items():
                if name.startswith(pname) or pname.startswith(name):
                    plan_url = url
                    break
        if name and name != "לא ידוע":
            plans.append({"carrier": "partner", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": None, "extras": extras, "url": plan_url})
    return plans


def scrape_pelephone(page):
    page.goto(
        "https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_selector(".border_5 .item", timeout=15000)

    # Extract pid→PDF map: each card has a popup link with a pid, and its more-info page has a PDF
    pelephone_urls = {}
    try:
        pid_map = page.evaluate("""() => {
            const result = {};
            document.querySelectorAll('.border_5 .item').forEach(card => {
                const nameEl = card.querySelector('.superlative');
                if (!nameEl) return;
                const name = nameEl.innerText.trim();
                // Find the popup link — href contains showPopupIframe with pid=NNN
                for (const a of card.querySelectorAll('a[href*="pid="]')) {
                    const m = a.href.match(/pid=([\\d]+)/);
                    if (m) { result[name] = m[1]; break; }
                }
            });
            return result;
        }""")
        # Fetch all more-info pages in parallel to get PDF URLs
        if pid_map:
            pdf_map = page.evaluate("""async (pidMap) => {
                const entries = Object.entries(pidMap);
                const fetches = entries.map(([name, pid]) =>
                    fetch('/ds/heb/packages/mobile-packages/join-pelephone-online/more-info/?pid=' + pid)
                        .then(r => r.text())
                        .then(html => {
                            const m = html.match(/https?:\\/\\/[^\\s"'<>]+\\.pdf/);
                            return [name, m ? m[0] : null];
                        })
                        .catch(() => [name, null])
                );
                return Object.fromEntries(await Promise.all(fetches));
            }""", pid_map)
            pelephone_urls = {k: v for k, v in pdf_map.items() if v}
    except Exception as exc:
        logger.warning(f"scrape_pelephone: failed to fetch terms URLs: {exc}")

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
                          "data_gb": gb, "minutes": None, "extras": extras,
                          "url": pelephone_urls.get(name)})
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
        # Extract PDF terms link from hidden input data-pdf attribute
        pdf_el = card.query_selector('input[data-pdf]')
        plan_url = None
        if pdf_el:
            pdf_path = pdf_el.get_attribute('data-pdf') or ''
            if pdf_path:
                plan_url = ('https://www.hotmobile.co.il' + pdf_path) if pdf_path.startswith('/') else pdf_path

        if name and name != "לא ידוע":
            plans.append({"carrier": "hotmobile", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": minutes, "extras": extras, "url": plan_url})
    return plans


def _cellcom_extract_terms_urls(data):
    """Walk Cellcom's Episerver Packages JSON → {plan_name: terms_url}.
    Per package: last featureLink (the visible 'לעיקרי התוכנית' anchor), falling back to
    the block-level programDetailsLink / termsLink — the 2026-06-11 lineup refresh
    (500GB/550GB/1500GB) shipped cards whose featureList had no link at all.
    """
    plan_urls = {}
    content_areas = (data.get("mainContentArea") or {}).get("expandedValue") or []
    for area in content_areas:
        tabs = (area.get("tabs") or {}).get("expandedValue") or []
        for tab in tabs:
            packages = (tab.get("salePackages") or {}).get("expandedValue") or []
            for pkg in packages:
                # Plan name: text before <br> ('title' is the populated field; 'packageTitle' is legacy)
                title_html = ((pkg.get("title") or {}).get("value")
                              or (pkg.get("packageTitle") or {}).get("value") or "")
                name = re.sub(r"<[^>]+>", " ", title_html.split("<br")[0]).strip()
                if not name:
                    continue
                feat_url = None
                for ef in ((pkg.get("extraFeatures") or {}).get("expandedValue") or []):
                    for feat in ((ef.get("featureList") or {}).get("expandedValue") or []):
                        link = (feat.get("featureLink") or {}).get("value")
                        if link:
                            feat_url = link
                if not feat_url:
                    for key in ("programDetailsLink", "termsLink"):
                        link = (pkg.get(key) or {}).get("value")
                        if link:
                            feat_url = link
                            break
                if feat_url:
                    if not feat_url.startswith("http"):
                        feat_url = "https://contentepi.cellcom.co.il" + feat_url
                    plan_urls[name] = feat_url
    return plan_urls


def _fetch_cellcom_terms_urls():
    """Fetch plan terms PDF URLs from Cellcom Episerver API (see _cellcom_extract_terms_urls)."""
    api_url = (
        "https://contentepi.cellcom.co.il/production/Private/Cellular/Packages/"
        "?expand=*&currentPageUrl=%2Fproduction%2FPrivate%2FCellular%2FPackages%2F"
    )
    try:
        # Without Accept: application/json Episerver serves the HTML page instead
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0",
                                                       "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode())
        return _cellcom_extract_terms_urls(data)
    except Exception as exc:
        logger.warning(f"_fetch_cellcom_terms_urls failed: {exc}")
        return {}


def scrape_cellcom(page):
    page.goto("https://cellcom.co.il/production/Private/Cellular/Packages/", timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(4000)
    # Fetch terms URLs via in-page fetch() (CORS allowed — same parent domain)
    cellcom_urls = {}
    try:
        raw = page.evaluate("""async () => {
            const r = await fetch(
                'https://contentepi.cellcom.co.il/production/Private/Cellular/Packages/' +
                '?expand=*&currentPageUrl=%2Fproduction%2FPrivate%2FCellular%2FPackages%2F',
                { headers: { 'Accept': 'application/json' } }
            );
            return r.text();
        }""")
        cellcom_urls = _cellcom_extract_terms_urls(_json.loads(raw))
    except Exception as exc:
        logger.warning(f"scrape_cellcom: failed to fetch terms URLs: {exc}")
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
        # Lineup-refresh cards (e.g. '500GB') carry the GB in the name with no second
        # title line — without this, data_gb=None renders as "ללא הגבלה". Require an
        # explicit GB suffix so '5G'/'4G Basic' never parse as a volume.
        if gb is None and not gb_text:
            gb_in_name = re.search(r"(\d+(?:\.\d+)?)\s*GB", name, re.IGNORECASE)
            if gb_in_name:
                gb = _parse_gb(gb_in_name.group(0))
        # Minutes: look for "דק' /SMS" feature line
        minutes = None
        for feat in extras:
            if "דק" in feat and "חו" not in feat:
                minutes = _parse_minutes(feat)
                break
        if name and name != "לא ידוע":
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": minutes, "extras": extras,
                          "url": cellcom_urls.get(name)})
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

                # Extract "טיוטת הסכם התקשרות" PDF link
                link_el = card.query_selector('a[href*=".pdf"]')
                plan_url = None
                if link_el:
                    href = link_el.get_attribute('href') or ''
                    plan_url = ('https://019mobile.co.il' + href) if href.startswith('/') else href or None

                if name and name != "לא ידוע":
                    plans.append({"carrier": "mobile019", "plan_name": name, "price": price,
                                  "data_gb": gb, "minutes": None, "extras": extras, "url": plan_url})
            return plans
        finally:
            browser.close()


# ── Abroad / Roaming scrapers ──────────────────────────────────────────────

# Pelephone roaming terms: each card's "מידע נוסף" modal (more-info/?socId=<id>) embeds the
# plan-specific "לתנאי החבילה והתוכנית" link (class icn_pack) → /abroad/terms/<slug>/ page.
# This regex pulls that exact URL — anchored on the "לתנאי" anchor text so it ignores the
# recurring nav/footer terms link that also appears on the page. Lets terms_url auto-populate
# for every present/future roaming plan (replaces the hardcoded PLAN_DETAILS_PDFS.pelephone map).
_PELE_ABROAD_TERMS_RE = re.compile(
    r'(https?://[^"\'\\<>\s]+/abroad/terms[^"\'\\<>\s]*)[^>]*?>\s*'
    "לתנאי"  # 'לתנאי' — start of "לתנאי החבילה והתוכנית"
)

# Manual corrections for auto-captured terms links. Pelephone clones a new plan's
# "מידע נוסף" page from an old plan's and sometimes leaves the old "לתנאי" link in
# place ABOVE the right one, so the first regex hit is wrong (מונדיאל 2026's page
# leads with חו"ל משפחתית's Family-Travel-Package link). Verified correct URL wins.
_PELE_ABROAD_TERMS_OVERRIDES = {
    "מונדיאל 2026": "https://www.pelephone.co.il/DigitalSite/heb/abroad/terms/mondial/",
}


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
    soc_map = {}   # plan name → socId (from each card's "מידע נוסף" link)
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
        # socId drives the per-plan terms link — resolved in one batch after the loop
        soc_id = None
        info_a = card.query_selector('a[href*="more-info/?socId="]')
        if info_a:
            m_soc = re.search(r'socId=(\d+)', info_a.get_attribute("href") or "")
            if m_soc:
                soc_id = m_soc.group(1)
        key = (name, days, price)
        if key in seen:
            continue
        seen.add(key)
        plans.append({"carrier": "pelephone", "plan_name": name, "price": price,
                      "days": days, "data_gb": gb, "minutes": minutes,
                      "sms": sms, "extras": extras, "_soc": soc_id})

    # ── Auto-capture terms_url (the "עיקרי התוכנית" link) per plan ───────────
    # Each plan's "מידע נוסף" modal embeds its "לתנאי החבילה והתוכנית" link. Fetch all
    # more-info pages in-page (reuses the browser session — anti-bot-safe) and map
    # socId→terms_url, so every present/future roaming plan resolves automatically.
    soc_ids = sorted({p["_soc"] for p in plans if p.get("_soc")})
    terms_by_soc = {}
    if soc_ids:
        try:
            raw = page.evaluate("""async (socIds) => {
                const out = {};
                await Promise.all(socIds.map(soc =>
                    fetch('/digitalsite/heb/abroad/more-info/?socId=' + soc + '&mode=open')
                        .then(r => r.text()).then(html => { out[soc] = html; })
                        .catch(() => { out[soc] = ''; })
                ));
                return out;
            }""", soc_ids)
            for soc, html in (raw or {}).items():
                # A more-info page can carry a leftover terms link from the plan it
                # was CMS-cloned from (e.g. מונדיאל 2026's page leads with חו"ל
                # משפחתית's link before its own). Log multi-link pages so clone
                # leftovers surface; overrides below pin the correct URL.
                found = list(dict.fromkeys(m.group(1) for m in _PELE_ABROAD_TERMS_RE.finditer(html or "")))
                if found:
                    terms_by_soc[str(soc)] = found[0]
                    if len(found) > 1:
                        logger.warning(f"scrape_pelephone_abroad: socId {soc} has {len(found)} distinct terms links {found} — possible CMS clone leftover, verify/override")
        except Exception as exc:
            logger.warning(f"scrape_pelephone_abroad: terms capture failed: {exc}")
    for p in plans:
        auto = terms_by_soc.get(str(p.pop("_soc", None)))
        p["terms_url"] = _PELE_ABROAD_TERMS_OVERRIDES.get(p["plan_name"], auto)
    return plans


# Cellcom package codes ("SOC"), e.g. FMWH998 / FMWH0047 / HUL4209. GetPackagePopular
# echoes back ONLY the SOCs the caller asks for, so a SOC we never learned about is a
# package whose terms PDF we can never fetch — hence the DOM discovery in
# scrape_cellcom_abroad.
_CELLCOM_SOC_RE = re.compile(r'\b(?:FMWH|HUL)\d{3,5}\b')

# A Cellcom terms PDF always lives under /globalassets/ on the contentepi CDN (that is
# exactly the shape of every `policiesEpi` value). Anchoring on it keeps the per-card DOM
# fallback from grabbing an unrelated PDF (a price list, a generic brochure) and linking
# the wrong document to a plan.
_CELLCOM_TERMS_HREF_RE = re.compile(r'/globalassets/[^\s"\'<>]+\.pdf', re.I)


def _cellcom_norm_title(name):
    """Cellcom's API `titleEpi` and the DOM card title are the same string typed twice —
       in practice they drift by NBSPs, doubled/trailing spaces, HTML entities and quote
       glyphs (״ vs "). Terms are matched by title, so normalise BOTH sides or a purely
       cosmetic difference silently costs a plan its 'עיקרי התוכנית' link."""
    s = _html_unescape(str(name or "")).replace("\u00a0", " ")
    for src_ch, dst_ch in (("\u05f4", '"'), ("\u201c", '"'), ("\u201d", '"'),
                           ("\u05f3", "'"), ("\u2018", "'"), ("\u2019", "'")):
        s = s.replace(src_ch, dst_ch)
    return re.sub(r"\s+", " ", s).strip()


def _cellcom_fetch_abroad_policies(soc_ids, block_id):
    """Return (by_title, by_soc) terms-PDF maps for one Cellcom abroad GetPackagePopular
       block. The PDF is each package's `policiesEpi` — the same doc the roaming card
       surfaces via 'חשוב לדעת' → 'לתנאי חבילה המלאים' — served from the contentepi CDN.
       Used to populate `terms_url` (the 'עיקרי התוכנית' link) on each plan. `by_soc` is
       the authoritative key (one package, one code); `by_title` covers plans scraped from
       the DOM, whose SOC the card may not expose."""
    import urllib.request, json as _json
    out, by_soc = {}, {}
    try:
        payload = _json.dumps({"SocIdList": soc_ids, "BlockId": block_id}).encode()
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
            name = _cellcom_norm_title(pkg.get("titleEpi"))
            pol  = pkg.get("policiesEpi")
            if not pol:
                continue
            url = pol if pol.startswith("http") else "https://contentepi.cellcom.co.il" + pol
            if name:
                out[name] = url
            soc = (pkg.get("socCode") or "").strip().upper()
            if soc:
                by_soc[soc] = url
    except Exception as e:
        logger.error(f"Cellcom abroad policies (block {block_id}) failed: {e}")
    return out, by_soc


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
                          "sms": sms, "extras": extras,
                          "_soc": (pkg.get("socCode") or "").strip().upper() or None})
    except Exception as e:
        logger.error(f"Cellcom abroad API failed: {e}")

    # ── Source 2: Silent Roamers page (DOM) ───────────────────────────────
    page_socs = set()
    try:
        page.goto("https://cellcom.co.il/AbroadMain/Silent_roamers-old/",
                  timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(2000)
        # Every SOC the page mentions — this is what makes terms capture automatic for a
        # package Cellcom publishes here without telling anyone (see the enrich step).
        try:
            page_socs = {m.group(0).upper() for m in _CELLCOM_SOC_RE.finditer(page.content() or "")}
        except Exception:
            page_socs = set()
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
            # Per-card terms discovery, in the card's OWN subtree only so a neighbour's
            # document can never be attributed to this plan: the package SOC (purchase
            # link / data attribute) and, if the "חשוב לדעת" panel is inline, its PDF.
            card_soc, card_pdf = None, None
            try:
                m = _CELLCOM_SOC_RE.search(card.evaluate("el => el.outerHTML") or "")
                if m:
                    card_soc = m.group(0).upper()
                for a in card.query_selector_all('a[href*=".pdf"]'):
                    href = a.get_attribute("href") or ""
                    if not _CELLCOM_TERMS_HREF_RE.search(href):
                        continue
                    card_pdf = href if href.startswith("http") else \
                        "https://contentepi.cellcom.co.il" + href
                    if "תנאי" in (a.inner_text() or ""):
                        break            # an explicit "לתנאי החבילה" anchor wins
            except Exception:
                pass
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": [],
                          "_soc": card_soc, "_dom_terms": card_pdf})
    except Exception as e:
        logger.error(f"Cellcom silent roamers scrape failed: {e}")

    # ── Enrich with terms PDFs (policiesEpi) — the "עיקרי התוכנית" link ────
    # The two known blocks: lobby (BlockId 20557, same SOC list as Source 1) + silent
    # roamers (BlockId 60988). These lists are CLOSED, but Source 2 is open-ended — it
    # ingests whatever cards Cellcom publishes — so a package outside them used to get
    # terms_url=None with nothing to fall back on but PlanCard's hardcoded map, which
    # nobody updates for a plan that launched this morning (that is how the holiday promo
    # "מושלמת לחגים" landed with an empty "עיקרי התוכנית", 2026-09). Anything the page
    # mentions but the lists don't know is therefore asked for by SOC below, so the terms
    # come from Cellcom's own API rather than from a list somebody has to remember to edit.
    SILENT_ROAMER_SOCS = ["FMWH990", "FMWH0065", "HUL4710", "FMWH627", "FMWH947", "FMWH946"]
    KNOWN_SOCS = SOC_IDS + SILENT_ROAMER_SOCS
    terms, terms_by_soc = {}, {}
    for socs, block in ((SOC_IDS, 20557), (SILENT_ROAMER_SOCS, 60988)):
        t, s = _cellcom_fetch_abroad_policies(socs, block)
        terms.update(t); terms_by_soc.update(s)

    new_socs = sorted(page_socs - {s.upper() for s in KNOWN_SOCS})
    for block in (60988, 20557):          # 2nd block only if the 1st returned nothing
        if not new_socs or all(s in terms_by_soc for s in new_socs):
            break
        t, s = _cellcom_fetch_abroad_policies(new_socs, block)
        # setdefault, not update: a page-wide regex can also pick up codes that aren't
        # consumer roaming packages, and those must never overwrite a title the two
        # authoritative blocks already resolved.
        for k, v in t.items():
            terms.setdefault(k, v)
        for k, v in s.items():
            terms_by_soc.setdefault(k, v)
    if new_socs:
        logger.info(f"scrape_cellcom_abroad: discovered {len(new_socs)} SOC(s) not in the "
                    f"known lists {new_socs} — resolved terms for "
                    f"{sum(1 for s in new_socs if s in terms_by_soc)}")

    for pl in plans:
        soc = pl.pop("_soc", None)
        dom_terms = pl.pop("_dom_terms", None)
        # SOC is the authoritative key (one package, one code); title covers DOM-scraped
        # cards that hide their SOC; the card's own PDF anchor is the last resort.
        pl["terms_url"] = (terms_by_soc.get(soc) if soc else None) \
            or terms.get(_cellcom_norm_title(pl["plan_name"])) \
            or dom_terms
        if not pl["terms_url"]:
            logger.warning(
                f"scrape_cellcom_abroad: no terms link for {pl['plan_name']!r} (soc={soc}) — "
                f"Cellcom published a package whose SOC and terms PDF the page never exposed; "
                f"run the plan-terms-coverage skill")

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

    # Terms PDFs from Partner's roaming CMS — mirrors scrape_partner's domestic walk.
    # Each roaming package node carries a `serviceTermsPdf` property holding the
    # canonical "תנאי השירות" PDF link. Walking the tree (pageid=75299) means a NEW
    # roaming plan gets its "עיקרי התוכנית" link AUTOMATICALLY on the next scrape — no
    # PLAN_DETAILS_PDFS edit needed. PlanCard prefers this scraped terms_url over the
    # hardcoded map (which stays as a fallback before the first re-scrape). Historically
    # Partner roaming had NO terms capture and relied entirely on the manual map, so a
    # new package (e.g. "חבילת המונדיאל", 2026-06) showed no terms until edited by hand.
    abroad_terms = {}
    _ABROAD_PDF_RE = re.compile(r'https?://u\.partner\.co\.il/media/[a-z0-9]+/[^\s"\\]+\.pdf')

    def _collect_abroad_terms(node):
        if isinstance(node, dict):
            props = node.get('properties') or {}
            pname = (props.get('planName') or props.get('packageName')
                     or node.get('name') or '').strip()
            terms = props.get('serviceTermsPdf')
            if pname and isinstance(terms, str) and terms.strip():
                m = _ABROAD_PDF_RE.search(terms)
                if m:
                    abroad_terms.setdefault(pname, m.group(0))
            for v in node.values():
                _collect_abroad_terms(v)
        elif isinstance(node, list):
            for v in node:
                _collect_abroad_terms(v)

    try:
        raw = page.evaluate("""async () => {
            const r = await fetch(
                'https://u.partner.co.il/umbraco/api/CmsApi/GetPageContent/?pageid=75299&lang=he'
            );
            return r.text();
        }""")
        _collect_abroad_terms(_json.loads(raw))
    except Exception as exc:
        logger.warning(f"scrape_partner_abroad: failed to fetch terms URLs: {exc}")

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
            # Match storefront name to its terms PDF: exact, then tolerant prefix.
            terms_url = abroad_terms.get(name)
            if not terms_url:
                for pname, url in abroad_terms.items():
                    if name.startswith(pname) or pname.startswith(name):
                        terms_url = url
                        break
            plans.append({"carrier": "partner", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": extras, "terms_url": terms_url})
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
        # Catalog id from the card's onclick handlers (Order/ShowMoreDetails/ShowCountries),
        # e.g. onclick="ShowMoreDetails('51011067');" → used below to open the details
        # modal and capture the "תנאי החבילה" PDF into terms_url.
        soc_id = None
        id_el = card.query_selector("a[onclick*='ShowMoreDetails'], a[onclick*='Order']")
        if id_el:
            m = re.search(r"'(\d+)'", id_el.get_attribute("onclick") or "")
            if m:
                soc_id = m.group(1)
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
                          "sms": None, "extras": extras, "_socid": soc_id})

    # ── Enrich with the per-plan "תנאי החבילה" terms PDF — the "עיקרי התוכנית" link ──
    # Each roaming card's "לפרטים נוספים" opens a modal (ShowMoreDetails('<socId>'))
    # containing a "תנאי החבילה" link → https://www.hotmobile.co.il/media/<slug>/<socId>.pdf.
    # The <slug> is a random per-upload path that changes on re-upload, so we re-capture
    # it every run rather than hardcoding. A miss leaves terms_url=None and PlanCard
    # falls back to its hardcoded PLAN_DETAILS_PDFS map.
    for pl in plans:
        pl["terms_url"] = None
        soc_id = pl.pop("_socid", None)
        if not soc_id:
            continue
        try:
            page.evaluate(f"ShowMoreDetails('{soc_id}')")
            page.wait_for_timeout(1200)
            pl["terms_url"] = page.eval_on_selector_all(
                "a",
                """els => {
                    const hit = els.find(e => {
                        const h = (e.href || '').toLowerCase();
                        const t = (e.innerText || '').replace(/\\s+/g, '');
                        return h.includes('.pdf') && h.includes('/media/') && t.includes('תנאיהחבילה');
                    });
                    return hit ? hit.href : null;
                }""",
            )
        except Exception as e:
            logger.warning(f"scrape_hotmobile_abroad: terms PDF for {pl['plan_name']!r} failed: {e}")
        finally:
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
            except Exception:
                pass
    return plans


# Site-wide VoLTE notice 019 shows on its roaming lobby (the "שימו לב!" popup). It applies
# to every 019 חו"ל package, so it's appended to each plan's "עיקרי התוכנית" modal lines.
_MOBILE019_VOLTE_NOTE = (
    "שימו לב: ביעדים ארצות הברית, קנדה, סינגפור, טייוואן, אוסטריה ויפן תתאפשר קבלת "
    "והוצאת שיחות רק במכשיר התומך בשיחות בדור 4 (VoLTE). ללא מכשיר תומך VoLTE לא "
    "תתאפשר קבלה והוצאת שיחות למרות רכישת החבילה."
)


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
                info_lines = []          # full card text for the "עיקרי התוכנית" modal
                for li_el in blist_els:
                    text = re.sub(r"\s+", " ", li_el.inner_text()).strip()
                    if not text:
                        continue
                    info_lines.append(text)
                    if "למשך" in text and "ימים" in text:
                        days = _parse_days(text)
                    elif "דק" in text:
                        strong = li_el.query_selector("strong")
                        minutes = _parse_minutes(strong.inner_text() if strong else text)
                    else:
                        extras.append(text)
                if name and name != "לא ידוע":
                    # "עיקרי התוכנית" popup: 019 roaming has no terms PDF, so the card's own
                    # bullets + the site-wide VoLTE notice are reproduced in-app as a filtered
                    # "__info__|" extra (PlanCard renders it as a modal beside "לאתר הספק").
                    info_lines.append(_MOBILE019_VOLTE_NOTE)
                    extras = extras + ["__info__|" + "\n".join(info_lines)]
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


def _get_gbp_to_ils():
    """Fetch live GBP\u2192ILS exchange rate. Returns float (fallback: 4.8)."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/GBP", timeout=8
        ) as r:
            data = _json.loads(r.read())
            rate = data["rates"]["ILS"]
            logger.info(f"GBP\u2192ILS rate: {rate}")
            return float(rate)
    except Exception as e:
        logger.warning(f"GBP rate fetch failed: {e}. Using 4.8")
        return 4.8


def _make_global_plan(carrier, name, price_ils, currency, original_price,
                      data_gb, days, minutes=None, sms=None, esim=True, extras=None):
    # Scraped titles/JSON may carry HTML entities (&amp; \u2192 &) \u2014 unescape before any formatting
    name = _html_unescape(name)
    if extras:
        extras = [_html_unescape(e) if isinstance(e, str) else e for e in extras]
        # Canonicalize extras[0] (destination) at CREATION, mirroring the DB
        # write path: change detection compares raw scraped extras against the
        # _norm_extras-stored row, so a non-canonical dest here flapped
        # extras_change on every scrape (~1,300 phantom changes/day across 20
        # providers as of 2026-07-14). plan_name is deliberately untouched.
        from db import _norm_extras
        extras = _norm_extras(extras)
    # Insert RLM (\u200f) before digits after separators to fix BiDi rendering in RTL tables
    import re as _re
    name = _re.sub(r'( [\u2013-] )(\d)', lambda m: m.group(1) + '\u200f' + m.group(2), name)
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


AIRALO_SLUG_TO_HEBREW = {
    "afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria": "\u05d0\u05dc\u05d2\u0027\u05d9\u05e8\u05d9\u05d4",
    "andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "antigua-and-barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4\u0020\u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2\u0027\u05df",
    "azores": "\u05d4\u05d0\u05d9\u05d9\u05dd\u0020\u05d4\u05d0\u05d6\u05d5\u05e8\u05d9\u05d9\u05dd",
    "bahamas": "\u05d0\u05d9\u05d9\u0020\u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "belize": "\u05d1\u05dc\u05d9\u05d6",
    "benin": "\u05d1\u05e0\u05d9\u05df",
    "bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bhutan": "\u05d1\u05d4\u05d5\u05d8\u05df",
    "bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "bonaire": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4\u0020\u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands": "\u05d0\u05d9\u05d9\u0020\u05d4\u05d1\u05ea\u05d5\u05dc\u05d4\u0020\u0028\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4\u0029",
    "brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4\u0020\u05e4\u05d0\u05e1\u05d5",
    "cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada": "\u05e7\u05e0\u05d3\u05d4",
    "canary-islands": "\u05d0\u05d9\u05d9\u0020\u05e7\u05e0\u05e8\u05d9",
    "cape-verde": "\u05db\u05e3\u0020\u05d5\u05e8\u05d3\u05d4",
    "cayman-islands": "\u05d0\u05d9\u05d9\u0020\u05e7\u05d9\u05d9\u05de\u05df",
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4\u0020\u05d4\u05de\u05e8\u05db\u05d6\u002d\u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "chad": "\u05e6\u0027\u05d0\u05d3",
    "chile": "\u05e6\u0027\u05d9\u05dc\u05d4",
    "china": "\u05e1\u05d9\u05df",
    "colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4\u0020\u05e8\u05d9\u05e7\u05d4",
    "cote-divoire": "\u05d7\u05d5\u05e3\u0020\u05d4\u05e9\u05e0\u05d4\u05d1",
    "croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic": "\u05e6\u0027\u05db\u05d9\u05d4",
    "democratic-republic-of-the-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4\u0020\u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea\u0020\u05e9\u05dc\u0020\u05e7\u05d5\u05e0\u05d2\u05d5",
    "denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4\u0020\u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador": "\u05d0\u05dc\u0020\u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "faroe-islands": "\u05d0\u05d9\u05d9\u0020\u05e4\u05d0\u05e8\u05d5",
    "fiji": "\u05e4\u05d9\u05d2\u0027\u05d9",
    "finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france": "\u05e6\u05e8\u05e4\u05ea",
    "french-guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4\u0020\u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon": "\u05d2\u05d1\u05d5\u05df",
    "gambia": "\u05d2\u05de\u05d1\u05d9\u05d4",
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
    "guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4\u0020\u05d1\u05d9\u05e1\u05d0\u05d5",
    "guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2\u0020\u05e7\u05d5\u05e0\u05d2",
    "hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india": "\u05d4\u05d5\u05d3\u05d5",
    "indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man": "\u05d4\u05d0\u05d9\u0020\u05de\u05d0\u05df",
    "israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "jamaica": "\u05d2\u0027\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan": "\u05d9\u05e4\u05df",
    "jersey": "\u05d2\u0027\u05e8\u05d6\u05d9",
    "jordan": "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya": "\u05e7\u05e0\u05d9\u05d4",
    "kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos": "\u05dc\u05d0\u05d5\u05e1",
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "lebanon": "\u05dc\u05d1\u05e0\u05d5\u05df",
    "lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macao": "\u05de\u05e7\u05d0\u05d5",
    "madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "madeira": "\u05de\u05d3\u05d9\u05d9\u05e8\u05d4",
    "malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali": "\u05de\u05d0\u05dc\u05d9",
    "malta": "\u05de\u05dc\u05d8\u05d4",
    "marie-galante": "\u05de\u05d0\u05e8\u05d9\u002d\u05d2\u05d0\u05dc\u05d0\u05e0\u05d8",
    "martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "nepal": "\u05e0\u05e4\u05d0\u05dc",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "new-zealand": "\u05e0\u05d9\u05d5\u0020\u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d2\u0027\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "northern-cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df\u0020\u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palestine-state-of": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4\u0020\u05d2\u05d9\u05e0\u05d0\u05d4\u0020\u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "puerto-rico-us": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5\u0020\u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8",
    "congo": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saba": "\u05e1\u05d0\u05d1\u05d4",
    "saint-barthelemy": "\u05e1\u05df\u0020\u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8\u0020\u05e7\u05d9\u05d8\u05e1\u0020\u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8\u0020\u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martinfrench-part": "\u05e1\u05df\u0020\u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8\u0020\u05d5\u05d9\u05e0\u05e1\u05e0\u05d8\u0020\u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "saudi-arabia": "\u05e2\u05e8\u05d1\u0020\u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "scotland": "\u05e1\u05e7\u05d5\u05d8\u05dc\u05e0\u05d3",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "seychelles": "\u05d0\u05d9\u05d9\u0020\u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4\u0020\u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-eustatius": "\u05e1\u05d9\u05e0\u05d8\u0020\u05d0\u05d5\u05e1\u05d8\u05d8\u05d9\u05d5\u05e1",
    "sint-maartendutch-part": "\u05e1\u05d9\u05e0\u05d8\u0020\u05de\u05d0\u05e8\u05d8\u05df",
    "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd\u0020\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd\u0020\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "spain": "\u05e1\u05e4\u05e8\u05d3",
    "sri-lanka": "\u05e1\u05e8\u05d9\u0020\u05dc\u05e0\u05e7\u05d4",
    "suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "tajikistan": "\u05d8\u05d2\u0027\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "timor-leste": "\u05d8\u05d9\u05de\u05d5\u05e8\u0020\u05dc\u05e1\u05d8\u05d4",
    "togo": "\u05d8\u05d5\u05d2\u05d5",
    "tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3\u0020\u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-and-caicos-islands": "\u05d0\u05d9\u05d9\u0020\u05d8\u05d5\u05e8\u05e7\u05e1\u0020\u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3\u0020\u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea\u0020\u05d4\u05d1\u05e8\u05d9\u05ea",
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "vatican-city": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "virgin-islands": "\u05d0\u05d9\u05d9\u0020\u05d4\u05d1\u05ea\u05d5\u05dc\u05d4\u0020\u0028\u05d0\u05e8\u05d4\u0022\u05d1\u0029",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
    "zimbabwe": "\u05d6\u05d9\u05de\u05d1\u05d1\u05d5\u05d0\u05d4",
    "mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "sudan": "\u05e1\u05d5\u05d3\u05df",
    "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
}

AIRALO_REGION_TO_HEBREW = {
    "africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "africa-safari": "\u05e1\u05e4\u05d0\u05e8\u05d9 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "asia": "\u05d0\u05e1\u05d9\u05d4",
    "caribbean-islands": "\u05d0\u05d9\u05d9 \u05d4\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "eu-plus-uk": "\u05d4\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05d9\u05e8\u05d5\u05e4\u05d9 \u05d5\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "latin-america": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "middle-east-and-north-africa": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "north-america": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "oceania": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
}

def scrape_airalo_local(_page=None, usd_rate=None):
    """Scrape Airalo per-country local eSIM packages via REST API."""
    import urllib.request as _req
    import json as _json
    import time as _time
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/json",
        "x-client-version": "version2",
        "accept-language": "en",
    }
    all_plans = []
    for slug, country_heb in AIRALO_SLUG_TO_HEBREW.items():
        try:
            req = _req.Request(
                "https://www.airalo.com/api/v4/countries/{}".format(slug),
                headers=headers,
            )
            with _req.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
            packages = data.get("packages", [])
            for pkg in packages:
                try:
                    price_obj = pkg.get("price", {})
                    usd = float(price_obj.get("amount", 0))
                    if usd <= 0:
                        continue
                    price_ils = round(usd * usd_rate, 2)

                    if pkg.get("is_unlimited"):
                        gb = None
                        gb_label = "ללא הגבלה"  # ללא הגבלה
                    else:
                        mb = pkg.get("amount", 0)
                        gb = round(mb / 1024, 2) if mb else None
                        if gb is None:
                            continue
                        if gb >= 1:
                            gb_label = "{}GB".format(int(gb) if gb == int(gb) else gb)
                        else:
                            gb_label = "{}MB".format(round(gb * 1024))

                    days    = pkg.get("day")
                    minutes = pkg.get("voice")
                    sms     = pkg.get("text")

                    if not days:
                        continue

                    name = "{} – {} – {} ימים".format(
                        country_heb, gb_label, days
                    )
                    if minutes:
                        name += " – {} דקות".format(minutes)
                    if sms:
                        name += " – {} SMS".format(sms)

                    all_plans.append(_make_global_plan(
                        "airalo_local", name, price_ils, "USD", usd,
                        gb, days, minutes=minutes, sms=sms, esim=True,
                        extras=[country_heb],
                    ))
                except Exception as e:
                    logger.debug("Airalo local pkg parse error ({}): {}".format(slug, e))
                    continue
            _time.sleep(0.15)
        except Exception as e:
            logger.warning("Airalo local {} failed: {}".format(slug, e))
            continue

    logger.info("Airalo local: {} plans from {} countries".format(
        len(all_plans), len(AIRALO_SLUG_TO_HEBREW)
    ))
    return all_plans


def scrape_airalo_regional(_page=None, usd_rate=None):
    """Scrape Airalo regional eSIM packages (Africa, Asia, Europe, etc.) via REST API."""
    import urllib.request as _req
    import json as _json
    import time as _time
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/json",
        "x-client-version": "version2",
        "accept-language": "en",
    }
    all_plans = []
    try:
        req = _req.Request("https://www.airalo.com/api/v4/regions", headers=headers)
        with _req.urlopen(req, timeout=15) as resp:
            regions = _json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("Airalo regional: failed to fetch regions list: {}".format(e))
        return all_plans

    for region in regions:
        slug = region.get("slug", "")
        region_heb = AIRALO_REGION_TO_HEBREW.get(slug)
        if not region_heb:
            continue
        try:
            req2 = _req.Request(
                "https://www.airalo.com/api/v4/regions/{}".format(slug),
                headers=headers,
            )
            with _req.urlopen(req2, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
            packages = data.get("packages", [])
            seen = set()
            for pkg in packages:
                try:
                    price_obj = pkg.get("price", {})
                    usd = float(price_obj.get("amount", 0))
                    if usd <= 0:
                        continue
                    price_ils = round(usd * usd_rate, 2)

                    if pkg.get("is_unlimited"):
                        gb = None
                        gb_label = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"
                    else:
                        mb = pkg.get("amount", 0)
                        gb = round(mb / 1024, 2) if mb else None
                        if gb is None:
                            continue
                        if gb >= 1:
                            gb_label = "{}GB".format(int(gb) if gb == int(gb) else gb)
                        else:
                            gb_label = "{}MB".format(round(gb * 1024))

                    days    = pkg.get("day")
                    minutes = pkg.get("voice")
                    sms     = pkg.get("text")
                    if not days:
                        continue

                    dedup = (gb, days, minutes, sms)
                    if dedup in seen:
                        continue
                    seen.add(dedup)

                    name = "Airalo {} \u2013 {} \u2013 {} \u05d9\u05de\u05d9\u05dd".format(
                        region_heb, gb_label, days
                    )
                    if minutes:
                        name += " \u2013 {} \u05d3\u05e7\u05d5\u05ea".format(minutes)
                    if sms:
                        name += " \u2013 {} SMS".format(sms)

                    all_plans.append(_make_global_plan(
                        "airalo_regional", name, price_ils, "USD", usd,
                        gb, days, minutes=minutes, sms=sms, esim=True,
                        extras=[region_heb, "eSIM \u05d1\u05dc\u05d1\u05d3"],
                    ))
                except Exception as e:
                    logger.debug("Airalo regional pkg parse error ({}): {}".format(slug, e))
                    continue
            _time.sleep(0.2)
        except Exception as e:
            logger.warning("Airalo regional {} failed: {}".format(slug, e))
            continue

    logger.info("Airalo regional: {} plans from {} regions".format(
        len(all_plans), len(AIRALO_REGION_TO_HEBREW)
    ))
    return all_plans


def scrape_pelephone_globalsim(page):
    # domcontentloaded + explicit card wait: "networkidle" never settles on this
    # page (analytics long-polling) and timed out ~1 in 4 scheduled runs, which
    # silently aged the 8 GlobalSIM rows (missed both 2026-09-03 runs).
    page.goto(
        "https://www.pelephone.co.il/digitalsite/heb/abroad/global-sim/",
        timeout=40000, wait_until="domcontentloaded"
    )
    try:
        page.wait_for_selector(".packs > div[id^='p'] .pack_top .price", timeout=25000)
    except Exception:
        logger.warning("Pelephone GlobalSIM: plan cards did not render within 25s")
    page.wait_for_timeout(1500)
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


ESIMO_CODE_TO_HEBREW = {
    "AD": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "AE": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "AF": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "AG": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "AI": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "AL": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "AM": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "AN": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "AR": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "AT": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "AU": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "AW": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "AX": "\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3",
    "AZ": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "BA": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "BB": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "BD": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "BE": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "BF": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "BG": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "BH": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "BJ": "\u05d1\u05e0\u05d9\u05df",
    "BL": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "BM": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "BN": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "BO": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "BQ": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "BR": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "BS": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "BW": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "BY": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "BZ": "\u05d1\u05dc\u05d9\u05d6",
    "CA": "\u05e7\u05e0\u05d3\u05d4",
    "CD": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "CF": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "CG": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d1\u05e8\u05d6\u05d5\u05d5\u05d9\u05dc",  # Congo-Brazzaville \u2014 distinct from CD so plan names don't collide
    "CH": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "CL": "\u05e6'\u05d9\u05dc\u05d4",
    "CM": "\u05e7\u05de\u05e8\u05d5\u05df",
    "CN": "\u05e1\u05d9\u05df",
    "CO": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "CR": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "CU": "\u05e7\u05d5\u05d1\u05d4",
    "CV": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "CW": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "CY": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "CZ": "\u05e6'\u05db\u05d9\u05d4",
    "DE": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "DK": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "DM": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "DO": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "DZ": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "EC": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "EE": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "EG": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "ES": "\u05e1\u05e4\u05e8\u05d3",
    "ET": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "FI": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "FJ": "\u05e4\u05d9\u05d2'\u05d9",
    "FO": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "FR": "\u05e6\u05e8\u05e4\u05ea",
    "GA": "\u05d2\u05d0\u05d1\u05d5\u05df",
    "GB": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "GD": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "GE": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "GF": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "GG": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "GH": "\u05d2\u05d0\u05e0\u05d4",
    "GI": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "GL": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "GM": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "GN": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "GP": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "GR": "\u05d9\u05d5\u05d5\u05df",
    "GT": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "GU": "\u05d2\u05d5\u05d0\u05dd",
    "GW": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "GY": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "HK": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "HN": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "HR": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "HT": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "HU": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "IC": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05e7\u05e0\u05e8\u05d9\u05d9\u05dd",
    "ID": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "IE": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "IL": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "IM": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "IN": "\u05d4\u05d5\u05d3\u05d5",
    "IQ": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "IR": "\u05d0\u05d9\u05e8\u05d0\u05df",
    "IS": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "IT": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "JE": "\u05d2'\u05e8\u05d6\u05d9",
    "JM": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "JO": "\u05d9\u05e8\u05d3\u05df",
    "JP": "\u05d9\u05e4\u05df",
    "KE": "\u05e7\u05e0\u05d9\u05d4",
    "KG": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "KH": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "KN": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "KR": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "KW": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "KY": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "KZ": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "LA": "\u05dc\u05d0\u05d5\u05e1",
    "LB": "\u05dc\u05d1\u05e0\u05d5\u05df",
    "LC": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "LI": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "LK": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "LR": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "LS": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "LT": "\u05dc\u05d9\u05d8\u05d0",
    "LU": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "LV": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "LY": "\u05dc\u05d5\u05d1",
    "MA": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "MC": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "MD": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "ME": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "MF": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "MG": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "MK": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "ML": "\u05de\u05d0\u05dc\u05d9",
    "MN": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "MO": "\u05de\u05e7\u05d0\u05d5",
    "MQ": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "MR": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "MS": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "MT": "\u05de\u05dc\u05d8\u05d4",
    "MU": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "MV": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "MW": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "MX": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "MY": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "MZ": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "NA": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "NE": "\u05e0\u05d9\u05d2'\u05e8",
    "NG": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "NI": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "NL": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "NO": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "NP": "\u05e0\u05e4\u05d0\u05dc",
    "NR": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "NZ": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "OM": "\u05e2\u05d5\u05de\u05d0\u05df",
    "PA": "\u05e4\u05e0\u05de\u05d4",
    "PE": "\u05e4\u05e8\u05d5",
    "PG": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "PH": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "PK": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "PL": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "PR": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "PT": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "PY": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "QA": "\u05e7\u05d8\u05e8",
    "RE": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "RO": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "RS": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "RU": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "RW": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "SA": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "SC": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "SD": "\u05e1\u05d5\u05d3\u05df",
    "SE": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "SG": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "SI": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "SK": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "SL": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "SN": "\u05e1\u05e0\u05d2\u05dc",
    "SR": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "SS": "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "SV": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "SZ": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "TC": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "TD": "\u05e6'\u05d0\u05d3",
    "TG": "\u05d8\u05d5\u05d2\u05d5",
    "TH": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "TJ": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "TN": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "TO": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "TR": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "TT": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "TW": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "TZ": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "UA": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "UG": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "US": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "UY": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "UZ": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "VA": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "VC": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "VE": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "VG": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "VI": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",
    "VN": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "VU": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "WS": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "YT": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "ZA": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "ZM": "\u05d6\u05de\u05d1\u05d9\u05d4",
}

ESIMO_REGION_TO_HEBREW = {
    "Europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "Asia": "\u05d0\u05e1\u05d9\u05d4",
    "Africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "North America": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "Latin America": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "Middle East": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "Caribbean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "Balkans": "\u05d1\u05dc\u05e7\u05df",
    "Oceania": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "Global": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
}


_ESIMO_REGION_SLUGS = [
    "europe-only-data", "asia-only-data", "africa-only-data",
    "north-america-only-data", "latin-america-only-data", "middle-east-only-data",
    "caribbean-only-data", "balkans-only-data", "oceania-only-data",
    "global-esim-only-data",
]

_ESIMO_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _esimo_fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": _ESIMO_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _esimo_extract_packages(html, array_key="packages"):
    """Reconstruct the Next.js RSC flight stream and pull the embedded packages array.

    esimo.io is a Next.js app: plan data is server-rendered as escaped JSON split across
    multiple self.__next_f.push([1,"..."]) script chunks. The packages array frequently
    straddles a chunk boundary, so the chunks must be decoded and joined BEFORE searching —
    bracket-matching the raw HTML hits the </script><script> junk and corrupts the parse.
    array_key names the prop that holds the array — other Next.js RSC sites embed the
    same shape under a different key (esimgenius.ai uses "plans").
    """
    import json as _json
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    decoded = []
    for c in chunks:
        try:
            decoded.append(_json.loads('"' + c + '"'))
        except Exception:
            continue
    stream = "".join(decoded)
    idx = stream.find(f'"{array_key}":[')
    if idx < 0:
        return []
    start = stream.index('[', idx)
    depth, in_str, esc, end = 0, False, False, None
    for i in range(start, len(stream)):
        ch = stream[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return []
    try:
        return _json.loads(stream[start:end])
    except Exception:
        return []


def scrape_esimo_global(_page=None, usd_rate=None):
    """Scrape ALL eSIMo plans: ~200 country pages (sitemap) + 9 region pages + global.

    Pure HTTP, no Playwright — product pages are SSR'd so the packages JSON is in the
    initial HTML. The sitemap also lists city alias pages (e.g. new-york) that serve
    their country's packages; deduped by package id. Prices are USD (verified against
    /api/firebase-data startingPrice.USD). The destination Hebrew name comes from the
    package `code` field (ISO alpha2 / region name), never from the slug, so alias and
    stale pages cannot mislabel a plan.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    # Region/global products are not in the sitemap — fixed slugs + sitemap countries
    slugs = set(_ESIMO_REGION_SLUGS)
    try:
        sitemap = _esimo_fetch("https://esimo.io/sitemap.xml", timeout=30)
        slugs.update(re.findall(r"<loc>https://esimo\.io/product/([a-z0-9-]+)</loc>", sitemap))
    except Exception as exc:
        logger.warning(f"eSIMo sitemap fetch failed ({exc}) — scraping region/global pages only")

    def fetch_one(slug):
        return _esimo_extract_packages(_esimo_fetch(f"https://esimo.io/product/{slug}"))

    plans, seen_ids = [], set()
    empty, failed = 0, 0
    unknown_codes = set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): s for s in sorted(slugs)}
        for fut in as_completed(futures):
            slug = futures[fut]
            try:
                pkgs = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIMo {slug}: {exc}")
                continue
            if not pkgs:
                empty += 1  # stale sitemap entry — Next.js soft-404 has no packages
                continue
            for pkg in pkgs:
                pid = pkg.get("id") or f"{pkg.get('code')}|{pkg.get('data')}|{pkg.get('validity')}"
                if pid in seen_ids:
                    continue  # city alias page — country already captured
                code = pkg.get("code") or ""
                dest = ESIMO_CODE_TO_HEBREW.get(code) or ESIMO_REGION_TO_HEBREW.get(code)
                if not dest:
                    unknown_codes.add(code)
                    continue
                try:
                    gb = float(pkg.get("data", 0))
                    days = int(pkg.get("validity", 0))
                    usd = float(pkg.get("price", 0))
                except (TypeError, ValueError):
                    continue
                if gb <= 0 or days <= 0 or usd <= 0:
                    continue
                seen_ids.add(pid)
                price_ils = round(usd * usd_rate, 2)
                if gb >= 1:
                    gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
                else:
                    gb_str = f"{round(gb * 1024)}MB"
                plan_name = f"{dest} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                plans.append(_make_global_plan(
                    "esimo", plan_name, price_ils, "USD", usd,
                    gb, days, esim=True, extras=[dest]
                ))
    if unknown_codes:
        logger.warning(
            f"eSIMo: skipped unmapped destination codes {sorted(unknown_codes)} "
            f"— add them to ESIMO_CODE_TO_HEBREW"
        )
    logger.info(f"eSIMo global: {len(plans)} plans from {len(slugs)} pages ({empty} empty, {failed} failed)")
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


# ── SimTLV full eSIM catalog (simtlv.co.il/esim/) ─────────────────────────
# The WooCommerce Store API exposes the whole catalog (~2,400 products) with
# ILS prices. Country pages (/esim/<iso3>) render cards whose data-id equals
# the product id, and every LIVE product follows one of the strict naming
# conventions below; legacy/B2B products (Global Card zones, TopUps, app
# credits, physical SIMs, partner promos) don't match them and are skipped.
# Verified 2026-06-11 against the ita/grc/tha/usa pages: pattern set == page
# card set, no false positives.
#
# SIMTLV_DEST_FIX repairs regex artifacts only: the local pattern strips an
# optional 'ל' prefix ("eSIM לאיטליה" → "איטליה"), which also eats the first
# letter of countries that themselves start with ל ("eSIM לוקסמבורג" →
# "וקסמבורג"). Pure spelling fixes belong in db._DEST_NORM, not here.
SIMTLV_DEST_FIX = {
    "וקסמבורג": "לוקסמבורג",
    "טביה": "לטביה",
    "יטא": "ליטא",
    "יכטנשטיין": "ליכטנשטיין",
    "אוס": "לאוס",
    "סוטו": "לסוטו",
    "יבריה": "ליבריה",
    "רפובליקה הדומיניקנית": "הרפובליקה הדומיניקנית",
    "לרפובליקה הדומיניקנית": "הרפובליקה הדומיניקנית",  # double-ל typo on the site
    "דרום אמריקה ל-11 מדינות": "דרום אמריקה (11 מדינות)",
}

_SIMTLV_RX_UNLIMITED = re.compile(
    r"^eSIM ברשת Tmobile לארצות הברית ללא הגבלה (\d+) יום$"
)
_SIMTLV_RX_EUROPE = re.compile(
    r"^eSIM לאירופה(?: ל-(\d+)(?: מדינות)?)? (\d+(?:\.\d+)?)GB ל-?\s*(\d+) (?:יום|ימים)\s*[–-]\s*כרטיס סים וירטואלי$"
)
_SIMTLV_RX_EUROPE_YR = re.compile(
    r"^eSIM לאירופה ל-(\d+) מדינות (\d+(?:\.\d+)?)GB לשנה\s*[–-]\s*כרטיס סים וירטואלי$"
)
_SIMTLV_RX_GLOBAL_N = re.compile(
    r"^eSIM גלובלי ל-(\d+) מדינות (\d+(?:\.\d+)?)GB ל-?\s*(\d+) (?:יום|ימים)\s*[–-]\s*כרטיס סים וירטואלי$"
)
_SIMTLV_RX_EUR_PKG = re.compile(
    r"^(?:כרטיס|חבילת) eSIM אירופה: (\d+(?:\.\d+)?)GB (ל-\d+ ימים|לשנה|ל-\d+ שנים) ב-(\d+) מדינות$"
)
_SIMTLV_RX_GLOB_PKG = re.compile(
    r"^חבילת eSIM גלובלית: (\d+(?:\.\d+)?)GB (ל-\d+ ימים|לשנה|ל-\d+ שנים) ב-(\d+) מדינות$"
)
_SIMTLV_RX_LOCAL = re.compile(
    # (?i:esim) — the site mixes eSIM/Esim/esim casing on live products
    r"^(?i:esim) ל?(.+?) (\d+(?:\.\d+)?)GB ל-?\s*(\d+) (?:יום|ימים)\s*[–-]\s*כרטיס סים וירטואלי$"
)


def _simtlv_duration(text):
    """'ל-90 ימים' → 90, 'לשנה' → 365, 'ל-5 שנים' → 1825."""
    if text == "לשנה":
        return 365
    m = re.match(r"ל-(\d+) ימים$", text)
    if m:
        return int(m.group(1))
    m = re.match(r"ל-(\d+) שנים$", text)
    if m:
        return int(m.group(1)) * 365
    return None


def _simtlv_classify(name):
    """Classify a normalized catalog product name.

    Returns (dest, gb, days, note) for live store packages, None for
    everything else (legacy/B2B/physical/credit products). gb=None means
    unlimited. Patterns are ordered most-specific-first so the regional
    products don't fall through to the generic local pattern.
    """
    m = _SIMTLV_RX_UNLIMITED.match(name)
    if m:
        return ("ארצות הברית", None, int(m.group(1)), "רשת T-Mobile")
    m = _SIMTLV_RX_EUROPE.match(name)
    if m:
        n = m.group(1)
        dest = f"אירופה ({n} מדינות)" if n else "אירופה"
        return (dest, float(m.group(2)), int(m.group(3)), None)
    m = _SIMTLV_RX_EUROPE_YR.match(name)
    if m:
        return (f"אירופה ({m.group(1)} מדינות)", float(m.group(2)), 365, None)
    m = _SIMTLV_RX_GLOBAL_N.match(name)
    if m:
        return (f"גלובלי ({m.group(1)} מדינות)", float(m.group(2)), int(m.group(3)), None)
    m = _SIMTLV_RX_EUR_PKG.match(name)
    if m:
        return (f"אירופה ({m.group(3)} מדינות)", float(m.group(1)), _simtlv_duration(m.group(2)), None)
    m = _SIMTLV_RX_GLOB_PKG.match(name)
    if m:
        return (f"גלובלי ({m.group(3)} מדינות)", float(m.group(1)), _simtlv_duration(m.group(2)), None)
    m = _SIMTLV_RX_LOCAL.match(name)
    if m:
        dest = m.group(1).strip()
        dest = SIMTLV_DEST_FIX.get(dest, dest)
        return (dest, float(m.group(2)), int(m.group(3)), None)
    return None


def _woo_store_fetch(products_url, label="Woo"):
    """Page through a WooCommerce Store API `products` endpoint; return raw dicts.

    Each page is retried 3× with backoff (these endpoints intermittently take
    >30s). A page that still fails is skipped — a partial catalog is safe
    because save_global_plans never deletes stale rows and new/removed
    events are dropped for global carriers. Shared by SimTLV + Terminal eSIM
    (both run the same WooCommerce Store API).
    """
    import requests
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }
    products, page_num, total_pages, failed_pages = [], 1, 1, 0
    while page_num <= total_pages:
        resp = None
        for attempt in range(3):
            try:
                r = requests.get(
                    products_url,
                    params={"per_page": 100, "page": page_num},
                    headers=headers, timeout=60,
                )
                if r.status_code == 200:
                    resp = r
                    break
                logger.warning(f"{label} catalog page {page_num}: HTTP {r.status_code}")
            except requests.RequestException as exc:
                logger.warning(f"{label} catalog page {page_num} attempt {attempt + 1}: {type(exc).__name__}")
            time.sleep(2 * (attempt + 1))
        if resp is None:
            failed_pages += 1
            page_num += 1
            continue
        total_pages = int(resp.headers.get("X-WP-TotalPages") or page_num)
        products.extend(resp.json())
        page_num += 1
    if failed_pages:
        logger.warning(f"{label} catalog: {failed_pages} pages failed — partial catalog")
    return products


def _simtlv_fetch_catalog():
    """SimTLV WooCommerce catalog (~2,400 products), via the shared Woo fetcher."""
    return _woo_store_fetch("https://simtlv.co.il/wp-json/wc/store/v1/products", "SimTLV")


def scrape_simtlv_esim(_page=None):
    """Scrape SimTLV's full per-country/regional eSIM catalog → ~940 plans.

    Pure HTTP, no Playwright. Complements scrape_simtlv_global (the
    127-country bundles on /global-61-30days) — both run every cycle.
    Per-country plans carry the Hebrew country in extras[0]; regional
    products use the 'אירופה (N מדינות)' / 'גלובלי (N מדינות)' labels the
    dashboard knows. Destinations are canonicalized via db._DEST_NORM
    *before* the plan name is built, so plan_name and extras[0] agree
    (the save path re-applies the same mapping — idempotent).
    """
    import html as _html
    from db import _DEST_NORM
    products = _simtlv_fetch_catalog()
    best = {}  # (dest, gb, days) -> (product_id, price, note)
    for prod in products:
        try:
            raw = prod.get("name") or ""
            name = re.sub(
                r"\s+", " ",
                _html.unescape(raw).replace("״", '"').replace("׳", "'")
            ).strip()
            parsed = _simtlv_classify(name)
            if not parsed:
                continue
            dest, gb, days, note = parsed
            dest = _DEST_NORM.get(dest, dest)
            prices = prod.get("prices") or {}
            minor = int(prices.get("currency_minor_unit") or 2)
            price = int(prices.get("price")) / (10 ** minor)
            pid = int(prod.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not days or price <= 0:
            continue
        key = (dest, gb, days)
        # Same package published under two product ids → keep the newest
        if key not in best or pid > best[key][0]:
            best[key] = (pid, price, note)
    plans = []
    for (dest, gb, days), (pid, price, note) in best.items():
        if gb is None:
            size_str = "ללא הגבלה"
        elif gb >= 1:
            size_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        else:
            size_str = f"{round(gb * 1024)}MB"
        plan_name = f"{dest} – {size_str} – {days} ימים"
        extras = [dest] + ([note] if note else [])
        plans.append(_make_global_plan(
            "simtlv", plan_name, price, "ILS", price,
            gb, days, esim=True, extras=extras
        ))
    logger.info(f"SimTLV eSIM catalog: {len(plans)} plans from {len(products)} products")
    return plans


# ── Terminal eSIM (terminalesim.com) ─────────────────
# Pure-HTTP WooCommerce Store API scrape (same platform as SimTLV). ~2,900
# products across ~190 countries + regional/global bundles, priced in USD
# (minor units -> /100). Replaced GlobaleSIM 2026-07 when the operator asked
# us to track terminalesim.com instead (message from 054-4322104).
#
# The product slug encodes the package: "<code>_<gb>_<period>" where period
# is a day count ("et_20_30" = 20GB/30d) or "daily" ("et_10_daily" = 10GB/
# day, no fixed validity). Country codes are ISO-3166 alpha-2 -> Hebrew via
# TERMINAL_CODE_TO_HEBREW; regional codes carry a trailing area count
# ("eu-33", "gl-120") and map to a canonical Hebrew region (all KNOWN_REGIONS
# on the dashboard) via TERMINAL_REGION_BASE. Data/validity are read from the
# product NAME (explicit GB/MB + "NDays" / "/Day"), which is authoritative.
TERMINAL_CODE_TO_HEBREW = {
    "ad": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "ae": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "af": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "ag": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "ai": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "al": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "am": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "ao": "\u05d0\u05e0\u05d2\u05d5\u05dc\u05d4",
    "ar": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "at": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "au": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "ax": "\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3",
    "az": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "ba": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "bb": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "bd": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "be": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "bf": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "bg": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "bh": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bj": "\u05d1\u05e0\u05d9\u05df",
    "bl": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "bm": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bn": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bo": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "br": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "bs": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bt": "\u05d1\u05d4\u05d5\u05d8\u05df",
    "bw": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4",
    "by": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "bz": "\u05d1\u05dc\u05d9\u05d6",
    "ca": "\u05e7\u05e0\u05d3\u05d4",
    "cd": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "cf": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "cg": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "ch": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "ci": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "cl": "\u05e6'\u05d9\u05dc\u05d4",
    "cm": "\u05e7\u05de\u05e8\u05d5\u05df",
    "cn": "\u05e1\u05d9\u05df",
    "co": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "cr": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "cv": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "cw": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cy": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "cz": "\u05e6'\u05db\u05d9\u05d4",
    "de": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "dk": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dm": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "do": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "dz": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "ec": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "ee": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eg": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "es": "\u05e1\u05e4\u05e8\u05d3",
    "et": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "fi": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "fj": "\u05e4\u05d9\u05d2'\u05d9",
    "fo": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fr": "\u05e6\u05e8\u05e4\u05ea",
    "ga": "\u05d2\u05d1\u05d5\u05df",
    "gb": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "gd": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "ge": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "gf": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gg": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "gh": "\u05d2\u05d0\u05e0\u05d4",
    "gi": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "gl": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "gm": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "gn": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "gp": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "gr": "\u05d9\u05d5\u05d5\u05df",
    "gt": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "gu": "\u05d2\u05d5\u05d0\u05dd",
    "gw": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "gy": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "hk": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hn": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hr": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "ht": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "hu": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "id": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "ie": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "il": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "im": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "in": "\u05d4\u05d5\u05d3\u05d5",
    "iq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "is": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "it": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "je": "\u05d2'\u05e8\u05d6\u05d9",
    "jm": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "jo": "\u05d9\u05e8\u05d3\u05df",
    "jp": "\u05d9\u05e4\u05df",
    "ke": "\u05e7\u05e0\u05d9\u05d4",
    "kg": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "kh": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "kn": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "kr": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "kw": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "ky": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "kz": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "la": "\u05dc\u05d0\u05d5\u05e1",
    "lc": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "li": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lk": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "lr": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "lt": "\u05dc\u05d9\u05d8\u05d0",
    "lu": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "lv": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "ly": "\u05dc\u05d5\u05d1",
    "ma": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mc": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "md": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "me": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "mf": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "mg": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "mk": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "ml": "\u05de\u05d0\u05dc\u05d9",
    "mn": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "mo": "\u05de\u05e7\u05d0\u05d5",
    "mq": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "ms": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "mt": "\u05de\u05dc\u05d8\u05d4",
    "mu": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mv": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mw": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "mx": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "my": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "mz": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "ne": "\u05e0\u05d9\u05d2'\u05e8",
    "ng": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "ni": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "nl": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "no": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "np": "\u05e0\u05e4\u05d0\u05dc",
    "nz": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "om": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pa": "\u05e4\u05e0\u05de\u05d4",
    "pe": "\u05e4\u05e8\u05d5",
    "pf": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "ph": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "pk": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "pl": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "pr": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "pt": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "py": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "qa": "\u05e7\u05d8\u05e8",
    "re": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "ro": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "rs": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "ru": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rw": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "sa": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "sc": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sd": "\u05e1\u05d5\u05d3\u05df",
    "se": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "sg": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "si": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "sk": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "sl": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "sm": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "sn": "\u05e1\u05e0\u05d2\u05dc",
    "sr": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sv": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "sz": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9",
    "tc": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "td": "\u05e6'\u05d0\u05d3",
    "th": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "tj": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tn": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "tr": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "tt": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tz": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "ua": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "ug": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "us": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uy": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "uz": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "va": "\u05d4\u05d5\u05d5\u05ea\u05d9\u05e7\u05df",
    "vc": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd",
    "vg": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d1\u05e8\u05d9\u05d8\u05d9\u05d9\u05dd",
    "vn": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "ws": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "xk": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "yt": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "za": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "zm": "\u05d6\u05de\u05d1\u05d9\u05d4",
}

TERMINAL_REGION_BASE = {
    "eu": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "as": "\u05d0\u05e1\u05d9\u05d4",
    "na": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "sa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "af": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "oc": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "o-oc": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "me": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "cb": "\u05d0\u05d9\u05d9 \u05d4\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "ca": "\u05de\u05e8\u05db\u05d6 \u05d0\u05e1\u05d9\u05d4",
    "gl": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "cn": "\u05e1\u05d9\u05df + \u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2 + \u05de\u05e7\u05d0\u05d5",
    "cnhk": "\u05e1\u05d9\u05df + \u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2 + \u05de\u05e7\u05d0\u05d5",
    "cnjpkr": "\u05d0\u05e1\u05d9\u05d4",
    "jpkr": "\u05d9\u05e4\u05df \u05d5\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "aunz": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "usca": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "bi": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "iesi": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "aukus": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "saaeqakwombh": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "sgmy": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "sgmyth": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "sgmyvnthid": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
}

TERMINAL_REGION_FULL = {
    "eu-7": "\u05d1\u05dc\u05e7\u05df",
    "as-5": "\u05de\u05e8\u05db\u05d6 \u05d0\u05e1\u05d9\u05d4",
}


def _terminal_resolve_dest(slug):
    """slug -> (dest_hebrew, is_region, area_count) or (None, None, None)."""
    code = slug.split("_")[0]
    if code in TERMINAL_CODE_TO_HEBREW:
        return TERMINAL_CODE_TO_HEBREW[code], False, None
    low = slug.lower()
    if low.startswith("england") or low.startswith("united-kingdom"):
        return TERMINAL_CODE_TO_HEBREW["gb"], False, None
    if code in TERMINAL_REGION_FULL:
        m = re.search(r"-(\d+)$", code)
        return TERMINAL_REGION_FULL[code], True, (int(m.group(1)) if m else None)
    m = re.match(r"^(.*)-(\d+)$", code)
    if m and m.group(1) in TERMINAL_REGION_BASE:
        return TERMINAL_REGION_BASE[m.group(1)], True, int(m.group(2))
    return None, None, None


def _terminal_parse_pkg(name):
    """Terminal product name -> (data_gb, days, is_daily, fup_note).

    data_gb: None if no size token; MB stored as GB fraction (<1).
    days: None for "/Day" plans (validity chosen at checkout).
    """
    n = name
    is_daily = bool(re.search(r"/\s*Day", n, re.I) or re.search(r"\bDaily\b", n, re.I))
    gb = None
    dm = re.search(r"(\d+(?:\.\d+)?)\s*GB", n, re.I)
    mbm = re.search(r"(\d+(?:\.\d+)?)\s*MB", n, re.I)
    if dm:
        gb = float(dm.group(1))
        gb = int(gb) if gb == int(gb) else gb
    elif mbm:
        gb = round(float(mbm.group(1)) / 1024, 4)
    dd = re.search(r"(\d+)\s*Days?\b", n, re.I)
    days = int(dd.group(1)) if dd else None
    fup = re.search(r"FUP\s*([0-9]+\s*[MKmk]bps)", n)
    return gb, days, is_daily, (fup.group(1) if fup else None)


def scrape_terminalesim(_page=None, usd_rate=None):
    """Terminal eSIM full per-country/regional catalog via the WooCommerce
    Store API. Pure HTTP, no Playwright. USD prices -> ILS via usd_rate.
    Mirrors scrape_simtlv_esim: dedup by (title, gb, days, daily) keeping the
    newest product id; destinations canonicalized via db._DEST_NORM before the
    plan name is built so plan_name and extras[0] agree (idempotent on save).
    """
    import html as _html
    from db import _DEST_NORM
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    products = _woo_store_fetch(
        "https://terminalesim.com/wp-json/wc/store/v1/products", "Terminal eSIM")
    best = {}  # (title, gb, days, is_daily) -> (product_id, usd, dest, fup)
    for prod in products:
        try:
            slug = prod.get("slug") or ""
            if not slug or slug == "topup" or slug.startswith("topup"):
                continue
            name = re.sub(r"\s+", " ", _html.unescape(prod.get("name") or "")).strip()
            dest, is_region, area = _terminal_resolve_dest(slug)
            if dest is None:
                continue
            gb, days, is_daily, fup = _terminal_parse_pkg(name)
            if gb is None and not is_daily:
                continue
            if not is_daily and days is None:
                continue
            prices = prod.get("prices") or {}
            minor = int(prices.get("currency_minor_unit") or 2)
            usd = int(prices.get("price")) / (10 ** minor)
            pid = int(prod.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if usd <= 0:
            continue
        dest = _DEST_NORM.get(dest, dest)
        title = f"{dest} ({area} " + "\u05de\u05d3\u05d9\u05e0\u05d5\u05ea" + ")" if (is_region and area) else dest
        key = (title, gb, days, is_daily)
        if key not in best or pid > best[key][0]:
            best[key] = (pid, usd, dest, fup)
    plans = []
    for (title, gb, days, is_daily), (pid, usd, dest, fup) in best.items():
        if gb is None:
            size = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"
        elif gb >= 1:
            size = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        else:
            size = f"{round(gb * 1024)}MB"
        if is_daily:
            plan_name = f"{title} \u2013 {size} " + "\u05dc\u05d9\u05d5\u05dd"
        else:
            plan_name = f"{title} \u2013 {size} \u2013 {days} " + "\u05d9\u05de\u05d9\u05dd"
        extras = [dest]
        if is_daily:
            extras.append("\u05d2\u05dc\u05d9\u05e9\u05d4 \u05d9\u05d5\u05de\u05d9\u05ea")
        if fup:
            extras.append(f"FUP {fup}")
        plans.append(_make_global_plan(
            "terminalesim", plan_name, round(usd * usd_rate, 2), "USD", round(usd, 2),
            gb, days, esim=True, extras=extras))
    logger.info(f"Terminal eSIM: {len(plans)} plans from {len(products)} products")
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


def scrape_carrier_news():
    """Fetch Google News RSS headlines for each domestic carrier.

    Uses the free Google News RSS endpoint (no API key required).
    Returns list of dicts: {carrier, headline, url, source, published_at}
    """
    import requests as _req
    import urllib.parse
    import xml.etree.ElementTree as ET

    CARRIER_KEYWORDS = {
        'partner':   '\u05e4\u05e8\u05d8\u05e0\u05e8 \u05e1\u05dc\u05d5\u05dc\u05e8',
        'pelephone': '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df',
        'hotmobile': '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
        'cellcom':   '\u05e1\u05dc\u05e7\u05d5\u05dd',
        'mobile019': '019 \u05e1\u05dc\u05d5\u05dc\u05e8',
        'xphone':    'XPhone \u05e1\u05dc\u05d5\u05dc\u05e8',
        'wecom':     'We-Com \u05e1\u05dc\u05d5\u05dc\u05e8',
        'neptucom':  'Neptucom \u05e1\u05dc\u05d5\u05dc\u05e8',
        'golan':     '\u05d2\u05d5\u05dc\u05df \u05d8\u05dc\u05e7\u05d5\u05dd',
        'rami_levy': '\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9 \u05e1\u05dc\u05d5\u05dc\u05e8',
        'breez': 'Breeze eSIM',
    }

    articles = []
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; MOCABot/1.0)'}

    for carrier, keyword in CARRIER_KEYWORDS.items():
        try:
            rss_url = (
                'https://news.google.com/rss/search'
                f'?q={urllib.parse.quote(keyword)}&hl=iw&gl=IL&ceid=IL:iw'
            )
            resp = _req.get(rss_url, headers=headers, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item'):
                title     = item.findtext('title') or ''
                link      = item.findtext('link') or ''
                pub       = item.findtext('pubDate') or ''
                source_el = item.find('source')
                source    = source_el.text if source_el is not None else ''
                # Normalize RFC 2822 pubDate → ISO 8601 for correct text sorting in SQLite
                if pub:
                    try:
                        from email.utils import parsedate_to_datetime as _p2d
                        pub = _p2d(pub).isoformat()
                    except Exception:
                        pass
                if title and link:
                    articles.append({
                        'carrier':      carrier,
                        'headline':     title,
                        'url':          link,
                        'source':       source,
                        'published_at': pub,
                    })
        except Exception as e:
            logger.error(f"scrape_carrier_news: {carrier} failed: {e}")

    logger.info(f"scrape_carrier_news: {len(articles)} articles fetched")
    return articles


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
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
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
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4", "lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
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
    "montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5", "montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5", "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4", "nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "nepal": "\u05e0\u05e4\u05d0\u05dc", "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3", "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4", "niger": "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "northern-mariana-islands": "\u05d0\u05d9\u05d9 \u05de\u05e8\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05d9\u05dd",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4", "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df", "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9", "peru": "\u05e4\u05e8\u05d5",
    "philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd", "poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc", "puerto-rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar": "\u05e7\u05d8\u05e8", "republic-of-congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df", "romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4", "saint-barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-and-nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4", "saint-martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "saint-vincent-and-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4", "san-marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea", "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4", "seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4", "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-maarten": "\u05e1\u05df \u05de\u05e8\u05d8\u05df", "slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
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
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "us-virgin-islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05de\u05e8\u05d9\u05e7\u05d4)",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df", "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4", "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4", "zimbabwe": "\u05d6\u05d9\u05de\u05d1\u05d1\u05d5\u05d0\u05d4",
}


# ISO 3166-1 alpha-2 -> Hebrew country name for Saily's Partners API
# (covered_countries returns ISO codes, not slugs). Derived from the canonical
# hotelDestinations.js {he, iso} list so extras[0] matches the rest of the system,
# plus a few non-ISO codes Saily uses (AS/HI/S1/SB/SX/BQ).
SAILY_ISO_TO_HEBREW = {
    "AD": "אנדורה",
    "AE": "איחוד האמירויות",
    "AF": "אפגניסטן",
    "AG": "אנטיגואה וברבודה",
    "AI": "אנגווילה",
    "AL": "אלבניה",
    "AM": "ארמניה",
    "AR": "ארגנטינה",
    "AS": "סמואה האמריקנית",
    "AT": "אוסטריה",
    "AU": "אוסטרליה",
    "AW": "ארובה",
    "AZ": "אזרבייג'ן",
    "BA": "בוסניה והרצגובינה",
    "BB": "ברבדוס",
    "BD": "בנגלדש",
    "BE": "בלגיה",
    "BF": "בורקינה פאסו",
    "BG": "בולגריה",
    "BH": "בחריין",
    "BJ": "בנין",
    "BL": "סן ברתלמי",
    "BM": "ברמודה",
    "BN": "ברוניי",
    "BO": "בוליביה",
    "BQ": "בונייר",
    "BR": "ברזיל",
    "BS": "איי הבהאמה",
    "BW": "בוטסואנה",
    "BZ": "בליז",
    "CA": "קנדה",
    "CD": "הרפובליקה הדמוקרטית של קונגו",
    "CF": "הרפובליקה המרכז אפריקאית",
    "CG": "רפובליקת קונגו",
    "CH": "שוויץ",
    "CI": "חוף השנהב",
    "CL": "צ'ילה",
    "CM": "קמרון",
    "CN": "סין",
    "CO": "קולומביה",
    "CR": "קוסטה ריקה",
    "CV": "קייפ ורדה",
    "CW": "קוראסאו",
    "CY": "קפריסין",
    "CZ": "צ'כיה",
    "DE": "גרמניה",
    "DK": "דנמרק",
    "DM": "דומיניקה",
    "DO": "הרפובליקה הדומיניקנית",
    "DZ": "אלג'יריה",
    "EC": "אקוודור",
    "EE": "אסטוניה",
    "EG": "מצרים",
    "ES": "ספרד",
    "FI": "פינלנד",
    "FJ": "פיג'י",
    "FO": "איי פארו",
    "FR": "צרפת",
    "GA": "גאבון",
    "GB": "בריטניה",
    "GD": "גרנדה",
    "GE": "גאורגיה",
    "GF": "גיאנה הצרפתית",
    "GG": "גרנזי",
    "GH": "גאנה",
    "GI": "גיברלטר",
    "GL": "גרינלנד",
    "GM": "גמביה",
    "GN": "גינאה",
    "GP": "גוואדלופ",
    "GR": "יוון",
    "GT": "גואטמלה",
    "GU": "גואם",
    "GW": "גינאה ביסאו",
    "GY": "גיאנה",
    "HI": "הוואי",
    "HK": "הונג קונג",
    "HN": "הונדורס",
    "HR": "קרואטיה",
    "HT": "האיטי",
    "HU": "הונגריה",
    "ID": "אינדונזיה",
    "IE": "אירלנד",
    "IL": "ישראל",
    "IM": "האי מאן",
    "IN": "הודו",
    "IQ": "עיראק",
    "IS": "איסלנד",
    "IT": "איטליה",
    "JE": "ג'רזי",
    "JM": "ג'מייקה",
    "JO": "ירדן",
    "JP": "יפן",
    "KE": "קניה",
    "KG": "קירגיזסטן",
    "KH": "קמבודיה",
    "KN": "סנט קיטס ונוויס",
    "KR": "דרום קוריאה",
    "KW": "כוויית",
    "KY": "איי קיימן",
    "KZ": "קזחסטן",
    "LA": "לאוס",
    "LC": "סנט לוסיה",
    "LI": "ליכטנשטיין",
    "LK": "סרי לנקה",
    "LR": "ליבריה",
    "LS": "לסוטו",
    "LT": "ליטא",
    "LU": "לוקסמבורג",
    "LV": "לטביה",
    "MA": "מרוקו",
    "MC": "מונקו",
    "MD": "מולדובה",
    "ME": "מונטנגרו",
    "MF": "סן מרטן",
    "MG": "מדגסקר",
    "MK": "מקדוניה הצפונית",
    "ML": "מאלי",
    "MN": "מונגוליה",
    "MO": "מקאו",
    "MP": "איי מריאנה הצפוניים",
    "MQ": "מרטיניק",
    "MR": "מאוריטניה",
    "MS": "מונסראט",
    "MT": "מלטה",
    "MU": "מאוריציוס",
    "MV": "האיים המלדיביים",
    "MW": "מלאווי",
    "MX": "מקסיקו",
    "MY": "מלזיה",
    "MZ": "מוזמביק",
    "NA": "נמיביה",
    "NE": "ניג'ר",
    "NG": "ניגריה",
    "NI": "ניקראגואה",
    "NL": "הולנד",
    "NO": "נורבגיה",
    "NP": "נפאל",
    "NR": "נאורו",
    "NZ": "ניו זילנד",
    "OM": "עומאן",
    "PA": "פנמה",
    "PE": "פרו",
    "PF": "פולינזיה הצרפתית",
    "PG": "פפואה גינאה החדשה",
    "PH": "הפיליפינים",
    "PK": "פקיסטן",
    "PL": "פולין",
    "PR": "פוארטו ריקו",
    "PT": "פורטוגל",
    "PY": "פראגוואי",
    "QA": "קטר",
    "RE": "ראוניון",
    "RO": "רומניה",
    "RS": "סרביה",
    "RW": "רואנדה",
    "S1": "האנטילים ההולנדיים",
    "SA": "ערב הסעודית",
    "SB": "איי שלמה",
    "SC": "איי סיישל",
    "SD": "סודן",
    "SE": "שבדיה",
    "SG": "סינגפור",
    "SI": "סלובניה",
    "SK": "סלובקיה",
    "SL": "סיירה ליאונה",
    "SM": "סן מרינו",
    "SN": "סנגל",
    "SR": "סורינאם",
    "SS": "דרום סודן",
    "SV": "אל סלבדור",
    "SX": "סנט מארטן",
    "SZ": "אסוואטיני",
    "TC": "איי טורקס וקאיקוס",
    "TD": "צ'אד",
    "TG": "טוגו",
    "TH": "תאילנד",
    "TJ": "טג'יקיסטן",
    "TL": "טימור לסטה",
    "TN": "תוניסיה",
    "TO": "טונגה",
    "TR": "טורקיה",
    "TT": "טרינידד וטובגו",
    "TW": "טייוואן",
    "TZ": "טנזניה",
    "UA": "אוקראינה",
    "UG": "אוגנדה",
    "US": "ארצות הברית",
    "UY": "אורוגוואי",
    "UZ": "אוזבקיסטן",
    "VC": "סנט וינסנט והגרדינים",
    "VE": "ונצואלה",
    "VG": "איי הבתולה (בריטניה)",
    "VI": "איי הבתולה (ארה\"ב)",
    "VN": "וייטנאם",
    "VU": "ונואטו",
    "WS": "סמואה",
    "XK": "קוסובו",
    "YT": "מאיוט",
    "ZA": "דרום אפריקה",
    "ZM": "זמביה",
    "ZW": "זימבבואה",
}

# Saily Partners API region codes -> Hebrew (multi-country plans carry `region`).
SAILY_API_REGION_TO_HEBREW = {
    "EU":   "אירופה",
    "GLB":  "גלובלי",
    "ASA":  "אסיה ואוקיאניה",
    "NAM":  "צפון אמריקה",
    "CIS":  "חבר העמים",
    "LAT":  "אמריקה הלטינית",
    "MENA": "המזרח התיכון וצפון אפריקה",
    "AFR":  "אפריקה",
}

_SAILY_API_URL = "https://web.saily.com/v3/partners/plans?utm_source=moca"
# Cloudflare in front of web.saily.com fingerprints the client: a plain urllib
# request 403s, but a browser User-Agent + Referer (via requests) passes.
_SAILY_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://partners.saily.com/",
}
_SAILY_API_CACHE = {"ts": 0.0, "items": None}


def _fetch_saily_api(force=False):
    """GET the Saily Partners API once and cache for 10 min (the global and
    regional scrape fns run in the same cycle and share this). Returns items[]."""
    import time
    import requests
    now = time.time()
    if not force and _SAILY_API_CACHE["items"] is not None and now - _SAILY_API_CACHE["ts"] < 600:
        return _SAILY_API_CACHE["items"]
    resp = requests.get(_SAILY_API_URL, headers=_SAILY_API_HEADERS, timeout=30)
    resp.raise_for_status()
    items = (resp.json() or {}).get("items", []) or []
    _SAILY_API_CACHE["ts"] = now
    _SAILY_API_CACHE["items"] = items
    return items


def _saily_api_item_to_plan(item, heb_name, usd_rate):
    """Convert one Saily API plan item into the internal global-plan dict."""
    bal = next((b for b in (item.get("balances") or []) if b.get("type") == "DATA"), None)
    if item.get("is_unlimited") or (bal and bal.get("is_unlimited")):
        gb = None
    elif bal is not None and bal.get("amount") is not None:
        gb = bal["amount"]
    else:
        return None
    dur = item.get("duration") or {}
    if dur.get("unit") != "day" or dur.get("amount") is None:
        return None
    days = dur["amount"]
    # amount_with_tax is in minor units (cents); take the cheapest USD merchant plan.
    usd_mps = [mp for mp in (item.get("merchant_plans") or [])
               if mp.get("price") and mp["price"].get("amount_with_tax") is not None
               and mp["price"].get("currency") == "USD"]
    if not usd_mps:
        return None
    cheapest = min(usd_mps, key=lambda mp: mp["price"]["amount_with_tax"])
    price_usd = round(cheapest["price"]["amount_with_tax"] / 100.0, 2)
    price_ils = round(price_usd * usd_rate, 2)
    # planId for the Saily checkout deep-link: the price `identifier` is the checkout
    # token for THIS merchant plan, consumed by app.py `_saily_checkout_url` via /go.
    plan_ref = cheapest["price"].get("identifier")
    if gb is None:
        gb_str = "ללא הגבלה"
    elif gb >= 1:
        gb_str = f"{int(gb)}GB"
    else:
        gb_str = f"{round(gb * 1024)}MB"
    plan_name = f"{heb_name} – {gb_str} – {days} ימים"
    plan = _make_global_plan("saily", plan_name, price_ils, "USD", price_usd,
                             gb, days, esim=True, extras=[heb_name])
    if plan_ref:
        plan["plan_ref"] = plan_ref
    return plan


def scrape_saily_global(_page=None, usd_rate=None):
    """Saily single-country eSIM plans via the official Partners API
    (utm_source=moca). Replaces the old per-country Playwright scrape (~199 page
    loads, brittle behind Cloudflare) with one JSON call. _page kept for the
    runner's uniform signature; unused."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    all_plans = []
    unmapped = set()
    try:
        items = _fetch_saily_api()
    except Exception as exc:
        logger.warning(f"Saily API fetch failed (global): {exc}")
        return all_plans
    for item in items:
        cc = item.get("covered_countries") or []
        if len(cc) != 1:
            continue
        heb = SAILY_ISO_TO_HEBREW.get(cc[0])
        if not heb:
            unmapped.add(cc[0])
            continue
        plan = _saily_api_item_to_plan(item, heb, usd_rate)
        if plan:
            all_plans.append(plan)
    if unmapped:
        logger.warning(f"Saily global: skipped unmapped ISO codes {sorted(unmapped)}")
    logger.info(f"Saily global: {len(all_plans)} plans (Partners API, single-country)")
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
    "azores": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05d0\u05d6\u05d5\u05e8\u05d9\u05d9\u05dd",
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
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
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
    "montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "nepal": "\u05e0\u05e4\u05d0\u05dc",
    "netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "netherlands-antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd",
    "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "northern-cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "northern-mariana-islands": "\u05d0\u05d9\u05d9 \u05de\u05e8\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05d9\u05dd",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
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
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "san-marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "scotland": "\u05e1\u05e7\u05d5\u05d8\u05dc\u05e0\u05d3",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-eustatius": "\u05e1\u05d9\u05e0\u05d8 \u05d0\u05d5\u05e1\u05d8\u05d8\u05d9\u05d5\u05e1",
    "sint-maarten": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
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
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "vatican": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


def _esimio_packages_to_plans(pkgs, dest_heb, usd_rate):
    """Convert esim.io RSC `packages` entries to MOCA global plan dicts.

    Package shape since the 2026-04 redesign: `data` in bytes, `duration` +
    `durationUnit`, price nested as {"price": 2.2, "currency": "USD", ...}.
    PAYG/unlimited teasers are skipped \u2014 only fixed-GB packages are comparable.
    """
    plans = []
    for pkg in pkgs:
        if pkg.get("isUnlimited"):
            continue
        price_obj = pkg.get("price") or {}
        try:
            data_bytes = float(pkg.get("data") or 0)
            price_usd = float(price_obj.get("price") or 0)
        except (TypeError, ValueError):
            continue
        currency = (price_obj.get("currency") or "USD").upper()
        gb = data_bytes / (1024 ** 3)
        if gb < 1 or price_usd <= 0 or currency != "USD":
            continue
        days = 30
        try:
            if pkg.get("duration") and str(pkg.get("durationUnit") or "DAYS").upper() == "DAYS":
                days = int(pkg["duration"])
        except (TypeError, ValueError):
            pass
        gb = int(gb) if gb == int(gb) else round(gb, 2)
        gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        plan_name = f"{dest_heb} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
        plans.append(_make_global_plan(
            "esimio", plan_name, round(price_usd * usd_rate, 2), "USD", price_usd,
            gb, days, esim=True, extras=[dest_heb]
        ))
    return plans


def scrape_esimio_destinations(_page=None, usd_rate=None):
    """Scrape eSIM.io per-country plans from all destination pages.

    Since ~2026-04 esim.io runs on the eSIMO Next.js platform (assets from
    statics.esimo.com) \u2014 the old h5 plan cards are gone (only duration-tab labels
    and a PAYG teaser remain), but the full 30-day packages array is server-rendered
    into the RSC flight stream, same encoding as esimo.io. Reuses
    _esimo_extract_packages; pure HTTP, no Playwright. Catalogs/prices differ from
    esimo.io (separate brand), so it stays a distinct provider.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    def fetch_one(slug):
        return _esimo_extract_packages(
            _esimo_fetch(f"https://esim.io/destinations/esim-{slug}")
        )

    all_plans = []
    empty, failed = 0, 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): (s, heb) for s, heb in ESIMIO_SLUG_TO_HEBREW.items()}
        for fut in as_completed(futures):
            slug, country_heb = futures[fut]
            try:
                pkgs = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIM.io {slug}: {exc}")
                continue
            if not pkgs:
                empty += 1  # removed destination or page without embedded packages
                continue
            all_plans.extend(_esimio_packages_to_plans(pkgs, country_heb, usd_rate))
    logger.info(
        f"eSIM.io destinations: {len(all_plans)} plans from "
        f"{len(ESIMIO_SLUG_TO_HEBREW)} countries ({empty} empty, {failed} failed)"
    )
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
    "central-african-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
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
    "latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
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
    "nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger": "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "north-macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "panama": "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
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
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "senegal": "\u05e1\u05e0\u05d2\u05dc",
    "serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
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
    "uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
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


def scrape_saily_regions(_page=None, usd_rate=None):
    """Saily regional eSIM plans via the official Partners API (utm_source=moca).
    Multi-country items carry a `region` code (EU/GLB/ASA/NAM/CIS/LAT/MENA/AFR).
    Replaces the old per-region Playwright scrape. _page unused (uniform sig)."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    all_plans = []
    unmapped = set()
    try:
        items = _fetch_saily_api()
    except Exception as exc:
        logger.warning(f"Saily API fetch failed (regions): {exc}")
        return all_plans
    for item in items:
        cc = item.get("covered_countries") or []
        if len(cc) <= 1:
            continue
        heb = SAILY_API_REGION_TO_HEBREW.get(item.get("region"))
        if not heb:
            unmapped.add(item.get("region"))
            continue
        plan = _saily_api_item_to_plan(item, heb, usd_rate)
        if plan:
            all_plans.append(plan)
    if unmapped:
        logger.warning(f"Saily regions: skipped unmapped region codes {sorted(unmapped)}")
    logger.info(f"Saily regions: {len(all_plans)} plans (Partners API, regional)")
    return all_plans


# ── Yesim (own platform; plans embedded as Next.js __NEXT_DATA__ JSON) ───────
# Price = vanillaPrice/100 * currency.rate (the geo-localized USD price the
# Israel-based backend sees = what Israeli users pay). ISO -> Hebrew reuses
# SAILY_ISO_TO_HEBREW plus a few countries Saily doesn't cover. Palestine (PS)
# is deliberately excluded (left unmapped → skipped).
# Shared supplement of ISO -> Hebrew for countries Saily doesn't cover (used by
# the Yesim and Nomad scrapers on top of SAILY_ISO_TO_HEBREW).
_YESIM_EXTRA_ISO_TO_HEBREW = {
    "AO": "אנגולה", "AN": "האנטילים ההולנדיים", "BT": "בהוטן",
    "BY": "בלארוס", "CU": "קובה", "ET": "אתיופיה", "RU": "רוסיה",
    "AX": "איי אולנד", "BI": "בורונדי", "DJ": "ג'יבוטי", "LY": "לוב",
    "ST": "סאו טומה ופרינסיפה", "VA": "הוותיקן", "US-HI": "הוואי",
}

_YESIM_REGION_TO_HEBREW = {
    "europe-esim": "אירופה",
    "balkans-esim": "הבלקן",
    "asia-pacific-esim": "אסיה ואוקיאניה",
    "south-east-asia-esim": "דרום מזרח אסיה",
    "cis-esim": "חבר העמים",
    "north-america-esim": "צפון אמריקה",
    "south-america-esim": "דרום אמריקה",
    "middle-east-esim": "המזרח התיכון",
    "caribbean-esim": "איי הקריביים",
    "africa-esim": "אפריקה",
}

_YESIM_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _yesim_iso_to_heb(iso):
    return SAILY_ISO_TO_HEBREW.get(iso) or _YESIM_EXTRA_ISO_TO_HEBREW.get(iso)


def _yesim_get_pp(url):
    """Fetch a Yesim page and return its Next.js pageProps dict (or None)."""
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": _YESIM_UA}, timeout=30)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return None
    try:
        return _json.loads(m.group(1)).get("props", {}).get("pageProps")
    except Exception:
        return None


def _yesim_plans_from_pp(pp, usd_rate, heb_override=None):
    out = []
    try:
        rate = float((pp.get("currency") or {}).get("rate", 1)) or 1.0
    except (TypeError, ValueError):
        rate = 1.0
    for key in ("standardPlans", "unlimitedPlans"):
        for p in (pp.get(key) or []):
            if heb_override:
                heb = heb_override
            else:
                dests = p.get("destinations") or []
                if not dests:
                    continue
                iso = ((dests[0].get("direction") or {}).get("iso") or "").upper()
                heb = _yesim_iso_to_heb(iso)
                if not heb:
                    continue  # unmapped / deliberately excluded (e.g. PS)
            da = p.get("dataAmount") or {}
            ingb = da.get("inGb")
            try:
                gb = None if (p.get("unlimited") or key == "unlimitedPlans"
                              or ingb in (None, "", "NaN")) else float(ingb)
            except (TypeError, ValueError):
                gb = None
            days = p.get("validityPeriod")
            vp = p.get("vanillaPrice")
            if days is None or vp is None:
                continue
            price_usd = round(vp / 100 * rate, 2)
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
            out.append(_make_global_plan("yesim", plan_name, price_ils, "USD",
                                         price_usd, gb, days, esim=True, extras=[heb]))
    return out


def scrape_yesim_global(_page=None, usd_rate=None):
    """Yesim single-country eSIM plans from the site's embedded __NEXT_DATA__ JSON
    (browser UA required; urllib/empty-UA gets a 202). Enumerates countries from
    `popularCountries` on one page, then fetches each concurrently. Palestine (PS)
    is deliberately excluded."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    seed = _yesim_get_pp("https://yesim.app/country/united-states/")
    if not seed:
        logger.warning("Yesim: could not load seed page for country enumeration")
        return []
    urls = ["https://yesim.app" + (c.get("url") or "")
            for c in (seed.get("popularCountries") or [])
            if (c.get("url") or "").startswith("/country/")]
    all_plans, seen = [], set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_yesim_get_pp, u): u for u in urls}
        for f in as_completed(futs):
            try:
                pp = f.result()
                if not pp:
                    continue
                for plan in _yesim_plans_from_pp(pp, usd_rate):
                    k = (plan["carrier"], plan["plan_name"])
                    if k not in seen:
                        seen.add(k)
                        all_plans.append(plan)
            except Exception as exc:
                logger.warning(f"Yesim country {futs[f]}: {exc}")
    logger.info(f"Yesim global: {len(all_plans)} plans from {len(urls)} countries")
    return all_plans


def scrape_yesim_regions(_page=None, usd_rate=None):
    """Yesim regional eSIM plans from /regions/<slug>/ pages (region name forced
    from the slug since per-plan destinations list individual countries)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    all_plans, seen = [], set()

    def _one(slug, heb):
        pp = _yesim_get_pp(f"https://yesim.app/regions/{slug}/")
        return _yesim_plans_from_pp(pp, usd_rate, heb_override=heb) if pp else []

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_one, slug, heb): slug
                for slug, heb in _YESIM_REGION_TO_HEBREW.items()}
        for f in as_completed(futs):
            try:
                for plan in f.result():
                    k = (plan["carrier"], plan["plan_name"])
                    if k not in seen:
                        seen.add(k)
                        all_plans.append(plan)
            except Exception as exc:
                logger.warning(f"Yesim region {futs[f]}: {exc}")
    logger.info(f"Yesim regions: {len(all_plans)} plans from {len(_YESIM_REGION_TO_HEBREW)} regions")
    return all_plans


# ── Nomad (nomadesim.com; plans embedded as `vike_pageContext` JSON) ─────────
# ISO-based coverage (single-country) reuses SAILY_ISO_TO_HEBREW + extras;
# multi-country plans map slug -> region Hebrew. "Unlimited" plans carry a numeric
# fair-use cap in data.amount but say "unlimited" in the name -> detect via name.
_NOMAD_REGION_SLUG_TO_HEBREW = {
    "europe-eSIM": "אירופה",
    "apac-eSIM": "אסיה ואוקיאניה",
    "asia-eSIM": "אסיה",
    "global-eSIM": "גלובלי",
    "global-ex-eSIM": "גלובלי",
    "mena-eSIM": "המזרח התיכון וצפון אפריקה",
    "middle-east-eSIM": "המזרח התיכון",
    "north-america-eSIM": "צפון אמריקה",
    "latin-america-eSIM": "אמריקה הלטינית",
    "caribbean-eSIM": "איי הקריביים",
    "africa-eSIM": "אפריקה",
    "balkans-eSIM": "הבלקן",
    "caucasus-eSIM": "הקווקז",
    "oceania-eSIM": "אוקיאניה",
    "cn-jp-kr-eSIM": "סין, יפן, קוריאה",
    "sg-my-th-eSIM": "סינגפור, מלזיה, תאילנד",
    "gcc-eSIM": "מדינות המפרץ",
    "sea-oceania-eSIM": "דרום מזרח אסיה ואוקיאניה",
}


def _nomad_find_plans(obj):
    if isinstance(obj, dict):
        v = obj.get("plans")
        if isinstance(v, list):
            return v
        for x in obj.values():
            r = _nomad_find_plans(x)
            if r:
                return r
    elif isinstance(obj, list):
        for x in obj:
            r = _nomad_find_plans(x)
            if r:
                return r
    return None


def _nomad_get_plans(url):
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": _YESIM_UA}, timeout=30)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    m = re.search(r'<script id="vike_pageContext"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return []
    try:
        return _nomad_find_plans(_json.loads(m.group(1))) or []
    except Exception:
        return []


def scrape_nomad_global(_page=None, usd_rate=None):
    """Nomad eSIM plans from embedded vike_pageContext JSON on each /<slug>-eSIM
    page (slugs from sitemap-plans.xml). Single-country -> ISO->Hebrew; multi-country
    -> slug->region Hebrew. Dedups by plan_name keeping the cheapest."""
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    try:
        sm = requests.get("https://www.nomadesim.com/sitemap-plans.xml",
                          headers={"User-Agent": _YESIM_UA}, timeout=30).text
    except Exception as exc:
        logger.warning(f"Nomad sitemap fetch failed: {exc}")
        return []
    slugs = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm)
             if re.match(r"https://www\.nomadesim\.com/[^/]+-eSIM$", u)]
    iso2he = {**SAILY_ISO_TO_HEBREW, **_YESIM_EXTRA_ISO_TO_HEBREW}
    unmapped = set()

    def _do(url):
        slug = url.rsplit("/", 1)[-1]
        res = []
        for p in _nomad_get_plans(url):
            prod = p.get("product") or {}
            cc = (prod.get("coverage") or {}).get("countries") or []
            if not cc:
                continue
            heb = iso2he.get(cc[0]) if len(cc) == 1 else _NOMAD_REGION_SLUG_TO_HEBREW.get(slug)
            if not heb:
                unmapped.add(cc[0] if len(cc) == 1 else slug)
                continue
            data = (prod.get("service") or {}).get("data") or {}
            amt = data.get("amount")
            unit = (data.get("amount_unit") or "GB").upper()
            if "unlimited" in (prod.get("name") or "").lower():
                gb = None
            elif amt is None:
                continue
            else:
                try:
                    gb = float(amt) / 1024 if unit == "MB" else float(amt)
                except (TypeError, ValueError):
                    continue
            spec = prod.get("specification") or {}
            days = spec.get("duration")
            if days is None or (spec.get("duration_unit") or "DAY").upper() != "DAY":
                continue
            usd = ((p.get("price") or {}).get("USD") or {}).get("amount")
            if usd is None:
                continue
            try:
                price_usd = round(float(usd), 2)
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
            res.append((plan_name, price_ils, price_usd, gb, days, heb))
        return res

    best = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_do, u): u for u in slugs}
        for f in as_completed(futs):
            try:
                for (pn, pil, pusd, gb, days, heb) in f.result():
                    if pn not in best or pil < best[pn][1]:
                        best[pn] = (pn, pil, pusd, gb, days, heb)
            except Exception as exc:
                logger.warning(f"Nomad {futs[f]}: {exc}")
    all_plans = [_make_global_plan("nomad", pn, pil, "USD", pusd, gb, days, esim=True, extras=[heb])
                 for (pn, pil, pusd, gb, days, heb) in best.values()]
    if unmapped:
        logger.warning(f"Nomad: skipped unmapped {sorted(unmapped)[:30]}")
    logger.info(f"Nomad global: {len(all_plans)} plans from {len(slugs)} pages")
    return all_plans


# ── Ubigi (Transatel/NTT; open WooCommerce Store REST API) ───────────────────
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
    return SAILY_SLUG_TO_HEBREW.get(sl) or _UBIGI_EXTRA_HEBREW.get(sl)


def scrape_ubigi_global(_page=None, usd_rate=None):
    """Ubigi eSIM plans from the open WooCommerce Store REST API (~11 pages, no
    auth). One-time (ONEOFF) plans only; recurring subscriptions skipped. Country/
    GB/days parsed from the `name` ('DEST • 10GB • 30 days'); price = minor units."""
    import requests
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    headers = {"User-Agent": _YESIM_UA}
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
    all_plans = [_make_global_plan("ubigi", pn, pil, "USD", pusd, gb, days, esim=True, extras=[heb])
                 for (pil, pusd, gb, days, heb, pn) in best.values()]
    logger.info(f"Ubigi global: {len(all_plans)} plans")
    return all_plans


# ── aloSIM (alosim.com; WordPress; plan data in destination-page HTML) ───────
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
    base = _UBIGI_ALIAS.get(base, base)
    return SAILY_SLUG_TO_HEBREW.get(base) or _ALOSIM_EXTRA.get(slug)


def _alosim_page_plans(url, heb, usd_rate):
    import requests, time as _t
    html = None
    for attempt in range(3):  # aloSIM (Wordfence/Cloudflare) rate-limits at scale → retry
        try:
            r = requests.get(url, headers={"User-Agent": _YESIM_UA}, timeout=30)
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
        usd_rate = _get_usd_to_ils()
    locs = []
    for page in range(1, 5):
        try:
            r = requests.get(f"https://alosim.com/wp-json/wp/v2/location?per_page=100&page={page}&_fields=slug,link",
                             headers={"User-Agent": _YESIM_UA}, timeout=40)
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
    all_plans = [_make_global_plan("alosim", pn, pil, "USD", pusd, gb, days, esim=True, extras=[heb])
                 for pn, (pil, pusd, gb, days, heb) in best.items()]
    logger.info(f"aloSIM global: {len(all_plans)} plans from {len(targets)} destinations")
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


ESIMIO_REGIONS = {
    "esim-europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "esim-africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "esim-asia-pacific": "\u05d0\u05e1\u05d9\u05d4 \u05e4\u05e1\u05d9\u05e4\u05d9\u05e7",
    "esim-balkans": "\u05d1\u05dc\u05e7\u05df",
    "esim-carribean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "esim-latin-america": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "esim-central-asia": "\u05de\u05e8\u05db\u05d6 \u05d0\u05e1\u05d9\u05d4",
    "esim-middle-east": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "esim-north-africa": "\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "esim-north-america": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
}


def scrape_esimio_regions(_page=None, usd_rate=None):
    """Scrape eSIM.io regional eSIM plans (10 regions).

    Same RSC-embedded packages extraction as scrape_esimio_destinations (the old
    h5-card parsing died in the 2026-04 redesign). The /regions/<slug> pages still
    use the original esim-* slugs \u2014 verified against the /regions index links.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    def fetch_one(slug):
        return _esimo_extract_packages(
            _esimo_fetch(f"https://esim.io/regions/{slug}")
        )

    all_plans = []
    empty, failed = 0, 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): (s, heb) for s, heb in ESIMIO_REGIONS.items()}
        for fut in as_completed(futures):
            slug, region_heb = futures[fut]
            try:
                pkgs = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIM.io region {slug}: {exc}")
                continue
            if not pkgs:
                empty += 1
                continue
            all_plans.extend(_esimio_packages_to_plans(pkgs, region_heb, usd_rate))
    logger.info(
        f"eSIM.io regions: {len(all_plans)} plans from "
        f"{len(ESIMIO_REGIONS)} regions ({empty} empty, {failed} failed)"
    )
    return all_plans


TUKI_REGIONS = {
    "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4": {  # אוקיאניה
        (1, 7): 12.0, (3, 30): 33.0, (5, 30): 46.5, (10, 30): 69.3, (20, 30): 115.5,
    },
    "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4": {  # אירופה
        (1, 7): 5.0, (2, 15): 9.5, (3, 30): 13.0, (5, 30): 20.0, (10, 30): 37.0, (20, 30): 49.0, (50, 90): 100.0, (100, 180): 185.0,
    },
    "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea": {  # אמריקה הדרומית
        (1, 7): 15.0, (2, 15): 28.0, (3, 30): 39.0, (5, 30): 60.0,
    },
    "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea": {  # אמריקה הלטינית (Central/Caribbean)
        (1, 7): 6.5, (2, 15): 12.0, (3, 30): 17.0, (5, 30): 25.5, (10, 30): 46.0, (20, 30): 65.0,
    },
    "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4": {  # צפון אמריקה
        (1, 7): 6.5, (2, 15): 12.0, (3, 30): 17.0, (5, 30): 25.5, (10, 30): 46.0,
    },
    "\u05d0\u05e1\u05d9\u05d4": {  # אסיה
        (1, 7): 5.0, (2, 15): 9.5, (3, 30): 13.0, (5, 30): 20.0, (10, 30): 37.0, (20, 30): 49.0, (50, 90): 100.0, (100, 180): 185.0,
    },
    "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4": {  # אפריקה
        (1, 30): 27.0, (2, 30): 38.0, (3, 30): 59.0,
    },
    "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9": {  # גלובלי
        (1, 7): 9.0, (2, 15): 17.0, (3, 30): 24.0, (5, 60): 35.0, (10, 180): 59.0, (20, 365): 69.0,
    },
}

def scrape_tuki_regions(page, usd_rate):
    """Tuki regional eSIM plans — hardcoded prices (USD)."""
    all_plans = []
    for region_heb, plans_data in TUKI_REGIONS.items():
        for (gb, days), price_usd in plans_data.items():
            price_ils = round(price_usd * usd_rate, 2)
            plan_name = f"{region_heb} \u2013 {gb}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
            all_plans.append(_make_global_plan(
                "tuki", plan_name, price_ils, "USD", price_usd,
                data_gb=gb, days=days, esim=True, extras=[region_heb]
            ))
    logger.info(f"Tuki regions: {len(all_plans)} plans from {len(TUKI_REGIONS)} regions")
    return all_plans


def scrape_tuki_local(page, usd_rate):
    """Scrape Tuki per-country eSIM plans via their JSON API."""
    import urllib.request, json as _json
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124"
    all_plans = []

    try:
        url = "https://www.tuki-esim.co.il/ds/api/globalsim/data/?lcid=1037&pageControlId=21412"
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read().decode("utf-8")
        # Response is JS assignment: datasource.globalsimData={...}
        json_str = raw.split("=", 1)[1]
        data = _json.loads(json_str)

        countries = data.get("countries", [])
        packages = data.get("packages", [])

        # Build package lookup by id
        pkg_by_id = {p["id"]: p for p in packages}

        # Normalize country names to match other providers
        _tuki_name_fix = {
            "\u05d0\u05d9\u05d9 \u05d1\u05d4\u05d0\u05de\u05d4": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",  # איי בהאמה -> איי הבהאמה
            "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d1\u05e8\u05d9\u05d8\u05d9\u05d9\u05dd": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",  # איי הבתולה (בריטניה) -> איי הבתולה (בריטניה)
            "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d0\u05de\u05e8\u05d9\u05e7\u05e0\u05d9\u05dd": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",  # איי הבתולה האמריקנים -> איי הבתולה (ארה"ב)
            "\u05e0\u05d5\u05e8\u05d5\u05d5\u05d2\u05d9\u05d4": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",  # נורווגיה -> נורבגיה
            "\u05e9\u05d5\u05d5\u05d3\u05d9\u05d4": "\u05e9\u05d1\u05d3\u05d9\u05d4",  # שוודיה -> שבדיה
            "\u05e9\u05d5\u05d5\u05d9\u05d9\u05e5": "\u05e9\u05d5\u05d5\u05d9\u05e5",  # שווייץ -> שוויץ
            "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea \u05d4\u05e2\u05e8\u05d1\u05d9\u05d5\u05ea": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",  # איחוד האמירויות -> איחוד האמירויות
            "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טורק וקייקוס -> איי טורקס וקאיקוס
            "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טורקס וקייקוס -> איי טורקס וקאיקוס
            "\u05d0\u05d9\u05d9 \u05d8\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טרקס וקייקוס -> איי טורקס וקאיקוס
        }
        for country in countries:
            raw_name = country.get("nameHeb", "").strip()
            country_heb = _tuki_name_fix.get(raw_name, raw_name)
            pkg_ids = country.get("countryPackagesIds", [])
            if not country_heb or not pkg_ids:
                continue

            for pid in pkg_ids:
                pkg = pkg_by_id.get(pid)
                if not pkg:
                    continue
                try:
                    gb = float(pkg.get("gigaDataByte", 0))
                    days = int(pkg.get("validityPeriodDays", 30))
                    price_usd = float(pkg.get("price", 0))
                except (ValueError, TypeError):
                    continue
                if gb <= 0 or price_usd <= 0:
                    continue

                price_ils = round(price_usd * usd_rate, 2)
                plan_name = f"{country_heb} \u2013 {int(gb)}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(_make_global_plan(
                    "tuki", plan_name, price_ils, "USD", price_usd,
                    data_gb=gb, days=days, esim=True, extras=[country_heb]
                ))

        logger.info(f"Tuki local: {len(all_plans)} per-country plans from {len(countries)} countries")
    except Exception as e:
        logger.error(f"Tuki local API failed: {e}", exc_info=True)

    return all_plans


# ── Sparks Travel eSIM ──────────────────────────────────────────────────

SPARKS_REGIONS = {
    "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4": {  # אירופה (was אירופה+)
        (1, 60): 3.40, (2, 60): 5.00, (3, 60): 6.50, (5, 60): 8.60,
        (10, 60): 14.70, (15, 60): 21.80, (30, 90): 42.60, (50, 120): 68.30,
    },
    "\u05e9\u05d5\u05d5\u05d9\u05e5+": {  # שוויץ+
        (1, 60): 3.40, (2, 60): 4.20, (3, 60): 4.90, (5, 60): 6.30,
        (10, 60): 9.80, (15, 60): 14.40, (30, 90): 28.30, (50, 120): 46.80,
    },
    "\u05d2\u05d5\u05d5\u05d3\u05dc\u05d5\u05e4": {  # גוודלופ
        (1, 60): 8.50, (2, 60): 10.80, (3, 60): 12.80, (5, 60): 16.90,
        (10, 60): 30.50, (15, 60): 45.10, (30, 90): 89.60, (50, 120): 149.40,
    },
    "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df+": {  # קפריסין+
        (1, 60): 8.50, (2, 60): 10.80, (3, 60): 12.80, (5, 60): 16.90,
        (10, 60): 30.50, (15, 60): 45.10, (30, 90): 89.60, (50, 120): 149.40,
    },
}


SPARKS_COUNTRY_TO_HEBREW_EXTRA = {
    "united-states": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "united-kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "south-korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "south-africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "hong-kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "new-zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "sri-lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "costa-rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "dominican-republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "el-salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "burkina-faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "saudi-arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "trinidad-and-tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "czech-republic": "\u05e6'\u05db\u05d9\u05d4",
    "ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "papua-new-guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "north-macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "cape-verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "guinea-bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "united-arab-emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "bosnia-and-herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    # VOYE-specific names
    "russian-federation": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "macao-china": "\u05de\u05e7\u05d0\u05d5",
    "congo-dem.-rep": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea",
    "congo-democratic-rep": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea",
    "congo-republic": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "french-west-indies": "\u05d4\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05d9\u05dd",
    "cruise": "\u05e7\u05e8\u05d5\u05d6 \u05d1\u05e1\u05e4\u05d9\u05e0\u05d4",
    "uae": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "uk": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "usa": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "caribbean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "global": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "saint-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "st.-vincent-and-the-grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "cote-d'ivoire-ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "cote-divoire-ivory-coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "st.-martin-and-st.-barth-guadeloupe": "\u05e1\u05df \u05de\u05e8\u05d8\u05df \u05d5\u05d2\u05d5\u05d5\u05d3\u05dc\u05d5\u05e4",
}


def scrape_sparks_global(_page=None, usd_rate=None):
    """Scrape Sparks Travel eSIM plans \u2014 regional (hardcoded) + per-country (API)."""
    import urllib.request, json as _json

    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    all_plans = []

    # 1. Regional plans (hardcoded)
    for region_heb, plans_data in SPARKS_REGIONS.items():
        for (gb, days), price_usd in plans_data.items():
            price_ils = round(price_usd * usd_rate, 2)
            plan_name = f"{region_heb} \u2013 {gb}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
            all_plans.append(_make_global_plan(
                "sparks", plan_name, price_ils, "USD", price_usd,
                data_gb=gb, days=days, esim=True, extras=[region_heb]
            ))

    # 2. Per-country plans via API
    try:
        import os
        data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sparks_travel_data.json")
        if os.path.exists(data_file):
            with open(data_file, encoding="utf-8") as f:
                data = _json.load(f)

            for country in data.get("countries", []):
                country_name = country.get("country_name", "")
                # Convert to Hebrew using slug
                slug = country_name.lower().replace(" ", "-")
                country_heb = SAILY_SLUG_TO_HEBREW.get(slug)
                if not country_heb:
                    country_heb = SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(slug, country_name)

                for plan in country.get("plans", []):
                    gb = plan.get("data_gb")
                    days = plan.get("validity_days", 60)
                    price_usd = plan.get("price_usd")
                    if not gb or not price_usd:
                        continue
                    price_ils = round(price_usd * usd_rate, 2)
                    plan_name = f"{country_heb} \u2013 {int(gb)}GB \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                    all_plans.append(_make_global_plan(
                        "sparks", plan_name, price_ils, "USD", price_usd,
                        data_gb=gb, days=days, esim=True, extras=[country_heb]
                    ))
        else:
            logger.warning("Sparks data file not found \u2014 only regional plans available")
    except Exception as e:
        logger.warning(f"Sparks per-country: {e}")

    logger.info(f"Sparks global: {len(all_plans)} plans")
    return all_plans


VOYE_REGION_MAP = {
    "asia": "\u05d0\u05e1\u05d9\u05d4",
    "europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "latin-america": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "middle-east": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "north-america": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
}


def scrape_voye_global(_page=None, usd_rate=None):
    """Scrape VOYE global eSIM plans via WooCommerce Store API."""
    import urllib.request, json as _json, html as _html

    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    all_plans = []
    page_num = 1
    while True:
        url = f"https://voyeglobal.com/wp-json/wc/store/v1/products?per_page=100&page={page_num}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                products = _json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"VOYE page {page_num}: {e}")
            break

        if not products:
            break

        for prod in products:
            name = _html.unescape(prod.get("name", ""))
            # Price in cents
            price_raw = prod.get("prices", {}).get("price")
            if not price_raw:
                continue
            try:
                price_usd = int(price_raw) / 100
                if price_usd <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            cats_list = [c.get("slug", "") for c in prod.get("categories", [])]
            # Skip "zombie" products with no categories — these are old products VOYE
            # removed from the public site but the WooCommerce Store API still exposes.
            # They cause stale duplicates (e.g. an old "Europe 30 days 10GB @ $25" overwrites
            # the current "Europe 30 days 10GB @ $19" via shared plan_name).
            if not cats_list:
                continue

            # Parse data — GB (incl. decimals like 1.5GB), MB (e.g. 500MB → fraction of GB),
            # or "Unlimited" (3GB/day high-speed + unlimited throttled)
            gb_match = re.search(r"(\d+(?:\.\d+)?)\s*GB", name, re.IGNORECASE)
            mb_match = re.search(r"(\d+(?:\.\d+)?)\s*MB(?![/a-z])", name, re.IGNORECASE)
            is_unlimited = "unlimited" in name.lower()
            if gb_match:
                gb_val = float(gb_match.group(1))
                data_gb = int(gb_val) if gb_val == int(gb_val) else gb_val
            elif mb_match:
                # CLAUDE.md convention: MB stored as fraction of GB (X / 1024)
                data_gb = round(float(mb_match.group(1)) / 1024, 4)
            elif is_unlimited:
                data_gb = None  # will be stored as unlimited
            else:
                continue  # skip plans without GB info

            # Parse days
            days_match = re.search(r"(\d+)\s*Days?", name, re.IGNORECASE)
            days = int(days_match.group(1)) if days_match else None

            # Parse minutes
            min_match = re.search(r"(\d+)\s*[Mm]in", name)
            minutes = int(min_match.group(1)) if min_match else None

            # Parse SMS
            sms_match = re.search(r"(\d+)\s*SMS", name, re.IGNORECASE)
            sms = int(sms_match.group(1)) if sms_match else None

            # Determine type from categories
            categories = [c.get("slug", "") for c in prod.get("categories", [])]
            plan_type = "country"  # default
            dest_heb = None

            for cat_slug in categories:
                if cat_slug == "global":
                    plan_type = "global"
                    dest_heb = "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9"
                    break
                if cat_slug in VOYE_REGION_MAP:
                    plan_type = "regional"
                    dest_heb = VOYE_REGION_MAP[cat_slug]
                    break

            # Check if it's a Global Light plan (name starts with "Global Light")
            if name.startswith("Global Light") or name.startswith("Global Voice"):
                plan_type = "global"
                dest_heb = "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9"

            if plan_type == "country":
                # Find country slug from categories (not region/global)
                skip_cats = {"global", "global-voice", "uncategorized", "esim", "e-sim",
                             "data-plans", "unlimited", "data-with-calls", "cruise"}
                for cat_slug in categories:
                    if cat_slug in skip_cats:
                        continue
                    if cat_slug in VOYE_REGION_MAP:
                        continue
                    # Try to convert slug to Hebrew
                    country_heb = SAILY_SLUG_TO_HEBREW.get(cat_slug)
                    if not country_heb:
                        country_heb = SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(cat_slug)
                    if country_heb:
                        dest_heb = country_heb
                        break
                if not dest_heb:
                    # Fallback: parse country from product name before "N Days" pattern
                    fallback = re.match(r"^(.+?)\s+\d+\s*[Dd]ays?", name)
                    if not fallback:
                        fallback = re.match(r"^([A-Za-z\s\-\.\'\(\)]+?)(?:\s*\d)", name)
                    if fallback:
                        raw = fallback.group(1).strip().rstrip("-– ")
                        slug = raw.lower().replace(" ", "-").replace("(", "").replace(")", "").rstrip("-")
                        dest_heb = SAILY_SLUG_TO_HEBREW.get(slug)
                        if not dest_heb:
                            dest_heb = SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(slug)
                        if not dest_heb:
                            # Try simpler slug variants
                            for variant in [slug.split("-")[0], slug.replace("'", "")]:
                                dest_heb = SAILY_SLUG_TO_HEBREW.get(variant) or SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(variant)
                                if dest_heb: break
                        if not dest_heb:
                            dest_heb = VOYE_REGION_MAP.get(slug)  # e.g. north-america → צפון אמריקה
                        if not dest_heb:
                            dest_heb = raw  # keep English as last resort

            if not dest_heb:
                dest_heb = name  # last resort

            price_ils = round(price_usd * usd_rate, 2)

            # Build plan name and extras
            plan_extras = [dest_heb]
            if is_unlimited:
                # Daily limit varies by country
                _VOYE_15GB_COUNTRIES = {
                    "turkey", "canada", "brazil", "argentina",
                    "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4", "\u05e7\u05e0\u05d3\u05d4", "\u05d1\u05e8\u05d6\u05d9\u05dc", "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
                }
                _VOYE_2GB_COUNTRIES = {
                    "mexico", "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
                }
                # Check country slug from categories
                country_slug_lower = ""
                for cs in cats_list:
                    if cs not in ("global", "global-voice", "uncategorized", "esim", "e-sim",
                                  "data-plans", "unlimited", "data-with-calls", "cruise",
                                  "asia", "europe", "latin-america", "middle-east", "north-america", "regional"):
                        country_slug_lower = cs
                        break

                if country_slug_lower in _VOYE_2GB_COUNTRIES or (dest_heb and dest_heb in _VOYE_2GB_COUNTRIES):
                    daily_gb = "2"
                elif country_slug_lower in _VOYE_15GB_COUNTRIES or (dest_heb and dest_heb in _VOYE_15GB_COUNTRIES):
                    daily_gb = "1.5"
                else:
                    daily_gb = "3"

                gb_str = f"{daily_gb}GB/\u05d9\u05d5\u05dd"  # XGB/יום
                plan_extras.append(f"\u05e2\u05d3 {daily_gb}GB \u05d1\u05de\u05d4\u05d9\u05e8\u05d5\u05ea \u05d2\u05d1\u05d5\u05d4\u05d4 \u05dc\u05d9\u05d5\u05dd. \u05dc\u05d0\u05d7\u05e8 \u05de\u05db\u05df \u05d4\u05de\u05d4\u05d9\u05e8\u05d5\u05ea \u05de\u05d5\u05d0\u05d8\u05ea, \u05d0\u05da \u05ea\u05d5\u05de\u05da \u05d1\u05e4\u05d5\u05e0\u05e7\u05e6\u05d9\u05d5\u05ea \u05d1\u05e1\u05d9\u05e1\u05d9\u05d5\u05ea. \u05d4\u05de\u05db\u05e1\u05d4 \u05de\u05ea\u05d0\u05e4\u05e1\u05ea \u05de\u05d3\u05d9 \u05d9\u05d5\u05dd.")
            else:
                if data_gb is None:
                    gb_str = ""
                elif data_gb < 1:
                    gb_str = f"{round(data_gb * 1024)}MB"
                else:
                    gb_str = f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb}GB"

            days_str = f"{days} \u05d9\u05de\u05d9\u05dd" if days else ""
            plan_name = f"{dest_heb} \u2013 {gb_str}"
            if days_str:
                plan_name += f" \u2013 {days_str}"

            all_plans.append(_make_global_plan(
                "voye", plan_name, price_ils, "USD", price_usd,
                data_gb=data_gb, days=days, minutes=minutes, sms=sms,
                esim=True, extras=plan_extras
            ))

        page_num += 1
        if len(products) < 100:
            break

    logger.info(f"VOYE global: {len(all_plans)} plans")
    return all_plans


# ── Orbit Mobile ──────────────────────────────────────────────────────────

ORBIT_NAME_TO_HEBREW = {
    "Afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "Albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Anguilla": "\u05d0\u05e0\u05d2\u05d9\u05dc\u05d4",
    "Antigua And Barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "Argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "Armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "Aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "Australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "Austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "Azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "Bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "Bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "Bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "Barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "Belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "Belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "Belize": "\u05d1\u05dc\u05d9\u05d6",
    "Benin": "\u05d1\u05e0\u05d9\u05df",
    "Bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "Bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Bosnia And Herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Botswana": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4",
    "Brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "British Virgin Islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Burkina Faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "Canada": "\u05e7\u05e0\u05d3\u05d4",
    "Cape Verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "Cayman Islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Central African Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Chad": "\u05e6'\u05d0\u05d3",
    "Chile": "\u05e6'\u05d9\u05dc\u05d4",
    "China": "\u05e1\u05d9\u05df",
    "Colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Congo": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "Costa Rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Cuba": "\u05e7\u05d5\u05d1\u05d4",
    "Curacao": "\u05e7\u05d5\u05e8\u05e1\u05d0\u05d5",
    "Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Czech Republic": "\u05e6'\u05db\u05d9\u05d4",
    "Democratic Republic Of The Congo": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea",
    "Denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "Dominican Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "East Timor": "\u05de\u05d6\u05e8\u05d7 \u05d8\u05d9\u05de\u05d5\u05e8",
    "Ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "El Salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "Estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9",
    "Ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Faroe Islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "Finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "France": "\u05e6\u05e8\u05e4\u05ea",
    "French Guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Gabon": "\u05d2\u05d1\u05d5\u05df",
    "Gambia": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "Georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "Germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "Ghana": "\u05d2\u05d0\u05e0\u05d4",
    "Gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "Greece": "\u05d9\u05d5\u05d5\u05df",
    "Greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "Guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "Guam": "\u05d2\u05d5\u05d0\u05dd",
    "Guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "Guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "Guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "Guinea-Bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "Guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "Haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "Honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "Hong Kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "Hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "Iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "India": "\u05d4\u05d5\u05d3\u05d5",
    "Indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "Iran": "\u05d0\u05d9\u05e8\u05df",
    "Iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "Ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Isle of Man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Ivory Coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Japan": "\u05d9\u05e4\u05df",
    "Jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "Jordan": "\u05d9\u05e8\u05d3\u05df",
    "Kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Kenya": "\u05e7\u05e0\u05d9\u05d4",
    "Kosovo": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "Kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "Kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Laos": "\u05dc\u05d0\u05d5\u05e1",
    "Latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "Liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "Luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "Madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Mali": "\u05de\u05d0\u05dc\u05d9",
    "Malta": "\u05de\u05dc\u05d8\u05d4",
    "Martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "Mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "Mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "Mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "Moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "Monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "Mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "Montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "Montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "Morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "Nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "Nepal": "\u05e0\u05e4\u05d0\u05dc",
    "Netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "Netherlands Antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "New Zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Niger": "\u05e0\u05d9\u05d2'\u05e8",
    "Nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "Norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "Oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "Pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "Palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "Panama": "\u05e4\u05e0\u05de\u05d4",
    "Papua New Guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Peru": "\u05e4\u05e8\u05d5",
    "Philippines": "\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Puerto Rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "Qatar": "\u05e7\u05d8\u05e8",
    "Reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Russia": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "Rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Saint Kitts And Nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d1\u05d9\u05e1",
    "Saint Lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Saint Vincent And The Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "San Marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "Saudi Arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Senegal": "\u05e1\u05e0\u05d2\u05dc",
    "Serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Sierra Leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "Singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Sint Maarten": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "Slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "South Africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "South Korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "South Sudan": "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "Spain": "\u05e1\u05e4\u05e8\u05d3",
    "Sri Lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Sudan": "\u05e1\u05d5\u05d3\u05df",
    "Suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Togo": "\u05d8\u05d5\u05d2\u05d5",
    "Tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Trinidad And Tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "Turks And Caicos Islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טורקס וקאיקוס
    "Uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "United Arab Emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "United Kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "United States": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "United States Virgin Islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",  # איי הבתולה (ארה"ב)
    "Uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}

ORBIT_ZONE_TO_HEBREW = {
    1: "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",                           # אירופה
    2: "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",                           # גלובלי
    3: "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",                           # אפריקה
    4: "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",  # המזרח התיכון וצפון אפריקה
    5: "\u05d0\u05e1\u05d9\u05d4",                                        # אסיה
    7: "\u05e6\u05e4\u05d5\u05df \u05d5\u05d3\u05e8\u05d5\u05dd \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",  # צפון ודרום אמריקה
    17: "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9 \u05e4\u05dc\u05d5\u05e1",  # גלובלי פלוס
    18: "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",  # צפון אמריקה
    19: "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",  # אמריקה הלטינית
}

def scrape_orbit_global(_page=None, usd_rate=None):
    """Scrape Orbit Mobile eSIM plans via their REST API (no browser needed)."""
    import requests as _req
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    all_plans = []
    headers = {
        "companycode": "Web",
        "accept-language": "en",
        "app-version": "1.2",
        "accept": "application/json",
        "apikey": "HzN1buVkKZQfjRhkUy3hFFMif3nTTPE7JEp8ddDv0BQunnJFAq",
        "operatingsystem": "web",
    }
    base = "https://be.orbitmobile.com"

    try:
        # ── Per-country plans ─────────────────────────────────────
        countries_resp = _req.get(f"{base}/plans/countries", headers=headers, timeout=20)
        countries = countries_resp.json().get("countries", [])

        for country in countries:
            cc = country.get("countryCode", "")
            en_name = country.get("countryName", "")
            heb_name = ORBIT_NAME_TO_HEBREW.get(en_name, "")
            if not heb_name or not cc:
                continue
            try:
                plans_resp = _req.get(f"{base}/plans", params={"countryCode": cc}, headers=headers, timeout=15)
                esim_plans = plans_resp.json().get("esimPlans", [])
            except Exception:
                continue

            for plan in esim_plans:
                try:
                    gb = float(plan.get("dataAllowance", 0))
                    days = int(plan.get("validity", 30))
                    prices = plan.get("prices", [])
                    if not prices:
                        continue
                    p = prices[0]
                    price_usd = p.get("discountedCost") or p.get("cost", 0)
                    original_usd = p.get("cost", price_usd)
                    if not price_usd or price_usd <= 0 or gb <= 0:
                        continue
                except (ValueError, TypeError):
                    continue

                price_ils = round(float(price_usd) * usd_rate, 2)
                gb_str = f"{int(gb)}GB" if gb >= 1 else f"{round(gb * 1024)}MB"
                plan_name = f"{heb_name} - {gb_str} - {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(_make_global_plan(
                    "orbit", plan_name, price_ils, "USD", float(original_usd),
                    data_gb=gb, days=days, esim=True, extras=[heb_name]
                ))

        logger.info(f"Orbit countries: {len(all_plans)} plans from {len(countries)} countries")

        # ── Regional / Zone plans ─────────────────────────────────
        zone_count = 0
        try:
            zones_resp = _req.get(f"{base}/plans/zones/custom", headers=headers, timeout=20)
            zones = zones_resp.json().get("zones", [])
        except Exception:
            zones = []

        for zone in zones:
            zone_id = zone.get("zoneId")
            zone_name_en = zone.get("zoneName", "")
            zone_heb = ORBIT_ZONE_TO_HEBREW.get(zone_id, zone_name_en)
            zone_countries = zone.get("countries", [])
            zone_countries_heb = [ORBIT_NAME_TO_HEBREW.get(c.get("countryName", ""), c.get("countryName", "")) for c in zone_countries]

            try:
                zp_resp = _req.get(f"{base}/plans", params={"customZoneId": zone_id}, headers=headers, timeout=15)
                esim_plans = zp_resp.json().get("esimPlans", [])
            except Exception:
                continue

            for plan in esim_plans:
                try:
                    gb = float(plan.get("dataAllowance", 0))
                    days = int(plan.get("validity", 30))
                    prices = plan.get("prices", [])
                    if not prices:
                        continue
                    p = prices[0]
                    price_usd = p.get("discountedCost") or p.get("cost", 0)
                    original_usd = p.get("cost", price_usd)
                    if not price_usd or price_usd <= 0 or gb <= 0:
                        continue
                except (ValueError, TypeError):
                    continue

                price_ils = round(float(price_usd) * usd_rate, 2)
                gb_str = f"{int(gb)}GB" if gb >= 1 else f"{round(gb * 1024)}MB"
                plan_name = f"{zone_heb} - {gb_str} - {days} \u05d9\u05de\u05d9\u05dd"
                # Unify "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9 \u05e4\u05dc\u05d5\u05e1" under canonical "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9" region (qualifier remains in plan_name)
                region_for_extras = "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9" if zone_id == 17 else zone_heb
                all_plans.append(_make_global_plan(
                    "orbit", plan_name, price_ils, "USD", float(original_usd),
                    data_gb=gb, days=days, esim=True, extras=[region_for_extras] + zone_countries_heb
                ))
                zone_count += 1

        logger.info(f"Orbit zones: {zone_count} plans from {len(zones)} zones")
        logger.info(f"Orbit total: {len(all_plans)} plans")
    except Exception as e:
        logger.error(f"Orbit global failed: {e}", exc_info=True)

    return all_plans


def scrape_travelsim(page=None):
    """Travel Sim \u2014 static global eSIM plans (travelsimobile.co.il).
    10 plans across 3 zones (no Playwright needed).
    """
    plans = [
        # \u2500\u2500 Zone 123: Global (144 countries) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        _make_global_plan(
            "travelsim", "Travel Mini", 19, "ILS", 19,
            data_gb=1, days=4, minutes=None, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Lite", 59, "ILS", 59,
            data_gb=6, days=7, minutes=15, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Plus", 69, "ILS", 69,
            data_gb=7, days=14, minutes=30, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Max", 99, "ILS", 99,
            data_gb=20, days=30, minutes=100, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Ultra", 139, "ILS", 139,
            data_gb=30, days=45, minutes=30, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Long", 49, "ILS", 49,
            data_gb=1, days=1095, minutes=None, sms=None, esim=True,
            extras=["", "\u05d9\u05ea\u05e8\u05d4 \u05e0\u05e9\u05de\u05e8\u05ea \u05dc\u05e0\u05e1\u05d9\u05e2\u05d5\u05ea \u05d4\u05d1\u05d0\u05d5\u05ea"]  # extras[0]="" = no destination, extras[1] = feature
        ),
        # \u2500\u2500 Zone 1: \u05d0\u05e8\u05d4"\u05d1 / \u05e7\u05e0\u05d3\u05d4 / \u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea (3 countries) \u2500\u2500\u2500\u2500\u2500
        _make_global_plan(
            "travelsim", "Travel USA 30GB", 89, "ILS", 89,
            data_gb=30, days=14, minutes=30, sms=None, esim=True,
            extras=["\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea"]
        ),
        _make_global_plan(
            "travelsim", "Travel USA 70GB", 99, "ILS", 99,
            data_gb=70, days=30, minutes=100, sms=None, esim=True,
            extras=["\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea"]
        ),
        # \u2500\u2500 Zone 6: \u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df (5 countries) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        _make_global_plan(
            "travelsim", "Middle East 1GB", 89, "ILS", 89,
            data_gb=1, days=30, minutes=None, sms=None, esim=True,
            extras=["\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df"]
        ),
        _make_global_plan(
            "travelsim", "Middle East 5GB", 189, "ILS", 189,
            data_gb=5, days=30, minutes=None, sms=None, esim=True,
            extras=["\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df"]
        ),
    ]
    logger.info(f"Travel Sim: {len(plans)} plans")
    return plans


# ── GoMoWorld eSIM ──────────────────────────────────────────────────────────
GOMOWORLD_SLUG_TO_HEBREW = {
    # ─── Countries ───────────────────────────────────────────────────────────
    "Afghanistan":                      "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "Albania":                          "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Algeria":                          "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Andorra":                          "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Angola":                           "\u05d0\u05e0\u05d2\u05d5\u05dc\u05d4",
    "Anguilla":                         "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "Antigua_and_Barbuda":              "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "Argentina":                        "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "Armenia":                          "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "Australia":                        "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "Austria":                          "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "Azerbaijan":                       "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "Bahamas":                          "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "Bahrain":                          "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "Bangladesh":                       "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "Barbados":                         "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "Belarus":                          "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "Belgium":                          "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "Belize":                           "\u05d1\u05dc\u05d9\u05d6",
    "Benin":                            "\u05d1\u05e0\u05d9\u05df",
    "Bermuda":                          "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "Bhutan":                           "\u05d1\u05d4\u05d5\u05d8\u05df",
    "Bolivia":                          "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Bosnia_and_Herzegovina":           "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Botswana":                         "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "Brazil":                           "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "British_Virgin_Islands":           "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Brunei":                           "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Bulgaria":                         "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Burkina_Faso":                     "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Cambodia":                         "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Cameroon":                         "\u05e7\u05de\u05e8\u05d5\u05df",
    "Canada":                           "\u05e7\u05e0\u05d3\u05d4",
    "Cape_Verde":                       "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "Cayman_Islands":                   "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Central_African_Republic":         "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Chad":                             "\u05e6'\u05d0\u05d3",
    "Chile":                            "\u05e6'\u05d9\u05dc\u05d4",
    "China":                            "\u05e1\u05d9\u05df",
    "Colombia":                         "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Comoros":                          "\u05e7\u05d5\u05de\u05d5\u05e8\u05d5",
    "Costa_Rica":                       "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Croatia":                          "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Cyprus":                           "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Czech_Republic":                   "\u05e6'\u05db\u05d9\u05d4",
    "Democratic_Republic_of_the_Congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Denmark":                          "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Dominica":                         "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "Dominican_Republic":               "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "Ecuador":                          "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Egypt":                            "\u05de\u05e6\u05e8\u05d9\u05dd",
    "El_Salvador":                      "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "Estonia":                          "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Ethiopia":                         "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Faroe_Islands":                    "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Fiji":                             "\u05e4\u05d9\u05d2'\u05d9",
    "Finland":                          "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "France":                           "\u05e6\u05e8\u05e4\u05ea",
    "French_Polynesia":                 "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Gabon":                            "\u05d2\u05d0\u05d1\u05d5\u05df",
    "Gambia":                           "\u05d2\u05de\u05d1\u05d9\u05d4",
    "Georgia":                          "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "Germany":                          "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "Ghana":                            "\u05d2\u05d0\u05e0\u05d4",
    "Gibraltar":                        "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "Greece":                           "\u05d9\u05d5\u05d5\u05df",
    "Greenland":                        "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Grenada":                          "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "Guam":                             "\u05d2\u05d5\u05d0\u05dd",
    "Guatemala":                        "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "Guernsey":                         "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "Guinea":                           "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "Guinea-Bissau":                    "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "Haiti":                            "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "Honduras":                         "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "Hong_Kong":                        "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "Hungary":                          "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "Iceland":                          "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "India":                            "\u05d4\u05d5\u05d3\u05d5",
    "Indonesia":                        "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "Iraq":                             "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "Ireland":                          "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Isle_of_Man":                      "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Israel":                           "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "Italy":                            "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Ivory_Coast":                      "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Jamaica":                          "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Japan":                            "\u05d9\u05e4\u05df",
    "Jersey":                           "\u05d2'\u05e8\u05d6\u05d9",
    "Jordan":                           "\u05d9\u05e8\u05d3\u05df",
    "Kazakhstan":                       "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Kenya":                            "\u05e7\u05e0\u05d9\u05d4",
    "Kiribati":                         "\u05e7\u05d9\u05e8\u05d9\u05d1\u05d0\u05d8\u05d9",
    "Korea":                            "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "Kosovo":                           "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "Kuwait":                           "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "Kyrgyzstan":                       "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Laos":                             "\u05dc\u05d0\u05d5\u05e1",
    "Latvia":                           "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Liberia":                          "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Libya":                            "\u05dc\u05d5\u05d1",
    "Liechtenstein":                    "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Lithuania":                        "\u05dc\u05d9\u05d8\u05d0",
    "Luxembourg":                       "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Macao":                            "\u05de\u05e7\u05d0\u05d5",
    "Madagascar":                       "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Malawi":                           "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Malaysia":                         "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Maldives":                         "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "Mali":                             "\u05de\u05d0\u05dc\u05d9",
    "Malta":                            "\u05de\u05dc\u05d8\u05d4",
    "Mauritania":                       "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Mauritius":                        "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "Mayotte":                          "\u05de\u05d0\u05d9\u05d5\u05d8",
    "Mexico":                           "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "Moldova":                          "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "Monaco":                           "\u05de\u05d5\u05e0\u05e7\u05d5",
    "Mongolia":                         "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "Montenegro":                       "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "Montserrat":                       "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "Morocco":                          "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Mozambique":                       "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Nepal":                            "\u05e0\u05e4\u05d0\u05dc",
    "Netherlands":                      "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "New_Zealand":                      "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Nicaragua":                        "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Niger":                            "\u05e0\u05d9\u05d2'\u05e8",
    "Nigeria":                          "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "North_Macedonia":                  "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "Norway":                           "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "Oman":                             "\u05e2\u05d5\u05de\u05df",
    "Pakistan":                         "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "Palau":                            "\u05e4\u05d0\u05dc\u05d0\u05d5",
    "Panama":                           "\u05e4\u05e0\u05de\u05d4",
    "Papua_New_Guinea":                 "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Paraguay":                         "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Peru":                             "\u05e4\u05e8\u05d5",
    "Philippines":                      "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Poland":                           "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Portugal":                         "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Puerto_Rico":                      "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "Qatar":                            "\u05e7\u05d8\u05e8",
    "Republic_of_the_Congo":            "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Reunion":                          "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Romania":                          "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Russia":                           "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "Rwanda":                           "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Saint_Kitts_and_Nevis":            "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "Saint_Lucia":                      "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Saint_Vincent_and_the_Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Samoa":                            "\u05e1\u05de\u05d5\u05d0\u05d4",
    "San_Marino":                       "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "Saudi_Arabia":                     "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Senegal":                          "\u05e1\u05e0\u05d2\u05dc",
    "Serbia":                           "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Seychelles":                       "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Sierra_Leone":                     "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "Singapore":                        "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Slovakia":                         "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Slovenia":                         "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "Solomon_Island":                   "\u05d0\u05d9\u05d9 \u05e9\u05dc\u05de\u05d4",
    "South_Africa":                     "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "South_Sudan":                      "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "Spain":                            "\u05e1\u05e4\u05e8\u05d3",
    "Sri_Lanka":                        "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Suriname":                         "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Swaziland":                        "\u05d0\u05e1\u05d5\u05d0\u05d5\u05d8\u05d9\u05e0\u05d9",
    "Sweden":                           "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Switzerland":                      "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Taiwan":                           "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Tajikistan":                       "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Tanzania":                         "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Thailand":                         "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Timor-Leste":                      "\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4",
    "Togo":                             "\u05d8\u05d5\u05d2\u05d5",
    "Tonga":                            "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Trinidad_and_Tobago":              "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Tunisia":                          "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Turkey":                           "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "Turks_and_Caicos_Islands":         "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "Uganda":                           "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Ukraine":                          "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "United_Arab_Emirates":             "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "United_Kingdom":                   "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "United_States":                    "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "Uruguay":                          "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Uzbekistan":                       "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu":                          "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Venezuela":                        "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "Viet_Nam":                         "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Yemen":                            "\u05ea\u05d9\u05de\u05df",
    "Zambia":                           "\u05d6\u05de\u05d1\u05d9\u05d4",
    # ─── Zones / Regions ─────────────────────────────────────────────────────
    "Channel_Islands":                  "\u05d0\u05d9\u05d9 \u05d4\u05ea\u05e2\u05dc\u05d4",
    "Europe":                           "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "French_Antilles":                  "\u05d4\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05d9\u05dd",
    "Latin_America":                    "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "Netherlands_Antilles":             "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "North_America":                    "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "South_East_Asia":                  "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
}


_GOMO_SYMBOL_CCY = {"\u20aa": "ILS", "\u00a3": "GBP", "$": "USD", "\u20ac": "EUR"}


def _parse_gomoworld_plans(body, country_heb, gbp_rate, usd_rate=None, eur_rate=None):
    """Parse plan blocks from a GoMoWorld destination page body text.

    Currency-aware (2026-09-03): the site geo-prices per visitor and flips the
    quoted currency between GBP / USD / ILS from run to run (cookie
    `gmw_currency`), while this parser used to treat every number as GBP -
    8,600 phantom price_change rows (x1.26 / x3.7 swings) since 2026-07-10.
    `scrape_gomoworld_global` now pins the cookie to ILS, and the symbol in the
    price line decides the conversion here as a safety net: ILS is stored as-is
    (they are fixed x.99 price points, not FX-converted), other symbols are
    converted with the matching rate and logged.
    """
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    # Find start after "Compatible smartphones"
    start = -1
    for i, l in enumerate(lines):
        if l == 'Compatible smartphones':
            start = i + 1
            break
    if start == -1:
        return []
    # Find end
    end = len(lines)
    for i, l in enumerate(lines[start:], start):
        if 'face issues' in l or 'unable to activate' in l or 'encounter issues' in l or 'Confirm,' in l:
            end = i
            break
    plan_lines = lines[start:end]
    plans = []
    warned = set()
    i = 0
    while i < len(plan_lines):
        line = plan_lines[i]
        # GB line: e.g. "35GB" or "90GB75GB" (PROMO = concatenated)
        m_gb = re.match(r'^(\d+(?:\.\d+)?)GB', line)
        if m_gb and i + 2 < len(plan_lines):
            gb = float(m_gb.group(1))
            # Next line: "X-day plan"
            m_day = re.match(r'^(\d+)-day plan$', plan_lines[i + 1])
            if m_day:
                days = int(m_day.group(1))
                # Next line: price with currency symbol + number, e.g. "₪109.99" / "£29.99"
                price_line = plan_lines[i + 2]
                m_price = re.search(r'([\u20aa\u00a3$\u20ac])\s*(\d+(?:\.\d+)?)', price_line)
                if m_price:
                    sym, price_orig = m_price.group(1), float(m_price.group(2))
                    ccy = _GOMO_SYMBOL_CCY[sym]
                    if ccy == "ILS":
                        price_ils = round(price_orig, 2)
                    else:
                        if ccy not in warned:
                            warned.add(ccy)
                            logger.warning(f"GoMoWorld {country_heb}: page quoted {ccy}, not ILS - converting")
                        if ccy == "GBP":
                            rate = gbp_rate
                        elif ccy == "USD":
                            rate = usd_rate or _get_usd_to_ils()
                        else:
                            rate = eur_rate or _get_eur_to_ils()
                        price_ils = round(price_orig * rate, 2)
                    gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
                    plan_name = f"{country_heb} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                    plans.append(_make_global_plan(
                        "gomoworld", plan_name, price_ils, ccy, price_orig,
                        data_gb=gb, days=days, esim=True, extras=[country_heb]
                    ))
                    i += 3
                    continue
        i += 1
    return plans


def scrape_gomoworld_global(_page=None, gbp_rate=None):
    """Scrape GoMoWorld eSIM per-country and regional plans.

    Prices are read in ILS: the `gmw_currency` cookie is pinned to ILS on the
    browser context so the quoted currency no longer depends on geo-detection
    (see `_parse_gomoworld_plans`). `gbp_rate` is only used as the fallback
    conversion if a page still comes back in GBP.
    """
    if gbp_rate is None:
        gbp_rate = _get_gbp_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    all_plans = []
    success_count = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(user_agent=ua)
        context.add_cookies([{
            "name": "gmw_currency", "value": "ILS",
            "domain": ".gomoworld.com", "path": "/",
        }])
        page = context.new_page()
        for slug, country_heb in GOMOWORLD_SLUG_TO_HEBREW.items():
            try:
                page.goto(
                    f"https://www.gomoworld.com/en/destinations/{slug}",
                    timeout=25000, wait_until="domcontentloaded"
                )
                page.wait_for_timeout(1500)
                body = page.inner_text("body")
                plans = _parse_gomoworld_plans(body, country_heb, gbp_rate)
                if plans:
                    all_plans.extend(plans)
                    success_count += 1
                else:
                    logger.warning(f"GoMoWorld {slug}: no plans parsed")
            except Exception as exc:
                logger.warning(f"GoMoWorld {slug}: {exc}")
                continue
        browser.close()
    logger.info(f"GoMoWorld: {len(all_plans)} plans from {success_count}/{len(GOMOWORLD_SLUG_TO_HEBREW)} destinations")
    return all_plans


# ── Tasim eSIM (USA only) ────────────────────────────────────────────────────
def scrape_tasim_global(_page=None, usd_rate=None):
    """Scrape Tasim eSIM — USA voice+data plans (USD pricing).

    Pure HTTP, no Playwright: the homepage purchase form reads
    https://www.tasim.us/api/plans?type=one_time — the same endpoint is the
    source of truth here. one_time = the packages publicly sold on the site
    (15GB / 50GB as of 2026-06); the API also returns 'subscription' plans
    that have no public page, so the type filter excludes them. The one-time
    setup fee (setupCost) is surfaced as an extra, not added to the price —
    the site advertises the package price.

    Plan-name format is kept identical to the legacy single-plan scraper
    ("ארצות הברית – 15GB + שיחות ללא הגבלה – 30 ימים") so the existing row
    keeps its price history.
    """
    import requests
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    try:
        r = requests.get(
            "https://www.tasim.us/api/plans",
            params={"type": "one_time"},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
            timeout=30,
        )
        r.raise_for_status()
        items = (r.json() or {}).get("plans") or []
    except Exception as exc:
        logger.warning(f"Tasim scraper failed: {exc}")
        return []

    country_heb = "ארצות הברית"
    plans = []
    for item in items:
        try:
            price_usd = float(item.get("price"))
            data_gb = float(item.get("gb"))
            days = int(item.get("days"))
            setup_usd = float(item.get("setupCost") or 0)
        except (TypeError, ValueError):
            continue
        if price_usd <= 0 or data_gb <= 0 or days <= 0:
            continue
        price_ils = round(price_usd * usd_rate, 2)
        gb_str = f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb}GB"
        plan_name = f"{country_heb} – {gb_str} + שיחות ללא הגבלה – {days} ימים"
        extras = [
            country_heb,
            'שיחות ללא הגבלה בארה"ב',
            "שיחות לישראל ללא הגבלה",
            "הודעות SMS ללא הגבלה",
            f"אינטרנט {gb_str} (לאחר מכן מהירות יורדת)",
            "רשת T-Mobile (כיסוי מקסימלי)",
            "הפעלה מידית — אין צורך בכרטיס פיזי",
        ]
        if setup_usd > 0:
            setup_str = f"{int(setup_usd)}" if setup_usd == int(setup_usd) else f"{setup_usd}"
            extras.append(f"דמי הקמה חד-פעמיים ${setup_str}")
        plans.append(_make_global_plan(
            "tasim", plan_name, price_ils, "USD", price_usd,
            data_gb=data_gb, days=days, esim=True, extras=extras,
        ))
    logger.info(f"Tasim: {len(plans)} plans")
    return plans


# ── GigSky eSIM ──────────────────────────────────────────────────────────────
# Pure HTTP, no Playwright: GigSky exposes its ENTIRE catalog as one static JSON
# on their CDN (the same file the site's plan picker fetches):
#   https://cdn-prod.gigsky.com/planBundle/...2-plan-bundle-ext.json
# 180 "plan bundles" split by planBundleType into COUNTRY / REGIONAL / WORLD
# (WORLD = the global "World Plan" tiers + the "Cruise + …" packages + ferries).
# Each bundle carries a `plans` array; each plan has dataLimitInKB (0 = unlimited),
# validityPeriodInDays and a `prices` array aligned to currencyCodes — USD is the
# index we bill on. Destinations resolve to canonical Hebrew by reusing the
# existing ESIMO_CODE_TO_HEBREW (ISO alpha-2 → Hebrew) so we don't hand-maintain
# 157 country names; only the handful of multi-code / non-ESIMO bundles need an
# override below.
GIGSKY_PLAN_BUNDLE_URL = (
    "https://cdn-prod.gigsky.com/planBundle/"
    "includeSponsorPlans=false&simType=ACME_GSMA_ESIM_V2&includePlanVariants=true"
    "&lang=en&version=2-plan-bundle-ext.json"
)
# COUNTRY bundles whose countryCodes[0] is NOT the primary country → force the code.
GIGSKY_NAME_TO_CODE = {
    "United States": "US", "Israel": "IL", "Fiji": "FJ",
    "Vanuatu": "VU", "Mayotte": "YT", "Réunion": "RE",
}
# COUNTRY bundles that are not real travel destinations (offshore rigs / inflight) or
# politically redundant (Palestine == Israel coverage on GigSky) → not ingested.
GIGSKY_COUNTRY_SKIP = {
    "North Sea - Offshore", "Gulf of Mexico - Offshore", "Inflight", "Palestine",
}
# Codes GigSky uses that ESIMO_CODE_TO_HEBREW lacks.
GIGSKY_CODE_EXTRA = {
    "AO": "אנגולה",              # Angola
    "PF": "פולינזיה הצרפתית",  # French Polynesia
    "CI": "חוף השנהב",  # Ivory Coast
    "SX": "סינט מארטן",  # Sint Maarten
    "XK": "קוסובו",              # Kosovo
}
GIGSKY_REGION_TO_HEBREW = {
    "Caribbean":        "קריביים",
    "Middle East":      "המזרח התיכון",
    "North America":    "צפון אמריקה",
    "Africa":           "אפריקה",
    "Latin America":    "אמריקה הלטינית",
    "Europe":           "אירופה",
    "Asia Pacific":     "אסיה פסיפיק",
    "Dutch Caribbean":  "האיים הקריביים ההולנדיים",
    "French Caribbean": "האנטילים הצרפתיים",
}
# WORLD bundles → global tiers collapse to "גלובלי"; cruise packages become a
# "קרוז - <region>" label (the "קרוז" prefix drives isCruiseDest + the B2C cruise
# fold, see db._CRUISE_SOURCE_DESTS). Ferries are not ingested (value None).
GIGSKY_WORLD_TO_HEBREW = {
    "World Plan":                   "גלובלי",
    "World Plan Lite":              "גלובלי",
    "Cruise + Americas/Caribbean":  "קרוז - אמריקה וקריביים",
    "Cruise + Asia Pacific":        "קרוז - אסיה פסיפיק",
    "Cruise + Europe":              "קרוז - אירופה",
    "Cruise + World":               "קרוז - עולמי",
    "Cruise + Middle East":         "קרוז - המזרח התיכון",
    "Cruise - At Sea Only":         "קרוז - בים בלבד",
    "European Ferries":             None,
    "Europe Ferries + Land":        None,
}


def _gigsky_dest_hebrew(bundle):
    """Canonical Hebrew destination for a GigSky plan bundle (None → skip)."""
    btype = bundle.get("planBundleType")
    name = bundle.get("planBundleName", "")
    if btype == "REGIONAL":
        return GIGSKY_REGION_TO_HEBREW.get(name)
    if btype == "WORLD":
        return GIGSKY_WORLD_TO_HEBREW.get(name)
    # COUNTRY
    if name in GIGSKY_COUNTRY_SKIP:
        return None
    code = GIGSKY_NAME_TO_CODE.get(name) or (bundle.get("countryCodes") or [None])[0]
    return ESIMO_CODE_TO_HEBREW.get(code) or GIGSKY_CODE_EXTRA.get(code)


def _gigsky_gb_str(data_gb):
    if data_gb is None:
        return "בלתי מוגבל"  # בלתי מוגבל
    if data_gb >= 1:
        return f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb:g}GB"
    return f"{round(data_gb * 1024)}MB"


def scrape_gigsky_global(_page=None, usd_rate=None):
    """Scrape the full GigSky eSIM catalog (countries + regions + global + cruise).

    Pure HTTP — one CDN JSON (GIGSKY_PLAN_BUNDLE_URL) holds every plan bundle.
    Skips free trials (freePlan), the recurring "GigSky One" subscription bundles,
    offshore/inflight/Palestine, and ferry bundles. USD is the billed currency.
    """
    import requests
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    try:
        r = requests.get(
            GIGSKY_PLAN_BUNDLE_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
            timeout=40,
        )
        r.raise_for_status()
        payload = r.json() or {}
    except Exception as exc:
        logger.warning(f"GigSky scraper failed: {exc}")
        return []

    currencies = payload.get("currencyCodes") or []
    try:
        usd_idx = currencies.index("USD")
    except ValueError:
        usd_idx = 5  # BRL,CAD,EUR,GBP,JPY,USD
    unlimited_note = "גלישה יומית ללא הגבלה"  # גלישה יומית ללא הגבלה

    plans, seen = [], set()
    for bundle in payload.get("list") or []:
        if bundle.get("isRecurringPlan"):
            continue
        dest = _gigsky_dest_hebrew(bundle)
        if not dest:
            continue
        for p in bundle.get("plans") or []:
            if p.get("freePlan"):
                continue
            prices = p.get("prices") or []
            usd = prices[usd_idx] if usd_idx < len(prices) else None
            try:
                usd = float(usd)
            except (TypeError, ValueError):
                continue
            if usd <= 0:
                continue
            kb = p.get("dataLimitInKB") or 0
            unlimited = (p.get("chargingType") == "UNLIMITED") or kb == 0
            data_gb = None if unlimited else round(kb / 1048576, 4)
            try:
                days = int(p.get("validityPeriodInDays"))
            except (TypeError, ValueError):
                continue
            g = _gigsky_gb_str(data_gb)
            day_unit = "יום" if days == 1 else "ימים"  # יום / ימים
            plan_name = f"{dest} – {g} – {days} {day_unit}"
            if plan_name in seen:      # guard UNIQUE(carrier, plan_name)
                continue
            seen.add(plan_name)
            extras = [dest]
            if unlimited:
                extras.append(unlimited_note)
            plans.append(_make_global_plan(
                "gigsky", plan_name, round(usd * usd_rate, 2), "USD", usd,
                data_gb=data_gb, days=days, esim=True, extras=extras,
            ))
    logger.info(f"GigSky: {len(plans)} plans")
    return plans


# ── eSIM Genius (esimgenius.ai) ──────────────────────────────────────────────
# Destination slugs that esimgenius.ai has but SAILY_SLUG_TO_HEBREW doesn't
# (sub-national islands, UK nations, and naming variants). Values are the
# canonical Hebrew spellings already used in global_plans / db._DEST_NORM.
ESIMGENIUS_SLUG_OVERRIDES = {
    "aland-islands": "איי אולנד",
    "azores": "האיים האזוריים",
    "balearic-islands": "האיים הבלאריים",
    "belarus": "בלארוס",
    "cabo-verde": "קייפ ורדה",
    "canary-islands": "האיים הקנריים",
    "congo": "רפובליקת קונגו",
    "corfu": "קורפו",
    "crete": "כרתים",
    "cyclades-islands": "האיים הקיקלדיים",
    "democratic-republic-congo": "הרפובליקה הדמוקרטית של קונגו",
    "ethiopia": "אתיופיה",
    "ivory-coast": "חוף השנהב",
    "madeira": "מדיירה",
    "rhodes": "רודוס",
    "saint-pierre-miquelon": "סן פייר ומיקלון",
    "sardinia": "סרדיניה",
    "scotland": "סקוטלנד",
    "sicily": "סיציליה",
    "usa": "ארצות הברית",
    "vatican": "ותיקן",
    "wales": "ויילס",
}

ESIMGENIUS_REGION_TO_HEBREW = {
    "europe": "אירופה",
    "asia": "אסיה",
    "africa": "אפריקה",
    "middle-east": "המזרח התיכון",
    "global": "גלובלי",
}

# Non-catalog pages in the esimgenius.ai sitemap; Palestine dropped (GigSky precedent)
_ESIMGENIUS_SKIP_SLUGS = {
    "advisor", "contact", "destinations", "how-it-works", "privacy",
    "refund-policy", "terms", "travel-esim-guide", "palestine",
}


def scrape_esimgenius_global(_page=None, usd_rate=None):
    """Scrape the full eSIM Genius catalog: ~180 country pages + 5 regional/global bundles.

    Pure HTTP — esimgenius.ai is a Next.js app that server-renders each destination
    page with its plans array (label / daysNum / priceCents in USD cents) in the RSC
    stream, so _esimo_extract_packages(array_key="plans") reads it with no Playwright.
    Slugs come from the sitemap (English <loc> entries only). Hebrew destinations
    resolve via SAILY_SLUG_TO_HEBREW (same kebab-case slugs) + ESIMGENIUS_SLUG_OVERRIDES,
    then canonicalize through db._DEST_NORM at scrape time so the raw scraped extras
    match the stored row (a non-canonical value here flaps extras_change every scrape).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from db import _DEST_NORM
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    slugs = set(ESIMGENIUS_REGION_TO_HEBREW)
    try:
        sitemap = _esimo_fetch("https://esimgenius.ai/sitemap.xml", timeout=30)
        slugs.update(re.findall(r"<loc>https://esimgenius\.ai/([a-z0-9-]+)</loc>", sitemap))
    except Exception as exc:
        logger.warning(f"eSIM Genius sitemap fetch failed ({exc}) — scraping regional pages only")
    slugs -= _ESIMGENIUS_SKIP_SLUGS

    dest_by_slug, unknown_slugs = {}, set()
    for slug in sorted(slugs):
        dest = (ESIMGENIUS_REGION_TO_HEBREW.get(slug)
                or ESIMGENIUS_SLUG_OVERRIDES.get(slug)
                or SAILY_SLUG_TO_HEBREW.get(slug))
        if dest:
            dest_by_slug[slug] = _DEST_NORM.get(dest, dest)
        else:
            unknown_slugs.add(slug)

    def fetch_one(slug):
        return _esimo_extract_packages(
            _esimo_fetch(f"https://esimgenius.ai/{slug}"), array_key="plans")

    plans, seen_names = [], set()
    empty, failed = 0, 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): s for s in dest_by_slug}
        for fut in as_completed(futures):
            slug = futures[fut]
            dest = dest_by_slug[slug]
            try:
                items = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIM Genius {slug}: {exc}")
                continue
            if not items:
                empty += 1
                continue
            for it in items:
                label = (it.get("label") or "").strip()
                try:
                    days = int(it.get("daysNum") or 0)
                    usd = int(it.get("priceCents") or 0) / 100.0
                except (TypeError, ValueError):
                    continue
                if days <= 0 or usd <= 0:
                    continue
                unlimited = it.get("planType") == "unlimited" or label.lower().startswith("unlim")
                if unlimited:
                    gb, gb_str = None, "ללא הגבלה"  # ללא הגבלה
                else:
                    m = re.match(r"([\d.]+)\s*(GB|MB)", label, re.I)
                    if not m:
                        continue
                    val = float(m.group(1))
                    gb = round(val / 1024, 4) if m.group(2).upper() == "MB" else val
                    gb_str = f"{m.group(1)}{m.group(2).upper()}"
                day_unit = "יום" if days == 1 else "ימים"  # יום / ימים
                plan_name = f"{dest} – {gb_str} – {days} {day_unit}"
                if plan_name in seen_names:      # guard UNIQUE(carrier, plan_name)
                    continue
                seen_names.add(plan_name)
                extras = [dest]
                if unlimited:
                    extras.append("גלישה ללא הגבלה")  # גלישה ללא הגבלה
                plans.append(_make_global_plan(
                    "esimgenius", plan_name, round(usd * usd_rate, 2), "USD", usd,
                    data_gb=gb, days=days, esim=True, extras=extras,
                ))
    if unknown_slugs:
        logger.warning(
            f"eSIM Genius: skipped unmapped destination slugs {sorted(unknown_slugs)} "
            f"— add them to ESIMGENIUS_SLUG_OVERRIDES"
        )
    logger.info(
        f"eSIM Genius: {len(plans)} plans from {len(dest_by_slug)} pages "
        f"({empty} empty, {failed} failed)"
    )
    return plans


# ── Nisim eSIM (nisim-esim.co.il) ────────────────────────────────────────────
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
    return _json.loads(_esimo_fetch(f"https://www.nisim-esim.co.il/wp-json/wc/store/v1/{path}"))


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
        best[plan_name] = _make_global_plan(
            "nisim", plan_name, price, "ILS", price,
            data_gb=gb, days=days, esim=True, extras=extras,
        )
    if unmapped:
        logger.warning(f"Nisim eSIM: skipped non-destination products {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"Nisim eSIM: {len(plans)} plans from {len(dest_by_parent)} products")
    return plans


# ── eSIM Max (esimax.io) ─────────────────────────────────────────────────────
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
        usd_rate = _get_usd_to_ils()

    def clean_name(raw):
        n = _html.unescape(raw or "").replace("׳", "'").replace("’", "'")
        return re.sub(r"\s+", " ", n).strip()

    parents = _woo_store_fetch(
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

    variations = _woo_store_fetch(
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
        best[plan_name] = _make_global_plan(
            "esimax", plan_name, round(usd * usd_rate, 2), "USD", round(usd, 2),
            data_gb=gb, days=days, esim=True, extras=[dest],
        )
    if unmapped:
        logger.warning(f"eSIM Max: skipped non-destination products {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"eSIM Max: {len(plans)} plans from {len(title_dest_by_parent)} products")
    return plans


# ── VenterraSIM (venterrasim.com) ────────────────────────────────────────────
# Israeli travel-eSIM shop. The storefront reads its whole catalogue from one
# public, auth-free endpoint (/api/v1/plans/ — explicitly Allow:ed in the site's
# own robots.txt so Google can render the package lists), so this is a pure-HTTP
# scrape: ~1,000 plans, prices already in ILS, destinations as ISO-3166 alpha-2.
#
# Hebrew destination names reuse ESIMO_CODE_TO_HEBREW (same uppercase ISO keys,
# already-canonical spellings) plus the handful of codes eSIMo doesn't sell.
VENTERRA_CODE_TO_HEBREW = {
    **ESIMO_CODE_TO_HEBREW,
    "AO": "אנגולה",
    "BT": "בהוטן",
    "CI": "חוף השנהב",
    "PF": "פולינזיה הצרפתית",
    "SM": "סן מרינו",
    "XK": "קוסובו",
    "ZW": "זימבבואה",
}

# Regional/global bundles, keyed by the API `name` with its trailing
# "<N>GB <M>Days" spec stripped → (plan_name title, canonical extras[0] dest).
# Regions that sell SEVERAL coverage tiers under one label (Europe 33/35/41
# areas, Asia 7/20, South America 6/20) keep the area count in the TITLE: the
# tiers share (gb, days) pairs, so a bare region title would collide under
# UNIQUE(carrier, plan_name), and the title is what VENTERRA_REGION_MAP in
# globalCountries.js keys on to resolve the right country list.
VENTERRA_REGION_NAMES = {
    "Europe (33 areas)":               ("אירופה 33 יעדים", "אירופה"),
    "Europe (35 areas)":               ("אירופה 35 יעדים", "אירופה"),
    "Europe":                          ("אירופה 41 יעדים", "אירופה"),
    "Balkans (5+ areas)":              ("בלקן", "בלקן"),
    "Asia (7 areas)":                  ("אסיה 7 יעדים", "אסיה"),
    "Asia-20":                         ("אסיה 20 יעדים", "אסיה"),
    "Singapore & Malaysia & Thailand": ("סינגפור, מלזיה, תאילנד", "סינגפור, מלזיה, תאילנד"),
    "China (mainland HK Macao)":       ("סין + הונג קונג + מקאו", "סין + הונג קונג + מקאו"),
    "Central Asia (4 areas)":          ("מרכז אסיה", "מרכז אסיה"),
    "North America":                   ("צפון אמריקה", "צפון אמריקה"),
    "South America (6 areas)":         ("דרום אמריקה 6 יעדים", "דרום אמריקה"),
    "South America":                   ("דרום אמריקה 20 יעדים", "דרום אמריקה"),
    "Caribbean (20+ areas)":           ("האיים הקריביים", "האיים הקריביים"),
    "Global (120+ areas)":             ("גלובלי", "גלובלי"),
}

_VENTERRA_SPEC_RE = re.compile(r"\s*[\d.]+\s*GB\s*[\d.]+\s*Days?\s*$", re.I)


def scrape_venterrasim_global(_page=None, usd_rate=None):
    """Scrape the VenterraSIM catalog from its public JSON plans endpoint.

    One request returns every package: `type` is COUNTRY (location_code = a
    single ISO2) or REGIONAL (location_code = a comma-separated ISO2 list, and
    the region is identified by the name prefix via VENTERRA_REGION_NAMES).
    Prices are native ILS — `price_ils` is the live selling price, which is
    what change detection should track; `original_price_ils` is a permanent
    strike-through list price on every row, so it is deliberately ignored.
    """
    import json as _json

    raw = _json.loads(_esimo_fetch("https://venterrasim.com/api/v1/plans/", timeout=40))
    if not isinstance(raw, list) or not raw:
        logger.warning("VenterraSIM: empty/unexpected catalog payload")
        return []

    best, unmapped = {}, set()
    for p in raw:
        try:
            gb = float(p.get("data_gb") or 0)
            days = int(p.get("duration_days") or 0)
            price = float(p.get("price_ils") or p.get("price") or 0)
        except (TypeError, ValueError):
            continue
        if gb <= 0 or days <= 0 or price <= 0:
            continue

        if (p.get("type") or "").upper() == "REGIONAL":
            key = _VENTERRA_SPEC_RE.sub("", p.get("name") or "").strip()
            td = VENTERRA_REGION_NAMES.get(key)
            if not td:
                unmapped.add(key)
                continue
            title, dest = td
        else:
            code = (p.get("location_code") or "").strip().upper()
            dest = VENTERRA_CODE_TO_HEBREW.get(code)
            if not dest:
                unmapped.add(f"{code}={p.get('country')}")
                continue
            title = dest

        gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        day_unit = "יום" if days == 1 else "ימים"
        plan_name = f"{title} – {gb_str} – {days} {day_unit}"
        if plan_name in best and best[plan_name]["price"] <= price:
            continue  # cheapest duplicate tier wins (UNIQUE(carrier, plan_name))
        best[plan_name] = _make_global_plan(
            "venterrasim", plan_name, price, "ILS", price,
            data_gb=gb, days=days, esim=True, extras=[dest],
        )
    if unmapped:
        logger.warning(f"VenterraSIM: skipped unmapped destinations {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"VenterraSIM: {len(plans)} plans from {len(raw)} catalog rows")
    return plans

# ── Simzol / סים זול (simzol.co.il) ──────────────────────────────────────────
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
        sitemap = _esimo_fetch(SIMZOL_SITEMAP, timeout=30)
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
            page_html = _esimo_fetch(url, timeout=30)
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
            best[plan_name] = _make_global_plan(
                "simzol", plan_name, price, "ILS", price,
                data_gb=gb, days=days, esim=is_esim, extras=extras,
            )
    if unmapped:
        logger.warning(f"Simzol: unmapped eSIM products {sorted(unmapped)}")
    plans = list(best.values())
    logger.info(f"Simzol: {len(plans)} plans from {seen} products")
    return plans

# ── Maya Mobile eSIM ─────────────────────────────────────────────────────────
MAYA_SLUG_TO_HEBREW = {
    # Global & regions
    "global":                       "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "oceania":                      "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    # Countries (A-Z)
    "afghanistan":                  "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "albania":                      "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria":                      "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "andorra":                      "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla":                     "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "antigua-barbuda":              "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina":                    "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "armenia":                      "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba":                        "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "australia":                    "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria":                      "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "azerbaijan":                   "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "bahamas":                      "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bahrain":                      "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh":                   "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "barbados":                     "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belarus":                      "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "belgium":                      "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "belize":                       "\u05d1\u05dc\u05d9\u05d6",
    "benin":                        "\u05d1\u05e0\u05d9\u05df",
    "bermuda":                      "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bhutan":                       "\u05d1\u05d4\u05d5\u05d8\u05df",
    "bolivia":                      "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "bonaire-saba-eustatius":       "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-herzegovina":           "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana":                     "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "brazil":                       "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands":       "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "brunei":                       "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria":                     "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso":                 "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "burundi":                      "\u05d1\u05d5\u05e8\u05d5\u05e0\u05d3\u05d9",
    "cambodia":                     "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "cameroon":                     "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada":                       "\u05e7\u05e0\u05d3\u05d4",
    "cape-verde":                   "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "cayman-islands":               "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "chad":                         "\u05e6'\u05d0\u05d3",
    "chile":                        "\u05e6'\u05d9\u05dc\u05d4",
    "china":                        "\u05e1\u05d9\u05df",
    "colombia":                     "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "congo-drc":                    "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "costa-rica":                   "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "croatia":                      "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao":                      "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cyprus":                       "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic":               "\u05e6'\u05db\u05d9\u05d4",
    "denmark":                      "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica":                     "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic":           "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador":                      "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt":                        "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador":                  "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia":                      "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "ethiopia":                     "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "falkland-islands":             "\u05d0\u05d9\u05d9 \u05e4\u05d5\u05e7\u05dc\u05e0\u05d3",
    "faroe-islands":                "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fiji":                         "\u05e4\u05d9\u05d2'\u05d9",
    "finland":                      "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france":                       "\u05e6\u05e8\u05e4\u05ea",
    "french-guiana":                "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "french-polynesia":             "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon":                        "\u05d2\u05d0\u05d1\u05d5\u05df",
    "gambia":                       "\u05d2\u05de\u05d1\u05d9\u05d4",
    "georgia":                      "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "germany":                      "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "ghana":                        "\u05d2\u05d0\u05e0\u05d4",
    "gibraltar":                    "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "greece":                       "\u05d9\u05d5\u05d5\u05df",
    "greenland":                    "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "grenada":                      "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "guadeloupe":                   "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "guam":                         "\u05d2\u05d5\u05d0\u05dd",
    "guatemala":                    "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "guernsey":                     "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "guinea":                       "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "guinea-bissau":                "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "guyana":                       "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti":                        "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras":                     "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong":                    "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hungary":                      "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland":                      "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india":                        "\u05d4\u05d5\u05d3\u05d5",
    "indonesia":                    "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iraq":                         "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland":                      "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man":                  "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel":                       "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy":                        "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "ivory-coast":                  "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "jamaica":                      "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan":                        "\u05d9\u05e4\u05df",
    "jersey":                       "\u05d2'\u05e8\u05d6\u05d9",
    "jordan":                       "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan":                   "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya":                        "\u05e7\u05e0\u05d9\u05d4",
    "kosovo":                       "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "kuwait":                       "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan":                   "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos":                         "\u05dc\u05d0\u05d5\u05e1",
    "latvia":                       "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "liberia":                      "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "liechtenstein":                "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania":                    "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg":                   "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau":                        "\u05de\u05e7\u05d0\u05d5",
    "macedonia":                    "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "madagascar":                   "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "malawi":                       "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia":                     "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives":                     "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali":                         "\u05de\u05d0\u05dc\u05d9",
    "malta":                        "\u05de\u05dc\u05d8\u05d4",
    "martinique":                   "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritania":                   "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "mauritius":                    "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayotte":                      "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico":                       "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova":                      "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco":                       "\u05de\u05d5\u05e0\u05e7\u05d5",
    "mongolia":                     "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro":                   "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "montserrat":                   "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "morocco":                      "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique":                   "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "namibia":                      "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "nauru":                        "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "nepal":                        "\u05e0\u05e4\u05d0\u05dc",
    "netherlands":                  "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "netherlands-antilles":         "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "new-zealand":                  "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua":                    "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger":                        "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria":                      "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "norway":                       "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "oman":                         "\u05e2\u05d5\u05de\u05df",
    "pakistan":                     "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palau":                        "\u05e4\u05d0\u05dc\u05d0\u05d5",
    "panama":                       "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea":             "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay":                     "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "peru":                         "\u05e4\u05e8\u05d5",
    "philippines":                  "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "poland":                       "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal":                     "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "puerto-rico":                  "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar":                        "\u05e7\u05d8\u05e8",
    "republic-congo":               "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion":                      "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania":                      "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "russia":                       "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rwanda":                       "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saint-barthelemy":             "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-nevis":            "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia":                  "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martin":                 "\u05e1\u05e0\u05d8 \u05de\u05e8\u05d8\u05df",
    "saint-pierre-miquelon":        "\u05e1\u05df \u05e4\u05d9\u05d9\u05e8 \u05d5\u05de\u05d9\u05e7\u05dc\u05d5\u05df",
    "saint-vincent-grenadines":     "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "saipan":                       "\u05e1\u05d9\u05d9\u05e4\u05df",
    "samoa":                        "\u05e1\u05de\u05d5\u05d0\u05d4",
    "san-marino":                   "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia":                 "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "senegal":                      "\u05e1\u05e0\u05d2\u05dc",
    "serbia":                       "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "seychelles":                   "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone":                 "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "singapore":                    "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-maarten":                 "\u05e1\u05d9\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df",
    "slovakia":                     "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia":                     "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa":                 "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea":                  "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "spain":                        "\u05e1\u05e4\u05e8\u05d3",
    "sri-lanka":                    "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "sudan":                        "\u05e1\u05d5\u05d3\u05df",
    "suriname":                     "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "swaziland":                    "\u05d0\u05e1\u05d5\u05d0\u05d5\u05d8\u05d9\u05e0\u05d9",
    "sweden":                       "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "switzerland":                  "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan":                       "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "tajikstan":                    "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania":                     "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "thailand":                     "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "timor-leste":                  "\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4",
    "togo":                         "\u05d8\u05d5\u05d2\u05d5",
    "tonga":                        "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-tobago":              "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia":                      "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "turkey":                       "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-caicos":                 "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uae":                          "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "uganda":                       "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "uk":                           "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "ukraine":                      "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "uruguay":                      "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "usa":                          "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "us-virgin-islands":            "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d0\u05de\u05e8\u05d9\u05e7\u05e0\u05d9\u05d9\u05dd",
    "uzbekistan":                   "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu":                      "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "venezuela":                    "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "vietnam":                      "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia":                       "\u05d6\u05de\u05d1\u05d9\u05d4",
}


def scrape_maya_global(_page=None, usd_rate=None):
    """Fetch Maya Mobile's current eSIM catalog from the official affiliate feed.

    SOURCE CHANGE (2026-06): switched from scraping the Angular-SSR `maya-mobile-state`
    blob to Maya's official partner feed at
        https://assets.maya.net/affiliates/plans.json
    (shared by their partnerships team; auth-free, stable JSON). The old scrape parsed
    `CACHE_CONTENT_STATE_KEY.cache.globalRegions/cruiseRegions` out of the page HTML --
    that markup died twice in the 2026 redesigns, so the official feed is far more robust.

    The feed lists the same 8 unlimited tiers: 4 "global" (regionType=global) + 4
    "global + cruise" (regionType=cruise / supportedCruises set), at 3/7/14/30 days. We
    shape it into the globalRegions / cruiseRegions buckets the rest of this function
    already expects, so plan naming + dedup (and the stored plan_name keys) are unchanged.

    Plans are unlimited (daily FUP) -> data_gb=None. extras[0] = global / global+cruise
    (Hebrew); the plain "global" name maps to MAYA_GLOBAL in getPlanCoverage. Price uses
    priceDiscounted.USD (falls back to priceOriginal). The current catalog is exactly the
    8 rows already stored, so no stale-row purge is needed.
    """
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Official affiliate data feed (shared by Maya's partnerships team 2026-06). Replaces
    # the brittle Angular-SSR `maya-mobile-state` scrape that died twice in the 2026 site
    # redesigns. Auth-free JSON of the same 8 unlimited tiers (4 global + 4 global+cruise).
    API_URL = "https://assets.maya.net/affiliates/plans.json"
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            payload = _json.loads(r.read().decode("utf-8", errors="replace"))
        api_plans = payload.get("plans") or []
    except Exception as exc:
        logger.warning(f"Maya Mobile API: {exc} -- skipping")
        return []
    if not api_plans:
        logger.warning("Maya Mobile API: no plans returned -- skipping")
        return []

    def _adapt(p):
        # Map the affiliate-feed shape onto the legacy region-plan shape _ingest expects,
        # so the naming / dedup logic below (and the stored plan_name keys) stay unchanged.
        return {
            "validity": p.get("validityInDays"),
            "priceBundle": p.get("priceDiscounted") or p.get("priceOriginal") or {},
            "dataUsageAllowanceType": p.get("dataUsageAllowanceType"),
            "dataUsageAllowanceInGb": p.get("dataUsageAllowanceInGb"),
            "fupDescription": p.get("fupDescription"),
            "isActive": True,
        }

    def _is_cruise(p):
        return (p.get("regionType") == "cruise") or bool(p.get("supportedCruises"))

    # Shape into the buckets _ingest already consumes.
    cache = {
        "globalRegions": [{"plans": [_adapt(p) for p in api_plans if not _is_cruise(p)]}],
        "cruiseRegions": [{"plans": [_adapt(p) for p in api_plans if _is_cruise(p)]}],
    }

    GLOBAL_HEB = "גלובלי"
    CRUISE_HEB = "גלובלי ושייט"

    by_name = {}

    def _ingest(regions, dest_heb):
        for region in regions or []:
            for p in region.get("plans") or []:
                try:
                    days = int(p.get("validity"))
                    price_usd = float((p.get("priceBundle") or {}).get("USD") or 0)
                except (TypeError, ValueError):
                    continue
                if days <= 0 or price_usd <= 0 or not p.get("isActive", True):
                    continue
                # All current Maya plans are unlimited (daily FUP) -> data_gb=None.
                unlimited = (p.get("dataUsageAllowanceType") or "").upper() == "UNLIMITED"
                data_gb = None if unlimited else (p.get("dataUsageAllowanceInGb") or None)
                if data_gb is None:
                    label = "ללא הגבלה"
                else:
                    label = f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb}GB"
                plan_name = (
                    f"{dest_heb} – {label} – {days} ימים"
                )
                extras = [dest_heb]
                fup = (p.get("fupDescription") or "").strip()
                if fup:
                    extras.append(fup)
                # Dedup: Maya lists each tier twice (two slugs); keep the cheapest.
                prev = by_name.get(plan_name)
                if prev and prev.get("original_price", 1e9) <= price_usd:
                    continue
                by_name[plan_name] = _make_global_plan(
                    "maya", plan_name, round(price_usd * usd_rate, 2), "USD",
                    price_usd, data_gb=data_gb, days=days, esim=True, extras=extras,
                )

    _ingest(cache.get("globalRegions"), GLOBAL_HEB)
    _ingest(cache.get("cruiseRegions"), CRUISE_HEB)

    all_plans = list(by_name.values())
    logger.info(
        f"Maya Mobile: {len(all_plans)} plans "
        f"(global + cruise unlimited; per-country catalog retired)"
    )
    return all_plans


BCENGI_EN_TO_HEB = {
    "Albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "Antigua and Barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "Argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "Armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "Aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "Australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "Austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "Azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "Bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "Bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "Bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "Barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "Belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "Belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "Belize": "\u05d1\u05dc\u05d9\u05d6",
    "Benin": "\u05d1\u05e0\u05d9\u05df",
    "Bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "Bhutan": "\u05d1\u05d4\u05d5\u05d8\u05df",
    "Bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Bosnia and Herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Botswana": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "Brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "British Virgin Islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Burkina Faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "Canada": "\u05e7\u05e0\u05d3\u05d4",
    "Cape Verde": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "Cayman Islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Central African Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Chad": "\u05e6'\u05d0\u05d3",
    "Chile": "\u05e6'\u05d9\u05dc\u05d4",
    "China": "\u05e1\u05d9\u05df",
    "Colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Comoros": "\u05d0\u05d9\u05d9 \u05e7\u05d5\u05de\u05d5\u05e8\u05d5",
    "Costa Rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Cuba": "\u05e7\u05d5\u05d1\u05d4",
    "Curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Czech Republic": "\u05e6'\u05db\u05d9\u05d4",
    "Democratic Republic of the Congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "Dominican Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "Ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "El Salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "Estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Faroe Islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "Finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "France": "\u05e6\u05e8\u05e4\u05ea",
    "French Guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "French Polynesia": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Gabon": "\u05d2\u05d0\u05d1\u05d5\u05df",
    "Gambia": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "Georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "Germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "Ghana": "\u05d2\u05d0\u05e0\u05d4",
    "Gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "Greece": "\u05d9\u05d5\u05d5\u05df",
    "Greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "Guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "Guam": "\u05d2\u05d5\u05d0\u05dd",
    "Guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "Guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "Guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "Guinea-Bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "Guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "Haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "Honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "Hong Kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "Hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "Iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "India": "\u05d4\u05d5\u05d3\u05d5",
    "Indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "Iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "Ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Isle of Man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "Italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Ivory Coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Japan": "\u05d9\u05e4\u05df",
    "Jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "Jordan": "\u05d9\u05e8\u05d3\u05df",
    "Kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Kenya": "\u05e7\u05e0\u05d9\u05d4",
    "Kiribati": "\u05e7\u05d9\u05e8\u05d9\u05d1\u05d8\u05d9",
    "Kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Laos": "\u05dc\u05d0\u05d5\u05e1",
    "Latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Lebanon": "\u05dc\u05d1\u05e0\u05d5\u05df",
    "Lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "Liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "Luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Macau": "\u05de\u05e7\u05d0\u05d5",
    "Macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "Madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Maldives": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "Mali": "\u05de\u05d0\u05dc\u05d9",
    "Malta": "\u05de\u05dc\u05d8\u05d4",
    "Martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "Mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "Mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "Mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "Moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "Monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "Mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "Montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "Montserrat": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "Morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Nepal": "\u05e0\u05e4\u05d0\u05dc",
    "Netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "Netherlands Antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "New Caledonia": "\u05e7\u05dc\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "New Zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Niger": "\u05e0\u05d9\u05d2'\u05e8",
    "Nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "Norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "Oman": "\u05e2\u05d5\u05de\u05df",
    "Pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "Palau": "\u05e4\u05dc\u05d0\u05d5",
    # "Palestine" intentionally omitted: db.py _DEST_NORM maps it to "ישראל",
    # which would collide with the Israel entry at a different per-GB rate.
    "Panama": "\u05e4\u05e0\u05de\u05d4",
    "Papua New Guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Peru": "\u05e4\u05e8\u05d5",
    "Philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Puerto Rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "Qatar": "\u05e7\u05d8\u05e8",
    "Republic of the Congo": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Saint Barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "Saint Kitts and Nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "Saint Lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Saint Maarten": "\u05e1\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df",
    "Saint Martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "Saint Vincent and the Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "San Marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "Saudi Arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Senegal": "\u05e1\u05e0\u05d2\u05dc",
    "Serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Sierra Leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "Singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "South Africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "South Korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "Spain": "\u05e1\u05e4\u05e8\u05d3",
    "Sri Lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Sudan": "\u05e1\u05d5\u05d3\u05df",
    "Suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Swaziland": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "Sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Timor-Leste": "\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4",
    "Togo": "\u05d8\u05d5\u05d2\u05d5",
    "Tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Trinidad and Tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "Turks and Caicos Islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "U.S. Virgin Islands": '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4"\u05d1)',
    "Uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "United Arab Emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "United Kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "United States": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "Uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Vatican City": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "Venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "Vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


BCENGI_BENEFITS = [
    "\u05ea\u05e9\u05dc\u05d5\u05dd \u05dc\u05e4\u05d9 \u05e9\u05d9\u05de\u05d5\u05e9 (GB)",
    "\u05dc\u05dc\u05d0 \u05ea\u05e4\u05d5\u05d2\u05d4 \u05dc\u05d9\u05ea\u05e8\u05d4",
    "\u05ea\u05e2\u05e8\u05d9\u05e4\u05d9 \u05de\u05e4\u05e2\u05d9\u05dc \u05de\u05e7\u05d5\u05de\u05d9",
    "eSIM \u05d0\u05d7\u05d3 \u05dc\u05db\u05dc \u05d4\u05d8\u05d9\u05d5\u05dc\u05d9\u05dd",
]


def _parse_bcengi_body(body, usd_rate):
    lines = [l.strip() for l in body.split('\n')]
    plans = []
    for i, line in enumerate(lines):
        if line == '/GB' and i >= 8:
            price_str  = lines[i - 2]
            dollar     = lines[i - 4]
            country_en = lines[i - 8]
            if dollar != '$':
                continue
            try:
                price_usd = float(price_str)
            except ValueError:
                continue
            country_heb = BCENGI_EN_TO_HEB.get(country_en)
            if not country_heb:
                logger.debug(f"Bcengi: unmapped country '{country_en}'")
                continue
            price_ils = round(price_usd * usd_rate, 2)
            plans.append(_make_global_plan(
                "bcengi", country_heb, price_ils, "USD", price_usd,
                data_gb=1, days=None, esim=True,
                extras=[country_heb] + BCENGI_BENEFITS,
            ))
    logger.info(f"Bcengi: {len(plans)} plans")
    return plans


def scrape_bcengi_global(_page=None, usd_rate=None):
    """Scrape Bcengi TravelPass per-country pricing (pay-per-GB eSIM).

    Each plan represents the per-GB rate for one country (data_gb=1 = price per 1 GB).
    Balance top-ups are $10/$25/$50/$100 and never expire; GB amount depends on country.
    """
    from playwright.sync_api import sync_playwright as _sp

    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    URL = "https://www.bcengi.com/travelpass/pricing"

    with _sp() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_UA)
        try:
            page.goto(URL, timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            body = page.inner_text("body")
        finally:
            browser.close()

    return _parse_bcengi_body(body, usd_rate)


ESIM70_ISO2_TO_HEBREW = {
    "AF": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df", "AL": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "DZ": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4", "AD": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "AI": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4", "AG": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "AR": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4", "AM": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "AU": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4", "AT": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "AZ": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df", "BS": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "BH": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df", "BD": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "BB": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1", "BY": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "BE": "\u05d1\u05dc\u05d2\u05d9\u05d4", "BZ": "\u05d1\u05dc\u05d9\u05d6",
    "BO": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4", "BA": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "BR": "\u05d1\u05e8\u05d6\u05d9\u05dc", "VG": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "BG": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4", "KH": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "CA": "\u05e7\u05e0\u05d3\u05d4", "CV": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "KY": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df", "TD": "\u05e6'\u05d0\u05d3",
    "CL": "\u05e6'\u05d9\u05dc\u05d4", "CN": "\u05e1\u05d9\u05df",
    "CO": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4", "CD": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "CG": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5", "CR": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "HR": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4", "CY": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "CZ": "\u05e6'\u05db\u05d9\u05d4", "DK": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "DM": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4", "DO": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "EC": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8", "EG": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "SV": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8", "EE": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "FO": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5", "FJ": "\u05e4\u05d9\u05d2'\u05d9",
    "FI": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3", "FR": "\u05e6\u05e8\u05e4\u05ea",
    "GF": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea", "GA": "\u05d2\u05d0\u05d1\u05d5\u05df",
    "GE": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4", "DE": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "GH": "\u05d2\u05d0\u05e0\u05d4", "GI": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "GR": "\u05d9\u05d5\u05d5\u05df", "GD": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "GU": "\u05d2\u05d5\u05d0\u05dd", "GT": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "HN": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1", "HK": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "HU": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4", "IS": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "IN": "\u05d4\u05d5\u05d3\u05d5", "ID": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "IQ": "\u05e2\u05d9\u05e8\u05d0\u05e7", "IE": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "IL": "\u05d9\u05e9\u05e8\u05d0\u05dc", "IT": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "JM": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4", "JP": "\u05d9\u05e4\u05df",
    "JO": "\u05d9\u05e8\u05d3\u05df", "KZ": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "KE": "\u05e7\u05e0\u05d9\u05d4", "XK": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "KW": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea", "KG": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "LA": "\u05dc\u05d0\u05d5\u05e1", "LV": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "LI": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df", "LT": "\u05dc\u05d9\u05d8\u05d0",
    "LU": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2", "MO": "\u05de\u05e7\u05d0\u05d5",
    "MK": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea", "MG": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "MW": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9", "MY": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "MV": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd", "MT": "\u05de\u05dc\u05d8\u05d4",
    "MU": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1", "MX": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "MD": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4", "MN": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "ME": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5", "MS": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "MA": "\u05de\u05e8\u05d5\u05e7\u05d5", "NP": "\u05e0\u05e4\u05d0\u05dc",
    "NL": "\u05d4\u05d5\u05dc\u05e0\u05d3", "AN": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "NZ": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3", "NI": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "NE": "\u05e0\u05d9\u05d2'\u05e8", "NG": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "NO": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4", "OM": "\u05e2\u05d5\u05de\u05df",
    "PK": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df", "PS": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "PA": "\u05e4\u05e0\u05de\u05d4", "PY": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "PE": "\u05e4\u05e8\u05d5", "PH": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "PL": "\u05e4\u05d5\u05dc\u05d9\u05df", "PT": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "PR": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5", "QA": "\u05e7\u05d8\u05e8",
    "RE": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df", "RO": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "RU": "\u05e8\u05d5\u05e1\u05d9\u05d4", "RW": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "KN": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1", "LC": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "VC": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "SA": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea", "SN": "\u05e1\u05e0\u05d2\u05dc",
    "RS": "\u05e1\u05e8\u05d1\u05d9\u05d4", "SG": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "SK": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4", "SI": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "ZA": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4", "KR": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "ES": "\u05e1\u05e4\u05e8\u05d3", "LK": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "SE": "\u05e9\u05d1\u05d3\u05d9\u05d4", "CH": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "TW": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df", "TZ": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "TH": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3", "TN": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "TR": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4", "TC": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "UG": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4", "UA": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "AE": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea", "GB": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "US": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea", "UY": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "UZ": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df", "VE": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "VN": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd", "ZM": "\u05d6\u05de\u05d1\u05d9\u05d4",
    "GP": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
}

ESIM70_REGION_BASE_TO_HEBREW = {
    "Europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "CIS": "\u05d7\u05d1\u05e8 \u05d4\u05de\u05d3\u05d9\u05e0\u05d5\u05ea",
    "SEA": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "Balkans": "\u05d4\u05d1\u05dc\u05e7\u05df",
    "MIDDLE EAST": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "LATAM": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "Latin America": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "North America": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "Asia Pacific": "\u05d0\u05e1\u05d9\u05d4 \u05e4\u05e1\u05d9\u05e4\u05d9\u05e7",
    "Asia": "\u05d0\u05e1\u05d9\u05d4",
    "Global Package": "\u05d7\u05d1\u05d9\u05dc\u05d4 \u05d2\u05dc\u05d5\u05d1\u05dc\u05d9\u05ea",
}


def scrape_esim70_global(_page=None, eur_rate=None):
    """Scrape eSIM70 global plans via Lascade REST API — no Playwright needed.

    2026-07: the API dropped the bulk listing (plans/ now returns 400 without a
    filter_country or region param), so we enumerate /api/countries/ (150 codes,
    paginated) + /api/regions/ (9 slugs) and fetch per-country / per-region.
    Plan payloads and names are unchanged, so plan_name keys stay stable.
    """
    import urllib.request as _ur, urllib.error as _ue, json as _js, time as _time

    if eur_rate is None:
        eur_rate = _get_eur_to_ils()

    all_plans = []
    _LASCADE_API = "https://esim.lascade.com/api"
    _LASCADE_COMMON = "is_active=true&app_code=D1WE&billing_country=IL&currency=EUR"
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

    def _get_json(url):
        # ~160 per-country calls trip the API's rate limit — pace steadily and
        # back off on 429 (honoring Retry-After when sent).
        backoff = 10
        for attempt in range(4):
            _time.sleep(0.45)
            try:
                req = _ur.Request(url, headers={"User-Agent": _UA})
                with _ur.urlopen(req, timeout=20) as r:
                    return _js.loads(r.read())
            except _ue.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    retry_after = e.headers.get("Retry-After") or ""
                    _time.sleep(min(int(retry_after) if retry_after.isdigit() else backoff, 120))
                    backoff *= 2
                    continue
                raise

    def _paged(url):
        """Yield results across DRF-style pagination (follows 'next' links)."""
        while url:
            data = _get_json(url)
            if isinstance(data, list):  # /regions/ returns a bare list
                yield from data
                return
            yield from (data.get("results") or [])
            url = data.get("next")

    def _region_heb(raw_name):
        base = re.sub(r"\s+\d+\s+days?\s+unlim$", "", raw_name, flags=re.IGNORECASE).strip()
        base = re.sub(r"\s*\d+(\.\d+)?GB$", "", base).strip()
        return ESIM70_REGION_BASE_TO_HEBREW.get(base, base)

    def _gb_str(gb):
        return f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"

    def _build_plan(plan_type, p):
        is_unlimited = p.get("is_unlimited", False)
        days = p.get("days")
        price_eur = float(p.get("display_price") or 0)
        if price_eur <= 0:
            return None
        price_ils = round(price_eur * eur_rate, 2)

        if plan_type == "region":
            raw = p["name"].split("_")[0].strip()
            heb_name = _region_heb(raw)
        else:
            codes = p.get("countries", [])
            if not codes:
                return None
            heb_name = ESIM70_ISO2_TO_HEBREW.get(codes[0]["code"]) or codes[0].get("name") or ""
            if not heb_name:
                return None

        if is_unlimited:
            data_gb = None
            gb_part = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"  # ללא הגבלה
        else:
            data_gb = float(p.get("data_in_gb") or 0) or None
            gb_part = _gb_str(data_gb) if data_gb else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"

        plan_name = f"{heb_name} \u2013 {gb_part} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
        return _make_global_plan(
            "esim70", plan_name, price_ils, "EUR", price_eur,
            data_gb=data_gb, days=days, esim=True, extras=[heb_name],
        )

    try:
        region_slugs = [r["slug"] for r in _paged(f"{_LASCADE_API}/regions/?app_code=D1WE")]
    except Exception as e:
        logger.warning(f"eSIM70 regions list: {e}")
        region_slugs = []
    try:
        country_codes = [c["code"] for c in _paged(f"{_LASCADE_API}/countries/?app_code=D1WE")]
    except Exception as e:
        logger.warning(f"eSIM70 countries list: {e}")
        country_codes = []

    # A plan covering several countries comes back once per covered country —
    # dedupe by API id so it lands as a single row (keyed to countries[0], as
    # the old bulk listing did).
    seen_ids = set()

    def _collect(plan_type, filt):
        try:
            for p in _paged(f"{_LASCADE_API}/plans/?{_LASCADE_COMMON}&plan_type={plan_type}&{filt}&limit=200"):
                pid = p.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                plan = _build_plan(plan_type, p)
                if plan:
                    all_plans.append(plan)
        except Exception as e:
            logger.warning(f"eSIM70 {plan_type} {filt}: {e}")

    for slug in region_slugs:
        _collect("region", f"region={slug}")
    for code in country_codes:
        _collect("country", f"filter_country={code}")

    logger.info(f"eSIM70 global: {len(all_plans)} plans")
    return all_plans


# ── Jetpack ───────────────────────────────────────────────────────────
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
    if slug in SAILY_SLUG_TO_HEBREW:
        return SAILY_SLUG_TO_HEBREW[slug]
    # Fallback: titlecase the slug
    return slug.replace("-", " ").title()


def scrape_jetpack_global(_page=None, usd_rate=None):
    """Scrape Jetpack global eSIM plans via content.jetpacglobal.com JSON catalogs."""
    import urllib.request as _ur, urllib.error as _ue, json as _js, time as _time

    if usd_rate is None:
        usd_rate = _get_usd_to_ils()

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
            all_plans.append(_make_global_plan(
                "jetpack", plan_name, price_ils, "USD", usd_val,
                data_gb=data_gb, days=days, esim=True, extras=[dest_heb],
            ))

    logger.info(f"Jetpack global: {len(all_plans)} plans from {fetched} catalogs "
                f"(failed: {len(failed)})")
    return all_plans


# ── Breeze eSIM ────────────────────────────────────────────────────────────────
BREEZ_EN_TO_HEBREW = {
    # Countries
    "Canada": "\u05e7\u05e0\u05d3\u05d4",
    "United States of America": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "Morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "United Kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Spain": "\u05e1\u05e4\u05e8\u05d3",
    "United Arab Emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "Italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Netherlands Antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "France": "\u05e6\u05e8\u05e4\u05ea",
    "Japan": "\u05d9\u05e4\u05df",
    "Switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "Greece": "\u05d9\u05d5\u05d5\u05df",
    "Peru": "\u05e4\u05e8\u05d5",
    "Saudi Arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "Thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "Tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "Portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "Northern Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "China": "\u05e1\u05d9\u05df",
    "Brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "Colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Costa Rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Korea Republic of": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "Iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "Albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "Netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "Bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "Hong Kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "Singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Hawaii": "\u05d4\u05d5\u05d5\u05d0\u05d9",
    "Barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "Pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "VietNam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "India": "\u05d4\u05d5\u05d3\u05d5",
    "Canary Islands": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05e7\u05e0\u05e8\u05d9\u05d9\u05dd",
    "Dominican Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "South Africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "Poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "Sri Lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "New Zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Chile": "\u05e6'\u05d9\u05dc\u05d4",
    "Croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Taiwan-Province of China": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "Czech Republic": "\u05e6'\u05db\u05d9\u05d4",
    "Montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "Ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "Antigua And Barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "Denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Tanzania, United Republic of": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Cape Verde": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "Suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Malta": "\u05de\u05dc\u05d8\u05d4",
    "Romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Virgin Islands - British": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Panama": "\u05e4\u05e0\u05de\u05d4",
    "Qatar": "\u05e7\u05d8\u05e8",
    "Saint Lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "Finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "El Salvador": "\u05d0\u05dc \u05e1\u05dc\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Kenya": "\u05e7\u05e0\u05d9\u05d4",
    "Turks And Caicos Islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "Trinidad And Tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Russian Federation": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "Guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "Guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "Serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Bosnia And Herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Cayman Islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "Algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Oman": "\u05e2\u05d5\u05de\u05df",
    "Nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "Dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "North Macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "Bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Ghana": "\u05d2\u05d0\u05e0\u05d4",
    "Jordan": "\u05d9\u05e8\u05d3\u05df",
    "Bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "Saint Martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "Honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "Saint Vincent And The Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "Lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "Isle of Man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "Latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Macao": "\u05de\u05e7\u05d0\u05d5",
    "Moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "Ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "Curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "Bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "Nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "Middle East and North Africa": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "Azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "Senegal": "\u05e1\u05e0\u05d2\u05dc",
    "Kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Bonaire, saint Eustatius and Saba": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "Estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "Monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "Anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "Ivory Coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "Zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
    "Botswana": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "Saint Kitts And Nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "Andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Guam": "\u05d2\u05d5\u05d0\u05dd",
    "Rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "Lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "Virgin Islands - United States": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",
    "Bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "Fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "Reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Togo": "\u05d8\u05d5\u05d2\u05d5",
    "Ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "Papua New Guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Saint Barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "Benin": "\u05d1\u05e0\u05d9\u05df",
    "Brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Laos": "\u05dc\u05d0\u05d5\u05e1",
    "Palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "Kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "Seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Montserrat": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "Swaziland": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "Congo-the Democratic Republic of the": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Faroe Islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "Mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Sudan": "\u05e1\u05d5\u05d3\u05df",
    "Aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "Cuba": "\u05e7\u05d5\u05d1\u05d4",
    "Belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "Central African Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Congo": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "Cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "Burkina Faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Guinea-Bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "Niger": "\u05e0\u05d9\u05d2'\u05e8",
    "Liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Mali": "\u05de\u05d0\u05dc\u05d9",
    "Iran-Islamic Republic of": "\u05d0\u05d9\u05e8\u05d0\u05df",
    "Chad": "\u05e6'\u05d0\u05d3",
    "Vatican City": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "French Guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "Gabon": "\u05d2\u05d0\u05d1\u05d5\u05df",
    "Nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "Mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "Tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "Puerto Rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    # Regions (country-bundles collection)
    "Caribbean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "South America": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "EU & USA": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4 \u05d5\u05d0\u05e8\u05d4\"\u05d1",
    "Portugal and Spain": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc \u05d5\u05e1\u05e4\u05e8\u05d3",
    "CENAM": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6\u05d9\u05ea",
    "Balkans": "\u05d4\u05d1\u05dc\u05e7\u05df",
    "CIS": "\u05d7\u05d1\u05e8 \u05d4\u05de\u05d3\u05d9\u05e0\u05d5\u05ea",
    "Middle East Lite": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05dc\u05d9\u05d9\u05d8",
    "Europe Lite": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4 \u05dc\u05d9\u05d9\u05d8",
    # Regions (regional-bundles collection)
    "EU+": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4+",
    "North America": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "Middle East": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "Asia": "\u05d0\u05e1\u05d9\u05d4",
    "Global": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "Africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
}

# English product title -> Shopify product handle (breezesim.com/products/<handle>),
# from the same country-bundles + regional-bundles collections the scraper reads. Used
# by app.py to build per-destination affiliate deep-links (/go/breez?dest=...) with the
# UpPromote sca_ref param. Format verified via the dashboard "Get product link" tool
# 2026-07-06 (it emits exactly /products/<handle>?sca_ref=<tag>). Regenerate when Breeze
# changes its catalog (scratchpad breez_en_handles.py: fetch collections, map title->handle).
BREEZ_EN_TO_HANDLE = {
    "Africa": "esimg_raf_v2",
    "Albania": "esimg_al_v2",
    "Algeria": "esimg_dz_v2",
    "Andorra": "esimg_ad_v2",
    "Anguilla": "esimg_ai_v2",
    "Antigua And Barbuda": "esimg_ag_v2",
    "Argentina": "esim-argentina",
    "Armenia": "esimg_am_v2",
    "Aruba": "esim-aruba",
    "Asia": "esim-asia",
    "Australia": "esim-australia",
    "Austria": "esimg_at_v2",
    "Azerbaijan": "esimg_az_v2",
    "Bahamas": "esim-bahamas",
    "Bahrain": "esimg_bh_v2",
    "Balkans": "esim-balkans",
    "Bangladesh": "esimg_bd_v2",
    "Barbados": "esimg_bb_v2",
    "Belarus": "esimg_by_v2",
    "Belgium": "esimg_be_v2",
    "Benin": "esimg_bj_v2",
    "Bermuda": "esim-bermuda",
    "Bolivia": "esimg_bo_v2",
    "Bonaire, saint Eustatius and Saba": "esim-bonaire-saint-eustatius-and-saba",
    "Bosnia And Herzegovina": "esimg_ba_v2",
    "Botswana": "esimg_bw_v2",
    "Brazil": "esim-brazil",
    "Brunei": "esimg_bn_v2",
    "Bulgaria": "esimg_bg_v2",
    "Burkina Faso": "esimg_bf_v2",
    "CENAM": "esim-cenam",
    "CIS": "esim-cis-region",
    "Cambodia": "esimg_kh_v2",
    "Cameroon": "esimg_cm_v2",
    "Canada": "esim-canada",
    "Canary Islands": "esimg_ic_v2",
    "Cape Verde": "esim-cape-verde",
    "Caribbean": "esim-caribbean",
    "Cayman Islands": "esimg_ky_v2",
    "Central African Republic": "esimg_cf_v2",
    "Chad": "esimg_td_v2",
    "Chile": "esimg_cl_v2",
    "China": "esim-china",
    "Colombia": "esim-colombia",
    "Congo": "esimg_cg_v2",
    "Congo-the Democratic Republic of the": "esimg_cd_v2",
    "Costa Rica": "esim-costa-rica",
    "Croatia": "esimg_hr_v2",
    "Cuba": "esim-cuba",
    "Curacao": "esim-curacao",
    "Cyprus": "esimg_cy_v2",
    "Czech Republic": "esimg_cz_v2",
    "Denmark": "esimg_dk_v2",
    "Dominica": "esimg_dm_v2",
    "Dominican Republic": "esim-dominican-republic",
    "EU+": "esim-europe",
    "Ecuador": "esimg_ec_v2",
    "Egypt": "esim-egypt",
    "El Salvador": "esimg_sv_v2",
    "Estonia": "esimg_ee_v2",
    "Ethiopia": "esim-ethiopia",
    "Europe Lite": "esim-europe-lite",
    "Faroe Islands": "esimg_fo_v2",
    "Fiji": "esimg_fj_v2",
    "Finland": "esimg_fi_v2",
    "France": "esim-france",
    "French Guiana": "esimg_gf_v2",
    "Gabon": "esimg_ga_v2",
    "Georgia": "esimg_ge_v2",
    "Germany": "esim-germany",
    "Ghana": "esimg_gh_v2",
    "Gibraltar": "esimg_gi_v2",
    "Global": "esim-global",
    "Greece": "esim-greece",
    "Greenland": "esimg_gl_v2",
    "Grenada": "esimg_gd_v2",
    "Guadeloupe": "esimg_gp_v2",
    "Guam": "esimg_gu_v2",
    "Guatemala": "esimg_gt_v2",
    "Guernsey": "esimg_gg_v2",
    "Guinea": "esimg_gn_v2",
    "Guinea-Bissau": "esimg_gw_v2",
    "Guyana": "esimg_gy_v2",
    "Haiti": "esim-haiti",
    "Hawaii": "esim-hawaii",
    "Honduras": "esimg_hn_v2",
    "Hong Kong": "esim-hong-kong",
    "Hungary": "esim-hungary",
    "Iceland": "esimg_is_v2",
    "India": "esim-india",
    "Indonesia": "esimg_id_v2",
    "Iran-Islamic Republic of": "esimg_ir_v2",
    "Ireland": "esim-ireland",
    "Isle of Man": "esimg_im_v2",
    "Israel": "esimg_il_v2",
    "Italy": "esim-italy",
    "Ivory Coast": "esimg_ci_v2",
    "Jamaica": "esimg_jm_v2",
    "Japan": "esim-japan",
    "Jersey": "esimg_je_v2",
    "Jordan": "esimg_jo_v2",
    "Kazakhstan": "esimg_kz_v2",
    "Kenya": "esimg_ke_v2",
    "Korea Republic of": "esim-south-korea",
    "Kyrgyzstan": "esimg_kg_v2",
    "Laos": "esimg_la_v2",
    "Latvia": "esimg_lv_v2",
    "Lesotho": "esimg_ls_v2",
    "Liberia": "esimg_lr_v2",
    "Liechtenstein": "esimg_li_v2",
    "Lithuania": "esimg_lt_v2",
    "Luxembourg": "esimg_lu_v2",
    "Macao": "esimg_mo_v2",
    "Madagascar": "esimg_mg_v2",
    "Malawi": "esimg_mw_v2",
    "Malaysia": "esimg_my_v2",
    "Mali": "esimg_ml_v2",
    "Malta": "esimg_mt_v2",
    "Martinique": "esimg_mq_v2",
    "Mauritania": "esimg_mr_v2",
    "Mauritius": "esimg_mu_v2",
    "Mayotte": "esimg_yt_v2",
    "Mexico": "esim-mexico",
    "Middle East": "esimg_rme_v2",
    "Middle East and North Africa": "esim-middle-east-and-north-africa",
    "Moldova": "esimg_md_v2",
    "Monaco": "esimg_mc_v2",
    "Mongolia": "esimg_mn_v2",
    "Montenegro": "esimg_me_v2",
    "Montserrat": "esimg_ms_v2",
    "Morocco": "esim-morocco",
    "Mozambique": "esimg_mz_v2",
    "Namibia": "esimg_na_v2",
    "Nauru": "esimg_nr_v2",
    "Netherlands": "esim-netherlands",
    "Netherlands Antilles": "esim-netherlands-antilles",
    "New Zealand": "esimg_nz_v2",
    "Nicaragua": "esimg_ni_v2",
    "Niger": "esimg_ne_v2",
    "Nigeria": "esimg_ng_v2",
    "North America": "esim-north-america",
    "North Macedonia": "esimg_mk_v2",
    "Northern Cyprus": "esim-northern-cyprus",
    "Norway": "esimg_no_v2",
    "Oman": "esimg_om_v2",
    "Pakistan": "esimg_pk_v2",
    "Palestine": "esimg_ps_v2",
    "Panama": "esim-panama",
    "Papua New Guinea": "esimg_pg_v2",
    "Paraguay": "esimg_py_v2",
    "Peru": "esim-peru",
    "Philippines": "esim-philippines",
    "Poland": "esimg_pl_v2",
    "Portugal": "esim-portugal",
    "Puerto Rico": "esim-puerto-rico",
    "Qatar": "esimg_qa_v2",
    "Reunion": "esimg_re_v2",
    "Romania": "esimg_ro_v2",
    "Russian Federation": "esimg_ru_v2",
    "Rwanda": "esimg_rw_v2",
    "Saint Barthelemy": "esimg_bl_v2",
    "Saint Kitts And Nevis": "esimg_kn_v2",
    "Saint Lucia": "esim-saint-lucia",
    "Saint Martin": "esimg_mf_v2",
    "Saint Vincent And The Grenadines": "esimg_vc_v2",
    "Samoa": "esimg_eh_v2",
    "Saudi Arabia": "esim-saudi-arabia",
    "Senegal": "esimg_sn_v2",
    "Serbia": "esimg_rs_v2",
    "Seychelles": "esim-seychelles",
    "Singapore": "esimg_sg_v2",
    "Slovakia": "esimg_sk_v2",
    "Slovenia": "esimg_si_v2",
    "South Africa": "esim-south-africa",
    "South America": "esim-south-america",
    "Spain": "esim-spain",
    "Sri Lanka": "esimg_lk_v2",
    "Sudan": "esimg_sd_v2",
    "Suriname": "esimg_sr_v2",
    "Swaziland": "esimg_sz_v2",
    "Sweden": "esimg_se_v2",
    "Switzerland": "esim-switzerland",
    "Taiwan-Province of China": "esim-taiwan",
    "Tajikistan": "esimg_tj_v2",
    "Tanzania, United Republic of": "esim-tanzania",
    "Thailand": "esim-thailand",
    "Togo": "esim-togo",
    "Tonga": "esimg_to_v2",
    "Trinidad And Tobago": "esimg_tt_v2",
    "Tunisia": "esim-tunisia",
    "Turkey": "esim-turkey",
    "Turks And Caicos Islands": "esimg_tc_v2",
    "Uganda": "esimg_ug_v2",
    "Ukraine": "esimg_ua_v2",
    "United Arab Emirates": "esim-united-arab-emirates",
    "United Kingdom": "esim-united-kingdom",
    "United States of America": "esim-usa",
    "Uruguay": "esimg_uy_v2",
    "Uzbekistan": "esimg_uz_v2",
    "Vanuatu": "esim-vanuatu",
    "Vatican City": "esimg_va_v2",
    "VietNam": "esim-vietnam",
    "Virgin Islands - British": "esimg_vg_v2",
    "Virgin Islands - United States": "esim-virgin-islands-us",
    "Zambia": "esimg_zm_v2",
}

# Hebrew destination -> Shopify handle, composed from the two maps above so the
# /go/breez deep-link layer can key on the canonical Hebrew ?dest= value.
BREEZ_HEB_TO_HANDLE = {
    BREEZ_EN_TO_HEBREW[_en]: _h
    for _en, _h in BREEZ_EN_TO_HANDLE.items()
    if _en in BREEZ_EN_TO_HEBREW
}


def scrape_breez_global(_page=None, usd_rate=None):
    """Scrape Breeze eSIM global plans via Shopify JSON API (USD base pricing, no browser).

    Prices are fetched in the shop's BASE currency (USD) and converted to ILS
    with usd_rate. Do NOT request `currency=ILS` from Shopify — its converted
    prices are re-rounded against a daily FX rate, so the whole catalog
    "changed price" by ±1 ₪ every day (~700 phantom price_change events/day,
    fixed 2026-07-26). currency='USD' + original_price=USD lets
    change_detector compare the stable USD value.
    """
    import requests as _req
    import re as _re

    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    base = "https://breezesim.com"
    all_plans = []
    seen_names = set()

    def _parse_sku(sku):
        m = _re.match(r'^(?:esimd|2025h2)_(\w+)_(\d+)D_', sku)
        if not m:
            return None, None
        data_part, days = m.group(1), int(m.group(2))
        if data_part == 'ULE':
            return None, days
        gb_m = _re.match(r'^(\d+)GB$', data_part)
        if gb_m:
            return int(gb_m.group(1)), days
        return None, None

    def _fetch_products(collection_handle):
        products, page = [], 1
        while True:
            try:
                r = _req.get(
                    f"{base}/collections/{collection_handle}/products.json",
                    params={"limit": 250, "page": page},
                    timeout=25,
                )
                r.raise_for_status()
                batch = r.json().get("products", [])
                if not batch:
                    break
                products.extend(batch)
                if len(batch) < 250:
                    break
                page += 1
            except Exception:
                break
        return products

    try:
        country_products = _fetch_products("country-bundles")
        regional_products = _fetch_products("regional-bundles")
        logger.info(
            f"Breez: {len(country_products)} country products, "
            f"{len(regional_products)} regional products"
        )

        for product in country_products + regional_products:
            title = product.get("title", "")
            heb_name = BREEZ_EN_TO_HEBREW.get(title)
            if not heb_name:
                continue

            for variant in product.get("variants", []):
                if not variant.get("available", True):
                    continue
                sku = variant.get("sku", "")
                data_gb, days = _parse_sku(sku)
                if days is None:
                    continue
                try:
                    usd = float(variant.get("price", 0))
                except (ValueError, TypeError):
                    continue
                if usd <= 0:
                    continue

                gb_str = (f"{int(data_gb)}GB" if data_gb is not None
                          else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                day_word = "\u05d9\u05d5\u05dd" if days == 1 else "\u05d9\u05de\u05d9\u05dd"
                plan_name = f"{heb_name} \u2013 {gb_str} \u2013 {days} {day_word}"

                if plan_name in seen_names:
                    continue
                seen_names.add(plan_name)

                all_plans.append(_make_global_plan(
                    "breez", plan_name, usd * usd_rate, "USD", usd,
                    data_gb=data_gb, days=days, esim=True, extras=[heb_name],
                ))

        logger.info(f"Breez total: {len(all_plans)} plans")
    except Exception as e:
        logger.error(f"Breez global failed: {e}", exc_info=True)

    return all_plans


# ─────────────────────────────────────────────────────────────────────────────
# ByteSim
# ─────────────────────────────────────────────────────────────────────────────

# Per-country handles → Hebrew names.  Derived from SAILY_SLUG_TO_HEBREW with
# two handle differences: ByteSim uses "usa" and "uae" instead of the full names.
BYTESIM_HANDLE_TO_HEBREW = {
    k: v for k, v in SAILY_SLUG_TO_HEBREW.items()
    if k not in ("united-states", "united-arab-emirates")
}
BYTESIM_HANDLE_TO_HEBREW["usa"] = SAILY_SLUG_TO_HEBREW["united-states"]
BYTESIM_HANDLE_TO_HEBREW["uae"] = SAILY_SLUG_TO_HEBREW["united-arab-emirates"]

# Zone/regional product handles → Hebrew zone names used as extras[0]
BYTESIM_ZONE_HANDLES = {
    # handle: (plan_label used in plan_name, canonical KNOWN_REGIONS string for extras[0])
    # Global
    "esim-global":                             ("גלובלי ByteSim – 125 מדינות",         "גלובלי"),
    "esim-global-148":                         ("גלובלי ByteSim – 109 מדינות",         "גלובלי"),
    # Europe
    "europe-esim-unlimited-30-countries-lite": ("אירופה – ByteSim MAX (57 מדינות)",    "אירופה"),
    "europe-esim-max":                         ("אירופה – ByteSim UK+ (45 מדינות)",    "אירופה"),
    "europe-esim-lite":                        ("אירופה – ByteSim לייט (42 מדינות)",   "אירופה"),
    "esim-balkans":                            ("בלקן – ByteSim (12 מדינות)",           "בלקן"),
    # Asia
    "esim-asia":                               ("אסיה – ByteSim (25 מדינות)",           "אסיה"),
    "asia-esim-13-countries":                  ("אסיה פסיפיק – ByteSim (15 מדינות)",   "אסיה פסיפיק"),
    "esim-china-hong-kong-macao":              ("סין, הונג קונג ומקאו – ByteSim",      "סין + הונג קונג + מקאו"),
    # Americas
    "esim-north-america":                      ("צפון אמריקה – ByteSim (3 מדינות)",    "צפון אמריקה"),
    "esim-us-canada":                          ("ארה\"ב וקנדה – ByteSim",               "צפון אמריקה"),
    "esim-south-america":                      ("דרום אמריקה – ByteSim (11 מדינות)",   "אמריקה הלטינית"),
    "south-america-lite":                      ("דרום אמריקה – ByteSim לייט (12 מדינות)", "אמריקה הלטינית"),
    "esim-caribbean":                          ("הקריביים – ByteSim",                  "קריביים"),
    # Middle East & Africa
    "esim-middle-east":                        ("המזרח התיכון – ByteSim",               "המזרח התיכון"),
    "esim-africa":                             ("אפריקה – ByteSim",                    "אפריקה"),
}


def _parse_bytesim_option1(opt1):
    """Parse ByteSim plan option1 ('1GB/Day', 'Total 5GB', 'Unlimited Data').
    Returns (data_gb, data_str_heb)."""
    if not opt1:
        return None, "ללא הגבלה"
    opt1 = opt1.strip()
    m = re.match(r'^(\d+(?:\.\d+)?)GB/Day$', opt1, re.I)
    if m:
        gb = float(m.group(1))
        gb_int = int(gb) if gb == int(gb) else gb
        return gb_int, f"{gb_int}GB/יום"
    m = re.match(r'^(\d+(?:\.\d+)?)MB/Day$', opt1, re.I)
    if m:
        mb = float(m.group(1))
        return round(mb / 1024, 4), f"{int(mb)}MB/יום"
    m = re.match(r'^Total\s+(\d+(?:\.\d+)?)GB$', opt1, re.I)
    if m:
        gb = float(m.group(1))
        gb_int = int(gb) if gb == int(gb) else gb
        return gb_int, f"{gb_int}GB"
    if "unlimited" in opt1.lower():
        return None, "ללא הגבלה"
    return None, opt1


_BYTESIM_JS = """() => {
    const s = window.__PRELOAD_STATE__;
    if (!s || !s.product) return null;
    return s.product.variants
        .filter(v => v.available)
        .map(v => ({o1: v.option1, o2: v.option2, price: v.price}));
}"""

_BYTESIM_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _scrape_bytesim_batch(items, carrier_label, usd_rate):
    """Fetch one batch of ByteSim product URLs in a single sequential browser session."""
    _ensure_event_loop()
    batch_plans = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_BYTESIM_UA)
        for item in items:
            url, heb_name = item[0], item[1]
            # heb_name may be a (plan_label, region_tag) tuple for zone plans
            if isinstance(heb_name, tuple):
                plan_label, region_tag = heb_name
            else:
                plan_label = region_tag = heb_name
            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
                variants = page.evaluate(_BYTESIM_JS)
                if not variants:
                    continue
                for v in variants:
                    data_gb, data_str = _parse_bytesim_option1(v.get("o1", ""))
                    try:
                        days = int(v["o2"])
                    except (TypeError, ValueError):
                        continue
                    price_cents = v.get("price", 0)
                    if not days or not price_cents:
                        continue
                    price_usd = price_cents / 100.0
                    price_ils = round(price_usd * usd_rate, 2)
                    day_word = "יום" if days == 1 else "ימים"
                    plan_name = f"{plan_label} – {data_str} – {days} {day_word}"
                    batch_plans.append(_make_global_plan(
                        "bytesim", plan_name, price_ils, "USD", price_usd,
                        data_gb, days, esim=True, extras=[region_tag],
                    ))
            except Exception as exc:
                logger.warning(f"ByteSim {carrier_label} {url}: {exc}")
        browser.close()
    return batch_plans


def _scrape_bytesim_product_list(url_iter, carrier_label, usd_rate):
    """Split url_iter into 4 batches and fetch them in parallel browser sessions.
    Reduces wall time from ~19 min (sequential) to ~5 min (4-way parallel)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    url_list = list(url_iter)
    batch_size = max(1, (len(url_list) + 3) // 4)
    batches = [url_list[i:i + batch_size] for i in range(0, len(url_list), batch_size)]
    all_plans = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_scrape_bytesim_batch, b, carrier_label, usd_rate) for b in batches]
        for fut in _as_completed(futures, timeout=600):
            try:
                all_plans.extend(fut.result())
            except Exception as exc:
                logger.warning(f"ByteSim {carrier_label} batch error: {exc}")
    return all_plans


def scrape_bytesim_global(_page=None, usd_rate=None):
    """Scrape ByteSim per-country eSIM plans (~197 countries)."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    url_iter = [
        (f"https://bytesim.com/products/esim-{handle}", heb)
        for handle, heb in BYTESIM_HANDLE_TO_HEBREW.items()
    ]
    plans = _scrape_bytesim_product_list(url_iter, "countries", usd_rate)
    logger.info(f"ByteSim global: {len(plans)} plans from {len(BYTESIM_HANDLE_TO_HEBREW)} countries")
    return plans


def scrape_bytesim_regions(_page=None, usd_rate=None):
    """Scrape ByteSim zone/regional eSIM plans."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    url_iter = [
        (f"https://bytesim.com/products/{handle}", (plan_label, region_tag))
        for handle, (plan_label, region_tag) in BYTESIM_ZONE_HANDLES.items()
    ]
    plans = _scrape_bytesim_product_list(url_iter, "zones", usd_rate)
    logger.info(f"ByteSim regions: {len(plans)} plans from {len(BYTESIM_ZONE_HANDLES)} zones")
    return plans


# ── 7G eSIM ───────────────────────────────────────────────────────────────────

SEVEN_G_DESTINATIONS = [
    "Afghanistan", "Africa", "Africa (25+ areas)", "Albania", "Algeria", "Andorra",
    "Anguilla", "Antigua And Barbuda", "Antilles", "Argentina", "Armenia", "Aruba",
    "Asia (12 areas)", "Asia (20 areas)", "Asia (20+ areas)", "Asia (7 areas)",
    "Australia", "Australia & New Zealand", "Austria", "Azerbaijan", "Azores",
    "Bahamas", "Bahrain", "Balkans (5+ areas)", "Bangladesh", "Barbados", "Belarus",
    "Belgium", "Belize", "Benin", "Bermuda", "Bhutan", "Bolivia", "Bonaire",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "British Virgin Islands", "Brunei",
    "Bulgaria", "Burkina Faso", "Burundi", "Cambodia", "Cameroon", "Canada",
    "Canary Islands", "Cape Verde", "Caribbean Islands", "Cayman Islands",
    "Central African Republic", "Central Asia", "Chad", "Chile", "China",
    "China mainland & Japan & South Korea", "Colombia", "Costa Rica",
    "Côte d'Ivoire", "Croatia", "Curaçao", "Cyprus",
    "Czech Republic", "Democratic Republic Of The Congo", "Denmark", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Estonia", "Eswatini",
    "Ethiopia", "Europe (30+ areas)", "Europe (40+ areas)", "Faroe Islands", "Fiji",
    "Finland", "France", "French Guiana", "French Polynesia", "Gabon", "Gambia",
    "GCC", "Georgia", "Germany", "Ghana", "Gibraltar", "Global (120+ areas)",
    "Global (130+ areas)", "Greece", "Greenland", "Grenada", "Guadeloupe", "Guam",
    "Guatemala", "Guinea", "Guinea-Bissau", "Gulf Region", "Guyana", "Haiti",
    "Honduras", "Hong Kong", "Hungary", "Iceland", "India", "Indonesia",
    "Iran (Islamic Republic of)", "Iraq", "Ireland", "Isle of Man", "Israel",
    "Italy", "Jamaica", "Japan", "Jersey", "Jordan", "Kazakhstan", "Kenya",
    "Kosovo", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho",
    "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Macao",
    "Madagascar", "Madeira", "Malawi", "Malaysia", "Maldives", "Mali", "Malta",
    "Marie-Galante", "Martinique", "Mauritius", "Mayotte", "Mexico", "Middle East",
    "Middle East & North Africa", "Middle East and North Africa", "Moldova",
    "Monaco", "Mongolia", "Montenegro", "Montserrat", "Morocco", "Mozambique",
    "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua",
    "Niger", "Nigeria", "North America", "North America (3 areas)",
    "North Macedonia", "Northern Cyprus", "Norway", "Oceania", "Oman", "Pakistan",
    "Palestine, State of", "Panama", "Papua New Guinea", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal", "Puerto Rico", "Qatar",
    "Republic of the Congo", "Réunion", "Romania", "Russia", "Rwanda",
    "Saba", "Saint Barthélemy", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Martin (French Part)", "Saint Vincent and the Grenadines", "Samoa",
    "Saudi Arabia", "Scotland", "Senegal", "Serbia", "Seychelles", "Sierra Leone",
    "Singapore", "Singapore & Malaysia & Thailand", "Sint Eustatius",
    "Sint Maarten (Dutch Part)", "Slovakia", "Slovenia", "South Africa",
    "South America (15+ areas)", "South Korea", "Spain", "Sri Lanka", "Suriname",
    "Sweden", "Switzerland", "Taiwan", "Tajikistan", "Tanzania", "Thailand",
    "Timor - Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey",
    "Turks and Caicos Islands", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu",
    "Vatican City", "Venezuela", "Vietnam", "Virgin Islands (U.S.)", "Zambia",
    "Zimbabwe",
]

_SEVEN_G_SLUG_OVERRIDES = {
    "republic of the congo": "congo",
}

# Canonical Hebrew region labels for extras[0] — keeps plans in the region filter
_SEVEN_G_REGION_HEB = {
    "Africa":                               "אפריקה",
    "Africa (25+ areas)":                   "אפריקה",
    "Asia (12 areas)":                      "אסיה",
    "Asia (20 areas)":                      "אסיה",
    "Asia (20+ areas)":                     "אסיה",
    "Asia (7 areas)":                       "אסיה",
    "Australia & New Zealand":              "אוקיאניה",
    "Balkans (5+ areas)":                   "בלקן",
    "Caribbean Islands":                    "איי הקריביים",
    "Central Asia":                         "מרכז אסיה",
    "China mainland & Japan & South Korea": "אסיה",
    "Europe (30+ areas)":                   "אירופה",
    "Europe (40+ areas)":                   "אירופה",
    "GCC":                                  "המזרח התיכון",
    "Global (120+ areas)":                  "גלובלי",
    "Global (130+ areas)":                  "גלובלי",
    "Gulf Region":                          "המזרח התיכון",
    "Middle East":                          "המזרח התיכון",
    "Middle East & North Africa":           "המזרח התיכון וצפון אפריקה",
    "Middle East and North Africa":         "המזרח התיכון וצפון אפריקה",
    "North America":                        "צפון אמריקה",
    "North America (3 areas)":              "צפון אמריקה",
    "Oceania":                              "אוקיאניה",
    "Singapore & Malaysia & Thailand":      "אסיה",
    "South America (15+ areas)":            "אמריקה הלטינית",
}

# Regions whose slugs can't be derived from the name — map directly to /he/esim/region/{slug}
SEVEN_G_REGION_SLUG_MAP = {
    "Africa":                                "africa",
    "Africa (25+ areas)":                    "af-29",
    "Asia (12 areas)":                       "as-12",
    "Asia (20 areas)":                       "as-20",
    "Asia (20+ areas)":                      "as-21",
    "Asia (7 areas)":                        "as-7",
    "Australia & New Zealand":               "aunz-2",
    "Balkans (5+ areas)":                    "eu-7",
    "Caribbean Islands":                     "caribbean-islands",
    "Central Asia":                          "as-5",
    "China mainland & Japan & South Korea":  "cnjpkr-3",
    "Europe (30+ areas)":                    "eu-30",
    "Europe (40+ areas)":                    "eu-42",
    "GCC":                                   "gcc",
    "Global (120+ areas)":                   "gl-120",
    "Global (130+ areas)":                   "gl-139",
    "Gulf Region":                           "me-6",
    "Middle East":                           "me-13",
    "Middle East & North Africa":            "me-12",
    "Middle East and North Africa":          "middle-east-and-north-africa",
    "North America":                         "north-america",
    "North America (3 areas)":               "na-3",
    "Oceania":                               "oceania",
    "Singapore & Malaysia & Thailand":       "sgmyth-3",
    "South America (15+ areas)":             "sa-18",
}


def _seven_g_slugify(name):
    import unicodedata as _ud
    lower = name.lower()
    if lower in _SEVEN_G_SLUG_OVERRIDES:
        return _SEVEN_G_SLUG_OVERRIDES[lower]
    name = re.sub(r"\s*\([^)]*\)", "", name).strip()
    n = _ud.normalize("NFD", name)
    n = "".join(c for c in n if _ud.category(c) != "Mn")
    n = n.replace("'", "").replace("’", "")
    n = n.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    return slug


def _parse_seven_g_page(html, usd_rate, eng_name, extras_region=None):
    from html.parser import HTMLParser as _HP

    class _TE(_HP):
        def __init__(self):
            super().__init__()
            self.texts = []

        def handle_data(self, d):
            if d.strip():
                self.texts.append(d.strip())

    p = _TE()
    p.feed(html)
    lines = p.texts

    # Hebrew name from title: "eSIM ל{name} – ..."
    heb_name = eng_name
    title_m = re.search(r"<title>([^<]+)</title>", html)
    if title_m:
        m = re.search(r"eSIM [לב](.+?) [–—]", title_m.group(1))
        if m:
            heb_name = _html_unescape(m.group(1)).strip()

    # Parse plan blocks: N GB → M ימים → US$ → price (each plan appears twice)
    seen = {}
    i = 0
    while i < len(lines):
        gb_m = re.match(r"^(\d+(?:\.\d+)?)\s*GB$", lines[i], re.I)
        if gb_m and i + 2 < len(lines):
            day_m = re.match(r"^(\d+)\s*ימים$", lines[i + 1])
            if day_m:
                price = None
                for j in range(i + 2, min(i + 8, len(lines))):
                    if lines[j] == "US$" and j + 1 < len(lines):
                        pm = re.match(r"^(\d+\.?\d*)$", lines[j + 1])
                        if pm:
                            price = float(pm.group(1))
                            break
                    pm = re.match(r"^US\$(\d+\.?\d*)$", lines[j])
                    if pm:
                        price = float(pm.group(1))
                        break
                if price is not None:
                    gb = float(gb_m.group(1))
                    days = int(day_m.group(1))
                    key = (gb, days)
                    if key not in seen or price < seen[key]:
                        seen[key] = price
        i += 1

    plans = []
    for (gb, days), usd in seen.items():
        gb_label = int(gb) if gb == int(gb) else gb
        plans.append(_make_global_plan(
            "seven_g", f"{heb_name} – ‏{gb_label}GB – ‏{days} ימים",
            round(usd * usd_rate, 2), "USD", usd,
            gb, days, extras=[extras_region if extras_region is not None else heb_name],
        ))
    return plans


def _fetch_seven_g_destination(name, usd_rate):
    import urllib.request as _ur
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    if name in SEVEN_G_REGION_SLUG_MAP:
        url = f"https://7g.app/he/esim/region/{SEVEN_G_REGION_SLUG_MAP[name]}"
        try:
            req = _ur.Request(url, headers={"User-Agent": _UA})
            with _ur.urlopen(req, timeout=15) as r:
                html = r.read().decode("utf-8")
            return _parse_seven_g_page(html, usd_rate, name, extras_region=_SEVEN_G_REGION_HEB.get(name))
        except Exception:
            return []
    slug = _seven_g_slugify(name)
    if not slug:
        return []
    try:
        req = _ur.Request(f"https://7g.app/he/esim/{slug}", headers={"User-Agent": _UA})
        with _ur.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8")
        return _parse_seven_g_page(html, usd_rate, name)
    except Exception:
        return []


def scrape_seven_g_global(_page=None, usd_rate=None):
    """Scrape 7G eSIM plans from all destinations (~190+ countries and regions)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _ac
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    all_plans = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_fetch_seven_g_destination, name, usd_rate): name
            for name in SEVEN_G_DESTINATIONS
        }
        for fut in _ac(futures):
            try:
                all_plans.extend(fut.result() or [])
            except Exception as e:
                logger.debug(f"seven_g: {futures[fut]}: {e}")
    logger.info(f"7G global: {len(all_plans)} plans from {len(SEVEN_G_DESTINATIONS)} destinations")
    return all_plans


# ── Best Connect ──────────────────────────────────────────────────────────────

_BC_API_HEADERS = {
    "x-partition-id": "c8468e6f-3041-4320-a813-bcff3ae990cf",
    "authorization": "Basic MTAxOjEwMQ==",
    "x-platform": "3",
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Regional slugs not in SAILY_SLUG_TO_HEBREW — checked before the generic lookup
_BC_REGIONAL_HEBREW = {
    "europe-esim":               "אירופה",
    "balkan":                    "בלקן",
    "turkey-and-greek-islands":  "טורקיה ואיי יוון",
}


def _fetch_bestconnect_catalog(slug, eng_name, catalog_id, usd_rate):
    import urllib.request as _ur, json as _json
    try:
        req = _ur.Request(
            f"https://bestconnect.online/api/v1/product/offerings?filters[catalog_id]={catalog_id}",
            headers=_BC_API_HEADERS,
        )
        with _ur.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read())
        # Resolve Hebrew name — regional overrides first, then SAILY lookup
        if slug in _BC_REGIONAL_HEBREW:
            heb_name = _BC_REGIONAL_HEBREW[slug]
        else:
            saily_slug = re.sub(r'-esim$', '', slug)
            heb_name = SAILY_SLUG_TO_HEBREW.get(saily_slug, SAILY_SLUG_TO_HEBREW.get(slug, eng_name))
        plans = []
        for listing in data.get("listings", []):
            prices = listing.get("prices", [])
            services = listing.get("services", [])
            if not prices or not services:
                continue
            usd = prices[0].get("price")
            days = prices[0].get("validity_days")
            total_mb = services[0].get("total_mb")
            if not (usd and days and total_mb):
                continue
            gb = round(total_mb / 1024, 3)
            gb_label = int(gb) if gb == int(gb) else gb
            plan_name = f"{heb_name} – ‏{gb_label}GB – ‏{int(days)} ימים"
            plans.append(_make_global_plan(
                "bestconnect", plan_name,
                round(float(usd) * usd_rate, 2), "USD", float(usd),
                gb, int(days), extras=[heb_name],
            ))
        return plans
    except Exception as e:
        logger.debug(f"bestconnect {slug}: {e}")
        return []


def scrape_bestconnect_global(_page=None, usd_rate=None):
    """Scrape Best Connect eSIM plans via REST API (~158 destinations)."""
    import urllib.request as _ur, json as _json
    from concurrent.futures import ThreadPoolExecutor, as_completed as _ac
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    try:
        req = _ur.Request(
            "https://bestconnect.online/api/v1/product/catalogs",
            headers=_BC_API_HEADERS,
        )
        with _ur.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read())
        catalogs = [(l["slug"], l["name"], l["catalog_id"]) for l in data.get("listings", [])]
    except Exception as e:
        logger.error(f"bestconnect: catalog fetch failed: {e}")
        return []
    all_plans = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_fetch_bestconnect_catalog, slug, name, cid, usd_rate): slug
            for slug, name, cid in catalogs
        }
        for fut in _ac(futures):
            try:
                all_plans.extend(fut.result() or [])
            except Exception as e:
                logger.debug(f"bestconnect: {futures[fut]}: {e}")
    logger.info(f"Best Connect: {len(all_plans)} plans from {len(catalogs)} catalogs")
    return all_plans


# ── eSIM Plus ─────────────────────────────────────────────────────────────────

# Maps eSIM Plus slugs that differ from SAILY_SLUG_TO_HEBREW keys
_ESIMPLUS_TO_SAILY = {
    "united-kingdom-of-great-britain": "united-kingdom",
    "usa": "united-states",
    "brunei-darussalam": "brunei",
    "viet-nam": "vietnam",
    "russian-federation": "russia",
    "cte-divoire": "cote-d-ivoire",
    "curaao": "curacao",
    "cabo-verde": "cape-verde",
    "czechia": "czech-republic",
    "macao": "macau",
    "palestine-state-of": "israel",   # db.py _DEST_NORM maps Palestine → Israel
    "runion": "reunion",
    "saint-barthlemy": "saint-barthelemy",
    "saint-vincent-and-the-grenadines": "saint-vincent-and-grenadines",
    "virgin-islands-british": "british-virgin-islands",
    "virgin-islands-us": "us-virgin-islands",
    "bonaire-sint-eustatius-and-saba": "bonaire",
    "congo-democratic-republic-of-the": "democratic-republic-of-congo",
    "land-islands": None,   # skip
    "holy-see": None,       # skip
}

ESIMPLUS_COUNTRY_SLUGS = [
    "albania", "algeria", "andorra", "angola", "anguilla", "antigua-and-barbuda",
    "argentina", "armenia", "aruba", "australia", "austria", "azerbaijan",
    "bahamas", "bahrain", "bangladesh", "barbados", "belarus", "belgium", "belize",
    "benin", "bermuda", "bolivia", "bonaire-sint-eustatius-and-saba",
    "bosnia-and-herzegovina", "botswana", "brazil", "brunei-darussalam", "bulgaria",
    "burkina-faso", "cabo-verde", "cambodia", "cameroon", "canada", "cayman-islands",
    "central-african-republic", "chad", "chile", "china", "colombia", "congo",
    "congo-democratic-republic-of-the", "costa-rica", "cte-divoire", "croatia",
    "cuba", "curaao", "cyprus", "czechia", "denmark", "dominica",
    "dominican-republic", "ecuador", "egypt", "el-salvador", "equatorial-guinea",
    "estonia", "eswatini", "ethiopia", "faroe-islands", "fiji", "finland", "france",
    "french-guiana", "french-polynesia", "gabon", "gambia", "georgia", "germany",
    "ghana", "gibraltar", "greece", "greenland", "grenada", "guadeloupe", "guam",
    "guatemala", "guernsey", "guinea", "guinea-bissau", "guyana", "haiti",
    "honduras", "hong-kong", "hungary", "iceland", "india", "indonesia", "iran",
    "iraq", "ireland", "isle-of-man", "israel", "italy", "jamaica", "japan",
    "jersey", "jordan", "kazakhstan", "kenya", "south-korea", "kyrgyzstan", "laos",
    "latvia", "lebanon", "lesotho", "liberia", "liechtenstein", "lithuania",
    "luxembourg", "macao", "madagascar", "malawi", "malaysia", "mali", "malta",
    "martinique", "mauritania", "mauritius", "mayotte", "mexico", "moldova",
    "monaco", "mongolia", "montenegro", "montserrat", "morocco", "mozambique",
    "myanmar", "namibia", "nauru", "netherlands", "new-zealand", "nicaragua",
    "niger", "nigeria", "north-macedonia", "norway", "oman", "pakistan",
    "palestine-state-of", "panama", "papua-new-guinea", "paraguay", "peru",
    "philippines", "poland", "portugal", "puerto-rico", "qatar", "runion",
    "romania", "russian-federation", "rwanda", "saint-barthlemy",
    "saint-kitts-and-nevis", "saint-lucia", "saint-martin-french-part",
    "saint-vincent-and-the-grenadines", "samoa", "saudi-arabia", "senegal",
    "serbia", "seychelles", "sierra-leone", "singapore", "slovakia", "slovenia",
    "south-africa", "south-sudan", "spain", "sri-lanka", "sudan", "suriname",
    "sweden", "switzerland", "taiwan", "tajikistan", "tanzania", "thailand",
    "togo", "tonga", "trinidad-and-tobago", "tunisia", "turkey",
    "turks-and-caicos-islands", "uganda", "ukraine", "united-arab-emirates",
    "united-kingdom-of-great-britain", "usa", "uruguay", "uzbekistan", "vanuatu",
    "viet-nam", "virgin-islands-british", "virgin-islands-us", "zambia",
    "netherlands-antilles",
    # Multi-country regions (esim-regional page)
    "asia", "africa", "balkans", "europe", "north-america", "oceania", "caribbean",
    "europe-usa", "middle-east", "americas-us-ca",
    # Global packages (esim-global page)
    "global", "global-max", "global-light", "global-standard", "europe-usa-business-hubs",
]

_ESIMPLUS_REGION_HEB = {
    "asia":                     "אסיה",
    "africa":                   "אפריקה",
    "balkans":                  "בלקן",
    "europe":                   "אירופה",
    "north-america":            "צפון אמריקה",
    "oceania":                  "אוקיאניה",
    "caribbean":                "איי הקריביים",
    "europe-usa":               'אירופה וארה"ב',
    "middle-east":              "המזרח התיכון ואפריקה",
    "americas-us-ca":           "האמריקות",
    "global":                   "גלובלי",
    "global-max":               "גלובלי",
    "global-light":             "גלובלי",
    "global-standard":          "גלובלי",
    "europe-usa-business-hubs": 'אירופה וארה"ב',
}

# Plan-name prefix for global variants that share extras[0]="גלובלי"
# Keeps DB plan_name distinct so UPSERT doesn't collide between tiers
_ESIMPLUS_PLAN_PREFIX = {
    "global-max":               "גלובלי Premium",
    "global-light":             "גלובלי Light",
    "global-standard":          "גלובלי Plus",
    "europe-usa-business-hubs": 'אירופה וארה"ב עסקים',
}


def _fetch_esimplus_country(slug, usd_rate):
    import urllib.request as _ur, base64 as _b64
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    # Resolve Hebrew name
    saily_slug = _ESIMPLUS_TO_SAILY.get(slug, slug)
    if saily_slug is None:
        return []
    heb_name = (
        _ESIMPLUS_REGION_HEB.get(slug)
        or SAILY_SLUG_TO_HEBREW.get(saily_slug)
        or SAILY_SLUG_TO_HEBREW.get(slug)
    )
    try:
        req = _ur.Request(
            f"https://esimplus.me/esim-{slug}",
            headers={"User-Agent": _UA},
        )
        with _ur.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8")
        if heb_name is None:
            title_m = re.search(r"<title>eSIM (?:for )?([^|]+)\|", html)
            heb_name = _html_unescape(title_m.group(1)).strip() if title_m else slug.replace("-", " ").title()
        # Decode paymentCode base64 PHP-serialized objects for exact prices
        codes = re.findall(r"paymentCode=([A-Za-z0-9+/%]+)", html)
        seen = {}
        for code in codes:
            try:
                data_bytes = _b64.b64decode(code + "==")
                p   = re.search(rb"\x00\*\x00price\";d:([\d.]+)", data_bytes)
                d   = re.search(rb"\x00\*\x00dataAmount\";i:(\d+)", data_bytes)
                dur = re.search(rb"\x00\*\x00duration\";i:(\d+)", data_bytes)
                t   = re.search(rb'\x00\*\x00type\";s:\d+:"([^"]+)"', data_bytes)
                if p and d and dur:
                    usd = float(p.group(1))
                    gb = int(d.group(1)) / 1000.0
                    days = int(dur.group(1))
                    plan_type = t.group(1).decode("utf-8") if t else "regular"
                    key = (gb, days, plan_type)
                    if key not in seen or usd < seen[key][0]:
                        seen[key] = (usd, plan_type)
            except Exception:
                continue
        plan_prefix = _ESIMPLUS_PLAN_PREFIX.get(slug, heb_name)
        plans = []
        for (gb, days, plan_type), (usd, _) in seen.items():
            gb_label = int(gb) if gb == int(gb) else gb
            suffix = " (שיחות+SMS)" if plan_type == "legacy" else ""
            plans.append(_make_global_plan(
                "esimplus", f"{plan_prefix} – ‏{gb_label}GB – ‏{days} ימים{suffix}",
                round(usd * usd_rate, 2), "USD", usd,
                gb, days, extras=[heb_name],
            ))
        return plans
    except Exception as e:
        logger.debug(f"esimplus {slug}: {e}")
        return []


def scrape_esimplus_global(_page=None, usd_rate=None):
    """Scrape eSIM Plus plans via per-country pages (~214 destinations)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed as _ac
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
    all_plans = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_fetch_esimplus_country, slug, usd_rate): slug
            for slug in ESIMPLUS_COUNTRY_SLUGS
        }
        for fut in _ac(futures):
            try:
                all_plans.extend(fut.result() or [])
            except Exception as e:
                logger.debug(f"esimplus: {e}")
    logger.info(f"eSIM Plus: {len(all_plans)} plans from {len(ESIMPLUS_COUNTRY_SLUGS)} destinations")
    return all_plans


# ─── Besim (https://besim.co.il) ────────────────────────────────────────
# Israeli eSIM reseller. ~130 single-country pages + 19 regional/global bundles.
# Every product page renders identical 3-line plan blocks: "<X>GB / תוקף N ימים / $price".

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
    _ensure_event_loop()
    batch_plans = []
    with sync_playwright() as pw:
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
                    batch_plans.append(_make_global_plan(
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


# ── BNESIM (bnesim.com) ──────────────────────────────────────────────────────
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
        eur_rate = _get_eur_to_ils()
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
        heb = (ORBIT_NAME_TO_HEBREW.get(dest_en)
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
                plan = _make_global_plan("bnesim", plan_name, price_ils, "EUR", price_eur,
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


def scrape_besim_global(_page=None, usd_rate=None):
    """Scrape Besim per-country eSIM plans from ~130 country pages."""
    if usd_rate is None:
        usd_rate = _get_usd_to_ils()
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
        usd_rate = _get_usd_to_ils()
    items = [
        (f"https://besim.co.il/product/{slug}", plan_label, region_tag)
        for slug, (plan_label, region_tag) in BESIM_REGIONAL_BUNDLES.items()
    ]
    plans = _scrape_besim_product_list(items, usd_rate)
    logger.info(f"Besim regions: {len(plans)} plans from {len(BESIM_REGIONAL_BUNDLES)} bundles")
    return plans


def scrape_all_global():
    """Scrape global eSIM packages from all providers. Returns flat list of plan dicts.

    Self-contained scrapers (own browser / HTTP / REST) run in parallel threads
    (max 4 concurrent) while shared-page scrapers run sequentially in the main thread.
    Both groups execute concurrently for ~12 min total vs ~35 min sequential.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    _ensure_event_loop()
    usd_rate = _get_usd_to_ils()
    eur_rate = _get_eur_to_ils()
    gbp_rate = _get_gbp_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

    # ── Sequential jobs: share one Playwright browser page ────────────────
    sequential_jobs = [
        ("scrape_tuki_global",         lambda pg: scrape_tuki_global(pg, usd_rate)),
        ("scrape_tuki_regions",        lambda pg: scrape_tuki_regions(pg, usd_rate)),
        ("scrape_tuki_local",          lambda pg: scrape_tuki_local(pg, usd_rate)),
        ("scrape_airalo_global",       lambda pg: scrape_airalo_global(pg, usd_rate)),
        ("scrape_airalo_local",        lambda pg: scrape_airalo_local(pg, usd_rate)),
        ("scrape_airalo_regional",     lambda pg: scrape_airalo_regional(pg, usd_rate)),
        ("scrape_pelephone_globalsim", scrape_pelephone_globalsim),
        ("scrape_simtlv_global",       scrape_simtlv_global),
        ("scrape_world8_global",       scrape_world8_global),
    ]

    # ── Parallel jobs: each creates its own browser / HTTP / REST ─────────
    parallel_jobs = [
        ("scrape_xphone_global",       lambda: scrape_xphone_global()),
        ("scrape_saily_global",        lambda: scrape_saily_global(usd_rate=usd_rate)),
        ("scrape_saily_regions",       lambda: scrape_saily_regions(usd_rate=usd_rate)),
        ("scrape_yesim_global",        lambda: scrape_yesim_global(usd_rate=usd_rate)),
        ("scrape_yesim_regions",       lambda: scrape_yesim_regions(usd_rate=usd_rate)),
        ("scrape_nomad_global",        lambda: scrape_nomad_global(usd_rate=usd_rate)),
        ("scrape_ubigi_global",        lambda: scrape_ubigi_global(usd_rate=usd_rate)),
        ("scrape_alosim_global",       lambda: scrape_alosim_global(usd_rate=usd_rate)),
        ("scrape_esimio_destinations", lambda: scrape_esimio_destinations(usd_rate=usd_rate)),
        ("scrape_esimio_regions",      lambda: scrape_esimio_regions(usd_rate=usd_rate)),
        ("scrape_esimo_global",        lambda: scrape_esimo_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_simtlv_esim",         lambda: scrape_simtlv_esim()),  # pure HTTP, no Playwright
        ("scrape_terminalesim",        lambda: scrape_terminalesim(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_holafly_global",      lambda: scrape_holafly_global(usd_rate=usd_rate)),
        ("scrape_holafly_regions",     lambda: scrape_holafly_regions(usd_rate=usd_rate)),
        ("scrape_sparks_global",       lambda: scrape_sparks_global(usd_rate=usd_rate)),
        ("scrape_voye_global",         lambda: scrape_voye_global(usd_rate=usd_rate)),
        ("scrape_orbit_global",        lambda: scrape_orbit_global(usd_rate=usd_rate)),
        ("scrape_travelsim",           scrape_travelsim),
        ("scrape_gomoworld_global",    lambda: scrape_gomoworld_global(gbp_rate=gbp_rate)),
        ("scrape_tasim_global",        lambda: scrape_tasim_global(usd_rate=usd_rate)),
        ("scrape_gigsky_global",       lambda: scrape_gigsky_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_esimgenius_global",   lambda: scrape_esimgenius_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_nisim_global",        lambda: scrape_nisim_global()),  # pure HTTP, ILS, no Playwright
        ("scrape_esimax_global",       lambda: scrape_esimax_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_venterrasim_global",  lambda: scrape_venterrasim_global()),  # pure HTTP, ILS, no Playwright
        ("scrape_simzol_global",       lambda: scrape_simzol_global()),  # pure HTTP, ILS, no Playwright
        ("scrape_maya_global",         lambda: scrape_maya_global(usd_rate=usd_rate)),
        ("scrape_bcengi_global",       lambda: scrape_bcengi_global(usd_rate=usd_rate)),
        ("scrape_esim70_global",        lambda: scrape_esim70_global(eur_rate=eur_rate)),
        ("scrape_bnesim_global",        lambda: scrape_bnesim_global(eur_rate=eur_rate)),
        ("scrape_jetpack_global",       lambda: scrape_jetpack_global(usd_rate=usd_rate)),
        ("scrape_breez_global",         lambda: scrape_breez_global(usd_rate=usd_rate)),
        ("scrape_bytesim_global",       lambda: scrape_bytesim_global(usd_rate=usd_rate)),
        ("scrape_bytesim_regions",      lambda: scrape_bytesim_regions(usd_rate=usd_rate)),
        ("scrape_besim_global",         lambda: scrape_besim_global(usd_rate=usd_rate)),
        ("scrape_besim_regions",        lambda: scrape_besim_regions(usd_rate=usd_rate)),
        ("scrape_seven_g_global",       lambda: scrape_seven_g_global(usd_rate=usd_rate)),
        ("scrape_bestconnect_global",   lambda: scrape_bestconnect_global(usd_rate=usd_rate)),
        ("scrape_esimplus_global",      lambda: scrape_esimplus_global(usd_rate=usd_rate)),
    ]

    plans = []

    # Submit parallel jobs immediately so they start while sequential jobs run
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_run_parallel_scraper, name, fn): name
            for name, fn in parallel_jobs
        }

        # Run sequential jobs in main thread (shares browser with no thread contention)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=ua)
            for name, fn in sequential_jobs:
                try:
                    result = fn(page)
                    if not result:
                        logger.warning(
                            f"{name}: returned 0 plans — possible bot-block or selector change. Skipping."
                        )
                    else:
                        logger.info(f"{name}: {len(result)} global plans")
                        plans.extend(result)
                except Exception as e:
                    logger.error(f"{name} failed: {e}", exc_info=True)
            browser.close()

        # Collect parallel results — 15-minute hard cap per scraper run
        try:
            for future in as_completed(futures, timeout=900):
                _, result = future.result()   # _run_parallel_scraper never raises
                plans.extend(result)
        except TimeoutError:
            for future, name in futures.items():
                if not future.done():
                    logger.error(f"{name}: timed out after 900s, skipping")

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
    {"service": "eSIM שעון", "carrier": "golan",
     "url": "https://www.golantelecom.co.il/esimwatchintro",
     "strategy": "manual_price", "price_value": "₪19.90", "free_trial": "חודש ראשון חינם"},
    # ── סייבר ──────────────────────────────────────────────────────────────
    {"service": "סייבר", "carrier": "golan",
     "url": "https://www.golantelecom.co.il/golancyber",
     "strategy": "manual_price", "price_value": "₪5.90", "free_trial": "ללא תקופת חינם"},
    # ── נורטון ─────────────────────────────────────────────────────────────
    {"service": "נורטון", "carrier": "golan",
     "url": "https://www.golantelecom.co.il/golancyber",
     "strategy": "manual_price", "price_value": "₪6.90", "free_trial": "ללא תקופת חינם"},
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
    {"service": "תא קולי", "carrier": "golan",
     "url": "https://www.golantelecom.co.il/info_and_support#faq-item-11",
     "strategy": "manual_price", "price_value": "₪5.90", "free_trial": "ללא תקופת חינם"},
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


def _cellcom_faq_esim_price(page, url, attempts=3):
    """Robustly extract the Cellcom eSIM-watch monthly price.

    The price lives only inside the "מה עלות השירות" FAQ accordion on a heavy SPA,
    so the naive click-then-read flaked intermittently and returned "לא נמצא" over a
    good price (false "service not found" alerts, 2026-05-28 + 2026-07-01). Hardened:
      1. wait for the FAQ block to actually render (not just networkidle),
      2. read answers via textContent — the answer DOM usually exists even while the
         accordion is collapsed, so no click/expand-timing dependency,
      3. fall back to expanding the FAQ (flexible text match) + innerText,
      4. fall back to a keyword-scoped scan of the rendered page + raw HTML,
      5. retry the whole flow with a fresh navigation.
    Returns a "₪X" string or None. Assumes `page` is already on `url` for attempt 0.
    """
    _ANSWER_SEL = ".FAQItemBlock__answer, [class*='answer']"
    _QUESTION_SEL = ".FAQItemBlock__question, [class*='question'], [class*='faq'] button"
    for attempt in range(attempts):
        try:
            if attempt > 0:
                page.goto(url, timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    page.wait_for_timeout(2500)
            for pct in (0.3, 0.6, 1.0):
                page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
                page.wait_for_timeout(400)
            try:
                page.wait_for_selector(".FAQItemBlock__question", timeout=8000)
            except Exception:
                pass

            # 1) collapsed answers are usually in the DOM already → textContent
            answer = page.evaluate(f"""
                () => {{
                    const els = Array.from(document.querySelectorAll("{_ANSWER_SEL}"));
                    for (const el of els) {{
                        const t = (el.textContent || '').trim();
                        if (t.includes('₪')) return t;
                    }}
                    return null;
                }}
            """)
            price = _extract_content_price(answer) if answer else None
            if price:
                return price

            # 2) expand the cost FAQ (flexible match), else expand all, then read
            page.evaluate(f"""
                () => {{
                    const qs = Array.from(document.querySelectorAll("{_QUESTION_SEL}"));
                    let hit = false;
                    for (const q of qs) {{
                        const t = (q.innerText || q.textContent || '').trim();
                        if (t.includes('עלות השירות') || t.includes('מה עלות') || t.includes('כמה עול')) {{
                            q.scrollIntoView(); q.click(); hit = true;
                        }}
                    }}
                    if (!hit) {{ for (const q of qs) {{ try {{ q.click(); }} catch (e) {{}} }} }}
                }}
            """)
            page.wait_for_timeout(2000)
            answer = page.evaluate(f"""
                () => {{
                    const els = Array.from(document.querySelectorAll("{_ANSWER_SEL}"));
                    for (const el of els) {{
                        const t = (el.innerText || el.textContent || '').trim();
                        if (t.includes('₪')) return t;
                    }}
                    return null;
                }}
            """)
            price = _extract_content_price(answer) if answer else None
            if price:
                return price

            # 3) last resort — keyword-scoped scan of rendered text + raw HTML (a
            #    naive full-page ₪ grab would risk catching an unrelated price)
            body = page.inner_text("body")
            html = re.sub(r"<[^>]+>", " ", page.evaluate("() => document.documentElement.innerHTML"))
            for text in (body, html):
                for kw in ("עלות השירות", "עלות השרות", "כמה עולה", "עלות", "לחודש"):
                    price = _extract_content_price(text, kw)
                    if price:
                        return price
        except Exception as e:
            logger.warning(f"cellcom_faq_esim attempt {attempt + 1}/{attempts} failed: {e}")
    return None


def scrape_all_content():
    """Scrape all content services (eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי).
    Returns list of dicts: {service, carrier, price, free_trial, note, status}
    """
    _ensure_event_loop()
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

            elif entry["strategy"] == "manual_price":
                price = entry.get("price_value", "לא נמצא")
                results.append(_result(price, "ידני"))
                logger.info(f"Content {service}/{carrier}: {price} (manual)")
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
                    price = _cellcom_faq_esim_price(page, url)
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
    """Scrape abroad packages from all carriers. Returns flat list of plan dicts."""
    _ensure_event_loop()
    plans = []

    # Phase 1: scrapers that open their own sync_playwright session — must run OUTSIDE
    # any outer sync_playwright context to avoid nested asyncio event-loop conflict.
    for fn in [scrape_wecom_abroad, scrape_019_abroad, scrape_golan_abroad, scrape_rami_levy_abroad]:
        try:
            result = fn()
            if not result:
                logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping.")
            else:
                logger.info(f"{fn.__name__}: {len(result)} abroad plans")
                plans.extend(result)
        except Exception as e:
            logger.error(f"{fn.__name__} failed: {e}", exc_info=True)

    # Phase 2: scrapers that share a single Playwright session
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        for fn in [scrape_partner_abroad, scrape_pelephone_abroad,
                   scrape_hotmobile_abroad, scrape_cellcom_abroad]:
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


# ── CARRIER HOMEPAGE BANNER SCREENSHOTS ──────────────────────────────────────

# Text fragments that indicate a WAF / bot-challenge / error page rather than
# the real site. Used by _is_error_page() to skip saving useless screenshots
# (the previous good banner stays on disk).
_BANNER_ERROR_INDICATORS = (
    "confirm you are human",
    "http error 503",
    "http error 502",
    "http error 504",
    "service unavailable",
    "access denied",
    "request blocked",
    "you have been blocked",
    "the owner of this website",
    "cloudflare",
    "checking your browser",
    "are you a robot",
    "התחברות נכשלה",
)


def _is_error_page(page, *, min_body_chars: int = 300) -> tuple[bool, str]:
    """
    Detect if the current page is a WAF / bot-challenge / generic error page
    instead of the real carrier site. Returns (is_error, reason).
    """
    try:
        body = (page.evaluate("document.body.innerText") or "").strip()
    except Exception as e:
        return True, f"could not read body: {e}"
    if len(body) < min_body_chars:
        return True, f"body too short ({len(body)} chars)"
    body_lc = body.lower()
    for marker in _BANNER_ERROR_INDICATORS:
        if marker in body_lc:
            return True, f"matched indicator '{marker}'"
    return False, ""


# Minimum acceptable screenshot file size in bytes. Anything smaller is almost
# always a near-blank error/challenge page rather than a real banner.
_MIN_BANNER_FILE_BYTES = 50_000


# CSS selectors for common popup close buttons (cookie banners, promos, etc.)
_POPUP_CLOSE_SELECTORS = [
    # Generic close/dismiss buttons by aria-label
    "[aria-label='Close']", "[aria-label='close']",
    "[aria-label='סגור']", "[aria-label='Close dialog']",
    # Common class/id patterns
    ".modal-close", ".popup-close", ".close-btn", ".btn-close",
    "#close-button", "#popup-close", "#modal-close",
    # Cookie consent accept/close buttons
    ".cookie-accept", ".cookie-close", ".cc-dismiss", ".cc-btn",
    "#cookie-accept", "#cookieAccept", "#acceptCookies",
    "[data-dismiss='modal']", "[data-action='close']",
    # Israeli carrier-specific patterns
    ".dialog-close", ".lightbox-close", ".overlay-close",
    # Adoric marketing popups (Partner store)
    ".closeLightboxButton", ".adoric_element.closeLightboxButton",
]

# Marketing-popup containers to force-hide before a screenshot. These are vendor /
# site-specific wrappers that the click-to-close step can miss when a page stacks
# 2-3 popups (e.g. Partner's homepage shows a native #popup1 promo AND an Adoric
# lightbox; Partner's store stacks several Adoric smartboxes). Removing the wrappers
# is safe — they are dedicated overlay containers, not page content — and far more
# reliable than clicking, which can be intercepted by a full-page Adoric backdrop.
# We deliberately do NOT blind-click every generic close selector: on SPA stores a
# stray force-click can hit a router link and navigate to a blank/loading page.
_POPUP_HIDE_JS = r"""
() => {
  let n = 0;
  const sels = [
    'div[class*="__ADORIC__"]',   // Adoric marketing popups + their full-page backdrop
    '[id^="adoric_smartbox"]',    // individual Adoric smartbox lightboxes
    '#popup1',                    // Partner homepage native promo ("ALL IN +")
  ];
  for (const s of sels) {
    for (const el of document.querySelectorAll(s)) {
      el.style.setProperty('display', 'none', 'important');
      n++;
    }
  }
  // Popups commonly lock body scroll — restore it so the hero renders normally.
  document.documentElement.style.overflow = '';
  document.body.style.overflow = '';
  return n;
}
"""

def _dismiss_popups(page) -> None:
    """Try to close any popups or overlays before taking a screenshot."""
    # 1. Press Escape — closes most modal overlays
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception:
        pass

    # 2. Click known close-button selectors (stop after first success)
    for selector in _POPUP_CLOSE_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=300):
                btn.click(timeout=500)
                page.wait_for_timeout(400)
                logger.info("Dismissed popup via selector: %s", selector)
                break
        except Exception:
            continue

    # 3. Safety net: force-hide any leftover marketing overlay (Adoric / Partner
    #    #popup1) that the single click missed. Guarantees a clean screenshot even
    #    when a page stacks multiple popups or a backdrop intercepts the close click.
    try:
        hidden = page.evaluate(_POPUP_HIDE_JS)
        if hidden:
            logger.info("Force-hid %d leftover popup container(s) before screenshot", hidden)
    except Exception:
        pass

    # 4. Final short wait to let any closing animation finish
    page.wait_for_timeout(500)


# International eSIM provider sites stack a GDPR cookie-consent banner (OneTrust /
# Cookiebot / Osano / CookieYes / Iubenda / Usercentrics / Quantcast …) AND often a
# marketing / newsletter modal — neither of which _dismiss_popups (tuned for Israeli
# carriers, clicks only ONE button on purpose) reliably clears. Accepting the cookie
# banner is the cleanest dismissal (it's what a real visitor does) and leaves the
# hero — the "main banner" — fully visible. Kept SEPARATE from _dismiss_popups so the
# domestic scrapers' careful single-click behavior is untouched.
_GLOBAL_POPUP_DISMISS_JS = r"""
() => {
  let clicked = 0, hidden = 0;

  // 1) Click well-known consent "accept all" / modal-close controls by id/class.
  const clickSels = [
    '#onetrust-accept-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    '.osano-cm-accept-all', '.osano-cm-accept',
    '.cky-btn-accept', '[data-cky-tag="accept-button"]',
    '.iubenda-cs-accept-btn',
    '#uc-btn-accept-banner', '[data-testid="uc-accept-all-button"]',
    '.cc-allow', '.cc-dismiss',
    '.cookie-accept', '#acceptCookies', '#cookie-accept', '#cookieAccept',
    '.termly-styles-buttonPrimary',
    '#hs-eu-confirmation-button',
    '.qc-cmp2-summary-buttons button[mode="primary"]',
    'button[aria-label="Accept all"]', 'button[aria-label="Accept"]',
    '[aria-label="Close"]', '[aria-label="close"]', '[aria-label="Dismiss"]',
    '.modal-close', '.popup-close', '.close-btn', '.btn-close', '[data-dismiss="modal"]',
  ];
  for (const s of clickSels) {
    document.querySelectorAll(s).forEach(el => {
      try { const r = el.getBoundingClientRect(); if (r.width && r.height) { el.click(); clicked++; } } catch (e) {}
    });
  }

  // 2) Click buttons/links by their TEXT (frameworks without stable ids). Kept
  //    consent-specific + short so we never hit a hero CTA (e.g. "Buy", "Continue").
  const wantText = ['accept all','accept cookies','accept','allow all','allow cookies',
    'i agree','agree','got it','אני מסכים','מאשר','אישור','קבל','סגור'];
  document.querySelectorAll('button, a, [role="button"]').forEach(el => {
    const t = (el.innerText || el.textContent || '').trim().toLowerCase();
    if (!t || t.length > 20) return;
    if (wantText.includes(t)) { try { el.click(); clicked++; } catch (e) {} }
  });

  // 3) Force-hide known consent-SDK / overlay containers that survive clicking,
  //    plus the Israeli Adoric marketing wrappers (some .co.il global providers).
  const hideSels = [
    '#onetrust-consent-sdk', '#onetrust-banner-sdk',
    '#CybotCookiebotDialog', '.CybotCookiebotDialog', '#CybotCookiebotDialogBodyUnderlay',
    '.osano-cm-window', '.osano-cm-dialog',
    '.cky-consent-container', '.cky-overlay', '.cky-modal',
    '.iubenda-cs-container', '#iubenda-cs-banner',
    '#usercentrics-root', '#uc-center-container', '#usercentrics-cmp-ui',
    '[id*="usercentrics"]', 'usercentrics-root', 'usercentrics-cmp-ui',
    '#axeptio_overlay', '.axeptio_mount', '[class*="axeptio"]', '#axeptio_main_button',
    '.termly-consent-banner', '#hs-eu-cookie-confirmation',
    '.qc-cmp2-container', '#qc-cmp2-container',
    '.cc-window', '#gdpr-cookie-message', '#gdpr-cookie-notice',
    '[class*="cookie-consent"]', '[id*="cookie-consent"]', '[class*="CookieConsent"]',
    'div[class*="__ADORIC__"]', '[id^="adoric_smartbox"]',
  ];
  for (const s of hideSels) {
    document.querySelectorAll(s).forEach(el => { el.style.setProperty('display','none','important'); hidden++; });
  }

  // 4) Hide common backdrop/overlay wrappers by class so the dimming layer behind a
  //    modal doesn't leave the screenshot darkened. NB: match SPECIFIC backdrop
  //    classes — a bare [class*="backdrop"] wrongly hits Tailwind's `backdrop-blur`
  //    utility (used on sticky headers), which nuked real nav bars.
  const overlaySels = ['.modal-backdrop', '.modal-overlay', '[class*="modal-backdrop"]',
    '[class*="ModalBackdrop"]', '.cdk-overlay-backdrop', '.MuiBackdrop-root',
    '.ReactModal__Overlay', '.fancybox-container', '.fancybox__backdrop',
    '[class*="overlay"][class*="open"]', '[class*="Overlay"][class*="open"]'];
  for (const s of overlaySels) {
    document.querySelectorAll(s).forEach(el => { el.style.setProperty('display','none','important'); hidden++; });
  }

  // 5) General overlay/modal killer: any fixed/sticky element with a high z-index
  //    that either covers most of the viewport (backdrop / full-screen modal) or sits
  //    as a large centered box (cookie / language / newsletter dialog). Hero content
  //    is never position:fixed, and sticky top nav / slim footers are excluded, so
  //    this removes the popup without touching the banner.
  const vw = innerWidth, vh = innerHeight;
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') return;
    if ((parseInt(cs.zIndex, 10) || 0) < 100) return;
    const r = el.getBoundingClientRect();
    if (r.width < 60 || r.height < 60) return;
    if (r.top <= 2 && r.height <= vh * 0.2) return;            // sticky top nav — keep
    if (r.bottom >= vh - 2 && r.height <= vh * 0.15) return;   // slim sticky footer — keep
    const coversMost  = r.width >= vw * 0.85 && r.height >= vh * 0.85;
    const centeredBox = r.width >= vw * 0.3 && r.height >= vh * 0.25 &&
                        r.top > vh * 0.02 && r.top < vh * 0.6;
    const cls = ((el.className && el.className.toString ? el.className.toString() : '') + ' ' + (el.id || '')).toLowerCase();
    const looksOverlay = /(overlay|backdrop|modal|popup|lightbox|dialog|drawer|cookie|consent|lang|newsletter|subscribe)/.test(cls)
      || /rgba\(0,\s*0,\s*0/.test(cs.backgroundColor)
      || !!el.querySelector('[role="dialog"], [class*="modal"], [class*="popup"], [class*="lightbox"]');
    if ((coversMost && looksOverlay) || centeredBox) {
      el.style.setProperty('display','none','important'); hidden++;
    }
  });

  // 5b) Shadow-DOM consent (Usercentrics v2 et al. render the banner inside a
  //     custom-element shadow root, so the light-DOM button/text passes miss it).
  document.querySelectorAll('*').forEach(el => {
    const sr = el.shadowRoot;
    if (!sr) return;
    sr.querySelectorAll('button, [role="button"]').forEach(b => {
      const t = (b.innerText || b.textContent || '').trim().toLowerCase();
      if (b.getAttribute && b.getAttribute('data-testid') === 'uc-accept-all-button') { try { b.click(); clicked++; } catch (e) {} return; }
      if (['accept all','accept cookies','accept','allow all','agree','i agree','ok','got it','אני מסכים','מאשר','אישור','קבל'].includes(t)) {
        try { b.click(); clicked++; } catch (e) {}
      }
    });
    const hostId = ((el.id || '') + ' ' + (el.tagName || '')).toLowerCase();
    if (/usercentrics|consent|cookie|cmp|gdpr/.test(hostId)) { el.style.setProperty('display','none','important'); hidden++; }
  });

  // 6) Consent-text pass: cookie banners are often bottom-anchored (top > 60%, so
  //    the geometry rules above miss them). Hide any fixed/sticky/absolute strip whose
  //    text (or class/id) is clearly a cookie/consent notice — EN or HE (Israeli
  //    providers like GlobalSIM show a Hebrew "שימוש ב-Cookies … מדיניות הפרטיות" bar).
  //    The nav/header guard means a sticky menu that merely links to a cookie policy
  //    is never nuked.
  document.querySelectorAll('div,section,aside,footer').forEach(el => {
    if (el.tagName === 'HEADER' || el.querySelector('nav, header')) return;
    const cs = getComputedStyle(el);
    if (!['fixed','sticky','absolute'].includes(cs.position)) return;
    const r = el.getBoundingClientRect();
    if (r.height > vh * 0.7 || r.width < vw * 0.3 || r.width < 200) return;  // strip, not whole page
    const low = (el.innerText || '').slice(0, 600).toLowerCase();
    const clsid = ((el.className && el.className.toString ? el.className.toString() : '') + ' ' + (el.id || '')).toLowerCase();
    const cookieTok = low.includes('cookie') || low.includes('עוגיות') || low.includes('קוקיז')
      || /(cookie|consent|gdpr)/.test(clsid);
    const consentWord = /(accept|consent|agree|continue|got it|confirm|understood|\bok\b|manage|policy|settings|allow|preferences)/.test(low)
      || /(מדיניות|פרטיות|מסכים|אישור|לאשר|הסכמה|שימוש ב)/.test(low);
    const isConsent = low.includes('we use cookies') || low.includes('uses cookies') ||
      low.includes('gdpr') || (cookieTok && consentWord);
    if (isConsent) { el.style.setProperty('display','none','important'); hidden++; }
  });

  // 7) Restore scroll that popups commonly lock so the hero renders normally.
  document.documentElement.style.overflow = '';
  document.body.style.overflow = '';
  document.body.style.position = '';
  return { clicked, hidden };
}
"""


def _dismiss_global_popups(page) -> None:
    """Aggressively clear cookie-consent + marketing popups on international
    provider sites so the screenshot shows only the hero banner."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        pass
    # Two main-document passes — a 2nd modal often appears only after the consent
    # banner is accepted/closed.
    for _ in range(2):
        try:
            res = page.evaluate(_GLOBAL_POPUP_DISMISS_JS)
            if res and (res.get("clicked") or res.get("hidden")):
                logger.info("Global popup dismiss: clicked=%s hidden=%s",
                            res.get("clicked"), res.get("hidden"))
        except Exception:
            pass
        page.wait_for_timeout(500)
    # Iframe-based consent (Quantcast / TrustArc / some Cookiebot render in an iframe).
    for fr in page.frames:
        for sel in ("#onetrust-accept-btn-handler",
                    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                    "button[aria-label='Accept all']",
                    ".qc-cmp2-summary-buttons button[mode='primary']"):
            try:
                loc = fr.locator(sel).first
                if loc.is_visible(timeout=200):
                    loc.click(timeout=500)
                    page.wait_for_timeout(300)
            except Exception:
                continue
    # Final late pass — some banners (Axeptio, a few Hebrew bars) inject a second or
    # two after load, after the passes above already ran.
    page.wait_for_timeout(1300)
    try:
        page.evaluate(_GLOBAL_POPUP_DISMISS_JS)
    except Exception:
        pass
    page.wait_for_timeout(400)


# Persistent consent-hider — installed as an init script so it runs on every page
# load and keeps HIDING (not clicking) known consent containers + fixed cookie-text
# strips on a 500ms interval for ~15s. Timing-independent: a banner injected 8-12s
# after load (e.g. TravelSim's Hebrew bar, which isn't in the DOM even at 9s) is
# removed within half a second of appearing, regardless of when the one-shot
# dismissal passes ran. Only hides consent-shaped elements, never navs/heroes.
_PERSISTENT_CONSENT_HIDER_JS = r"""
(() => {
  const SELS = [
    '#onetrust-consent-sdk','#onetrust-banner-sdk','#CybotCookiebotDialog','.CybotCookiebotDialog',
    '#CybotCookiebotDialogBodyUnderlay','.osano-cm-window','.osano-cm-dialog','.cky-consent-container',
    '.cky-overlay','.cky-modal','.iubenda-cs-container','#iubenda-cs-banner','#usercentrics-root',
    '#usercentrics-cmp-ui','[id*="usercentrics"]','usercentrics-root','usercentrics-cmp-ui',
    '#axeptio_overlay','.axeptio_mount','[class*="axeptio"]','#axeptio_main_button','.termly-consent-banner',
    '#hs-eu-cookie-confirmation','.qc-cmp2-container','#qc-cmp2-container','.cc-window','#gdpr-cookie-message',
    '#gdpr-cookie-notice','[class*="cookie-consent"]','[id*="cookie-consent"]','[class*="CookieConsent"]',
    'div[class*="__ADORIC__"]','[id^="adoric_smartbox"]'
  ];
  const hide = () => {
    for (const s of SELS) { try { document.querySelectorAll(s).forEach(el => el.style.setProperty('display','none','important')); } catch (e) {} }
    if (!document.body) return;
    const vw = innerWidth, vh = innerHeight;
    document.querySelectorAll('div,section,aside,footer').forEach(el => {
      if (el.tagName === 'HEADER' || el.querySelector('nav, header')) return;
      const cs = getComputedStyle(el);
      if (!['fixed','sticky','absolute'].includes(cs.position)) return;
      const r = el.getBoundingClientRect();
      if (r.height > vh * 0.7 || r.width < vw * 0.3 || r.width < 200) return;
      const low = (el.innerText || '').slice(0, 600).toLowerCase();
      const clsid = ((el.className && el.className.toString ? el.className.toString() : '') + ' ' + (el.id || '')).toLowerCase();
      const cookieTok = low.includes('cookie') || low.includes('עוגיות') || low.includes('קוקיז') || /(cookie|consent|gdpr)/.test(clsid);
      const consentWord = /(accept|consent|agree|continue|got it|confirm|understood|\bok\b|manage|policy|settings|allow|preferences)/.test(low)
        || /(מדיניות|פרטיות|מסכים|אישור|לאשר|הסכמה|שימוש ב)/.test(low);
      if (low.includes('we use cookies') || low.includes('uses cookies') || low.includes('gdpr') || (cookieTok && consentWord)) {
        el.style.setProperty('display','none','important');
      }
    });
    document.documentElement.style.overflow = ''; document.body.style.overflow = '';
  };
  let n = 0;
  const iv = setInterval(() => { try { hide(); } catch (e) {} if (++n > 30) clearInterval(iv); }, 500);
  try { hide(); } catch (e) {}
})();
"""


CARRIER_HOMEPAGE_URLS = {
    "partner":   "https://www.partner.net.il",
    "pelephone": "https://www.pelephone.co.il",
    "hotmobile": "https://www.hotmobile.co.il",
    "cellcom":   "https://www.cellcom.co.il",
    "mobile019": "https://www.019mobile.co.il",
    "xphone":    "https://www.xphone.co.il",
    "wecom":     "https://we-com.co.il",
    "neptucom":  "https://www.neptucom.com",
    "golan":     "https://www.golantelecom.co.il",
    "rami_levy": "https://mobile.rami-levy.co.il",
}

_STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _banner_019_stealth(url: str, out_path: str, scraped_at: str) -> dict:
    """
    Take a banner screenshot of 019mobile using playwright-stealth to bypass
    Imperva/Incapsula WAF.  Returns the same result dict as the main loop.
    """
    try:
        from playwright_stealth import Stealth
        with Stealth().use_sync(sync_playwright()) as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.set_viewport_size({"width": 1280, "height": 720})
                page.goto(url, timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                # If page is too small it's still a challenge page — bail out
                if len(page.content()) < 8000:
                    logger.warning("_banner_019_stealth: WAF challenge still active, skipping screenshot.")
                    return {"carrier": "mobile019", "scraped_at": scraped_at, "success": False}
                _dismiss_popups(page)
                page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                file_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
                if file_size < 5000:
                    logger.warning("_banner_019_stealth: screenshot too small (%d bytes), removing.", file_size)
                    os.remove(out_path)
                    return {"carrier": "mobile019", "scraped_at": scraped_at, "success": False}
                logger.info("Banner screenshot saved (stealth): %s", out_path)
                return {"carrier": "mobile019", "scraped_at": scraped_at, "success": True}
            finally:
                browser.close()
    except Exception as exc:
        logger.warning("_banner_019_stealth failed: %s", exc)
        return {"carrier": "mobile019", "scraped_at": scraped_at, "success": False}


def _banner_xphone_stealth(url: str, out_path: str, scraped_at: str) -> dict:
    """
    Take a banner screenshot of XPhone using a fresh session + Chrome 124 UA to bypass
    AWS WAF (same workaround used by scrape_xphone for plan data).
    """
    try:
        from playwright.sync_api import sync_playwright as _sp
        with _sp() as pw:
            # AWS WAF serves a JS challenge that headless Chromium fails.
            # headed=False fails (202 + empty body); headed=True passes the challenge.
            browser = pw.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=_XPHONE_UA,
                viewport={"width": 1280, "height": 720},
                locale="he-IL",
                extra_http_headers={
                    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            page = context.new_page()
            try:
                try:
                    resp = page.goto(url, timeout=40000, wait_until="domcontentloaded")
                except Exception:
                    resp = None
                page.wait_for_timeout(12000)  # extra time for JS challenge to complete
                body = page.evaluate("document.body.innerText") or ""
                if len(body) < 300 or "confirm you are human" in body.lower() or "http error 503" in body.lower():
                    logger.warning("_banner_xphone_stealth: site unavailable or WAF block (body=%d chars), skipping.", len(body))
                    return {"carrier": "xphone", "scraped_at": scraped_at, "success": False}
                _dismiss_popups(page)
                page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                import os as _os
                file_size = _os.path.getsize(out_path) if _os.path.exists(out_path) else 0
                if file_size < 5000:
                    logger.warning("_banner_xphone_stealth: screenshot too small (%d bytes), likely blank.", file_size)
                    _os.remove(out_path)  # remove bad file so previous good screenshot stays on disk
                    return {"carrier": "xphone", "scraped_at": scraped_at, "success": False}
                logger.info("Banner screenshot saved (xphone stealth): %s (%d bytes)", out_path, file_size)
                return {"carrier": "xphone", "scraped_at": scraped_at, "success": True}
            finally:
                browser.close()
    except Exception as exc:
        logger.warning("_banner_xphone_stealth failed: %s", exc)
        return {"carrier": "xphone", "scraped_at": scraped_at, "success": False}


def scrape_carrier_banners(output_dir: str) -> list[dict]:
    """
    Navigate to each domestic carrier homepage and save a 1280x720 PNG screenshot.
    Returns a list of dicts: { carrier, scraped_at, success }.
    output_dir — absolute path to the folder where PNGs will be saved.
    """
    _ensure_event_loop()
    results = []
    os.makedirs(output_dir, exist_ok=True)

    # Phase 1: WAF-protected carriers — each stealth helper opens its own
    # sync_playwright() session, so they MUST run outside the shared session
    # below (Playwright forbids nested sync contexts in the same thread).
    stealth_carriers = {
        "mobile019": _banner_019_stealth,
        "xphone":    _banner_xphone_stealth,
    }
    for carrier, fn in stealth_carriers.items():
        if carrier not in CARRIER_HOMEPAGE_URLS:
            continue
        out_path = os.path.join(output_dir, f"{carrier}.png")
        scraped_at = datetime.now(timezone.utc).isoformat()
        results.append(fn(CARRIER_HOMEPAGE_URLS[carrier], out_path, scraped_at))

    # Phase 2: regular carriers — share a single Playwright session.
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,  # some carriers have cert mismatches
            )

            for carrier, url in CARRIER_HOMEPAGE_URLS.items():
                if carrier in stealth_carriers:
                    continue  # handled in Phase 1
                out_path = os.path.join(output_dir, f"{carrier}.png")
                scraped_at = datetime.now(timezone.utc).isoformat()
                page = context.new_page()  # fresh page per carrier — avoids cross-navigation pollution
                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)  # let hero images render
                    _dismiss_popups(page)
                    page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                    results.append({"carrier": carrier, "scraped_at": scraped_at, "success": True})
                    logger.info("Banner screenshot saved: %s", out_path)
                except Exception as exc:
                    logger.warning("Banner screenshot failed for %s: %s", carrier, exc)
                    results.append({"carrier": carrier, "scraped_at": scraped_at, "success": False})
                finally:
                    page.close()
        finally:
            browser.close()

    return results


CARRIER_STORE_URLS = {
    "pelephone": "https://www.pelephone.co.il/ds/heb/eshop/lobby/",
    "cellcom":   "https://shop.cellcom.co.il/",
    "partner":   "https://store.partner.co.il/home",
    "hotmobile": "https://hotstore.hotmobile.co.il/smartphones.html",
}


def scrape_carrier_store_banners(output_dir: str) -> list[dict]:
    """
    Navigate to each carrier e-store page and save a 1280x720 PNG screenshot.
    Files are saved as {carrier}_store.png in output_dir.
    Returns a list of dicts: { carrier, scraped_at, success }.
    """
    _ensure_event_loop()
    results = []
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )

            for carrier, url in CARRIER_STORE_URLS.items():
                out_path = os.path.join(output_dir, f"{carrier}_store.png")
                scraped_at = datetime.now(timezone.utc).isoformat()
                # Try up to 2 times — WAF 503 / bot-challenge pages are often
                # transient on retry with a fresh page/context.
                success = False
                last_reason = ""
                for attempt in (1, 2):
                    page = context.new_page()
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        # Store pages load marketing popups with a delay — wait longer than homepage scraper
                        page.wait_for_timeout(4000)
                        is_err, reason = _is_error_page(page)
                        if is_err:
                            last_reason = f"attempt {attempt}: {reason}"
                            logger.warning("Store banner %s: skipping bad page (%s)", carrier, last_reason)
                            if attempt == 1:
                                page.wait_for_timeout(3000)  # brief backoff before retry
                            continue
                        _dismiss_popups(page)
                        tmp_path = out_path + ".new.png"
                        page.screenshot(path=tmp_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                        file_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
                        if file_size < _MIN_BANNER_FILE_BYTES:
                            last_reason = f"attempt {attempt}: screenshot too small ({file_size} bytes)"
                            logger.warning("Store banner %s: %s", carrier, last_reason)
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                            continue
                        # Valid — atomically replace the existing banner.
                        os.replace(tmp_path, out_path)
                        success = True
                        logger.info("Store banner screenshot saved: %s (%d bytes)", out_path, file_size)
                        break
                    except Exception as exc:
                        last_reason = f"attempt {attempt}: {exc}"
                        logger.warning("Store banner attempt %d failed for %s: %s", attempt, carrier, exc)
                    finally:
                        page.close()
                if not success:
                    logger.warning("Store banner FAILED for %s after retries; previous banner preserved (%s)",
                                   carrier, last_reason)
                results.append({"carrier": carrier, "scraped_at": scraped_at, "success": success})
        finally:
            browser.close()

    return results


# ── Global eSIM provider homepage banners ───────────────────────────────────
# Screenshot the MAIN (homepage) banner of every global eSIM provider once per
# capture, exactly like the domestic carrier banners. Files are saved as
# {provider}_global.png in the same data/banners/ folder. URLs are the provider's
# clean homepage root (the "main banner"), NOT an Israel deep-link — mirror of
# app.py's GLOBAL_PROVIDERS_REGISTRY / _GUEST_PROVIDER_META ids.
GLOBAL_BANNER_URLS = {
    "seven_g":          "https://7g.app",
    "world8":           "https://world8.co.il",
    "airalo":           "https://www.airalo.com",
    "bcengi":           "https://www.bcengi.com",
    "besim":            "https://besim.co.il",
    "bestconnect":      "https://bestconnect.online",
    "bnesim":           "https://www.bnesim.com",
    "breez":            "https://breezesim.com",
    "bytesim":          "https://bytesim.com",
    "esimplus":         "https://esimplus.me",
    "esimio":           "https://esim.io",
    "esim70":           "https://esim70.com",
    "esimgenius":       "https://esimgenius.ai",
    "esimax":           "https://esimax.io",
    "esimo":            "https://esimo.io",
    "terminalesim":     "https://terminalesim.com",
    "gigsky":           "https://www.gigsky.com",
    "pelephone_global": "https://www.pelephone.co.il/digitalsite/heb/abroad/global-sim/",
    "gomoworld":        "https://www.gomoworld.com",
    "holafly":          "https://esim.holafly.com",
    "jetpack":          "https://www.jetpacglobal.com",
    "maya":             "https://maya.net",
    "nisim":            "https://www.nisim-esim.co.il",
    "orbit":            "https://orbitmobile.com",
    "saily":            "https://saily.com",
    "simtlv":           "https://simtlv.co.il",
    "sparks":           "https://www.sparks.travel",
    "tasim":            "https://tasim.us",
    "travelsim":        "https://travelsimobile.co.il",
    "tuki":             "https://tuki-esim.co.il",
    "venterrasim":      "https://venterrasim.com",
    "simzol":           "https://www.simzol.co.il",
    "voye":             "https://voyeglobal.com",
    "xphone_global":    "https://www.xphone.co.il",
    "yesim":            "https://yesim.app",
    "nomad":            "https://www.nomadesim.com",
    "ubigi":            "https://www.ubigi.com",
    "alosim":           "https://alosim.com",
}


# "Banner changed" (freshness) tracking. We store a small perceptual average-hash
# (aHash) per provider in a JSON sidecar; when a fresh capture's aHash drifts past a
# threshold from the stored one, the provider changed its homepage campaign and we
# stamp changed_at=now. A perceptual hash (not sha256) is used so minor rendering
# noise — antialiasing, a blinking cursor — doesn't trigger a false "changed".
_GLOBAL_BANNER_STATE_FILE = "_global_banner_state.json"
_BANNER_CHANGE_THRESHOLD = 18   # aHash bits (out of 256) that must differ = a real change


def _banner_ahash(path: str):
    """16x16 grayscale average-hash → 256-char bit string (None on failure)."""
    try:
        from PIL import Image
        img = Image.open(path).convert("L").resize((16, 16))
        px = list(img.getdata())
        avg = sum(px) / len(px)
        return "".join("1" if p >= avg else "0" for p in px)
    except Exception as exc:
        logger.warning("aHash failed for %s: %s", path, exc)
        return None


def _ahash_distance(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 999
    return sum(1 for x, y in zip(a, b) if x != y)


def _load_global_banner_state(output_dir: str) -> dict:
    import json
    try:
        with open(os.path.join(output_dir, _GLOBAL_BANNER_STATE_FILE), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_global_banner_state(output_dir: str, state: dict) -> None:
    import json
    try:
        with open(os.path.join(output_dir, _GLOBAL_BANNER_STATE_FILE), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as exc:
        logger.warning("Could not write global banner state: %s", exc)


def scrape_global_provider_banners(output_dir: str) -> list[dict]:
    """
    Navigate to each global eSIM provider's homepage and save a 1280x720 PNG.
    Files are saved as {provider}_global.png in output_dir.
    Returns a list of dicts: { carrier, scraped_at, success }.

    Mirrors scrape_carrier_store_banners: 2 attempts, error-page detection,
    min-size guard, atomic replace — so a failed capture preserves the previous
    good screenshot instead of overwriting it with a blank/consent page. On each
    successful capture it also updates the perceptual-hash state so the API can
    flag which banners changed their campaign (freshness badge).
    """
    _ensure_event_loop()
    results = []
    os.makedirs(output_dir, exist_ok=True)
    state = _load_global_banner_state(output_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )
            # Persistent hider catches late-injected consent banners regardless of
            # the one-shot dismissal timing.
            context.add_init_script(_PERSISTENT_CONSENT_HIDER_JS)

            for provider, url in GLOBAL_BANNER_URLS.items():
                out_path = os.path.join(output_dir, f"{provider}_global.png")
                scraped_at = datetime.now(timezone.utc).isoformat()
                success = False
                last_reason = ""
                for attempt in (1, 2):
                    page = context.new_page()
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        # Global SPA sites render hero + consent banners with a delay.
                        page.wait_for_timeout(4000)
                        is_err, reason = _is_error_page(page)
                        if is_err:
                            last_reason = f"attempt {attempt}: {reason}"
                            logger.warning("Global banner %s: skipping bad page (%s)", provider, last_reason)
                            if attempt == 1:
                                page.wait_for_timeout(3000)
                            continue
                        # International cookie-consent + marketing popups need the
                        # aggressive dismissal, not the Israeli-tuned _dismiss_popups.
                        _dismiss_global_popups(page)
                        tmp_path = out_path + ".new.png"
                        page.screenshot(path=tmp_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                        file_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
                        if file_size < _MIN_BANNER_FILE_BYTES:
                            last_reason = f"attempt {attempt}: screenshot too small ({file_size} bytes)"
                            logger.warning("Global banner %s: %s", provider, last_reason)
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                            continue
                        os.replace(tmp_path, out_path)
                        success = True
                        logger.info("Global banner screenshot saved: %s (%d bytes)", out_path, file_size)
                        # ── Freshness tracking: mark changed_at when the campaign drifts.
                        new_h = _banner_ahash(out_path)
                        prev = state.get(provider) or {}
                        prev_h = prev.get("hash")
                        if not prev_h or new_h is None:
                            # First-ever baseline (or hash failure) — record, don't flag.
                            changed_at = prev.get("changed_at")
                        elif _ahash_distance(new_h, prev_h) > _BANNER_CHANGE_THRESHOLD:
                            changed_at = datetime.now(timezone.utc).isoformat()
                            logger.info("Global banner CHANGED: %s", provider)
                        else:
                            changed_at = prev.get("changed_at")
                        state[provider] = {"hash": new_h or prev_h, "changed_at": changed_at}
                        break
                    except Exception as exc:
                        last_reason = f"attempt {attempt}: {exc}"
                        logger.warning("Global banner attempt %d failed for %s: %s", attempt, provider, exc)
                    finally:
                        page.close()
                if not success:
                    logger.warning("Global banner FAILED for %s after retries; previous banner preserved (%s)",
                                   provider, last_reason)
                results.append({"carrier": provider, "scraped_at": scraped_at, "success": success})
        finally:
            browser.close()

    _save_global_banner_state(output_dir, state)
    return results
