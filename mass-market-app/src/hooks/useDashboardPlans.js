// Dashboard plan pipeline - extracted from DashboardPage.jsx (2026-09) so the
// filter / sort / group / destination logic is a set of PURE functions with one
// thin memoizing hook on top. DashboardPage only wires state in and cards out.
//
//   filterAndSortPlans   - tab-aware filters (carrier, 5G, roaming, provider,
//                          region/destination/cruise, GB, days) + sort
//   groupGlobalDisplayItems - global tab: one card per (provider, destination)
//                          with the GB ladder inside (GroupedPlanCard)
//   globalRegionsOf / globalDestinationsOf / hasCruisePackages - dropdown sources
//   useDashboardPlans    - the hook DashboardPage calls
import { useMemo } from 'react'
import { has5G, hasMaxPriority } from '../data/networkPriority'
import { destKey, dedupeDestOptions, isCruiseDest, cruiseLabel, CRUISE_VALUE } from '../data/destI18n'
import { ISRAELI_GLOBAL_PROVIDERS } from '../data/carrierLabels'
import { MULTI_COUNTRY_CARRIERS, getPlanCoverage } from '../data/planCoverage'
import { KNOWN_REGIONS, isLargeMultiCountryRegion, normalizeRegionLabel } from '../data/regionLabels'

// Provider filter chip -> carrier ids (airalo is three scraper ids)
export function providerIds(globalProvider) {
  return globalProvider === 'airalo' ? ['airalo', 'airalo_local', 'airalo_regional'] : [globalProvider]
}

function scopeToProvider(plansGlobal, globalProvider) {
  if (globalProvider === 'all') return plansGlobal
  const ids = providerIds(globalProvider)
  return plansGlobal.filter(p => ids.includes(p.carrier))
}

const pricePerGb = (p) => {
  const pr = Number(p.price)
  const gb = Number(p.data_gb)
  if (!pr || !gb || gb <= 0) return null
  return pr / gb
}

/**
 * Filter + sort the plans of one tab. Everything EXCEPT the personal
 * "watched only" filter, which is applied downstream so toggling a star
 * doesn't re-run this (regex-heavy) pass over the full dataset.
 *
 * @param {object[]} tabPlans      plans[tab]
 * @param {string}   tab           domestic | abroad | global | usa | resellers | content
 * @param {object}   f             the filters state object
 * @param {object}   ctx           { visibleCarrierIds, carrierIds, usaOperators }
 */
export function filterAndSortPlans(tabPlans, tab, f, ctx) {
  let result = tabPlans || []
  const { visibleCarrierIds = [], carrierIds = [], usaOperators = [] } = ctx || {}

  // Apply workspace visible_carriers scoping on domestic + abroad tabs
  if ((tab === 'domestic' || tab === 'abroad') && visibleCarrierIds.length < carrierIds.length) {
    result = result.filter(p => visibleCarrierIds.includes(p.carrier))
  }

  if (tab === 'domestic' || tab === 'abroad') {
    if (f.carrier !== 'all') result = result.filter(p => p.carrier === f.carrier)
  }
  if (tab === 'domestic' && f.gen !== 'all') {
    // "5G" = basic 5G only (excludes priority); "5G מתועדף" = priority only
    if (f.gen === '5g') result = result.filter(p => has5G(p) && !hasMaxPriority(p))
    if (f.gen === '5g_priority') result = result.filter(hasMaxPriority)
    if (f.gen === '4g') result = result.filter(p => !has5G(p))
  }
  if (tab === 'domestic' && f.roaming === 'yes') {
    // Accept either a quantified data note ("1GB גלישה בחו\"ל בכל חודש") OR a
    // qualitative "חו\"ל כלול"-style tag (premium plans share total data pool).
    // Pay-per-use abroad routes (e.g. Pelephone's "מסלול חו\"ל Travel") are
    // deliberately NOT matched - they have no included data volume.
    result = result.filter(p => p.extras && p.extras.some(e => {
      const hasIntl = /חו"ל|חו״ל/.test(e)
      if (!hasIntl) return false
      const hasQuantifiedData = /\d+/.test(e) && /GB|גלישה/i.test(e)
      const hasIncludedTag = /(?:כלול(?:ה|ים)?|כולל)/.test(e)
      return hasQuantifiedData || hasIncludedTag
    }))
  }
  if (tab === 'global') {
    if (f.globalProvider !== 'all') {
      const ids = providerIds(f.globalProvider)
      result = result.filter(p => ids.includes(p.carrier))
    }
    if (f.israeliProvider !== 'all') {
      const wantIsraeli = f.israeliProvider === 'israeli'
      result = result.filter(p => ISRAELI_GLOBAL_PROVIDERS.has(p.carrier) === wantIsraeli)
    }
    if (f.region !== 'all') {
      const rTarget = destKey(f.region)
      result = result.filter(p => p.extras && destKey(normalizeRegionLabel(p.extras[0])) === rTarget)
    }
    else if (f.destination === CRUISE_VALUE) {
      // Unified "Cruise" filter - matches every provider's cruise-at-sea package.
      result = result.filter(p => p.extras && isCruiseDest(p.extras[0]))
    }
    else if (f.destination !== 'all') {
      // Compare via canonical English key so a selected representative spelling
      // matches plans tagged with any of its de-duplicated variants.
      const dTarget = destKey(f.destination)
      result = result.filter(p => {
        if (MULTI_COUNTRY_CARRIERS.has(p.carrier)) {
          const coverage = getPlanCoverage(p)
          if (coverage) return coverage.some(c => destKey(c) === dTarget)
          return p.extras && destKey(p.extras[0]) === dTarget
        }
        return p.extras && destKey(p.extras[0]) === dTarget
      })
    }
  }
  if (tab === 'content') {
    const NA = ['לא נמצא', 'שגיאה', 'לא זמין']
    if (f.contentCarrier !== 'all') result = result.filter(p => p.carrier === f.contentCarrier)
    if (f.contentService !== 'all') result = result.filter(p => p.service === f.contentService)
    result = result.filter(p => !p.price || !NA.some(v => String(p.price).includes(v)))
  }
  if (tab === 'resellers') {
    if (f.reseller !== 'all') result = result.filter(p => p.reseller_id === f.reseller)
    if (f.carrier !== 'all') result = result.filter(p => p.carrier === f.carrier)
  }
  if (tab === 'usa') {
    if (f.usaOperator !== 'all') result = result.filter(p => p.carrier === f.usaOperator)
    if (f.usaNetwork !== 'all') {
      const opsOnNet = new Set(usaOperators.filter(o => o.net === f.usaNetwork).map(o => o.id))
      result = result.filter(p => opsOnNet.has(p.carrier))
    }
  }

  if (f.gb !== 'all' && tab !== 'content') {
    if (f.gb === 'unlimited') result = result.filter(p => p.data_gb === null)
    else if (f.gb === '0-5') result = result.filter(p => p.data_gb !== null && p.data_gb <= 5)
    else if (f.gb === '5-15') result = result.filter(p => p.data_gb !== null && p.data_gb > 5 && p.data_gb <= 15)
    else if (f.gb === '15-100') result = result.filter(p => p.data_gb !== null && p.data_gb > 15 && p.data_gb <= 100)
    else if (f.gb === '100+') result = result.filter(p => p.data_gb !== null && p.data_gb > 100)
  }

  if (f.days !== 'all' && (tab === 'abroad' || tab === 'global' || tab === 'usa')) {
    if (f.days === '1-7') result = result.filter(p => p.days && p.days <= 7)
    else if (f.days === '8-14') result = result.filter(p => p.days && p.days > 7 && p.days <= 14)
    else if (f.days === '15-30') result = result.filter(p => p.days && p.days > 14 && p.days <= 30)
    else if (f.days === '30+') result = result.filter(p => p.days && p.days > 30)
  }

  if (f.sort === 'price_asc') result = [...result].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
  else if (f.sort === 'price_desc') result = [...result].sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
  else if (f.sort === 'gb_asc') result = [...result].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
  else if (f.sort === 'gb_desc') result = [...result].sort((a, b) => (b.data_gb ?? 99999) - (a.data_gb ?? 99999))
  else if (f.sort === 'ppgb_asc') result = [...result].sort((a, b) => (pricePerGb(a) ?? 9999) - (pricePerGb(b) ?? 9999))
  else if (f.sort === 'ppgb_desc') result = [...result].sort((a, b) => (pricePerGb(b) ?? 0) - (pricePerGb(a) ?? 0))

  return result
}

// Providers whose bundles are told apart by the plan_name prefix, not extras[0]
const PREFIX_GROUPED = new Set(['bytesim', 'besim', 'seven_g'])

function productLabelOf(plan) {
  const parts = plan.plan_name?.split(' – ') || []
  return parts.slice(0, -2).join(' – ') || plan.extras?.[0]
}

/**
 * Group the global tab into display items: { isGroup: false, plan } or
 * { isGroup: true, carrier, destination, plans } (GroupedPlanCard).
 */
export function groupGlobalDisplayItems(filteredPlans, tab) {
  if (tab !== 'global') return filteredPlans.map(p => ({ isGroup: false, plan: p }))
  const grouped = new Map()
  const singles = []
  for (const plan of filteredPlans) {
    const dest = plan.extras?.[0]
    if (dest) {
      // bytesim: group by product label (plan_name minus last 2 parts) to separate MAX/UK+/Lite
      // besim: same - multiple bundles share extras[0] (4× אסיה, 2× אירופה, 2× גלובלי).
      //        Group by plan_name prefix so each bundle gets its own card.
      // airalo: split Discover (data only) vs Discover+ (data+calls+sms) like Airalo's website tabs
      let key
      if (PREFIX_GROUPED.has(plan.carrier)) {
        key = `${plan.carrier}|${productLabelOf(plan)}`
      } else if (plan.carrier === 'airalo') {
        const operator = (plan.plan_name || '').includes('Discover+') ? 'Discover+' : 'Discover'
        key = `airalo|${dest}|${operator}`
      } else {
        key = `${plan.carrier}|${dest}`
      }
      if (!grouped.has(key)) grouped.set(key, [])
      grouped.get(key).push(plan)
    } else {
      singles.push({ isGroup: false, plan })
    }
  }
  const result = []
  for (const [, plans] of grouped) {
    if (plans.length <= 1) {
      result.push({ isGroup: false, plan: plans[0] })
    } else {
      const byGb = new Map()
      for (const p of plans) {
        // bytesim/maya/besim: keep all (data × days) combinations; other carriers: keep cheapest per GB.
        // Besim's Global bundles have e.g. 1GB/7d AND 1GB/365d - both need to show.
        // Unlimited plans (data_gb null) are differentiated by days so VOYE-style
        // 3GB/יום × {3,7,10,15,20,30}-day variants don't collapse into one card.
        const keepAll = PREFIX_GROUPED.has(p.carrier) || p.carrier === 'maya'
        const isUnlimited = p.data_gb == null
        const gbKey = keepAll
          ? p.plan_name
          : (isUnlimited ? `unl-${p.days ?? 0}` : p.data_gb)
        if (!byGb.has(gbKey) || (!keepAll && p.price < byGb.get(gbKey).price)) byGb.set(gbKey, p)
      }
      const unique = [...byGb.values()].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
      // bytesim/besim: destination shown as product label extracted from plan_name
      // airalo: destination shows Discover vs Discover+ to mirror Airalo's site tabs
      let destination
      if (PREFIX_GROUPED.has(unique[0].carrier)) {
        destination = productLabelOf(unique[0])
      } else if (unique[0].carrier === 'airalo') {
        const isPlus = (unique[0].plan_name || '').includes('Discover+')
        const opLabel = isPlus ? 'Airalo Discover+ - דאטה ושיחות' : 'Airalo Discover - דאטה'
        destination = `${opLabel} (${unique[0].extras[0]})`
      } else {
        destination = unique[0].extras[0]
      }
      result.push({ isGroup: true, carrier: unique[0].carrier, destination, plans: unique })
    }
  }
  return [...result, ...singles]
}

/** Region dropdown source for the global tab (provider-scoped, label-normalized). */
export function globalRegionsOf(plansGlobal, globalProvider) {
  const src = scopeToProvider(plansGlobal, globalProvider)
  return [...new Set(
    src
      .filter(p => p.extras && p.extras[0] && (KNOWN_REGIONS.has(p.extras[0]) || isLargeMultiCountryRegion(p.extras[0])))
      .map(p => normalizeRegionLabel(p.extras[0]))
  )].sort((a, b) => a.localeCompare(b, 'he'))
}

/** Destination dropdown source for the global tab (multi-country coverage expanded). */
export function globalDestinationsOf(plansGlobal, globalProvider) {
  const src = scopeToProvider(plansGlobal, globalProvider)
  const destSet = new Set()
  const isPlainCountry = (d) => d && !/\d/.test(d) && !KNOWN_REGIONS.has(d)
  for (const p of src) {
    // Cruise packages are surfaced via the single synthetic "Cruise" option
    // (see hasCruisePackages / destinationOptions), not as raw per-provider rows.
    if (p.extras && isCruiseDest(p.extras[0])) continue
    if (MULTI_COUNTRY_CARRIERS.has(p.carrier)) {
      const coverage = getPlanCoverage(p)
      if (coverage) {
        for (const c of coverage) destSet.add(c)
      } else if (p.extras && isPlainCountry(p.extras[0])) {
        // single-country plan from a multi-country carrier - add directly
        destSet.add(p.extras[0])
      }
    } else if (p.extras && isPlainCountry(p.extras[0])) {
      destSet.add(p.extras[0])
    }
  }
  return [...destSet].sort((a, b) => a.localeCompare(b, 'he'))
}

/** Any cruise-at-sea package in the (provider-scoped) global set? */
export function hasCruisePackages(plansGlobal, globalProvider) {
  return scopeToProvider(plansGlobal, globalProvider).some(p => p.extras && isCruiseDest(p.extras[0]))
}

/**
 * The memoized pipeline DashboardPage renders from.
 * Memo boundaries mirror the original inline useMemos: the heavy filter+sort
 * pass depends only on (plans, tab, filters); the watchlist toggle re-runs a
 * light filter; grouping re-runs only when the filtered list changes.
 */
export function useDashboardPlans({
  plans, tab, filters, visibleCarrierIds, carrierIds, usaOperators,
  onlyWatched, isWatched, watchItems, lang,
}) {
  // useVisibleCarriers returns a fresh array per render; key on its contents so
  // workspace scoping changes re-filter without re-running on every render.
  const visibleKey = (visibleCarrierIds || []).join(',')
  const baseFilteredPlans = useMemo(
    () => filterAndSortPlans(plans[tab] || [], tab, filters, { visibleCarrierIds, carrierIds, usaOperators }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [plans, tab, filters, visibleKey, carrierIds, usaOperators],
  )

  // Apply the personal "watched only" filter downstream. When off, returns the
  // base array unchanged (stable identity → displayItems doesn't recompute).
  const filteredPlans = useMemo(() => {
    if (!onlyWatched) return baseFilteredPlans
    return baseFilteredPlans.filter(p => isWatched({
      carrier: p.carrier,
      plan_name: p.plan_name || p.service || '',
      plan_type: tab,
    }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseFilteredPlans, onlyWatched, watchItems, isWatched, tab])

  const displayItems = useMemo(() => groupGlobalDisplayItems(filteredPlans, tab), [filteredPlans, tab])

  const globalRegions = useMemo(
    () => (tab === 'global' ? globalRegionsOf(plans.global, filters.globalProvider) : []),
    [plans.global, tab, filters.globalProvider],
  )
  const globalDestinations = useMemo(
    () => (tab === 'global' ? globalDestinationsOf(plans.global, filters.globalProvider) : []),
    [plans.global, tab, filters.globalProvider],
  )
  const hasCruise = useMemo(
    () => tab === 'global' && hasCruisePackages(plans.global, filters.globalProvider),
    [plans.global, tab, filters.globalProvider],
  )

  // Deduplicated, localized dropdown options - spelling variants that resolve to
  // the same English collapse into one entry (value = a representative Hebrew).
  const regionOptions = useMemo(() => dedupeDestOptions(globalRegions, lang), [globalRegions, lang])
  const destinationOptions = useMemo(() => {
    const opts = dedupeDestOptions(globalDestinations, lang)
    // Pin the unified "Cruise" option at the top when cruise packages exist.
    return hasCruise ? [{ value: CRUISE_VALUE, label: cruiseLabel(lang) }, ...opts] : opts
  }, [globalDestinations, hasCruise, lang])

  return {
    baseFilteredPlans, filteredPlans, displayItems,
    globalRegions, globalDestinations, hasCruise, regionOptions, destinationOptions,
  }
}
