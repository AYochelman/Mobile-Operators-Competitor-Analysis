/* The public origin every absolute URL on this site declares itself under:
 * canonicals, hreflang alternates, OG/Twitter images, JSON-LD @id, the sitemap
 * and the IndexNow submissions.
 *
 * It is deliberately NOT mocaintel.com. That domain was taken offline on
 * 2026-07-13 at the employer's request (commit af0c061) - the Netlify custom
 * domain and the esim alias were removed, and the apex now answers DNS with
 * NODATA: no A record, no AAAA record, nothing to connect to. A canonical that
 * points at an unresolvable host tells Google the real home of the content does
 * not exist, which is how the whole site drops out of the index; Ahrefs Site
 * Audit flagged the same thing from the other end ("Robots.txt is not
 * accessible", 2 URLs crawled). The Netlify origin below is the host that
 * actually serves, per that commit's own verification note.
 *
 * Imported by the build scripts (scripts/*.mjs) and by the pages that rewrite
 * their canonical at runtime. Static files cannot import, so they carry the
 * literal origin and must be changed together with this constant:
 *   index.html                 public/sitemap.xml        public/robots.txt
 *   public/llms.txt            public/privacy.html       public/terms.html
 *   public/cookies.html        public/accessibility.html
 * sitemap.xml drift fails the build loudly - scripts/stamp-sitemap.mjs matches
 * on this origin and throws when it finds no entries.
 */
export const SITE_ORIGIN = 'https://lucent-kulfi-f037ad.netlify.app'
