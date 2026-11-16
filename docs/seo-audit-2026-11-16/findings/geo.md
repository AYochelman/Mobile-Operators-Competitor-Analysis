# GEO / AI-Search Readiness - lucent-kulfi-f037ad.netlify.app

Audit date: 2026-11-16. Method: live curl with 7 crawler user-agents, extraction of 5 destination pages (japan, greece, thailand, united-states, europe) + /esim-deals + hub, review of pre-fetched robots.txt / llms.txt / sitemap.xml / crawl.json (167 URLs), source read of `mass-market-app/scripts/prerender-esim-dests.mjs` and `api/esim.py`, light brand-presence checks (Bing, Wikipedia). Inferences are marked [inference].

## GEO Readiness Score: 48 / 100

| Dimension | Weight | Score | Weighted | Why |
|---|---|---|---|---|
| Citability | 25% | 35 | 8.75 | Good dated Q&A template, but every destination page quotes the same wrong numbers (see C1) |
| Structural Readability | 20% | 70 | 14.0 | Clean H1/H2, FAQ with question headings, breadcrumbs, visible "updated" date |
| Multi-Modal Content | 15% | 45 | 6.75 | Per-destination OG image, no comparison table, no charts, no video |
| Authority & Brand Signals | 20% | 20 | 4.0 | No own domain, no sameAs, no author/methodology page, no Wikipedia/Reddit/YouTube footprint, Bing shows no indexed pages |
| Technical Accessibility | 20% | 72 | 14.4 | All AI bots get 200 + SSR HTML on static pages; /esim-deals prices are CSR-only, soft-404s, EN hreflang serves Hebrew |

Fixing C1 alone would move Citability to about 65 and the total to about 56. [inference]

## AI crawler access (tested live, 2026-11-16)

Every UA below got HTTP 200 and byte-identical responses on `/`, `/esim-deals`, `/esim/japan/`, `/llms.txt` (no WAF / bot challenge / UA cloaking).

| Crawler | Governs | robots.txt | Live result |
|---|---|---|---|
| OAI-SearchBot | ChatGPT Search citations | Allowed (`*`) | 200, full HTML |
| GPTBot | OpenAI training only | Allowed | 200 |
| Claude-SearchBot | Claude search citations | Allowed | 200 |
| ClaudeBot | Anthropic training only | Allowed | 200 |
| PerplexityBot | Perplexity index | Allowed | 200 |
| Googlebot | Google Search + AI Overviews | Allowed | 200 |
| bingbot | Bing + Copilot (+ ChatGPT Search grounding via Bing [inference]) | Allowed | 200 |
| Google-Extended | Gemini training/grounding (not AIO) | Allowed (`*`) | n/a (robots token only) |
| Applebot-Extended, CCBot, cohere-ai | training | Allowed | not tested |

Note: robots.txt comment lists the AI bots but they rely on the `*` group. Claude-SearchBot and OAI-SearchBot are not named in the comment (cosmetic only).

## llms.txt: present, well-formed, partly stale

- Present at /llms.txt (2,536 B, 200, text). Good H1 + blockquote summary + key facts + Hebrew section.
- Provider names (Airalo, Holafly, Saily, Maya, Nomad, Ubigi, GigSky) verified against `carrierLabels.js`.
- Gaps: no link to the 160 static `/esim/<slug>/` pages or the `/esim/destinations/` hub (the only pages with server-rendered prices); no "last updated" date; "150+ destinations" undersells (~160 pages, ~190 countries per CLAUDE.md); recommends `/esim-deals` as "citable, up-to-date" although its prices are client-rendered and invisible to non-JS crawlers; no methodology statement (how prices are collected, FX basis, affiliate disclosure).

## Findings (severity, evidence, fix)

### C1 - CRITICAL: all 160 destination pages show the same (Israel) deals
- Evidence: japan, greece, thailand, united-states, europe all say "154 חבילות מ-29 ספקים, החל מ-₪1.19 (102MB ל30 ימים אצל eSIM Plus)"; the 10-card lists are byte-identical apart from the country name; crawl.json shows all 160 titles "מ-₪1.19" and all descriptions "154 חבילות". Root cause: `prerender-esim-dests.mjs:209` calls `/api/esim/compare?dest=...` but `api/esim.py:29` reads `request.args.get("destination")` and defaults to `ISRAEL_HE`, so every page is built from the Israel feed (local API confirmed: `destination` echoed back as ישראל for `?dest=יפן`). The SPA (`src/lib/api.js:326`) correctly uses `?destination=`.
- Impact: every FAQ answer and Product/AggregateOffer schema on 160 pages is factually wrong; an AI engine quoting "eSIM to Japan from ₪1.19" is quoting an Israel package. Misleading structured data also risks a Google manual action. [inference on the manual action]
- Fix: change line 209 to `?destination=` (or make the API accept both), rebuild, redeploy, re-ping IndexNow; add a build guard that fails when more than ~20% of pages share the same min price/plan count.

### H1 - HIGH: "starts at" headline uses a non-trip-sized package
- Evidence: the lead answer is a 102MB plan at ₪1.19; the product itself knows this is meaningless (`get_esim_alert_floor` uses >=5GB/>=7d per CLAUDE.md).
- Fix: lead each page with tiered, quotable facts: cheapest 1GB/7d, 5GB/7d, 10GB/30d, unlimited 7d, each with provider + price + date; keep "from ₪X" as a secondary line.

### H2 - HIGH: no English content for AI answers
- Evidence: 161 of 167 URLs have no hreflang; all `/esim/<slug>/` pages are `lang="he"` only; `/esim-deals?lang=en` returns the same Hebrew HTML (Hebrew title, Hebrew FAQ) while sitemap/hreflang declares it the English alternate.
- Fix: prerender `/en/esim/<slug>/` (or `?lang=en` variants as separate static files) with English FAQ and reciprocal hreflang; until then remove the `en` hreflang from `/esim-deals` or make the prerender emit English head + FAQ for `?lang=en`.

### H3 - HIGH: brand/entity is effectively invisible
- Evidence: Bing `site:lucent-kulfi-f037ad.netlify.app` returned no results from the site (scraped SERP, weak signal [inference]); no Wikipedia article; Organization JSON-LD has no `sameAs`, describes MOCA as the B2B CI product, not the consumer eSIM comparison; no author, about, or methodology page.
- Constraint cost [inference]: netlify.app is on the Public Suffix List, so the subdomain is treated as its own site (no shared-domain penalty), but the random hostname carries no brand token, cannot earn branded navigational queries, and every link/mention earned now is lost if the canonical later moves to mocaintel.com unless 301s are possible (they are not from a Netlify subdomain to a custom domain without keeping the site).
- Fix within the constraint: (a) add `sameAs` to the MOCA Instagram / Facebook "Moca - eSIM Market" / TikTok profiles and make each profile link back to the netlify URL; (b) add a consumer `Organization`/`WebSite` node for "MOCA eSIM" with `knowsAbout` and `areaServed: IL`; (c) publish an `/about` + `/methodology` page (who runs it, how prices are scraped, update cadence, FX basis, affiliate disclosure) and reference it from llms.txt; (d) seed genuine mentions in Israeli travel communities (Facebook groups, Reddit r/Israel / r/travel threads, Hebrew travel blogs) and a short YouTube explainer, since YouTube/Reddit mentions correlate most with AI citations; (e) consider a neutral brand subdomain on a domain the employer agreement allows, decided by Alon, not in this audit.

### H4 - HIGH: /esim-deals price content is client-side only
- Evidence: raw HTML seen by OAI-SearchBot/PerplexityBot is 187 words: H1, 3-step how-to, 4 FAQs, no prices or providers.
- Fix: keep the SPA, but inject a static "cheapest deals today for top 10 destinations" table into `esim.html` at build time (the prerender already has the data), linking to the `/esim/<slug>/` pages.

### M1 - MEDIUM: FAQs are 75% boilerplate across 160 pages
- Evidence: 3 of 4 FAQ answers are identical on every destination page; only "how much" varies.
- Fix: add 2-3 destination-specific Q&As generated from data (best value per GB, best unlimited, number of providers with local vs roaming network, typical trip size), plus one local fact (e.g. supported networks) where available.

### M2 - MEDIUM: soft 404s
- Evidence: `/esim/atlantis-xyz/`, `/nope-page`, `/esim-deals/foo` all return 200 with the SPA shell.
- Fix: in `_redirects`, return a real 404 page for unknown `/esim/*` paths (`/esim/*  /404.html  404` after the explicit page rules), and let the SPA route-not-found render `noindex`.

### M3 - MEDIUM: incomplete deal facts
- Evidence: 10 cards across 5 pages show "1GB · " with no validity (Terminal eSIM, Bcengi).
- Fix: render "תוקף לא צוין" or hide validity-less plans from the top-10 list; citable passages need complete tuples (data, days, price, provider).

### M4 - MEDIUM: IndexNow is manual
- Evidence: key file `/847f1f3063de3170789ee85703e90cf6.txt` is live (200); `scripts/indexnow-ping.mjs` header says "Run AFTER every Netlify deploy (manual)", not wired into `deploy-frontend.yml`.
- Fix: add a post-verify step in `deploy-frontend.yml` that runs the ping; pages change daily, and Bing/Copilot freshness depends on it.

### L1 - LOW: freshness signals only in visible text
- Evidence: visible "עודכן 16 בנובמבר 2026" and dated FAQ answer (good); no `dateModified` in JSON-LD; sitemap `lastmod` is the build date for all 163 entries (accurate only if rebuilt daily).
- Fix: add `dateModified` to a `WebPage` node per destination page; keep sitemap lastmod tied to actual data change.

### L2 - LOW: schema type choice
- Evidence: `Product` + `AggregateOffer` for "eSIM ליפן" without brand/reviews.
- Fix: after C1, keep AggregateOffer but nest under a `WebPage`/`ItemList` of offers with `seller` per provider; or use `ItemList` of `Offer`s. Validate in Rich Results Test.

### L3 - LOW: llms.txt staleness (see section above)
- Fix: add hub + top destination links (after C1), date line, methodology link, English deep-link example.

## Positive signals
- Static SSR destination pages (~360 words each) with H1, question-based FAQ H3s, breadcrumbs, FAQPage + BreadcrumbList schema.
- Visible update date and dated, self-contained "how much" answer: the template is right, the data is wrong.
- Affiliate disclosure on every destination page footer.
- llms.txt exists and is bilingual; robots.txt explicitly documents the allow-AI policy.
- No bot blocking, no cloaking, fast responses (0.5-0.8 s).

## Platform notes
| Platform | Score | Notes |
|---|---|---|
| Google AI Overviews | 35 | Hebrew SSR pages are indexable, but C1 data errors and boilerplate FAQs; AIO favors pages already ranking; zero brand authority |
| ChatGPT Search | 30 | Depends on OAI-SearchBot (allowed) and Bing index [inference]; Bing shows no pages; IndexNow not automated |
| Perplexity | 40 | PerplexityBot allowed, likes dated numeric passages; would cite C1 errors as-is |
| Bing Copilot | 30 | Same Bing index gap; IndexNow key live but pings manual |

## Top 5 changes (impact, effort)
1. Fix `?dest=` -> `?destination=` in prerender + identical-data build guard, redeploy, ping IndexNow (critical, 30 min).
2. Tiered, trip-sized "cheapest" answers per destination + 2-3 data-driven unique FAQs (high, 1 day).
3. English static destination pages + correct hreflang; fix `/esim-deals?lang=en` head/FAQ (high, 1-2 days).
4. Entity layer: sameAs to social profiles, /about + /methodology page, llms.txt refresh, community/YouTube mentions (high, 1 day + ongoing).
5. Automate IndexNow in deploy workflow + static top-destinations table in `esim.html` + real 404s (medium, half a day).

## audit-data.json (AI Search Readiness)
```json
{
  "category": "AI Search Readiness",
  "score": 48,
  "dimensions": {"citability": 35, "structure": 70, "multimodal": 45, "authority": 20, "technical": 72},
  "crawler_access": {"OAI-SearchBot": "allowed_200", "GPTBot": "allowed_200", "Claude-SearchBot": "allowed_200", "ClaudeBot": "allowed_200", "PerplexityBot": "allowed_200", "Googlebot": "allowed_200", "bingbot": "allowed_200", "Google-Extended": "allowed_robots"},
  "llms_txt": "present_partly_stale",
  "findings": [
    {"id": "C1", "severity": "critical", "title": "All 160 destination pages built from Israel feed (dest vs destination param)", "file": "mass-market-app/scripts/prerender-esim-dests.mjs:209"},
    {"id": "H1", "severity": "high", "title": "Headline price uses 102MB non-trip package"},
    {"id": "H2", "severity": "high", "title": "No English destination content; en hreflang serves Hebrew"},
    {"id": "H3", "severity": "high", "title": "No entity signals: no sameAs, no about/methodology, no third-party mentions, netlify.app hostname"},
    {"id": "H4", "severity": "high", "title": "/esim-deals prices client-rendered only"},
    {"id": "M1", "severity": "medium", "title": "75% boilerplate FAQs"},
    {"id": "M2", "severity": "medium", "title": "Soft 404s on unknown paths"},
    {"id": "M3", "severity": "medium", "title": "Deal cards missing validity days"},
    {"id": "M4", "severity": "medium", "title": "IndexNow ping manual"},
    {"id": "L1", "severity": "low", "title": "No dateModified in schema"},
    {"id": "L2", "severity": "low", "title": "Product schema without brand/seller structure"},
    {"id": "L3", "severity": "low", "title": "llms.txt missing hub links, date, methodology"}
  ]
}
```
