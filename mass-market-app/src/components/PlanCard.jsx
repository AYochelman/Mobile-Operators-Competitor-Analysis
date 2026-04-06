import Badge from './ui/Badge'

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
  holafly: 'Holafly', esimio: 'eSIM.io',
}
const GLOBAL_COLORS = {
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'blue',
  esimo: 'purple', simtlv: 'red', world8: 'teal', xphone_global: 'teal',
  saily: 'purple', holafly: 'orange', esimio: 'blue',
}

function formatGB(gb) {
  if (gb === null || gb === undefined) return 'ללא הגבלה'
  if (gb < 1) return `${Math.round(gb * 1024)}MB`
  return `${gb}GB`
}

export default function PlanCard({ plan, type = 'domestic', changeType, onCountryClick }) {
  const isGlobal = type === 'global'
  const isAbroad = type === 'abroad'
  const isContent = type === 'content'
  const carrier = plan.carrier
  const label = isGlobal ? (GLOBAL_LABELS[carrier] || carrier) : (CARRIER_LABELS[carrier] || carrier)
  const badgeColor = isGlobal ? (GLOBAL_COLORS[carrier] || 'gray') : (CARRIER_COLORS[carrier] || 'gray')

  const changeBadge = changeType === 'new_plan' ? { text: 'חדש', color: 'green' }
    : changeType === 'price_change' ? { text: 'שינוי מחיר', color: 'orange' }
    : changeType === 'removed_plan' ? { text: 'הוסרה', color: 'red' }
    : null

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow relative">
      {changeBadge && (
        <Badge color={changeBadge.color} className="absolute top-3 left-3">{changeBadge.text}</Badge>
      )}

      {/* Plan name (hidden for content — service name shown in section header) */}
      {!isContent && <h3 className="text-sm font-bold text-blue-600 mb-2 leading-snug">{plan.plan_name}</h3>}

      {/* Carrier badge */}
      <Badge color={badgeColor} className="mb-3">{label}</Badge>
      {isGlobal && plan.esim && <Badge color="green" className="mb-3 mr-1">eSIM</Badge>}

      {/* Price */}
      <div className="mb-3">
        <span className="text-2xl font-bold text-gray-900">{String(plan.price).startsWith('₪') ? plan.price : `₪${plan.price}`}</span>
        {!isGlobal && !isContent && <span className="text-xs text-gray-500 mr-1">לחודש</span>}
        {isContent && <span className="text-xs text-gray-500 mr-1">לחודש</span>}
        {isGlobal && plan.original_price && (
          <div className="text-xs text-gray-400 mt-0.5">${plan.original_price} {plan.currency}</div>
        )}
      </div>

      {/* Details */}
      <div className="space-y-1 text-sm text-gray-600">
        {!isContent && (
          <div className="flex justify-between">
            <span>גלישה</span>
            <span className="font-medium">{formatGB(plan.data_gb)}</span>
          </div>
        )}
        {(isAbroad || isGlobal) && plan.days && (
          <div className="flex justify-between">
            <span>תקופה</span>
            <span className="font-medium">{plan.days} ימים</span>
          </div>
        )}
        {plan.minutes && (
          <div className="flex justify-between">
            <span>שיחות</span>
            <span className="font-medium">{plan.minutes}</span>
          </div>
        )}
        {plan.sms && (
          <div className="flex justify-between">
            <span>SMS</span>
            <span className="font-medium">{plan.sms}</span>
          </div>
        )}
        {isContent && plan.free_trial && (
          <div className="flex justify-between">
            <span>🎁 תקופת חינם</span>
            <span className="font-medium">{plan.free_trial}</span>
          </div>
        )}
        {isContent && plan.note && (
          <div className="mt-1 text-xs text-gray-400">{plan.note}</div>
        )}
      </div>

      {/* Extras */}
      {plan.extras && plan.extras.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-1">
          {plan.extras.map((extra, i) => (
            <div key={i} className="text-xs text-gray-500 flex items-start gap-1">
              <span className="text-blue-400 mt-0.5">✦</span>
              <span>{extra}</span>
            </div>
          ))}
        </div>
      )}

      {/* Country link for global regional plans */}
      {onCountryClick && (
        <button
          onClick={onCountryClick}
          className="mt-3 text-xs text-blue-500 hover:text-blue-700 transition-colors"
        >
          מדינות כלולות ✈️
        </button>
      )}
    </div>
  )
}
