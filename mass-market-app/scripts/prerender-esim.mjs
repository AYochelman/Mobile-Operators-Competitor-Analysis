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
if (!existsSync(distIndex)) throw new Error('prerender-esim: missing ' + distIndex + ' - run the client build first')

const CANON = 'https://mocaintel.com/esim-deals'
const TITLE = 'השוואת מחירי eSIM לטיול בחו"ל - חינם | MOCA'
const DESC = 'השוואת מחירי eSIM חינמית לטיול בחו"ל, בלי הרשמה. מוצאים את החבילה המשתלמת ביותר מתוך למעלה מ-30 ספקי eSIM גלובליים, מתעדכן פעמיים ביום.'
const OG_TITLE = 'השוואת מחירי eSIM לטיול בחו"ל | MOCA'
const OG_DESC = 'מוצאים את חבילת ה-eSIM המשתלמת ביותר לטיול, מושווה על פני למעלה מ-30 ספקים גלובליים ומתעדכן פעמיים ביום. חינם, בלי הרשמה.'
const OG_IMG = 'https://mocaintel.com/og/og-esim.png'

// FAQ — rendered BOTH as visible content in #root (crawlable) and as FAQPage
// JSON-LD (rich-result eligible). Keep the two lists identical.
const FAQ = [
  { q: 'האם ה-eSIM עובד בטלפון שלי?',
    a: 'רוב הטלפונים מ-2018 ואילך תומכים ב-eSIM: אייפון XS ומעלה, סמסונג גלקסי S20 ומעלה וגוגל פיקסל 3 ומעלה. אפשר לבדוק בהגדרות הטלפון אם קיימת אפשרות להוספת eSIM.' },
  { q: 'איך מתקינים את ה-eSIM?',
    a: 'רוכשים אונליין בכ-2 דקות, מקבלים קוד QR למייל, סורקים אותו והטלפון מתקין את החבילה אוטומטית. אפשר להתקין עוד לפני הטיסה ולנחות כבר מחוברים.' },
  { q: 'כמה דאטה צריך לשבוע בחו"ל?',
    a: 'לשימוש קל (ניווט והודעות) מספיקים כ-3GB, לשימוש רגיל (רשתות חברתיות) כ-10GB, ולשימוש כבד עם וידאו כדאי 20GB ומעלה או חבילה ללא הגבלה.' },
  { q: 'האם צריך להירשם או למסור פרטים ל-MOCA?',
    a: 'לא. השוואת המחירים חינמית לחלוטין ובלי הרשמה. הרכישה עצמה מתבצעת ישירות באתר ספק ה-eSIM שתבחרו.' },
]

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

// PWA identity: the generic /manifest.json is the B2B dashboard app (start_url
// "/", name MOCA). Installing from /esim-deals (or esim.mocaintel.com) must
// produce the CONSUMER app — its own name/icon label, start_url back to
// /esim-deals with pwa attribution, id "/esim-deals" so Chrome treats it as a
// separate installable app from the dashboard PWA.
swap(/<link rel="manifest"[^>]*>/, `<link rel="manifest" href="/esim-manifest.webmanifest" />`, 'manifest link')
swap(/<meta name="apple-mobile-web-app-title"[^>]*>/, `<meta name="apple-mobile-web-app-title" content="MOCA eSIM" />`, 'apple-mobile-web-app-title')

// Page-specific share image + Twitter card (index.html's default points at the
// home card / home copy — override for the eSIM page).
swap(/<meta property="og:image" content="[^"]*"\s*\/>/, `<meta property="og:image" content="${OG_IMG}" />`, 'og:image')
swap(/<meta property="og:image:alt" content="[^"]*"\s*\/>/, `<meta property="og:image:alt" content="${escAttr(OG_TITLE)}" />`, 'og:image:alt')
swap(/<meta name="twitter:title" content="[^"]*"\s*\/>/, `<meta name="twitter:title" content="${escAttr(OG_TITLE)}" />`, 'twitter:title')
swap(/<meta name="twitter:description" content="[^"]*"\s*\/>/, `<meta name="twitter:description" content="${escAttr(OG_DESC)}" />`, 'twitter:description')
swap(/<meta name="twitter:image" content="[^"]*"\s*\/>/, `<meta name="twitter:image" content="${OG_IMG}" />`, 'twitter:image')

// FAQPage + WebPage JSON-LD. The Organization/WebSite @graph is inherited from
// index.html's head (site-wide); this adds the page-level rich-result markup.
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

// A1 (biggest SEO win): the esim SPA shell shipped an EMPTY <div id="root">, so
// crawlers/social/LLM bots saw zero content until React booted and fetched the
// API. Inject a real, crawlable above-the-fold block (h1 + intro + how-it-works
// + FAQ). main.jsx mounts with createRoot(), which CLEARS #root and renders the
// live interactive page over it — no hydration mismatch, and the static markup
// is a graceful pre-JS paint (matches the page's cream background, so no flash).
const faqHtml = FAQ.map((f) =>
  `<div style="margin:0 auto 14px;max-width:640px;text-align:right">` +
  `<h3 style="font-size:17px;font-weight:700;color:#4a2a13;margin:0 0 4px">${escText(f.q)}</h3>` +
  `<p style="font-size:15px;color:#8a6a4a;margin:0">${escText(f.a)}</p></div>`
).join('')
const rootContent =
  `<div dir="rtl" style="max-width:820px;margin:0 auto;padding:44px 20px;text-align:center;` +
  `font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;color:#3b1f0d">` +
  `<div style="font-size:13px;font-weight:800;letter-spacing:2px;color:#c9622f;text-transform:uppercase;margin-bottom:12px">השוואת eSIM · חינם</div>` +
  `<h1 style="font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:clamp(28px,6vw,40px);line-height:1.18;margin:0 0 12px;color:#4a2a13">כמה תשלמו על אינטרנט בטיול הבא בחו"ל?</h1>` +
  `<p style="font-size:18px;color:#8a6a4a;max-width:620px;margin:0 auto 28px">השוואת מחירים חינמית, בלי הרשמה. מוצאים את חבילת ה-eSIM המשתלמת ביותר לטיול, מושווה על פני למעלה מ-30 ספקי eSIM גלובליים ומתעדכן פעמיים ביום.</p>` +
  `<h2 style="font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:24px;color:#4a2a13;margin:0 0 16px">פעם ראשונה עם eSIM?</h2>` +
  `<div style="max-width:640px;margin:0 auto 32px;text-align:right;color:#3b1f0d;font-size:16px;line-height:1.7">` +
  `<div style="margin-bottom:8px"><b>1. רוכשים אונליין ב-2 דקות</b> - בלי חנות ובלי תור, משלמים בכרטיס וזהו.</div>` +
  `<div style="margin-bottom:8px"><b>2. סורקים QR שמגיע במייל</b> - הטלפון מתקין את החבילה אוטומטית.</div>` +
  `<div><b>3. נוחתים מחוברים</b> - וואטסאפ והמספר מהבית ממשיכים לעבוד במקביל.</div></div>` +
  `<h2 style="font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:24px;color:#4a2a13;margin:0 0 16px">שאלות נפוצות</h2>` +
  faqHtml +
  `</div>`
html = html.replace('<div id="root"></div>', `<div id="root">${rootContent}</div>`)
if (html.includes(`<div id="root">${rootContent}`)) {
  // ok
} else {
  console.warn('prerender-esim: WARNING - could not inject #root SEO content (marker not found)')
}

writeFileSync(resolve(root, 'dist/esim.html'), html, 'utf8')
console.log(`prerender-esim: wrote dist/esim.html (${(html.length / 1024).toFixed(1)} KB)`)
