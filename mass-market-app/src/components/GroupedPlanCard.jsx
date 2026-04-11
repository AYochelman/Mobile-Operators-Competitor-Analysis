import { useState } from 'react'
import Badge from './ui/Badge'
import CountryModal from './CountryModal'
import { getCountriesForPlan } from '../data/globalCountries'

const CARRIER_LOGOS = {
  tuki:            '/logos/tuki.png',
  globalesim:      '/logos/globalesim.png',
  airalo:          '/logos/airalo.png',
  pelephone_global:'/logos/pelephone_global.png',
  esimo:           '/logos/esimo.png',
  simtlv:          '/logos/simtlv.png',
  world8:          '/logos/world8.png',
  xphone_global:   '/logos/xphone_global.png',
  saily:           '/logos/saily.png',
  holafly:         '/logos/holafly.png',
  esimio:          '/logos/esimio.png',
  sparks:          '/logos/sparks.png',
  voye:            '/logos/voye.png',
  orbit:           '/logos/orbit.png',
}

const GLOBAL_LABELS = {
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo',
  pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV',
  world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily',
  holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks', voye: 'VOYE',
  orbit: 'Orbit',
}
const GLOBAL_COLORS = {
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'blue',
  esimo: 'purple', simtlv: 'red', world8: 'teal', xphone_global: 'teal',
  saily: 'purple', holafly: 'orange', esimio: 'blue', sparks: 'amber', voye: 'pink',
  orbit: 'indigo',
}

function formatGB(gb) {
  if (gb === null || gb === undefined) return 'ללא הגבלה'
  if (gb < 1) return `${Math.round(gb * 1024)}MB`
  return `${gb}GB`
}

function formatDays(days) {
  if (!days) return null
  if (days >= 365) return `${(days / 365).toFixed(days % 365 === 0 ? 0 : 1)} שנים`
  if (days > 60) return `${Math.round(days / 30)} חודשים`
  return `${days} ימים`
}

export default function GroupedPlanCard({ carrier, destination, plans }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [showCountries, setShowCountries] = useState(false)

  const selectedPlan = plans[selectedIndex]
  const label = GLOBAL_LABELS[carrier] || carrier
  const badgeColor = GLOBAL_COLORS[carrier] || 'gray'
  const countryData = getCountriesForPlan(selectedPlan)

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm relative text-right hover-lift animate-fade-in-up">
      {/* Carrier logo — top-left, no background */}
      {CARRIER_LOGOS[carrier] && (
        <img
          src={CARRIER_LOGOS[carrier]}
          alt={label}
          className="absolute top-3 left-3 w-8 h-8 object-contain"
        />
      )}

      {/* Carrier badges */}
      <div className="flex items-center gap-1.5 justify-end mb-2">
        {selectedPlan.esim && <Badge color="green">eSIM</Badge>}
        <Badge color={badgeColor}>{label}</Badge>
      </div>

      {/* Destination title */}
      <h3 className="text-[15px] font-bold text-gray-800 mb-3">
        <bdi>{destination}</bdi>
      </h3>

      {/* GB selector pills */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {plans.map((plan, idx) => (
          <button
            key={idx}
            onClick={() => setSelectedIndex(idx)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all duration-150 ${
              selectedIndex === idx
                ? 'bg-moca-bolt text-white shadow-sm'
                : 'bg-moca-cream text-moca-sub hover:bg-moca-sand hover:text-moca-text'
            }`}
          >
            {formatGB(plan.data_gb)}
          </button>
        ))}
      </div>

      {/* Price */}
      <div className="mb-2">
        <span className="text-3xl font-bold text-gray-900 tracking-tight">
          ₪{selectedPlan.price}
        </span>
        {selectedPlan.original_price && selectedPlan.currency && selectedPlan.currency !== 'ILS' && (
          <div className="text-[11px] text-gray-400 mt-0.5" dir="ltr">
            {selectedPlan.currency} ${selectedPlan.original_price}
          </div>
        )}
      </div>

      {/* Info line */}
      <p className="text-sm text-gray-500 mb-3">
        <bdi>{formatGB(selectedPlan.data_gb)}</bdi>
        <span className="mx-1.5 text-gray-300">·</span>
        <bdi>{formatDays(selectedPlan.days)}</bdi>
      </p>

      {/* Country modal link */}
      {countryData && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <button
            onClick={() => setShowCountries(true)}
            className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
          >
            מדינות ({countryData.countries.length}) &larr;
          </button>
        </div>
      )}

      {/* Country modal */}
      {countryData && (
        <CountryModal
          open={showCountries}
          onClose={() => setShowCountries(false)}
          title={countryData.title}
          countries={countryData.countries}
        />
      )}
    </div>
  )
}
