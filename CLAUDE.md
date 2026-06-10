# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Israeli cellular plan comparison system branded **MOCA** (Mobile Operators Competitor Analysis), with two frontends:
- **Legacy dashboard**: Flask-served HTML at localhost:5000 (templates/index.html)
- **New React app**: Vite + Tailwind + Supabase Auth at localhost:5173 (mass-market-app/)

Both frontends consume the same Flask REST API. The system scrapes 10 domestic carriers + 27 global eSIM providers twice daily, detects price changes, and sends notifications via Telegram/Email/WhatsApp/Web Push.

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
Python does NOT hot-reload — changes to `db.py` / `app.py` take effect only after Flask
restarts. Flask runs **elevated** (Task Scheduler `CellularComparison` → `flask_watchdog.bat`),
so `taskkill` / `wmic delete` / `Stop-Process` from a normal shell fail with "Access is
denied". Restart it **as administrator**:
```bash
# Right-click scripts/restart_flask.bat → "Run as administrator"
#   → kills the PID listening on :5000; the watchdog relaunches `python app.py` (new code) in ~15s.
# Elevated PowerShell one-liner equivalent:
#   Stop-Process -Id (Get-NetTCPConnection -LocalPort 5000 -State Listen).OwningProcess -Force
# Then hard refresh: Ctrl+Shift+R
```
Stopgap without restarting: regenerate DB-cached data from a FRESH process (loads new code),
e.g. `python -c "import app; app.generate_executive_summary()"` — the server serves the SQLite
cache per request, so the fix shows immediately but reverts on the next server-side regen.

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
| app.py | Flask server, API routes, APScheduler, CORS, API key auth. `CARRIER_DISPLAY` (10 carriers, homepage URLs) and `CARRIER_STORE_DISPLAY` (4 carriers with e-stores) drive the banners API. |
| scraper.py | 40+ scrapers (domestic + abroad + global per-country/regional + content) + `scrape_carrier_banners()` / `scrape_carrier_store_banners()` for screenshots + `scrape_carrier_news()` for Google News RSS |
| db.py | SQLite CRUD — 25 tables with UPSERT logic |
| change_detector.py | Diff old vs new plans, detect price/extras/details changes |
| notifier.py | Format + send notifications (Telegram, Email, WhatsApp, Web Push). `alert_missing_terms()` = post-scrape safety net: if a **new** domestic/roaming plan lands with no "עיקרי התוכנית" link (no `url`/`terms_url`/`__info__`), it Telegrams the operator so the per-provider fetch can be wired in (run the plan-terms-coverage skill). Wired into every scrape path; exempts neptucom domestic + xphone roaming (no terms by design). |
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
| pages/SettingsPage.jsx | Admin panel — scrape triggers, user management (adminOnly). "ניהול משתמשים" tab (super_admin) creates users via direct-DB provisioning (`POST /api/users`, no email — see Security) and resets a user's password via `<AdminResetPasswordModal>` → `POST /api/users/<id>/password`. |
| pages/ExecutiveSummaryPage.jsx | Per-category cards + ₪/GB bar chart + AI narrative, from cached `executive_summaries` (regen 08:05 / `POST /api/executive-summary/refresh`). Metrics from `compute_executive_metrics` (db.py): ₪/GB chart is GB-**weighted** `SUM(price)/SUM(GB)` — a naive `AVG(price/data_gb)` lets a tiny-data plan (e.g. 019's 100MB "חבילת עשר", ~102 ₪/GB) dominate the mean; "המשתלם ביותר" card = `MIN(price/GB)` (best single deal); "האגרסיבי ביותר" shows `—` when there are 0 price drops (no false aggressor) |
| pages/PositioningPage.jsx | Competitive positioning matrix |
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

**Domestic (10)**: partner, pelephone, hotmobile, cellcom, mobile019, xphone, wecom, neptucom, golan, rami_levy
**Abroad**: same carriers, per-country roaming plans (rami_levy_abroad, wecom_abroad, golan_abroad, 019_abroad have dedicated scrapers)
**E-store carriers (4)**: pelephone, cellcom, partner, hotmobile — screenshots saved as `{carrier}_store.png` in `data/banners/`
**Global eSIM (27)**: tuki, globalesim, airalo, pelephone_global (GlobalSIM), esimo, simtlv, world8, xphone_global, saily (199 countries + 8 regions), holafly (182 countries + 16 regions), esimio (183 countries + 10 regions), sparks (143 countries), voye (157 countries + 5 regions + global), orbit (195 countries + 9 zones, REST API at be.orbitmobile.com), travelsim (global + USA + Middle East zones), seven_g (7G), gomoworld (GoMoWorld), tasim, maya (Maya Mobile), bcengi, esim70, jetpack, breez (Breeze), bytesim, bestconnect (Best Connect), besim, esimplus (eSIM Plus). Source of truth: `GLOBAL_LABELS` in carrierLabels.js (29 keys — airalo_local/airalo_regional are aliases of airalo) mirrored by `_CARRIER_NAMES` in app.py.
**Content (5 services × 4 carriers)**: eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי
**Resellers (משווקים)**: independent shops/social pages selling carrier plans at unique prices not on the carrier's own rate card. Currently tracked: `cellcomshefamr` (Instagram, Cellcom). Data is sparse — Israeli reseller market has minimal social-media pricing presence (verified by scanning 1,400 messages across 7 large Israeli deal Telegram channels — zero plan-pricing matches).

## Database Schema (SQLite — data/plans.db)

25 tables. Key constraints: UNIQUE(carrier, plan_name) for plans, UNIQUE(service, carrier) for content, UNIQUE(url) for news, UNIQUE(reseller_id, carrier, plan_name) for resellers.

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
| user_activity | user_email, workspace_id, event_type (login/page_view/alert_created/watchlist_added/watchlist_removed/comparison_saved), path, details (JSON), user_agent, created_at — powers the super-admin user-activity dashboard; super-admins are never recorded |

## Change Detection

change_detector.py compares old vs new plan lists by (carrier, plan_name) key:
- `price_change` — uses original_price for foreign currency (avoids FX false alarms)
- `new_plan` / `removed_plan` — guarded: only marks removed if carrier returned ≥1 plan
- `extras_change` / `details_change` — array/field diffs
- `_coerce()` normalizes '7000' vs 7000 vs 7000.0

`save_plans` and `save_abroad_plans` call `db._delete_stale_carrier_rows()` before the upsert — for any carrier that returned ≥1 plan, rows whose `plan_name` is no longer in the scrape are deleted. This prevents the "stuck removal" loop where a discontinued plan stays in the DB and triggers the same `removed_plan` event on every scrape. `save_global_plans` deliberately skips this guard because some global scrapers are per-country and partial failures are common — global notification dedup is handled by `filter_already_notified()` instead. **(2026-06-04)** That accumulation made partial scrapes flap `removed_plan`/`new_plan` (286K phantom rows in 2 months, bloating the DB), so the **3 global scrape paths in app.py now drop `new_plan`/`removed_plan` right after `detect_changes(...)`** — only `price_change`/`extras_change`/`details_change` are persisted for global (`price_change` still powers the history charts). Domestic/abroad are unaffected.

`db.filter_already_notified(changes, table_name, key_field='carrier', within_hours=24)` reads the corresponding `*_changes` table and drops any change whose (key_field, plan_name, change_type) already appeared in the last N hours. Wired into every scrape path (scheduled job + `/api/scrape-*-now` endpoints) so Telegram / WhatsApp / Web Push / Slack only fire on genuinely new events. Use `key_field='service'` for `content_changes`.

## Security

- Sensitive endpoints protected by `@require_api_key` decorator (auto-generated key in config.json)
- CORS restricted to known origins (configurable via ALLOWED_ORIGINS env var)
- XSS: `escHtml()` sanitizes all scraped data before innerHTML in legacy dashboard
- React app: dev mode auth requires explicit `VITE_DEV_AUTH=true` in .env
- Production auth: Supabase with user_roles table (viewer/admin/super_admin)
- Flask binds to 127.0.0.1 by default (fine for the Cloudflare Tunnel — cloudflared connects to localhost:5000 on the same host; set FLASK_HOST=0.0.0.0 only for direct LAN access)
- **User provisioning is direct-DB, NOT GoTrue signup**: `POST /api/users` (super_admin) writes `auth.users` + `auth.identities` + a workspace-less `user_roles` row in one transaction, email pre-confirmed, password hashed with `crypt(pw, gen_salt('bf', 10))` (pgcrypto). It deliberately does **not** call `/auth/v1/signup` — signup sends a confirmation email on every create (which we then force-confirm anyway), and Supabase's shared email sender rate-limits those to a few/hour, so onboarding >2 users in a row failed with `over_email_send_rate_limit` → the generic "Failed to create user". Direct provisioning sends no email; onboarding mail is our own Welcome email (fired by the workspace-assign step). Mirror a known-good `auth.users`/`auth.identities` row when changing columns — `auth.users.confirmed_at` and `auth.identities.email` are GENERATED (never insert them).
- **Password management** — three flows, no Supabase email except recovery: self-service change (`changePassword` in useAuth → `supabase.auth.updateUser`, profile menu), admin reset (`POST /api/users/<id>/password`, direct-DB bcrypt, super_admin only), and "forgot password" (`resetPasswordForEmail` → `/reset-password` page → `updateUser`). The recovery email is the **only** Supabase email in the user lifecycle; its redirect target `https://mocaintel.com/reset-password` (and `http://localhost:5173/reset-password` for dev) must stay in Supabase → Auth → URL Configuration → Redirect URLs, and the SPA `_redirects` `/*  /index.html  200` rule must serve that path.

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
- Other routes: `/compare`, `/positioning`, `/alerts`, `/executive-summary`, `/archive`, `/ai-insights`, `/preferences`, `/notifications`, `/settings`, `/workspace/users`, `/workspace/settings`, `/admin/workspaces`, `/admin/audit`, `/usage`, `/admin/user-activity`
- **Public routes** (siblings of `/`, outside the AppShell auth gate): `/login`, `/reset-password` (Supabase password-recovery target), `/invite/:token`

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
- Golan uses **two distinct source pages**: `scrape_golan` reads `golantelecom.co.il/offers` (domestic Mass-Market plans — `.offer` cards with `data-gtm-price` + `.properties.israel`/`.properties.roaming` benefit tabs + `.important_info` "פרטי המבצע" bullets; plans whose בחו"ל tab includes browsing get a `NNGB גלישה בחו"ל` extra so PlanCard shows the חו"ל badge). `scrape_golan_abroad` reads `golantelecom.co.il/overseas_offers` (genuine roaming bundles, stored as `abroad_plans`). Do NOT point the abroad scraper at `/offers` — that re-lists the domestic plans as fake roaming. Per-package country lists come from `getCountriesForAbroadPlan` (carrier `golan` → `COUNTRIES_GOLAN`; the מצרים וירדן bundle is matched by `GOLAN_SPECIFIC` to show only those 2 countries). **Visibility differs by page**: `/offers` keeps hidden/legacy `.offer` cards in the DOM (e.g. a discontinued "זוגית") so `scrape_golan` filters to VISIBLE cards only (`offsetParent && height>0`); `/overseas_offers` features 3 cards and parks the other 9 real bundles in `d-none`, so `scrape_golan_abroad` deliberately keeps ALL cards. Both scrapers expand "פרטי המבצע"/"פרטי החבילה" and emit a filtered `__info__|<lines>` extra that PlanCard renders as the "תנאי התוכנית" popup (abroad has no url column, so the popup is its only terms affordance); free-data apps are surfaced as icons via `getAppsForPlan` (`GOLAN_APPS_BY_PLAN` by name for 750GB, else parsed from the "גלישה חופשית באפליקציות: …" extra).

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
- **08:10** — scrape Google News RSS for all 10 domestic carriers + Breeze (`scrape_carrier_news()` → `upsert_news_articles()`), INSERT OR IGNORE by URL
- **08:20** — **morning changes digest** (`run_morning_check_job` in app.py): reads the change LOG (not a live scrape) for the last 26h across all 4 change tables — new/removed plans, price/extras changes — plus **scraper-freshness warnings** (`db.get_scrape_freshness`: carrier stale >36h, 0 plans, or missing from `plans` entirely vs `CARRIER_DISPLAY`), and **always** sends Telegram — an explicit "לא זוהו שינויים" message doubles as a daily heartbeat (no message = job/Flask down). A scraper that silently breaks can never report a new plan it didn't see, so the freshness warnings surface the breakage. Manual trigger / preview: `GET|POST /api/morning-check/now?api_key=…` (`&send=false` returns the digest JSON without sending). config.json knobs (all optional): `morning_check_time` ("08:20"), `morning_check_window_hours` (26), `morning_check_stale_hours` (36), `morning_check_whatsapp` (false)
- **09:00** — send daily Excel email report via Resend SMTP (SendGrid fallback)
- **07:30 + 17:00** — scrape all (domestic + abroad + global + content), detect changes, notify (Telegram + WhatsApp + Web Push). Times come from `config.json:schedule_times`. Notifications are deduplicated against the last 24h of changes — `db.filter_already_notified()` drops any (carrier, plan_name, change_type) already announced, so a sticky removal isn't reported twice.
- WhatsApp via Green API (config.json: greenapi_url, greenapi_instance, greenapi_token, whatsapp_phone or whatsapp_group_id)
- **Autologon ENABLED** (Sysinternals) — the box auto-logs-in as `Alon` at boot, so the at-logon tasks below start **without a manual login** (survives Windows Update / power-blip reboots).
- **Windows Task Scheduler** (RunLevel=Highest unless noted):
  - `CellularComparison` → `scripts/flask_watchdog.ps1` — at logon, loops `python app.py`, restarts Flask 15s after any exit
  - `MOCA-Cloudflared` → `scripts/cloudflared_watchdog.ps1` — at logon, runs the Cloudflare Tunnel `moca` (api.mocaintel.com → :5000), restarts 10s after exit
  - `MOCA-Vite` → `scripts/vite_watchdog.ps1` — at logon, loops `npm run dev`, restarts 10s after exit
  - `MOCA-Ngrok` → **DISABLED 2026-06-04** (ngrok retired; kept as a re-enable-able fallback)
  - `MOCA Morning Health Check` → `scripts/morning_health_check.ps1` — **every 10 min**, checks Flask:5000 / cloudflared(process) / Vite:5173, restarts whatever is down, alerts via Telegram+email
  - `MOCA Daily Backup` → `scripts/backup_to_drive.ps1` — **02:30 + every 4h**
  - Watchdogs log restart events to `scripts/*_watchdog.log`

## Automation Scripts (scripts/)

| File | Purpose |
|------|---------|
| flask_watchdog.bat | Keeps Flask alive — loops `python app.py`, restarts after 15s on any exit |
| restart_flask.bat | Restarts the **elevated** Flask so it reloads backend code — kills the PID on :5000 (watchdog relaunches with new code in ~15s). **Run as administrator.** |
| vite_watchdog.bat | Keeps Vite alive — loops `npm run dev` via cmd (not PowerShell — execution policy blocks npm.ps1) |
| backup_to_drive.ps1 | Backup of config.json + plans.db + banner PNGs to Google Drive — **02:30 + every 4h** (RPO ~4h). Auto-restarts GoogleDriveFS if not mounted. |
| backup_health_check.ps1 | Monthly integrity check: file presence, SQLite PRAGMA integrity_check, row counts per table, Task Scheduler state. Sends email via Resend SMTP (SendGrid fallback). |
| drive_monitor.ps1 | Runs 2×/day, monitors Drive mount health, tracks consecutive failures to avoid alert spam. |
| alert.py | Multi-channel alert sender (Resend SMTP email + Telegram, SendGrid fallback) used by the PS1 scripts. |
| morning_health_check.ps1 | Runs **every 10 min** — checks Flask:5000 / cloudflared(process) / Vite:5173, restarts any that are down, alerts via Telegram+email. |
| cloudflared.exe + cloudflared_watchdog.ps1 | **Cloudflare Tunnel** binary + watchdog: loops `cloudflared tunnel run moca` (config `~/.cloudflared/config.yml`: api.mocaintel.com → localhost:5000). The public ingress — replaced ngrok 2026-06-04. |
| ngrok_watchdog.ps1 | (Task DISABLED 2026-06-04) loops `ngrok http 5000 --domain=…` — kept as a re-enable-able fallback. |
| db_compress_and_prune.py | One-time DB maintenance: snapshot → zlib-compress archive_snapshots → delete global_changes flap noise → VACUUM (shrank DB 421→43MB). |

## Archive System

`archive.py` stores historical plan snapshots (table `archive_snapshots`, browsable via `ArchivePage.jsx` / Time Machine):
- One snapshot per (carrier, plan_type) per day (`save_plan_snapshot` skips if today's already exists); a `content_hash` is also stored
- **`plans_json` is zlib-compressed (2026-06-04)** via `_archive_encode`/`_archive_decode` in db.py — written compressed in `insert_archive_snapshot`, decompressed in `get_archive_plans`. Backward-compatible (bytes=compressed, str=legacy). Shrank this table ~19× (was 305MB of raw JSON — the bulk of a 421MB DB → now ~18MB). Lossless; all history kept
- Banner snapshots (PNGs) live in `data/archive/banners/`

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
- `VITE_API_URL` — Flask API base URL (empty = proxy via Vite; production build = https://api.mocaintel.com via .env.production). Code fallback is `''` (no hardcoded URL)
- `VITE_API_KEY` — Flask API key for protected endpoints (fallback hardcoded)
- `VITE_DEV_AUTH` — set to "true" for auto-login as admin in dev (`.env` only, never in production)

### Production Build
`.env.production` overrides `.env` during `npm run build` — sets `VITE_DEV_AUTH=false` to ensure login is required. Never set `VITE_DEV_AUTH=true` in Netlify env vars or `.env.production`.

## Deployment

- **Frontend**: Netlify, served at **https://mocaintel.com** (canonical; `www.mocaintel.com` 301-redirects to it; custom domain via Cloudflare DNS — the `lucent-kulfi-f037ad.netlify.app` subdomain still resolves) — drag `mass-market-app/dist` manually
- **Backend**: Local Flask, exposed via **Cloudflare Tunnel** → https://api.mocaintel.com (cloudflared tunnel "moca", run by the **MOCA-Cloudflared** task / `scripts/cloudflared_watchdog.ps1`). ngrok retired 2026-06-04 (MOCA-Ngrok task disabled + kept as fallback; reserved domain still on the account)
- **Auth**: Supabase (https://gmfefvjdmgzluwffzrzj.supabase.co)
- **Code**: GitHub (https://github.com/AYochelman/Mobile-Operators-Competitor-Analysis)
- **Build command**: `cd mass-market-app && npm install && npm run build`
- **Publish directory**: `mass-market-app/dist`
- Netlify env vars must include: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL, VITE_API_KEY (NOT VITE_DEV_AUTH)
- All API requests include `ngrok-skip-browser-warning: true` header (legacy from ngrok; harmless/ignored now that ingress is Cloudflare)

## Key UI Components

- **SearchableSelect** (`components/ui/SearchableSelect.jsx`): Custom dropdown with search input, renders via React Portal to avoid clipping
- **PlanCard**: Universal card for all plan types (domestic/abroad/global/resellers/content via `type` prop), supports highlight animation from chat. Content cards skip plan name and info line; all text must use explicit `text-right` or RTL-aware flex (`justify-start`). For `type='resellers'`, the "לאתר הספק" button becomes "לפוסט המקור" and links to `plan.source_url` instead of `CARRIER_HOME_URLS[carrier]`. The DashboardPage `loadTab` injects `"משווק: <label>"` as `extras[0]` so the reseller name appears as a bullet on the card.
- **BannerCard** (`components/BannerCard.jsx`): Carrier screenshot card (16:7 ratio), modal on click, fallback gradient. Used for both homepage banners and e-store banners in the Banners tab
- **GroupedPlanCard** (`components/GroupedPlanCard.jsx`): Used for XPhone "גולשים ומדברים" plans — renders GB selector pills + price + info line (GB · days · minutes · SMS)
- **ChatPanel**: AI chat with clickable carrier names that navigate to filtered dashboard
- **FilterTag**: Compact filter toggle pill used across Dashboard and Compare pages

## After Every Code Change

Always run `npm run build` in `mass-market-app/` after any React/JS change. The `dist/` folder is deployed to Netlify manually by dragging.
