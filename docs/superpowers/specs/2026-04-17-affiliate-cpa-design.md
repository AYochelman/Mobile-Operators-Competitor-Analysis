# Spec: Affiliate / CPA — ספקי eSIM גלובליים

**תאריך:** 2026-04-17  
**מודל עסקי:** Redirect endpoint + click tracking + analytics  
**ספקים בשלב א׳:** Airalo, Holafly, Saily, Globalesim

---

## מטרה

להפוך כל קליק על "לאתר הספק" בחבילות eSIM גלובליות להכנסה — דרך תוכניות affiliate קיימות של הספקים. MOCA מפנה את המשתמש דרך endpoint פנימי שרושם את הקליק ומוסיף את ה-tag של MOCA לURL היעד.

---

## ארכיטקטורה

```
משתמש לוחץ "רכישה" בPlanCard
        ↓
GET /go/<provider>/<plan_id>   (Flask)
        ↓
1. רשום קליק ב affiliate_clicks
2. בדוק affiliate config לספק
3. 302 Redirect → URL ספק + affiliate tag
        ↓
משתמש מגיע לאתר הספק עם tag → רכישה → עמלה ל-MOCA
```

---

## Backend

### טבלה: `affiliate_clicks`
```sql
CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    plan_id    TEXT,
    country    TEXT,
    clicked_at TEXT NOT NULL,  -- ISO 8601
    ip_hash    TEXT            -- SHA-256(IP), לא IP גולמי
);
```

### Endpoint: `GET /go/<provider>/<plan_id>`
- **אין** `@require_api_key` — ציבורי לחלוטין
- `plan_id` הוא slug של שם החבילה (אופציונלי, לאנליטיקס בלבד)
- אם הספק לא קיים ב-affiliate config → redirect לbase_url של הספק ללא tag (fallback שקט)
- response: `302 Location: <affiliate_url>`

### Endpoint: `GET /api/affiliate/stats?days=30`
- מוגן ב-`@require_api_key`
- מחזיר: קליקים מקובצים לפי `provider` + `date(clicked_at)`
- JSON: `[{ provider, date, clicks }]`

### config.json — הרחבה
```json
"affiliate": {
  "airalo": {
    "tag": "MOCA_IL",
    "base_url": "https://www.airalo.com/?ref=MOCA_IL"
  },
  "holafly": {
    "tag": "moca",
    "base_url": "https://esim.holafly.com/?ref=moca"
  },
  "saily": {
    "tag": "moca",
    "base_url": "https://saily.com/?ref=moca"
  },
  "globalesim": {
    "tag": "moca",
    "base_url": "https://globalesim.com/?ref=moca"
  }
}
```
> הערה: ה-tags הם placeholders — יש להחליף בtagים האמיתיים לאחר אישור ההרשמה לכל תוכנית.

### db.py — פונקציות חדשות
- `log_affiliate_click(provider, plan_id, country, ip_hash, db_path=None)`
- `get_affiliate_stats(days=30, db_path=None)` → `list[dict]`

---

## Frontend

### `AFFILIATE_PROVIDERS` — קבוע ב-PlanCard
```js
const AFFILIATE_PROVIDERS = new Set(['airalo', 'holafly', 'saily', 'globalesim'])
```

### PlanCard — שינוי כפתור לחבילות גלובליות
- אם `AFFILIATE_PROVIDERS.has(plan.carrier)`:
  - href: `/go/<provider>/<slugified_plan_name>`
  - טקסט: `🛒 רכישה ↗`
  - עיצוב: כפתור מלא בצבע espresso (`bg-[#5c3317] text-white`)
  - מתחת לכפתור: טקסט קטן `"דרך MOCA"` (disclosure)
- אחרת: לינק רגיל כמו היום

### `slugify(name)` — utility
```js
// "Israel – 1GB – 7 ימים" → "israel-1gb-7-days"
function slugify(str) {
  return str.toLowerCase()
    .replace(/[–—]/g, '-')
    .replace(/\s+/g, '-')
    .replace(/[^\w-]/g, '')
    .replace(/-+/g, '-')
    .trim('-')
}
```

### SettingsPage — טאב "Affiliate" (admin בלבד)
- טבלה: ספק / קליקים 30 יום / הכנסה משוערת
- הכנסה משוערת = `קליקים × conversion_rate × avg_commission` (מוגדר ב-config)
- גרף קווי של קליקים לפי יום (Recharts — כבר מותקן)
- גלוי רק כש-`user.role === 'admin'`

---

## Edge Cases

| מצב | התנהגות |
|-----|---------|
| ספק ללא config | redirect לדף הבית של הספק ללא tag, ללא שגיאה |
| plan_id לא קיים | מתעלמים — לא חובה לזיהוי |
| קליק כפול | נרשם (הספק מסנן בצד שלו) |
| המשתמש חוזר ללא רכישה | לא ידוע ל-MOCA — הספק מנהל attribution window |

---

## תהליך הרשמה לתוכניות (מחוץ לקוד)

| ספק | קישור | עמלה | אישור |
|-----|-------|------|-------|
| Airalo | partners.airalo.com | ~10% | אוטומטי |
| Holafly | affiliate.holafly.com | ~12% | ידני 2-5 ימים |
| Saily | Impact.com | ~10% | ידני |
| Globalesim | צור קשר ישיר | 8-15% | משא ומתן |

**סדר מומלץ:** Airalo ראשון (אישור מיידי) → Holafly → Saily → Globalesim.

---

## מה לא בסקופ (שלב ב׳)

- A/B testing על מיקום הכפתור
- banner ייעודי "חבילות מומלצות"
- ספקי סלולר ישראליים (פרטנר, פלאפון, סלקום)
- conversion tracking (דורש pixel/postback מהספק)
