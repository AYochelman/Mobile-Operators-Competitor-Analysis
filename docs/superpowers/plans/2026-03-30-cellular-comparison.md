# Israeli Cellular Plans Comparison — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Flask app that scrapes 5 Israeli carrier websites twice daily, shows a Hebrew RTL comparison UI at localhost:5000, and sends Telegram notifications only when prices or plans change.

**Architecture:** A single Python process (`app.py`) starts on Windows login, combining Flask (web UI) with APScheduler (cron at 10:00 + 16:00). Playwright scrapes JS-rendered carrier pages sequentially. SQLite stores current plans + change history. Telegram notifications go via direct HTTP to Bot API.

**Tech Stack:** Python 3, Flask, Playwright (sync), APScheduler, SQLite (stdlib), requests, pytest

---

## File Map

| File | Responsibility |
|------|----------------|
| `app.py` | Flask routes + APScheduler startup + scrape pipeline orchestration |
| `db.py` | All SQLite operations (init, save, query) |
| `change_detector.py` | Pure function: compare old vs new plans → change list |
| `notifier.py` | Format Hebrew Telegram message + send via Bot API |
| `scraper.py` | Playwright scrapers for all 5 carriers |
| `config.json` | User config (bot token, chat ID, schedule times) |
| `requirements.txt` | Python dependencies |
| `templates/index.html` | RTL Hebrew dark UI — sidebar + plan cards |
| `tests/test_db.py` | DB unit tests (in-memory SQLite) |
| `tests/test_change_detector.py` | Change detection unit tests |
| `tests/test_notifier.py` | Notifier unit tests (mocked requests) |
| `tests/test_api.py` | Flask route tests (test client) |

---

## Task 1: Scaffold — directories, requirements, config template

**Files:**
- Create: `requirements.txt`
- Create: `config.json`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
flask
playwright
apscheduler
requests
pytest
```

- [ ] **Step 2: Create `config.json`**

```json
{
  "telegram_bot_token": "YOUR_BOT_TOKEN_HERE",
  "telegram_chat_id": "YOUR_CHAT_ID_HERE",
  "schedule_times": ["10:00", "16:00"],
  "notify_on_changes_only": true
}
```

- [ ] **Step 3: Create directory structure**

```bash
cd "D:\השוואת MASS MARKET"
mkdir data templates tests
type nul > data\.gitkeep
type nul > tests\__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

Expected: `playwright install chromium` downloads ~130MB Chromium binary with no errors.

- [ ] **Step 5: Commit**

```bash
git init
git add requirements.txt config.json tests/__init__.py
git commit -m "feat: project scaffold"
```

---

## Task 2: Database module (`db.py`)

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db.py`:

```python
import os
import pytest
import tempfile
from db import init_db, save_plans, get_plans, save_changes, get_changes

@pytest.fixture
def tmp_db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(db_path=path)
    return path

SAMPLE_PLANS = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,
     "data_gb": 60, "minutes": "unlimited", "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 69,
     "data_gb": 100, "minutes": "unlimited", "extras": []},
    {"carrier": "pelephone", "plan_name": "50GB", "price": 55,
     "data_gb": 50, "minutes": "unlimited", "extras": []},
]

def test_init_creates_tables(tmp_db):
    plans = get_plans(db_path=tmp_db)
    assert plans == []

def test_save_and_get_all_plans(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    plans = get_plans(db_path=tmp_db)
    assert len(plans) == 3

def test_get_plans_filter_by_carrier(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    plans = get_plans(carrier="partner", db_path=tmp_db)
    assert len(plans) == 2
    assert all(p["carrier"] == "partner" for p in plans)

def test_save_plans_upsert(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    updated = [{"carrier": "partner", "plan_name": "60GB", "price": 45,
                "data_gb": 60, "minutes": "unlimited", "extras": []}]
    save_plans(updated, db_path=tmp_db)
    plans = get_plans(carrier="partner", db_path=tmp_db)
    sixty = next(p for p in plans if p["plan_name"] == "60GB")
    assert sixty["price"] == 45  # updated

def test_save_and_get_changes(tmp_db):
    changes = [
        {"carrier": "partner", "plan_name": "60GB",
         "change_type": "price_change", "old_val": "59", "new_val": "49"}
    ]
    save_changes(changes, db_path=tmp_db)
    result = get_changes(db_path=tmp_db)
    assert len(result) == 1
    assert result[0]["change_type"] == "price_change"

def test_get_changes_limit(tmp_db):
    changes = [
        {"carrier": "partner", "plan_name": f"plan{i}",
         "change_type": "new_plan", "old_val": None, "new_val": "49"}
        for i in range(5)
    ]
    save_changes(changes, db_path=tmp_db)
    result = get_changes(limit=3, db_path=tmp_db)
    assert len(result) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "D:\השוואת MASS MARKET"
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Create `db.py`**

```python
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "plans.db")


def _connect(db_path=None):
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return sqlite3.connect(path)


def init_db(db_path=None):
    conn = _connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS plans (
            id         INTEGER PRIMARY KEY,
            carrier    TEXT NOT NULL,
            plan_name  TEXT NOT NULL,
            price      INTEGER,
            data_gb    INTEGER,
            minutes    TEXT,
            extras     TEXT,
            scraped_at TEXT,
            UNIQUE(carrier, plan_name)
        );
        CREATE TABLE IF NOT EXISTS changes (
            id          INTEGER PRIMARY KEY,
            carrier     TEXT NOT NULL,
            plan_name   TEXT NOT NULL,
            change_type TEXT NOT NULL,
            old_val     TEXT,
            new_val     TEXT,
            changed_at  TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def save_plans(plans, db_path=None):
    conn = _connect(db_path)
    now = datetime.now().isoformat()
    for plan in plans:
        conn.execute("""
            INSERT INTO plans (carrier, plan_name, price, data_gb, minutes, extras, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(carrier, plan_name) DO UPDATE SET
                price      = excluded.price,
                data_gb    = excluded.data_gb,
                minutes    = excluded.minutes,
                extras     = excluded.extras,
                scraped_at = excluded.scraped_at
        """, (
            plan["carrier"], plan["plan_name"], plan.get("price"),
            plan.get("data_gb"), plan.get("minutes"),
            json.dumps(plan.get("extras", []), ensure_ascii=False),
            now
        ))
    conn.commit()
    conn.close()


def get_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    if carrier:
        rows = conn.execute(
            "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at "
            "FROM plans WHERE carrier=? ORDER BY price",
            (carrier,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at "
            "FROM plans ORDER BY carrier, price"
        ).fetchall()
    conn.close()
    return [
        {
            "carrier": r[0], "plan_name": r[1], "price": r[2],
            "data_gb": r[3], "minutes": r[4],
            "extras": json.loads(r[5]) if r[5] else [],
            "scraped_at": r[6]
        }
        for r in rows
    ]


def save_changes(changes, db_path=None):
    conn = _connect(db_path)
    now = datetime.now().isoformat()
    for ch in changes:
        conn.execute(
            "INSERT INTO changes (carrier, plan_name, change_type, old_val, new_val, changed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ch["carrier"], ch["plan_name"], ch["change_type"],
             str(ch["old_val"]) if ch.get("old_val") is not None else None,
             str(ch["new_val"]) if ch.get("new_val") is not None else None,
             now)
        )
    conn.commit()
    conn.close()


def get_changes(limit=20, db_path=None):
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
        "FROM changes ORDER BY changed_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
         "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
        for r in rows
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: database module with init, save, query operations"
```

---

## Task 3: Change detector (`change_detector.py`)

**Files:**
- Create: `change_detector.py`
- Create: `tests/test_change_detector.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_change_detector.py`:

```python
from change_detector import detect_changes

OLD = [
    {"carrier": "partner", "plan_name": "60GB", "price": 59,
     "data_gb": 60, "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 79,
     "data_gb": 100, "extras": []},
    {"carrier": "pelephone", "plan_name": "OLD_PLAN", "price": 55,
     "data_gb": 50, "extras": []},
]

NEW = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,       # price dropped
     "data_gb": 60, "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 79,      # unchanged
     "data_gb": 100, "extras": []},
    {"carrier": "partner", "plan_name": "ללא הגבלה", "price": 89, # new plan
     "data_gb": None, "extras": []},
    # pelephone OLD_PLAN removed
]

def test_no_changes_returns_empty():
    assert detect_changes(OLD[:2], OLD[:2]) == []

def test_detects_price_decrease():
    changes = detect_changes(OLD, NEW)
    price_changes = [c for c in changes if c["change_type"] == "price_change"]
    assert len(price_changes) == 1
    assert price_changes[0]["plan_name"] == "60GB"
    assert price_changes[0]["old_val"] == 59
    assert price_changes[0]["new_val"] == 49

def test_detects_new_plan():
    changes = detect_changes(OLD, NEW)
    new_plans = [c for c in changes if c["change_type"] == "new_plan"]
    assert len(new_plans) == 1
    assert new_plans[0]["plan_name"] == "ללא הגבלה"
    assert new_plans[0]["new_val"] == 89

def test_detects_removed_plan():
    changes = detect_changes(OLD, NEW)
    removed = [c for c in changes if c["change_type"] == "removed_plan"]
    assert len(removed) == 1
    assert removed[0]["plan_name"] == "OLD_PLAN"
    assert removed[0]["carrier"] == "pelephone"

def test_detects_extras_change():
    old = [{"carrier": "partner", "plan_name": "60GB", "price": 49,
            "data_gb": 60, "extras": ["TV Basic"]}]
    new = [{"carrier": "partner", "plan_name": "60GB", "price": 49,
            "data_gb": 60, "extras": ["TV Basic", "Roaming"]}]
    changes = detect_changes(old, new)
    assert len(changes) == 1
    assert changes[0]["change_type"] == "extras_change"

def test_unchanged_plan_produces_no_change():
    plans = [{"carrier": "partner", "plan_name": "60GB", "price": 49,
              "data_gb": 60, "extras": []}]
    assert detect_changes(plans, plans) == []
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_change_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'change_detector'`

- [ ] **Step 3: Create `change_detector.py`**

```python
from collections import defaultdict


def detect_changes(old_plans, new_plans):
    """
    Compare two lists of plan dicts.
    Returns list of change dicts:
      {carrier, plan_name, change_type, old_val, new_val}
    change_type: 'price_change' | 'new_plan' | 'removed_plan' | 'extras_change'
    """
    old_map = {(p["carrier"], p["plan_name"]): p for p in old_plans}
    new_map = {(p["carrier"], p["plan_name"]): p for p in new_plans}
    changes = []

    for key, new_plan in new_map.items():
        if key not in old_map:
            changes.append({
                "carrier": key[0], "plan_name": key[1],
                "change_type": "new_plan",
                "old_val": None, "new_val": new_plan.get("price")
            })
        else:
            old_plan = old_map[key]
            if old_plan.get("price") != new_plan.get("price"):
                changes.append({
                    "carrier": key[0], "plan_name": key[1],
                    "change_type": "price_change",
                    "old_val": old_plan.get("price"),
                    "new_val": new_plan.get("price")
                })
            old_extras = sorted(old_plan.get("extras") or [])
            new_extras = sorted(new_plan.get("extras") or [])
            if old_extras != new_extras:
                changes.append({
                    "carrier": key[0], "plan_name": key[1],
                    "change_type": "extras_change",
                    "old_val": old_extras, "new_val": new_extras
                })

    for key in old_map:
        if key not in new_map:
            changes.append({
                "carrier": key[0], "plan_name": key[1],
                "change_type": "removed_plan",
                "old_val": old_map[key].get("price"), "new_val": None
            })

    return changes
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_change_detector.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add change_detector.py tests/test_change_detector.py
git commit -m "feat: change detector — detects price, new, removed, extras changes"
```

---

## Task 4: Notifier (`notifier.py`)

**Files:**
- Create: `notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_notifier.py`:

```python
from unittest.mock import patch, MagicMock
from notifier import format_message, send_notification

PRICE_DROP = [
    {"carrier": "partner", "plan_name": "60GB",
     "change_type": "price_change", "old_val": 59, "new_val": 49}
]

PRICE_RISE = [
    {"carrier": "hotmobile", "plan_name": "30GB",
     "change_type": "price_change", "old_val": 35, "new_val": 39}
]

NEW_PLAN = [
    {"carrier": "cellcom", "plan_name": "ללא הגבלה",
     "change_type": "new_plan", "old_val": None, "new_val": 89}
]

REMOVED = [
    {"carrier": "pelephone", "plan_name": "OLD",
     "change_type": "removed_plan", "old_val": 55, "new_val": None}
]

def test_format_price_drop_contains_arrow_down():
    msg = format_message(PRICE_DROP)
    assert "↘" in msg
    assert "59" in msg
    assert "49" in msg
    assert "פרטנר" in msg

def test_format_price_rise_contains_arrow_up():
    msg = format_message(PRICE_RISE)
    assert "↗" in msg
    assert "הוט מובייל" in msg

def test_format_new_plan_contains_sparkle():
    msg = format_message(NEW_PLAN)
    assert "✨" in msg
    assert "ללא הגבלה" in msg

def test_format_removed_plan_contains_x():
    msg = format_message(REMOVED)
    assert "❌" in msg
    assert "OLD" in msg

def test_format_contains_localhost_url():
    msg = format_message(PRICE_DROP)
    assert "localhost:5000" in msg

def test_format_multi_carrier_shows_count():
    changes = PRICE_DROP + PRICE_RISE
    msg = format_message(changes)
    assert "2" in msg

def test_send_notification_success():
    config = {"telegram_bot_token": "TOKEN123", "telegram_chat_id": "CHAT456"}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("notifier.requests.post", return_value=mock_resp) as mock_post:
        result = send_notification("test message", config)
    assert result is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "TOKEN123" in call_kwargs.args[0]
    assert call_kwargs.kwargs["json"]["chat_id"] == "CHAT456"
    assert call_kwargs.kwargs["json"]["text"] == "test message"

def test_send_notification_failure():
    config = {"telegram_bot_token": "BAD", "telegram_chat_id": "BAD"}
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("notifier.requests.post", return_value=mock_resp):
        result = send_notification("msg", config)
    assert result is False
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_notifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'notifier'`

- [ ] **Step 3: Create `notifier.py`**

```python
import requests
from datetime import datetime
from collections import defaultdict

CARRIER_NAMES = {
    "partner":   "פרטנר",
    "pelephone": "פלאפון",
    "hotmobile": "הוט מובייל",
    "cellcom":   "סלקום",
    "mobile019": "019",
}


def format_message(changes):
    now = datetime.now().strftime("%H:%M")
    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch["carrier"]].append(ch)

    n = len(by_carrier)
    suffix = "חברה" if n == 1 else "חברות"
    lines = [
        f"📱 השוואת סלולר | עדכון {now}",
        "",
        f"🔔 זוהו שינויים ב-{n} {suffix}",
    ]

    for carrier, carrier_changes in by_carrier.items():
        name = CARRIER_NAMES.get(carrier, carrier)
        lines.append(f"\n● {name}")
        for ch in carrier_changes:
            ct = ch["change_type"]
            if ct == "price_change":
                old, new = ch["old_val"], ch["new_val"]
                arrow = "↘" if new < old else "↗"
                lines.append(f"{arrow} {ch['plan_name']}: ₪{old} ← ₪{new}")
            elif ct == "new_plan":
                lines.append(f"✨ חבילה חדשה: {ch['plan_name']} ב-₪{ch['new_val']}")
            elif ct == "removed_plan":
                lines.append(f"❌ הוסרה: {ch['plan_name']}")
            elif ct == "extras_change":
                lines.append(f"🔄 שינוי הטבות: {ch['plan_name']}")

    lines += ["", "📊 http://localhost:5000"]
    return "\n".join(lines)


def send_notification(message, config):
    token = config["telegram_bot_token"]
    chat_id = config["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notifier.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "feat: telegram notifier with Hebrew message formatting"
```

---

## Task 5: Flask API (`app.py`)

**Files:**
- Create: `app.py`
- Create: `tests/test_api.py`
- Create: `templates/index.html` (placeholder — replaced in Task 10)

- [ ] **Step 1: Write failing tests**

Create `tests/test_api.py`:

```python
import json
import pytest
import tempfile
import os
os.environ["TEST_DB"] = "1"  # flag for app to use temp DB

from app import app as flask_app
from db import init_db, save_plans

PLANS = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,
     "data_gb": 60, "minutes": "unlimited", "extras": ["TV"]},
    {"carrier": "pelephone", "plan_name": "50GB", "price": 55,
     "data_gb": 50, "minutes": "unlimited", "extras": []},
]

@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "test.db")
    flask_app.config["TEST_DB_PATH"] = db
    flask_app.config["TESTING"] = True
    init_db(db_path=db)
    save_plans(PLANS, db_path=db)
    with flask_app.test_client() as c:
        yield c

def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"html" in resp.data.lower()

def test_api_plans_returns_all(client):
    resp = client.get("/api/plans")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert len(data) == 2

def test_api_plans_filter_by_carrier(client):
    resp = client.get("/api/plans?carrier=partner")
    data = json.loads(resp.data)
    assert len(data) == 1
    assert data[0]["carrier"] == "partner"

def test_api_changes_returns_list(client):
    resp = client.get("/api/changes")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert isinstance(data, list)
```

- [ ] **Step 2: Create minimal `templates/index.html`** (placeholder for tests)

```html
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head><meta charset="UTF-8"><title>השוואת סלולר</title></head>
<body><h1>טוען...</h1></body>
</html>
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 4: Create `app.py`**

```python
import json
import os
import logging
from flask import Flask, jsonify, render_template, request, current_app
from db import init_db, get_plans, get_changes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

app = Flask(__name__)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _db_path():
    """Return test DB path when running under pytest, else default."""
    return app.config.get("TEST_DB_PATH") or None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/plans")
def api_plans():
    carrier = request.args.get("carrier")
    plans = get_plans(carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/changes")
def api_changes():
    limit = int(request.args.get("limit", 20))
    changes = get_changes(limit=limit, db_path=_db_path())
    return jsonify(changes)


if __name__ == "__main__":
    from apscheduler.schedulers.background import BackgroundScheduler
    from change_detector import detect_changes
    from notifier import format_message, send_notification
    import scraper

    def run_scrape_job():
        logger.info("Starting scheduled scrape...")
        config = load_config()
        try:
            new_plans = scraper.scrape_all()
            from db import save_plans, save_changes
            old_plans = get_plans()
            changes = detect_changes(old_plans, new_plans)
            save_plans(new_plans)
            if changes:
                save_changes(changes)
                msg = format_message(changes)
                ok = send_notification(msg, config)
                logger.info(f"Telegram sent: {ok}")
            else:
                logger.info("No changes.")
            logger.info(f"Done. {len(new_plans)} plans, {len(changes)} changes.")
        except Exception as e:
            logger.error(f"Scrape job failed: {e}", exc_info=True)

    init_db()
    config = load_config()
    scheduler = BackgroundScheduler()
    for time_str in config.get("schedule_times", ["10:00", "16:00"]):
        hour, minute = map(int, time_str.split(":"))
        scheduler.add_job(run_scrape_job, "cron", hour=hour, minute=minute)
    scheduler.start()
    logger.info("Flask starting → http://localhost:5000")
    try:
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
    finally:
        scheduler.shutdown()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 6: Smoke test — start Flask manually**

```bash
python app.py
```

Open `http://localhost:5000` in browser. Expected: page loads with "טוען..." heading.
Stop with Ctrl+C.

- [ ] **Step 7: Commit**

```bash
git add app.py templates/index.html tests/test_api.py
git commit -m "feat: Flask API with /api/plans and /api/changes routes"
```

---

## Task 6: Scraper — site inspection

**Files:**
- Create: `scraper.py` (skeleton only — selectors added in Task 7)

> This task discovers the CSS selectors needed before writing scraper code. Use `mcp__Claude_in_Chrome__navigate` and `mcp__Claude_in_Chrome__read_page` (or open headed Playwright) to inspect each site.

- [ ] **Step 1: Inspect Partner DOM structure**

Navigate to `https://www.partner.co.il/n/cellularsale/lobby`, wait for plan cards to render. Record:
- CSS selector for each plan card container
- Selector for plan name text
- Selector for price element
- Selector for GB/data amount
- Selector for extras/benefits list

- [ ] **Step 2: Inspect remaining 4 sites**

Repeat for:
- `https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/`
- `https://www.hotmobile.co.il/saleslobby`
- `https://cellcom.co.il/production/Private/Cellular/`
- `https://019mobile.co.il/חבילות-סלולר/`

Record selectors for each.

- [ ] **Step 3: Create `scraper.py` skeleton**

```python
"""
Playwright scrapers for 5 Israeli cellular carriers.
Uses sync API — no asyncio needed.
All scrape_* functions take a Playwright Page object and return list of plan dicts:
  {"carrier": str, "plan_name": str, "price": int|None,
   "data_gb": int|None, "minutes": str, "extras": list[str]}
"""
from playwright.sync_api import sync_playwright
import re


def _parse_price(text):
    """Extract integer price from string like '₪49' or '49 ש"ח'. Returns None if not found."""
    match = re.search(r"\d+", text.replace(",", ""))
    return int(match.group()) if match else None


def _parse_gb(text):
    """Extract GB integer from string like '60GB' or '60 ג"ב'. Returns None if unlimited."""
    if not text:
        return None
    text_lower = text.lower()
    if "ללא" in text or "unlimit" in text_lower:
        return None
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def scrape_all():
    """Scrape all 5 carriers. Returns flat list of plan dicts."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        plans = []
        for fn in [scrape_partner, scrape_pelephone, scrape_hotmobile,
                   scrape_cellcom, scrape_019]:
            try:
                plans.extend(fn(page))
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Scraper {fn.__name__} failed: {e}")
        browser.close()
    return plans


def scrape_partner(page):
    # TODO after Task 6 site inspection — fill selectors
    pass


def scrape_pelephone(page):
    # TODO after Task 6 site inspection — fill selectors
    pass


def scrape_hotmobile(page):
    # TODO after Task 6 site inspection — fill selectors
    pass


def scrape_cellcom(page):
    # TODO after Task 6 site inspection — fill selectors
    pass


def scrape_019(page):
    # TODO after Task 6 site inspection — fill selectors
    pass
```

- [ ] **Step 4: Commit inspection notes and skeleton**

```bash
git add scraper.py
git commit -m "feat: scraper skeleton + site inspection selectors recorded"
```

---

## Task 7: Scraper — Partner implementation

**Files:**
- Modify: `scraper.py`
- Create: `tests/test_scraper_partner.html` (HTML fixture from live page)
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Save Partner page HTML fixture**

Navigate to `https://www.partner.co.il/n/cellularsale/lobby`, wait for plans to load, save the rendered HTML to `tests/test_scraper_partner.html`.

Using headed Playwright:
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.partner.co.il/n/cellularsale/lobby")
    page.wait_for_load_state("networkidle")
    with open("tests/test_scraper_partner.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    browser.close()
```

Run this as a one-off script: `python -c "exec(open('inspect_partner.py').read())"` (save above as `inspect_partner.py`).

- [ ] **Step 2: Write failing test using the HTML fixture**

Create `tests/test_scraper.py`:

```python
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="module")
def partner_plans():
    """Integration test — hits live Partner site. Skip if no internet."""
    pytest.importorskip("playwright")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        from scraper import scrape_partner
        plans = scrape_partner(page)
        browser.close()
    return plans

@pytest.mark.integration
def test_partner_returns_list(partner_plans):
    assert isinstance(partner_plans, list)

@pytest.mark.integration
def test_partner_plans_have_required_fields(partner_plans):
    assert len(partner_plans) > 0
    for plan in partner_plans:
        assert plan["carrier"] == "partner"
        assert isinstance(plan["plan_name"], str) and plan["plan_name"]
        assert plan["price"] is None or isinstance(plan["price"], int)

@pytest.mark.integration
def test_partner_plans_have_price(partner_plans):
    plans_with_price = [p for p in partner_plans if p["price"] is not None]
    assert len(plans_with_price) > 0

@pytest.mark.integration
def test_partner_plans_have_data_gb_or_unlimited(partner_plans):
    for plan in partner_plans:
        # data_gb is None (unlimited) or a positive int
        assert plan["data_gb"] is None or plan["data_gb"] > 0
```

- [ ] **Step 3: Run integration test to confirm failure**

```bash
pytest tests/test_scraper.py -m integration -v
```

Expected: Tests fail because `scrape_partner` returns `None`.

- [ ] **Step 4: Implement `scrape_partner` in `scraper.py`**

Using selectors found in Task 6 inspection, replace the `scrape_partner` stub:

```python
def scrape_partner(page):
    """
    Selectors discovered during Task 6 inspection.
    Update CARD_SEL, NAME_SEL, PRICE_SEL, GB_SEL, EXTRAS_SEL
    based on actual DOM found during inspection.
    """
    CARD_SEL   = "[data-testid='plan-card']"    # update from inspection
    NAME_SEL   = ".plan-title"                   # update from inspection
    PRICE_SEL  = ".plan-price .price-number"     # update from inspection
    GB_SEL     = ".plan-data .data-amount"       # update from inspection
    EXTRAS_SEL = ".plan-benefits li"             # update from inspection

    page.goto("https://www.partner.co.il/n/cellularsale/lobby", timeout=30000)
    page.wait_for_selector(CARD_SEL, timeout=15000)

    plans = []
    for card in page.query_selector_all(CARD_SEL):
        name_el  = card.query_selector(NAME_SEL)
        price_el = card.query_selector(PRICE_SEL)
        gb_el    = card.query_selector(GB_SEL)
        extras   = [el.inner_text().strip()
                    for el in card.query_selector_all(EXTRAS_SEL)]

        name  = name_el.inner_text().strip()  if name_el  else "לא ידוע"
        price = _parse_price(price_el.inner_text()) if price_el else None
        gb    = _parse_gb(gb_el.inner_text())       if gb_el    else None

        plans.append({
            "carrier": "partner", "plan_name": name,
            "price": price, "data_gb": gb,
            "minutes": "unlimited", "extras": extras
        })
    return plans
```

> **Note:** After running the integration test for the first time, update the selector constants above to match what was actually found in the live HTML fixture.

- [ ] **Step 5: Run integration tests**

```bash
pytest tests/test_scraper.py -m integration -v
```

Expected: 4 tests PASSED. If selectors are wrong, open `tests/test_scraper_partner.html` in browser DevTools to find correct selectors and update.

- [ ] **Step 6: Commit**

```bash
git add scraper.py tests/test_scraper.py tests/test_scraper_partner.html
git commit -m "feat: Partner carrier scraper"
```

---

## Task 8: Scraper — remaining 4 carriers

**Files:**
- Modify: `scraper.py`
- Add to: `tests/test_scraper.py`

For each carrier (Pelephone, Hot Mobile, Cellcom, 019), repeat the same pattern as Task 7:

- [ ] **Step 1: Save HTML fixtures for each carrier**

Run for each URL:
```python
from playwright.sync_api import sync_playwright
carriers = [
    ("pelephone", "https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/"),
    ("hotmobile",  "https://www.hotmobile.co.il/saleslobby"),
    ("cellcom",    "https://cellcom.co.il/production/Private/Cellular/"),
    ("mobile019",  "https://019mobile.co.il/חבילות-סלולר/"),
]
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    for name, url in carriers:
        page.goto(url)
        page.wait_for_load_state("networkidle")
        with open(f"tests/test_scraper_{name}.html", "w", encoding="utf-8") as f:
            f.write(page.content())
    browser.close()
```

Save the above as `inspect_all.py` and run: `python inspect_all.py`

- [ ] **Step 2: Add integration tests for all 4 carriers to `tests/test_scraper.py`**

```python
@pytest.fixture(scope="module")
def pelephone_plans():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        from scraper import scrape_pelephone
        plans = scrape_pelephone(page)
        browser.close()
    return plans

@pytest.mark.integration
def test_pelephone_returns_plans(pelephone_plans):
    assert len(pelephone_plans) > 0
    assert all(p["carrier"] == "pelephone" for p in pelephone_plans)

@pytest.fixture(scope="module")
def hotmobile_plans():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        from scraper import scrape_hotmobile
        plans = scrape_hotmobile(page)
        browser.close()
    return plans

@pytest.mark.integration
def test_hotmobile_returns_plans(hotmobile_plans):
    assert len(hotmobile_plans) > 0
    assert all(p["carrier"] == "hotmobile" for p in hotmobile_plans)

@pytest.fixture(scope="module")
def cellcom_plans():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        from scraper import scrape_cellcom
        plans = scrape_cellcom(page)
        browser.close()
    return plans

@pytest.mark.integration
def test_cellcom_returns_plans(cellcom_plans):
    assert len(cellcom_plans) > 0
    assert all(p["carrier"] == "cellcom" for p in cellcom_plans)

@pytest.fixture(scope="module")
def mobile019_plans():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        from scraper import scrape_019
        plans = scrape_019(page)
        browser.close()
    return plans

@pytest.mark.integration
def test_019_returns_plans(mobile019_plans):
    assert len(mobile019_plans) > 0
    assert all(p["carrier"] == "mobile019" for p in mobile019_plans)

@pytest.mark.integration
def test_scrape_all_returns_all_carriers():
    from scraper import scrape_all
    plans = scrape_all()
    carriers = {p["carrier"] for p in plans}
    assert carriers == {"partner", "pelephone", "hotmobile", "cellcom", "mobile019"}
```

- [ ] **Step 3: Implement `scrape_pelephone` using found selectors**

Follow the same pattern as `scrape_partner` — use selectors found from `tests/test_scraper_pelephone.html`:

```python
def scrape_pelephone(page):
    CARD_SEL   = ".package-card"       # update from inspection
    NAME_SEL   = ".package-name"       # update from inspection
    PRICE_SEL  = ".price-value"        # update from inspection
    GB_SEL     = ".data-amount"        # update from inspection
    EXTRAS_SEL = ".benefit-item"       # update from inspection

    page.goto(
        "https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/",
        timeout=30000
    )
    page.wait_for_selector(CARD_SEL, timeout=15000)
    plans = []
    for card in page.query_selector_all(CARD_SEL):
        name_el  = card.query_selector(NAME_SEL)
        price_el = card.query_selector(PRICE_SEL)
        gb_el    = card.query_selector(GB_SEL)
        extras   = [el.inner_text().strip()
                    for el in card.query_selector_all(EXTRAS_SEL)]
        plans.append({
            "carrier": "pelephone",
            "plan_name": name_el.inner_text().strip() if name_el else "לא ידוע",
            "price": _parse_price(price_el.inner_text()) if price_el else None,
            "data_gb": _parse_gb(gb_el.inner_text()) if gb_el else None,
            "minutes": "unlimited", "extras": extras
        })
    return plans
```

- [ ] **Step 4: Implement `scrape_hotmobile`**

```python
def scrape_hotmobile(page):
    CARD_SEL   = ".plan-item"          # update from inspection
    NAME_SEL   = ".plan-name"          # update from inspection
    PRICE_SEL  = ".plan-price"         # update from inspection
    GB_SEL     = ".plan-data"          # update from inspection
    EXTRAS_SEL = ".plan-benefit"       # update from inspection

    page.goto("https://www.hotmobile.co.il/saleslobby", timeout=30000)
    page.wait_for_selector(CARD_SEL, timeout=15000)
    plans = []
    for card in page.query_selector_all(CARD_SEL):
        name_el  = card.query_selector(NAME_SEL)
        price_el = card.query_selector(PRICE_SEL)
        gb_el    = card.query_selector(GB_SEL)
        extras   = [el.inner_text().strip()
                    for el in card.query_selector_all(EXTRAS_SEL)]
        plans.append({
            "carrier": "hotmobile",
            "plan_name": name_el.inner_text().strip() if name_el else "לא ידוע",
            "price": _parse_price(price_el.inner_text()) if price_el else None,
            "data_gb": _parse_gb(gb_el.inner_text()) if gb_el else None,
            "minutes": "unlimited", "extras": extras
        })
    return plans
```

- [ ] **Step 5: Implement `scrape_cellcom`**

```python
def scrape_cellcom(page):
    CARD_SEL   = ".package-wrapper"    # update from inspection
    NAME_SEL   = ".package-title"      # update from inspection
    PRICE_SEL  = ".package-price"      # update from inspection
    GB_SEL     = ".package-data"       # update from inspection
    EXTRAS_SEL = ".package-feature"    # update from inspection

    page.goto("https://cellcom.co.il/production/Private/Cellular/", timeout=30000)
    page.wait_for_selector(CARD_SEL, timeout=15000)
    plans = []
    for card in page.query_selector_all(CARD_SEL):
        name_el  = card.query_selector(NAME_SEL)
        price_el = card.query_selector(PRICE_SEL)
        gb_el    = card.query_selector(GB_SEL)
        extras   = [el.inner_text().strip()
                    for el in card.query_selector_all(EXTRAS_SEL)]
        plans.append({
            "carrier": "cellcom",
            "plan_name": name_el.inner_text().strip() if name_el else "לא ידוע",
            "price": _parse_price(price_el.inner_text()) if price_el else None,
            "data_gb": _parse_gb(gb_el.inner_text()) if gb_el else None,
            "minutes": "unlimited", "extras": extras
        })
    return plans
```

- [ ] **Step 6: Implement `scrape_019`**

```python
def scrape_019(page):
    CARD_SEL   = ".plan-box"           # update from inspection
    NAME_SEL   = ".plan-box-title"     # update from inspection
    PRICE_SEL  = ".plan-price-number"  # update from inspection
    GB_SEL     = ".plan-gb"            # update from inspection
    EXTRAS_SEL = ".plan-extra-item"    # update from inspection

    page.goto("https://019mobile.co.il/חבילות-סלולר/", timeout=30000)
    page.wait_for_selector(CARD_SEL, timeout=15000)
    plans = []
    for card in page.query_selector_all(CARD_SEL):
        name_el  = card.query_selector(NAME_SEL)
        price_el = card.query_selector(PRICE_SEL)
        gb_el    = card.query_selector(GB_SEL)
        extras   = [el.inner_text().strip()
                    for el in card.query_selector_all(EXTRAS_SEL)]
        plans.append({
            "carrier": "mobile019",
            "plan_name": name_el.inner_text().strip() if name_el else "לא ידוע",
            "price": _parse_price(price_el.inner_text()) if price_el else None,
            "data_gb": _parse_gb(gb_el.inner_text()) if gb_el else None,
            "minutes": "unlimited", "extras": extras
        })
    return plans
```

- [ ] **Step 7: Run all integration tests**

```bash
pytest tests/test_scraper.py -m integration -v
```

Expected: All 9 tests PASSED. Fix any selector mismatches using the saved HTML fixtures.

- [ ] **Step 8: Commit**

```bash
git add scraper.py tests/test_scraper.py tests/test_scraper_*.html
git commit -m "feat: scrapers for all 5 carriers (Pelephone, Hot, Cellcom, 019)"
```

---

## Task 9: Full end-to-end run test

**Files:**
- Modify: `app.py` (add `/api/scrape-now` debug endpoint)

- [ ] **Step 1: Add debug scrape-now endpoint to `app.py`**

Add after the existing routes, inside the `if __name__ == "__main__":` block — actually add it as a regular route for debug purposes:

```python
@app.route("/api/scrape-now")
def api_scrape_now():
    """Manual trigger for testing. Remove before final deployment."""
    from db import save_plans, save_changes
    from change_detector import detect_changes
    from notifier import format_message, send_notification
    import scraper as sc
    try:
        new_plans = sc.scrape_all()
        old_plans = get_plans(db_path=_db_path())
        changes = detect_changes(old_plans, new_plans)
        save_plans(new_plans, db_path=_db_path())
        if changes:
            save_changes(changes, db_path=_db_path())
        return jsonify({"plans": len(new_plans), "changes": len(changes)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 2: Start the app and trigger a manual scrape**

```bash
python app.py
```

In a second terminal:
```bash
curl http://localhost:5000/api/scrape-now
```

Expected response: `{"plans": 20, "changes": 20}` (first run — all plans are "new").

- [ ] **Step 3: Verify plans in DB**

```bash
curl http://localhost:5000/api/plans
```

Expected: JSON array with plans from all 5 carriers.

- [ ] **Step 4: Trigger second scrape — verify no duplicate changes**

```bash
curl http://localhost:5000/api/scrape-now
```

Expected: `{"plans": N, "changes": 0}` (no changes since first scrape).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: manual scrape trigger endpoint for testing"
```

---

## Task 10: Frontend (`templates/index.html`)

**Files:**
- Replace: `templates/index.html`

- [ ] **Step 1: Replace `templates/index.html` with full RTL UI**

```html
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>השוואת חבילות סלולר</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #e0e0e0; direction: rtl; height: 100vh; display: flex; flex-direction: column; }

  /* ── Header ── */
  .header { background: #161b22; border-bottom: 1px solid #30363d; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
  .header h1 { font-size: 18px; color: #f0f6fc; }
  .header .sub { font-size: 12px; color: #8b949e; margin-top: 2px; }
  .update-info { font-size: 11px; color: #8b949e; text-align: left; direction: ltr; }
  .update-info span { color: #3fb950; }

  /* ── Layout ── */
  .main { display: flex; flex: 1; overflow: hidden; }

  /* ── Sidebar ── */
  .sidebar { width: 200px; background: #161b22; border-left: 1px solid #30363d; padding: 16px; overflow-y: auto; flex-shrink: 0; }
  .sidebar-section { margin-bottom: 22px; }
  .sidebar-title { font-size: 10px; font-weight: bold; color: #8b949e; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px; }
  .carrier-btn { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; margin-bottom: 4px; background: transparent; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 13px; cursor: pointer; text-align: right; }
  .carrier-btn.active { background: #1f2d3d; border-color: #388bfd; color: #f0f6fc; }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .dot-partner   { background: #e91e63; }
  .dot-pelephone { background: #2196f3; }
  .dot-hotmobile { background: #ff5722; }
  .dot-cellcom   { background: #4caf50; }
  .dot-mobile019 { background: #9c27b0; }

  .tag-group { display: flex; flex-wrap: wrap; gap: 4px; }
  .tag { padding: 3px 9px; border-radius: 12px; font-size: 11px; background: #21262d; border: 1px solid #30363d; color: #8b949e; cursor: pointer; }
  .tag.active { background: #1f2d3d; border-color: #388bfd; color: #58a6ff; }

  /* ── Content ── */
  .content { flex: 1; overflow-y: auto; padding: 20px; }
  .content-header { margin-bottom: 16px; }
  .content-header h2 { font-size: 16px; color: #f0f6fc; }
  .content-header p { font-size: 12px; color: #8b949e; margin-top: 3px; }

  /* ── Plan cards ── */
  .plans-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
  .plan-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px; position: relative; }
  .plan-card:hover { border-color: #388bfd; }
  .carrier-badge { font-size: 10px; font-weight: bold; padding: 2px 8px; border-radius: 10px; display: inline-block; margin-bottom: 10px; }
  .badge-partner   { color: #e91e63; background: rgba(233,30,99,0.15); }
  .badge-pelephone { color: #2196f3; background: rgba(33,150,243,0.15); }
  .badge-hotmobile { color: #ff5722; background: rgba(255,87,34,0.15); }
  .badge-cellcom   { color: #4caf50; background: rgba(76,175,80,0.15); }
  .badge-mobile019 { color: #9c27b0; background: rgba(156,39,176,0.15); }
  .price { font-size: 28px; font-weight: bold; color: #f0f6fc; }
  .price sup { font-size: 14px; vertical-align: super; }
  .price-note { font-size: 11px; color: #8b949e; margin-bottom: 10px; }
  .details { border-top: 1px solid #21262d; padding-top: 10px; }
  .detail-row { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 12px; }
  .detail-label { color: #8b949e; }
  .detail-value { color: #c9d1d9; font-weight: 500; }
  .extras { margin-top: 8px; font-size: 11px; color: #3fb950; line-height: 1.6; }
  .change-badge { position: absolute; top: 10px; left: 10px; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; }
  .badge-new     { background: #1a4731; color: #3fb950; border: 1px solid #2ea043; }
  .badge-changed { background: #341a00; color: #f0883e; border: 1px solid #d29922; }

  .no-plans { color: #8b949e; padding: 40px; text-align: center; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>📱 השוואת חבילות סלולר</h1>
    <div class="sub">פלאפון · פרטנר · הוט מובייל · סלקום · 019</div>
  </div>
  <div class="update-info" id="updateInfo">טוען...</div>
</div>

<div class="main">
  <div class="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-title">חברה</div>
      <button class="carrier-btn active" data-carrier="all">
        <span class="dot" style="background:#888"></span> כולם
      </button>
      <button class="carrier-btn" data-carrier="partner">
        <span class="dot dot-partner"></span> פרטנר
      </button>
      <button class="carrier-btn" data-carrier="pelephone">
        <span class="dot dot-pelephone"></span> פלאפון
      </button>
      <button class="carrier-btn" data-carrier="hotmobile">
        <span class="dot dot-hotmobile"></span> הוט מובייל
      </button>
      <button class="carrier-btn" data-carrier="cellcom">
        <span class="dot dot-cellcom"></span> סלקום
      </button>
      <button class="carrier-btn" data-carrier="mobile019">
        <span class="dot dot-mobile019"></span> 019
      </button>
    </div>

    <div class="sidebar-section">
      <div class="sidebar-title">גלישה</div>
      <div class="tag-group">
        <span class="tag active" data-gb="all">הכל</span>
        <span class="tag" data-gb="0-50">עד 50GB</span>
        <span class="tag" data-gb="50-100">50–100GB</span>
        <span class="tag" data-gb="100+">100GB+</span>
        <span class="tag" data-gb="unlimited">ללא הגבלה</span>
      </div>
    </div>

    <div class="sidebar-section">
      <div class="sidebar-title">מיון</div>
      <div class="tag-group">
        <span class="tag active" data-sort="price_asc">מחיר ↑</span>
        <span class="tag" data-sort="price_desc">מחיר ↓</span>
        <span class="tag" data-sort="gb_desc">GB ↓</span>
      </div>
    </div>
  </div>

  <div class="content">
    <div class="content-header">
      <h2 id="contentTitle">כל החבילות</h2>
      <p id="contentSubtitle">טוען נתונים...</p>
    </div>
    <div class="plans-grid" id="plansGrid"></div>
  </div>
</div>

<script>
const CARRIER_LABELS = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל',
  cellcom: 'סלקום', mobile019: '019'
};

let allPlans = [];
let recentChanges = new Set(); // "carrier|plan_name" changed within 24h
let state = { carrier: 'all', gb: 'all', sort: 'price_asc' };

async function loadData() {
  const [plans, changes] = await Promise.all([
    fetch('/api/plans').then(r => r.json()),
    fetch('/api/changes?limit=50').then(r => r.json())
  ]);
  allPlans = plans;

  const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  recentChanges = new Set(
    changes
      .filter(c => c.changed_at > cutoff)
      .map(c => `${c.carrier}|${c.plan_name}`)
  );

  const latestTime = plans.length
    ? plans.map(p => p.scraped_at).sort().at(-1).slice(11, 16)
    : '—';
  document.getElementById('updateInfo').innerHTML =
    `עדכון אחרון: <span>${latestTime}</span>`;

  render();
}

function getChangeBadgeType(plan) {
  const key = `${plan.carrier}|${plan.plan_name}`;
  if (!recentChanges.has(key)) return null;
  const ch = /* check from changes array */ null; // simplified: show "changed"
  return 'changed';
}

function filterAndSort(plans) {
  let result = plans;
  if (state.carrier !== 'all') result = result.filter(p => p.carrier === state.carrier);
  if (state.gb === '0-50')      result = result.filter(p => p.data_gb !== null && p.data_gb <= 50);
  if (state.gb === '50-100')    result = result.filter(p => p.data_gb !== null && p.data_gb > 50 && p.data_gb <= 100);
  if (state.gb === '100+')      result = result.filter(p => p.data_gb !== null && p.data_gb > 100);
  if (state.gb === 'unlimited') result = result.filter(p => p.data_gb === null);
  if (state.sort === 'price_asc')  result.sort((a, b) => (a.price ?? 999) - (b.price ?? 999));
  if (state.sort === 'price_desc') result.sort((a, b) => (b.price ?? 0) - (a.price ?? 0));
  if (state.sort === 'gb_desc')    result.sort((a, b) => (b.data_gb ?? 9999) - (a.data_gb ?? 9999));
  return result;
}

function renderCard(plan) {
  const key = `${plan.carrier}|${plan.plan_name}`;
  const isChanged = recentChanges.has(key);
  const badge = isChanged
    ? `<span class="change-badge badge-changed">שינוי מחיר</span>` : '';
  const extras = plan.extras?.length
    ? `<div class="extras">✦ ${plan.extras.join(' ✦ ')}</div>` : '';
  const gb = plan.data_gb === null ? 'ללא הגבלה' : `${plan.data_gb}GB`;
  const price = plan.price !== null ? `<sup>₪</sup>${plan.price}` : '—';

  return `
    <div class="plan-card">
      ${badge}
      <span class="carrier-badge badge-${plan.carrier}">${CARRIER_LABELS[plan.carrier] || plan.carrier}</span>
      <div class="price">${price}</div>
      <div class="price-note">לחודש | מקוון</div>
      <div class="details">
        <div class="detail-row"><span class="detail-label">גלישה</span><span class="detail-value">${gb}</span></div>
        <div class="detail-row"><span class="detail-label">שיחות</span><span class="detail-value">${plan.minutes === 'unlimited' ? 'ללא הגבלה' : plan.minutes || '—'}</span></div>
        <div class="detail-row"><span class="detail-label">תוכנית</span><span class="detail-value">${plan.plan_name}</span></div>
      </div>
      ${extras}
    </div>`;
}

function render() {
  const filtered = filterAndSort(allPlans);
  const grid = document.getElementById('plansGrid');
  const title = document.getElementById('contentTitle');
  const subtitle = document.getElementById('contentSubtitle');

  const carrierLabel = state.carrier === 'all' ? 'כל החבילות' : CARRIER_LABELS[state.carrier];
  title.textContent = carrierLabel;
  subtitle.textContent = `${filtered.length} חבילות`;

  if (!filtered.length) {
    grid.innerHTML = '<div class="no-plans">אין חבילות תואמות את הסינון</div>';
    return;
  }
  grid.innerHTML = filtered.map(renderCard).join('');
}

// Sidebar interactions
document.querySelectorAll('.carrier-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.carrier-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.carrier = btn.dataset.carrier;
    render();
  });
});

document.querySelectorAll('.tag[data-gb]').forEach(tag => {
  tag.addEventListener('click', () => {
    document.querySelectorAll('.tag[data-gb]').forEach(t => t.classList.remove('active'));
    tag.classList.add('active');
    state.gb = tag.dataset.gb;
    render();
  });
});

document.querySelectorAll('.tag[data-sort]').forEach(tag => {
  tag.addEventListener('click', () => {
    document.querySelectorAll('.tag[data-sort]').forEach(t => t.classList.remove('active'));
    tag.classList.add('active');
    state.sort = tag.dataset.sort;
    render();
  });
});

loadData();
</script>
</body>
</html>
```

- [ ] **Step 2: Reload `http://localhost:5000` and verify UI**

Start `python app.py`, open browser. Verify:
- Plans grid shows cards from all 5 carriers
- Carrier filter buttons work (click "פרטנר" → shows only Partner plans)
- GB filter works
- Sort by price works
- "שינוי מחיר" badge appears on plans changed within 24h

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: full RTL Hebrew dark UI with sidebar filters and plan cards"
```

---

## Task 11: Telegram bot setup + Windows Task Scheduler

**Files:**
- Modify: `config.json` (fill in real values)

- [ ] **Step 1: Create Telegram bot**

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`
3. Enter bot name (e.g., `השוואת סלולר`)
4. Enter username (e.g., `cellular_compare_bot`)
5. Copy the **API Token** (format: `123456789:ABCdef...`)

- [ ] **Step 2: Get your Chat ID**

1. Search for `@userinfobot` in Telegram
2. Send `/start`
3. Copy the **Id** number shown (e.g., `123456789`)

- [ ] **Step 3: Fill in `config.json`**

```json
{
  "telegram_bot_token": "123456789:ABCdef...",
  "telegram_chat_id": "123456789",
  "schedule_times": ["10:00", "16:00"],
  "notify_on_changes_only": true
}
```

- [ ] **Step 4: Test Telegram notification manually**

```bash
python -c "
import json
from notifier import format_message, send_notification
config = json.load(open('config.json'))
test_changes = [{'carrier': 'partner', 'plan_name': '60GB', 'change_type': 'price_change', 'old_val': 59, 'new_val': 49}]
msg = format_message(test_changes)
ok = send_notification(msg, config)
print('Sent:', ok)
"
```

Expected: Telegram message received on your phone. Console: `Sent: True`

- [ ] **Step 5: Set up Windows Task Scheduler**

Open PowerShell as Administrator and run:

```powershell
$python = (Get-Command python).Source
$script = "D:\השוואת MASS MARKET\app.py"
$action = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory "D:\השוואת MASS MARKET"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "CellularComparison" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
```

- [ ] **Step 6: Verify Task Scheduler entry**

```powershell
Get-ScheduledTask -TaskName "CellularComparison" | Select-Object TaskName, State
```

Expected: `CellularComparison   Ready`

- [ ] **Step 7: Test a manual scrape via the debug endpoint**

```bash
curl http://localhost:5000/api/scrape-now
```

- [ ] **Step 8: Final commit**

```bash
git add config.json
git commit -m "feat: Telegram bot configured + Windows Task Scheduler setup complete"
```

---

## Run All Tests

```bash
pytest tests/test_db.py tests/test_change_detector.py tests/test_notifier.py tests/test_api.py -v
```

Expected: All unit tests PASSED (integration tests excluded — run separately with `-m integration`).

---

## Verification Checklist

- [ ] `python app.py` starts without errors
- [ ] `http://localhost:5000` loads Hebrew RTL UI
- [ ] Sidebar carrier filter shows/hides plans correctly
- [ ] GB and sort filters work
- [ ] `GET /api/plans` returns JSON with all 5 carriers
- [ ] `GET /api/changes` returns JSON array
- [ ] Manual Telegram test message received on phone
- [ ] `GET /api/scrape-now` returns `{"plans": N, "changes": 0}` on second run
- [ ] Windows Task Scheduler entry visible and enabled
