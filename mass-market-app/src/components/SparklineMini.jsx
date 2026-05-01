import { useState, useEffect, useRef } from 'react'
import { api } from '../lib/api'

// Bounded LRU cache with TTL. Without bounds, scrolling through 5,000 plans
// during a long session leaves 5,000 entries pinned forever and the prices
// shown won't update for stale items either.
const CACHE_MAX = 500
const CACHE_TTL_MS = 5 * 60 * 1000  // 5 minutes
const _cache = new Map()  // key -> { value, ts }
const _pending = new Set()

function cacheGet(key) {
  const e = _cache.get(key)
  if (!e) return undefined
  if (Date.now() - e.ts > CACHE_TTL_MS) {
    _cache.delete(key)
    return undefined
  }
  // Touch — move to end so it's the freshest entry in insertion order.
  _cache.delete(key)
  _cache.set(key, e)
  return e.value
}

function cacheSet(key, value) {
  if (_cache.has(key)) _cache.delete(key)
  _cache.set(key, { value, ts: Date.now() })
  while (_cache.size > CACHE_MAX) {
    // Evict oldest (Map preserves insertion order).
    const oldest = _cache.keys().next().value
    if (oldest === undefined) break
    _cache.delete(oldest)
  }
}

function cacheHas(key) {
  return cacheGet(key) !== undefined
}

const MIN_TREND_PCT = 5  // hide sparkline when overall change is below this %

function buildPath(points, w, h, pad = 3) {
  const prices = points.map(p => p.price)
  const first = prices[0]
  const last = prices[prices.length - 1]
  if (!first || first <= 0) return null
  const pct = ((last - first) / first) * 100
  if (Math.abs(pct) < MIN_TREND_PCT) return null
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1
  const n = points.length
  const xs = points.map((_, i) => pad + (i / (n - 1)) * (w - 2 * pad))
  const ys = points.map(p => h - pad - ((p.price - min) / range) * (h - 2 * pad))
  const d = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(' ')
  return { d, trend: last < first - 0.01 ? 'down' : last > first + 0.01 ? 'up' : 'flat' }
}

export default function SparklineMini({ carrier, planName, planType, w = 68, h = 22 }) {
  const key = `${carrier}|${planType}|${planName}`
  const [path, setPath] = useState(() => cacheHas(key) ? cacheGet(key) : undefined)
  const ref = useRef(null)

  useEffect(() => {
    if (!carrier || !planName || path !== undefined) return
    if (cacheHas(key)) { setPath(cacheGet(key)); return }
    if (_pending.has(key)) return

    let obs
    let cancelled = false
    const doFetch = () => {
      _pending.add(key)
      api.getHistoryPriceSeries(carrier, planType, planName, '')
        .then(res => {
          const series = res?.series || []
          const match = series.find(s => s.plan_name === planName) || series[0]
          const pts = match?.points || []
          const result = pts.length >= 2 ? buildPath(pts, w, h) : null
          cacheSet(key, result)
          if (!cancelled) setPath(result)
        })
        .catch(() => { cacheSet(key, null); if (!cancelled) setPath(null) })
        .finally(() => _pending.delete(key))
    }

    if ('IntersectionObserver' in window) {
      obs = new IntersectionObserver(([e]) => {
        if (!e.isIntersecting) return
        obs.disconnect()
        doFetch()
      }, { threshold: 0.1, rootMargin: '80px' })
      if (ref.current) obs.observe(ref.current)
    } else {
      doFetch()
    }
    return () => {
      cancelled = true
      obs?.disconnect()
    }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  const stroke = path?.trend === 'down' ? '#10b981' : path?.trend === 'up' ? '#f87171' : '#d1d5db'

  return (
    <div ref={ref} style={{ width: w, height: path ? h : 4, transition: 'height 0.15s' }}>
      {path && (
        <svg width={w} height={h} className="overflow-visible">
          <path d={path.d} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  )
}
