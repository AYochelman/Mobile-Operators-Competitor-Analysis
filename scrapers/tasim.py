"""tasim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


def scrape_tasim_global(_page=None, usd_rate=None):
    """Scrape Tasim eSIM — USA voice+data plans (USD pricing).

    Pure HTTP, no Playwright: the homepage purchase form reads
    https://www.tasim.us/api/plans?type=one_time — the same endpoint is the
    source of truth here. one_time = the packages publicly sold on the site
    (15GB / 50GB as of 2026-06); the API also returns 'subscription' plans
    that have no public page, so the type filter excludes them. The one-time
    setup fee (setupCost) is surfaced as an extra, not added to the price —
    the site advertises the package price.

    Plan-name format is kept identical to the legacy single-plan scraper
    ("ארצות הברית – 15GB + שיחות ללא הגבלה – 30 ימים") so the existing row
    keeps its price history.
    """
    import requests
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    try:
        r = requests.get(
            "https://www.tasim.us/api/plans",
            params={"type": "one_time"},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
            timeout=30,
        )
        r.raise_for_status()
        items = (r.json() or {}).get("plans") or []
    except Exception as exc:
        logger.warning(f"Tasim scraper failed: {exc}")
        return []

    country_heb = "ארצות הברית"
    plans = []
    for item in items:
        try:
            price_usd = float(item.get("price"))
            data_gb = float(item.get("gb"))
            days = int(item.get("days"))
            setup_usd = float(item.get("setupCost") or 0)
        except (TypeError, ValueError):
            continue
        if price_usd <= 0 or data_gb <= 0 or days <= 0:
            continue
        price_ils = round(price_usd * usd_rate, 2)
        gb_str = f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb}GB"
        plan_name = f"{country_heb} – {gb_str} + שיחות ללא הגבלה – {days} ימים"
        extras = [
            country_heb,
            'שיחות ללא הגבלה בארה"ב',
            "שיחות לישראל ללא הגבלה",
            "הודעות SMS ללא הגבלה",
            f"אינטרנט {gb_str} (לאחר מכן מהירות יורדת)",
            "רשת T-Mobile (כיסוי מקסימלי)",
            "הפעלה מידית — אין צורך בכרטיס פיזי",
        ]
        if setup_usd > 0:
            setup_str = f"{int(setup_usd)}" if setup_usd == int(setup_usd) else f"{setup_usd}"
            extras.append(f"דמי הקמה חד-פעמיים ${setup_str}")
        plans.append(core._make_global_plan(
            "tasim", plan_name, price_ils, "USD", price_usd,
            data_gb=data_gb, days=days, esim=True, extras=extras,
        ))
    logger.info(f"Tasim: {len(plans)} plans")
    return plans
