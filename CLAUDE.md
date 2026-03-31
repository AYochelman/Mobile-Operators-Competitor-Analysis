# Mass Market — Israeli Cellular Comparison System

## Project Overview
Flask app that scrapes 5 Israeli carriers twice daily, shows a Hebrew RTL comparison UI at localhost:5000, and sends Telegram + daily Excel email report on plan changes.

## Project Path
`D:/השוואת MASS MARKET/`

## Architecture
- **app.py** — Flask server + APScheduler (scrape at 10:00 + 16:00, email report at 09:00)
- **scraper.py** — Playwright sync scraper for all 5 carriers
- **db.py** — SQLite (data/plans.db): `plans` table + `changes` history
- **change_detector.py** — Pure function: detect_changes(old, new) → change list
- **notifier.py** — format_message(), send_notification() (Telegram), send_whatsapp() (Green API), send_email_report() (SendGrid)
- **excel_report.py** — Builds daily Excel workbook (1 sheet/carrier, yellow rows = changed in 24h)
- **config.json** — All credentials and settings
- **templates/index.html** — RTL Hebrew dark UI

## Carriers
| Key | Hebrew | Plans |
|-----|--------|-------|
| partner | פרטנר | 5 |
| pelephone | פלאפון | 5 |
| hotmobile | הוט מובייל | 6 |
| cellcom | סלקום | 3 |
| mobile019 | 019 | 8 |

## Schedule
- **10:00 + 16:00** — scrape all 5 carriers, detect changes, send Telegram if changes
- **09:00** — send daily Excel email report via SendGrid

## Notifications
- **Telegram**: bot @Mass_Marketbot, token in config.json, chat_id: 6024815382
- **WhatsApp**: Green API (instance 7107569664), phone field empty (disabled)
- **Email**: SendGrid API → alon.yoch@gmail.com → alonyoch@pelephone.co.il

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
  "email_report_time": "09:00"
}
```

## Windows Task Scheduler
- Task name: `CellularComparison`
- Trigger: At logon
- Action: `python "D:\השוואת MASS MARKET\app.py"`

## Key Technical Details
- Playwright sync API (headless Chromium) for JS-rendered carrier sites
- SQLite with UNIQUE(carrier, plan_name) + ON CONFLICT upsert
- APScheduler BackgroundScheduler with cron jobs
- Excel: openpyxl, RTL sheets, header #4472C4, changed rows #FFFF00
- SendGrid Single Sender verified: alon.yoch@gmail.com (Mass Market)
- Green API WhatsApp: currently disabled (whatsapp_phone is empty)

## Run
```bash
cd "D:/השוואת MASS MARKET"
python app.py
# → http://localhost:5000
```

## Tests
```bash
pytest tests/ -v
```
