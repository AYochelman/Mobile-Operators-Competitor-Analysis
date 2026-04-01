# Mass Market — Israeli Cellular Comparison System

## Project Overview
Flask app that scrapes 5 Israeli carriers twice daily, shows a Hebrew RTL comparison UI at localhost:5000, and sends Telegram + daily Excel email report on plan changes. Also available as a PWA (Progressive Web App) via ngrok with Web Push notifications.

## Project Path
`D:/השוואת MASS MARKET/`

## Architecture
- **app.py** — Flask server + APScheduler (scrape at 10:00 + 16:00, email report at 09:00). Listens on 0.0.0.0 for ngrok access. Auto-generates VAPID keys on first run.
- **scraper.py** — Playwright sync scraper for all 5 carriers
- **db.py** — SQLite (data/plans.db): `plans` table (price REAL) + `changes` history + `push_subscriptions` table
- **change_detector.py** — Pure function: detect_changes(old, new) → change list
- **notifier.py** — format_message(), send_notification() (Telegram), send_whatsapp() (Green API), send_email_report() (SendGrid), send_push_notifications() (Web Push)
- **excel_report.py** — Builds daily Excel workbook (1 sheet/carrier, yellow rows = changed in 24h)
- **config.json** — All credentials and settings (including auto-generated VAPID keys)
- **templates/index.html** — RTL Hebrew dark UI with PWA support + bell button 🔔
- **static/sw.js** — Service worker for Web Push notifications
- **static/manifest.json** — PWA manifest (RTL Hebrew, standalone display)
- **static/icon-192.png** / **icon-512.png** — App icons (Pillow-generated)
- **start_ngrok.bat** — One-click ngrok tunnel launcher

## Carriers
| Key | Hebrew | Plans |
|-----|--------|-------|
| partner | פרטנר | 5 |
| pelephone | פלאפון | 5 |
| hotmobile | הוט מובייל | 6 |
| cellcom | סלקום | 3 |
| mobile019 | 019 | 8 |

## Schedule
- **10:00 + 16:00** — scrape all 5 carriers, detect changes, send Telegram + Web Push if changes
- **09:00** — send daily Excel email report via SendGrid

## Notifications
- **Telegram**: bot @Mass_Marketbot, token in config.json, chat_id: 6024815382
- **WhatsApp**: Green API (instance 7107569664), phone field empty (disabled)
- **Email**: SendGrid API → alon.yoch@gmail.com → alonyoch@pelephone.co.il
- **Web Push**: VAPID keys auto-generated, stored in config.json, subscriptions in SQLite

## Credentials (config.json)
```json
{
  "telegram_bot_token": "8740382640:AAH6JFoyooa9HoT-aL9cAsbTN8QDenx_WaI",
  "telegram_chat_id": "6024815382",
  "schedule_times": ["10:00", "16:00"],
  "notify_on_changes_only": true,
  "greenapi_url": "https://7107.api.greenapi.com",
  "greenapi_instance": "7107569664",
  "greenapi_token": "7538a29c287a42359016621d434566a6115b43c6685043889a",
  "whatsapp_phone": "",
  "sendgrid_api_key": "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",
  "email_sender": "alon.yoch@gmail.com",
  "email_recipient": "alonyoch@pelephone.co.il",
  "email_report_time": "09:00",
  "vapid_private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "vapid_public_key": "BMFFJCUEsyEOdw...",
  "vapid_email": "mailto:alon.yoch@gmail.com"
}
```
Note: VAPID keys are auto-generated on first run if missing. Do not delete them after generation.

## PWA + Ngrok Setup
- **ngrok.exe** lives at `D:\השוואת MASS MARKET\ngrok.exe`
- **Authtoken** configured: `ngrok config add-authtoken <token>`
- **Start tunnel**: double-click `start_ngrok.bat` or run:
  `"D:\השוואת MASS MARKET\ngrok.exe" http 5000`
- **Current ngrok URL**: https://terra-nonrestrained-overpiteously.ngrok-free.dev (changes on restart)
- **Add to Home Screen**: open URL on phone → Share → "הוסף למסך הבית"
- **Bell button 🔔**: click in app header to subscribe to push notifications
- **Test push**: browse to `/api/push/test`

## PWA Routes (app.py)
- `GET /sw.js` — service worker (Content-Type: application/javascript, no-cache)
- `GET /api/push/vapid-public-key` — returns VAPID public key for browser subscription
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
- Plan name shown at TOP of each card (blue, bold)
- Carrier badge + price + details below
- Sidebar filters: חברה, גלישה, דור רשת (5G בלבד), מיון
- 5G filter: matches plan_name or extras containing "5G"
- No-cache headers to prevent browser caching issues
- Bell button 🔔 in header: green when subscribed, grey when not
- PWA meta tags: theme-color, apple-mobile-web-app-capable, manifest link

## Scraper Details
- `_parse_price()` returns float (no rounding) — e.g. 39.90 not 40
- `plans.price` column is REAL in SQLite
- Partner extras: `.mid_white .inc span > span` deduplicated + `.free_apps span`
- Pelephone extras: `.mid_white .inc span > span` deduplicated + `.free_apps span`
- Hot Mobile extras: parsed from hidden `input[id^="planDetails-"]` JSON field
- 019 extras: `.blist li` elements

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

## Run
```bash
python "D:/השוואת MASS MARKET/app.py"
# → http://localhost:5000
# → http://0.0.0.0:5000 (all interfaces)
```

## After Code Changes — Restart Procedure
1. `taskkill /F /IM python.exe`
2. `python "D:/השוואת MASS MARKET/app.py"`
3. Browse to `http://localhost:5000/api/scrape-now`
4. Hard refresh browser: Ctrl+Shift+R

## Tests
```bash
pytest tests/ -v
```
