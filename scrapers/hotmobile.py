"""hotmobile scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


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
        price = core._parse_price(data_price) if data_price else (core._parse_price(price_el.inner_text()) if price_el else None)

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
                parsed = core._parse_gb(t)
                if parsed is not None and parsed > best_gb:
                    best_gb, best_text = parsed, t
            gb_text = best_text
        # Fallback extras
        if not extras:
            extras = [el.inner_text().strip() for el in card.query_selector_all(".additional-features .feature") if el.inner_text().strip()]

        gb = core._parse_gb(gb_text)
        # Parse minutes from planDetails JSON
        minutes = None
        for d in extras:
            if re.search(r"\d", d) and ("דקות שיחה" in d or "דקות" in d) and "חו" not in d and "לחו" not in d:
                minutes = core._parse_minutes(d)
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
            price = core._parse_price(price_el.inner_text().replace("₪", "").strip())
        days = core._parse_days(duration_el.inner_text() if duration_el else "")
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
                gb = core._parse_gb(b_text)
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
