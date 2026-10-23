"""golan scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.

2026-10 rewrite: Golan moved to a headless Episerver site (the old /offers and
/overseas_offers pages now 302 to an SPA, so the .offer-card DOM scrape returned 0
plans from 2026-10-16). Both scrapers now read the site's own JSON:
  * domestic - the CMS content API for /production/Cellular/Packages/ (pure HTTP);
  * abroad   - digital-api GetPackagePopular, which only answers inside a browser
               session (clientid/deviceid/sessionid headers), so the lobby page is
               loaded in Playwright and that response is captured.
Plan names are built exactly as the DOM-era builders did, so price history and
the frontend name maps (GOLAN_APPS_BY_PLAN, GOLAN_SPECIFIC) keep matching.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import html
import re
logger = core.logger


def _golan_num(s):
    """First number in a string as float, or None."""
    m = re.search(r'(\d+(?:\.\d+)?)', str(s or ''))
    return float(m.group(1)) if m else None


def _golan_gb_from_text(s):
    """'300GB' -> 300.0 ; '0.5GB' -> 0.5 ; no GB -> None."""
    m = re.search(r'(\d+(?:\.\d+)?)\s*GB', s or '', re.I)
    return float(m.group(1)) if m else None


def _golan_gb_label(v):
    if v is None:
        return None
    return f"{int(v)}GB" if v == int(v) else f"{v}GB"


def _golan_strip(rich):
    """CMS rich-text -> single-line plain text."""
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(rich or '')))
    return re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip()


def _golan_val(v):
    """Episerver wraps every property as {"value": ...} or {"expandedValue": ...}."""
    if isinstance(v, dict):
        if 'value' in v:
            return v['value']
        if 'expandedValue' in v:
            return v['expandedValue']
    return v


def _golan_find(obj, pred, out=None):
    """All dicts in a JSON tree matching pred (not descending into matches)."""
    out = [] if out is None else out
    if isinstance(obj, dict):
        if pred(obj):
            out.append(obj)
            return out
        for v in obj.values():
            _golan_find(v, pred, out)
    elif isinstance(obj, list):
        for v in obj:
            _golan_find(v, pred, out)
    return out


_GOLAN_SITE = "https://golantelecom.co.il"
# globalassets PDFs live on the CMS host; the same path on the SPA host returns the HTML shell
_GOLAN_ASSETS = "https://contentepi.golantelecom.co.il"
_GOLAN_PACKAGES_PATH = "/production/Cellular/Packages/"
_GOLAN_OFFERS_URL = _GOLAN_SITE + _GOLAN_PACKAGES_PATH
_GOLAN_PACKAGES_API = (f"{_GOLAN_ASSETS}{_GOLAN_PACKAGES_PATH}?expand=*"
                       "&currentPageUrl=%2Fproduction%2FCellular%2FPackages%2F")
_GOLAN_OVERSEAS_URL = _GOLAN_SITE + "/AbroadMain/lobby/"
_GOLAN_ROAMING_TARIFFS = "https://golant.co/roaming_tariffs"

_GOLAN_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def _golan_asset(path):
    path = (path or '').strip()
    if not path:
        return None
    return path if path.startswith('http') else _GOLAN_ASSETS + path


def _build_golan_domestic(pkgs):
    """CMS SalePackageContentData blocks -> domestic plan dicts.
    Card fields: title (NNNGB [DATA ONLY]), banner (headline perk), header*FeatureText
    (data / minutes+SMS / intl minutes / roaming), price + textUnderPrice (promo).
    """
    plans, seen = [], set()
    for p in pkgs:
        g = lambda k: _golan_strip(_golan_val(p.get(k)))
        price = _golan_num(g('price'))
        if price is None:
            continue
        title, banner, benefit = g('title'), g('banner'), g('benefitTitle')
        features = [g(k) for k in ('headerRightFeatureText', 'headerLeftFeatureText',
                                   'headerThirdFeatureText', 'headerFourthFeatureText')]
        features = [f for f in features if f]

        # Headline label - DATA ONLY before the GB figure ("500GB DATA ONLY" -> "גולן DATA ONLY")
        m = re.search(r'DATA ONLY', title, re.I) or re.search(r'\d+GB', title, re.I)
        label = m.group(0) if m else (p.get('name') or 'חבילה')
        name = f"גולן {label}"
        if 'החו"ל כלול' in banner or 'חו"ל כלול' in (p.get('name') or ''):
            name += ' – חו"ל כלול'
        if name in seen:
            name += f" ({g('pricePlanCode')})"
        seen.add(name)

        data_gb = None
        for f in features:
            if 'גלישה בנפח' in f:
                data_gb = _golan_gb_from_text(f)
                break
        if data_gb is None:
            data_gb = _golan_gb_from_text(title)

        # minutes: thousands = effectively unlimited (stored None, as before); a small
        # explicit allowance (DATA ONLY "50 דקות") is the plan's real voice cap.
        minutes = None
        for f in features:
            mm = re.match(r'^(\d+)\s*דקות(?!\s*(?:שיחה\s*)?לחו)', f)
            if mm and int(mm.group(1)) < 1000:
                minutes = str(int(mm.group(1)))

        extras = []
        # 1) roaming benefits FIRST -> drives the חו"ל badge
        for f in [banner] + features:
            mm = re.search(r'(\d+(?:\.\d+)?GB)\s*בחו"ל', f)
            if mm and 'גלישה בחו' not in f:
                f = f'{mm.group(1)} גלישה בחו"ל'
            if 'גלישה בחו' in f or 'בחו"ל ל/מישראל' in f:
                extras.append(f)
        # 2) intl minutes + domestic minutes/SMS + the headline perk
        for f in [banner] + features:
            if re.search(r'דק[\'א-ת]*\s*(?:שיחה\s*)?לחו"ל', f):
                n = _golan_num(f)
                extras.append(f'{int(n)} דקות לחו"ל' if n else f)
            elif ' / ' in f and not f.startswith('גלישה בנפח'):
                extras.extend(s.strip() for s in f.split(' / ') if s.strip())
            elif f and f not in (banner,) and not f.startswith('גלישה בנפח'):
                extras.append(f)
        if banner and 'GB' not in banner and 'חו"ל' not in banner and not re.search(r'דק', banner):
            extras.append(banner)
        if benefit and re.search(r'דור 5', benefit):
            extras.append('גלישה ברשת דור 5')
        under = g('textUnderPrice')
        if under:
            extras.append(under if 'ראשונים ב' in under else f'המחיר {under}')
        extras = [e for e in dict.fromkeys(re.sub(r'\s+', ' ', e).strip() for e in extras) if e]
        full = list(extras)
        extras = full[:7]

        promo_price = promo_months = None
        mm = re.search(r'(\d+)\s*חודשים\s*ראשונים\s*ב[\-\s]?(\d+(?:\.\d+)?)', under)
        if mm:
            promo_months, promo_price = int(mm.group(1)), float(mm.group(2))
        else:
            mm = re.search(r'חודשיים\s*ראשונים\s*ב[\-\s]?(\d+(?:\.\d+)?)', under)
            if mm:
                promo_months, promo_price = 2, float(mm.group(1))

        # "תנאי התוכנית" popup + the official plan PDF ("לעיקרי התוכנית")
        pdf = _golan_asset(g('programDetailsLink') or g('termsLink'))
        info_lines = list(full)
        if pdf:
            info_lines.append(f'התקנון המלא (PDF)|{pdf}')
        extras = extras + ['__info__|' + '\n'.join(info_lines)]

        plans.append({
            'carrier': 'golan', 'plan_name': name, 'price': price,
            'data_gb': data_gb, 'minutes': minutes, 'extras': extras,
            'url': pdf or _GOLAN_OFFERS_URL,
            'promo_price': promo_price, 'promo_months': promo_months,
        })
    return plans


_GOLAN_GENERIC_SUPERL = re.compile(r'מושלמת|הכי|בגדול|בסטייל|לקצב')  # מושלמת/הכי/בגדול/בסטייל/לקצב


def _golan_days(pkg):
    n, unit = pkg.get('packageDuration'), (pkg.get('packageDurationUnit') or '').lower()
    if not n:
        return None
    if unit.startswith('month'):
        return 365 if int(n) == 12 else int(n) * 30
    if unit.startswith('year'):
        return 365 * int(n)
    return int(n)


def _build_golan_abroad(pkgs):
    """digital-api GetPackagePopular packages -> abroad plan dicts.
    extras[0] is the destination marker ('כלל העולם' for the ~126-country bundles, the
    package name for a regional one, e.g. 'מצרים וירדן' / 'TAVERNA TRIP'); the per-package
    country list is rendered by getCountriesForAbroadPlan() in the React app.
    """
    plans, seen = [], set()
    for p in pkgs:
        price = _golan_num(p.get('price'))
        if not price:
            continue
        det = (p.get('packageDetailsList') or [{}])[0] or {}
        q = lambda k: (det.get(k) or {}).get('value')
        data_unit = ((det.get('data') or {}).get('unit') or 'GB').upper()
        data_gb = q('data')
        if data_gb is not None and data_unit == 'MB':
            data_gb = data_gb / 1024
        minutes = int(q('voice')) if q('voice') else None
        sms = int(q('sms')) if q('sms') else None
        days = _golan_days(p)
        title = (p.get('titleEpi') or '').strip()
        countries = [c.get('countryHebName') for c in (p.get('countrySupportedList') or []) if c.get('countryHebName')]
        is_world = len(countries) >= 40

        period = ('שנתי' if days == 365 else 'יומי' if days == 1
                  else f"{days} יום" if days else '')
        gbl = _golan_gb_label(data_gb) or ''
        # BiDi-safe name: GB / minutes / period are separate " – " segments (PlanCard wraps
        # each in its own <bdi>); joined in one string the Latin "GB" reorders the numbers.
        segs = [s for s in [gbl, (f"{minutes} דק'" if minutes else ''), period] if s]
        name = 'גולן חו"ל ' + (' – '.join(segs) if segs else (title or 'חבילה'))
        dest = ('כלל העולם' if is_world else
                (title if title and not _GOLAN_GENERIC_SUPERL.search(title) else ' ו'.join(countries)))
        if not is_world and dest and dest not in name:
            name += f" ({dest})"
        tag2 = (p.get('tagTextSecondary') or '').strip()
        if name in seen:
            # two bundles with identical GB/minutes/period: FAMILY PLUS vs PERFECT MATCH
            # differ by name, the two "100 דקות" packs only by the local-calls tag
            first = next((q for q in pkgs if q is not p and (q.get('titleEpi') or '').strip() == title), None)
            name += f" ({(tag2 if first is not None else '') or title or p.get('socCode')})"
        seen.add(name)

        extras = [dest]
        if title and title != dest:
            extras.append(title)
        bonus = (p.get('textUnderPackage') or '').strip()
        if bonus:
            extras.append(bonus)
        if tag2:
            extras.append(tag2)
        app = p.get('dataForApp') or {}
        if app.get('hasDataForApp'):
            extras.append('גלישה חופשית באפליקציות')
        for para in re.split(r'</p>|\n', ' '.join(p.get('importantInfo') or [])):
            s = _golan_strip(para).lstrip('•').strip().rstrip('*').strip()
            if not s or len(s) <= 2 or s.startswith('*'):
                continue
            if re.match(r'^ש?ירותים הכלולים|^השירותים הכלולים', s):    # duplicates GB/minutes
                continue
            if re.search(r'לתקנון|לחצו כאן|>>|לתנאים המלאים', s):        # CTA / cross-promo noise
                continue
            if 'ביטול חינם' in s:
                s = 'ביטול חינם עד יום הטיסה'
            elif len(s) > 140:
                continue
            if s not in extras:
                extras.append(s)
        full = list(dict.fromkeys(e for e in extras if e))
        extras = full[:8]

        terms = _golan_asset(p.get('policiesEpi'))
        info_lines = [e for e in full if e != dest]
        if terms:
            info_lines.append(f'תנאי החבילה (PDF)|{terms}')
        info_lines.append(f'תעריפון חו"ל (PDF)|{_GOLAN_ROAMING_TARIFFS}')
        extras = extras + ['__info__|' + '\n'.join(info_lines)]

        plans.append({
            'carrier': 'golan', 'plan_name': name, 'price': price,
            'days': days, 'data_gb': data_gb, 'minutes': minutes, 'sms': sms,
            'extras': extras, 'terms_url': terms,
        })
    return plans


def scrape_golan(_page=None):
    """Scrape Golan Telecom domestic plans from the CMS JSON behind
    golantelecom.co.il/production/Cellular/Packages/ ("כל חבילות הסלולר שלנו")."""
    import requests
    try:
        r = requests.get(_GOLAN_PACKAGES_API, timeout=30,
                         headers={"User-Agent": _GOLAN_UA, "Accept": "application/json"})
        r.raise_for_status()
        pkgs = _golan_find(r.json(), lambda o: 'SalePackageContentData' in (o.get('contentType') or []))
    except Exception as exc:
        logger.warning(f"scrape_golan: CMS fetch failed: {exc}")
        return []
    plans = _build_golan_domestic(pkgs)
    if not plans:
        logger.warning(f"scrape_golan: 0 plans from {_GOLAN_PACKAGES_API} ({len(pkgs)} package blocks)")
    return plans


def scrape_golan_abroad(_page=None):
    """Scrape Golan Telecom roaming bundles: load the abroad lobby and capture the
    GetPackagePopular response it fetches (the API rejects requests outside a
    browser session). Genuine overseas packages, stored as abroad_plans."""
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=_GOLAN_UA)
        try:
            with page.expect_response(lambda r: 'GetPackagePopular' in r.url and r.request.method == 'POST',
                                      timeout=60000) as resp:
                page.goto(_GOLAN_OVERSEAS_URL, timeout=60000, wait_until="domcontentloaded")
            pkgs = (resp.value.json() or {}).get('Body') or []
        except Exception as exc:
            logger.warning(f"scrape_golan_abroad: package API capture failed: {exc}")
            return []
        finally:
            browser.close()
    plans = _build_golan_abroad(pkgs)
    if not plans:
        logger.warning(f"scrape_golan_abroad: 0 plans from GetPackagePopular ({len(pkgs)} packages)")
    return plans
