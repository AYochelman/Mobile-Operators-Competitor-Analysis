"""rami_levy scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


def _parse_rami_levy_body(body_text):
    BLOCK_END = "למידע נוסף"
    SKIP_DETAIL = {'להצטרפות'}

    lines = [l.strip() for l in body_text.split('\n')]
    blocks, cur = [], []
    for l in lines:
        if l == BLOCK_END:
            blocks.append(cur)
            cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)

    plans = []
    for block in blocks:
        non_empty = [l for l in block if l]
        try:
            shekel_idx = next(i for i, l in enumerate(non_empty) if l == '₪')
        except StopIteration:
            continue
        if shekel_idx < 2:
            continue

        price_str = non_empty[shekel_idx - 1]
        plan_name = non_empty[shekel_idx - 2]

        try:
            price = float(price_str.replace(',', ''))
        except ValueError:
            continue

        # Skip header nav items (block 0 has nav text before the first plan)
        if plan_name in {'דלג לתוכן', 'רמי לוי באינטרנט', 'תוכניות', 'סניפים', 'הפעלת סים', 'האזור האישי'}:
            continue

        details_start = shekel_idx + 2  # skip ₪ and לחודש
        detail_lines = non_empty[details_start:]
        extras = [l for l in detail_lines if l not in SKIP_DETAIL]

        gb_val = None
        for l in non_empty:
            m = re.search(r'(\d+)GB', l)
            if m and 'גלישה' in l:
                gb_val = int(m.group(1))
                break

        minutes = None
        for l in non_empty:
            if 'דקות שיחה' in l and 'בתוך רשת' not in l and 'מחוץ לרשת' not in l:
                m = re.search(r'([\d,]+)', l)
                if m:
                    minutes = int(m.group(1).replace(',', ''))
                    break

        plans.append({
            'carrier': 'rami_levy',
            'plan_name': plan_name,
            'price': price,
            'data_gb': gb_val,
            'minutes': minutes,
            'extras': extras,
            'url': 'https://mobile.rami-levy.co.il/Home/Packages',
        })
    return plans


def _parse_rami_levy_abroad_body(body_text):
    BLOCK_END = "למידע נוסף"
    SKIP_DETAIL = {'רכישה'}
    WORLD = "\u05db\u05dc\u05dc \u05d4\u05e2\u05d5\u05dc\u05dd"  # כלל העולם

    lines = [l.strip() for l in body_text.split('\n')]
    blocks, cur = [], []
    for l in lines:
        if l == BLOCK_END:
            blocks.append(cur)
            cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)

    # First pass: extract parsed blocks, second pass: disambiguate names
    parsed = []
    for block in blocks:
        non_empty = [l for l in block if l]
        try:
            shekel_idx = next(i for i, l in enumerate(non_empty) if l == '₪')
        except StopIteration:
            continue
        if shekel_idx < 1:
            continue

        price_str = non_empty[shekel_idx - 1]
        try:
            price = float(price_str.replace(',', ''))
        except ValueError:
            continue

        # Line 2 before ₪ is either data highlight (e.g. "5GB") or plan name
        candidate = non_empty[shekel_idx - 2] if shekel_idx >= 2 else ''
        if re.fullmatch(r'\d+(?:\.\d+)?\s*(?:GB|MB)', candidate, re.I) and shekel_idx >= 3:
            plan_name = non_empty[shekel_idx - 3]
        else:
            plan_name = candidate

        if plan_name in {'דלג לתוכן', 'רמי לוי באינטרנט', 'תוכניות', 'סניפים',
                         'הפעלת סים', 'האזור האישי', 'Bon Voyage'}:
            continue

        details_start = shekel_idx + 1
        detail_lines = [l for l in non_empty[details_start:] if l not in SKIP_DETAIL]

        data_gb = None
        for l in detail_lines:
            m = re.search(r'(\d+(?:\.\d+)?)\s*GB', l, re.I)
            if m and 'גלישה' in l:
                data_gb = float(m.group(1))
                if data_gb == int(data_gb):
                    data_gb = int(data_gb)
                break
            m = re.search(r'(\d+)\s*MB', l, re.I)
            if m and 'גלישה' in l:
                data_gb = int(m.group(1)) / 1024
                break

        minutes = None
        for l in detail_lines:
            if 'דקות שיחה' in l:
                m = re.search(r'([\d,]+)', l)
                if m:
                    minutes = int(m.group(1).replace(',', ''))
                    break

        sms = None
        for l in detail_lines:
            if 'הודעות' in l or 'SMS' in l:
                m = re.search(r'([\d,]+)', l)
                if m:
                    sms = int(m.group(1).replace(',', ''))
                    break

        days = None
        for l in detail_lines:
            if 'תקף ליום אחד' in l or 'מתחדשת כל יום' in l:
                days = 1
                break
            m = re.search(r'תקף ל-(\d+)\s*ימים', l)
            if m:
                days = int(m.group(1))
                break

        parsed.append({
            'plan_name': plan_name,
            'price': price,
            'data_gb': data_gb,
            'minutes': minutes,
            'sms': sms,
            'days': days,
            'detail_lines': detail_lines,
        })

    # Disambiguate duplicate plan names: all instances get a suffix when duplicated
    from collections import Counter
    name_counter = Counter(p['plan_name'] for p in parsed)

    plans = []
    for p in parsed:
        name = p['plan_name']
        if name_counter[name] > 1:
            if p['minutes']:
                name = f"{name} \u2013 {p['minutes']} \u05d3\u05e7\u05f3"
            else:
                name = f"{name} \u2013 {int(p['price'])}\u20aa"
        plans.append({
            'carrier': 'rami_levy',
            'plan_name': name,
            'price': p['price'],
            'data_gb': p['data_gb'],
            'minutes': p['minutes'],
            'sms': p['sms'],
            'days': p['days'],
            'extras': [WORLD] + p['detail_lines'],
            'url': 'https://mobile.rami-levy.co.il/Home/aboard',
        })
    return plans


def _enrich_rami_levy_abroad_info(page, plans):
    """Attach each plan's "למידע נוסף" modal text as a `__info__|` extra — the per-plan
    terms popup PlanCard renders as the "תנאי התוכנית" button. Mirrors the domestic
    scrape_rami_levy enrichment. The roaming page renders every card twice (a visible
    card + a hidden responsive twin), so only the visible `a.more` is clickable; modal
    is matched back to its plan by PRICE, which is unique per plan."""
    # Modal chrome lines to drop: title, close glyphs, "סגור" button.
    _CHROME = {
        "מידע נוסף על התוכנית",  # מידע נוסף על התוכנית (modal title)
        "✕", "✖", "×", "X", "x",                                                                  # close glyphs
        "סגור",                                                                              # סגור
    }
    try:
        price_to_info = {}
        more = page.locator("a.more")
        for i in range(more.count()):
            link = more.nth(i)
            # Card price = the numeric line immediately before the ₪ line (same rule
            # the body parser uses). Hidden twins (offsetParent === null) return null.
            price = link.evaluate("""el => {
                if (el.offsetParent === null) return null;
                let p = el;
                for (let k=0;k<6 && p;k++){ p=p.parentElement; if (p && p.innerText && p.innerText.length>40) break; }
                const lines = (p ? p.innerText : '').split('\\n').map(s=>s.trim()).filter(Boolean);
                const idx = lines.indexOf('₪');
                if (idx > 0) { const v = parseFloat(lines[idx-1].replace(/,/g,'')); return isNaN(v)?null:v; }
                return null;
            }""")
            if price is None:
                continue
            try:
                link.scroll_into_view_if_needed(timeout=4000)
                page.wait_for_timeout(150)
                link.click(timeout=4000)
                page.wait_for_timeout(700)
                raw = page.evaluate("""() => {
                    const cands = document.querySelectorAll('.modal-body, .modal, [role="dialog"], [class*="modal" i]');
                    for (const m of cands){ if (m.offsetParent !== null && m.innerText && m.innerText.trim().length > 20) return m.innerText; }
                    return null;
                }""")
                if raw:
                    info = "\n".join(
                        l.strip() for l in raw.split("\n")
                        if l.strip() and l.strip() not in _CHROME
                    )
                    if info:
                        price_to_info[round(price, 2)] = info
                page.keyboard.press("Escape")
                page.wait_for_timeout(250)
            except Exception as exc:
                logger.warning(f"_enrich_rami_levy_abroad_info: modal capture failed @ {price}: {exc}")
        for pl in plans:
            pr = pl.get("price")
            info = price_to_info.get(round(pr, 2)) if pr is not None else None
            if info:
                pl["plan_info"] = info
                pl["extras"] = list(pl.get("extras", [])) + [f"__info__|{info}"]
    except Exception as exc:
        logger.warning(f"_enrich_rami_levy_abroad_info: skipped ({exc})")


def scrape_rami_levy_abroad(_page=None):
    """Scrape Rami Levy abroad plans. Single plan covers 145 countries."""
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_UA)
        try:
            page.goto(
                "https://mobile.rami-levy.co.il/Home/aboard",
                timeout=40000,
                wait_until="domcontentloaded"
            )
            page.wait_for_timeout(3000)
            core._dismiss_popups(page)
            body = page.inner_text("body")
            plans = _parse_rami_levy_abroad_body(body)
            _enrich_rami_levy_abroad_info(page, plans)
            return plans
        finally:
            browser.close()


def scrape_rami_levy(_page=None):
    """Scrape Rami Levy domestic plans + per-plan info modal text."""
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    from playwright.sync_api import sync_playwright as _sp
    with _sp() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_UA, viewport={"width": 1280, "height": 800})
        try:
            page.goto(
                "https://mobile.rami-levy.co.il/Home/Packages",
                timeout=40000,
                wait_until="networkidle"
            )
            page.wait_for_timeout(3000)
            core._dismiss_popups(page)
            body = page.inner_text("body")
            plans = _parse_rami_levy_body(body)

            # Click each "למידע נוסף" link and capture the modal text
            more_links = page.locator('a.more')
            total = more_links.count()
            for i in range(min(total, len(plans))):
                try:
                    link = more_links.nth(i)
                    link.scroll_into_view_if_needed()
                    page.wait_for_timeout(200)
                    link.click()
                    page.wait_for_timeout(700)
                    info_text = page.evaluate("""() => {
                        const modals = document.querySelectorAll('.modal-body, .modal');
                        for (const m of modals) {
                            if (m.offsetParent !== null && m.innerText) return m.innerText;
                        }
                        return null;
                    }""")
                    if info_text:
                        # Strip trailing "סגור" button text
                        info_text = re.sub(r'\s*\u05e1\u05d2\u05d5\u05e8\s*$', '', info_text).strip()
                        plans[i]['plan_info'] = info_text
                        # Marker line preserved through extras/JSON round-trip
                        plans[i]['extras'] = list(plans[i].get('extras', [])) + [f"__info__|{info_text}"]
                    # Close modal
                    try:
                        page.keyboard.press('Escape')
                        page.wait_for_timeout(300)
                    except Exception:
                        pass
                except Exception as exc:
                    logger.warning(f"scrape_rami_levy: failed to capture info for plan {i}: {exc}")
            return plans
        finally:
            browser.close()
