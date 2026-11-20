"""world8 scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


_W8_TAG = re.compile(r"<[^>]+>")


def _w8_text(fragment):
    import html as _html
    return re.sub(r"\s+", " ", _html.unescape(_W8_TAG.sub(" ", fragment or ""))).strip()


def _w8_all(pattern, card):
    return [_w8_text(m) for m in re.findall(pattern, card, re.S)]


def _parse_world8_html(html_text):
    """world8.co.il home page -> plan dicts.

    The site was rebuilt in 2026-11 (Astro): the old `.price-card` markup is gone
    and the offer is 3 `<article class="wf-card" data-price="...">` cards, all in
    the server-rendered HTML. Per card: `.wf-title` (name), `.wf-big` (data),
    `.wf-note` (validity lines), `.wf-extra li` (minutes / SMS / extra data),
    `.wf-pill` (number of destinations), `.wf-ribbon` (badge).
    """
    plans = []
    cards = re.findall(
        r'<article\b[^>]*class="wf-card[^"]*"[^>]*data-price="([\d.]+)"[^>]*>(.*?)</article>',
        html_text, re.S)
    for price_raw, card in cards:
        names = _w8_all(r'class="wf-title"[^>]*>(.*?)</h2>', card)
        price = core._parse_price(price_raw)
        if not names or not names[0] or not price:
            continue
        big = " ".join(_w8_all(r'class="wf-big[^"]*"[^>]*>(.*?)</p>', card))
        notes = _w8_all(r'class="wf-note[^"]*"[^>]*>(.*?)</p>', card)
        extra_items = _w8_all(r"<li[^>]*>(.*?)</li>",
                              " ".join(re.findall(r'class="wf-extra[^"]*"[^>]*>(.*?)</div>', card, re.S)))
        pill = " ".join(_w8_all(r'class="wf-pill"[^>]*>(.*?)</a>', card))
        ribbon = " ".join(_w8_all(r'class="wf-ribbon"[^>]*>(.*?)</span>', card))

        gb_m = re.search(r"(\d+(?:\.\d+)?)\s*GB", big, re.I)
        gb = float(gb_m.group(1)) if gb_m else None
        extra_text = " ".join(extra_items)
        min_m = re.search(r"(\d+)\s*\u05d3\u05e7\u05d5\u05ea", extra_text)
        sms_m = re.search(r"(\d+)\s*(?:\u05e1\u05de\u05e1|SMS)", extra_text, re.I)
        minutes = int(min_m.group(1)) if min_m else None
        sms = int(sms_m.group(1)) if sms_m else None
        days = next((d for d in (core._parse_days(n) for n in notes) if d), None)

        extras = [t for t in [ribbon] + notes if t]
        if extra_items:
            # "60 minutes + 60 SMS + 1GB" is on top of the data; "or 120 minutes or
            # 120 SMS" is an alternative to it - keep the site's wording so the card
            # does not read as data AND minutes
            extras.append(" + ".join(extra_items))
        if pill:
            extras.append(pill)
        if not (gb or minutes):
            continue
        plans.append(core._make_global_plan(
            "world8", names[0], price, "ILS", price,
            gb, days, minutes=minutes, sms=sms, esim=True, extras=extras
        ))
    return plans


def scrape_world8_global(page):
    page.goto("https://world8.co.il/", timeout=35000, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("article.wf-card", timeout=15000)
    except Exception:
        pass
    plans = _parse_world8_html(page.content())
    if not plans:
        logger.warning("World8 global: 0 plans - the page markup probably changed again")
    logger.info(f"World8 global: {len(plans)} plans")
    return plans
