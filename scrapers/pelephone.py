"""pelephone scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


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
        price = core._parse_price(price_el.inner_text()) if price_el else None
        gb    = core._parse_gb(gb_el.inner_text())       if gb_el    else None
        if name and name != "לא ידוע":
            plans.append({"carrier": "pelephone", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": None, "extras": extras,
                          "url": pelephone_urls.get(name)})
    return plans


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
        price = core._parse_price(price_text)
        days  = core._parse_days(period_text)
        gb_el  = card.query_selector(".data .g_d_s .g")
        min_el = card.query_selector(".data .g_d_s .d")
        sms_el = card.query_selector(".data .g_d_s .s")
        gb      = core._parse_gb(gb_el.inner_text())       if gb_el  else None
        # Fallback: MB-tier plans store value elsewhere; search entire .data block
        if gb is None:
            data_el = card.query_selector(".data")
            if data_el:
                gb = core._parse_gb(data_el.inner_text())
        minutes = core._parse_minutes(min_el.inner_text()) if min_el else None
        sms     = core._parse_sms(sms_el.inner_text())     if sms_el else None
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
