# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Israeli cellular plan comparison system branded **MOCA** (Mobile Operators Competitor Analysis), with two frontends:
- **Legacy dashboard**: Flask-served HTML at localhost:5000 (templates/index.html)
- **New React app**: Vite + Tailwind + Supabase Auth at localhost:5173 (mass-market-app/)

Both frontends consume the same Flask REST API. The system scrapes 7 domestic carriers + 13 global eSIM providers twice daily, detects price changes, and sends notifications via Telegram/Email/Web Push.

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
taskkill /F /IM python.exe       # Kill Flask (Windows)
python app.py                    # Restart
# Then hard refresh: Ctrl+Shift+R
```

### Manual Scrape (requires API key from config.json)
```
GET http://localhost:5000/api/scrape-all-now?api_key=<KEY>
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
│  ├─ /api/scrape-*-now (@require_api_key)             │
│  ├─ /api/chat (Claude AI, @require_api_key)          │
│  └─ /api/push/* (Web Push VAPID)                     │
├──────────────────────────────────────────────────────┤
│  APScheduler: 10:00+16:00 scrape, 09:00 email report │
├──────────────────────────────────────────────────────┤
│  scraper.py (Playwright sync) → change_detector.py   │
│  → db.py (SQLite) → notifier.py (Telegram/Email/Push)│
└──────────────────────────────────────────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| app.py | Flask server, API routes, APScheduler, CORS, API key auth |
| scraper.py | 40+ scrapers (domestic + abroad + global per-country/regional + content) |
| db.py | SQLite CRUD — 9 tables with UPSERT logic |
| change_detector.py | Diff old vs new plans, detect price/extras/details changes |
| notifier.py | Format + send notifications (Telegram, Email, Web Push) |
| excel_report.py | Daily Excel report (openpyxl, RTL, yellow=changed) |
| config.json | All credentials — NOT in git, auto-generates VAPID keys |
| templates/index.html | Legacy RTL Hebrew dashboard (2,300+ lines, escHtml XSS protection) |

## React App Structure (mass-market-app/src/)

| Path | Purpose |
|------|---------|
| pages/DashboardPage.jsx | Main 4-tab view (domestic/abroad/global/content) with filters |
| pages/ComparePage.jsx | Price comparison charts (Recharts) |
| pages/AlertsPage.jsx | Personal price alerts with DB persistence |
| pages/SettingsPage.jsx | Admin panel — scrape triggers, user management |
| components/Logo.jsx | MOCA brand logo (bolt + wordmark), sizes: xs/sm/md |
| components/PlanCard.jsx | Universal plan card with country/apps modals |
| components/ChatPanel.jsx | AI chat (🤖 floating button → /api/chat) |
| data/globalCountries.js | Country lists for 13 global providers + getCountriesForPlan() |
| data/abroadCountries.js | Country lists for 7 domestic carriers + getCountriesForAbroadPlan() |
| data/abroadApps.js | Free app lists (Cellcom 6 apps, Pelephone 12 apps) |
| hooks/useAuth.jsx | Supabase Auth + dev mode (VITE_DEV_AUTH=true) |
| lib/api.js | Flask API wrapper with JWT headers |
| lib/supabase.js | Supabase client (graceful null if unconfigured) |

## Carriers & Providers

**Domestic (7)**: partner, pelephone, hotmobile, cellcom, mobile019, xphone, wecom
**Abroad (7)**: same carriers, per-country roaming plans
**Global eSIM (13)**: tuki, globalesim, airalo, pelephone_global, esimo, simtlv, world8, xphone_global, saily (199 countries + 8 regions), holafly (182 countries + 16 regions), esimio (183 countries + 10 regions), sparks (143 countries), voye (157 countries + 5 regions + global)
**Content (5 services × 4 carriers)**: eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי

## Database Schema (SQLite — data/plans.db)

9 tables. Key constraints: UNIQUE(carrier, plan_name) for plans, UNIQUE(service, carrier) for content.

| Table | Key Fields |
|-------|-----------|
| plans | carrier, plan_name, price, data_gb, minutes, extras, scraped_at |
| changes | carrier, plan_name, change_type, old_val, new_val, changed_at |
| abroad_plans | + days, sms |
| global_plans | + currency, original_price, days, sms, esim |
| content_plans | service, carrier, price, free_trial, note, status |
| push_subscriptions | endpoint, p256dh, auth |

## Change Detection

change_detector.py compares old vs new plan lists by (carrier, plan_name) key:
- `price_change` — uses original_price for foreign currency (avoids FX false alarms)
- `new_plan` / `removed_plan` — guarded: only marks removed if carrier returned ≥1 plan
- `extras_change` / `details_change` — array/field diffs
- `_coerce()` normalizes '7000' vs 7000 vs 7000.0

## Security

- Sensitive endpoints protected by `@require_api_key` decorator (auto-generated key in config.json)
- CORS restricted to known origins (configurable via ALLOWED_ORIGINS env var)
- XSS: `escHtml()` sanitizes all scraped data before innerHTML in legacy dashboard
- React app: dev mode auth requires explicit `VITE_DEV_AUTH=true` in .env
- Production auth: Supabase with user_roles table (admin/viewer)
- Flask binds to 127.0.0.1 by default (set FLASK_HOST=0.0.0.0 for ngrok)

## Brand & UI

The React app uses a **mocha-latte** color palette defined in `index.css` `@theme` block:
- Body background: `#f9f4ee` (light cream)
- Primary actions / active states: `#5c3317` (espresso)
- Hover backgrounds: `#f5ede0` (cream)
- Filter/card borders: `border-moca-border/60` (subtle, rounded-xl)
- Carrier/provider badge colors (blue, green, orange, etc.) are intentionally preserved

PWA icons live in `public/icons/` (180/192/512px). `Logo.jsx` accepts `size` prop (xs/sm/md) and `showSubtext` prop (default true, set false on login page).

## Conventions

- All Hebrew text uses unicode escapes in Python (`"\u05d9\u05e9\u05e8\u05d0\u05dc"` for ישראל)
- Plan names use ` – ` (en-dash with spaces) as separator
- data_gb: None = unlimited, ≥1 = GB, <1 = MB (stored as fraction: 100MB = 100/1024)
- extras[0] = country/region name for destination filtering (global/abroad plans)
- Scraper functions take a Playwright Page object, return list of plan dicts
- `_make_global_plan()` helper standardizes global plan dict creation
- Slug-to-Hebrew dictionaries (SAILY_SLUG_TO_HEBREW, ESIMIO_SLUG_TO_HEBREW, HOLAFLY_SLUG_TO_HEBREW) for per-country scrapers

## Schedule

- **10:00 + 16:00** — scrape all (domestic + abroad + global + content), detect changes, notify
- **09:00** — send daily Excel email report via SendGrid
- Windows Task Scheduler: task "CellularComparison" at logon runs `python app.py`

## Environment Variables

### Flask (.env or config.json)
- `FLASK_HOST` — bind address (default: 127.0.0.1)
- `ALLOWED_ORIGINS` — comma-separated CORS origins

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
- **PlanCard**: Universal card for all plan types, supports highlight animation from chat
- **ChatPanel**: AI chat with clickable carrier names that navigate to filtered dashboard
- **FilterTag**: Compact filter toggle pill used across Dashboard and Compare pages
