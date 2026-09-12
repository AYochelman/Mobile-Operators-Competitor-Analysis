"""esimgenius scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# Destination slugs that esimgenius.ai has but SAILY_SLUG_TO_HEBREW doesn't
# (sub-national islands, UK nations, and naming variants). Values are the
# canonical Hebrew spellings already used in global_plans / db._DEST_NORM.
ESIMGENIUS_SLUG_OVERRIDES = {
    "aland-islands": "איי אולנד",
    "azores": "האיים האזוריים",
    "balearic-islands": "האיים הבלאריים",
    "belarus": "בלארוס",
    "cabo-verde": "קייפ ורדה",
    "canary-islands": "האיים הקנריים",
    "congo": "רפובליקת קונגו",
    "corfu": "קורפו",
    "crete": "כרתים",
    "cyclades-islands": "האיים הקיקלדיים",
    "democratic-republic-congo": "הרפובליקה הדמוקרטית של קונגו",
    "ethiopia": "אתיופיה",
    "ivory-coast": "חוף השנהב",
    "madeira": "מדיירה",
    "rhodes": "רודוס",
    "saint-pierre-miquelon": "סן פייר ומיקלון",
    "sardinia": "סרדיניה",
    "scotland": "סקוטלנד",
    "sicily": "סיציליה",
    "usa": "ארצות הברית",
    "vatican": "ותיקן",
    "wales": "ויילס",
}


ESIMGENIUS_REGION_TO_HEBREW = {
    "europe": "אירופה",
    "asia": "אסיה",
    "africa": "אפריקה",
    "middle-east": "המזרח התיכון",
    "global": "גלובלי",
}


# Non-catalog pages in the esimgenius.ai sitemap; Palestine dropped (GigSky precedent)
_ESIMGENIUS_SKIP_SLUGS = {
    "advisor", "contact", "destinations", "how-it-works", "privacy",
    "refund-policy", "terms", "travel-esim-guide", "palestine",
}


def scrape_esimgenius_global(_page=None, usd_rate=None):
    """Scrape the full eSIM Genius catalog: ~180 country pages + 5 regional/global bundles.

    Pure HTTP — esimgenius.ai is a Next.js app that server-renders each destination
    page with its plans array (label / daysNum / priceCents in USD cents) in the RSC
    stream, so _esimo_extract_packages(array_key="plans") reads it with no Playwright.
    Slugs come from the sitemap (English <loc> entries only). Hebrew destinations
    resolve via SAILY_SLUG_TO_HEBREW (same kebab-case slugs) + ESIMGENIUS_SLUG_OVERRIDES,
    then canonicalize through db._DEST_NORM at scrape time so the raw scraped extras
    match the stored row (a non-canonical value here flaps extras_change every scrape).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from db import _DEST_NORM
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    slugs = set(ESIMGENIUS_REGION_TO_HEBREW)
    try:
        sitemap = core._esimo_fetch("https://esimgenius.ai/sitemap.xml", timeout=30)
        slugs.update(re.findall(r"<loc>https://esimgenius\.ai/([a-z0-9-]+)</loc>", sitemap))
    except Exception as exc:
        logger.warning(f"eSIM Genius sitemap fetch failed ({exc}) — scraping regional pages only")
    slugs -= _ESIMGENIUS_SKIP_SLUGS

    dest_by_slug, unknown_slugs = {}, set()
    for slug in sorted(slugs):
        dest = (ESIMGENIUS_REGION_TO_HEBREW.get(slug)
                or ESIMGENIUS_SLUG_OVERRIDES.get(slug)
                or core.SAILY_SLUG_TO_HEBREW.get(slug))
        if dest:
            dest_by_slug[slug] = _DEST_NORM.get(dest, dest)
        else:
            unknown_slugs.add(slug)

    def fetch_one(slug):
        return core._esimo_extract_packages(
            core._esimo_fetch(f"https://esimgenius.ai/{slug}"), array_key="plans")

    plans, seen_names = [], set()
    empty, failed = 0, 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): s for s in dest_by_slug}
        for fut in as_completed(futures):
            slug = futures[fut]
            dest = dest_by_slug[slug]
            try:
                items = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIM Genius {slug}: {exc}")
                continue
            if not items:
                empty += 1
                continue
            for it in items:
                label = (it.get("label") or "").strip()
                try:
                    days = int(it.get("daysNum") or 0)
                    usd = int(it.get("priceCents") or 0) / 100.0
                except (TypeError, ValueError):
                    continue
                if days <= 0 or usd <= 0:
                    continue
                unlimited = it.get("planType") == "unlimited" or label.lower().startswith("unlim")
                if unlimited:
                    gb, gb_str = None, "ללא הגבלה"  # ללא הגבלה
                else:
                    m = re.match(r"([\d.]+)\s*(GB|MB)", label, re.I)
                    if not m:
                        continue
                    val = float(m.group(1))
                    gb = round(val / 1024, 4) if m.group(2).upper() == "MB" else val
                    gb_str = f"{m.group(1)}{m.group(2).upper()}"
                day_unit = "יום" if days == 1 else "ימים"  # יום / ימים
                plan_name = f"{dest} – {gb_str} – {days} {day_unit}"
                if plan_name in seen_names:      # guard UNIQUE(carrier, plan_name)
                    continue
                seen_names.add(plan_name)
                extras = [dest]
                if unlimited:
                    extras.append("גלישה ללא הגבלה")  # גלישה ללא הגבלה
                plans.append(core._make_global_plan(
                    "esimgenius", plan_name, round(usd * usd_rate, 2), "USD", usd,
                    data_gb=gb, days=days, esim=True, extras=extras,
                ))
    if unknown_slugs:
        logger.warning(
            f"eSIM Genius: skipped unmapped destination slugs {sorted(unknown_slugs)} "
            f"— add them to ESIMGENIUS_SLUG_OVERRIDES"
        )
    logger.info(
        f"eSIM Genius: {len(plans)} plans from {len(dest_by_slug)} pages "
        f"({empty} empty, {failed} failed)"
    )
    return plans
