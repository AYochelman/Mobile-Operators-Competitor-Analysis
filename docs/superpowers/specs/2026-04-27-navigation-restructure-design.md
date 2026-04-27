# Navigation Restructure — Design Spec

**Date:** 2026-04-27
**Status:** Approved (pending user spec review)
**Scope:** React app (`mass-market-app/`) — navigation hierarchy and merged Alerts/Notifications page

## 1. Motivation

The current top-level navigation has 8–11 items competing for attention in a single horizontal strip (6 main + admin items + super-admin items + 3 right-side icons). Six concrete problems were identified:

1. **Horizontal overload** — no visual rest between "work with data" vs "manage system" items.
2. **Compare + Positioning are conceptually adjacent** — both are visual comparisons, but split.
3. **Executive Summary is over-prominent** — it's a weekly read, not daily.
4. **"Archive" + "History" are semantically similar** but live at different hierarchy levels (Archive is a top-level page, History is a tab inside Dashboard).
5. **Five admin entries scattered**: הגדרות, Workspaces, יומן, הצוות, מיתוג — no grouping.
6. **`/alerts` (price alerts) and `/notifications` (push + watchlist) appear duplicated** — both look like "התראות" to the user.

## 2. Current State (verified in code)

Navbar items live in [Navbar.jsx:45-52](mass-market-app/src/components/Navbar.jsx#L45):

```js
const NAV_ITEMS = [
  { to: '/', label: 'דשבורד', end: true },
  { to: '/compare', label: 'השוואה' },
  { to: '/positioning', label: 'מיצוב' },
  { to: '/alerts', label: 'התראות' },
  { to: '/executive-summary', label: 'תקציר מנהלים' },
  { to: '/archive', label: 'ארכיב' },
]
```

Plus inline-rendered admin links in the same `<nav>` element:
- admin (not super-admin): הצוות (`/workspace/users`), מיתוג (`/workspace/settings`)
- admin: הגדרות (`/settings`)
- super-admin: Workspaces (`/admin/workspaces`), יומן (`/admin/audit`)

Right-side icons: 🔔 → `/notifications` (with watchlist count badge), ⚙ → `/preferences`, logout.

Mobile bottom-bar: same `visibleNav` items + bell + (admin) gear.

Feature flags from `useFeatureFlags()` hide individual items via `FLAG_FOR_PATH` map ([Navbar.jsx:54](mass-market-app/src/components/Navbar.jsx#L54)).

Existing pages relevant to scope:
- `/` — `DashboardPage.jsx`. Has internal tabs incl. `'history'` accessible via `?tab=history` query param ([DashboardPage.jsx:206](mass-market-app/src/pages/DashboardPage.jsx#L206)).
- `/alerts` — `AlertsPage.jsx`, has internal sub-tabs (domestic/abroad/global).
- `/notifications` — `NotificationsPage.jsx`, watchlist-driven.
- `CarrierAIInsights.jsx` — component used per-carrier inside Dashboard. **No standalone AI insights page exists.**

## 3. Target Design

### 3.1 Desktop top bar

```
[MOCA logo]   ניתוח ▾   תובנות ▾   היסטוריה ▾   ניהול ▾        🔔  ⚙  alon@…  ↩
```

**Four dropdown groups**, click-to-open (not hover) for accessibility consistency with mobile:

| Group | Items | Path | Role gate |
|-------|-------|------|-----------|
| **ניתוח** | דשבורד | `/` | all |
|  | השוואה | `/compare` | all (flag: `hide_compare`) |
|  | התראות | `/alerts` | all (flag: `hide_alerts`) |
| **תובנות** | תקציר מנהלים | `/executive-summary` | all (flag: `hide_executive_summary`) |
|  | מיצוב תחרותי | `/positioning` | all (flag: `hide_positioning`) |
|  | AI Insights | `/ai-insights` | all (new — flag: `hide_ai_insights`, default visible) |
| **היסטוריה** | ארכיב snapshots | `/archive` | all (flag: `hide_archive`) |
|  | שינויי היסטוריה | `/?tab=history` | all (no flag — links into Dashboard) |
| **ניהול** | הצוות | `/workspace/users` | admin |
|  | מיתוג | `/workspace/settings` | admin |
|  | הגדרות | `/settings` | admin |
|  | Workspaces | `/admin/workspaces` | super_admin |
|  | יומן ביקורת | `/admin/audit` | super_admin |

**Group visibility rule**: a group is hidden if all its items are hidden by feature flags or by role.

**Right-side icons** (unchanged):
- 🔔 → `/alerts` (instead of `/notifications` — both pages merge, see §3.2). Watchlist-changes badge logic preserved.
- ⚙ → `/preferences` (per-user, distinct from "ניהול" which is org-level).
- email + logout.

### 3.2 `/alerts` merge

`AlertsPage.jsx` gains a **top-level tab strip**:

```
┌──────────────────────────────────────────────────────────┐
│  [Tab] התראות מחיר   [Tab] הגדרות Push ו-Watchlist      │
├──────────────────────────────────────────────────────────┤
│  (existing content of selected tab)                      │
└──────────────────────────────────────────────────────────┘
```

- **Tab 1 — התראות מחיר**: existing `AlertsPage` body (with its own internal domestic/abroad/global sub-tabs preserved as nested).
- **Tab 2 — הגדרות Push ו-Watchlist**: existing `NotificationsPage` body, rendered inline.

**Implementation:**
- Move current `AlertsPage` body into a new component `AlertsTab.jsx`.
- Move current `NotificationsPage` body into a new component `WatchlistTab.jsx`.
- New `AlertsPage.jsx` wrapper renders the two-tab strip and switches between them.
- Tab state persisted via `?tab=price` / `?tab=watchlist` query param. Default = `price`.
- `/notifications` route **remains** but redirects to `/alerts?tab=watchlist` (preserves bell icon link, deep-links from emails, browser bookmarks).

### 3.3 `/ai-insights` — new page (inline rendering)

A vertical list aggregating `CarrierAIInsights` for every domestic carrier the user can see (respecting `useHiddenCarrier()`). On this page each card renders the report **inline (expand-in-place)** instead of opening a modal — modal stays the default for the existing dashboard usage.

#### 3.3.1 Refactor `CarrierAIInsights` to support inline mode

Add an optional prop `inline?: boolean` (default `false`).

- **`inline === false`** (default, used by Dashboard): existing behavior preserved — button opens a `<Modal>`.
- **`inline === true`** (used by `/ai-insights`): no modal. The trigger button toggles an inline section beneath itself that contains the same loading/error/answer/refresh states. Clicking the same button after content is loaded collapses the section.

Implementation sketch:
```jsx
export default function CarrierAIInsights({ carrierId, inline = false }) {
  const [open, setOpen] = useState(false)
  // ...existing state (loading, answer, error)

  const Body = (
    <div className="text-right">
      {/* existing loading / error / answer JSX */}
    </div>
  )

  if (inline) {
    return (
      <div>
        <button onClick={() => { if (!open) loadInsights(); setOpen(o => !o) }}>
          {/* same trigger styling */}
          {open ? 'הסתר דוח' : `דוח AI על ${carrierName}`}
        </button>
        {open && <div className="mt-3 border-t pt-3">{Body}</div>}
      </div>
    )
  }

  return (
    <>
      <button onClick={() => { setOpen(true); loadInsights() }}>...</button>
      <Modal open={open} onClose={() => setOpen(false)}>{Body}</Modal>
    </>
  )
}
```

Body JSX is extracted once and reused — no duplicate logic. Existing dashboard call sites (which pass no `inline` prop) keep working unchanged.

#### 3.3.2 New page

```jsx
// pages/AIInsightsPage.jsx
import { DOMESTIC_LABELS } from '../data/carrierLabels'
import CarrierAIInsights from '../components/CarrierAIInsights'
import { useHiddenCarrier } from '../hooks/useHiddenCarrier'

export default function AIInsightsPage() {
  const { hidden } = useHiddenCarrier()
  const carriers = Object.keys(DOMESTIC_LABELS).filter(c => !hidden.has(c))
  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-3">
      <h1 className="text-lg font-semibold mb-4">AI Insights — תובנות תחרותיות לכל ספק</h1>
      {carriers.map(c => (
        <div key={c} className="bg-white border border-moca-border/60 rounded-xl p-4">
          <CarrierAIInsights carrierId={c} inline />
        </div>
      ))}
    </div>
  )
}
```

Lazy-loaded via `lazy()` in `App.jsx`. Loading remains lazy at the API level: nothing fires until the user clicks a specific carrier's button.

### 3.4 Mobile bottom-bar

Flat list of 5 most-used items + "עוד":

```
┌─────┬─────┬─────┬───────┬──────┐
│דשבוד│השואה│התראות│תקציר │ עוד  │
└─────┴─────┴─────┴───────┴──────┘
```

- Tapping "עוד" opens a bottom-sheet with the remaining items, organized by the same 4-group structure as desktop (mini visual section headers).
- Bell badge logic moves from a separate icon to the "התראות" item.
- Admin/super-admin items appear inside the "עוד" sheet under a "ניהול" section (role-gated).
- **Hidden-flag handling**: each of the 5 items respects its feature flag (e.g., if `hide_compare`, the "השוואה" slot is replaced by the next-priority item — currently מיצוב). Always preserve "דשבורד" as slot 1 (no flag for it). If fewer than 4 visible non-Dashboard items exist, the bottom-bar shrinks accordingly (no empty slots).

### 3.5 Component changes

| File | Change |
|------|--------|
| `components/Navbar.jsx` | Replaces flat nav with 4 dropdown groups + new "More" sheet for mobile |
| `components/NavDropdown.jsx` | **NEW** — generic dropdown component (button + popover with items) |
| `components/MobileMoreSheet.jsx` | **NEW** — bottom-sheet for mobile "עוד" |
| `pages/AlertsPage.jsx` | Becomes a tab wrapper; old body → `components/alerts/AlertsTab.jsx` |
| `pages/NotificationsPage.jsx` | Body extracted to `components/alerts/WatchlistTab.jsx`; page becomes a redirect |
| `pages/AIInsightsPage.jsx` | **NEW** |
| `components/CarrierAIInsights.jsx` | Add optional `inline` prop (default `false`); preserves existing modal behavior on Dashboard, renders expand-in-place when `inline` |
| `App.jsx` | Add `/ai-insights` route; `/notifications` → `<Navigate to="/alerts?tab=watchlist" replace />` |

**Feature flag note**: `useFeatureFlags()` is already a generic passthrough that returns `workspace.feature_flags`. No hook change is needed — adding `hide_ai_insights` to the navbar's `FLAG_FOR_PATH` map is sufficient. Super-admin still bypasses all flags via the existing `if (isSuperAdmin) return {}` early return in the hook.

No backend changes. No DB schema changes. No API changes.

## 4. Data Flow

- Group visibility: computed in `Navbar` from `{NAV_GROUPS, flags, isAdmin, isSuperAdmin}` — pure function of these inputs.
- Active group highlight: a group shows as active if any of its child paths matches the current route.
- Sheet/dropdown state: local component state; closed on route change (subscribe to `useLocation`).
- Bell badge: still driven by `useWatchlist().changesCount`, but now points at `/alerts?tab=watchlist`.

## 5. Accessibility

- Each dropdown trigger: `<button aria-haspopup="menu" aria-expanded={open}>`.
- Each item inside: `<NavLink role="menuitem">`.
- Keyboard: Enter/Space opens, Escape closes, ArrowDown moves between items, focus returned to trigger on close.
- Mobile sheet: `aria-modal="true"` with focus trap.
- RTL preserved — dropdown anchors to right edge of trigger (since `direction: rtl`).

## 6. Edge cases

- **All children of a group hidden by flags** — group itself is hidden.
- **User on `/positioning` when `hide_positioning` flag flips on** — the page route still works (route registration unchanged); only the menu entry hides. (Matches current behavior.)
- **`/notifications` external links / bookmarks** — `<Navigate>` redirect preserves them.
- **Existing `?tab=` users on Dashboard** — unchanged. The "שינויי היסטוריה" link is just a `NavLink to="/?tab=history"`.
- **Suspended workspace** — `<ProtectedRoute>` already short-circuits to `SuspendedPage` before `Layout` renders, so navbar isn't reached.
- **View-as super-admin** — dropdown contents respect impersonated workspace's `feature_flags` exactly as today.

## 7. Out of scope (explicitly deferred)

- **Cmd+K command-palette extension** — `GlobalSearch` stays as-is (package search only). To be revisited in a follow-up after this restructure stabilizes.
- **Renaming/refactoring AlertsPage internal sub-tabs** (domestic/abroad/global) — preserved verbatim as nested under new "התראות מחיר" tab.
- **Backend changes** — none required.

## 8. Testing approach

- Manual smoke pass on Desktop:
  - Each dropdown opens, items navigate, dropdown closes on selection.
  - Active highlight on parent group when child route is active.
  - Role gating: log in as viewer / admin / super_admin (use `VITE_DEV_AUTH=true`) — verify correct visibility.
  - Feature flag toggles (via Supabase row update on workspace) — verify hide/show.
- Manual smoke pass on Mobile (devtools narrow viewport):
  - 5 items visible, "עוד" sheet opens, all items reachable.
- `/alerts` merge:
  - Direct visit `/alerts` → defaults to "התראות מחיר" tab.
  - Visit `/alerts?tab=watchlist` → renders watchlist directly.
  - Visit `/notifications` → redirects to `/alerts?tab=watchlist`.
  - Bell icon click → `/alerts?tab=watchlist`. Badge count preserved.
- Build: `npm run build` must pass without warnings (per project convention to always rebuild).

## 9. Risks

- **Dropdown UX is a new interaction pattern** for this app. Mitigation: click-to-open (not hover) — consistent across desktop and mobile sheet, matches app's existing modal patterns (SearchableSelect, AnnotationsModal).
- **`/alerts` merge changes URL semantics** — old `/notifications` deep-links must keep working. Mitigation: explicit `<Navigate>` redirect, validated in tests.
- **AI Insights page perf** — page renders 8 inline-mode cards but each defers its API call until the user clicks. No simultaneous fan-out; cost stays linear with user clicks. If a future enhancement auto-loads all on mount, revisit with intersection observer.
- **Feature flag for AI Insights defaults to visible** — workspace admins who want to hide it must set `hide_ai_insights: true` in `feature_flags`. No back-compat issue (new flag).
