# MOCA — מודל הוצאות תפעוליות

> עדכון אחרון: אפריל 2026

---

## סיכום מהיר

| תקופה | עלות |
|-------|------|
| יומי | ~$1.11 |
| חודשי | ~$33.20 |
| שנתי | ~$398 |

---

## פירוט לפי ספק

### Apify — Social Media Scraping
**תפקיד:** סריקת פוסטים ציבוריים מ-Facebook / Instagram / Twitter / TikTok עבור 7 ספקים (סנטימנט סושיאל)  
**תוכנית:** Starter  
**מודל חיוב:** Flat fee חודשי קבוע + $5 compute credits כלולים. חיוב מחזורי גם אם לא נצרכו כל ה-credits. Credits לא מצטברים.

| יומי | חודשי | שנתי |
|------|-------|------|
| $0.97 | $29.00 | $348.00 |

**ריצות יומיות:** 7 ספקים × 4 פלטפורמות = 28 actor runs/יום  
**כתובת:** https://console.apify.com/billing

---

### Anthropic Claude API — AI & ניתוח
**תפקיד:** סנטימנט סושיאל יומי + Executive Summary יומי + AI Chat לפי דרישה  
**מודל חיוב:** Pay-per-use (אין מינימום חודשי)

#### סנטימנט סושיאל — `claude-sonnet-4-5`
רץ ב-08:10 כל יום עבור 7 ספקים  
תמחור: $3/MTok input · $15/MTok output

| פרמטר | ערך |
|-------|-----|
| Input tokens/יום | ~22,400 (7 × ~3,200) |
| Output tokens/יום | ~1,750 (7 × ~250, max_tokens=350) |
| עלות יומית | ~$0.09 |

#### Executive Summary — `claude-sonnet-4-5`
רץ פעם ביום, מסכם שינויי מחירים וסנטימנט

| פרמטר | ערך |
|-------|-----|
| Input tokens/יום | ~6,000 |
| Output tokens/יום | ~300 (max_tokens=400) |
| עלות יומית | ~$0.02 |

#### AI Chat — `claude-haiku-4-5`
לפי דרישה (/api/chat)  
תמחור: $0.80/MTok input · $4/MTok output

| פרמטר | ערך |
|-------|-----|
| Input tokens/יום | ~3,000–5,000 (משתנה) |
| Output tokens/יום | ~800–1,500 (max_tokens=1024) |
| עלות יומית | ~$0.01–0.05 |

#### סיכום Anthropic

| יומי | חודשי | שנתי |
|------|-------|------|
| ~$0.12–0.16 | ~$3.60–4.80 | ~$43–58 |

**כתובת:** https://console.anthropic.com/settings/billing

---

### שירותים חינמיים

| ספק | תפקיד | תוכנית | עלות |
|-----|--------|--------|------|
| **Netlify** | אחסון React frontend | Free (100GB bandwidth) | $0 |
| **Supabase** | Auth + PostgreSQL (משתמשים והרשאות) | Free (500MB, 50k MAU) | $0 |
| **ngrok** | מנהרה — חשיפת Flask המקומי לאינטרנט | Free (1 static domain) | $0 |
| **GitHub** | ניהול קוד מקור | Free | $0 |
| **Green API** | שליחת הודעות WhatsApp | Developer (Free) | $0 |
| **SendGrid** | דוח Excel יומי במייל | Free (100 מיילים/יום) | $0 |
| **Telegram Bot API** | התראות Telegram | חינמי תמיד | $0 |

---

### Backend מקומי (ללא עלות ענן)

| רכיב | איפה רץ | עלות |
|------|---------|------|
| Flask + APScheduler | Windows מקומי | $0 |
| Playwright scraping (40+ scrapers) | Windows מקומי | $0 |
| SQLite DB | Windows מקומי | $0 |
| Change detection | Windows מקומי | $0 |
| Banner screenshots (Playwright) | Windows מקומי | $0 |

> סריקת המחירים של כל הספקים (domestic / abroad / global / content) רצה לחלוטין מקומית — אפס עלות ענן.

---

## טבלת עלויות מלאה

| ספק | תפקיד | יומי | חודשי | שנתי |
|-----|--------|------|-------|------|
| Apify (Starter) | Social scraping | $0.97 | $29.00 | $348.00 |
| Anthropic API | Sentiment + Summary + Chat | ~$0.14 | ~$4.20 | ~$50.40 |
| Netlify | Frontend hosting | $0 | $0 | $0 |
| Supabase | Auth + DB | $0 | $0 | $0 |
| ngrok | Backend tunnel | $0 | $0 | $0 |
| GitHub | Code repo | $0 | $0 | $0 |
| Green API | WhatsApp | $0 | $0 | $0 |
| SendGrid | Email | $0 | $0 | $0 |
| Telegram | Notifications | $0 | $0 | $0 |
| **סה"כ** | | **~$1.11** | **~$33.20** | **~$398** |

---

## הערות והתראות

### Supabase Free — סכנת השהייה
Supabase משהה פרויקטים ב-Free tier לאחר **7 ימים ללא קריאות DB**.  
ה-scraper המקומי לא נוגע ב-Supabase (משתמש ב-SQLite). הפרויקט נשמר פעיל רק כשמשתמש מתחבר דרך ה-React app.  
אם אין התחברות 7 ימים → Supabase יושבת → יש לבצע Restore ידני.

### Apify — בדיקת ניצול Credits
כדאי לבדוק חודשית אם ה-$5 compute credits הכלולים מספיקים ל-28 הריצות היומיות.  
אם הניצול בפועל נמוך מ-$5/חודש → שקול מעבר חזרה ל-Free + Pay-as-you-go.

### קונסטלציות שיגדילו עלות סקרייפינג
1. **העברת Backend לענן** — Playwright שורף compute בענן ($10–50+/חודש)
2. **חסימת IP על ידי ספק** — דורש proxies ($10–300+/חודש)
3. **הרחבת סושיאל** — ספקים / פלטפורמות נוספות תחרוגנה מ-$5 credits
