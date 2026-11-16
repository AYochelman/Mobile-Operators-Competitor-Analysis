# MOCA structured data audit (2026-11-16)

Origin: https://lucent-kulfi-f037ad.netlify.app. Raw HTML saved in scratchpad/moca-audit/schema_raw/ (p1..p8, hub, fr).
Pages validated: /, /esim-deals, /hotels, /esim/ (see note), /esim/destinations/ (the real hub), thailand, united-states, japan, italy, plus france/spain/georgia/maldives/cyprus/egypt (Product block only).
Score: 42/100

## Detection
| URL | JSON-LD | Notes |
|---|---|---|
| / | @graph: Organization, WebSite | valid JSON, no microdata |
| /esim-deals | block 1 @graph Organization+WebSite; block 2 @graph WebPage+FAQPage (4 Q) | @id/isPartOf chain resolves |
| /hotels | none | 2 body mentions of mocaintel.com + Helpdesk@mocaintel.com mailto (text, not schema) |
| /esim/ | byte-identical to /esim-deals (SPA fallback, canonical = /esim-deals) | real hub is /esim/destinations/ |
| /esim/destinations/ | CollectionPage only (name, description, url) | 161 links to destinations, no ItemList |
| /esim/<slug>/ | 3 separate blocks: Product(+AggregateOffer), FAQPage(4 Q), BreadcrumbList(3) | no @id, no @graph, no WebPage, no Organization link |

## Findings

### CRITICAL
1. Aggregate numbers are identical on every destination page (and so is the visible price list).
   Evidence: thailand, united-states, japan, italy, france, spain, georgia, maldives, cyprus, egypt all emit lowPrice 1.19 / highPrice 1540.79 / offerCount 154, and "154 plans from 29 providers"; the first visible prices (1.19, 2.34, 2.38, 3.21, 6.33) are the same on Thailand and France. Looks like the prerender is not filtering the catalog by destination (or the API fell back to a global/default set at build time).
   Fix: debug prerender-esim-dests.mjs: filter by destination before computing stats and rendering rows; add a build guard that fails if >3 pages share the same (low, high, count).
2. Product markup is false for the page it sits on (follows from 1), and structured data must match visible content. Marking Thailand with France's offers is a spam-markup pattern (Google "spammy structured data" manual action risk, at minimum markup ignored).
   Fix: see item 1 plus the corrected block below.
3. Affiliate links on all destination pages point to a dead host. Evidence: 10 links per page to https://api.mocaintel.com/go/<provider>?... ; curl returns HTTP 530 (Cloudflare tunnel down). The working same-origin route https://lucent-kulfi-f037ad.netlify.app/go/esimplus returns 302.
   Fix: set GO_BASE in prerender-esim-dests.mjs to SITE_ORIGIN (/go/...), rebuild, redeploy. (Not schema, but it is the biggest revenue defect found.)

### HIGH
4. lowPrice is a misleading tiny package. Evidence: description/FAQ cites "102MB / 30 days, 1.19 ILS" as the "cheapest eSIM"; this is a trial-size package nobody travels with (same issue the project already handled for the price-drop alert floor, >=5GB and >=7d). Google merchant/product guidance expects price of the offer actually purchasable as described; a 102MB floor on a "eSIM Thailand" product misleads.
   Fix: compute lowPrice from the same trip-sized floor (>=5GB, >=7d), keep tiny packages out of the aggregate and the copy. Also highPrice 1540.79 is an outlier; consider a p95 or the same trip-sized band.
5. Product + AggregateOffer legitimacy. Product snippets are meant for a page about one specific product; offers need a seller you can buy from on that page. MOCA is a comparison/affiliate site: it sells nothing, no brand, no review/aggregateRating, no real product (eSIM Thailand is a category, not a SKU). Expected outcome: markup ignored for rich results (no price snippet), with elevated manual-action risk when the numbers are wrong (item 1). Not eligible for merchant listings (no shipping/return, no seller). Marked UNCERTAIN: Google does not publish an explicit ban on aggregator Product markup, but its product-snippet docs exclude list/category pages and require markup to reflect the page's main content.
   Fix (recommended): drop Product/AggregateOffer from destination pages; use WebPage (or CollectionPage) + ItemList of the top offers (name + url, no price) + BreadcrumbList. If you keep Product, add brand, correct numbers, and accept it is non-rich.
6. FAQPage on 161 pages (160 destinations + /esim-deals). Google retired FAQ rich results for all sites on 2026-05-07, so no SERP benefit. Info priority, not a defect. AI/GEO benefit unconfirmed. Content in the FAQ is also near-duplicate boilerplate across destinations apart from the 1.19 figure (the Q1 answer quotes the wrong destination data, see 1). Fix: either keep as harmless content (visible on page only) or remove to cut payload; do not invest more.

### MEDIUM
7. /hotels has no JSON-LD. Fix: add Organization link + WebPage + Service (B2B hotel guest connectivity); SoftwareApplication only if there is a downloadable/web app listing with price (otherwise it would be ignored); no rich result, benefit is entity clarity. Ready block below (B).
8. Hub /esim/destinations/ has CollectionPage only. Fix: add ItemList (position, name, url) of the 160 destinations plus BreadcrumbList. Hub URL is listed inconsistently: /esim/ serves the esim-deals page (200, duplicate of /esim-deals with canonical to it). Fix: 301 /esim/ to /esim/destinations/ in _redirects.
9. Organization incomplete: no sameAs (Facebook page "Moca - eSIM Market", Instagram, TikTok), no contactPoint, no email, no foundingDate, no address. logo is a 512x512 PNG (OK, 200 image/png, 7.9KB; Google prefers >=112x112, square: passes). Fix: add sameAs + contactPoint (Helpdesk address, but NOTE it is on the taken-down mocaintel.com mail domain; confirm it still receives mail before publishing). Description is Hebrew only while the site is bilingual.
10. Entity graph inconsistent. Org/WebSite use @id (#org, #website) on /, /esim-deals, hub-less; destination pages' Product, FAQPage, BreadcrumbList have no @id and no link to Organization/WebSite/WebPage, and are 3 separate script blocks. Fix: emit one @graph per page with WebPage @id, isPartOf WebSite, breadcrumb referencing, publisher Org.
11. Org/WebSite absent on destination pages (only on / and /esim-deals). Fine technically; add publisher reference inside the page @graph.

### LOW
12. WebSite has no potentialAction SearchAction. Not needed: Google removed the sitelinks search box feature (Nov 2024). The site has no URL-based search anyway. Do not add.
13. WebSite lacks alternateName; add "MOCA eSIM" / "Mobile Operators Competitor Analysis" for site-name signals. Also / and /esim-deals blocks 1 duplicates (Org+WebSite repeated on /esim-deals, same @id, harmless).
14. English variants (?lang=en) share the same Hebrew inLanguage he-IL JSON-LD (checked: JSON-LD is static he). Low impact since canonical = Hebrew URL? Verify: /esim-deals?lang=en canonical in crawl.json.
15. BreadcrumbList is correct: 3 items, positions 1-3, absolute URLs, item 2 /esim/destinations/ exists (200), item 3 = page URL, last-item `item` allowed. Name "eSIM חו\"ל" contains a quote, escaped correctly in JSON. PASS. Hebrew label for item 1 is "MOCA" (brand): fine.
16. mocaintel.com in schema: none (all @id/url/logo/image/item use the netlify origin). Remaining mocaintel.com occurrences: api.mocaintel.com affiliate hrefs (item 3), hotels page text/mailto. Consistent with the takedown intent except item 3.
17. Image property on Product points to /dest-bg/<cc>.webp (200). Decorative background photo, 1200? dimensions unverified; Google wants a representative product image. Minor.
18. Product lacks priceValidUntil (not required for AggregateOffer), priceCurrency ILS present, availability InStock on an aggregate across 29 providers is an unverifiable claim; remove availability.

## Validation checklist summary
- @context https://schema.org: pass everywhere. Dates: no dates used (no dateModified; add dateModified on WebPage since FAQ copy says "16 November 2026").
- Required props: Product has name + offers (passes Google minimum), AggregateOffer has lowPrice + priceCurrency (pass). FAQPage and BreadcrumbList structurally valid. Organization has name/url/logo (valid).
- Values wrong, not malformed: item 1.
- Placeholders: none found. Absolute URLs: pass.

## Ready-to-paste fix A: destination page (replace the 3 blocks with one graph; example Thailand, numbers to be generated from per-destination, trip-sized data)
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebPage",
      "@id": "https://lucent-kulfi-f037ad.netlify.app/esim/thailand/#webpage",
      "url": "https://lucent-kulfi-f037ad.netlify.app/esim/thailand/",
      "name": "eSIM תאילנד - השוואת מחירים בין ספקים | MOCA",
      "inLanguage": "he-IL",
      "isPartOf": { "@id": "https://lucent-kulfi-f037ad.netlify.app/#website" },
      "about": { "@type": "Country", "name": "Thailand" },
      "primaryImageOfPage": { "@type": "ImageObject", "url": "https://lucent-kulfi-f037ad.netlify.app/dest-bg/th.webp" },
      "breadcrumb": { "@id": "https://lucent-kulfi-f037ad.netlify.app/esim/thailand/#breadcrumb" },
      "mainEntity": { "@id": "https://lucent-kulfi-f037ad.netlify.app/esim/thailand/#offers" },
      "dateModified": "2026-11-16"
    },
    {
      "@type": "ItemList",
      "@id": "https://lucent-kulfi-f037ad.netlify.app/esim/thailand/#offers",
      "name": "eSIM לתאילנד - ההצעות הזולות לטיול (5GB ומעלה, 7 ימים ומעלה)",
      "numberOfItems": 5,
      "itemListOrder": "https://schema.org/ItemListOrderAscending",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "<provider> - <GB>GB ל-<days> ימים", "url": "https://lucent-kulfi-f037ad.netlify.app/go/<provider>?dest=thailand" }
      ]
    },
    {
      "@type": "BreadcrumbList",
      "@id": "https://lucent-kulfi-f037ad.netlify.app/esim/thailand/#breadcrumb",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "MOCA", "item": "https://lucent-kulfi-f037ad.netlify.app/" },
        { "@type": "ListItem", "position": 2, "name": "eSIM חו\"ל", "item": "https://lucent-kulfi-f037ad.netlify.app/esim/destinations/" },
        { "@type": "ListItem", "position": 3, "name": "תאילנד", "item": "https://lucent-kulfi-f037ad.netlify.app/esim/thailand/" }
      ]
    }
  ]
}
```
(Template values in angle brackets are generator placeholders to be filled by prerender-esim-dests.mjs, do not ship them literally. FAQPage dropped on purpose: no SERP benefit since 2026-05-07; keep the visible FAQ text if wanted.)

If the team insists on keeping Product, the minimum honest version: name "eSIM תאילנד (השוואה בין ספקים)", brand omitted, offers AggregateOffer with lowPrice = cheapest >=5GB/>=7d package for THAT destination, highPrice = max of same band, offerCount = that band's count, no availability. Expect no rich result.

## Ready-to-paste fix B: /hotels (Organization linked, B2B service)
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://lucent-kulfi-f037ad.netlify.app/#org",
      "name": "MOCA",
      "url": "https://lucent-kulfi-f037ad.netlify.app/",
      "logo": "https://lucent-kulfi-f037ad.netlify.app/icons/icon-512.png",
      "sameAs": ["<facebook page url>", "<instagram url>", "<tiktok url>"]
    },
    {
      "@type": "WebPage",
      "@id": "https://lucent-kulfi-f037ad.netlify.app/hotels#webpage",
      "url": "https://lucent-kulfi-f037ad.netlify.app/hotels",
      "name": "MOCA Guest Connect - חיבור סלולרי לתיירים במלון",
      "inLanguage": "he-IL",
      "isPartOf": { "@id": "https://lucent-kulfi-f037ad.netlify.app/#website" },
      "about": { "@id": "https://lucent-kulfi-f037ad.netlify.app/hotels#service" }
    },
    {
      "@type": "Service",
      "@id": "https://lucent-kulfi-f037ad.netlify.app/hotels#service",
      "name": "MOCA Guest Connect",
      "serviceType": "Tourist eSIM and mobile plan comparison portal for hotels",
      "provider": { "@id": "https://lucent-kulfi-f037ad.netlify.app/#org" },
      "areaServed": { "@type": "Country", "name": "Israel" },
      "audience": { "@type": "BusinessAudience", "audienceType": "Hotels" }
    }
  ]
}
```
Fill sameAs with real profile URLs (do not ship the angle-bracket placeholders). No rich result expected; value is entity/AI clarity.

## Uncertainty notes
- Whether Google ignores or penalizes aggregator Product markup is not publicly specified; rated by documented principles (single product, content must match page).
- FAQ retirement date and scope taken from project reference data (2026-05-07, all sites).
- Did not run Google Rich Results Test (no network access to it from here); validation was by direct JSON parse and manual rule checking.
- Browser rendering not used: markup is static prerendered, so raw HTML equals rendered for schema purposes.
