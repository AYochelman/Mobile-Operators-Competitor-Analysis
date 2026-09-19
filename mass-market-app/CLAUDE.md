# CLAUDE.md - mass-market-app (React frontend)

Supplements the root CLAUDE.md when working in `mass-market-app/`. Moved here so backend-only sessions don't carry it in context.

## React App Structure (mass-market-app/src/)

### Pages

| Path | Purpose |
|------|---------|
| pages/DashboardPage.jsx | Main 8-tab view (domestic/abroad/global/**resellers**/content/banners/history/news) with filters. **Lazy-loaded** since phase 15. Since 2026-09 (~1,570 lines, was 1,984) the filter/sort/group/destination logic lives in `hooks/useDashboardPlans.js` and the multi-country + region-label data in `data/planCoverage.js` / `data/regionLabels.js`; the page keeps the UI catalogs (`TABS`, `RESELLERS`, `USA_OPERATORS`, `CARRIERS` + `CARRIER_IDS`) and the JSX. `RESELLERS` const lists reseller IDs+labels mapped to underlying carriers. Reads `lockedTab` from `useLocation().pathname` — when on a clean URL like `/plans` or `/banners` the tab navigation hides and `setTab` navigates instead of mutating state. |
| pages/ComparePage.jsx | Price comparison charts (Recharts) |
| pages/AlertsPage.jsx | Personal price alerts with DB persistence |
| pages/SettingsPage.jsx | Admin panel — scrape triggers, user management (adminOnly). "ניהול משתמשים" tab (super_admin) creates users via direct-DB provisioning (`POST /api/users`, no email — see Security) and resets a user's password via `<AdminResetPasswordModal>` → `POST /api/users/<id>/password`. |
| pages/ExecutiveSummaryPage.jsx | Per-category cards + ₪/GB bar chart + AI narrative, from cached `executive_summaries` (regen 08:05 / `POST /api/executive-summary/refresh`). Metrics from `compute_executive_metrics` (db.py): ₪/GB chart is GB-**weighted** `SUM(price)/SUM(GB)` — a naive `AVG(price/data_gb)` lets a tiny-data plan (e.g. 019's 100MB "חבילת עשר", ~102 ₪/GB) dominate the mean; "המשתלם ביותר" card = `MIN(price/GB)` (best single deal); "האגרסיבי ביותר" shows `—` when there are 0 price drops (no false aggressor) |
| pages/PositioningPage.jsx | Competitive positioning matrix |
| pages/CockpitPage.jsx | **Executive situation room** (`/cockpit`, nav group ניטור, feature flag `hide_cockpit`). One screen for a סמנכ"ל, in two plain measures — what a package COSTS (₪/month) and what it GIVES (GB); the ₪/GB ratio was retired at the owner's request (v2, 2026-09). Blocks: verdict bar (our rank on median package price + median volume vs the market, weekly competitor tally, a red "נתונים לא עדכניים" badge when a source is >36h old), 4 KPI tiles (market price / market volume / ours or cheapest / ours or most generous), **weekly competitor changes** (fixed 7-day window regardless of the chart picker, competitors only, domestic + roaming, grouped by carrier logo and ranked by impact 3·cuts+2·launches+rises+removals+0.5·benefits, ≤5 groups × ≤4 rows with expanders, "הפעיל ביותר השבוע" in the header, a truncation hint when a 500-row feed was capped inside the week, and an empty state that switches tone when the scrape itself is stale), positioning ladder (single-hue median-price bar + volume as a NUMBER — a bar cannot show ∞ honestly — logo + name per row, only "ours" tinted `#c9622f`, a "לשים לב" line naming the competitor that gives more data at our price or less), price trend (`/api/history/daily` avg_price: ours vs market median, cost-only because history stores no GB aggregate; the 7/30/90 picker lives in this card since nothing else depends on it; neutral ▲/▼ deltas — a price move's direction is not good/bad by itself) and a freshness strip. The cached AI narrative is NOT shown here: it is generated around the ₪/GB index. Carriers always render as their logo via `CarrierChip`. Data layer: `hooks/useCockpitData.js`. |
| pages/ArchivePage.jsx | Historical plan snapshots (content-hash based, via archive.py) |
| pages/PreferencesPage.jsx | Per-user display preferences |
| pages/NotificationsPage.jsx | Web Push / notification settings |
| pages/ResetPasswordPage.jsx | **Public** route `/reset-password` (outside the AppShell auth gate) — the Supabase recovery-link target. Waits for the `PASSWORD_RECOVERY` session, then sets the new password via `supabase.auth.updateUser`. Paired with the "שכחתי סיסמה" flow on LoginPage (`sendPasswordReset` → `resetPasswordForEmail`, redirectTo `/reset-password`). |
| pages/WorkspaceUsersPage.jsx | Manage users in current workspace (adminOnly) |
| pages/WorkspaceBrandingPage.jsx | Workspace logo, colors, MVNO theme (adminOnly). Logo accepts a hosted **URL** *or* a **file upload** via the shared `<LogoField>` (`components/LogoField.jsx`, also used by `WorkspacesAdminPage`): the picked file is resized client-side to a 480×160 bounding box and stored **inline as a `data:` URI** in `brand_config.logo_url` (SVGs kept verbatim). No upload endpoint / file-serving — `PATCH /api/workspace/branding` (and the workspace POST/PATCH) store the string as-is, CSP already allows `img-src data:`, and every consumer (`Logo`/`Sidebar`/`Navbar`/preview) is a plain `<img src>`. Keeps the logo in the cloud workspace row (no dependence on local Flask/ngrok). |
| pages/WorkspacesAdminPage.jsx | Global workspace CRUD (superAdminOnly) |
| pages/AuditLogPage.jsx | Action audit trail (superAdminOnly) |
| pages/UsagePage.jsx | Claude API usage analytics (**superAdminOnly**, `/usage` — hidden from client-workspace admins since it reports the owner's global Anthropic spend) — cost/tokens by day/model/endpoint from the `claude_api_usage` table. **Budget panel** (`BudgetPanel`): remaining balance + depletion forecast. Anthropic exposes no balance API, so the budget is user-entered in config.json (`claude_budget_usd`, optional `claude_budget_as_of` baseline — set it after a top-up so old spend doesn't count). `remaining = budget − logged spend` (lifetime, or since `as_of`); burn rate = the selected 7/30/90-day window's daily pace over its *active span* (so a partly-filled window isn't understated). Set/cleared via `POST /api/usage/budget` (`@require_api_key`); the `GET /api/usage/summary` response carries a `budget` block built by `_claude_budget_block()` in app.py. **Official spend** (`OfficialSpend` row): authoritative org-wide spend from Anthropic's **Admin Cost API** (`/v1/organizations/cost_report`), via `GET /api/usage/official-cost?days=N` → `_fetch_anthropic_cost_usd()` (10-min TTL cache, paginated). Needs config.json `anthropic_admin_key` (org Admin key `sk-ant-admin…`; **not available for individual accounts**). GOTCHA: the API's `amount` is in **cents** (lowest currency unit) as a decimal string → divide by 100. This is SPEND, not balance — Anthropic still has no remaining-credit endpoint, so "remaining" always needs the user-set total. |
| pages/UserActivityPage.jsx | **Super-admin user-activity dashboard** (`/admin/user-activity`, superAdminOnly). Per-client-user login times, pages visited, and actions (alerts / watchlist / saved comparisons), merged from Supabase `auth.users` + the `user_activity` table. **Super-admins are excluded** everywhere (operator's own activity is never recorded or shown). Mirrors `UsagePage` (StatCards + Recharts daily chart + sortable table with row-click drill-down) and links to existing user management (`/settings?tab=users`). Activity is recorded via a best-effort beacon — `POST /api/activity` (`components/RouteTracker.jsx` fires `page_view` on each authed route change; `useAuth` fires `login` on real sign-in, deduped per browser session) — plus server-side hooks in the alert/watchlist/saved-view handlers (`_track_user_action` in app.py). Read endpoints `GET /api/activity/overview` + `GET /api/activity/events` are `@require_api_key_or_super_admin` (so they work with the dev API key locally, like the usage endpoints). |

### Components

| Path | Purpose |
|------|---------|
| components/Logo.jsx | MOCA brand logo (bolt + wordmark), sizes: xs/sm/md |
| components/PlanCard.jsx | Universal plan card with country/apps modals. Uses `<Delta>` from moca/ for price-trend pills |
| components/ChatPanel.jsx | AI chat (floating button → /api/chat) |
| components/NewsTab.jsx | Google News RSS per carrier, client-side filter by carrier + date window |
| components/GlobalSearch.jsx | Cmd+K / Ctrl+K full-app plan search, portal-rendered |
| components/AnnotationsModal.jsx | Team notes per plan — pinned to (carrier, plan_name) |
| components/ScrapeProgressPanel.jsx | Live scrape progress indicator (SSE stream) |
| components/AuthDegradedBanner.jsx | Red bar shown when `useAuth().contextDegraded` is set — i.e. the role on screen is a FALLBACK, not the server's answer. `/api/my-context` failing (Flask/tunnel down, timeout, 401/403) or answering without an identity (`reason: no_jwt`/`no_email`) used to drop the user to `viewer` **silently**, so every admin menu vanished and it looked like a permissions change. The app still runs in the degraded role, but names the reason and offers `retryContext()` — no sign-out needed. |
| components/ViewAsBanner.jsx | Super-admin "viewing as workspace X" banner. Rendered inside Layout (above the sidebar+main flex row) — not sticky |
| components/CarrierAIInsights.jsx | Per-carrier AI summary widget. Used inline in DashboardPage; `/ai-insights` page uses its own feed-style layout |
| components/MarketMoversWidget.jsx | Biggest price changes since last scrape |
| components/SparklineMini.jsx | Inline price-history sparkline (Recharts) — API-fetching variant |
| components/SavedComparesMenu.jsx | Save/load named comparison filter sets |
| components/SavedViewsMenu.jsx | Save/load named dashboard filter states |
| components/PriceHistoryModal.jsx | Full price history chart for a single plan |
| components/OfflineBanner.jsx | Offline detection banner (useOnlineStatus) |
| components/ChangePasswordModal.jsx | Self-service password change for the logged-in user (profile menu → "שינוי סיסמה"). Verifies the current password (re-auth), then `supabase.auth.updateUser` — no email. Exposed via `changePassword` in useAuth |
| components/AdminResetPasswordModal.jsx | super_admin sets a new password for any user from SettingsPage "ניהול משתמשים" → `api.adminSetPassword` → `POST /api/users/<id>/password` (direct DB, no email). Generates an unambiguous temp password to hand over |

### MOCA Design System (`components/moca/`)

Shared primitives that drive the new visual language. Import via the barrel: `import { CarrierChip, Delta, Tag, PageHeader, ... } from '../components/moca'`.

| Path | Purpose |
|------|---------|
| moca/CarrierChip.jsx | Circular avatar with brand color (from `mvnoBrandColors.js`) + 1-2 letter glyph + optional name. Workspace-themed |
| moca/Sparkline.jsx | **Pure presentational** SVG sparkline (no API). Pair with `useCarrierPriceTrend` for fetched data |
| moca/Delta.jsx | +/- pill with ▲/▼ arrows. Positive=red (`--color-moca-up`)=bad-for-us; negative=green (`--color-moca-down`)=good-for-us |
| moca/Tag.jsx | Compact uppercase status pill — NEW, HOT, PRICE UP, BENCHMARK |
| moca/PageHeader.jsx | Standard page top — kicker + title + subtitle + actions + tabs. Title is **optional** (omit when Topbar already shows it) |
| moca/Sidebar.jsx | Universal: desktop sticky aside on RTL start; pass `mobile open onClose` for the slide-in drawer variant |
| moca/Topbar.jsx | Desktop topbar — kicker + dynamic title from `routeMeta.js` + LIVE pulse + ⌘K search + Time Machine + alerts + profile |
| moca/TimeMachineModal.jsx | `/api/archive` viewer — carrier dropdown + date picker, renders historical banners + plans for the picked snapshot |
| moca/CompetitorBoard.jsx | Per-carrier competitive snapshot row — chip + sparkline + min/avg price + delta + "ביחס לשלך". Domestic-tab only |
| moca/BannerMosaic.jsx | column-count layout for banners (3→2→1 responsive). Wires tiles → drawer state. Per-banner `kind` overrides mosaic-level `source` |
| moca/BannerTile.jsx | Single banner tile with carrier color dot + freshness pill (היום / אתמול / לפני N ימים) + hover lift |
| moca/BannerDrawer.jsx | Slide-in detail drawer (480px from RTL start) for a banner — large preview + facts grid + actions |
| moca/routeMeta.js | Pathname → `{ kicker, title }` map used by Topbar. Add new entries when adding routes |
| moca/carrierMeta.js | `getCarrierColor(id)` / `getCarrierLetter(id)` / `getCarrierName(id)` for the chip primitives |
| moca/index.js | Barrel re-export — always import from here for consistency |

### Hooks & Lib

| Path | Purpose |
|------|---------|
| hooks/useAuth.jsx | Supabase Auth + dev mode (VITE_DEV_AUTH=true). Exposes user, isAdmin, isSuperAdmin, workspace |
| hooks/useFeatureFlags.js | Returns workspace.feature_flags (empty obj for super_admin = all features on) |
| hooks/useHiddenCarrier.js | Per-user hidden carrier list (persisted) |
| hooks/useScrape.jsx | ScrapeProvider context — SSE progress stream, trigger scrape |
| hooks/useAnnotationCounts.jsx | Aggregated annotation counts per plan |
| hooks/useWatchlist.jsx | Per-user watchlist of plan IDs |
| hooks/useOnlineStatus.js | Navigator online/offline event listener |
| hooks/useCarrierPriceTrend.js | Aggregate per-carrier price-history series (avg across all plans, daily). Module-scope cache + in-flight coalescing. Used by `<CompetitorBoard>` |
| hooks/useDashboardPlans.js | **Dashboard plan pipeline** (extracted from DashboardPage 2026-09): PURE functions `filterAndSortPlans(tabPlans, tab, filters, ctx)`, `groupGlobalDisplayItems`, `globalRegionsOf`, `globalDestinationsOf`, `hasCruisePackages` + the `useDashboardPlans({plans, tab, filters, visibleCarrierIds, carrierIds, usaOperators, onlyWatched, isWatched, watchItems, lang})` memo hook that DashboardPage renders from. Memo boundaries mirror the old inline useMemos (heavy filter+sort keyed on plans/tab/filters + a join-key of visibleCarrierIds; the watchlist toggle only re-runs a light filter). Smoke-testable in node via `npx esbuild src/hooks/useDashboardPlans.js --bundle --platform=node` |
| hooks/useCockpitData.js | Data layer for `/cockpit`: PURE exported derivations + the `useCockpitData(oursCarrier, days)` hook over `/api/plans`, `/api/changes?limit=500`, `/api/abroad-plans`, `/api/abroad-changes?limit=500`, `/api/history/daily` (`api.getHistoryDaily`). `classifyPlan` mirrors api/mobile.py (data_gb ≥ 9999 → unlimited (wecom's 10000 sentinel); NULL → unlimited unless plan_name/extras match `כשר|נטפרי|ועד הרבנים|KOSHER|ללא גלישה` → voice-only; 0<gb<1 → sub-GB). `buildCostVolume`: per carrier median list price + `medianWithInf` volume (unlimited = +∞, so an unlimited-typical carrier reads ∞ instead of being under-reported); voice/sub-GB rows excluded from BOTH measures and disclosed; competition ranking on cost (tied medians share a rank — .9 pricing makes ties common; `row.rank` is what the ladder prints); ranks suppressed under 3 carriers; `defender` = competitor with more data at ≤ our price. The hook runs TWO effects: the core feeds (keyed on `reloadKey`, drive `loading`/`error` — a failed `/api/plans` raises the Retry card instead of an empty all-green page) and the history window (keyed on `days`, drives only `trendLoading`, so the 7/30/90 picker re-requests one endpoint and never unmounts the page). A source with no `scraped_at` at all counts as stale (red), never fresh. `buildPriceTrend`: skips `carrier='*'` aggregate rows, days with <3 carriers, and carrier-days whose plan_count < 50% of that carrier's window max (partial scrape); carries the day's floor for the tooltip. `buildWeeklyChanges`: 7-day window, net-dedup per (scope, carrier, plan, type) earliest→latest with net-zero dropped, launched+removed pairs dropped as flaps, `extras_change` through `lib/benefitDiff.materialDiff` so rewordings never show, `truncated` when a feed hit its cap inside the window. Smoke-testable in node like `useDashboardPlans.js` (`npx esbuild src/hooks/useCockpitData.js --bundle --platform=node`). |
| lib/api.js | Flask API wrapper with JWT headers |
| lib/supabase.js | Supabase client (graceful null if unconfigured) |

### Data Files

| Path | Purpose |
|------|---------|
| data/carrierLabels.js | **Single source of truth** for carrier ID → display name. Exports `carrierLabel(id)`, `DOMESTIC_LABELS`, `GLOBAL_LABELS`. Mirror in app.py: `_CARRIER_NAMES`. Update both together when adding a carrier. |
| data/mvnoBrandColors.js | MVNO-specific primary/secondary colors. `getMvnoColors(mvno_carrier)` used by `BrandThemeApplier` in App.jsx to set `--color-moca-bolt` / `--color-moca-dark` CSS vars. |
| data/globalCountries.js | Country lists for global eSIM providers + getCountriesForPlan() |
| data/planCoverage.js | `MULTI_COUNTRY_CARRIERS` + `getPlanCoverage(plan)` (moved out of DashboardPage 2026-09) - which providers sell one plan over many countries and how to resolve a plan's coverage list from globalCountries.js |
| data/regionLabels.js | `KNOWN_REGIONS`, `isLargeMultiCountryRegion`, `normalizeRegionLabel` - region tags on global plans and the "N+ מדינות → גלובלי", "*אירופה* → אירופה" consolidation rules |
| data/abroadCountries.js | Country lists for domestic abroad plans + getCountriesForAbroadPlan() |
| data/abroadApps.js | Free app lists (Cellcom 6 apps, Pelephone 12 apps) |

## Multi-Workspace Architecture

The React app supports multiple isolated workspaces (e.g. different MVNO clients). Key concepts:

- **Roles**: `viewer` / `admin` / `super_admin`. `isSuperAdmin` in `useAuth` bypasses all feature flags and workspace restrictions.
- **Workspace object** (from Supabase): `id`, `name`, `active`, `feature_flags` (JSON), `brand_config` (primary/secondary colors), `mvno_carrier` (links to mvnoBrandColors.js).
- **Brand theming**: `BrandThemeApplier` in `App.jsx` applies workspace `brand_config` or `mvno_carrier` colors as CSS variables at runtime — no rebuild needed.
- **Suspended workspaces**: `workspace.active === false` redirects non-super-admin users to `SuspendedPage`.
- **ViewAsBanner**: Super-admin can impersonate any workspace; `ViewAsBanner` shows a persistent indicator.
- **feature_flags**: Gate features per workspace via `useFeatureFlags()`. Super-admin always sees all features regardless of flags.

Route protection uses `<ProtectedRoute adminOnly>` or `<ProtectedRoute superAdminOnly>` wrappers in `App.jsx`.

## Brand & UI

The React app uses the **MOCA mocha-latte** design system (per Claude Design handoff, see `design-handoff/` at the repo root). All tokens live in `index.css` `@theme` block:

**Surface colors**:
- `--color-moca-bg: #f9f4ee` (page background)
- `--color-moca-cream: #f5ede0` (cards, hover)
- `--color-moca-mist: #faf5ee` (subtle hover)
- `--color-moca-sand: #e8d5bc` (warm dividers)
- `--color-moca-border: #e0cdb5` (default border)

**Brand / text**:
- `--color-moca-bolt: #5c3317` (primary brand — buttons, accents). Aliased as `--color-moca-espresso`
- `--color-moca-dark: #4a2a13` (darkest text)
- `--color-moca-text: #3b1f0d` (body text)
- `--color-moca-sub: #8a6a4a` (secondary text)
- `--color-moca-muted: #a08468` (tertiary)

**Semantic** (added phase 1):
- `--color-moca-up: #b4472d` (price ↑ — bad-for-us in competitive context)
- `--color-moca-down: #4a7c3f` (price ↓ — good-for-us)
- `--color-moca-hot: #c9622f` (NEW / attention)

**Typography** (added phase 1):
- `--font-display` is aliased to Assistant (the Frank Ruhl serif was retired 2026-07-06; its woff2 files were deleted 2026-09-11)
- `--font-body: 'Assistant', system-ui, sans-serif` — everything else (set on `body`)
- Self-hosted: `public/fonts/fonts.css` + `assistant-*.woff2` (OFL 1.1, notice in `public/fonts/OFL.txt`). Nothing loads from Google Fonts any more and the CSP no longer allows it.

**Accessibility + consent (2026-09-11):** the public pages carry a skip link, `<main>` landmark, `aria-pressed` on every chip/tab-like button, `role="status"`/`aria-live` on loading and result counts, labelled form controls, `role="dialog"` modals with focus trap/return (`useDialogFocus` in MobileComparePage), solid 3px `:focus-visible` outlines, and AA-safe text colors (`--sub #7d5f40`, `--muted #6f553b`, hot-orange text `#9a4419`, green pill text `#3d6a33`; the brand oranges stay for backgrounds only). Keep new text on these tokens. `src/lib/consent.js` + `components/CookieBanner.jsx` gate the TikTok pixel (`lib/tiktokPixel.js`) behind explicit marketing consent (`moca_consent` in localStorage, versioned by `CONSENT_VERSION`); the bar only appears when `VITE_TIKTOK_PIXEL_ID` is set. Legal pages live in `public/{privacy,terms,cookies,accessibility}.html` (bilingual, static) and get the operator identity stamped from `src/data/legalEntity.js` by `scripts/stamp-legal.mjs` at build time. `dev-pages/` holds operator-only HTML that must never ship.

**Shadows** (added phase 1, scoped to `:root`):
- `--sh-card`, `--sh-card-hover`, `--sh-modal`, `--sh-drawer`, `--sh-popover`

**Layout shell** (rebuilt phase 2):
- Desktop: right-side `<Sidebar>` (RTL start) + sticky `<Topbar>` + content. Layout is `flex-col md:flex-row` so the sidebar is the first flex child = physical right in RTL
- Mobile: existing `<Navbar>` top bar + bottom-nav + hamburger that opens `<Sidebar mobile>` drawer
- `BrandThemeApplier` in App.jsx still overrides `--color-moca-bolt` / `--color-moca-dark` per workspace (mvno_carrier or brand_config)

**Routing — clean URLs** (added phase 9):
- `/` — Dashboard (CompetitorBoard widget + tab navigation)
- `/plans` `/roaming` `/esim` `/banners` `/history` — all mount `DashboardPage` with a `lockedTab` derived from pathname; tab nav is hidden on these routes. Legacy `?tab=X` URLs still resolve via the searchParams fallback in DashboardPage
- Other routes: `/compare`, `/positioning`, `/alerts`, `/cockpit`, `/executive-summary`, `/archive`, `/ai-insights`, `/preferences`, `/notifications`, `/settings`, `/workspace/users`, `/workspace/settings`, `/admin/workspaces`, `/admin/audit`, `/usage`, `/admin/user-activity`
- **Public routes** (siblings of `/`, outside the AppShell auth gate): `/login`, `/reset-password` (Supabase password-recovery target), `/invite/:token`

PWA icons live in `public/icons/` (180/192/512px). `Logo.jsx` accepts `size` prop (xs/sm/md) and `showSubtext` prop (default true, set false on login page).

## Key UI Components

- **SearchableSelect** (`components/ui/SearchableSelect.jsx`): Custom dropdown with search input, renders via React Portal to avoid clipping
- **PlanCard**: Universal card for all plan types (domestic/abroad/global/resellers/content via `type` prop), supports highlight animation from chat. Content cards skip plan name and info line; all text must use explicit `text-right` or RTL-aware flex (`justify-start`). For `type='resellers'`, the "לאתר הספק" button becomes "לפוסט המקור" and links to `plan.source_url` instead of `CARRIER_HOME_URLS[carrier]`. The DashboardPage `loadTab` injects `"משווק: <label>"` as `extras[0]` so the reseller name appears as a bullet on the card.
- **BannerCard** (`components/BannerCard.jsx`): Carrier screenshot card (16:7 ratio), modal on click, fallback gradient. Used for both homepage banners and e-store banners in the Banners tab
- **GroupedPlanCard** (`components/GroupedPlanCard.jsx`): Used for XPhone "גולשים ומדברים" plans — renders GB selector pills + price + info line (GB · days · minutes · SMS)
- **ChatPanel**: AI chat with clickable carrier names that navigate to filtered dashboard
- **FilterTag**: Compact filter toggle pill used across Dashboard and Compare pages
