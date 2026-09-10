"""golan scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


def _golan_num(s):
    """First number in a string as float, or None."""
    m = re.search(r'(\d+(?:\.\d+)?)', s or '')
    return float(m.group(1)) if m else None


def _golan_gb_from_text(s):
    """'300GB' -> 300.0 ; '0.5GB' -> 0.5 ; no GB -> None."""
    m = re.search(r'(\d+(?:\.\d+)?)\s*GB', s or '', re.I)
    return float(m.group(1)) if m else None


def _golan_gb_label(v):
    if v is None:
        return None
    return f"{int(v)}GB" if v == int(v) else f"{v}GB"


def _golan_period_to_days(text):
    """Parse the roaming price line: '299 ש"ח ל-30 יום' -> 30 ; 'ליום' -> 1 ; 'לשנה' -> 365."""
    if not text:
        return None
    if 'לשנה' in text:                 # לשנה
        return 365
    m = re.search(r'ל[\-\s]?(\d+)\s*יום', text)  # ל-NN יום
    if m:
        return int(m.group(1))
    if 'ליום' in text:                 # ליום
        return 1
    return None


# JS extractor for golantelecom.co.il/offers (domestic Mass-Market plans).
# Each .offer card carries data-gtm-price (exact price) and two benefit panels:
# .properties.israel (the "בישראל" tab) and .properties.roaming (the "בחול" tab).
# .important_info is the "פרטי המבצע" expandable bullet list.
_GOLAN_DOMESTIC_JS = r"""() => {
    const txt = el => (el ? (el.textContent||'').replace(/\s+/g,' ').trim() : '');
    // Only VISIBLE cards: the page keeps hidden/legacy .offer cards in the DOM (0x0,
    // offsetParent null, no `show-first` ancestor) — e.g. "זוגית" / a discontinued 550GB.
    const visible = c => c.offsetParent !== null && c.getBoundingClientRect().height > 0;
    return Array.from(document.querySelectorAll('.offer')).filter(visible).map(card => {
        const israel = card.querySelector('.properties.israel');
        const roaming = card.querySelector('.properties.roaming');
        const itemBy = (panel, label) => {
            if (!panel) return '';
            for (const it of panel.querySelectorAll('.item')) {
                if (txt(it.querySelector('.right')) === label)
                    return it.querySelector('.left img') ? '[check]' : txt(it.querySelector('.left'));
            }
            return '';
        };
        // בחול tab benefits — keep real items, drop the "תוקף מבצע" validity meta only
        const roamingItems = roaming ? Array.from(roaming.querySelectorAll('.item'))
            .filter(it => !it.classList.contains('sale_validity'))
            .map(it => ({
                right: txt(it.querySelector('.right')),
                left:  it.querySelector('.left img') ? '[check]' : txt(it.querySelector('.left')),
                all:   txt(it),
            }))
            .filter(it => it.all && !/^תוקף מבצע/.test(it.all)) : [];
        // פרטי המבצע — the .important_info bullet list
        const info = card.querySelector('.important_info');
        const importantInfo = info ? Array.from(info.querySelectorAll('li')).map(li => txt(li)).filter(Boolean) : [];
        const titleEl = card.querySelector('.upper h2.title .offer-content') || card.querySelector('.upper h2.title');
        const promoEl = Array.from(card.querySelectorAll('div,span,p')).find(e => {
            const t = e.textContent||''; return /חודש(?:ים|יים)\s*ראשונים/.test(t) && t.length < 120;
        });
        const pdf = card.querySelector('a[href*=".pdf"]');
        return {
            cls: card.className,
            gtmId: card.getAttribute('data-gtm-id'),
            gtmPrice: card.getAttribute('data-gtm-price'),
            gtmTitle: (card.getAttribute('data-gtm-title')||'').replace(/\s+/g,' ').trim(),
            titleText: txt(titleEl),
            promoText: txt(promoEl),
            gbText: itemBy(israel, 'גלישה'),
            callsText: itemBy(israel, 'שיחות'),
            intlMinutes: itemBy(israel, 'שיחות בינלאומיות'),
            subtitle: txt(card.querySelector('.upper .subtitle')),
            roamingItems, importantInfo,
            pdfHref: pdf ? pdf.href : '',
        };
    });
}"""


# JS extractor for golantelecom.co.il/overseas_offers (genuine roaming bundles).
# Each .offer card: .upper .title = "299 ש"ח ל-30 יום" (price + validity); .bottom .title =
# "50GB גלישה + 200 דקות"; two coloured .auto-fit-text lines = superlative (red) + bonus (grey);
# .pcrf-roaming-1 img = free apps; button.country_list[title] = full country list (HTML).
_GOLAN_OVERSEAS_JS = r"""() => {
    const txt = el => (el ? (el.textContent||'').replace(/\s+/g,' ').trim() : '');
    const decode = html => { const d = document.createElement('div'); d.innerHTML = html||''; return d; };
    const RED = ['rgb(237, 27, 47)', '#ed1b2f', 'rgb(237,27,47)'];
    const GRAY = ['rgb(104, 104, 117)', '#686875', 'rgb(104,104,117)'];
    // NB: unlike /offers we keep ALL .offer cards. The page features only 3 (30-day) plans;
    // the rest sit in d-none containers but are the real catalog behind "לכל חבילות חו\"ל"
    // (7/14-day, daily, yearly, מצרים וירדן). Dropping them would lose 9 genuine bundles.
    return Array.from(document.querySelectorAll('.offer')).map(card => {
        const autofit = Array.from(card.querySelectorAll('.bottom .auto-fit-text')).map(el => ({
            text: txt(el),
            color: (el.getAttribute('style')||'').match(/color:\s*([^;]+)/)?.[1]?.trim() || '',
        }));
        const superl = autofit.find(a => RED.includes(a.color))?.text || '';
        const bonus  = autofit.find(a => GRAY.includes(a.color))?.text || '';
        const apps = Array.from(card.querySelectorAll('.pcrf-roaming-1 img, [class*="pcrf"] img'))
            .map(i => (i.getAttribute('alt')||'').replace(/\s*Icon\s*$/i,'').trim()).filter(Boolean);
        let countries = [];
        const btn = card.querySelector('button.country_list, .country_list');
        if (btn) decode(btn.getAttribute('title')).querySelectorAll('.row-value').forEach(rv =>
            (rv.textContent||'').split(',').forEach(c => { const s=c.trim(); if(s) countries.push(s); }));
        // פרטי החבילה — services list (.important_info li, else its paragraph lines)
        const info = card.querySelector('.important_info');
        let services = [];
        if (info) {
            services = Array.from(info.querySelectorAll('li')).map(li => txt(li)).filter(Boolean);
            if (!services.length)
                services = (info.innerText||'').split('\n').map(s=>s.trim())
                    .filter(s => s && !/פרטי החבילה|השירותים הכלולים|לרכישה/.test(s));
        }
        return {
            cls: card.className,
            gtmId: card.getAttribute('data-gtm-id'),
            gtmPrice: card.getAttribute('data-gtm-price'),
            gtmTitle: (card.getAttribute('data-gtm-title')||'').replace(/\s+/g,' ').trim(),
            upperTitle: txt(card.querySelector('.upper .title')),
            mainTitle: txt(card.querySelector('.bottom > .title')),
            subtitle: txt(card.querySelector('.bottom > .subtitle')),
            superlative: superl, bonus, apps, countries, services,
        };
    });
}"""


def _build_golan_domestic(cards):
    """Turn raw .offer card dicts (from _GOLAN_DOMESTIC_JS) into domestic plan dicts.
    Merges the בישראל + בחול tabs and the פרטי המבצע bullets into extras; plans whose
    בחול tab includes browsing get a "NNGB גלישה בחול" extra so the UI shows the חול badge.
    """
    plans, seen = [], set()
    for c in cards:
        price = _golan_num(c.get('gtmPrice'))
        if price is None:
            continue
        title = c.get('titleText') or ''
        gtm = c.get('gtmTitle') or ''
        subtitle = c.get('subtitle') or ''

        # Headline label — DATA ONLY / זוגית / משפחתית / NNNGB (regex skips injected Adoric junk)
        m = re.search(r'(DATA ONLY|זוגית|משפחתית|\d+GB)', f"{title} {gtm}", re.I)
        label = m.group(1) if m else (gtm.split()[0] if gtm else 'חבילה')

        data_gb = _golan_gb_from_text(c.get('gbText'))
        if data_gb is None:
            data_gb = _golan_gb_from_text(subtitle)        # DATA ONLY -> "500GB דור 5"

        name = f"גולן {label}"
        if 'החו"ל כלול' in subtitle or 'החו״ל כלול' in subtitle:
            name += ' – חו"ל כלול'
        if name in seen:
            name += f" ({c.get('gtmId')})"
        seen.add(name)

        # minutes: check-mark = unlimited (None); explicit number (DATA ONLY "50 דקות") = limited
        minutes = None
        calls = c.get('callsText') or ''
        if calls and '[check]' not in calls and _golan_num(calls):
            minutes = int(_golan_num(calls))

        extras = []
        # 1) בחול tab benefits FIRST -> drives the חול badge + shows up top
        for it in c.get('roamingItems', []):
            right, left, allt = it.get('right', ''), it.get('left', ''), it.get('all', '')
            if left and left != '[check]' and right:
                line = f"{left} {right}"                    # "12GB גלישה בחול"
            elif left == '[check]' and right:
                line = right                                # "שיחות מחול לישראל"
            else:
                line = allt
            line = re.sub(r'\s+', ' ', line).strip()
            if line and line not in extras:
                extras.append(line)
        # 2) intl calling minutes (שיחות בינלאומיות)
        if c.get('intlMinutes') and _golan_num(c['intlMinutes']):
            extras.append(f"{int(_golan_num(c['intlMinutes']))} דקות לחו\"ל")
        # 3) פרטי המבצע bullets — drop redundant "גלישה בנפח NNNGB" / CTA noise / dup roaming
        have_intl_gb = any('גלישה בחו' in e for e in extras)
        for s in c.get('importantInfo', []):
            s = re.sub(r'\s+', ' ', s).strip().rstrip('*').strip()
            if not s or len(s) <= 2 or s == 'SMS':
                continue
            if re.match(r'^גלישה בנפח', s):
                continue
            if re.search(r'לתקנון|לחצו כאן|>>', s):
                continue
            if have_intl_gb and 'גלישה בחו' in s:
                continue
            if s not in extras:
                extras.append(s)
        # 4) descriptor (דור 5 / שירות תיקונים / 2 קווים) when it adds something new
        if subtitle and not re.search(r'דק[א-ת\']*\s*לחו|גלישה בחו|הנחה|החו"ל כלול', subtitle):
            if subtitle not in extras:
                extras.append(subtitle)
        full = list(dict.fromkeys(extras))
        extras = full[:7]

        # promo ("3 חודשים ראשונים ב-39 ש״ח" / "חודשיים ראשונים ב-49 ש״ח")
        promo_price = promo_months = None
        for raw in [c.get('promoText'), subtitle] + c.get('importantInfo', []):
            mm = re.search(r'(\d+)\s*חודשים\s*ראשונים\s*ב[\-\s]?(\d+(?:\.\d+)?)', raw or '')
            if mm:
                promo_months, promo_price = int(mm.group(1)), float(mm.group(2)); break
            mm = re.search(r'חודשיים\s*ראשונים\s*ב[\-\s]?(\d+(?:\.\d+)?)', raw or '')
            if mm:
                promo_months, promo_price = 2, float(mm.group(1)); break

        # planInfo popup ("תנאי התוכנית") — full benefit detail + a clickable link to the
        # official terms PDF. Stored as a filtered "__info__|" extra (hidden from bullets).
        pdf = c.get('pdfHref')
        info_lines = list(full)
        if pdf:
            info_lines.append(f'התקנון המלא (PDF)|{pdf}')
        if info_lines:
            extras = extras + ['__info__|' + '\n'.join(info_lines)]

        plans.append({
            'carrier': 'golan', 'plan_name': name, 'price': price,
            'data_gb': data_gb, 'minutes': minutes, 'extras': extras,
            'url': pdf or _GOLAN_OFFERS_URL,
            'promo_price': promo_price, 'promo_months': promo_months,
        })
    return plans


_GOLAN_GENERIC_SUPERL = re.compile(r'מושלמת|הכי|בגדול|בסטייל|לקצב')  # מושלמת/הכי/בגדול/בסטייל/לקצב


def _build_golan_abroad(cards):
    """Turn raw .offer card dicts (from _GOLAN_OVERSEAS_JS) into abroad plan dicts.
    extras[0] is the destination marker ('כלל העולם' for the ~126-country bundles, the
    region name for a country-specific bundle e.g. 'מצרים וירדן'); the per-package country
    list is rendered by getCountriesForAbroadPlan() in the React app.
    """
    plans, seen = [], set()
    for c in cards:
        price = _golan_num(c.get('gtmPrice'))
        if price is None:
            continue
        main = c.get('mainTitle') or c.get('gtmTitle') or ''
        data_gb = _golan_gb_from_text(main)
        mm = re.search(r'\+\s*(\d+)\s*דקות', main)
        minutes = int(mm.group(1)) if mm else None
        days = _golan_period_to_days(c.get('upperTitle') or '')
        countries = c.get('countries') or []
        superl = (c.get('superlative') or '').strip()
        is_world = len(countries) >= 40

        period = ('שנתי' if days == 365 else 'יומי' if days == 1
                  else f"{days} יום" if days else '')
        gbl = _golan_gb_label(data_gb) or ''
        # BiDi-safe name: GB / minutes / period each become a separate " – " segment, which
        # PlanCard wraps in its own <bdi>. Joining them in one string (e.g. "80GB + 300 דק'")
        # lets the Latin "GB" reorder the numbers visually ("300 + 80GB דק'").
        segs = [s for s in [gbl, (f"{minutes} דק'" if minutes else ''), period] if s]
        name = 'גולן חו"ל ' + (' – '.join(segs) if segs else (main or 'חבילה'))
        # destination marker (extras[0]) + name disambiguation for country-specific bundles
        dest = ('כלל העולם' if is_world else
                (superl if superl and not _GOLAN_GENERIC_SUPERL.search(superl) else ' ו'.join(countries)))
        if not is_world and dest and dest not in name:
            name += f" ({dest})"
        if name in seen:
            name += f" ({c.get('gtmId')})"
        seen.add(name)

        extras = [dest]
        if superl and superl != dest:
            extras.append(superl)                          # superlative (e.g. "הכי נמכרת")
        if c.get('bonus'):
            extras.append(c['bonus'])                      # "חבילה שנייה 20GB ..."
        has_apps = bool(c.get('apps'))
        if has_apps:
            extras.append('גלישה חופשית באפליקציות: ' + ' · '.join(c['apps']))
        for s in c.get('services', []):
            s = re.sub(r'\s+', ' ', s).strip().lstrip('•').strip().rstrip('*').strip()
            if not s or len(s) <= 2 or s.startswith('*'):
                continue
            if re.match(r'^\d+(?:\.\d+)?\s*GB גלישה', s):     # duplicates data_gb
                continue
            if re.search(r'תוקף החבילה', s):                    # duplicates days
                continue
            if re.search(r'לתקנון|לחצו כאן|>>', s):              # CTA noise
                continue
            if has_apps and 'גלישה חופשית באפליקציות' in s:
                continue
            if s not in extras:
                extras.append(s)
        full = list(dict.fromkeys([e for e in extras if e]))
        extras = full[:8]

        # planInfo popup ("תנאי התוכנית") — abroad_plans store no url column, so the terms
        # affordance is driven entirely by this "__info__|" extra (full detail + tariff link).
        info_lines = [e for e in full if e != dest]
        info_lines.append('תעריפון חו"ל (PDF)|https://golant.co/roaming_tariffs')
        extras = extras + ['__info__|' + '\n'.join(info_lines)]

        plans.append({
            'carrier': 'golan', 'plan_name': name, 'price': price,
            'days': days, 'data_gb': data_gb, 'minutes': minutes, 'sms': None,
            'extras': extras,
            'url': f"{_GOLAN_OVERSEAS_URL.rsplit('/',1)[0]}/userGuide/step3?packageidChange={c.get('gtmId')}&process=roamingflights",
        })
    return plans


def _golan_open(page, url):
    """Navigate to a Golan offers page, dismiss popups, and expand every
    'פרטי המבצע' / 'פרטי החבילה' toggle so .important_info is in the DOM."""
    page.goto(url, timeout=40000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    core._dismiss_popups(page)
    try:
        page.evaluate(r"""() => document.querySelectorAll('.info-text,[class*="info-text"],button,a,span')
            .forEach(e => { const t=(e.textContent||'').trim();
                if (t==='פרטי המבצע' || t==='פרטי החבילה') { try{e.click()}catch(x){} } })""")
        page.wait_for_timeout(900)
    except Exception:
        pass


_GOLAN_OFFERS_URL = "https://www.golantelecom.co.il/offers"


_GOLAN_OVERSEAS_URL = "https://www.golantelecom.co.il/overseas_offers"


_GOLAN_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def scrape_golan(_page=None):
    """Scrape Golan Telecom domestic plans from golantelecom.co.il/offers.
    DOM-based: each .offer card carries data-gtm-price plus structured בישראל / בחול
    benefit panels and a פרטי המבצע bullet list — see _GOLAN_DOMESTIC_JS / _build_golan_domestic.
    """
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_GOLAN_UA)
        try:
            _golan_open(page, _GOLAN_OFFERS_URL)
            plans = _build_golan_domestic(page.evaluate(_GOLAN_DOMESTIC_JS))
            if not plans:
                logger.warning("scrape_golan: 0 plans extracted from golantelecom.co.il/offers")
            return plans
        finally:
            browser.close()


def scrape_golan_abroad(_page=None):
    """Scrape Golan Telecom roaming bundles from golantelecom.co.il/overseas_offers.
    These are genuine overseas packages (e.g. 6GB+100דק' for 14 days, ~126 countries),
    NOT the domestic line-up — stored as abroad_plans so they populate the חול tab with
    real prices, validity, included countries and superlatives. See _build_golan_abroad.
    """
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_GOLAN_UA)
        try:
            _golan_open(page, _GOLAN_OVERSEAS_URL)
            plans = _build_golan_abroad(page.evaluate(_GOLAN_OVERSEAS_JS))
            if not plans:
                logger.warning("scrape_golan_abroad: 0 plans from golantelecom.co.il/overseas_offers")
            return plans
        finally:
            browser.close()
