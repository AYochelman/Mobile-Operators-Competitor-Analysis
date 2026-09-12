// Stamp the operator's identity (src/data/legalEntity.js) into the four static
// legal pages in dist/ - privacy, terms, cookies, accessibility - so the legal
// name / registration number / address live in ONE file and every page (HE+EN)
// shows the same block. Runs after `vite build` (public/ has been copied to
// dist/ by then). Null fields are omitted, never rendered as placeholders.
//
// Markers in the HTML:
//   <!--OPERATOR:he:start-->…<!--OPERATOR:he:end-->     the operator box (HE)
//   <!--OPERATOR:en:start-->…<!--OPERATOR:en:end-->     the operator box (EN)
//   <!--OPERATOR:he:footer-->…<!--/OPERATOR-->           one-line footer credit
//   <span data-coordinator>…</span>                     accessibility contact label
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { LEGAL_ENTITY as E } from '../src/data/legalEntity.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DIST = path.resolve(__dirname, '..', 'dist')
const PAGES = ['privacy.html', 'terms.html', 'cookies.html', 'accessibility.html']

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

function box(lang, page) {
  const he = lang === 'he'
  const role = page === 'privacy.html'
    ? (he ? 'מפעיל השירות ובעל מאגר המידע:' : 'Service operator and database owner:')
    : page === 'accessibility.html'
      ? (he ? 'מפעיל האתר:' : 'Site operator:')
      : (he ? 'מפעיל השירות:' : 'Service operator:')
  const parts = []
  parts.push(`<b>${role}</b> ${esc(E.brand)}${E.legalName ? ` (${esc(E.legalName)})` : ''}`)
  if (E.registrationId) parts.push((he ? 'מס\' עוסק/ח.פ. ' : 'Reg. no. ') + esc(E.registrationId))
  if (E.address) parts.push((he ? 'כתובת: ' : 'Address: ') + esc(E.address))
  const mail = page === 'privacy.html' ? E.privacyEmail : page === 'accessibility.html' ? E.accessibilityEmail : E.email
  parts.push(`<a href="mailto:${esc(mail)}">${esc(mail)}</a>`)
  return parts.join(' · ')
}

function footer(lang) {
  const he = lang === 'he'
  const parts = [E.legalName ? `${esc(E.brand)} (${esc(E.legalName)})` : esc(E.brand)]
  if (E.registrationId) parts.push((he ? 'ח.פ./ע.מ. ' : 'Reg. no. ') + esc(E.registrationId))
  if (E.address) parts.push(esc(E.address))
  parts.push(esc(E.email))
  return parts.join(' · ')
}

let done = 0
for (const page of PAGES) {
  const file = path.join(DIST, page)
  if (!fs.existsSync(file)) { console.warn(`stamp-legal: ${page} not in dist/, skipped`); continue }
  let html = fs.readFileSync(file, 'utf8')
  for (const lang of ['he', 'en']) {
    html = html.replace(
      new RegExp(`<!--OPERATOR:${lang}:start-->[\\s\\S]*?<!--OPERATOR:${lang}:end-->`, 'g'),
      `<!--OPERATOR:${lang}:start-->${box(lang, page)}<!--OPERATOR:${lang}:end-->`,
    )
    html = html.replace(
      new RegExp(`<!--OPERATOR:${lang}:footer-->[\\s\\S]*?<!--/OPERATOR-->`, 'g'),
      `<!--OPERATOR:${lang}:footer-->${footer(lang)}<!--/OPERATOR-->`,
    )
  }
  if (E.accessibilityCoordinator) {
    html = html.replace(/<span data-coordinator>איש הקשר לנגישות:<\/span>/, `<span data-coordinator>איש הקשר לנגישות: ${esc(E.accessibilityCoordinator)},</span>`)
    html = html.replace(/<span data-coordinator>Accessibility contact:<\/span>/, `<span data-coordinator>Accessibility contact: ${esc(E.accessibilityCoordinator)},</span>`)
  }
  fs.writeFileSync(file, html)
  done++
}
console.log(`stamp-legal: stamped ${done} page(s) - ${E.brand}${E.legalName ? ` (${E.legalName})` : ' (legalName not set yet)'}`)
