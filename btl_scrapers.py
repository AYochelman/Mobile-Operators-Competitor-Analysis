"""Below-the-line (מתחת לקו) reseller / landing-page scrapers.

Sources whose cellular offers do NOT appear on the carriers' official rate
cards: third-party resellers (tiber, zol-li, kamaze, tikshoretishit),
carrier-owned lead-gen pages (Partner sale lobby, Rami Levy hever club +
landing, WeCom sim-data) and Pelephone's ClubDeal members club.

Each source has its own scrape_* function; scrape() aggregates them with
per-source isolation so one broken site doesn't block the rest. Called daily
at 08:15 by app.scrape_resellers_job (alongside pelephon4u_scraper /
pelephone_join_scraper), which diffs results against the previous scrape and
feeds the morning digest's "מתחת לקו" section.

Plan names are deliberately PRICE-FREE and stable, so a price move UPSERTs
the same row (detected as price_change) instead of spawning a new row.

Two sources need a real browser (JS-rendered): Rami Levy hever + Partner
lobby. They share one headless Playwright session via _render_pages().

Usage:
  python btl_scrapers.py          # scrape all sources + print (no DB write)
  python btl_scrapers.py --save   # scrape + upsert into reseller_plans
"""
from __future__ import annotations

import html
import io
import logging
import re
import sys
from datetime import date

import requests

# Windows console defaults to cp1252 — force UTF-8 so Hebrew prints don't crash.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _fetch_text(url: str) -> str:
    """GET a page and return its visible text (tags stripped, entities decoded)."""
    resp = requests.get(url, timeout=25, headers={"User-Agent": _UA})
    resp.raise_for_status()
    raw = resp.text
    raw = re.sub(r"<script[\s\S]*?</script>", " ", raw)
    raw = re.sub(r"<style[\s\S]*?</style>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw)


def _render_pages(urls: list[str]) -> dict[str, str]:
    """Render JS-only pages in one headless Chromium session → {url: body text}."""
    from playwright.sync_api import sync_playwright

    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=_UA, locale="he-IL")
        for url in urls:
            try:
                page = ctx.new_page()
                page.goto(url, timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(6000)
                out[url] = re.sub(r"\s+", " ", page.inner_text("body"))
                page.close()
            except Exception as e:
                logger.warning(f"btl render failed for {url}: {e}")
        browser.close()
    return out


def _today() -> str:
    return date.today().isoformat()


# ───────────────────────────── tiber.co.il ─────────────────────────────
# Cashback broker selling Pelephone / Partner / Golan / 019 plans below the
# official rate cards. Static ASP.NET pages — plan cards end at "להצטרפות".

TIBER_PAGES = [
    ("https://tiber.co.il/Product/Package/Pelephone-Cellular-5G", "pelephone", "5G"),
    ("https://tiber.co.il/Product/Package/Pelephone-Cellular-4G", "pelephone", "4G"),
    ("https://tiber.co.il/Product/Package/Partner-Cellular", "partner", ""),
    ("https://tiber.co.il/Product/Package/Golan-Cellular-4G", "golan", ""),
    ("https://tiber.co.il/Product/Package/019Mobile-Cellular-4G", "mobile019", ""),
]

_TIBER_CARD = re.compile(
    r"סלולר[^₪]{0,80}?(\d{2,4})\s*ג'?יגה(.{0,900}?)"
    r"(\d{1,3}(?:\.\d{1,2})?)\s*₪\s*/?\s*חודש(.{0,140}?)להצטרפות"
)
_TIBER_AFTER = re.compile(r"לאחר (\d+) חודשים (\d{1,3}(?:\.\d{1,2})?)\s*₪ לחודש")
_TIBER_PROMO = re.compile(r"מחיר מבצע ל-?(\d+) חודשים")
_TIBER_CB = re.compile(r"(\d{1,3})\s*₪ קאשבק")
_TIBER_MINS = re.compile(r"(\d{3,5}) דקות והודעות")
# Multi-line ladders, two styles: "2 קווים- 35₪ עבור כל קו" / "שני קווים ומעלה 30₪ לקו"
_TIBER_LADDER = re.compile(r"(\d)\s*קווים\s*(?:ומעלה)?\s*-?\s*(\d{1,3}(?:\.\d{1,2})?)\s*₪")
_TIBER_LADDER2 = re.compile(r"שני קווים ומעלה\s*(\d{1,3}(?:\.\d{1,2})?)\s*₪ לקו")


def scrape_tiber() -> list[dict]:
    plans = []
    for url, carrier, net in TIBER_PAGES:
        try:
            text = _fetch_text(url)
        except requests.RequestException as e:
            logger.warning(f"tiber fetch failed ({carrier}): {e}")
            continue
        best = {}  # (gb) → plan, keep the cheaper card per GB tier
        for m in _TIBER_CARD.finditer(text):
            gb = int(m.group(1))
            mid, tail = m.group(2), m.group(4)
            price = float(m.group(3))
            promo = _TIBER_PROMO.search(tail) or _TIBER_PROMO.search(mid)
            after = _TIBER_AFTER.search(mid)
            cb = _TIBER_CB.search(tail) or _TIBER_CB.search(mid)
            mins = _TIBER_MINS.search(mid)

            suffix = ""
            extras = []
            if promo and after:
                suffix = " — מבצע לחודשיים" if after.group(1) == "2" else f" — מבצע ל-{after.group(1)} חודשים"
                extras.append(f"מחיר מבצע ל-{after.group(1)} חודשים, לאחר מכן {after.group(2)} ₪ לחודש")
            if cb:
                extras.append(f"קאשבק חד-פעמי {cb.group(1)} ₪ למנוי דרך טיבר")
            if mins:
                extras.append(f"{mins.group(1)} דקות והודעות SMS")

            name = f"{gb}GB{' ' + net if net else ''}{suffix}".strip()
            plan = {
                "reseller_id": "tiber", "carrier": carrier, "plan_name": name,
                "price": price, "data_gb": float(gb),
                "minutes": int(mins.group(1)) if mins else None,
                "sms": int(mins.group(1)) if mins else None,
                "extras": extras, "source_url": url, "seen_at": _today(),
            }
            if gb not in best or price < best[gb]["price"]:
                best[gb] = plan

            # Multi-line ladder lives inside the card bullets → emit a dedicated row
            ladder = _TIBER_LADDER.findall(mid)
            ladder2 = _TIBER_LADDER2.search(mid)
            if ladder and len(ladder) >= 2:
                steps = ", ".join(f"{n} קווים: {p} ₪ לקו" for n, p in ladder)
                lp = min(float(p) for _, p in ladder)
                best[(gb, "multi")] = {
                    "reseller_id": "tiber", "carrier": carrier,
                    "plan_name": f"{gb}GB{' ' + net if net else ''} — רב-קווי",
                    "price": lp, "data_gb": float(gb),
                    "minutes": int(mins.group(1)) if mins else None,
                    "sms": int(mins.group(1)) if mins else None,
                    "extras": [f"מדרגות רב-קו: {steps}", f"מנוי בודד: {price} ₪"] + extras[-1:],
                    "source_url": url, "seen_at": _today(),
                }
            elif ladder2:
                best[(gb, "multi")] = {
                    "reseller_id": "tiber", "carrier": carrier,
                    "plan_name": f"{gb}GB{' ' + net if net else ''} — רב-קווי",
                    "price": float(ladder2.group(1)), "data_gb": float(gb),
                    "minutes": int(mins.group(1)) if mins else None,
                    "sms": int(mins.group(1)) if mins else None,
                    "extras": [f"שני קווים ומעלה: {ladder2.group(1)} ₪ לקו", f"מנוי בודד: {price} ₪"] + extras[-1:],
                    "source_url": url, "seen_at": _today(),
                }
        plans.extend(best.values())
    return plans


# ───────────────────────────── zol-li.co.il ─────────────────────────────
# HOT Mobile dealer channel — plans absent from hotmobile.co.il's saleslobby.

ZOL_LI_URL = ("https://www.zol-li.co.il/"
              "%D7%94%D7%95%D7%98-%D7%9E%D7%95%D7%91%D7%99%D7%99%D7%9C-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/")

# Card title → its "פרטי המסלול / פירוט המחיר" detail block
_ZOL_CARD = re.compile(
    r"פרטי המסלול:\s*(.{10,400}?)פירוט המחיר:\s*(.{5,260}?)(?:get_app|התקנה:)"
)
_ZOL_TITLE = re.compile(r"((?:סלולר\s*)?(?:דור 5\s*)?(?:5G|4G|משפחתי|TOP)[\w\s./-]{0,30}?(\d{2,4})GB[\w\s.\-–]{0,25}?)\s*(?:&nbsp|\d[\d,]{2,4} דק)")
_ZOL_PRICE = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)\s*₪ לחודש")
_ZOL_SINGLE = re.compile(r"מנוי בודד\s*(\d{1,3}(?:\.\d{1,2})?)\s*₪")
_ZOL_COND = re.compile(r"בצירוף (\d) מנויים ומעלה")


def scrape_zol_li() -> list[dict]:
    text = _fetch_text(ZOL_LI_URL)
    plans, seen = [], set()
    # Each card carries a "פרטי המסלול … פירוט המחיר …" detail block. Two
    # pricing styles on the page:
    #   "הנחה בצירוף 2 מנויים ומעלה 35 ₪ לחודש למנוי … (מנוי בודד 39.9 ₪ …)"
    #   "39.9 ₪ לחודש למשך 24 חודשים. בצירוף 3 מנויים ומעלה: הנחה של 9.9 ₪
    #    למנוי (עלות חודשית של 30 ₪)"
    for m in _ZOL_CARD.finditer(text):
        details, pricing = m.group(1), m.group(2)
        gbm = re.search(r"(\d{2,4})GB", details)
        base = _ZOL_PRICE.search(pricing)
        if not (gbm and base):
            continue
        gb = int(gbm.group(1))
        net = "5G" if ("5G" in details or "דור 5" in details) else "4G"
        # Card title from the text just before the detail block
        pre = text[max(0, m.start() - 280):m.start()]
        markers = re.findall(r"משפחתי TOP|5G Basic Family|מבצע זוגי", pre)
        title = markers[-1] if markers else None

        single = _ZOL_SINGLE.search(pricing)
        plain_disc = re.search(
            r"הנחה בצירוף (\d) מנויים ומעלה (\d{1,3}(?:\.\d{1,2})?) ₪ לחודש", pricing)
        paren_disc = re.search(
            r"בצירוף (\d) מנויים ומעלה:? הנחה של [\d.]+ ₪ למנוי \(עלות חודש\w*(?: של)? (\d{1,3}(?:\.\d{1,2})?) ₪\)", pricing)

        extras = ["ערוץ משווקים — לא מופיע במחירון הרשמי של הוט מובייל"]
        if plain_disc:
            cond_n, price = plain_disc.group(1), float(plain_disc.group(2))
            extras.append(f"{price} ₪ לקו בצירוף {cond_n} מנויים ומעלה")
            if single:
                extras.append(f"מנוי בודד: {single.group(1)} ₪ לחודש")
        elif paren_disc:
            cond_n, price = paren_disc.group(1), float(paren_disc.group(2))
            extras.append(f"{price} ₪ לקו בצירוף {cond_n} מנויים ומעלה")
            extras.append(f"ללא ההנחה: {base.group(1)} ₪ לחודש")
        else:
            cond_n, price = None, float(base.group(1))
        term = re.search(r"למשך (\d{1,2}) (?:ה)?חודשים|למשך שנה", pricing)
        if term:
            extras.append(f"המחיר קבוע ל-{term.group(1) or '12'} חודשים")

        name = f"הוט מובייל {net} {gb}GB" + (f" — {title}" if title else "")
        key = name
        if key in seen:
            continue
        seen.add(key)
        mins = re.search(r"([\d,]{3,5}) דק", details)
        mins_val = int(mins.group(1).replace(",", "")) if mins else None
        plans.append({
            "reseller_id": "zol_li", "carrier": "hotmobile", "plan_name": name,
            "price": price, "data_gb": float(gb),
            "minutes": mins_val, "sms": mins_val,
            "extras": extras, "source_url": ZOL_LI_URL, "seen_at": _today(),
        })
    return plans


# ───────────────────────────── kamaze.co.il ─────────────────────────────
# Deal-comparison site listing dealer-channel Cellcom/Partner plans.
# Cards end with "לנציג <carrier>".

KAMAZE_PAGES = [
    ("https://www.kamaze.co.il/companies/6378/cellcom/cellular", "cellcom", "סלקום"),
    ("https://www.kamaze.co.il/companies/6383/partner/cellular", "partner", "פרטנר"),
]


def scrape_kamaze() -> list[dict]:
    """Card layout: [card head] לנציג [פרטים נוספים of that card] [next card] לנציג …
    so each card's fine print sits at the START of the chunk that FOLLOWS its
    'לנציג' delimiter. Only cards with a below-the-line marker (multi-line
    discount / intro price / price ladder) are emitted — the rest mirror the
    official rate card, which the main scraper already tracks."""
    plans = []
    for url, carrier, _label in KAMAZE_PAGES:
        try:
            text = _fetch_text(url)
        except requests.RequestException as e:
            logger.warning(f"kamaze fetch failed ({carrier}): {e}")
            continue
        chunks = text.split("לנציג")
        seen = set()
        for i, chunk in enumerate(chunks[:-1]):
            head = chunk[-900:]
            # fine print runs until the next card's "הועתק" copy marker
            details = chunks[i + 1][:700].split("הועתק")[0] if i + 1 < len(chunks) else ""
            both = head + " " + details
            gbm = re.search(r"עד (\d{2,4}) ג'?יגה", head)
            prices = re.findall(r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:ש[\"״]ח|₪) לחודש", head)
            if not (gbm and prices):
                continue
            gb = int(gbm.group(1))
            base_price = float(prices[-1])  # the card's bold price, before לנציג

            disc = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:ש[\"״]ח|₪) לחודש (?:לקו -? ?)?בהצטרפות (שני|שלושה|2|3) מנויים ומעלה", head)
            intro = re.search(r"(חודשיים|\d+ חודשים) (?:ה)?ראשונים ב-(\d{1,3}(?:\.\d{1,2})?)", both)
            ladder = re.search(
                r"חודשים 1-2: (\d{1,3}(?:\.\d{1,2})?) .{0,40}?חודשים 3-12: (\d{1,3}(?:\.\d{1,2})?) .{0,50}?מחודש 13: (\d{1,3}(?:\.\d{1,2})?)",
                details)
            if not (disc or intro or ladder):
                continue  # rate-card mirror — skip

            extras = ["ערוץ הצטרפות/משווקים — תמחור שאינו בדף החבילות הרשמי"]
            suffix = ""
            price = base_price
            if disc:
                n = {"שני": "2", "שלושה": "3"}.get(disc.group(2), disc.group(2))
                suffix = f" — בהצטרפות {n} מנויים ומעלה"
                price = float(disc.group(1))
                extras.append(f"{price} ₪ לקו בהצטרפות {n} מנויים ומעלה")
                single = re.search(r"מחיר ל ?1-2 מנויים: (\d{1,3}(?:\.\d{1,2})?)", both) \
                    or re.search(r"מחיר מנוי 1: (\d{1,3}(?:\.\d{1,2})?)", both)
                if single:
                    extras.append(f"מחיר למנוי בודד: {single.group(1)} ₪ לחודש")
            if ladder:
                suffix = suffix or " — מדרגות מחיר"
                extras.append(f"חודשים 1-2: {ladder.group(1)} ₪ · חודשים 3-12: {ladder.group(2)} ₪ · מחודש 13: {ladder.group(3)} ₪")
                price = float(ladder.group(2))
            elif intro:
                suffix = suffix or " — מבצע היכרות"
                extras.append(f"{intro.group(1)} ראשונים ב-{intro.group(2)} ₪ לחודש")
            bonus = re.search(r"הטבה לאחר שנה: ([^!₪]{5,60})", both)
            if bonus:
                extras.append(f"הטבה לאחר שנה: {bonus.group(1).strip()}")

            name = f"{gb}GB{suffix}"
            if name in seen:
                continue
            seen.add(name)
            plans.append({
                "reseller_id": "kamaze", "carrier": carrier,
                "plan_name": name,
                "price": price, "data_gb": float(gb),
                "minutes": None, "sms": None,
                "extras": extras, "source_url": url, "seen_at": _today(),
            })
    return plans


# ──────────────────────────── we-com sim-data ────────────────────────────
# WeCom's own data-only SIM page — absent from the scraped מסלולים rate card.

WECOM_URL = "https://we-com.co.il/sim-data/"


def scrape_wecom_simdata() -> list[dict]:
    text = _fetch_text(WECOM_URL)
    plans = []
    for m in re.finditer(r"סים דאטה דור (\d)\s*(\d{2,4})GB\s*(\d{1,3}(?:\.\d{1,2})?)\s*₪", text):
        gen, gb, price = m.group(1), int(m.group(2)), float(m.group(3))
        plans.append({
            "reseller_id": "wecom_site", "carrier": "wecom",
            "plan_name": f"סים דאטה דור {gen} — {gb}GB",
            "price": price, "data_gb": float(gb), "minutes": 0, "sms": 0,
            "extras": [
                "גלישה בלבד — ללא שיחות וללא SMS",
                "ללא דמי חיבור ועלות סים",
                "דורש מכשיר התומך בהגדרת APN ידנית",
            ],
            "source_url": WECOM_URL, "seen_at": _today(),
        })
    return plans


# ────────────────────── Rami Levy lead-gen landing ──────────────────────
# Already tracked manually as reseller_id rami_levy_landing — this keeps the
# 3 packages fresh automatically. Plan names must match the seeded ones.

RAMI_LANDING_URL = "https://landing-mobile.rami-levy.co.il/landing/"

_RAMI_CARD = re.compile(
    r"(\d{3,4})GB\s+(.+?)\s+\1GB נפח גלישה\s+(\d{3,5}) דקות שיחה\s+(\d{3,5}) SMS הודעות\s+₪\s*(\d{1,3}(?:\.\d{1,2})?)(.{0,40}?)תוקף:\s*(\d+) חודשים"
)


def scrape_rami_landing() -> list[dict]:
    text = _fetch_text(RAMI_LANDING_URL)
    gift = "חודש במתנה למצטרפים חדשים" in text
    plans = []
    for m in _RAMI_CARD.finditer(text):
        gb, title, mins, sms, price, tail, term = m.groups()
        title = re.sub(r"ב-\s+", "ב-", title.strip())
        name = title if "ב-" in title else f"{title} – {gb}GB"
        extras = [f"תוקף: {term} חודשים"]
        per_line = re.search(r"(\d{1,3}(?:\.\d{1,2})?)\s*₪ לכל קו", tail)
        if "לשני קווים" in tail:
            extras.insert(0, f"₪{price} לשני הקווים יחד")
        elif per_line:
            extras.insert(0, f"₪{price} לכל הקווים יחד ({per_line.group(1)} ₪ לקו)")
        if gift and "זוגות" in name:
            extras.append("חודש במתנה למצטרפים חדשים")
        extras.append("בכפוף לתקנון המבצע והסכם ההתקשרות (ט.ל.ח)")
        plans.append({
            "reseller_id": "rami_levy_landing", "carrier": "rami_levy",
            "plan_name": name, "price": float(price), "data_gb": float(gb),
            "minutes": int(mins), "sms": int(sms),
            "extras": extras, "source_url": RAMI_LANDING_URL, "seen_at": _today(),
        })
    return plans


# ──────────────────────── tikshoretishit (Golan) ────────────────────────

TIKSHORET_URL = ("https://tikshoretishit.co.il/"
                 "%D7%92%D7%95%D7%9C%D7%9F-%D7%98%D7%9C%D7%A7%D7%95%D7%9D-750-%D7%92%D7%99%D7%92%D7%94/")


def scrape_tikshoretishit() -> list[dict]:
    text = _fetch_text(TIKSHORET_URL)
    m = re.search(
        r"תוכנית (\d{2,4}) ג'?יגה.{0,160}?(\d{2,3})\s*₪ מחיר חודשי\s*\.?\s*(\d+) חודשים ראשונים ב-(\d{2,3})\s*₪",
        text)
    if not m:
        return []
    gb, full_price, intro_months, intro_price = m.groups()
    mins = re.search(r"(\d{3,5}) דקות", text)
    return [{
        "reseller_id": "tikshoretishit", "carrier": "golan",
        "plan_name": f"{gb}GB 5G — מבצע הצטרפות",
        "price": float(intro_price), "data_gb": float(gb),
        "minutes": int(mins.group(1)) if mins else None,
        "sms": int(mins.group(1)) if mins else None,
        "extras": [
            f"{intro_months} חודשים ראשונים ב-{intro_price} ₪, לאחר מכן {full_price} ₪ לחודש",
            "דמי חיבור 30 ₪ + כרטיס סים 19 ₪",
            "במחירון הרשמי של גולן: 750GB ב-49 ₪ ללא מבצע",
        ],
        "source_url": TIKSHORET_URL, "seen_at": _today(),
    }]


# ─────────────────────────── ClubDeal (Pelephone) ───────────────────────────
# Members club owned by Pelephone Communications Ltd — first-year pricing not
# on the public rate card. GB volume is behind the club login.

CLUBDEAL_URL = "https://clubdeal.co.il/pelephone/"


def scrape_clubdeal() -> list[dict]:
    text = _fetch_text(CLUBDEAL_URL)
    m = re.search(r"החל מ (\d{1,3}(?:\.\d{1,2})?) ש[\"״]ח לחודש.{0,160}?לאחר שנה -?(\d{1,3}(?:\.\d{1,2})?) ש[\"״]ח", text)
    if not m:
        return []
    first, after = m.groups()
    extras = [
        f"מחיר לשנה הראשונה, לאחר שנה {after} ₪ לחודש למנוי",
        "מועדון בבעלות פלאפון תקשורת בע\"מ — נפח הג'יגה מאחורי לוגין המועדון",
    ]
    card = re.search(r"שובר DREAM CARD בשווי (\d+) ש[\"״]ח", text)
    if card:
        extras.append(f"שובר DREAM CARD בשווי {card.group(1)} ₪ מתנת המועדון")
    return [{
        "reseller_id": "clubdeal", "carrier": "pelephone",
        "plan_name": "ClubDeal — חבילות מועדון (שנה ראשונה)",
        "price": float(first), "data_gb": None, "minutes": None, "sms": None,
        "extras": extras, "source_url": CLUBDEAL_URL, "seen_at": _today(),
    }]


# ──────────────── JS-rendered: Rami Levy hever + Partner lobby ────────────────

HEVER_URL = "https://mobile.rami-levy.co.il/Home/Hever"
PARTNER_LOBBY_URL = "https://www.partner.co.il/n/cellularsale/lobby"


def _parse_hever(text: str) -> list[dict]:
    plans = []
    for m in re.finditer(r"(\d{2,4})GB (\d{1,3}(?:\.\d{1,2})?) ₪ לחודש תומך דור 5", text):
        gb, price = int(m.group(1)), float(m.group(2))
        plans.append({
            "reseller_id": "rami_levy_hever", "carrier": "rami_levy",
            "plan_name": f"מועדון חבר — {gb}GB דור 5",
            "price": price, "data_gb": float(gb), "minutes": 5000, "sms": 5000,
            "extras": [
                "בלעדי לעמיתי מועדון \"חבר\" (משרתי קבע וגמלאים)",
                "5,000 דקות שיחה + 5,000 הודעות",
                "500 דקות שיחה לחו\"ל",
            ],
            "source_url": HEVER_URL, "seen_at": _today(),
        })
    return plans


_PARTNER_NAME = re.compile(r"(Partner [A-Za-z]+(?: 5G)?(?: NEW)?|Better Future Boost 5G)")


def _parse_partner_lobby(text: str) -> list[dict]:
    plans = []
    for chunk in text.split("תנאי התכנית"):
        names = _PARTNER_NAME.findall(chunk)
        gbm = re.search(r"(\d{3,4})\s*GB", chunk)
        pm = re.search(r"(\d{2,3}(?:\.\d)?)\s*₪ לחודש למנוי", chunk)
        if not (names and gbm and pm):
            continue
        # the card title is the LAST "Partner X" before the price — earlier
        # matches are nav items like "Partner tv"
        name, gb, price = names[-1], int(gbm.group(1)), float(pm.group(1))
        multi = re.search(r"בצרוף (\d+) מנויים ומעלה", chunk)
        single = re.search(r"מנוי יחיד (\d{2,3}(?:\.\d)?)\s*₪", chunk)
        intro = re.search(r"₪ לחודש למנוי למשך (\d+) חודשים", chunk)
        after = re.search(r"(\d{2,3}(?:\.\d)?) לחודש למנוי מהחודש ה-(\d+)", chunk)
        coupon = re.search(r"קופון אביזרים (\d+) ₪", chunk)
        mins = re.search(r"([\d,]{3,5}) דקות ו-", chunk)
        mins_val = int(mins.group(1).replace(",", "")) if mins else None

        # Only the below-the-line deltas: multi-line price, intro price, coupon
        if not (multi or intro or coupon):
            continue
        extras = ["דף ההצטרפות של פרטנר — תנאים שאינם בלוח התעריפים"]
        suffix = ""
        if multi:
            suffix = " — רב-קווי"
            extras.append(f"{price} ₪ לקו בצירוף {multi.group(1)} מנויים ומעלה")
            if single:
                extras.append(f"מנוי יחיד: {single.group(1)} ₪ לחודש")
        if intro and after:
            suffix = " — מחיר היכרות"
            extras.append(f"{price} ₪ ל-{intro.group(1)} חודשים, מהחודש ה-{after.group(2)}: {after.group(1)} ₪")
        if coupon:
            extras.append(f"קופון אביזרים {coupon.group(1)} ₪ למצטרפים")
            if not suffix:
                suffix = " — קופון אביזרים"
        plans.append({
            "reseller_id": "partner_site", "carrier": "partner",
            "plan_name": f"{name} {gb}GB{suffix}",
            "price": price, "data_gb": float(gb),
            "minutes": mins_val, "sms": mins_val,
            "extras": extras, "source_url": PARTNER_LOBBY_URL, "seen_at": _today(),
        })
    return plans


def scrape_browser_sources() -> list[dict]:
    texts = _render_pages([HEVER_URL, PARTNER_LOBBY_URL])
    plans = []
    if HEVER_URL in texts:
        plans += _parse_hever(texts[HEVER_URL])
    if PARTNER_LOBBY_URL in texts:
        plans += _parse_partner_lobby(texts[PARTNER_LOBBY_URL])
    return plans


# ─────────────────────────────── aggregate ───────────────────────────────

SOURCES = [
    ("tiber", scrape_tiber),
    ("zol_li", scrape_zol_li),
    ("kamaze", scrape_kamaze),
    ("wecom_site", scrape_wecom_simdata),
    ("rami_levy_landing", scrape_rami_landing),
    ("tikshoretishit", scrape_tikshoretishit),
    ("clubdeal", scrape_clubdeal),
    ("browser (hever+partner)", scrape_browser_sources),
]


def scrape() -> list[dict]:
    """Scrape every below-the-line source; per-source failures are logged, not raised."""
    plans = []
    for label, fn in SOURCES:
        try:
            got = fn()
            if got:
                plans.extend(got)
                logger.info(f"btl {label}: {len(got)} plans")
            else:
                logger.warning(f"btl {label}: 0 plans — site layout may have changed")
        except Exception as e:
            logger.warning(f"btl {label} failed: {e}")
    return plans


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    plans = scrape()
    for p in plans:
        gb = "∞" if p["data_gb"] is None else f"{p['data_gb']:.0f}GB"
        print(f"  [{p['reseller_id']:>18}] {p['carrier']:<10} {p['plan_name']}  ({gb}, {p['price']}₪)")
    print(f"\nTotal: {len(plans)} plans")
    if "--save" in sys.argv:
        from db import init_db, save_reseller_plans
        init_db()
        save_reseller_plans(plans)
        print("Upserted into reseller_plans.")


if __name__ == "__main__":
    main()
