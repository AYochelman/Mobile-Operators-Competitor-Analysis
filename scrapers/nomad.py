"""nomad scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
import json as _json
logger = core.logger


# ISO-based coverage (single-country) reuses SAILY_ISO_TO_HEBREW + extras;
# multi-country plans map slug -> region Hebrew. "Unlimited" plans carry a numeric
# fair-use cap in data.amount but say "unlimited" in the name -> detect via name.
_NOMAD_REGION_SLUG_TO_HEBREW = {
    "europe-eSIM": "אירופה",
    "apac-eSIM": "אסיה ואוקיאניה",
    "asia-eSIM": "אסיה",
    "global-eSIM": "גלובלי",
    "global-ex-eSIM": "גלובלי",
    "mena-eSIM": "המזרח התיכון וצפון אפריקה",
    "middle-east-eSIM": "המזרח התיכון",
    "north-america-eSIM": "צפון אמריקה",
    "latin-america-eSIM": "אמריקה הלטינית",
    "caribbean-eSIM": "איי הקריביים",
    "africa-eSIM": "אפריקה",
    "balkans-eSIM": "הבלקן",
    "caucasus-eSIM": "הקווקז",
    "oceania-eSIM": "אוקיאניה",
    "cn-jp-kr-eSIM": "סין, יפן, קוריאה",
    "sg-my-th-eSIM": "סינגפור, מלזיה, תאילנד",
    "gcc-eSIM": "מדינות המפרץ",
    "sea-oceania-eSIM": "דרום מזרח אסיה ואוקיאניה",
}


def _nomad_find_plans(obj):
    if isinstance(obj, dict):
        v = obj.get("plans")
        if isinstance(v, list):
            return v
        for x in obj.values():
            r = _nomad_find_plans(x)
            if r:
                return r
    elif isinstance(obj, list):
        for x in obj:
            r = _nomad_find_plans(x)
            if r:
                return r
    return None


def _nomad_get_plans(url):
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": core._YESIM_UA}, timeout=30)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    m = re.search(r'<script id="vike_pageContext"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return []
    try:
        return _nomad_find_plans(_json.loads(m.group(1))) or []
    except Exception:
        return []


def scrape_nomad_global(_page=None, usd_rate=None):
    """Nomad eSIM plans from embedded vike_pageContext JSON on each /<slug>-eSIM
    page (slugs from sitemap-plans.xml). Single-country -> ISO->Hebrew; multi-country
    -> slug->region Hebrew. Dedups by plan_name keeping the cheapest."""
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    try:
        sm = requests.get("https://www.nomadesim.com/sitemap-plans.xml",
                          headers={"User-Agent": core._YESIM_UA}, timeout=30).text
    except Exception as exc:
        logger.warning(f"Nomad sitemap fetch failed: {exc}")
        return []
    slugs = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm)
             if re.match(r"https://www\.nomadesim\.com/[^/]+-eSIM$", u)]
    iso2he = {**core.SAILY_ISO_TO_HEBREW, **core._YESIM_EXTRA_ISO_TO_HEBREW}
    unmapped = set()

    def _do(url):
        slug = url.rsplit("/", 1)[-1]
        res = []
        for p in _nomad_get_plans(url):
            prod = p.get("product") or {}
            cc = (prod.get("coverage") or {}).get("countries") or []
            if not cc:
                continue
            heb = iso2he.get(cc[0]) if len(cc) == 1 else _NOMAD_REGION_SLUG_TO_HEBREW.get(slug)
            if not heb:
                unmapped.add(cc[0] if len(cc) == 1 else slug)
                continue
            data = (prod.get("service") or {}).get("data") or {}
            amt = data.get("amount")
            unit = (data.get("amount_unit") or "GB").upper()
            if "unlimited" in (prod.get("name") or "").lower():
                gb = None
            elif amt is None:
                continue
            else:
                try:
                    gb = float(amt) / 1024 if unit == "MB" else float(amt)
                except (TypeError, ValueError):
                    continue
            spec = prod.get("specification") or {}
            days = spec.get("duration")
            if days is None or (spec.get("duration_unit") or "DAY").upper() != "DAY":
                continue
            usd = ((p.get("price") or {}).get("USD") or {}).get("amount")
            if usd is None:
                continue
            try:
                price_usd = round(float(usd), 2)
            except (TypeError, ValueError):
                continue
            if price_usd <= 0:
                continue
            price_ils = round(price_usd * usd_rate, 2)
            if gb is None:
                gb_str = "ללא הגבלה"
            elif gb >= 1:
                gb_str = f"{int(gb)}GB"
            else:
                gb_str = f"{round(gb * 1024)}MB"
            plan_name = f"{heb} – {gb_str} – {days} ימים"
            res.append((plan_name, price_ils, price_usd, gb, days, heb))
        return res

    best = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_do, u): u for u in slugs}
        for f in as_completed(futs):
            try:
                for (pn, pil, pusd, gb, days, heb) in f.result():
                    if pn not in best or pil < best[pn][1]:
                        best[pn] = (pn, pil, pusd, gb, days, heb)
            except Exception as exc:
                logger.warning(f"Nomad {futs[f]}: {exc}")
    all_plans = [core._make_global_plan("nomad", pn, pil, "USD", pusd, gb, days, esim=True, extras=[heb])
                 for (pn, pil, pusd, gb, days, heb) in best.values()]
    if unmapped:
        logger.warning(f"Nomad: skipped unmapped {sorted(unmapped)[:30]}")
    logger.info(f"Nomad global: {len(all_plans)} plans from {len(slugs)} pages")
    return all_plans
