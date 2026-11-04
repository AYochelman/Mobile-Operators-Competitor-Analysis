"""yesim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
import json as _json
logger = core.logger


# Price = vanillaPrice/100 * currency.rate (the geo-localized USD price the
# Israel-based backend sees = what Israeli users pay). ISO -> Hebrew reuses
# SAILY_ISO_TO_HEBREW plus a few countries Saily doesn't cover. Palestine (PS)
# is deliberately excluded (left unmapped → skipped).
# Shared supplement of ISO -> Hebrew for countries Saily doesn't cover (used by
# the Yesim and Nomad scrapers on top of SAILY_ISO_TO_HEBREW).
_YESIM_EXTRA_ISO_TO_HEBREW = {
    "AO": "אנגולה", "AN": "האנטילים ההולנדיים", "BT": "בהוטן",
    "BY": "בלארוס", "CU": "קובה", "ET": "אתיופיה", "RU": "רוסיה",
    "AX": "איי אולנד", "BI": "בורונדי", "DJ": "ג'יבוטי", "LY": "לוב",
    "ST": "סאו טומה ופרינסיפה", "VA": "הוותיקן", "US-HI": "הוואי",
}


_YESIM_REGION_TO_HEBREW = {
    "europe-esim": "אירופה",
    "balkans-esim": "הבלקן",
    "asia-pacific-esim": "אסיה ואוקיאניה",
    "south-east-asia-esim": "דרום מזרח אסיה",
    "cis-esim": "חבר העמים",
    "north-america-esim": "צפון אמריקה",
    "south-america-esim": "דרום אמריקה",
    "middle-east-esim": "המזרח התיכון",
    "caribbean-esim": "איי הקריביים",
    "africa-esim": "אפריקה",
}


_YESIM_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _yesim_iso_to_heb(iso):
    return core.SAILY_ISO_TO_HEBREW.get(iso) or _YESIM_EXTRA_ISO_TO_HEBREW.get(iso)


def _yesim_get_pp(url):
    """Fetch a Yesim page and return its Next.js pageProps dict (or None)."""
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": _YESIM_UA}, timeout=30)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return None
    try:
        return _json.loads(m.group(1)).get("props", {}).get("pageProps")
    except Exception:
        return None


def _yesim_page_rate(pp):
    try:
        return float((pp.get("currency") or {}).get("rate", 1)) or 1.0
    except (TypeError, ValueError):
        return 1.0


def _yesim_run_rate(pps, label):
    """One geo rate for the whole run.

    Yesim's backend multiplies vanillaPrice by a per-visitor geo rate (1.2 for an
    Israeli IP since 2026-07, rendered on the page as e.g. $4.20 for a 350-cent
    plan). Some responses intermittently come back with rate 1.0 instead - a
    single page (the 36-plan europe bundle, Sep 2026) or the whole catalog (3,500
    rows on 2026-10-05) - which flapped every plan by x0.833 / x1.2. 1.0 is the
    fallback, so take the highest rate seen in the run and apply it to every page.
    """
    rates = [_yesim_page_rate(pp) for pp in pps if pp]
    if not rates:
        return 1.0
    run_rate = max(rates)
    if min(rates) != run_rate:
        logger.warning(f"Yesim {label}: pages disagree on geo rate {sorted(set(rates))}"
                       f" - pricing all at {run_rate}")
    if run_rate == 1.0:
        logger.warning(f"Yesim {label}: every page returned geo rate 1.0 (fallback?)")
    return run_rate


def _yesim_plans_from_pp(pp, usd_rate, heb_override=None, rate=None):
    out = []
    if rate is None:
        rate = _yesim_page_rate(pp)
    for key in ("standardPlans", "unlimitedPlans"):
        for p in (pp.get(key) or []):
            if heb_override:
                heb = heb_override
            else:
                dests = p.get("destinations") or []
                if not dests:
                    continue
                iso = ((dests[0].get("direction") or {}).get("iso") or "").upper()
                heb = _yesim_iso_to_heb(iso)
                if not heb:
                    continue  # unmapped / deliberately excluded (e.g. PS)
            da = p.get("dataAmount") or {}
            ingb = da.get("inGb")
            try:
                gb = None if (p.get("unlimited") or key == "unlimitedPlans"
                              or ingb in (None, "", "NaN")) else float(ingb)
            except (TypeError, ValueError):
                gb = None
            days = p.get("validityPeriod")
            vp = p.get("vanillaPrice")
            if days is None or vp is None:
                continue
            price_usd = round(vp / 100 * rate, 2)
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
            out.append(core._make_global_plan("yesim", plan_name, price_ils, "USD",
                                         price_usd, gb, days, esim=True, extras=[heb]))
    return out


def _yesim_dedup(plans):
    """Unique plan_name, cheapest wins (deterministic, unlike first-come from as_completed)."""
    best = {}
    for plan in plans:
        k = plan["plan_name"]
        if k not in best or plan["original_price"] < best[k]["original_price"]:
            best[k] = plan
    return list(best.values())


def scrape_yesim_global(_page=None, usd_rate=None):
    """Yesim single-country eSIM plans from the site's embedded __NEXT_DATA__ JSON
    (browser UA required; urllib/empty-UA gets a 202). Enumerates countries from
    `popularCountries` on one page, then fetches each concurrently. Palestine (PS)
    is deliberately excluded."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    seed = _yesim_get_pp("https://yesim.app/country/united-states/")
    if not seed:
        logger.warning("Yesim: could not load seed page for country enumeration")
        return []
    urls = ["https://yesim.app" + (c.get("url") or "")
            for c in (seed.get("popularCountries") or [])
            if (c.get("url") or "").startswith("/country/")]
    pps = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_yesim_get_pp, u): u for u in urls}
        for f in as_completed(futs):
            try:
                pps[futs[f]] = f.result()
            except Exception as exc:
                logger.warning(f"Yesim country {futs[f]}: {exc}")
    rate = _yesim_run_rate(list(pps.values()) + [seed], "global")
    all_plans = _yesim_dedup(
        plan
        for u in sorted(pps) if pps[u]
        for plan in _yesim_plans_from_pp(pps[u], usd_rate, rate=rate)
    )
    logger.info(f"Yesim global: {len(all_plans)} plans from {len(urls)} countries")
    return all_plans


def scrape_yesim_regions(_page=None, usd_rate=None):
    """Yesim regional eSIM plans from /regions/<slug>/ pages (region name forced
    from the slug since per-plan destinations list individual countries)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    pps = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_yesim_get_pp, f"https://yesim.app/regions/{slug}/"): slug
                for slug in _YESIM_REGION_TO_HEBREW}
        for f in as_completed(futs):
            try:
                pps[futs[f]] = f.result()
            except Exception as exc:
                logger.warning(f"Yesim region {futs[f]}: {exc}")
    rate = _yesim_run_rate(list(pps.values()), "regions")
    all_plans = _yesim_dedup(
        plan
        for slug in sorted(pps) if pps[slug]
        for plan in _yesim_plans_from_pp(pps[slug], usd_rate,
                                         heb_override=_YESIM_REGION_TO_HEBREW[slug], rate=rate)
    )
    logger.info(f"Yesim regions: {len(all_plans)} plans from {len(_YESIM_REGION_TO_HEBREW)} regions")
    return all_plans
