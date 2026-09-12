// Region labels on global plans (extras[0]) and their consolidation rules.
// Extracted from DashboardPage.jsx (2026-09); used by hooks/useDashboardPlans.js.

export const KNOWN_REGIONS = new Set([
  'אירופה','אסיה','אסיה ואוקיאניה','אפריקה','גלובלי','קריביים','איי הקריביים',
  'אמריקה הלטינית','צפון אמריקה','המזרח התיכון','המזרח התיכון וצפון אפריקה',
  'דרום מזרח אסיה','סקנדינביה','בלקן','מזרח אירופה','מרכז אמריקה','אוקיאניה',
  'סין + הונג קונג + מקאו','יפן וקוריאה','יפן וסין',
  'אסיה פסיפיק','מרכז אסיה','צפון אפריקה',
  'שוויץ+','גוודלופ','קפריסין+',
  'אמריקה הדרומית','דרום אמריקה',
  'צפון ודרום אמריקה','מדינות האיים הקריביים',
  'אירופה — גלישה בלבד','אירופה — גולשים ומדברים',
  '167+ מדינות','156+ מדינות',
  'ספארי אפריקה','האיחוד האירופי ובריטניה',
  'כלל העולם',
  // Breeze regions
  'אירופה+','אמריקה המרכזית','חבר המדינות',
  'אירופה וארה"ב','פורטוגל וספרד','המזרח התיכון לייט','אירופה לייט',
  // SimTLV catalog regional bundles (counts < 100 so the generic
  // "N מדינות → גלובלי" rule doesn't catch them)
  'אירופה (32 מדינות)','אירופה (33 מדינות)','אירופה (37 מדינות)',
  'גלובלי (36 מדינות)','גלובלי (37 מדינות)','גלובלי (41 מדינות)',
  'גלובלי (47 מדינות)','גלובלי (58 מדינות)','גלובלי (84 מדינות)',
  'דרום אמריקה (11 מדינות)',
])

// Region-label consolidation rules:
// 1. Any "<N>+? מדינות" tag with N > 100 → unified "גלובלי" (global multi-country bundle).
// 2. Any tag whose name contains the word "אירופה" (e.g. "אירופה+", "אירופה לייט",
//    "אירופה — גלישה בלבד", "מזרח אירופה") → unified "אירופה" so the regions
//    dropdown shows one Europe entry instead of six near-duplicates.
const MULTI_COUNTRY_REGION_RE = /^(\d+)\+?\s*מדינות$/
export function isLargeMultiCountryRegion(region) {
  const m = region && String(region).match(MULTI_COUNTRY_REGION_RE)
  return !!m && parseInt(m[1], 10) > 100
}
export function normalizeRegionLabel(region) {
  if (isLargeMultiCountryRegion(region)) return 'גלובלי'
  if (region && String(region).includes('אירופה')) return 'אירופה'
  // "גלובלי (47 מדינות)" etc. (SimTLV) fold into the unified global entry
  if (region && String(region).includes('גלובלי')) return 'גלובלי'
  return region
}
