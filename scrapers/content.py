"""Content services (eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי) across the 4 big carriers.

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


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


def scrape_all_content():
    """Scrape all content services (eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי).
    Returns list of dicts: {service, carrier, price, free_trial, note, status}
    """
    core._ensure_event_loop()
    from datetime import datetime as _dt
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    results = []

    with core.sync_playwright() as p:
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
                    price = core._cellcom_hub_price(page, entry["page_keyword"])
                    results.append(_result(price or "לא נמצא", "נמצא" if price else "לא נמצא"))

                # ── Cellcom FAQ (eSIM שעון) ───────────────────────────────
                elif entry["strategy"] == "cellcom_faq_esim":
                    price = core._cellcom_faq_esim_price(page, url)
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
