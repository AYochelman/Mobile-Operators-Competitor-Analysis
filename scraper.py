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


def scrape_all():
    """Scrape all 5 carriers sequentially. Returns flat list of plan dicts."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        plans = []
        for fn in [scrape_partner, scrape_pelephone, scrape_hotmobile, scrape_cellcom, scrape_019]:
            try:
                result = fn(page)
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


def scrape_019(page):
    page.goto("https://019mobile.co.il/חבילות-סלולר/", timeout=30000, wait_until="networkidle")
    page.wait_for_selector(".list .item", timeout=15000)
    plans = []
    for card in page.query_selector_all(".list .item:not(.item_hor)"):
        name_el  = card.query_selector("h3.title")
        price_el = card.query_selector(".price")
        extras   = [el.inner_text().strip() for el in card.query_selector_all(".blist li") if el.inner_text().strip()]
        # Find data (GB/MB) specifically from the "גלישה" line in extras
        gb = None
        for item_el in card.query_selector_all(".blist li"):
            text = item_el.inner_text().strip()
            if "גלישה" in text or ("GB" in text and "גלישה" not in text) or "MB" in text.upper():
                if "גלישה" in text or re.search(r"\d+\s*(GB|MB|gb|mb)", text):
                    gb = _parse_gb(text)
                    break
        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        if name and name != "לא ידוע":
            plans.append({"carrier": "mobile019", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": None, "extras": extras})
    return plans


# ── Abroad / Roaming scrapers ──────────────────────────────────────────────

def scrape_pelephone_abroad(page):
    page.goto("https://www.pelephone.co.il/digitalsite/heb/abroad/packages/",
              timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(2000)
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
        name = re.sub(r'\s+', ' ', ttl_text.replace(period_text, "").replace(price_text, "")).strip()
        price = _parse_price(price_text)
        days  = _parse_days(period_text)
        gb_el  = card.query_selector(".data .g_d_s .g")
        min_el = card.query_selector(".data .g_d_s .d")
        sms_el = card.query_selector(".data .g_d_s .s")
        gb      = _parse_gb(gb_el.inner_text())       if gb_el  else None
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
    page.goto("https://cellcom.co.il/AbroadMain/lobby/", timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(3000)
    plans = []
    for card in page.query_selector_all(".abroad-package-client"):
        name_el     = card.query_selector(".abroad-package-client__title")
        duration_el = card.query_selector(".abroad-package-client__duration")
        data_el     = card.query_selector(".abroad-package-client__data--bank")
        voice_sms   = card.query_selector_all(".abroad-package-voice-sms__value")
        price_el    = card.query_selector(".abroad-package-client__price-real--bank--container")
        name = name_el.inner_text().strip() if name_el else "לא ידוע"
        days = _parse_days(duration_el.inner_text() if duration_el else "")
        gb   = _parse_gb(data_el.inner_text())       if data_el else None
        minutes = _parse_minutes(voice_sms[0].inner_text()) if len(voice_sms) > 0 else None
        sms     = _parse_sms(voice_sms[1].inner_text())     if len(voice_sms) > 1 else None
        price = None
        if price_el:
            for span in price_el.query_selector_all("span"):
                t = span.inner_text().strip()
                if re.match(r'^\d', t):
                    price = _parse_price(t)
                    break
        extras = []
        app_el = card.query_selector(".abroad-package-client__data--bank-unlimited-app--text")
        if app_el:
            t = app_el.inner_text().strip()
            if t:
                extras.append(t)
        if name and name != "לא ידוע":
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": extras})
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


def scrape_019_abroad(page):
    page.goto(
        "https://019mobile.co.il/%d7%92%d7%9c%d7%99%d7%a9%d7%94-%d7%91%d7%97%d7%95%d7%9c-"
        "%d7%97%d7%91%d7%99%d7%9c%d7%94-%d7%9c%d7%97%d7%95%d7%9c-%d7%97%d7%91%d7%99%d7%9c%d7%95%d7%aa-"
        "%d7%90%d7%99%d7%a0%d7%98%d7%a8%d7%a0%d7%98/",
        timeout=30000, wait_until="networkidle"
    )
    page.wait_for_timeout(2000)
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
        price = None
        if price_el:
            price = _parse_price(price_el.inner_text().replace("₪", "").strip())
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


def scrape_all_abroad():
    """Scrape abroad packages from all 5 carriers. Returns flat list of plan dicts."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        plans = []
        for fn in [scrape_partner_abroad, scrape_pelephone_abroad,
                   scrape_hotmobile_abroad, scrape_cellcom_abroad, scrape_019_abroad]:
            try:
                result = fn(page)
                logger.info(f"{fn.__name__}: {len(result)} abroad plans")
                plans.extend(result)
            except Exception as e:
                logger.error(f"{fn.__name__} failed: {e}", exc_info=True)
        browser.close()
    return plans
