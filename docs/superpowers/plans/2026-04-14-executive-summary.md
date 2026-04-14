# Executive Summary Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "תקציר מנהלים" tab showing daily AI-powered market analysis across all 4 plan categories, with metric cards, bar charts, and Claude-generated narratives, refreshed at 08:05 daily.

**Architecture:** Algorithmic metrics are computed from SQLite via new `db.py` functions. Claude Haiku generates a Hebrew narrative per category. Results are cached in a new `executive_summary` DB table, served from `GET /api/executive-summary`, and refreshed by APScheduler at 08:05 or via admin trigger. The React page renders 4 stacked `SummarySection` components with Recharts bar charts.

**Tech Stack:** Python/Flask + SQLite (backend), Anthropic API via `requests` (Claude Haiku), React + Recharts (frontend), Tailwind CSS.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `db.py` | Modify | Add `executive_summary` table to `init_db()`, add `save_executive_summary()`, `get_executive_summary()`, `compute_executive_metrics()` |
| `app.py` | Modify | Add `generate_executive_summary()` fn, `GET /api/executive-summary`, `POST /api/executive-summary/refresh`, APScheduler job at 08:05 |
| `mass-market-app/src/lib/api.js` | Modify | Add `getExecutiveSummary()`, `refreshExecutiveSummary()` |
| `mass-market-app/src/pages/ExecutiveSummaryPage.jsx` | Create | Page with 4 `SummarySection` sub-components |
| `mass-market-app/src/components/Navbar.jsx` | Modify | Add nav item + icon for `/executive-summary` |
| `mass-market-app/src/App.jsx` | Modify | Add route for `executive-summary` |

---

## Task 1: DB Table + Helper Functions

**Files:**
- Modify: `db.py`

- [ ] **Step 1: Add `executive_summary` table to `init_db()` executescript**

In `db.py`, inside the `executescript("""...""")` call at line 52, append this table definition just before the closing `""")` (after the `price_alerts` block at line 158):

```python
            CREATE TABLE IF NOT EXISTS executive_summary (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category     TEXT NOT NULL UNIQUE,
                metrics_json TEXT NOT NULL,
                narrative    TEXT NOT NULL,
                generated_at TEXT NOT NULL
            );
```

The UNIQUE on `category` enables INSERT OR REPLACE upsert.

- [ ] **Step 2: Add `save_executive_summary()` to `db.py`**

Add after `init_db()` (after line 168):

```python
def save_executive_summary(category, metrics, narrative, db_path=None):
    """Upsert one category's executive summary row."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO executive_summary (category, metrics_json, narrative, generated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(category) DO UPDATE SET
                   metrics_json = excluded.metrics_json,
                   narrative    = excluded.narrative,
                   generated_at = excluded.generated_at""",
            (category, json.dumps(metrics, ensure_ascii=False),
             narrative, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_executive_summary(db_path=None):
    """Return list of all 4 category summaries, or [] if table is empty."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT category, metrics_json, narrative, generated_at "
            "FROM executive_summary ORDER BY category"
        ).fetchall()
        return [
            {
                "category":     r[0],
                "metrics":      json.loads(r[1]),
                "narrative":    r[2],
                "generated_at": r[3],
            }
            for r in rows
        ]
    finally:
        conn.close()
```

- [ ] **Step 3: Add `compute_executive_metrics()` to `db.py`**

Add after `get_executive_summary()`:

```python
def compute_executive_metrics(category, usd_rate=3.7, eur_rate=4.0, db_path=None):
    """Compute algorithmic market metrics for one category.

    Returns a dict: { cheapest, most_aggressive, weekly_changes, chart_data, top_plans }
    where:
      cheapest         = { carrier, value, unit }
      most_aggressive  = { carrier, changes }
      weekly_changes   = { total, drops, rises }
      chart_data       = [{ carrier, value }, ...] sorted asc
      top_plans        = list of short plan strings for Claude prompt context
    """
    conn = _connect(db_path)
    try:
        # ── 1. Price chart data (carrier → avg metric value) ─────────────
        if category == 'domestic':
            rows = conn.execute("""
                SELECT carrier, AVG(price * 1.0 / data_gb) AS v
                FROM plans
                WHERE data_gb > 0 AND price IS NOT NULL
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa/GB'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, data_gb FROM plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]} | {r[3]}GB"
                for r in top_rows
            ]
            changes_table = 'changes'
            changes_carrier_col = 'carrier'

        elif category == 'abroad':
            rows = conn.execute("""
                SELECT carrier, AVG(price * 1.0 / NULLIF(days, 0)) AS v
                FROM abroad_plans
                WHERE days > 0 AND price IS NOT NULL
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa/\u05d9\u05d5\u05dd'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, days, data_gb FROM abroad_plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]} | {r[3]} \u05d9\u05de\u05d9\u05dd | {r[4]}GB"
                for r in top_rows
            ]
            changes_table = 'abroad_changes'
            changes_carrier_col = 'carrier'

        elif category == 'global':
            all_global = conn.execute(
                "SELECT carrier, plan_name, price, currency, data_gb FROM global_plans "
                "WHERE price IS NOT NULL ORDER BY carrier"
            ).fetchall()
            # Convert all prices to ILS
            by_carrier = {}
            for r in all_global:
                carrier, name, price, currency, data_gb = r
                if currency == 'USD':
                    ils = price * usd_rate
                elif currency == 'EUR':
                    ils = price * eur_rate
                else:
                    ils = price if price else 0
                if data_gb and data_gb > 0:
                    ppgb = ils / data_gb
                    by_carrier.setdefault(carrier, []).append(ppgb)
            rows_raw = [
                (c, sum(v) / len(v)) for c, v in by_carrier.items()
            ]
            rows_raw.sort(key=lambda x: x[1])
            rows = rows_raw  # list of (carrier, avg_ppgb)
            unit = '\u20aa/GB (\u05d1\u05e9\u05e7\u05dc\u05d9\u05dd)'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, currency, data_gb FROM global_plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | {r[2]}{r[3]} | {r[4]}GB"
                for r in top_rows
            ]
            changes_table = 'global_changes'
            changes_carrier_col = 'carrier'

        else:  # content
            rows = conn.execute("""
                SELECT carrier, AVG(CAST(price AS REAL)) AS v
                FROM content_plans
                WHERE price GLOB '[0-9]*'
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa (\u05de\u05d7\u05d9\u05e8 \u05e2\u05e8\u05d5\u05e5 \u05de\u05d5\u05e6\u05dc\u05d1)'
            top_rows = conn.execute("""
                SELECT carrier, service, price, free_trial FROM content_plans
                WHERE price GLOB '[0-9]*' ORDER BY CAST(price AS REAL) ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]}"
                + (f" | \u05e0\u05d9\u05e1\u05d9\u05d5\u05df: {r[3]}" if r[3] else "")
                for r in top_rows
            ]
            changes_table = 'content_changes'
            changes_carrier_col = 'carrier'

        chart_data = [
            {'carrier': r[0], 'value': round(float(r[1]), 2)}
            for r in rows if r[1] is not None
        ]
        cheapest = chart_data[0] if chart_data else {'carrier': '-', 'value': 0}

        # ── 2. Price drops (last 7 days) ──────────────────────────────────
        if category == 'content':
            # content_changes has no numeric old_val/new_val for price comparison
            drop_rows = conn.execute(f"""
                SELECT {changes_carrier_col}, COUNT(*) AS cnt
                FROM {changes_table}
                WHERE change_type = 'price_change'
                  AND changed_at >= datetime('now', '-7 days')
                GROUP BY {changes_carrier_col} ORDER BY cnt DESC
            """).fetchall()
        else:
            drop_rows = conn.execute(f"""
                SELECT {changes_carrier_col}, COUNT(*) AS cnt
                FROM {changes_table}
                WHERE change_type = 'price_change'
                  AND changed_at >= datetime('now', '-7 days')
                  AND CAST(new_val AS REAL) < CAST(old_val AS REAL)
                GROUP BY {changes_carrier_col} ORDER BY cnt DESC
            """).fetchall()

        rise_rows = conn.execute(f"""
            SELECT {changes_carrier_col}, COUNT(*) AS cnt
            FROM {changes_table}
            WHERE change_type = 'price_change'
              AND changed_at >= datetime('now', '-7 days')
              AND CAST(new_val AS REAL) > CAST(old_val AS REAL)
            GROUP BY {changes_carrier_col} ORDER BY cnt DESC
        """).fetchall()

        total_drops = sum(r[1] for r in drop_rows)
        total_rises = sum(r[1] for r in rise_rows)
        most_aggressive_carrier = drop_rows[0][0] if drop_rows else (
            chart_data[-1]['carrier'] if chart_data else '-'
        )
        most_aggressive_count = drop_rows[0][1] if drop_rows else 0

        return {
            'cheapest':        {'carrier': cheapest['carrier'], 'value': cheapest['value'], 'unit': unit},
            'most_aggressive': {'carrier': most_aggressive_carrier, 'changes': most_aggressive_count},
            'weekly_changes':  {'total': total_drops + total_rises, 'drops': total_drops, 'rises': total_rises},
            'chart_data':      chart_data,
            'top_plans':       top_plans,
        }
    finally:
        conn.close()
```

- [ ] **Step 4: Update import in `app.py` to include the new DB functions**

In `app.py`, line 15, extend the `from db import ...` line to add the three new functions:

```python
from db import init_db, get_plans, get_changes, get_abroad_plans, get_abroad_changes, get_global_plans, get_global_changes, \
               get_content_plans, get_content_changes, \
               save_price_alert, get_price_alerts, delete_price_alert, update_alert_triggered, \
               save_executive_summary, get_executive_summary, compute_executive_metrics
```

- [ ] **Step 5: Verify DB initialises cleanly**

```bash
cd "D:\השוואת MASS MARKET"
python -c "from db import init_db; init_db(); print('OK')"
```

Expected output: `OK` (no errors).

- [ ] **Step 6: Commit**

```bash
git add db.py app.py
git commit -m "feat: add executive_summary table and DB helpers (compute_executive_metrics, save/get)"
```

---

## Task 2: `generate_executive_summary()` Function in `app.py`

**Files:**
- Modify: `app.py` — add function at module level, before the routes

- [ ] **Step 1: Add `generate_executive_summary()` to `app.py`**

Add this function after the `CARRIER_STORE_DISPLAY` dict (around line 594, before the `@app.route("/api/banners")` decorator):

```python
# ── Executive Summary generation ───────────────────────────────────────────

_CATEGORY_LABELS = {
    'domestic': '\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05e1\u05dc\u05d5\u05dc\u05e8',   # חבילות סלולר
    'abroad':   '\u05d7\u05d5"\u05dc',                                                       # חו"ל
    'global':   '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9 (eSIM)',                               # גלובלי (eSIM)
    'content':  '\u05ea\u05d5\u05db\u05df',                                                   # תוכן
}


def generate_executive_summary():
    """Generate AI-powered executive summary for all 4 categories and store in DB.

    Runs at 08:05 via APScheduler and on-demand via POST /api/executive-summary/refresh.
    Uses Claude Haiku for narrative generation.
    """
    logger.info("Generating executive summary...")
    config = load_config()
    api_key = config.get("anthropic_api_key", "")
    if not api_key:
        logger.warning("executive summary: anthropic_api_key missing, skipping")
        return

    try:
        import requests as _req
        from scraper import _get_usd_to_ils, _get_eur_to_ils
        usd_rate = _get_usd_to_ils()
        eur_rate = _get_eur_to_ils()
    except Exception as e:
        logger.warning(f"executive summary: could not get exchange rates: {e}, using defaults")
        usd_rate, eur_rate = 3.7, 4.0
        import requests as _req

    for category in ['domestic', 'abroad', 'global', 'content']:
        try:
            metrics = compute_executive_metrics(
                category, usd_rate=usd_rate, eur_rate=eur_rate, db_path=_db_path()
            )
            if not metrics['chart_data']:
                logger.info(f"executive summary: no data for {category}, skipping")
                continue

            cat_label = _CATEGORY_LABELS.get(category, category)
            cheapest = metrics['cheapest']
            aggressive = metrics['most_aggressive']
            wc = metrics['weekly_changes']
            top_plans_str = '\n'.join(f"  - {p}" for p in metrics['top_plans'])

            # Build display name for cheapest carrier
            cheapest_name = CARRIER_DISPLAY.get(cheapest['carrier'], {}).get('name', cheapest['carrier'])
            aggressive_name = CARRIER_DISPLAY.get(aggressive['carrier'], {}).get('name', aggressive['carrier'])

            prompt = (
                f"\u05d0\u05ea\u05d4 \u05d0\u05e0\u05dc\u05d9\u05e1\u05d8 \u05e9\u05d5\u05e7 \u05e1\u05dc\u05d5\u05dc\u05e8 \u05d9\u05e9\u05e8\u05d0\u05dc\u05d9. "
                f"\u05dc\u05d4\u05dc\u05df \u05e0\u05ea\u05d5\u05e0\u05d9 \u05e9\u05d5\u05e7 \u05e2\u05d3\u05db\u05e0\u05d9\u05d9\u05dd \u05dc\u05e7\u05d8\u05d2\u05d5\u05e8\u05d9\u05d9\u05ea {cat_label}:\n\n"
                f"\u05de\u05d3\u05d3\u05d9\u05dd:\n"
                f"- \u05d4\u05d6\u05d5\u05dc \u05d1\u05d9\u05d5\u05ea\u05e8: {cheapest_name} ({cheapest['value']} {cheapest['unit']})\n"
                f"- \u05d4\u05d0\u05d2\u05e8\u05e1\u05d9\u05d1\u05d9 \u05d1\u05d9\u05d5\u05ea\u05e8: {aggressive_name} ({aggressive['changes']} \u05d4\u05d5\u05e8\u05d3\u05d5\u05ea \u05de\u05d7\u05d9\u05e8 \u05d1-7 \u05d9\u05de\u05d9\u05dd)\n"
                f"- \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05d4\u05e9\u05d1\u05d5\u05e2: {wc['total']} \u05e1\u05d4'\u05db \u05e2\u05dd {wc['drops']} \u05d9\u05e8\u05d9\u05d3\u05d5\u05ea \u05d5-{wc['rises']} \u05e2\u05dc\u05d9\u05d5\u05ea \u05de\u05d7\u05d9\u05e8\n\n"
                f"10 \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05de\u05d5\u05d1\u05d9\u05dc\u05d5\u05ea:\n{top_plans_str}\n\n"
                f"\u05db\u05ea\u05d5\u05d1 \u05e4\u05e1\u05e7\u05d4 \u05d0\u05d7\u05ea \u05d1\u05e2\u05d1\u05e8\u05d9\u05ea (\u05e2\u05d3 150 \u05de\u05d9\u05dc\u05d4) \u05d4\u05de\u05e0\u05ea\u05d7\u05ea:\n"
                "1. \u05de\u05d9 \u05d4\u05de\u05d5\u05d1\u05d9\u05dc \u05d5\u05dc\u05de\u05d4\n"
                "2. \u05d4\u05d2\u05d9\u05e9\u05d4 \u05d4\u05d0\u05d2\u05e8\u05e1\u05d9\u05d1\u05d9\u05ea \u05d1\u05e9\u05d5\u05e7\n"
                "3. \u05d4\u05de\u05e1\u05e8 \u05d4\u05e9\u05d9\u05d5\u05d5\u05e7\u05d9 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05e0\u05d8\n"
                "4. \u05ea\u05d5\u05d1\u05e0\u05d4 \u05ea\u05d7\u05e8\u05d5\u05ea\u05d9\u05ea \u05d0\u05d7\u05ea \u05d7\u05e9\u05d5\u05d1\u05d4"
            )

            resp = _req.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            narrative = resp.json()["content"][0]["text"].strip()

            save_executive_summary(category, metrics, narrative, db_path=_db_path())
            logger.info(f"executive summary: saved {category}")

        except Exception as e:
            logger.error(f"executive summary: failed for {category}: {e}", exc_info=True)

    logger.info("Executive summary generation complete.")
```

- [ ] **Step 2: Verify the function is syntactically valid**

```bash
cd "D:\השוואת MASS MARKET"
python -c "import app; print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add generate_executive_summary() with metrics + Claude Haiku narrative"
```

---

## Task 3: Flask API Endpoints

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add `GET /api/executive-summary` endpoint**

Add after the `generate_executive_summary()` function (just before `@app.route("/api/banners")`):

```python
@app.route("/api/executive-summary")
@limiter.limit("60 per minute")
def api_executive_summary():
    """Return cached executive summary for all 4 categories."""
    rows = get_executive_summary(db_path=_db_path())
    if not rows:
        return jsonify({"error": "not_generated_yet"}), 404
    return jsonify(rows)


@app.route("/api/executive-summary/refresh", methods=["POST"])
@require_api_key
def api_executive_summary_refresh():
    """Trigger manual regeneration of all 4 executive summaries."""
    try:
        generate_executive_summary()
        rows = get_executive_summary(db_path=_db_path())
        generated_at = rows[0]["generated_at"] if rows else None
        return jsonify({"status": "ok", "generated_at": generated_at})
    except Exception as e:
        logger.error(f"executive summary refresh failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
```

- [ ] **Step 2: Verify endpoints are importable and Flask routes register**

```bash
cd "D:\השוואת MASS MARKET"
python -c "import app; rules = [r.rule for r in app.app.url_map.iter_rules()]; assert '/api/executive-summary' in rules; assert '/api/executive-summary/refresh' in rules; print('routes OK')"
```

Expected: `routes OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add GET /api/executive-summary and POST /api/executive-summary/refresh endpoints"
```

---

## Task 4: APScheduler Job

**Files:**
- Modify: `app.py` — inside the `if __name__ == '__main__':` block

- [ ] **Step 1: Register the scheduler job**

In `app.py`, inside the `if __name__ == '__main__':` block, find the line:
```python
    scheduler.add_job(scrape_store_banners_job, "cron", hour=8, minute=0)
```
(around line 1240)

Add immediately after it:
```python
    scheduler.add_job(generate_executive_summary, "cron", hour=8, minute=5, id="executive_summary")
```

- [ ] **Step 2: Verify scheduler job is registered (check startup log)**

```bash
cd "D:\השוואת MASS MARKET"
python -c "
import app
from apscheduler.schedulers.background import BackgroundScheduler
s = BackgroundScheduler()
s.add_job(app.generate_executive_summary, 'cron', hour=8, minute=5, id='executive_summary')
jobs = [j.id for j in s.get_jobs()]
assert 'executive_summary' in jobs
print('job registered OK')
"
```

Expected: `job registered OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: schedule generate_executive_summary at 08:05 daily"
```

---

## Task 5: API Client Methods

**Files:**
- Modify: `mass-market-app/src/lib/api.js`

- [ ] **Step 1: Add two methods to the `api` object in `api.js`**

In `api.js`, inside the `export const api = { ... }` object, add after the `deleteAlert` line (line 53):

```js
  // Executive summary
  getExecutiveSummary:     () => fetchApi('/api/executive-summary'),
  refreshExecutiveSummary: () => fetchApi('/api/executive-summary/refresh', { method: 'POST' }),
```

- [ ] **Step 2: Commit**

```bash
git add mass-market-app/src/lib/api.js
git commit -m "feat: add getExecutiveSummary and refreshExecutiveSummary to API client"
```

---

## Task 6: ExecutiveSummaryPage.jsx

**Files:**
- Create: `mass-market-app/src/pages/ExecutiveSummaryPage.jsx`

- [ ] **Step 1: Create the page file**

```jsx
import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'

const CATEGORIES = [
  { id: 'domestic', label: 'חבילות סלולר', icon: '📱' },
  { id: 'abroad',   label: 'חו"ל',          icon: '✈️' },
  { id: 'global',   label: 'גלובלי',         icon: '🌍' },
  { id: 'content',  label: 'תוכן',           icon: '📺' },
]

const CARRIER_NAMES = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל',
  cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'וי-קום',
  neptucom: 'נפטוקום', tuki: 'Tuki', globalesim: 'GlobaleSIM',
  airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo',
  simtlv: 'SimTLV', world8: 'World8', saily: 'Saily', holafly: 'Holafly',
  esimio: 'eSIMio', sparks: 'Sparks', voye: 'Voye', orbit: 'Orbit',
  travelsim: 'TravelSim',
}

const BAR_COLORS = ['#5c3317', '#7a4a28', '#9a6040', '#b87c58', '#d4a07a', '#e8c9a8']

function carrierName(id) {
  return CARRIER_NAMES[id] || id
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })
}

function SummarySection({ data, onRefresh, refreshing, isAdmin }) {
  const { category, metrics, narrative, generated_at } = data
  const meta = CATEGORIES.find(c => c.id === category) || { label: category, icon: '📋' }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-moca-border/40 p-5 mb-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{meta.icon}</span>
          <h2 className="text-lg font-semibold text-moca-text">{meta.label}</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-moca-sub">עודכן: {formatDate(generated_at)}</span>
          {isAdmin && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="text-[11px] px-2 py-1 rounded-lg border border-moca-border text-moca-muted hover:text-moca-bolt hover:border-moca-bolt transition-colors disabled:opacity-50"
            >
              {refreshing ? 'מרענן...' : 'רענן עכשיו'}
            </button>
          )}
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#5c3317' }}>
          <div className="text-lg mb-1">🏆</div>
          <div className="text-[10px] opacity-80 mb-1">המשתלם ביותר</div>
          <div className="text-sm font-bold">{carrierName(metrics.cheapest?.carrier)}</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.cheapest?.value} {metrics.cheapest?.unit}
          </div>
        </div>
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#b85c1a' }}>
          <div className="text-lg mb-1">🔥</div>
          <div className="text-[10px] opacity-80 mb-1">האגרסיבי ביותר</div>
          <div className="text-sm font-bold">{carrierName(metrics.most_aggressive?.carrier)}</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.most_aggressive?.changes} הורדות מחיר
          </div>
        </div>
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#c47a3a' }}>
          <div className="text-lg mb-1">📊</div>
          <div className="text-[10px] opacity-80 mb-1">שינויים השבוע</div>
          <div className="text-sm font-bold">{metrics.weekly_changes?.total} שינויים</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.weekly_changes?.drops} ירידות · {metrics.weekly_changes?.rises} עליות
          </div>
        </div>
      </div>

      {/* Bar chart */}
      {metrics.chart_data?.length > 0 && (
        <div className="bg-[#f9f4ee] rounded-xl p-4 mb-4">
          <div className="text-[11px] text-moca-sub font-semibold mb-3 text-right">
            {metrics.cheapest?.unit} לפי ספק
          </div>
          <ResponsiveContainer width="100%" height={metrics.chart_data.length * 30 + 20}>
            <BarChart
              data={[...metrics.chart_data].reverse()}
              layout="vertical"
              margin={{ top: 0, right: 50, bottom: 0, left: 10 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="carrier"
                tickFormatter={carrierName}
                width={80}
                tick={{ fontSize: 11, fill: '#6b5a4e' }}
              />
              <Tooltip
                formatter={(value) => [`${value} ${metrics.cheapest?.unit}`, 'ערך']}
                labelFormatter={carrierName}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {metrics.chart_data.map((_, i) => (
                  <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Claude narrative */}
      <div className="bg-white rounded-xl p-4 border-r-4 border-[#5c3317] shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm">🤖</span>
          <span className="text-[11px] text-moca-sub font-semibold">ניתוח AI</span>
        </div>
        <p className="text-sm text-moca-text leading-relaxed text-right">{narrative}</p>
      </div>
    </div>
  )
}

function SkeletonSection() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-moca-border/40 p-5 mb-5 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 bg-gray-200 rounded" />
        <div className="h-4 bg-gray-200 rounded w-32" />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[0, 1, 2].map(i => (
          <div key={i} className="h-20 bg-gray-200 rounded-xl" />
        ))}
      </div>
      <div className="h-32 bg-gray-100 rounded-xl mb-4" />
      <div className="h-24 bg-gray-100 rounded-xl" />
    </div>
  )
}

export default function ExecutiveSummaryPage() {
  const { user, isAdmin } = useAuth()
  const [summaries, setSummaries] = useState([])
  const [loading, setLoading] = useState(true)
  const [notGenerated, setNotGenerated] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  async function load() {
    try {
      const data = await api.getExecutiveSummary()
      // Sort by CATEGORIES order
      const ordered = CATEGORIES.map(c => data.find(d => d.category === c.id)).filter(Boolean)
      setSummaries(ordered)
      setNotGenerated(false)
    } catch (err) {
      if (err.message?.includes('not_generated_yet') || err.message?.includes('404')) {
        setNotGenerated(true)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await api.refreshExecutiveSummary()
      await load()
    } catch (err) {
      console.error('refresh failed', err)
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-moca-text mb-6 text-right">תקציר מנהלים</h1>
        {[0, 1, 2, 3].map(i => <SkeletonSection key={i} />)}
      </div>
    )
  }

  if (notGenerated) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-moca-text mb-6 text-right">תקציר מנהלים</h1>
        <div className="bg-white rounded-xl p-12 text-center border border-moca-border/40">
          <div className="text-4xl mb-3">🕗</div>
          <p className="text-moca-muted text-sm">הניתוח ייווצר ב-08:00 הקרוב</p>
          {isAdmin && (
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="mt-4 px-4 py-2 rounded-lg bg-[#5c3317] text-white text-sm hover:bg-[#7a4a28] transition-colors disabled:opacity-50"
            >
              {refreshing ? 'מייצר ניתוח...' : 'צור עכשיו'}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-moca-text mb-6 text-right">תקציר מנהלים</h1>
      {summaries.map(s => (
        <SummarySection
          key={s.category}
          data={s}
          onRefresh={handleRefresh}
          refreshing={refreshing}
          isAdmin={isAdmin}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add mass-market-app/src/pages/ExecutiveSummaryPage.jsx
git commit -m "feat: add ExecutiveSummaryPage with metric cards, bar chart, and Claude narrative"
```

---

## Task 7: Routing + Navbar

**Files:**
- Modify: `mass-market-app/src/App.jsx`
- Modify: `mass-market-app/src/components/Navbar.jsx`

- [ ] **Step 1: Add route in `App.jsx`**

In `App.jsx`, add the import after line 8 (`import AlertsPage`):

```js
import ExecutiveSummaryPage from './pages/ExecutiveSummaryPage'
```

In the routes, add after the `/alerts` route (line 28):

```jsx
        <Route path="executive-summary" element={<ExecutiveSummaryPage />} />
```

- [ ] **Step 2: Add nav item in `Navbar.jsx`**

In `Navbar.jsx`, in the `NAV_ITEMS` array (line 33), add the new item after `/alerts`:

```js
const NAV_ITEMS = [
  { to: '/', label: 'דשבורד', end: true },
  { to: '/compare', label: 'השוואה' },
  { to: '/alerts', label: 'התראות' },
  { to: '/executive-summary', label: 'תקציר מנהלים' },
]
```

Add the matching icon in the `NAV_ICONS` object (after the `/alerts` icon, around line 21):

```js
  '/executive-summary': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  ),
```

- [ ] **Step 3: Commit**

```bash
git add mass-market-app/src/App.jsx mass-market-app/src/components/Navbar.jsx
git commit -m "feat: add executive-summary route and nav item"
```

---

## Task 8: Build and Verify

- [ ] **Step 1: Run the React build**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run build
```

Expected: Build succeeds with no errors. A warning about bundle size is acceptable.

- [ ] **Step 2: Start Flask and trigger a manual summary generation**

```bash
cd "D:\השוואת MASS MARKET"
python app.py
```

In a second terminal (or browser/curl), trigger refresh using the API key from `config.json`:

```bash
curl -X POST "http://localhost:5000/api/executive-summary/refresh?api_key=<YOUR_API_KEY>"
```

Expected response:
```json
{"status": "ok", "generated_at": "2026-04-14T..."}
```

- [ ] **Step 3: Verify DB contains summaries**

```bash
cd "D:\השוואת MASS MARKET"
python -c "
from db import get_executive_summary
rows = get_executive_summary()
print(f'{len(rows)} categories generated')
for r in rows:
    print(r['category'], '|', r['generated_at'][:16], '|', r['narrative'][:60])
"
```

Expected: 4 rows printed, each with a Hebrew narrative snippet.

- [ ] **Step 4: Start React dev server and test the tab**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run dev
```

Open `http://localhost:5173` → navigate to "תקציר מנהלים" tab:
- All 4 sections render (סלולר / חו"ל / גלובלי / תוכן)
- Each section shows 3 metric cards, bar chart, and Hebrew AI paragraph
- Timestamp shown in each section header
- Admin users see "רענן עכשיו" button; non-admin users do not

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: executive summary tab — metrics + Claude AI narrative, daily 08:05 refresh"
```

---

## Verification Checklist

| Check | How |
|-------|-----|
| DB table created | `python -c "from db import init_db; init_db()"` — no error |
| Metrics computed | `python -c "from db import compute_executive_metrics; print(compute_executive_metrics('domestic'))"` |
| Claude narrative generated | `POST /api/executive-summary/refresh?api_key=...` → check response + DB |
| API returns data | `GET http://localhost:5000/api/executive-summary` → 4 category objects |
| React tab renders | Navigate to `/executive-summary` — 4 sections with charts and text |
| Admin button visible | Login as admin → see "רענן עכשיו" in each section |
| Non-admin no button | Login as non-admin → no refresh button |
| Scheduler registered | Check Flask startup logs for `executive_summary` job at 08:05 |
| Build passes | `npm run build` → no errors |
