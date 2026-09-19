/* Notify search engines (Bing/Yandex and everyone on the IndexNow network) that
 * MOCA's public pages changed. ChatGPT Search answers come from Bing's index,
 * so a fast Bing index = faster presence in AI answers.
 *
 * Run AFTER every Netlify deploy (manual):
 *   node scripts/indexnow-ping.mjs
 *
 * The key file public/847f1f3063de3170789ee85703e90cf6.txt must be live at
 * <SITE_ORIGIN>/<key>.txt (it ships inside dist/ automatically) - IndexNow
 * validates ownership by fetching it. A 200/202 response = accepted. The host
 * must be the one that actually serves, so it is derived from SITE_ORIGIN.
 */
import { SITE_ORIGIN } from '../src/data/siteOrigin.js'

const KEY = '847f1f3063de3170789ee85703e90cf6'
const HOST = new URL(SITE_ORIGIN).host
const URLS = [
  `${SITE_ORIGIN}/`,
  `${SITE_ORIGIN}/esim-deals`,
  `${SITE_ORIGIN}/esim-deals?lang=en`,
  `${SITE_ORIGIN}/hotels`,
  `${SITE_ORIGIN}/llms.txt`,
]

// Programmatic destination pages (dist/esim-pages.json is written by
// prerender-esim-dests.mjs at build time) - ping them too when present.
try {
  const { readFileSync } = await import('node:fs')
  const manifest = JSON.parse(readFileSync('dist/esim-pages.json', 'utf8'))
  URLS.push(...manifest.urls.filter(u => !URLS.includes(u)))
} catch { /* no manifest in this build - ping the base list only */ }

const res = await fetch('https://api.indexnow.org/indexnow', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
  body: JSON.stringify({
    host: HOST,
    key: KEY,
    keyLocation: `https://${HOST}/${KEY}.txt`,
    urlList: URLS,
  }),
})
console.log(`IndexNow: HTTP ${res.status} ${res.statusText} for ${URLS.length} URLs`)
if (res.status >= 400) {
  console.error(await res.text())
  process.exit(1)
}
