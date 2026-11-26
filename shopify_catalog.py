"""Patient collector for the Shopify shops we read (Holafly, Breeze).

Why this exists (measured 2026-11-21): Shopify rate limits the storefront
LISTING endpoints (`/products.json`, `/collections/<x>/products.json`) for our
client to roughly ONE request every ~20 minutes, apparently one budget shared
by every Shopify shop we ask. Everything else on those shops answers normally.
Holafly needs 1 listing request per refresh and Breeze 2, so the three can never
fit inside a 10-minute scrape: whichever scraper asked second got
`429 local_rate_limited` (Breeze froze from 2026-11-18).

So the listings are collected OUTSIDE the scrape, at the pace the shop allows:

  collect()        - scheduled about 80 minutes before each scrape. Asks for one
                     listing, waits, asks for the next. A 429 is waited out and
                     retried; nothing is ever asked faster than RETRY_GAP.
  products(key)    - what the scrapers call. Returns the cached listing when it
                     is younger than MAX_AGE_HOURS, else None. The scrape itself
                     makes NO request to these shops.

A source that could not be collected simply stays old: its scraper returns no
plans, the rows age, and the morning freshness check reports the carrier.

LIVE = True (set by the fixture harness and the unit tests) makes products()
fetch directly instead of reading the cache, so the scrapers stay testable
through the same record / replay doors as every other provider.

Do not answer a 429 here by changing the HTTP client or its headers - that is
getting around the shop's limit, not respecting it. The fix for "not enough
budget" is fewer or later requests.
"""
import gzip
import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(ROOT, "data", "shopify_cache")

# key -> listing URL template. ORDER is the collection order: Holafly first (the
# bigger catalog), then the two Breeze collections, which are only useful together.
SOURCES = {
    "holafly": "https://holafly-esim.myshopify.com/products.json?limit=250&page={page}",
    "breez_country": "https://breezesim.com/collections/country-bundles/products.json?limit=250&page={page}",
    "breez_regional": "https://breezesim.com/collections/regional-bundles/products.json?limit=250&page={page}",
}
ORDER = ("holafly", "breez_country", "breez_regional")

PAGE_SIZE = 250
MAX_PAGES = 6
MAX_AGE_HOURS = 14        # a cache older than this is not served to the scrapers
FRESH_HOURS = 5           # collect() skips a source collected more recently than this
RETRY_GAP = 300           # seconds between two attempts after a 429. Was 120: the live run of
                          # 2026-11-21 spent 18 of its 21 requests on 429s, because the budget
                          # refills in ~20 min however often we ask.
AFTER_SUCCESS_GAP = 18 * 60   # the budget refills in ~20 min; do not ask sooner
MAX_MINUTES = 100         # whole-run deadline for collect()

LIVE = False


class RateLimited(Exception):
    """The shop answered 429 to a listing request."""


def _slim(product):
    """Keep only what the scrapers read (the raw Holafly listing is ~7 MB)."""
    return {
        "handle": product.get("handle"),
        "title": product.get("title"),
        "variants": [
            {"sku": v.get("sku"), "title": v.get("title"), "price": v.get("price"),
             "available": v.get("available")}
            for v in (product.get("variants") or [])
        ],
    }


def _get_page(key, page):
    """One listing request. Returns (status, products, retry_after_seconds)."""
    import requests
    r = requests.get(SOURCES[key].format(page=page), timeout=90)
    if r.status_code == 429:
        ra = str(r.headers.get("Retry-After") or "")
        return 429, [], int(ra) if ra.isdigit() else None
    if r.status_code != 200:
        return r.status_code, [], None
    return 200, [_slim(p) for p in (r.json().get("products") or [])], None


def fetch_live(key):
    """All pages of one source, no waiting. Raises RateLimited on a 429.
    Used when LIVE is set (tests, fixture record / replay / drift)."""
    out = []
    for page in range(1, MAX_PAGES + 1):
        status, batch, _ = _get_page(key, page)
        if status == 429:
            raise RateLimited(key)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        out.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return out


# ── cache ────────────────────────────────────────────────────────────────────
def _path(key):
    return os.path.join(CACHE_DIR, f"{key}.json.gz")


def save(key, products_list):
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = _path(key) + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump({"key": key, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "products": products_list}, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, _path(key))


def age_hours(key):
    """Hours since the source was last collected, or None when never."""
    try:
        with gzip.open(_path(key), "rt", encoding="utf-8") as f:
            stamp = json.load(f).get("fetched_at")
        return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds() / 3600
    except (OSError, ValueError, TypeError):
        return None


def load(key, max_age_hours=None):
    """Cached product list, or None when missing / unreadable / too old."""
    limit = MAX_AGE_HOURS if max_age_hours is None else max_age_hours
    try:
        with gzip.open(_path(key), "rt", encoding="utf-8") as f:
            data = json.load(f)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(data["fetched_at"])).total_seconds() / 3600
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if age > limit:
        return None
    return data.get("products") or None


def products(key):
    """What the scrapers call: the listing for `key`, or None when unavailable."""
    if LIVE:
        return fetch_live(key)
    return load(key)


# ── the patient collector ────────────────────────────────────────────────────
def collect(max_minutes=None, sleep=time.sleep, clock=time.monotonic, keys=None):
    """Refresh every stale source at the pace the shop allows.

    Returns {key: "fresh" | "collected (N products, M requests)" | "rate_limited" | "http <code>" | "error: ..."}.
    Safe to re-run: a source collected less than FRESH_HOURS ago is skipped, so an
    interrupted run continues where it stopped.
    """
    deadline = clock() + 60 * (MAX_MINUTES if max_minutes is None else max_minutes)
    results = {}
    asked_once = False          # the first request of a run needs no waiting
    wait, last_status = 0, None
    if keys is None:
        # Stalest first (never collected = stalest; ties keep ORDER). The first
        # request of a run is the one that reliably passes - the budget refilled
        # overnight - while the later ones can meet 429s until the deadline. With a
        # fixed order the same source starved every run: breez_regional, always
        # third, went uncollected 2026-11-22 .. 11-26 and froze all of Breeze.
        ages = {k: age_hours(k) for k in ORDER}
        keys = sorted(ORDER, key=lambda k: -(ages[k] if ages[k] is not None else float("inf")))
    for key in keys:
        age = age_hours(key)
        if age is not None and age < FRESH_HOURS:
            results[key] = "fresh"
            continue
        collected, page, requests_made = [], 1, 0
        while True:
            if asked_once:
                # Never ask faster than the shop's refill: wait out the gap that the
                # previous answer calls for, and stop when the run's deadline is near.
                if clock() + wait > deadline:
                    results[key] = "rate_limited" if last_status == 429 else "deadline"
                    break
                sleep(wait)
            try:
                status, batch, retry_after = _get_page(key, page)
            except Exception as exc:
                results[key] = f"error: {type(exc).__name__}: {exc}"[:160]
                last_status, wait, asked_once = None, RETRY_GAP, True
                break
            requests_made += 1
            asked_once, last_status = True, status
            if status == 429:
                wait = max(RETRY_GAP, retry_after or 0)
                continue
            if status != 200:
                results[key] = f"http {status}"
                wait = RETRY_GAP
                break
            wait = AFTER_SUCCESS_GAP
            collected.extend(batch)
            if len(batch) < PAGE_SIZE or page >= MAX_PAGES:
                if collected:
                    save(key, collected)
                    results[key] = f"collected ({len(collected)} products, {requests_made} requests)"
                else:
                    results[key] = "empty listing"
                break
            page += 1
    for key, outcome in results.items():
        (logger.info if outcome == "fresh" or outcome.startswith("collected") else logger.warning)(
            f"Shopify catalog {key}: {outcome}")
    _log_run(results)
    return results


def _log_run(results):
    """Append the run's outcome to CACHE_DIR/collect_log.jsonl. Flask's log only
    reaches the watchdog console, so without this a source that keeps failing
    leaves no trace of WHY (`python shopify_catalog.py status` prints the tail)."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, "collect_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "results": results}, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning(f"Shopify catalog: could not write the run log: {exc}")


def _log_tail(n=6):
    try:
        with open(os.path.join(CACHE_DIR, "collect_log.jsonl"), encoding="utf-8") as f:
            return f.readlines()[-n:]
    except OSError:
        return []


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        for k in ORDER:
            a = age_hours(k)
            print(k, "never collected" if a is None else f"{a:.1f}h old", len(load(k, 10 ** 6) or []), "products")
        tail = _log_tail()
        if tail:
            print("last runs:")
            for line in tail:
                print(" ", line.rstrip())
    else:
        print(json.dumps(collect(), ensure_ascii=False, indent=1))
