# History Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "היסטוריה" tab to the MOCA Dashboard that shows carrier price-change history as a step-line chart and a sortable change-log table, powered by the existing `changes` / `abroad_changes` / `global_changes` / `content_changes` SQLite tables.

**Architecture:** Two new read-only Flask routes (`/api/history/changes`, `/api/history/price-series`) backed by two new helper functions in `db.py`. A new `HistoryTab.jsx` React component renders filters, summary cards, a Recharts `LineChart` with `stepAfter` interpolation, and a change-log table. The tab is wired into `DashboardPage.jsx` as the 6th entry in `TABS`.

**Tech Stack:** Python/Flask, SQLite, React, Recharts (`LineChart`), xlsx (already installed)

---

## File Map

| Action | File |
|--------|------|
| Modify | `db.py` — add `get_history_changes()`, `get_history_price_series()` |
| Modify | `app.py` — add `/api/history/changes` and `/api/history/price-series` routes |
| Modify | `tests/test_app.py` — add history endpoint tests |
| Modify | `mass-market-app/src/lib/api.js` — add `getHistoryChanges`, `getHistoryPriceSeries` |
| **Create** | `mass-market-app/src/components/HistoryTab.jsx` |
| Modify | `mass-market-app/src/pages/DashboardPage.jsx` — add tab entry, icon, render |

---

## Task 1: `db.py` — `get_history_changes()`

**Files:**
- Modify: `db.py`

The `changes` / `abroad_changes` / `global_changes` tables share the schema `(carrier, plan_name, change_type, old_val, new_val, changed_at)`. `content_changes` uses `service` instead of `plan_name`. Add the table map and first helper at the bottom of `db.py` (before the last blank line).

- [ ] **Step 1: Open `db.py` and scroll to the end — find the last function**

  Confirm the last function defined (likely `get_content_changes`) so you know where to append.

- [ ] **Step 2: Append `_HISTORY_TABLE_MAP` and `get_history_changes()` to `db.py`**

  ```python
  # ---------------------------------------------------------------------------
  # History helpers
  # ---------------------------------------------------------------------------

  _HISTORY_TABLE_MAP = {
      'domestic': ('changes',        'plan_name'),
      'abroad':   ('abroad_changes', 'plan_name'),
      'global':   ('global_changes', 'plan_name'),
      'content':  ('content_changes','service'),
  }


  def get_history_changes(carrier, plan_type='domestic', from_date='', to_date='', db_path=None):
      """Return all change events for a carrier+plan_type, newest first.

      Args:
          carrier:   carrier id string (e.g. 'pelephone')
          plan_type: one of domestic/abroad/global/content
          from_date: ISO date string 'YYYY-MM-DD' (inclusive lower bound, optional)
          to_date:   ISO date string 'YYYY-MM-DD' (inclusive upper bound, optional)
          db_path:   override DB path (used by tests)

      Returns:
          list of dicts with keys: plan_name, change_type, old_val, new_val, changed_at
          Empty list if plan_type is unknown.
      """
      if plan_type not in _HISTORY_TABLE_MAP:
          return []
      table, name_col = _HISTORY_TABLE_MAP[plan_type]
      db_path = db_path or DB_PATH
      with sqlite3.connect(db_path) as conn:
          sql = (f'SELECT {name_col} AS plan_name, change_type, old_val, new_val, changed_at '
                 f'FROM {table} WHERE carrier = ?')
          params = [carrier]
          if from_date:
              sql += ' AND changed_at >= ?'
              params.append(from_date)
          if to_date:
              sql += ' AND changed_at <= ?'
              params.append(to_date + 'T23:59:59')
          sql += ' ORDER BY changed_at DESC'
          rows = conn.execute(sql, params).fetchall()
      return [
          {'plan_name': r[0], 'change_type': r[1], 'old_val': r[2],
           'new_val': r[3], 'changed_at': r[4]}
          for r in rows
      ]
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add db.py
  git commit -m "feat: add get_history_changes() helper to db.py"
  ```

---

## Task 2: `db.py` — `get_history_price_series()`

**Files:**
- Modify: `db.py`

- [ ] **Step 1: Append `get_history_price_series()` to `db.py` after `get_history_changes()`**

  ```python
  def get_history_price_series(carrier, plan_type='domestic', plan_name='', from_date='', db_path=None):
      """Build price time-series from price_change events.

      Args:
          carrier:   carrier id string
          plan_type: one of domestic/abroad/global/content
          plan_name: specific plan to narrow to (empty = all plans)
          from_date: ISO date string lower bound (optional)
          db_path:   override DB path

      Returns:
          list of dicts: [{plan_name: str, points: [{date: str, price: float}]}]
          Capped at 10 plans (those with the most change events).
          First point uses old_val of first event (price before the change).
      """
      if plan_type not in _HISTORY_TABLE_MAP:
          return []
      table, name_col = _HISTORY_TABLE_MAP[plan_type]
      db_path = db_path or DB_PATH
      with sqlite3.connect(db_path) as conn:
          sql = (f"SELECT {name_col} AS plan_name, old_val, new_val, changed_at "
                 f"FROM {table} WHERE carrier = ? AND change_type = 'price_change'")
          params = [carrier]
          if plan_name:
              sql += f' AND {name_col} = ?'
              params.append(plan_name)
          if from_date:
              sql += ' AND changed_at >= ?'
              params.append(from_date)
          sql += ' ORDER BY changed_at ASC'
          rows = conn.execute(sql, params).fetchall()

      plan_events = {}
      for pname, old_val, new_val, ts in rows:
          plan_events.setdefault(pname, []).append(
              {'old': old_val, 'new': new_val, 'date': ts[:10]}
          )

      # Keep the 10 plans with the most change events
      top = sorted(plan_events.items(), key=lambda x: len(x[1]), reverse=True)[:10]
      series = []
      for pname, events in top:
          try:
              pts = [{'date': events[0]['date'], 'price': float(events[0]['old'])}]
              for e in events:
                  pts.append({'date': e['date'], 'price': float(e['new'])})
              series.append({'plan_name': pname, 'points': pts})
          except (ValueError, TypeError):
              continue
      return series
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add db.py
  git commit -m "feat: add get_history_price_series() helper to db.py"
  ```

---

## Task 3: `tests/test_app.py` — history tests

**Files:**
- Modify: `tests/test_app.py`

- [ ] **Step 1: Add import for `save_changes` at the top of `tests/test_app.py`**

  Find the existing imports block (first ~5 lines) and add:
  ```python
  from db import init_db, save_plans, save_changes
  ```

  (replace the existing `from db import init_db, save_plans` line — just add `save_changes` to it)

- [ ] **Step 2: Add test data constant and fixture after the existing `PLANS` constant**

  ```python
  HISTORY_CHANGES = [
      {'carrier': 'partner', 'plan_name': 'Test 50GB', 'change_type': 'price_change',
       'old_val': '40', 'new_val': '45', 'changed_at': '2025-06-01T10:00:00'},
      {'carrier': 'partner', 'plan_name': 'Test 50GB', 'change_type': 'price_change',
       'old_val': '45', 'new_val': '50', 'changed_at': '2025-09-01T10:00:00'},
      {'carrier': 'partner', 'plan_name': 'New Plan', 'change_type': 'new_plan',
       'old_val': None, 'new_val': '30', 'changed_at': '2025-07-01T10:00:00'},
  ]

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

- [ ] **Step 3: Append the six new test functions at the end of `tests/test_app.py`**

  ```python
  # --- /api/history/changes ---------------------------------------------------

  def test_history_changes_empty_for_unknown_carrier(client):
      resp = client.get('/api/history/changes?carrier=nobody&plan_type=domestic')
      data = json.loads(resp.data)
      assert resp.status_code == 200
      assert data['changes'] == []
      assert data['summary']['total'] == 0

  def test_history_changes_invalid_plan_type_returns_400(client):
      resp = client.get('/api/history/changes?carrier=partner&plan_type=invalid')
      assert resp.status_code == 400

  def test_history_changes_returns_data_and_summary(client_with_history):
      resp = client_with_history.get('/api/history/changes?carrier=partner&plan_type=domestic')
      data = json.loads(resp.data)
      assert resp.status_code == 200
      assert data['summary']['total'] == 3
      assert data['summary']['price_up'] == 2   # both price_change events are up
      assert data['summary']['price_down'] == 0
      assert data['summary']['new_plans'] == 1
      assert len(data['changes']) == 3

  # --- /api/history/price-series ----------------------------------------------

  def test_history_price_series_invalid_plan_type_returns_400(client):
      resp = client.get('/api/history/price-series?carrier=partner&plan_type=bad')
      assert resp.status_code == 400

  def test_history_price_series_empty_for_unknown_carrier(client):
      resp = client.get('/api/history/price-series?carrier=nobody&plan_type=domestic')
      data = json.loads(resp.data)
      assert resp.status_code == 200
      assert data['series'] == []

  def test_history_price_series_builds_correct_timeline(client_with_history):
      resp = client_with_history.get(
          '/api/history/price-series?carrier=partner&plan_type=domestic&plan_name=Test+50GB'
      )
      data = json.loads(resp.data)
      assert resp.status_code == 200
      assert len(data['series']) == 1
      pts = data['series'][0]['points']
      # first point = old_val of first change, then new_val of each change
      assert pts[0]['price'] == 40.0
      assert pts[1]['price'] == 45.0
      assert pts[2]['price'] == 50.0
  ```

- [ ] **Step 4: Run all history tests**

  ```bash
  cd "D:\השוואת MASS MARKET"
  pytest tests/test_app.py -k "history" -v
  ```

  Expected: 6 tests PASSED.

- [ ] **Step 5: Commit**

  ```bash
  git add tests/test_app.py
  git commit -m "test: add history endpoint tests"
  ```

---

## Task 4: `app.py` — history routes

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add `get_history_changes, get_history_price_series` to the `db` import line**

  Find the line near the top of `app.py` that imports from `db` (e.g. `from db import get_plans, save_plans, ...`). Add the two new functions to it:

  ```python
  from db import (
      ...,  # keep everything already there
      get_history_changes,
      get_history_price_series,
  )
  ```

- [ ] **Step 2: Append the two new routes to `app.py` (before the `if __name__ == '__main__':` block)**

  ```python
  @app.route('/api/history/changes')
  @limiter.limit('60 per minute')
  def api_history_changes():
      carrier   = request.args.get('carrier', '')
      plan_type = request.args.get('plan_type', 'domestic')
      from_date = request.args.get('from', '')
      to_date   = request.args.get('to', '')
      if plan_type not in ('domestic', 'abroad', 'global', 'content'):
          return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400

      def _is_up(c):
          try:
              return float(c['new_val']) > float(c['old_val'])
          except (ValueError, TypeError):
              return False

      changes = get_history_changes(carrier, plan_type, from_date, to_date, db_path=_db_path())
      summary = {
          'total':         len(changes),
          'price_up':      sum(1 for c in changes if c['change_type'] == 'price_change' and _is_up(c)),
          'price_down':    sum(1 for c in changes if c['change_type'] == 'price_change' and not _is_up(c)),
          'new_plans':     sum(1 for c in changes if c['change_type'] == 'new_plan'),
          'removed_plans': sum(1 for c in changes if c['change_type'] == 'removed_plan'),
      }
      return jsonify({'changes': changes, 'summary': summary})


  @app.route('/api/history/price-series')
  @limiter.limit('60 per minute')
  def api_history_price_series():
      carrier   = request.args.get('carrier', '')
      plan_type = request.args.get('plan_type', 'domestic')
      plan_name = request.args.get('plan_name', '')
      from_date = request.args.get('from', '')
      if plan_type not in ('domestic', 'abroad', 'global', 'content'):
          return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
      series = get_history_price_series(
          carrier, plan_type, plan_name, from_date, db_path=_db_path()
      )
      return jsonify({'series': series})
  ```

- [ ] **Step 3: Run the full test suite to confirm no regressions**

  ```bash
  cd "D:\השוואת MASS MARKET"
  pytest tests/ -v
  ```

  Expected: all tests PASSED (including the 6 new history tests).

- [ ] **Step 4: Commit**

  ```bash
  git add app.py
  git commit -m "feat: add /api/history/changes and /api/history/price-series routes"
  ```

---

## Task 5: `lib/api.js` — API wrapper functions

**Files:**
- Modify: `mass-market-app/src/lib/api.js`

- [ ] **Step 1: Add two new entries inside the `api` object in `lib/api.js`**

  Find the `getArchiveDateRange` line (last entry in the public-read section) and add after it:

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

- [ ] **Step 2: Commit**

  ```bash
  git add mass-market-app/src/lib/api.js
  git commit -m "feat: add getHistoryChanges and getHistoryPriceSeries to api.js"
  ```

---

## Task 6: Create `HistoryTab.jsx`

**Files:**
- Create: `mass-market-app/src/components/HistoryTab.jsx`

- [ ] **Step 1: Create the file with the full component**

  ```jsx
  import { useState, useEffect, useMemo } from 'react'
  import {
    LineChart, Line, XAxis, YAxis, CartesianGrid,
    Tooltip, Legend, ResponsiveContainer,
  } from 'recharts'
  import * as XLSX from 'xlsx'
  import { api } from '../lib/api'
  import Spinner from './ui/Spinner'

  const DOMESTIC_CARRIERS = [
    { id: 'partner',   label: 'פרטנר' },
    { id: 'pelephone', label: 'פלאפון' },
    { id: 'hotmobile', label: 'הוט מובייל' },
    { id: 'cellcom',   label: 'סלקום' },
    { id: 'mobile019', label: '019' },
    { id: 'xphone',    label: 'XPhone' },
    { id: 'wecom',     label: 'We-Com' },
    { id: 'neptucom',  label: 'Neptucom' },
  ]

  const GLOBAL_CARRIERS = [
    { id: 'tuki',             label: 'Tuki' },
    { id: 'globalesim',       label: 'GlobaleSIM' },
    { id: 'airalo',           label: 'Airalo' },
    { id: 'pelephone_global', label: 'GlobalSIM' },
    { id: 'esimo',            label: 'eSIMo' },
    { id: 'simtlv',           label: 'SimTLV' },
    { id: 'world8',           label: '8 World' },
    { id: 'xphone_global',    label: 'XPhone Global' },
    { id: 'saily',            label: 'Saily' },
    { id: 'holafly',          label: 'Holafly' },
    { id: 'esimio',           label: 'eSIM.io' },
    { id: 'sparks',           label: 'Sparks' },
    { id: 'voye',             label: 'VOYE' },
    { id: 'orbit',            label: 'Orbit' },
    { id: 'travelsim',        label: 'Travel Sim' },
  ]

  const CARRIERS_BY_TYPE = {
    domestic: DOMESTIC_CARRIERS,
    abroad:   DOMESTIC_CARRIERS,
    global:   GLOBAL_CARRIERS,
    content:  DOMESTIC_CARRIERS,
  }

  const PLAN_TYPE_LABELS = {
    domestic: 'מקומי',
    abroad:   'חו"ל',
    global:   'גלובלי',
    content:  'תוכן',
  }

  const LINE_COLORS = [
    '#5c3317','#b06030','#e0956a','#d4845a',
    '#c87040','#a05828','#8a4820','#6e3818','#521e08','#3a0e00',
  ]

  const BADGE_CONFIG = {
    price_change: {
      up:   { label: '⬆ עלייה', cls: 'bg-red-100 text-red-700' },
      down: { label: '⬇ ירידה', cls: 'bg-green-100 text-green-700' },
    },
    new_plan:      { label: '✦ חדש',    cls: 'bg-blue-100 text-blue-700' },
    removed_plan:  { label: '✕ הוסר',   cls: 'bg-orange-100 text-orange-700' },
    extras_change: { label: '✎ פרטים',  cls: 'bg-gray-100 text-gray-600' },
    details_change:{ label: '✎ פרטים',  cls: 'bg-gray-100 text-gray-600' },
  }

  function rangeToFrom(range) {
    const now = new Date()
    if (range === '30d')  { const d = new Date(now); d.setDate(d.getDate() - 30);        return d.toISOString().slice(0, 10) }
    if (range === '90d')  { const d = new Date(now); d.setDate(d.getDate() - 90);        return d.toISOString().slice(0, 10) }
    if (range === 'year') { const d = new Date(now); d.setFullYear(d.getFullYear() - 1); return d.toISOString().slice(0, 10) }
    return ''
  }

  function PriceTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-white border border-moca-border rounded-lg p-2 text-xs shadow-sm">
        <div className="font-semibold text-moca-text mb-1">{label}</div>
        {payload.map(p => (
          <div key={p.dataKey} style={{ color: p.color }}>
            {p.name}: ₪{p.value}
          </div>
        ))}
      </div>
    )
  }

  function Badge({ change }) {
    if (change.change_type === 'price_change') {
      const up = parseFloat(change.new_val) > parseFloat(change.old_val)
      const b = BADGE_CONFIG.price_change[up ? 'up' : 'down']
      return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${b.cls}`}>{b.label}</span>
    }
    const b = BADGE_CONFIG[change.change_type] || { label: change.change_type, cls: 'bg-gray-100 text-gray-500' }
    return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${b.cls}`}>{b.label}</span>
  }

  function Delta({ change }) {
    if (change.change_type !== 'price_change') return <span>—</span>
    try {
      const d = parseFloat(change.new_val) - parseFloat(change.old_val)
      const cls = d > 0 ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'
      return <span className={cls}>{d > 0 ? '+' : ''}₪{d.toFixed(0)}</span>
    } catch {
      return <span>—</span>
    }
  }

  export default function HistoryTab() {
    const [carrier,  setCarrier]  = useState('pelephone')
    const [planType, setPlanType] = useState('domestic')
    const [planName, setPlanName] = useState('all')
    const [range,    setRange]    = useState('year')
    const [changes,  setChanges]  = useState([])
    const [series,   setSeries]   = useState([])
    const [summary,  setSummary]  = useState(null)
    const [loading,  setLoading]  = useState(false)

    // Reset plan selection when carrier or plan type changes
    useEffect(() => { setPlanName('all') }, [carrier, planType])

    useEffect(() => {
      if (!carrier) return
      setLoading(true)
      const from = rangeToFrom(range)
      Promise.all([
        api.getHistoryChanges(carrier, planType, from),
        api.getHistoryPriceSeries(carrier, planType, planName === 'all' ? '' : planName, from),
      ])
        .then(([changesRes, seriesRes]) => {
          setChanges(changesRes.changes  || [])
          setSummary(changesRes.summary  || null)
          setSeries(seriesRes.series     || [])
        })
        .catch(() => { setChanges([]); setSummary(null); setSeries([]) })
        .finally(() => setLoading(false))
    }, [carrier, planType, planName, range])

    // Unique plan names from current changes data (for drill-down dropdown)
    const planOptions = useMemo(
      () => [...new Set(changes.map(c => c.plan_name))].sort(),
      [changes]
    )

    // Merge all series onto a shared date axis for Recharts
    const chartData = useMemo(() => {
      if (!series.length) return []
      const dateSet = new Set()
      series.forEach(s => s.points.forEach(p => dateSet.add(p.date)))
      return [...dateSet].sort().map(date => {
        const row = { date }
        series.forEach(s => {
          const before = s.points.filter(p => p.date <= date)
          if (before.length) row[s.plan_name] = before[before.length - 1].price
        })
        return row
      })
    }, [series])

    function exportToExcel() {
      const rows = changes.map(c => ({
        'תאריך':  c.changed_at?.slice(0, 10),
        'חבילה':  c.plan_name,
        'שינוי':  c.change_type,
        'לפני':   c.old_val,
        'אחרי':   c.new_val,
      }))
      const ws = XLSX.utils.json_to_sheet(rows)
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, 'היסטוריה')
      XLSX.writeFile(wb, `history-${carrier}-${planType}.xlsx`)
    }

    const carriers = CARRIERS_BY_TYPE[planType] || DOMESTIC_CARRIERS

    return (
      <div>
        {/* Filter bar */}
        <div className="flex flex-wrap gap-3 items-end mb-4 bg-white border border-moca-border/60 rounded-xl p-3">
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide">מפעיל</span>
            <select
              value={carrier}
              onChange={e => setCarrier(e.target.value)}
              className="border border-moca-border rounded-lg px-2 py-1.5 text-sm bg-moca-cream text-moca-text"
            >
              {carriers.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide">סוג</span>
            <select
              value={planType}
              onChange={e => setPlanType(e.target.value)}
              className="border border-moca-border rounded-lg px-2 py-1.5 text-sm bg-moca-cream text-moca-text"
            >
              {Object.entries(PLAN_TYPE_LABELS).map(([id, label]) => (
                <option key={id} value={id}>{label}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide">חבילה</span>
            <select
              value={planName}
              onChange={e => setPlanName(e.target.value)}
              className="border border-moca-border rounded-lg px-2 py-1.5 text-sm bg-moca-cream text-moca-text min-w-[160px]"
            >
              <option value="all">כל החבילות</option>
              {planOptions.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>

          <div className="flex gap-1.5 items-center">
            {[['30d','30י׳'],['90d','90י׳'],['year','שנה'],['all','הכל']].map(([val, lbl]) => (
              <button
                key={val}
                onClick={() => setRange(val)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  range === val
                    ? 'bg-moca-text text-white border-moca-text'
                    : 'border-moca-border text-moca-sub hover:border-moca-bolt hover:text-moca-bolt'
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="flex justify-center py-10"><Spinner /></div>
        )}

        {!loading && (
          <>
            {/* Summary cards */}
            {summary && (
              <div className="grid grid-cols-4 gap-3 mb-4">
                {[
                  { label: 'שינויי מחיר', value: summary.total,        sub: 'בתקופה הנבחרת', cls: '' },
                  { label: 'עליות',        value: summary.price_up,     sub: 'מחיר עלה',      cls: 'text-red-600' },
                  { label: 'ירידות',       value: summary.price_down,   sub: 'מחיר ירד',      cls: 'text-green-600' },
                  { label: 'חדש / הוסר',  value: `${summary.new_plans} / ${summary.removed_plans}`, sub: 'חבילות', cls: '' },
                ].map(({ label, value, sub, cls }) => (
                  <div key={label} className="bg-white border border-moca-border/60 rounded-xl p-3">
                    <div className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide mb-1">{label}</div>
                    <div className={`text-2xl font-bold ${cls || 'text-moca-text'}`}>{value}</div>
                    <div className="text-[11px] text-moca-muted mt-0.5">{sub}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Price chart — shown only when series data exists */}
            {series.length > 0 && (
              <div className="bg-white border border-moca-border/60 rounded-xl p-4 mb-4">
                <div className="text-sm font-bold text-moca-text mb-0.5">מגמת מחיר (₪)</div>
                <div className="text-xs text-moca-muted mb-3">כל נקודה = שינוי מחיר שזוהה</div>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0e8de" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tickFormatter={v => `₪${v}`} tick={{ fontSize: 10 }} width={45} />
                    <Tooltip content={<PriceTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    {series.map((s, i) => (
                      <Line
                        key={s.plan_name}
                        type="stepAfter"
                        dataKey={s.plan_name}
                        stroke={LINE_COLORS[i % LINE_COLORS.length]}
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        activeDot={{ r: 6 }}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Empty state — no changes at all */}
            {changes.length === 0 && (
              <div className="bg-white border border-moca-border/60 rounded-xl p-8 text-center mb-4">
                <div className="text-moca-muted text-sm">אין נתוני שינויים לתקופה הנבחרת.</div>
                <div className="text-moca-muted text-xs mt-1">הנתונים יצטברו עם הזמן עם כל סריקה.</div>
              </div>
            )}

            {/* Change log table */}
            {changes.length > 0 && (
              <div className="bg-white border border-moca-border/60 rounded-xl p-4">
                <div className="flex justify-between items-center mb-3">
                  <div className="text-sm font-bold text-moca-text">לוג שינויים</div>
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
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b-2 border-moca-border">
                      {['תאריך','חבילה','שינוי','לפני','אחרי','דלתא'].map(h => (
                        <th key={h} className="text-right pb-2 px-2 text-[11px] font-semibold uppercase text-moca-muted tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {changes.map((c, i) => (
                      <tr key={i} className="border-b border-moca-bg hover:bg-moca-bg/50">
                        <td className="py-2 px-2 text-xs text-moca-muted">{c.changed_at?.slice(0, 10)}</td>
                        <td className="py-2 px-2 font-medium">{c.plan_name}</td>
                        <td className="py-2 px-2"><Badge change={c} /></td>
                        <td className="py-2 px-2 text-xs line-through text-moca-muted">{c.old_val ? `₪${c.old_val}` : '—'}</td>
                        <td className="py-2 px-2 font-semibold">{c.new_val ? `₪${c.new_val}` : '—'}</td>
                        <td className="py-2 px-2"><Delta change={c} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add mass-market-app/src/components/HistoryTab.jsx
  git commit -m "feat: add HistoryTab component"
  ```

---

## Task 7: Wire up in `DashboardPage.jsx` + build

**Files:**
- Modify: `mass-market-app/src/pages/DashboardPage.jsx`

- [ ] **Step 1: Add `HistoryTab` import at the top of `DashboardPage.jsx`**

  Find the existing component imports (the block starting `import PlanCard`) and add:
  ```js
  import HistoryTab from '../components/HistoryTab'
  ```

- [ ] **Step 2: Add `history` entry to `TAB_ICONS` object (lines ~65–91)**

  Add after the `banners` entry (before the closing `}`):
  ```js
  history: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
      <polyline points="17 6 23 6 23 12"/>
    </svg>
  ),
  ```

- [ ] **Step 3: Add `history` entry to `TABS` array (lines ~93–99)**

  Add after the `banners` entry (before the closing `]`):
  ```js
  { id: 'history', label: 'היסטוריה' },
  ```

- [ ] **Step 4: Hide the filter strip for the history tab**

  Find the line (around line 501):
  ```jsx
  <div className="mb-4" style={tab === 'banners' ? {display:'none'} : undefined}>
  ```
  Change to:
  ```jsx
  <div className="mb-4" style={tab === 'banners' || tab === 'history' ? {display:'none'} : undefined}>
  ```

- [ ] **Step 5: Render `<HistoryTab />` in the content area**

  Find where the banners tab content renders (search for `tab === 'banners'` in the JSX return). Add directly after it:
  ```jsx
  {tab === 'history' && <HistoryTab />}
  ```

- [ ] **Step 6: Build**

  ```bash
  cd "D:\השוואת MASS MARKET\mass-market-app"
  npm run build
  ```

  Expected: build completes with no errors.

- [ ] **Step 7: Smoke-test in dev server**

  ```bash
  npm run dev
  ```

  Open http://localhost:5173. Click the "היסטוריה" tab. Verify:
  - Tab appears with TrendingUp SVG icon
  - Filter bar renders (carrier / plan type / plan name / range pills)
  - Summary cards show (zeroed out if no data yet)
  - Empty state message shows when no changes exist for the selected filter

- [ ] **Step 8: Commit**

  ```bash
  git add mass-market-app/src/pages/DashboardPage.jsx
  git commit -m "feat: wire up History tab in DashboardPage"
  ```
