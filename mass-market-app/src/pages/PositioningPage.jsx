import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { classifyPriority } from '../data/networkPriority'

const CARRIERS = [
  { id: 'partner', label: 'פרטנר', color: '#ec4899' },
  { id: 'pelephone', label: 'פלאפון', color: '#3b82f6' },
  { id: 'hotmobile', label: 'הוט מובייל', color: '#f97316' },
  { id: 'cellcom', label: 'סלקום', color: '#22c55e' },
  { id: 'mobile019', label: '019', color: '#a855f7' },
  { id: 'xphone', label: 'XPhone', color: '#14b8a6' },
  { id: 'wecom', label: 'We-Com', color: '#f59e0b' },
  { id: 'neptucom', label: 'Neptucom', color: '#6366f1' },
  { id: 'rami_levy', label: 'רמי לוי', color: '#e32032' },
]

const PRICE_BUCKETS = [
  { id: '0-25',   label: '₪0-25',   min: 0,   max: 25 },
  { id: '25-50',  label: '₪25-50',  min: 25,  max: 50 },
  { id: '50-80',  label: '₪50-80',  min: 50,  max: 80 },
  { id: '80-120', label: '₪80-120', min: 80,  max: 120 },
  { id: '120+',   label: '₪120+',   min: 120, max: Infinity },
]

const GB_BUCKETS = [
  { id: '0-5',     label: '0-5GB',     min: 0,   max: 5 },
  { id: '5-15',    label: '5-15GB',    min: 5,   max: 15 },
  { id: '15-100',  label: '15-100GB',  min: 15,  max: 100 },
  { id: '100+',    label: '100+GB',    min: 100, max: Infinity },
  { id: 'unlim',   label: 'ללא הגבלה', min: -1,  max: -1 },
]

const PRIORITY_BUCKETS = [
  { id: 'none',    label: 'ללא 5G' },
  { id: 'basic',   label: '5G בסיסי' },
  { id: 'max',     label: 'תעדוף מקסימלי' },
]

// classifyPriority + MAX_PRIORITY_KEYWORDS imported from data/networkPriority.js

function heatColor(v, max) {
  if (v === 0) return 'bg-gray-50 text-gray-300'
  const intensity = Math.min(1, v / Math.max(1, max))
  if (intensity > 0.75) return 'bg-emerald-500 text-white'
  if (intensity > 0.5)  return 'bg-emerald-300 text-emerald-900'
  if (intensity > 0.25) return 'bg-emerald-100 text-emerald-800'
  return 'bg-emerald-50 text-emerald-700'
}

export default function PositioningPage() {
  const navigate = useNavigate()
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [axis, setAxis] = useState('price') // 'price' | 'gb' | 'priority'
  const visibleCarrierIds = useVisibleCarriers(CARRIERS.map(c => c.id))

  useEffect(() => {
    api.getPlans()
      .then(p => setPlans(p || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const visibleCarriers = useMemo(
    () => CARRIERS.filter(c => visibleCarrierIds.includes(c.id)),
    [visibleCarrierIds]
  )

  const buckets = axis === 'price' ? PRICE_BUCKETS : axis === 'gb' ? GB_BUCKETS : PRIORITY_BUCKETS

  // matrix[carrierId][bucketId] = { count, minPrice, plans }
  const matrix = useMemo(() => {
    const m = {}
    for (const c of visibleCarriers) {
      m[c.id] = {}
      for (const b of buckets) m[c.id][b.id] = { count: 0, minPrice: Infinity, plans: [] }
    }
    for (const p of plans) {
      if (!m[p.carrier]) continue
      const price = Number(p.price)
      const gb = p.data_gb
      let bucketId = null
      if (axis === 'price') {
        for (const b of PRICE_BUCKETS) {
          if (price >= b.min && price < b.max) { bucketId = b.id; break }
        }
      } else if (axis === 'gb') {
        if (gb === null || gb === undefined) bucketId = 'unlim'
        else for (const b of GB_BUCKETS) {
          if (b.id === 'unlim') continue
          if (gb >= b.min && gb < b.max) { bucketId = b.id; break }
        }
      } else {
        bucketId = classifyPriority(p)
      }
      if (!bucketId) continue
      const cell = m[p.carrier][bucketId]
      cell.count++
      cell.plans.push(p)
      if (price > 0 && price < cell.minPrice) cell.minPrice = price
    }
    return m
  }, [plans, visibleCarriers, axis, buckets])

  const maxCount = useMemo(() => {
    let max = 0
    for (const c of visibleCarriers) {
      for (const b of buckets) max = Math.max(max, matrix[c.id][b.id].count)
    }
    return max
  }, [matrix, visibleCarriers, buckets])

  // Carrier totals
  const carrierTotals = useMemo(() => {
    const t = {}
    for (const c of visibleCarriers) {
      t[c.id] = visibleCarriers.length === 0 ? 0 :
        buckets.reduce((sum, b) => sum + matrix[c.id][b.id].count, 0)
    }
    return t
  }, [matrix, visibleCarriers, buckets])

  // Bucket totals
  const bucketTotals = useMemo(() => {
    const t = {}
    for (const b of buckets) {
      t[b.id] = visibleCarriers.reduce((sum, c) => sum + matrix[c.id][b.id].count, 0)
    }
    return t
  }, [matrix, visibleCarriers, buckets])

  const totalPlans = visibleCarriers.reduce((s, c) => s + carrierTotals[c.id], 0)

  // Find white-space cells (zero plans across all visible carriers)
  const whiteSpaces = useMemo(() => {
    const empty = []
    for (const b of buckets) {
      const carriersWithoutPlan = visibleCarriers.filter(c => matrix[c.id][b.id].count === 0)
      if (carriersWithoutPlan.length > 0 && carriersWithoutPlan.length < visibleCarriers.length) {
        empty.push({ bucket: b, carriers: carriersWithoutPlan })
      }
    }
    return empty
  }, [matrix, visibleCarriers, buckets])

  const handleCellClick = (carrierId, _bucket) => {
    navigate(`/plans?carrier=${carrierId}`)
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Page identity is owned by the Topbar — only the helper subtitle stays. */}
      <p className="text-xs text-gray-400 mb-6 text-right">
        פיזור חבילות סלולר לפי ספק וקטגוריה — אתר את ה-white space
      </p>

      {/* Axis toggle */}
      <div className="mb-6 flex items-center gap-2">
        <span className="text-xs text-moca-sub">צירים:</span>
        <button
          onClick={() => setAxis('price')}
          className={`text-xs px-3 py-1 rounded-lg transition-colors ${
            axis === 'price' ? 'bg-moca-bolt text-white' : 'bg-white border border-moca-border/50 text-moca-sub hover:bg-moca-cream'
          }`}
        >
          לפי מחיר
        </button>
        <button
          onClick={() => setAxis('gb')}
          className={`text-xs px-3 py-1 rounded-lg transition-colors ${
            axis === 'gb' ? 'bg-moca-bolt text-white' : 'bg-white border border-moca-border/50 text-moca-sub hover:bg-moca-cream'
          }`}
        >
          לפי גלישה
        </button>
        <button
          onClick={() => setAxis('priority')}
          className={`text-xs px-3 py-1 rounded-lg transition-colors ${
            axis === 'priority' ? 'bg-moca-bolt text-white' : 'bg-white border border-moca-border/50 text-moca-sub hover:bg-moca-cream'
          }`}
        >
          לפי תעדוף
        </button>
        <span className="mr-auto text-xs text-gray-400">{totalPlans} חבילות סך הכל</span>
      </div>

      {loading && <div className="flex justify-center py-20"><Spinner /></div>}

      {!loading && (
        <>
          {/* Matrix */}
          <div className="bg-white rounded-2xl border border-moca-border/40 overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-right" dir="rtl">
                <thead>
                  <tr className="bg-moca-cream/60 border-b border-moca-border/40">
                    <th className="px-3 py-2.5 text-[11px] font-semibold text-moca-sub text-right">ספק</th>
                    {buckets.map(b => (
                      <th key={b.id} className="px-2 py-2.5 text-[11px] font-semibold text-moca-sub text-center min-w-[88px]">
                        {b.label}
                      </th>
                    ))}
                    <th className="px-3 py-2.5 text-[11px] font-semibold text-moca-sub text-center min-w-[60px]">סה"כ</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleCarriers.map(c => (
                    <tr key={c.id} className="border-b border-gray-50">
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full" style={{ background: c.color }} />
                          <span className="text-[12px] font-medium text-gray-700">{c.label}</span>
                        </div>
                      </td>
                      {buckets.map(b => {
                        const cell = matrix[c.id][b.id]
                        return (
                          <td
                            key={b.id}
                            onClick={() => cell.count > 0 && handleCellClick(c.id, b)}
                            className={`px-2 py-2.5 text-center transition-all ${heatColor(cell.count, maxCount)} ${
                              cell.count > 0 ? 'cursor-pointer hover:opacity-80' : ''
                            }`}
                            title={cell.count > 0 ? `${cell.count} חבילות, מ-₪${cell.minPrice}` : 'אין חבילות'}
                          >
                            <div className="text-base font-bold">{cell.count || ''}</div>
                            {cell.count > 0 && cell.minPrice !== Infinity && (
                              <div className="text-[9px] opacity-75 mt-0.5">מ-&#8362;{cell.minPrice}</div>
                            )}
                          </td>
                        )
                      })}
                      <td className="px-3 py-2.5 text-center text-[12px] font-bold text-gray-700 bg-moca-cream/30">
                        {carrierTotals[c.id]}
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-moca-cream/40">
                    <td className="px-3 py-2.5 text-[11px] font-semibold text-moca-sub">סה"כ</td>
                    {buckets.map(b => (
                      <td key={b.id} className="px-2 py-2.5 text-center text-[12px] font-bold text-gray-700">
                        {bucketTotals[b.id]}
                      </td>
                    ))}
                    <td className="px-3 py-2.5 text-center text-[12px] font-bold text-moca-bolt">{totalPlans}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* White space insights */}
          {whiteSpaces.length > 0 && (
            <div className="mt-6 bg-amber-50 border border-amber-200 rounded-2xl p-4 text-right">
              <h3 className="text-sm font-bold text-amber-900 mb-2 flex items-center gap-2 justify-start">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span>הזדמנויות (White Space)</span>
              </h3>
              <ul className="space-y-1.5">
                {whiteSpaces.slice(0, 5).map((ws, i) => (
                  <li key={i} className="text-xs text-amber-800">
                    <strong>{ws.bucket.label}</strong> —
                    <span className="text-amber-700 mx-1">חסר אצל:</span>
                    {ws.carriers.map(c => c.label).join(', ')}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-[11px] text-gray-400 mt-4 text-right">
            לחץ על תא כדי לראות את החבילות בדשבורד · צבע ירוק כהה = ריבוי חבילות בקטגוריה
          </p>
        </>
      )}
    </div>
  )
}
