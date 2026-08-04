---
name: new-global-provider
description: >-
  End-to-end checklist for integrating a NEW global eSIM provider into MOCA (or
  auditing/retiring an existing one). Use whenever the user wants to add, onboard,
  or "תוסיף ספק" a global eSIM brand, replace one provider with another, asks why a
  provider is missing a logo/label/coverage/banner somewhere, or after writing a new
  global scraper. There are ~10 hand-maintained registration points across
  scraper.py, app.py, and the React app - missing one produces a silent gap (bare
  chips, dead /go links, no banner, no CRM row). This skill enumerates all of them,
  keyed to how gigsky (2026-07) was wired.
---

# New Global Provider - the full wiring checklist

Adding a provider is never just "write the scraper". The registries below are
hand-maintained and DON'T warn when a provider is missing - the symptom is a bare
gray chip, a dead redirect, or a provider invisible in one tab. Work through the
list in order; `gigsky` is the newest complete reference (grep it to see every spot).

## A. The scraper (scraper.py)

1. Write `scrape_<id>_global(...)`. Prefer **pure-HTTP** (official feed > public
   JSON API > sitemap/RSC payload > Playwright DOM) - it survives redesigns and runs
   in the parallel pool. Use `_make_global_plan()` for every plan dict; `extras[0]`
   must be the canonical Hebrew destination (match spellings in globalCountries.js,
   else add a `db._DEST_NORM` entry only for genuinely-variant spellings).
2. Register it in `scrape_all_global()` (~line 9856): append to `parallel_jobs`
   (~9884) if it builds its own HTTP/browser, or `sequential_jobs` (~9871) if it
   shares the main Playwright page. Entry shape: `("scrape_<id>_global", lambda: ...)`.
3. Add the homepage to `GLOBAL_BANNER_URLS` (~10988) so `/esim-banners` screenshots it.

## B. Mandatory registrations (all hand-edited)

| # | Where | What |
|---|---|---|
| 1 | `carrierLabels.js` → `GLOBAL_PROVIDERS_REGISTRY` (~line 62) | ONE row (`id, label, color, chartColor, israeli, aliases`) - GLOBAL_LABELS/COLORS/CHART_COLORS/PROVIDERS/ISRAELI_* all derive from it |
| 2 | `app.py` → `_HISTORY_CARRIER_NAMES` (~2654) | Hebrew name for history/changes views |
| 3 | `app.py` → `_CARRIER_NAMES` (~4155) | Hebrew name for the AI-chat context |
| 4 | `app.py` → `_GUEST_PROVIDER_META` (~1043) | label/color/url/domain - drives guest-portal chips, /go fallback URL, favicon. Missing here = bare chip + dead /go |
| 5 | `carrierMeta.js` → `CARRIER_LOGOS` (~49) | dashboard logo path `/logos/<id>.png` |
| 6 | `providerLogos.js` → `PROVIDER_LOGOS` (~15) | square chip logo for the public compare page + guest portal |
| 7 | `mass-market-app/public/logos/<id>.png` | the actual asset (get a clean square logo) |

Three logo spots (5-7) - forgetting one was the original GigSky gotcha.

## C. Coverage plumbing (only for multi-country/regional plans)

If the provider sells regional/global bundles (one plan covering many countries):

1. `globalCountries.js`: per-region Hebrew country arrays + an exported
   `<ID>_REGION_MAP` (GigSky pattern ~504-514), and a branch in
   `getCountriesForPlan()` (~527, gigsky at ~889).
2. `DashboardPage.jsx`: import the map (~46), add the id to
   `MULTI_COUNTRY_CARRIERS` (~50), add a branch in `getPlanCoverage()` (~66).
3. `ComparePage.jsx`: import the global list (~17), add to
   `CARRIER_COUNTRY_LISTS` (~198).

Per-country-only providers skip this whole section (extras[0] does the filtering).

## D. Conditional registrations

- **Cruise packages** → add the provider's cruise labels to `db._CRUISE_SOURCE_DESTS`
  (~932) so they fold into the synthetic "קרוז" destination.
- **Affiliate link exists** → run the **affiliate-link-wiring** skill (config.json
  `affiliate.<id>`, /go dispatch branch, affiliateLinks.js, verification).
- **Coupon exists** → seed_coupons.py row + `python seed_coupons.py`.
- **Always**: CRM row in seed_provider_deals.py (NOT CONTACTED section unless a deal
  exists; id must equal the registry id) + `python seed_provider_deals.py` - the
  provider-status-sync skill covers field semantics. Exception: Pelephone brands
  (Tuki, GlobalSIM) get no CRM row.
- **New destinations** the catalog introduces → rerun
  `scripts/gen_dest_backgrounds.py` (needs Flask on :5000, node, gemini_api_key);
  curation overrides in `scripts/dest_bg_map.json`. Existing destinations need nothing.

## E. Automatic - do NOT add registrations for these

- Freshness monitoring: the morning digest picks up any carrier with rows in
  `global_plans` automatically (72h staleness threshold).
- `/api/esim/destinations` + `/api/esim/compare`: data-driven from `global_plans`,
  no allow-list.
- Change-detection: global paths drop new_plan/removed_plan by design; don't expect
  a "new provider" Telegram flood.

## F. Verify & ship

1. Standalone scrape from a fresh process (see the scraper-triage skill for the
   exact patterns) - plausible plan count, Hebrew destinations, ILS prices,
   ` – ` name separator (Orbit-style ` - ` only if BiDi requires).
2. `python -m py_compile scraper.py app.py` and `cd mass-market-app && npm run build`.
3. Trigger `GET /api/scrape-global-now?api_key=…` after the **elevated Flask
   restart** (`schtasks /end /tn CellularComparison` + `/run`) so the server runs
   the new code.
4. Spot-check in the UI: dashboard גלובלי tab (chip + logo + label), destination
   filter (coverage), /esim-deals (provider appears with logo), /admin/deals (CRM
   row), /esim-banners (after the next 08:00 banner run or a manual trigger).
5. Deploy the frontend (deploy-live skill).
6. Grep the new id across the repo and compare against gigsky's ~14 files - any
   registry gigsky appears in that the new provider doesn't, justify or fix.

## Retiring / replacing a provider

Run the same list in reverse - the cleanup checklist lives in the
**scraper-triage** skill (section 5), derived from the GlobaleSIM → Terminal eSIM
retirement. DB rows are never deleted; they age out.
