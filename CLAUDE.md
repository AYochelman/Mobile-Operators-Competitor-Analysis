# Mass Market — Israeli Cellular Comparison System

## Project Overview
Flask app that scrapes 5 Israeli carriers twice daily, shows a Hebrew RTL comparison UI at localhost:5000, and sends Telegram + daily Excel email report on plan changes. Also available as a PWA (Progressive Web App) via ngrok with Web Push notifications.

## Project Path
`D:/השוואת MASS MARKET/`

## Architecture
- **app.py** — Flask server + APScheduler (scrape at 10:00 + 16:00, email report at 09:00). Listens on 0.0.0.0 for ngrok access. Auto-generates VAPID keys on first run.
- **scraper.py** — Playwright sync scraper for all 5 carriers (domestic + abroad + global eSIM + content services)
- **db.py** — SQLite (data/plans.db): `plans` + `changes` + `push_subscriptions` + `abroad_plans` + `abroad_changes` + `global_plans` + `global_changes` + `content_plans` + `content_changes` tables
- **change_detector.py** — Pure functions: `detect_changes()`, `detect_content_changes()`
- **notifier.py** — format_message(), format_abroad_message(), send_notification() (Telegram), send_whatsapp() (Green API), send_email_report() (SendGrid), send_push_notifications() (Web Push)
- **excel_report.py** — Builds daily Excel workbook (1 sheet/carrier, yellow rows = changed in 24h)
- **config.json** — All credentials and settings (including auto-generated VAPID keys)
- **templates/index.html** — RTL Hebrew **Minimal Clean** light UI with PWA support + bell button 🔔 + refresh button 🔄
- **static/sw.js** — Service worker for Web Push notifications
- **static/manifest.json** — PWA manifest (RTL Hebrew, standalone display)
- **static/icon-192.png** / **icon-512.png** — App icons (Pillow-generated)
- **start_ngrok.bat** — One-click ngrok tunnel launcher

## Carriers
| Key | Hebrew | Domestic Plans | Abroad Plans |
|-----|--------|---------------|--------------|
| partner | פרטנר | 5 | 7 |
| pelephone | פלאפון | 5 | ~20 (deduped) |
| hotmobile | הוט מובייל | 6 | 6 |
| cellcom | סלקום | 6 | 11 (8 via API + 3 silent roamers) |
| mobile019 | 019 | 8 | 3 |

## Global eSIM Providers
| Key | Display Name | Plans | Scrape Method |
|-----|-------------|-------|---------------|
| tuki | Tuki | 6 | DOM (.dataInfo_box cards), USD→ILS |
| globalesim | GlobaleSIM | 8 | DOM (.dataInfo_box), ILS direct |
| airalo | Airalo | ~20 | REST API: GET airalo.com/api/v4/regions/world with `x-client-version: version2` + `Referer: global-esim`, USD→ILS. Returns Discover (data-only) + Discover+ (voice+SMS) packages |
| pelephone_global | GlobalSIM - Pelephone | 5 | DOM (pelephone.co.il/global-sim), ILS direct |
| esimo | eSIMo | 5 | Next.js escaped JSON in HTML (`\"packages\"` literal) → bracket-counting extraction → unescape `\"` → `"` → JSON.parse, USD→ILS |
| simtlv | SimTLV | 8 | DOM (.elementor-price-table), ILS direct |
| world8 | 8 World | 2 | DOM (.price-card), ILS direct |

**Total global plans: ~40**

## Content Services (שירותי תוכן)
Imported from `D:\השוואת מתחרים - שירותי תוכן\` Streamlit project.

| Service | Carriers | Scrape Strategy |
|---------|----------|----------------|
| eSIM שעון | cellcom, partner, hotmobile, pelephone | keyword_scan / cellcom_faq_esim |
| סייבר | cellcom, partner, hotmobile, pelephone | keyword_scan / cellcom_hub |
| נורטון | cellcom, partner, hotmobile, pelephone | keyword_scan / cellcom_hub |
| שיר בהמתנה | cellcom, partner, hotmobile(לא זמין), pelephone | keyword_scan / html_scan / not_available |
| תא קולי | cellcom, partner, hotmobile(לא זמין), pelephone | keyword_scan / not_available |

- `CONTENT_SERVICES` list: 20 entries (5 services × 4 carriers) in `scraper.py`
- Price field includes ₪ symbol (e.g. `"₪19.90"`) — UI strips leading ₪ before display
- Strategies: `keyword_scan`, `cellcom_hub`, `cellcom_faq_esim`, `html_scan`, `not_available`
- `_extract_content_price()` + `_cellcom_hub_price()` helpers in scraper.py
- `scrape_all_content()` uses sync Playwright

## Schedule
- **10:00 + 16:00** — scrape all (domestic + abroad + global + content), detect changes, send Telegram + Web Push if changes
- **09:00** — send daily Excel email report via SendGrid

## Notifications
- **Telegram**: bot @Mass_Marketbot, token in config.json, chat_id: 6024815382
  - Domestic changes: `📱 השוואת סלולר | עדכון HH:MM`
  - Abroad changes: `✈️ חבילות חו"ל | עדכון HH:MM` (separate message)
  - Global changes: `🌍 חבילות גלובליות | עדכון HH:MM` (separate message)
  - Content changes: `📺 שירותי תוכן | עדכון HH:MM` (separate message)
- **WhatsApp**: Green API (instance 7107569664), phone field empty (disabled)
- **Email**: SendGrid API → alon.yoch@gmail.com → alonyoch@pelephone.co.il
- **Web Push**: VAPID keys auto-generated, stored in config.json, subscriptions in SQLite

## Credentials (config.json)
All credentials stored in `config.json` (not committed to git). Structure:
```json
{
  "telegram_bot_token": "<TELEGRAM_BOT_TOKEN>",
  "telegram_chat_id": "<CHAT_ID>",
  "schedule_times": ["10:00", "16:00"],
  "notify_on_changes_only": true,
  "greenapi_url": "<GREENAPI_URL>",
  "greenapi_instance": "<INSTANCE_ID>",
  "greenapi_token": "<GREENAPI_TOKEN>",
  "whatsapp_phone": "",
  "sendgrid_api_key": "<SENDGRID_API_KEY>",
  "email_sender": "<SENDER_EMAIL>",
  "email_recipient": "<RECIPIENT_EMAIL>",
  "email_report_time": "09:00",
  "vapid_private_key": "<AUTO_GENERATED>",
  "vapid_public_key": "<AUTO_GENERATED>",
  "vapid_email": "mailto:<EMAIL>"
}
```
Note: VAPID keys are auto-generated on first run if missing. Do not delete them after generation.
**SECURITY: Never commit config.json or real credentials to git.**

## PWA + Ngrok Setup
- **ngrok.exe** lives at `D:\השוואת MASS MARKET\ngrok.exe`
- **Authtoken** configured: `ngrok config add-authtoken <token>`
- **Start tunnel**: double-click `start_ngrok.bat` or run:
  `"D:\השוואת MASS MARKET\ngrok.exe" http 5000`
- **Current ngrok URL**: https://terra-nonrestrained-overpiteously.ngrok-free.dev (changes on restart)
- **Add to Home Screen**: open URL on phone → Share → "הוסף למסך הבית"
- **Bell button 🔔**: click in app header to subscribe to push notifications
- **Test push**: browse to `/api/push/test`

## API Routes (app.py)
- `GET /` — main dashboard
- `GET /sw.js` — service worker (Content-Type: application/javascript, no-cache)
- `GET /api/plans` — domestic plans JSON
- `GET /api/changes` — domestic change history JSON
- `GET /api/abroad-plans` — abroad plans JSON
- `GET /api/abroad-changes` — abroad change history JSON
- `GET /api/global-plans` — global eSIM plans JSON
- `GET /api/global-changes` — global eSIM change history JSON
- `GET /api/content-plans` — content services plans JSON
- `GET /api/content-changes` — content services change history JSON
- `GET /api/scrape-now` — manual trigger: scrape domestic plans
- `GET /api/scrape-abroad-now` — manual trigger: scrape abroad plans + detect changes
- `GET /api/scrape-global-now` — manual trigger: scrape global eSIM plans + detect changes
- `GET /api/scrape-content-now` — manual trigger: scrape content services + detect changes
- `GET /api/scrape-all-now` — manual trigger: scrape ALL tabs (domestic + abroad + global + content) in one call
- `GET /api/push/vapid-public-key` — returns VAPID public key
- `POST /api/push/subscribe` — saves push subscription to DB
- `DELETE /api/push/unsubscribe` — removes push subscription from DB
- `GET /api/push/test` — sends test push to all subscribers

## Windows Task Scheduler
- Task name: `CellularComparison`
- Trigger: At logon
- Action: `python "D:\השוואת MASS MARKET\app.py"`
- **Note**: After code changes, kill all python.exe processes and restart manually:
  `taskkill /F /IM python.exe` then `python "D:/השוואת MASS MARKET/app.py"`

## UI Features (templates/index.html)
- **Design**: Minimal Clean light theme (white cards, gray background, blue accents, pastel carrier badges)
- **Tab bar** (top, centered): 4 tabs:
  - 📱 חבילות Mass Market
  - ✈️ חבילות חו"ל
  - 🌍 חבילות גלובליות
  - 📺 שירותי תוכן
  - **Mobile (≤600px)**: 2×2 grid of bordered pill buttons (no underline), `flex: 0 0 calc(50% - 3px)`, `white-space: normal`, 10px border-radius, active = blue border + `#eff6ff` bg
- **Header buttons**: 🔄 עדכן הכל (green, triggers `/api/scrape-all-now`) + 🔔 Bell (push notifications)
  - Refresh button has subtitle: "עדכון כל החוצצים אורך כ־4 דקות" (10px gray, below button)
  - Refresh button states: loading ⏳ spin / success ✅ with count / error ❌
  - After successful scrape: auto-reloads all previously-visited tabs
- Plan name shown at TOP of each card (blue, bold)
- Carrier badge + price + details below
- Creator credit: "נוצר ע"י אלון יוכלמן" in header
- Last update shown with **date + time** (e.g. 04/04/2026 16:00)
- Change badges on cards: חדש (green) / שינוי מחיר (orange) / הוסרה (orange)
- **Sidebar filters (domestic)**: חברה, גלישה, גלישה בחו"ל, דור רשת (5G), חידושים, מיון
- **Sidebar filters (abroad)**: חברה, גלישה, תקופה (ימים), מיון
- **Sidebar filters (global)**: ספק (7 provider buttons), גלישה, תקופה, מטבע, מיון
- **Sidebar filters (content)**: חברה (4 carriers), שירות (5 services)
  - "חברה" section shared between domestic + abroad (hidden on global + content tabs)
- **Bug fix**: `.carrier-btn` event listener scoped to `[data-carrier]` only — prevents global/content carrier buttons from setting `state.carrier = undefined` and causing blank screen on tab switch
- Recent changes list: clickable items → filter to carrier + scroll+highlight card
- Roaming filter: checks extras for "חו"ל" + digit + GB/גלישה pattern
- 5G filter: matches plan_name or extras containing "5G"
- No-cache headers to prevent browser caching issues
- Bell button 🔔 in header: green when subscribed, grey when not
- PWA meta tags: theme-color, apple-mobile-web-app-capable, manifest link

## Content Services Tab (שירותי תוכן)
- Organized by service (5 sections), each section shows carrier cards in a grid
- Each card: carrier badge + price (₪/month) + free trial period + notes
- Change badges: חדש (new_service) / שינוי מחיר (price_change) / שינוי ניסיון (trial_change)
- CSS classes: `.content-service-section`, `.content-service-title`, `.content-cards-grid`, `.content-card`, `.content-price-val`, `.content-trial`, `.content-note`, `.content-na`
- Data loaded lazily on first tab visit (same pattern as abroad/global tabs)
- Price field may include ₪ symbol from scraper — stripped via `.replace(/^₪\s*/, '')` before display

## Global eSIM Card Display
- Provider badge with color dot (7 distinct colors)
- eSIM badge (green pill) on all global cards
- Price in ₪ (converted from original currency)
- Original price + currency shown below (e.g. "$14.90 USD")
- Days / GB / Minutes / SMS fields
- GLOBAL_LABELS map: `{ tuki, globalesim, airalo, pelephone_global: 'GlobalSIM - Pelephone', esimo, simtlv, world8 }`

## Abroad Scraper Details (scraper.py)
- `scrape_all_abroad()` → calls all 5 per-carrier abroad scrapers
- **Pelephone**: `.package` cards, clicks `.btn_more_packs.more_show` to reveal hidden plans, dedupes by (name, days, price)
- **Cellcom**: uses internal REST API `POST digital-api.cellcom.co.il/api/abroad/GetPackagePopular` for 8 lobby plans + DOM scrape of `/AbroadMain/Silent_roamers-old/` for 3 more
- **Partner**: `.package-wrapper` cards, clicks "לצפייה בחבילות נוספות" to reveal 3 more
- **Hot Mobile**: `.lobby2022_dealsItem` cards, clicks "לחבילות נוספות" to reveal hidden cards
- **019**: `.item_pack` cards, all visible upfront
- abroad plan fields: carrier, plan_name, price, days, data_gb, minutes, sms, extras
- First run seeds `abroad_changes` with all plans as `new_plan` so badges appear immediately

## Global eSIM Scraper Details (scraper.py)
- `scrape_all_global()` → fetches live USD+EUR→ILS rates, then calls all 7 scrapers in sequence
- **Airalo**: REST API `GET https://www.airalo.com/api/v4/regions/world` with headers `x-client-version: version2` + `Referer: https://www.airalo.com/global-esim` → returns 20 packages from both Discover (data-only) and Discover+ (voice+SMS) operators. No Playwright needed.
- **eSIMo**: Playwright → `https://esimo.io/product/global-esim-only-data` → finds `\"packages\":[` literal in Next.js escaped HTML → bracket-counting extraction → unescape `\"` → `"` → JSON.parse. Prices in USD.
- **GlobaleSIM**: DOM `.dataInfo_box` cards, two tabs (data-only + calls+data), deduped by name. Prices in ILS.
- **GlobalSIM - Pelephone**: DOM `.packs > div[id^='p']` cards on pelephone.co.il/global-sim. Prices in ILS.
- **Tuki**: DOM `.dataInfo_box` cards. Prices in USD→ILS.
- **SimTLV**: DOM `.elementor-price-table` cards. Prices in ILS.
- **8 World**: DOM `.price-card` cards. Prices in ILS.
- global plan fields: carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at
- First run seeds `global_changes` with all plans as `new_plan` so badges appear immediately

## DB Tables
| Table | Key fields |
|-------|-----------|
| plans | carrier, plan_name, price, data_gb, minutes, extras, scraped_at |
| changes | carrier, plan_name, change_type, old_val, new_val, changed_at |
| abroad_plans | carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at |
| abroad_changes | carrier, plan_name, change_type, old_val, new_val, changed_at |
| global_plans | carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at |
| global_changes | carrier, plan_name, change_type, old_val, new_val, changed_at |
| push_subscriptions | endpoint, p256dh, auth, created_at |
| content_plans | service, carrier, price, free_trial, note, status, scraped_at — UNIQUE(service, carrier) |
| content_changes | service, carrier, change_type, old_val, new_val, changed_at |

## Change Types (change_detector.py)
| change_type | מתי | שדות |
|-------------|-----|------|
| `new_plan` | חבילה חדשה | new_val = price |
| `removed_plan` | חבילה הוסרה | old_val = price |
| `price_change` | שינוי מחיר | old_val, new_val = מחיר |
| `extras_change` | שינוי הטבות/תוספות | old_val, new_val = רשימת extras |
| `details_change` | שינוי ימים/גלישה/דקות/SMS | old_val, new_val = תיאור טקסטואלי |
| `new_service` | שירות תוכן חדש | new_val = price |
| `price_change` | שינוי מחיר בשירות תוכן | old_val, new_val = מחיר |
| `trial_change` | שינוי תקופת ניסיון | old_val, new_val = תיאור |

## data_gb Format
- `None` → "ללא הגבלה" (unlimited)
- `>= 1` → "X GB"
- `0 < x < 1` → "X MB" (e.g. 100MB stored as 100/1024 ≈ 0.0977)
- `_parse_gb()` handles MB via regex `(\d+)\s*mb` → divides by 1024
- UI: `plan.data_gb < 1 ? Math.round(data_gb * 1024) + "MB" : data_gb + "GB"`

## Key Technical Details
- Playwright sync API (headless Chromium) for JS-rendered carrier sites
- SQLite with UNIQUE(carrier, plan_name) + ON CONFLICT upsert
- APScheduler BackgroundScheduler with cron jobs
- Excel: openpyxl, RTL sheets, header #4472C4, changed rows #FFFF00
- SendGrid Single Sender verified: alon.yoch@gmail.com (Mass Market)
- Green API WhatsApp: currently disabled (whatsapp_phone is empty)
- Flask: SEND_FILE_MAX_AGE_DEFAULT=0, no-cache headers on index route, host=0.0.0.0
- pywebpush 2.3.0 + cryptography: VAPID keys use X962/UncompressedPoint encoding → urlsafe base64
- Pillow 12.1.1: used to generate icon-192.png and icon-512.png
- Currency conversion: `_get_usd_to_ils()` and `_get_eur_to_ils()` via open.er-api.com (fallback: 3.7 / 4.0)

## Run
```bash
python "D:/השוואת MASS MARKET/app.py"
# → http://localhost:5000
# → http://0.0.0.0:5000 (all interfaces)
```

## After Code Changes — Restart Procedure
1. `taskkill /F /IM python.exe`
2. `python "D:/השוואת MASS MARKET/app.py"`
3. Browse to `http://localhost:5000/api/scrape-all-now` (scrapes all tabs at once)
4. Hard refresh browser: Ctrl+Shift+R

## Tests
```bash
pytest tests/ -v
```
