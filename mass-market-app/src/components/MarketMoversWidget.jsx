import { useState, useEffect } from 'react'
import { api } from '../lib/api'

const CARRIER_LABELS = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום',
  mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', neptucom: 'Neptucom',
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM',
  esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global',
  saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks',
  voye: 'VOYE', orbit: 'Orbit', travelsim: 'TravelSim',
}

const TYPE_LABEL = { domestic: 'סלולר', abroad: 'חו"ל', global: 'גלובלי' }

function formatPrice(p) {
  return `₪${Number(p).toFixed(Number(p) % 1 === 0 ? 0 : 2)}`
}

function MoverCard({ mover, onClick, visibleCarriers, isAllowedCarrier }) {
  const drop = mover.pct_change < 0
  const pctLabel = `${drop ? '' : '+'}${mover.pct_change}%`
  const label = CARRIER_LABELS[mover.carrier] || mover.carrier
  return (
    <button
      onClick={() => onClick?.(mover)}
      disabled={!isAllowedCarrier}
      className={`relative flex-shrink-0 w-[200px] bg-white border border-moca-border/60 rounded-xl p-3 text-right hover:border-moca-bolt/40 hover:shadow-sm transition-all ${!isAllowedCarrier ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
      title={mover.plan_name}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
          drop ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
        }`}>
          {drop ? '↓' : '↑'} {pctLabel}
        </span>
        <span className="text-[10px] text-gray-400">{TYPE_LABEL[mover.plan_type] || mover.plan_type}</span>
      </div>
      <p className="text-xs font-semibold text-gray-800 truncate mb-1">{label}</p>
      <p className="text-[11px] text-gray-500 truncate leading-tight">{mover.plan_name}</p>
      <div className="mt-2 flex items-baseline gap-2 justify-end" dir="ltr">
        <span className="text-[11px] text-gray-400 line-through">{formatPrice(mover.old_price)}</span>
        <span className={`text-sm font-bold ${drop ? 'text-emerald-600' : 'text-red-600'}`}>{formatPrice(mover.new_price)}</span>
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
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1" style={{ scrollbarWidth: 'thin' }}>
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
