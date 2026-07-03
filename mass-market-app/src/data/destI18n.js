/**
 * Destination localization for the eSIM / global / roaming filters and cards.
 *
 * Resolution order (localizeDest → _toEn):
 *   1. REGION_EN     — regions / zones / bundles (not real ISO countries)
 *   2. COUNTRY_EN    — non-ISO places + bundles with a fixed English name
 *   3. COUNTRY_ALIAS — spelling variants → the canonical Hebrew in the country
 *                      catalog (hotelDestinations), so destLabel (ISO →
 *                      Intl.DisplayNames) yields the SAME English as the
 *                      canonical spelling → variants dedupe cleanly
 *   4. "N+ מדינות" / "<region> (N מדינות)" count patterns
 *   5. strip a trailing ", <region>" or "(...)" note, retry
 *   6. destLabel(he) — ISO → Intl.DisplayNames, else the Hebrew itself
 *
 * The stored value stays Hebrew everywhere (it matches global_plans.extras[0]
 * and drives filtering); only the DISPLAYED label is localized. `destKey(he)`
 * returns the canonical English used to collapse duplicate spellings in the
 * filter dropdowns (dedupeDestOptions) and to compare when filtering.
 */

import { destLabel } from './hotelDestinations.js'

const HE = /[֐-׿]/

export const REGION_EN = {
  'אירופה': 'Europe',
  'אסיה': 'Asia',
  'אסיה ואוקיאניה': 'Asia & Oceania',
  'אפריקה': 'Africa',
  'גלובלי': 'Global',
  'גלובלי ושייט': 'Global & Cruise',
  'שייט': 'Cruise',
  'קרוז': 'Cruise',
  'קריביים': 'Caribbean',
  'איי הקריביים': 'Caribbean Islands',
  'מדינות האיים הקריביים': 'Caribbean Islands',
  'אמריקה הלטינית': 'Latin America',
  'צפון אמריקה': 'North America',
  'המזרח התיכון': 'Middle East',
  'המזרח התיכון וצפון אפריקה': 'Middle East & North Africa',
  'דרום מזרח אסיה': 'Southeast Asia',
  'סקנדינביה': 'Scandinavia',
  'בלקן': 'Balkans',
  'מזרח אירופה': 'Eastern Europe',
  'מרכז אמריקה': 'Central America',
  'אמריקה המרכזית': 'Central America',
  'אוקיאניה': 'Oceania',
  'סין + הונג קונג + מקאו': 'China + Hong Kong + Macau',
  'יפן וקוריאה': 'Japan & Korea',
  'יפן וסין': 'Japan & China',
  'אסיה פסיפיק': 'Asia Pacific',
  'מרכז אסיה': 'Central Asia',
  'צפון אפריקה': 'North Africa',
  'שוויץ+': 'Switzerland+',
  'גוודלופ': 'Guadeloupe',
  'קפריסין+': 'Cyprus+',
  'אמריקה הדרומית': 'South America',
  'דרום אמריקה': 'South America',
  'צפון ודרום אמריקה': 'North & South America',
  'אירופה — גלישה בלבד': 'Europe - data only',
  'אירופה — גולשים ומדברים': 'Europe - data & calls',
  'ספארי אפריקה': 'Africa Safari',
  'האיחוד האירופי ובריטניה': 'EU & UK',
  'האיחוד האירופי': 'European Union',
  'כלל העולם': 'Worldwide',
  'אירופה+': 'Europe+',
  'חבר המדינות': 'CIS',
  'אירופה וארה"ב': 'Europe & USA',
  'פורטוגל וספרד': 'Portugal & Spain',
  'המזרח התיכון לייט': 'Middle East Lite',
  'אירופה לייט': 'Europe Lite',
  'האנטילים הצרפתיים': 'French Antilles',
  'אמריקה': 'Americas',
  'האמריקות': 'Americas',
  'ביג אמריקה': 'Big America',
  'מצרים וירדן': 'Egypt & Jordan',
  'אנדורה וספרד': 'Andorra & Spain',
  // Multi-country bundles + regions seen in live global_plans.extras[0]
  'אוסטרליה וניו זילנד': 'Australia & New Zealand',
  'ארצות הברית קנדה ואנגליה': 'USA, Canada & UK',
  'בריטניה ואירלנד': 'UK & Ireland',
  'גיאנה הצרפתית ומרטיניק': 'French Guiana & Martinique',
  'דרום מזרח אסיה ואוקיאניה': 'Southeast Asia & Oceania',
  'האי מאן ואיי התעלה': 'Isle of Man & Channel Islands',
  'איי התעלה': 'Channel Islands',
  'האיים הקריביים': 'Caribbean Islands',
  'האיים הקריביים ההולנדיים': 'Dutch Caribbean',
  'האנטילים': 'Antilles',
  'המזרח התיכון ואפריקה': 'Middle East & Africa',
  'חבר העמים': 'Commonwealth',
  'טורקיה ואיי יוון': 'Turkey & Greek Islands',
  'מדינות המפרץ': 'Gulf States',
  'מלזיה וסינגפור': 'Malaysia & Singapore',
  'מערב אירופה': 'Western Europe',
  'מקאו והונג קונג': 'Macau & Hong Kong',
  'מקסיקו וארה"ב': 'Mexico & USA',
  'סן מרטן וגוודלופ': 'Saint Martin & Guadeloupe',
  'סקנדינביה והבלטיות': 'Scandinavia & Baltics',
  'גלובלי מיני': 'Global Mini',
  'קרוז בספינה': 'Cruise Ship',
  'דקות לישראל ובחו"ל': 'Calls to Israel & abroad',
  'כולל': 'Included',
}

// Non-ISO places / bundles with a fixed English name (no catalog canonical).
export const COUNTRY_EN = {
  'אנטילים הולנדיים': 'Netherlands Antilles',
  'האיים האזוריים': 'Azores',
  'מרי-גלנט': 'Marie-Galante',
  'סאבה': 'Saba',
  'סינט אוסטטיוס': 'Sint Eustatius',
  'סנט מארטן': 'Sint Maarten',
  'בורונדי': 'Burundi',
  'טורקמניסטן': 'Turkmenistan',
  'פאלאו': 'Palau',
  'איי קומורו': 'Comoros',
  'אנגליה': 'United Kingdom',
  // Single places / countries / cities / states from live global_plans.extras[0]
  'איי שלמה': 'Solomon Islands',
  'באלי': 'Bali',
  'ג\'יבוטי': 'Djibouti',
  'גינאה המשוונית': 'Equatorial Guinea',
  'דובאי': 'Dubai',
  'הוואי': 'Hawaii',
  'הליפקס': 'Halifax',
  'טורונטו': 'Toronto',
  'טקסס': 'Texas',
  'מארי-גאלאנט': 'Marie-Galante',
  'ניו יורק': 'New York',
  'סאו טומה ופרינסיפה': 'São Tomé & Príncipe',
  'סמואה האמריקנית': 'American Samoa',
  'פלורידה': 'Florida',
  'קונגו ברזוויל': 'Congo-Brazzaville',
  'קלדוניה החדשה': 'New Caledonia',
  'קליפורניה': 'California',
}

// Spelling variants → canonical Hebrew present in the country catalog, so
// destLabel resolves them to the SAME English as the canonical spelling.
export const COUNTRY_ALIAS = {
  'אזרביג\'ן': 'אזרבייג\'ן',
  'איחוד האמירויות הערביות': 'איחוד האמירויות',
  'ארה"ב': 'ארצות הברית',
  'בילרוס': 'בלארוס',
  'בלרוס': 'בלארוס',
  'גיאורגיה': 'גאורגיה',
  'הונג-קונג': 'הונג קונג',
  'טאיוואן': 'טייוואן',
  'מצריים': 'מצרים',
  'חבילת מצרים': 'מצרים',
  'מקדוניה': 'מקדוניה הצפונית',
  'ניגר': 'ניג\'ר',
  'ניז\'ר': 'ניג\'ר',
  'ניקרגואה': 'ניקראגואה',
  'סורינם': 'סורינאם',
  'סיישל': 'איי סיישל',
  'פיליפינים': 'הפיליפינים',
  'פרגוואי': 'פראגוואי',
  'ריוניון': 'ראוניון',
  'שוודיה': 'שבדיה',
  'כף ורדה': 'קייפ ורדה',
  'סווזילנד': 'אסוואטיני',
  'בוסניה': 'בוסניה והרצגובינה',
  'קיימן איילנד': 'איי קיימן',
  'גבון': 'גאבון',
  'מונטסראט': 'מונסראט',
  'איי בתולה בריטיים': 'איי הבתולה (בריטניה)',
  'איי הבתולה הבריטיים': 'איי הבתולה (בריטניה)',
  'איי טורק וקייקוס': 'איי טורקס וקאיקוס',
  'איי טרקס וקייקוס': 'איי טורקס וקאיקוס',
  'סנט קיטס': 'סנט קיטס ונוויס',
  'סנט וינסנט': 'סנט וינסנט והגרדינים',
  'סנט וינסנט והגרנדינים': 'סנט וינסנט והגרדינים',
  'מקדוניה הצפונית': 'מקדוניה הצפונית',
  'אמולדובה': 'מולדובה',
}

// English for the region prefix inside a "<region> (N מדינות)" bundle label.
const REGION_PREFIX_EN = {
  'אירופה': 'Europe',
  'גלובלי': 'Global',
  'דרום אמריקה': 'South America',
  'אסיה': 'Asia',
  'אפריקה': 'Africa',
}

const COUNT_RE = /^(\d+)(\+?)\s*מדינות$/
const PREFIX_COUNT_RE = /^(.+?)\s*\((\d+)\s*מדינות\)$/

function _toEn(s) {
  if (REGION_EN[s]) return REGION_EN[s]
  if (COUNTRY_EN[s]) return COUNTRY_EN[s]
  if (COUNTRY_ALIAS[s]) return destLabel(COUNTRY_ALIAS[s], 'en')

  const m1 = s.match(COUNT_RE)
  if (m1) return `${m1[1]}${m1[2]} countries`

  const m2 = s.match(PREFIX_COUNT_RE)
  if (m2) {
    const prefix = REGION_EN[m2[1]] || REGION_PREFIX_EN[m2[1]] || _toEn(m2[1])
    return `${prefix} (${m2[2]} countries)`
  }

  // Trailing ", <region>" note, e.g. "גאנה, מערב אפריקה".
  if (s.includes(',')) {
    const base = s.replace(/\s*,.*$/, '').trim()
    if (base && base !== s) {
      const r = _toEn(base)
      if (!HE.test(r)) return r
    }
  }
  // Trailing parenthetical note, e.g. "קפריסין (דרום)".
  if (s.includes('(')) {
    const base = s.replace(/\s*\(.*\)\s*$/, '').trim()
    if (base && base !== s) {
      const r = _toEn(base)
      if (!HE.test(r)) return r
    }
  }

  return destLabel(s, 'en')
}

/** Localized destination label. Hebrew passes through unchanged. */
export function localizeDest(he, lang = 'en') {
  if (!he || lang === 'he') return he
  return _toEn(String(he))
}

// ── Cruise ──────────────────────────────────────────────────────────────────
// A few providers sell cruise-at-sea packages under different destination
// strings (Maya "גלובלי ושייט", Voye "קרוז בספינה"). The filters expose them as
// ONE synthetic "Cruise / קרוז" option instead of several near-duplicate rows.
export const CRUISE_VALUE = 'קרוז' // sentinel filter value (also the HE label)
export function isCruiseDest(he) {
  return !!he && /שייט|קרוז|cruise/i.test(String(he))
}
export function cruiseLabel(lang) {
  return lang === 'he' ? 'קרוז' : 'Cruise'
}

// Canonical English key for a destination — used to collapse duplicate Hebrew
// spellings in the dropdowns and to compare when filtering. Cached.
const _keyCache = new Map()
export function destKey(he) {
  if (!he) return ''
  if (_keyCache.has(he)) return _keyCache.get(he)
  const k = _toEn(String(he))
  _keyCache.set(he, k)
  return k
}

/**
 * Build de-duplicated {value, label} options from a list of Hebrew destination
 * strings: strings that localize to the same English collapse into one option.
 * value = a representative Hebrew string (filtering compares via destKey, so any
 * representative matches all its spelling variants); label = localized name.
 */
export function dedupeDestOptions(heList, lang) {
  const byKey = new Map()
  for (const he of heList) {
    if (!he) continue
    const k = destKey(he)
    if (!byKey.has(k)) byKey.set(k, he) // first spelling wins as representative
  }
  const opts = [...byKey.entries()].map(([k, he]) => ({ value: he, label: lang === 'he' ? he : k }))
  return opts.sort((a, b) => a.label.localeCompare(b.label, lang === 'he' ? 'he' : 'en'))
}
