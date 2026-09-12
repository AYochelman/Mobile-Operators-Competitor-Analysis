"""partner scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
import json as _json
logger = core.logger


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
                price = core._parse_price(price_text)
            except Exception:
                price = core._parse_price(price_el.inner_text())
        gb    = core._parse_gb(gb_el.inner_text())       if gb_el    else None
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
        gb    = core._parse_gb(size_el.inner_text()) if size_el  else None
        price = core._parse_price(price_el.inner_text()) if price_el else None
        days, minutes, sms = None, None, None
        for item in desc_items:
            if "ימים" in item and days is None:
                days = core._parse_days(item)
            elif "דקות" in item and minutes is None:
                minutes = core._parse_minutes(item)
            elif "הודעות" in item and sms is None:
                sms = core._parse_sms(item)
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
