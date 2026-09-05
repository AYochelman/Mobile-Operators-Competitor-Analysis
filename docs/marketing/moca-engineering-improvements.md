# MOCA — שיפורי הנדסה, איכות ותפעול

**תאריך:** אפריל 2026
**מסמך משלים** ל־`moca-future-developments.md` (מפת דרכים מוצרית).
בעוד שהמסמך האחר עוסק ב**מה** נבנה, מסמך זה עוסק ב**איך** נחזיק את מה שכבר נבנה — באמינות, באבטחה ובמהירות פיתוח.

---

## 1. ניקוי הריפו והקטנת ה־blast radius

### המצב כיום
שורש הפרויקט מכיל למעלה מ־30 קבצי דיבוג זמניים (`inspect_*.py`, `*_inspect_out.txt`), קובץ `ngrok.exe` בגודל 32MB וגיבוי `.ngrok.exe.old` נוסף בגודל 32MB, לוגים גדולים (`flask_log.txt` ~250KB, `vite_log.txt` ~64KB), ודאמפים שלמים של תשובות API (`voye_raw_data.json` ~2.4MB, `cellcom_abroad_api_result.json` ~175KB, ועוד).

### השיפור
- העברת כל קבצי ה־`inspect_*` לתיקיית `scripts/exploration/` (אם בכלל נחוצים), והוספתם ל־`.gitignore`
- הסרת הבינארים של ngrok והפניית ה־README להתקנה עצמאית
- הוספת `*.log`, `data/banners/`, `data/archive/`, `*_raw_data.json` ל־`.gitignore`
- הרצת `git filter-repo` חד־פעמית להקטנת היסטוריית ה־`.git` (כיום ~51MB)

### ערך
זמן clone מהיר יותר, היסטוריה נקייה לסקרי קוד, וסיכון נמוך יותר שמפתח יסכר בטעות סוד או בינארי.

---

## 2. CI/CD מלא ב־GitHub Actions

### המצב כיום
אין תיקיית `.github/`. הבדיקות (`pytest`, `eslint`, `npm run build`) רצות רק ידנית מקומית. הפריסה ל־Netlify מתבצעת על ידי גרירת `dist/` ידנית.

### השיפור
שלוש workflows:
1. **`ci.yml`** — בכל PR: `pytest -v` (Backend) + `npm run lint` + `npm run build` (Frontend). חוסם merge ב־failure
2. **`security.yml`** — `pip-audit`, `npm audit`, סריקת secrets (`gitleaks`), Dependabot/Renovate ל־updates שבועיים
3. **`deploy.yml`** — בכל push ל־`main`: build ופריסה אוטומטית ל־Netlify דרך CLI/API

### ערך
מונע regressions, תופס CVEs לפני production, מבטל את הצורך בגרירה ידנית של `dist`.

---

## 3. פירוק `scraper.py` ו־`app.py` לחבילות

### המצב כיום
- `scraper.py` ~7,000 שורות, 81 פונקציות מסוג `def`, 40+ scrapers שונים
- `app.py` ~3,180 שורות, 63 endpoints
- `templates/index.html` 2,300+ שורות (legacy שכבר מוחלף ב־React)

### השיפור
```
scrapers/
  __init__.py         # ייצוא מאוחד + רישום (registry)
  base.py             # _dismiss_popups, _make_global_plan, helpers
  domestic/
    pelephone.py
    cellcom.py
    ...
  abroad/
    ...
  global/
    saily.py          # כל scraper בקובץ משלו, < 300 שורות
    holafly.py
    ...
  banners.py
  news.py

api/
  __init__.py         # create_app() factory
  plans.py            # blueprint
  scrape.py           # blueprint עם @require_api_key
  push.py
  chat.py
  workspaces.py
```

הסרת `templates/index.html` לחלוטין (ה־React app מכסה הכל).

### ערך
- ניתן לבדוק כל scraper בנפרד (`pytest tests/scrapers/test_saily.py`)
- שינוי באתר של Saily לא דורש קריאה של 7,000 שורות
- ירידה דרסטית בקונפליקטים של git כשמספר אנשים נוגעים בקוד
- הסרת ה־legacy template חוסכת תחזוקה כפולה של אותו דשבורד

---

## 4. החלפת `local Flask + ngrok` ב־hosting אמיתי

### המצב כיום
שרת Flask רץ על מכונת Windows מקומית, נחשף לעולם דרך ngrok. תלוי ב־Task Scheduler שמפעיל `python app.py` ב־logon. נצפו בעיות clock drift עם JWT (commit `1ed83cd: JWT leeway 4h for Windows clock drift`).

### השיפור
- מעבר ל־Fly.io / Railway / Render עם תמונת Docker
- `Dockerfile` ל־Flask + `playwright install`, `docker-compose.yml` להרצה מקומית
- `gunicorn` כבר ב־requirements — ניתן לשרת בייצור
- ה־scheduler עובר ל־Worker process נפרד (ראו סעיף 6)
- ngrok נשאר ככלי dev בלבד

### ערך
זמינות 24/7 ללא תלות ב־PC, ללא clock drift, פריסה אטומית עם rollback, וכתובת קבועה במקום ngrok URL מתחלף.

---

## 5. השלמת המעבר ל־PostgreSQL

### המצב כיום
ה־`requirements.txt` כבר כולל `psycopg2-binary` אבל `db.py` עדיין מבוסס SQLite. ה־CLAUDE.md מתעד את הסכמה כ־SQLite. WAL ב־SQLite שביר תחת ריבוי writers (scrape ב־10:00 + alerts + push בו־זמנית).

### השיפור
- שכבת DAL מאוחדת (`db.py`) שתומכת בשני הנהגים דרך SQLAlchemy Core / `databases`
- מיגרציות מסודרות עם Alembic (כיום `docs/sql/001_workspaces.sql` ידני)
- חיבור ל־Neon / Supabase Postgres (כבר משתמשים ב־Supabase ל־Auth → אפשר לאחד)
- אינדקסים על `(carrier, plan_name)`, `(changed_at)`, `(workspace_id)`

### ערך
תמיכה ב־concurrent reads/writes אמיתית, backups מנוהלים, יכולת לרוץ multiple instances של Flask, ו־full-text search בעברית (`pg_trgm`).

---

## 6. הפרדת job queue מה־web server

### המצב כיום
APScheduler רץ בתוך אותו process של Flask. אם השרת קורס באמצע scrape — חצי scrape, חצי data. אם המכונה restartה ב־10:00 — הסקרייפ פוספס בלי alert.

### השיפור
- `worker.py` נפרד שמריץ APScheduler / RQ / Arq, מאזין לתור
- `app.py` חושף endpoint `POST /api/jobs/scrape` שמכניס job לתור
- `redis` כ־broker (זול, מנוהל ב־Upstash)
- כל job מתועד: `started_at`, `finished_at`, `status`, `error_traceback` בטבלת `scrape_jobs`
- Dashboard `/admin/jobs` שמראה היסטוריה ושיעור הצלחה לכל carrier

### ערך
חוסן: scrape שנכשל מנוסה שוב אוטומטית. תצפיות: רואים ב־UI אם Holafly נכשל 3 פעמים ברצף לפני שמשתמש מתלונן. סקלביליות: ניתן להריץ מספר workers במקביל.

---

## 7. בדיקות frontend

### המצב כיום
63 בדיקות ב־`tests/` (pytest) — כיסוי טוב לבקאנד.
**אפס** בדיקות ב־`mass-market-app/` — אין Vitest, אין Playwright e2e, אין React Testing Library.

### השיפור
- **Vitest + RTL** ל־components קריטיים: `PlanCard`, `SearchableSelect`, `ChatPanel`, `useAuth`
- **Playwright e2e** לתסריטי זהב: התחברות → דשבורד → סינון → השוואה → צפייה ב־alerts
- **Visual regression** עם Playwright screenshots ל־`Logo`, `BannerCard`, layout RTL
- כל אלה רצים ב־`ci.yml` בכל PR

### ערך
החלפת react 19 → 20 לא תשבור את ה־UI בשקט. שינוי ב־CSS לא יפיל את כיוון ה־RTL בלי שנדע. מפתחים יכולים לעשות refactor באומץ.

---

## 8. Type safety מלא

### המצב כיום
Python: אין type hints ב־`scraper.py`, `db.py`, `notifier.py`. שגיאות runtime בלבד.
JS: `.jsx` נטו, ללא TypeScript. שגיאות props מתגלות רק במשתמש.

### השיפור
- הוספת type hints הדרגתית עם `mypy --strict` על modules חדשים בלבד, וטיפוסים זרימה לבסיסיים
- מעבר הדרגתי ל־TypeScript ב־frontend: שינוי `vite.config.js` → תמיכה ב־`.tsx`, התחלה מ־`lib/api.ts` (חוזה ה־API)
- שיתוף הטיפוסים בין backend ל־frontend דרך OpenAPI → `openapi-typescript` (ראו סעיף 10)

### ערך
תפיסת באגים בזמן compile, אוטומציה משופרת, ו־refactoring בטוח.

---

## 9. Observability ו־error tracking

### המצב כיום
לוגים ב־`flask_log.txt` בשרת, אין aggregation, אין alerting. הדרך היחידה לדעת ש־scraper נשבר היא שמשתמש מתלונן ש"חסרים מסלולים".

### השיפור
- **Sentry** ב־Backend (Python SDK) וב־Frontend (React SDK) — חינמי עד 5K events/month
- **Structured logging** עם `structlog` — JSON logs, קל לחיפוש
- **Health endpoint** `/api/health` שמחזיר: זמן scrape אחרון לכל carrier, מספר plans נוכחי, חיבור ל־DB
- **Scraper carrier health page** ב־React: דשבורד ירוק/צהוב/אדום לכל ספק עם זמן ההצלחה האחרון
- **Telegram alert** אם scraper נכשל יותר מ־2x ברצף

### ערך
זיהוי מידי של שינוי באתר יעד ששובר scraper (תרחיש הכי שכיח), ושקיפות מול ה־user שיודע שהמערכת עובדת.

---

## 10. תיעוד API + OpenAPI

### המצב כיום
63 endpoints ללא תיעוד מסודר. CLAUDE.md מציג רשימה חלקית. כל לקוח Enterprise (ראו סעיף 4 במפת המוצר) ידרוש תיעוד.

### השיפור
- מעבר ל־`Flask-Smorest` או `apiflask` — generation אוטומטית של OpenAPI spec מ־decorators
- `/api/docs` עם Swagger UI מובנה
- versioning: `/api/v1/...` עתידית
- חוזי request/response מוגדרים כ־`marshmallow` / `pydantic` schemas

### ערך
סעיף 4 במפת המוצר ("REST API ציבורי") הופך ממאמץ של חודש למאמץ של ימים. Onboarding של מפתחים חדשים מהיר יותר.

---

## 11. Security hardening

### המצב כיום
- `config.json` עם כל הסודות (Telegram, SendGrid, Claude API, GreenAPI, Supabase service role) בקובץ אחד שלא ב־git — אבל עדיין plaintext על דיסק
- אין CSP headers, אין HSTS, אין סריקת תלויות
- `flask-limiter` ב־requirements אבל אין ראיה לשימוש על ה־endpoints החשופים

### השיפור
- מעבר ל־ENV vars / Doppler / 1Password Secrets / AWS SSM
- הוספת `flask-talisman` ל־CSP + HSTS + X-Frame-Options
- הפעלת `flask-limiter` על `/api/chat` (יקר), `/api/auth/*`, ו־`/api/scrape-*-now`
- `gitleaks` ב־CI (סעיף 2)
- הוספת `SECURITY.md` עם vulnerability disclosure policy

### ערך
הקטנת blast radius של דליפה, התקפת brute-force ב־`/api/chat` שעלולה לעלות אלפי שקלים ב־Anthropic API.

---

## 12. ארגון תלויות, lint, ו־DX

### המצב כיום
- אין `pyproject.toml` — `requirements.txt` בלבד, ללא pinning של transitive deps
- אין `pre-commit` hooks
- אין `ruff` / `black` — סגנון קוד לא אחיד
- ESLint רץ אבל לא ב־CI

### השיפור
- מעבר ל־`pyproject.toml` + `uv` / `poetry` עם `uv.lock`
- `ruff format` + `ruff check` ב־pre-commit
- `prettier` ל־frontend ב־pre-commit
- `commitlint` לסגנון commits אחיד (כבר נראה כמו conventional commits ב־`git log`)

### ערך
חוויית מפתח עקבית, פחות bikeshedding ב־PR reviews, builds reproducible.

---

## סיכום: מפת דרכים הנדסית

| שלב | עבודה | ערך עיקרי | זמן משוער |
|-----|-------|-----------|-----------|
| **שבוע 1** | סעיפים 1, 2, 12 | ניקוי, CI, DX | יסודות תפעוליים |
| **שבוע 2–4** | סעיפים 9, 11 | observability + security | "מצב חירום" → "מצב מקצועי" |
| **חודשים 1–2** | סעיפים 3, 7 | פירוק קוד + בדיקות frontend | קוד ניתן לתחזוקה |
| **חודשים 2–3** | סעיפים 4, 6 | hosting אמיתי + worker נפרד | זמינות 24/7 |
| **חודשים 3–4** | סעיפים 5, 10 | Postgres + OpenAPI | תשתית להרחבה ארגונית |
| **חודשים 4–6** | סעיף 8 | type safety מלא | קצב פיתוח גבוה |

---

## הקשר למפת המוצר הקיימת

| יכולת מוצרית | תלות הנדסית הכרחית |
|--------------|---------------------|
| היסטוריית שינויים (סעיף 1 מוצרי) | Postgres + indexes (סעיף 5 כאן) |
| מנוע ניתוח AI יזום (סעיף 2 מוצרי) | Job queue (סעיף 6 כאן) + observability (9) |
| ניטור באנרים וקופי (סעיף 3 מוצרי) | פירוק `scraper.py` (סעיף 3 כאן) |
| API ציבורי + BI (סעיף 4 מוצרי) | OpenAPI + versioning (סעיף 10 כאן) |
| הרחבה לענפים נוספים (סעיף 5 מוצרי) | פירוק לחבילות + tests (3, 7 כאן) |

המסקנה: **ללא היסודות ההנדסיים, מפת המוצר תיתקע**. הסעיפים כאן הם תנאי הכרחי לקצב הפיתוח שמפת המוצר מניחה.
