/* Build step 3/3 — emit a pure-static dist/landing.html for the marketing page.
 *
 * Pipeline (see package.json "build"):
 *   1. vite build                              → dist/ (the SPA + hashed assets/CSS)
 *   2. vite build --ssr src/entry-landing.jsx  → dist-ssr/entry-landing.js
 *   3. node scripts/prerender-landing.mjs      → dist/landing.html  (this file)
 *
 * Netlify serves landing.html at "/" (see netlify.toml), so the marketing page
 * paints from static HTML + CSS with NO React boot. The asset hashes in the SSR
 * render match the client build (Vite content-hashing is identical for identical
 * files), so the <img>/CSS references resolve against dist/assets directly.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const distIndex = resolve(root, 'dist/index.html')
const ssrEntry = resolve(root, 'dist-ssr/entry-landing.js')

if (!existsSync(ssrEntry)) throw new Error('prerender: missing ' + ssrEntry + ' — run the --ssr build first')
if (!existsSync(distIndex)) throw new Error('prerender: missing ' + distIndex + ' — run the client build first')

// 1. render the landing component to a static HTML string
const { render } = await import(pathToFileURL(ssrEntry).href)
const body = render()
if (!/<h1/.test(body)) throw new Error('prerender: rendered landing has no <h1> — render() likely failed')

// 2. reuse the SPA's built <head> (hashed Tailwind CSS, fonts, meta) minus SPA-only scripts
const spa = readFileSync(distIndex, 'utf8')
const headMatch = spa.match(/<head>([\s\S]*?)<\/head>/)
if (!headMatch) throw new Error('prerender: could not find <head> in dist/index.html')
let head = headMatch[1]
  .replace(/<script\b[^>]*type="module"[^>]*><\/script>/g, '')
  .replace(/<link\b[^>]*rel="modulepreload"[^>]*>/g, '')
  .replace(/<script\b[^>]*registerSW[^>]*><\/script>/g, '')
  .replace(/<script\b[^>]*id="vite-plugin-pwa[^>]*><\/script>/g, '')

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
  throw new Error('prerender: app CSS <link> missing from head — landing would be unstyled')
}

// 3. logged-in visitors who land on "/" get bounced into the app (the SPA home)
const authedRedirect =
  `<script>try{if(localStorage.getItem('auth_token'))location.replace('/home')}catch(e){}</script>`

// 4. the hero pointer-tilt (the React handler isn't shipped to the static page)
const tilt =
  `<script>(function(){var s=document.querySelector('.lhs-stage');var f=s&&s.querySelector('.lhs-frame');if(!s||!f)return;var M=20;` +
  `s.addEventListener('pointermove',function(e){var r=s.getBoundingClientRect();var px=(e.clientX-r.left)/r.width-0.5;var py=(e.clientY-r.top)/r.height-0.5;` +
  `f.style.transform='rotateY('+(px*2*M)+'deg) rotateX('+(-py*2*M)+'deg)';f.style.setProperty('--gx',(px*70+50)+'%');f.style.setProperty('--gy',(py*70+50)+'%');});` +
  `s.addEventListener('pointerleave',function(){f.style.transform='rotateY(-13deg) rotateX(8deg)';});})();</script>`

const html = `<!DOCTYPE html>
<html lang="he" dir="rtl">
  <head>
    ${authedRedirect}
    ${head}
  </head>
  <body>
${body}
    ${tilt}
  </body>
</html>
`

writeFileSync(resolve(root, 'dist/landing.html'), html, 'utf8')
console.log(`prerender: wrote dist/landing.html (${(html.length / 1024).toFixed(1)} KB)`)
