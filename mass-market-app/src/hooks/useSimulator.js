import { firstYearCost } from './useAgentDeskData'

/**
 * Pure logic for /simulator - the launch simulator ("what if we launched X").
 *
 * The page hands in a DRAFT plan that does not exist yet and the normalized
 * market (the same `normalizePlan` shape /agent-desk uses) and gets back where
 * the draft would land: who already offers at least the same data for no more
 * money (it is "dominated"), whom it would dominate, the price it has to hit to
 * be undominated, and a ladder of the comparable plans around it.
 *
 * Like the agent desk, every comparison is on the FIRST-YEAR cost, so a promo
 * price counts for its months only. Smoke-testable in node:
 * `npx esbuild src/hooks/useSimulator.js --bundle --platform=node --define:import.meta.env={}`.
 */

const gbKey = (gb) => (gb === Infinity ? 1e6 : gb == null ? 0 : gb)
const EPS = 0.01

/** The draft as typed in the form → the normalized shape, or null when incomplete. */
export function buildDraft({ price, promoPrice, promoMonths, gb, unlimited, abroadGb, network, minutesUnlimited }) {
  const p = Number(price)
  if (!(p > 0)) return null
  const g = unlimited ? Infinity : Number(gb)
  if (!unlimited && !(g > 0)) return null
  const pp = Number(promoPrice) > 0 && Number(promoPrice) < p ? Number(promoPrice) : null
  const pm = pp && Number(promoMonths) > 0 ? Math.min(12, Math.round(Number(promoMonths))) : null
  return {
    key: '__draft__',
    isDraft: true,
    source: 'draft',
    carrier: null,
    plan_name: '',
    price: p,
    promoPrice: pm ? pp : null,
    promoMonths: pm,
    yearCost: firstYearCost(p, pm ? pp : null, pm),
    gb: g,
    kind: g === Infinity ? 'unlimited' : 'data',
    minutes: minutesUnlimited ? Infinity : null,
    abroadGb: Math.max(0, Number(abroadGb) || 0),
    network: network || 'none',
    extras: [],
  }
}

/** a dominates b: at least the same data for no more first-year money, better on one. */
export function dominates(a, b) {
  const ga = gbKey(a.gb), gb = gbKey(b.gb)
  if (ga < gb) return false
  if (a.yearCost > b.yearCost + EPS) return false
  return ga > gb || a.yearCost < b.yearCost - EPS
}

/** What the dominating plan lacks that the draft has - the honest counter-arguments. */
function edgesOver(draft, other) {
  const rank = { none: 0, basic: 1, max: 2 }
  const out = []
  if (draft.abroadGb > (other.abroadGb || 0)) out.push('abroad')
  if (rank[draft.network] > rank[other.network || 'none']) out.push('network')
  if (draft.minutes === Infinity && other.minutes != null && other.minutes !== Infinity) out.push('minutes')
  return out
}

/**
 * @param draft        buildDraft() result
 * @param market       normalized rate-card plans of every carrier
 * @param oursCarrier  our carrier id (its plans are reported separately), or null
 * @param resellers    normalized below-the-line offers (optional)
 */
export function simulatePlan(draft, market, oursCarrier, resellers = []) {
  if (!draft) return null
  const dataPlans = (market || []).filter((p) => p && p.kind !== 'voice' && p.gb != null)
  const competitors = dataPlans.filter((p) => p.carrier !== oursCarrier)
  const own = oursCarrier ? dataPlans.filter((p) => p.carrier === oursCarrier) : []

  const byCost = (a, b) => a.yearCost - b.yearCost || gbKey(b.gb) - gbKey(a.gb)
  const dominators = competitors.filter((p) => dominates(p, draft)).sort(byCost)
    .map((p) => ({ plan: p, edges: edgesOver(draft, p) }))
  const beaten = competitors.filter((p) => dominates(draft, p))
    .sort((a, b) => b.yearCost - a.yearCost)

  // Comparable = gives at least the draft's data. The cheapest of them sets the
  // price the draft has to match to stop being dominated.
  const comparable = competitors.filter((p) => gbKey(p.gb) >= gbKey(draft.gb)).sort(byCost)
  const cheapestComparable = comparable[0] || null
  const targetMonthly = cheapestComparable ? cheapestComparable.yearCost / 12 : null

  // Price position among EVERY competitor data plan (share that costs more).
  const pricier = competitors.filter((p) => p.yearCost > draft.yearCost + EPS).length
  const cheaperThanPct = competitors.length ? Math.round((pricier / competitors.length) * 100) : null

  // Per competitor: its cheapest plan with at least the draft's data.
  const perCarrier = []
  for (const carrier of [...new Set(competitors.map((p) => p.carrier))]) {
    const match = comparable.find((p) => p.carrier === carrier) || null
    perCarrier.push({
      carrier,
      plan: match,
      yearGap: match ? match.yearCost - draft.yearCost : null, // >0 = we are cheaper
      beatsUs: match ? dominates(match, draft) : false,
    })
  }
  perCarrier.sort((a, b) => (a.yearGap ?? Infinity) - (b.yearGap ?? Infinity))

  // The ladder: comparable plans by first-year cost with the draft slotted in.
  const ladderAll = [...comparable, draft].sort(byCost)
  const at = ladderAll.indexOf(draft)
  const from = Math.max(0, Math.min(at - 4, ladderAll.length - 9))
  const ladder = ladderAll.slice(from, from + 9)

  const ownClash = {
    undercut: own.filter((p) => dominates(draft, p)).sort((a, b) => b.yearCost - a.yearCost),
    redundant: own.filter((p) => dominates(p, draft)).sort(byCost),
  }
  const btl = (resellers || []).filter((p) => p && p.kind !== 'voice' && p.gb != null && p.carrier !== oursCarrier && dominates(p, draft)).sort(byCost)

  const verdict = !comparable.length ? 'alone' : dominators.length === 0 ? 'leader' : dominators.length <= 2 ? 'contested' : 'dominated'
  return {
    draft, verdict, dominators, beaten, comparable, cheapestComparable, targetMonthly,
    cheaperThanPct, perCarrier, ladder, rank: at + 1, rankOf: ladderAll.length, ownClash, btl,
    marketSize: competitors.length,
  }
}
