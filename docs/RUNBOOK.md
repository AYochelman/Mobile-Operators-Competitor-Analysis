# MOCA Operator Runbook

מדריך תפעולי לכשלים נפוצים. מיועד לאלון (או לכל מי שיתחזק את MOCA בעתיד).

> **חשוב:** אם משהו לא עובד, **לא תמיד הפתרון הוא restart**. קרא את הסעיף הרלוונטי ובדוק קודם **למה** המערכת קרסה — אחרת תפספס את הסיבה האמיתית והבעיה תחזור.

## תוכן עניינים

1. [Architecture Quick Reference](#architecture-quick-reference)
2. [תרחיש: Flask לא מגיב](#flask-not-responding)
3. [תרחיש: ngrok URL השתנה](#ngrok-url-changed)
4. [תרחיש: Supabase suspended (אחרי חופשה ארוכה)](#supabase-suspended)
5. [תרחיש: סקרייפר אחד נכשל באופן עקבי](#scraper-failing)
6. [תרחיש: Telegram bot לא שולח התראות](#telegram-not-sending)
7. [תרחיש: Email דו"ח יומי לא נשלח (SendGrid)](#sendgrid-not-sending)
8. [תרחיש: SQLite "database is locked"](#sqlite-locked)
9. [תרחיש: Disk space נגמר](#disk-full)
10. [תרחיש: ה-PC מת — Disaster Recovery](#disaster-recovery)
11. [תרחיש: VAPID keys השתנו והמשתמשים לא מקבלים push](#vapid-changed)
12. [תרחיש: התראה כפולה על אותו שינוי](#duplicate-notifications)
13. [סיבוב סודות שגרתי](#secret-rotation)
14. [Backup test (פעם ברבעון)](#backup-test)

---

## Architecture Quick Reference

```
[Netlify (frontend)] ──https──► [ngrok tunnel] ──http──► [Flask :5000 on PC]
                                                              │
                                                              ├─► SQLite data/plans.db
                                                              ├─► APScheduler → scrape jobs
                                                              ├─► Telegram / WhatsApp / Web Push / SendGrid
                                                              └─► Supabase (auth + workspaces)
```

- Frontend ב-`https://lucent-kulfi-f037ad.netlify.app`
- ngrok URL: `https://terra-nonrestrained-overpiteously.ngrok-free.dev` (static-paid)
- Flask על המחשב של אלון, port 5000, `127.0.0.1` או `0.0.0.0` בהתאם ל-`FLASK_HOST`
- Watchdog: `scripts/flask_watchdog.bat` ו-`scripts/vite_watchdog.bat`
- Logs: `logs/flask.log` (rotating), `scripts/flask_watchdog.log`, `scripts/backup.log`

---

<a name="flask-not-responding"></a>
## תרחיש: Flask לא מגיב

**סימנים:** הדפסה ב-Netlify מחזירה network errors. `https://terra-...ngrok-free.dev/api/plans` מחזיר 502 או timeout.

### דיאגנוזה

```cmd
REM 1. בדוק אם Flask רץ
wmic process where "name='python.exe'" get processid,commandline | findstr app.py

REM 2. בדוק אם הוא מאזין על port 5000
netstat -ano | findstr :5000

REM 3. בדוק logs האחרונים
type logs\flask.log | tail -50
type scripts\flask_watchdog.log | tail -20
```

### אבחון לפי תוצאה

| מה ראית | סיבה סבירה | תיקון |
|---|---|---|
| תהליך python קיים, port 5000 בשימוש | Flask חי אבל לא מגיב — תקוע | `wmic process where processid=<PID> delete` והwatchdog יחזיר אותו |
| תהליך python לא קיים | Flask קרס | בדוק `flask.log` לסיבה. אם רואה `ImportError` — הריץ `pip install -r requirements.txt` |
| תהליך פעיל אבל ב-loop מהיר ב-watchdog | crash loop | פתח את `flask.log` — תראה stack trace חוזר. תקן את הסיבה לפני restart |
| הכל נראה תקין אבל ngrok נופל | ngrok tunnel לא חי | ראה [ngrok URL השתנה](#ngrok-url-changed) |

### Hard restart (אם הכל נכשל)

```cmd
REM הרוג כל python ותן ל-Task Scheduler לעלות מחדש
wmic process where "name='python.exe' and commandline like '%%app.py%%'" delete
REM (Task Scheduler "CellularComparison" יחזיר את Flask תוך 15 שניות)
```

---

<a name="ngrok-url-changed"></a>
## תרחיש: ngrok URL השתנה

**סימנים:** הקוד הקיים ב-Netlify מנסה להתחבר ל-`terra-nonrestrained-overpiteously.ngrok-free.dev` ומקבל connection refused.

**מתי זה קורה:**
- חידוש אקראי של ngrok (לא צפוי בתוכנית paid עם static domain)
- שינוי תוכנית (free → paid או הפך)
- ngrok account suspension

### תיקון

1. רשום את ה-URL החדש: https://dashboard.ngrok.com/domains
2. עדכן ב-3 מקומות:
   - **Netlify:** Environment Variables → `VITE_API_URL` → ערך חדש → **Redeploy**
   - **Flask config (אם משתמש):** `app.py:ALLOWED_ORIGINS` או env var `ALLOWED_ORIGINS`
   - **Watchdog (אם hardcoded):** `scripts/flask_watchdog.bat` (לא צריך אם הקוד יציב)
3. בנה את ה-frontend מחדש:
   ```cmd
   cd mass-market-app
   npm run build
   REM גרור dist/ ל-Netlify ידנית, או:
   netlify deploy --prod --dir=dist
   ```

---

<a name="supabase-suspended"></a>
## תרחיש: Supabase suspended (אחרי חופשה ארוכה)

**סימנים:** משתמש לא יכול להיכנס. Console מציג `Auth API returned 503` או דומה.

**סיבה:** Supabase Free tier משעה פרויקטים אחרי 7 ימים בלי פעילות.

### תיקון

1. https://app.supabase.com/projects → בחר את הפרויקט (`gmfefvjdmgzluwffzrzj`)
2. אם רואה "Project paused" → לחץ "Restore project" / "Unpause"
3. שחזור לוקח 1-3 דקות
4. בדוק שלוגין עובד: `https://lucent-kulfi-f037ad.netlify.app/login`

### מניעה

הוסף scheduled task ב-Windows שיעשה ping ל-Supabase פעם בכמה ימים:

```cmd
REM scripts/keep_supabase_alive.bat
curl -s -o nul -X GET "https://gmfefvjdmgzluwffzrzj.supabase.co/auth/v1/health" -H "apikey: <ANON_KEY>"
```

קבע ב-Task Scheduler: `daily 03:00`. זה ימנע השעיה.

---

<a name="scraper-failing"></a>
## תרחיש: סקרייפר אחד נכשל באופן עקבי

**סימנים:** ב-Dashboard, חבילות של ספק מסויים (למשל פלאפון) לא מתעדכנות כבר ימים. או שכל החבילות שלו "נעלמות" פתאום והתראות "removed_plan" מתפרצות.

### דיאגנוזה

```cmd
REM הרץ סקרייפ ידני עם output מלא
python -c "from scraper import scrape_pelephone; from playwright.sync_api import sync_playwright; \
  with sync_playwright() as p: \
    b = p.chromium.launch(headless=True); \
    page = b.new_page(); \
    plans = scrape_pelephone(page); \
    print(f'Got {len(plans)} plans'); \
    b.close()"
```

**אם 0 plans:** הסלקטור שבור (האתר השתנה). פתח את ה-URL בדפדפן רגיל ובדוק:
- האם האתר עלה? (יכול להיות maintenance)
- האם המבנה השתנה? (`devtools` → השווה ל-`scraper.py` selector)

### תיקון לפי סיבה

| בעיה | פעולה |
|---|---|
| האתר במצב maintenance | חכה. ה-`_delete_stale_carrier_rows` threshold (50%) ימנע מחיקה שגויה |
| WAF/Cloudflare blocking | התווסף stealth ב-`_banner_*_stealth` — הרחב לסקרייפר הראשי או הוסף delay |
| Selector השתנה | פתח devtools, מצא selector חדש, עדכן ב-`scraper.py` ובדוק עם הפקודה למעלה |
| Anti-bot CAPTCHA | במצב הזה אי אפשר לסקרייפ — דווח לאלון. לא לנסות לעקוף |

### לבדוק שהסקרייפר תקני אחרי תיקון

```cmd
REM הרץ scrape ידני דרך API (דורש API key)
curl -X GET "https://terra-...ngrok-free.dev/api/scrape-all-now" -H "X-API-Key: <KEY>"
REM או דרך הUI: SettingsPage → "Scrape now"
```

---

<a name="telegram-not-sending"></a>
## תרחיש: Telegram bot לא שולח התראות

**סימנים:** סקרייפ עבר, יש changes ב-DB, אבל אין התראה ב-Telegram.

### דיאגנוזה

```cmd
REM בדוק שה-token תקני
curl -s "https://api.telegram.org/bot<TOKEN>/getMe" | python -m json.tool
```

תקני: מחזיר `{"ok": true, "result": {...}}`. שגוי: `{"ok": false, "error_code": 401}`.

### תיקונים נפוצים

1. **Token פג / השתנה:**
   - https://t.me/BotFather → `/mybots` → בחר את MOCA → API Token → רענן
   - עדכן ב-`config.json` תחת `telegram_bot_token`
   - Restart Flask

2. **chat_id שגוי:**
   - שלח הודעה לבוט ב-Telegram
   - `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"` → מצא את `chat.id` בתוצאה
   - עדכן ב-`config.json` תחת `telegram_chat_id`

3. **Rate limited (חריגה מ-30 הודעות/שניה לבוט):**
   - מ-2026-05-01 יש retry עם backoff. אם עדיין נכשל — דווח לAlon וחפש logs ל-"telegram"

4. **Token format שגוי:**
   - מ-2026-05-01 `send_notification` בודק `\d+:[\w-]{30,}`. אם הtoken לא תואם — לוג יראה "invalid shape"

---

<a name="sendgrid-not-sending"></a>
## תרחיש: Email דו"ח יומי לא נשלח (SendGrid)

**סימנים:** דו"ח Excel היומי לא הגיע לבוקר.

### דיאגנוזה

1. https://app.sendgrid.com/email_activity — בדוק activity ב-24 שעות אחרונות
2. אם יש "Bounce" / "Block" → בדוק הסיבה (כתובת לא תקפה, spam filter, וכו')
3. אם אין כל activity → הבעיה אצלנו, לא אצל SendGrid

### תיקונים נפוצים

| בעיה | פעולה |
|---|---|
| Free tier quota (100/יום) חרגה | חכה ליום הבא, או שדרג. בדוק ב-SendGrid → Statistics |
| API key לא תקף | https://app.sendgrid.com/settings/api_keys → צור חדש → עדכן `config.json:sendgrid_api_key` |
| Sender domain לא verified | https://app.sendgrid.com/settings/sender_auth → ודא שה-domain מאומת |
| Flask לא הצליח לפתוח את הקובץ Excel | בדוק `logs/flask.log` ל-stack trace של `excel_report.py` |

---

<a name="sqlite-locked"></a>
## תרחיש: SQLite "database is locked"

**סימנים:** API מחזיר 500 errors, log מציג `sqlite3.OperationalError: database is locked`.

מ-2026-05-01 הפעלנו WAL mode + busy_timeout=5000ms, אז זה אמור להיות נדיר. אם זה קורה:

### דיאגנוזה

```cmd
REM בדוק אם יש process פתוח שתופס את ה-DB
python -c "import sqlite3; c = sqlite3.connect('data/plans.db'); c.execute('PRAGMA quick_check'); print('OK')"
```

### תיקון

1. **אם Flask + scrape job רצים בו-זמנית:** WAL אמור לפתור. אם לא — בדוק שכבר אין גרסה ישנה של `db.py` שלא משתמשת ב-WAL
2. **ה-DB מקולקל (rare):**
   ```cmd
   sqlite3 data/plans.db "PRAGMA integrity_check"
   ```
   אם החזיר משהו חוץ מ-`ok` → שחזר מ-backup (`scripts/backup_to_drive.ps1` או Google Drive)
3. **WAL file הענק (data/plans.db-wal > 50MB):**
   ```cmd
   sqlite3 data/plans.db "PRAGMA wal_checkpoint(TRUNCATE)"
   ```

---

<a name="disk-full"></a>
## תרחיש: Disk space נגמר

**סימנים:** Flask משליך errors, `flask.log` מציג `OSError: [Errno 28] No space left on device` או דומה (Windows: error 112).

### תיקון מיידי

```cmd
REM נקה logs ישנים
del /Q scripts\*.log
del /Q logs\*.log.*

REM נקה Vite cache
rd /S /Q mass-market-app\node_modules\.vite

REM בדוק את הגודל של ה-DB
dir data\plans.db

REM בדוק backups ישנים שלא נמחקו
dir scripts\backups\
```

### מניעה ארוכת-טווח

מ-2026-05-01 יש retention יומית: `audit_log` עד 180 ימים, `*_changes` עד 365 ימים. אם ה-DB גדול במיוחד:

```cmd
python -c "from db import prune_audit_log, prune_changes; print(prune_audit_log(days=90), prune_changes(days=180))"
```

---

<a name="disaster-recovery"></a>
## תרחיש: ה-PC מת — Disaster Recovery

**סימנים:** המחשב לא עולה, או disk failure.

### זמני RPO/RTO נוכחיים
- **RPO:** עד 24 שעות (backup יומי ב-`scripts/backup_to_drive.ps1`)
- **RTO:** 4-12 שעות (ידני, לא containerized)

### צעדי DR

1. **קבל מכונה חדשה** (Windows 10+)
2. **התקן python 3.13** (https://python.org → 64-bit installer)
3. **התקן Node 20** (https://nodejs.org)
4. **התקן Git** (https://git-scm.com)
5. **Clone את הריפו:**
   ```cmd
   cd C:\
   git clone https://github.com/AYochelman/Mobile-Operators-Competitor-Analysis.git
   ren Mobile-Operators-Competitor-Analysis "השוואת MASS MARKET"
   cd "השוואת MASS MARKET"
   ```
6. **התקן deps:**
   ```cmd
   pip install -r requirements.txt
   playwright install chromium
   cd mass-market-app
   npm install --legacy-peer-deps
   ```
7. **שחזר config.json מ-Google Drive:**
   - https://drive.google.com → תיקיית `MOCA-backups`
   - הורד את ה-zip האחרון
   - חלץ את `config.json` ו-`data/plans.db` למיקומים המקוריים
8. **שחזר Telegram session (אופציונלי, רק אם רוצה לסקרייפ resellers):**
   - אין session backup ב-Drive → חייב login דו-שלבי מחדש: `python telegram_resellers.py login_request`
9. **הפעל:**
   ```cmd
   python app.py
   ```
   ובמקביל:
   ```cmd
   cd mass-market-app
   npm run dev
   ```
10. **התקן ngrok ועדכן authtoken:**
    ```cmd
    REM Microsoft Store → "ngrok"
    ngrok config add-authtoken <TOKEN_FROM_DASHBOARD>
    ngrok http --domain=terra-nonrestrained-overpiteously.ngrok-free.dev 5000
    ```
11. **אם יש Dockerfile (כשיתווסף):**
    ```cmd
    docker compose up -d
    ```
    שלבים 5-10 מתאחדים ל-10 דקות.

### קיצורי זמן

- אם יש Dockerfile + docker-compose — RTO יורד ל-30 דקות
- אם יש backup דרך rsync/restic ל-S3 — RPO יורד ל-15 דקות
- אם יש cloud-hosted alternative (Fly.io / Railway) — אפס downtime

---

<a name="vapid-changed"></a>
## תרחיש: VAPID keys השתנו והמשתמשים לא מקבלים push

**סימנים:** משתמשים מדווחים שהפסיקו לקבל התראות push. log מציג `WebPushException: 410 Gone` חוזר על עצמו.

**סיבה:** VAPID keys ב-`config.json` הוחלפו (במכוון או בטעות), אבל המנויים הקיימים נחתמו עם הישנים.

### תיקון

ה-VAPID keys צריכים להיות קבועים. הם מסתנכרנים בעזרת `_ensure_vapid_keys` ב-app.py, אבל **רק אם** הם חסרים. אם הם השתנו אחרי הראשון:

```cmd
REM אופציה 1 (פשוטה): הזחר את ה-keys הישנים מ-backup של config.json
REM אופציה 2: scrub את כל המנויים כי הם בלי-תועלת ממילא
python -c "from db import _connect; c = _connect(); c.execute('DELETE FROM push_subscriptions'); c.commit(); print('cleared')"
```

המשתמשים יצטרכו ללחוץ "אפשר התראות" שוב באתר (במכשיר שלהם).

---

<a name="duplicate-notifications"></a>
## תרחיש: התראה כפולה על אותו שינוי

**סימנים:** קיבלת אותה התראה ב-Telegram פעמיים תוך כמה דקות.

### סיבות אפשריות

1. **שני סקרייפ jobs רצו בו-זמנית** (08:00 שני tasks או manual + scheduled): 
   - מ-2026-05-01 יש `max_instances=1` ב-APScheduler אז זה לא צריך לקרות לשני scheduled jobs
   - אבל manual scrape (`/api/scrape-all-now`) יכול לרוץ במקביל ל-scheduled job
2. **`filter_already_notified` race condition:** שני סקרייפים רצים במקביל, שניהם רואים "לא דווח", שניהם שומרים. 
   - מ-2026-05-01 יש פחות סיכוי בזכות `max_instances=1`
3. **Cache stuck:** Flask ראה את אותו change אחרי restart

### תיקון

```cmd
REM הצג שינויים ב-24 שעות אחרונות לפי תאריך
python -c "from db import _connect; c = _connect(); rows = c.execute('SELECT carrier, plan_name, change_type, COUNT(*) c FROM changes WHERE changed_at >= datetime(\"now\", \"-1 day\") GROUP BY carrier, plan_name, change_type HAVING c > 1').fetchall(); print(rows)"
```

אם יש דופליקטים — מחק את הישן יותר:

```cmd
sqlite3 data/plans.db "DELETE FROM changes WHERE id NOT IN (SELECT MAX(id) FROM changes GROUP BY carrier, plan_name, change_type, substr(changed_at, 1, 13))"
```

---

<a name="secret-rotation"></a>
## סיבוב סודות שגרתי (כל 90 ימים)

| סוד | איפה | איך לסבב |
|---|---|---|
| `api_key` (Flask) | `config.json` | מחק את השדה → restart → Flask יצור חדש אוטומטית. עדכן ב-Netlify env `VITE_API_KEY` |
| `server_admin_key` | `config.json` | אותו דבר. עדכן בכל מקום שמשתמש ב-`X-Server-Admin-Key` header |
| `ngrok_authtoken` | `config.json` ו-`ngrok config` | https://dashboard.ngrok.com/get-started/your-authtoken → Reset → `ngrok config add-authtoken <NEW>` |
| `telegram_bot_token` | `config.json` | https://t.me/BotFather → `/revoke` → `/token` חדש |
| `sendgrid_api_key` | `config.json` | https://app.sendgrid.com/settings/api_keys → Create → Delete הישן |
| `supabase_anon_key` | Netlify env vars | https://app.supabase.com → Settings → API → "Reset anon key" (זהירות!) |
| `supabase_db_password` | `config.json` | https://app.supabase.com → Settings → Database → "Reset database password" |
| **2FA recovery codes** | מחוץ למחשב | https://dashboard.ngrok.com → User Settings → Recovery Codes → Regenerate. שמור ב-1Password |

**Reminder:** הוסף ב-Google Calendar event חוזר כל 90 יום: "Rotate MOCA secrets — see docs/RUNBOOK.md".

---

<a name="backup-test"></a>
## Backup test (פעם ברבעון)

**למה:** backup שלא נבדק = אין backup. גרסת DR לא מאומתת = לא יודעים אם יעבוד באמת.

### צעדים

1. הורד את ה-zip האחרון מ-Google Drive (`MOCA-backups/YYYY-MM-DD.zip`)
2. צור תיקייה זמנית ב-`C:\Temp\moca-restore`
3. חלץ לשם
4. ודא שיש: `config.json`, `data/plans.db`, `data/banners/*.png`
5. נסה לפתוח את ה-DB:
   ```cmd
   sqlite3 C:\Temp\moca-restore\data\plans.db "SELECT COUNT(*) FROM plans"
   ```
   צפי: > 100
6. ודא שאין corruption:
   ```cmd
   sqlite3 C:\Temp\moca-restore\data\plans.db "PRAGMA integrity_check"
   ```
   צפי: `ok`
7. בדוק שכל הצבירים יש לפחות שורה אחת:
   ```cmd
   sqlite3 C:\Temp\moca-restore\data\plans.db "SELECT carrier, COUNT(*) FROM plans GROUP BY carrier"
   ```
8. נקה: `rd /S /Q C:\Temp\moca-restore`

**אם אחד מ-1-7 נכשל:** ה-backup שבור. בדוק `scripts/backup_to_drive.ps1` ו-`scripts/backup_health_check.ps1`. ייתכן שצריך לתקן את הסקריפט וליצור backup חדש.

---

## Quick command reference

```cmd
REM Restart Flask
wmic process where "name='python.exe' and commandline like '%%app.py%%'" delete

REM Tail logs
type logs\flask.log | tail -50

REM Trigger scrape now
curl -X GET "http://localhost:5000/api/scrape-all-now" -H "X-API-Key: <KEY>"

REM DB integrity
sqlite3 data\plans.db "PRAGMA integrity_check"

REM Force WAL checkpoint
sqlite3 data\plans.db "PRAGMA wal_checkpoint(TRUNCATE)"

REM Run unit tests
pytest tests/ -m "not integration" -v

REM Build frontend
cd mass-market-app && npm run build

REM Check ngrok status
curl http://localhost:4040/api/tunnels
```

---

**עדכון אחרון:** 2026-05-01 (audit cycle)
**מתחזק:** Alon Yochelman
