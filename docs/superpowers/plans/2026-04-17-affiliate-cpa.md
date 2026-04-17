# Affiliate CPA — Global eSIM Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up affiliate click tracking and redirect links for Airalo, Holafly, Saily and Globalesim so every "רכישה" click from a PlanCard earns a commission.

**Architecture:** A Flask `/go/<provider>/<plan_id>` endpoint logs each click (SHA-256 hashed IP, provider, plan slug, country) to a new `affiliate_clicks` SQLite table, then issues a 302 redirect to the provider's affiliate URL from `config.json`. PlanCard replaces the plain "תנאי התוכנית" link with a styled "רכישה" button for the four affiliate providers. SettingsPage gains an Affiliate tab with click counts and estimated earnings (admin-only).

**Tech Stack:** Python/Flask, SQLite (via db.py patterns), React/Tailwind, Recharts (already installed), `config.json` for affiliate tags.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `db.py` | Add `affiliate_clicks` table + `log_affiliate_click()` + `get_affiliate_stats()` |
| Modify | `app.py` | Add `redirect` import, db imports, `/go/<provider>/<plan_id>` endpoint, `/api/affiliate/stats` endpoint |
| Modify | `mass-market-app/src/lib/api.js` | Add `getAffiliateStats()` |
| Modify | `mass-market-app/src/components/PlanCard.jsx` | Add `AFFILIATE_PROVIDERS`, `slugify()`, affiliate button |
| Modify | `mass-market-app/src/pages/SettingsPage.jsx` | Add Affiliate analytics tab |
| Modify | `tests/test_db.py` | Affiliate DB tests |
| Modify | `tests/test_app.py` | Affiliate endpoint tests |

---

## Task 1: DB — `affiliate_clicks` table + CRUD functions

**Files:**
- Modify: `db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_db.py`:

```python
from db import (init_db, save_plans, get_plans, save_changes, get_changes,
                upsert_news_articles, get_news_articles,
                log_affiliate_click, get_affiliate_stats)

def test_log_affiliate_click_basic(tmp_db):
    log_affiliate_click("airalo", plan_id="israel-1gb", country="ישראל",
                        ip_hash="abc123", db_path=tmp_db)
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    assert len(stats) == 1
    assert stats[0]["provider"] == "airalo"
    assert stats[0]["clicks"] == 1

def test_log_affiliate_click_optional_fields(tmp_db):
    # plan_id, country and ip_hash are all optional
    log_affiliate_click("holafly", db_path=tmp_db)
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    assert stats[0]["clicks"] == 1

def test_get_affiliate_stats_groups_by_provider(tmp_db):
    log_affiliate_click("airalo", db_path=tmp_db)
    log_affiliate_click("airalo", db_path=tmp_db)
    log_affiliate_click("holafly", db_path=tmp_db)
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    providers = {s["provider"]: s["clicks"] for s in stats}
    assert providers["airalo"] == 2
    assert providers["holafly"] == 1

def test_get_affiliate_stats_respects_days_window(tmp_db):
    # Insert one old click directly via SQL
    import sqlite3, datetime
    old_ts = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=40)).isoformat()
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO affiliate_clicks (provider, clicked_at) VALUES (?,?)",
        ("airalo", old_ts)
    )
    conn.commit()
    conn.close()
    # days=30 window should exclude it
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    assert stats == []
```

- [ ] **Step 2: Run to verify failure**

```bash
cd "D:\השוואת MASS MARKET"
pytest tests/test_db.py::test_log_affiliate_click_basic -v
```

Expected: `ImportError: cannot import name 'log_affiliate_click'`

- [ ] **Step 3: Add `affiliate_clicks` table to `init_db()`**

In `db.py`, inside `init_db()`, find the line that ends with `CREATE INDEX IF NOT EXISTS idx_news_carrier` and the line after it. Add the new table definition to the executescript block, right after the news_articles table:

```python
            CREATE TABLE IF NOT EXISTS affiliate_clicks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                provider   TEXT NOT NULL,
                plan_id    TEXT,
                country    TEXT,
                clicked_at TEXT NOT NULL,
                ip_hash    TEXT
            );
```

- [ ] **Step 4: Add `timedelta` to the datetime import at the top of `db.py`**

Change:
```python
from datetime import datetime, timezone
```
To:
```python
from datetime import datetime, timezone, timedelta
```

- [ ] **Step 5: Add `log_affiliate_click()` and `get_affiliate_stats()` after `get_news_articles()`**

```python
def log_affiliate_click(provider, plan_id=None, country=None, ip_hash=None, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO affiliate_clicks (provider, plan_id, country, clicked_at, ip_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (provider, plan_id, country, datetime.now(timezone.utc).isoformat(), ip_hash)
        )
        conn.commit()
    finally:
        conn.close()


def get_affiliate_stats(days=30, db_path=None):
    conn = _connect(db_path)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT provider, date(clicked_at) AS date, COUNT(*) AS clicks
               FROM affiliate_clicks
               WHERE clicked_at >= ?
               GROUP BY provider, date(clicked_at)
               ORDER BY date DESC, clicks DESC""",
            (cutoff,)
        ).fetchall()
        return [{"provider": r[0], "date": r[1], "clicks": r[2]} for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_db.py::test_log_affiliate_click_basic tests/test_db.py::test_log_affiliate_click_optional_fields tests/test_db.py::test_get_affiliate_stats_groups_by_provider tests/test_db.py::test_get_affiliate_stats_respects_days_window -v
```

Expected: 4 PASSED

- [ ] **Step 7: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add affiliate_clicks table and CRUD functions"
```

---

## Task 2: Flask — `/go/<provider>/<plan_id>` redirect endpoint

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_app.py`:

```python
from db import log_affiliate_click, get_affiliate_stats

def test_affiliate_redirect_known_provider(client):
    """Should redirect and log the click."""
    with patch("app.load_config") as mock_cfg:
        mock_cfg.return_value = {
            "affiliate": {
                "airalo": {"tag": "TEST", "base_url": "https://www.airalo.com/?ref=TEST"}
            },
            "api_key": "test-key"
        }
        resp = client.get("/go/airalo/israel-1gb-7days")
    assert resp.status_code == 302
    assert "airalo.com" in resp.headers["Location"]

def test_affiliate_redirect_unknown_provider_uses_fallback(client):
    """Unknown provider falls back silently — no 404, no crash."""
    with patch("app.load_config") as mock_cfg:
        mock_cfg.return_value = {"affiliate": {}, "api_key": "test-key"}
        resp = client.get("/go/unknownprovider/some-plan")
    assert resp.status_code == 302

def test_affiliate_redirect_logs_click(client):
    """Click is persisted to DB."""
    with patch("app.load_config") as mock_cfg:
        mock_cfg.return_value = {
            "affiliate": {
                "holafly": {"tag": "moca", "base_url": "https://esim.holafly.com/?ref=moca"}
            },
            "api_key": "test-key"
        }
        client.get("/go/holafly/france-5gb")
    db_path = client.application.config["TEST_DB_PATH"]
    stats = get_affiliate_stats(days=1, db_path=db_path)
    assert any(s["provider"] == "holafly" for s in stats)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_app.py::test_affiliate_redirect_known_provider -v
```

Expected: `FAILED` — 404 (route not defined yet)

- [ ] **Step 3: Add `redirect` to Flask imports in `app.py`**

Change line 11:
```python
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort
```
To:
```python
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect
```

- [ ] **Step 4: Add `log_affiliate_click` and `get_affiliate_stats` to the db import in `app.py`**

Find the line that imports db functions (around line 22):
```python
               upsert_news_articles, get_news_articles
```
Change it to:
```python
               upsert_news_articles, get_news_articles,
               log_affiliate_click, get_affiliate_stats
```

- [ ] **Step 5: Add the redirect endpoint to `app.py`**

Add after the `/api/news` endpoint (around line 420):

```python
_AFFILIATE_FALLBACK_URLS = {
    "airalo":     "https://www.airalo.com",
    "holafly":    "https://esim.holafly.com",
    "saily":      "https://saily.com",
    "globalesim": "https://globalesim.com",
}

@app.route("/go/<provider>")
@app.route("/go/<provider>/<plan_id>")
def affiliate_redirect(provider, plan_id=None):
    from hashlib import sha256
    ip      = request.remote_addr or ""
    ip_hash = sha256(ip.encode()).hexdigest()
    country = request.args.get("country")

    log_affiliate_click(provider, plan_id=plan_id, country=country,
                        ip_hash=ip_hash, db_path=_db_path())

    cfg       = load_config()
    affiliate = cfg.get("affiliate", {}).get(provider)
    if affiliate:
        return redirect(affiliate["base_url"], 302)

    fallback = _AFFILIATE_FALLBACK_URLS.get(provider, "https://lucent-kulfi-f037ad.netlify.app")
    return redirect(fallback, 302)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_app.py::test_affiliate_redirect_known_provider tests/test_app.py::test_affiliate_redirect_unknown_provider_uses_fallback tests/test_app.py::test_affiliate_redirect_logs_click -v
```

Expected: 3 PASSED

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: add /go/<provider>/<plan_id> affiliate redirect endpoint"
```

---

## Task 3: Flask — `/api/affiliate/stats` endpoint

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_app.py`:

```python
def test_affiliate_stats_requires_api_key(client):
    resp = client.get("/api/affiliate/stats")
    assert resp.status_code == 401

def test_affiliate_stats_returns_data(client):
    db_path = client.application.config["TEST_DB_PATH"]
    log_affiliate_click("airalo", plan_id="test", db_path=db_path)
    log_affiliate_click("airalo", plan_id="test", db_path=db_path)
    log_affiliate_click("holafly", db_path=db_path)
    resp = client.get("/api/affiliate/stats?days=30",
                      headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    data = resp.get_json()
    providers = {r["provider"]: r["clicks"] for r in data}
    assert providers.get("airalo") == 2
    assert providers.get("holafly") == 1
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_app.py::test_affiliate_stats_requires_api_key -v
```

Expected: `FAILED` — 404

- [ ] **Step 3: Add the stats endpoint to `app.py`**, right after the `affiliate_redirect` endpoint:

```python
@app.route("/api/affiliate/stats")
@require_api_key
def api_affiliate_stats():
    days  = min(int(request.args.get("days", 30)), 365)
    stats = get_affiliate_stats(days=days, db_path=_db_path())
    return jsonify(stats)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_app.py::test_affiliate_stats_requires_api_key tests/test_app.py::test_affiliate_stats_returns_data -v
```

Expected: 2 PASSED

- [ ] **Step 5: Run the full test suite to check nothing regressed**

```bash
pytest tests/ -v
```

Expected: all tests PASSED (or only pre-existing failures)

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: add /api/affiliate/stats endpoint (admin-only)"
```

---

## Task 4: Frontend — PlanCard affiliate button

**Files:**
- Modify: `mass-market-app/src/components/PlanCard.jsx`

- [ ] **Step 1: Add `AFFILIATE_PROVIDERS` set and `slugify()` helper**

At the top of `PlanCard.jsx`, after the imports, add:

```js
const AFFILIATE_PROVIDERS = new Set(['airalo', 'holafly', 'saily', 'globalesim'])

function slugify(str) {
  if (!str) return 'plan'
  return str
    .toLowerCase()
    .replace(/[–—]/g, '-')
    .replace(/\s+/g, '-')
    .replace(/[^\w-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}
```

- [ ] **Step 2: Replace the provider link button for affiliate plans**

Find the existing provider link block in `PlanCard.jsx` (the `{plan.url && ...}` block near the bottom that renders "תנאי התוכנית"). Replace it with:

```jsx
{plan.url && (
  <div className="mt-auto pt-3">
    {isGlobal && AFFILIATE_PROVIDERS.has(plan.carrier) ? (
      <div>
        <a
          href={`/go/${plan.carrier}/${slugify(plan.plan_name)}?country=${encodeURIComponent(plan.extras?.[0] || '')}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-1.5 w-full text-xs text-white bg-[#5c3317] rounded-lg py-1.5 font-medium transition-colors hover:bg-[#7a4520]"
          onClick={(e) => e.stopPropagation()}
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
            <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
          </svg>
          רכישה
        </a>
        <p className="text-center text-[10px] text-[#a08060] mt-1">דרך MOCA</p>
      </div>
    ) : (
      <a
        href={plan.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-center gap-1.5 w-full text-xs text-moca-sub hover:text-moca-bolt border border-moca-border/40 rounded-lg py-1.5 transition-colors hover:bg-moca-cream"
        onClick={(e) => e.stopPropagation()}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/>
          <line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
        תנאי התוכנית
      </a>
    )}
  </div>
)}
```

- [ ] **Step 3: Build and verify no errors**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run build 2>&1 | tail -5
```

Expected: `✓ built in X.XXs`

- [ ] **Step 4: Commit**

```bash
cd "D:\השוואת MASS MARKET"
git add mass-market-app/src/components/PlanCard.jsx mass-market-app/dist/
git commit -m "feat: affiliate purchase button on global eSIM plan cards"
```

---

## Task 5: Frontend — SettingsPage Affiliate analytics tab

**Files:**
- Modify: `mass-market-app/src/lib/api.js`
- Modify: `mass-market-app/src/pages/SettingsPage.jsx`

- [ ] **Step 1: Add `getAffiliateStats` to `api.js`**

In `mass-market-app/src/lib/api.js`, add inside the api object (alongside `getNews`):

```js
getAffiliateStats: (days = 30) =>
  fetchApi(`/api/affiliate/stats?days=${days}`),
```

- [ ] **Step 2: Add affiliate state and data-fetching to `SettingsPage.jsx`**

Add these imports at the top of `SettingsPage.jsx` (alongside existing imports):

```js
import { useState, useEffect, useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
```

Add this state block inside the component, after the existing state declarations:

```js
const [activeTab, setActiveTab]             = useState('users')
const [affiliateStats, setAffiliateStats]   = useState([])
const [affiliateDays, setAffiliateDays]     = useState(30)
const [affiliateLoading, setAffiliateLoading] = useState(false)

const loadAffiliateStats = async () => {
  setAffiliateLoading(true)
  try {
    const data = await api.getAffiliateStats(affiliateDays)
    setAffiliateStats(data)
  } catch {}
  setAffiliateLoading(false)
}

useEffect(() => {
  if (activeTab === 'affiliate') loadAffiliateStats()
}, [activeTab, affiliateDays])
```

Add this computed value after the state block (derives chart data from raw stats):

```js
const AFFILIATE_COMMISSION = { airalo: 0.10, holafly: 0.12, saily: 0.10, globalesim: 0.10 }
const AFFILIATE_AVG_ORDER  = { airalo: 18,   holafly: 20,   saily: 16,   globalesim: 15   }

const affiliateSummary = useMemo(() => {
  const byProvider = {}
  affiliateStats.forEach(({ provider, clicks }) => {
    byProvider[provider] = (byProvider[provider] || 0) + clicks
  })
  return Object.entries(byProvider).map(([provider, clicks]) => ({
    provider,
    clicks,
    estimatedUsd: Math.round(
      clicks * 0.08 * (AFFILIATE_AVG_ORDER[provider] || 15) * (AFFILIATE_COMMISSION[provider] || 0.10) * 100
    ) / 100
  }))
}, [affiliateStats])

const affiliateChartData = useMemo(() => {
  const byDate = {}
  affiliateStats.forEach(({ date, clicks }) => {
    byDate[date] = (byDate[date] || 0) + clicks
  })
  return Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, clicks]) => ({ date, clicks }))
}, [affiliateStats])
```

- [ ] **Step 3: Add the tab bar and affiliate panel to the JSX**

At the very top of the return statement in `SettingsPage.jsx`, before the existing content, wrap it with tab navigation:

```jsx
return (
  <div>
    {/* Tab bar */}
    <div className="flex gap-2 mb-6 border-b border-moca-border/40 pb-2">
      {[
        { id: 'users',     label: 'משתמשים' },
        { id: 'scrape',    label: 'עדכון נתונים' },
        { id: 'affiliate', label: 'Affiliate' },
      ].map(t => (
        <button
          key={t.id}
          onClick={() => setActiveTab(t.id)}
          className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors
            ${activeTab === t.id
              ? 'bg-[#5c3317] text-white border-[#5c3317]'
              : 'bg-white text-[#5c3317] border-[#d4bfa8] hover:bg-[#f5ede0]'}`}
        >
          {t.label}
        </button>
      ))}
    </div>

    {/* Users tab — move the entire existing return() content here */}
    {activeTab === 'users' && (
      <div>
        {/* Cut everything from the existing return() — the user management
            heading, add-user form, users table, delete/toggle buttons —
            and paste it here verbatim. Do not change any of that code. */}
      </div>
    )}

    {/* Scrape tab — move scrape trigger section here */}
    {activeTab === 'scrape' && (
      <div>
        {/* Cut the scrape-trigger buttons block (the section with
            triggerScrape / scraping state) from the existing JSX
            and paste it here verbatim. */}
      </div>
    )}

    {/* Affiliate tab */}
    {activeTab === 'affiliate' && (
      <div>
        {/* Day range selector */}
        <div className="flex gap-2 mb-4 items-center">
          <span className="text-sm text-[#8b6b52] font-medium">תקופה:</span>
          {[7, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setAffiliateDays(d)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
                ${affiliateDays === d
                  ? 'bg-[#5c3317] text-white border-[#5c3317]'
                  : 'bg-white text-[#5c3317] border-[#d4bfa8] hover:bg-[#f5ede0]'}`}
            >
              {d} ימים
            </button>
          ))}
        </div>

        {affiliateLoading && <p className="text-sm text-gray-400">טוען...</p>}

        {!affiliateLoading && (
          <>
            {/* Summary table */}
            <table className="w-full text-sm mb-6 border-separate border-spacing-y-1">
              <thead>
                <tr className="text-[#8b6b52] text-right text-xs">
                  <th className="font-medium pb-2">ספק</th>
                  <th className="font-medium pb-2">קליקים</th>
                  <th className="font-medium pb-2">הכנסה משוערת</th>
                </tr>
              </thead>
              <tbody>
                {affiliateSummary.length === 0 && (
                  <tr><td colSpan={3} className="text-center text-gray-400 py-4">אין נתונים</td></tr>
                )}
                {affiliateSummary.map(row => (
                  <tr key={row.provider} className="bg-white rounded-lg">
                    <td className="px-3 py-2 rounded-r-lg font-medium">{row.provider}</td>
                    <td className="px-3 py-2">{row.clicks}</td>
                    <td className="px-3 py-2 rounded-l-lg text-green-700 font-medium">${row.estimatedUsd}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Clicks over time chart */}
            {affiliateChartData.length > 0 && (
              <div className="bg-white rounded-xl border border-moca-border/40 p-4">
                <p className="text-sm font-medium text-[#5c3317] mb-3">קליקים לפי יום</p>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={affiliateChartData}>
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                    <Tooltip />
                    <Line type="monotone" dataKey="clicks" stroke="#5c3317" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </div>
    )}
  </div>
)
```

> **Note:** The existing JSX in SettingsPage (user management form, scrape buttons) needs to be moved inside the `users` and `scrape` tab `<div>` wrappers respectively. Keep all existing logic exactly as-is; only reorganize which tab it renders under.

- [ ] **Step 4: Build**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run build 2>&1 | tail -5
```

Expected: `✓ built in X.XXs`

- [ ] **Step 5: Commit**

```bash
cd "D:\השוואת MASS MARKET"
git add mass-market-app/src/lib/api.js mass-market-app/src/pages/SettingsPage.jsx mass-market-app/dist/
git commit -m "feat: affiliate analytics tab in SettingsPage"
```

---

## Task 6: Seed `config.json` with affiliate placeholder block

**Files:**
- Modify: `config.json` (local only — not committed to git)

- [ ] **Step 1: Add the affiliate block to `config.json`**

Open `config.json` and add the following key at the top level (alongside existing keys):

```json
"affiliate": {
  "airalo": {
    "tag": "REPLACE_WITH_REAL_TAG",
    "base_url": "https://www.airalo.com/?ref=REPLACE_WITH_REAL_TAG"
  },
  "holafly": {
    "tag": "REPLACE_WITH_REAL_TAG",
    "base_url": "https://esim.holafly.com/?ref=REPLACE_WITH_REAL_TAG"
  },
  "saily": {
    "tag": "REPLACE_WITH_REAL_TAG",
    "base_url": "https://saily.com/?ref=REPLACE_WITH_REAL_TAG"
  },
  "globalesim": {
    "tag": "REPLACE_WITH_REAL_TAG",
    "base_url": "https://globalesim.com/?ref=REPLACE_WITH_REAL_TAG"
  }
}
```

- [ ] **Step 2: Restart Flask**

```bash
wmic process where "name='python.exe'" get processid,commandline
wmic process where processid=<PID> delete
cd "D:\השוואת MASS MARKET"
python app.py
```

- [ ] **Step 3: Manual smoke test**

Open browser → `http://localhost:5000/go/airalo/test-plan`  
Expected: redirected to `https://www.airalo.com/?ref=REPLACE_WITH_REAL_TAG`

Then check SettingsPage → Affiliate tab shows 1 click for airalo.

---

## Post-Implementation: Replace placeholder tags

After registering at each affiliate program (see spec for URLs), replace each `REPLACE_WITH_REAL_TAG` in `config.json` with the real tag provided by the program. No code changes needed — Flask reads `config.json` live.
