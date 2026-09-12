"""voye scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


VOYE_REGION_MAP = {
    "asia": "\u05d0\u05e1\u05d9\u05d4",
    "europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "latin-america": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "middle-east": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "north-america": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
}


def scrape_voye_global(_page=None, usd_rate=None):
    """Scrape VOYE global eSIM plans via WooCommerce Store API."""
    import urllib.request, json as _json, html as _html

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    all_plans = []
    page_num = 1
    while True:
        url = f"https://voyeglobal.com/wp-json/wc/store/v1/products?per_page=100&page={page_num}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                products = _json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"VOYE page {page_num}: {e}")
            break

        if not products:
            break

        for prod in products:
            name = _html.unescape(prod.get("name", ""))
            # Price in cents
            price_raw = prod.get("prices", {}).get("price")
            if not price_raw:
                continue
            try:
                price_usd = int(price_raw) / 100
                if price_usd <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            cats_list = [c.get("slug", "") for c in prod.get("categories", [])]
            # Skip "zombie" products with no categories — these are old products VOYE
            # removed from the public site but the WooCommerce Store API still exposes.
            # They cause stale duplicates (e.g. an old "Europe 30 days 10GB @ $25" overwrites
            # the current "Europe 30 days 10GB @ $19" via shared plan_name).
            if not cats_list:
                continue

            # Parse data — GB (incl. decimals like 1.5GB), MB (e.g. 500MB → fraction of GB),
            # or "Unlimited" (3GB/day high-speed + unlimited throttled)
            gb_match = re.search(r"(\d+(?:\.\d+)?)\s*GB", name, re.IGNORECASE)
            mb_match = re.search(r"(\d+(?:\.\d+)?)\s*MB(?![/a-z])", name, re.IGNORECASE)
            is_unlimited = "unlimited" in name.lower()
            if gb_match:
                gb_val = float(gb_match.group(1))
                data_gb = int(gb_val) if gb_val == int(gb_val) else gb_val
            elif mb_match:
                # CLAUDE.md convention: MB stored as fraction of GB (X / 1024)
                data_gb = round(float(mb_match.group(1)) / 1024, 4)
            elif is_unlimited:
                data_gb = None  # will be stored as unlimited
            else:
                continue  # skip plans without GB info

            # Parse days
            days_match = re.search(r"(\d+)\s*Days?", name, re.IGNORECASE)
            days = int(days_match.group(1)) if days_match else None

            # Parse minutes
            min_match = re.search(r"(\d+)\s*[Mm]in", name)
            minutes = int(min_match.group(1)) if min_match else None

            # Parse SMS
            sms_match = re.search(r"(\d+)\s*SMS", name, re.IGNORECASE)
            sms = int(sms_match.group(1)) if sms_match else None

            # Determine type from categories
            categories = [c.get("slug", "") for c in prod.get("categories", [])]
            plan_type = "country"  # default
            dest_heb = None

            for cat_slug in categories:
                if cat_slug == "global":
                    plan_type = "global"
                    dest_heb = "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9"
                    break
                if cat_slug in VOYE_REGION_MAP:
                    plan_type = "regional"
                    dest_heb = VOYE_REGION_MAP[cat_slug]
                    break

            # Check if it's a Global Light plan (name starts with "Global Light")
            if name.startswith("Global Light") or name.startswith("Global Voice"):
                plan_type = "global"
                dest_heb = "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9"

            if plan_type == "country":
                # Find country slug from categories (not region/global)
                skip_cats = {"global", "global-voice", "uncategorized", "esim", "e-sim",
                             "data-plans", "unlimited", "data-with-calls", "cruise"}
                for cat_slug in categories:
                    if cat_slug in skip_cats:
                        continue
                    if cat_slug in VOYE_REGION_MAP:
                        continue
                    # Try to convert slug to Hebrew
                    country_heb = core.SAILY_SLUG_TO_HEBREW.get(cat_slug)
                    if not country_heb:
                        country_heb = core.SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(cat_slug)
                    if country_heb:
                        dest_heb = country_heb
                        break
                if not dest_heb:
                    # Fallback: parse country from product name before "N Days" pattern
                    fallback = re.match(r"^(.+?)\s+\d+\s*[Dd]ays?", name)
                    if not fallback:
                        fallback = re.match(r"^([A-Za-z\s\-\.\'\(\)]+?)(?:\s*\d)", name)
                    if fallback:
                        raw = fallback.group(1).strip().rstrip("-– ")
                        slug = raw.lower().replace(" ", "-").replace("(", "").replace(")", "").rstrip("-")
                        dest_heb = core.SAILY_SLUG_TO_HEBREW.get(slug)
                        if not dest_heb:
                            dest_heb = core.SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(slug)
                        if not dest_heb:
                            # Try simpler slug variants
                            for variant in [slug.split("-")[0], slug.replace("'", "")]:
                                dest_heb = core.SAILY_SLUG_TO_HEBREW.get(variant) or core.SPARKS_COUNTRY_TO_HEBREW_EXTRA.get(variant)
                                if dest_heb: break
                        if not dest_heb:
                            dest_heb = VOYE_REGION_MAP.get(slug)  # e.g. north-america → צפון אמריקה
                        if not dest_heb:
                            dest_heb = raw  # keep English as last resort

            if not dest_heb:
                dest_heb = name  # last resort

            price_ils = round(price_usd * usd_rate, 2)

            # Build plan name and extras
            plan_extras = [dest_heb]
            if is_unlimited:
                # Daily limit varies by country
                _VOYE_15GB_COUNTRIES = {
                    "turkey", "canada", "brazil", "argentina",
                    "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4", "\u05e7\u05e0\u05d3\u05d4", "\u05d1\u05e8\u05d6\u05d9\u05dc", "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
                }
                _VOYE_2GB_COUNTRIES = {
                    "mexico", "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
                }
                # Check country slug from categories
                country_slug_lower = ""
                for cs in cats_list:
                    if cs not in ("global", "global-voice", "uncategorized", "esim", "e-sim",
                                  "data-plans", "unlimited", "data-with-calls", "cruise",
                                  "asia", "europe", "latin-america", "middle-east", "north-america", "regional"):
                        country_slug_lower = cs
                        break

                if country_slug_lower in _VOYE_2GB_COUNTRIES or (dest_heb and dest_heb in _VOYE_2GB_COUNTRIES):
                    daily_gb = "2"
                elif country_slug_lower in _VOYE_15GB_COUNTRIES or (dest_heb and dest_heb in _VOYE_15GB_COUNTRIES):
                    daily_gb = "1.5"
                else:
                    daily_gb = "3"

                gb_str = f"{daily_gb}GB/\u05d9\u05d5\u05dd"  # XGB/יום
                plan_extras.append(f"\u05e2\u05d3 {daily_gb}GB \u05d1\u05de\u05d4\u05d9\u05e8\u05d5\u05ea \u05d2\u05d1\u05d5\u05d4\u05d4 \u05dc\u05d9\u05d5\u05dd. \u05dc\u05d0\u05d7\u05e8 \u05de\u05db\u05df \u05d4\u05de\u05d4\u05d9\u05e8\u05d5\u05ea \u05de\u05d5\u05d0\u05d8\u05ea, \u05d0\u05da \u05ea\u05d5\u05de\u05da \u05d1\u05e4\u05d5\u05e0\u05e7\u05e6\u05d9\u05d5\u05ea \u05d1\u05e1\u05d9\u05e1\u05d9\u05d5\u05ea. \u05d4\u05de\u05db\u05e1\u05d4 \u05de\u05ea\u05d0\u05e4\u05e1\u05ea \u05de\u05d3\u05d9 \u05d9\u05d5\u05dd.")
            else:
                if data_gb is None:
                    gb_str = ""
                elif data_gb < 1:
                    gb_str = f"{round(data_gb * 1024)}MB"
                else:
                    gb_str = f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb}GB"

            days_str = f"{days} \u05d9\u05de\u05d9\u05dd" if days else ""
            plan_name = f"{dest_heb} \u2013 {gb_str}"
            if days_str:
                plan_name += f" \u2013 {days_str}"

            all_plans.append(core._make_global_plan(
                "voye", plan_name, price_ils, "USD", price_usd,
                data_gb=data_gb, days=days, minutes=minutes, sms=sms,
                esim=True, extras=plan_extras
            ))

        page_num += 1
        if len(products) < 100:
            break

    logger.info(f"VOYE global: {len(all_plans)} plans")
    return all_plans
