"""Facebook-ad (Meta Ad Library) reseller scraper - מתחת לקו.

Some below-the-line offers exist ONLY as Facebook lead-form ads (no landing
page): dealer/lead-gen pages that sell a carrier's plans with prices that are
not on the carrier's rate card. The public Meta Ad Library
(facebook.com/ads/library) shows every ACTIVE ad in Israel without a login, so
we render a keyword search for each advertiser's page name, keep only the ads
whose advertiser line matches exactly, and parse the offer tiers out of the ad
copy.

Advertisers tracked (ADVERTISERS below):
  fb_pelephone_join      "הצטרפות לפלאפון - הרשת המהירה בישראל"  (facebook.com/pelephone.miztarfim)
  fb_pelephone_deals     "פלאפון מבצעים חדשים"                    (facebook.com/61594994356422)
  fb_pelephone_promos    "פלאפון- מבצעים"                          (added 2026-11-10)
  fb_simpel              "סימפל אתר השוואת מחירים"                 (comparison site; carrier read per ad)
  fb_rami_levy_branches  "רמי לוי תקשורת - סניפים"                 (Rami Levy branches page)

Offer extraction is regex over the ad text, tolerant of the copy variants these
pages rotate through:
  * "1–4 מנויים: 29.90 ₪ ... 5 מנויים ומעלה: 20 ₪"   (tier disclosure)
  * "רק 20 ₪ לחודש ואתם נהנים מ־400GB ... למצטרפים 5 מנויים ומעלה"
  * "5 מנויים ב-100 ₪ לחודש"                           (bundle total -> per line)
  * "4 מנויים במסלול דור 5 של פלאפון ב-100 ₪"          (words between count and price)
  * "שני קווי סלולר ב־55 ₪" / "3 קווים רק ב-80₪"        (קווים / קווי, number words)
  * "400 גיגה" / "400 גי'גה"                            (Hebrew GB unit)
  * "המחיר קבוע ל-12 חודשים. אחר כך 69.90 ₪"           (promo length + list price after it)
Rows are keyed by (data_gb, minimum lines) and the plan name is PRICE-FREE,
so a price move is a price_change and not a new row. The stored price is PER
LINE; the multi-line condition is spelled out in the plan name + extras.

When a campaign ends, the advertiser returns 0 ads: sync_reseller_plans then
leaves the old rows alone (it only touches pairs that returned >=1 plan) and the
morning digest's freshness check flags the source as stale - that is the
"campaign ended, remove or re-check" signal.

Usage:
  python fb_ads_scraper.py          # scrape + print (no DB write)
  python fb_ads_scraper.py --save   # scrape + sync_reseller_plans
"""
from __future__ import annotations

import io
import logging
import re
import sys
import urllib.parse
from datetime import date

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

ADVERTISERS = [
    {
        "reseller_id": "fb_pelephone_join",
        "carrier": "pelephone",
        "page_name": "הצטרפות לפלאפון - הרשת המהירה בישראל",
        "query": "הצטרפות לפלאפון",
    },
    {
        "reseller_id": "fb_pelephone_deals",
        "carrier": "pelephone",
        "page_name": "פלאפון מבצעים חדשים",
        "query": "פלאפון מבצעים חדשים",
    },
    {
        "reseller_id": "fb_pelephone_promos",
        "carrier": "pelephone",
        "page_name": "פלאפון- מבצעים",
        "query": "פלאפון- מבצעים",
    },
    {
        # A price-comparison site: it can advertise any carrier, so the carrier
        # is read from each ad's copy; an ad naming no single carrier is skipped
        # rather than guessed.
        "reseller_id": "fb_simpel",
        "carrier": "pelephone",
        "detect_carrier": True,
        "page_name": "סימפל אתר השוואת מחירים",
        "query": "סימפל אתר השוואת מחירים",
    },
    {
        "reseller_id": "fb_rami_levy_branches",
        "carrier": "rami_levy",
        "page_name": "רמי לוי תקשורת - סניפים",
        "query": "רמי לוי תקשורת - סניפים",
    },
]

_LINES = r"(?:מנויים|קווים|קווי(?:\s*סלולר)?)"   # מנויים / קווים / קווי סלולר
_AND_UP = "ומעלה"                 # ומעלה
_NIS = r"(?:₪|ש\"ח|ש״ח)"      # ₪ / ש"ח
_NUM = r"(\d+(?:\.\d+)?)"
_GB = r"(\d{2,4})\s*(?:GB|ג['׳]?י['׳]?גה)"      # 400GB / 400 גיגה / 400 גי'גה
# Line counts written as words ("שני קווי סלולר"). Longest spelling first.
_WORD_NUM = {"שלושה": 3, "שלוש": 3, "ארבעה": 4, "ארבע": 4, "חמישה": 5, "חמש": 5,
             "שישה": 6, "שש": 6, "שני": 2, "שתי": 2}
_COUNT = r"(\d+|" + "|".join(_WORD_NUM) + r")"
# "N lines ... ב-T ₪": the bundle TOTAL. Words may sit between the count and the
# price ("4 מנויים במסלול דור 5 של פלאפון ב-100 ₪"), but not a line break, a ₪ or
# a colon (that is a tier disclosure). A price followed by "למנוי"/"לקו" is
# already per line.
_BUNDLE_RE = re.compile(
    _COUNT + r"\s*" + _LINES + r"[^\n₪:]{0,45}?(?<![א-ת])ב-?\s*" + _NUM + r"\s*" + _NIS
    + r"(\s*(?:למנוי|לקו|לכל\s*(?:מנוי|קו))(?![א-ת]))?")

# Carrier names for advertisers that sell more than one carrier (detect_carrier).
_CARRIER_WORDS = [
    ("pelephone", r"פלאפון"), ("cellcom", r"סלקום"), ("partner", r"פרטנר"),
    ("hotmobile", r"הוט\s*מובייל"), ("golan", r"גולן"), ("rami_levy", r"רמי\s*לוי"),
    ("mobile019", r"019"), ("xphone", r"אקספון|XPhone"), ("wecom", r"וי-?קום|We4G"),
]


def _count(s: str) -> int:
    return int(s) if s.isdigit() else _WORD_NUM[s]


def detect_carrier(text: str) -> str | None:
    """The one carrier an ad names, or None when it names none or several."""
    hits = [c for c, rx in _CARRIER_WORDS if re.search(rx, text)]
    return hits[0] if len(hits) == 1 else None


def ad_library_url(query: str) -> str:
    return ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
            "&country=IL&q=" + urllib.parse.quote(query)
            + "&search_type=keyword_unordered&media_type=all")


def _today() -> str:
    return date.today().isoformat()


def _render(urls: list[str]) -> dict[str, str]:
    """Render Ad Library searches in one headless Chromium session -> {url: body text}."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(locale="he-IL", user_agent=_UA)
            for url in urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(8000)
                    for _ in range(4):           # lazy-loaded result cards
                        page.mouse.wheel(0, 5000)
                        page.wait_for_timeout(1500)
                    out[url] = page.inner_text("body")
                except Exception as e:
                    logger.warning(f"fb_ads: render failed for {url}: {e}")
        finally:
            browser.close()
    return out


def ad_texts_for(body: str, page_name: str) -> list[str]:
    """Split the Ad Library result text into ad cards and return the copy of the
    cards whose advertiser line is exactly `page_name` (deduplicated)."""
    texts, seen = [], set()
    for card in re.split(r"\n(?=פעילה\n)", body):   # "פעילה" opens a card
        lines = [l.strip() for l in card.split("\n")]
        if page_name not in lines:
            continue
        i = lines.index(page_name)
        copy = "\n".join(l for l in lines[i + 1:] if l and l != "​")
        if copy not in seen:
            seen.add(copy)
            texts.append(copy)
    return texts


def parse_offers(text: str) -> list[dict]:
    """Extract offer tiers from one ad's copy.
    Returns [{data_gb, min_lines, max_lines, price, after_price, minutes, gen5}]."""
    t = text.replace("–", "-").replace("—", "-").replace("־", "-")
    gbs = [int(g) for g in re.findall(_GB, t)]
    if not gbs:
        return []
    data_gb = gbs[0]
    m = re.search(r"([\d,]{3,})\s*דקות", t)                       # דקות
    minutes = int(m.group(1).replace(",", "")) if m else None
    m = (re.search(r"(?:לאחר (?:שנה|\d+ חודשים)|אחר כך|לאחר מכן)[:\s-]*" + _NUM + r"\s*" + _NIS, t)
         or re.search(r"מחיר החבילה (?:לקו|למנוי) (?:הינו |הוא )?" + _NUM, t))
    after = float(m.group(1)) if m else None
    gen5 = bool(re.search(r"דור 5|5G", t))
    months = _fixed_months(t)
    perks = []
    if re.search(r"חודש (?:ב)?מתנה", t):
        perks.append("חודש מתנה לכל קו" + (" למגיעים לסניף עם המודעה" if "סניף" in t else ""))
    m = re.search(r"דמי חיבור[^|\n\d]{0,15}" + _NUM, t)
    if m:
        perks.append(f"דמי חיבור חד-פעמיים {float(m.group(1)):g} ₪ לקו")

    tiers: dict[int, dict] = {}

    def add(min_lines, price, max_lines=None, total=None):
        price = round(float(price), 2)
        if not (5 <= price <= 300) or min_lines < 1 or min_lines > 10:
            return
        tiers.setdefault(min_lines, {"min_lines": min_lines, "max_lines": max_lines,
                                     "price": price, "total": total})

    # 1) explicit tier disclosure: "1-4 מנויים: 29.90 ₪" / "5 מנויים ומעלה: 20 ₪"
    for a, b, p in re.findall(r"(\d+)\s*-\s*(\d+)\s*" + _LINES + r"\s*:\s*" + _NUM, t):
        add(int(a), p, int(b))
    for n, p in re.findall(r"(\d+)\s*" + _LINES + r"\s*" + _AND_UP + r"\s*:\s*" + _NUM, t):
        add(int(n), p)
    # 2) "רק 20 ₪ לחודש ..." + optional "למצטרפים 5 מנויים ומעלה"
    m = re.search(r"רק\s*" + _NUM + r"\s*" + _NIS + r"\s*לחודש", t)
    if m:
        n = re.search(r"(\d+)\s*" + _LINES + r"\s*" + _AND_UP, t)
        add(int(n.group(1)) if n else 1, m.group(1))
    # 3) bundle total: "5 מנויים ב-100 ₪" / "שני קווי סלולר ב-55 ₪" (a price
    #    followed by "למנוי"/"לקו" is per line, not a total)
    for n, price, per_line in _BUNDLE_RE.findall(t):
        n = _count(n)
        if n < 2:
            continue
        if per_line:
            add(n, price)
        else:
            add(n, float(price) / n, total=float(price))

    return [dict(v, data_gb=data_gb, after_price=after, minutes=minutes, gen5=gen5,
                 months=months, perks=perks)
            for v in tiers.values()]


def _fixed_months(t: str) -> int | None:
    """How long the promo price holds: "המחיר קבוע ל-12 חודשים", "ל-24 החודשים
    הראשונים", "למשך 3 שנים", "לאחר 12 חודשים". None when the ad doesn't say."""
    m = (re.search(r"(?:^|[\s(])ל-?\s*(\d{1,2})\s*ה?חודשים", t)
         or re.search(r"(\d{1,2})\s*חודשים\s*ה?ראשונים", t)
         or re.search(r"לאחר\s*(\d{1,2})\s*חודשים", t))
    if m and 1 <= int(m.group(1)) <= 60:
        return int(m.group(1))
    m = re.search(r"למשך\s*(\d)\s*שנים", t)
    if m:
        return 12 * int(m.group(1))
    if re.search(r"לאחר\s*שנה|קבוע\s*ל-?\s*שנה", t):
        return 12
    return None


def _months_label(months: int) -> str:
    if months == 12:
        return "שנה"
    if months % 12 == 0:
        return f"{months // 12} שנים"
    return f"{months} חודשים"


def _plan_name(o: dict) -> str:
    if o["min_lines"] <= 1:
        lines = (f"{o['min_lines']}-{o['max_lines']} מנויים"
                 if o.get("max_lines") else "קו בודד")     # קו בודד
    else:
        lines = f"{o['min_lines']} מנויים ומעלה"
    return f"{o['data_gb']}GB – {lines} – קמפיין פייסבוק"


def _to_plan(adv: dict, o: dict, url: str) -> dict:
    extras = []
    if o["min_lines"] > 1:
        total = o.get("total") or o["price"] * o["min_lines"]
        extras.append(f"{o['price']:g} ₪ למנוי בהצטרפות "
                      f"{o['min_lines']} מנויים ומעלה "
                      f"(סה\"כ {total:g} ₪)")
    elif o.get("max_lines"):
        extras.append(f"{o['price']:g} ₪ למנוי ב-{o['min_lines']}-{o['max_lines']} מנויים")
    months = o.get("months")
    if o.get("after_price"):
        extras.append(f"לאחר {_months_label(months or 12)}: {o['after_price']:g} ₪ לחודש למנוי")
    elif months:
        extras.append(f"מחיר קבוע ל-{_months_label(months)}")
    if o.get("gen5"):
        extras.append("דור 5")
    extras.extend(o.get("perks") or [])
    extras.append(f"מודעת פייסבוק של העמוד \"{adv['page_name']}\"")
    extras.append("למצטרפים חדשים, הצטרפות דרך טופס לידים במודעה")
    return {
        "reseller_id": adv["reseller_id"], "carrier": o.get("carrier") or adv["carrier"],
        "plan_name": _plan_name(o), "price": o["price"], "data_gb": float(o["data_gb"]),
        "minutes": o.get("minutes"), "sms": o.get("minutes"),
        "extras": extras, "source_url": url, "seen_at": _today(),
    }


def plans_from_body(adv: dict, body: str, url: str) -> list[dict]:
    """Parse every matching ad of one advertiser into deduplicated plan rows.
    Same (data_gb, min_lines) seen in several ad variants -> first wins, but
    missing fields (minutes, after-price) are filled from later variants."""
    merged: dict[tuple, dict] = {}
    for text in ad_texts_for(body, adv["page_name"]):
        carrier = adv["carrier"]
        if adv.get("detect_carrier"):
            carrier = detect_carrier(text)
            if carrier is None:
                if parse_offers(text):
                    logger.info(f"fb_ads {adv['reseller_id']}: skipped an ad naming no single carrier")
                continue
        for o in parse_offers(text):
            o["carrier"] = carrier
            key = (carrier, o["data_gb"], o["min_lines"])
            if key not in merged:
                merged[key] = o
            else:
                for f in ("minutes", "after_price", "max_lines", "months", "total"):
                    if merged[key].get(f) is None and o.get(f) is not None:
                        merged[key][f] = o[f]
                merged[key]["gen5"] = merged[key]["gen5"] or o["gen5"]
                merged[key]["perks"] = merged[key]["perks"] or o["perks"]
    return [_to_plan(adv, o, url) for o in merged.values()]


def scrape() -> list[dict]:
    urls = {a["reseller_id"]: ad_library_url(a["query"]) for a in ADVERTISERS}
    bodies = _render(list(urls.values()))
    plans = []
    for adv in ADVERTISERS:
        url = urls[adv["reseller_id"]]
        body = bodies.get(url, "")
        try:
            got = plans_from_body(adv, body, url)
        except Exception as e:
            logger.warning(f"fb_ads {adv['reseller_id']} parse failed: {e}")
            continue
        if got:
            logger.info(f"fb_ads {adv['reseller_id']}: {len(got)} plans")
            plans.extend(got)
        else:
            logger.warning(f"fb_ads {adv['reseller_id']}: 0 plans (campaign ended or Ad Library layout changed)")
    return plans


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    plans = scrape()
    for p in plans:
        print(f"  [{p['reseller_id']:>21}] {p['plan_name']}  ({p['price']}₪, {p['minutes']} min)")
        for e in p["extras"]:
            print(f"       - {e}")
    print(f"\nTotal: {len(plans)} plans")
    if "--save" in sys.argv:
        from db import init_db, sync_reseller_plans
        init_db()
        changes = sync_reseller_plans(plans)
        print(f"Synced into reseller_plans ({len(changes)} changes).")


if __name__ == "__main__":
    main()
