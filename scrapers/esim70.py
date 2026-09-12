"""esim70 scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


ESIM70_ISO2_TO_HEBREW = {
    "AF": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df", "AL": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "DZ": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4", "AD": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "AI": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4", "AG": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "AR": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4", "AM": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "AU": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4", "AT": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "AZ": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df", "BS": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "BH": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df", "BD": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "BB": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1", "BY": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "BE": "\u05d1\u05dc\u05d2\u05d9\u05d4", "BZ": "\u05d1\u05dc\u05d9\u05d6",
    "BO": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4", "BA": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "BR": "\u05d1\u05e8\u05d6\u05d9\u05dc", "VG": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "BG": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4", "KH": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "CA": "\u05e7\u05e0\u05d3\u05d4", "CV": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "KY": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df", "TD": "\u05e6'\u05d0\u05d3",
    "CL": "\u05e6'\u05d9\u05dc\u05d4", "CN": "\u05e1\u05d9\u05df",
    "CO": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4", "CD": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "CG": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5", "CR": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "HR": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4", "CY": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "CZ": "\u05e6'\u05db\u05d9\u05d4", "DK": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "DM": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4", "DO": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "EC": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8", "EG": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "SV": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8", "EE": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "FO": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5", "FJ": "\u05e4\u05d9\u05d2'\u05d9",
    "FI": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3", "FR": "\u05e6\u05e8\u05e4\u05ea",
    "GF": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea", "GA": "\u05d2\u05d0\u05d1\u05d5\u05df",
    "GE": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4", "DE": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "GH": "\u05d2\u05d0\u05e0\u05d4", "GI": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "GR": "\u05d9\u05d5\u05d5\u05df", "GD": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "GU": "\u05d2\u05d5\u05d0\u05dd", "GT": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "HN": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1", "HK": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "HU": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4", "IS": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "IN": "\u05d4\u05d5\u05d3\u05d5", "ID": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "IQ": "\u05e2\u05d9\u05e8\u05d0\u05e7", "IE": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "IL": "\u05d9\u05e9\u05e8\u05d0\u05dc", "IT": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "JM": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4", "JP": "\u05d9\u05e4\u05df",
    "JO": "\u05d9\u05e8\u05d3\u05df", "KZ": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "KE": "\u05e7\u05e0\u05d9\u05d4", "XK": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "KW": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea", "KG": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "LA": "\u05dc\u05d0\u05d5\u05e1", "LV": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "LI": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df", "LT": "\u05dc\u05d9\u05d8\u05d0",
    "LU": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2", "MO": "\u05de\u05e7\u05d0\u05d5",
    "MK": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea", "MG": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "MW": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9", "MY": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "MV": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd", "MT": "\u05de\u05dc\u05d8\u05d4",
    "MU": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1", "MX": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "MD": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4", "MN": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "ME": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5", "MS": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "MA": "\u05de\u05e8\u05d5\u05e7\u05d5", "NP": "\u05e0\u05e4\u05d0\u05dc",
    "NL": "\u05d4\u05d5\u05dc\u05e0\u05d3", "AN": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "NZ": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3", "NI": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "NE": "\u05e0\u05d9\u05d2'\u05e8", "NG": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "NO": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4", "OM": "\u05e2\u05d5\u05de\u05df",
    "PK": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df", "PS": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "PA": "\u05e4\u05e0\u05de\u05d4", "PY": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "PE": "\u05e4\u05e8\u05d5", "PH": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "PL": "\u05e4\u05d5\u05dc\u05d9\u05df", "PT": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "PR": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5", "QA": "\u05e7\u05d8\u05e8",
    "RE": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df", "RO": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "RU": "\u05e8\u05d5\u05e1\u05d9\u05d4", "RW": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "KN": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1", "LC": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "VC": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "SA": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea", "SN": "\u05e1\u05e0\u05d2\u05dc",
    "RS": "\u05e1\u05e8\u05d1\u05d9\u05d4", "SG": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "SK": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4", "SI": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "ZA": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4", "KR": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "ES": "\u05e1\u05e4\u05e8\u05d3", "LK": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "SE": "\u05e9\u05d1\u05d3\u05d9\u05d4", "CH": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "TW": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df", "TZ": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "TH": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3", "TN": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "TR": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4", "TC": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "UG": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4", "UA": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "AE": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea", "GB": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "US": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea", "UY": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "UZ": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df", "VE": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "VN": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd", "ZM": "\u05d6\u05de\u05d1\u05d9\u05d4",
    "GP": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
}


ESIM70_REGION_BASE_TO_HEBREW = {
    "Europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "CIS": "\u05d7\u05d1\u05e8 \u05d4\u05de\u05d3\u05d9\u05e0\u05d5\u05ea",
    "SEA": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "Balkans": "\u05d4\u05d1\u05dc\u05e7\u05df",
    "MIDDLE EAST": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "LATAM": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "Latin America": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "North America": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "Asia Pacific": "\u05d0\u05e1\u05d9\u05d4 \u05e4\u05e1\u05d9\u05e4\u05d9\u05e7",
    "Asia": "\u05d0\u05e1\u05d9\u05d4",
    "Global Package": "\u05d7\u05d1\u05d9\u05dc\u05d4 \u05d2\u05dc\u05d5\u05d1\u05dc\u05d9\u05ea",
}


def scrape_esim70_global(_page=None, eur_rate=None):
    """Scrape eSIM70 global plans via Lascade REST API — no Playwright needed.

    2026-07: the API dropped the bulk listing (plans/ now returns 400 without a
    filter_country or region param), so we enumerate /api/countries/ (150 codes,
    paginated) + /api/regions/ (9 slugs) and fetch per-country / per-region.
    Plan payloads and names are unchanged, so plan_name keys stay stable.
    """
    import urllib.request as _ur, urllib.error as _ue, json as _js, time as _time

    if eur_rate is None:
        eur_rate = core._get_eur_to_ils()

    all_plans = []
    _LASCADE_API = "https://esim.lascade.com/api"
    _LASCADE_COMMON = "is_active=true&app_code=D1WE&billing_country=IL&currency=EUR"
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

    def _get_json(url):
        # ~160 per-country calls trip the API's rate limit — pace steadily and
        # back off on 429 (honoring Retry-After when sent).
        backoff = 10
        for attempt in range(4):
            _time.sleep(0.45)
            try:
                req = _ur.Request(url, headers={"User-Agent": _UA})
                with _ur.urlopen(req, timeout=20) as r:
                    return _js.loads(r.read())
            except _ue.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    retry_after = e.headers.get("Retry-After") or ""
                    _time.sleep(min(int(retry_after) if retry_after.isdigit() else backoff, 120))
                    backoff *= 2
                    continue
                raise

    def _paged(url):
        """Yield results across DRF-style pagination (follows 'next' links)."""
        while url:
            data = _get_json(url)
            if isinstance(data, list):  # /regions/ returns a bare list
                yield from data
                return
            yield from (data.get("results") or [])
            url = data.get("next")

    def _region_heb(raw_name):
        base = re.sub(r"\s+\d+\s+days?\s+unlim$", "", raw_name, flags=re.IGNORECASE).strip()
        base = re.sub(r"\s*\d+(\.\d+)?GB$", "", base).strip()
        return ESIM70_REGION_BASE_TO_HEBREW.get(base, base)

    def _gb_str(gb):
        return f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"

    def _build_plan(plan_type, p):
        is_unlimited = p.get("is_unlimited", False)
        days = p.get("days")
        price_eur = float(p.get("display_price") or 0)
        if price_eur <= 0:
            return None
        price_ils = round(price_eur * eur_rate, 2)

        if plan_type == "region":
            raw = p["name"].split("_")[0].strip()
            heb_name = _region_heb(raw)
        else:
            codes = p.get("countries", [])
            if not codes:
                return None
            heb_name = ESIM70_ISO2_TO_HEBREW.get(codes[0]["code"]) or codes[0].get("name") or ""
            if not heb_name:
                return None

        if is_unlimited:
            data_gb = None
            gb_part = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"  # ללא הגבלה
        else:
            data_gb = float(p.get("data_in_gb") or 0) or None
            gb_part = _gb_str(data_gb) if data_gb else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"

        plan_name = f"{heb_name} \u2013 {gb_part} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
        return core._make_global_plan(
            "esim70", plan_name, price_ils, "EUR", price_eur,
            data_gb=data_gb, days=days, esim=True, extras=[heb_name],
        )

    try:
        region_slugs = [r["slug"] for r in _paged(f"{_LASCADE_API}/regions/?app_code=D1WE")]
    except Exception as e:
        logger.warning(f"eSIM70 regions list: {e}")
        region_slugs = []
    try:
        country_codes = [c["code"] for c in _paged(f"{_LASCADE_API}/countries/?app_code=D1WE")]
    except Exception as e:
        logger.warning(f"eSIM70 countries list: {e}")
        country_codes = []

    # A plan covering several countries comes back once per covered country —
    # dedupe by API id so it lands as a single row (keyed to countries[0], as
    # the old bulk listing did).
    seen_ids = set()

    def _collect(plan_type, filt):
        try:
            for p in _paged(f"{_LASCADE_API}/plans/?{_LASCADE_COMMON}&plan_type={plan_type}&{filt}&limit=200"):
                pid = p.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                plan = _build_plan(plan_type, p)
                if plan:
                    all_plans.append(plan)
        except Exception as e:
            logger.warning(f"eSIM70 {plan_type} {filt}: {e}")

    for slug in region_slugs:
        _collect("region", f"region={slug}")
    for code in country_codes:
        _collect("country", f"filter_country={code}")

    logger.info(f"eSIM70 global: {len(all_plans)} plans")
    return all_plans
