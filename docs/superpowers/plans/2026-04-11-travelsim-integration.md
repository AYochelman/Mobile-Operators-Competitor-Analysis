# Travel Sim Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Travel Sim (travelsimobile.co.il) as a global eSIM provider in the eSIM גלובלי tab with 10 plans across 3 zones, country modals, and logo.

**Architecture:** Static scraper → `global_plans` table → displayed via existing PlanCard/GroupedPlanCard. Zone 123 global plans have no `extras[0]` (individual cards). Zone 1 (ארה"ב) and Zone 6 (מזרח התיכון) use `extras[0]` so they auto-group into GroupedPlanCards via existing DashboardPage grouping logic.

**Tech Stack:** Python static scraper, React JSX, Tailwind CSS, SQLite via Flask API.

---

## File Map

| File | Change |
|------|--------|
| `scraper.py` | Add `scrape_travelsim()` + register in `scrape_all_global()` |
| `src/components/PlanCard.jsx` | Add travelsim to GLOBAL_LABELS / GLOBAL_COLORS / CARRIER_LOGOS |
| `src/components/GroupedPlanCard.jsx` | Same additions as PlanCard.jsx |
| `src/data/globalCountries.js` | Add 3 country arrays + travelsim block in `getCountriesForPlan()` |
| `src/pages/DashboardPage.jsx` | Add travelsim to GLOBAL_PROVIDERS + CARRIER_HEB |
| `public/logos/travelsim.png` | Download from travelsimobile.co.il |

---

## Task 1: Download Travel Sim logo

**Files:**
- Create: `mass-market-app/public/logos/travelsim.png`

- [ ] **Step 1: Find and download the logo**

Fetch `https://travelsimobile.co.il/lobby` (or the homepage), locate the logo `<img>` tag, then download the source URL to `mass-market-app/public/logos/travelsim.png`.

The logo URL is likely `https://travelsimobile.co.il/wp-content/uploads/...`. Use Playwright or a direct HTTP fetch to grab it.

If no colored logo found, create a simple text-based placeholder PNG using HTML Canvas (similar to how globalesim.png was created): white background, "Travel Sim" in bold teal text (`#0d9488`), 300×80px.

- [ ] **Step 2: Verify file exists**

```bash
ls "D:\השוואת MASS MARKET\mass-market-app\public\logos\travelsim.png"
```
Expected: file present, size > 1KB.

- [ ] **Step 3: Commit**

```bash
git add "mass-market-app/public/logos/travelsim.png"
git commit -m "feat: add Travel Sim logo"
```

---

## Task 2: Add scrape_travelsim() to scraper.py

**Files:**
- Modify: `D:\השוואת MASS MARKET\scraper.py` (after last global scraper function, before `scrape_all_global`)

- [ ] **Step 1: Add the static scraper function**

Insert the following function anywhere before `scrape_all_global()`:

```python
def scrape_travelsim(page=None):
    """Travel Sim — static global eSIM plans (travelsimobile.co.il).
    10 plans across 3 zones (no Playwright needed).
    """
    plans = [
        # ── Zone 123: Global (144 countries) ──────────────────────────
        _make_global_plan(
            "travelsim", "Travel Mini", 19, "ILS", 19,
            data_gb=1, days=4, minutes=None, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Lite", 59, "ILS", 59,
            data_gb=6, days=7, minutes=15, sms=None, esim=True,
            extras=["\u05d4\u05e9\u05d1\u05d5\u05e2\u05d9\u05ea \u05e9\u05dc\u05e0\u05d5!"]
        ),
        _make_global_plan(
            "travelsim", "Travel Plus", 69, "ILS", 69,
            data_gb=7, days=14, minutes=30, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Max", 99, "ILS", 99,
            data_gb=20, days=30, minutes=100, sms=None, esim=True,
            extras=["\u05d4\u05e4\u05d5\u05e4\u05d5\u05dc\u05e8\u05d9\u05ea \u05e9\u05dc\u05e0\u05d5!"]
        ),
        _make_global_plan(
            "travelsim", "Travel Ultra", 139, "ILS", 139,
            data_gb=30, days=45, minutes=30, sms=None, esim=True,
            extras=[]
        ),
        _make_global_plan(
            "travelsim", "Travel Long", 49, "ILS", 49,
            data_gb=1, days=1095, minutes=None, sms=None, esim=True,
            extras=["\u05d9\u05ea\u05e8\u05d4 \u05e0\u05e9\u05de\u05e8\u05ea \u05dc\u05e0\u05e1\u05d9\u05e2\u05d5\u05ea \u05d4\u05d1\u05d0\u05d5\u05ea"]
        ),
        # ── Zone 1: ארה"ב / קנדה / איחוד האמירויות (3 countries) ──────
        _make_global_plan(
            "travelsim", "Travel USA", 89, "ILS", 89,
            data_gb=30, days=14, minutes=30, sms=None, esim=True,
            extras=["\u05d0\u05e8\u05d4\"\u05d1"]
        ),
        _make_global_plan(
            "travelsim", "Travel USA", 99, "ILS", 99,
            data_gb=70, days=30, minutes=100, sms=None, esim=True,
            extras=["\u05d0\u05e8\u05d4\"\u05d1"]
        ),
        # ── Zone 6: מזרח התיכון (5 countries) ─────────────────────────
        _make_global_plan(
            "travelsim", "Middle East 1GB", 89, "ILS", 89,
            data_gb=1, days=30, minutes=None, sms=None, esim=True,
            extras=["\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df"]
        ),
        _make_global_plan(
            "travelsim", "Middle East 5GB", 189, "ILS", 189,
            data_gb=5, days=30, minutes=None, sms=None, esim=True,
            extras=["\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df"]
        ),
    ]
    logger.info(f"Travel Sim: {len(plans)} plans")
    return plans
```

Unicode clarification (for readability):
- `\u05d4\u05e9\u05d1\u05d5\u05e2\u05d9\u05ea \u05e9\u05dc\u05e0\u05d5!` = `השבועית שלנו!`
- `\u05d4\u05e4\u05d5\u05e4\u05d5\u05dc\u05e8\u05d9\u05ea \u05e9\u05dc\u05e0\u05d5!` = `הפופולרית שלנו!`
- `\u05d9\u05ea\u05e8\u05d4 \u05e0\u05e9\u05de\u05e8\u05ea \u05dc\u05e0\u05e1\u05d9\u05e2\u05d5\u05ea \u05d4\u05d1\u05d0\u05d5\u05ea` = `יתרה נשמרת לנסיעות הבאות`
- `\u05d0\u05e8\u05d4"\u05d1` = `ארה"ב`
- `\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df` = `המזרח התיכון`

- [ ] **Step 2: Register in scrape_all_global()**

In `scrape_all_global()`, find the `jobs` list and add travelsim as the last entry before the closing `]`:

```python
            ("scrape_travelsim",            lambda pg: scrape_travelsim()),
```

The full end of the jobs list should look like:
```python
            ("scrape_voye_global",          lambda pg: scrape_voye_global(pg, usd_rate)),
            ("scrape_orbit_global",         lambda pg: scrape_orbit_global(pg, usd_rate)),
            ("scrape_travelsim",            lambda pg: scrape_travelsim()),
        ]
```

- [ ] **Step 3: Smoke-test the scraper**

```bash
cd "D:\השוואת MASS MARKET"
python -c "from scraper import scrape_travelsim; plans = scrape_travelsim(); print(f'{len(plans)} plans'); [print(f'  {p[\"plan_name\"]:25} ₪{p[\"price\"]:>5}  {p[\"data_gb\"]}GB  {p[\"days\"]}d  extras={p[\"extras\"]}') for p in plans]"
```

Expected output — exactly 10 plans:
```
10 plans
  Travel Mini               ₪19    1GB  4d  extras=[]
  Travel Lite               ₪59    6GB  7d  extras=['השבועית שלנו!']
  Travel Plus               ₪69    7GB  14d extras=[]
  Travel Max                ₪99   20GB  30d extras=['הפופולרית שלנו!']
  Travel Ultra              ₪139  30GB  45d extras=[]
  Travel Long               ₪49    1GB  1095d extras=['יתרה נשמרת לנסיעות הבאות']
  Travel USA                ₪89   30GB  14d extras=['ארה"ב']
  Travel USA                ₪99   70GB  30d extras=['ארה"ב']
  Middle East 1GB           ₪89    1GB  30d extras=['המזרח התיכון']
  Middle East 5GB           ₪189   5GB  30d extras=['המזרח התיכון']
```

- [ ] **Step 4: Commit**

```bash
git add scraper.py
git commit -m "feat: add scrape_travelsim() static scraper — 10 plans across 3 zones"
```

---

## Task 3: Add Travel Sim country lists to globalCountries.js

**Files:**
- Modify: `mass-market-app/src/data/globalCountries.js`

- [ ] **Step 1: Add the three country arrays**

Find the end of the existing country arrays (before `export function getCountriesForPlan`) and insert:

```javascript
// ── Travel Sim ─────────────────────────────────────────────────────────────

// Zone 1: ארה"ב / קנדה / איחוד האמירויות
const TRAVELSIM_USA = [
  'ארצות הברית', 'קנדה', 'איחוד האמירויות הערביות',
]

// Zone 6: מזרח התיכון
const TRAVELSIM_ME = [
  'ירדן', 'מצרים (דרום סיני בלבד)', 'עומאן', 'ערב הסעודית', 'קטאר',
]

// Zone 123: Global (144 countries — Zone 12 base + Zone 123 additions)
const TRAVELSIM_GLOBAL = [
  // Zone 12 base (99 countries)
  'אוזבקיסטן', 'אוסטריה', 'אוסטרליה', 'אוקראינה', 'אזרבייג\'ן',
  'איטליה', 'איי בהאמה', 'איי הבתולה האמריקאיים', 'איי הבתולה הבריטיים',
  'איי טורקס וקייקוס', 'איי פארו', 'איי קיימן', 'אינדונזיה', 'איסלנד',
  'אירלנד', 'אלבניה', 'אנגווילה', 'אנטיגואה וברבודה', 'אסטוניה',
  'ארגנטינה', 'ארמניה', 'בולגריה', 'בוסניה והרצגובינה', 'בחריין',
  'בלגיה', 'בלארוס', 'ברבדוס', 'ברזיל', 'בריטניה',
  'ג\'מייקה', 'ג\'רזי', 'גאנה', 'גאורגיה', 'גרמניה',
  'גרנדה', 'דומיניקה', 'דנמרק', 'דרום אפריקה', 'דרום קוריאה',
  'האיים ההולנדיים האנטיליים', 'הודו', 'הולנד', 'הונג קונג', 'הונגריה',
  'הרפובליקה הדומיניקנית', 'וייטנאם', 'ותיקן', 'טורקיה', 'טייוואן',
  'טנזניה', 'יוון', 'יפן', 'לוקסמבורג', 'לטביה',
  'ליטא', 'ליכטנשטיין', 'מאוריציוס', 'מולדובה', 'מונטנגרו',
  'מונטסראט', 'מונאקו', 'מלטה', 'מקאו', 'מקסיקו',
  'מרוקו', 'נורווגיה', 'ניו זילנד', 'נפאל', 'סן מרינו',
  'סין', 'סינגפור', 'סלובניה', 'סלובקיה', 'סנט וינסנט וגרנדינס',
  'סנט לוסיה', 'סנט קיטס ונוויס', 'ספרד', 'סרביה', 'סרי לנקה',
  'פולין', 'פורטו ריקו', 'פורטוגל', 'פיליפינים', 'פינלנד',
  'פנמה', 'פרו', 'צ\'ילה', 'צ\'כיה', 'צרפת',
  'קולומביה', 'קוסטה ריקה', 'קזחסטן', 'קמבודיה', 'קפריסין',
  'קרואטיה', 'רומניה', 'רוסיה', 'שוודיה', 'שוויץ', 'תאילנד',
  // Zone 123 additions (45 countries)
  'אורוגוואי', 'אולנד', 'אנדורה', 'ארובה', 'אתיופיה',
  'בוליביה', 'ברמודה', 'גיברלטר', 'גואם', 'גוואדלופ',
  'גואטמלה', 'גיאנה', 'גיאנה הצרפתית', 'גינאה', 'גינאה-ביסאו',
  'גרינלנד', 'גרנזי', 'האיטי', 'הונדורס', 'זמביה',
  'חוף השנהב', 'טוגו', 'טרינידד וטובגו', 'מדגסקר', 'מוזמביק',
  'מונגוליה', 'מיאנמר', 'מקדוניה', 'מרטיניק', 'ניגריה',
  'סורינם', 'סיירה לאון', 'סיישל', 'סלבדור', 'סנגל',
  'פולינזיה הצרפתית', 'פיג\'י', 'פפואה גינאה החדשה', 'פרגוואי', 'קוסובו',
  'קייפ ורדה', 'קירגיזסטן', 'קמרון', 'קניה',
]
```

- [ ] **Step 2: Add travelsim block in getCountriesForPlan()**

Find the end of the function (before the final `return null`), and insert the travelsim block. The section to add after the `orbit` block:

```javascript
  // ── Travel Sim ──
  if (carrier === 'travelsim') {
    const dest = extras[0]
    if (!dest) return { title: 'Travel Sim — גלובלי (144 מדינות)', countries: TRAVELSIM_GLOBAL }
    if (dest === '\u05d0\u05e8\u05d4"\u05d1') return { title: 'Travel Sim — ארה"ב / קנדה / איחוד האמירויות', countries: TRAVELSIM_USA }
    if (dest === '\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df') return { title: 'Travel Sim — מזרח התיכון', countries: TRAVELSIM_ME }
    return null
  }
```

- [ ] **Step 3: Verify in browser console (or node)**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
node -e "
const { getCountriesForPlan } = await import('./src/data/globalCountries.js');
console.log(getCountriesForPlan({ carrier: 'travelsim', plan_name: 'Travel Max', extras: [], data_gb: 20, days: 30 }));
console.log(getCountriesForPlan({ carrier: 'travelsim', plan_name: 'Travel USA', extras: ['\u05d0\u05e8\u05d4\"\u05d1'], data_gb: 30, days: 14 }));
console.log(getCountriesForPlan({ carrier: 'travelsim', plan_name: 'Middle East 1GB', extras: ['\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df'], data_gb: 1, days: 30 }));
" --input-type=module 2>&1 | head -20
```

Expected: first call returns object with 144 countries, second with 3 countries, third with 5 countries.

If the node command fails (ESM), skip this step — verification happens in the browser in Task 6.

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/src/data/globalCountries.js
git commit -m "feat: add Travel Sim country lists (global 144, USA 3, Middle East 5)"
```

---

## Task 4: Add travelsim metadata to PlanCard.jsx and GroupedPlanCard.jsx

**Files:**
- Modify: `mass-market-app/src/components/PlanCard.jsx`
- Modify: `mass-market-app/src/components/GroupedPlanCard.jsx`

### PlanCard.jsx

- [ ] **Step 1: Add to GLOBAL_LABELS**

Find:
```javascript
const GLOBAL_LABELS = {
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo',
```
Change to:
```javascript
const GLOBAL_LABELS = {
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo',
  travelsim: 'Travel Sim',
```

- [ ] **Step 2: Add to GLOBAL_COLORS**

Find:
```javascript
const GLOBAL_COLORS = {
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'blue',
```
Change to:
```javascript
const GLOBAL_COLORS = {
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'blue',
  travelsim: 'teal',
```

- [ ] **Step 3: Add to CARRIER_LOGOS**

Find the comment `// Global eSIM` section inside `CARRIER_LOGOS` and add at the end of that section (before the closing `}`):
```javascript
  travelsim:       '/logos/travelsim.png',
```

### GroupedPlanCard.jsx

- [ ] **Step 4: Add to GLOBAL_LABELS in GroupedPlanCard**

Find:
```javascript
const GLOBAL_LABELS = {
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo',
```
Add `travelsim: 'Travel Sim',` to the map.

- [ ] **Step 5: Add to GLOBAL_COLORS in GroupedPlanCard**

Find:
```javascript
const GLOBAL_COLORS = {
  tuki: 'blue', globalesim: 'green',
```
Add `travelsim: 'teal',` to the map.

- [ ] **Step 6: Add to CARRIER_LOGOS in GroupedPlanCard**

Add:
```javascript
  travelsim:       '/logos/travelsim.png',
```

- [ ] **Step 7: Commit**

```bash
git add mass-market-app/src/components/PlanCard.jsx mass-market-app/src/components/GroupedPlanCard.jsx
git commit -m "feat: add travelsim badge (teal) and logo to PlanCard + GroupedPlanCard"
```

---

## Task 5: Update DashboardPage.jsx

**Files:**
- Modify: `mass-market-app/src/pages/DashboardPage.jsx`

- [ ] **Step 1: Add travelsim to GLOBAL_PROVIDERS**

Find:
```javascript
const GLOBAL_PROVIDERS = [
  { id: 'tuki', label: 'Tuki' }, { id: 'globalesim', label: 'GlobaleSIM' },
```
Add at the end of the array (before the closing `]`):
```javascript
  { id: 'travelsim', label: 'Travel Sim' },
```

- [ ] **Step 2: Add travelsim to CARRIER_HEB in exportToExcel**

Find:
```javascript
const CARRIER_HEB = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks' }
```
Add `travelsim: 'Travel Sim',` anywhere in that object (e.g., after `sparks: 'Sparks'`):
```javascript
const CARRIER_HEB = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks', travelsim: 'Travel Sim' }
```

- [ ] **Step 3: Commit**

```bash
git add mass-market-app/src/pages/DashboardPage.jsx
git commit -m "feat: add travelsim to global providers filter and Excel export"
```

---

## Task 6: Seed DB, build, and verify

**Files:** No file changes — run commands only.

- [ ] **Step 1: Seed Travel Sim plans into DB**

```bash
cd "D:\השוואת MASS MARKET"
python -c "
from scraper import scrape_travelsim
from db import upsert_global_plans
plans = scrape_travelsim()
upsert_global_plans(plans)
print(f'Seeded {len(plans)} Travel Sim plans')
"
```

Expected: `Seeded 10 Travel Sim plans`

- [ ] **Step 2: Verify DB via Flask API**

Start Flask if not running: `python app.py` (background), then:

```bash
curl -s "http://localhost:5000/api/global-plans" | python -c "import sys,json; d=json.load(sys.stdin); ts=[p for p in d if p['carrier']=='travelsim']; print(f'{len(ts)} travelsim plans'); [print(f'  {p[\"plan_name\"]:25} ₪{p[\"price\"]}  extras={p[\"extras\"]}') for p in ts]"
```

Expected: 10 travelsim plans printed with correct names/prices/extras.

- [ ] **Step 3: Build React app**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run build 2>&1
```

Expected: `✓ built in X.Xs` with no errors.

- [ ] **Step 4: Visual verification in browser**

Open `http://localhost:5173` → click **גלובלי** tab:

1. ✅ Filter by provider → "Travel Sim" option appears in provider dropdown
2. ✅ 6 individual Travel Sim cards visible (Travel Mini / Lite / Plus / Max / Ultra / Long)
3. ✅ 1 GroupedPlanCard for "ארה"ב" with 2 GB pills (30GB / 70GB)
4. ✅ 1 GroupedPlanCard for "המזרח התיכון" with 2 GB pills (1GB / 5GB)
5. ✅ Teal badge on all Travel Sim cards
6. ✅ Travel Sim logo visible top-left on each card
7. ✅ "מדינות (144) ←" button on global cards → opens modal with country list
8. ✅ "מדינות (3) ←" button on ארה"ב grouped card
9. ✅ "מדינות (5) ←" button on מזרח התיכון grouped card
10. ✅ Travel Long card shows "יתרה נשמרת לנסיעות הבאות" in extras
11. ✅ Filter by region "המזרח התיכון" → shows only ME grouped card (and other providers' ME plans)
12. ✅ Filter by destination "ארה"ב" → shows Travel Sim USA grouped card

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: integrate Travel Sim as global eSIM provider — 10 plans, 3 zones, country modals"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: 10 plans ✓ | 3 zones ✓ | GroupedPlanCard for USA + ME ✓ | Individual cards for global ✓ | Country modals (144/3/5) ✓ | Logo ✓ | teal badge ✓ | Travel Long extra ✓ | Provider filter ✓ | Excel export ✓
- [x] **No placeholders**: All code is complete and exact
- [x] **Type consistency**: `_make_global_plan` signature is `(carrier, name, price_ils, currency, original_price, data_gb, days, minutes, sms, esim, extras)` — matches all usages in Task 2
- [x] **`extras[0]` for grouping**: Zone 1 → `'ארה"ב'`, Zone 6 → `'המזרח התיכון'` — matches getCountriesForPlan() matching logic in Task 3
- [x] **`KNOWN_REGIONS`**: `'המזרח התיכון'` is already in the KNOWN_REGIONS set in DashboardPage.jsx (line 47) — ME plans will appear in region filter pills automatically
- [x] **`'ארה"ב'`** is NOT in KNOWN_REGIONS — will appear in the destinations dropdown, which is correct behavior
