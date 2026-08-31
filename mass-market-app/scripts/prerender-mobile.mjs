/* Build step — emit dist/mobile.html: the SPA shell with a domestic-plans
 * <head> (self-referencing canonical + title + description + OG) served at
 * /mobile-deals (and, at launch, the mobile.mocaintel.com mirror).
 *
 * Exact sibling of prerender-esim.mjs — NOT a standalone static render: the SPA
 * boot stays intact so React Router mounts the live MobileComparePage; only the
 * <head> meta is swapped, plus a crawlable pre-JS #root block that createRoot()
 * wipes on boot. Written AFTER `vite build`, so the PWA service worker never
 * precaches it.
 *
 * NOTE (Stage 1): the file is built but unreferenced — no _redirects rule, no
 * sitemap entry — until the public launch flips MOBILE_B2C_LIVE and adds them.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const distIndex = resolve(root, 'dist/index.html')
if (!existsSync(distIndex)) throw new Error('prerender-mobile: missing ' + distIndex + ' - run the client build first')

const CANON = 'https://mocaintel.com/mobile-deals'
const TITLE = 'השוואת חבילות סלולר בישראל - כל המפעילים במקום אחד | MOCA'
const DESC = 'השוואת מחירים חינמית של חבילות סלולר בישראל, בלי הרשמה. מחירים, נפחי גלישה, 5G והטבות מכל 10 המפעילים, מתעדכן פעמיים ביום.'
const OG_TITLE = 'השוואת חבילות סלולר בישראל | MOCA'
const OG_DESC = 'משווים מחירים, נפחי גלישה, 5G והטבות מכל 10 מפעילי הסלולר בישראל. חינם, בלי הרשמה, מתעדכן פעמיים ביום.'

// FAQ — rendered BOTH as visible content in #root (crawlable) and as FAQPage
// JSON-LD (rich-result eligible). Keep the two lists identical.
const FAQ = [
  { q: 'כמה עולה חבילת סלולר בישראל?',
    a: 'המחירים נעים בין כ-10 שקלים לחודש למסלולים בסיסיים ועד כ-130 שקלים לחבילות פרימיום עם 5G מתועדף. רוב החבילות עם נפח גלישה גדול נמצאות בטווח של 20-60 שקלים לחודש. ההשוואה בעמוד מתעדכנת פעמיים ביום מאתרי המפעילים.' },
  { q: 'איך עוברים מפעיל ושומרים על המספר?',
    a: 'ניוד מספר בישראל הוא חינמי: מצטרפים למפעיל החדש אונליין או בטלפון, מוסרים את פרטי הקו, והמעבר מתבצע בדרך כלל תוך יום עסקים בלי לאבד את המספר. אין צורך להודיע למפעיל הישן - המפעיל החדש מטפל בניוד.' },
  { q: 'מה זה 5G מתועדף?',
    a: 'מסלולי פרימיום שמקבלים תיעדוף ברשת ה-5G במצבי עומס, כלומר מהירות גבוהה יותר כשהרשת עמוסה. בעמוד אפשר לסנן לפי "5G מתועדף" ולהשוות רק את המסלולים האלה.' },
  { q: 'האם יש התחייבות במעבר לחבילה חדשה?',
    a: 'רוב חבילות הסלולר בישראל הן ללא התחייבות וניתנות לביטול או שינוי בכל חודש. חלק מהמבצעים כוללים מחיר מוזל לתקופה מוגבלת או מחיר שמותנה במספר קווים - חבילות כאלה מסומנות בעמוד בתגית "מחיר מותנה".' },
]

let html = readFileSync(distIndex, 'utf8')

// Values injected into ATTRIBUTES must escape & then " (Hebrew copy may carry
// a literal double-quote, e.g. חו"ל). Text nodes need & < >.
const escAttr = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
const escText = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const swap = (re, to, label) => {
  if (!re.test(html)) throw new Error('prerender-mobile: could not find ' + label + ' in dist/index.html')
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

// PWA identity: installing from /mobile-deals must produce the domestic
// consumer app (own id/start_url), not the B2B dashboard PWA.
swap(/<link rel="manifest"[^>]*>/, `<link rel="manifest" href="/mobile-manifest.webmanifest" />`, 'manifest link')
swap(/<meta name="apple-mobile-web-app-title"[^>]*>/, `<meta name="apple-mobile-web-app-title" content="MOCA סלולר" />`, 'apple-mobile-web-app-title')

// twitter card copy follows the OG copy. og:image / twitter:image deliberately
// NOT swapped — no page-specific og-mobile.png asset yet, so the site default
// card from index.html stays (better than pointing at a 404).
swap(/<meta name="twitter:title" content="[^"]*"\s*\/>/, `<meta name="twitter:title" content="${escAttr(OG_TITLE)}" />`, 'twitter:title')
swap(/<meta name="twitter:description" content="[^"]*"\s*\/>/, `<meta name="twitter:description" content="${escAttr(OG_DESC)}" />`, 'twitter:description')

// FAQPage + WebPage JSON-LD (the Organization/WebSite @graph is inherited from
// index.html's site-wide head).
const faqJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebPage',
      '@id': CANON + '#webpage',
      url: CANON,
      name: OG_TITLE,
      description: DESC,
      inLanguage: 'he-IL',
      isPartOf: { '@id': 'https://mocaintel.com/#website' },
    },
    {
      '@type': 'FAQPage',
      '@id': CANON + '#faq',
      mainEntity: FAQ.map((f) => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
      })),
    },
  ],
}
const jsonLdTag = `<script type="application/ld+json">${JSON.stringify(faqJsonLd).replace(/</g, '\\u003c')}</script>`
html = html.replace('</head>', `    ${jsonLdTag}\n  </head>`)

// Crawlable pre-JS #root block (h1 + intro + how-to-switch + FAQ). main.jsx
// mounts with createRoot(), which clears #root and renders the live page over
// it — the static markup is a graceful pre-JS paint on the page's cream bg.
const faqHtml = FAQ.map((f) =>
  `<div style="margin:0 auto 14px;max-width:640px;text-align:right">` +
  `<h3 style="font-size:17px;font-weight:700;color:#4a2a13;margin:0 0 4px">${escText(f.q)}</h3>` +
  `<p style="font-size:15px;color:#8a6a4a;margin:0">${escText(f.a)}</p></div>`
).join('')
const rootContent =
  `<div dir="rtl" style="max-width:820px;margin:0 auto;padding:44px 20px;text-align:center;` +
  `font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;color:#3b1f0d">` +
  `<div style="font-size:13px;font-weight:800;letter-spacing:2px;color:#c9622f;text-transform:uppercase;margin-bottom:12px">השוואת חבילות סלולר · חינם</div>` +
  `<h1 style="font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:clamp(28px,6vw,40px);line-height:1.18;margin:0 0 12px;color:#4a2a13">השוואת חבילות סלולר בישראל</h1>` +
  `<p style="font-size:18px;color:#8a6a4a;max-width:620px;margin:0 auto 28px">משווים מחירים, נפחי גלישה, 5G והטבות מכל 10 מפעילי הסלולר בישראל - חינם, בלי הרשמה. המחירים נאספים מאתרי המפעילים ומתעדכנים פעמיים ביום.</p>` +
  `<h2 style="font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:24px;color:#4a2a13;margin:0 0 16px">איך עוברים מפעיל?</h2>` +
  `<div style="max-width:640px;margin:0 auto 32px;text-align:right;color:#3b1f0d;font-size:16px;line-height:1.7">` +
  `<div style="margin-bottom:8px"><b>1. משווים ובוחרים חבילה</b> - מסננים לפי מחיר, נפח גלישה, רשת והטבות.</div>` +
  `<div style="margin-bottom:8px"><b>2. מצטרפים למפעיל החדש</b> - אונליין או בטלפון, בלי לבקר בחנות.</div>` +
  `<div><b>3. המספר עובר איתכם</b> - ניוד חינמי, בדרך כלל תוך יום עסקים.</div></div>` +
  `<h2 style="font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:24px;color:#4a2a13;margin:0 0 16px">שאלות נפוצות</h2>` +
  faqHtml +
  `</div>`
html = html.replace('<div id="root"></div>', `<div id="root">${rootContent}</div>`)
if (!html.includes(`<div id="root">${rootContent}`)) {
  console.warn('prerender-mobile: WARNING - could not inject #root SEO content (marker not found)')
}

writeFileSync(resolve(root, 'dist/mobile.html'), html, 'utf8')
console.log(`prerender-mobile: wrote dist/mobile.html (${(html.length / 1024).toFixed(1)} KB)`)
