import { useState } from 'react'
import Badge from './ui/Badge'
import CountryModal from './CountryModal'
import { getCountriesForPlan } from '../data/globalCountries'
import { getCountriesForAbroadPlan } from '../data/abroadCountries'
import { getAppsForAbroadPlan } from '../data/abroadApps'
import AppsModal from './AppsModal'

const CARRIER_COLORS = {
  partner: 'pink', pelephone: 'blue', hotmobile: 'orange', cellcom: 'green',
  mobile019: 'purple', xphone: 'teal', wecom: 'amber',
}
const CARRIER_LABELS = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום',
  mobile019: '019', xphone: 'XPhone', wecom: 'We-Com',
}
const GLOBAL_LABELS = {
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo',
  pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV',
  world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily',
  holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks',
}
const GLOBAL_COLORS = {
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'blue',
  esimo: 'purple', simtlv: 'red', world8: 'teal', xphone_global: 'teal',
  saily: 'purple', holafly: 'orange', esimio: 'blue', sparks: 'amber',
}

const CHANGE_DOT = {
  new_plan: 'bg-emerald-400',
  price_change: 'bg-amber-400',
  removed_plan: 'bg-red-400',
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

export default function PlanCard({ plan, type = 'domestic', changeType }) {
  const [showCountries, setShowCountries] = useState(false)
  const [showApps, setShowApps] = useState(false)
  const [showAllExtras, setShowAllExtras] = useState(false)
  const isGlobal = type === 'global'
  const isAbroad = type === 'abroad'
  const isContent = type === 'content'
  const countryData = isGlobal ? getCountriesForPlan(plan) : isAbroad ? getCountriesForAbroadPlan(plan) : null
  const appsData = isAbroad ? getAppsForAbroadPlan(plan) : null
  const carrier = plan.carrier
  const label = isGlobal ? (GLOBAL_LABELS[carrier] || carrier) : (CARRIER_LABELS[carrier] || carrier)
  const badgeColor = isGlobal ? (GLOBAL_COLORS[carrier] || 'gray') : (CARRIER_COLORS[carrier] || 'gray')

  // Build info line: data + period, dot-separated
  const infoParts = []
  if (!isContent) infoParts.push(formatGB(plan.data_gb))
  if ((isAbroad || isGlobal) && plan.days) infoParts.push(formatDays(plan.days))
  if (plan.minutes) infoParts.push(`${plan.minutes} דקות`)
  if (plan.sms) infoParts.push(`${plan.sms} SMS`)

  // Extras — filter out app-related text if we have an apps link
  const extras = plan.extras ? plan.extras.filter(e => !(appsData && /אפליקציות/.test(e))) : []
  const visibleExtras = extras
  const hiddenCount = 0

  const hasRoaming = !isGlobal && !isAbroad && !isContent && plan.extras && plan.extras.some(e => /חו"ל|חו״ל/.test(e) && /\d+\s*GB|גלישה/i.test(e))

  return (
    <div className="bg-white rounded-2xl p-5 hover:shadow-md transition-all duration-200 shadow-sm relative group text-right">
      {/* Change indicator dot */}
      {changeType && CHANGE_DOT[changeType] && (
        <span
          className={`absolute top-4 left-4 w-2 h-2 rounded-full ${CHANGE_DOT[changeType]}`}
          title={changeType === 'new_plan' ? 'חדש' : changeType === 'price_change' ? 'שינוי מחיר' : 'הוסרה'}
        />
      )}

      {/* Carrier badge — top right */}
      <div className="flex items-center gap-1.5 mb-3">
        <Badge color={badgeColor}>{label}</Badge>
        {isGlobal && plan.esim && <Badge color="green">eSIM</Badge>}
        {hasRoaming && <Badge color="blue">חו״ל</Badge>}
      </div>

      {/* Plan name */}
      {!isContent && (
        <h3 className="text-[13px] font-semibold text-gray-800 mb-3 leading-relaxed">{
          (plan.plan_name || '').split(' – ').map((part, i) => (
            <span key={i}>{i > 0 && <span className="text-gray-300"> - </span>}<bdi>{part}</bdi></span>
          ))
        }</h3>
      )}

      {/* Price */}
      <div className="mb-3">
        <div className="text-3xl font-bold text-gray-900 tracking-tight">{String(plan.price).startsWith('₪') ? plan.price : `₪${plan.price}`}</div>
        {isGlobal && plan.original_price && plan.currency && plan.currency !== 'ILS' && (
          <div className="text-[11px] text-gray-400 mt-0.5" dir="ltr">{plan.currency} ${plan.original_price}</div>
        )}
      </div>

      {/* Info line — dot separated */}
      {infoParts.length > 0 && (
        <p className="text-sm text-gray-500 mb-3">
          {infoParts.map((part, i) => (
            <span key={i}>{i > 0 && <span className="mx-1.5 text-gray-300">·</span>}<bdi>{part}</bdi></span>
          ))}
        </p>
      )}

      {/* Content-specific fields */}
      {isContent && plan.free_trial && !['ללא תקופת חינם', '—', ''].includes(plan.free_trial) && (
        <p className="text-xs text-gray-500 mb-2">🎁 {plan.free_trial}</p>
      )}
      {isContent && plan.note && (
        <p className="text-[11px] text-gray-400 mb-2">{plan.note}</p>
      )}

      {/* Extras */}
      {extras.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-1">
          {visibleExtras.map((extra, i) => (
            <div key={i} className="text-[11px] text-gray-400 flex items-start gap-1.5">
              <span className="text-gray-300 mt-px shrink-0">&#10022;</span>
              <span>{extra}</span>
            </div>
          ))}
          {hiddenCount > 0 && !showAllExtras && (
            <button
              onClick={() => setShowAllExtras(true)}
              className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
            >
              +{hiddenCount} נוספים
            </button>
          )}
        </div>
      )}

      {/* Country / Apps links */}
      {(countryData || appsData) && (
        <div className="mt-3 pt-2 border-t border-gray-50 flex items-center gap-3">
          {countryData && (
            <button
              onClick={() => setShowCountries(true)}
              className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
            >
              מדינות ({countryData.countries.length}) &larr;
            </button>
          )}
          {appsData && (
            <button
              onClick={() => setShowApps(true)}
              className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
            >
              אפליקציות &larr;
            </button>
          )}
        </div>
      )}

      {/* Modals */}
      {countryData && (
        <CountryModal
          open={showCountries}
          onClose={() => setShowCountries(false)}
          title={countryData.title}
          countries={countryData.countries}
        />
      )}
      {appsData && (
        <AppsModal
          open={showApps}
          onClose={() => setShowApps(false)}
          title={appsData.title}
          apps={appsData.apps}
        />
      )}
    </div>
  )
}
