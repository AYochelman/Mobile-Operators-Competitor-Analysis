import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import Badge from './ui/Badge'

const CARRIER_LABELS = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום',
  mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', neptucom: 'Neptucom',
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM',
  esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global',
  saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks',
  voye: 'VOYE', orbit: 'Orbit', travelsim: 'TravelSim',
}

const CARRIER_COLORS = {
  partner: 'pink', pelephone: 'blue', hotmobile: 'orange', cellcom: 'green',
  mobile019: 'purple', xphone: 'teal', wecom: 'amber', neptucom: 'indigo',
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'blue',
  esimo: 'purple', simtlv: 'red', world8: 'teal', xphone_global: 'teal',
  saily: 'purple', holafly: 'orange', esimio: 'blue', sparks: 'amber',
  voye: 'pink', orbit: 'indigo', travelsim: 'teal',
}

const TYPE_LABEL = { domestic: 'סלולר', abroad: 'חו"ל', global: 'גלובלי' }
const TYPE_BADGE_COLOR = { domestic: 'blue', abroad: 'amber', global: 'purple' }

function formatPrice(p) {
  return `₪${Number(p).toFixed(Number(p) % 1 === 0 ? 0 : 2)}`
}

function MoverCard({ mover, onClick, isAllowedCarrier }) {
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
      className={`relative flex-shrink-0 w-[215px] bg-white border border-gray-200 rounded-2xl shadow p-3.5 pr-5 text-right overflow-hidden hover-lift
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
        <Badge color={TYPE_BADGE_COLOR[mover.plan_type] || 'gray'}>
          {TYPE_LABEL[mover.plan_type] || mover.plan_type}
        </Badge>
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
}

export default function MarketMoversWidget({ onMoverClick, visibleCarriers }) {
  const [movers, setMovers] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.getMarketMovers(7, 5)
      .then(res => { if (!cancelled) setMovers(res?.movers || []) })
      .catch(e => !cancelled && setErr(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  if (loading || err || movers.length === 0) return null

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-moca-bolt">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
            <polyline points="17 6 23 6 23 12"/>
          </svg>
          <h2 className="text-sm font-semibold text-gray-800">שינויי המחיר המשמעותיים השבוע</h2>
        </div>
        <span className="text-[11px] text-gray-400">7 ימים אחרונים</span>
      </div>
      <div
        className="flex gap-3 overflow-x-auto -mx-1 px-1 [&::-webkit-scrollbar]:hidden"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {movers.map((m, i) => (
          <MoverCard
            key={`${m.carrier}-${m.plan_name}-${i}`}
            mover={m}
            onClick={onMoverClick}
            visibleCarriers={visibleCarriers}
            isAllowedCarrier={!visibleCarriers || visibleCarriers.length === 0 || visibleCarriers.includes(m.carrier)}
          />
        ))}
      </div>
    </div>
  )
}
