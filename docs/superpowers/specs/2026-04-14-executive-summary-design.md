# Executive Summary Tab — Design Spec

**Date:** 2026-04-14
**Feature:** תקציר מנהלים (Executive Summary)
**Branch:** feature/banners-tab (extend in place)

---

## Context

The MOCA app currently provides raw plan data across four categories (domestic cellular, abroad, global eSIM, content). Users — primarily analysts and decision-makers — have no quick way to understand the competitive landscape without manually browsing plans. This feature adds an "Executive Summary" tab that automatically generates a daily market analysis: who is cheapest, who is pricing aggressively, and what the competitive messaging looks like across all four categories. Analysis is generated via a hybrid approach: algorithmic metric computation + Claude AI narrative layer, cached in the DB and refreshed daily at 08:00.

---

## Navigation

A new top-level nav item **"תקציר מנהלים"** is added to `Navbar.jsx` **to the left of "התראות"**.

Final order (RTL, right → left): דשבורד → השוואה → התראות → **תקציר מנהלים**

Route: `/executive-summary`

---

## Page Layout

The page renders four stacked sections, one per category:

1. 📱 חבילות סלולר
2. ✈️ חו"ל
3. 🌍 גלובלי
4. 📺 תוכן

Each section contains:

### A. Three metric cards (row)
| Card | Icon | Metric |
|------|------|--------|
| המשתלם ביותר | 🏆 | Carrier with lowest avg price/GB; shows carrier name + value |
| האגרסיבי ביותר | 🔥 | Carrier with most price-drop changes in past 7 days; shows carrier name + count |
| שינויים השבוע | 📊 | Total changes count; shows N drops · M rises |

### B. Horizontal bar chart
- Shows average price/GB (or average price for content/abroad) per carrier
- Built with **Recharts** `BarChart` (already used in ComparePage)
- RTL layout: carrier names on right, bars extend left
- Mocha-latte color palette (espresso gradient shades)

### C. Claude AI narrative paragraph
- ~150-word Hebrew paragraph
- Bordered card with `🤖 ניתוח AI` label
- Right border accent in espresso color (`#5c3317`)
- Covers: leading provider, aggressive pricing moves, marketing message, competitive insight

### Section footer
- Timestamp: "עודכן: DD/MM/YYYY 08:00"
- Admin-only "רענן עכשיו" button (visible only when `user.role === 'admin'`)

---

## Backend — Flask (`app.py`)

### New DB table: `executive_summary`

```sql
CREATE TABLE IF NOT EXISTS executive_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,          -- 'domestic' | 'abroad' | 'global' | 'content'
    metrics_json TEXT NOT NULL,       -- JSON: { cheapest, most_aggressive, changes }
    narrative TEXT NOT NULL,          -- Claude-generated Hebrew paragraph
    generated_at TEXT NOT NULL        -- ISO8601 timestamp
);
```

One row per category. On refresh, rows are upserted (INSERT OR REPLACE).

### New API endpoints

**`GET /api/executive-summary`**
- No auth required
- Returns array of 4 objects:
```json
[
  {
    "category": "domestic",
    "metrics": {
      "cheapest": { "carrier": "partner", "value": 0.49, "unit": "₪/GB" },
      "most_aggressive": { "carrier": "pelephone", "changes": 3 },
      "weekly_changes": { "total": 5, "drops": 3, "rises": 2 },
      "chart_data": [
        { "carrier": "partner", "value": 0.49 },
        { "carrier": "pelephone", "value": 0.71 },
        { "carrier": "cellcom", "value": 0.85 }
      ]
    },
    "narrative": "פרטנר שומרת על...",
    "generated_at": "2026-04-14T08:00:00"
  },
  ...
]
```
- If no data yet (first run), returns 404 with `{ "error": "not_generated_yet" }`

**`POST /api/executive-summary/refresh`**
- Protected by `@require_api_key`
- Triggers synchronous regeneration of all 4 categories
- Returns `{ "status": "ok", "generated_at": "..." }`

### New APScheduler job

```python
scheduler.add_job(generate_executive_summary, 'cron', hour=8, minute=5, id='executive_summary')
```

Runs at **08:05** (5 minutes after banner job at 08:00, ensuring fresh data).

---

## Summary Generation Logic (`generate_executive_summary()`)

For each category, a two-step pipeline:

### Step 1 — Algorithmic metrics

**Domestic:**
- Fetch all plans from `plans` table
- Group by carrier, compute `avg(price / data_gb)` where `data_gb IS NOT NULL AND data_gb > 0`
- Cheapest = carrier with lowest avg price/GB
- Fetch `changes` table (last 7 days): count drops vs rises per carrier
- Most aggressive = carrier with highest drop count

**Abroad:**
- Fetch from `abroad_plans`
- Cheapest = carrier with lowest avg `price / data_gb` per day
- Changes from `abroad_changes` (last 7 days)

**Global:**
- Fetch from `global_plans`
- Convert all prices to ILS using exchange rates (`/api/exchange-rates`)
- Cheapest = lowest avg ILS price/GB
- Changes from `global_changes`

**Content:**
- Fetch from `content_plans` where status is active
- Cheapest = carrier with lowest average content package price
- Changes from `content_changes`
- "Aggressive" = carrier with most free_trial offerings

### Step 2 — Claude API narrative

Prompt sent to Claude (`claude-haiku-4-5-20251001` for speed/cost):

```
אתה אנליסט שוק סלולר ישראלי. להלן נתוני שוק עדכניים לקטגוריית {category}:

מדדים:
- הזול ביותר: {cheapest.carrier} ({cheapest.value} {cheapest.unit})
- האגרסיבי ביותר: {most_aggressive.carrier} ({most_aggressive.changes} הורדות מחיר ב-7 ימים)
- שינויים השבוע: {total} סה"כ ({drops} ירידות, {rises} עליות)

5 חבילות מובילות:
{top_plans_list}

כתוב פסקה אחת בעברית (עד 150 מילה) המנתחת:
1. מי המוביל ולמה
2. הגישה האגרסיבית בשוק
3. המסר השיווקי הדומיננטי
4. תובנה תחרותית אחת חשובה
```

Response stored as plain Hebrew text in `narrative` column.

---

## Frontend — React (`mass-market-app/src/`)

### New files
- `pages/ExecutiveSummaryPage.jsx` — main page component

### Modified files
- `components/Navbar.jsx` — add nav item (line ~35)
- `App.jsx` — add route
- `lib/api.js` — add `getExecutiveSummary()` and `refreshExecutiveSummary()`

### `ExecutiveSummaryPage.jsx` structure

```jsx
// State
const [summaries, setSummaries] = useState([])    // array of 4 category objects
const [loading, setLoading] = useState(true)
const [refreshing, setRefreshing] = useState(false)
const { user } = useAuth()

// On mount: fetch /api/executive-summary
// Sections: CATEGORIES.map(cat => <SummarySection key={cat} data={...} />)
```

### `SummarySection` (inline sub-component)

Props: `{ category, metrics, narrative, generated_at }`

Renders:
1. Section header (icon + title + timestamp)
2. 3 metric cards (grid-cols-3)
3. Recharts `BarChart` — reuses pattern from `ComparePage.jsx`
4. Claude narrative card
5. Admin refresh button (conditional on `user?.role === 'admin'`)

### Chart details

Reuses `<ResponsiveContainer>`, `<BarChart>`, `<Bar>` from Recharts (already in `package.json`). Data computed client-side from `metrics.chart_data` array (carrier + value pairs). Bar fill: `#5c3317`. Tooltip shows ₪ value. No legend needed (carrier labels on Y-axis).

### Skeleton loading

While fetching: render 4 placeholder sections with animated pulse divs (matching existing skeleton pattern in `DashboardPage.jsx`).

### Empty state

If API returns 404 (`not_generated_yet`): show centered message "הניתוח ייווצר ב-08:00 הקרוב" with clock icon.

---

## Styling

Follows existing MOCA mocha-latte palette:
- Metric card backgrounds: `#5c3317` / `#b85c1a` / `#c47a3a` (espresso shades)
- Chart bar fill: `#5c3317`
- Narrative card: white background, `border-r-4 border-[#5c3317]`
- Section background: white, `rounded-xl`, subtle shadow
- Page background: inherits `#f9f4ee`

---

## Verification

1. Start Flask: `python app.py`
2. Trigger manual refresh: `POST /api/executive-summary/refresh?api_key=<KEY>`
3. Check DB: `SELECT category, generated_at, narrative FROM executive_summary`
4. Start React dev server: `cd mass-market-app && npm run dev`
5. Navigate to `/executive-summary` — verify 4 sections render with metrics, chart, and narrative
6. Verify admin refresh button appears only when logged in as admin
7. Verify timestamp updates after refresh
8. Run `npm run build` — confirm no build errors
9. Confirm APScheduler job appears in Flask startup logs at 08:05
