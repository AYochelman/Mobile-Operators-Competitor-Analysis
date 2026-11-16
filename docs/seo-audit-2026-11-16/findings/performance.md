# Performance / CWV audit - https://lucent-kulfi-f037ad.netlify.app (2026-11-16)

Data source: LAB ONLY, one machine, single runs. No CrUX/PSI credentials (google_auth.py --check: tier -1, no API key; PSI keyless = rate limited, so fallback used).
Method: local Playwright Chromium, mobile emulation 412x823 DPR 2.6, CDP throttle 150ms RTT / ~1.6 Mbps, CPU 4x (TBT/LCP rows); transfer bytes from a second unthrottled run (CDP encodedDataLength). No Lighthouse score exists; the scores below are my judgement.

Scores (judgement, not Lighthouse): Performance 64/100, Images 70/100.

## Measured (lab, mobile profile)
| Page | TTFB | FCP | LCP (element) | CLS | TBT (4x CPU) | Requests | Transfer | JS | CSS | Img | Font |
|---|---|---|---|---|---|---|---|---|---|---|---|
| / | 0.3s | 1.5s | 1.96s - IMG banners-wall.webp (85KB, preloaded) | 0 in 2 runs; 0.855 in 1 run (see note) | 50ms | 13 | 306KB | 0 | 13KB | 253KB | 30KB |
| /esim-deals | 0.3s | 1.1s | 1.06s - P text | 0.19 (0.155 esim-help card + ~0.04 pill buttons) | 955ms | 39 | 309KB | 204KB | 13KB | 53KB | 30KB |
| /hotels | 0.3s | 1.7s | 1.70s - P.lead text | 0.29 | 2405ms (16 long tasks, max 1.07s) | 38 | 279KB | 209KB | 13KB | 0 | 41KB |
| /esim/thailand/ | 0.3s | 0.8s | 1.48s - DIV.hero bg th.webp (49KB) | 0.007 | 203ms | 14 | 216KB | 0 | 0.5KB | 170KB | 41KB |
INP: not measurable in lab; TBT is the proxy. Pass/fail (lab): LCP good on all 4 (<2.5s). CLS fails on /esim-deals (0.19, needs improvement) and /hotels (0.29, poor). TBT is high on /hotels and /esim-deals.
Note landing CLS: the first harness run (instant 3000px wheel jump) reported 0.855; two later runs with throttling and gradual scroll gave 0. Treat as unverified/intermittent; recheck in field data.

## Findings
1. HIGH - Hashed build assets are not cached. /assets/*.js|css and /fonts/*.woff2, /logos/*.png all return Cache-Control: public,max-age=0,must-revalidate (curl verified). Only /dest-bg/*.webp has max-age=2592000. Every repeat visit pays a revalidation round trip per asset (35-39 requests on the SPA pages; hotels showed 304s). Fix: in public/_headers add `/assets/*` -> `Cache-Control: public, max-age=31536000, immutable`; same for `/fonts/*`, `/logos/*`, `/dest-bg/*` (use a long max-age, immutable only if filenames are hashed). Keep HTML at max-age=0,must-revalidate.
2. HIGH - /hotels loads the whole app twice. The demo iframe (/guest/demo?lang=en) is eager and boots the full SPA (main, vendor-react, vendor-supabase 52KB, GuestPortalPage, Logo, useAuth...) plus an /api/auth/logout call. Result: TBT 2.4s, 16 long tasks, load 4.0s vs 1.9s elsewhere, ~210KB JS. Fix: loading="lazy" on the iframe or load it on click/IntersectionObserver (facade with a poster image); remove the Supabase client from the guest portal route.
3. HIGH - /hotels CLS 0.28 at ~1.7-2.3s: DIV.stats shifts up 28px, `::after` pseudo height 213>240. Cause looks like font swap (latin-ext + latin loaded after first paint; page preloads no fonts) plus hydration. Fix: preload assistant-hebrew + assistant-latin woff2 on /hotels (landing already preloads hebrew), add a metric-matched fallback (size-adjust/ascent-override) to @font-face in fonts.css, give .stats a fixed min-height.
4. MEDIUM - /esim-deals CLS 0.19: SECTION.card.esim-help moves 354px>578px at ~2.4s (content injected after the destinations API response, which comes from the other origin), and the BUTTON.pop destination pills reflow horizontally (font swap / late data). Fix: reserve space/skeleton for the destinations block and the help card, render pills with fixed min-width or from the prerender, preload the latin font.
5. MEDIUM - /esim-deals TBT 955ms: public marketing page ships vendor-supabase (52KB), useAuth, navFlags, Logo and the dashboard providers, and fires /api/auth/logout and /api/esim/event on load. Fix: lazy-load Supabase only on login routes; skip logout call when no session; defer the event beacon (requestIdleCallback). 17 script requests, 10 modulepreloads, many are tiny chunks (<1KB): merge via manualChunks.
6. MEDIUM - API on a different origin (terra-nonrestrained-overpiteously.ngrok-free.dev) with no preconnect. Add `<link rel=preconnect href=https://terra-...ngrok-free.dev crossorigin>` to the /esim-deals head (prerender-esim.mjs) and /hotels; better, inline the destinations JSON (5.4KB) into the prerendered HTML so first paint does not depend on the tunnel. ngrok free edge adds a latency/interstitial risk; this host is the single point of failure for content.
7. MEDIUM - Third-party flag SVGs on /esim-deals: https://flagcdn.com/*.svg, 11 images, no width/height attributes, es.svg alone is 48KB (rendered ~20px, natural 1235px wide). Fix: self-host a trimmed flag sprite or use emoji/tiny inline SVG, or request flagcdn raster `w40/xx.png` (a few hundred bytes), and set width/height.
8. MEDIUM - Provider logos on /esim/thailand/ are PNG, 20-29KB each for a 40px slot (natural 112-512px, up to 12x the CSS size): terminalesim.png 29KB, esim70.png 27KB, esimplus.png 23KB, bnesim.png 20KB; 10 imgs, none with width/height (CLS stays low only because boxes are CSS-sized). Fix: convert to WebP/AVIF at 80x80 (2x), expected 1-3KB each (~150KB saved on this page; the sitemap has ~1,632 <img>, mostly logos, so this repeats site-wide), add width/height. They are lazy-loaded (10/10), good.
9. LOW - Landing / : LCP image banners-wall.webp is 1100px wide shown at 352 CSS px (2.6x DPR = 924px needed); 85KB. A 960px or srcset variant saves ~30%. Preload is declared twice (duplicate `<link rel=preload as=image>`); remove one. 6 of 16 images oversized >2.5x; 14/16 lazy, all have width/height, all WebP - good. Landing has zero JS and passes everything; CLS shift risk only with the unverified 0.855 run.
10. LOW - Render-blocking: /fonts/fonts.css (358 bytes) is a separate blocking stylesheet on every page (landing even links it twice), costing an RTT before first paint. Inline it into the head (it is ~358B) or merge into main CSS; main-*.css (12.4KB br) blocks on the SPA pages, acceptable. Only fonts are `font-display` - verify it is `swap`/`optional`; weights 400-800 are a variable font, 3 files ~41KB on hotels/thailand (latin-ext not needed for Hebrew/English pages; drop it or use unicode-range only).
11. LOW - Compression: assets are brotli; HTML document ~3.6-11KB transfer. Fine. Document Cache-Control as stated (max-age=0,must-revalidate) is right for HTML.

## Images site-wide (from measured pages; sitemap not crawled for this report beyond what the prerender pages showed)
- Formats: landing all WebP (good); dest-bg WebP with 30-day cache (good); provider logos PNG (bad, finding 8); flags remote SVG (finding 7).
- Lazy-loading: 14/16 on landing, 11/11 esim-deals, 10/10 thailand. Hero/LCP images are not lazy (correct). Check that no above-the-fold logo is lazy on the 160 dest pages.
- width/height attributes: present on landing, MISSING on /esim-deals (11/11) and /esim/thailand/ (10/10). Likely the same on all ~160 dest pages.
- Alt: present on all measured imgs.
- Oversized: landing 6/16, thailand 8/10 (logos), esim-deals 11/11 (flags).

## Priorities
1. Immutable caching for /assets, /fonts, /logos (one _headers edit, biggest repeat-visit win).
2. Lazy-load the /hotels demo iframe (TBT 2.4s -> ~0.3s expected).
3. Fix CLS on /hotels and /esim-deals (font preload + fallback metrics, reserved space).
4. Re-encode logos to small WebP and add width/height on esim pages.
5. Preconnect/inline API data on /esim-deals; drop Supabase from public routes.
