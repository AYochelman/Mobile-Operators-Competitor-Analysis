# Parallel Global Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `scrape_all_global()` runtime from ~35 minutes to ~12 minutes by running self-contained scraper functions in parallel threads.

**Architecture:** Split the 21 jobs in `scrape_all_global()` into two groups. The 10 scrapers that share a Playwright page run sequentially in the main thread (unchanged). The 11 self-contained scrapers (own browser / HTTP / REST) are submitted to a `ThreadPoolExecutor(max_workers=4)` and run concurrently. Sequential and parallel groups execute simultaneously — the main thread runs sequential scrapers while threads handle the heavy per-country ones (Saily, ESIMio).

**Tech Stack:** Python `concurrent.futures.ThreadPoolExecutor`, existing `_ensure_event_loop()` helper, `playwright.sync_api.sync_playwright`

---

## File Structure

| File | Change |
|---|---|
| `scraper.py` | Add `_run_parallel_scraper()` helper (~10 lines). Rewrite `scrape_all_global()` (~45 lines). No other files touched. |
| `tests/test_scraper.py` | Add unit test for `scrape_all_global()` parallel behavior (mocked). |

---

### Task 1: Add `_run_parallel_scraper` helper and write its test

**Files:**
- Modify: `scraper.py` — add helper after `_ensure_event_loop()`
- Modify: `tests/test_scraper.py` — add unit test

- [ ] **Step 1: Write the failing unit test**

Add to `tests/test_scraper.py`:

```python
def test_run_parallel_scraper_success():
    """_run_parallel_scraper returns (name, list) on success."""
    from scraper import _run_parallel_scraper
    name, result = _run_parallel_scraper("test_fn", lambda: [{"carrier": "x"}])
    assert name == "test_fn"
    assert result == [{"carrier": "x"}]


def test_run_parallel_scraper_exception():
    """_run_parallel_scraper returns (name, []) and does not raise on exception."""
    from scraper import _run_parallel_scraper
    def _bad():
        raise RuntimeError("boom")
    name, result = _run_parallel_scraper("bad_fn", _bad)
    assert name == "bad_fn"
    assert result == []


def test_run_parallel_scraper_empty():
    """_run_parallel_scraper returns (name, []) when fn returns empty list."""
    from scraper import _run_parallel_scraper
    name, result = _run_parallel_scraper("empty_fn", lambda: [])
    assert name == "empty_fn"
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "D:\השוואת MASS MARKET"
pytest tests/test_scraper.py::test_run_parallel_scraper_success tests/test_scraper.py::test_run_parallel_scraper_exception tests/test_scraper.py::test_run_parallel_scraper_empty -v
```

Expected: `ImportError: cannot import name '_run_parallel_scraper'`

- [ ] **Step 3: Add `_run_parallel_scraper` to `scraper.py`**

Add immediately after the `_ensure_event_loop()` function definition (around line 30):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py::test_run_parallel_scraper_success tests/test_scraper.py::test_run_parallel_scraper_exception tests/test_scraper.py::test_run_parallel_scraper_empty -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add _run_parallel_scraper thread worker helper"
```

---

### Task 2: Rewrite `scrape_all_global()` with parallel execution

**Files:**
- Modify: `scraper.py` — replace `scrape_all_global()` body

- [ ] **Step 1: Write unit test for parallel behavior**

Add to `tests/test_scraper.py`:

```python
def test_scrape_all_global_merges_parallel_and_sequential(monkeypatch):
    """scrape_all_global merges results from both sequential and parallel groups."""
    import scraper

    # Patch sequential scrapers (page-based) to return one plan each
    seq_plan = {"carrier": "tuki", "plan_name": "T", "price": 10,
                "data_gb": 1, "days": 7, "extras": []}
    par_plan = {"carrier": "saily", "plan_name": "S", "price": 20,
                "data_gb": 2, "days": 30, "extras": []}

    def _fake_seq(page, *a, **kw):
        return [seq_plan]

    def _fake_par(*a, **kw):
        return [par_plan]

    # Patch all sequential scrapers
    for fn in ["scrape_tuki_global", "scrape_tuki_regions", "scrape_tuki_local",
               "scrape_globalesim_global", "scrape_globalesim_regions",
               "scrape_airalo_global", "scrape_pelephone_globalsim",
               "scrape_esimo_global", "scrape_simtlv_global", "scrape_world8_global"]:
        monkeypatch.setattr(scraper, fn, _fake_seq)

    # Patch all parallel scrapers
    for fn in ["scrape_xphone_global", "scrape_saily_global", "scrape_saily_regions",
               "scrape_esimio_destinations", "scrape_esimio_regions",
               "scrape_holafly_global", "scrape_holafly_regions",
               "scrape_sparks_global", "scrape_voye_global",
               "scrape_orbit_global", "scrape_travelsim"]:
        monkeypatch.setattr(scraper, fn, _fake_par)

    # Patch playwright and rate fetchers so no network calls happen
    class _FakePage:
        pass
    class _FakeBrowser:
        def new_page(self, **kw): return _FakePage()
        def close(self): pass
    class _FakeP:
        chromium = type("C", (), {"launch": staticmethod(lambda **kw: _FakeBrowser())})()
    class _FakePW:
        def __enter__(self): return _FakeP()
        def __exit__(self, *a): pass
    monkeypatch.setattr(scraper, "sync_playwright", lambda: _FakePW())
    monkeypatch.setattr(scraper, "_get_usd_to_ils", lambda: 3.7)
    monkeypatch.setattr(scraper, "_get_eur_to_ils", lambda: 4.0)

    plans = scraper.scrape_all_global()

    # 10 sequential scrapers × 1 plan + 11 parallel scrapers × 1 plan = 21 plans
    assert len(plans) == 21
    carriers = {p["carrier"] for p in plans}
    assert "tuki" in carriers
    assert "saily" in carriers
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_scraper.py::test_scrape_all_global_merges_parallel_and_sequential -v
```

Expected: FAIL (current implementation runs everything in one sequential loop)

- [ ] **Step 3: Replace `scrape_all_global()` body in `scraper.py`**

Replace the entire function (currently lines ~3684–3728) with:

```python
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
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

    # ── Sequential jobs: share one Playwright browser page ────────────────
    sequential_jobs = [
        ("scrape_tuki_global",         lambda pg: scrape_tuki_global(pg, usd_rate)),
        ("scrape_tuki_regions",        lambda pg: scrape_tuki_regions(pg, usd_rate)),
        ("scrape_tuki_local",          lambda pg: scrape_tuki_local(pg, usd_rate)),
        ("scrape_globalesim_global",   scrape_globalesim_global),
        ("scrape_globalesim_regions",  scrape_globalesim_regions),
        ("scrape_airalo_global",       lambda pg: scrape_airalo_global(pg, usd_rate)),
        ("scrape_pelephone_globalsim", scrape_pelephone_globalsim),
        ("scrape_esimo_global",        lambda pg: scrape_esimo_global(pg, usd_rate)),
        ("scrape_simtlv_global",       scrape_simtlv_global),
        ("scrape_world8_global",       scrape_world8_global),
    ]

    # ── Parallel jobs: each creates its own browser / HTTP / REST ─────────
    parallel_jobs = [
        ("scrape_xphone_global",       lambda: scrape_xphone_global()),
        ("scrape_saily_global",        lambda: scrape_saily_global(usd_rate=usd_rate)),
        ("scrape_saily_regions",       lambda: scrape_saily_regions(usd_rate=usd_rate)),
        ("scrape_esimio_destinations", lambda: scrape_esimio_destinations(usd_rate=usd_rate)),
        ("scrape_esimio_regions",      lambda: scrape_esimio_regions(usd_rate=usd_rate)),
        ("scrape_holafly_global",      lambda: scrape_holafly_global(usd_rate=usd_rate)),
        ("scrape_holafly_regions",     lambda: scrape_holafly_regions(usd_rate=usd_rate)),
        ("scrape_sparks_global",       lambda: scrape_sparks_global(usd_rate=usd_rate)),
        ("scrape_voye_global",         lambda: scrape_voye_global(usd_rate=usd_rate)),
        ("scrape_orbit_global",        lambda: scrape_orbit_global(usd_rate=usd_rate)),
        ("scrape_travelsim",           scrape_travelsim),
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

        # Collect parallel results (blocks until all threads finish)
        for future in as_completed(futures):
            _, result = future.result()   # _run_parallel_scraper never raises
            plans.extend(result)

    return plans
```

- [ ] **Step 4: Run the unit test**

```bash
pytest tests/test_scraper.py::test_scrape_all_global_merges_parallel_and_sequential -v
```

Expected: PASS

- [ ] **Step 5: Run full unit test suite (non-integration)**

```bash
pytest tests/ -v -m "not integration"
```

Expected: All existing tests PASS (no regressions in db, change_detector, notifier, api).

- [ ] **Step 6: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "perf: parallelize scrape_all_global with ThreadPoolExecutor(max_workers=4)"
```

---

### Task 3: Smoke-test timing

- [ ] **Step 1: Restart Flask**

```bash
wmic process where "name='python.exe'" get processid,commandline
wmic process where processid=<PID> delete
python app.py
```

- [ ] **Step 2: Trigger scrape and measure**

In a second terminal, record the start time and call the endpoint:

```bash
date && curl -s "http://localhost:5000/api/scrape-all-now?api_key=<KEY>" | python -m json.tool && date
```

Expected response includes `"global": {"plans": <N>, ...}` with N > 0.
Expected wall-clock for global portion: ~10–15 minutes (vs ~35 before).

- [ ] **Step 3: Check logs for parallel evidence**

```bash
grep "global plans" flask_log.txt | tail -30
```

Expected: lines from scrape_saily_global, scrape_esimio_destinations, scrape_xphone_global etc. appear interleaved (not in original sequential order), confirming parallel execution.
