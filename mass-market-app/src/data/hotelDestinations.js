/**
 * MOCA Guest Connect — hotel destination catalog.
 *
 * Single source of truth for the country a hotel's guest portal localizes to.
 * `he` is the canonical Hebrew destination string that EXACTLY matches
 * `global_plans.extras[0]` in the DB (so the backend can filter the eSIM feed by
 * it). `iso` is the ISO 3166-1 alpha-2 code, used only to localize the display
 * name into the guest's language via `Intl.DisplayNames` (no per-language table
 * to maintain). Sub-national / non-ISO destinations (Scotland, Madeira, Northern
 * Cyprus, Bonaire) carry an explicit `en` instead — `destLabel` falls back to it.
 *
 * Generated + validated by scripts/gen_hotel_destinations.mjs from the live
 * destination inventory; regions/bundles ("אירופה", "גלובלי") are deliberately
 * excluded — the portal localizes to a single destination.
 */

export const DEFAULT_DEST = 'ישראל'

export const HOTEL_DESTINATIONS = [
  { he: "אוגנדה", iso: 'UG' },
  { he: "אוזבקיסטן", iso: 'UZ' },
  { he: "אוסטריה", iso: 'AT' },
  { he: "אוסטרליה", iso: 'AU' },
  { he: "אוקראינה", iso: 'UA' },
  { he: "אורוגוואי", iso: 'UY' },
  { he: "אזרבייג'ן", iso: 'AZ' },
  { he: "איחוד האמירויות", iso: 'AE' },
  { he: "איטליה", iso: 'IT' },
  { he: "איי אולנד", iso: 'AX' },
  { he: "איי הבהאמה", iso: 'BS' },
  { he: "איי הבתולה (ארה\"ב)", iso: 'VI' },
  { he: "איי הבתולה (בריטניה)", iso: 'VG' },
  { he: "איי טורקס וקאיקוס", iso: 'TC' },
  { he: "איי מריאנה הצפוניים", iso: 'MP' },
  { he: "איי סיישל", iso: 'SC' },
  { he: "איי פארו", iso: 'FO' },
  { he: "איי קיימן", iso: 'KY' },
  { he: "אינדונזיה", iso: 'ID' },
  { he: "איסלנד", iso: 'IS' },
  { he: "איראן", iso: 'IR' },
  { he: "אירלנד", iso: 'IE' },
  { he: "אל סלבדור", iso: 'SV' },
  { he: "אלבניה", iso: 'AL' },
  { he: "אלג'יריה", iso: 'DZ' },
  { he: "אנגווילה", iso: 'AI' },
  { he: "אנגולה", iso: 'AO' },
  { he: "אנדורה", iso: 'AD' },
  { he: "אנטיגואה וברבודה", iso: 'AG' },
  { he: "אסוואטיני", iso: 'SZ' },
  { he: "אסטוניה", iso: 'EE' },
  { he: "אפגניסטן", iso: 'AF' },
  { he: "אקוודור", iso: 'EC' },
  { he: "ארגנטינה", iso: 'AR' },
  { he: "ארובה", iso: 'AW' },
  { he: "ארמניה", iso: 'AM' },
  { he: "ארצות הברית", iso: 'US' },
  { he: "אתיופיה", iso: 'ET' },
  { he: "בהוטן", iso: 'BT' },
  { he: "בוטסואנה", iso: 'BW' },
  { he: "בולגריה", iso: 'BG' },
  { he: "בוליביה", iso: 'BO' },
  { he: "בונייר", en: "Bonaire" },
  { he: "בוסניה והרצגובינה", iso: 'BA' },
  { he: "בורקינה פאסו", iso: 'BF' },
  { he: "בחריין", iso: 'BH' },
  { he: "בלארוס", iso: 'BY' },
  { he: "בלגיה", iso: 'BE' },
  { he: "בליז", iso: 'BZ' },
  { he: "בנגלדש", iso: 'BD' },
  { he: "בנין", iso: 'BJ' },
  { he: "ברבדוס", iso: 'BB' },
  { he: "ברוניי", iso: 'BN' },
  { he: "ברזיל", iso: 'BR' },
  { he: "בריטניה", iso: 'GB' },
  { he: "ברמודה", iso: 'BM' },
  { he: "ג'מייקה", iso: 'JM' },
  { he: "ג'רזי", iso: 'JE' },
  { he: "גאבון", iso: 'GA' },
  { he: "גאורגיה", iso: 'GE' },
  { he: "גאנה", iso: 'GH' },
  { he: "גואטמלה", iso: 'GT' },
  { he: "גואם", iso: 'GU' },
  { he: "גוואדלופ", iso: 'GP' },
  { he: "גיאנה", iso: 'GY' },
  { he: "גיאנה הצרפתית", iso: 'GF' },
  { he: "גיברלטר", iso: 'GI' },
  { he: "גינאה", iso: 'GN' },
  { he: "גינאה ביסאו", iso: 'GW' },
  { he: "גמביה", iso: 'GM' },
  { he: "גרינלנד", iso: 'GL' },
  { he: "גרמניה", iso: 'DE' },
  { he: "גרנדה", iso: 'GD' },
  { he: "גרנזי", iso: 'GG' },
  { he: "דומיניקה", iso: 'DM' },
  { he: "דנמרק", iso: 'DK' },
  { he: "דרום אפריקה", iso: 'ZA' },
  { he: "דרום סודן", iso: 'SS' },
  { he: "דרום קוריאה", iso: 'KR' },
  { he: "האי מאן", iso: 'IM' },
  { he: "האיטי", iso: 'HT' },
  { he: "האיים המלדיביים", iso: 'MV' },
  { he: "האיים הקנריים", iso: 'IC' },
  { he: "הודו", iso: 'IN' },
  { he: "הולנד", iso: 'NL' },
  { he: "הונג קונג", iso: 'HK' },
  { he: "הונגריה", iso: 'HU' },
  { he: "הונדורס", iso: 'HN' },
  { he: "הפיליפינים", iso: 'PH' },
  { he: "הרפובליקה הדומיניקנית", iso: 'DO' },
  { he: "הרפובליקה הדמוקרטית של קונגו", iso: 'CD' },
  { he: "הרפובליקה המרכז אפריקאית", iso: 'CF' },
  { he: "וייטנאם", iso: 'VN' },
  { he: "ונואטו", iso: 'VU' },
  { he: "ונצואלה", iso: 'VE' },
  { he: "ותיקן", iso: 'VA' },
  { he: "זימבבואה", iso: 'ZW' },
  { he: "זמביה", iso: 'ZM' },
  { he: "חוף השנהב", iso: 'CI' },
  { he: "טג'יקיסטן", iso: 'TJ' },
  { he: "טוגו", iso: 'TG' },
  { he: "טונגה", iso: 'TO' },
  { he: "טורקיה", iso: 'TR' },
  { he: "טייוואן", iso: 'TW' },
  { he: "טימור לסטה", iso: 'TL' },
  { he: "טנזניה", iso: 'TZ' },
  { he: "טרינידד וטובגו", iso: 'TT' },
  { he: "יוון", iso: 'GR' },
  { he: "יפן", iso: 'JP' },
  { he: "ירדן", iso: 'JO' },
  { he: "ישראל", iso: 'IL' },
  { he: "כוויית", iso: 'KW' },
  { he: "לאוס", iso: 'LA' },
  { he: "לבנון", iso: 'LB' },
  { he: "לוב", iso: 'LY' },
  { he: "לוקסמבורג", iso: 'LU' },
  { he: "לטביה", iso: 'LV' },
  { he: "ליבריה", iso: 'LR' },
  { he: "ליטא", iso: 'LT' },
  { he: "ליכטנשטיין", iso: 'LI' },
  { he: "לסוטו", iso: 'LS' },
  { he: "מאוריטניה", iso: 'MR' },
  { he: "מאוריציוס", iso: 'MU' },
  { he: "מאיוט", iso: 'YT' },
  { he: "מאלי", iso: 'ML' },
  { he: "מדגסקר", iso: 'MG' },
  { he: "מדיירה", en: "Madeira" },
  { he: "מוזמביק", iso: 'MZ' },
  { he: "מולדובה", iso: 'MD' },
  { he: "מונגוליה", iso: 'MN' },
  { he: "מונטנגרו", iso: 'ME' },
  { he: "מונסראט", iso: 'MS' },
  { he: "מונקו", iso: 'MC' },
  { he: "מיאנמר", iso: 'MM' },
  { he: "מלאווי", iso: 'MW' },
  { he: "מלזיה", iso: 'MY' },
  { he: "מלטה", iso: 'MT' },
  { he: "מצרים", iso: 'EG' },
  { he: "מקאו", iso: 'MO' },
  { he: "מקדוניה הצפונית", iso: 'MK' },
  { he: "מקסיקו", iso: 'MX' },
  { he: "מרוקו", iso: 'MA' },
  { he: "מרטיניק", iso: 'MQ' },
  { he: "נאורו", iso: 'NR' },
  { he: "נורבגיה", iso: 'NO' },
  { he: "ניג'ר", iso: 'NE' },
  { he: "ניגריה", iso: 'NG' },
  { he: "ניו זילנד", iso: 'NZ' },
  { he: "ניקראגואה", iso: 'NI' },
  { he: "נמיביה", iso: 'NA' },
  { he: "נפאל", iso: 'NP' },
  { he: "סודן", iso: 'SD' },
  { he: "סורינאם", iso: 'SR' },
  { he: "סיירה ליאונה", iso: 'SL' },
  { he: "סין", iso: 'CN' },
  { he: "סינגפור", iso: 'SG' },
  { he: "סלובניה", iso: 'SI' },
  { he: "סלובקיה", iso: 'SK' },
  { he: "סמואה", iso: 'WS' },
  { he: "סן ברתלמי", iso: 'BL' },
  { he: "סן מרטן", iso: 'MF' },
  { he: "סן מרינו", iso: 'SM' },
  { he: "סנגל", iso: 'SN' },
  { he: "סנט וינסנט והגרדינים", iso: 'VC' },
  { he: "סנט לוסיה", iso: 'LC' },
  { he: "סנט קיטס ונוויס", iso: 'KN' },
  { he: "ספרד", iso: 'ES' },
  { he: "סקוטלנד", en: "Scotland" },
  { he: "סרביה", iso: 'RS' },
  { he: "סרי לנקה", iso: 'LK' },
  { he: "עומאן", iso: 'OM' },
  { he: "עיראק", iso: 'IQ' },
  { he: "ערב הסעודית", iso: 'SA' },
  { he: "פוארטו ריקו", iso: 'PR' },
  { he: "פולין", iso: 'PL' },
  { he: "פולינזיה הצרפתית", iso: 'PF' },
  { he: "פורטוגל", iso: 'PT' },
  { he: "פיג'י", iso: 'FJ' },
  { he: "פינלנד", iso: 'FI' },
  { he: "פנמה", iso: 'PA' },
  { he: "פפואה גינאה החדשה", iso: 'PG' },
  { he: "פקיסטן", iso: 'PK' },
  { he: "פראגוואי", iso: 'PY' },
  { he: "פרו", iso: 'PE' },
  { he: "צ'אד", iso: 'TD' },
  { he: "צ'ילה", iso: 'CL' },
  { he: "צ'כיה", iso: 'CZ' },
  { he: "צרפת", iso: 'FR' },
  { he: "קובה", iso: 'CU' },
  { he: "קולומביה", iso: 'CO' },
  { he: "קוסובו", iso: 'XK' },
  { he: "קוסטה ריקה", iso: 'CR' },
  { he: "קוראסאו", iso: 'CW' },
  { he: "קזחסטן", iso: 'KZ' },
  { he: "קטר", iso: 'QA' },
  { he: "קייפ ורדה", iso: 'CV' },
  { he: "קירגיזסטן", iso: 'KG' },
  { he: "קיריבאטי", iso: 'KI' },
  { he: "קמבודיה", iso: 'KH' },
  { he: "קמרון", iso: 'CM' },
  { he: "קנדה", iso: 'CA' },
  { he: "קניה", iso: 'KE' },
  { he: "קפריסין", iso: 'CY' },
  { he: "קפריסין הצפונית", en: "Northern Cyprus" },
  { he: "קרואטיה", iso: 'HR' },
  { he: "ראוניון", iso: 'RE' },
  { he: "רואנדה", iso: 'RW' },
  { he: "רומניה", iso: 'RO' },
  { he: "רוסיה", iso: 'RU' },
  { he: "רפובליקת קונגו", iso: 'CG' },
  { he: "שבדיה", iso: 'SE' },
  { he: "שוויץ", iso: 'CH' },
  { he: "תאילנד", iso: 'TH' },
  { he: "תוניסיה", iso: 'TN' },
  { he: "תימן", iso: 'YE' },
]

/** Canonical Hebrew destination → full catalog entry. */
export const DEST_BY_HE = Object.fromEntries(HOTEL_DESTINATIONS.map(d => [d.he, d]))
/** Canonical Hebrew destination → ISO 3166-1 alpha-2 code (ISO entries only). */
export const DEST_ISO_BY_HE = Object.fromEntries(
  HOTEL_DESTINATIONS.filter(d => d.iso).map(d => [d.he, d.iso]))

const _displayNamesCache = {}
function _displayNames(lang) {
  if (!(lang in _displayNamesCache)) {
    try { _displayNamesCache[lang] = new Intl.DisplayNames([lang], { type: 'region' }) }
    catch { _displayNamesCache[lang] = null }
  }
  return _displayNamesCache[lang]
}

/**
 * Localized country name for display. Hebrew returns the canonical string as-is
 * (the operator-chosen, scraper-matching spelling); other languages resolve via
 * `Intl.DisplayNames` from the ISO code, or the explicit `en` for sub-national
 * destinations. Always falls back to the Hebrew string.
 */
export function destLabel(he, lang = 'en') {
  if (!he) return ''
  if (lang === 'he') return he
  const entry = DEST_BY_HE[he]
  if (entry && entry.iso) {
    const dn = _displayNames(lang)
    try { const n = dn && dn.of(entry.iso); if (n && n !== entry.iso) return n } catch { /* fall through */ }
  }
  if (entry && entry.en) return entry.en  // sub-national, or fr/ru fallback
  return he
}

// Hebrew prepositional ("ב…") forms where naive "ב"+name is wrong because the
// name starts with the definite article ה, which the prefix absorbs. Names whose
// leading ה is part of the word (הולנד, הודו, הונגריה…) keep the default.
const INHE_OVERRIDES = {
  'הפיליפינים': 'בפיליפינים',
  'הרפובליקה הדומיניקנית': 'ברפובליקה הדומיניקנית',
  'הרפובליקה הדמוקרטית של קונגו': 'ברפובליקה הדמוקרטית של קונגו',
  'הרפובליקה המרכז אפריקאית': 'ברפובליקה המרכז אפריקאית',
  'האיים המלדיביים': 'באיים המלדיביים',
  'האיים הקנריים': 'באיים הקנריים',
  'האי מאן': 'באי מאן',
}

/** Hebrew "in {country}" phrase, e.g. 'בקפריסין' / 'בפיליפינים'. */
export function destInHe(he) {
  if (!he) return ''
  return INHE_OVERRIDES[he] || ('ב' + he)
}
