# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Israeli cellular plan comparison system branded **MOCA** (Mobile Operators Competitor Analysis), with two frontends:
- **Legacy dashboard**: Flask-served HTML at localhost:5000 (templates/index.html)
- **New React app**: Vite + Tailwind + Supabase Auth at localhost:5173 (mass-market-app/)

Both frontends consume the same Flask REST API. The system scrapes 10 domestic carriers + 38 global eSIM providers twice daily, detects price changes, and sends notifications via Telegram/Email/WhatsApp/Web Push.

## Commands

### Flask Backend
```bash
cd "D:\השוואת MASS MARKET"
python app.py                    # Start server on port 5000
pytest -q                        # Unit suite (~8s). pytest.ini deselects @integration by default
pytest -m integration -v         # Live carrier/provider tests (Playwright + internet, ~2.5 min)
pytest tests/test_scraper_fixtures.py -q   # Offline replay of the pure-HTTP scrapers (tests/fixtures/http/)
python scripts/record_scraper_fixture.py <provider>|all [--cap 12]   # (re)record a provider's HTTP fixture
python scripts/scraper_drift_check.py [provider] [--notify]          # live drift probe (what the Sunday job runs)
python -m pyflakes app.py scraper.py api/ scrapers/ | grep "undefined name"   # the late-binding split's safety check
```

**CI (2026-09):** `.github/workflows/ci.yml` runs on every push/PR - backend (unit pytest + fixture replay + pyflakes
undefined-name check on Python 3.12) and frontend (`npm ci`, `npm run lint`, `npm run build` with dummy `VITE_*` env,
sanity check of the prerendered HTML). Local pre-commit hook in `.githooks/pre-commit` (enable once per clone with
`git config core.hooksPath .githooks`) runs the unit suite when `.py` files are staged and ESLint when `mass-market-app`
JS/JSX is staged. ESLint is green (0 errors); the React-Compiler rules from `eslint-plugin-react-hooks` 6 are `warn`
in `eslint.config.js` until the flagged effects are reworked - don't turn them back to `error` without fixing them.

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
| app.py | Flask **core** (~3,000 lines since the 2026-09 split): config, auth decorators, shared helpers, the plan/changes feeds, `/go` affiliate redirect, APScheduler. `CARRIER_DISPLAY` (10 carriers, homepage URLs) and `CARRIER_STORE_DISPLAY` (4 carriers with e-stores) drive the banners API. Everything else lives in `api/` blueprints (below). |
| api/*.py | **Flask blueprints extracted from app.py by `scripts/split_monolith.py` (2026-09)** - `esim`, `mobile`, `hotels`, `scrape`, `jobs` (scheduled jobs + their preview endpoints), `banners`, `engagement` (alerts/watchlist/saved views/activity/annotations/coupons/deals), `chat`, `account`, `workspaces`, `history`, `usage`. Each module does `import app as core` and references every app.py name as `core.<name>` (LATE-BOUND: tests that `monkeypatch.setattr(app, ...)` keep working); app.py imports the blueprints at its bottom and re-exports all their names, so `app.<name>` still resolves for scripts, tests and the scheduler. Paths from `__file__` must use `core.__file__` (guarded by `tests/test_url_map.py`). `tests/fixtures/url_map.json` is the route snapshot - regenerate it when you add/remove a route (command in the test docstring). To re-split after a merge: `python scripts/split_monolith.py scripts/split_plan_app.json` on a monolithic app.py. |
| scraper.py | Scraper **core** (~900 lines): parsers, FX rates, `_make_global_plan`, `_woo_store_fetch`, the `scrape_all` / `scrape_all_global` / `scrape_all_abroad` aggregators. The 76 `scrape_*` functions + their per-provider dicts live in `scrapers/<provider>.py` (49 modules: one per domestic carrier incl. its roaming scraper, one per global provider, `content.py`, `banners.py` for screenshots/popups/news) and are re-exported, so `scraper.scrape_saily_global` / `scraper._SAILY_API_CACHE` keep working. Same late-binding scheme as `api/` (`core.<name>`), so patching `scraper._get_usd_to_ils` / `scraper.sync_playwright` still reaches every provider. Plan generator: `scripts/make_split_plan_scraper.py` (keyword buckets + `OVERRIDES`). |
| scraper_fixtures.py | **Record / replay harness for the pure-HTTP scrapers** (2026-09). `PROVIDERS` registry (51 `_page=None` scrapers, pinned FX 3.7/4.0/4.7); `record()` captures the first N distinct URLs of a live run into `tests/fixtures/http/<provider>.json.gz` (gzipped JSON, ~8 MB total, 36 providers; Playwright-launching scrapers are auto-marked `playwright: true` and skipped); `replay()` runs the scraper offline (unrecorded URLs = connection error, sleeps no-op) and `tests/test_scraper_fixtures.py` asserts the exact recorded plan count + schema; `drift_check()` re-fetches ONLY the fixture's URL set live and flags <50% of the expected plans - the Sunday 06:30 `run_scraper_drift_job` (api/jobs.py, Telegram) and `scripts/scraper_drift_check.py`. Re-record after an intentional scraper change. Sizing rule: keep a fixture under ~700 KB (lower `--cap` for heavy HTML sites). |
| maintenance.py | **Scheduled DB maintenance** (2026-09): `price_history_daily` builder (08:50 + 18:30, per-carrier and market-per-destination aggregates; backfilled from `archive_snapshots` since 2026-04), weekly Sunday 03:00 `run_weekly` = `prune_change_logs` (config `changes_retention_days`, 180) + optional `thin_archive_snapshots` (`archive_thin_after_days`, OFF by default - archive_snapshots is ~80 MB of the DB) + VACUUM on the first Sunday of the month. `GET /api/maintenance/run-now?job=weekly|daily|backfill&dry_run=true&api_key=…`. One-off cleanup already applied 2026-09-10 (`scripts/db_prune_2026_09.py`: 161K flap rows deleted, DB 141 → 117 MB). |
| db.py | SQLite CRUD — 25 tables with UPSERT logic |
| change_detector.py | Diff old vs new plans, detect price/extras/details changes |
| notifier.py | Format + send notifications (Telegram, Email, WhatsApp, Web Push). `alert_missing_terms()` = post-scrape safety net: if a **new** domestic/roaming plan lands with no "עיקרי התוכנית" link (no `url`/`terms_url`/`__info__`), it Telegrams the operator so the per-provider fetch can be wired in (run the plan-terms-coverage skill). Wired into every scrape path; exempts neptucom domestic + xphone roaming (no terms by design). |
| excel_report.py | Daily Excel report (openpyxl, RTL, yellow=changed) |
| seed_resellers.py | Manually-curated reseller plan data (FB-ad campaigns, login-gated clubs, low-churn broker pages) — UPSERTs `reseller_plans` table |
| btl_scrapers.py | **Below-the-line scrapers** — daily-scraped reseller/landing sources (tiber, zol-li, kamaze, tikshoretishit, clubdeal, partner_site, wecom_site, rami_levy_hever/landing). requests+regex for static sites, Playwright for the 2 JS pages (hever, Partner lobby). One `scrape()` aggregator with per-source isolation; price-free stable plan names so price moves UPSERT in place |
| telegram_resellers.py | Telethon-based scraper for public Telegram channels → `reseller_plans`. Two-phase login flow. |
| config.json | All credentials — NOT in git, auto-generates VAPID keys |
| templates/index.html | Legacy RTL Hebrew dashboard (2,300+ lines, escHtml XSS protection) |

## React App Structure

React app structure, the MOCA design system, multi-workspace architecture, Brand & UI tokens, and key UI component docs live in `mass-market-app/CLAUDE.md` (loads automatically when working on files under `mass-market-app/`).

## Carriers & Providers

**Domestic (10)**: partner, pelephone, hotmobile, cellcom, mobile019, xphone, wecom, neptucom, golan, rami_levy
**Abroad**: same carriers, per-country roaming plans (rami_levy_abroad, wecom_abroad, golan_abroad, 019_abroad have dedicated scrapers)
**E-store carriers (4)**: pelephone, cellcom, partner, hotmobile — screenshots saved as `{carrier}_store.png` in `data/banners/`
**Global eSIM (38)**: tuki, terminalesim (Terminal eSIM — full per-country + regional/global catalog (~2,500 plans, ~190 countries) via the public WooCommerce Store API `terminalesim.com/wp-json/wc/store/v1/products`, USD priced (minor units → /100); `scrape_terminalesim` pure-HTTP, dedup by (title, gb, days, daily); country codes via `TERMINAL_CODE_TO_HEBREW`, regionals via `TERMINAL_REGION_BASE`; REPLACED GlobaleSIM 2026-07 at the operator's request), airalo, pelephone_global (GlobalSIM), esimo (200 countries + 9 regions + global — pure-HTTP scrape: sitemap slugs + Next.js RSC-embedded packages JSON, dest Hebrew from package `code` via ESIMO_CODE_TO_HEBREW), simtlv (130 countries + regional/global bundles + USA unlimited — `scrape_simtlv_esim` pure-HTTP via the public WooCommerce Store API `wp-json/wc/store/v1/products`; live products identified by strict name patterns, legacy/B2B products skipped; PLUS `scrape_simtlv_global` for the 127-country bundles page), world8, xphone_global, saily (199 countries + 8 regions), holafly (182 countries + 16 regions), esimio (eSIM.io — ~184 countries + 10 regions; site moved to the eSIMo Next.js platform ~2026-04, so `scrape_esimio_destinations`/`scrape_esimio_regions` now reuse `_esimo_extract_packages` to read the RSC-embedded `packages` JSON, pure-HTTP, no Playwright — the old h5 plan-card parsing died in that redesign), sparks (143 countries), voye (157 countries + 5 regions + global), orbit (195 countries + 9 zones, REST API at be.orbitmobile.com), travelsim (global + USA + Middle East zones), seven_g (7G), gomoworld (GoMoWorld), tasim (USA 15/50GB one-time packages — pure HTTP via tasim.us/api/plans?type=one_time; 'subscription' plans skipped, no public page), maya (Maya Mobile, GLOBAL-ONLY catalog: `scrape_maya_global` reads Maya's OFFICIAL affiliate feed `https://assets.maya.net/affiliates/plans.json` (auth-free JSON, shared by their partnerships team 2026-06) - this REPLACED the brittle Angular-SSR `<script id="maya-mobile-state">` scrape that broke twice in the 2026 redesigns. ~8 unlimited "גלובלי"/"גלובלי ושייט" tiers at 3/7/14/30 days; the feed is split by `regionType` into the same globalRegions/cruiseRegions buckets `_ingest` expects, so plan_name keys stay unchanged. Catalog = exactly the 8 stored rows, no stale purge needed), bcengi, esim70, jetpack, breez (Breeze), bytesim, bestconnect (Best Connect), besim, esimplus (eSIM Plus), gigsky, esimgenius (eSIM Genius), nisim (Nisim eSIM), esimax (eSIM Max), bnesim (BNESIM), venterrasim (VenterraSIM — Israeli, ILS-priced; ~1,017 packages / 188 countries + 14 regional-global bundles from ONE public JSON endpoint `venterrasim.com/api/v1/plans/` (auth-free, explicitly Allow:ed in their robots.txt). Destinations arrive as ISO-3166 alpha-2 in `location_code`, so `VENTERRA_CODE_TO_HEBREW` just extends `ESIMO_CODE_TO_HEBREW` with the 7 codes eSIMo doesn't sell. Regional bundles are keyed by the plan_name TITLE, not extras[0], because several coverage tiers share one destination — Europe 33/35/41 areas, Asia 7/20, South America 6/20 — see `VENTERRA_REGION_MAP` in globalCountries.js. Every price carries a permanent 20%-off list price; only `price_ils` is stored), simzol (Simzol / סים זול — small Israeli reseller on the CashCow storefront, no API: `scrape_simzol_global` walks `simzol.co.il/crowlers/sitemap` and parses each product page. ~36 ILS plans across גלובלי / גאורגיה / איחוד האמירויות / ארצות הברית / אירופה. Products are keyed by permalink slug in `SIMZOL_PRODUCTS` → (title, dest, esim?, perks); an unmapped page that sits under the site's `/c/esim` category WARNS rather than being dropped silently — that is how the 7-day USA eSIM was caught. Carries BOTH eSIMs and the shop's physical travel SIMs: physical rows get `esim=False` (→ `form='sim'`, excluded by the /esim-deals "eSIM" filter chip) and a ` – סים פיזי` plan_name suffix, without which the physical USA ladder collides with the eSIM USA ladder at 7/20/30 days under UNIQUE(carrier, plan_name). Two products share extras[0]='גלובלי' with different coverage — the eSIM packages (83 destinations) and the physical סים עולמי פלטינום (123, unlimited data+calls sold by trip length) — so `SIMZOL_REGION_MAP` in globalCountries.js keys on the plan_name TITLE, same trick as VenterraSIM). Source of truth: `GLOBAL_LABELS` in carrierLabels.js (40 keys — airalo_local/airalo_regional are aliases of airalo) mirrored by `_CARRIER_NAMES` in app.py.
**Content (5 services × 4 carriers)**: eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי
**Resellers / מתחת לקו (משווקים)**: below-the-line offers that don't appear on the carriers' official rate cards — third-party reseller sites (tiber/טיבר, zol_li/זול-לי, kamaze/כמה זה, tikshoretishit, sell_zoll, kamazeole), carrier-owned lead-gen pages (partner_site lobby, rami_levy_landing/hever/cc, wecom_site sim-data, clubdeal, pelephone_join, pelephon4u, pelephone_cellphone), Facebook-ad campaigns (pelephone_fb, analizer) and social resellers (cellcomshefamr, zorro). ~19 reseller_ids, ~55 rows. Auto-scraped ids are listed in `db.AUTO_SCRAPED_RESELLER_IDS`; labels live in `RESELLERS` (DashboardPage.jsx) + `RESELLER_NAMES` (notifier.py) — keep all three in sync. Social-media-only pricing remains sparse (1,400 Telegram messages scanned — zero matches); the 2026-06-11 web sweep found the real BTL channel is reseller WEBSITES + landing pages.

## Database Schema (SQLite — data/plans.db)

26 tables. Key constraints: UNIQUE(carrier, plan_name) for plans, UNIQUE(service, carrier) for content, UNIQUE(url) for news, UNIQUE(reseller_id, carrier, plan_name) for resellers.

| Table | Key Fields |
|-------|-----------|
| plans | carrier, plan_name, price, data_gb, minutes, extras, scraped_at |
| changes | carrier, plan_name, change_type, old_val, new_val, changed_at |
| abroad_plans | + days, sms |
| global_plans | + currency, original_price, days, sms, esim |
| content_plans | service, carrier, price, free_trial, note, status |
| reseller_plans | reseller_id, carrier (underlying), plan_name, price, data_gb, minutes, sms, extras (JSON), source_url, seen_at |
| reseller_changes | reseller_id, carrier, plan_name, change_type, old_val, new_val, changed_at — written by `sync_reseller_plans`, read by the morning digest |
| push_subscriptions | endpoint, p256dh, auth |
| news_articles | carrier, headline, url (UNIQUE), source, published_at (ISO 8601), fetched_at |
| user_activity | user_email, workspace_id, event_type (login/page_view/alert_created/watchlist_added/watchlist_removed/comparison_saved), path, details (JSON), user_agent, created_at — powers the super-admin user-activity dashboard; super-admins are never recorded |
| price_history_daily | day, plan_type, carrier, destination, min/avg/max_price, min_ppgb, plan_count, min_carrier, source — PK (day, plan_type, carrier, destination). Two row kinds: per-carrier (`destination=''`) and market-wide per destination (`carrier='*'`, `min_carrier` = who had the min). The change-log-independent history source (maintenance.py); read via `GET /api/history/daily`. A full carrier×destination matrix was tried and rejected (570K rows / 5 months) |
| maintenance_log | ran_at, job (prune/vacuum/thin_archive/price_history), details (JSON) — audit trail of maintenance.py runs |

**Retention (2026-09):** `*_changes` rows older than `changes_retention_days` (180) are deleted every Sunday 03:00 by `maintenance.run_weekly`; charts that need longer history read `price_history_daily` instead of the change log. `archive_snapshots` is untouched unless `archive_thin_after_days` is set in config.json.

## Change Detection

change_detector.py compares old vs new plan lists by (carrier, plan_name) key:
- `price_change` — uses original_price for foreign currency (avoids FX false alarms)
- `new_plan` / `removed_plan` — guarded: only marks removed if carrier returned ≥1 plan
- `extras_change` / `details_change` — array/field diffs
- `_coerce()` normalizes '7000' vs 7000 vs 7000.0

`save_plans` and `save_abroad_plans` call `db._delete_stale_carrier_rows()` before the upsert — for any carrier that returned ≥1 plan, rows whose `plan_name` is no longer in the scrape are deleted. This prevents the "stuck removal" loop where a discontinued plan stays in the DB and triggers the same `removed_plan` event on every scrape. `save_global_plans` deliberately skips this guard because some global scrapers are per-country and partial failures are common — global notification dedup is handled by `filter_already_notified()` instead. **Stale-row purge (2026-09-03)**: because nothing ever deleted global rows, discontinued tiers/destinations accumulated for months and were served unfiltered (gomoworld: 894 rows vs a 716-plan catalog; 17% of all global rows stale, sparks/tuki/orbit ~51%). `db.purge_stale_global_rows(new_global)` now runs right after `save_global_plans` (and before `notify_esim_price_drops`) on all 3 global scrape paths via `_purge_stale_global` in app.py. Per carrier PRESENT in the fresh list it deletes rows whose plan_name is not in the scrape AND that are older than a grace period (72h; 168h for the flaky per-country providers in `GLOBAL_PURGE_OVERRIDES`: esimplus/holafly/alosim/besim/gomoworld) - but ONLY when the scrape looks complete: fresh rows ≥ 90% of the rows AND fresh destinations ≥ 90% of the destinations the DB saw for that carrier in the last 30 days (`window_days`), and ≥ 2 rows. The baseline is deliberately the rolling window, not the total row count - an old backlog would otherwise block the purge forever. A scraper that returned `[]` never purges. It writes nothing to `global_changes` (no new/removed noise) and doesn't touch `esim_push_subscriptions` (a purge can only raise a destination's alert floor, which the notifier absorbs as a silent baseline rise). Knobs in config.json: `global_purge_enabled` (false = dry-run, report still logged), `global_purge_min_ratio`, `global_purge_min_rows`, `global_purge_grace_hours`, `global_purge_window_days`. Preview what it would do: `python scripts/global_stale_report.py` (read-only). **(2026-06-04)** That accumulation made partial scrapes flap `removed_plan`/`new_plan` (286K phantom rows in 2 months, bloating the DB), so the **3 global scrape paths in app.py now drop `new_plan`/`removed_plan` right after `detect_changes(...)`** — only `price_change`/`extras_change`/`details_change` are persisted for global (`price_change` still powers the history charts). Domestic/abroad are unaffected.

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

Caveats: `_DEST_NORM` rewrites extras/destination only — it never touches `plan_name`. Change detection compares the SCRAPED extras against the (normalized) stored row, which historically made any non-canonical scraper value flap `extras_change` on every scrape (eSIM Plus "St. Vincent &amp; Grenadines" — daily false Telegram alerts; by 2026-07-14 the same mechanism produced ~1,300 phantom `extras_change`/day across 20 global providers). **Fixed 2026-07-14**: `_make_global_plan()` now runs `db._norm_extras` on `extras` at creation (in addition to the earlier `html.unescape` safety net), so for global scrapers using the helper, scraped extras == stored extras and adding a `_DEST_NORM` mapping is safe. `plan_name` is still never normalized — a wrong plan_name spelling must be fixed in the scraper's own dict (fix the DB rows' `plan_name` in place at the same time, or the old keys linger as stale duplicates: see the esim70/breez "ההפיליפינים" typo cleanup, 2026-07-14).

### Multi-Country Provider Filtering (DashboardPage / ComparePage)

Some global providers sell a single plan that covers many countries (e.g. SimTLV, TravelSim, World8, Airalo, Terminal eSIM, eSIMo, XPhone Global, GlobalSIM). These are tracked in the `MULTI_COUNTRY_CARRIERS` Set in **`data/planCoverage.js`** (moved out of DashboardPage.jsx 2026-09, together with `getPlanCoverage`). The dashboard's filter / sort / group / destination pipeline itself is the set of pure functions in **`hooks/useDashboardPlans.js`** (`filterAndSortPlans`, `groupGlobalDisplayItems`, `globalDestinationsOf`, `globalRegionsOf`, `hasCruisePackages`) plus the `useDashboardPlans` memo hook; region-label consolidation (`KNOWN_REGIONS`, `normalizeRegionLabel`) is in `data/regionLabels.js`. Their country coverage is defined as static arrays in `globalCountries.js` and resolved at runtime by `getPlanCoverage(plan)`:

```js
// Returns string[] of covered countries, or null for single-country plans
function getPlanCoverage(plan) { ... }
```

- `globalDestinationsOf` (useDashboardPlans.js): for MULTI_COUNTRY_CARRIERS, expands all covered countries into the dropdown instead of using extras[0]
- `filterAndSortPlans` (useDashboardPlans.js): for MULTI_COUNTRY_CARRIERS, matches via `getPlanCoverage(p).includes(destination)` instead of `extras[0] === destination`
- `CARRIER_COUNTRY_LISTS` in ComparePage mirrors this for the comparison chart's country filter

When adding a new multi-country provider: add arrays to `globalCountries.js`, add the carrier id to `MULTI_COUNTRY_CARRIERS` and a branch in `getPlanCoverage()` (both in `data/planCoverage.js`), and add to `CARRIER_COUNTRY_LISTS` in ComparePage.

### RTL Layout Pitfalls

The global `direction: rtl` in `index.css` affects flex containers differently from text elements:
- `text-right` (`text-align: right`) = always physical right edge ✓
- `justify-end` in RTL flex = physical **left** edge ✗ — use `justify-start` instead
- `justify-start` in RTL flex = physical **right** edge ✓
- Icons inside flex rows: in RTL flex the first child renders on the right, so place the icon before the text in JSX to have it appear to the left of the text visually

### PlanCard const-ordering pitfall (TDZ)

PlanCard.jsx declares many derived consts at the top of the function body. **Any const that references `carrier` (e.g. `CARRIER_HOME_URLS[carrier]`) must be declared AFTER `const carrier = plan.carrier`** — otherwise the JS Temporal Dead Zone throws `ReferenceError: Cannot access 'carrier' before initialization`, which crashes PlanCard, which unmounts the entire dashboard, leaving a blank screen with no visible error in production. The error appears in dev console only. Same rule for `isGlobal`/`isAbroad`/`isContent`/`isReseller` references that depend on `type` — those are declared early so they can be referenced anywhere in the function body.

## Resellers tab + Telegram scraper

The "משווקים" tab (between גלובלי and תוכן) shows below-the-line offers that don't appear on the carrier's own rate card. Three ingest paths:

1. **Daily scrape (08:15)** — `scrape_resellers_job` in app.py iterates `RESELLER_SCRAPER_MODULES` (`pelephon4u_scraper`, `pelephone_join_scraper`, `btl_scrapers`), calls each module's `scrape()`, then `db.sync_reseller_plans()` — which diffs against the DB, logs `new_plan`/`price_change`/`removed_plan` to **`reseller_changes`**, deletes stale rows (scoped per (reseller_id, carrier) pair that returned ≥1 plan, mirroring `_delete_stale_carrier_rows` semantics) and UPSERTs. Manual trigger: `GET /api/scrape-resellers-now?api_key=…`. The 08:20 morning digest then shows these changes under "🏷️ מתחת לקו (משווקים)".

2. **Manual transcription** — `seed_resellers.py` for sources that can't be auto-scraped (Facebook Ad Library campaigns, login-gated club pages, low-churn broker pages). Edit + run to upsert. Source URLs become click-through targets via PlanCard's "לפוסט המקור" button. PlanCard checks `type === 'resellers'` and uses `plan.source_url` instead of `CARRIER_HOME_URLS[carrier]`.

3. **Telegram channels** — `telegram_resellers.py` uses Telethon (free) to fetch messages from public channels in `config.json -> telegram_reseller_channels`. Filter logic: must contain a carrier name (`סלקום`/`פלאפון`/`פרטנר`/`הוט מובייל` or English) AND a price match (`\d+\s*(?:₪|ש"ח)`) between 5-500. Login is two-phase (`login_request` → user receives code in Telegram app → `login_verify <code>`). Session persists in `data/telegram_session.session` (gitignored).

**Dominance filter**: `/api/reseller-plans` passes rows through `db.filter_undominated_reseller_plans` — a reseller row is hidden when the carrier's own rate card offers ≥data_gb at ≤price. `db.ALWAYS_SHOW_RESELLER_IDS` whitelists sources whose value is the *disclosure* (carrier-owned landing terms, club-member prices, multi-line bundles whose TOTAL price loses to single-line plans, FB-ad campaigns) — those always render. Third-party sites (tiber, zol_li…) stay filtered, so their rate-card-mirror rows don't clutter the tab.

PriceHistoryModal has a `HAS_HISTORY` whitelist (`['domestic', 'abroad', 'global', 'content']`). For other plan types (e.g. `resellers`) it skips the API call and renders the empty state — no error toast. The backend's `/api/history/price-series` rejects unknown plan_types with 400, so the whitelist must stay in sync.

## Schedule

- **08:00** — screenshot all carrier homepages (`scrape_carrier_banners`) + 4 e-store pages (`scrape_carrier_store_banners`), saved as PNG in `data/banners/`
- **08:10** — scrape Google News RSS for all 10 domestic carriers + Breeze (`scrape_carrier_news()` → `upsert_news_articles()`), INSERT OR IGNORE by URL
- **08:15** — **below-the-line reseller scrape** (`scrape_resellers_job`): all modules in `RESELLER_SCRAPER_MODULES` → `sync_reseller_plans` (diff → `reseller_changes` → upsert). Runs 5 min before the digest so its changes land in the same morning's "מתחת לקו" section
- **08:20** — **morning changes digest** (`run_morning_check_job` in app.py): reads the change LOG (not a live scrape) for the last 26h across all 5 change tables (domestic/abroad/global/content/**resellers**) — new/removed plans, price/extras changes — plus **scraper-freshness warnings** (`db.get_scrape_freshness`: carrier stale, 0 plans, or missing from `plans` entirely vs `CARRIER_DISPLAY`), and **always** sends Telegram — an explicit "לא זוהו שינויים" message doubles as a daily heartbeat (no message = job/Flask down). A scraper that silently breaks can never report a new plan it didn't see, so the freshness warnings surface the breakage. **Per-category staleness thresholds**: domestic/abroad/content/resellers use `morning_check_stale_hours` (36h); **global** uses a separate, more lenient `morning_check_global_stale_hours` (72h) — global eSIM providers scrape hundreds of per-country pages with partial coverage per run, so a blanket 36h false-positives on normal flakiness; a days-scale threshold catches real breakage (weeks of zero rows — e.g. esimio frozen since Apr 29, maya since May 11, both fixed 2026-06-11) while tolerating a missed run. NB: a broken global scraper returns `[]` but `save_global_plans` never deletes, so its rows AGE (caught by the MAX(scraped_at) check) rather than vanish. Manual trigger / preview: `GET|POST /api/morning-check/now?api_key=…` (`&send=false` returns the digest JSON without sending). config.json knobs (all optional): `morning_check_time` ("08:20"), `morning_check_window_hours` (26), `morning_check_stale_hours` (36), `morning_check_global_stale_hours` (72), `morning_check_whatsapp` (false)
- **08:50 + 18:30** — `maintenance.run_daily`: aggregate the live plan tables into `price_history_daily` (after each scrape window)
- **09:00** — send daily Excel email report via Resend SMTP (SendGrid fallback)
- **Sunday 03:00** — `maintenance.run_weekly`: prune `*_changes` older than 180 days (+ optional archive thinning); VACUUM on the first Sunday of the month
- **Sunday 06:30** — `run_scraper_drift_job` (api/jobs.py): live drift probe of every scraper with an HTTP fixture (`scraper_fixtures.drift_check`), Telegram summary listing providers that now return <50% of their recorded plans or fail validation. Manual: `GET /api/scraper-drift/now?api_key=…&send=false`
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
| global_stale_report.py | READ-ONLY dry run of the global stale-row purge: per provider, rows in DB vs rows in its latest scrape, stale/eligible counts, coverage ratios and the exact purge decision (`db.purge_stale_global_rows(dry_run=True)`). Run before/after changing the `global_purge_*` knobs. |
| db_compress_and_prune.py | One-time DB maintenance (2026-06): snapshot → zlib-compress archive_snapshots → delete global_changes flap noise → VACUUM (shrank DB 421→43MB). |
| db_prune_2026_09.py | One-time (already run 2026-09-10): deleted the two documented flap backlogs from global_changes - 73,568 phantom `extras_change` rows before the 2026-07-14 fix and 87,400 Breeze FX-flap `price_change` rows before the 2026-07-26 fix - then VACUUM (141 → 105 MB; snapshot in `data/plans_pre_prune_2026_09.db`, delete once verified). Standing retention now lives in maintenance.py. |
| split_monolith.py + split_plan_app.json / split_plan_scraper.json | The 2026-09 monolith splitter (app.py → api/, scraper.py → scrapers/). AST-based: moves top-level nodes by plan, rewrites references to monolith names as `core.<name>` (scope-aware, incl. `__file__`), replicates stdlib/third-party imports, late-binds project-module imports, topologically orders modules by import-time deps, warns on import-time refs left in the core, appends the import + re-export block before `if __name__ == "__main__"`. Re-runnable on a monolithic file; `--dry-run` reports only. |
| make_split_plan_scraper.py | Generates split_plan_scraper.json from scraper.py by name-keyword buckets (`BUCKETS`, `OVERRIDES`, `KEEP`). Run it, then the splitter. |
| record_scraper_fixture.py | Records HTTP fixtures for the pure-HTTP scrapers (`scraper_fixtures.record`): `all`, `all --missing`, or named providers; `--cap N` distinct URLs (default 12; use 3-6 for heavy HTML sites). Prints a per-provider table (plans, urls, KB, validation). |
| scraper_drift_check.py | Live drift probe over the recorded URL sets (`--notify` = Telegram); the same check the Sunday 06:30 job runs. |
| gen_dest_backgrounds.py + dest_bg_map.json | Destination background images for the /esim-deals trip wizard: one Gemini-generated landmark photo per live destination (config.json `gemini_api_key`, model gemini-2.5-flash-image) → `mass-market-app/public/dest-bg/<slug>.jpg`, then auto-rewrites the React manifest `src/data/destBg.js` (he string → path) from what exists on disk. Curation (region images shared by variants, combo-plan aliases, sub-national places, cruise ship) lives in dest_bg_map.json. Idempotent — delete a jpg to regenerate; rerun when new destinations appear. Needs Flask on :5000 + node. |

## Archive System

`archive.py` stores historical plan snapshots (table `archive_snapshots`, browsable via `ArchivePage.jsx` / Time Machine):
- One snapshot per (carrier, plan_type) per day (`save_plan_snapshot` skips if today's already exists); a `content_hash` is also stored
- **`plans_json` is zlib-compressed (2026-06-04)** via `_archive_encode`/`_archive_decode` in db.py — written compressed in `insert_archive_snapshot`, decompressed in `get_archive_plans`. Backward-compatible (bytes=compressed, str=legacy). Shrank this table ~19× (was 305MB of raw JSON — the bulk of a 421MB DB → now ~18MB). Lossless; all history kept
- Banner snapshots (PNGs) live in `data/archive/banners/`

## Environment Variables

### Flask (.env or config.json)
- `FLASK_HOST` — bind address (default: 127.0.0.1)
- `ALLOWED_ORIGINS` — comma-separated CORS origins
- **Supabase Postgres (`_supabase_conn()` in app.py — the ONLY connection site; every `api/*.py` blueprint goes through it):** `supabase_db_host` + `supabase_db_password` (required), `supabase_db_user` (default `postgres`), `supabase_db_port` (default 5432), `supabase_db_name` (default `postgres`), `supabase_db_connect_timeout` (10s). Each has a `SUPABASE_DB_*` env fallback. **Use the Session Pooler, not the direct host (2026-09-20):** the direct `db.<ref>.supabase.co` is IPv6-only on the free tier, so a box without an IPv6 route gets `could not translate host name … Name or service not known`, `_get_user_context` swallows it and returns `viewer`, and EVERY signed-in user — admins and super_admin included — silently loses their role (that was the "I log in as viewer" incident; `hide_self_carrier` silently switches off too). Dashboard → **Connect** → *Session pooler* gives `supabase_db_host = aws-0-<region>.pooler.supabase.com`, `supabase_db_user = postgres.<project-ref>` (the tenant suffix is mandatory), port 5432 (session mode — 6543 is transaction mode, which breaks prepared statements). **Verified values for THIS project (repair run 2026-09-20 16:48):** `supabase_db_host = aws-1-eu-west-2.pooler.supabase.com`, `supabase_db_user = postgres.gmfefvjdmgzluwffzrzj`, `supabase_db_port = 5432` — note the `aws-1` prefix: the probe found that `aws-0-eu-west-2` (and every other region) answers `FATAL: Tenant or user not found`, so only the exact prefix+region pair connects. Right after the rewrite `_get_user_context('alon.yoch@gmail.com')` returned `super_admin` in a fresh process and Flask was restarted; the pre-change file is kept as `config.json.bak-<timestamp>`. Quick health check from the box, no restart needed: `python -c "import app; app._supabase_conn(); print('DB OK')"`. **One-shot repair: `python scripts\fix_supabase_pooler.py`** (admin PowerShell) — pulls, finds the pooler region by probing every `aws-{0,1}-<region>.pooler.supabase.com` with the tenant user, backs up + rewrites `config.json`, verifies `_get_user_context` in a fresh process, and restarts Flask; `--dry-run` / `--host <pooler-host>` / `--email` flags. **How it actually broke (2026-09-18):** the host's IPv6 upstream failed (addresses from the router, no route out — see the note in `scripts/morning_health_check.ps1`), so every connect() to the direct host hung; IPv6 was then disabled on the host on a session's advice to cure the slowness, with no check of what depended on it — this did. **Rule: before advising ANY change to the host's networking (IPv6, DNS, proxy, VPN, firewall), grep `config.json` + `app.py` for external hosts and check each one still resolves and connects afterwards.** Re-enabling IPv6 is not a fix here (it restores the hang); the pooler is. **Resolved 2026-09-20** by running that script on the box.

### Telegram (config.json)
- `telegram_api_id` / `telegram_api_hash` — from https://my.telegram.org → API development tools
- `telegram_user_phone` — international format `+972...`
- `telegram_reseller_channels` — array of `{username, label, limit}` or plain usernames

### React (mass-market-app/.env)
- `VITE_SUPABASE_URL` — Supabase project URL
- `VITE_SUPABASE_ANON_KEY` — Supabase anon key
- `VITE_API_URL` — Flask API base URL (empty = proxy via Vite; production build = https://api.mocaintel.com via .env.production). Code fallback is `''` (no hardcoded URL)
- `VITE_DEV_API_KEY` — dev-only `X-API-Key` header for protected endpoints (`src/lib/api.js`; empty string when unset). Production auth is the Supabase JWT, so no API key belongs in a production bundle. **`VITE_API_KEY` is read by NOTHING** — it survives in the Netlify dashboard from before the rename and can be deleted
- `VITE_DEV_AUTH` — set to "true" for auto-login as admin in dev (`.env` only, never in production)

### Production Build
`.env.production` overrides `.env` during `npm run build` — sets `VITE_DEV_AUTH=false` to ensure login is required. Never set `VITE_DEV_AUTH=true` in Netlify env vars or `.env.production`.

## Deployment

- **Who can deploy**: the Netlify CLI is logged in **only on the local Windows machine**. A Claude Code web/cloud session has no CLI, no `.env.production` (gitignored, 0 commits) and no network route to `api.netlify.com` (the sandbox returns `CONNECT tunnel failed, 403`) — so it cannot deploy directly and must not imply otherwise — but it CAN trigger `deploy-frontend.yml` (workflow_dispatch), which deploys from a GitHub runner with the repo's `NETLIFY_AUTH_TOKEN`. The Netlify site's Git link still reads **Not linked** (2026-09), so merges to `main` deploy nothing by themselves.
- **Deploy from GitHub Actions (2026-09, VERIFIED by run logs)**: the deploy workflow is `.github/workflows/deploy-frontend.yml` (manual: Actions → *Deploy frontend to Netlify* → Run workflow). The `NETLIFY_AUTH_TOKEN` repo secret **exists** (added 2026-09-19); run #3 (2026-09-19 18:08, commit `805e659`) built with the ngrok API edge, prerendered **161** `/esim/<destination>/` pages, deployed `6aaed0e1` and verified the live fingerprint against the Netlify origin `https://lucent-kulfi-f037ad.netlify.app` — that is the reference for a good deploy. Its `require_dest_pages` input (default true) refuses to deploy a build with 0 destination pages; keep it. **A second workflow (`deploy.yml`, push-to-main, added by PR #13) was REMOVED 2026-09-20 after its first run broke production**: it defaulted `VITE_API_URL` to `https://api.mocaintel.com`, which the runner could not reach (prerender skipped → 0 destination pages, 161 SEO pages dropped from the live site), it verified against `mocaintel.com` (no bundle returned, 6/6 attempts), and its ngrok-domain guard would have *blocked* the host the live bundle actually uses. Lessons, so they are not repeated: (1) the live API origin as of 2026-09-20 is the **ngrok edge** `https://terra-nonrestrained-overpiteously.ngrok-free.dev` (what `deploy-frontend.yml` defaults to, what the 09-19 deploy shipped, what `public/_redirects` routes `/go/*` to, and what `scripts/morning_health_check.ps1` probes) — `api.mocaintel.com` / the Cloudflare tunnel is NOT a safe assumption; verify with the health-check probe before building against it; (2) verify a deploy against the Netlify origin, never the custom domain; (3) never add a push-triggered deploy without the destination-pages guard. Trust the run logs over this file when they disagree.
- **Frontend**: Netlify, served at **https://mocaintel.com** (canonical; `www.mocaintel.com` 301-redirects to it; custom domain via Cloudflare DNS — the `lucent-kulfi-f037ad.netlify.app` subdomain still resolves). **Deploy via Netlify CLI** (since 2026-07-09: CLI installed, logged in as Alon, `mass-market-app/` linked to site `39164e5d-2df9-4254-82e1-a1e9d825a240`): `cd mass-market-app && netlify deploy --prod --dir=dist --no-build`, then verify the live bundle hash matches dist (deploy-live skill). **`--no-build` is mandatory** — without it the CLI rebuilds with the Netlify dashboard env vars instead of local `.env.production` (this shipped a dead-API bundle once, 2026-07-09, when the dashboard `VITE_API_URL` was still the retired ngrok URL; fixed same day, but the local build remains the canonical artifact). Manual drag of `mass-market-app/dist` remains the fallback.
- **Frontend from anywhere (2026-09-19)**: `.github/workflows/deploy-frontend.yml` — a `workflow_dispatch` job that runs the same `npm run build` on a GitHub runner and deploys with `netlify-cli deploy --prod --dir=dist --no-build`, guarded like the deploy-live skill: refuses without the `NETLIFY_AUTH_TOKEN` repository secret, refuses a bundle whose `VITE_API_URL` is missing from the built JS or from the CSP `connect-src` in `dist/_headers`, refuses a sitemap still on mocaintel.com, refuses (by default) a build with 0 prerendered `/esim/<dest>/` pages (`ESIM_API_BASE` = the API origin, so the runner needs the ngrok edge up), and fails unless the live `assets/main-*.js` fingerprint equals the built one. Values: `VITE_API_URL` defaults to the ngrok origin (override with a repo VARIABLE), Supabase URL/anon key fall back to `src/lib/supabase.js` (note: production reads `VITE_API_URL` + `VITE_SUPABASE_*` only — `VITE_API_KEY` is not read by the bundle; `api.js` reads `VITE_DEV_API_KEY` for dev). Trigger: Actions tab → Run workflow, or the dispatch API — which is how a cloud Claude session deploys, since it has no Netlify CLI, no `.env.production` and no egress to Netlify. Manual-only by design; the file's header shows the 3-line `push:` block that would make every merge to main go live.
- **Backend**: Local Flask, exposed via **Cloudflare Tunnel** → https://api.mocaintel.com (cloudflared tunnel "moca", run by the **MOCA-Cloudflared** task / `scripts/cloudflared_watchdog.ps1`). ngrok retired 2026-06-04 (MOCA-Ngrok task disabled + kept as fallback; reserved domain still on the account)
- **Auth**: Supabase (https://gmfefvjdmgzluwffzrzj.supabase.co)
- **Code**: GitHub (https://github.com/AYochelman/Mobile-Operators-Competitor-Analysis)
- **Build command**: `cd mass-market-app && npm install && npm run build`
- **Publish directory**: `mass-market-app/dist`
- Netlify env vars must include: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL (NOT VITE_DEV_AUTH, and NOT VITE_API_KEY — nothing reads it)
- All API requests include `ngrok-skip-browser-warning: true` header — still REQUIRED: as of 2026-09-20 the live API edge is ngrok again (see Deploy above); `public/_redirects` `/go/*` → the ngrok host is correct, not a leftover

### Static prerendered marketing pages (`/` and `/hotels`)

Two public marketing pages are **prerendered to static HTML at build time** so they paint instantly with no SPA boot. The `npm run build` chain (package.json) is: `vite build` → `vite build --ssr src/entry-landing.jsx --outDir dist-ssr` → `node scripts/prerender-landing.mjs` → `vite build --ssr src/entry-hotels.jsx --outDir dist-ssr-hotels` → `node scripts/prerender-hotels.mjs` → `node scripts/prerender-esim.mjs`. All prerender scripts run **after** `vite build`, so the PWA service worker never precaches their HTML (the SPA routes are the SW / offline / dev fallback). Netlify serves them via `public/_redirects` rules placed BEFORE the SPA catch-all: `/ → /landing.html`, `/hotels → /hotels.html`, `/esim-deals → /esim.html`.

**SEO canonical note (`/esim-deals`):** `prerender-esim.mjs` is NOT a standalone render like landing/hotels — it copies `dist/index.html` and only swaps the `<head>` (self-referencing canonical `https://mocaintel.com/esim-deals`, title, description, hreflang, OG), keeping the SPA boot intact, so `EsimComparePage` still mounts live. It exists because the generic `index.html` head canonicalises every SPA route to the site root, which made Google treat the public `/esim-deals` page (and its `esim.mocaintel.com` mirror) as a duplicate of the homepage and de-index it. The `esim.mocaintel.com` host is served this same `esim.html` (see `_redirects`) so the subdomain consolidates its SEO signal onto the apex `/esim-deals` instead of self-canonicalising. `EsimComparePage.jsx` also rewrites the canonical + description client-side (belt-and-suspenders for any JS-rendered view). GOTCHA: attribute values injected by the prerender must be HTML-escaped — the Hebrew `חו"ל` carries a literal `"` that closes a `"`-delimited attr early (`escAttr` handles it). `sitemap.xml` lists `/esim-deals` (he + `?lang=en`); `robots.txt` Disallows the login-gated dashboard routes but deliberately NOT `/esim` (a prefix of `/esim-deals`).

**Public origin = `src/data/siteOrigin.js` (2026-09-19):** every absolute self-URL the site declares - canonicals, hreflang alternates, `og:url`/`og:image`, JSON-LD `@id`, `sitemap.xml`, the IndexNow ping - is built from `SITE_ORIGIN`, currently the Netlify origin `https://lucent-kulfi-f037ad.netlify.app`: mocaintel.com was taken offline 2026-07-13 (commit af0c061, employer request) and its apex answers DNS with NODATA (no A/AAAA), so canonicals on that host were de-indexing the whole site (Ahrefs Site Audit: "Robots.txt is not accessible", 2 URLs crawled). The prerender scripts, `stamp-sitemap.mjs`, `indexnow-ping.mjs` and the 3 pages that rewrite their canonical at runtime (Esim/Mobile/HotelsLanding) import it; the static files (`index.html`, `public/sitemap.xml`, `robots.txt`, `llms.txt`, the 4 legal pages' canonical) carry the literal and MUST be changed together with it - `stamp-sitemap.mjs` fails the build when `sitemap.xml` drifts. When the canonical domain returns, flip the constant + those files in one commit. Deliberately NOT covered (still hardcoded to mocaintel.com): `_redirects`/`_headers` host rules, `App.jsx` esim./mobile. host detection, `api.js` API fallback, `HotelsAdminPage` `PUBLIC_ORIGIN`, `prerender-esim-dests.mjs` `GO_BASE` (affiliate links -> api.mocaintel.com), and the Helpdesk@ e-mail addresses.

**eSIM consumer PWA (2026-07-11):** `/esim-deals` is an installable consumer PWA, separate in identity from the dashboard PWA. `prerender-esim.mjs` swaps the head's manifest link to `public/esim-manifest.webmanifest` (id `/esim-deals`, name "MOCA eSIM", start_url `/esim-deals?utm_source=pwa&utm_campaign=pwa_install`) + `apple-mobile-web-app-title` "MOCA eSIM"; the generic `/manifest.json` stays the dashboard app. Web-push display lives in `public/push-sw.js`, imported into the Workbox SW via `vite.config.js` `workbox.importScripts` (the generated SW has NO push/notificationclick handlers of its own — without this, pushes are silently dropped). EsimComparePage carries an engagement-gated install card (`beforeinstallprompt` on Android, share-sheet instructions on iOS, 30-day dismissal, `pwa_install` event beacon) + a **destination price-drop alert card**: public `POST /api/esim/push/subscribe` / `unsubscribe` (no auth, one alert per device, UPSERT by endpoint) → `esim_push_subscriptions` table → `notifier.notify_esim_price_drops(config)` runs after `save_global_plans` on ALL 3 global scrape paths. It's STATE-based (baseline vs `db.get_esim_alert_floor` = cheapest trip-sized deal ≥5GB/≥7d — the raw catalog min is a meaningless ~₪1 daily package), so it also catches new-cheaper-plan drops that the global change log deliberately discards; threshold ≥5% AND ≥₪2 (FX noise), baseline silently rises so a later fall re-alerts.

- **`/` → `dist/landing.html`** (`LandingPage.jsx` + `entry-landing.jsx`): **zero JS** — `renderToStaticMarkup` (purely presentational). Bilingual he/en are BOTH rendered into the DOM under `[data-lang-root]`; a vanilla script toggles visibility + recreates the hero tilt. The SPA home moved to `/home`.
- **`/hotels` → `dist/hotels.html`** (`HotelsLandingPage.jsx` + `entry-hotels.jsx` + `entry-hotels-client.jsx`): **prerender + React hydration** — this page is interactive (live demo iframe picker, ROI calculator sliders, lead form), so it uses `renderToString` and `hydrateRoot(#hotels-root)`. The hydration bundle is a **2nd Vite input** (`vite.config.js` `build.rollupOptions.input['hotels-client']` → `dist/assets/hotels-client-*.js`), located by `prerender-hotels.mjs` via a glob. Its `<head>` is hand-built (self-hosted `/fonts/fonts.css` only — the component is fully self-scoped under `#hl-app`, no Tailwind needed) with a page-specific canonical + hreflang + OG block for shareable previews. **Hydration gotcha**: `HotelsLandingPage` MUST init language deterministically (`useState('he')`, then apply `?lang=` / stored pref in a mount `useEffect`) — otherwise `?lang=en` deep-links make the server markup ('he') differ from the client's first render and React throws a hydration mismatch.

When adding a new prerendered page: add an `entry-<x>.jsx` (SSR) + — if interactive — an `entry-<x>-client.jsx` (hydration, wired into the vite `input` map), a `scripts/prerender-<x>.mjs`, two build-chain steps in package.json, and a `_redirects` rule before the catch-all. **ALSO add the route to `workbox.navigateFallbackDenylist` in vite.config.js** — returning visitors' service worker otherwise swallows the navigation into the SPA (404). This bit the `/esim/<dest>/` pages and again `/privacy?lang=en` (2026-07-11: bare `/privacy` accidentally survived via the precache clean-URLs match → `privacy.html`, but any query string breaks that match, so the Hebrew link worked while the English one 404'd).

**Domestic consumer page `/mobile-deals` (2026-08-04, Stage 1 - UNPUBLISHED preview):** the domestic twin of `/esim-deals`. `MobileComparePage.jsx` (self-contained `#mobile-app` microsite, he/en via the shared `esim_lang` key, 3 tabs: domestic / roaming / content, carrier click-out via `data/carrierHomeUrls.js` + `carrier_click` beacon - no affiliate). Backend: `/api/mobile/compare` (public, `_assemble_mobile_plans` in app.py normalizes the domestic data quirks server-side: `data_gb>=9999`→unlimited, NULL+kosher→`voice_only`, `price_conditional` multi-line regex, sub-GB `price_per_gb` guard, `__info__` extraction, ≤4 curated `chips`, facet booleans), `/api/mobile/event` (separate `mobile_events` table - do NOT widen the esim whitelist), `/api/mobile/push/subscribe|unsubscribe` (`mobile_push_subscriptions`, keyed carrier-or-'all', EVENT-driven: `notifier.notify_mobile_price_drops(fresh_changes, config)` hooked into all 3 domestic scrape paths, unlike the eSIM floor model). Launch switch `MOBILE_B2C_LIVE` in App.jsx is `import.meta.env.DEV` (super-admins preview in production, everyone else 404). `prerender-mobile.mjs` → `dist/mobile.html` is built but UNREFERENCED until launch.

**/mobile-deals email/WhatsApp reminders (2026-08-06; extended to all 3 tabs 2026-08-09):** per-plan bell button → `ReminderModal` (email and/or WhatsApp number, at least one) with two opt-ins. **`plan_type` ('domestic'|'roaming'|'content', column on `mobile_reminders` + `days` snapshot column)**: roaming bells sit on the חבילות לחו"ל cards (validated against `abroad_plans`; better_deal matcher `find_better_roaming_deals` = ≥data AND ≥days for less, cross-carrier; NULL `data_gb` on abroad rows means a VOICE-MINUTES package - e.g. rami_levy "טסים בראש שקט" - NOT unlimited, excluded from both sides of the match and no longer rendered as "ללא הגבלה" on the card); content bells sit on the שירותים נוספים rows (`plan_name` = the service name, validated against `content_plans`; price parsed from the free-text ₪ string; `find_better_content_deals` = same service, other carrier, cheaper; plan_end doubles as a free-trial-end reminder). Modal copy per type via `t.remByType`; the paid_price question is hidden for roaming (one-time package). Monthly heartbeat + renewal follow-up stay domestic-only (market percentile is a domestic stat). BTL reseller section: domestic only. Original domestic mechanics: (1) `better_deal` - recurring alert when another carrier offers ≥ the same data for less (matcher `find_better_mobile_deals` in notifier.py; excludes voice-only + `price_conditional` rows; `best_price_alerted` ratchet + 72h cooldown prevent repeats - a re-alert needs a ≥₪1-better offer); (2) `plan_end` - one-shot reminder at `end_date - remind_days_before` (3/7/14/30), optional `include_offers` attaches retention alternatives (`find_similar_mobile_offers` - any carrier, ≥ data, cheapest first). Backend: `POST /api/mobile/reminders` (public; server snapshots price/data from the live feed, Israeli phones normalized 05x→972), `GET|POST /api/mobile/reminders/unsubscribe?token=` (GET = bilingual HTML confirmation for the email link; token shared per signup, deletes all its rows), `POST /api/mobile/reminders/run-now` (`@require_api_key` smoke test). Table `mobile_reminders` (db.py; re-signup for same kind+plan+contact replaces, not stacks). Daily job `run_mobile_reminders_job` at **09:15** (after the 07:30 scrape). Email via `_send_email` (Resend), WhatsApp via `_send_whatsapp_direct` (Green API; the chatId is resolved per phone via `checkWhatsapp` + module cache - `@lid` privacy accounts silently DROP messages sent to `<phone>@c.us` (200 + stuck at 'sent' forever), so never send to `@c.us` directly). Message links are config-driven via `public_site_url` / `public_api_url` in config.json (currently the Netlify subdomain + reserved ngrok domain per the mocaintel takedown; remove the keys to fall back to the canonical domains). Privacy policy section 3א/3a documents the contact-details collection - keep it in sync.

**Reminder emails are DESIGNED (2026-08-06):** branded HTML built by `_build_better_deal_html` / `_build_plan_end_html` / `_build_heartbeat_html` / `_build_renewal_html` in notifier.py (shared shell `_rem_email_shell` + `_rem_email_body`, palette mirrors `#mobile-app` tokens, tables + inline styles only). Hero illustrations are Gemini-generated (mocha palette, 21:9, `scripts/gen_email_banners.py`) hosted as PUBLIC Netlify URLs at `public/email/{better_deal,plan_end,heartbeat,renewal}.jpg` via `_rem_hero_url` - regenerating requires a frontend deploy. **Engagement layer (email-only until the Green API upgrade):** (a) better_deal emails carry a monthly+annual savings pill; (b) `notify_mobile_heartbeat` - monthly market-pulse email (percentile bar `_market_percentile` + 30d drops/rises from `db.count_domestic_price_drops` + cheapest/cheapest-unlimited chips), gated per row by 28 days since last touch (`last_heartbeat_at` column); (c) `notify_mobile_renewal_followups` - one-shot "התחדשתם?" email 7 days after a done plan_end's end_date (`followup_sent` column, rows via `db.get_mobile_plan_end_followups`), re-signup CTA closes the yearly loop. All 4 flows run in `run_mobile_reminders_job`. **Extensions (same day):** every email carries a refer-a-friend footer (`_rem_share_url`, utm_source=referral) and every text/WhatsApp body a share line; better_deal emails append a clearly-tagged "מתחת לקו" section of reseller offers that beat the user's plan (`_find_reseller_deals` over reseller_plans + `_rem_btl_cards_html`, dashed-border cards linking to source_url); the heartbeat carries the consumer "מדד MOCA" chip (`_market_ppgb` - GB-weighted SUM(price)/SUM(GB)); signup accepts an optional self-declared `paid_price` (5-500, column on mobile_reminders) and ALL comparisons use `_rem_base_price` (paid_price > current rate-card > snapshot). **Super-admin subscribers view:** `/admin/mobile-subscribers` (`MobileSubscribersPage.jsx`, superAdminOnly, profile-menu entry in Topbar+Navbar) ← `GET /api/mobile/reminders/subscribers` (`@require_api_key_or_super_admin`, `db.get_all_mobile_reminders` - raw contact details, stats, CSV export client-side; consent scope = reminders only, see privacy 3א). **Public-launch (Stage 2) checklist:** flip `MOBILE_B2C_LIVE=true`; `_redirects`: subdomain privacy/terms rules + `https://mobile.mocaintel.com/* /mobile.html 200` (after the esim host rule) + `/mobile-deals /mobile.html 200!`; sitemap.xml he+en entries + add `'mobile-deals'` to `STAMP_PATHS` in stamp-sitemap.mjs; reciprocal footer link in EsimComparePage; Cloudflare DNS CNAME `mobile` + Netlify domain alias; Search Console request-indexing.

**Legal pages (rewritten 2026-09-11 after the privacy/accessibility audit):** `public/privacy.html`, `terms.html`, `cookies.html`, `accessibility.html` — bilingual (he default, EN toggle via `?lang=en` / shared `esim_lang` localStorage key), static, self-styled, skip link + focus styles built in. Clean URLs `/privacy` `/terms` `/cookies` `/accessibility` via `_redirects` on BOTH hosts (the esim-subdomain host-scoped rules must precede the esim.html host wildcard) + netlify.toml mirror + `workbox.navigateFallbackDenylist`. Linked from every public footer (esim, mobile, hotels, landing, the 160 dest pages). `https://mocaintel.com/privacy` is the Play-Console privacy-policy URL. **The operator identity block (legal name, ח.פ., address, contact) is stamped at build time by `mass-market-app/scripts/stamp-legal.mjs` from `src/data/legalEntity.js`** (null fields are omitted - fill them in; the server-side twin for e-mail sender identification is config.json `business_name/business_id/business_address/business_email`, read by `notifier._sender_identity`). Content is code-accurate as of 2026-09-11 (processors: Netlify/Cloudflare/ngrok, Supabase, Resend/SendGrid, Green API/WhatsApp, Telegram for hotel leads, Anthropic for /api/chat, Google Drive backup; retention table mirrors `maintenance.PERSONAL_RETENTION`) — update it if data collection changes.

**Consent + anti-spam plumbing (2026-09-11):** `POST /api/mobile/reminders` and `POST /api/hotels/lead` refuse without `consent: true` and store `consent_at` + `consent_version`; reminders also carry `marketing_ok` (separate, unchecked-by-default opt-in) and the monthly market-pulse + renewal follow-up e-mails go ONLY to `marketing_ok=1` rows. Every message that promotes other carriers' plans is sent with `promo=True` → subject prefixed "פרסומת: " (Communications Law s.30A(e)), WhatsApp text opens with "פרסומת", and both channels end with `_sender_identity()`. The public consumer pages ship no third-party tracker by default; the TikTok pixel loads only after the CookieBanner's "accept all" (see mass-market-app/CLAUDE.md). `maintenance.prune_personal_data` (Sunday 03:00) enforces the retention periods the privacy policy states: analytics beacons 13 months, `user_activity` 180d, `hotel_leads` 24 months, finished reminders 90d.

## After Every Code Change

Always run `npm run build` in `mass-market-app/` after any React/JS change. Deploy `dist/` with `netlify deploy --prod --dir=dist --no-build` from `mass-market-app/` (see the deploy-live skill; `--no-build` is mandatory — the dashboard env vars are stale; manual drag is the fallback). The build also regenerates the prerendered `/` and `/hotels` static pages — so a change to `LandingPage.jsx` / `HotelsLandingPage.jsx` (or their copy) only goes live after a rebuild + redeploy (see Deployment → Static prerendered marketing pages).
