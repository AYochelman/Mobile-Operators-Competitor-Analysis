import { useState, useEffect, useRef } from 'react'
import { api } from '../lib/api'

const _cache = new Map()
const _pending = new Set()

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
  const [path, setPath] = useState(() => _cache.has(key) ? _cache.get(key) : undefined)
  const ref = useRef(null)

  useEffect(() => {
    if (!carrier || !planName || path !== undefined) return
    if (_cache.has(key)) { setPath(_cache.get(key)); return }
    if (_pending.has(key)) return

    let obs
    const doFetch = () => {
      _pending.add(key)
      api.getHistoryPriceSeries(carrier, planType, planName, '')
        .then(res => {
          const series = res?.series || []
          const match = series.find(s => s.plan_name === planName) || series[0]
          const pts = match?.points || []
          const result = pts.length >= 2 ? buildPath(pts, w, h) : null
          _cache.set(key, result)
          setPath(result)
        })
        .catch(() => { _cache.set(key, null); setPath(null) })
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
    return () => obs?.disconnect()
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
