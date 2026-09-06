---
name: plan-terms-coverage
description: >-
  Ensure every cellular plan in MOCA exposes its "עיקרי התוכנית" / "תנאי התוכנית"
  (plan terms/details — a PDF link or an in-app info modal). Use whenever a NEW plan
  appears from any carrier (domestic or roaming), after a scrape adds plans, when a
  plan's terms button is missing/empty, or when auditing terms coverage. Encodes the
  per-provider method for fetching terms ("the logic from past experience") and the
  wire-in procedure so new plans get their terms automatically.
---

# Plan Terms ("עיקרי התוכנית") Coverage

Every plan card in MOCA (`mass-market-app/src/components/PlanCard.jsx`) shows a
terms/details affordance. When a carrier adds a **new plan**, that affordance can come
up empty if nobody captured the terms for it. This skill is the runbook for **detecting
that gap and closing it the way each provider expects** — based on how the existing
scrapers already do it.

**Automated trigger:** `alert_missing_terms()` in notifier.py (~line 496) is the
post-scrape safety net - when a NEW domestic/roaming plan lands with no
`url`/`terms_url`/`__info__`, it Telegrams the operator. When the user brings such an
alert (or mentions a plan whose terms button is empty), this skill is the runbook.
The alert already exempts neptucom domestic + xphone roaming (no terms by design -
matching the "static"/"none" rows in the methodology table below), so any alert it
sends is actionable.

## The 3 mechanisms (how a card shows terms)

PlanCard resolves terms in this order (see PlanCard.jsx ~lines 290–340, 600–660):

1. **`terms_url`** (roaming, `abroad_plans` table) or **`url`** (domestic, `plans` table)
   — a scraped link to a terms PDF / terms page. **Preferred** (`detailsUrl = plan.terms_url || …`).
   Button label: **"עיקרי התוכנית"** (PDF link).
2. **`PLAN_DETAILS_PDFS[carrier][plan_name]`** — a hardcoded fallback map in PlanCard.jsx
   (~line 183). Used only when `terms_url`/`url` is null. Button label: **"עיקרי התוכנית"**.
3. **`__info__|<lines>`** marker inside the `extras` array — rendered as an **in-app modal**
   (no PDF needed). Button label: **"תנאי התוכנית"** (or "עיקרי התוכנית" for 019 roaming).
   `label|https://…` lines inside become clickable links.

**Goal:** every plan resolves to at least one of these. The robust fix is almost always
**mechanism 1 captured automatically by the scraper** — so future new plans need no manual
edit. The hardcoded map (2) is a stopgap; `__info__` (3) is for providers with no PDF.

## Step 1 — Audit: find plans missing terms

Run this from the repo root (`D:\השוואת MASS MARKET`). It flags every current plan with no
terms by any mechanism. Keep the `PLAN_DETAILS_PDFS` key-sets in sync with PlanCard.jsx.

```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
import sqlite3
con = sqlite3.connect('data/plans.db'); con.row_factory = sqlite3.Row; cur = con.cursor()
# Mirror PLAN_DETAILS_PDFS keys from PlanCard.jsx for the MAP-only roaming carriers.
MAP = {
 'partner': {'חבילת המונדיאל','חו"ל ספיישל','חו"ל Connect','חו"ל בסטייל','חו"ל מושלמת',
             'חופשה משפחתית','חו"ל בגדול','חופשה משפחתית בגדול'},
 'pelephone': {'מונדיאל 2026','חבילת חו"ל קטנה','שומרים על קשר',
             'חבילת חו"ל למצרים (טאבה, נואיבה, דאהב, שארם א-שייח)','חבילת special גלישה ב-MB',
             'חבילת special+ גלישה ב-MB','מושלמת','חו"ל מושלמת L','ביג אמריקה לארה"ב (כולל קנדה)',
             'חו"ל משפחתית','חו"ל מושלמת XL','חו"ל מושלמת 45 יום','חו"ל מושלמת 60 יום'},
}
info = lambda e: bool(e) and '__info__' in e
miss = 0
for r in cur.execute('SELECT carrier,plan_name,url,extras FROM plans'):
    if not (r['url'] or info(r['extras'])):
        miss += 1; print('DOMESTIC MISS |', r['carrier'], '|', r['plan_name'])
for r in cur.execute('SELECT carrier,plan_name,terms_url,extras FROM abroad_plans'):
    if not (r['terms_url'] or info(r['extras']) or r['plan_name'] in MAP.get(r['carrier'], set())):
        miss += 1; print('ROAMING  MISS |', r['carrier'], '|', r['plan_name'])
print('TOTAL MISSING:', miss); con.close()
PY
```

To see only what was **newly added recently** (so you can act right after a scrape):

```bash
PYTHONIOENCODING=utf-8 python -c "
import sqlite3; con=sqlite3.connect('data/plans.db')
for t in ('changes','abroad_changes'):
    print('==',t); 
    for c,n,d in con.execute(f\"SELECT carrier,plan_name,changed_at FROM {t} WHERE change_type='new_plan' AND changed_at>=date('now','-30 day') ORDER BY changed_at DESC\"):
        print(' ',d[:10],c,n)
"
```

Global eSIM (`global_plans`) and resellers/content are **out of scope** — globals are
affiliate-only by design (no "לאתר הספק"/terms button), content has its own modal.

## Step 2 — Identify the provider's method

Look up the carrier + variant (domestic vs roaming) in the **methodology table** below.
It tells you the mechanism, whether capture is AUTOMATIC (scraper handles new plans) or
HARDCODED (you must act), and the exact technical method to obtain the value.

## Step 3 — Fetch the terms using that method

Apply the provider's method to the specific new plan. Most methods are a single HTTP
fetch you can reproduce in Python without Playwright (CMS/JSON APIs) — verify the result
before wiring it in. **Always confirm the PDF/page returns HTTP 200** (a stale link is as
bad as none):

```bash
PYTHONIOENCODING=utf-8 python -c "
import urllib.request as u
url='<THE_PDF_URL>'
r=u.urlopen(u.Request(url,headers={'User-Agent':'Mozilla/5.0 Chrome/124 Safari/537.36'},method='HEAD'),timeout=20)
print(r.status, r.headers.get('Content-Type'))
"
```

## Step 4 — Wire it in (decision tree)

- **The scraper already auto-captures for this carrier (column "AUTO" below):** the plan
  was likely scraped before the capture step landed, or the scrape failed transiently.
  Re-run that carrier's scrape from a **fresh process** (loads current code) to repopulate
  — see CLAUDE.md "After Code Changes". No code edit needed.
- **The carrier relies on a HARDCODED MAP (column "MAP"):** prefer to **upgrade the scraper
  to capture `terms_url` automatically** if the provider exposes a clean per-plan source
  (a CMS/JSON endpoint) — that fixes all future new plans, not just this one. This is what
  was done for Partner roaming (worked example below). If no clean source exists, add the
  one entry to `PLAN_DETAILS_PDFS[carrier]` in PlanCard.jsx as a stopgap.
- **No PDF exists (provider only has on-page bullets/modal):** emit a `__info__|<lines>`
  extra from the scraper (see `_wecom_wefly_popup_info`, `_enrich_rami_levy_abroad_info`,
  the Golan builders, `scrape_019_abroad` for the pattern).
- **Immediate live fix without waiting for a scrape:** `abroad_plans.terms_url` /
  `plans.url` are served to the frontend via the API at runtime, and PlanCard prefers them
  over its bundled map — so a direct DB `UPDATE` of `terms_url`/`url` makes the **already
  deployed** site show the terms with no rebuild. ⚠️ This only persists if the scraper also
  produces that value, because `save_abroad_plans`/`save_plans` upsert with
  `terms_url = excluded.terms_url` and will **wipe** a manual value on the next scrape if the
  scraper returns None. So pair any direct DB write with the scraper fix.

## Step 5 — Verify & ship

1. Re-run the Step 1 audit → expect `TOTAL MISSING: 0`.
2. If you edited the scraper: `python -m py_compile scraper.py`, and dry-test the fetch
   logic against the live source (resolve the new plan name to a URL) before relying on it.
3. If you edited PlanCard.jsx (the map): `cd mass-market-app && npm run build`, then the
   user drag-deploys `dist/` to Netlify (manual — see CLAUDE.md "Deployment"). The DB/API
   data fix shows without a rebuild; the **map** fallback needs the rebuild+deploy.
4. Optionally confirm in the preview (roaming tab → the carrier → the plan card shows
   "עיקרי התוכנית").

---

## Per-provider methodology reference (the "past experience")

Mechanism: **url**/**terms_url** = scraped PDF/page link · **map** = PLAN_DETAILS_PDFS only ·
**__info__** = in-app modal. Capture: **AUTO** = scraper handles new plans · **MAP** = manual
edit required.

### Domestic (`plans` table → `url` or `__info__`)

| Carrier | Mech | Capture | How to get the terms for a plan |
|---|---|---|---|
| partner | url | AUTO | In-page fetch CMS `GetPageContent/?pageid=91228&lang=he`; walk nodes `nodeTypeAlias=='transverseProductsPlan'` → `properties.planTerms` (JSON array → `url`, or regex `u.partner.co.il/media/…/*.pdf`). Match by exact plan name, then prefix. (`scrape_partner`) |
| pelephone | url | AUTO | Build name→`pid` from `.border_5 .item` popup links; fetch `…/join-pelephone-online/more-info/?pid=<pid>`; regex `.pdf` in HTML. (`scrape_pelephone`) |
| cellcom | url | AUTO | In-page fetch Episerver `contentepi.cellcom.co.il/production/Private/Cellular/Packages/?expand=*`; per package: last `featureLink`, falling back to block-level `programDetailsLink` → `termsLink` (added 2026-06-11 — lineup refreshes can ship cards with no featureLink at all); prefix `https://contentepi.cellcom.co.il`. Shared walker `_cellcom_extract_terms_urls`, used by `scrape_cellcom` (in-page) and standalone `_fetch_cellcom_terms_urls` (must send `Accept: application/json` or Episerver returns HTML). |
| hotmobile | url | AUTO | DOM: `input[data-pdf]` → `data-pdf`; prefix `https://www.hotmobile.co.il` if path-relative. (`scrape_hotmobile`) |
| mobile019 | url | AUTO | Stealth session (Incapsula). DOM `a[href*=".pdf"]` on the plan card. (`scrape_019`) |
| xphone | url | AUTO | DOM `a[href*="wp-content/uploads"][href$=".pdf"]`, matched to plan by URL-slug substring; static fallbacks. (`scrape_xphone`) |
| wecom | url | AUTO | Walk ancestor DOM for `a[href*=".pdf"]`. (`_scrape_wecom_page`) |
| golan | __info__ (+url) | AUTO | JS extracts each `.offer` card's `pdfHref` + "פרטי המבצע" bullets → emits `__info__|…` with a `התקנון המלא (PDF)|<href>` line. (`scrape_golan` / `_build_golan_domestic`) |
| rami_levy | __info__ | AUTO | Click each `a.more` ("למידע נוסף") → read `.modal-body` text → `__info__|`. (`scrape_rami_levy`) |
| neptucom | — | static | Hardcoded plan list; **no terms button by design** (eSIM-only). Don't flag as missing. (`scrape_neptucom`) |

### Roaming (`abroad_plans` table → `terms_url` or `__info__`)

| Carrier | Mech | Capture | How to get the terms for a plan |
|---|---|---|---|
| **partner** | terms_url | **AUTO** | In-page fetch CMS `GetPageContent/?pageid=75299&lang=he`; walk nodes → `properties.serviceTermsPdf` → regex `u.partner.co.il/media/…/*.pdf`. Match exact name then prefix. (`scrape_partner_abroad` — added 2026-06; **was MAP-only**.) |
| cellcom | terms_url | AUTO | POST `https://digital-api.cellcom.co.il/api/abroad/GetPackagePopular` `{SocIdList:[…], BlockId}`; read each pkg's `policiesEpi`; prefix `https://contentepi.cellcom.co.il`. (`_cellcom_fetch_abroad_policies`, blocks 20557 + 60988.) The API **echoes back only the SOCs you ask for**, so the two hardcoded lists are not the catalogue — `scrape_cellcom_abroad` also regex-harvests SOC codes (`_CELLCOM_SOC_RE`) out of the silent-roamers page and asks for the unknown ones, which is what covers a package published outside the lists (2026-09; see worked example). Matching order per plan: **socCode** → normalised **title** (`_cellcom_norm_title`) → the card's own `/globalassets/…pdf` anchor. |
| hotmobile | terms_url | AUTO | Card `onclick=ShowMoreDetails('<socId>')` → `page.evaluate` opens modal → find `a` whose href has `.pdf` & `/media/` and text ≈ "תנאיהחבילה". Re-captured every run (slug rotates). (`scrape_hotmobile_abroad`) |
| **pelephone** | terms_url | **AUTO** | socId from each card's `a[href*="more-info/?socId="]`; in-page fetch the "מידע נוסף" modal (`/abroad/more-info/?socId=<id>&mode=open`); regex the plan-specific "לתנאי החבילה והתוכנית" anchor via `_PELE_ABROAD_TERMS_RE` → `/abroad/terms/<slug>/` page. ("מושלמת" family shares `terms-summer2019`; promo plans may reuse another plan's page, e.g. מונדיאל 2026 → `Family-Travel-Package`.) (`scrape_pelephone_abroad` — added 2026-06-09; **was MAP-only**.) Map kept as fallback. |
| mobile019 | __info__ | AUTO | Card `.blist li` bullets + the site-wide `_MOBILE019_VOLTE_NOTE` → `__info__|`. Label shows "עיקרי התוכנית". (`scrape_019_abroad`) |
| wecom | __info__ | AUTO | POST `we-com.co.il/wp-admin/admin-ajax.php` `action=jet_popup_get_content&data[popupId]=jet-popup-14068&data[postId]=<id>`; strip HTML; call-rates link → `label|url`. (`_wecom_wefly_popup_info`) |
| rami_levy | __info__ | AUTO | Visible `a.more` → modal text, matched to plan by price. (`_enrich_rami_levy_abroad_info`) |
| golan | __info__ | AUTO | JS extracts benefits + appends `תעריפון חו"ל (PDF)|https://golant.co/roaming_tariffs`. (`scrape_golan_abroad` / `_build_golan_abroad`) |
| xphone | — | none | Roaming scraped as plain text; no terms source. Leave as-is unless a source appears. (`scrape_xphone_abroad`) |

**At-a-glance — who needs manual action on a new plan:** **none.** Every domestic and
roaming carrier now auto-captures terms at scrape time (Pelephone roaming was the last
hold-out — upgraded 2026-06-09). A missing terms button therefore means the plan was
scraped **before** the capture step landed, or a transient fetch failure → **re-scrape that
carrier** (or run the immediate DB fix), don't hand-edit. partner/pelephone/cellcom/hotmobile
keep a `PLAN_DETAILS_PDFS` map but it's now a pure fallback (the scraper writes `terms_url`/`url`).

> **Skills don't run themselves.** This runbook only fires when Claude is in the loop. The
> twice-daily *scheduled* scrape runs unattended — nothing here executes during it. The thing
> that actually closes the gap with no human is **scraper-level capture** (column AUTO). That's
> why the durable fix for any MAP carrier is to upgrade the scraper, not to lean on this skill
> running. After 2026-06-09 every carrier is AUTO, so the unattended scrape self-heals terms.

---

## Worked example — Partner "חבילת המונדיאל" (2026-06-08)

Partner added a new roaming package ("חבילת המונדיאל", 279₪/90GB/30d). Its "עיקרי התוכנית"
was empty because, at the time, **Partner roaming had no terms capture at all** — it relied
100% on `PLAN_DETAILS_PDFS.partner`, which nobody had updated.

Fix applied (the template for any MAP→AUTO upgrade):

1. **Found the source.** Partner's roaming CMS (`GetPageContent/?pageid=75299`) exposes
   `serviceTermsPdf` per package — including the new one →
   `https://u.partner.co.il/media/f01jlh2t/reprt1525p.pdf` (verified 200, application/pdf).
2. **Upgraded the scraper** (`scrape_partner_abroad`) to walk that CMS tree and set
   `terms_url` per plan — mirroring the domestic `scrape_partner` (pageid=91228 / `planTerms`).
   Now **every** Partner roaming plan, present and future, auto-resolves (validated 8/8).
3. **Map fallback:** added the one entry to `PLAN_DETAILS_PDFS.partner` and re-noted the map
   as a fallback (terms_url preferred).
4. **Immediate live fix:** direct-`UPDATE`d `abroad_plans.terms_url` for all 8 Partner roaming
   rows from the same CMS, so the deployed site showed terms without waiting for a scrape —
   safe because the scraper now reproduces those exact values (no upsert wipe).
5. **Verified:** audit → `TOTAL MISSING: 0`; `npm run build`; hand off `dist/` for deploy.

## Worked example — Pelephone "מונדיאל 2026" (2026-06-09)

Pelephone added a roaming package ("מונדיאל 2026", 299₪/100GB/30d) and its "עיקרי התוכנית"
was empty — Pelephone roaming was the **last MAP-only** carrier (all 12 rows had
`terms_url=NULL`, living off `PLAN_DETAILS_PDFS.pelephone`), and nobody had added the new
plan to the map. The same MAP→AUTO upgrade as Partner:

1. **Found the source.** Each card carries `a[href*="more-info/?socId="]` (מונדיאל = socId 467).
   The `/abroad/more-info/?socId=<id>&mode=open` page embeds the plan-specific
   `<a class="icn_pack" …>לתנאי החבילה והתוכנית</a>` → here `/abroad/terms/Family-Travel-Package/`
   (Pelephone reused the family-travel terms page; verified 200, text/html).
2. **Gotcha:** each more-info page also has a *recurring* `terms-pesach/terms-family/` nav link.
   Anchor the regex on the `>לתנאי` anchor text (`_PELE_ABROAD_TERMS_RE`) to grab the real one,
   not the noise. Validated against the old map: 12/12 exact match.
3. **Upgraded the scraper** (`scrape_pelephone_abroad`) to read socId per card + in-page
   `Promise.all` fetch of all more-info pages + regex → `terms_url`. End-to-end run: 12/12 captured.
4. **Map fallback:** added the one `מונדיאל 2026` entry to `PLAN_DETAILS_PDFS.pelephone`.
5. **Immediate live fix:** direct-`UPDATE`d `abroad_plans.terms_url` for all 12 Pelephone rows
   (scrape→DB), so the deployed site showed terms with no wait — safe, the scraper reproduces them.
6. **Verified:** audit → `TOTAL MISSING: 0`; local `/api/abroad-plans` serves the terms_url;
   `npm run build`; hand off `dist/`.

## Worked example — Cellcom "מושלמת לחגים" (2026-09-06): a closed SOC list vs an open DOM source

`alert_missing_terms` flagged a new Cellcom **roaming** package, "מושלמת לחגים", with no
"עיקרי התוכנית". Cellcom roaming was already marked AUTO — so why the gap?

1. **The two sources disagree about what the catalogue is.** `scrape_cellcom_abroad` has a
   closed source (the API, `SocIdList` hardcoded) and an **open** one (the Silent-Roamers
   page DOM, which ingests whatever cards Cellcom publishes). Terms came only from
   `_cellcom_fetch_abroad_policies` over the two hardcoded SOC lists, keyed by title.
2. **Confirmed the API filters by the caller's list** from the recorded response
   `cellcom_abroad_api_result.json`: 8 SOCs requested → exactly those 8 returned, in order,
   each carrying its own `blockId` (the request's `BlockId` is context, not a selector).
   So a SOC nobody hardcoded is a package whose `policiesEpi` is **unreachable** — the DOM
   can scrape a plan the policy fetch can never cover. That is the whole bug; the holiday
   promo was simply the first plan to fall through it.
3. **Fix — discover the SOC instead of remembering it.** `scrape_cellcom_abroad` now
   regex-harvests SOC codes (`FMWH…`/`HUL…`) from the silent-roamers page HTML and from each
   card's own subtree, asks GetPackagePopular for the ones the hardcoded lists don't know,
   and resolves terms by **socCode first** (one package, one code), then normalised title,
   then the card's own `/globalassets/…pdf` anchor. Lobby plans now carry their `socCode`
   too, so they stop depending on title matching at all.
4. **Did NOT invent a URL** for the new plan (same call as the 500GB case below) — the terms
   come from Cellcom's own API on the next scrape or not at all. A plan that still resolves
   to nothing now emits a `logger.warning` naming it, alongside the Telegram alert.
5. **Verified offline** (`tests/test_cellcom_abroad_terms.py`, 14 tests, no network): the
   recorded API response as a fixture + a fake Page; the regression test asserts a card whose
   SOC appears **only** in the page HTML gets the right PDF, and that an unrelated
   (non-`/globalassets/`) PDF is never linked as terms.

**Lesson:** "AUTO" is only as open as its narrowest link. When a scraper pairs an open-ended
source with a closed id list, new plans are ingested but never enriched — check that the
enrichment key set can actually grow before trusting the AUTO column.

## Worked example — Cellcom 500GB flash-publish (2026-06-11): when NO link exists yet

The 07:31 scrape caught a Cellcom lineup refresh (500GB ₪40 / 550GB ₪129 / 1500GB ₪59
replacing 5G Pro + 5G Pro Fly) that Cellcom **rolled back later that morning** — the live
page reverted to the old lineup within hours. In the brief publish, Cellcom's own CMS
attached the OLD 5G plan's PDF (`item_15057_1.pdf`, an 800GB document) to 550GB/1500GB as a
placeholder, and gave 500GB **no featureLink at all** → `url=None` in MOCA.

Diagnosis path that established "no correct link exists on the company site yet":
fresh-context retries of the page (rules out cookie A/B → it was publish+rollback), the
Episerver funnel page (`/sale/cellular/mobile/MOBILE_5g/?expand=*` — exposes per-block
`programDetailsLink`/`termsLink`!), campaign pages, and a ~3.7K-URL CDN probe of the PDF
id spaces (`item_<n>_1.pdf` and makat `<n>[-MMYY-VV].pdf` under `/globalassets/pdf/3{,-5g-pro}/`).
All negative — the new plans' PDFs simply weren't uploaded.

Resolution (differs from the MAP→AUTO examples — there was nothing to link):
1. **Scraper hardened, not the data**: `_cellcom_extract_terms_urls` (shared walker) now
   falls back from `featureList[].featureLink` → block-level `programDetailsLink` → `termsLink`,
   so a re-publish with sloppy featureLists still auto-captures. Validated 5/5 current plans
   via the fallback path with featureLinks stripped.
2. **Deliberately did NOT** copy the siblings' placeholder PDF onto 500GB — MOCA mirrors the
   provider site; linking a factually-wrong document is worse than the empty state.
3. Audit ends at `TOTAL MISSING: 1` (cellcom/500GB) — acceptable: the plan vanishes on the
   next scrape (rollback) or self-heals via the fallback when Cellcom re-publishes properly.
Lesson: a missing-terms alert right after a lineup-level change can mean a **flash publish /
rollback**; verify the plan still exists on the live site before hunting for its PDF.
