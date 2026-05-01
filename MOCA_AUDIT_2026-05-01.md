# MOCA — סקירה מעמיקה של הפרויקט (2026-05-01)

סקירה מקיפה ב-5 צירים: אבטחה, איכות קוד backend, איכות קוד frontend, ארכיטקטורה ו-data flow, תפעול וחוסן. הסקירה בוצעה ע"י 5 subagents במקביל ואוחדה לדוח אחד.

**TL;DR — מה הכי חשוב לפעולה השבוע:**
1. JWT verifier מקבל טוקנים פגי-תוקף עד 4 שעות אחרי `exp` — צמצם ל-60s skew
2. הוסף `PRAGMA journal_mode=WAL` ב-`db._connect` — שורה אחת, מונע נעילות SQLite
3. החלף `provided != expected` ב-`hmac.compare_digest` בכל מקום שמשווים API keys
4. הסר את ה-fallback של `?api_key=` ב-query string על endpoints של scrape
5. אחד את כל ה-`CARRIER_LABELS` הכפולים ל-`carrierLabels.js` ולמראה ב-Python

---

## א. ממצאי אבטחה

### קריטי

**A1. JWT verifier מקבל 4 שעות פגיעה אחרי `exp`** — `app.py:592-670`
ה-verifier בודק `exp + 14400` (4 שעות) "כי השעון של Windows סוטה". בפועל זו חלון של 14,400 שניות שבו טוקן גנוב או טוקן של אדמין שהוסר נשאר תקף. גם אין בדיקת `iss`/`aud`. תיקון: דחה אם `time() > exp + 60`, הוסף בדיקת `iss == supabase_url + '/auth/v1'`. את סטיית השעון פתור עם `w32tm /resync`.

**A2. השוואת API keys לא ב-constant time** — `app.py:95-104, 436, 452`
`require_api_key`, `require_api_key_or_query`, `require_scrape_auth` — כל אחד עושה `provided != expected`. שאר הקוד כבר משתמש ב-`hmac.compare_digest` (שורות 134, 267) — צריך לאחד. החשיפה האמיתית: ngrok = רשת ציבורית, timing recoverable.

**A3. API key ב-query string על `/api/scrape-*-now`** — `app.py:429-439, 865, 906, 1885, 1907`
המפתח דולף ל-access logs, ngrok logs, browser history, browser referer. בנוכחות `flask_log.txt` (256KB ב-working tree) זה מתועד. תיקון: הסר את ה-fallback של `?api_key=`, רק `X-API-Key` header.

**A4. דליפת סודות ב-stack traces של `_supabase_conn`** — `app.py:673-682`
`psycopg2.OperationalError` יכול להכיל connection string עם password, ו-`logger.error(..., exc_info=True)` כותב את כל ה-traceback ל-log. תיקון: עטוף ב-`except: raise RuntimeError("supabase_conn_failed") from None` והוסף logging filter שמסנן `password=...`.

### גבוה

**A5. Email digest מזריק HTML בלי `html.escape`** — `notifier.py:438-497`
`workspace_name`, `app_title`, `logo_url`, `plan_name` (משוטח מנתונים שנגרדו) מוכנסים לתבנית HTML. workspace admin יכול לזרוע XSS דרך `app_title`, ויעדי גריד יכולים לזרוע דרך `plan_name`. תיקון: `from html import escape as h` והשתמש בכל מקום + ולידציה ל-`logo_url` כ-`^https://...$`.

**A6. נקודות `/api/plans`, `/api/changes`, `/api/banners`, `/api/executive-summary`, `/api/social-sentiment` ללא `@require_auth`**
המוצר הוא הדאטה. עם זאת ה-endpoints הראשיים פתוחים. גם אם הסקירה הציבורית רצויה — `_filter_hidden_carrier()` בכלל לא פועל כש-JWT לא קיים, אז feature_flags של workspace חסרים נחשפים.

**A7. CORS עם `supports_credentials=True` + `samesite="None"` cookie ללא הגנת CSRF** — `app.py:48-51, 2428-2435`
חברה עם form POST של `application/x-www-form-urlencoded` יכולה לעקוף CORS preflight ולשלוח cookie. בנוסף `request.get_json(force=True)` מקבל את ה-body. תיקון: הוסף בדיקה של `Content-Type: application/json` במוטטים, או החלף ל-`samesite="Lax"`.

**A8. Telegram session file חשוף** — `.gitignore:23, telegram_resellers.py:30`
`data/*.session` בלבד, לא `data/*.session*` (חסר WAL/SHM). 2FA password ניתן ב-`argv[3]` (process listing leak). תיקון: הרחב glob, השתמש ב-`getpass`.

**A9. `/api/users/<id>/role` מאפשרת לאדמין workspace לקדם משתמש לאדמין גלובלי** — `app.py:2709-2728`
התיקון: `@require_super_admin` ל-route הגלובלי, השאר workspace-scoped רק ב-`/api/workspaces/<ws>/users`.

**A10. Rate limit לפי `127.0.0.1` (כי behind ngrok)** — `app.py:38, 2580-2582`
כל המשתמשים נכנסים בעין שלי = הם חולקים budget של 3/min על `/api/contact`. תיקון: קונפיגרציה של `Limiter(key_func=...)` שלוקח X-Forwarded-For + `ProxyFix` middleware.

### בינוני

**A11.** `f"DELETE FROM {table}"` ב-`db.py:740, 717, 1497, 1541, 1603, 644, 652, 661` — היום בטוח (כל הקריאות עם constants), אבל הוסף `assert table in {whitelist}` נגד רגרסיה.

**A12.** `webhook_url` regex רחב מדי — `app.py:221-223, notifier.py:194-196`. הצמצם ל-`r'^https://[^./]+\.webhook\.office\.com/'` והעבר ל-מקום אחד.

**A13.** `request.get_json(force=True)` בעשרות routes — מתאים ל-CSRF דרך form POST. הסר `force=True` והחזר `415` ל-non-JSON.

**A14.** הסר את ה-HS256 path ב-JWT verifier (`app.py:636-651`) אחרי שה-migration הסתיים — עוד code path = עוד שטח תקיפה.

---

## ב. ממצאי איכות קוד — Backend

### בעיות נכונות קריטיות

**B1. הטסט של `removed_plan` לא תואם את הקוד** — `tests/test_change_detector.py:40-45`
ב-`change_detector.py:87-101` יש guard: `if key[0] not in carriers_with_new_data: continue`. הטסט מצפה ל-`removed_plan` של pelephone אבל ה-NEW לא מכיל pelephone — guard ידלג ויחזיר רשימה ריקה. **הטסט הנוכחי אמור ליפול**. אין כיסוי על לוגיקת ה-guard עצמה.

**B2. `_norm_extras` רץ רק על `save_global_plans`, לא על `save_abroad_plans` או `save_plans`** — `db.py:91-98, 824, 891-917, 745-779`
`cellcom_abroad` יכול להחזיר "שוודיה" ו-`pelephone_abroad` "שבדיה" — שתי כניסות שונות במסנן המדינות. תיקון: helper משותף שכל 4 ה-save callים יקראו אליו.

**B3. `filter_already_notified` חשוף ל-race condition** — `db.py:688-724`
שתי ריצות מקבילות יכולות לראות "לא דווח" ולהוסיף שני INSERT. ה-API `/api/scrape-*-now` יכול לרוץ במקביל לסקרייפ מתוזמן. תיקון: `UNIQUE` constraint + `INSERT OR IGNORE`, או mutex רחב.

**B4. `_delete_stale_carrier_rows` מוחק גם בקריסה חלקית** — `db.py:727-742`
כש-Pelephone מחזיר 4 מתוך 12 חבילות, ה-guard של "≥1" לא תופס — 8 חבילות תקפות נמחקות, אח"כ 8 התראות `removed_plan` שגויות. תיקון: threshold יחסי (`< 0.5 * count` = ויתור), או soft-delete עם `last_seen_at`.

**B5. דליפת timezone — local time מעורב עם UTC**
`filter_already_notified` עושה `cutoff = datetime.now() - timedelta(hours=24)` ([אזור הזמן של ישראל](db.py:703)), אבל `upsert_news_articles` (db.py:382) שומר `datetime.now(timezone.utc)`. סינון יוצא 2-3 שעות מוטה. תיקון: UTC עקבי בכל המודולים.

**B6. `os.remove` race ב-banner screenshots** — `scraper.py:7090, 7146`
אם ה-screenshot קטן מ-5KB מנסים למחוק. בין `screenshot()` ל-`getsize()` בקשת HTTP יכולה להחזיר את הקובץ הריק. תיקון: כתיבה ל-`*.png.tmp` ו-`os.replace` (atomic).

**B7. `detect_content_changes` — `trial_change` אסימטרי** — `change_detector.py:137-140`
התנאי `if old_trial and trial and old_trial != trial:` לא תופס מצב של הוספה/הסרה. תיקון: `if (old_trial or trial) and old_trial != trial:`.

### בעיות תחזוקתיות משמעותיות

**B8. `db.py` ללא מערכת migrations אמיתית** — try/except על ALTER. אין רישום גרסה, אין rollback, `except Exception: pass` בולע שגיאות אמיתיות. תיקון: טבלת `_migrations` + קבצי `migrations/0001_*.sql`.

**B9. `db.py` — 66 פונקציות, כל אחת פותחת חיבור משלה** — לוגיקה batch (`save_plans` + `save_changes`) מתפצלת לחיבורים נפרדים בלי טרנזקציה משותפת. תיקון: context manager `with db.session() as s`.

**B10. אינדקסים חסרים על שדות hot** — `changes.changed_at`, `(carrier, plan_name, change_type)`. `filter_already_notified` יסרוק טבלה בעוד שנה.

**B11. `scraper.py` 7,270-7,595 שורות** — 86 פונקציות top-level, אין הפרדה לפי תחום. תיקון: `scrapers/{domestic,abroad,global,content,banners}.py`.

**B12. אין retry/backoff/timeout policy אחיד בסקרייפרים** — סלקטור אחד נכשל ל-30 שניות = `removed_plan` שווא. תיקון: decorator `@with_retries(timeout=30000, retries=2)`.

**B13. `_make_global_plan` לא בשימוש עקבי** — סקרייפרים חדשים (Maya, ByteSim, Jetpack) עושים custom dict ולא עוברים דרך ה-helper, אז ה-RLM fix לא מוחל עליהם.

**B14. פיזור של מילוני נירמול שמות מדינות** — `_DEST_NORM`, `AIRALO_SLUG_TO_HEBREW`, `SAILY_SLUG_TO_HEBREW`, `ESIMIO_SLUG_TO_HEBREW`, `HOLAFLY_SLUG_TO_HEBREW`, `ORBIT_NAME_TO_HEBREW`, `_tuki_name_fix`. תיקון: `data/canonical_countries.json` משותף לפייתון ו-JS.

**B15. `app.py` 4,003 שורות, 110 routes** — Flask Blueprints חיוניים: `plans_bp`, `auth_bp`, `admin_bp`, `notifications_bp`, `scheduler.py`.

**B16. APScheduler ללא `misfire_grace_time` או `coalesce`** — `app.py:3974-3996`. אם הPC ישן ב-7:30 וה-job פספס, הוא לא ירוץ עד יום אחרי. תיקון: `misfire_grace_time=900, coalesce=True, max_instances=1`.

**B17. SSE endpoint ללא limit על מנויים בו-זמנית** — `app.py:984-1037`. כל מנוי תופס thread, ו-`_scrape_progress['log']` גדל ללא חיתוך.

**B18. `notifier.py` עם `localhost:5000` קשיח** — `notifier.py:63, 102, 141, 171, 243`. WhatsApp/Telegram recipients חיצוניים יראו לינק מת.

**B19. רטריי-לוגיקה חסרה בכל הערוצים של `notifier`** — Telegram/Slack/Email/Push/WhatsApp מחזירים `False` על `RequestException` בלי retry. transient blip = הודעה אבודה.

**B20. `archive.py:35-52` — `save_plan_snapshot` לא מנרמל extras** — ארכיון יראה "שוודיה" בעוד הדאשבורד מציג "שבדיה".

### Quick wins backend

- `inspect_*.py` ב-root (15+ קבצים) → `debug_archive/` או למחוק
- `flask_log.txt` (255KB) ו-JSON sample data ב-root → `data/cache/` או gitignore
- `pytest.ini` עם markers ו-`testpaths` (`PytestUnknownMarkWarning` מעצבן)
- magic numbers → constants (`MIN_VALID_BANNER_BYTES = 10_000`, `MARKET_MOVER_THRESHOLD_PCT = 5.0`)
- `requirements-dev.txt` עם `pytest`, `pytest-cov`, `ruff`
- `excel_report.py:15-23` רק 5 carriers, חסר xphone/wecom/neptucom
- `seed_resellers.py:55` משתמש ב-`db._connect` (private API)

---

## ג. ממצאי איכות קוד — Frontend

### באגים קריטיים

**C1. `useEffect` לולאתי ב-DashboardPage** — `DashboardPage.jsx:290-313`
ה-effect תלוי ב-`searchParams` ובסיומו עושה `setSearchParams({})` — בעת הוספת פרמטר חדש בעתיד = לולאה אינסופית. תיקון: dep array `[]` או guard.

**C2. כפילות `CARRIER_LABELS` בשמונה מקומות לפחות**
- `PlanCard.jsx:73-93`, `GroupedPlanCard.jsx:81-95`, `DashboardPage.jsx:676, 1365`, `ExecutiveSummaryPage.jsx:36-52`, `NewsTab.jsx:35-49`, `ChatPanel.jsx:15-66`, `ComparePage.jsx:21-71`, `HistoryTab.jsx:10-47`, `MarketMoversWidget.jsx:6-15`
CLAUDE.md אומר ש-`carrierLabels.js` הוא single source — אבל לא משתמשים בו. תוצאה: ספקים חדשים (`bytesim`, `bcengi`, `breez`) מוצגים באנגלית בחצי מהמסכים. תיקון: ייבוא אחד מכל מקום.

**C3. כפילות מפתח ב-`CARRIER_LOGOS`** — `PlanCard.jsx:106, 127`
`rami_levy` מוגדר פעמיים. JS שותק.

**C4. `useScrape` Provider בלי cleanup** — `useScrape.jsx:26-39`
`pollRef.current` ו-`scrapeAll` request נשארים פעילים אחרי unmount. ב-StrictMode: warnings; בעתיד: leak.

**C5. `useEffect` ב-`DashboardPage.jsx:228-233` עם `eslint-disable exhaustive-deps`** — מחביא באג של tab שלא משתנה כשעוברים ל-tab חבוי.

**C6. JWT token refresh — אם `TOKEN_REFRESHED` event לא נורה, `localStorage` נשאר עם token ישן** — `useAuth.jsx:79-142`.

**C7. `mass-market-app/dist/` ב-working tree** — אם נכנס ל-git, כל commit יכלול build artifacts.

**C8. Hardcoded fallback של Supabase anon key (HS256!)** — `lib/supabase.js:5`
לפי הזיכרון של 2026-04-25, המפתחות עברו ל-ES256. ה-fallback הוא JWT עם `alg: HS256` — לא תקף. בכל סביבה ללא env var = כשל אילם. תיקון: הסר fallback.

**C9. catch silent — `catch(() => setItems([]))` בכמה hooks**
`useScrape`, `useAnnotationCounts`, `useWatchlist` — שגיאות שרת = "רשימה ריקה". משתמש שמדווח "ה-watchlist נעלם" — אין לדעת מה קרה. תיקון: error state + banner.

### תחזוקה

**C10. `DashboardPage.jsx` 1,447 שורות** — סינון, מיון, טעינת 5 סוגים, modals, ייצוא Excel, ייצוא PDF inline, search params. תיקון: hooks `useDashboardData(tab)`, `usePlanFilters`, components `<DashboardFilters>`, `<CompareDrawer>`.

**C11. `MULTI_COUNTRY_CARRIERS` ו-`getPlanCoverage` רק ב-DashboardPage**, ב-ComparePage גרסה שונה (`CARRIER_COUNTRY_LISTS`). ספק חדש = שינוי ב-3 מקומות.

**C12. `KNOWN_REGIONS` כפול עם רשימות שונות** — `DashboardPage.jsx:162-178`, `ComparePage.jsx:73-89`. `DashboardPage` חסר `'איי התעלה'` ש-ComparePage כן מכיל. אזור שמופיע במסך אחד ולא במשנהו.

**C13. `setVisibleCount` עם 5000/50/`prev+500` שונה ב-handlers שונים** — לא דטרמיניסטי במקרה של batching.

**C14. ProtectedRoute מקונן בעצמו ב-App.jsx** — `<ProtectedRoute><ProtectedRoute adminOnly>`. תיקון: `useRequireAuth({adminOnly})` hook.

### ביצועים

**C15. `filteredPlans` נבנה מחדש על כל `watchItems` change** — `DashboardPage.jsx:542`. עם 5,000 plans זה לא חינם.

**C16. `SparklineMini` global cache שגדל ללא LRU/TTL** — `SparklineMini.jsx:4-5`. שעה של גלילה = 5,000 entries תקועות.

**C17. fetch ישיר ל-`open.er-api.com/v6/latest/GBP` מהפרונט** — `DashboardPage.jsx:327-330`. אין cache, אין fallback. עבור ל-`/api/exchange-rates` בצד שרת.

**C18. ייבוא `xlsx` רגיל ב-HistoryTab** — `HistoryTab.jsx:6`. 80KB gzipped בכל פתיחה. עבור ל-dynamic import.

**C19. `key={key + i}` ב-PlanCard list** — `DashboardPage.jsx:1203`. sort = drop+mount של 5,000 cards.

**C20. `displayItems` O(n²) על `plans.global`** — `DashboardPage.jsx:608-621`. שני filterים נפרדים על אותו array.

### נגישות

**C21. `text-gray-300` על רקע לבן = ניגודיות 1.6:1 (WCAG מצריך 4.5:1)** — micro-text ב-PlanCard.

**C22. כפתורי אייקון בלי `aria-label`** — `PlanCard.jsx:600-614`. `title` הוא tooltip בלבד, לא accessible name.

**C23. Modal ללא `role="dialog"` / `aria-modal` / focus trap** — `Modal.jsx`. `BannerCard.jsx:97-99` כן עושה את זה נכון.

**C24. `SearchableSelect` — חצי לוח-מקשים לא עובד** — אין מקשי חצים בתוך listbox.

**C25. `<a><div>headline</div></a>` ב-NewsTab בלי `aria-label`** — screen reader רק "link".

### דברים שטובים

✓ Lazy routing מסודר ב-App.jsx
✓ PWA + service worker עם NetworkFirst לדאטא, CacheFirst ל-assets
✓ `_clearTimers` ב-useScrape — מסודר
✓ cancel flag ב-PriceHistoryModal ו-MarketMoversWidget — pattern נכון
✓ dynamic import של xlsx ושל PriceHistoryModal/Recharts — חיסכון bundle משמעותי
✓ IntersectionObserver ב-SparklineMini — load on visible
✓ `bootTimeout` 3 שניות ב-useAuth — defensive
✓ `<bdi>` סביב מספרים ב-RTL — ידע מעמיק
✓ `prefers-reduced-motion` ב-CSS — תקני
✓ Tailwind v4 `@theme` — גישה חדשה ונכונה

---

## ד. ממצאי ארכיטקטורה ו-Data Flow

### חוזקות

✓ `change_detector.py` 143 שורות, אלגנטי, מטפל בכל ה-edge cases (currency-aware, type coercion, removal guard)
✓ `filter_already_notified` כמנגנון dedup ל-24 שעות, מובנה לכל path
✓ Archive system עם content hashing — חוסך אחסון
✓ Lazy-loaded React routes + PWA — bundle נכון
✓ JWT verification ידנית עם JWKS caching ו-key rotation
✓ הפרדת `api_key` מ-`server_admin_key`
✓ `backup_to_drive.ps1` מהונדס היטב — alert mailer, drive auto-restart, sqlite `.backup` API, rotation
✓ Watchdogs פשוטים אבל עובדים

### סיכונים קריטיים

**D1. SPOF = ה-PC של אלון.** המוצר חי על PC ביתי. כיבוי = כל המוצר יורד.

**D2. ngrok Free static URL** — אם השירות יסגר/ישנה תנאים, כל ה-React ב-Netlify מת. `VITE_API_URL` קשיח אליו.

**D3. SQLite ללא WAL** — APScheduler scrape (10+ דק' כתיבה) חוסם API requests. `database is locked` ייפול בעת pilot.

**D4. אין CI** (אין `.github/workflows/`). regression שיתגלה רק בפרודקשן.

**D5. Backup לא נבדק לשחזור**. RTO לא מאומת.

**D6. שכפול לוגיקה ב-`run_scrape_job` (`app.py:3684-3850`) מול `api_scrape_all_now` (`app.py:1053-1172`)** — שני entry points עם 5 פעולות זהות בסדר שונה. אחד מהם ייפרד מהשני בהמשך.

**D7. שני jobs ב-08:00 בו-זמנית** (banners + store_banners) — שני Playwright instances בו-זמנית, race על RAM.

### בעיות עיצוב מהותיות

**D8. `scraper.py` 7,595 שורות** — 15 מודולים לוגיים נדחסים לקובץ אחד. צריך `scrapers/` package.

**D9. `app.py` 4,003 שורות, 110 routes** — Flask Blueprints חיוניים.

**D10. אין notifier abstract** — ערוץ חדש = 4 שינויים hardcoded ב-`run_scrape_job`. צריך `class Channel: send(message, changes)` ו-registry.

**D11. Multi-workspace = view filter, לא tenancy אמיתי**.
- `plans/abroad_plans/global_plans/content_plans` ללא `workspace_id`
- `hide_self_carrier` הוא רק שכבת view
- `executive_summary`, `social_sentiment` גלובליים — MVNO רואה תובנות שכוללות את עצמו
- `feature_flags` נאכפים רק ב-frontend, לא ב-backend
- `saved_views`, `watchlist` per-user ללא workspace_id — drift בעת מעבר workspace

**D12. אין pagination + אין versioning ב-API** — `/api/plans` מחזיר 3K שורות, `/api/global-plans` עד 2,500. 500KB-2MB לכל טעינה.

**D13. אין `aud`/`iss`/`jti` בדיקה ב-JWT** (אזכור מאבטחה).

**D14. SSE עם 6-min timeout ו-`Condition.wait` polling 2s** — כל מנוי תופס thread, ב-Flask dev server זה לא בר-קיימא.

**D15. APScheduler in-process** — בלי persistent jobstore, jobs שפוספסו אבודים.

### צווארי בקבוק לסקיילינג

| משאב | יקרוס סביב | פתרון |
|---|---|---|
| 5-10 משתמשים בו-זמנית | `database is locked` | WAL + gunicorn |
| 20-50 פיילוטים | `_supabase_conn()` נפתח כל request | connection pool |
| 1M שורות ב-`changes` | `filter_already_notified` ללא index | `CREATE INDEX changes_at` |
| 15 ספקים גלובליים נוספים | scrape sequential = 30+ דק' | ThreadPoolExecutor |

### כיוון 10x משתמשים/ספקים

1. **DB:** Postgres (psycopg2 כבר מותקן)
2. **Pipeline:** Celery/RQ/Dramatiq, retry+backoff per scraper
3. **API:** FastAPI עם async + OpenAPI + pydantic validation, `/api/v1/`
4. **Frontend:** React Query/SWR, אולי Next.js
5. **Multi-tenancy:** row-level (`workspace_id`) או database-per-tenant
6. **Observability:** Sentry + Prometheus + Grafana
7. **Deployment:** Docker → Fly.io/Railway/Hetzner
8. **Backup:** S3 versioning, רבעון restore drill

---

## ה. ממצאי תפעול וחוסן

### סיכונים תפעוליים קריטיים

**E1. אין retention על `audit_log`, `changes`, `news_articles`** — `db.py:304`. תוך שנתיים ה-DB יגיע לעשרות GB. `PRAGMA integrity_check` החודשי ייקח דקות, backup ל-Drive ייחנק. **פצצת זמן.**

**E2. `flask_watchdog.bat` ללא crash loop detection** — אם `app.py` נכשל ב-import, restart כל 15s לנצח. אין escalation. תיקון: ספור 5 כשלונות ב-5 דק' → alert ועצירה.

**E3. כל ה-logs גדלים לנצח** — `flask_watchdog.log`, `vite_watchdog.log`, `backup.log`, `health_check.log`, `drive_monitor.log`. אין rotation.

**E4. Flask logging ל-stdout בלבד** — `app.py:29`. אין `FileHandler`. כשהמערכת תתנהג מוזר, אין היסטוריה. תיקון: `RotatingFileHandler('logs/flask.log', maxBytes=10MB, backupCount=5)`.

**E5. SQLite ללא WAL** — כפי שצוין בכמה מקומות.

**E6. ngrok Free tier — single static URL** — סיכון vendor.

**E7. PC SPOF — RTO 4-12 שעות במקרה הטוב, יום-יומיים במקרה רע.** לא containerized, paths קשיחים ל-`D:\השוואת MASS MARKET\`.

### Resilience gaps

**E8. אין timeout per-scraper.** סלקום נתקע = `run_scrape_job` יכול לרוץ שעה.

**E9. Telegram session corruption** — לא נכלל ב-backup. שחזור = login ידני דו-שלבי מחדש.

**E10. APScheduler restart מתעלם מ-misfires** — אין persistent jobstore.

**E11. `vite_watchdog.bat` רץ `npm run dev` (לא production build)** — hot-reload + source maps.

### Silent failures (מה לא מנוטר)

| ערוץ כשל | מתי תגלה |
|---|---|
| Scraper נכשל לספק יחיד | ימים-שבועות, רק במקרה |
| Telegram bot rate-limited | אף פעם |
| SendGrid quota (100/day Free) | אחרי שעוברת |
| Anthropic API spend חורג | בחיוב חודשי |
| Apify credits נגמרו | בסוף החודש |
| Supabase suspended (7 ימים ללא login) | משתמש ראשון לא נכנס |
| Netlify deploy נכשל | בפעם הבאה שתפתח |
| ngrok tunnel נופל | תוך דקות |
| Disk space < 1GB | scraper נופל בלי alert |
| `plans.db` corruption | health check חודשי |
| VAPID keys "expired" | משתמשים מפסיקים לקבל push |
| Google News RSS משתנה | רק אם תסתכל בטאב חדשות ריק |
| Audit log → 1M שורות | הפיך-לאט |

תיקון: `service_health_monitor.ps1` שעושה GET ל-`/api/health` כל שעה לשלושה endpoints (Flask local, ngrok, Netlify) + alert ב-streak של 1/3/6 כשלונות.

### Disaster recovery — הערכה כנה

- **RPO:** 24 שעות (backup יומי)
- **RTO:** 4-12 שעות במקרה טוב, יום-יומיים במקרה רע
- **אין Dockerfile/docker-compose** — קוד לא portable
- **אין off-site copy מעבר ל-Google Drive** — חשבון אחד = single attack vector

תיקון: Dockerfile + `docker-compose.yml` → `docker compose up` על Linux = 10 דק' DR. תוסף backup שבועי ל-S3 ($1/חודש).

### Quick wins תפעולי

| # | פעולה | זמן | השפעה |
|---|---|---|---|
| 1 | `PRAGMA journal_mode=WAL` | 5 דק' | מבטל נעילות SQLite |
| 2 | `RotatingFileHandler` | 15 דק' | היסטוריית debug |
| 3 | Audit log retention (DELETE > 180d) | 30 דק' | מונע גידול |
| 4 | `service_health_monitor.ps1` | שעה | זיהוי outages |
| 5 | Crash loop detection ב-watchdog | שעה | מונע tight loop |
| 6 | `docs/RUNBOOK.md` | יום | onboarding + הצלת זמן |
| 7 | Dockerfile + docker-compose | יום-יומיים | DR = דקות |
| 8 | Per-carrier scrape timeout | שעה | מונע hang שלם |
| 9 | `/api/health` עם last_scrape, DB size, last_change | שעה | ראייה תוך שניות |
| 10 | `post-commit` hook → `npm run build` | 30 דק' | ביטול שכחה |
| 11 | Secret rotation reminder ב-Calendar | 5 דק' | תהליך מסודר |
| 12 | רבעון: בדיקת restore על מכונה שנייה | חצי יום | DR confidence |

---

## ו. תיעדוף משוקלל — מה לעשות ובאיזה סדר

### השבוע (1-3 ימי עבודה)
1. **A1** — JWT verifier: 4-hour grace → 60s + iss check
2. **A2-A3** — `hmac.compare_digest` + הסר `?api_key=`
3. **E5** — `PRAGMA journal_mode=WAL` (שורה אחת!)
4. **E4** — `RotatingFileHandler`
5. **B1** — תקן את הטסט של `removed_plan` (כיסוי לוגיקת ה-guard)
6. **B5** — UTC עקבי ב-timezone handling
7. **C8** — הסר Supabase HS256 fallback
8. **C2** — אחד `CARRIER_LABELS` ל-`carrierLabels.js` (גם ב-Python)

### החודש (5-10 ימים)
9. **A5** — escape HTML ב-email digest
10. **A6** — `@require_auth` על `/api/plans` ושאר הקריאות
11. **B2** — `_norm_extras` משותף לכל 4 ה-save callים
12. **B4** — soft-delete בדיקת threshold ב-`_delete_stale_carrier_rows`
13. **B12** — decorator `@with_retries` לסקרייפרים
14. **B16** — `misfire_grace_time` + `coalesce` ב-APScheduler
15. **C1** — תקן `useEffect` לולאתי ב-DashboardPage
16. **C9** — error states ב-hooks
17. **E1** — retention על audit_log + changes
18. **E2** — crash loop detection ב-watchdog
19. **E9** — health endpoint עם ראייה אופרטיבית

### תוך שלושה חודשים
20. **B11, D8** — פיצול `scraper.py` ל-`scrapers/` package
21. **B15, D9** — Flask Blueprints
22. **C10** — פיצול `DashboardPage.jsx`
23. **D10** — Notifier abstract interface
24. **D11** — תיעדוף multi-workspace: לפחות `feature_flags` ב-backend, `_filter_hidden_carrier` בכל ה-endpoints, `workspace_id` ב-`saved_views`/`watchlist`
25. **E7** — Dockerfile + docker-compose
26. **GitHub Actions CI** — `pytest` + `npm run lint` + build verification (חצי יום, מונע regressions לעולם)
27. **Sentry SDK** (free tier) — חצי שעה install, ראייה דרמטית

### המלצה ל-DR vs שילוב פיצ׳רים
ההמלצה הכי קונקרטית מכל הסקירה: **השקעה של שבוע אחד ב-WAL + RotatingFileHandler + service health monitor + retention job + Dockerfile** מהפכת את MOCA מ-"רץ כי אנחנו צופים בו" ל-"רץ ושולח אלרט רק כשמשהו נשבר באמת". זה צעד אחד שלם בבגרות תפעולית, ואחר כך אפשר להחזיר את הפוקוס לפיצ׳רים.

---

## תקציר מנהלים — 5 משפטים

הפרויקט בעל **רמת קוד גבוהה לקטגוריה שלו** (decorators מאובטחים, JWKS verification ידני, CSP, rate limiting, web push VAPID, content-hashing archive). הסיכונים העיקריים הם **סיכונים שעולים עם הסקייל** — לא בעיות של איכות אלא של בגרות תפעולית: SQLite ללא WAL, scheduler לא persistent, אין CI, אין Dockerfile, אין retention. **8 מקומות שבהם `CARRIER_LABELS` משוכפלים** מבטיחים שהוספת ספק חדש תיכשל בחלק מהמסכים. **JWT verifier מקבל 4 שעות פגיעה** היא הסיכון האבטחתי הכי משמעותי. **המלצה אסטרטגית:** שבוע של hardening תפעולי (12 quick wins ברשימה למעלה) שווה יותר מחודש של פיצ׳רים חדשים.
