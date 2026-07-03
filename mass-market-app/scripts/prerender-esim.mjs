/* Build step — emit dist/esim.html: the SPA shell with an eSIM-specific <head>
 * (self-referencing canonical + title + description + OG) served at /esim-deals.
 *
 * Pipeline (see package.json "build"): runs LAST, after `vite build`.
 *
 * Unlike landing.html / hotels.html this is NOT a standalone static render. It
 * keeps the SPA boot (<script type="module" ...> + modulepreloads) intact, so
 * React Router mounts the live, interactive EsimComparePage. We only swap the
 * <head> meta.
 *
 * Why: the public consumer page /esim-deals (and its esim.mocaintel.com mirror)
 * otherwise inherits index.html's <head>, whose canonical points at the site
 * root. Google then treats the eSIM page as a duplicate of the homepage and
 * drops it from the index. A self-referencing canonical + its own title/OG make
 * it index on its own URL. The esim subdomain is served this same file (see
 * public/_redirects), so its canonical points at the apex /esim-deals too,
 * consolidating all SEO signal on one URL.
 *
 * Written AFTER `vite build`, so the PWA service worker never precaches it (the
 * SPA /esim-deals route stays the offline / repeat-visit fallback).
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const distIndex = resolve(root, 'dist/index.html')
if (!existsSync(distIndex)) throw new Error('prerender-esim: missing ' + distIndex + ' — run the client build first')

const CANON = 'https://mocaintel.com/esim-deals'
const TITLE = 'השוואת מחירי eSIM לטיול בחו"ל - חינם | MOCA'
const DESC = 'השוואת מחירי eSIM חינמית לטיול בחו"ל, בלי הרשמה. מוצאים את החבילה המשתלמת ביותר מתוך למעלה מ-30 ספקי eSIM גלובליים, מתעדכן פעמיים ביום.'
const OG_TITLE = 'השוואת מחירי eSIM לטיול בחו"ל | MOCA'
const OG_DESC = 'מוצאים את חבילת ה-eSIM המשתלמת ביותר לטיול, מושווה על פני למעלה מ-30 ספקים גלובליים ומתעדכן פעמיים ביום. חינם, בלי הרשמה.'

let html = readFileSync(distIndex, 'utf8')

// The Hebrew abbreviation חו"ל carries a literal double-quote, which would close a
// "-delimited attribute early. Escape values injected into ATTRIBUTES (& first,
// then "). Text nodes (<title>) don't need the " escape but do need & < >.
const escAttr = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
const escText = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const swap = (re, to, label) => {
  if (!re.test(html)) throw new Error('prerender-esim: could not find ' + label + ' in dist/index.html')
  html = html.replace(re, to)
}

swap(/<title>[\s\S]*?<\/title>/, `<title>${escText(TITLE)}</title>`, '<title>')
swap(/<meta name="description"[^>]*>/, `<meta name="description" content="${escAttr(DESC)}" />`, 'meta description')
swap(/<meta property="og:title"[^>]*>/, `<meta property="og:title" content="${escAttr(OG_TITLE)}" />`, 'og:title')
swap(/<meta property="og:description"[^>]*>/, `<meta property="og:description" content="${escAttr(OG_DESC)}" />`, 'og:description')
swap(/<meta property="og:url"[^>]*>/, `<meta property="og:url" content="${CANON}" />`, 'og:url')
swap(
  /<link rel="canonical"[^>]*>/,
  `<link rel="canonical" href="${CANON}" />` +
    `<link rel="alternate" hreflang="he" href="${CANON}" />` +
    `<link rel="alternate" hreflang="en" href="${CANON}?lang=en" />` +
    `<link rel="alternate" hreflang="x-default" href="${CANON}" />` +
    `<meta property="og:locale" content="he_IL" />` +
    `<meta property="og:locale:alternate" content="en_US" />`,
  'canonical',
)

writeFileSync(resolve(root, 'dist/esim.html'), html, 'utf8')
console.log(`prerender-esim: wrote dist/esim.html (${(html.length / 1024).toFixed(1)} KB)`)
