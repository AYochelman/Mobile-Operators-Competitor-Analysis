/* Build step — emit a prerendered, HYDRATED dist/hotels.html for the hotels
 * marketing page (MOCA Guest Connect, route /hotels).
 *
 * Pipeline (see package.json "build"):
 *   1. vite build                                 → dist/ (SPA + the hotels-client hydration chunk)
 *   2. vite build --ssr src/entry-hotels.jsx ...  → dist-ssr-hotels/entry-hotels.js
 *   3. node scripts/prerender-hotels.mjs          → dist/hotels.html  (this file)
 *
 * Netlify serves hotels.html at /hotels (see public/_redirects), so the page
 * paints instantly from static HTML, then the hotels-client chunk hydrates it
 * to restore the live demo iframe, the ROI calculator and the lead form.
 *
 * Unlike landing.html (zero JS, presentational) this page ships a hydration
 * script. Like landing.html it is written AFTER `vite build`, so the PWA
 * service worker never precaches it — and the SPA /hotels route in App.jsx is
 * the offline / repeat-visit fallback.
 *
 * The <head> here is hand-built (not reused from the SPA's index.html) for two
 * reasons: (1) the component carries its own scoped CSS inline (#hl-app), so it
 * needs NO Tailwind app stylesheet — only the self-hosted fonts; (2) a page-
 * specific canonical + OG block gives links shared to prospects a proper
 * preview, which the generic SPA shell could not.
 */
import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const ssrEntry = resolve(root, 'dist-ssr-hotels/entry-hotels.js')
const assetsDir = resolve(root, 'dist/assets')
const fontsCss = resolve(root, 'dist/fonts/fonts.css')

if (!existsSync(ssrEntry)) throw new Error('prerender-hotels: missing ' + ssrEntry + ' — run the --ssr build first')
if (!existsSync(assetsDir)) throw new Error('prerender-hotels: missing ' + assetsDir + ' — run the client build first')
if (!existsSync(fontsCss)) throw new Error('prerender-hotels: missing dist/fonts/fonts.css — the page would be unstyled')

// 1. render the hotels page to a hydration-compatible HTML string
const { render } = await import(pathToFileURL(ssrEntry).href)
const markup = render()
if (!/<h1/.test(markup) || !/hl-app/.test(markup)) {
  throw new Error('prerender-hotels: rendered markup is missing <h1>/#hl-app — render() likely failed')
}

// 2. locate the hashed client hydration chunk (Vite: assets/hotels-client-[hash].js)
const clientJs = readdirSync(assetsDir).find((f) => /^hotels-client-.*\.js$/.test(f))
if (!clientJs) {
  throw new Error('prerender-hotels: no hotels-client-*.js in dist/assets — is entry-hotels-client.jsx wired into vite.config input?')
}

// 3. hand-built <head> — self-hosted fonts only (component is self-scoped) + a
//    page-specific canonical/OG block for shareable link previews.
const head = `<meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <meta name="theme-color" content="#5c3317" />
    <title>MOCA Guest Connect — eSIM concierge for your hotel guests</title>
    <meta name="description" content="A guest-facing portal, branded in your hotel's colors, that compares every eSIM &amp; tourist-SIM deal in Israel in real time — over 30 global providers and 10 local operators. No inventory, no operations, and a commission to the hotel on every purchase." />
    <link rel="canonical" href="https://mocaintel.com/hotels" />
    <link rel="alternate" hreflang="he" href="https://mocaintel.com/hotels" />
    <link rel="alternate" hreflang="en" href="https://mocaintel.com/hotels?lang=en" />
    <link rel="alternate" hreflang="x-default" href="https://mocaintel.com/hotels" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="apple-touch-icon" href="/icons/icon-180.png" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="MOCA Guest Connect — Wi-Fi &amp; eSIM concierge for hotel guests" />
    <meta property="og:description" content="A portal branded in your hotel's colors that shows guests the best eSIM &amp; SIM deals in Israel, live. Zero operations — and a commission on every purchase." />
    <meta property="og:url" content="https://mocaintel.com/hotels" />
    <meta property="og:image" content="https://mocaintel.com/icons/icon-512.png" />
    <meta property="og:locale" content="he_IL" />
    <meta property="og:locale:alternate" content="en_US" />
    <meta name="twitter:card" content="summary_large_image" />
    <link rel="stylesheet" href="/fonts/fonts.css" />
    <style>html,body{margin:0;background:#f9f4ee}</style>`

// 4. compose. First paint = the SSR markup inside #hotels-root; the module
//    script then hydrates it in place (no flash, no re-paint).
const html = `<!DOCTYPE html>
<html lang="he" dir="rtl">
  <head>
    ${head}
  </head>
  <body>
    <div id="hotels-root">${markup}</div>
    <script type="module" src="/assets/${clientJs}"></script>
  </body>
</html>
`

writeFileSync(resolve(root, 'dist/hotels.html'), html, 'utf8')
console.log(`prerender-hotels: wrote dist/hotels.html (${(html.length / 1024).toFixed(1)} KB) — hydrates via /assets/${clientJs}`)
