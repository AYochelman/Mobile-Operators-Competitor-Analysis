// One-off generator: builds the hotel-destination catalog {he, iso} by matching
// the live DB destinations (data/_dest_inventory.json) against Intl.DisplayNames
// Hebrew region names, with a manual alias table for scraper-Hebrew spellings
// that differ from CLDR. Emits the final JS array + a validation table.
import fs from 'fs'

const inv = JSON.parse(fs.readFileSync('data/_dest_inventory.json', 'utf8'))
const heName = new Intl.DisplayNames(['he'], { type: 'region' })
const enName = new Intl.DisplayNames(['en'], { type: 'region' })

const norm = s => (s || '').replace(/[׳'’]/g, "'").replace(/[״"”]/g, '"').replace(/\s+/g, ' ').trim()

// Legacy / transitional / exceptional ISO reservations that CLDR still resolves
// but must NOT win auto-matching (they shadow the modern code).
const EXCLUDE = new Set(['AN','BU','CS','DD','DY','FX','HV','NH','NQ','PZ','RH','SU','TP','UK','VD','WK','YD','YU','ZR','EU','UN','XK'])

// Scraper-Hebrew → ISO for names CLDR-Hebrew spells differently.
const MANUAL = {
  'בריטניה': 'GB', 'ארצות הברית': 'US', 'דרום קוריאה': 'KR', 'הונג קונג': 'HK',
  'מקאו': 'MO', 'נורבגיה': 'NO', 'שבדיה': 'SE', 'שוויץ': 'CH', 'קטר': 'QA',
  'כוויית': 'KW', 'איחוד האמירויות': 'AE', 'פראגוואי': 'PY', 'ניקראגואה': 'NI',
  "ניג'ר": 'NE', 'גאבון': 'GA', 'סיירה ליאונה': 'SL', 'גינאה ביסאו': 'GW',
  'סנט וינסנט והגרדינים': 'VC', 'סן ברתלמי': 'BL', 'קייפ ורדה': 'CV',
  'איי הבהאמה': 'BS', 'איי טורקס וקאיקוס': 'TC', 'איי הבתולה (ארה"ב)': 'VI',
  'איי הבתולה (בריטניה)': 'VG', 'הרפובליקה הדמוקרטית של קונגו': 'CD',
  'הרפובליקה המרכז אפריקאית': 'CF', 'בורקינה פאסו': 'BF', 'בנין': 'BJ',
  'סרביה': 'RS', 'רוסיה': 'RU', 'צרפת': 'FR',
  'קוסובו': 'XK', 'ותיקן': 'VA', 'טימור לסטה': 'TL', 'רפובליקת קונגו': 'CG',
  'מיאנמר': 'MM',  // CLDR-he: 'מיאנמר (בורמה)'
}

// Auto map: Hebrew(normalized) → iso, over current codes only.
const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')
const he2iso = {}
for (const a of A) for (const b of A) {
  const code = a + b
  if (EXCLUDE.has(code)) continue
  let n; try { n = heName.of(code) } catch { continue }
  if (!n || n === code) continue
  if (!(norm(n) in he2iso)) he2iso[norm(n)] = code  // first-wins among valid codes
}

// High-coverage tourist destinations with NO ISO 3166-1 alpha-2 code (sub-national
// or special) — Intl.DisplayNames can't localize them, so we carry an explicit
// English name and destLabel falls back to it.
const SUBNATIONAL = [
  { he: 'קפריסין הצפונית', en: 'Northern Cyprus' },
  { he: 'בונייר',          en: 'Bonaire' },
  { he: 'סקוטלנד',         en: 'Scotland' },
  { he: 'מדיירה',          en: 'Madeira' },
]
const SUB_HE = new Set(SUBNATIONAL.map(s => s.he))

const MIN_PROVS = 2
const catalog = [], unresolved = []
for (const o of inv) {
  if (!o.dest || o.provs < MIN_PROVS || SUB_HE.has(o.dest)) continue
  const iso = MANUAL[o.dest] || he2iso[norm(o.dest)]
  if (iso) catalog.push({ he: o.dest, iso, provs: o.provs, rows: o.rows })
  else unresolved.push(o)
}
for (const s of SUBNATIONAL) {
  const o = inv.find(x => x.dest === s.he)
  catalog.push({ he: s.he, en: s.en, provs: o ? o.provs : 0, rows: o ? o.rows : 0 })
}
catalog.sort((x, y) => x.he.localeCompare(y.he, 'he'))

// Validation table
console.log('=== VALIDATION (he | iso | CLDR-he | CLDR-en) ===')
let bad = 0
for (const c of catalog) {
  if (!c.iso) { console.log(`SUBNAT\t${c.he}\t—\t${c.he}\t${c.en}`); continue }
  const clHe = heName.of(c.iso), clEn = enName.of(c.iso)
  const ok = norm(clHe) === norm(c.he) ? 'AUTO' : 'manual'
  if (!clEn || clEn === c.iso) bad++
  console.log(`${ok}\t${c.he}\t${c.iso}\t${clHe}\t${clEn}`)
}
console.log(`\nTOTAL ${catalog.length} countries, ${bad} with no English name`)
console.log('\n=== UNRESOLVED (provs>=' + MIN_PROVS + ', likely regions — excluded) ===')
console.log(unresolved.map(u => `${u.dest} (${u.provs}p)`).join('\n'))

// Emit final JS array — {he, iso} for ISO countries, {he, en} for sub-national.
const js = catalog.map(c => c.iso
  ? `  { he: ${JSON.stringify(c.he)}, iso: '${c.iso}' },`
  : `  { he: ${JSON.stringify(c.he)}, en: ${JSON.stringify(c.en)} },`
).join('\n')
fs.writeFileSync('scripts/_hotel_destinations.out.js', js, 'utf8')
console.log('\nWrote scripts/_hotel_destinations.out.js (' + catalog.length + ' entries)')
