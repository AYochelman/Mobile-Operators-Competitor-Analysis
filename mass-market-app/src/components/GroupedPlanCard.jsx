import { useState, useCallback, useMemo, memo } from 'react'
import Badge from './ui/Badge'
import Delta from './moca/Delta'
import CountryModal from './CountryModal'
import AnnotationsModal from './AnnotationsModal'
import { getCountriesForPlan } from '../data/globalCountries'
import { useWatchlist } from '../hooks/useWatchlist'
import { useAnnotationCounts } from '../hooks/useAnnotationCounts'
import { useCoupons } from '../hooks/useCoupons'
import { AFFILIATE_PROVIDERS, AFFILIATE_URLS } from '../data/affiliateLinks'
import { GLOBAL_LABELS, GLOBAL_COLORS } from '../data/carrierLabels'

const CARRIER_LOGOS = {
  tuki:            '/logos/tuki.png',
  globalesim:      '/logos/globalesim.png',
  airalo:          '/logos/airalo.png',
  airalo_local:    '/logos/airalo.png',
  airalo_regional: '/logos/airalo.png',
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
  yesim:           '/logos/yesim.png',
  nomad:           '/logos/nomad.png',
  ubigi:           '/logos/ubigi.png',
  alosim:          '/logos/alosim.png',
  orbit:           '/logos/orbit.png',
  travelsim:       '/logos/travelsim.png',
  gomoworld:       '/logos/gomoworld.png',
  tasim:           '/logos/tasim.png',
  maya:            '/logos/maya.png',
  bcengi:          '/logos/bcengi.png',
  esim70:          '/logos/esim70.png',
  jetpack:         '/logos/jetpack.png',
  breez:           '/logos/breez.png',
  bytesim:         '/logos/bytesim.png',
  besim:           '/logos/besim.png',
  seven_g:         '/logos/seven_g.png',
  bestconnect:     '/logos/bestconnect.png',
  esimplus:        '/logos/esimplus.png',
}

// Custom logo sizes (base: 32px / w-8) — +50% = 48px
const LOGO_SIZES = {
  globalesim:       '72px',
  pelephone_global: '72px',
  esimo:            '72px',
  simtlv:           '48px',
  esimio:           '48px',
  holafly:          '48px',
  sparks:           '48px',
  voye:             '48px',
  orbit:            '48px',
  travelsim:        '64px',
  gomoworld:        '40px',
  maya:             '43px',
  bytesim:          '58px',
  besim:            '52px',
}

// Wide logos: width-only override (height stays at LOGO_SIZES default 32px)
const LOGO_WIDTHS = {
  jetpack: '52px',
  breez: '63px',
}

// AFFILIATE_PROVIDERS + AFFILIATE_URLS now live in ../data/affiliateLinks (shared
// with PlanCard) so the Saily/Voye tracking links can't drift between the two views.

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

// GLOBAL_LABELS + GLOBAL_COLORS now live in ../data/carrierLabels (single source of
// truth, shared with PlanCard + ComparePage + DashboardPage) so newly added eSIM
// providers can't drift out of sync.

function formatGB(gb) {
  if (gb === null || gb === undefined) return 'ללא הגבלה'
  if (gb < 1) return `${Math.round(gb * 1024)}MB`
  return `${Number(gb).toLocaleString('en-US')}GB`
}

function getPillLabel(plan) {
  if (plan.carrier === 'bytesim' || plan.carrier === 'besim') {
    const parts = plan.plan_name?.split(' – ') || []
    const dataStr = parts.at(-2)
    if (dataStr) return dataStr
  }
  return formatGB(plan.data_gb)
}

function formatDays(days) {
  if (!days) return null
  if (days >= 365) return `${(days / 365).toFixed(days % 365 === 0 ? 0 : 1)} שנים`
  if (days > 60) return `${Math.round(days / 30)} חודשים`
  return `${days} ימים`
}

function GroupedPlanCard({ carrier, destination, plans, trendInfo, isInCompare, onCompareToggle, repPlan, tabId }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [selectedDays, setSelectedDays] = useState(() => {
    // Initialize to the days of the first data option (sorted by data_gb ascending)
    const seen = new Map()
    for (const p of plans) {
      const ds = getPillLabel(p)
      if (!seen.has(ds)) seen.set(ds, p)
    }
    const sorted = [...seen.values()].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
    return sorted[0]?.days ?? null
  })
  const [showCountries, setShowCountries] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showAnnotations, setShowAnnotations] = useState(false)
  const { isWatched, toggle: toggleWatch } = useWatchlist()
  const { countFor } = useAnnotationCounts()
  const { couponFor } = useCoupons()
  const coupon = couponFor(carrier)
  const [couponCopied, setCouponCopied] = useState(false)
  const copyCoupon = useCallback((e) => {
    e.stopPropagation()
    if (!coupon?.code) return
    navigator.clipboard?.writeText(coupon.code).then(() => {
      setCouponCopied(true); setTimeout(() => setCouponCopied(false), 2000)
    }).catch(() => {})
  }, [coupon])

  // One representative plan per unique data label, sorted by data_gb ascending
  const dataOptions = useMemo(() => {
    const seen = new Map()
    for (const p of plans) {
      const ds = getPillLabel(p)
      if (!seen.has(ds)) seen.set(ds, p)
    }
    return [...seen.values()].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
  }, [plans])

  // Unique sorted days for the currently selected data option (empty = no choice)
  const availableDays = useMemo(() => {
    const rep = dataOptions[selectedIndex]
    if (!rep) return []
    const ds = getPillLabel(rep)
    return [...new Set(plans.filter(p => getPillLabel(p) === ds && p.days).map(p => p.days))].sort((a, b) => a - b)
  }, [dataOptions, selectedIndex, plans])

  // Active plan: match by (data_label, days); fall back to first plan for that data label
  const selectedPlan = useMemo(() => {
    const rep = dataOptions[selectedIndex]
    const ds = rep ? getPillLabel(rep) : null
    if (selectedDays !== null) {
      const exact = plans.find(p => getPillLabel(p) === ds && p.days === selectedDays)
      if (exact) return exact
    }
    return plans.find(p => getPillLabel(p) === ds) || plans[0]
  }, [plans, dataOptions, selectedIndex, selectedDays])

  const handleDataSelect = useCallback((idx) => {
    setSelectedIndex(idx)
    const ds = getPillLabel(dataOptions[idx])
    const first = plans.find(p => getPillLabel(p) === ds)
    setSelectedDays(first?.days ?? null)
  }, [dataOptions, plans])
  const label = GLOBAL_LABELS[carrier] || carrier
  const badgeColor = GLOBAL_COLORS[carrier] || 'gray'
  const countryData = getCountriesForPlan(selectedPlan)

  const watchKey = { carrier, plan_name: selectedPlan.plan_name || '', plan_type: 'global' }
  const watched = isWatched(watchKey)
  const annotationCount = selectedPlan.plan_name ? countFor(carrier, 'global', selectedPlan.plan_name) : 0

  const handleShare = useCallback((e) => {
    e.stopPropagation()
    const url = `${window.location.origin}/esim?carrier=${carrier}&highlight=${encodeURIComponent(selectedPlan.plan_name || '')}`
    navigator.clipboard?.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {})
  }, [carrier, selectedPlan.plan_name])

  return (
    <div className="bg-white rounded-2xl p-5 shadow-card relative group text-right hover-lift animate-fade-in-up flex flex-col">
      {/* Carrier logo — absolute top-left */}
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

      {/* Carrier badges — absolute top-right */}
      <div className="absolute top-3 right-3 flex items-center gap-1 flex-wrap max-w-[140px]">
        <Badge color={badgeColor}>{label}</Badge>
        {trendInfo && (
          <span className="inline-flex items-center gap-0.5">
            <Delta value={Math.round(trendInfo.pct_change)} size="sm" suffix="%" />
            {trendInfo.pct_change <= -10 && <span aria-hidden="true" className="text-[10px]">🔥</span>}
          </span>
        )}
        {selectedPlan.esim && <Badge color="green">eSIM</Badge>}
      </div>

      {/* Spacer so content doesn't overlap logo/badges */}
      <div className="mt-9" />

      {/* Destination title */}
      <h3 className="text-[15px] font-bold text-gray-800 mb-3">
        <bdi>{destination}</bdi>
      </h3>

      {/* Data / days selector — deduplicated for all carriers */}
      <>
        <div className={`flex flex-wrap gap-1.5 ${availableDays.length > 1 ? 'mb-2' : 'mb-3'}`}>
          {dataOptions.map((rep, idx) => (
            <button
              key={idx}
              onClick={() => handleDataSelect(idx)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all duration-150 ${
                selectedIndex === idx
                  ? 'bg-moca-bolt text-white shadow-sm'
                  : 'bg-moca-cream text-moca-sub hover:bg-moca-sand hover:text-moca-text'
              }`}
            >
              {getPillLabel(rep)}
            </button>
          ))}
        </div>
        {availableDays.length > 1 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {availableDays.map(days => (
              <button
                key={days}
                onClick={() => setSelectedDays(days)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all duration-150 ${
                  selectedDays === days
                    ? 'bg-moca-sand text-moca-text shadow-sm border border-moca-bolt/30'
                    : 'bg-white text-moca-sub border border-gray-200 hover:bg-moca-cream hover:text-moca-text'
                }`}
              >
                {days} ימים
              </button>
            ))}
          </div>
        )}
      </>

      {/* Price */}
      <div className="mb-2">
        <span className="text-3xl font-bold text-gray-900 tracking-tight">
          ₪{selectedPlan.price}
        </span>
        {selectedPlan.original_price && selectedPlan.currency && selectedPlan.currency !== 'ILS' && (
          <div className="text-[11px] text-gray-400 mt-0.5" dir="ltr">
            {selectedPlan.currency} {({'USD':'$','GBP':'£','EUR':'€','AUD':'A$','CAD':'C$','JPY':'¥','CHF':'CHF ','NZD':'NZ$'})[selectedPlan.currency] || '$'}{selectedPlan.original_price}
          </div>
        )}
      </div>

      {/* Info line */}
      <p className="text-sm text-gray-500 mb-3">
        <bdi>{getPillLabel(selectedPlan)}</bdi>
        <span className="mx-1.5 text-gray-300">·</span>
        <bdi>{formatDays(selectedPlan.days)}</bdi>
        {selectedPlan.minutes ? (
          <><span className="mx-1.5 text-gray-300">·</span><bdi>{Number(selectedPlan.minutes).toLocaleString('en-US')} דקות</bdi></>
        ) : null}
        {selectedPlan.sms ? (
          <><span className="mx-1.5 text-gray-300">·</span><bdi>{selectedPlan.sms} SMS</bdi></>
        ) : null}
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

      {/* Bottom section: coupon + affiliate buy + icon strip */}
      <div className="mt-auto">
        {coupon && (
          <div className="pt-3">
            {coupon.external_offer_url ? (
              <a
                href={coupon.external_offer_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="w-full flex items-center justify-center gap-1.5 text-[11px] font-medium text-moca-bolt bg-[#fff4d6] border border-[#e8c97a]/60 rounded-lg py-1.5 px-2 transition-colors hover:bg-[#ffe9a8]"
              >
                <span aria-hidden="true">🎟</span>
                <span>{coupon.discount_label || 'הטבה'}{coupon.partner_name ? ` · אצל ${coupon.partner_name}` : ''}</span>
                <span className="text-[10px] text-[#7a5a30] mr-auto">פתח ↗</span>
              </a>
            ) : (
              <button
                type="button"
                onClick={copyCoupon}
                className="w-full flex items-center justify-center gap-1.5 text-[11px] font-medium text-moca-bolt bg-[#fff4d6] border border-[#e8c97a]/60 rounded-lg py-1.5 px-2 transition-colors hover:bg-[#ffe9a8]"
              >
                <span aria-hidden="true">🎟</span>
                <span>קוד: <span className="font-mono tracking-wide">{coupon.code}</span>{coupon.discount_label ? ` · ${coupon.discount_label}` : ''}</span>
                <span className="text-[10px] text-[#7a5a30] mr-auto">{couponCopied ? '✓ הועתק' : 'העתק'}</span>
              </button>
            )}
          </div>
        )}
        {AFFILIATE_PROVIDERS.has(carrier) && (
          <div className="pt-3">
            <a
              href={AFFILIATE_URLS[carrier] || `https://www.${carrier}.com`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-1.5 w-full text-xs text-white bg-moca-bolt rounded-lg py-1.5 font-medium transition-colors hover:bg-[#7a4520]"
              onClick={(e) => e.stopPropagation()}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
                <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
              </svg>
              רכישה
            </a>
            <p className="text-center text-[10px] text-[#a08060] mt-1">דרך MOCA</p>
          </div>
        )}

        {/* Action icon strip — equal spacing across visible icons */}
        <div className="flex items-center justify-around pt-2 mt-2 border-t border-gray-100">
          {/* Compare */}
          {onCompareToggle && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onCompareToggle(repPlan || selectedPlan, tabId || 'global') }}
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
          )}

          {/* Annotations */}
          {selectedPlan.plan_name && (
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
          {selectedPlan.plan_name && (
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

      {/* Country modal */}
      {countryData && (
        <CountryModal
          open={showCountries}
          onClose={() => setShowCountries(false)}
          title={countryData.title}
          countries={countryData.countries}
        />
      )}

      {/* Annotations modal — keyed to currently selected plan (the active GB pill) */}
      {selectedPlan.plan_name && showAnnotations && (
        <AnnotationsModal
          open={showAnnotations}
          onClose={() => setShowAnnotations(false)}
          carrier={carrier}
          planName={selectedPlan.plan_name}
          planType="global"
          planLabel={`${destination} · ${selectedPlan.data_gb === null ? 'ללא הגבלה' : Number(selectedPlan.data_gb).toLocaleString('en-US') + 'GB'}`}
        />
      )}
    </div>
  )
}

export default memo(GroupedPlanCard)
