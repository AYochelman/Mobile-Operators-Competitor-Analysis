# Technical SEO audit - lucent-kulfi-f037ad.netlify.app (2026-11-16)
Score: 68/100. Observed unless marked (inferred).

HIGH
- Soft 404: /zzz, /esim/zzzz/, /.well-known/security.txt all return 200 with the generic SPA shell (title "MOCA - ...", canonical = "/"). Fix: add `/* /404.html 404` after the SPA rules, and serve real 404 for unknown /esim/* (the SPA routes can stay explicit rewrites).
- Netlify host as canonical: no brand equity, Ahrefs DR 0 (per notes), *.netlify.app shared domain, mocaintel.com and www both fail DNS (curl code 000). Static files still carry the literal origin. Fix: restore a custom domain ASAP; until then keep canonicals self-consistent (they are).
- hreflang/lang mismatch: sitemap lists /?lang=en, /hotels?lang=en, /esim-deals?lang=en with hreflang en, but each canonicalises to the Hebrew URL and serves <html lang="he"> (raw HTML). Google will ignore the en alternates (non-self-canonical pair). Fix: remove ?lang=en URLs from sitemap and hreflang, or give real prerendered /en/ paths with self canonicals and lang="en".

MEDIUM
- /esim-deals needs JS for the interactive content: raw HTML (11 KB, 187 words) has an h1 + intro + FAQ JSON-LD, but 0 anchor links and no plan/price data; all deals load client-side. Non-JS crawlers see only the intro. Fix: prerender top deals/links into the shell, or link to /esim/destinations/ in the shell.
- Sitemap omits /privacy /terms /cookies /accessibility (low SEO value, but linked sitewide) and /esim/destinations/ is present only via crawl (in sitemap: yes, 167 URLs). Fix: add legal pages or leave out deliberately.
- Sitemap lastmod: 163 URLs = 2026-11-16 (looks build-stamped, i.e. every URL updated every deploy - inferred, not content-based), 4 URLs (/, /?lang=en, /hotels, /hotels?lang=en) = 2026-06-12 stale. Fix: use real content change dates; Google discounts uniformly-stamped lastmod.
- Duplicate-content aliases return 200 (canonical-handled): /index.html, /landing.html, /esim.html, /hotels.html, /privacy.html, /hotels/, /esim-deals/, /privacy/, /sitemap.xml/, /home. Fix: 301 the .html variants to clean URLs in _redirects (force=true).
- Duplicate titles/descriptions: 3 pairs, all from ?lang=en vs base (consequence of the hreflang issue above).
- Hotels page: title/description English-only on the Hebrew-canonical URL; no JSON-LD (schema=[]). Fix: add Organization/Product/FAQ schema and decide target language.
- Cache-Control is `public,max-age=0,must-revalidate` on HTML and sitemap/robots (fine for HTML). Not verified: hashed /assets/* long-cache (a probe of /assets/ was only the SPA fallback). Check an actual hashed file (inferred OK).

LOW
- 161 /esim/<dest>/ pages have no hreflang (Hebrew-only, acceptable; add self hreflang he + x-default optionally).
- Homepage has 2 h1 (he + hidden en, both in DOM). Fix: render only the active language's h1 or demote the other to a div/aria-hidden.
- /esim/ 301 -> /esim (200, canonical /esim-deals) and /esim/europe 301 -> /esim/europe/: works, but /esim URL variant is an indexable-duplicate; canonical covers it. Chain depth 1.
- 149 of 160 destination pages receive only 1 internal link (the hub /esim/destinations/); 10 are linked from all pages, so 150 are 1-click-deep orphan-adjacent. Fix: add related/nearby-destination links per page.
- /hotels is in sitemap but has 0 inbound links in the crawl set (home links: /accessibility /cookies /esim-deals /esim/destinations/ /login /privacy /terms). Fix: link /hotels from the home footer/nav.
- Home links to /login (disallowed in robots; ok) - nofollow optional.
- robots.txt: valid. `Allow: /` + Disallows; AI crawlers allowed; Sitemap declared and validated (urlset valid). Disallow:/home etc. are prefixes (e.g. /history, /content) - verify no public page begins with these (inferred, none in sitemap). Disallowed paths still return 200 SPA shell with canonical "/" if fetched.
- sitemap_discovery helper: /sitemap_index.xml returned 200 with an HTML doc (SPA fallback, "DOCTYPE not allowed") - another soft-404 symptom.

PASS
- HTTP -> HTTPS 301 on same host. Single-hop. www on netlify subdomain does not exist (n/a).
- Sitemap: 167 URLs, all 200, no redirects (final == url for all), canonical == url for 164/167.
- Titles/descriptions/canonical present on all 167; word count min 187, median 361; 0 images missing alt; max response 1007 ms, TTFB fine.
- Security headers: HSTS (1y, includeSubDomains, preload), CSP (default-src self; allows unsafe-inline scripts/styles - weakness), X-Frame-Options SAMEORIGIN, nosniff, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy. No COOP/CORP (minor).
- Mobile: viewport width=device-width, initial-scale=1, viewport-fit=cover; theme-color; manifest. Font preload + LCP image preload on home.
- Structured data: 160 dest pages Product+AggregateOffer+FAQPage+BreadcrumbList; home Organization+WebSite; /esim-deals WebPage+FAQPage (FAQ rich results restricted since 2023, low value - inferred). Hub CollectionPage.
- Home is a static prerender (49 KB, 1,106 words), no JS needed.
- No X-Robots-Tag and no meta robots noindex on any page.
- og:image set on audited pages; /og/og-home.png 200; llms.txt 200.
