"""mobile019 scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


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
    with Stealth().use_sync(core.sync_playwright()) as pw:
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

                price = core._parse_price(price_el.inner_text().replace("₪", "").strip()) if price_el else None
                gb    = core._parse_gb(gb_el.inner_text()) if gb_el else None

                extras = []
                for li_el in card.query_selector_all(".blist li"):
                    text = li_el.inner_text().strip()
                    if not text:
                        continue
                    if gb is None and re.search(r"\d+\s*(GB|MB|gb|mb)", text):
                        gb = core._parse_gb(text)
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
    with Stealth().use_sync(core.sync_playwright()) as pw:
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
                price = core._parse_price(price_el.inner_text().replace("₪", "").strip()) if price_el else None
                gb = core._parse_gb(gb_el.inner_text()) if gb_el else None
                days, minutes = None, None
                extras = []
                info_lines = []          # full card text for the "עיקרי התוכנית" modal
                for li_el in blist_els:
                    text = re.sub(r"\s+", " ", li_el.inner_text()).strip()
                    if not text:
                        continue
                    info_lines.append(text)
                    if "למשך" in text and "ימים" in text:
                        days = core._parse_days(text)
                    elif "דק" in text:
                        strong = li_el.query_selector("strong")
                        minutes = core._parse_minutes(strong.inner_text() if strong else text)
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
