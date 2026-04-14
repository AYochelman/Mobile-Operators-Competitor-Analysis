# Travel Sim Integration — Design Spec
**Date:** 2026-04-11  
**Status:** Approved by user

---

## Overview
Add Travel Sim (travelsimobile.co.il) as a new global eSIM provider in the **eSIM גלובלי** tab.  
Travel Sim is a pure abroad/travel eSIM product — it has no Israeli domestic service.  
Badge color: **teal/cyan**.

---

## Plans (10 total — voice add-ons excluded)

### Zone 123 — Global (144 countries) — 6 individual PlanCards

| plan_name      | price | data_gb | minutes | days | extras                                 |
|----------------|-------|---------|---------|------|----------------------------------------|
| Travel Mini    | 19    | 1       | null    | 4    | []                                     |
| Travel Lite    | 59    | 6       | 15      | 7    | ["השבועית שלנו!"]                       |
| Travel Plus    | 69    | 7       | 30      | 14   | []                                     |
| Travel Max     | 99    | 20      | 100     | 30   | ["הפופולרית שלנו!"]                     |
| Travel Ultra   | 139   | 30      | 30      | 45   | []                                     |
| Travel Long    | 49    | 1       | null    | 1095 | ["יתרה נשמרת לנסיעות הבאות"]           |

- `extras[0]` = **null/empty** — no destination filter, shown as individual PlanCards
- `esim = True` on all
- `currency = 'ILS'`, `original_price = None`, `sms = None`

### Zone 1 — ארה"ב / קנדה / איחוד האמירויות (3 countries) — 1 GroupedPlanCard

| plan_name      | price | data_gb | minutes | days | extras              |
|----------------|-------|---------|---------|------|---------------------|
| Travel USA     | 89    | 30      | 30      | 14   | ["ארה\"ב"]          |
| Travel USA     | 99    | 70      | 100     | 30   | ["ארה\"ב"]          |

- `extras[0] = 'ארה"ב'` → groups into one GroupedPlanCard (destination: ארה"ב)
- `esim = True` on both

### Zone 6 — מזרח התיכון (5 countries) — 1 GroupedPlanCard

| plan_name            | price | data_gb | minutes | days | extras                  |
|----------------------|-------|---------|---------|------|-------------------------|
| Middle East 1GB      | 89    | 1       | null    | 30   | ["המזרח התיכון"]        |
| Middle East 5GB      | 189   | 5       | null    | 30   | ["המזרח התיכון"]        |

- `extras[0] = 'המזרח התיכון'` → already in `KNOWN_REGIONS` → appears in region filter pills

---

## Display Logic

- **Zone 123 plans**: No `extras[0]`, so each falls into `singles` in the displayItems logic → individual `PlanCard`
- **Zone 1 + Zone 6 plans**: Grouped by `carrier|extras[0]` key → `GroupedPlanCard` with GB picker
- **Deduplication**: Travel USA has 30GB and 70GB → two pills. Middle East has 1GB and 5GB → two pills.
- **Country modal button**: All plans show "מדינות (N) ←" via `getCountriesForPlan()`

### Country modal matching logic (globalCountries.js)
```javascript
if (carrier === 'travelsim') {
  if (!extras || !extras[0]) return { title: 'Travel Sim — מדינות כלולות (144)', countries: COUNTRIES_TRAVELSIM_GLOBAL }
  if (extras[0] === 'ארה"ב') return { title: 'Travel Sim — ארה"ב / קנדה / איחוד האמירויות', countries: COUNTRIES_TRAVELSIM_USA }
  if (extras[0] === 'המזרח התיכון') return { title: 'Travel Sim — מזרח התיכון', countries: COUNTRIES_TRAVELSIM_ME }
}
```

### Country lists
- **COUNTRIES_TRAVELSIM_USA** (3): ארצות הברית, קנדה, איחוד האמירויות הערביות
- **COUNTRIES_TRAVELSIM_ME** (5): ירדן, מצרים (דרום סיני בלבד), עומאן, ערב הסעודית, קטאר
- **COUNTRIES_TRAVELSIM_GLOBAL** (144): full list — Zone 12 (99 countries) + Zone 123 additions (45 countries)

---

## Files Changed

### 1. `scraper.py`
- Add `scrape_travelsim()` — static scraper returning 10 plans via `_make_global_plan()`
- Add to `scrape_all()` global section

### 2. `mass-market-app/src/components/PlanCard.jsx`
- `GLOBAL_LABELS`: `travelsim: 'Travel Sim'`
- `GLOBAL_COLORS`: `travelsim: 'teal'`
- `CARRIER_LOGOS`: `travelsim: '/logos/travelsim.png'`
- `LOGO_SIZES`: no special size (use default 32px) unless logo looks small — evaluate after download

### 3. `mass-market-app/src/components/GroupedPlanCard.jsx`
- Same additions as PlanCard.jsx

### 4. `mass-market-app/src/data/globalCountries.js`
- Add 3 country arrays: `COUNTRIES_TRAVELSIM_GLOBAL`, `COUNTRIES_TRAVELSIM_USA`, `COUNTRIES_TRAVELSIM_ME`
- Update `getCountriesForPlan()` with travelsim block

### 5. `mass-market-app/src/pages/DashboardPage.jsx`
- Add `{ id: 'travelsim', label: 'Travel Sim' }` to `GLOBAL_PROVIDERS`
- Add `travelsim: 'Travel Sim'` to `CARRIER_HEB` in exportToExcel

### 6. `mass-market-app/public/logos/travelsim.png`
- Download from https://travelsimobile.co.il (find logo asset URL)

---

## Notes
- Travel Long (1GB, 3-year validity): `days=1095`, extra = "יתרה נשמרת לנסיעות הבאות". Will dedup with Travel Mini (1GB, 4 days) if both appear in the same grouped card — but they don't: they both have `extras[0]=null`, so they're individual PlanCards. No conflict.
- No `DashboardPage.jsx` grouping logic changes needed — existing logic already groups any global plans sharing `carrier|extras[0]`
- Middle East: Egypt displayed as "מצרים (דרום סיני בלבד)" in countries list to reflect the restriction
