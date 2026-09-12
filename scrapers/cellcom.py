"""cellcom scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
import json as _json
import urllib.request
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module
logger = core.logger


def _cellcom_extract_terms_urls(data):
    """Walk Cellcom's Episerver Packages JSON → {plan_name: terms_url}.
    Per package: last featureLink (the visible 'לעיקרי התוכנית' anchor), falling back to
    the block-level programDetailsLink / termsLink — the 2026-06-11 lineup refresh
    (500GB/550GB/1500GB) shipped cards whose featureList had no link at all.
    """
    plan_urls = {}
    content_areas = (data.get("mainContentArea") or {}).get("expandedValue") or []
    for area in content_areas:
        tabs = (area.get("tabs") or {}).get("expandedValue") or []
        for tab in tabs:
            packages = (tab.get("salePackages") or {}).get("expandedValue") or []
            for pkg in packages:
                # Plan name: text before <br> ('title' is the populated field; 'packageTitle' is legacy)
                title_html = ((pkg.get("title") or {}).get("value")
                              or (pkg.get("packageTitle") or {}).get("value") or "")
                name = re.sub(r"<[^>]+>", " ", title_html.split("<br")[0]).strip()
                if not name:
                    continue
                feat_url = None
                for ef in ((pkg.get("extraFeatures") or {}).get("expandedValue") or []):
                    for feat in ((ef.get("featureList") or {}).get("expandedValue") or []):
                        link = (feat.get("featureLink") or {}).get("value")
                        if link:
                            feat_url = link
                if not feat_url:
                    for key in ("programDetailsLink", "termsLink"):
                        link = (pkg.get(key) or {}).get("value")
                        if link:
                            feat_url = link
                            break
                if feat_url:
                    if not feat_url.startswith("http"):
                        feat_url = "https://contentepi.cellcom.co.il" + feat_url
                    plan_urls[name] = feat_url
    return plan_urls


def _fetch_cellcom_terms_urls():
    """Fetch plan terms PDF URLs from Cellcom Episerver API (see _cellcom_extract_terms_urls)."""
    api_url = (
        "https://contentepi.cellcom.co.il/production/Private/Cellular/Packages/"
        "?expand=*&currentPageUrl=%2Fproduction%2FPrivate%2FCellular%2FPackages%2F"
    )
    try:
        # Without Accept: application/json Episerver serves the HTML page instead
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0",
                                                       "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode())
        return _cellcom_extract_terms_urls(data)
    except Exception as exc:
        logger.warning(f"_fetch_cellcom_terms_urls failed: {exc}")
        return {}


def scrape_cellcom(page):
    page.goto("https://cellcom.co.il/production/Private/Cellular/Packages/", timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(4000)
    # Fetch terms URLs via in-page fetch() (CORS allowed — same parent domain)
    cellcom_urls = {}
    try:
        raw = page.evaluate("""async () => {
            const r = await fetch(
                'https://contentepi.cellcom.co.il/production/Private/Cellular/Packages/' +
                '?expand=*&currentPageUrl=%2Fproduction%2FPrivate%2FCellular%2FPackages%2F',
                { headers: { 'Accept': 'application/json' } }
            );
            return r.text();
        }""")
        cellcom_urls = _cellcom_extract_terms_urls(_json.loads(raw))
    except Exception as exc:
        logger.warning(f"scrape_cellcom: failed to fetch terms URLs: {exc}")
    plans = []
    for card in page.query_selector_all(".package"):
        # Only cellular plan cards
        sale_type = card.get_attribute("data-saletype") or ""
        if sale_type and "cellular" not in sale_type.lower():
            continue
        title_el  = card.query_selector(".header .title p")
        price_el  = card.query_selector(".body-package .content")
        feat_els  = card.query_selector_all(".body-package .header-feature .text")
        extras    = [el.inner_text().strip() for el in feat_els if el.inner_text().strip()]
        # Name and GB are in same element separated by newline
        name, gb_text = "לא ידוע", None
        if title_el:
            parts = [p.strip() for p in title_el.inner_text().split("\n") if p.strip()]
            name    = parts[0] if parts else "לא ידוע"
            gb_text = parts[1] if len(parts) > 1 else None
        # Price: first line only (ignore promo text like "לחודשיים הראשונים")
        price = core._parse_price(price_el.inner_text().split("\n")[0]) if price_el else None
        gb    = core._parse_gb(gb_text)
        # Lineup-refresh cards (e.g. '500GB') carry the GB in the name with no second
        # title line — without this, data_gb=None renders as "ללא הגבלה". Require an
        # explicit GB suffix so '5G'/'4G Basic' never parse as a volume.
        if gb is None and not gb_text:
            gb_in_name = re.search(r"(\d+(?:\.\d+)?)\s*GB", name, re.IGNORECASE)
            if gb_in_name:
                gb = core._parse_gb(gb_in_name.group(0))
        # Minutes: look for "דק' /SMS" feature line
        minutes = None
        for feat in extras:
            if "דק" in feat and "חו" not in feat:
                minutes = core._parse_minutes(feat)
                break
        if name and name != "לא ידוע":
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "data_gb": gb, "minutes": minutes, "extras": extras,
                          "url": cellcom_urls.get(name)})
    return plans


# Cellcom package codes ("SOC"), e.g. FMWH998 / FMWH0047 / HUL4209. GetPackagePopular
# echoes back ONLY the SOCs the caller asks for, so a SOC we never learned about is a
# package whose terms PDF we can never fetch — hence the DOM discovery in
# scrape_cellcom_abroad.
_CELLCOM_SOC_RE = re.compile(r'\b(?:FMWH|HUL)\d{3,5}\b')

# A Cellcom terms PDF always lives under /globalassets/ on the contentepi CDN (that is
# exactly the shape of every `policiesEpi` value). Anchoring on it keeps the per-card DOM
# fallback from grabbing an unrelated PDF (a price list, a generic brochure) and linking
# the wrong document to a plan.
_CELLCOM_TERMS_HREF_RE = re.compile(r'/globalassets/[^\s"\'<>]+\.pdf', re.I)


def _cellcom_norm_title(name):
    """Cellcom's API `titleEpi` and the DOM card title are the same string typed twice —
       in practice they drift by NBSPs, doubled/trailing spaces, HTML entities and quote
       glyphs (״ vs "). Terms are matched by title, so normalise BOTH sides or a purely
       cosmetic difference silently costs a plan its 'עיקרי התוכנית' link."""
    s = _html_unescape(str(name or "")).replace("\u00a0", " ")
    for src_ch, dst_ch in (("\u05f4", '"'), ("\u201c", '"'), ("\u201d", '"'),
                           ("\u05f3", "'"), ("\u2018", "'"), ("\u2019", "'")):
        s = s.replace(src_ch, dst_ch)
    return re.sub(r"\s+", " ", s).strip()


def _cellcom_fetch_abroad_policies(soc_ids, block_id):
    """Return (by_title, by_soc) terms-PDF maps for one Cellcom abroad GetPackagePopular
       block. The PDF is each package's `policiesEpi` — the same doc the roaming card
       surfaces via 'חשוב לדעת' → 'לתנאי חבילה המלאים' — served from the contentepi CDN.
       Used to populate `terms_url` (the 'עיקרי התוכנית' link) on each plan. `by_soc` is
       the authoritative key (one package, one code); `by_title` covers plans scraped from
       the DOM, whose SOC the card may not expose."""
    import urllib.request, json as _json
    out, by_soc = {}, {}
    try:
        payload = _json.dumps({"SocIdList": soc_ids, "BlockId": block_id}).encode()
        req = urllib.request.Request(
            "https://digital-api.cellcom.co.il/api/abroad/GetPackagePopular",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://cellcom.co.il",
                "Referer": "https://cellcom.co.il/AbroadMain/lobby/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())
        for pkg in data.get("Body", []):
            name = _cellcom_norm_title(pkg.get("titleEpi"))
            pol  = pkg.get("policiesEpi")
            if not pol:
                continue
            url = pol if pol.startswith("http") else "https://contentepi.cellcom.co.il" + pol
            if name:
                out[name] = url
            soc = (pkg.get("socCode") or "").strip().upper()
            if soc:
                by_soc[soc] = url
    except Exception as e:
        logger.error(f"Cellcom abroad policies (block {block_id}) failed: {e}")
    return out, by_soc


def scrape_cellcom_abroad(page):
    """Scrape Cellcom abroad packages via their internal API (returns all 8+ plans)
       plus the Silent Roamers page for additional packages."""
    import urllib.request, urllib.error, json as _json

    plans = []
    seen_names = set()

    # ── Source 1: API (lobby packages) ────────────────────────────────────
    SOC_IDS = ["FMWH998","FMWH267","FMWH0047","FMWH717","FMWH720",
               "HUL4209","FMWH995","HUL4539"]
    try:
        payload = _json.dumps({"SocIdList": SOC_IDS, "BlockId": 20557}).encode()
        req = urllib.request.Request(
            "https://digital-api.cellcom.co.il/api/abroad/GetPackagePopular",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://cellcom.co.il",
                "Referer": "https://cellcom.co.il/AbroadMain/lobby/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())
        for pkg in data.get("Body", []):
            name = (pkg.get("titleEpi") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            price   = pkg.get("price")
            days    = pkg.get("packageDuration")
            details = (pkg.get("packageDetailsList") or [{}])[0]
            d_data  = details.get("data") or {}
            d_voice = details.get("voice") or {}
            d_sms   = details.get("sms") or {}
            gb      = float(d_data["value"]) if d_data.get("value") is not None else None
            if d_data.get("isUnlimited"):
                gb = None
            minutes = int(d_voice["value"]) if d_voice.get("value") is not None else None
            sms     = int(d_sms["value"])   if d_sms.get("value")   is not None else None
            extras  = []
            tag = (pkg.get("tagTextSecondary") or "").strip()
            if tag:
                extras.append(tag)
            app_info = pkg.get("dataForApp") or {}
            if app_info.get("hasDataForApp"):
                extras.append("גלישה חופשית באפליקציות נבחרות")
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": extras,
                          "_soc": (pkg.get("socCode") or "").strip().upper() or None})
    except Exception as e:
        logger.error(f"Cellcom abroad API failed: {e}")

    # ── Source 2: Silent Roamers page (DOM) ───────────────────────────────
    page_socs = set()
    try:
        page.goto("https://cellcom.co.il/AbroadMain/Silent_roamers-old/",
                  timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(2000)
        # Every SOC the page mentions — this is what makes terms capture automatic for a
        # package Cellcom publishes here without telling anyone (see the enrich step).
        try:
            page_socs = {m.group(0).upper() for m in _CELLCOM_SOC_RE.finditer(page.content() or "")}
        except Exception:
            page_socs = set()
        for card in page.query_selector_all(".abroad-package-client"):
            name_el     = card.query_selector(".abroad-package-client__title")
            duration_el = card.query_selector(".abroad-package-client__duration")
            data_el     = card.query_selector(".abroad-package-client__data--bank")
            voice_sms   = card.query_selector_all(".abroad-package-voice-sms__value")
            price_el    = card.query_selector(".abroad-package-client__price-real--bank--container")
            name = name_el.inner_text().strip() if name_el else ""
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            days    = core._parse_days(duration_el.inner_text() if duration_el else "")
            gb      = core._parse_gb(data_el.inner_text()) if data_el else None
            minutes = core._parse_minutes(voice_sms[0].inner_text()) if len(voice_sms) > 0 else None
            sms     = core._parse_sms(voice_sms[1].inner_text())     if len(voice_sms) > 1 else None
            price   = None
            if price_el:
                for span in price_el.query_selector_all("span"):
                    t = span.inner_text().strip()
                    if re.match(r'^\d', t):
                        price = core._parse_price(t)
                        break
            # Per-card terms discovery, in the card's OWN subtree only so a neighbour's
            # document can never be attributed to this plan: the package SOC (purchase
            # link / data attribute) and, if the "חשוב לדעת" panel is inline, its PDF.
            card_soc, card_pdf = None, None
            try:
                m = _CELLCOM_SOC_RE.search(card.evaluate("el => el.outerHTML") or "")
                if m:
                    card_soc = m.group(0).upper()
                for a in card.query_selector_all('a[href*=".pdf"]'):
                    href = a.get_attribute("href") or ""
                    if not _CELLCOM_TERMS_HREF_RE.search(href):
                        continue
                    card_pdf = href if href.startswith("http") else \
                        "https://contentepi.cellcom.co.il" + href
                    if "תנאי" in (a.inner_text() or ""):
                        break            # an explicit "לתנאי החבילה" anchor wins
            except Exception:
                pass
            plans.append({"carrier": "cellcom", "plan_name": name, "price": price,
                          "days": days, "data_gb": gb, "minutes": minutes,
                          "sms": sms, "extras": [],
                          "_soc": card_soc, "_dom_terms": card_pdf})
    except Exception as e:
        logger.error(f"Cellcom silent roamers scrape failed: {e}")

    # ── Enrich with terms PDFs (policiesEpi) — the "עיקרי התוכנית" link ────
    # The two known blocks: lobby (BlockId 20557, same SOC list as Source 1) + silent
    # roamers (BlockId 60988). These lists are CLOSED, but Source 2 is open-ended — it
    # ingests whatever cards Cellcom publishes — so a package outside them used to get
    # terms_url=None with nothing to fall back on but PlanCard's hardcoded map, which
    # nobody updates for a plan that launched this morning (that is how the holiday promo
    # "מושלמת לחגים" landed with an empty "עיקרי התוכנית", 2026-09). Anything the page
    # mentions but the lists don't know is therefore asked for by SOC below, so the terms
    # come from Cellcom's own API rather than from a list somebody has to remember to edit.
    SILENT_ROAMER_SOCS = ["FMWH990", "FMWH0065", "HUL4710", "FMWH627", "FMWH947", "FMWH946"]
    KNOWN_SOCS = SOC_IDS + SILENT_ROAMER_SOCS
    terms, terms_by_soc = {}, {}
    for socs, block in ((SOC_IDS, 20557), (SILENT_ROAMER_SOCS, 60988)):
        t, s = _cellcom_fetch_abroad_policies(socs, block)
        terms.update(t); terms_by_soc.update(s)

    new_socs = sorted(page_socs - {s.upper() for s in KNOWN_SOCS})
    for block in (60988, 20557):          # 2nd block only if the 1st returned nothing
        if not new_socs or all(s in terms_by_soc for s in new_socs):
            break
        t, s = _cellcom_fetch_abroad_policies(new_socs, block)
        # setdefault, not update: a page-wide regex can also pick up codes that aren't
        # consumer roaming packages, and those must never overwrite a title the two
        # authoritative blocks already resolved.
        for k, v in t.items():
            terms.setdefault(k, v)
        for k, v in s.items():
            terms_by_soc.setdefault(k, v)
    if new_socs:
        logger.info(f"scrape_cellcom_abroad: discovered {len(new_socs)} SOC(s) not in the "
                    f"known lists {new_socs} — resolved terms for "
                    f"{sum(1 for s in new_socs if s in terms_by_soc)}")

    for pl in plans:
        soc = pl.pop("_soc", None)
        dom_terms = pl.pop("_dom_terms", None)
        # SOC is the authoritative key (one package, one code); title covers DOM-scraped
        # cards that hide their SOC; the card's own PDF anchor is the last resort.
        pl["terms_url"] = (terms_by_soc.get(soc) if soc else None) \
            or terms.get(_cellcom_norm_title(pl["plan_name"])) \
            or dom_terms
        if not pl["terms_url"]:
            logger.warning(
                f"scrape_cellcom_abroad: no terms link for {pl['plan_name']!r} (soc={soc}) — "
                f"Cellcom published a package whose SOC and terms PDF the page never exposed; "
                f"run the plan-terms-coverage skill")

    return plans


def _cellcom_hub_price(page, page_keyword):
    """Extract price from Cellcom hub page by finding product section and clicking its FAQ."""
    try:
        for pct in [0.2, 0.4, 0.6, 0.8, 1.0]:
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
            page.wait_for_timeout(400)
        page.evaluate(f"""
            () => {{
                const allEls = Array.from(document.querySelectorAll('*'));
                let container = null;
                for (const el of allEls) {{
                    const txt = (el.innerText || '').trim();
                    if (txt.includes('{page_keyword}') && txt.length < 200) {{
                        container = el; break;
                    }}
                }}
                if (!container) return false;
                const section = container.closest(
                    'section, article, div[class*="product"], div[class*="card"], div[class*="item"]'
                ) || container.parentElement;
                if (!section) return false;
                const questions = section.querySelectorAll(
                    '.FAQItemBlock__question, [class*="question"], [class*="faq"] button'
                );
                for (const q of questions) {{
                    const qt = (q.innerText || '').trim();
                    if (qt.includes('מה עלות') || qt.includes('עלות השירות')) {{
                        q.scrollIntoView(); q.click(); return true;
                    }}
                }}
                container.scrollIntoView(); container.click(); return true;
            }}
        """)
        page.wait_for_timeout(2000)
        answer = page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll('.FAQItemBlock__answer, [class*="answer"]'));
                for (const el of els) {
                    const txt = (el.innerText || '').trim();
                    if (txt.includes('₪')) return txt;
                }
                return null;
            }
        """)
        if answer:
            price = core._extract_content_price(answer)
            if price:
                return price
        body = page.inner_text("body")
        return core._extract_content_price(body, page_keyword, lookback=0)
    except Exception:
        return None


def _cellcom_faq_esim_price(page, url, attempts=3):
    """Robustly extract the Cellcom eSIM-watch monthly price.

    The price lives only inside the "מה עלות השירות" FAQ accordion on a heavy SPA,
    so the naive click-then-read flaked intermittently and returned "לא נמצא" over a
    good price (false "service not found" alerts, 2026-05-28 + 2026-07-01). Hardened:
      1. wait for the FAQ block to actually render (not just networkidle),
      2. read answers via textContent — the answer DOM usually exists even while the
         accordion is collapsed, so no click/expand-timing dependency,
      3. fall back to expanding the FAQ (flexible text match) + innerText,
      4. fall back to a keyword-scoped scan of the rendered page + raw HTML,
      5. retry the whole flow with a fresh navigation.
    Returns a "₪X" string or None. Assumes `page` is already on `url` for attempt 0.
    """
    _ANSWER_SEL = ".FAQItemBlock__answer, [class*='answer']"
    _QUESTION_SEL = ".FAQItemBlock__question, [class*='question'], [class*='faq'] button"
    for attempt in range(attempts):
        try:
            if attempt > 0:
                page.goto(url, timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    page.wait_for_timeout(2500)
            for pct in (0.3, 0.6, 1.0):
                page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
                page.wait_for_timeout(400)
            try:
                page.wait_for_selector(".FAQItemBlock__question", timeout=8000)
            except Exception:
                pass

            # 1) collapsed answers are usually in the DOM already → textContent
            answer = page.evaluate(f"""
                () => {{
                    const els = Array.from(document.querySelectorAll("{_ANSWER_SEL}"));
                    for (const el of els) {{
                        const t = (el.textContent || '').trim();
                        if (t.includes('₪')) return t;
                    }}
                    return null;
                }}
            """)
            price = core._extract_content_price(answer) if answer else None
            if price:
                return price

            # 2) expand the cost FAQ (flexible match), else expand all, then read
            page.evaluate(f"""
                () => {{
                    const qs = Array.from(document.querySelectorAll("{_QUESTION_SEL}"));
                    let hit = false;
                    for (const q of qs) {{
                        const t = (q.innerText || q.textContent || '').trim();
                        if (t.includes('עלות השירות') || t.includes('מה עלות') || t.includes('כמה עול')) {{
                            q.scrollIntoView(); q.click(); hit = true;
                        }}
                    }}
                    if (!hit) {{ for (const q of qs) {{ try {{ q.click(); }} catch (e) {{}} }} }}
                }}
            """)
            page.wait_for_timeout(2000)
            answer = page.evaluate(f"""
                () => {{
                    const els = Array.from(document.querySelectorAll("{_ANSWER_SEL}"));
                    for (const el of els) {{
                        const t = (el.innerText || el.textContent || '').trim();
                        if (t.includes('₪')) return t;
                    }}
                    return null;
                }}
            """)
            price = core._extract_content_price(answer) if answer else None
            if price:
                return price

            # 3) last resort — keyword-scoped scan of rendered text + raw HTML (a
            #    naive full-page ₪ grab would risk catching an unrelated price)
            body = page.inner_text("body")
            html = re.sub(r"<[^>]+>", " ", page.evaluate("() => document.documentElement.innerHTML"))
            for text in (body, html):
                for kw in ("עלות השירות", "עלות השרות", "כמה עולה", "עלות", "לחודש"):
                    price = core._extract_content_price(text, kw)
                    if price:
                        return price
        except Exception as e:
            logger.warning(f"cellcom_faq_esim attempt {attempt + 1}/{attempts} failed: {e}")
    return None
