# Design Spec: "בחדשות" News Tab

**Date:** 2026-04-17  
**Status:** Approved

---

## Context

The MOCA dashboard currently has 6 tabs: חבילות סלולר, חו"ל, גלובלי, תוכן, באנרים, היסטוריה.  
This spec adds a 7th tab — **"בחדשות"** — placed immediately after "היסטוריה".  
The tab surfaces news headlines mentioning Israeli cellular carriers, sourced from popular Israeli news and financial sites, so operators can track media coverage alongside pricing data.

---

## Data Source

**Google News RSS** — free, no API key, aggregates from all Israeli news sites.

Query URL pattern per carrier:
```
https://news.google.com/rss/search?q={KEYWORD}&hl=iw&gl=IL&ceid=IL:iw
```

Keywords (Hebrew carrier names used as search terms):

| Carrier ID   | Search keyword         |
|--------------|------------------------|
| partner      | פרטנר סלולר            |
| pelephone    | פלאפון                 |
| hotmobile    | הוט מובייל             |
| cellcom      | סלקום                  |
| mobile019    | 019 סלולר              |
| xphone       | XPhone סלולר           |
| wecom        | We-Com סלולר           |
| neptucom     | Neptucom סלולר         |

Each RSS item provides: title, link, source (via `<source>`), pubDate.

---

## Backend

### New DB Table — `news_articles`

```sql
CREATE TABLE IF NOT EXISTS news_articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    carrier     TEXT NOT NULL,
    headline    TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    source      TEXT,
    published_at TEXT,
    fetched_at  TEXT NOT NULL
);
```

### New function — `scraper.py`

`scrape_carrier_news() → list[dict]`  
- Fetches Google News RSS for each carrier keyword using `requests` + `xml.etree.ElementTree`  
- Deduplicates by URL  
- Returns list of dicts: `{carrier, headline, url, source, published_at}`

### New DB function — `db.py`

`upsert_news_articles(articles: list[dict])` — INSERT OR IGNORE by URL uniqueness.  
`get_news_articles(carrier=None) → list[dict]` — returns all (or filtered by carrier), ordered by `published_at DESC`, limit 200.

### New API endpoint — `app.py`

```
GET /api/news?carrier=<id>
```
- Returns JSON array of news articles (carrier filter optional)
- No API key required (read-only, public data)

### Scheduler — `app.py`

The existing **09:00 job** (executive summary email) gets a preflight call to `scrape_carrier_news()` + `upsert_news_articles()`.

---

## Frontend

### New tab — `DashboardPage.jsx`

Add to the `TABS` array (after `history`):
```js
{ id: 'news', label: 'בחדשות', icon: <Newspaper size={16} /> }
```

Import `Newspaper` from `lucide-react`.

Tab content switch: render `<NewsTab />` when `tab === 'news'`.

Data loading: lazy-load on first tab visit via `api.getNews()`.

### New API function — `lib/api.js`

```js
getNews: (carrier = null) =>
  request(`/api/news${carrier ? `?carrier=${carrier}` : ''}`)
```

### New component — `components/NewsTab.jsx`

**State:**
- `articles` — full list from API
- `carrierFilter` — selected carrier ID or `'all'`
- `loading` / `error`

**Layout (RTL):**

1. **Header row** — title "📰 בחדשות" (using `Newspaper` icon from Lucide, not emoji), subtitle, last-updated timestamp
2. **Filter bar** — carrier pills (הכל + 8 carriers), same style as existing filter pills in DashboardPage
3. **News grid** — `grid-cols-1 sm:grid-cols-2 xl:grid-cols-3`, gap-4
4. **NewsCard** — per article:
   - Top row: source badge (right) + relative date with `Calendar` icon (left) — Lucide
   - Headline (bold, 2-line clamp)
   - Footer: carrier tag pill(s) + `ExternalLink` icon (Lucide) on the left
   - Entire card is `<a href={url} target="_blank" rel="noopener noreferrer">`
   - Hover: subtle shadow + border darkening (matching existing PlanCard style)
5. **Empty state** — "לא נמצאו כתבות" when no results after filtering
6. **Error state** — "שגיאה בטעינת החדשות" with retry button

**Carrier tag colors** — reuse the existing badge color scheme from DashboardPage (blue=partner, pink=pelephone, orange=hotmobile, green=cellcom, purple=mobile019, sky=xphone, yellow=wecom, slate=neptucom).

**Icons used (all Lucide React):**
- `Newspaper` — tab icon + section header
- `Calendar` — article date
- `ExternalLink` — card link indicator

---

## Data Flow

```
09:00 APScheduler
  └─ scrape_carrier_news()       ← Google News RSS (8 queries)
  └─ upsert_news_articles(...)   ← SQLite INSERT OR IGNORE
  └─ [existing executive summary job continues]

User opens "בחדשות" tab
  └─ api.getNews()               ← GET /api/news
  └─ NewsTab renders articles
  └─ carrier filter → client-side filtering (no re-fetch)
```

---

## Verification

1. Run Flask: `python app.py`
2. Trigger news scrape manually: call `scrape_carrier_news()` from Python shell, verify returned list
3. Check DB: `SELECT * FROM news_articles LIMIT 10`
4. Hit endpoint: `GET http://localhost:5000/api/news` — expect JSON array
5. Hit with filter: `GET http://localhost:5000/api/news?carrier=pelephone`
6. Start React dev server: `npm run dev` in `mass-market-app/`
7. Open dashboard → click "בחדשות" tab — cards should render
8. Click a card → opens source article in new tab
9. Click a carrier filter pill → cards filter correctly
10. Run `npm run build` — no TypeScript/lint errors
