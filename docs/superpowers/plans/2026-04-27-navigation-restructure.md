# Navigation Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the React app's top navigation from 8–11 flat items to 4 dropdown groups (ניתוח / תובנות / היסטוריה / ניהול), merge `/alerts` and `/notifications` into one tabbed page, add a new `/ai-insights` page, and flatten the mobile bottom-bar to 5 items + "More" sheet.

**Architecture:** Frontend-only React work. No backend changes. Component decomposition: extract existing `AlertsPage` and `NotificationsPage` bodies into reusable tab components, then wrap them in a new tabbed `AlertsPage`. Add an optional `inline` prop to `CarrierAIInsights` so the new `/ai-insights` page can render reports expand-in-place while Dashboard usage stays modal. Two new generic UI components: `NavDropdown` (click-to-open menu) and `MobileMoreSheet` (bottom sheet). Refactor `Navbar` to compose them.

**Tech Stack:** React 18, react-router-dom v6, Tailwind CSS, existing `Modal` and `useAuth`/`useFeatureFlags`/`useVisibleCarriers` hooks. No new dependencies.

**Spec:** [docs/superpowers/specs/2026-04-27-navigation-restructure-design.md](../specs/2026-04-27-navigation-restructure-design.md)

**Verification approach:** This codebase has **no React test runner** (only ESLint + Vite build, plus Python `pytest` for the Flask backend). Each task ends with `npm run build` (must succeed) + a brief manual smoke check at `localhost:5173`. Frequent commits — one per task minimum.

**Working directory for all `npm` commands:** `mass-market-app/`

---

## Task 1: Add `inline` prop to `CarrierAIInsights`

**Files:**
- Modify: `mass-market-app/src/components/CarrierAIInsights.jsx`

Goal: introduce an optional `inline` prop so the new AI Insights page can render expand-in-place. Default `false` preserves existing modal behavior on the Dashboard.

- [ ] **Step 1: Read the current component**

```
Read mass-market-app/src/components/CarrierAIInsights.jsx (full file, 101 lines)
```

Confirm: it exports `CarrierAIInsights({ carrierId })`, has state `open / loading / answer / error`, renders a button + a `<Modal>` with the body.

- [ ] **Step 2: Refactor to extract body and add `inline` branch**

Replace the entire file content with:

```jsx
import { useState, useCallback } from 'react'
import { api } from '../lib/api'
import Modal from './ui/Modal'
import { ALL_CARRIER_LABELS as CARRIER_NAMES } from '../data/carrierLabels'

export default function CarrierAIInsights({ carrierId, inline = false }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState(null)

  const carrierName = CARRIER_NAMES[carrierId] || carrierId

  const loadInsights = useCallback(async () => {
    setLoading(true)
    setError(null)
    setAnswer('')
    const prompt = `תן לי דוח תחרותי תמציתי וממוקד על ${carrierName}.

תוכן רצוי (בסדר הזה):
1. **מצב נוכחי** — מספר חבילות פעילות וטווחי מחירים (ביתי וחו"ל בנפרד)
2. **אסטרטגיה** — מה הספק מנסה לעשות? (תחרות במחיר, פרימיום, data-heavy, חו"ל וכד')
3. **שינויים אחרונים** — מה קרה בחבילות שלו לאחרונה (אם יש בנתונים)
4. **מול המתחרים** — שני משפטים על נקודות חוזק וחולשה ביחס לאחרים
5. **הזדמנויות** — 1-3 פעולות שהמתחרים יכולים לנצל

דרישות איכות (חובה):
- כתוב בעברית תקנית בלבד. אל תמציא מילים. אל תתרגם ישירות מאנגלית — אם אתה לא בטוח במונח, השתמש בעברית פשוטה או השאר באנגלית.
- בדוק כל משפט לפני שאתה כותב אותו. אם משהו נשמע מוזר — נסח מחדש.
- השתמש במונחי הענף הנכונים: "חבילת גלישה", "דקות שיחה", "הודעות SMS", "גלישה בחו\\"ל".`

    try {
      const result = await api.chat(prompt)
      setAnswer(result.response || result.answer || '')
    } catch (err) {
      setError(err.message || 'שגיאה בטעינת הדוח')
    } finally {
      setLoading(false)
    }
  }, [carrierName])

  const Trigger = (
    <button
      onClick={() => {
        if (inline) {
          if (!open) loadInsights()
          setOpen(o => !o)
        } else {
          setOpen(true)
          loadInsights()
        }
      }}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg transition-colors"
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
      </svg>
      {inline && open ? 'הסתר דוח' : `דוח AI על ${carrierName}`}
    </button>
  )

  const Body = (
    <div className="text-right">
      {loading && (
        <div className="flex flex-col items-center py-12 gap-3">
          <div className="animate-spin h-8 w-8 border-4 border-purple-500 border-t-transparent rounded-full" />
          <p className="text-xs text-gray-500">Claude מנתח את הנתונים...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
          <button onClick={loadInsights} className="block mt-2 text-xs text-red-600 underline">נסה שוב</button>
        </div>
      )}

      {!loading && !error && answer && (
        <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
          {answer}
          <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
            <button
              onClick={loadInsights}
              className="text-xs text-purple-600 hover:text-purple-800 transition-colors flex items-center gap-1"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
              רענן דוח
            </button>
            <span className="text-[10px] text-gray-400">נוצר על ידי Claude · {new Date().toLocaleString('he-IL')}</span>
          </div>
        </div>
      )}
    </div>
  )

  if (inline) {
    return (
      <div>
        {Trigger}
        {open && <div className="mt-3 border-t border-gray-100 pt-3">{Body}</div>}
      </div>
    )
  }

  return (
    <>
      {Trigger}
      <Modal open={open} onClose={() => setOpen(false)} title={`דוח תחרותי — ${carrierName}`} maxWidth="max-w-2xl">
        {Body}
      </Modal>
    </>
  )
}
```

> **Note:** If you find that the original component's JSX (button styling, icon SVG paths, prompt text) differs from what's pasted above, **prefer the original strings verbatim** — they were copied from the live component and any drift here is unintentional. The structural changes (extracting `Body`, adding `inline` branch) are what matters.

- [ ] **Step 3: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds with no new warnings.

- [ ] **Step 4: Smoke check existing Dashboard usage**

Open `localhost:5173`, navigate to Dashboard, click any "דוח AI על X" button. Modal should still open and load (existing behavior preserved).

- [ ] **Step 5: Commit**

```bash
cd "D:/השוואת MASS MARKET/.claude/worktrees/eloquent-jackson-116630"
git add mass-market-app/src/components/CarrierAIInsights.jsx
git commit -m "feat(ai-insights): add inline prop to CarrierAIInsights

Default behavior (modal) preserved for Dashboard. New inline mode
expands the report below the trigger button — used by upcoming
/ai-insights page."
```

---

## Task 2: Extract `AlertsPriceTab.jsx`

**Files:**
- Create: `mass-market-app/src/components/alerts/AlertsPriceTab.jsx`

Goal: move the body of `pages/AlertsPage.jsx` into a reusable tab component. The original `AlertsPage.jsx` keeps its current behavior for now — we'll replace it in Task 5. After this task, the new file is unused (no harm).

- [ ] **Step 1: Create directory**

```bash
mkdir -p "mass-market-app/src/components/alerts"
```

- [ ] **Step 2: Create `AlertsPriceTab.jsx`**

Copy `mass-market-app/src/pages/AlertsPage.jsx` to the new path and rename the function:

```bash
cp "mass-market-app/src/pages/AlertsPage.jsx" "mass-market-app/src/components/alerts/AlertsPriceTab.jsx"
```

Then in the new file, change exactly two lines:
1. `export default function AlertsPage()` → `export default function AlertsPriceTab()`
2. Adjust the relative imports (paths went from `../` to `../../`):
   - `'../lib/api'` → `'../../lib/api'`
   - `'../hooks/useAuth'` → `'../../hooks/useAuth'`
   - `'../hooks/useHiddenCarrier'` → `'../../hooks/useHiddenCarrier'`
   - `'../components/ui/Button'` → `'../ui/Button'`
   - `'../components/ui/Badge'` → `'../ui/Badge'`
   - `'../components/ui/SearchableSelect'` → `'../ui/SearchableSelect'`

Use Edit on each import to change the path. Do NOT use `replace_all` — the strings might appear elsewhere in JSX class names.

- [ ] **Step 3: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds. The new file is bundled but unused (no other file imports it yet).

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/src/components/alerts/AlertsPriceTab.jsx
git commit -m "refactor(alerts): extract AlertsPriceTab component

Mirrors current pages/AlertsPage.jsx. Will become a tab inside the
merged AlertsPage in a later task. Currently unused."
```

---

## Task 3: Extract `AlertsWatchlistTab.jsx`

**Files:**
- Create: `mass-market-app/src/components/alerts/AlertsWatchlistTab.jsx`

Goal: move the body of `pages/NotificationsPage.jsx` into a reusable tab component. Same pattern as Task 2.

- [ ] **Step 1: Copy file and rename function**

```bash
cp "mass-market-app/src/pages/NotificationsPage.jsx" "mass-market-app/src/components/alerts/AlertsWatchlistTab.jsx"
```

In the new file, change `export default function NotificationsPage()` → `export default function AlertsWatchlistTab()`.

- [ ] **Step 2: Adjust import paths**

In `mass-market-app/src/components/alerts/AlertsWatchlistTab.jsx`, update:
- `'../lib/api'` → `'../../lib/api'`
- `'../hooks/useWatchlist'` → `'../../hooks/useWatchlist'`
- `'../components/ui/Badge'` → `'../ui/Badge'`
- `'../components/ui/Spinner'` → `'../ui/Spinner'`
- `'../data/carrierLabels'` → `'../../data/carrierLabels'`

Use Edit per import.

- [ ] **Step 3: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/src/components/alerts/AlertsWatchlistTab.jsx
git commit -m "refactor(alerts): extract AlertsWatchlistTab component

Mirrors current pages/NotificationsPage.jsx. Will become a tab inside
the merged AlertsPage in a later task. Currently unused."
```

---

## Task 4: Create `AIInsightsPage.jsx`

**Files:**
- Create: `mass-market-app/src/pages/AIInsightsPage.jsx`

Goal: new page that aggregates `<CarrierAIInsights inline />` for every domestic carrier the user can see.

- [ ] **Step 1: Create the page**

Write the file with this exact content:

```jsx
import CarrierAIInsights from '../components/CarrierAIInsights'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { DOMESTIC_LABELS, carrierLabel } from '../data/carrierLabels'

export default function AIInsightsPage() {
  const allDomestic = Object.keys(DOMESTIC_LABELS)
  const carriers = useVisibleCarriers(allDomestic)

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-moca-text">AI Insights</h1>
        <p className="text-xs text-moca-muted mt-0.5">תובנות תחרותיות מבוססות Claude עבור כל ספק. לחץ "דוח AI" לפתיחת ניתוח לכל ספק.</p>
      </div>

      <div className="space-y-3">
        {carriers.map(c => (
          <div key={c} className="bg-white border border-moca-border/60 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-moca-text">{carrierLabel(c)}</span>
            </div>
            <CarrierAIInsights carrierId={c} inline />
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds. Page is unreachable (no route yet) — that's fine.

- [ ] **Step 3: Commit**

```bash
git add mass-market-app/src/pages/AIInsightsPage.jsx
git commit -m "feat(ai-insights): add AIInsightsPage

Lists all visible domestic carriers; each card has an inline
CarrierAIInsights trigger. Route registration comes in next task."
```

---

## Task 5: Replace `pages/AlertsPage.jsx` with tab wrapper

**Files:**
- Modify: `mass-market-app/src/pages/AlertsPage.jsx` (full rewrite)

Goal: replace the current AlertsPage body with a tab wrapper that renders `<AlertsPriceTab />` or `<AlertsWatchlistTab />` based on a `?tab=` query param.

- [ ] **Step 1: Replace file with tab wrapper**

Overwrite `mass-market-app/src/pages/AlertsPage.jsx` with this exact content:

```jsx
import { useSearchParams } from 'react-router-dom'
import AlertsPriceTab from '../components/alerts/AlertsPriceTab'
import AlertsWatchlistTab from '../components/alerts/AlertsWatchlistTab'

const TABS = [
  { id: 'price',     label: 'התראות מחיר' },
  { id: 'watchlist', label: 'הגדרות Push ו-Watchlist' },
]

export default function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'watchlist' ? 'watchlist' : 'price'

  function selectTab(id) {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (id === 'price') next.delete('tab')
      else next.set('tab', id)
      return next
    })
  }

  return (
    <div className="max-w-6xl mx-auto px-4 pt-4">
      <div className="border-b border-moca-border/60 mb-4">
        <div className="flex gap-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => selectTab(t.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                tab === t.id
                  ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-0 after:h-[2px] after:bg-moca-bolt'
                  : 'text-moca-muted hover:text-moca-text'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'price' && <AlertsPriceTab />}
      {tab === 'watchlist' && <AlertsWatchlistTab />}
    </div>
  )
}
```

- [ ] **Step 2: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Smoke check**

Visit `localhost:5173/alerts` — tab strip visible, "התראות מחיר" tab active by default, content renders. Click "הגדרות Push ו-Watchlist" — URL becomes `/alerts?tab=watchlist`, watchlist content renders. Reload page — same tab restored.

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/src/pages/AlertsPage.jsx
git commit -m "feat(alerts): merge AlertsPage with tabbed wrapper

/alerts now hosts two tabs: price alerts (default) and watchlist
push settings. Tab persisted via ?tab= query param."
```

---

## Task 6: Update routing — `/notifications` redirect, `/ai-insights` route

**Files:**
- Modify: `mass-market-app/src/App.jsx`

Goal: route `/notifications` → `/alerts?tab=watchlist`, register the new `/ai-insights` route, and delete the unused `NotificationsPage` import (the page file itself stays for one more task — see Task 7).

- [ ] **Step 1: Open App.jsx and locate the changes**

Read `mass-market-app/src/App.jsx`. The relevant lines:
- Line 25: `const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))`
- Line 26: `const PositioningPage = lazy(() => import('./pages/PositioningPage'))` — add new lazy import after this
- Line 94: `<Route path="notifications" element={<NotificationsPage />} />` — replace with redirect

- [ ] **Step 2: Add new lazy import**

Use Edit:
```
old_string: const PositioningPage       = lazy(() => import('./pages/PositioningPage'))
new_string: const PositioningPage       = lazy(() => import('./pages/PositioningPage'))
const AIInsightsPage        = lazy(() => import('./pages/AIInsightsPage'))
```

- [ ] **Step 3: Remove old import**

Use Edit:
```
old_string: const NotificationsPage     = lazy(() => import('./pages/NotificationsPage'))
new_string: 
```

(Replace with empty string to delete that line. The line will still exist in `pages/NotificationsPage.jsx` — we delete the file in Task 7.)

- [ ] **Step 4: Replace `/notifications` route with redirect, add `/ai-insights` route**

Use Edit:
```
old_string: <Route path="notifications" element={<NotificationsPage />} />
new_string: <Route path="notifications" element={<Navigate to="/alerts?tab=watchlist" replace />} />
            <Route path="ai-insights" element={<AIInsightsPage />} />
```

`Navigate` is already imported on line 2: `import { Routes, Route, Navigate } from 'react-router-dom'`. ✓

- [ ] **Step 5: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds.

- [ ] **Step 6: Smoke check**

- Visit `localhost:5173/notifications` → URL becomes `/alerts?tab=watchlist`, watchlist tab shown.
- Visit `localhost:5173/ai-insights` → page renders with carrier cards. Click any "דוח AI על X" — section expands inline below the button, loading spinner appears, then the report.
- Visit `localhost:5173/alerts` → tab wrapper still works.

- [ ] **Step 7: Commit**

```bash
git add mass-market-app/src/App.jsx
git commit -m "feat(routing): redirect /notifications to /alerts?tab=watchlist; add /ai-insights"
```

---

## Task 7: Delete `pages/NotificationsPage.jsx`

**Files:**
- Delete: `mass-market-app/src/pages/NotificationsPage.jsx`

Goal: remove the now-unused file. We waited until Task 6 was committed in case rollback was needed.

- [ ] **Step 1: Verify no remaining references**

```bash
cd "D:/השוואת MASS MARKET/.claude/worktrees/eloquent-jackson-116630"
```

Grep:
```
Pattern: NotificationsPage
Path: mass-market-app/src
```

Expected output: zero matches (the import was removed in Task 6, the file's own self-reference doesn't count once we delete it).

If any matches outside the file itself appear, STOP and investigate before deleting.

- [ ] **Step 2: Delete the file**

```bash
rm "mass-market-app/src/pages/NotificationsPage.jsx"
```

- [ ] **Step 3: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/src/pages/NotificationsPage.jsx
git commit -m "refactor(alerts): remove NotificationsPage

Body lives in components/alerts/AlertsWatchlistTab.jsx, route
redirects to /alerts?tab=watchlist."
```

---

## Task 8: Create `NavDropdown` component

**Files:**
- Create: `mass-market-app/src/components/NavDropdown.jsx`

Goal: a generic click-to-open dropdown for the new desktop nav. Closes on outside click, route change, and Escape. Items are passed as children — typically `<NavLink>` elements from react-router.

- [ ] **Step 1: Create the file**

```jsx
import { useState, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

export default function NavDropdown({ label, isActive = false, children }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const location = useLocation()

  // Close on route change
  useEffect(() => { setOpen(false) }, [location.pathname, location.search])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    function onKey(e) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`px-3 py-1.5 text-[13px] font-medium transition-all duration-150 inline-flex items-center gap-1 ${
          isActive
            ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-3 after:h-[1.5px] after:bg-moca-bolt after:rounded-full relative'
            : 'text-moca-muted hover:text-moca-bolt'
        }`}
      >
        {label}
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={`transition-transform ${open ? 'rotate-180' : ''}`}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute top-full mt-1 right-0 min-w-[180px] bg-white border border-moca-border/60 rounded-lg shadow-lg py-1 z-50"
        >
          {children}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds. Component is unused — that's fine.

- [ ] **Step 3: Commit**

```bash
git add mass-market-app/src/components/NavDropdown.jsx
git commit -m "feat(nav): add generic NavDropdown component

Click-to-open dropdown that closes on outside click, route change,
and Escape. Used by the new 4-group navbar."
```

---

## Task 9: Create `MobileMoreSheet` component

**Files:**
- Create: `mass-market-app/src/components/MobileMoreSheet.jsx`

Goal: a bottom sheet for mobile that lists all nav items grouped by section. Opens from the "עוד" tab in the bottom-bar.

- [ ] **Step 1: Create the file**

```jsx
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

export default function MobileMoreSheet({ open, onClose, sections }) {
  const location = useLocation()

  // Close on route change
  useEffect(() => { if (open) onClose() }, [location.pathname, location.search])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    function onKey(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      <div
        className="md:hidden fixed inset-0 bg-black/40 z-50"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-white rounded-t-2xl shadow-2xl max-h-[80vh] overflow-y-auto"
      >
        <div className="sticky top-0 bg-white border-b border-moca-border/60 px-4 py-3 flex items-center justify-between">
          <span className="text-sm font-semibold text-moca-text">תפריט</span>
          <button
            onClick={onClose}
            className="text-moca-muted hover:text-moca-text p-1"
            aria-label="סגור"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="px-2 py-2 pb-6">
          {sections.filter(s => s.items.length > 0).map(section => (
            <div key={section.title} className="mb-2">
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-moca-sub">
                {section.title}
              </div>
              <div className="space-y-0.5">
                {section.items}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
```

- [ ] **Step 2: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add mass-market-app/src/components/MobileMoreSheet.jsx
git commit -m "feat(nav): add MobileMoreSheet component

Bottom sheet listing nav items grouped by section. Opened by the
'עוד' tab in the mobile bottom-bar."
```

---

## Task 10: Refactor `Navbar.jsx` — desktop 4-group dropdowns + bell target

**Files:**
- Modify: `mass-market-app/src/components/Navbar.jsx`

Goal: replace the flat desktop nav with 4 `NavDropdown` groups (ניתוח / תובנות / היסטוריה / ניהול). Mobile bottom-bar refactor happens in Task 11. Update the bell icon target from `/notifications` to `/alerts?tab=watchlist`.

- [ ] **Step 1: Read the current Navbar.jsx**

Read the full file (271 lines) to anchor your edits.

- [ ] **Step 2: Replace the file with the new version**

Overwrite `mass-market-app/src/components/Navbar.jsx` entirely with:

```jsx
import { NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { useWatchlist } from '../hooks/useWatchlist'
import Logo from './Logo'
import NavDropdown from './NavDropdown'
import MobileMoreSheet from './MobileMoreSheet'

const NAV_ICONS = {
  '/': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
    </svg>
  ),
  '/compare': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  ),
  '/alerts': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  ),
  '/executive-summary': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  ),
  '/more': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  ),
}

const FLAG_FOR_PATH = {
  '/compare':           'hide_compare',
  '/positioning':       'hide_positioning',
  '/alerts':            'hide_alerts',
  '/executive-summary': 'hide_executive_summary',
  '/archive':           'hide_archive',
  '/ai-insights':       'hide_ai_insights',
}

const itemCls = ({ isActive }) =>
  `block px-4 py-2 text-[13px] transition-colors ${
    isActive
      ? 'text-moca-bolt bg-moca-bolt/5 font-medium'
      : 'text-moca-text hover:bg-moca-cream'
  }`

export default function Navbar() {
  const { user, isAdmin, isSuperAdmin, signOut, workspace } = useAuth()
  const flags = useFeatureFlags()
  const { changesCount } = useWatchlist()
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)

  const appTitle = workspace?.brand_config?.app_title || null
  const logoUrl  = workspace?.brand_config?.logo_url  || null

  const visible = (path) => !FLAG_FOR_PATH[path] || !flags[FLAG_FOR_PATH[path]]

  // ---------- Group definitions (used by both desktop dropdowns and mobile sheet) ----------
  const groups = [
    {
      key: 'analysis',
      label: 'ניתוח',
      items: [
        { to: '/',        label: 'דשבורד',  visible: true },
        { to: '/compare', label: 'השוואה',  visible: visible('/compare') },
        { to: '/alerts',  label: 'התראות',  visible: visible('/alerts') },
      ],
    },
    {
      key: 'insights',
      label: 'תובנות',
      items: [
        { to: '/executive-summary', label: 'תקציר מנהלים',  visible: visible('/executive-summary') },
        { to: '/positioning',       label: 'מיצוב תחרותי',  visible: visible('/positioning') },
        { to: '/ai-insights',       label: 'AI Insights',   visible: visible('/ai-insights') },
      ],
    },
    {
      key: 'history',
      label: 'היסטוריה',
      items: [
        { to: '/archive',         label: 'ארכיב snapshots',  visible: visible('/archive') },
        { to: '/?tab=history',    label: 'שינויי היסטוריה',  visible: true },
      ],
    },
    {
      key: 'admin',
      label: 'ניהול',
      items: [
        { to: '/workspace/users',    label: 'הצוות',           visible: isAdmin },
        { to: '/workspace/settings', label: 'מיתוג',           visible: isAdmin },
        { to: '/settings',           label: 'הגדרות',          visible: isAdmin },
        { to: '/admin/workspaces',   label: 'Workspaces',     visible: isSuperAdmin },
        { to: '/admin/audit',        label: 'יומן ביקורת',    visible: isSuperAdmin },
      ],
    },
  ].map(g => ({ ...g, items: g.items.filter(i => i.visible) })).filter(g => g.items.length > 0)

  function isGroupActive(group) {
    return group.items.some(i => {
      if (i.to === '/') return location.pathname === '/' && !location.search
      if (i.to === '/?tab=history') return location.pathname === '/' && location.search.includes('tab=history')
      return location.pathname === i.to || location.pathname.startsWith(i.to + '/')
    })
  }

  // ---------- Mobile bottom-bar (5 items + עוד) ----------
  const mobileBarItems = [
    { to: '/',                  label: 'דשבורד',  icon: NAV_ICONS['/'],                  visible: true },
    { to: '/compare',           label: 'השוואה',   icon: NAV_ICONS['/compare'],           visible: visible('/compare') },
    { to: '/alerts',            label: 'התראות',   icon: NAV_ICONS['/alerts'],            visible: visible('/alerts') },
    { to: '/executive-summary', label: 'תקציר',   icon: NAV_ICONS['/executive-summary'], visible: visible('/executive-summary') },
  ].filter(i => i.visible)

  // ---------- Mobile sheet sections ----------
  const sheetSections = groups.map(g => ({
    title: g.label,
    items: g.items.map(i => (
      <NavLink
        key={i.to}
        to={i.to}
        end={i.to === '/'}
        className={itemCls}
      >
        {i.label}
      </NavLink>
    )),
  }))

  return (
    <>
      {/* Desktop header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-200/60 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 h-12 flex items-center justify-between">
          <NavLink to="/" className="flex items-center">
            <Logo size="md" appTitle={appTitle} logoUrl={logoUrl} />
          </NavLink>

          <nav className="hidden md:flex items-center gap-2">
            {groups.map(g => (
              <NavDropdown key={g.key} label={g.label} isActive={isGroupActive(g)}>
                {g.items.map(i => (
                  <NavLink key={i.to} to={i.to} end={i.to === '/'} className={itemCls}>
                    {i.label}
                  </NavLink>
                ))}
              </NavDropdown>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <span className="text-[11px] text-moca-sub hidden sm:inline">{user?.email}</span>
            <NavLink
              to="/alerts?tab=watchlist"
              className="relative text-moca-sub hover:text-moca-bolt transition-colors p-1"
              title="התראות מעקב"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              {changesCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 bg-red-500 text-white text-[8px] font-bold rounded-full flex items-center justify-center px-0.5 leading-none">
                  {changesCount > 9 ? '9+' : changesCount}
                </span>
              )}
            </NavLink>
            <NavLink
              to="/preferences"
              className="text-moca-sub hover:text-moca-bolt transition-colors p-1"
              title="העדפות"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </NavLink>
            <button
              onClick={signOut}
              className="text-[11px] text-moca-sub hover:text-moca-bolt transition-colors p-1"
              title="יציאה"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile bottom-bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-md border-t border-moca-border/60">
        <div className="flex items-center justify-around h-14">
          {mobileBarItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-1.5 px-3 transition-colors ${
                  isActive ? 'text-moca-bolt' : 'text-moca-muted'
                }`
              }
            >
              {item.icon}
              <span className="text-[9px] font-medium">{item.label}</span>
            </NavLink>
          ))}
          <button
            onClick={() => setMoreOpen(true)}
            className="flex flex-col items-center gap-0.5 py-1.5 px-3 transition-colors text-moca-muted"
          >
            {NAV_ICONS['/more']}
            <span className="text-[9px] font-medium">עוד</span>
          </button>
        </div>
      </nav>

      <MobileMoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} sections={sheetSections} />
    </>
  )
}
```

- [ ] **Step 3: Build**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Smoke check (Desktop, viewport ≥768px)**

- 4 dropdown buttons visible: ניתוח · תובנות · היסטוריה · ניהול.
- Click "ניתוח" → menu shows דשבורד / השוואה / התראות.
- Click "השוואה" → navigates to `/compare`, dropdown closes, "ניתוח" button shows active underline.
- Click outside the menu → it closes.
- Press Escape with menu open → it closes.
- Bell icon → navigates to `/alerts?tab=watchlist`.
- Login as super-admin (`VITE_DEV_AUTH=true` + super_admin role): "ניהול" group includes Workspaces and יומן ביקורת.
- Login as plain user (`VITE_DEV_AUTH=true` + viewer role): "ניהול" group is hidden entirely.

- [ ] **Step 5: Smoke check (Mobile, devtools narrow viewport ≤767px)**

- Bottom-bar shows 5 items: דשבורד · השוואה · התראות · תקציר · עוד.
- Tap "עוד" → bottom sheet slides up with 4 group sections.
- Tap any item → navigates, sheet closes.
- Tap dim overlay or X → sheet closes.

- [ ] **Step 6: Commit**

```bash
git add mass-market-app/src/components/Navbar.jsx
git commit -m "feat(nav): restructure navbar to 4 dropdown groups + mobile More sheet

Desktop: ניתוח / תובנות / היסטוריה / ניהול dropdowns. Bell now points
at /alerts?tab=watchlist. Mobile: 5-item bottom-bar + 'עוד' sheet
listing all nav items grouped by section."
```

---

## Task 11: Final smoke pass + dist rebuild for deployment

**Files:** none (verification only)

Goal: end-to-end pass to verify nothing regressed.

- [ ] **Step 1: Build production bundle**

```bash
cd mass-market-app && npm run build
```

Expected: build succeeds, no errors, no new warnings beyond what `main` already has.

- [ ] **Step 2: Run dev server and walk through every nav surface**

```bash
cd mass-market-app && npm run dev
```

Open `localhost:5173`. Verify each item below:

**Desktop nav:**
- [ ] Logo links to `/`.
- [ ] ניתוח dropdown → דשבורד / השוואה / התראות, each navigates correctly.
- [ ] תובנות dropdown → תקציר מנהלים / מיצוב תחרותי / AI Insights, each navigates.
- [ ] היסטוריה dropdown → ארכיב snapshots (`/archive`) / שינויי היסטוריה (`/?tab=history`).
- [ ] ניהול dropdown (admin role) → הצוות / מיתוג / הגדרות.
- [ ] ניהול dropdown (super_admin) → adds Workspaces / יומן ביקורת.
- [ ] Bell → `/alerts?tab=watchlist`, badge count preserved.
- [ ] ⚙ → `/preferences`.
- [ ] Logout works.

**Routing:**
- [ ] `/notifications` redirects to `/alerts?tab=watchlist`.
- [ ] `/alerts` defaults to `?tab=price` (no query param).
- [ ] `/alerts?tab=watchlist` deep-link works.
- [ ] `/ai-insights` renders, click "דוח AI על X" expands inline.

**Mobile (devtools narrow viewport):**
- [ ] Bottom-bar shows 5 items + עוד.
- [ ] עוד sheet opens, lists 4 sections, navigates, closes.

**Feature flags:**
- [ ] Set `feature_flags: {"hide_compare": true}` on workspace in Supabase → "ניתוח" group still appears with דשבורד and התראות.
- [ ] Set all of `hide_executive_summary`, `hide_positioning`, `hide_ai_insights` true → "תובנות" group disappears.
- [ ] Revert flags after testing.

- [ ] **Step 3: Lint pass**

```bash
cd mass-market-app && npm run lint
```

Expected: no new lint errors. If there are warnings about unused imports from earlier tasks, clean them now.

- [ ] **Step 4: Final commit and dist rebuild**

The user manually drags `mass-market-app/dist` to Netlify. The build from Step 1 already produced it. If you made any cleanup edits in Step 3, run `npm run build` once more.

```bash
cd "D:/השוואת MASS MARKET/.claude/worktrees/eloquent-jackson-116630"
git add mass-market-app/dist
git commit -m "chore(dist): rebuild frontend dist for navigation restructure"
```

---

## Self-review checklist (run before declaring done)

- [ ] Spec §3.1 (4 dropdown groups) → covered by Tasks 8 + 10.
- [ ] Spec §3.2 (`/alerts` merge with two tabs + redirect) → covered by Tasks 2, 3, 5, 6, 7.
- [ ] Spec §3.3 (`/ai-insights` page + `inline` prop) → covered by Tasks 1, 4, 6.
- [ ] Spec §3.4 (mobile bottom-bar 5 items + More sheet) → covered by Tasks 9 + 10.
- [ ] Spec §3.5 (full file change list) → all 8 files touched across Tasks 1–10.
- [ ] Spec §6 edge cases (group hiding, deep-links, suspended workspace) → tested in Task 11 Step 2.
- [ ] No leftover references to deleted `NotificationsPage` (verified in Task 7 Step 1).
- [ ] Bell icon target updated (Task 10).
- [ ] `npm run build` runs at the end of every task that touches code.
