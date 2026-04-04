# Israeli Cellular Plans Comparison — Design Spec

**Date:** 2026-03-30
**Status:** Approved

---

## Context

The user wants a local tool that automatically monitors Israeli cellular carrier pricing twice daily and surfaces changes. Five carriers are tracked: Pelephone, Partner, Hot Mobile, Cellcom, and 019. The tool consists of a styled Hebrew RTL comparison website (served locally) and a Telegram bot that fires only when prices or plans change.

---

## Architecture

A single Python process (`app.py`) runs on Windows startup, combining a Flask web server with an APScheduler background job. Playwright handles browser automation for JS-rendered carrier pages. SQLite persists plan data and change history. Telegram notifications are sent via HTTP to the Bot API — no extra library required.

```
Windows Startup
    └── python app.py
            ├── Flask  →  localhost:5000  (always available)
            └── APScheduler  →  10:00 + 16:00
                    ├── scraper.py   (Playwright, 5 carriers async)
                    ├── change detector  (new data vs DB)
                    ├── notifier.py  (Telegram — only if changes)
                    └── DB update   (plans.db)
```

---

## File Structure

```
D:\השוואת MASS MARKET\
├── app.py                # Flask server + APScheduler entrypoint
├── scraper.py            # Playwright scrapers for all 5 carriers
├── notifier.py           # Telegram Bot API integration
├── config.json           # Bot token, Chat ID (user-filled on setup)
├── requirements.txt
├── data/
│   └── plans.db          # SQLite — plans + changes tables
└── templates/
    └── index.html        # RTL Hebrew UI (layout C)
```

---

## Components

### 1. Scraper (`scraper.py`)

- Uses `playwright.async_api` — launches headless Chromium
- All 5 carriers scraped **in parallel** (`asyncio.gather`)
- Each carrier has its own `scrape_<carrier>()` function
- Returns a list of plan dicts per carrier:

```python
{
  "carrier": "partner",
  "plan_name": "60GB בייסיק",
  "price": 49,
  "data_gb": 60,          # None = unlimited
  "minutes": "unlimited",
  "extras": ["Partner TV Basic"],
  "source_url": "https://..."
}
```

**Carriers and URLs:**
| Carrier | URL |
|---------|-----|
| Pelephone | https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/ |
| Partner | https://www.partner.co.il/n/cellularsale/lobby |
| Hot Mobile | https://www.hotmobile.co.il/saleslobby |
| Cellcom | https://cellcom.co.il/production/Private/Cellular/ |
| 019 | https://019mobile.co.il/חבילות-סלולר/ |

> **Note:** All sites are React/JS-rendered. Playwright must wait for DOM elements to load (`wait_for_selector`) before extracting data. CSS selectors per carrier may need tuning on first run.

### 2. Change Detector (inline in `app.py`)

On each scrape run:
1. Load previous plans from DB for each carrier
2. Compare with newly scraped plans by `(carrier, plan_name)` key
3. Detect: price changes, new plans, removed plans, extras changes
4. Write detected changes to `changes` table
5. Pass change list to notifier (empty list = no notification)

### 3. Database (`data/plans.db`)

**`plans` table** — latest state per plan:
```sql
CREATE TABLE plans (
  id         INTEGER PRIMARY KEY,
  carrier    TEXT,
  plan_name  TEXT,
  price      INTEGER,
  data_gb    INTEGER,       -- NULL = unlimited
  minutes    TEXT,
  extras     TEXT,          -- JSON array
  scraped_at TEXT,
  UNIQUE(carrier, plan_name)
);
```

**`changes` table** — full history:
```sql
CREATE TABLE changes (
  id         INTEGER PRIMARY KEY,
  carrier    TEXT,
  plan_name  TEXT,
  change_type TEXT,         -- 'price_change' | 'new_plan' | 'removed_plan' | 'extras_change'
  old_val    TEXT,
  new_val    TEXT,
  changed_at TEXT
);
```

### 4. Notifier (`notifier.py`)

- Sends Hebrew-formatted message via `requests.post` to Telegram Bot API
- Called only when change list is non-empty
- Message format (Hebrew, RTL):

```
📱 השוואת סלולר | עדכון 10:03

🔔 זוהו שינויים ב-2 חברות

● פרטנר
↘ חבילת 60GB: ₪59 → ₪49
✨ חבילה חדשה: ללא הגבלה ב-₪89

● הוט מובייל
↗ חבילת 30GB: ₪35 → ₪39

📊 http://localhost:5000
```

- Price decrease: `↘` + green formatting
- Price increase: `↗` + orange formatting
- New plan: `✨`
- Removed plan: `❌`

### 5. Flask Server (`app.py`)

**Routes:**
- `GET /` — serves `templates/index.html`
- `GET /api/plans?carrier=<name>` — returns current plans JSON
- `GET /api/changes?limit=20` — returns recent change history

### 6. Frontend (`templates/index.html`)

Single HTML file, no build step, no framework.

- **Direction:** RTL Hebrew (`dir="rtl"`, `lang="he"`)
- **Theme:** Dark (`#0d1117` background, GitHub-dark palette)
- **Layout C:** Sidebar (right) + plan cards (left)
- **Sidebar filters:** Carrier selector, GB range (All / ≤50 / 50–100 / 100+ / ∞), sort (price ↑↓, GB)
- **Plan cards:** carrier badge, price, GB, minutes, extras, change badges
- **Change badges:** "ירד מחיר" (orange) / "חדש" (green) — visible for 24h after change
- **Header:** last update time + next scheduled run
- **Data loading:** `fetch('/api/plans')` on page load; no auto-refresh (manual F5)

**Carrier color scheme:**
| Carrier | Color |
|---------|-------|
| Partner | #e91e63 |
| Pelephone | #2196f3 |
| Hot Mobile | #ff5722 |
| Cellcom | #4caf50 |
| 019 | #9c27b0 |

### 7. Configuration (`config.json`)

```json
{
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "schedule_times": ["10:00", "16:00"],
  "notify_on_changes_only": true
}
```

---

## Setup Flow (First Run)

1. `pip install -r requirements.txt`
2. `playwright install chromium`
3. Create Telegram bot via [@BotFather](https://t.me/BotFather) → get token
4. Get your Chat ID via [@userinfobot](https://t.me/userinfobot)
5. Fill in `config.json`
6. `python app.py` — opens `http://localhost:5000`
7. Add to Windows Task Scheduler: run `python app.py` at Windows login

---

## Dependencies (`requirements.txt`)

```
flask
playwright
apscheduler
requests
```

---

## Verification

1. Run `python app.py` → confirm Flask starts on port 5000
2. Open `http://localhost:5000` → confirm RTL Hebrew UI loads
3. Trigger manual scrape: call `GET /api/plans` and verify JSON returns data from all 5 carriers
4. Manually call notifier with a test change dict → confirm Telegram message received
5. Wait for scheduled run (or set schedule to 2 minutes for testing) → confirm DB updated and badge appears on changed plan
6. Confirm no Telegram message sent when scrape produces identical data
