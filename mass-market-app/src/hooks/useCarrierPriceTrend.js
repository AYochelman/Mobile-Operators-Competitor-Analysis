import { useEffect, useState } from 'react'
import { api } from '../lib/api'

/**
 * Aggregate price-history sparkline series for a single carrier.
 *
 * Hits /api/history/price-series with no plan_name filter, then averages
 * each day's prices across all of the carrier's plans into a single series.
 *
 * Returns:
 *   undefined — still loading (initial)
 *   null      — fetch failed or no usable data
 *   number[]  — daily averages, ascending by date
 *
 * Module-level cache (5-minute TTL) means the dashboard's CompetitorBoard
 * only fires one request per carrier even when re-rendered repeatedly.
 */

const _cache = new Map() // key → { points: number[] | null, ts: number }
const _pending = new Map() // key → Promise — coalesce concurrent calls
const TTL_MS = 5 * 60 * 1000

function aggregateSeries(series) {
  if (!Array.isArray(series) || series.length === 0) return null
  const dateMap = new Map()
  for (const s of series) {
    for (const p of s.points || []) {
      if (!p?.date) continue
      const price = Number(p.price)
      if (!Number.isFinite(price) || price <= 0) continue
      const arr = dateMap.get(p.date) || []
      arr.push(price)
      dateMap.set(p.date, arr)
    }
  }
  if (dateMap.size < 2) return null // need at least 2 distinct days
  const sortedDates = Array.from(dateMap.keys()).sort()
  return sortedDates.map((d) => {
    const prices = dateMap.get(d)
    return prices.reduce((a, b) => a + b, 0) / prices.length
  })
}

function fetchTrend(carrier, planType) {
  const key = `${carrier}|${planType}`
  if (_pending.has(key)) return _pending.get(key)

  const promise = api
    .getHistoryPriceSeries(carrier, planType, '', '')
    .then((res) => aggregateSeries(res?.series))
    .catch(() => null)
    .then((points) => {
      _cache.set(key, { points, ts: Date.now() })
      _pending.delete(key)
      return points
    })

  _pending.set(key, promise)
  return promise
}

export function useCarrierPriceTrend(carrier, planType = 'domestic') {
  const key = carrier ? `${carrier}|${planType}` : null
  const [data, setData] = useState(() => {
    if (!key) return undefined
    const cached = _cache.get(key)
    if (cached && Date.now() - cached.ts < TTL_MS) return cached.points
    return undefined
  })

  useEffect(() => {
    if (!carrier) return
    const cached = _cache.get(key)
    if (cached && Date.now() - cached.ts < TTL_MS) {
      setData(cached.points)
      return
    }
    let alive = true
    fetchTrend(carrier, planType).then((points) => {
      if (alive) setData(points)
    })
    return () => { alive = false }
  }, [carrier, planType, key])

  return data
}
