/* Build step (last in the chain) - stamp fresh <lastmod> dates into
 * dist/sitemap.xml so crawlers (Google + AI answer engines) see an honest
 * freshness signal instead of a hand-edited date that silently rots.
 *
 * Only the /esim-deals entries are stamped with the build date: their
 * underlying deal data genuinely refreshes twice a day, so "this page changed
 * recently" is always true. The landing + hotels entries keep their curated
 * dates (their content changes only on real edits - stamping them fresh on
 * every build would be a false signal, which Google learns to distrust).
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const sitemapPath = resolve(root, 'dist/sitemap.xml')
if (!existsSync(sitemapPath)) throw new Error('stamp-sitemap: missing ' + sitemapPath + ' - run the client build first')

const today = new Date().toISOString().slice(0, 10)
let xml = readFileSync(sitemapPath, 'utf8')

let stamped = 0
xml = xml.replace(
  /(<loc>https:\/\/mocaintel\.com\/esim-deals[^<]*<\/loc>[\s\S]*?<lastmod>)[^<]+(<\/lastmod>)/g,
  (_, pre, post) => {
    stamped += 1
    return pre + today + post
  },
)
if (stamped === 0) throw new Error('stamp-sitemap: no /esim-deals <lastmod> entries found - sitemap structure changed?')

writeFileSync(sitemapPath, xml, 'utf8')
console.log(`stamp-sitemap: stamped ${stamped} /esim-deals lastmod entries with ${today}`)
