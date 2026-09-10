"""pelephone_globalsim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


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
        price = core._parse_price(price_text)
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
            gb = core._parse_gb(gb_text)
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
                    days = core._parse_days(f"{num} {unit}")
        if not is_voice_plan and txt_el:
            t = txt_el.inner_text().strip()
            if t:
                m = re.search(r"(\d+)\s*\u05d3\u05e7\u05d5\u05ea", t)
                if m:
                    plan_minutes = int(m.group(1))
                plan_extras.append(t)
        esim = esim_el is not None
        name = f"GlobalSIM {gb_text}"
        plans.append(core._make_global_plan(
            "pelephone_global", name, price, "ILS", price,
            gb, days, minutes=plan_minutes, esim=esim, extras=plan_extras
        ))
    logger.info(f"Pelephone GlobalSIM: {len(plans)} plans")
    return plans
