# Parallel Global Scraper Design

**Date:** 2026-04-15  
**Status:** Approved  
**Goal:** Cut `scrape_all_global()` runtime from ~35 minutes to ~12 minutes using `ThreadPoolExecutor(max_workers=4)`.

---

## Problem

`scrape_all_global()` in `scraper.py` runs 21 scraper functions sequentially. Eleven of them are fully self-contained (each opens its own Playwright browser or uses HTTP/REST — they accept `_page=None`). The two heaviest — `scrape_saily_global` (199 countries) and `scrape_esimio_destinations` (191 countries) — take ~10 minutes each and together account for ~20 of the ~35 total minutes.

---

## Approach: Parallel top-level scrapers (Approach A)

Split the jobs list into two groups and run them concurrently.

### Sequential group (10 functions — share one Playwright browser)

These functions take a required `page` argument (no default), so they must share a single browser instance and run in the main thread:

- `scrape_tuki_global(page, usd_rate)`
- `scrape_tuki_regions(page, usd_rate)`
- `scrape_tuki_local(page, usd_rate)`
- `scrape_globalesim_global(page)`
- `scrape_globalesim_regions(page)`
- `scrape_airalo_global(page, usd_rate)`
- `scrape_pelephone_globalsim(page)`
- `scrape_esimo_global(page, usd_rate)`
- `scrape_simtlv_global(page)`
- `scrape_world8_global(page)`

Estimated runtime: ~5 minutes (unchanged).

### Parallel group (11 functions — each self-contained)

These functions have `_page=None` or `page=None` and open their own Playwright browser, use `urllib.request`, or call a REST API. They are safe to run in separate threads:

| Function | Type | Est. time |
|---|---|---|
| `scrape_saily_global` | own browser, 199 pages | ~10 min |
| `scrape_saily_regions` | own browser | ~2 min |
| `scrape_esimio_destinations` | own browser, 191 pages | ~10 min |
| `scrape_esimio_regions` | own browser | ~2 min |
| `scrape_xphone_global` | own browser | ~1 min |
| `scrape_sparks_global` | own browser | ~2 min |
| `scrape_voye_global` | own browser | ~3 min |
| `scrape_holafly_global` | HTTP only, 182 requests | ~3 min |
| `scrape_holafly_regions` | HTTP only | ~1 min |
| `scrape_orbit_global` | REST API | ~1 min |
| `scrape_travelsim` | static data | instant |

With `max_workers=4`, the two ~10-minute scrapers (Saily + ESIMio) start immediately alongside two others. As fast workers finish, the remaining jobs fill their slots. Total parallel wall-clock: **~12 minutes**.

---

## Implementation

### Changes to `scrape_all_global()` in `scraper.py`

```
1. Compute usd_rate + eur_rate (unchanged)
2. Build parallel_jobs: list of (name, callable) for all 11 self-contained scrapers
3. Submit all parallel_jobs to ThreadPoolExecutor(max_workers=4)
   - Each thread wrapper calls _ensure_event_loop() before invoking the scraper
4. While threads run: execute sequential_jobs in main thread with shared browser (unchanged)
5. As each future completes: collect results, log success/failure
6. Merge sequential + parallel results and return
```

### Thread wrapper pattern

```python
def _run_parallel(name, fn):
    _ensure_event_loop()
    try:
        result = fn()
        logger.info(f"{name}: {len(result)} global plans")
        return result
    except Exception as e:
        logger.error(f"{name} failed: {e}", exc_info=True)
        return []
```

### Error handling

- Each future is collected with `future.result()` in a `try/except`
- A failed parallel scraper logs the error and returns `[]` — does not block others
- Mirrors the existing sequential error handling pattern

---

## Expected Results

| Metric | Before | After |
|---|---|---|
| `scrape_all_global()` | ~35 min | ~12 min |
| Full scrape (all tabs + banners) | ~50 min | ~25 min |
| Max concurrent browsers | 1 | 4 |
| RAM overhead (Chromium ~180MB each) | baseline | +~540MB peak |

---

## Files Changed

- `scraper.py` — only `scrape_all_global()` is modified. No changes to any individual scraper function.

---

## Out of Scope

- Per-country parallelism within Saily/ESIMio (Approach B) — bot-detection risk, larger change
- Async Playwright rewrite (Approach C) — ~4,000 lines of refactoring
- Parallelizing `scrape_all()` (domestic) or `scrape_all_abroad()` — already fast enough
