import { useState, useEffect, memo } from 'react'
import { api } from '../lib/api'
import Badge from './ui/Badge'
import { ALL_CARRIER_LABELS as CARRIER_LABELS } from '../data/carrierLabels'

const CARRIER_COLORS = {
  // domestic
  partner: 'pink', pelephone: 'blue', hotmobile: 'orange', cellcom: 'green',
  mobile019: 'purple', xphone: 'orange', wecom: 'amber', neptucom: 'purple',
  // global — warm palette so widget looks consistent across tabs
  tuki: 'amber', globalesim: 'orange', airalo: 'orange', pelephone_global: 'orange',
  esimo: 'amber', simtlv: 'pink', world8: 'amber', xphone_global: 'orange',
  saily: 'pink', holafly: 'orange', esimio: 'orange', sparks: 'amber',
  voye: 'pink', orbit: 'amber', travelsim: 'amber',
}

const TAB_TITLE = { domestic: 'חבילות סלולר', abroad: 'חבילות חו"ל', global: 'חבילות גלובלי' }

function formatPrice(p) {
  return `₪${Number(p).toFixed(Number(p) % 1 === 0 ? 0 : 2)}`
}

const MoverCard = memo(function MoverCard({ mover, onClick, isAllowedCarrier }) {
  const drop = mover.pct_change < 0
  const pctLabel = `${drop ? '' : '+'}${mover.pct_change}%`
  const label = CARRIER_LABELS[mover.carrier] || mover.carrier
  const accentBg   = drop ? 'bg-emerald-500' : 'bg-red-500'
  const priceClr   = drop ? 'text-emerald-700' : 'text-red-700'
  const badgeClr   = drop
    ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-200'
    : 'bg-red-600 text-white shadow-sm shadow-red-200'
  return (
    <button
      onClick={() => onClick?.(mover)}
      disabled={!isAllowedCarrier}
      className={`relative flex-shrink-0 w-[215px] bg-white border border-gray-200 rounded-2xl shadow p-3.5 pr-5 text-right overflow-hidden hover-lift outline-none focus:outline-none
        ${!isAllowedCarrier
          ? 'opacity-40 cursor-not-allowed'
          : 'cursor-pointer'}`}
      title={mover.plan_name}
    >
      {/* Side accent stripe */}
      <span className={`absolute inset-y-0 right-0 w-1.5 ${accentBg}`} />

      <div className="flex items-center justify-between mb-2">
        <span className={`inline-flex items-center gap-0.5 text-[11px] font-bold px-2 py-0.5 rounded-full ${badgeClr}`}>
          <span className="text-xs">{drop ? '↓' : '↑'}</span>
          {pctLabel}
        </span>
      </div>

      <div className="mb-1">
        <Badge color={CARRIER_COLORS[mover.carrier] || 'gray'}>{label}</Badge>
      </div>
      <p className="text-[13px] font-semibold text-gray-800 truncate leading-tight mt-1">{mover.plan_name}</p>

      <div className="mt-2.5 pt-2 border-t border-gray-200 flex items-baseline gap-2 justify-end" dir="ltr">
        <span className="text-[11px] text-gray-400 line-through decoration-2">{formatPrice(mover.old_price)}</span>
        <span className={`text-xl font-extrabold ${priceClr}`}>{formatPrice(mover.new_price)}</span>
      </div>
    </button>
  )
})

export default function MarketMoversWidget({ onMoverClick, visibleCarriers, tab = 'domestic' }) {
  const [movers, setMovers] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setMovers([])
    setErr(null)
    api.getMarketMovers(30, 5, [tab])
      .then(res => { if (!cancelled) setMovers(res?.movers || []) })
      .catch(e => !cancelled && setErr(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [tab])

  if (loading || err || movers.length === 0) return null

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-moca-bolt">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
            <polyline points="17 6 23 6 23 12"/>
          </svg>
          <h2 className="text-sm font-semibold text-gray-800">שינויי מחיר משמעותיים ב{TAB_TITLE[tab] || 'חבילות סלולר'}</h2>
        </div>
        <span className="text-[11px] text-gray-400">30 ימים אחרונים</span>
      </div>
      <div className="relative">
        <div
          className="flex gap-3 overflow-x-auto -mx-1 px-1 [&::-webkit-scrollbar]:hidden snap-x snap-mandatory scroll-px-1"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {movers.map((m, i) => (
            <div key={`${m.carrier}-${m.plan_name}-${i}`} className="snap-start shrink-0">
              <MoverCard
                mover={m}
                onClick={onMoverClick}
                visibleCarriers={visibleCarriers}
                isAllowedCarrier={!visibleCarriers || visibleCarriers.length === 0 || visibleCarriers.includes(m.carrier)}
              />
            </div>
          ))}
        </div>
        {/* Edge fade cue — RTL: physical left edge hints there's more to scroll to */}
        <div
          aria-hidden="true"
          className="md:hidden pointer-events-none absolute top-0 bottom-0 left-0 w-10"
          style={{ background: 'linear-gradient(to left, transparent, var(--color-moca-bg) 90%)' }}
        />
      </div>
    </div>
  )
}
