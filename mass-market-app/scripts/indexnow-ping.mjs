/* Notify search engines (Bing/Yandex and everyone on the IndexNow network) that
 * MOCA's public pages changed. ChatGPT Search answers come from Bing's index,
 * so a fast Bing index = faster presence in AI answers.
 *
 * Run AFTER every Netlify deploy (manual):
 *   node scripts/indexnow-ping.mjs
 *
 * The key file public/847f1f3063de3170789ee85703e90cf6.txt must be live at
 * https://mocaintel.com/<key>.txt (it ships inside dist/ automatically) -
 * IndexNow validates ownership by fetching it. A 200/202 response = accepted.
 */
const KEY = '847f1f3063de3170789ee85703e90cf6'
const HOST = 'mocaintel.com'
const URLS = [
  'https://mocaintel.com/',
  'https://mocaintel.com/esim-deals',
  'https://mocaintel.com/esim-deals?lang=en',
  'https://mocaintel.com/hotels',
  'https://mocaintel.com/llms.txt',
]

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
