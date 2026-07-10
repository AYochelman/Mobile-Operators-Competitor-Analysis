import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { classifyPriority } from '../data/networkPriority'
import { getCarrierColor } from '../components/moca/carrierMeta'
import { getAppsForPlan } from '../data/abroadApps'
import { useLang } from '../hooks/useLanguage'

const CARRIERS = [
  { id: 'partner',   label: 'פרטנר' },
  { id: 'pelephone', label: 'פלאפון' },
  { id: 'hotmobile', label: 'הוט מובייל' },
  { id: 'cellcom',   label: 'סלקום' },
  { id: 'mobile019', label: '019' },
  { id: 'xphone',    label: 'XPhone' },
  { id: 'wecom',     label: 'We-Com' },
  { id: 'neptucom',  label: 'Neptucom' },
  { id: 'golan',     label: 'גולן טלקום' },
  { id: 'rami_levy', label: 'רמי לוי' },
]

// Roaming (חו"ל) plans exist only for these 8 carriers — XPhone + Neptucom have
// no abroad packages (mirrors the exclusion in DashboardPage's abroad carrier list).
const ABROAD_CARRIERS = CARRIERS.filter(c => c.id !== 'xphone' && c.id !== 'neptucom')

// ---- Domestic axes ----
// Half-open intervals [min, max): a price equal to max falls into the NEXT
// bucket, so maxes are the next integer label + 1 (e.g. "26-38" → max 39) to
// keep decimal prices like 38.9 inside "26-38" and avoid gaps between buckets.
const PRICE_BUCKETS = [
  { id: '0-25',  label: '₪0-25',  min: 0,   max: 26 },
  { id: '26-38', label: '₪26-38', min: 26,  max: 39 },
  { id: '39-49', label: '₪39-49', min: 39,  max: 50 },
  { id: '50-79', label: '₪50-79', min: 50,  max: 80 },
  { id: '80-99', label: '₪80-99', min: 80,  max: 100 },
  { id: '100+',  label: '₪100+',  min: 100, max: Infinity },
]

// Domestic GB scale — fine-grained in the high range where Israeli plans cluster
// (most are "unlimited-ish" high fair-use caps: 500/1000/2000/5000GB+). Same
// half-open [min, max) convention as PRICE_BUCKETS: each bucket's max equals the
// next bucket's min, so the inclusive upper label (e.g. 200 in "51-200", 5000 in
// "3001-5000") lands here and the partition has no gaps. `unlim` (min/max -1) is
// the null-data_gb sentinel, kept separate so genuinely unlimited plans still show.
const GB_BUCKETS = [
  { id: '0-50',      label: 'פחות מ-50GB', min: 0,    max: 51 },
  { id: '51-200',    label: '51-200GB',    min: 51,   max: 201 },
  { id: '201-500',   label: '201-500GB',   min: 201,  max: 501 },
  { id: '501-999',   label: '501-999GB',   min: 501,  max: 1000 },
  { id: '1000-2000', label: '1000-2000GB', min: 1000, max: 2001 },
  { id: '2001-3000', label: '2001-3000GB', min: 2001, max: 3001 },
  { id: '3001-5000', label: '3001-5000GB', min: 3001, max: 5001 },
  { id: '5000+',     label: 'מעל 5000GB',  min: 5001, max: Infinity },
  { id: 'unlim',     label: 'ללא הגבלה',   min: -1,   max: -1 },
]

const PRIORITY_BUCKETS = [
  { id: 'none',    label: 'ללא 5G' },
  { id: 'basic',   label: '5G בסיסי' },
  { id: 'max',     label: 'תעדוף מקסימלי' },
]

// ---- Roaming axes ----
// Roaming data volumes cluster lower than domestic (most packages 1-50GB), so
// the GB axis uses tighter buckets than the domestic GB_BUCKETS.
const ROAMING_GB_BUCKETS = [
  { id: '0-1',     label: 'עד 1GB',    min: 0,   max: 1 },
  { id: '1-5',     label: '1-5GB',     min: 1,   max: 5 },
  { id: '5-15',    label: '5-15GB',    min: 5,   max: 15 },
  { id: '15-50',   label: '15-50GB',   min: 15,  max: 50 },
  { id: '50+',     label: '50GB+',     min: 50,  max: Infinity },
  { id: 'unlim',   label: 'ללא הגבלה', min: -1,  max: -1 },
]

// Same day-window cuts as DashboardPage's roaming "days" filter, for consistency.
const ROAMING_DAYS_BUCKETS = [
  { id: '1-7',   label: 'עד 7 ימים',  min: 1,  max: 8 },
  { id: '8-14',  label: '8-14 ימים',  min: 8,  max: 15 },
  { id: '15-30', label: '15-30 ימים', min: 15, max: 31 },
  { id: '30+',   label: '30+ ימים',   min: 31, max: Infinity },
]

// Roaming price scale — finer high-end buckets (₪50 steps from 100 up to 350) per
// the requested layout. Half-open [min, max): a price equal to a boundary falls
// into the upper bucket (₪100 → "₪101-149", ₪350 → "מעל ₪350"), so the partition is
// contiguous with no gaps. ₪ prefixes each value (matches the domestic PRICE_BUCKETS
// and cell labels); worded endpoints mirror the GB scales ('פחות מ-' / 'מעל').
const ROAMING_PRICE_BUCKETS = [
  { id: '0-100',   label: 'פחות מ-₪100', min: 0,   max: 100 },
  { id: '100-149', label: '₪101-149',    min: 100, max: 150 },
  { id: '150-199', label: '₪150-199',    min: 150, max: 200 },
  { id: '200-249', label: '₪200-249',    min: 200, max: 250 },
  { id: '250-299', label: '₪250-299',    min: 250, max: 300 },
  { id: '300-349', label: '₪300-349',    min: 300, max: 350 },
  { id: '350+',    label: 'מעל ₪350',    min: 350, max: Infinity },
]

const DOMESTIC_AXES = [
  { id: 'price',    label: 'לפי מחיר' },
  { id: 'gb',       label: 'לפי גלישה' },
  { id: 'priority', label: 'לפי תעדוף' },
]

const ABROAD_AXES = [
  { id: 'gb',    label: 'לפי גלישה' },
  { id: 'days',  label: 'לפי ימים' },
  { id: 'price', label: 'לפי מחיר' },
]

function getBuckets(domain, axis) {
  if (domain === 'abroad') {
    if (axis === 'days')  return ROAMING_DAYS_BUCKETS
    if (axis === 'price') return ROAMING_PRICE_BUCKETS
    return ROAMING_GB_BUCKETS
  }
  if (axis === 'gb')       return GB_BUCKETS
  if (axis === 'priority') return PRIORITY_BUCKETS
  return PRICE_BUCKETS
}

// Map a single plan to a bucket id for the active axis. `buckets` carries the
// active domain's ranges, so GB/price share one classifier across domains.
function classifyPlan(p, axis, buckets) {
  if (axis === 'priority') return classifyPriority(p)
  if (axis === 'days') {
    const d = Number(p.days)
    if (!d) return null
    for (const b of buckets) if (d >= b.min && d < b.max) return b.id
    return null
  }
  if (axis === 'gb') {
    const gb = p.data_gb
    if (gb === null || gb === undefined) return 'unlim'
    for (const b of buckets) {
      if (b.id === 'unlim') continue
      if (gb >= b.min && gb < b.max) return b.id
    }
    return null
  }
  // price
  const price = Number(p.price)
  for (const b of buckets) if (price >= b.min && price < b.max) return b.id
  return null
}

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
  const { tt } = useLang()
  const navigate = useNavigate()
  const [domesticPlans, setDomesticPlans] = useState([])
  const [abroadPlans, setAbroadPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [domain, setDomain] = useState('domestic') // 'domestic' | 'abroad'
  const [axis, setAxis] = useState('price')         // axis id within the active domain
  const visibleCarrierIds = useVisibleCarriers(CARRIERS.map(c => c.id))

  useEffect(() => {
    Promise.all([
      api.getPlans().catch(() => []),
      api.getAbroadPlans().catch(() => []),
    ])
      .then(([dom, abr]) => {
        setDomesticPlans(dom || [])
        setAbroadPlans(abr || [])
      })
      .finally(() => setLoading(false))
  }, [])

  // Switching domain resets the axis to that domain's default (GB for roaming —
  // the requested view; price for domestic) so axis/bucket combos stay valid.
  const handleDomain = (d) => {
    setDomain(d)
    setAxis(d === 'abroad' ? 'gb' : 'price')
  }

  const sourcePlans = domain === 'abroad' ? abroadPlans : domesticPlans
  const axes = domain === 'abroad' ? ABROAD_AXES : DOMESTIC_AXES

  const visibleCarriers = useMemo(() => {
    const base = domain === 'abroad' ? ABROAD_CARRIERS : CARRIERS
    return base.filter(c => visibleCarrierIds.includes(c.id))
  }, [visibleCarrierIds, domain])

  const buckets = useMemo(() => getBuckets(domain, axis), [domain, axis])

  // matrix[carrierId][bucketId] = { count, minPrice, plans }
  const matrix = useMemo(() => {
    const m = {}
    for (const c of visibleCarriers) {
      m[c.id] = {}
      for (const b of buckets) m[c.id][b.id] = { count: 0, minPrice: Infinity, plans: [] }
    }
    for (const p of sourcePlans) {
      if (!m[p.carrier]) continue
      const bucketId = classifyPlan(p, axis, buckets)
      if (!bucketId || !m[p.carrier][bucketId]) continue
      const cell = m[p.carrier][bucketId]
      cell.count++
      cell.plans.push(p)
      const price = Number(p.price)
      if (price > 0 && price < cell.minPrice) cell.minPrice = price
    }
    return m
  }, [sourcePlans, visibleCarriers, axis, buckets])

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

  // Free-in-app browsing per carrier (roaming only). Same source of truth as the
  // plan cards — getAppsForPlan resolves each plan's free-app list (Cellcom 6,
  // Pelephone 12, Golan/Rami Levy parsed from extras). maxApps = how many apps
  // are supported; planCount = on how many of the carrier's roaming bundles.
  const carrierApps = useMemo(() => {
    if (domain !== 'abroad') return {}
    const m = {}
    for (const p of abroadPlans) {
      const info = getAppsForPlan(p)
      if (!info || !info.apps?.length) continue
      const cur = m[p.carrier] || { planCount: 0, maxApps: 0, names: [] }
      cur.planCount++
      if (info.apps.length > cur.maxApps) {
        cur.maxApps = info.apps.length
        cur.names = info.apps.map(a => a.name)
      }
      m[p.carrier] = cur
    }
    return m
  }, [abroadPlans, domain])

  const handleCellClick = (carrierId) => {
    const path = domain === 'abroad' ? '/roaming' : '/plans'
    navigate(`${path}?carrier=${carrierId}`)
  }

  // English labels for bucket/axis ids — translate at render only (data ids stay untouched)
  const BUCKET_LABELS_EN = {
    // domestic price
    '0-25': '₪0-25', '26-38': '₪26-38', '39-49': '₪39-49', '50-79': '₪50-79', '80-99': '₪80-99', '100+': '₪100+',
    // domestic GB
    '0-50': 'Under 50GB', '51-200': '51-200GB', '201-500': '201-500GB', '501-999': '501-999GB',
    '1000-2000': '1000-2000GB', '2001-3000': '2001-3000GB', '3001-5000': '3001-5000GB', '5000+': 'Over 5000GB',
    unlim: 'Unlimited',
    // priority
    none: 'No 5G', basic: 'Basic 5G', max: 'Max priority',
    // roaming GB
    '0-1': 'Up to 1GB', '1-5': '1-5GB', '5-15': '5-15GB', '15-50': '15-50GB', '50+': '50GB+',
    // roaming days
    '1-7': 'Up to 7 days', '8-14': '8-14 days', '15-30': '15-30 days', '30+': '30+ days',
    // roaming price
    '0-100': 'Under ₪100', '100-149': '₪101-149', '150-199': '₪150-199', '200-249': '₪200-249',
    '250-299': '₪250-299', '300-349': '₪300-349', '350+': 'Over ₪350',
  }
  const bucketLabel = (b) => tt(b.label, BUCKET_LABELS_EN[b.id] ?? b.label)

  const AXIS_LABELS_EN = { price: 'By price', gb: 'By data', priority: 'By priority', days: 'By days' }
  const axisLabel = (a) => tt(a.label, AXIS_LABELS_EN[a.id] ?? a.label)

  const DOMAIN_TABS = [
    { id: 'domestic', label: tt('חבילות בארץ', 'Domestic plans') },
    { id: 'abroad',   label: tt('חבילות חו"ל', 'Roaming plans') },
  ]

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Page identity is owned by the Topbar — only the helper subtitle stays. */}
      <p className="text-xs text-gray-400 mb-5 text-right">
        {domain === 'abroad'
          ? tt('פיזור חבילות חו"ל לפי ספק ונפח גלישה - אתר את ה-white space', 'Distribution of roaming plans by provider and data volume - find the white space')
          : tt('פיזור חבילות סלולר לפי ספק וקטגוריה - אתר את ה-white space', 'Distribution of cellular plans by provider and category - find the white space')}
      </p>

      {/* Domain tabs — בארץ / חו"ל */}
      <div className="mb-5 flex items-center gap-1 border-b border-moca-border/40">
        {DOMAIN_TABS.map(d => (
          <button
            key={d.id}
            onClick={() => handleDomain(d.id)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
              domain === d.id
                ? 'border-moca-bolt text-moca-bolt'
                : 'border-transparent text-moca-sub hover:text-moca-dark'
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      {/* Axis toggle */}
      <div className="mb-6 flex items-center gap-2">
        <span className="text-xs text-moca-sub">{tt('צירים:', 'Axes:')}</span>
        {axes.map(a => (
          <button
            key={a.id}
            onClick={() => setAxis(a.id)}
            className={`text-xs px-3 py-1 rounded-lg transition-colors ${
              axis === a.id ? 'bg-moca-bolt text-white' : 'bg-white border border-moca-border/50 text-moca-sub hover:bg-moca-cream'
            }`}
          >
            {axisLabel(a)}
          </button>
        ))}
        <span className="mr-auto text-xs text-gray-400">{totalPlans} {tt('חבילות סך הכל', 'plans total')}</span>
      </div>

      {loading && <div className="flex justify-center py-20"><Spinner /></div>}

      {!loading && (
        <>
          {/* Matrix */}
          <div className="bg-white rounded-2xl border border-moca-border/40 overflow-hidden shadow-card">
            <div className="overflow-x-auto">
              <table className="w-full text-right" dir="rtl">
                <thead>
                  <tr className="bg-moca-cream/60 border-b border-moca-border/40">
                    <th className="px-3 py-2.5 text-[11px] font-semibold text-moca-sub text-right sticky right-0 bg-moca-cream/95 backdrop-blur-sm z-10 md:static md:bg-transparent">{tt('ספק', 'Provider')}</th>
                    {buckets.map(b => (
                      <th key={b.id} className="px-2 py-2.5 text-[11px] font-semibold text-moca-sub text-center min-w-[88px]">
                        {bucketLabel(b)}
                      </th>
                    ))}
                    <th className="px-3 py-2.5 text-[11px] font-semibold text-moca-sub text-center min-w-[60px]">{tt('סה"כ', 'Total')}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleCarriers.map(c => (
                    <tr key={c.id} className="border-b border-gray-50">
                      <td className="px-3 py-2.5 sticky right-0 bg-white z-10 md:static md:bg-transparent shadow-[-4px_0_8px_-4px_rgba(0,0,0,0.06)] md:shadow-none">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full" style={{ background: getCarrierColor(c.id) }} />
                          <span className="text-[12px] font-medium text-gray-700">{c.label}</span>
                          {domain === 'abroad' && carrierApps[c.id] && (
                            <span
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-moca-cream border border-moca-sand text-moca-bolt text-[10px] font-bold leading-none whitespace-nowrap"
                              title={tt(`גלישה חופשית ב-${carrierApps[c.id].maxApps} אפליקציות · ${carrierApps[c.id].planCount} מסלולי חו"ל\n${carrierApps[c.id].names.join(' · ')}`, `Free browsing in ${carrierApps[c.id].maxApps} apps · ${carrierApps[c.id].planCount} roaming plans\n${carrierApps[c.id].names.join(' · ')}`)}
                            >
                              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" />
                                <rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" />
                              </svg>
                              {carrierApps[c.id].maxApps}
                            </span>
                          )}
                        </div>
                      </td>
                      {buckets.map(b => {
                        const cell = matrix[c.id][b.id]
                        return (
                          <td
                            key={b.id}
                            onClick={() => cell.count > 0 && handleCellClick(c.id)}
                            className={`px-2 py-2.5 text-center transition-all ${heatColor(cell.count, maxCount)} ${
                              cell.count > 0 ? 'cursor-pointer hover:opacity-80' : ''
                            }`}
                            title={cell.count > 0 ? tt(`${cell.count} חבילות, מ-₪${cell.minPrice}`, `${cell.count} plans, from ₪${cell.minPrice}`) : tt('אין חבילות', 'No plans')}
                          >
                            <div className="text-base font-bold">{cell.count || ''}</div>
                            {cell.count > 0 && cell.minPrice !== Infinity && (
                              <div className="text-[9px] opacity-75 mt-0.5">{tt('מ-', 'from ')}&#8362;{cell.minPrice}</div>
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
                    <td className="px-3 py-2.5 text-[11px] font-semibold text-moca-sub sticky right-0 bg-moca-cream/95 backdrop-blur-sm z-10 md:static md:bg-transparent">{tt('סה"כ', 'Total')}</td>
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
                <span>{tt('הזדמנויות (White Space)', 'Opportunities (White Space)')}</span>
              </h3>
              <ul className="space-y-1.5">
                {whiteSpaces.slice(0, 5).map((ws, i) => (
                  <li key={i} className="text-xs text-amber-800">
                    <strong>{bucketLabel(ws.bucket)}</strong> -
                    <span className="text-amber-700 mx-1">{tt('חסר אצל:', 'Missing from:')}</span>
                    {ws.carriers.map(c => c.label).join(', ')}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-[11px] text-gray-400 mt-4 text-right">
            {tt('לחץ על תא כדי לראות את החבילות בדשבורד · צבע ירוק כהה = ריבוי חבילות בקטגוריה', 'Click a cell to see the plans in the dashboard · dark green = many plans in the category')}
            {domain === 'abroad' && tt(' · התג ▦ ליד שם הספק = גלישה חופשית באפליקציות (המספר = כמה אפליקציות)', ' · the ▦ tag next to a provider = free in-app browsing (the number = how many apps)')}
          </p>
        </>
      )}
    </div>
  )
}
