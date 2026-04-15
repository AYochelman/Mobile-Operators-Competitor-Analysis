# History AI Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "ניתוח AI" button to the History tab that sends the currently-filtered changes data to Claude Haiku and displays a Hebrew summary analysis in an expandable inline panel.

**Architecture:** A new `GET /api/history/analyze` Flask route (no auth required — consistent with the other `/api/history/*` endpoints) fetches the carrier's changes, builds a focused prompt, calls Claude Haiku, and returns `{"analysis": "..."}`. HistoryTab.jsx gets two new state variables, a button next to the Excel export, and a panel rendered between the summary cards and the price chart.

**Tech Stack:** Flask, Claude Haiku (`claude-haiku-4-5-20251001`), Recharts (existing), Tailwind CSS tokens (`moca-cream`, `moca-text`, `moca-border`), Lucide-style SVG icons.

---

## File Map

| File | Change |
|------|--------|
| `tests/test_app.py` | Add 3 tests for `/api/history/analyze` |
| `app.py` | Add `GET /api/history/analyze` route after `/api/history/price-series` |
| `mass-market-app/src/lib/api.js` | Add `analyzeHistory()` wrapper |
| `mass-market-app/src/components/HistoryTab.jsx` | Add state, button, panel |

---

## Task 1: Backend route `/api/history/analyze`

**Files:**
- Modify: `tests/test_app.py`
- Modify: `app.py` (after the `/api/history/price-series` route, around line 1268)

### Background: existing patterns

`app.py` uses `_connect()` + `try/finally` (never `with sqlite3.connect()`). Rate limiting decorator is `@limiter.limit('60 per minute')`. The two existing history routes look like:

```python
@app.route('/api/history/changes')
@limiter.limit('60 per minute')
def api_history_changes():
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    ...
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
    ...
    return jsonify({'changes': changes, 'summary': summary})
```

`load_config()` returns the dict from `config.json`. The Anthropic call pattern (from the existing `/api/chat` route at line 1260):

```python
import requests as _req
resp = _req.post(
    'https://api.anthropic.com/v1/messages',
    headers={
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    },
    json={
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 512,
        'system': system_prompt,
        'messages': [{'role': 'user', 'content': question}],
    },
    timeout=30,
)
resp.raise_for_status()
answer = resp.json()['content'][0]['text']
```

### Background: test patterns

`tests/test_app.py` imports:
```python
import json, pytest, os
from app import app as flask_app
from db import init_db, save_plans, save_changes
```

Fixtures use `tmp_path`:
```python
@pytest.fixture
def client_with_history(tmp_path):
    db = str(tmp_path / "test.db")
    flask_app.config["TEST_DB_PATH"] = db
    flask_app.config["TESTING"] = True
    init_db(db_path=db)
    save_plans(PLANS, db_path=db)
    save_changes(HISTORY_CHANGES, db_path=db)
    with flask_app.test_client() as c:
        yield c
```

`HISTORY_CHANGES` (already in test_app.py):
```python
HISTORY_CHANGES = [
    {'carrier': 'partner', 'plan_name': 'Test 50GB', 'change_type': 'price_change',
     'old_val': '40', 'new_val': '45', 'changed_at': '2025-06-01T10:00:00'},
    {'carrier': 'partner', 'plan_name': 'Test 50GB', 'change_type': 'price_change',
     'old_val': '45', 'new_val': '50', 'changed_at': '2025-09-01T10:00:00'},
    {'carrier': 'partner', 'plan_name': 'New Plan', 'change_type': 'new_plan',
     'old_val': None, 'new_val': '30', 'changed_at': '2025-07-01T10:00:00'},
]
```

- [ ] **Step 1: Write 3 failing tests for `/api/history/analyze`**

Add these tests at the end of `tests/test_app.py`:

```python
# --- /api/history/analyze ---------------------------------------------------
from unittest.mock import patch, MagicMock

def test_history_analyze_invalid_plan_type_returns_400(client):
    resp = client.get('/api/history/analyze?carrier=partner&plan_type=bad')
    assert resp.status_code == 400

def test_history_analyze_no_data_returns_null(client):
    resp = client.get('/api/history/analyze?carrier=nobody&plan_type=domestic')
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['analysis'] is None

def test_history_analyze_returns_analysis(client_with_history):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'content': [{'text': 'ניתוח בדיקה'}]}
    mock_resp.raise_for_status.return_value = None
    with patch('requests.post', return_value=mock_resp), \
         patch('app.load_config', return_value={'anthropic_api_key': 'test-key'}):
        resp = client_with_history.get(
            '/api/history/analyze?carrier=partner&plan_type=domestic'
        )
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['analysis'] == 'ניתוח בדיקה'
```

- [ ] **Step 2: Run to verify they fail**

```
cd "D:\השוואת MASS MARKET"
pytest tests/test_app.py::test_history_analyze_invalid_plan_type_returns_400 tests/test_app.py::test_history_analyze_no_data_returns_null tests/test_app.py::test_history_analyze_returns_analysis -v
```

Expected: 3 FAILED (route does not exist yet)

- [ ] **Step 3: Add the route to `app.py`**

Find the line `@app.route('/api/history/price-series')` in `app.py` (~line 1244). Insert the new route **after** the entire `api_history_price_series` function (after its closing `return jsonify({'series': series})`), before the blank line that leads to the push/users routes.

Add this complete function:

```python
@app.route('/api/history/analyze')
@limiter.limit('10 per minute')
def api_history_analyze():
    """AI analysis of historical price changes for a carrier using Claude Haiku."""
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')

    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400

    changes = get_history_changes(carrier, plan_type, from_date, to_date, db_path=_db_path())
    if not changes:
        return jsonify({'analysis': None})

    series = get_history_price_series(carrier, plan_type, from_date=from_date, db_path=_db_path())

    config = load_config()
    api_key = config.get('anthropic_api_key', '')
    if not api_key:
        return jsonify({'error': 'anthropic_api_key missing in config.json'}), 500

    _CARRIER_NAMES = {
        'partner': '\u05e4\u05e8\u05d8\u05e0\u05e8',
        'pelephone': '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df',
        'hotmobile': '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
        'cellcom': '\u05e1\u05dc\u05e7\u05d5\u05dd',
        'mobile019': '019',
        'xphone': 'XPhone',
        'wecom': 'We-Com',
        'neptucom': 'Neptucom',
        'tuki': 'Tuki',
        'globalesim': 'GlobaleSIM',
        'airalo': 'Airalo',
        'pelephone_global': 'GlobalSIM',
        'esimo': 'eSIMo',
        'simtlv': 'SimTLV',
        'world8': '8 World',
        'xphone_global': 'XPhone Global',
        'saily': 'Saily',
        'holafly': 'Holafly',
        'esimio': 'eSIM.io',
        'sparks': 'Sparks',
        'voye': 'VOYE',
        'orbit': 'Orbit',
        'travelsim': 'Travel Sim',
    }
    _TYPE_NAMES = {
        'domestic': '\u05de\u05e7\u05d5\u05de\u05d9',
        'abroad': '\u05d7\u05d5"\u05dc',
        'global': '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9',
        'content': '\u05ea\u05d5\u05db\u05df',
    }

    carrier_display = _CARRIER_NAMES.get(carrier, carrier)
    type_display    = _TYPE_NAMES.get(plan_type, plan_type)

    if from_date and to_date:
        period_display = f'{from_date} \u05e2\u05d3 {to_date}'
    elif from_date:
        period_display = f'\u05de-{from_date} \u05e2\u05d3 \u05d4\u05d9\u05d5\u05dd'
    else:
        period_display = '\u05db\u05dc \u05d4\u05d6\u05de\u05e0\u05d9\u05dd'

    def _price_dir(c):
        try:
            old, new = float(c['old_val']), float(c['new_val'])
            if new > old: return 'up'
            if new < old: return 'down'
            return None
        except (ValueError, TypeError):
            return None

    price_up      = sum(1 for c in changes if c['change_type'] == 'price_change' and _price_dir(c) == 'up')
    price_down    = sum(1 for c in changes if c['change_type'] == 'price_change' and _price_dir(c) == 'down')
    new_plans     = sum(1 for c in changes if c['change_type'] == 'new_plan')
    removed_plans = sum(1 for c in changes if c['change_type'] == 'removed_plan')

    price_changes = [c for c in changes if c['change_type'] == 'price_change'][:20]
    price_lines = '\n'.join(
        f"  {c['plan_name']}: \u20aa{c['old_val']} \u2192 \u20aa{c['new_val']} ({c['changed_at'][:10]})"
        for c in price_changes
    ) or '  \u05d0\u05d9\u05df \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9 \u05de\u05d7\u05d9\u05e8'

    series_lines = '\n'.join(
        f"  {s['plan_name']}: \u20aa{s['points'][0]['price']} \u2192 \u20aa{s['points'][-1]['price']} ({len(s['points']) - 1} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd)"
        for s in series[:10]
    ) if series else '  \u05d0\u05d9\u05df \u05e0\u05ea\u05d5\u05e0\u05d9 \u05de\u05d2\u05de\u05d4'

    question = (
        f"\u05e0\u05ea\u05d7 \u05d0\u05ea \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9 \u05d4\u05de\u05d7\u05d9\u05e8 \u05e9\u05dc {carrier_display}"
        f" \u05d1\u05ea\u05d7\u05d5\u05dd {type_display} \u05d1\u05ea\u05e7\u05d5\u05e4\u05d4 {period_display}.\n\n"
        f"\u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd:\n"
        f'- \u05e1\u05d4"\u05db \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd: {len(changes)}\n'
        f"- \u05e2\u05dc\u05d9\u05d9\u05d5\u05ea \u05de\u05d7\u05d9\u05e8: {price_up}\n"
        f"- \u05d9\u05e8\u05d9\u05d3\u05d5\u05ea \u05de\u05d7\u05d9\u05e8: {price_down}\n"
        f"- \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05d7\u05d3\u05e9\u05d5\u05ea: {new_plans}\n"
        f"- \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05e9\u05d4\u05d5\u05e1\u05e8\u05d5: {removed_plans}\n\n"
        f"\u05e4\u05d9\u05e8\u05d5\u05d8 \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9 \u05de\u05d7\u05d9\u05e8:\n{price_lines}\n\n"
        f"\u05de\u05d2\u05de\u05d5\u05ea \u05de\u05d7\u05d9\u05e8:\n{series_lines}"
    )

    system_prompt = (
        "\u05d0\u05ea\u05d4 \u05de\u05e0\u05ea\u05d7 \u05e0\u05ea\u05d5\u05e0\u05d9 \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05e9\u05dc \u05e1\u05e4\u05e7\u05d9 \u05e1\u05dc\u05d5\u05dc\u05e8 \u05d9\u05e9\u05e8\u05d0\u05dc\u05d9\u05d9\u05dd.\n"
        "\u05e2\u05e0\u05d4 \u05d1\u05e2\u05d1\u05e8\u05d9\u05ea \u05d1\u05dc\u05d1\u05d3, \u05d1\u05e6\u05d5\u05e8\u05d4 \u05ea\u05de\u05e6\u05d9\u05ea\u05d9\u05ea \u05d5\u05d1\u05e8\u05d5\u05e8\u05d4 \u2014 3 \u05e2\u05d3 5 \u05de\u05e9\u05e4\u05d8\u05d9\u05dd.\n"
        "\u05d4\u05ea\u05de\u05e7\u05d3 \u05d1\u05de\u05d2\u05de\u05d5\u05ea, \u05d1\u05d4\u05d9\u05e7\u05e3 \u05d4\u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05d5\u05d1\u05db\u05d9\u05d5\u05d5\u05df \u05d4\u05de\u05d7\u05d9\u05e8\u05d9\u05dd \u05d4\u05db\u05dc\u05dc\u05d9.\n"
        "\u05d0\u05dc \u05ea\u05e6\u05d9\u05d9\u05df \u05ea\u05d0\u05e8\u05d9\u05db\u05d9\u05dd \u05e1\u05e4\u05e6\u05d9\u05e4\u05d9\u05d9\u05dd \u05dc\u05db\u05dc \u05e9\u05d9\u05e0\u05d5\u05d9 \u2014 \u05ea\u05df \u05ea\u05de\u05d5\u05e0\u05d4 \u05db\u05d5\u05dc\u05dc\u05ea."
    )

    try:
        import requests as _req
        resp = _req.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 512,
                'system': system_prompt,
                'messages': [{'role': 'user', 'content': question}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        answer = resp.json()['content'][0]['text']
        return jsonify({'analysis': answer})
    except Exception as e:
        logger.error(f'history analyze failed: {e}', exc_info=True)
        return jsonify({'error': 'analysis failed'}), 500
```

- [ ] **Step 4: Run to verify tests pass**

```
cd "D:\השוואת MASS MARKET"
pytest tests/test_app.py::test_history_analyze_invalid_plan_type_returns_400 tests/test_app.py::test_history_analyze_no_data_returns_null tests/test_app.py::test_history_analyze_returns_analysis -v
```

Expected: 3 PASSED

- [ ] **Step 5: Run full test suite to check no regressions**

```
pytest tests/test_app.py -v
```

Expected: 13 passed (10 existing + 3 new)

- [ ] **Step 6: Commit**

```bash
git add tests/test_app.py app.py
git commit -m "feat: add /api/history/analyze route for AI analysis"
```

---

## Task 2: Frontend — `api.js` wrapper + `HistoryTab.jsx` UI

**Files:**
- Modify: `mass-market-app/src/lib/api.js`
- Modify: `mass-market-app/src/components/HistoryTab.jsx`

### Background: `api.js` pattern

`mass-market-app/src/lib/api.js` exports an `api` object. The existing history wrappers (added just before this task) look like:

```js
getHistoryChanges: (carrier, planType, fromDate = '', toDate = '') => {
  const p = new URLSearchParams({ carrier, plan_type: planType })
  if (fromDate) p.append('from', fromDate)
  if (toDate)   p.append('to', toDate)
  return fetchApi(`/api/history/changes?${p}`)
},
getHistoryPriceSeries: (carrier, planType, planName = '', fromDate = '') => {
  const p = new URLSearchParams({ carrier, plan_type: planType })
  if (planName)  p.append('plan_name', planName)
  if (fromDate)  p.append('from', fromDate)
  return fetchApi(`/api/history/price-series?${p}`)
},
```

### Background: `HistoryTab.jsx` structure

The component state at the top:
```js
const [carrier,  setCarrier]  = useState('pelephone')
const [planType, setPlanType] = useState('domestic')
const [planName, setPlanName] = useState('all')
const [range,    setRange]    = useState('year')
const [changes,  setChanges]  = useState([])
const [series,   setSeries]   = useState([])
const [summary,  setSummary]  = useState(null)
const [loading,  setLoading]  = useState(false)
```

First useEffect (resets planName on carrier/planType change, line 123):
```js
useEffect(() => { setPlanName('all') }, [carrier, planType])
```

Second useEffect (data fetch, line 125–140) runs on `[carrier, planType, planName, range]`.

The JSX layout when `!loading`:
1. Summary cards (`summary && (...)`)   ← insert analysis panel AFTER THIS
2. Price chart (`series.length > 0 && (...)`)
3. Empty state (`changes.length === 0 && (...)`)
4. Change log table (`changes.length > 0 && (...)`)  ← add button inside the header

- [ ] **Step 1: Add `analyzeHistory` to `api.js`**

In `mass-market-app/src/lib/api.js`, find `getHistoryPriceSeries` and add the new wrapper directly after it:

```js
  analyzeHistory: (carrier, planType, fromDate = '', toDate = '') => {
    const p = new URLSearchParams({ carrier, plan_type: planType })
    if (fromDate) p.append('from', fromDate)
    if (toDate)   p.append('to', toDate)
    return fetchApi(`/api/history/analyze?${p}`)
  },
```

- [ ] **Step 2: Add `analysis` and `analyzeLoading` state to `HistoryTab.jsx`**

After the `loading` state (line 120), add:

```js
const [analysis,       setAnalysis]       = useState(null)
const [analyzeLoading, setAnalyzeLoading] = useState(false)
```

- [ ] **Step 3: Reset `analysis` when filters change**

In the first useEffect (line 123), change:
```js
useEffect(() => { setPlanName('all') }, [carrier, planType])
```
to:
```js
useEffect(() => {
  setPlanName('all')
  setAnalysis(null)
  setAnalyzeLoading(false)
}, [carrier, planType])
```

At the **start** of the data-fetch useEffect callback (line 127, inside `if (!carrier) return`), add `setAnalysis(null)` before `setLoading(true)`:
```js
useEffect(() => {
  if (!carrier) return
  setAnalysis(null)        // ← add this line
  setLoading(true)
  ...
}, [carrier, planType, planName, range])
```

- [ ] **Step 4: Add `handleAnalyze` function**

After the `exportToExcel` function (line 170–182), add:

```js
async function handleAnalyze() {
  setAnalyzeLoading(true)
  try {
    const from = rangeToFrom(range)
    const res = await api.analyzeHistory(carrier, planType, from)
    setAnalysis(
      res.analysis ?? 'אין מספיק נתונים לניתוח עבור הפילטרים הנבחרים.'
    )
  } catch {
    setAnalysis('שגיאה בניתוח. נסה שוב.')
  } finally {
    setAnalyzeLoading(false)
  }
}
```

- [ ] **Step 5: Add the analysis panel JSX**

In the `!loading` block, **after** the closing `)}` of the summary cards block (after line 265) and **before** the price chart block, insert:

```jsx
          {/* AI Analysis panel */}
          {analysis !== null && (
            <div className="bg-moca-cream border border-moca-border/60 rounded-xl p-4 mb-4 text-right">
              <div className="flex items-center justify-between mb-2">
                <button
                  onClick={() => setAnalysis(null)}
                  className="text-moca-muted hover:text-moca-text transition-colors"
                  aria-label="סגור ניתוח"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" strokeWidth="2"
                       strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
                <div className="flex items-center gap-2 text-moca-text font-semibold text-sm">
                  <span>ניתוח AI</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" strokeWidth="2"
                       strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 3l1.88 5.76a1 1 0 0 0 .95.69h6.06l-4.9 3.56a1 1 0 0 0-.36 1.12L17.5 20l-4.9-3.56a1 1 0 0 0-1.18 0L6.5 20l1.88-5.87a1 1 0 0 0-.36-1.12L3.11 9.45h6.06a1 1 0 0 0 .95-.69L12 3z"/>
                  </svg>
                </div>
              </div>
              <p className="text-moca-text text-sm leading-relaxed">{analysis}</p>
            </div>
          )}
```

- [ ] **Step 6: Add the "ניתוח AI" button next to the Excel button**

Inside the change log section header `<div className="flex justify-between items-center mb-3">`, add the button after the Excel export button:

```jsx
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleAnalyze}
                    disabled={analyzeLoading || changes.length === 0}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-moca-sub hover:text-moca-text hover:bg-moca-cream transition-all disabled:opacity-40"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" strokeWidth="2"
                         strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="10" rx="2"/>
                      <circle cx="12" cy="5" r="2"/>
                      <path d="M12 7v4"/>
                      <line x1="8" y1="16" x2="8" y2="16"/>
                      <line x1="16" y1="16" x2="16" y2="16"/>
                    </svg>
                    {analyzeLoading ? 'מנתח...' : 'ניתוח AI'}
                  </button>
                  <button
                    onClick={exportToExcel}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-moca-sub hover:text-moca-text hover:bg-moca-cream transition-all"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="7 10 12 15 17 10"/>
                      <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    Excel
                  </button>
                </div>
```

Note: the existing standalone Excel `<button>` must be **replaced** by this `<div>` wrapping both buttons. Remove the original Excel button element.

- [ ] **Step 7: Build and verify**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run build
```

Expected: build completes with no errors (same ~654 modules).

- [ ] **Step 8: Commit**

```bash
cd "D:\השוואת MASS MARKET"
git add mass-market-app/src/lib/api.js mass-market-app/src/components/HistoryTab.jsx mass-market-app/dist/
git commit -m "feat: add AI analysis panel to History tab"
```
