/**
 * Network priority detection — premium 5G tiers with guaranteed priority on
 * the carrier's network during congestion (תעדוף ברשת).
 *
 * The scraper does not capture priority badges from carrier pages, so we rely
 * on brand-specific tier names known to ship with priority guarantees:
 *   Pelephone — "5G Max VIP"
 *   Cellcom   — "5G Pro / Pro Care / Pro Sound / Pro Fly"
 *   Hotmobile — "5G ULTRA / Premium"
 *   Partner   — "Boost"
 *   We-Com    — "wecomGlobal 5G ULTRA"
 *
 * Update both this file AND scraper-side enrichment together when a carrier
 * adds a new priority tier name.
 */
export const MAX_PRIORITY_KEYWORDS = ['MAX', 'ULTRA', 'PREMIUM', 'VIP', 'PRO', 'BOOST']

const KW_PATTERNS = MAX_PRIORITY_KEYWORDS.map(kw => new RegExp(`\\b${kw}\\b`))
// Matches "5G" (English) and "דור 5" / "דור5" (Hebrew "Generation 5", used by
// Rami Levy and others who don't write "5G" in plan_name/extras).
const FIVE_G_PATTERN = /\b5G\b|דור\s?5/

function planHaystack(plan) {
  return ((plan.plan_name || '') + ' ' + ((plan.extras || []).join(' '))).toUpperCase()
}

export function has5G(plan) {
  return FIVE_G_PATTERN.test(planHaystack(plan))
}

export function hasMaxPriority(plan) {
  const h = planHaystack(plan)
  // Network priority requires 5G — guards against false positives like Rami Levy's
  // "MAX Kosher" plan, where MAX refers to kashrut level, not network priority.
  return FIVE_G_PATTERN.test(h) && KW_PATTERNS.some(re => re.test(h))
}

/**
 * Returns 'max' (premium 5G with priority), 'basic' (plain 5G), or 'none'.
 */
export function classifyPriority(plan) {
  const h = planHaystack(plan)
  const fiveG = FIVE_G_PATTERN.test(h)
  if (fiveG && KW_PATTERNS.some(re => re.test(h))) return 'max'
  if (fiveG) return 'basic'
  return 'none'
}
