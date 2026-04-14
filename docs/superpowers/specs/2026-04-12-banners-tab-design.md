# באנרים ראשיים — מפרט עיצובי

**תאריך:** 2026-04-12  
**סטטוס:** מאושר

---

## רקע

המערכת עוקבת אחרי 8 ספקי סלולר ביתיים ומציגה את חבילותיהם. קיימת דרישה להוסיף כרטיסייה "באנרים ראשיים" שתציג צילומי מסך אוטומטיים של עמוד הבית של כל ספק, כדי לעקוב אחרי הקמפיינים השיווקיים שלהם לאורך זמן.

---

## מטרה

- צילום אוטומטי יומי של עמוד הבית של כל אחד מ-8 הספקים הביתיים
- תצוגת גריד של הבאנרים עם תאריך עדכון
- לחיצה על באנר פותחת modal עם תמונה מוגדלת + כפתור לאתר הספק

---

## ספקים

כל 8 הספקים הביתיים:

| מזהה | שם עברי | URL |
|------|---------|-----|
| partner | פרטנר | https://www.partner.net.il |
| pelephone | פלאפון | https://www.pelephone.co.il |
| hotmobile | הוט מובייל | https://www.hotmobile.co.il |
| cellcom | סלקום | https://www.cellcom.co.il |
| mobile019 | 019 מובייל | https://www.019mobile.co.il |
| xphone | XPhone | https://www.xphone.co.il |
| wecom | וי-קום | https://www.we.co.il |
| neptucom | נפטוקום | https://www.neptucom.co.il |

---

## ארכיטקטורה

### Backend

**תיקייה חדשה:** `data/banners/`  
שומרת PNG לכל ספק: `partner.png`, `pelephone.png`, וכו'.

**פונקציה חדשה ב-`scraper.py`:** `scrape_carrier_banners()`  
- מקבלת Page object מ-Playwright
- מנווטת לעמוד הבית של כל ספק
- ממתינה לטעינה (`networkidle` או `domcontentloaded` + 2s)
- מגדירה viewport ל-1280×720
- מצלמת screenshot ושומרת ל-`data/banners/<carrier>.png`
- מחזירה dict עם `{ carrier, scraped_at }` לכל ספק

**שינויים ב-`app.py`:**
1. APScheduler job חדש: `scrape_banners_job()` — רץ כל יום בשעה **08:00**
2. Route סטטי: `/banners/<carrier>.png` — מגיש את קבצי ה-PNG מ-`data/banners/`
3. API endpoint: `GET /api/banners` — מחזיר JSON:
   ```json
   [
     { "carrier": "partner", "name": "פרטנר", "url": "https://www.partner.net.il", "scraped_at": "2026-04-12T08:02:00", "image_url": "/banners/partner.png" },
     ...
   ]
   ```

### Frontend

**`DashboardPage.jsx`:**
- הוספת `{ id: 'banners', label: 'באנרים ראשיים' }` ל-`TABS`
- הוספת icon מתאים ל-`TAB_ICONS` (למשל `Camera`)
- Data loading: `api.getBanners()` — נטען בכניסה לכרטיסייה (כמו שאר הטאבים)
- State: `banners` (array), `bannersLoaded` (boolean), `selectedBanner` (object|null)

**גריד:**
- `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` — 8 כרטיסים = 2 שורות של 4 בדסקטופ
- padding/gap אחיד עם שאר הטאבים

**כרטיס ספק (`BannerCard`):**
- `<img>` full-width, `aspect-ratio: 16/7`, `object-fit: cover`
- footer: נקודת צבע + שם ספק + "עודכן: DD/MM HH:MM"
- hover: `translateY(-3px) scale(1.012)` + shadow
- לחיצה: מעדכן `selectedBanner` → פותח Modal
- במקרה שהתמונה לא נטענה: placeholder עם gradient צבע הספק

**Modal:**
- overlay כהה עם backdrop-filter blur
- תמונה מוגדלת (עד `90vw`, `max-width: 960px`)
- footer: שם ספק + תאריך + כפתור "🌐 פתח באתר הספק" (פותח tab חדש)
- סגירה: לחיצה על X, לחיצה מחוץ ל-modal, Escape

**`lib/api.js`:**
- הוספת `getBanners()` — `GET /api/banners`

---

## לוח זמנים (Scheduling)

| זמן | פעולה |
|-----|-------|
| 08:00 | `scrape_banners_job()` — מצלם כל 8 ספקים |
| 10:00 | scrape חבילות (קיים) |
| 16:00 | scrape חבילות (קיים) |

---

## טיפול בשגיאות

- אם screenshot נכשל לספק מסוים: ממשיך לשאר, לא זורק exception
- אם קובץ PNG לא קיים: הפרונטאנד מציג placeholder gradient
- אם endpoint `/api/banners` נכשל: הכרטיסייה מציגה הודעת שגיאה אחידה (כמו שאר הטאבים)

---

## בדיקה

1. הרץ `scrape_carrier_banners()` ידנית — ודא שנוצרים קבצי PNG ב-`data/banners/`
2. בקש `GET /api/banners` — ודא JSON עם 8 רשומות
3. בדפדפן: פתח כרטיסיית "באנרים ראשיים" — ודא גריד של 8 כרטיסים
4. לחץ על כרטיס — ודא modal עם תמונה + כפתור אתר
5. ודא Escape וX סוגרים את ה-modal
6. בדוק mobile: ודא עמודה אחת / 2 עמודות
