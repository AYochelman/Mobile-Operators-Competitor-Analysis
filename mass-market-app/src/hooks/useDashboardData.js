import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'

/**
 * Aggregate dashboard data for the Editorial Deep view.
 *
 * One fetch for plans + one for changes. Everything else is derived in
 * useMemo so cards re-render cheap. Returns:
 *   { loading, plans, changes,
 *     leadChange,    // biggest 24h change with our-plan match
 *     kpis,          // { changesToday, avgPrice, newPlans, oursVsMarket }
 *     heatmap,       // { carriers[], days[], cells: Map<key, count> }
 *     recentChanges, // sorted desc by changed_at, last 30
 *   }
 */

const HEATMAP_DAYS = 14

function impactScore(change) {
  // Bigger absolute price change AND change types we care about score higher.
  if (!change) return 0
  if (change.change_type === 'new_plan') return 50
  if (change.change_type === 'removed_plan') return 30
  if (change.change_type === 'price_change') {
    const oldVal = Number(change.old_val)
    const newVal = Number(change.new_val)
    if (Number.isFinite(oldVal) && Number.isFinite(newVal) && oldVal > 0) {
      const pct = Math.abs((newVal - oldVal) / oldVal) * 100
      return pct  // % drop is the impact magnitude
    }
  }
  return 0
}

function pickLeadChange(changes, plans, oursCarrier) {
  const recent24h = Date.now() - 24 * 60 * 60 * 1000
  const candidates = (changes || []).filter((c) => {
    if (!c?.carrier || c.carrier === oursCarrier) return false  // not us
    if (c.change_type === 'extras_change' || c.change_type === 'details_change') return false
    const ts = c.changed_at ? new Date(c.changed_at).getTime() : 0
    return ts >= recent24h
  })
  if (candidates.length === 0) return null

  // Sort by impact desc
  candidates.sort((a, b) => impactScore(b) - impactScore(a))
  const lead = candidates[0]

  // Find the matching competitor plan (current state)
  const competitorPlan = plans.find(
    (p) => p.carrier === lead.carrier && p.plan_name === lead.plan_name,
  )

  // Find our closest equivalent — same data_gb if we have one matching
  let oursPlan = null
  if (oursCarrier && competitorPlan) {
    const ourPlans = plans.filter((p) => p.carrier === oursCarrier)
    if (competitorPlan.data_gb === null) {
      oursPlan = ourPlans.find((p) => p.data_gb === null) || ourPlans[0]
    } else {
      ourPlans.sort((a, b) => {
        const da = Math.abs((a.data_gb ?? 999) - competitorPlan.data_gb)
        const db = Math.abs((b.data_gb ?? 999) - competitorPlan.data_gb)
        return da - db
      })
      oursPlan = ourPlans[0] || null
    }
  }

  return { change: lead, competitorPlan, oursPlan }
}

function computeKpis(plans, changes, oursCarrier) {
  const now = Date.now()
  const dayMs = 24 * 60 * 60 * 1000
  const weekMs = 7 * dayMs

  let changesToday = 0
  let changesYesterday = 0
  let newPlansThisWeek = 0
  let newPlansLastWeek = 0
  for (const c of changes || []) {
    const ts = c?.changed_at ? new Date(c.changed_at).getTime() : 0
    if (!ts) continue
    if (now - ts <= dayMs) changesToday++
    else if (now - ts <= 2 * dayMs) changesYesterday++
    if (c.change_type === 'new_plan') {
      if (now - ts <= weekMs) newPlansThisWeek++
      else if (now - ts <= 2 * weekMs) newPlansLastWeek++
    }
  }

  // Average prices (domestic only — we filter against carrier ids server-side via /api/plans)
  let allPrices = []
  let oursPrices = []
  for (const p of plans || []) {
    const price = Number(p?.price)
    if (!Number.isFinite(price) || price <= 0) continue
    allPrices.push(price)
    if (p.carrier === oursCarrier) oursPrices.push(price)
  }
  const avgPrice = allPrices.length
    ? Math.round(allPrices.reduce((a, b) => a + b, 0) / allPrices.length)
    : null
  const oursAvg = oursPrices.length
    ? oursPrices.reduce((a, b) => a + b, 0) / oursPrices.length
    : null

  // "Ours vs market" — % above (positive) or below (negative) the all-carrier avg
  let oursVsMarketPct = null
  if (avgPrice != null && oursAvg != null && avgPrice > 0) {
    oursVsMarketPct = Math.round(((oursAvg - avgPrice) / avgPrice) * 100)
  }

  return {
    changesToday,
    changesDelta: changesToday - changesYesterday,
    avgPrice,
    avgPriceDelta: null,  // would need historical avg — skip for now
    newPlans: newPlansThisWeek,
    newPlansDelta: newPlansThisWeek - newPlansLastWeek,
    oursVsMarketPct,
  }
}

function isoDay(ts) {
  // Get YYYY-MM-DD for a timestamp
  return new Date(ts).toISOString().slice(0, 10)
}

function buildHeatmap(changes, carrierIds) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = []
  for (let i = HEATMAP_DAYS - 1; i >= 0; i--) {
    days.push(isoDay(today.getTime() - i * 24 * 60 * 60 * 1000))
  }
  const cells = new Map()  // key="carrier|date" → count
  let maxCount = 0
  for (const c of changes || []) {
    if (!c?.carrier || !c?.changed_at) continue
    if (!carrierIds.includes(c.carrier)) continue
    const day = isoDay(new Date(c.changed_at).getTime())
    if (!days.includes(day)) continue
    const key = `${c.carrier}|${day}`
    const next = (cells.get(key) || 0) + 1
    cells.set(key, next)
    if (next > maxCount) maxCount = next
  }
  return { carriers: carrierIds, days, cells, maxCount }
}

export function useDashboardData(oursCarrier, carrierIds) {
  const [plans, setPlans] = useState([])
  const [changes, setChanges] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    Promise.all([
      api.getPlans().catch(() => []),
      api.getChanges(300).catch(() => []),
    ]).then(([planData, changeData]) => {
      if (!alive) return
      setPlans(Array.isArray(planData) ? planData : (planData?.plans || []))
      setChanges(Array.isArray(changeData) ? changeData : (changeData?.changes || []))
      setLoading(false)
    }).catch((e) => {
      if (!alive) return
      setError(e)
      setLoading(false)
    })
    return () => { alive = false }
  }, [])

  const leadChange = useMemo(() => pickLeadChange(changes, plans, oursCarrier), [changes, plans, oursCarrier])
  const kpis = useMemo(() => computeKpis(plans, changes, oursCarrier), [plans, changes, oursCarrier])
  const heatmap = useMemo(() => buildHeatmap(changes, carrierIds), [changes, carrierIds])

  const recentChanges = useMemo(() => {
    const arr = [...(changes || [])]
    arr.sort((a, b) => {
      const ta = a?.changed_at ? new Date(a.changed_at).getTime() : 0
      const tb = b?.changed_at ? new Date(b.changed_at).getTime() : 0
      return tb - ta
    })
    return arr.slice(0, 30)
  }, [changes])

  return { loading, error, plans, changes, leadChange, kpis, heatmap, recentChanges }
}
