# History Tab — Design Spec

**Date:** 2026-04-15  
**Status:** Approved

---

## Context

MOCA scrapes 8 domestic carriers + global eSIM providers twice daily and records every detected price change in dedicated `changes` tables (`changes`, `abroad_changes`, `global_changes`, `content_changes`). This data accumulates over time but currently has no UI surface for trend analysis.

The goal is to add a **"היסטוריה" (History) tab** to the existing Dashboard that lets users analyse historical price fluctuations per carrier and per plan — answering questions like "what did Pelephone do with prices over the last year?"

---

## Decisions

| Question | Decision |
|----------|----------|
| Entry point | New 6th tab in `DashboardPage` TABS array — no navigation changes |
| Plan types | All four: domestic, abroad, global, content |
| Data source | Existing `changes` / `abroad_changes` / `global_changes` / `content_changes` tables (Approach A) |
| Chart type | Recharts `LineChart` with `type="stepAfter"` — prices are discrete steps, not continuous |
| User flow | Default: carrier-level view → drill down to specific plan |

---

## Architecture

```
Frontend (HistoryTab.jsx)
  → GET /api/history/changes?carrier&plan_type&from&to
  → GET /api/history/price-series?carrier&plan_type&plan_name&from

Backend (app.py — two new routes)
  → queries changes tables in db.py
  → no new DB tables, no schema changes
```

---

## Backend

### Route map

```python
TABLE_MAP = {
    'domestic': 'changes',        # plan_name col
    'abroad':   'abroad_changes', # plan_name col
    'global':   'global_changes', # plan_name col
    'content':  'content_changes' # 'service' col (not plan_name)
}
```

`content_changes` uses `service` instead of `plan_name` — the API normalises this to `plan_name` in the response so the frontend is uniform.

---

### `GET /api/history/changes`

**Params:** `carrier`, `plan_type` (default: `domestic`), `from` (ISO date, optional), `to` (ISO date, optional)

**Response:**
```json
{
  "changes": [
    {
      "plan_name": "Pelephone MAX 100GB",
      "change_type": "price_change",
      "old_val": "49",
      "new_val": "54",
      "changed_at": "2026-03-15T10:00:00"
    }
  ],
  "summary": {
    "total": 14,
    "price_up": 9,
    "price_down": 5,
    "new_plans": 3,
    "removed_plans": 2
  }
}
```

Sorted `changed_at DESC`. No pagination needed for now (change frequency is low).  
No `@require_api_key` — read-only endpoint.

---

### `GET /api/history/price-series`

**Params:** `carrier`, `plan_type` (default: `domestic`), `plan_name` (optional, default: all), `from` (ISO date, optional)

**Logic:**
1. Query `price_change` events only, sorted `changed_at ASC`
2. Group by `plan_name`
3. For each plan, build point series:
   - First point: `{date: events[0].changed_at, price: float(events[0].old_val)}` — price *before* first change
   - Each subsequent event adds: `{date: event.changed_at, price: float(event.new_val)}`
4. If `plan_name=all` (default): cap at 10 plans with most change events

**Response:**
```json
{
  "series": [
    {
      "plan_name": "Pelephone MAX 100GB",
      "points": [
        {"date": "2025-04-15", "price": 44},
        {"date": "2025-09-05", "price": 49},
        {"date": "2026-03-15", "price": 54}
      ]
    }
  ]
}
```

---

## Frontend

### New files

| File | Purpose |
|------|---------|
| `mass-market-app/src/components/HistoryTab.jsx` | Full history tab UI |

### Modified files

| File | Change |
|------|--------|
| `mass-market-app/src/pages/DashboardPage.jsx` | Add `history` entry to `TABS` + `TAB_ICONS`; render `<HistoryTab>` when `tab === 'history'` |
| `mass-market-app/src/lib/api.js` | Add `getHistoryChanges()` and `getHistoryPriceSeries()` wrapper functions |

---

### `HistoryTab.jsx` — state

```js
const [carrier, setCarrier] = useState('pelephone')
const [planType, setPlanType] = useState('domestic')
const [planName, setPlanName] = useState('all')
const [range, setRange] = useState('year')     // '30d' | '90d' | 'year' | 'all'
const [changes, setChanges] = useState([])
const [series, setSeries] = useState([])
const [summary, setSummary] = useState(null)
const [loading, setLoading] = useState(false)
```

`range` is converted to a `from` date client-side before the API call.

---

### `HistoryTab.jsx` — layout (4 blocks)

**1. Filter bar**  
Carrier dropdown (same list as Dashboard) · Plan type dropdown · Plan name dropdown (loaded dynamically from changes data) · Date range pills (30י / 90י / שנה / הכל)

**2. Summary cards** (4 cards in a row)  
סה"כ שינויים · עליות מחיר (red) · ירידות מחיר (green) · חבילות חדשות / הוסרו

**3. Price trend chart**  
Recharts `<LineChart>` with `type="stepAfter"` lines.  
- X axis: date  
- Y axis: price in ₪  
- One `<Line>` per plan in `series`  
- Custom dot: rendered only on change events (not every point)  
- Custom tooltip: shows `plan_name`, `₪old → ₪new`, date  
- Max 10 plans simultaneously; mocha-latte colour palette (`#5c3317`, `#b06030`, `#e0956a`, `#d4845a`, `#c87040`, `#a05828`, `#8a4820`, `#6e3818`, `#521e08`, `#3a0e00`)  
- Hidden when `series` is empty (shows empty state instead)

**4. Change log table**  
Columns: תאריך · חבילה · סוג שינוי · לפני · אחרי · דלתא  
Sorted newest-first.  
Badge per change type:
- `price_change` + positive delta → `⬆ עלייה` (red pill)
- `price_change` + negative delta → `⬇ ירידה` (green pill)
- `new_plan` → `✦ חדש` (blue pill)
- `removed_plan` → `✕ הוסר` (orange pill)
- `extras_change` / `details_change` → `✎ פרטים` (grey pill)

Excel export button — same pattern as other tabs.

---

### Tab icon (SVG — TrendingUp, Lucide style)

```jsx
history: (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
    <polyline points="17 6 23 6 23 12"/>
  </svg>
)
```

---

## Empty state

When no data exists for the selected filters (archive is new — expected for a while):

> _"אין נתוני שינויים לתקופה הנבחרת. הנתונים יצטברו עם הזמן עם כל סריקה."_

Chart is hidden; log table shows the message instead.

---

## Verification

1. Start Flask: `python app.py`
2. Hit `GET /api/history/changes?carrier=pelephone&plan_type=domestic` — should return JSON with `changes` array and `summary`
3. Hit `GET /api/history/price-series?carrier=pelephone&plan_type=domestic` — should return `series` array
4. Start React dev server: `cd mass-market-app && npm run dev`
5. Open Dashboard → click "היסטוריה" tab — filter bar, summary cards, chart, and log table should render
6. Select a carrier with known changes → verify chart shows step lines and log shows correct badges
7. Select a specific plan from the plan dropdown → chart should narrow to that plan
8. Run `npm run build` — no TypeScript/ESLint errors
