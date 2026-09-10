"""
Record / replay harness for the pure-HTTP scrapers.

Why: 76 scrape functions, ~12 covered by tests, and the global providers rot
silently (rows AGE instead of vanishing when a site redesigns). A recorded
fixture per provider turns "did the parser break?" into an offline unit test,
and the same URL set doubles as a cheap weekly live drift probe.

Three entry points:

  record(provider)      - run the scraper LIVE once, capture every HTTP
                          response it makes (capped), store it under
                          tests/fixtures/http/<provider>.json.gz together
                          with the plan count the capture reproduces.
  replay(provider)      - run the scraper OFFLINE against the capture.
                          Deterministic: unrecorded URLs raise a connection
                          error, sleeps are no-ops, FX rates are pinned.
  drift_check(provider) - run the scraper LIVE but only against the URLs in
                          the capture; compare the plan count with the
                          fixture's. Used by the weekly job (app.py) and by
                          scripts/scraper_drift_check.py.

How the interception works: scraper.py talks HTTP through exactly two doors,
`urllib.request.urlopen` and `requests.get` (both looked up on the module at
call time, including the `import requests` inside functions), so patching
those two attributes is enough. Playwright is patched to raise, so a
"_page=None" scraper that secretly launches a browser is detected at record
time and marked `playwright: true` (no fixture, skipped by the tests).

Fixture format (gzipped JSON):
  {
    "provider": "saily_global", "fn": "scrape_saily_global",
    "kwargs": {"usd_rate": 3.7}, "recorded_at": "...", "scraper_sha1": "...",
    "expected_plans": 812, "cap": 12, "playwright": false,
    "responses": { "GET <url>": {"status": 200, "headers": {...}, "body_b64": "..."} }
  }
"""
from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import io
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.abspath(__file__))
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "http")

# Pinned FX rates so recorded ILS prices are reproducible offline.
FX = {"usd": 3.7, "eur": 4.0, "gbp": 4.7}

DEFAULT_CAP = 12          # distinct URLs captured per provider
MAX_BODY = 4 * 1024 * 1024  # per-response body cap (bytes) - bigger bodies are truncated + flagged


def _u(rate): return {"usd_rate": FX["usd"]} if rate == "usd" else {"eur_rate": FX["eur"]} if rate == "eur" else {"gbp_rate": FX["gbp"]} if rate == "gbp" else {}


# provider -> (scraper function name, kwargs, plan_type)
# Every "_page=None" scraper is registered; the ones that turn out to launch
# Playwright are auto-marked at record time and simply have no fixture.
PROVIDERS: dict[str, dict] = {
    # domestic
    "xphone":            {"fn": "scrape_xphone",            "kwargs": {},         "type": "domestic"},
    "wecom":             {"fn": "scrape_wecom",             "kwargs": {},         "type": "domestic"},
    "neptucom":          {"fn": "scrape_neptucom",          "kwargs": {},         "type": "domestic"},
    "golan":             {"fn": "scrape_golan",             "kwargs": {},         "type": "domestic"},
    "rami_levy":         {"fn": "scrape_rami_levy",         "kwargs": {},         "type": "domestic"},
    "019":               {"fn": "scrape_019",               "kwargs": {},         "type": "domestic"},
    # abroad (roaming)
    "xphone_abroad":     {"fn": "scrape_xphone_abroad",     "kwargs": {},         "type": "abroad"},
    "wecom_abroad":      {"fn": "scrape_wecom_abroad",      "kwargs": {},         "type": "abroad"},
    "golan_abroad":      {"fn": "scrape_golan_abroad",      "kwargs": {},         "type": "abroad"},
    "rami_levy_abroad":  {"fn": "scrape_rami_levy_abroad",  "kwargs": {},         "type": "abroad"},
    "019_abroad":        {"fn": "scrape_019_abroad",        "kwargs": {},         "type": "abroad"},
    # global eSIM
    "airalo_local":      {"fn": "scrape_airalo_local",      "kwargs": _u("usd"),  "type": "global"},
    "airalo_regional":   {"fn": "scrape_airalo_regional",   "kwargs": _u("usd"),  "type": "global"},
    "xphone_global":     {"fn": "scrape_xphone_global",     "kwargs": {},         "type": "global"},
    "saily_global":      {"fn": "scrape_saily_global",      "kwargs": _u("usd"),  "type": "global"},
    "saily_regions":     {"fn": "scrape_saily_regions",     "kwargs": _u("usd"),  "type": "global"},
    "yesim_global":      {"fn": "scrape_yesim_global",      "kwargs": _u("usd"),  "type": "global"},
    "yesim_regions":     {"fn": "scrape_yesim_regions",     "kwargs": _u("usd"),  "type": "global"},
    "nomad_global":      {"fn": "scrape_nomad_global",      "kwargs": _u("usd"),  "type": "global"},
    "ubigi_global":      {"fn": "scrape_ubigi_global",      "kwargs": _u("usd"),  "type": "global"},
    "alosim_global":     {"fn": "scrape_alosim_global",     "kwargs": _u("usd"),  "type": "global"},
    "esimio_destinations": {"fn": "scrape_esimio_destinations", "kwargs": _u("usd"), "type": "global"},
    "esimio_regions":    {"fn": "scrape_esimio_regions",    "kwargs": _u("usd"),  "type": "global"},
    "esimo_global":      {"fn": "scrape_esimo_global",      "kwargs": _u("usd"),  "type": "global"},
    "simtlv_esim":       {"fn": "scrape_simtlv_esim",       "kwargs": {},         "type": "global"},
    "terminalesim":      {"fn": "scrape_terminalesim",      "kwargs": _u("usd"),  "type": "global"},
    "holafly_global":    {"fn": "scrape_holafly_global",    "kwargs": _u("usd"),  "type": "global"},
    "holafly_regions":   {"fn": "scrape_holafly_regions",   "kwargs": _u("usd"),  "type": "global"},
    "sparks_global":     {"fn": "scrape_sparks_global",     "kwargs": _u("usd"),  "type": "global"},
    "voye_global":       {"fn": "scrape_voye_global",       "kwargs": _u("usd"),  "type": "global"},
    "orbit_global":      {"fn": "scrape_orbit_global",      "kwargs": _u("usd"),  "type": "global"},
    "travelsim":         {"fn": "scrape_travelsim",         "kwargs": {},         "type": "global"},
    "gomoworld_global":  {"fn": "scrape_gomoworld_global",  "kwargs": _u("gbp"),  "type": "global"},
    "tasim_global":      {"fn": "scrape_tasim_global",      "kwargs": _u("usd"),  "type": "global"},
    "gigsky_global":     {"fn": "scrape_gigsky_global",     "kwargs": _u("usd"),  "type": "global"},
    "esimgenius_global": {"fn": "scrape_esimgenius_global", "kwargs": _u("usd"),  "type": "global"},
    "nisim_global":      {"fn": "scrape_nisim_global",      "kwargs": {},         "type": "global"},
    "esimax_global":     {"fn": "scrape_esimax_global",     "kwargs": _u("usd"),  "type": "global"},
    "venterrasim_global": {"fn": "scrape_venterrasim_global", "kwargs": {},       "type": "global"},
    "simzol_global":     {"fn": "scrape_simzol_global",     "kwargs": {},         "type": "global"},
    "maya_global":       {"fn": "scrape_maya_global",       "kwargs": _u("usd"),  "type": "global"},
    "bcengi_global":     {"fn": "scrape_bcengi_global",     "kwargs": _u("usd"),  "type": "global"},
    "esim70_global":     {"fn": "scrape_esim70_global",     "kwargs": _u("eur"),  "type": "global"},
    "bnesim_global":     {"fn": "scrape_bnesim_global",     "kwargs": _u("eur"),  "type": "global"},
    "jetpack_global":    {"fn": "scrape_jetpack_global",    "kwargs": _u("usd"),  "type": "global"},
    "breez_global":      {"fn": "scrape_breez_global",      "kwargs": _u("usd"),  "type": "global"},
    "bytesim_global":    {"fn": "scrape_bytesim_global",    "kwargs": _u("usd"),  "type": "global"},
    "bytesim_regions":   {"fn": "scrape_bytesim_regions",   "kwargs": _u("usd"),  "type": "global"},
    "besim_global":      {"fn": "scrape_besim_global",      "kwargs": _u("usd"),  "type": "global"},
    "besim_regions":     {"fn": "scrape_besim_regions",     "kwargs": _u("usd"),  "type": "global"},
    "seven_g_global":    {"fn": "scrape_seven_g_global",    "kwargs": _u("usd"),  "type": "global"},
    "bestconnect_global": {"fn": "scrape_bestconnect_global", "kwargs": _u("usd"), "type": "global"},
    "esimplus_global":   {"fn": "scrape_esimplus_global",   "kwargs": _u("usd"),  "type": "global"},
}


# ── exceptions ───────────────────────────────────────────────────────────────
class FixtureMiss(ConnectionError):
    """Raised for a URL that is not part of the capture (replay / drift) or is
    beyond the record cap. Scrapers treat it like any network failure."""


class PlaywrightNeeded(RuntimeError):
    """The scraper launched a browser - it can't be captured as plain HTTP."""


# ── response fakes ───────────────────────────────────────────────────────────
class _Headers(dict):
    """Case-insensitive header lookup with the subset of the email.message /
    requests CaseInsensitiveDict API that scraper.py uses (.get / [] / in)."""
    def __init__(self, d=None):
        super().__init__()
        for k, v in (d or {}).items():
            self[k] = v
    def __setitem__(self, k, v): super().__setitem__(k.lower(), v)
    def __getitem__(self, k): return super().__getitem__(k.lower())
    def __contains__(self, k): return super().__contains__(str(k).lower())
    def get(self, k, default=None): return super().get(str(k).lower(), default)
    def get_content_charset(self, failobj=None):
        ct = self.get("content-type", "") or ""
        for part in ct.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part.split("=", 1)[1].strip('" ')
        return failobj


class _UrlopenResp(io.BytesIO):
    """Stand-in for http.client.HTTPResponse as returned by urlopen()."""
    def __init__(self, url, status, headers, body):
        super().__init__(body)
        self.url = url
        self.status = status
        self.code = status
        self.headers = _Headers(headers)
        self.reason = "OK" if status < 400 else "ERR"
    def getcode(self): return self.status
    def geturl(self): return self.url
    def info(self): return self.headers
    def __enter__(self): return self
    def __exit__(self, *a): self.close(); return False


class _RequestsResp:
    """Stand-in for requests.Response."""
    def __init__(self, url, status, headers, body):
        import requests
        self.url = url
        self.status_code = status
        self.headers = requests.structures.CaseInsensitiveDict(headers)
        self.content = body
        self.encoding = "utf-8"
        self.reason = "OK" if status < 400 else "ERR"
        self.ok = status < 400
    @property
    def text(self): return self.content.decode(self.encoding or "utf-8", errors="replace")
    def json(self, **kw): return json.loads(self.text, **kw)
    def raise_for_status(self):
        import requests
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for url: {self.url}", response=self)
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False


# ── the interceptor ──────────────────────────────────────────────────────────
class _Interceptor:
    """Patches urlopen / requests.get / Playwright / FX / sleep for one run.

    mode: "record"  - unknown URLs go live (until cap) and are stored
          "replay"  - only stored URLs answer, everything else is a miss
          "drift"   - stored URLs go LIVE (fresh bodies), everything else is a miss
    """
    def __init__(self, mode, responses=None, cap=DEFAULT_CAP, allow_playwright=False):
        assert mode in ("record", "replay", "drift")
        self.mode = mode
        self.responses = responses if responses is not None else {}
        self.cap = cap
        self.allow_playwright = allow_playwright
        self.lock = threading.Lock()
        self.misses = 0
        self.live_calls = 0
        self.truncated = []
        self.playwright_used = False
        self._patches = []
        self._inflight = set()   # keys reserved by live calls not yet stored (cap accounting)

    # -- key / storage helpers
    @staticmethod
    def _key(method, url, data=None):
        k = f"{method} {url}"
        if data:
            k += " #" + hashlib.sha1(data).hexdigest()[:10]
        return k

    def _store(self, key, status, headers, body):
        self._inflight.discard(key)
        if len(body) > MAX_BODY:
            self.truncated.append(key)
            body = body[:MAX_BODY]
        self.responses[key] = {
            "status": int(status),
            "headers": {str(k): str(v) for k, v in dict(headers or {}).items()},
            "body_b64": base64.b64encode(body).decode("ascii"),
        }

    def _lookup(self, key):
        rec = self.responses.get(key)
        if rec is None:
            return None
        return rec["status"], rec["headers"], base64.b64decode(rec["body_b64"])

    def _may_go_live(self, key):
        with self.lock:
            if self.mode == "replay":
                return False
            if self.mode == "drift":
                return key in self.responses
            # record: honour the cap on DISTINCT urls. Reserve the slot under the
            # lock so parallel per-country fetches can't all pass the check at once.
            if key in self.responses or key in self._inflight:
                return False
            if len(self.responses) + len(self._inflight) >= self.cap:
                return False
            self._inflight.add(key)
            return True

    # -- urlopen
    def _fake_urlopen(self, req, data=None, timeout=None, *a, **kw):
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        method = (req.get_method() if isinstance(req, urllib.request.Request) else "GET")
        payload = data if data is not None else (req.data if isinstance(req, urllib.request.Request) else None)
        key = self._key(method, url, payload)
        if self.mode != "drift":
            hit = self._lookup(key)
            if hit is not None:
                status, headers, body = hit
                if status >= 400:
                    raise urllib.error.HTTPError(url, status, "recorded error", _Headers(headers), io.BytesIO(body))
                return _UrlopenResp(url, status, headers, body)
        if not self._may_go_live(key):
            with self.lock:
                self.misses += 1
            raise urllib.error.URLError(FixtureMiss(f"not in fixture: {key}"))
        with self.lock:
            self.live_calls += 1
        try:
            resp = self._orig_urlopen(req, data, timeout, *a, **kw) if timeout is not None else self._orig_urlopen(req, data, *a, **kw)
            body = resp.read()
            status = resp.status
            headers = dict(resp.headers.items())
        except urllib.error.HTTPError as e:
            self._inflight.discard(key)
            body = e.read() if hasattr(e, "read") else b""
            status = e.code
            headers = dict(e.headers.items()) if e.headers else {}
            if self.mode == "record":
                with self.lock:
                    self._store(key, status, headers, body)
            raise urllib.error.HTTPError(url, status, str(e.reason), _Headers(headers), io.BytesIO(body))
        except Exception:
            self._inflight.discard(key)
            raise
        if self.mode == "record":
            with self.lock:
                self._store(key, status, headers, body)
        return _UrlopenResp(url, status, headers, body)

    # -- requests.get
    def _fake_requests_get(self, url, params=None, **kw):
        import requests
        full = url
        if params:
            full = requests.Request("GET", url, params=params).prepare().url
        key = self._key("GET", full)
        if self.mode != "drift":
            hit = self._lookup(key)
            if hit is not None:
                return _RequestsResp(full, *hit)
        if not self._may_go_live(key):
            with self.lock:
                self.misses += 1
            raise requests.ConnectionError(f"not in fixture: {key}")
        with self.lock:
            self.live_calls += 1
        try:
            resp = self._orig_requests_get(url, params=params, **kw)
            body = resp.content
        except Exception:
            self._inflight.discard(key)
            raise
        if self.mode == "record":
            with self.lock:
                self._store(key, resp.status_code, dict(resp.headers), body)
        return _RequestsResp(full, resp.status_code, dict(resp.headers), body)

    def _fake_playwright(self, *a, **kw):
        self.playwright_used = True
        if self.allow_playwright:
            return self._orig_playwright(*a, **kw)
        raise PlaywrightNeeded("scraper launched Playwright - not capturable as HTTP")

    # -- context manager
    def __enter__(self):
        import requests
        import scraper
        import playwright.sync_api as pw_api
        self._orig_urlopen = urllib.request.urlopen
        self._orig_requests_get = requests.get
        self._orig_playwright = pw_api.sync_playwright

        def patch(obj, name, value):
            self._patches.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

        patch(urllib.request, "urlopen", self._fake_urlopen)
        patch(requests, "get", self._fake_requests_get)
        patch(pw_api, "sync_playwright", self._fake_playwright)
        patch(scraper, "sync_playwright", self._fake_playwright)
        patch(scraper, "_get_usd_to_ils", lambda: FX["usd"])
        patch(scraper, "_get_eur_to_ils", lambda: FX["eur"])
        patch(scraper, "_get_gbp_to_ils", lambda: FX["gbp"])
        # Retry/backoff sleeps: a scraper that retries every capped-out country
        # 3x with 1.5s/3s/4.5s waits (aloSIM) turns a capture into a 7-minute
        # crawl. Replay = no sleeps at all; record/drift = clamp to 0.2s.
        _orig_sleep = time.sleep
        if self.mode == "replay":
            patch(time, "sleep", lambda *_a, **_k: None)
        else:
            patch(time, "sleep", lambda secs=0, *_a, **_k: _orig_sleep(min(float(secs or 0), 0.2)))
        _reset_scraper_caches(scraper)
        # Every capped-out URL is a "fetch failed" warning from the scraper's own
        # per-country loop - hundreds of lines per provider that mean nothing in
        # replay/drift. Keep ERROR and above.
        self._quiet = []
        if self.mode != "record":
            for lg in (logging.getLogger("scraper"), logging.getLogger("scrapers")):
                self._quiet.append((lg, lg.level))
                lg.setLevel(logging.ERROR)
        return self

    def __exit__(self, *a):
        for obj, name, orig in reversed(self._patches):
            setattr(obj, name, orig)
        self._patches.clear()
        for lg, level in self._quiet:
            lg.setLevel(level)
        return False


def _reset_scraper_caches(scraper_mod):
    """Module-level memo dicts (e.g. _SAILY_API_CACHE) would let a replay
    succeed on data fetched by a previous run in the same process."""
    for name in dir(scraper_mod):
        if name.endswith("_CACHE") and isinstance(getattr(scraper_mod, name), dict):
            d = getattr(scraper_mod, name)
            if "ts" in d and "items" in d:
                d.update({"ts": 0.0, "items": None})
            else:
                d.clear()


# ── running a provider ───────────────────────────────────────────────────────
def _resolve(provider):
    import scraper
    spec = PROVIDERS[provider]
    return getattr(scraper, spec["fn"]), dict(spec["kwargs"]), spec


def fixture_path(provider):
    return os.path.join(FIXTURE_DIR, f"{provider}.json.gz")


def load_fixture(provider):
    p = fixture_path(provider)
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_fixture(provider, data):
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    with gzip.open(fixture_path(provider), "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def list_recorded():
    """Providers that have a usable (non-Playwright) fixture on disk."""
    out = []
    if not os.path.isdir(FIXTURE_DIR):
        return out
    for fn in sorted(os.listdir(FIXTURE_DIR)):
        if fn.endswith(".json.gz"):
            name = fn[:-len(".json.gz")]
            fx = load_fixture(name)
            # 0 responses is fine for data-file scrapers (sparks reads a local JSON);
            # a 0-plan capture is a broken capture, not a test.
            if fx and not fx.get("playwright") and (fx.get("expected_plans") or 0) > 0:
                out.append(name)
    return out


def _scraper_sha1():
    with open(os.path.join(ROOT, "scraper.py"), "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:12]


def run_with(mode, provider, responses=None, cap=DEFAULT_CAP):
    """Run one provider's scraper under the interceptor. Returns (plans, interceptor)."""
    fn, kwargs, _ = _resolve(provider)
    with _Interceptor(mode, responses=responses, cap=cap) as it:
        plans = fn(**kwargs)
    return list(plans or []), it


def record(provider, cap=DEFAULT_CAP, verify=True):
    """Capture a live run. Returns the fixture dict (also written to disk)."""
    spec = PROVIDERS[provider]
    meta = {
        "provider": provider, "fn": spec["fn"], "kwargs": spec["kwargs"], "type": spec["type"],
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scraper_sha1": _scraper_sha1(), "cap": cap, "fx": dict(FX),
    }
    try:
        plans, it = run_with("record", provider, responses={}, cap=cap)
    except PlaywrightNeeded:
        meta.update({"playwright": True, "responses": {}, "expected_plans": None})
        save_fixture(provider, meta)
        logger.warning("%s: launches Playwright - marked, no HTTP fixture", provider)
        return meta
    if it.playwright_used:
        # the scraper caught its own PlaywrightNeeded per page/batch and returned
        # whatever it had (typically nothing) - still a browser scraper.
        meta.update({"playwright": True, "responses": {}, "expected_plans": None})
        save_fixture(provider, meta)
        logger.warning("%s: launches Playwright (swallowed) - marked, no HTTP fixture", provider)
        return meta
    meta.update({
        "playwright": False,
        "responses": it.responses,
        "recorded_plans": len(plans),
        "live_calls": it.live_calls,
        "capped_misses": it.misses,
        "truncated": it.truncated,
    })
    if verify:
        rplans, _ = run_with("replay", provider, responses=it.responses, cap=cap)
        meta["expected_plans"] = len(rplans)
        if len(rplans) != len(plans):
            logger.warning("%s: replay reproduces %d plans vs %d live (non-deterministic scraper?)",
                           provider, len(rplans), len(plans))
    else:
        meta["expected_plans"] = len(plans)
    errs = validate_plans(plans, spec["type"])
    meta["validation_errors"] = errs[:10]
    save_fixture(provider, meta)
    return meta


def replay(provider):
    """Offline run against the stored capture. Returns (plans, fixture)."""
    fx = load_fixture(provider)
    if fx is None:
        raise FileNotFoundError(f"no fixture for {provider} - run scripts/record_scraper_fixture.py {provider}")
    if fx.get("playwright"):
        raise PlaywrightNeeded(provider)
    plans, _ = run_with("replay", provider, responses=fx["responses"], cap=fx.get("cap", DEFAULT_CAP))
    return plans, fx


def drift_check(provider, min_ratio=0.5):
    """Live probe restricted to the fixture's URL set. Returns a result dict:
    status: ok | drift | error | skipped."""
    fx = load_fixture(provider)
    if fx is None or fx.get("playwright") or not fx.get("responses"):
        return {"provider": provider, "status": "skipped", "reason": "no http fixture"}
    expected = fx.get("expected_plans") or 0
    t0 = time.time()
    try:
        plans, it = run_with("drift", provider, responses=fx["responses"], cap=fx.get("cap", DEFAULT_CAP))
    except Exception as exc:
        return {"provider": provider, "status": "error", "expected": expected, "live": 0,
                "error": f"{type(exc).__name__}: {exc}"[:200], "secs": round(time.time() - t0, 1)}
    live = len(plans)
    errs = validate_plans(plans, fx.get("type", "global"))
    status = "ok"
    if expected and (live == 0 or live < expected * min_ratio):
        status = "drift"
    elif errs:
        status = "drift"
    return {"provider": provider, "status": status, "expected": expected, "live": live,
            "validation_errors": errs[:5], "live_calls": it.live_calls, "secs": round(time.time() - t0, 1)}


def run_drift_check_all(providers=None, min_ratio=0.5):
    providers = providers or list_recorded()
    return [drift_check(p, min_ratio=min_ratio) for p in providers]


def format_drift_report(results):
    """Telegram-ready summary (Hebrew), listing only the non-ok providers."""
    bad = [r for r in results if r["status"] in ("drift", "error")]
    ok = [r for r in results if r["status"] == "ok"]
    lines = ["\U0001f9ea בדיקת סקרייפרים שבועית (drift)",
             f"תקינים: {len(ok)} / {len(results)}"]
    if not bad:
        lines.append("כל הסקרייפרים מחזירים נתונים כצפוי ✅")
    for r in bad:
        if r["status"] == "error":
            lines.append(f"❌ {r['provider']}: {r.get('error', '')}")
        else:
            lines.append(f"⚠️ {r['provider']}: {r['live']} מתוך {r['expected']} תוכניות"
                         + (f" ({r['validation_errors'][0]})" if r.get("validation_errors") else ""))
    lines.append("")
    lines.append("להקלטה מחדש: python scripts/record_scraper_fixture.py <provider>")
    return "\n".join(lines)


# ── plan schema validation ───────────────────────────────────────────────────
def validate_plans(plans, plan_type="global"):
    """Return a list of human-readable problems (empty = valid)."""
    errs = []
    if not isinstance(plans, list):
        return [f"plans is {type(plans).__name__}, not list"]
    for i, p in enumerate(plans):
        tag = f"#{i}"
        if not isinstance(p, dict):
            errs.append(f"{tag}: not a dict"); continue
        if not isinstance(p.get("carrier"), str) or not p["carrier"]:
            errs.append(f"{tag}: missing carrier")
        name = p.get("plan_name")
        if not isinstance(name, str) or not name.strip():
            errs.append(f"{tag}: missing plan_name")
        price = p.get("price")
        if price is not None and not isinstance(price, (int, float)):
            errs.append(f"{tag} {name}: price {price!r} not numeric")
        elif isinstance(price, (int, float)) and price < 0:
            errs.append(f"{tag} {name}: negative price")
        gb = p.get("data_gb")
        if gb is not None and not isinstance(gb, (int, float)):
            errs.append(f"{tag} {name}: data_gb {gb!r} not numeric")
        if "extras" in p and p["extras"] is not None and not isinstance(p["extras"], list):
            errs.append(f"{tag} {name}: extras not a list")
        if plan_type in ("global", "abroad"):
            days = p.get("days")
            if days is not None and not isinstance(days, (int, float)):
                errs.append(f"{tag} {name}: days {days!r} not numeric")
        if len(errs) > 50:
            errs.append("..."); break
    return errs
