import { useState, useCallback, lazy, Suspense, memo } from 'react'
import Badge from './ui/Badge'
import Delta from './moca/Delta'
import CountryModal from './CountryModal'
import Modal from './ui/Modal'
import { getCountriesForPlan } from '../data/globalCountries'
import { getCountriesForAbroadPlan } from '../data/abroadCountries'
import { getAppsForPlan } from '../data/abroadApps'
import { has5G as detect5G } from '../data/networkPriority'
import AppsModal from './AppsModal'
import SparklineMini from './SparklineMini'
import AnnotationsModal from './AnnotationsModal'
import { useWatchlist } from '../hooks/useWatchlist'
import { useAnnotationCounts } from '../hooks/useAnnotationCounts'

// Lazy — Recharts is ~340KB. Only load when the user actually opens history.
const PriceHistoryModal = lazy(() => import('./PriceHistoryModal'))

const AFFILIATE_PROVIDERS = new Set(['airalo', 'holafly', 'saily', 'globalesim'])
const AFFILIATE_URLS = {
  airalo:     'https://www.airalo.com',
  holafly:    'https://esim.holafly.com',
  saily:      'https://saily.com',
  globalesim: 'https://globalesim.com',
}

const CARRIER_HOME_URLS = {
  partner:         'https://www.partner.net.il',
  pelephone:       'https://www.pelephone.co.il',
  hotmobile:       'https://www.hotmobile.co.il',
  cellcom:         'https://www.cellcom.co.il',
  mobile019:       'https://www.019mobile.co.il',
  xphone:          'https://www.xphone.co.il',
  wecom:           'https://we-com.co.il',
  neptucom:        'https://www.neptucom.com',
  tuki:            'https://tuki.co.il',
  globalesim:      'https://globalesim.com',
  airalo:          'https://www.airalo.com',
  pelephone_global:'https://www.pelephone.co.il',
  esimo:           'https://esimo.co.il',
  simtlv:          'https://www.simtlv.co.il',
  world8:          'https://world8.com',
  xphone_global:   'https://www.xphone.co.il',
  saily:           'https://saily.com',
  holafly:         'https://esim.holafly.com',
  esimio:          'https://esim.io',
  sparks:          'https://sparksesim.com',
  voye:            'https://voye.com',
  orbit:           'https://www.orbitmobile.com',
  travelsim:       'https://www.travelsim.com',
  gomoworld:       'https://www.gomoworld.com',
  tasim:           'https://www.tasim.us',
  maya:            'https://maya.net/esim',
  esim70:          'https://www.esim70.com',
  jetpack:         'https://www.jetpacglobal.com',
  besim:           'https://besim.co.il',
}

function slugify(str) {
  if (!str) return 'plan'
  return str
    .toLowerCase()
    .replace(/[–—]/g, '-')
    .replace(/\s+/g, '-')
    .replace(/[^\w-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '') || 'plan'
}

const CARRIER_COLORS = {
  partner: 'pink', pelephone: 'blue', hotmobile: 'orange', cellcom: 'green',
  mobile019: 'purple', xphone: 'teal', wecom: 'amber', neptucom: 'indigo',
  golan: 'teal', rami_levy: 'red',
}
const CARRIER_LABELS = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום',
  mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', neptucom: 'Neptucom',
  golan: 'גולן טלקום', rami_levy: 'רמי לוי תקשורת',
}
const GLOBAL_LABELS = {
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo',
  pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV',
  world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily',
  holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks', voye: 'VOYE',
  orbit: 'Orbit', travelsim: 'Travel Sim', gomoworld: 'GoMoWorld', tasim: 'Tasim',
  maya: 'Maya Mobile', bcengi: 'Bcengi', esim70: 'eSIM70', jetpack: 'Jetpack',
  breez: 'Breeze', bytesim: 'ByteSim', besim: 'Besim',
}
const GLOBAL_COLORS = {
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'blue',
  esimo: 'purple', simtlv: 'red', world8: 'teal', xphone_global: 'teal',
  saily: 'purple', holafly: 'orange', esimio: 'blue', sparks: 'amber', voye: 'pink',
  orbit: 'indigo', travelsim: 'teal', gomoworld: 'cyan', tasim: 'violet',
  maya: 'teal', esim70: 'emerald', jetpack: 'sky', breez: 'cyan',
  bytesim: 'emerald', besim: 'teal',
}

const CARRIER_LOGOS = {
  // Domestic
  neptucom:        '/logos/neptucom.png',
  partner:         '/logos/partner.png',
  pelephone:       '/logos/pelephone.png',
  hotmobile:       '/logos/hotmobile.png',
  cellcom:         '/logos/cellcom.png',
  mobile019:       '/logos/019.png',
  xphone:          '/logos/xphone_global.png',
  wecom:           '/logos/wecom.png',
  golan:           '/logos/golan.png',
  rami_levy:       '/logos/rami_levy.png',
  // Global eSIM
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
  travelsim:       '/logos/travelsim.png',
  gomoworld:       '/logos/gomoworld.png',
  tasim:           '/logos/tasim.png',
  maya:            '/logos/maya.png',
  bcengi:         '/logos/bcengi.png',
  rami_levy:      '/logos/rami_levy.png',
  esim70:         '/logos/esim70.png',
  jetpack:        '/logos/jetpack.png',
  breez:          '/logos/breez.png',
  bytesim:        '/logos/bytesim.png',
  besim:          '/logos/besim.png',
}

// Custom logo sizes (base: 32px / w-8) — +50% = 48px
const LOGO_SIZES = {
  globalesim:       '72px',
  pelephone_global: '72px',
  esimo:            '72px',
  cellcom:          '48px',
  simtlv:           '48px',
  esimio:           '48px',
  holafly:          '48px',
  sparks:           '48px',
  voye:             '48px',
  orbit:            '48px',
  neptucom:         '64px',
  travelsim:        '64px',
  golan:            '45px',
  gomoworld:        '40px',
  maya:             '43px',
  bytesim:          '58px',
  besim:            '52px',
}

// Wide logos: separate width override (height stays at LOGO_SIZES default 32px)
const LOGO_WIDTHS = {
  rami_levy: '110px',
  jetpack: '52px',
  breez: '63px',
}

const CONTENT_URLS = {
  'eSIM שעון_cellcom':    'https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/smart_watch_esim/',
  'eSIM שעון_partner':    'https://www.partner.co.il/u/esim',
  'eSIM שעון_hotmobile':  'https://hotmobile-sale.online/deals/esim-watch/',
  'eSIM שעון_pelephone':  'https://www.pelephone.co.il/ds/heb/eshop/campaigns/esim-watch/',
  'סייבר_pelephone':      'https://www.pelephone.co.il/ds/heb/content-products/pelephonecyber/',
  'סייבר_hotmobile':      'https://campaign.hotmobile.co.il/cyber/',
  'סייבר_partner':        'https://www.partner.co.il/u/cyberguard',
  'סייבר_cellcom':        'https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/Safe_browsing/',
  'נורטון_pelephone':     'https://www.pelephone.co.il/ds/heb/content-products/pelephonecyber/',
  'נורטון_hotmobile':     'https://www.hotmobile.co.il/Pages/Norton.aspx',
  'נורטון_partner':       'https://www.partner.co.il/u/norton-cell',
  'נורטון_cellcom':       'https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/',
  'נורטון_wecom':         'https://we-com.co.il/norton360/',
  'שיר בהמתנה_pelephone': 'https://www.pelephone.co.il/digitalsite/heb/content-products/songwaiting/lobby/',
  'שיר בהמתנה_partner':   'https://www.partner.co.il/n/funtone/main/home',
  'שיר בהמתנה_cellcom':   'https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/',
  'תא קולי_pelephone':    'https://www.pelephone.co.il/ds/heb/support/support/voice-mail/',
  'תא קולי_partner':      'https://www.partner.co.il/n/partnerdigital/voice_mail',
  'תא קולי_cellcom':      'https://cellcom.co.il/production/Private/Cellular/Cellular_upgrades/',
  'eSIM שעון_golan':      'https://www.golantelecom.co.il/esimwatchintro',
  'סייבר_golan':          'https://www.golantelecom.co.il/golancyber',
  'נורטון_golan':         'https://www.golantelecom.co.il/golancyber',
  'תא קולי_golan':        'https://www.golantelecom.co.il/info_and_support#faq-item-11',
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

function PlanCard({ plan, type = 'domestic', changeType, highlighted, trendInfo, isInCompare, onCompareToggle }) {
  const [showCountries, setShowCountries] = useState(false)
  const [showApps, setShowApps] = useState(false)
  const [showAllExtras, setShowAllExtras] = useState(false)
  const [showPlanInfo, setShowPlanInfo] = useState(false)
  const [showPriceHistory, setShowPriceHistory] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showAnnotations, setShowAnnotations] = useState(false)
  const { isWatched, toggle: toggleWatch } = useWatchlist()
  const { countFor } = useAnnotationCounts()
  const annotationCount = type !== 'content' && plan.plan_name ? countFor(plan.carrier, type, plan.plan_name) : 0

  const handleShare = useCallback((e) => {
    e.stopPropagation()
    const url = `${window.location.origin}/?tab=${type}&carrier=${plan.carrier}&highlight=${encodeURIComponent(plan.plan_name || '')}`
    navigator.clipboard?.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {})
  }, [type, plan.carrier, plan.plan_name])
  const watchKey = { carrier: plan.carrier, plan_name: plan.plan_name || plan.service || '', plan_type: type }
  const watched = isWatched(watchKey)
  const isGlobal = type === 'global'
  const isAbroad = type === 'abroad'
  const isContent = type === 'content'
  const isReseller = type === 'resellers'
  const hasNeptucomRoaming = plan.carrier === 'neptucom' && plan.extras && plan.extras.some(e => /\u05db\u05dc\u05d5\u05dc/.test(e) && /\u05d7\u05d5"?\u05dc/.test(e))
  const countryData = isGlobal
    ? getCountriesForPlan(plan)
    : isAbroad
      ? getCountriesForAbroadPlan(plan)
      : hasNeptucomRoaming
        ? getCountriesForAbroadPlan(plan)
        : null
  const appsData = isContent ? null : getAppsForPlan(plan)
  const carrier = plan.carrier
  const label = isGlobal ? (GLOBAL_LABELS[carrier] || carrier) : (CARRIER_LABELS[carrier] || carrier)
  const badgeColor = isGlobal ? (GLOBAL_COLORS[carrier] || 'gray') : (CARRIER_COLORS[carrier] || 'gray')
  // For reseller plans, link out to the source post/page (Instagram, FB, reseller site)
  // instead of the underlying carrier's homepage. Must be declared AFTER `carrier`.
  const providerUrl = isReseller && plan.source_url ? plan.source_url : CARRIER_HOME_URLS[carrier]
  const providerLabel = isReseller ? 'לפוסט המקור' : 'לאתר הספק'

  // Build info line: data + period, dot-separated
  const infoParts = []
  if (!isContent) infoParts.push(formatGB(plan.data_gb))
  if ((isAbroad || isGlobal) && plan.days) infoParts.push(formatDays(plan.days))
  if (plan.minutes) infoParts.push(`${plan.minutes} דקות`)
  if (plan.sms) infoParts.push(`${plan.sms} SMS`)

  // Extract plan_info marker (stored inside extras as "__info__|<text>")
  const planInfoMarker = plan.extras ? plan.extras.find(e => typeof e === 'string' && e.startsWith('__info__|')) : null
  const planInfo = planInfoMarker ? planInfoMarker.slice('__info__|'.length) : (plan.plan_info || null)

  // Extras — filter out app-related text if we have an apps link, and the info marker
  // For Orbit zone plans, extras[1+] are covered countries — hide them (shown in modal)
  const rawExtras = plan.extras ? plan.extras.filter(e => e && !(appsData && /אפליקציות/.test(e)) && !(typeof e === 'string' && e.startsWith('__info__|'))) : []
  // For Orbit zone plans: extras[1+] are country lists — hide (shown in modal)
  // For single-country global plans: if destination already in plan name, skip extras[0] but show extras[1+] (feature bullets)
  const extras = (plan.carrier === 'orbit' && rawExtras.length > 1)
    ? []
    : (isGlobal && rawExtras.length >= 1 && plan.plan_name && plan.plan_name.includes(rawExtras[0]))
      ? rawExtras.slice(1)
      : rawExtras
  const visibleExtras = extras
  const hiddenCount = 0

  // 5G marker — true if plan name or extras indicate 5G support
  const supports5G = (
    detect5G(plan)
  )
  const nameHas5G = plan.plan_name && /\b5G\b/i.test(plan.plan_name)

  const hasRoaming = !isGlobal && !isAbroad && !isContent && plan.extras && plan.extras.some(e => /חו"ל|חו״ל/.test(e) && /\d+\s*GB|גלישה/i.test(e))
  const contentUrl = isContent ? (CONTENT_URLS[`${plan.service}_${carrier}`] || null) : null

  return (
    <div className={`bg-white rounded-2xl p-5 shadow-sm relative group text-right hover-lift animate-fade-in-up flex flex-col ${highlighted ? 'ring-2 ring-amber-400 shadow-amber-100 shadow-lg animate-pulse-highlight' : ''}`}
      ref={highlighted ? (el) => { if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }) } : undefined}
    >
      {/* Carrier logo — top-left, no background */}
      {CARRIER_LOGOS[carrier] && (
        <img
          src={CARRIER_LOGOS[carrier]}
          alt={label}
          loading="lazy"
          decoding="async"
          className="absolute top-3 left-3 object-contain"
          style={{ width: LOGO_WIDTHS[carrier] || LOGO_SIZES[carrier] || '32px', height: LOGO_SIZES[carrier] || '32px' }}
        />
      )}

      {/* Change indicator dot */}
      {changeType && CHANGE_DOT[changeType] && (
        <span
          className={`absolute w-2 h-2 rounded-full ${CHANGE_DOT[changeType]} top-2 left-2`}
          title={changeType === 'new_plan' ? 'חדש' : changeType === 'price_change' ? 'שינוי מחיר' : 'הוסרה'}
        />
      )}


      {/* Carrier badge — absolute top-right */}
      <div className={`flex items-center gap-1 flex-wrap ${CARRIER_LOGOS[carrier] ? 'absolute top-3 right-3 max-w-[140px]' : 'mb-3'}`}>
        <Badge color={badgeColor}>{label}</Badge>
        {trendInfo && (
          <span className="inline-flex items-center gap-0.5">
            <Delta value={Math.round(trendInfo.pct_change)} size="sm" suffix="%" />
            {trendInfo.pct_change <= -10 && <span aria-hidden="true" className="text-[10px]">🔥</span>}
          </span>
        )}
        {isGlobal && plan.esim && <Badge color="green">eSIM</Badge>}
        {(hasRoaming || hasNeptucomRoaming) && <Badge color="blue">חו״ל</Badge>}
      </div>

      {/* Spacer so content starts below logo/badge row when logo present */}
      {CARRIER_LOGOS[carrier] && <div className="mt-9" />}

      {/* Plan name */}
      {!isContent && (
        <h3 className="text-[13px] font-semibold text-gray-800 mb-3 leading-relaxed flex items-center gap-1.5 flex-wrap">
          <span>{
            (plan.plan_name || '').split(' – ').map((part, i) => (
              <span key={i}>{i > 0 && <span className="text-gray-300"> - </span>}<bdi>{part}</bdi></span>
            ))
          }</span>
          {supports5G && !nameHas5G && (
            <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold rounded bg-purple-100 text-purple-700 leading-none tracking-wide">5G</span>
          )}
        </h3>
      )}
      {/* Service name for content plans */}
      {isContent && plan.service && (
        <h3 className="text-[13px] font-semibold text-gray-800 mb-3 leading-relaxed">{plan.service}</h3>
      )}

      {/* Price */}
      <div className="mb-3 text-right">
        <div className="flex items-baseline gap-2 justify-start">
          <div className="text-3xl font-bold text-gray-900 tracking-tight">{String(plan.price).startsWith('₪') ? plan.price : `₪${plan.price}`}</div>
          {!isContent && plan.plan_name && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setShowPriceHistory(true) }}
              title="היסטוריית מחיר"
              className="text-gray-300 hover:text-moca-bolt transition-colors p-1 -m-1"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                <polyline points="17 6 23 6 23 12"/>
              </svg>
            </button>
          )}
        </div>
        {isGlobal && plan.original_price && plan.currency && plan.currency !== 'ILS' && (
          <div className="text-[11px] text-gray-400 mt-0.5" dir="ltr">{plan.currency} {({'USD':'$','GBP':'£','EUR':'€','AUD':'A$','CAD':'C$','JPY':'¥','CHF':'CHF ','NZD':'NZ$'})[plan.currency] || '$'}{plan.original_price}</div>
        )}
        {plan.promo_price != null && plan.promo_months != null && (
          <div className="text-[11px] text-moca-bolt font-medium mt-0.5">
            {plan.promo_months === 2 ? 'חודשיים ראשונים' : `${plan.promo_months} חודשים ראשונים`} ב-₪{plan.promo_price} לחודש
          </div>
        )}
        {!isContent && Number(plan.price) > 0 && Number(plan.data_gb) > 0 && (
          <div className="text-[10px] text-gray-400 mt-0.5" dir="ltr">
            ₪{(Number(plan.price) / Number(plan.data_gb)).toFixed(2)}/GB
          </div>
        )}
        {!isContent && plan.plan_name && (
          <SparklineMini carrier={carrier} planName={plan.plan_name} planType={type} />
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
        <p className="text-xs text-gray-500 mb-2 flex items-center gap-1 justify-start">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5 text-moca-bolt shrink-0">
            <path fillRule="evenodd" d="M4.5 2A2.5 2.5 0 0 0 2 4.5v2.878a2.5 2.5 0 0 0 .732 1.768l5.5 5.5a2.5 2.5 0 0 0 3.536 0l2.878-2.878a2.5 2.5 0 0 0 0-3.536l-5.5-5.5A2.5 2.5 0 0 0 7.378 2H4.5ZM5 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
          </svg>
          <span>{plan.free_trial}</span>
        </p>
      )}
      {isContent && plan.note && (
        <p className="text-[11px] text-gray-400 mb-2 text-right">{plan.note}</p>
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

      {/* Bottom section: provider buttons + icon strip */}
      <div className="mt-auto">
        {/* Provider link button */}
        {(plan.url || (isGlobal && AFFILIATE_PROVIDERS.has(plan.carrier))) && (
        <div className="pt-3">
          {isGlobal && AFFILIATE_PROVIDERS.has(plan.carrier) ? (
            <div>
              <a
                href={AFFILIATE_URLS[plan.carrier] || `https://www.${plan.carrier}.com`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-1.5 w-full text-xs text-white bg-[#5c3317] rounded-lg py-1.5 font-medium transition-colors hover:bg-[#7a4520]"
                onClick={(e) => e.stopPropagation()}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
                  <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                </svg>
                רכישה
              </a>
              <p className="text-center text-[10px] text-[#a08060] mt-1">דרך MOCA</p>
            </div>
          ) : (
            <div className="flex gap-2">
              {planInfo ? (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setShowPlanInfo(true) }}
                  className="flex items-center justify-center gap-1.5 flex-1 text-xs text-moca-sub hover:text-moca-bolt border border-moca-border/40 rounded-lg py-1.5 transition-colors hover:bg-moca-cream"
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="16" x2="12" y2="12"/>
                    <line x1="12" y1="8" x2="12.01" y2="8"/>
                  </svg>
                  תנאי התוכנית
                </button>
              ) : (
              <a
                href={plan.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-1.5 flex-1 text-xs text-moca-sub hover:text-moca-bolt border border-moca-border/40 rounded-lg py-1.5 transition-colors hover:bg-moca-cream"
                onClick={(e) => e.stopPropagation()}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                  <polyline points="15 3 21 3 21 9"/>
                  <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
                תנאי התוכנית
              </a>
              )}
              {providerUrl && (
                <a
                  href={providerUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-1.5 flex-1 text-xs text-white bg-[#5c3317] rounded-lg py-1.5 font-medium transition-colors hover:bg-[#7a4520]"
                  onClick={(e) => e.stopPropagation()}
                >
                  {isReseller ? (
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                      <polyline points="15 3 21 3 21 9"/>
                      <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  ) : (
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
                      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                    </svg>
                  )}
                  {providerLabel}
                </a>
              )}
            </div>
          )}
        </div>
        )}

        {/* Action icon strip — equal spacing across visible icons */}
        <div className="flex items-center justify-around pt-2 mt-2 border-t border-gray-100">
          {/* Compare toggle (or content URL fallback) */}
          {!isContent && onCompareToggle ? (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onCompareToggle(plan, type) }}
              title={isInCompare ? 'הסר מהשוואה' : 'הוסף להשוואה'}
              className={`p-1 rounded transition-all ${
                isInCompare ? 'text-blue-500' : 'text-gray-300 group-hover:text-gray-400 hover:text-blue-400'
              }`}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill={isInCompare ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                {isInCompare && <polyline points="9 12 11 14 15 10" />}
              </svg>
            </button>
          ) : contentUrl ? (
            <a
              href={contentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1 text-gray-300 group-hover:text-gray-400 hover:text-moca-bolt transition-colors"
              onClick={(e) => e.stopPropagation()}
              title="לאתר הספק"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
            </a>
          ) : null}

          {/* Annotations */}
          {!isContent && plan.plan_name && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setShowAnnotations(true) }}
              title={annotationCount > 0 ? `${annotationCount} הערות צוות` : 'הוסף הערה'}
              className={`relative p-1 transition-all ${
                annotationCount > 0 ? 'text-moca-bolt' : 'text-gray-300 group-hover:text-gray-400 hover:text-moca-bolt'
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill={annotationCount > 0 ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              {annotationCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[12px] h-3 bg-moca-bolt text-white text-[8px] font-bold rounded-full flex items-center justify-center px-0.5 leading-none">
                  {annotationCount}
                </span>
              )}
            </button>
          )}

          {/* Share */}
          {!isContent && plan.plan_name && (
            <button
              type="button"
              onClick={handleShare}
              title="שתף חבילה"
              className={`p-1 transition-all ${
                copied ? 'text-emerald-500' : 'text-gray-300 group-hover:text-gray-400 hover:text-moca-bolt'
              }`}
            >
              {copied ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                  <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                </svg>
              )}
            </button>
          )}

          {/* Watchlist star */}
          {watchKey.plan_name && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); toggleWatch(watchKey) }}
              title={watched ? 'הסר מהמעקב' : 'הוסף למעקב'}
              className={`p-1 transition-all ${
                watched ? 'text-amber-400 hover:text-amber-500' : 'text-gray-300 group-hover:text-gray-400 hover:text-amber-400'
              }`}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill={watched ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
            </button>
          )}
        </div>
      </div>

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
      {!isContent && plan.plan_name && (
        <AnnotationsModal
          open={showAnnotations}
          onClose={() => setShowAnnotations(false)}
          carrier={plan.carrier}
          planName={plan.plan_name}
          planType={type}
          planLabel={plan.plan_name}
        />
      )}
      {!isContent && plan.plan_name && showPriceHistory && (
        <Suspense fallback={null}>
        <PriceHistoryModal
          open={showPriceHistory}
          onClose={() => setShowPriceHistory(false)}
          carrier={carrier}
          planName={plan.plan_name}
          planType={type}
          currentPrice={plan.price}
        />
        </Suspense>
      )}
      {planInfo && (
        <Modal open={showPlanInfo} onClose={() => setShowPlanInfo(false)} title="מידע נוסף על התוכנית" maxWidth="max-w-md">
          <div className="space-y-2 text-sm text-gray-700 leading-relaxed text-right">
            {planInfo.split('\n').map(l => l.trim()).filter(Boolean).map((line, i) => (
              <p key={i} className="flex items-start gap-2">
                <span className="text-moca-bolt mt-1 shrink-0">&#10094;</span>
                <span>{line}</span>
              </p>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}

export default memo(PlanCard)
