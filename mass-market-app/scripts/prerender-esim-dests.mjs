/* Programmatic SEO: generate ~150 static per-destination eSIM comparison pages
 * (dist/esim/<slug>/index.html) + a hub page (dist/esim/index.html), inject
 * Product/FAQ JSON-LD into dist/esim.html, and append everything to the sitemap.
 *
 * Runs LAST in the npm build chain (after stamp-sitemap.mjs). Data comes from the
 * local Flask API (must be running on :5000 - it always is on the build machine).
 * If the API is unreachable the script WARNS and exits 0 so the build still
 * succeeds - but the deploy will then carry no destination pages, so check the
 * build log before deploying an SEO-related change.
 *
 * Affiliate buttons go through https://api.mocaintel.com/go/<provider> with
 * dest + src=esim + campaign=seo_dest, so clicks are attributed like the live
 * compare page but distinguishable in the click log. rel="sponsored nofollow"
 * keeps Google happy about paid links.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { DEST_BG_BY_HE } from '../src/data/destBg.js'
import { GLOBAL_LABELS } from '../src/data/carrierLabels.js'

const API = process.env.ESIM_API_BASE || 'http://localhost:5000'
const SITE = 'https://mocaintel.com'
const GO_BASE = 'https://api.mocaintel.com/go'
const DIST = 'dist'
const MAX_PAGES = 160
const MIN_PLANS = 8
const DEALS_SHOWN = 10
const MAX_PER_PROVIDER = 2

const todayISO = new Date().toISOString().slice(0, 10)
const todayHe = new Intl.DateTimeFormat('he-IL', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const jsonLd = obj => `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, '\\u003c')}</script>`
// NFD-normalize first so diacritics don't punch holes in slugs (Türkiye ->
// turkiye, Curaçao -> curacao) - otherwise they'd become t-rkiye / cura-ao.
const slugify = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
const regionNames = new Intl.DisplayNames(['en'], { type: 'region' })

function destSlug(he) {
  const bg = DEST_BG_BY_HE[he]
  if (!bg) return null
  const base = bg.split('/').pop().replace('.webp', '')
  if (base.length === 2) {
    try { return slugify(regionNames.of(base.toUpperCase()) || base) } catch { return base }
  }
  return slugify(base)
}

const priceFmt = p => `₪${(+p).toFixed(2).replace(/\.00$/, '')}`
const gbFmt = gb => gb == null ? 'ללא הגבלה' : gb < 1 ? `${Math.round(gb * 1024)}MB` : `${String(+(+gb).toFixed(1)).replace(/\.0$/, '')}GB`
const daysFmt = d => !d ? '' : d === 1 ? 'יום אחד' : `${d} ימים`
const provName = id => GLOBAL_LABELS[id] || id

const sleep = ms => new Promise(r => setTimeout(r, ms))

// Flask rate-limits /api/esim/* to 60/min - pace batches below that and back off
// on 429 instead of dropping the destination.
async function getJson(path, tries = 8) {
  for (let i = 0; i < tries; i++) {
    const r = await fetch(`${API}${path}`, { signal: AbortSignal.timeout(30000) })
    if (r.status === 429) { await sleep(15000); continue }
    if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`)
    return r.json()
  }
  throw new Error(`${path} -> HTTP 429 after ${tries} retries`)
}

function pickDeals(deals) {
  const sorted = deals.filter(d => d.price > 0).sort((a, b) => a.price - b.price)
  const perProv = {}
  const picked = []
  for (const d of sorted) {
    perProv[d.provider] = (perProv[d.provider] || 0) + 1
    if (perProv[d.provider] <= MAX_PER_PROVIDER) picked.push(d)
    if (picked.length >= DEALS_SHOWN) break
  }
  return { picked, low: sorted[0]?.price, high: sorted[sorted.length - 1]?.price, total: sorted.length, providers: new Set(sorted.map(d => d.provider)).size }
}

const CSS = `
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Assistant',system-ui,sans-serif;background:#f9f4ee;color:#3b1f0d;line-height:1.65;font-size:17px}
a{color:#5c3317}
.wrap{max-width:860px;margin:0 auto;padding:0 20px}
header.top{background:#fff;border-bottom:1px solid #e0cdb5;padding:14px 0}
header.top .wrap{display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:800;font-size:22px;color:#4a2a13;text-decoration:none}
.brand span{color:#c9622f}
.crumbs{font-size:13px;color:#8a6a4a;margin:14px 0 0}
.crumbs a{color:#8a6a4a}
.hero{border-radius:16px;overflow:hidden;position:relative;margin:14px 0 22px;min-height:210px;display:flex;align-items:flex-end;background:#4a2a13 center/cover no-repeat}
.hero .shade{position:absolute;inset:0;background:linear-gradient(0deg,rgba(30,15,5,.78),rgba(30,15,5,.15))}
.hero .inner{position:relative;padding:22px;color:#fff}
h1{font-size:30px;line-height:1.25;margin-bottom:6px}
.hero p{font-size:15px;opacity:.95}
h2{font-size:22px;color:#4a2a13;margin:30px 0 12px}
.deal{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid #e0cdb5;border-radius:14px;padding:12px 16px;margin-bottom:10px;flex-wrap:wrap}
.deal img{width:42px;height:42px;border-radius:10px;object-fit:contain;background:#faf5ee;border:1px solid #eee0cc}
.deal .info{flex:1;min-width:160px}
.deal .prov{font-weight:700}
.deal .meta{font-size:14px;color:#8a6a4a}
.coupon{display:inline-block;font-size:12px;background:#faf0e2;border:1px dashed #c9622f;color:#8a4515;border-radius:999px;padding:1px 10px;margin-top:2px}
.deal .price{font-size:22px;font-weight:800;color:#4a2a13;min-width:86px;text-align:left}
.buy{background:#5c3317;color:#fff;text-decoration:none;border-radius:10px;padding:9px 20px;font-weight:700;font-size:15px;white-space:nowrap}
.buy:hover{background:#4a2a13}
.cta{display:block;text-align:center;background:#fff;border:2px solid #5c3317;border-radius:14px;padding:14px;margin:22px 0;font-weight:700;text-decoration:none;font-size:17px}
details{background:#fff;border:1px solid #e0cdb5;border-radius:12px;padding:14px 18px;margin-bottom:10px}
summary{font-weight:700;cursor:pointer}
details p{margin-top:8px;color:#5a3a20;font-size:15px}
.links{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 8px}
.links a{background:#fff;border:1px solid #e0cdb5;border-radius:999px;padding:6px 14px;font-size:14px;text-decoration:none}
footer{margin:36px 0 26px;font-size:13px;color:#a08468;border-top:1px solid #e8d5bc;padding-top:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin-top:14px}
.grid a{background:#fff;border:1px solid #e0cdb5;border-radius:12px;padding:12px 14px;text-decoration:none;font-size:15px}
.grid .mn{display:block;font-size:13px;color:#8a6a4a}
`.trim()

function pageShell({ title, desc, canonical, ogImage, schemas, body }) {
  return `<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
<link rel="canonical" href="${canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${canonical}">
${ogImage ? `<meta property="og:image" content="${SITE}${ogImage}">` : ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/icons/icon-192.png">
<link rel="stylesheet" href="/fonts/fonts.css">
${schemas.map(jsonLd).join('\n')}
<style>${CSS}</style>
</head>
<body>
<header class="top"><div class="wrap"><a class="brand" href="/">MOCA<span>.</span></a><a href="/esim-deals" style="font-size:14px">להשוואה האינטראקטיבית ←</a></div></header>
<div class="wrap">
${body}
<footer>המחירים נאספים אוטומטית מאתרי הספקים ועודכנו לאחרונה ב-${todayHe}. חלק מהקישורים הם קישורי שותפים - המחיר עבורכם זהה, ואנחנו עשויים לקבל עמלה שמממנת את ההשוואה. MOCA - השוואת eSIM וסלולר · <a href="/esim/destinations/">כל היעדים</a> · <a href="/esim-deals">השוואה חיה</a></footer>
</div>
</body>
</html>`
}

function faqItems(dest, cheapest, stats) {
  return [
    {
      q: `כמה עולה eSIM ל${dest}?`,
      a: `נכון ל-${todayHe}, חבילת eSIM ל${dest} מתחילה ב-${priceFmt(stats.low)} (${gbFmt(cheapest.gb)} ל${daysFmt(cheapest.days)} אצל ${provName(cheapest.provider)}). בהשוואה שלנו ${stats.total} חבילות מ-${stats.providers} ספקים, והמחירים מתעדכנים אוטומטית.`,
    },
    {
      q: 'מה זה eSIM ולמה זה משתלם יותר מחבילת גלישה של המפעיל?',
      a: 'eSIM הוא כרטיס SIM דיגיטלי שמתקינים בסריקת ברקוד, בלי כרטיס פיזי ובלי להחליף את הסים הישראלי. חבילות eSIM ייעודיות ליעד זולות בדרך כלל משמעותית מחבילות הגלישה בחו"ל של המפעילים הישראליים, במיוחד לנפחי גלישה גדולים.',
    },
    {
      q: 'איך מתקינים ומפעילים את ה-eSIM?',
      a: 'רוכשים אונליין לפני הטיסה, מקבלים ברקוד (QR) במייל, סורקים אותו בהגדרות המכשיר ומגדירים את קו ה-eSIM לנתונים. מומלץ להתקין בבית ולהפעיל רק בנחיתה. חשוב לוודא שהמכשיר תומך eSIM ואינו נעול לרשת.',
    },
    {
      q: 'האם המספר הישראלי והוואטסאפ ממשיכים לעבוד?',
      a: 'כן. הוואטסאפ נשאר מקושר למספר הישראלי גם כשגולשים דרך ה-eSIM. את הסים הישראלי אפשר להשאיר פעיל לקבלת SMS (למשל קודי אימות) - רק כדאי לכבות לו נדידת נתונים כדי להימנע מחיובים.',
    },
  ]
}

async function main() {
  let dests
  try {
    dests = await getJson('/api/esim/destinations')
  } catch (e) {
    console.warn(`prerender-esim-dests: SKIPPED - API unreachable (${e.message}). No destination pages in this build!`)
    return
  }

  const clean = dests
    .filter(d => d.count >= MIN_PLANS && d.destination && !/[A-Za-z0-9]/.test(d.destination) && !d.destination.includes('מדינות') && DEST_BG_BY_HE[d.destination])
    .sort((a, b) => b.count - a.count)

  const bySlug = new Map()
  for (const d of clean) {
    const slug = destSlug(d.destination)
    if (!slug || bySlug.has(slug)) continue
    bySlug.set(slug, d)
    if (bySlug.size >= MAX_PAGES) break
  }

  const pages = []
  const entries = [...bySlug.entries()]
  const CONC = 4
  for (let i = 0; i < entries.length; i += CONC) {
    if (i) await sleep(4500) // stay under the 60/min API rate limit
    await Promise.all(entries.slice(i, i + CONC).map(async ([slug, d]) => {
      const he = d.destination
      try {
        const cmp = await getJson(`/api/esim/compare?dest=${encodeURIComponent(he)}`)
        const stats = pickDeals(cmp.deals || [])
        if (!stats.picked.length) return
        pages.push({ slug, he, stats, coupons: cmp.coupons || {}, count: d.count })
      } catch (e) {
        console.warn(`  skip ${he}: ${e.message}`)
      }
    }))
  }
  pages.sort((a, b) => b.count - a.count)

  const related = pages.slice(0, 12)
  for (const p of pages) {
    const { slug, he, stats, coupons } = p
    const canonical = `${SITE}/esim/${slug}/`
    const ogImage = DEST_BG_BY_HE[he]
    const cheapest = stats.picked[0]
    const title = `eSIM ל${he} - השוואת מחירים מ-${priceFmt(stats.low)} | MOCA`
    const desc = `השוואת חבילות eSIM ל${he}: ${stats.total} חבילות מ-${stats.providers} ספקים, החל מ-${priceFmt(stats.low)}. מחירים שנאספים אוטומטית, קודי קופון והזמנה מיידית.`
    const faq = faqItems(he, cheapest, stats)

    const schemas = [
      {
        '@context': 'https://schema.org', '@type': 'Product',
        name: `eSIM ל${he}`, description: desc, image: `${SITE}${ogImage}`,
        offers: { '@type': 'AggregateOffer', lowPrice: stats.low, highPrice: stats.high, priceCurrency: 'ILS', offerCount: stats.total, availability: 'https://schema.org/InStock' },
      },
      {
        '@context': 'https://schema.org', '@type': 'FAQPage',
        mainEntity: faq.map(f => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
      },
      {
        '@context': 'https://schema.org', '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'MOCA', item: `${SITE}/` },
          { '@type': 'ListItem', position: 2, name: 'eSIM לחו"ל', item: `${SITE}/esim/destinations/` },
          { '@type': 'ListItem', position: 3, name: he, item: canonical },
        ],
      },
    ]

    const dealsHtml = stats.picked.map(dl => {
      const c = coupons[dl.provider]
      const go = `${GO_BASE}/${dl.provider}?dest=${encodeURIComponent(he)}&src=esim&campaign=seo_dest`
      return `<div class="deal">
<img src="/logos/${esc(dl.provider)}.png" alt="${esc(provName(dl.provider))}" loading="lazy" onerror="this.style.display='none'">
<div class="info"><div class="prov">${esc(provName(dl.provider))}</div>
<div class="meta">${esc(gbFmt(dl.gb))} · ${esc(daysFmt(dl.days))}</div>
${c ? `<span class="coupon">קופון ${esc(c.code)} - ${esc(c.discount_label || 'הנחה')}</span>` : ''}</div>
<div class="price">${priceFmt(dl.price)}</div>
<a class="buy" href="${go}" rel="sponsored nofollow noopener" target="_blank">לרכישה</a>
</div>`
    }).join('\n')

    const body = `
<nav class="crumbs"><a href="/">MOCA</a> › <a href="/esim/destinations/">eSIM לחו"ל</a> › ${esc(he)}</nav>
<div class="hero" style="background-image:url('${ogImage}')"><div class="shade"></div><div class="inner">
<h1>eSIM ל${esc(he)} - השוואת מחירים</h1>
<p>${stats.total} חבילות מ-${stats.providers} ספקים · החל מ-${priceFmt(stats.low)} · עודכן ${todayHe}</p>
</div></div>
<h2>החבילות המשתלמות ביותר ל${esc(he)}</h2>
${dealsHtml}
<a class="cta" href="/esim-deals?dest=${encodeURIComponent(he)}">לכל ${stats.total} החבילות ל${esc(he)} בהשוואה החיה ←</a>
<h2>שאלות נפוצות</h2>
${faq.map(f => `<details><summary>${esc(f.q)}</summary><p>${esc(f.a)}</p></details>`).join('\n')}
<h2>יעדים פופולריים נוספים</h2>
<div class="links">${related.filter(r => r.slug !== slug).slice(0, 10).map(r => `<a href="/esim/${r.slug}/">eSIM ל${esc(r.he)}</a>`).join('')}<a href="/esim/destinations/">כל היעדים ←</a></div>`

    const dir = join(DIST, 'esim', slug)
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, 'index.html'), pageShell({ title, desc, canonical, ogImage, schemas, body }))
  }

  // Hub page: /esim/
  const hubTitle = 'eSIM לחו"ל - השוואת מחירים לפי יעד | MOCA'
  const hubDesc = `השוואת מחירי eSIM ל-${pages.length} יעדים: מחירים חיים מ-30+ ספקים, קודי קופון והזמנה מיידית. בחרו יעד והשוו.`
  const hubSchemas = [{
    '@context': 'https://schema.org', '@type': 'CollectionPage', name: hubTitle, description: hubDesc, url: `${SITE}/esim/destinations/`,
  }]
  const hubBody = `
<nav class="crumbs"><a href="/">MOCA</a> › eSIM לחו"ל</nav>
<h1 style="margin-top:14px">eSIM לחו"ל - השוואת מחירים לפי יעד</h1>
<p style="margin-top:6px;color:#5a3a20">בחרו את היעד שלכם להשוואת כל חבילות ה-eSIM הזמינות - מחירים שנאספים אוטומטית מ-30+ ספקים, עם קודי קופון בלעדיים.</p>
<div class="grid">
${pages.map(p => `<a href="/esim/${p.slug}/">eSIM ל${esc(p.he)}<span class="mn">מ-${priceFmt(p.stats.low)} · ${p.stats.total} חבילות</span></a>`).join('\n')}
</div>
<a class="cta" href="/esim-deals">להשוואה האינטראקטיבית המלאה ←</a>`
  mkdirSync(join(DIST, 'esim', 'destinations'), { recursive: true })
  writeFileSync(join(DIST, 'esim', 'destinations', 'index.html'), pageShell({ title: hubTitle, desc: hubDesc, canonical: `${SITE}/esim/destinations/`, ogImage: '/dest-bg/global.webp', schemas: hubSchemas, body: hubBody }))

  // Inject Product + FAQ JSON-LD into the live compare page head (dist/esim.html)
  const esimHtml = join(DIST, 'esim.html')
  if (existsSync(esimHtml)) {
    let html = readFileSync(esimHtml, 'utf8')
    if (!html.includes('application/ld+json')) {
      const totLow = Math.min(...pages.map(p => p.stats.low))
      const totCount = pages.reduce((s, p) => s + p.stats.total, 0)
      const genFaq = faqItems('חו"ל', pages[0].stats.picked[0], { low: totLow, total: totCount, providers: 30 })
      const block = [
        { '@context': 'https://schema.org', '@type': 'Product', name: 'eSIM לחו"ל - השוואת מחירים', description: `השוואת ${totCount} חבילות eSIM לכל יעד בעולם`, offers: { '@type': 'AggregateOffer', lowPrice: totLow, priceCurrency: 'ILS', offerCount: totCount, availability: 'https://schema.org/InStock' } },
        { '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: genFaq.slice(1).map(f => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })) },
      ].map(jsonLd).join('\n')
      html = html.replace('</head>', `${block}\n</head>`)
      writeFileSync(esimHtml, html)
    }
  }

  // Sitemap: append hub + destination pages
  const smPath = join(DIST, 'sitemap.xml')
  if (existsSync(smPath)) {
    let sm = readFileSync(smPath, 'utf8')
    // Idempotent: strip any /esim/<something> entries from a previous run first
    // (the pattern requires a slash after "esim", so /esim-deals never matches).
    sm = sm.replace(/  <url>\s*<loc>https:\/\/mocaintel\.com\/esim\/[\s\S]*?<\/url>\n/g, '')
    const urls = [`  <url>\n    <loc>${SITE}/esim/destinations/</loc>\n    <lastmod>${todayISO}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>`]
    for (const p of pages) {
      urls.push(`  <url>\n    <loc>${SITE}/esim/${p.slug}/</loc>\n    <lastmod>${todayISO}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>`)
    }
    sm = sm.replace('</urlset>', `${urls.join('\n')}\n</urlset>`)
    writeFileSync(smPath, sm)
  }

  // Manifest for indexnow-ping.mjs
  writeFileSync(join(DIST, 'esim-pages.json'), JSON.stringify({ generated_at: todayISO, urls: [`${SITE}/esim/destinations/`, ...pages.map(p => `${SITE}/esim/${p.slug}/`)] }, null, 1))

  console.log(`prerender-esim-dests: wrote ${pages.length} destination pages + hub (/esim/), schema injected into esim.html, sitemap +${pages.length + 1} URLs`)
}

await main()
