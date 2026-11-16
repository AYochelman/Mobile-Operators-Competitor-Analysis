/* Build guard: every route declared in src/App.jsx must have a rule in
 * public/_redirects.
 *
 * WHY: _redirects no longer ends with a "/* -> /index.html 200" catch-all (that
 * answered 200 with the app shell for ANY unknown URL - a soft 404). SPA routes
 * are listed one by one and everything else gets a real 404, so a route added to
 * App.jsx without a matching rule would 404 on a direct visit or a refresh.
 * This fails the build instead of letting that reach production.
 */
import { readFileSync } from 'node:fs'

const app = readFileSync('src/App.jsx', 'utf8')
const lines = readFileSync('public/_redirects', 'utf8').split('\n')
  .map(l => l.trim()).filter(l => l && !l.startsWith('#'))
const froms = lines.map(l => l.split(/\s+/)[0]).filter(f => f.startsWith('/'))

const last = lines[lines.length - 1].split(/\s+/)
if (last[0] !== '/*' || last[2] !== '404') {
  throw new Error(`check-redirects: the last rule in public/_redirects must be "/* /404.html 404", found "${lines[lines.length - 1]}"`)
}

const covered = route => froms.some(f => {
  if (f === '/*') return false
  if (f.endsWith('/*')) return route === f.slice(0, -2) || route.startsWith(f.slice(0, -1))
  return f === route
})

const routes = [...new Set([...app.matchAll(/path="([^"]*)"/g)].map(m => m[1]))]
  .filter(p => p !== '*')
  .map(p => '/' + p.replace(/^\//, ''))
  // "/guest/:slug" is served by a "/guest/*" rule: test a concrete child path.
  .map(p => p.includes(':') ? p.replace(/:[^/]+/g, 'x') : p)

const missing = routes.filter(r => !covered(r))
if (missing.length) {
  throw new Error(`check-redirects: ${missing.length} route(s) in src/App.jsx have no rule in public/_redirects and would 404 on a direct visit: ${missing.join(', ')}. Add "<route>  /index.html  200" above the final 404 rule (and mirror it in netlify.toml).`)
}
console.log(`check-redirects: all ${routes.length} App.jsx routes are covered by public/_redirects`)
