# History AI Analysis — Design Spec

**Date:** 2026-04-15  
**Status:** Approved

---

## Context

The History tab (טאב היסטוריה) already shows a price trend chart and a change log table for a selected carrier and plan type. This feature adds an **"ניתוח AI"** button that calls Claude Haiku with the currently-filtered changes data and displays a short Hebrew summary analysis in an expandable panel below the summary cards.

---

## Decisions

| Question | Decision |
|----------|----------|
| Backend approach | New dedicated `/api/history/analyze` endpoint (not `/api/chat` reuse) |
| AI model | Claude Haiku (`claude-haiku-4-5-20251001`) — same as `/api/chat` |
| Analysis display | Expandable inline panel below summary cards (not modal, not sidebar) |
| Icon style | SVG (Lucide-style) — no emoji |
| Panel reset | Auto-resets when carrier / plan_type / range filter changes |

---

## Architecture

```
Frontend (HistoryTab.jsx)
  → GET /api/history/analyze?carrier&plan_type&from&to

Backend (app.py — one new route)
  → calls get_history_changes() from db.py
  → calls get_history_price_series() from db.py
  → builds focused prompt
  → calls Anthropic API (Claude Haiku)
  → returns { "analysis": "..." }
```

No new DB tables, no schema changes.

---

## Backend

### `GET /api/history/analyze`

**Auth:** `@require_auth`  
**Rate limit:** `@limiter.limit('10 per minute')`

**Params:** `carrier`, `plan_type` (default: `domestic`), `from` (ISO date, optional), `to` (ISO date, optional)

**Logic:**
1. Validate `plan_type` — return 400 if invalid
2. Call `get_history_changes(carrier, plan_type, from_date, to_date)` — get full change list
3. Call `get_history_price_series(carrier, plan_type, from_date=from_date)` — get price trend data
4. If no changes found — return `{"analysis": null}` (frontend shows empty state message, no Claude call)
5. Build focused prompt from the data (see Prompt Design below)
6. Call Anthropic API (`claude-haiku-4-5-20251001`, `max_tokens: 512`)
7. Return `{"analysis": "<Hebrew text>"}`

**Response:**
```json
{ "analysis": "פלאפון ביצעה 3 העלאות מחיר ב-6 החודשים האחרונים..." }
```
Or when no data:
```json
{ "analysis": null }
```

**Error handling:** On Anthropic API failure → return 500 with `{"error": "analysis failed"}`

---

### Prompt Design

**System prompt:**
```
אתה מנתח נתוני שינויים של ספקי סלולר ישראלים.
ענה בעברית בלבד, בצורה תמציתית וברורה — 3 עד 5 משפטים.
התמקד במגמות, בהיקף השינויים ובכיוון המחירים הכללי.
אל תציין תאריכים ספציפיים לכל שינוי — תן תמונה כוללת.
```

**User message (built dynamically):**
```
ניתח את שינויי המחיר של {carrier_display} בתחום {plan_type_display} בתקופה {period_display}.

סיכום שינויים:
- סה"כ שינויים: {total}
- עליות מחיר: {price_up}
- ירידות מחיר: {price_down}
- חבילות חדשות: {new_plans}
- חבילות שהוסרו: {removed_plans}

פירוט שינויי מחיר:
{price_change_lines}  ← formatted as "plan_name: ₪old → ₪new (date)"

מגמות מחיר:
{series_summary}  ← "plan_name: ₪X → ₪Y (N שינויים)" per series entry
```

`carrier_display` uses a dict mapping carrier IDs to Hebrew names (e.g. `pelephone` → `פלאפון`).  
`plan_type_display`: `domestic`→`ביתי`, `abroad`→`חו"ל`, `global`→`גלובלי`, `content`→`תוכן`.  
`period_display`: e.g. `"שנה אחרונה"` or `"כל הזמנים"` based on `from` param.

---

## Frontend

### Modified files

| File | Change |
|------|--------|
| `mass-market-app/src/lib/api.js` | Add `analyzeHistory()` wrapper |
| `mass-market-app/src/components/HistoryTab.jsx` | Add button + panel + state |

### `api.js` addition

```js
analyzeHistory: (carrier, planType, fromDate = '', toDate = '') => {
  const p = new URLSearchParams({ carrier, plan_type: planType })
  if (fromDate) p.append('from', fromDate)
  if (toDate)   p.append('to', toDate)
  return fetchApi(`/api/history/analyze?${p}`)
},
```

### `HistoryTab.jsx` — new state

```js
const [analysis, setAnalysis]           = useState(null)   // string | null
const [analyzeLoading, setAnalyzeLoading] = useState(false)
```

`analysis` and `analyzeLoading` reset to `null` / `false` when `carrier`, `planType`, or `range` changes (added to existing reset useEffect).

### Button

Placed alongside the Excel export button in the change log section header:

```jsx
<button onClick={handleAnalyze} disabled={analyzeLoading || changes.length === 0}>
  {/* Bot SVG icon — Lucide style */}
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
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
```

Button is disabled when `changes.length === 0` (nothing to analyze).

### Analysis panel

Rendered below the summary cards, above the chart, only when `analysis !== null`:

```jsx
{analysis && (
  <div className="bg-moca-cream border border-moca-border/60 rounded-xl p-4 text-right">
    <div className="flex items-center justify-between mb-2">
      <button onClick={() => setAnalysis(null)}>
        {/* X close SVG */}
      </button>
      <div className="flex items-center gap-2 text-moca-text font-medium text-sm">
        <span>ניתוח AI</span>
        {/* Sparkles SVG icon */}
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

### Panel placement in layout

```
[Filter bar]
[Summary cards]
[AI analysis panel]  ← new, conditionally rendered
[Price trend chart]
[Change log table + Export button + Analyze button]
```

---

## Empty state

When `analysis === null` after clicking (i.e., backend returned `{"analysis": null}` because no changes exist):

> _"אין מספיק נתונים לניתוח עבור הפילטרים הנבחרים."_

Shown in the panel location briefly, then dismissed.

---

## Verification

1. Start Flask: `python app.py`
2. Hit `GET /api/history/analyze?carrier=pelephone&plan_type=domestic` — returns `{"analysis": "..."}` with Hebrew text
3. Hit with unknown carrier — returns `{"analysis": null}`
4. Hit with invalid plan_type — returns 400
5. Start React dev: `cd mass-market-app && npm run dev`
6. Open History tab → click "ניתוח AI" → panel appears below summary cards with Hebrew text
7. Change carrier → panel disappears (auto-reset)
8. `npm run build` — no errors
