# Content Quality / E-E-A-T / On-Page - lucent-kulfi-f037ad.netlify.app

Audit date: 2026-11-16. Method: crawl.json (167 URLs) + live fetch of 10 destination pages (thailand, united-states, japan, greece, europe, global, israel, maldives, liberia, vanuatu), /, /hotels, /esim-deals, /esim/destinations/, the 4 legal pages, /about, /contact. Text extracted from served HTML (no JS). Live API cross-checked through the ngrok edge. Source code read: `mass-market-app/scripts/prerender-esim-dests.mjs`, `api/esim.py`, `src/data/legalEntity.js`.

## Scores

| Score | Value |
|---|---|
| Content Quality | **34 / 100** |
| On-Page SEO | **50 / 100** |
| AI citation readiness | **40 / 100** |

E-E-A-T (internal model, not Google weights):

| Factor | Weight | Score | Basis |
|---|---|---|---|
| Experience | 20% | 25 | No first-hand testing, no reviews, no named traveller/author; data is scraped |
| Expertise | 25% | 40 | Accurate generic eSIM FAQ; no author, no credentials; destination data wrong (see C1) |
| Authoritativeness | 25% | 20 | DR 0, no About page, no press/partners shown, unknown operator |
| Trustworthiness | 30% | 35 | Good affiliate footer + rel=sponsored + legal pages; but no legal entity, buy links broken, wrong prices on 160 pages |
| **Weighted** | | **31** | |

---

## CRITICAL

### C1. All 160 destination pages show the SAME (Israel) plan list - build bug
- Evidence: every /esim/<slug>/ page states "154 חבילות מ-29 ספקים · החל מ-₪1.19" and lists the identical 10 cards (eSIM Plus 102MB ₪1.19, Terminal eSIM 1GB ₪2.34 ... BNESIM 1GB ₪8.82). `diff thailand vanuatu` = only the destination name differs. crawl.json: 160/160 descriptions carry the numbers (154, 29, 1.19); hub /esim/destinations/ prints "מ-₪1.19 · 154 חבילות" next to every one of 160 destinations.
- Root cause (verified in code + live API): `prerender-esim-dests.mjs` line 209 calls `/api/esim/compare?dest=...`, but `api/esim.py` line 29 reads `request.args.get("destination")` and falls back to `core.ISRAEL_HE`. Live check: `?dest=תאילנד` returns destination "ישראל", 154 deals / 29 providers / ₪1.19; `?destination=תאילנד` returns 167 deals / 31 providers / ₪1.44; `?destination=יפן` returns 158 / 30 / ₪1.61.
- Impact: factual inaccuracy at scale (Vanuatu and Thailand cannot share a catalog), affiliate links carry `dest=<country>` while the plan shown is an Israel plan, Product/AggregateOffer schema asserts wrong prices on 160 URLs. Under the QRG this is "Lowest" (inaccurate, misleading) and under the scaled-content-abuse policy the pages are essentially one page x160.
- Fix: change line 209 to `?destination=${encodeURIComponent(he)}` (or make the API accept both), add a build assertion that fails if more than ~20% of pages share an identical `stats.low`+`stats.total`, rebuild and redeploy.

### C2. Every "לרכישה" button on the 160 pages is dead (Cloudflare 1033)
- Evidence: links point to `https://api.mocaintel.com/go/<provider>?dest=...&campaign=seo_dest`; live request returns `HTTP 530`, body `error code: 1033` (tunnel not connected). The live API edge is the ngrok host (returns 200 on /api/ping).
- Impact: zero monetisation from SEO pages and a broken primary CTA = strong low-quality/untrustworthy signal for users and raters.
- Fix: point `GO_BASE` in prerender-esim-dests.mjs at the live API origin (same env var as `VITE_API_URL`), or better a first-party `/go/*` path proxied by `_redirects` so the HTML never hardcodes the API host.

### C3. Doorway / scaled-content risk on /esim/<slug>/ even after C1 is fixed
- Evidence: ~364 words per page; diff shows ~25 words differ (destination name x6 plus one link swap). That is ~93% template today. After C1 the 10 deal cards would differ, but those are ~60 tokens of numbers/provider names, so pages would still be ~80% shared boilerplate (identical 4 FAQ answers, identical intro, identical footer). Long tail pages (Vanuatu, Montserrat, Anguilla, Mayotte) have no destination-specific information at all.
- Fix (unique value per page, generated from data you already have): (a) price ladder by need: cheapest 1GB/3GB/5GB/10GB/unlimited for 7 and 30 days; (b) median price per GB for the destination vs Europe/global average; (c) "cheapest unlimited" and "best value for a 7-day trip" call-outs; (d) price trend from `price_history_daily` ("הוזל ב-12% ב-30 יום"); (e) coverage notes: which providers sell a local vs regional plan, networks if known, whether a regional (Europe/Asia) bundle is cheaper; (f) destination FAQ with destination data (e.g. "כמה עולה eSIM ללא הגבלה ליפן?"). Set a quality floor: noindex (or drop from sitemap) destinations with fewer than ~5 providers or no trip-sized plan.

## HIGH

### H1. Title/description from-price "מ-₪1.19" is a 102MB package - misleading
- Evidence: title "eSIM לתאילנד - השוואת מחירים מ-₪1.19 | MOCA"; the card is "eSIM Plus 102MB · 30 ימים ₪1.19". Even with correct data, the minimum will always be a sub-1GB or 1-day package (live Thailand min ₪1.44).
- Impact: CTR bait that disappoints on landing (pogo-sticking), and a misleading price claim (Consumer Protection angle). Same problem the backend already solved for push alerts (`db.get_esim_alert_floor` = cheapest deal >=5GB/>=7d).
- Fix: headline price = cheapest trip-sized plan, e.g. "eSIM לתאילנד - 10GB לשבוע מ-₪X" or "מ-₪X ל-5GB"; keep the raw minimum out of title/meta.

### H2. Descriptions are a fill-in-the-name template with identical numbers
- Evidence: 160/160 "השוואת חבילות eSIM ל{X}: 154 חבילות מ-29 ספקים, החל מ-₪1.19. מחירים שנאספים אוטומטית, קודי קופון והזמנה מיידית." The heuristic metadata_template.py check (18 sampled pairs) reports site_risk=low, templated_ratio 0.0, no shared CTA (it detects title echo + CTA, not slot templates), but by inspection the descriptions are bulk-generated with one variable.
- Fix: after C1, include 2-3 destination-specific facts (cheapest 5GB/7d price, unlimited price, provider count) and vary the second sentence by region/price band.

### H3. No identifiable operator (E-E-A-T trust)
- Evidence: /about and /contact return the SPA shell (6 words, title "MOCA - מודיעין תחרותי לשוק הסלולר", HTTP 200 = soft 404). Privacy page: "מפעיל השירות ובעל מאגר המידע: MOCA · Helpdesk@mocaintel.com" with no legal name/ח.פ./address; `legalEntity.js` has `legalName: null, registrationId: null, address: null`. No named person anywhere on /, /esim-deals, destination pages.
- Fix: fill legalEntity.js; add a real /about (who runs MOCA, since when, the B2B telecom-intelligence background as expertise proof, how money is made) and /contact; link both from every footer; return 404 for unknown paths instead of the SPA shell.

### H4. No methodology page; "recommended" label is just "cheapest"
- Evidence: destination H2 "החבילות המומלצות לתאילנד" lists the 10 cheapest by raw price; footer only "המחירים נאספים אוטומטית מאתרי הספקים". No explanation of which providers are included, how prices are converted (FX), how often, whether affiliate status affects ranking.
- Fix: a /methodology page (sources, 40 providers, twice-daily scrape, FX method, ranking = price only, affiliate status does not affect order) linked from every comparison block; rename H2 to "החבילות הזולות ביותר" or add a real recommendation logic.

### H5. /esim-deals served HTML is thin and has no internal links
- Evidence: 187-194 words in served HTML; crawl internal_links = 0. Content = 3-step intro + 4 FAQs. H1 "כמה תשלמו על אינטרנט בטיול הבא בחו"ל?" does not contain "eSIM". The interactive comparison renders client-side only.
- Fix: prerender a static block: top 10-20 destinations with trip-sized from-prices linking to /esim/<slug>/ and the hub, "how we compare" summary + link to methodology, a short buying guide (data needs per trip type already in FAQ, expand). Put "eSIM" in the H1, e.g. "השוואת מחירי eSIM לחו"ל - כמה תשלמו על אינטרנט בטיול?".

### H6. /hotels: English title and description on a Hebrew page, no schema
- Evidence: `<html lang="he">`, H1 Hebrew "האורח נוחת ושואל ... המלון שלכם עונה - ומרוויח.", but title "MOCA Guest Connect - eSIM concierge for your hotel guests" and description (276 chars, English) "A guest-facing portal, branded in your hotel's colors...". crawl schema = [] . /hotels?lang=en serves the same head (hreflang en points to a URL with identical HTML head).
- Fix: Hebrew title (~55 chars) e.g. "eSIM לאורחי המלון - פורטל השוואה ממותג | MOCA Guest Connect" and Hebrew description under 155 chars; emit English head only for ?lang=en (or a separate /en/hotels prerender); add Organization + Service (or SoftwareApplication) + FAQPage schema.

## MEDIUM

### M1. Homepage: two H1s and identical head for ?lang=en
- Evidence: / renders both Hebrew and English H1 ("כל מהלך תחרותי בשוק הסלולר - ..." and "Every competitive move in the mobile market - ...") in the DOM; /?lang=en has the same Hebrew title/description (crawl) while hreflang declares it English. Description 169 chars (truncates at ~155).
- Fix: render only the active language's H1 server-side (or give English its own prerendered HTML), localise the head per lang, trim description to ~150 chars.

### M2. Homepage keyword targeting mixes B2B and B2C
- Evidence: title "MOCA - מודיעין תחרותי לשוק הסלולר" (B2B), description mentions "כ-40 ספקי eSIM" and footer links to /esim-deals. Brand-new domain with DR 0 (per memory) will not rank for B2B head terms; the B2C money pages get no homepage authority signal beyond a footer link.
- Fix: keep / B2B but add a clearly labelled consumer section linking to /esim-deals and the top destination pages with descriptive anchors.

### M3. Hebrew grammar errors from naive "ל" + name concatenation
- Evidence: hub and pages: "eSIM להאיים המלדיביים", "eSIM להרפובליקה הדומיניקנית", "eSIM להמזרח התיכון", "eSIM להאי מאן", "eSIM להונג קונג" (last one acceptable, others not); FAQ "102MB ל30 ימים" (missing hyphen: "ל-30").
- Fix: a `lamed(he)` helper that drops a leading definite ה ("לאיים המלדיביים", "לרפובליקה הדומיניקנית", "למזרח התיכון", "לאי מאן") and use "ל-" before digits.

### M4. Missing duration on some deal cards
- Evidence: Thailand page "Terminal eSIM 1GB · " and "Bcengi 1GB · " with empty days field.
- Fix: print "תוקף לא צוין" (or hide the separator) when days is null; prefer plans with known validity in the top 10.

### M5. Flat internal linking; long tail orphaned except for the hub
- Evidence: every destination page links to the same "יעדים פופולריים נוספים" (top 12 by count) + hub; crawl shows 16 internal links on all 160 pages. Vanuatu is linked only from /esim/destinations/. /esim-deals links to none.
- Fix: add contextual links: country -> its regional bundle page (Thailand -> /esim/asia/, Greece -> /esim/europe/ and /esim/balkans/), 4-6 geographic neighbours, and region pages -> member countries. Group the hub by continent with H2s.

### M6. Freshness signal is build-time only, no dateModified
- Evidence: "עודכן 16 בנובמבר 2026" is stamped at build; no `dateModified` in any schema (grep found none). Pages only update when someone rebuilds/deploys; after a few weeks without deploy the "updated" date ages while the claim "המחירים מתעדכנים אוטומטית" (FAQ) stays.
- Fix: schedule a rebuild+deploy (daily/weekly) and add `dateModified` to a WebPage node; reword FAQ to "נכון ל-<date>".

### M7. Affiliate disclosure placement
- Evidence: disclosure exists ("חלק מהקישורים הם קישורי שותפים - המחיר עבורכם זהה...") and buy links use `rel="sponsored nofollow"` (good), but it sits only in the footer, below the cards; coupon labels like "קופון alonyo15 - 15% הנחה" are shown without saying they are affiliate codes.
- Fix: one-line disclosure directly above the deal list, and "קוד שותפים" next to coupon codes.

### M8. Trust references point to an offline domain
- Evidence: privacy policy scope "mocaintel.com/esim-deals והכתובת esim.mocaintel.com"; /hotels footer "mocaintel.com"; contact Helpdesk@mocaintel.com. mocaintel.com does not resolve for HTTP (curl fails), although MX records still route to Cloudflare (inference: mail probably still works).
- Fix: until the domain returns, describe the service by the live origin in legal pages and footers, or state that mocaintel.com is the brand domain.

## LOW

### L1. Destination schema: Product + AggregateOffer for a comparison page
- Evidence: Product "eSIM לתאילנד" with AggregateOffer lowPrice 1.19 / offerCount 154 on every page.
- Fix: acceptable pattern for aggregators once data is correct (C1); add `seller`-less offers count that matches the visible list, and consider ItemList of the shown deals.

### L2. Title lengths fine, all under 65 chars
- Evidence: destination titles 40-65 chars (avg 44), descriptions 111-136 chars. Legal pages flagged `brand-suffix-in-description` (secondary).
- Fix: none needed beyond H1/H2.

### L3. FAQ copy is identical across 160 pages
- Evidence: 3 of 4 FAQ answers (מה זה eSIM, התקנה, וואטסאפ) are verbatim on all pages and on FAQPage schema x160.
- Fix: keep one generic FAQ on /esim-deals; on destination pages use destination-specific questions (data needs, unlimited price, regional vs local plan, network).

---

## AI citation readiness (40/100)
- Positive: clear H1/H2 hierarchy, FAQPage schema, explicit dated price statements ("נכון ל-16 בנובמבר 2026, חבילת eSIM ל... מתחילה ב-₪..."), llms.txt present.
- Negative: the quotable fact is wrong on 160 pages (C1), identical across pages so an LLM sees duplicate statements, no methodology/source page to cite, no named publisher entity.
- Fix: correct data; add 3-5 quotable, destination-specific sentences (cheapest 5GB/7d, cheapest unlimited, median ₪/GB, provider count); /methodology page; Organization schema with legalName and sameAs.

## Readability
Hebrew copy is short-sentence, plain, consumer-friendly (FAQ answers 25-45 words). No readability problem; the issue is depth and uniqueness, not clarity.

## Notes / inferences
- Word counts: crawl 361-382 for destination pages; my extraction 364-371.
- The claim that pages would stay ~80% template after C1 is an estimate from the card markup size.
- Email deliverability for Helpdesk@mocaintel.com is inferred from MX records only, not tested.
