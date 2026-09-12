"""world8 scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


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
        price = core._parse_price(re.sub(r'[^\d.]', '', price_li.inner_text()))
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
        days = core._parse_days(validity_text) if "ימים" in validity_text or "יום" in validity_text else None
        extras = [b.inner_text().strip() for b in badges if b.inner_text().strip()]
        if validity_text and validity_text not in extras:
            extras.append(validity_text)
        extras.append("120+ מדינות")
        if price and (gb or minutes):
            plans.append(core._make_global_plan(
                "world8", name, price, "ILS", price,
                gb, days, minutes=minutes, sms=sms, esim=True, extras=extras
            ))
    logger.info(f"World8 global: {len(plans)} plans")
    return plans
