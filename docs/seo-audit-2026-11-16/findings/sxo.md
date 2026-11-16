# SXO findings - MOCA eSIM (lucent-kulfi-f037ad.netlify.app)

Date: 2026-11-16. Category: Search Experience. Separate from SEO Health Score.

## SXO Gap Score: 42/100 (site-level, weighted to /esim/<slug>/ pages)

| Dimension | /esim/thailand/ | Evidence |
|---|---|---|
| Page Type | 10/15 | Aggregator listing is a valid secondary type on destination SERPs; dominant type is provider product page |
| Content Depth | 5/15 | 337 rendered words, 9 offer cards, 4 FAQs. No network/coverage (AIS/DTAC/True), no data-per-trip guide, no roaming-vs-eSIM numbers, no regional (Asia) option |
| UX Signals | 4/15 | Every "לרכישה" CTA points to api.mocaintel.com/go/... which returns HTTP 530; cards sorted by absolute price so the top pick is 102MB; two Terminal cards show no validity ("1GB · ") |
| Schema | 9/15 | Product+AggregateOffer (highPrice 1540.79 ILS, odd), FAQPage (no rich result for commercial sites since 2023), BreadcrumbList OK. No ItemList of offers, no dateModified |
| Media | 3/15 | Background image only; no install screenshots, no coverage map, no provider logos in HTML text |
| Authority | 2/15 | netlify.app subdomain, not found for its own hostname in search; no About/methodology page; personal coupon code "alonyo15" |
| Freshness | 9/10 | Visible "עודכן 16 בנובמבר 2026", prices refresh twice daily |
| **Total** | **42** | |

/esim-deals separately: rendered DOM only 155 words; H1 "כמה תשלמו על אינטרנט בטיול הבא?" lacks "eSIM"; no prices in HTML until a destination is picked. Estimated ~38/100 for its target query (inference).

## SERP evidence (WebSearch is US-located, not google.co.il - see limitations)

1. "eSIM לתאילנד": provider product pages dominate (eskimo, yesim, simcorner, etravelsim, nomad, zetsim, esimcard, true.th) ~70%; English "best eSIM for Thailand" listicles (wise, techradar, trip.com) and aggregators (travel-dealz, esims.io) ~30%. Almost no Hebrew results. Consensus: provider product page, ~70%.
2. "eSIM לארצות הברית": Hebrew-localized provider pages (mobimatter/he, airalo/he, yesim/he, cellesim/he, esim-now/he, getroamify) ~90%, one Hebrew coverage guide (esim-now). Consensus: provider product page, ~90%.
3. "השוואת מחירי eSIM": Israeli editorial (gadgety x2, TheMarker supermarker), provider "X vs Airalo" pages (esim-now, roamify blog), listicle (mylist), cellesim savings page. Consensus: comparison article / editorial, ~60%. No unified multi-provider price table ranks.
4. "eSIM לחו"ל מומלץ": listicles and guides (gadgety, mylist "6 כרטיסי eSIM מומלצים", kamaze review, voye/airalo/roamify blogs, globes). Consensus: best-of editorial guide, ~70%.
5. "חבילת גלישה לחו"ל": news/editorial (ynet, maariv, walla, srugim, bizportal sponsored x2, gadgety) plus kamaze carrier page. Frame is Israeli carrier roaming vs eSIM. Consensus: news/editorial, ~80%.
6. (extra long-tail) "eSIM ליוון השוואת מחירים": esim-now Hebrew guide "eSIM הטוב ביותר ליוון ב-2026" (with networks Vodafone/Nova and 5G notes), gadgety, English aggregators. Thin Hebrew competition.

SERP features: AI-generated summary present on every query (WebSearch synthesis; inference that Google AI Overview behaves similarly on google.co.il is unverified). PAA/ads/featured snippets not observable via this tool.

## Page-type mismatch

| Query | Dominant type | MOCA page | Severity |
|---|---|---|---|
| eSIM לתאילנד / לארה"ב / ליוון | Provider product page | /esim/<slug>/ aggregator | MEDIUM (aggregator is accepted minority type) |
| השוואת מחירי eSIM | Comparison article | /esim-deals interactive SPA, 155 words | HIGH |
| eSIM לחו"ל מומלץ | Best-of guide | none | HIGH (no page) |
| חבילת גלישה לחו"ל | News / carrier-vs-eSIM editorial | none (/mobile-deals unpublished) | CRITICAL (wrong format, not winnable) |

## Findings (severity, evidence, fix)

1. CRITICAL - All 160 destination pages send buyers to a dead host. Evidence: every "לרכישה" href is https://api.mocaintel.com/go/<provider>; curl returns HTTP 530 (Cloudflare origin/tunnel error) with a browser UA, while the same path on the ngrok edge returns 302 to esimplus.me. Source: prerender-esim-dests.mjs GO_BASE hardcoded to api.mocaintel.com (per CLAUDE.md). Fix: point GO_BASE at the live API origin (same value as VITE_API_URL) or a Netlify `/go/*` proxy rule already in _redirects, rebuild, redeploy, verify one CTA returns 302.
2. HIGH - "Top recommendations" lead with unusable micro plans. Evidence: card 1 is 102MB/30 days ₪1.19, then 1GB and 500MB plans; 9 of 9 cards are 1GB or less. A Thailand trip needs roughly 5-20GB for 7-14 days. Fix: rank the static cards by trip-sized deals (for example cheapest ≥5GB/≥7d, cheapest ≥10GB, cheapest unlimited 7/15/30 days) with ₪/GB and ₪/day shown, the same floor logic as db.get_esim_alert_floor.
3. HIGH - "מ-₪1.19" in title/meta reads as bait. Evidence: title "eSIM לתאילנד - השוואת מחירים מ-₪1.19 | MOCA"; the ₪1.19 item is 102MB. Inference: users who click and see 102MB bounce back to the SERP. Fix: lead with a trip-sized anchor, for example "eSIM לתאילנד: 10GB לשבוע מ-₪X, 154 חבילות מ-29 ספקים | MOCA". Keep the AggregateOffer lowPrice true but don't headline it.
4. HIGH - No page for the editorial intent ("מומלץ", "השוואת מחירי eSIM"). Evidence: those SERPs are 60-70% guides/listicles; /esim-deals has 155 words and no static table. Fix: add a prerendered static section to /esim-deals (or a /esim/guide/ page) with a live-data table "cheapest 5GB/10GB/unlimited by top 15 destinations", data-sizing guide (the FAQ already has the 3/10/20GB answer), carrier roaming vs eSIM price comparison. This is MOCA's unique data advantage over the gadgety/mylist articles.
5. MEDIUM - Thin destination content vs Hebrew competitors. Evidence: 337 words; esim-now's Hebrew Greece guide ranks with network names (Vodafone/Nova), 5G and island coverage. Fix: per destination add a generated block: local networks used by each plan (where providers publish it), hotspot support, regional plan alternatives (Asia/Europe), typical data needs, and a 1-line Israeli carrier roaming benchmark from abroad_plans.
6. MEDIUM - Missing validity on some cards. Evidence: "Terminal eSIM 1GB ·" and "Bcengi 1GB ·" with no days. Fix: render "תוקף לא צוין" or drop such plans from the featured block.
7. MEDIUM - /esim-deals H1 and above-the-fold lack keyword and proof. Evidence: H1 "כמה תשלמו על אינטרנט בטיול הבא?", no prices in rendered HTML before interaction. Fix: H1 "השוואת מחירי eSIM לחו"ל", and prerender a sample price strip (top 6 destinations with cheapest trip-sized deal) into the static HTML.
8. MEDIUM - Trust signals for a zero-authority domain. Evidence: no About/methodology page, coupon labeled with a personal handle, affiliate disclosure only in the footer. Fix: add "איך אנחנו משווים" page (sources, refresh cadence, how ranking works, no paid placement if true), link it near the H1; rename coupon labels to "קופון MOCA".
9. LOW - Schema quirks. AggregateOffer highPrice 1540.79 ILS looks like a data outlier; no dateModified. Fix: cap or verify highPrice, add dateModified to the page JSON-LD; consider ItemList of the featured offers.

## User stories (each tied to a SERP signal)

- Awareness: "As a first-time traveler, I want to know if my phone supports eSIM and how to install it, so I don't land offline." Signal: compatibility/installation repeated in every query's summary; gadgety "check if your device supports eSIM" ranks for comparison query.
- Consideration: "As a buyer, I want a recommended provider for my trip, not a raw list." Signal: "מומלץ" SERP is 70% best-of listicles (mylist, gadgety).
- Consideration: "As a price-sensitive traveler, I want to compare eSIM with my Israeli carrier's roaming package." Signal: "חבילת גלישה לחו"ל" SERP is ynet/maariv carrier-vs-eSIM pieces quoting Cellcom ₪149/2GB.
- Decision: "As a traveler to Greece/USA, I want to know which local network the eSIM uses and whether it covers islands/rural areas." Signal: esim-now Hebrew coverage guides rank for US and Greece.
- Decision: "As a buyer, I want plans by trip length (7/15/30 days) and hotspot support." Signal: Thailand SERP summaries emphasize validity tiers and hotspot.

## Personas (/esim/thailand/), weakest first

| Persona | Relevance | Clarity | Trust | Action | Total | Top fix |
|---|---|---|---|---|---|---|
| Family trip planner (3-4 phones, 10-14 days, hotspot) | 10 | 10 | 9 | 4 | 33 | Featured block by trip length + unlimited/hotspot filter; "per family" note (one eSIM per device) |
| First-time eSIM user | 18 | 13 | 9 | 4 | 44 | Move the install/compatibility FAQ into a 3-step strip above the cards (as on /esim-deals); explain what 1GB lasts |
| Price hunter | 20 | 13 | 12 | 4 | 49 | Show ₪/GB and ₪/day, sort selector on the static page, fix CTAs |

Action is 4/25 for everyone because the buy buttons fail (finding 1).

## Winnable vs not (inference, based on SERP composition and zero domain authority)

- Winnable: Hebrew long-tail destination + modifier queries where page 1 is mostly English or provider pages: "eSIM לתאילנד 15 יום", "eSIM לגאורגיה", "eSIM לווייטנאם זול", "eSIM ליוון ללא הגבלה", secondary/less-served destinations among the 160. Also data-led queries no editorial page answers ("כמה עולה eSIM ל..."), if the page shows trip-sized prices.
- Hard/not realistic now: "השוואת מחירי eSIM", "eSIM לחו"ל מומלץ", "eSIM לארצות הברית" (Airalo/yesim/mobimatter localized pages), and "חבילת גלישה לחו"ל" (news publishers + sponsored articles). These need a real domain, links, and press mentions; a data-PR angle (monthly "מדד מחירי eSIM" pitched to gadgety/TheMarker) is the most plausible route.

## Limitations

- WebSearch is US-located and not a raw Google results page; google.co.il rankings, PAA, ads, featured snippets and AI Overviews could not be observed directly.
- Could not confirm MOCA's indexation (search for its hostname returned nothing; consistent with near-zero visibility, not proof).
- Above-the-fold judged from DOM order, no mobile viewport screenshot.
- No GSC/analytics data used. Pages rendered with Chromium sandbox on.
- One test click was sent to the ngrok /go/esimplus endpoint with campaign=sxo_probe; it may appear in the click log.

## Structured (audit-data.json, Search Experience)

```json
{"category":"Search Experience","sxo_gap_score":42,"findings":[
{"id":"sxo-1","severity":"critical","title":"Destination-page buy CTAs point to api.mocaintel.com (HTTP 530)"},
{"id":"sxo-2","severity":"high","title":"Featured cards lead with 102MB-1GB micro plans"},
{"id":"sxo-3","severity":"high","title":"Title 'from ₪1.19' anchored on a 102MB plan"},
{"id":"sxo-4","severity":"high","title":"No page matching editorial intent for comparison/recommended queries"},
{"id":"sxo-5","severity":"medium","title":"Thin destination content, no network/coverage info"},
{"id":"sxo-6","severity":"medium","title":"Missing validity on some featured cards"},
{"id":"sxo-7","severity":"medium","title":"/esim-deals H1 lacks keyword, no prices in static HTML"},
{"id":"sxo-8","severity":"medium","title":"No methodology/about trust page; personal coupon label"},
{"id":"sxo-9","severity":"low","title":"AggregateOffer highPrice outlier, no dateModified"}]}
```
