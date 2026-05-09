# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Israeli cellular plan comparison system branded **MOCA** (Mobile Operators Competitor Analysis), with two frontends:
- **Legacy dashboard**: Flask-served HTML at localhost:5000 (templates/index.html)
- **New React app**: Vite + Tailwind + Supabase Auth at localhost:5173 (mass-market-app/)

Both frontends consume the same Flask REST API. The system scrapes 8 domestic carriers + 14 global eSIM providers twice daily, detects price changes, and sends notifications via Telegram/Email/WhatsApp/Web Push.

## Commands

### Flask Backend
```bash
cd "D:\השוואת MASS MARKET"
python app.py                    # Start server on port 5000
pytest tests/ -v                 # Run all tests
pytest tests/test_scraper.py -v  # Run single test file
```

### React Frontend
```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run dev                      # Dev server (port 5173)
npm run build                    # Production build → dist/
npm run lint                     # ESLint
```

### After Code Changes
```bash
# Kill Flask (Windows — taskkill /F fails with Hebrew paths, use wmic):
wmic process where "name='python.exe'" get processid,commandline
wmic process where processid=<PID> delete
python app.py                    # Restart
# Then hard refresh: Ctrl+Shift+R
```

### Manual Scrape (requires API key from config.json)
```
GET http://localhost:5000/api/scrape-all-now?api_key=<KEY>
```

### Reseller Plans (משווקים tab)
```bash
python seed_resellers.py                            # seed/upsert manually-curated reseller plans
python telegram_resellers.py login_request          # phase 1: send code to user's Telegram app
python telegram_resellers.py login_verify <code>    # phase 2: complete sign-in (one-time)
python telegram_resellers.py scrape                 # ingest channels listed in config.json
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  React App (mass-market-app/)     │  Legacy HTML    │
│  Vite + Tailwind + Supabase Auth  │  templates/     │
│  localhost:5173                    │  localhost:5000  │
└──────────────┬────────────────────┴────────┬────────┘
               │         REST API            │
┌──────────────▼─────────────────────────────▼────────┐
│  Flask (app.py) — port 5000                          │
│  ├─ /api/plans, /api/abroad-plans, /api/global-plans │
│  ├─ /api/changes, /api/abroad-changes, etc.          │
│  ├─ /api/banners, /api/store-banners (screenshots)   │
│  ├─ /banners/<file> (serves PNG files)               │
│  ├─ /api/scrape-*-now (@require_api_key)             │
│  ├─ /api/chat (Claude AI, @require_api_key)          │
│  └─ /api/push/* (Web Push VAPID)                     │
├──────────────────────────────────────────────────────┤
│  APScheduler: 08:00 banners, 08:10 news, 09:00 email, 07:30+17:00 scrape │
├──────────────────────────────────────────────────────┤
│  scraper.py (Playwright sync) → change_detector.py   │
│  → db.py (SQLite) → notifier.py (Telegram/Email/Push)│
└──────────────────────────────────────────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| app.py | Flask server, API routes, APScheduler, CORS, API key auth. `CARRIER_DISPLAY` (8 carriers, homepage URLs) and `CARRIER_STORE_DISPLAY` (4 carriers with e-stores) drive the banners API. |
| scraper.py | 40+ scrapers (domestic + abroad + global per-country/regional + content) + `scrape_carrier_banners()` / `scrape_carrier_store_banners()` for screenshots + `scrape_carrier_news()` for Google News RSS |
| db.py | SQLite CRUD — 11 tables with UPSERT logic |
| change_detector.py | Diff old vs new plans, detect price/extras/details changes |
| notifier.py | Format + send notifications (Telegram, Email, WhatsApp, Web Push) |
| excel_report.py | Daily Excel report (openpyxl, RTL, yellow=changed) |
| seed_resellers.py | Manually-curated reseller plan data — UPSERTs `reseller_plans` table |
| telegram_resellers.py | Telethon-based scraper for public Telegram channels → `reseller_plans`. Two-phase login flow. |
| config.json | All credentials — NOT in git, auto-generates VAPID keys |
| templates/index.html | Legacy RTL Hebrew dashboard (2,300+ lines, escHtml XSS protection) |

## React App Structure (mass-market-app/src/)

### Pages

| Path | Purpose |
|------|---------|
| pages/DashboardPage.jsx | Main 8-tab view (domestic/abroad/global/**resellers**/content/banners/history/news) with filters. **Lazy-loaded** since phase 15. `RESELLERS` const lists reseller IDs+labels mapped to underlying carriers. Reads `lockedTab` from `useLocation().pathname` — when on a clean URL like `/plans` or `/banners` the tab navigation hides and `setTab` navigates instead of mutating state. |
| pages/ComparePage.jsx | Price comparison charts (Recharts) |
| pages/AlertsPage.jsx | Personal price alerts with DB persistence |
| pages/SettingsPage.jsx | Admin panel — scrape triggers, user management (adminOnly) |
| pages/ExecutiveSummaryPage.jsx | Summary stats + MarketMoversWidget + SparklineMini charts |
| pages/PositioningPage.jsx | Competitive positioning matrix |
| pages/ArchivePage.jsx | Historical plan snapshots (content-hash based, via archive.py) |
| pages/PreferencesPage.jsx | Per-user display preferences |
| pages/NotificationsPage.jsx | Web Push / notification settings |
| pages/WorkspaceUsersPage.jsx | Manage users in current workspace (adminOnly) |
| pages/WorkspaceBrandingPage.jsx | Workspace logo, colors, MVNO theme (adminOnly) |
| pages/WorkspacesAdminPage.jsx | Global workspace CRUD (superAdminOnly) |
| pages/AuditLogPage.jsx | Action audit trail (superAdminOnly) |

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
| components/ViewAsBanner.jsx | Super-admin "viewing as workspace X" banner. Rendered inside Layout (above the sidebar+main flex row) — not sticky |
| components/CarrierAIInsights.jsx | Per-carrier AI summary widget. Used inline in DashboardPage; `/ai-insights` page uses its own feed-style layout |
| components/MarketMoversWidget.jsx | Biggest price changes since last scrape |
| components/SparklineMini.jsx | Inline price-history sparkline (Recharts) — API-fetching variant |
| components/SavedComparesMenu.jsx | Save/load named comparison filter sets |
| components/SavedViewsMenu.jsx | Save/load named dashboard filter states |
| components/PriceHistoryModal.jsx | Full price history chart for a single plan |
| components/OfflineBanner.jsx | Offline detection banner (useOnlineStatus) |

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
| lib/api.js | Flask API wrapper with JWT headers |
| lib/supabase.js | Supabase client (graceful null if unconfigured) |

### Data Files

| Path | Purpose |
|------|---------|
| data/carrierLabels.js | **Single source of truth** for carrier ID → display name. Exports `carrierLabel(id)`, `DOMESTIC_LABELS`, `GLOBAL_LABELS`. Mirror in app.py: `_CARRIER_NAMES`. Update both together when adding a carrier. |
| data/mvnoBrandColors.js | MVNO-specific primary/secondary colors. `getMvnoColors(mvno_carrier)` used by `BrandThemeApplier` in App.jsx to set `--color-moca-bolt` / `--color-moca-dark` CSS vars. |
| data/globalCountries.js | Country lists for global eSIM providers + getCountriesForPlan() |
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

## Carriers & Providers

**Domestic (8)**: partner, pelephone, hotmobile, cellcom, mobile019, xphone, wecom, neptucom
**Abroad (8)**: same carriers, per-country roaming plans
**E-store carriers (4)**: pelephone, cellcom, partner, hotmobile — screenshots saved as `{carrier}_store.png` in `data/banners/`
**Global eSIM (15)**: tuki, globalesim, airalo, pelephone_global, esimo, simtlv, world8, xphone_global, saily (199 countries + 8 regions), holafly (182 countries + 16 regions), esimio (183 countries + 10 regions), sparks (143 countries), voye (157 countries + 5 regions + global), orbit (195 countries + 9 zones, REST API at be.orbitmobile.com), travelsim (global + USA + Middle East zones)
**Content (5 services × 4 carriers)**: eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי
**Resellers (משווקים)**: independent shops/social pages selling carrier plans at unique prices not on the carrier's own rate card. Currently tracked: `cellcomshefamr` (Instagram, Cellcom). Data is sparse — Israeli reseller market has minimal social-media pricing presence (verified by scanning 1,400 messages across 7 large Israeli deal Telegram channels — zero plan-pricing matches).

## Database Schema (SQLite — data/plans.db)

11 tables. Key constraints: UNIQUE(carrier, plan_name) for plans, UNIQUE(service, carrier) for content, UNIQUE(url) for news, UNIQUE(reseller_id, carrier, plan_name) for resellers.

| Table | Key Fields |
|-------|-----------|
| plans | carrier, plan_name, price, data_gb, minutes, extras, scraped_at |
| changes | carrier, plan_name, change_type, old_val, new_val, changed_at |
| abroad_plans | + days, sms |
| global_plans | + currency, original_price, days, sms, esim |
| content_plans | service, carrier, price, free_trial, note, status |
| reseller_plans | reseller_id, carrier (underlying), plan_name, price, data_gb, minutes, sms, extras (JSON), source_url, seen_at |
| push_subscriptions | endpoint, p256dh, auth |
| news_articles | carrier, headline, url (UNIQUE), source, published_at (ISO 8601), fetched_at |

## Change Detection

change_detector.py compares old vs new plan lists by (carrier, plan_name) key:
- `price_change` — uses original_price for foreign currency (avoids FX false alarms)
- `new_plan` / `removed_plan` — guarded: only marks removed if carrier returned ≥1 plan
- `extras_change` / `details_change` — array/field diffs
- `_coerce()` normalizes '7000' vs 7000 vs 7000.0

`save_plans` and `save_abroad_plans` call `db._delete_stale_carrier_rows()` before the upsert — for any carrier that returned ≥1 plan, rows whose `plan_name` is no longer in the scrape are deleted. This prevents the "stuck removal" loop where a discontinued plan stays in the DB and triggers the same `removed_plan` event on every scrape. `save_global_plans` deliberately skips this guard because some global scrapers are per-country and partial failures are common — global notification dedup is handled by `filter_already_notified()` instead.

`db.filter_already_notified(changes, table_name, key_field='carrier', within_hours=24)` reads the corresponding `*_changes` table and drops any change whose (key_field, plan_name, change_type) already appeared in the last N hours. Wired into every scrape path (scheduled job + `/api/scrape-*-now` endpoints) so Telegram / WhatsApp / Web Push / Slack only fire on genuinely new events. Use `key_field='service'` for `content_changes`.

## Security

- Sensitive endpoints protected by `@require_api_key` decorator (auto-generated key in config.json)
- CORS restricted to known origins (configurable via ALLOWED_ORIGINS env var)
- XSS: `escHtml()` sanitizes all scraped data before innerHTML in legacy dashboard
- React app: dev mode auth requires explicit `VITE_DEV_AUTH=true` in .env
- Production auth: Supabase with user_roles table (viewer/admin/super_admin)
- Flask binds to 127.0.0.1 by default (set FLASK_HOST=0.0.0.0 for ngrok)

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
- `--font-display: 'Frank Ruhl Libre', serif` — page titles, big headings
- `--font-body: 'Assistant', system-ui, sans-serif` — everything else (set on `body`)
- Both loaded via `<link>` in `index.html` from Google Fonts

**Shadows** (added phase 1, scoped to `:root`):
- `--sh-card`, `--sh-card-hover`, `--sh-modal`, `--sh-drawer`, `--sh-popover`

**Layout shell** (rebuilt phase 2):
- Desktop: right-side `<Sidebar>` (RTL start) + sticky `<Topbar>` + content. Layout is `flex-col md:flex-row` so the sidebar is the first flex child = physical right in RTL
- Mobile: existing `<Navbar>` top bar + bottom-nav + hamburger that opens `<Sidebar mobile>` drawer
- `BrandThemeApplier` in App.jsx still overrides `--color-moca-bolt` / `--color-moca-dark` per workspace (mvno_carrier or brand_config)

**Routing — clean URLs** (added phase 9):
- `/` — Dashboard (CompetitorBoard widget + tab navigation)
- `/plans` `/roaming` `/esim` `/banners` `/history` — all mount `DashboardPage` with a `lockedTab` derived from pathname; tab nav is hidden on these routes. Legacy `?tab=X` URLs still resolve via the searchParams fallback in DashboardPage
- Other routes: `/compare`, `/positioning`, `/alerts`, `/executive-summary`, `/archive`, `/ai-insights`, `/preferences`, `/notifications`, `/settings`, `/workspace/users`, `/workspace/settings`, `/admin/workspaces`, `/admin/audit`

PWA icons live in `public/icons/` (180/192/512px). `Logo.jsx` accepts `size` prop (xs/sm/md) and `showSubtext` prop (default true, set false on login page).

## Conventions

- All Hebrew text uses unicode escapes in Python (`"\u05d9\u05e9\u05e8\u05d0\u05dc"` for ישראל)
- **JSX text nodes**: `\uXXXX` escapes are NOT interpreted in JSX text content — they render as literal backslash characters. Use literal Hebrew characters directly in JSX text, or wrap in `{'...'}` / template literals for JS string context. Only Python files should use unicode escapes.
- Plan names use ` – ` (en-dash with spaces) as separator; Orbit uses ` - ` (hyphen) to avoid BiDi rendering issues
- data_gb: None = unlimited, ≥1 = GB, <1 = MB (stored as fraction: 100MB = 100/1024)
- extras[0] = country/region name for destination filtering (global/abroad plans)
- Scraper functions take a Playwright Page object, return list of plan dicts
- `_dismiss_popups(page)` is called before every banner screenshot — tries Escape key then iterates `_POPUP_CLOSE_SELECTORS`. Partner's e-store uses an Adoric popup (`.closeLightboxButton`); store scraper waits 4s (vs 2s for homepages) to let delayed popups appear before dismissal
- `_make_global_plan()` helper standardizes global plan dict creation
- Slug-to-Hebrew dictionaries (SAILY_SLUG_TO_HEBREW, ESIMIO_SLUG_TO_HEBREW, HOLAFLY_SLUG_TO_HEBREW, ORBIT_NAME_TO_HEBREW) for per-country scrapers
- Orbit uses REST API (no Playwright): ORBIT_NAME_TO_HEBREW maps English→Hebrew, ORBIT_ZONE_TO_HEBREW maps zone IDs→Hebrew
- Tuki scraper has `_tuki_name_fix` dict to normalize country names from their API (e.g. "שוודיה"→"שבדיה")

### Country Name Normalization

`db.py` contains `_DEST_NORM` — a dict applied on every DB write to canonicalize country names across all scrapers. When a scraper returns a non-canonical name, add a mapping here rather than fixing each scraper individually. Canonical names are defined by what appears in `globalCountries.js` / `abroadCountries.js`.

### Multi-Country Provider Filtering (DashboardPage / ComparePage)

Some global providers sell a single plan that covers many countries (e.g. SimTLV, TravelSim, World8, Airalo, GlobaleSIM, eSIMo, XPhone Global, GlobalSIM). These are tracked in `MULTI_COUNTRY_CARRIERS` Set in `DashboardPage.jsx`. Their country coverage is defined as static arrays in `globalCountries.js` and resolved at runtime by `getPlanCoverage(plan)`:

```js
// Returns string[] of covered countries, or null for single-country plans
function getPlanCoverage(plan) { ... }
```

- `globalDestinations` useMemo: for MULTI_COUNTRY_CARRIERS, expands all covered countries into the dropdown instead of using extras[0]
- `filteredPlans`: for MULTI_COUNTRY_CARRIERS, matches via `getPlanCoverage(p).includes(destination)` instead of `extras[0] === destination`
- `CARRIER_COUNTRY_LISTS` in ComparePage mirrors this for the comparison chart's country filter

When adding a new multi-country provider: add arrays to `globalCountries.js`, add the carrier id to `MULTI_COUNTRY_CARRIERS`, add a branch in `getPlanCoverage()`, and add to `CARRIER_COUNTRY_LISTS` in ComparePage.

### RTL Layout Pitfalls

The global `direction: rtl` in `index.css` affects flex containers differently from text elements:
- `text-right` (`text-align: right`) = always physical right edge ✓
- `justify-end` in RTL flex = physical **left** edge ✗ — use `justify-start` instead
- `justify-start` in RTL flex = physical **right** edge ✓
- Icons inside flex rows: in RTL flex the first child renders on the right, so place the icon before the text in JSX to have it appear to the left of the text visually

### PlanCard const-ordering pitfall (TDZ)

PlanCard.jsx declares many derived consts at the top of the function body. **Any const that references `carrier` (e.g. `CARRIER_HOME_URLS[carrier]`) must be declared AFTER `const carrier = plan.carrier`** — otherwise the JS Temporal Dead Zone throws `ReferenceError: Cannot access 'carrier' before initialization`, which crashes PlanCard, which unmounts the entire dashboard, leaving a blank screen with no visible error in production. The error appears in dev console only. Same rule for `isGlobal`/`isAbroad`/`isContent`/`isReseller` references that depend on `type` — those are declared early so they can be referenced anywhere in the function body.

## Resellers tab + Telegram scraper

The "משווקים" tab (between גלובלי and תוכן) shows independent reseller offers that don't appear on the carrier's own site. Two ingest paths:

1. **Manual transcription** — `seed_resellers.py` is a runnable script with a `PLANS` array. Edit + run to upsert. Source URLs (Instagram/Facebook posts) become click-through targets via PlanCard's "לפוסט המקור" button. PlanCard checks `type === 'resellers'` and uses `plan.source_url` instead of `CARRIER_HOME_URLS[carrier]`.

2. **Telegram channels** — `telegram_resellers.py` uses Telethon (free) to fetch messages from public channels in `config.json -> telegram_reseller_channels`. Filter logic: must contain a carrier name (`סלקום`/`פלאפון`/`פרטנר`/`הוט מובייל` or English) AND a price match (`\d+\s*(?:₪|ש"ח)`) between 5-500. Login is two-phase (`login_request` → user receives code in Telegram app → `login_verify <code>`). Session persists in `data/telegram_session.session` (gitignored).

PriceHistoryModal has a `HAS_HISTORY` whitelist (`['domestic', 'abroad', 'global', 'content']`). For other plan types (e.g. `resellers`) it skips the API call and renders the empty state — no error toast. The backend's `/api/history/price-series` rejects unknown plan_types with 400, so the whitelist must stay in sync.

## Schedule

- **08:00** — screenshot all carrier homepages (`scrape_carrier_banners`) + 4 e-store pages (`scrape_carrier_store_banners`), saved as PNG in `data/banners/`
- **08:10** — scrape Google News RSS for all 8 carriers (`scrape_carrier_news()` → `upsert_news_articles()`), INSERT OR IGNORE by URL
- **09:00** — send daily Excel email report via SendGrid
- **07:30 + 17:00** — scrape all (domestic + abroad + global + content), detect changes, notify (Telegram + WhatsApp + Web Push). Times come from `config.json:schedule_times`. Notifications are deduplicated against the last 24h of changes — `db.filter_already_notified()` drops any (carrier, plan_name, change_type) already announced, so a sticky removal isn't reported twice.
- WhatsApp via Green API (config.json: greenapi_url, greenapi_instance, greenapi_token, whatsapp_phone or whatsapp_group_id)
- **Windows Task Scheduler**: two tasks at logon:
  - `CellularComparison` → runs `scripts/flask_watchdog.bat` (infinite loop, restarts Flask on crash, 15s delay)
  - `MOCA-Vite` → runs `scripts/vite_watchdog.bat` (infinite loop, restarts Vite on crash, 10s delay)
  - Both log restart events to `scripts/flask_watchdog.log` / `scripts/vite_watchdog.log`

## Automation Scripts (scripts/)

| File | Purpose |
|------|---------|
| flask_watchdog.bat | Keeps Flask alive — loops `python app.py`, restarts after 15s on any exit |
| vite_watchdog.bat | Keeps Vite alive — loops `npm run dev` via cmd (not PowerShell — execution policy blocks npm.ps1) |
| backup_to_drive.ps1 | Daily backup of config.json + plans.db + banner PNGs to Google Drive. Auto-restarts GoogleDriveFS if not mounted. |
| backup_health_check.ps1 | Monthly integrity check: file presence, SQLite PRAGMA integrity_check, row counts per table, Task Scheduler state. Sends email via SendGrid. |
| drive_monitor.ps1 | Runs 2×/day, monitors Drive mount health, tracks consecutive failures to avoid alert spam. |
| alert.py | Multi-channel alert sender (SendGrid + Telegram) used by the PS1 scripts. |

## Archive System

`archive.py` stores historical plan snapshots using content hashing:
- After each scrape, compares SHA-256 of scraped data against last archived snapshot
- Only writes a new snapshot file when content actually changed (storage-efficient)
- Snapshots live in `data/archive/` — browsable via `ArchivePage.jsx`

## Environment Variables

### Flask (.env or config.json)
- `FLASK_HOST` — bind address (default: 127.0.0.1)
- `ALLOWED_ORIGINS` — comma-separated CORS origins

### Telegram (config.json)
- `telegram_api_id` / `telegram_api_hash` — from https://my.telegram.org → API development tools
- `telegram_user_phone` — international format `+972...`
- `telegram_reseller_channels` — array of `{username, label, limit}` or plain usernames

### React (mass-market-app/.env)
- `VITE_SUPABASE_URL` — Supabase project URL
- `VITE_SUPABASE_ANON_KEY` — Supabase anon key
- `VITE_API_URL` — Flask API base URL (empty = proxy via Vite, fallback hardcoded to ngrok URL)
- `VITE_API_KEY` — Flask API key for protected endpoints (fallback hardcoded)
- `VITE_DEV_AUTH` — set to "true" for auto-login as admin in dev (`.env` only, never in production)

### Production Build
`.env.production` overrides `.env` during `npm run build` — sets `VITE_DEV_AUTH=false` to ensure login is required. Never set `VITE_DEV_AUTH=true` in Netlify env vars or `.env.production`.

## Deployment

- **Frontend**: Netlify (https://lucent-kulfi-f037ad.netlify.app) — drag `mass-market-app/dist` manually
- **Backend**: Local Flask + ngrok tunnel (https://terra-nonrestrained-overpiteously.ngrok-free.dev)
- **Auth**: Supabase (https://gmfefvjdmgzluwffzrzj.supabase.co)
- **Code**: GitHub (https://github.com/AYochelman/Mobile-Operators-Competitor-Analysis)
- **Build command**: `cd mass-market-app && npm install && npm run build`
- **Publish directory**: `mass-market-app/dist`
- Netlify env vars must include: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL, VITE_API_KEY (NOT VITE_DEV_AUTH)
- All API requests include `ngrok-skip-browser-warning: true` header

## Key UI Components

- **SearchableSelect** (`components/ui/SearchableSelect.jsx`): Custom dropdown with search input, renders via React Portal to avoid clipping
- **PlanCard**: Universal card for all plan types (domestic/abroad/global/resellers/content via `type` prop), supports highlight animation from chat. Content cards skip plan name and info line; all text must use explicit `text-right` or RTL-aware flex (`justify-start`). For `type='resellers'`, the "לאתר הספק" button becomes "לפוסט המקור" and links to `plan.source_url` instead of `CARRIER_HOME_URLS[carrier]`. The DashboardPage `loadTab` injects `"משווק: <label>"` as `extras[0]` so the reseller name appears as a bullet on the card.
- **BannerCard** (`components/BannerCard.jsx`): Carrier screenshot card (16:7 ratio), modal on click, fallback gradient. Used for both homepage banners and e-store banners in the Banners tab
- **GroupedPlanCard** (`components/GroupedPlanCard.jsx`): Used for XPhone "גולשים ומדברים" plans — renders GB selector pills + price + info line (GB · days · minutes · SMS)
- **ChatPanel**: AI chat with clickable carrier names that navigate to filtered dashboard
- **FilterTag**: Compact filter toggle pill used across Dashboard and Compare pages

## After Every Code Change

Always run `npm run build` in `mass-market-app/` after any React/JS change. The `dist/` folder is deployed to Netlify manually by dragging.
