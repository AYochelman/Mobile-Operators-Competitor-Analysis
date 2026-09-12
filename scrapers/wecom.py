"""wecom scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module


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
        days = core._parse_days('\n'.join(front_lines))
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
