/* Build step 3/3 — emit a pure-static dist/landing.html for the marketing page.
 *
 * Pipeline (see package.json "build"):
 *   1. vite build                              → dist/ (the SPA + hashed assets/CSS)
 *   2. vite build --ssr src/entry-landing.jsx  → dist-ssr/entry-landing.js
 *   3. node scripts/prerender-landing.mjs      → dist/landing.html  (this file)
 *
 * Netlify serves landing.html at "/" (see public/_redirects), so the marketing
 * page paints from static HTML + CSS with NO React boot. The asset hashes in the
 * SSR render match the client build (Vite content-hashing is identical for
 * identical files), so the <img>/CSS references resolve against dist/assets.
 *
 * BILINGUAL: render() is called twice (he + en). Both language copies are
 * embedded in the page inside [data-lang-root] wrappers; a tiny vanilla script
 * toggles between them (no React). Hebrew is the no-JS / default view; English
 * shows when the visitor picks it, has it stored, or opens the page with
 * ?lang=en (handy for sending the English page to international suppliers).
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const distIndex = resolve(root, 'dist/index.html')
const ssrEntry = resolve(root, 'dist-ssr/entry-landing.js')

const TITLE_HE = 'MOCA - מודיעין תחרותי לשוק הסלולר'
const TITLE_EN = 'MOCA - Competitive Intelligence for Mobile Operators'

if (!existsSync(ssrEntry)) throw new Error('prerender: missing ' + ssrEntry + ' - run the --ssr build first')
if (!existsSync(distIndex)) throw new Error('prerender: missing ' + distIndex + ' - run the client build first')

// 1. render the landing component to a static HTML string — once per language
const { render } = await import(pathToFileURL(ssrEntry).href)
const heMarkup = render('he')
const enMarkup = render('en')
if (!/<h1/.test(heMarkup) || !/<h1/.test(enMarkup)) {
  throw new Error('prerender: a rendered landing has no <h1> - render() likely failed')
}
// Both copies live in the DOM; CSS (below) shows only the active one. The Hebrew
// copy is the default/no-JS view, so it must render first and stay visible
// without any script running.
const body = `<div data-lang-root="he">${heMarkup}</div>\n<div data-lang-root="en">${enMarkup}</div>`

// 2. reuse the SPA's built <head> (hashed Tailwind CSS, fonts, meta) minus SPA-only scripts
const spa = readFileSync(distIndex, 'utf8')
const headMatch = spa.match(/<head>([\s\S]*?)<\/head>/)
if (!headMatch) throw new Error('prerender: could not find <head> in dist/index.html')
let head = headMatch[1]
  .replace(/<script\b[^>]*type="module"[^>]*><\/script>/g, '')
  .replace(/<link\b[^>]*rel="modulepreload"[^>]*>/g, '')
  .replace(/<script\b[^>]*registerSW[^>]*><\/script>/g, '')
  .replace(/<script\b[^>]*id="vite-plugin-pwa[^>]*><\/script>/g, '')
  // SEO/no-JS baseline title = Hebrew (the default view). The lang script keeps
  // document.title in sync once JS runs.
  .replace(/<title>[\s\S]*?<\/title>/, `<title>${TITLE_HE}</title>`)

// The SPA loads fonts from Google (non-render-blocking) because its text paints
// late, after the JS boot. The static landing paints in ~0.3s, so an external
// render-blocking font would slow FCP and an async one would swap in late and
// shift the hero (CLS). Swap both Google Fonts links for ONE self-hosted,
// same-origin stylesheet (public/fonts/fonts.css, display:optional). Same-origin
// + optional → fast first paint AND no swap → zero CLS.
head = head
  .replace(/<link\b[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>/g, '')
  .replace(/<noscript>[\s\S]*?<\/noscript>/g, '')
  .replace(/<\/title>/, '</title>\n    <link rel="stylesheet" href="/fonts/fonts.css">')
  .replace(/^[ \t]*\r?\n/gm, '')
  .trim()

if (!/\/fonts\/fonts\.css/.test(head)) throw new Error('prerender: failed to inject self-hosted fonts.css link')

if (!/<link[^>]*rel="stylesheet"[^>]*\/assets\/[^">]*\.css/.test(head)) {
  throw new Error('prerender: app CSS <link> missing from head - landing would be unstyled')
}

// 3. logged-in visitors who land on "/" get bounced into the app (the SPA home)
const authedRedirect =
  `<script>try{if(localStorage.getItem('auth_token'))location.replace('/home')}catch(e){}</script>`

// 4a. language visibility CSS + an early head script that picks the initial
// language BEFORE the body paints (zero flash on ?lang=en / stored preference).
// Default (no data-lang / no JS) = Hebrew visible, English hidden → graceful
// no-JS fallback that is never blank.
const langHeadCss =
  `<style>[data-lang-root="en"]{display:none}` +
  `html[data-lang="en"] [data-lang-root="en"]{display:block}` +
  `html[data-lang="en"] [data-lang-root="he"]{display:none}</style>`
const langHeadScript =
  `<script>(function(){try{var u=new URLSearchParams(location.search).get('lang');` +
  `var s=u||localStorage.getItem('moca_lang');var l=(s==='en'||s==='he')?s:'he';` +
  `var d=document.documentElement;d.setAttribute('data-lang',l);d.lang=l;d.dir=l==='en'?'ltr':'rtl';}catch(e){}})();</script>`

// 4c. SEO i18n: hreflang alternates + og:locale. The Hebrew page is "/" and the
// English variant is "/?lang=en" (same static file, JS-toggled — Googlebot renders
// JS so it sees the English DOM). The canonical is made self-referencing per
// language by the body script below, so the two URLs index as language alternates
// rather than the English one folding into the Hebrew canonical.
const seoI18n =
  `<link rel="alternate" hreflang="he" href="https://mocaintel.com/" />` +
  `<link rel="alternate" hreflang="en" href="https://mocaintel.com/?lang=en" />` +
  `<link rel="alternate" hreflang="x-default" href="https://mocaintel.com/" />` +
  `<meta property="og:locale" content="he_IL" />` +
  `<meta property="og:locale:alternate" content="en_US" />`

// 4b. end-of-body script: keep document.title + canonical in sync with the active
// language, wire the [data-lang-toggle] button to flip languages (persisting the
// choice), and re-create the hero pointer-tilt (the React handler isn't shipped to
// the static page) for EVERY rendered hero — there are two now (one per copy).
const langBodyScript =
  `<script>(function(){` +
  `var T={he:${JSON.stringify(TITLE_HE)},en:${JSON.stringify(TITLE_EN)}};` +
  `function setCanon(l){var c=document.querySelector('link[rel="canonical"]');if(c)c.href=l==='en'?'https://mocaintel.com/?lang=en':'https://mocaintel.com/';}` +
  `function setLang(l){var d=document.documentElement;d.setAttribute('data-lang',l);d.lang=l;` +
  `d.dir=l==='en'?'ltr':'rtl';if(T[l])document.title=T[l];setCanon(l);try{localStorage.setItem('moca_lang',l);}catch(e){}}` +
  `var cur=document.documentElement.getAttribute('data-lang')==='en'?'en':'he';document.title=T[cur];setCanon(cur);` +
  `document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-lang-toggle]');` +
  `if(!b)return;e.preventDefault();setLang(document.documentElement.getAttribute('data-lang')==='en'?'he':'en');});` +
  `function tilt(stage){var f=stage.querySelector('.lhs-frame');if(!f)return;var M=20;` +
  `stage.addEventListener('pointermove',function(e){var r=stage.getBoundingClientRect();` +
  `var px=(e.clientX-r.left)/r.width-0.5;var py=(e.clientY-r.top)/r.height-0.5;` +
  `f.style.transform='rotateY('+(px*2*M)+'deg) rotateX('+(-py*2*M)+'deg)';` +
  `f.style.setProperty('--gx',(px*70+50)+'%');f.style.setProperty('--gy',(py*70+50)+'%');});` +
  `stage.addEventListener('pointerleave',function(){f.style.transform='rotateY(-13deg) rotateX(8deg)';});}` +
  `var st=document.querySelectorAll('.lhs-stage');for(var i=0;i<st.length;i++)tilt(st[i]);` +
  `})();</script>`

const html = `<!DOCTYPE html>
<html lang="he" dir="rtl">
  <head>
    ${authedRedirect}
    ${langHeadCss}
    ${langHeadScript}
    ${head}
    ${seoI18n}
  </head>
  <body>
${body}
    ${langBodyScript}
  </body>
</html>
`

writeFileSync(resolve(root, 'dist/landing.html'), html, 'utf8')
console.log(`prerender: wrote dist/landing.html (${(html.length / 1024).toFixed(1)} KB)`)
