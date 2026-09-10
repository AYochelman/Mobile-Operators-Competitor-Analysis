"""
Playwright scrapers for 5 Israeli cellular carriers.
Uses sync API. All scrape_* functions take a Playwright Page object.
Returns list of plan dicts:
  {"carrier": str, "plan_name": str, "price": int|None,
   "data_gb": int|None, "minutes": str, "extras": list[str]}
"""
import sys as _sys
if __name__ == "__main__":
    # `python scraper.py` makes this module __main__; the scrapers/ sub-modules do
    # `import scraper as core`, which would otherwise execute this file a second time.
    _sys.modules.setdefault("scraper", _sys.modules[__name__])
from playwright.sync_api import sync_playwright
import re
import logging
import os
import json as _json
import urllib.request
import asyncio
from datetime import datetime, timezone
from html import unescape as _html_unescape  # aliased: locals named `html` shadow the module

logger = logging.getLogger(__name__)


def _ensure_event_loop():
    """Ensure an asyncio event loop exists for the current thread.
    Required by Playwright when called from Flask request handlers or APScheduler threads."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _run_parallel_scraper(name, fn):
    """Thread worker for scrape_all_global: ensure asyncio loop, run fn(), return (name, results).
    fn must be a zero-argument callable that returns a list of plan dicts."""
    _ensure_event_loop()
    try:
        result = fn()
        if not result:
            logger.warning(
                f"{name}: returned 0 plans — possible bot-block or selector change. Skipping."
            )
            return name, []
        logger.info(f"{name}: {len(result)} global plans")
        return name, result
    except Exception as e:
        logger.error(f"{name} failed: {e}", exc_info=True)
        return name, []


def _parse_price(text):
    """Extract price from string like '₪49', '34.9', '39.90'. Returns float or None (no rounding)."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    val = float(match.group(1))
    # Return int if whole number, float otherwise
    return int(val) if val == int(val) else val


def _parse_minutes(text):
    """Extract minutes count from string like '7,000 דקות שיחה/SMS בארץ'.
    Returns int or None (None = not included / no calls)."""
    if not text:
        return None
    text_clean = text.replace(",", "")
    if any(w in text for w in ["ללא הגבלה", "unlimit", "∞"]):
        return -1  # -1 = unlimited
    match = re.search(r"(\d+)", text_clean)
    return int(match.group(1)) if match else None


def _parse_gb(text):
    """Extract GB from string. Returns None if unlimited, float for MB (<1), int for GB."""
    if not text:
        return None
    text_clean = text.replace(",", "")  # handle 2,500 → 2500
    text_lower = text_clean.lower().strip()
    if any(w in text_lower for w in ["ללא", "unlimit", "∞"]):
        return None
    # MB values → store as fraction of GB (e.g. 100MB → 0.098)
    mb_match = re.search(r"(\d+(?:\.\d+)?)\s*mb", text_lower)
    if mb_match:
        return round(float(mb_match.group(1)) / 1024, 4)
    # GB values
    match = re.search(r"(\d+(?:\.\d+)?)", text_lower)
    if not match:
        return None
    val = float(match.group(1))
    return int(val) if val == int(val) else val


def _parse_days(text):
    """Extract number of days from strings like '4 ימים', 'חבילה ל-30 ימים', 'למשך 8 ימים'."""
    if not text:
        return None
    text_clean = text.replace(",", "").replace("-", " ")
    match = re.search(r"(\d+)\s*(?:יום|ימים)", text_clean)
    return int(match.group(1)) if match else None


def _parse_sms(text):
    """Extract SMS count from string like '300 SMS', '100 הודעות'. Returns int or None."""
    if not text:
        return None
    text_clean = text.replace(",", "")
    if any(w in text for w in ["ללא הגבלה", "unlimit", "∞"]):
        return -1
    match = re.search(r"(\d+)", text_clean)
    return int(match.group(1)) if match else None


def scrape_all():
    """Scrape all carriers. Returns flat list of plan dicts."""
    _ensure_event_loop()
    plans = []

    # Phase 1: scrapers that open their own sync_playwright session — must run OUTSIDE
    # any outer sync_playwright context to avoid nested asyncio event-loop conflict.
    for fn in [scrape_xphone, scrape_wecom, scrape_019, scrape_neptucom, scrape_golan, scrape_rami_levy]:
        try:
            result = fn()
            if not result:
                logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping to avoid false 'removed' alerts.")
            else:
                logger.info(f"{fn.__name__}: {len(result)} plans")
                plans.extend(result)
        except Exception as e:
            logger.error(f"{fn.__name__} failed: {e}", exc_info=True)

    # Phase 2: scrapers that share a single Playwright session
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        for fn in [scrape_partner, scrape_pelephone, scrape_hotmobile, scrape_cellcom]:
            try:
                result = fn(page)
                if not result:
                    logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping to avoid false 'removed' alerts.")
                else:
                    logger.info(f"{fn.__name__}: {len(result)} plans")
                    plans.extend(result)
            except Exception as e:
                logger.error(f"{fn.__name__} failed: {e}", exc_info=True)
        browser.close()

    return plans


# ── Abroad / Roaming scrapers ──────────────────────────────────────────────


# ── Global eSIM scrapers ───────────────────────────────────────────────────

def _get_usd_to_ils():
    """Fetch live USD→ILS exchange rate. Returns float (fallback: 3.7)."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(
            "https://api.exchangerate.host/latest?base=USD&symbols=ILS", timeout=8
        ) as r:
            data = _json.loads(r.read())
            rate = data["rates"]["ILS"]
            logger.info(f"USD→ILS rate: {rate}")
            return float(rate)
    except Exception:
        try:
            import urllib.request, json as _json
            with urllib.request.urlopen(
                "https://open.er-api.com/v6/latest/USD", timeout=8
            ) as r:
                data = _json.loads(r.read())
                rate = data["rates"]["ILS"]
                logger.info(f"USD→ILS rate (fallback): {rate}")
                return float(rate)
        except Exception as e:
            logger.warning(f"Exchange rate fetch failed: {e}. Using 3.7")
            return 3.7


def _get_eur_to_ils():
    """Fetch live EUR→ILS exchange rate. Returns float (fallback: 4.0)."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/EUR", timeout=8
        ) as r:
            data = _json.loads(r.read())
            rate = data["rates"]["ILS"]
            logger.info(f"EUR→ILS rate: {rate}")
            return float(rate)
    except Exception as e:
        logger.warning(f"EUR rate fetch failed: {e}. Using 4.0")
        return 4.0


def _get_gbp_to_ils():
    """Fetch live GBP\u2192ILS exchange rate. Returns float (fallback: 4.8)."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/GBP", timeout=8
        ) as r:
            data = _json.loads(r.read())
            rate = data["rates"]["ILS"]
            logger.info(f"GBP\u2192ILS rate: {rate}")
            return float(rate)
    except Exception as e:
        logger.warning(f"GBP rate fetch failed: {e}. Using 4.8")
        return 4.8


def _make_global_plan(carrier, name, price_ils, currency, original_price,
                      data_gb, days, minutes=None, sms=None, esim=True, extras=None):
    # Scraped titles/JSON may carry HTML entities (&amp; \u2192 &) \u2014 unescape before any formatting
    name = _html_unescape(name)
    if extras:
        extras = [_html_unescape(e) if isinstance(e, str) else e for e in extras]
        # Canonicalize extras[0] (destination) at CREATION, mirroring the DB
        # write path: change detection compares raw scraped extras against the
        # _norm_extras-stored row, so a non-canonical dest here flapped
        # extras_change on every scrape (~1,300 phantom changes/day across 20
        # providers as of 2026-07-14). plan_name is deliberately untouched.
        from db import _norm_extras
        extras = _norm_extras(extras)
    # Insert RLM (\u200f) before digits after separators to fix BiDi rendering in RTL tables
    import re as _re
    name = _re.sub(r'( [\u2013-] )(\d)', lambda m: m.group(1) + '\u200f' + m.group(2), name)
    return {
        "carrier": carrier,
        "plan_name": name,
        "price": round(price_ils, 2) if price_ils is not None else None,
        "currency": currency,
        "original_price": original_price,
        "days": days,
        "data_gb": data_gb,
        "minutes": minutes,
        "sms": sms,
        "esim": esim,
        "extras": extras or [],
    }


# ── SimTLV full eSIM catalog (simtlv.co.il/esim/) ─────────────────────────


def _woo_store_fetch(products_url, label="Woo"):
    """Page through a WooCommerce Store API `products` endpoint; return raw dicts.

    Each page is retried 3× with backoff (these endpoints intermittently take
    >30s). A page that still fails is skipped — a partial catalog is safe
    because save_global_plans never deletes stale rows and new/removed
    events are dropped for global carriers. Shared by SimTLV + Terminal eSIM
    (both run the same WooCommerce Store API).
    """
    import requests
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }
    products, page_num, total_pages, failed_pages = [], 1, 1, 0
    while page_num <= total_pages:
        resp = None
        for attempt in range(3):
            try:
                r = requests.get(
                    products_url,
                    params={"per_page": 100, "page": page_num},
                    headers=headers, timeout=60,
                )
                if r.status_code == 200:
                    resp = r
                    break
                logger.warning(f"{label} catalog page {page_num}: HTTP {r.status_code}")
            except requests.RequestException as exc:
                logger.warning(f"{label} catalog page {page_num} attempt {attempt + 1}: {type(exc).__name__}")
            time.sleep(2 * (attempt + 1))
        if resp is None:
            failed_pages += 1
            page_num += 1
            continue
        total_pages = int(resp.headers.get("X-WP-TotalPages") or page_num)
        products.extend(resp.json())
        page_num += 1
    if failed_pages:
        logger.warning(f"{label} catalog: {failed_pages} pages failed — partial catalog")
    return products


# ── Terminal eSIM (terminalesim.com) ─────────────────


# ── Yesim (own platform; plans embedded as Next.js __NEXT_DATA__ JSON) ───────


# ── Nomad (nomadesim.com; plans embedded as `vike_pageContext` JSON) ─────────


# ── Ubigi (Transatel/NTT; open WooCommerce Store REST API) ───────────────────


# ── aloSIM (alosim.com; WordPress; plan data in destination-page HTML) ───────


# ── Sparks Travel eSIM ──────────────────────────────────────────────────


# ── Orbit Mobile ──────────────────────────────────────────────────────────


# ── GoMoWorld eSIM ──────────────────────────────────────────────────────────


# ── Tasim eSIM (USA only) ────────────────────────────────────────────────────


# ── GigSky eSIM ──────────────────────────────────────────────────────────────


# ── eSIM Genius (esimgenius.ai) ──────────────────────────────────────────────


# ── Nisim eSIM (nisim-esim.co.il) ────────────────────────────────────────────


# ── eSIM Max (esimax.io) ─────────────────────────────────────────────────────


# ── VenterraSIM (venterrasim.com) ────────────────────────────────────────────


# ── Simzol / סים זול (simzol.co.il) ──────────────────────────────────────────


# ── Maya Mobile eSIM ─────────────────────────────────────────────────────────


# ── Jetpack ───────────────────────────────────────────────────────────


# ── Breeze eSIM ────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ByteSim
# ─────────────────────────────────────────────────────────────────────────────


# ── 7G eSIM ───────────────────────────────────────────────────────────────────


# ── Best Connect ──────────────────────────────────────────────────────────────


# ── eSIM Plus ─────────────────────────────────────────────────────────────────


# ─── Besim (https://besim.co.il) ────────────────────────────────────────
# Israeli eSIM reseller. ~130 single-country pages + 19 regional/global bundles.
# Every product page renders identical 3-line plan blocks: "<X>GB / תוקף N ימים / $price".


# ── BNESIM (bnesim.com) ──────────────────────────────────────────────────────


def scrape_all_global():
    """Scrape global eSIM packages from all providers. Returns flat list of plan dicts.

    Self-contained scrapers (own browser / HTTP / REST) run in parallel threads
    (max 4 concurrent) while shared-page scrapers run sequentially in the main thread.
    Both groups execute concurrently for ~12 min total vs ~35 min sequential.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    _ensure_event_loop()
    usd_rate = _get_usd_to_ils()
    eur_rate = _get_eur_to_ils()
    gbp_rate = _get_gbp_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

    # ── Sequential jobs: share one Playwright browser page ────────────────
    sequential_jobs = [
        ("scrape_tuki_global",         lambda pg: scrape_tuki_global(pg, usd_rate)),
        ("scrape_tuki_regions",        lambda pg: scrape_tuki_regions(pg, usd_rate)),
        ("scrape_tuki_local",          lambda pg: scrape_tuki_local(pg, usd_rate)),
        ("scrape_airalo_global",       lambda pg: scrape_airalo_global(pg, usd_rate)),
        ("scrape_airalo_local",        lambda pg: scrape_airalo_local(pg, usd_rate)),
        ("scrape_airalo_regional",     lambda pg: scrape_airalo_regional(pg, usd_rate)),
        ("scrape_pelephone_globalsim", scrape_pelephone_globalsim),
        ("scrape_simtlv_global",       scrape_simtlv_global),
        ("scrape_world8_global",       scrape_world8_global),
    ]

    # ── Parallel jobs: each creates its own browser / HTTP / REST ─────────
    parallel_jobs = [
        ("scrape_xphone_global",       lambda: scrape_xphone_global()),
        ("scrape_saily_global",        lambda: scrape_saily_global(usd_rate=usd_rate)),
        ("scrape_saily_regions",       lambda: scrape_saily_regions(usd_rate=usd_rate)),
        ("scrape_yesim_global",        lambda: scrape_yesim_global(usd_rate=usd_rate)),
        ("scrape_yesim_regions",       lambda: scrape_yesim_regions(usd_rate=usd_rate)),
        ("scrape_nomad_global",        lambda: scrape_nomad_global(usd_rate=usd_rate)),
        ("scrape_ubigi_global",        lambda: scrape_ubigi_global(usd_rate=usd_rate)),
        ("scrape_alosim_global",       lambda: scrape_alosim_global(usd_rate=usd_rate)),
        ("scrape_esimio_destinations", lambda: scrape_esimio_destinations(usd_rate=usd_rate)),
        ("scrape_esimio_regions",      lambda: scrape_esimio_regions(usd_rate=usd_rate)),
        ("scrape_esimo_global",        lambda: scrape_esimo_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_simtlv_esim",         lambda: scrape_simtlv_esim()),  # pure HTTP, no Playwright
        ("scrape_terminalesim",        lambda: scrape_terminalesim(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_holafly_global",      lambda: scrape_holafly_global(usd_rate=usd_rate)),
        ("scrape_holafly_regions",     lambda: scrape_holafly_regions(usd_rate=usd_rate)),
        ("scrape_sparks_global",       lambda: scrape_sparks_global(usd_rate=usd_rate)),
        ("scrape_voye_global",         lambda: scrape_voye_global(usd_rate=usd_rate)),
        ("scrape_orbit_global",        lambda: scrape_orbit_global(usd_rate=usd_rate)),
        ("scrape_travelsim",           scrape_travelsim),
        ("scrape_gomoworld_global",    lambda: scrape_gomoworld_global(gbp_rate=gbp_rate)),
        ("scrape_tasim_global",        lambda: scrape_tasim_global(usd_rate=usd_rate)),
        ("scrape_gigsky_global",       lambda: scrape_gigsky_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_esimgenius_global",   lambda: scrape_esimgenius_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_nisim_global",        lambda: scrape_nisim_global()),  # pure HTTP, ILS, no Playwright
        ("scrape_esimax_global",       lambda: scrape_esimax_global(usd_rate=usd_rate)),  # pure HTTP, no Playwright
        ("scrape_venterrasim_global",  lambda: scrape_venterrasim_global()),  # pure HTTP, ILS, no Playwright
        ("scrape_simzol_global",       lambda: scrape_simzol_global()),  # pure HTTP, ILS, no Playwright
        ("scrape_maya_global",         lambda: scrape_maya_global(usd_rate=usd_rate)),
        ("scrape_bcengi_global",       lambda: scrape_bcengi_global(usd_rate=usd_rate)),
        ("scrape_esim70_global",        lambda: scrape_esim70_global(eur_rate=eur_rate)),
        ("scrape_bnesim_global",        lambda: scrape_bnesim_global(eur_rate=eur_rate)),
        ("scrape_jetpack_global",       lambda: scrape_jetpack_global(usd_rate=usd_rate)),
        ("scrape_breez_global",         lambda: scrape_breez_global(usd_rate=usd_rate)),
        ("scrape_bytesim_global",       lambda: scrape_bytesim_global(usd_rate=usd_rate)),
        ("scrape_bytesim_regions",      lambda: scrape_bytesim_regions(usd_rate=usd_rate)),
        ("scrape_besim_global",         lambda: scrape_besim_global(usd_rate=usd_rate)),
        ("scrape_besim_regions",        lambda: scrape_besim_regions(usd_rate=usd_rate)),
        ("scrape_seven_g_global",       lambda: scrape_seven_g_global(usd_rate=usd_rate)),
        ("scrape_bestconnect_global",   lambda: scrape_bestconnect_global(usd_rate=usd_rate)),
        ("scrape_esimplus_global",      lambda: scrape_esimplus_global(usd_rate=usd_rate)),
    ]

    plans = []

    # Submit parallel jobs immediately so they start while sequential jobs run
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_run_parallel_scraper, name, fn): name
            for name, fn in parallel_jobs
        }

        # Run sequential jobs in main thread (shares browser with no thread contention)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=ua)
            for name, fn in sequential_jobs:
                try:
                    result = fn(page)
                    if not result:
                        logger.warning(
                            f"{name}: returned 0 plans — possible bot-block or selector change. Skipping."
                        )
                    else:
                        logger.info(f"{name}: {len(result)} global plans")
                        plans.extend(result)
                except Exception as e:
                    logger.error(f"{name} failed: {e}", exc_info=True)
            browser.close()

        # Collect parallel results — 15-minute hard cap per scraper run
        try:
            for future in as_completed(futures, timeout=900):
                _, result = future.result()   # _run_parallel_scraper never raises
                plans.extend(result)
        except TimeoutError:
            for future, name in futures.items():
                if not future.done():
                    logger.error(f"{name}: timed out after 900s, skipping")

    return plans


# ── Content Services Scraper ───────────────────────────────────────────────


def scrape_all_abroad():
    """Scrape abroad packages from all carriers. Returns flat list of plan dicts."""
    _ensure_event_loop()
    plans = []

    # Phase 1: scrapers that open their own sync_playwright session — must run OUTSIDE
    # any outer sync_playwright context to avoid nested asyncio event-loop conflict.
    for fn in [scrape_wecom_abroad, scrape_019_abroad, scrape_golan_abroad, scrape_rami_levy_abroad]:
        try:
            result = fn()
            if not result:
                logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping.")
            else:
                logger.info(f"{fn.__name__}: {len(result)} abroad plans")
                plans.extend(result)
        except Exception as e:
            logger.error(f"{fn.__name__} failed: {e}", exc_info=True)

    # Phase 2: scrapers that share a single Playwright session
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        for fn in [scrape_partner_abroad, scrape_pelephone_abroad,
                   scrape_hotmobile_abroad, scrape_cellcom_abroad]:
            try:
                result = fn(page)
                if not result:
                    logger.warning(f"{fn.__name__}: returned 0 plans — possible bot-block or selector change. Skipping.")
                else:
                    logger.info(f"{fn.__name__}: {len(result)} abroad plans")
                    plans.extend(result)
            except Exception as e:
                logger.error(f"{fn.__name__} failed: {e}", exc_info=True)
        browser.close()

    return plans


# ── CARRIER HOMEPAGE BANNER SCREENSHOTS ──────────────────────────────────────


# ── Global eSIM provider homepage banners ───────────────────────────────────


# ── sub-modules (scrapers/) - extracted 2026-09, see scripts/split_monolith.py ──
# Imported here (after every helper above is defined) so they can late-bind
# `core.<name>` back to this module; their public + private names are re-exported
# so `scraper.<name>` keeps working for tests, scripts and the scheduler.
from scrapers.xphone import (  # noqa: E402,F401
    _XPHONE_UA,
    scrape_xphone,
    scrape_xphone_abroad,
    scrape_xphone_global,
)
from scrapers.wecom import (  # noqa: E402,F401
    _WECOM_UA,
    _WECOM_FAIR_USE_GB,
    _WECOM_OVERSEAS_RATES_URL,
    _wecom_fetch_html,
    _wecom_text_lines,
    _wecom_tier_cards,
    _wecom_card_name,
    _wecom_card_price,
    _WECOM_CARD_NOISE,
    _wecom_popup_info,
    _wecom_card_extras,
    scrape_wecom,
    scrape_wecom_abroad,
)
from scrapers.neptucom import (  # noqa: E402,F401
    scrape_neptucom,
)
from scrapers.golan import (  # noqa: E402,F401
    _golan_num,
    _golan_gb_from_text,
    _golan_gb_label,
    _golan_period_to_days,
    _GOLAN_DOMESTIC_JS,
    _GOLAN_OVERSEAS_JS,
    _build_golan_domestic,
    _GOLAN_GENERIC_SUPERL,
    _build_golan_abroad,
    _golan_open,
    _GOLAN_OFFERS_URL,
    _GOLAN_OVERSEAS_URL,
    _GOLAN_UA,
    scrape_golan,
    scrape_golan_abroad,
)
from scrapers.rami_levy import (  # noqa: E402,F401
    _parse_rami_levy_body,
    _parse_rami_levy_abroad_body,
    _enrich_rami_levy_abroad_info,
    scrape_rami_levy_abroad,
    scrape_rami_levy,
)
from scrapers.partner import (  # noqa: E402,F401
    scrape_partner,
    scrape_partner_abroad,
)
from scrapers.pelephone import (  # noqa: E402,F401
    scrape_pelephone,
    _PELE_ABROAD_TERMS_RE,
    _PELE_ABROAD_TERMS_OVERRIDES,
    scrape_pelephone_abroad,
)
from scrapers.hotmobile import (  # noqa: E402,F401
    scrape_hotmobile,
    scrape_hotmobile_abroad,
)
from scrapers.cellcom import (  # noqa: E402,F401
    _cellcom_extract_terms_urls,
    _fetch_cellcom_terms_urls,
    scrape_cellcom,
    _cellcom_fetch_abroad_policies,
    scrape_cellcom_abroad,
    _cellcom_hub_price,
    _cellcom_faq_esim_price,
)
from scrapers.mobile019 import (  # noqa: E402,F401
    scrape_019,
    _MOBILE019_VOLTE_NOTE,
    scrape_019_abroad,
)
from scrapers.tuki import (  # noqa: E402,F401
    scrape_tuki_global,
    TUKI_REGIONS,
    scrape_tuki_regions,
    scrape_tuki_local,
)
from scrapers.airalo import (  # noqa: E402,F401
    scrape_airalo_global,
    AIRALO_SLUG_TO_HEBREW,
    AIRALO_REGION_TO_HEBREW,
    scrape_airalo_local,
    scrape_airalo_regional,
)
from scrapers.pelephone_globalsim import (  # noqa: E402,F401
    scrape_pelephone_globalsim,
)
from scrapers.esimo import (  # noqa: E402,F401
    ESIMO_CODE_TO_HEBREW,
    ESIMO_REGION_TO_HEBREW,
    _ESIMO_REGION_SLUGS,
    _ESIMO_UA,
    _esimo_fetch,
    _esimo_extract_packages,
    scrape_esimo_global,
)
from scrapers.simtlv import (  # noqa: E402,F401
    scrape_simtlv_global,
    SIMTLV_DEST_FIX,
    _SIMTLV_RX_UNLIMITED,
    _SIMTLV_RX_EUROPE,
    _SIMTLV_RX_EUROPE_YR,
    _SIMTLV_RX_GLOBAL_N,
    _SIMTLV_RX_EUR_PKG,
    _SIMTLV_RX_GLOB_PKG,
    _SIMTLV_RX_LOCAL,
    _simtlv_duration,
    _simtlv_classify,
    _simtlv_fetch_catalog,
    scrape_simtlv_esim,
)
from scrapers.terminalesim import (  # noqa: E402,F401
    TERMINAL_CODE_TO_HEBREW,
    TERMINAL_REGION_BASE,
    TERMINAL_REGION_FULL,
    _terminal_resolve_dest,
    _terminal_parse_pkg,
    scrape_terminalesim,
)
from scrapers.world8 import (  # noqa: E402,F401
    scrape_world8_global,
)
from scrapers.banners import (  # noqa: E402,F401
    scrape_carrier_news,
    _BANNER_ERROR_INDICATORS,
    _is_error_page,
    _MIN_BANNER_FILE_BYTES,
    _POPUP_CLOSE_SELECTORS,
    _POPUP_HIDE_JS,
    _dismiss_popups,
    _GLOBAL_POPUP_DISMISS_JS,
    _dismiss_global_popups,
    _PERSISTENT_CONSENT_HIDER_JS,
    CARRIER_HOMEPAGE_URLS,
    _STEALTH_UA,
    _banner_019_stealth,
    _banner_xphone_stealth,
    scrape_carrier_banners,
    CARRIER_STORE_URLS,
    scrape_carrier_store_banners,
    GLOBAL_BANNER_URLS,
    _GLOBAL_BANNER_STATE_FILE,
    _BANNER_CHANGE_THRESHOLD,
    _banner_ahash,
    _ahash_distance,
    _load_global_banner_state,
    _save_global_banner_state,
    scrape_global_provider_banners,
)
from scrapers.saily import (  # noqa: E402,F401
    SAILY_SLUG_TO_HEBREW,
    SAILY_ISO_TO_HEBREW,
    SAILY_API_REGION_TO_HEBREW,
    _SAILY_API_URL,
    _SAILY_API_HEADERS,
    _SAILY_API_CACHE,
    _fetch_saily_api,
    _saily_api_item_to_plan,
    scrape_saily_global,
    scrape_saily_regions,
)
from scrapers.esimio import (  # noqa: E402,F401
    ESIMIO_SLUG_TO_HEBREW,
    _esimio_packages_to_plans,
    scrape_esimio_destinations,
    ESIMIO_REGIONS,
    scrape_esimio_regions,
)
from scrapers.holafly import (  # noqa: E402,F401
    HOLAFLY_SLUG_TO_HEBREW,
    _HOLAFLY_KEY_DAYS,
    scrape_holafly_global,
    HOLAFLY_REGIONS,
    _HOLAFLY_NON_SHOPIFY_REGIONS,
    scrape_holafly_regions,
)
from scrapers.yesim import (  # noqa: E402,F401
    _YESIM_EXTRA_ISO_TO_HEBREW,
    _YESIM_REGION_TO_HEBREW,
    _YESIM_UA,
    _yesim_iso_to_heb,
    _yesim_get_pp,
    _yesim_plans_from_pp,
    scrape_yesim_global,
    scrape_yesim_regions,
)
from scrapers.nomad import (  # noqa: E402,F401
    _NOMAD_REGION_SLUG_TO_HEBREW,
    _nomad_find_plans,
    _nomad_get_plans,
    scrape_nomad_global,
)
from scrapers.ubigi import (  # noqa: E402,F401
    _UBIGI_API,
    _UBIGI_ALIAS,
    _UBIGI_EXTRA_HEBREW,
    _ubigi_norm,
    _ubigi_resolve,
    scrape_ubigi_global,
)
from scrapers.alosim import (  # noqa: E402,F401
    _ALOSIM_EXTRA,
    _alosim_resolve,
    _alosim_page_plans,
    scrape_alosim_global,
)
from scrapers.sparks import (  # noqa: E402,F401
    SPARKS_REGIONS,
    SPARKS_COUNTRY_TO_HEBREW_EXTRA,
    scrape_sparks_global,
)
from scrapers.voye import (  # noqa: E402,F401
    VOYE_REGION_MAP,
    scrape_voye_global,
)
from scrapers.orbit import (  # noqa: E402,F401
    ORBIT_NAME_TO_HEBREW,
    ORBIT_ZONE_TO_HEBREW,
    scrape_orbit_global,
)
from scrapers.travelsim import (  # noqa: E402,F401
    scrape_travelsim,
)
from scrapers.gomoworld import (  # noqa: E402,F401
    GOMOWORLD_SLUG_TO_HEBREW,
    _GOMO_SYMBOL_CCY,
    _parse_gomoworld_plans,
    scrape_gomoworld_global,
)
from scrapers.tasim import (  # noqa: E402,F401
    scrape_tasim_global,
)
from scrapers.gigsky import (  # noqa: E402,F401
    GIGSKY_PLAN_BUNDLE_URL,
    GIGSKY_NAME_TO_CODE,
    GIGSKY_COUNTRY_SKIP,
    GIGSKY_CODE_EXTRA,
    GIGSKY_REGION_TO_HEBREW,
    GIGSKY_WORLD_TO_HEBREW,
    _gigsky_dest_hebrew,
    _gigsky_gb_str,
    scrape_gigsky_global,
)
from scrapers.esimgenius import (  # noqa: E402,F401
    ESIMGENIUS_SLUG_OVERRIDES,
    ESIMGENIUS_REGION_TO_HEBREW,
    _ESIMGENIUS_SKIP_SLUGS,
    scrape_esimgenius_global,
)
from scrapers.nisim import (  # noqa: E402,F401
    NISIM_NAME_FIX,
    NISIM_REGION_NAMES,
    _NISIM_SKIP_CATS,
    _nisim_fetch_json,
    scrape_nisim_global,
)
from scrapers.esimax import (  # noqa: E402,F401
    ESIMAX_NAME_FIX,
    ESIMAX_REGION_NAMES,
    scrape_esimax_global,
)
from scrapers.simzol import (  # noqa: E402,F401
    SIMZOL_SITEMAP,
    SIMZOL_PRODUCTS,
    _SIMZOL_ADDON_RE,
    _SIMZOL_TAG_RE,
    _SIMZOL_ESIM_CAT_RE,
    _simzol_page_text,
    _simzol_tiers,
    scrape_simzol_global,
)
from scrapers.maya import (  # noqa: E402,F401
    MAYA_SLUG_TO_HEBREW,
    scrape_maya_global,
)
from scrapers.bcengi import (  # noqa: E402,F401
    BCENGI_EN_TO_HEB,
    BCENGI_BENEFITS,
    _parse_bcengi_body,
    scrape_bcengi_global,
)
from scrapers.esim70 import (  # noqa: E402,F401
    ESIM70_ISO2_TO_HEBREW,
    ESIM70_REGION_BASE_TO_HEBREW,
    scrape_esim70_global,
)
from scrapers.jetpack import (  # noqa: E402,F401
    JETPACK_SLUGS,
    JETPACK_REGION_SLUG_TO_HEBREW,
    JETPACK_EXTRA_COUNTRY_HEBREW,
    _jetpack_country_heb,
    scrape_jetpack_global,
)
from scrapers.breez import (  # noqa: E402,F401
    BREEZ_EN_TO_HEBREW,
    BREEZ_EN_TO_HANDLE,
    BREEZ_HEB_TO_HANDLE,
    scrape_breez_global,
)
from scrapers.seven_g import (  # noqa: E402,F401
    SEVEN_G_DESTINATIONS,
    _SEVEN_G_SLUG_OVERRIDES,
    _SEVEN_G_REGION_HEB,
    SEVEN_G_REGION_SLUG_MAP,
    _seven_g_slugify,
    _parse_seven_g_page,
    _fetch_seven_g_destination,
    scrape_seven_g_global,
)
from scrapers.bestconnect import (  # noqa: E402,F401
    _BC_API_HEADERS,
    _BC_REGIONAL_HEBREW,
    _fetch_bestconnect_catalog,
    scrape_bestconnect_global,
)
from scrapers.esimplus import (  # noqa: E402,F401
    _ESIMPLUS_TO_SAILY,
    ESIMPLUS_COUNTRY_SLUGS,
    _ESIMPLUS_REGION_HEB,
    _ESIMPLUS_PLAN_PREFIX,
    _fetch_esimplus_country,
    scrape_esimplus_global,
)
from scrapers.besim import (  # noqa: E402,F401
    BESIM_SLUG_TO_HEBREW,
    BESIM_REGIONAL_BUNDLES,
    _BESIM_UA,
    _BESIM_GB_RE,
    _BESIM_MB_RE,
    _BESIM_DAYS_RE,
    _BESIM_PRICE_RE,
    _parse_besim_plans,
    _besim_format_data,
    _scrape_besim_batch,
    _scrape_besim_product_list,
    scrape_besim_global,
    scrape_besim_regions,
)
from scrapers.bnesim import (  # noqa: E402,F401
    _BNESIM_UA,
    BNESIM_REGION_TO_HEBREW,
    BNESIM_NAME_TO_HEBREW,
    _bnesim_parse_offers,
    scrape_bnesim_global,
)
from scrapers.content import (  # noqa: E402,F401
    CONTENT_SERVICES,
    _extract_content_price,
    scrape_all_content,
)
from scrapers.venterrasim import (  # noqa: E402,F401
    VENTERRA_CODE_TO_HEBREW,
    VENTERRA_REGION_NAMES,
    _VENTERRA_SPEC_RE,
    scrape_venterrasim_global,
)
from scrapers.bytesim import (  # noqa: E402,F401
    BYTESIM_HANDLE_TO_HEBREW,
    BYTESIM_ZONE_HANDLES,
    _parse_bytesim_option1,
    _BYTESIM_JS,
    _BYTESIM_UA,
    _scrape_bytesim_batch,
    _scrape_bytesim_product_list,
    scrape_bytesim_global,
    scrape_bytesim_regions,
)
