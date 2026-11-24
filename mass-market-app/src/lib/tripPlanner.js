import { getPlanCoverage } from '../data/planCoverage'
import { getCountriesForPlan } from '../data/globalCountries'
import { destKey } from '../data/destI18n'

/**
 * Client half of the multi-destination trip planner (server half: esim_trip.py).
 *
 * The server sends, for every contiguous stretch of the itinerary, the cheapest
 * plans that are long enough and have enough data. This module
 *   1. keeps a bundle only when its PUBLISHED coverage list contains every
 *      country of its stretch (a bundle with no coverage list on file is never
 *      assumed to cover anything), and
 *   2. picks the cheapest way to cut the itinerary into stretches.
 *
 * Pure - smoke-testable in node:
 * `npx esbuild src/lib/tripPlanner.js --bundle --platform=node --define:import.meta.env={}`
 */

/** Countries a bundle deal covers, or null when no coverage list is on file. */
export function coverageOf(deal) {
  const plan = { carrier: deal.provider, plan_name: deal.plan_name, extras: [deal.dest] }
  const list = getPlanCoverage(plan) || getCountriesForPlan(plan)?.countries || null
  if (!list) return null
  // Some providers sell several tiers under one region label ("אסיה (14 מדינות)"
  // next to a 26-country Asia), while the coverage list on file is keyed by the
  // label alone. When the plan's own name states fewer countries than the list
  // holds, the list describes a bigger product - treat the coverage as unknown
  // rather than promise a country the plan may not include.
  const stated = statedCountryCount(deal.plan_name)
  if (stated != null && stated < list.length - 1) return null
  return list
}

/** The country count a plan name declares ("(14 מדינות)", "12 areas"), or null. */
export function statedCountryCount(name) {
  const m = String(name || '').match(/(\d{1,3})\+?\s*(?:מדינות|יעדים|countries|areas|destinations)/i)
  return m ? Number(m[1]) : null
}

const _covCache = new Map()
function coverageKeys(deal) {
  const id = `${deal.provider}|${deal.plan_name}|${deal.dest}`
  if (!_covCache.has(id)) {
    const list = coverageOf(deal)
    _covCache.set(id, list ? new Set(list.map(destKey)) : null)
  }
  return _covCache.get(id)
}

/** Does the bundle's coverage list contain every one of `countries`? */
export function coversAll(deal, countries) {
  const keys = coverageKeys(deal)
  return !!keys && countries.every((c) => keys.has(destKey(c)))
}

/**
 * @param legs      [{ destination, days }]
 * @param segments  the server payload's `segments`
 * @returns null when some leg has no option at all, otherwise
 *   { total, parts: [{ from, to, deal, bundle }],        the cheapest split
 *     separate: { total, parts } | null,                 one plan per country
 *     single:   { total, deal } | null,                  one bundle for the trip
 *     saving }                                           vs the separate option
 */
export function planTrip(legs, segments) {
  const n = legs.length
  const best = Array.from({ length: n }, () => Array(n).fill(null))
  const ownBest = Array(n).fill(null)
  for (const seg of segments || []) {
    const countries = legs.slice(seg.from, seg.to + 1).map((l) => l.destination)
    let pick = null
    for (const d of seg.own || []) {
      if (!pick || d.ils < pick.deal.ils) pick = { deal: d, bundle: false }
    }
    if (seg.from === seg.to && pick) ownBest[seg.from] = pick.deal
    for (const d of seg.bundles || []) {
      if (pick && d.ils >= pick.deal.ils) continue
      if (coversAll(d, countries)) pick = { deal: d, bundle: true }
    }
    best[seg.from][seg.to] = pick
  }

  // cost[k] = cheapest way to cover legs 0..k-1
  const cost = Array(n + 1).fill(Infinity)
  const cut = Array(n + 1).fill(-1)
  cost[0] = 0
  for (let k = 1; k <= n; k++) {
    for (let j = 0; j < k; j++) {
      const opt = best[j][k - 1]
      if (!opt || cost[j] === Infinity) continue
      const c = cost[j] + opt.deal.ils
      if (c < cost[k] - 1e-9) { cost[k] = c; cut[k] = j }
    }
  }
  if (cost[n] === Infinity) return null

  const parts = []
  for (let k = n; k > 0; k = cut[k]) {
    const j = cut[k]
    parts.unshift({ from: j, to: k - 1, ...best[j][k - 1] })
  }
  const separate = ownBest.every(Boolean)
    ? { total: ownBest.reduce((s, d) => s + d.ils, 0), parts: ownBest.map((deal, i) => ({ from: i, to: i, deal, bundle: false })) }
    : null
  const whole = best[0][n - 1]
  const single = n > 1 && whole && whole.bundle ? { total: whole.deal.ils, deal: whole.deal } : null
  return {
    total: cost[n], parts, separate, single,
    saving: separate ? Math.max(0, separate.total - cost[n]) : 0,
  }
}
