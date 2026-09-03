---
name: scraper-triage
description: >-
  Diagnose and fix a stale, broken, or silently-dead MOCA scraper - especially
  global eSIM providers, which rot invisibly (rows age instead of vanishing).
  Use whenever the morning digest flags a stale/0-plan carrier, a provider's plans
  look outdated or missing in the UI, a scrape endpoint errors, the user asks
  "הסקרייפר של X עובד?", or when auditing scraper health. Encodes the freshness
  SQL, the standalone-run patterns, the known redesign failure modes, and the full
  provider-retirement checklist.
---

# Scraper Triage (freshness → reproduce → fix or retire)

A broken global scraper returns `[]`, and `save_global_plans` (db.py ~1764) **never
deletes** - so the provider's rows silently AGE in place. esimio was frozen for 2
months and maya for 1 month before anyone noticed. The morning digest now flags
global carriers whose `MAX(scraped_at)` exceeds `morning_check_global_stale_hours`
(72h; domestic/abroad use 36h) - this skill is what to do when it fires.

## 1. Quantify - who is actually stale

```bash
cd "D:\השוואת MASS MARKET" && PYTHONIOENCODING=utf-8 python -c "
import sqlite3
con = sqlite3.connect('data/plans.db')
for c,last,n in con.execute('SELECT carrier, MAX(scraped_at), COUNT(*) FROM global_plans GROUP BY carrier ORDER BY 2'):
    print(f'{c:18} {last}  {n}')
"
```

Interpretation rules:
- `> 72h` old → real problem. A single missed run is tolerated by design.
- **Low row-counts that are NOT breakage** (by-design small catalogs): maya ~8,
  tasim ~2, world8 ~3, pelephone_global ~8, airalo (parent) ~15, travelsim ~10,
  xphone_global ~18. Don't "fix" these.
- Full picture across all tables: `db.get_scrape_freshness()` (db.py ~3652); manual
  digest preview: `GET /api/morning-check/now?api_key=…&send=false`.

## 2. Reproduce standalone - always from a FRESH process

The server may run old code; a fresh `python -c` loads current scraper.py.
Two invocation families (see `scraper.scrape_all_global`, ~line 9856):

**Pure-HTTP scrapers** (signature `(_page=None, usd_rate=None)`; e.g. maya, tasim,
esimo, terminalesim, gigsky, simtlv):

```bash
PYTHONIOENCODING=utf-8 python -c "
import scraper as sc
plans = sc.scrape_maya_global(usd_rate=sc._get_usd_to_ils())
print(len(plans)); print(plans[0] if plans else 'EMPTY')
"
```

**Playwright scrapers** (take a `page`; e.g. airalo, tuki):

```bash
PYTHONIOENCODING=utf-8 python -c "
import scraper as sc
from playwright.sync_api import sync_playwright
sc._ensure_event_loop()
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36')
    plans = sc.scrape_airalo_global(page, sc._get_usd_to_ils())
    print(len(plans)); b.close()
"
```

Empty/exception here confirms the scraper; a healthy standalone run + stale DB means
the scheduled job path is the problem (check Flask logs / whether Flask runs old code).

## 3. Diagnose - the known failure modes (check in this order)

1. **Site redesign killed the extraction point.** Open the source URL and look at
   what the site is NOW. Historical precedents worth imitating:
   - Angular/Next SSR state blob removed → switch to an official data feed if one
     exists (maya: `assets.maya.net/affiliates/plans.json`, auth-free).
   - Site migrated platforms → reuse an existing extractor (esimio moved onto the
     eSIMo Next.js platform; its scrapers now call `_esimo_extract_packages` on the
     RSC-embedded packages JSON).
   - WooCommerce shops → the public Store API `wp-json/wc/store/v1/products`
     (terminalesim, simtlv) beats DOM scraping.
   Preference order: official feed > public JSON API > sitemap+RSC payload >
   Playwright DOM. Pure-HTTP survives redesigns better and runs in the parallel pool.
2. **Bot-blocking** (Incapsula/Cloudflare): needs the stealth session pattern
   (see `scrape_019`) or a different endpoint.
3. **Schema drift**: JSON keys renamed, prices moved to minor units (divide by 100 -
   terminalesim gotcha), currency changed. Verify a sample price against the live site.
4. **Wrong-but-parsing data**: destination names that need `db._DEST_NORM` - fix the
   SCRAPER extraction, not the norm map (papering over HTML entities there causes
   daily extras_change flaps; `_make_global_plan()` already html.unescapes).
5. **Geo-priced currency flip** (gomoworld, 2026-09-03): the site quotes GBP / USD /
   ILS per visitor (cookie `gmw_currency`) and the parser assumed one currency ->
   8,600 phantom `price_change` rows at x1.26 / x3.7 / x0.27 over 2 months, 716 in
   one digest. Signature: a carrier's price_change ratios cluster at an FX rate
   (`SELECT carrier, COUNT(*), AVG(new/old) ... GROUP BY carrier`). Fix = pin the
   currency cookie on the browser context AND parse the symbol in the price line
   (`_parse_gomoworld_plans`); then migrate rows in place with `db.save_global_plans`
   from a fresh process and delete the flap rows (backup first) so the next run is
   silent. Israeli-facing sites with fixed x.99 ILS price points -> store ILS as-is;
   Shopify-style auto-converted ILS -> keep the foreign basis (breez precedent).
6. **Site outage, not a scraper bug**: CloudFront/WAF-fronted sites return an empty
   503 to EVERYONE (xphone 2026-08-31, verified via curl headers + a real browser +
   the Wayback availability API). The xphone scrapers now log `site down (HTTP 5xx)`
   vs `WAF block` - nothing to fix, rows age until the site returns; retire only if
   news/Wayback/socials confirm the company is gone.
7. **BTL regex scrapers die on copy changes** (btl_scrapers.py): tiber went 0 plans
   for 2 weeks when the card CTA changed "להצטרפות" -> "קבלו הצעה". Reproduce with
   `btl_scrapers._fetch_text(url)` and print the text around the first `₪`; persist
   with `db.sync_reseller_plans(rows)` from a fresh process.

## 4. Fix, then validate end-to-end

- Standalone run returns a plausible count (compare to the row counts in step 1) and
  sane fields (`plan_name` with ` – ` separator, `extras[0]` = Hebrew destination,
  price ILS, `data_gb` fraction for MB).
- `python -m py_compile scraper.py`.
- Persist: trigger `GET /api/scrape-global-now?api_key=…` (needs Flask running
  CURRENT code - elevated restart via `schtasks /end /tn CellularComparison` +
  `/run` if scraper.py changed), or wait for the 07:30/17:00 run.
- Re-run the step-1 SQL: the carrier's `MAX(scraped_at)` should be now.
- Expect NO new_plan/removed_plan spam: the 3 global scrape paths in app.py
  (~2302, ~2554, ~6362) drop those change types by design; only
  price/extras/details changes persist.

## 5. Retire instead (provider is defunct)

If the site is gone/pivoted and there's nothing to scrape, retire the provider.
Cleanup checklist (derived from the GlobaleSIM → Terminal eSIM retirement; grep the
old id to catch strays):

- **Labels**: `GLOBAL_LABELS` (carrierLabels.js) + `_CARRIER_NAMES` (app.py) +
  HistoryTab.jsx, ArchivePage.jsx, ExecutiveSummaryPage.jsx, ChatPanel.jsx lists
- **Coverage**: DashboardPage.jsx global-carriers array + MULTI_COUNTRY_CARRIERS +
  globalCountries.js arrays/region maps + ComparePage CARRIER_COUNTRY_LISTS
- **Logos/colors**: providerLogos.js, carrierMeta.js, MarketMoversWidget.jsx,
  AlertsPriceTab.jsx (+ the PNG under public/logos/)
- **Scraper**: remove the fn from `scrape_all_global` (delete or keep the fn dead)
- **Affiliate**: affiliateLinks.js, PlanCard special-cases, SettingsPage commission
  table, config.json affiliate block, /go dispatch branch
- **CRM + coupons**: seed_provider_deals.py row (note "החליף את X" if replaced),
  seed_coupons.py (reassign or deactivate) - rerun both seeds
- **DB rows**: do NOT delete - they age out and stop being served fresh; history stays
- Frontend changes need build + deploy (deploy-live skill); backend needs the
  elevated Flask restart. Update the morning-digest expectations only if the carrier
  was domestic (CARRIER_DISPLAY).
