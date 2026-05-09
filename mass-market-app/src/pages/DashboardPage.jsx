import { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useScrape } from '../hooks/useScrape'
import { useHiddenCarrier, useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { has5G, hasMaxPriority } from '../data/networkPriority'
import PlanCard from '../components/PlanCard'
import BannerMosaic from '../components/moca/BannerMosaic'
const HistoryTab = lazy(() => import('../components/HistoryTab'))
const NewsTab    = lazy(() => import('../components/NewsTab'))
import GroupedPlanCard from '../components/GroupedPlanCard'
import CountryModal from '../components/CountryModal'
import MarketMoversWidget from '../components/MarketMoversWidget'
import SavedViewsMenu from '../components/SavedViewsMenu'
import SavedComparesMenu from '../components/SavedComparesMenu'
import CarrierAIInsights from '../components/CarrierAIInsights'
import ScrapeProgressPanel from '../components/ScrapeProgressPanel'
import CompetitorBoard from '../components/moca/CompetitorBoard'
import { useWatchlist } from '../hooks/useWatchlist'
import FilterTag from '../components/ui/FilterTag'
import SearchableSelect from '../components/ui/SearchableSelect'
import Badge from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'
import Button from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import {
  TRAVELSIM_GLOBAL, TRAVELSIM_USA, TRAVELSIM_ME,
  SIMTLV_COUNTRIES, PELEPHONE_GLOBAL_COUNTRIES, ESIMO_COUNTRIES,
  WORLD8_EUROPE_USA, WORLD8_WORLDWIDE,
  XPHONE_EUROPE, XPHONE_WORLD,
  AIRALO_DISCOVER,
  AIRALO_REGION_MAP,
  GLOBALESIM_EUROPE, GLOBALESIM_ASIA, GLOBALESIM_NORTH_AMERICA,
  GLOBALESIM_SOUTH_AMERICA, GLOBALESIM_AFRICA, GLOBALESIM_OCEANIA, GLOBALESIM_GLOBAL_REGION,
  GOMOWORLD_EUROPE, GOMOWORLD_LATIN_AMERICA, GOMOWORLD_SOUTHEAST_ASIA,
  GOMOWORLD_FRENCH_ANTILLES, GOMOWORLD_NETHERLANDS_ANTILLES, GOMOWORLD_NORTH_AMERICA,
  MAYA_GLOBAL, MAYA_OCEANIA,
  BESIM_REGION_MAP,
} from '../data/globalCountries'

// Carriers where one plan covers many countries (zone/global plans)
const MULTI_COUNTRY_CARRIERS = new Set([
  'travelsim', 'xphone_global', 'simtlv', 'world8', 'airalo', 'airalo_regional',
  'pelephone_global', 'esimo', 'globalesim', 'gomoworld', 'maya', 'besim',
])

const GLOBALESIM_REGION_MAP = {
  'אפריקה': GLOBALESIM_AFRICA,
  'אסיה': GLOBALESIM_ASIA,
  'צפון אמריקה': GLOBALESIM_NORTH_AMERICA,
  'דרום אמריקה': GLOBALESIM_SOUTH_AMERICA,
  'אוקיאניה': GLOBALESIM_OCEANIA,
  'אירופה': GLOBALESIM_EUROPE,
  'גלובלי': GLOBALESIM_GLOBAL_REGION,
}

function getPlanCoverage(plan) {
  const carrier = plan.carrier
  const dest = plan.extras?.[0] || ''
  const name = plan.plan_name || ''
  if (carrier === 'travelsim') {
    if (dest === 'ארצות הברית') return TRAVELSIM_USA
    if (dest === 'המזרח התיכון') return TRAVELSIM_ME
    return TRAVELSIM_GLOBAL
  }
  if (carrier === 'xphone_global') {
    return dest.startsWith('אירופה') ? XPHONE_EUROPE : XPHONE_WORLD
  }
  if (carrier === 'simtlv') return SIMTLV_COUNTRIES
  if (carrier === 'world8') {
    return (name.includes('אירופה') || name.includes('Europe')) ? WORLD8_EUROPE_USA : WORLD8_WORLDWIDE
  }
  if (carrier === 'airalo') return AIRALO_DISCOVER
  if (carrier === 'airalo_regional') return AIRALO_REGION_MAP[dest] || null
  if (carrier === 'pelephone_global') return PELEPHONE_GLOBAL_COUNTRIES
  if (carrier === 'esimo') return ESIMO_COUNTRIES
  if (carrier === 'globalesim') return GLOBALESIM_REGION_MAP[dest] || GLOBALESIM_GLOBAL_REGION
  if (carrier === 'gomoworld') {
    const GOMOWORLD_ZONE_MAP = {
      'אירופה': GOMOWORLD_EUROPE, 'אמריקה הלטינית': GOMOWORLD_LATIN_AMERICA,
      'דרום מזרח אסיה': GOMOWORLD_SOUTHEAST_ASIA, 'האנטילים הצרפתיים': GOMOWORLD_FRENCH_ANTILLES,
      'אנטילים הולנדיים': GOMOWORLD_NETHERLANDS_ANTILLES, 'צפון אמריקה': GOMOWORLD_NORTH_AMERICA,
    }
    return GOMOWORLD_ZONE_MAP[dest] || null
  }
  if (carrier === 'maya') {
    if (dest === 'גלובלי') return MAYA_GLOBAL
    if (dest === 'אוקיאניה') return MAYA_OCEANIA
    return null
  }
  if (carrier === 'besim') {
    // Per-country plans: extras[0] is a country name (not a region) — return null so the
    // dashboard's destination-filter falls back to direct-equality matching on extras[0].
    // Regional/global bundles: extras[0] is a canonical region name → expand via the map.
    return BESIM_REGION_MAP[dest] || null
  }
  return null
}

const TAB_ICONS = {
  domestic: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="2" width="14" height="20" rx="2" ry="2" /><line x1="12" y1="18" x2="12" y2="18.01" />
    </svg>
  ),
  abroad: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />
    </svg>
  ),
  global: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  content: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="15" rx="2" ry="2" /><polyline points="17 2 12 7 7 2" />
    </svg>
  ),
  banners: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" />
    </svg>
  ),
  history: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
      <polyline points="17 6 23 6 23 12"/>
    </svg>
  ),
  news: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z"/>
      <line x1="7" y1="8" x2="17" y2="8"/>
      <line x1="7" y1="12" x2="17" y2="12"/>
      <line x1="7" y1="16" x2="13" y2="16"/>
    </svg>
  ),
  resellers: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
      <line x1="3" y1="6" x2="21" y2="6"/>
      <path d="M16 10a4 4 0 0 1-8 0"/>
    </svg>
  ),
}

const TABS = [
  { id: 'domestic', label: 'חבילות סלולר' },
  { id: 'abroad', label: 'חו"ל' },
  { id: 'global', label: 'גלובלי' },
  { id: 'resellers', label: 'משווקים' },
  { id: 'content', label: 'תוכן' },
  { id: 'banners', label: 'באנרים ראשיים' },
  { id: 'history', label: 'היסטוריה' },
  { id: 'news', label: '\u05d1\u05d7\u05d3\u05e9\u05d5\u05ea' },
]

const RESELLERS = [
  { id: 'm_pelephone',    label: '\u05de.\u05e4\u05dc\u05d0\u05e4\u05d5\u05df (\u05d0\u05d9\u05e0\u05e1\u05d8\u05d2\u05e8\u05dd)', underlying: 'pelephone',
    source_url: 'https://www.instagram.com/m.pelephone/' },
  { id: 'cellcomshefamr', label: '\u05e1\u05dc\u05e7\u05d5\u05dd \u05e9\u05e4\u05e8\u05e2\u05dd',          underlying: 'cellcom',
    source_url: 'https://www.instagram.com/cellcomshefamr/' },
]

const KNOWN_REGIONS = new Set([
  'אירופה','אסיה','אסיה ואוקיאניה','אפריקה','גלובלי','קריביים','איי הקריביים',
  'אמריקה הלטינית','צפון אמריקה','המזרח התיכון','המזרח התיכון וצפון אפריקה',
  'דרום מזרח אסיה','סקנדינביה','בלקן','מזרח אירופה','מרכז אמריקה','אוקיאניה',
  'סין + הונג קונג + מקאו','יפן וקוריאה','יפן וסין',
  'אסיה פסיפיק','מרכז אסיה','צפון אפריקה',
  'שוויץ+','גוודלופ','קפריסין+',
  'אמריקה הדרומית','דרום אמריקה',
  'צפון ודרום אמריקה','מדינות האיים הקריביים',
  'אירופה — גלישה בלבד','אירופה — גולשים ומדברים',
  '167+ מדינות','156+ מדינות',
  'ספארי אפריקה','האיחוד האירופי ובריטניה',
  'כלל העולם',
  // Breeze regions
  'אירופה+','אמריקה המרכזית','חבר המדינות',
  'אירופה וארה"ב','פורטוגל וספרד','המזרח התיכון לייט','אירופה לייט',
])

// Region-label consolidation rules:
// 1. Any "<N>+? מדינות" tag with N > 100 → unified "גלובלי" (global multi-country bundle).
// 2. Any tag whose name contains the word "אירופה" (e.g. "אירופה+", "אירופה לייט",
//    "אירופה — גלישה בלבד", "מזרח אירופה") → unified "אירופה" so the regions
//    dropdown shows one Europe entry instead of six near-duplicates.
const MULTI_COUNTRY_REGION_RE = /^(\d+)\+?\s*מדינות$/
function isLargeMultiCountryRegion(region) {
  const m = region && String(region).match(MULTI_COUNTRY_REGION_RE)
  return !!m && parseInt(m[1], 10) > 100
}
function normalizeRegionLabel(region) {
  if (isLargeMultiCountryRegion(region)) return 'גלובלי'
  if (region && String(region).includes('אירופה')) return 'אירופה'
  return region
}

const CARRIERS = [
  { id: 'partner', label: 'פרטנר' },
  { id: 'pelephone', label: 'פלאפון' },
  { id: 'hotmobile', label: 'הוט מובייל' },
  { id: 'cellcom', label: 'סלקום' },
  { id: 'mobile019', label: '019' },
  { id: 'xphone', label: 'XPhone' },
  { id: 'wecom', label: 'We-Com' },
  { id: 'neptucom', label: 'Neptucom' },
  { id: 'golan', label: 'גולן טלקום' },
  { id: 'rami_levy', label: 'רמי לוי' },
]

const GLOBAL_PROVIDERS = [
  { id: 'world8', label: '8 World' },
  { id: 'airalo', label: 'Airalo' },
  { id: 'bcengi', label: 'Bcengi' },
  { id: 'besim', label: 'Besim' },
  { id: 'breez', label: 'Breeze' },
  { id: 'bytesim', label: 'ByteSim' },
  { id: 'esimio', label: 'eSIM.io' },
  { id: 'esim70', label: 'eSIM70' },
  { id: 'esimo', label: 'eSIMo' },
  { id: 'globalesim', label: 'GlobaleSIM' },
  { id: 'pelephone_global', label: 'GlobalSIM' },
  { id: 'gomoworld', label: 'GoMoWorld' },
  { id: 'holafly', label: 'Holafly' },
  { id: 'jetpack', label: 'Jetpack' },
  { id: 'maya', label: 'Maya' },
  { id: 'orbit', label: 'Orbit' },
  { id: 'saily', label: 'Saily' },
  { id: 'simtlv', label: 'SimTLV' },
  { id: 'sparks', label: 'Sparks' },
  { id: 'tasim', label: 'Tasim' },
  { id: 'travelsim', label: 'Travel Sim' },
  { id: 'tuki', label: 'Tuki' },
  { id: 'voye', label: 'VOYE' },
  { id: 'xphone_global', label: 'XPhone' },
]

export default function DashboardPage() {
  const { isAdmin, workspace } = useAuth()
  const { scraping, countdown, triggerScrape } = useScrape()
  const hiddenCarrier = useHiddenCarrier()
  const visibleCarrierIds = useVisibleCarriers(CARRIERS.map(c => c.id))
  const flags = useFeatureFlags()
  const { items: watchItems, isWatched } = useWatchlist()
  const [onlyWatched, setOnlyWatched] = useState(false)
  const visibleTabs = useMemo(() => TABS.filter(t => !flags['hide_' + t.id]), [flags])
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState(searchParams.get('tab') || 'domestic')

  // If active tab gets hidden by feature flags, fall back to first visible tab
  useEffect(() => {
    if (flags['hide_' + tab]) {
      const first = TABS.find(t => !flags['hide_' + t.id])
      if (first) setTab(first.id)
    }
  }, [flags]) // eslint-disable-line react-hooks/exhaustive-deps
  const [loading, setLoading] = useState(true)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [plans, setPlans] = useState({ domestic: [], abroad: [], global: [], content: [], resellers: [] })
  const [changes, setChanges] = useState({ domestic: [], abroad: [], global: [], content: [] })
  const [filters, setFilters] = useState({
    carrier: 'all', gb: 'all', sort: 'price_asc', gen: 'all', roaming: 'all',
    globalProvider: 'all', destination: 'all', region: 'all', days: 'all',
    contentCarrier: 'all', contentService: 'all', reseller: 'all',
  })
  const [countryModal, setCountryModal] = useState(null)
  const [highlightPlan, setHighlightPlan] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [usdRate, setUsdRate] = useState(null)
  const [eurRate, setEurRate] = useState(null)
  const [gbpRate, setGbpRate] = useState(null)
  const [visibleCount, setVisibleCount] = useState(5000)
  const [trendMap, setTrendMap] = useState(new Map())   // carrier|plan_name → {pct_change}
  const [compareMap, setCompareMap] = useState(new Map()) // key → {plan, planType}
  const [showCompareDrawer, setShowCompareDrawer] = useState(false)
  const [banners, setBanners] = useState([])
  const [bannersLoaded, setBannersLoaded] = useState(false)
  const [storeBanners, setStoreBanners] = useState([])
  const [storeBannersLoaded, setStoreBannersLoaded] = useState(false)

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (tab === 'domestic' || tab === 'abroad') {
      if (filters.carrier !== 'all') count++
    }
    if (tab === 'domestic') {
      if (filters.gen !== 'all') count++
      if (filters.roaming !== 'all') count++
    }
    if (tab === 'global') {
      if (filters.globalProvider !== 'all') count++
      if (filters.region !== 'all') count++
      if (filters.destination !== 'all') count++
    }
    if (tab === 'content') {
      if (filters.contentCarrier !== 'all') count++
      if (filters.contentService !== 'all') count++
    }
    if (tab === 'resellers') {
      if (filters.reseller !== 'all') count++
      if (filters.carrier !== 'all') count++
    }
    if (tab !== 'content') {
      if (filters.gb !== 'all') count++
      if (filters.days !== 'all') count++
    }
    return count
  }, [filters, tab])

  // Load data
  // Apply URL params from chat navigation
  useEffect(() => {
    const urlTab = searchParams.get('tab')
    const urlCarrier = searchParams.get('carrier')
    const urlHighlight = searchParams.get('highlight')
    if (urlTab && ['domestic', 'abroad', 'global', 'content', 'resellers'].includes(urlTab)) {
      setTab(urlTab)
      if (urlCarrier) {
        if (urlTab === 'global') {
          setFilter('globalProvider', urlCarrier)
        } else {
          setFilter('carrier', urlCarrier)
        }
        setFiltersOpen(true)
      }
      if (urlHighlight) {
        // Delay highlight until data loads
        setTimeout(() => {
          setHighlightPlan(urlHighlight)
          setTimeout(() => setHighlightPlan(null), 6000)
        }, 2000)
      }
      setSearchParams({}, { replace: true })
    }
  }, [searchParams])

  useEffect(() => { loadTab(tab) }, [tab])
  useEffect(() => {
    const base = import.meta.env.VITE_API_URL || ''
    fetch(`${base}/api/exchange-rates`, { headers: { 'ngrok-skip-browser-warning': 'true' } })
      .then(r => r.json())
      .then(d => {
        setUsdRate(d.usd)
        setEurRate(d.eur)
        if (d.gbp) {
          setGbpRate(d.gbp)
        } else {
          // Flask not yet updated — fetch GBP→ILS directly
          fetch('https://open.er-api.com/v6/latest/GBP')
            .then(r2 => r2.json())
            .then(d2 => { if (d2.rates?.ILS) setGbpRate(d2.rates.ILS) })
            .catch(() => {})
        }
      })
      .catch(() => {})
  }, [])

  // Fetch market movers once to build the trend badge map
  useEffect(() => {
    api.getMarketMovers(7, 20)
      .then(res => {
        const map = new Map()
        for (const m of res?.movers || []) {
          map.set(`${m.carrier}|${m.plan_name}`, { pct_change: m.pct_change })
        }
        setTrendMap(map)
      })
      .catch(() => {})
  }, [])

  const toggleCompare = useCallback((plan, planType) => {
    const key = `${plan.carrier}|${plan.plan_name}|${planType}`
    setCompareMap(prev => {
      const next = new Map(prev)
      if (next.has(key)) next.delete(key)
      else if (next.size < 4) next.set(key, { plan, planType })
      return next
    })
  }, [])

  // Load a saved compare set: resolve plan refs to live plan objects from current state
  const applyCompareSet = useCallback(async (planRefs) => {
    const next = new Map()
    // Make sure all plan-type buckets are loaded
    const types = [...new Set(planRefs.map(r => r.plan_type))]
    const fetchPromises = []
    if (types.includes('domestic') && plans.domestic.length === 0) fetchPromises.push(api.getPlans().then(p => ({ k: 'domestic', p })))
    if (types.includes('abroad')   && plans.abroad.length === 0)   fetchPromises.push(api.getAbroadPlans().then(p => ({ k: 'abroad', p })))
    if (types.includes('global')   && plans.global.length === 0)   fetchPromises.push(api.getGlobalPlans().then(p => ({ k: 'global', p })))
    if (fetchPromises.length > 0) {
      const results = await Promise.all(fetchPromises)
      const updates = {}
      for (const r of results) updates[r.k] = r.p
      setPlans(prev => ({ ...prev, ...updates }))
      // Use newly fetched data for resolution
      for (const ref of planRefs) {
        const pool = updates[ref.plan_type] || plans[ref.plan_type] || []
        const found = pool.find(p => p.carrier === ref.carrier && p.plan_name === ref.plan_name)
        if (found) {
          const k = `${found.carrier}|${found.plan_name}|${ref.plan_type}`
          next.set(k, { plan: found, planType: ref.plan_type })
        }
      }
    } else {
      for (const ref of planRefs) {
        const pool = plans[ref.plan_type] || []
        const found = pool.find(p => p.carrier === ref.carrier && p.plan_name === ref.plan_name)
        if (found) {
          const k = `${found.carrier}|${found.plan_name}|${ref.plan_type}`
          next.set(k, { plan: found, planType: ref.plan_type })
        }
      }
    }
    setCompareMap(next)
    setShowCompareDrawer(true)
  }, [plans])

  async function loadTab(t) {
    setLoading(true)
    try {
      if (t === 'domestic' && plans.domestic.length === 0) {
        const [p, c] = await Promise.all([api.getPlans(), api.getChanges()])
        setPlans(prev => ({ ...prev, domestic: p }))
        setChanges(prev => ({ ...prev, domestic: c }))
        if (p.length) {
          const times = p.map(x => x.scraped_at).filter(Boolean).sort()
          setLastUpdate(times.at(-1))
        }
      } else if (t === 'abroad' && plans.abroad.length === 0) {
        const [p, c] = await Promise.all([api.getAbroadPlans(), api.getAbroadChanges()])
        setPlans(prev => ({ ...prev, abroad: p }))
        setChanges(prev => ({ ...prev, abroad: c }))
      } else if (t === 'global' && plans.global.length === 0) {
        const [p, c] = await Promise.all([api.getGlobalPlans(), api.getGlobalChanges()])
        setPlans(prev => ({ ...prev, global: p }))
        setChanges(prev => ({ ...prev, global: c }))
      } else if (t === 'resellers' && plans.resellers.length === 0) {
        const p = await api.getResellerPlans()
        // Tag each plan with its underlying carrier label and reseller name in extras for PlanCard rendering
        const enriched = p.map(plan => {
          const reseller = RESELLERS.find(r => r.id === plan.reseller_id)
          const resellerLabel = reseller ? reseller.label : plan.reseller_id
          const tag = `משווק: ${resellerLabel}`
          return { ...plan, extras: [tag, ...(plan.extras || [])] }
        })
        setPlans(prev => ({ ...prev, resellers: enriched }))
      } else if (t === 'content' && plans.content.length === 0) {
        const p = await api.getContentPlans()
        setPlans(prev => ({ ...prev, content: p }))
      } else if (t === 'banners' && !bannersLoaded) {
        const data = await api.getBanners()
        setBanners(data)
        setBannersLoaded(true)
      }
      if (t === 'banners' && !storeBannersLoaded) {
        const data = await api.getStoreBanners()
        setStoreBanners(data)
        setStoreBannersLoaded(true)
      }
    } catch (err) { console.error(err) }
    setLoading(false)
  }

  // Build change lookup
  const changeLookup = useMemo(() => {
    const key = tab === 'content' ? 'content' : tab
    const lookup = {}
    const cutoff = new Date(Date.now() - (tab === 'domestic' ? 24 : 168) * 60 * 60 * 1000).toISOString()
    ;(changes[key] || []).forEach(c => {
      if (c.changed_at >= cutoff) {
        const k = `${c.carrier}|${c.plan_name}`
        lookup[k] = c.change_type
      }
    })
    return lookup
  }, [changes, tab])

  // Filter + sort plans
  const filteredPlans = useMemo(() => {
    let result = plans[tab] || []
    const f = filters

    // Apply workspace visible_carriers scoping on domestic + abroad tabs
    if ((tab === 'domestic' || tab === 'abroad') && visibleCarrierIds.length < CARRIERS.length) {
      result = result.filter(p => visibleCarrierIds.includes(p.carrier))
    }

    if (tab === 'domestic' || tab === 'abroad') {
      if (f.carrier !== 'all') result = result.filter(p => p.carrier === f.carrier)
    }
    if (tab === 'domestic' && f.gen !== 'all') {
      // "5G" = basic 5G only (excludes priority); "5G מתועדף" = priority only
      if (f.gen === '5g') result = result.filter(p => has5G(p) && !hasMaxPriority(p))
      if (f.gen === '5g_priority') result = result.filter(hasMaxPriority)
      if (f.gen === '4g') result = result.filter(p => !has5G(p))
    }
    if (tab === 'domestic' && f.roaming === 'yes') {
      // Accept either a quantified data note ("1GB גלישה בחו\"ל בכל חודש") OR a
      // qualitative "חו\"ל כלול"-style tag (premium plans share total data pool).
      result = result.filter(p => p.extras && p.extras.some(e => {
        const hasIntl = /חו"ל|חו״ל/.test(e)
        if (!hasIntl) return false
        const hasQuantifiedData = /\d+/.test(e) && /GB|גלישה/i.test(e)
        const hasIncludedTag = /(?:כלול(?:ה|ים)?|כולל)/.test(e)
        return hasQuantifiedData || hasIncludedTag
      }))
    }
    if (tab === 'global') {
      if (f.globalProvider !== 'all') {
        const ids = f.globalProvider === 'airalo' ? ['airalo', 'airalo_local', 'airalo_regional'] : [f.globalProvider]
        result = result.filter(p => ids.includes(p.carrier))
      }
      if (f.region !== 'all') result = result.filter(p => p.extras && normalizeRegionLabel(p.extras[0]) === f.region)
      else if (f.destination !== 'all') result = result.filter(p => {
        if (MULTI_COUNTRY_CARRIERS.has(p.carrier)) {
          const coverage = getPlanCoverage(p)
          if (coverage) return coverage.includes(f.destination)
          // single-country plan from a multi-country carrier — match directly
          return p.extras && p.extras[0] === f.destination
        }
        return p.extras && p.extras[0] === f.destination
      })
    }
    if (tab === 'content') {
      const NA = ['לא נמצא', 'שגיאה', 'לא זמין']
      if (f.contentCarrier !== 'all') result = result.filter(p => p.carrier === f.contentCarrier)
      if (f.contentService !== 'all') result = result.filter(p => p.service === f.contentService)
      result = result.filter(p => !p.price || !NA.some(v => String(p.price).includes(v)))
    }
    if (tab === 'resellers') {
      if (f.reseller !== 'all') result = result.filter(p => p.reseller_id === f.reseller)
      if (f.carrier !== 'all') result = result.filter(p => p.carrier === f.carrier)
    }

    if (f.gb !== 'all' && tab !== 'content') {
      if (f.gb === 'unlimited') result = result.filter(p => p.data_gb === null)
      else if (f.gb === '0-5') result = result.filter(p => p.data_gb !== null && p.data_gb <= 5)
      else if (f.gb === '5-15') result = result.filter(p => p.data_gb !== null && p.data_gb > 5 && p.data_gb <= 15)
      else if (f.gb === '15-100') result = result.filter(p => p.data_gb !== null && p.data_gb > 15 && p.data_gb <= 100)
      else if (f.gb === '100+') result = result.filter(p => p.data_gb !== null && p.data_gb > 100)
    }

    if (f.days !== 'all' && (tab === 'abroad' || tab === 'global')) {
      if (f.days === '1-7') result = result.filter(p => p.days && p.days <= 7)
      else if (f.days === '8-14') result = result.filter(p => p.days && p.days > 7 && p.days <= 14)
      else if (f.days === '15-30') result = result.filter(p => p.days && p.days > 14 && p.days <= 30)
      else if (f.days === '30+') result = result.filter(p => p.days && p.days > 30)
    }

    if (onlyWatched) {
      result = result.filter(p => isWatched({
        carrier: p.carrier,
        plan_name: p.plan_name || p.service || '',
        plan_type: tab,
      }))
    }

    const ppgb = (p) => {
      const pr = Number(p.price)
      const gb = Number(p.data_gb)
      if (!pr || !gb || gb <= 0) return null
      return pr / gb
    }
    if (f.sort === 'price_asc') result = [...result].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    else if (f.sort === 'price_desc') result = [...result].sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
    else if (f.sort === 'gb_asc') result = [...result].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
    else if (f.sort === 'gb_desc') result = [...result].sort((a, b) => (b.data_gb ?? 99999) - (a.data_gb ?? 99999))
    else if (f.sort === 'ppgb_asc') result = [...result].sort((a, b) => (ppgb(a) ?? 9999) - (ppgb(b) ?? 9999))
    else if (f.sort === 'ppgb_desc') result = [...result].sort((a, b) => (ppgb(b) ?? 0) - (ppgb(a) ?? 0))

    return result
  }, [plans, tab, filters, onlyWatched, watchItems, isWatched])

  // Group plans into display items (GroupedPlanCard or PlanCard) for global tab
  const displayItems = useMemo(() => {
    if (tab !== 'global') return filteredPlans.map(p => ({ isGroup: false, plan: p }))
    const grouped = new Map()
    const singles = []
    for (const plan of filteredPlans) {
      const dest = plan.extras?.[0]
      if (dest) {
        // bytesim: group by product label (plan_name minus last 2 parts) to separate MAX/UK+/Lite
        // besim: same — multiple bundles share extras[0] (4× אסיה, 2× אירופה, 2× גלובלי).
        //        Group by plan_name prefix so each bundle gets its own card.
        // airalo: split Discover (data only) vs Discover+ (data+calls+sms) like Airalo's website tabs
        let key
        if (plan.carrier === 'bytesim' || plan.carrier === 'besim') {
          const parts = plan.plan_name?.split(' – ') || []
          const productLabel = parts.slice(0, -2).join(' – ') || dest
          key = `${plan.carrier}|${productLabel}`
        } else if (plan.carrier === 'airalo') {
          const operator = (plan.plan_name || '').includes('Discover+') ? 'Discover+' : 'Discover'
          key = `airalo|${dest}|${operator}`
        } else {
          key = `${plan.carrier}|${dest}`
        }
        if (!grouped.has(key)) grouped.set(key, [])
        grouped.get(key).push(plan)
      } else {
        singles.push({ isGroup: false, plan })
      }
    }
    const result = []
    for (const [, plans] of grouped) {
      if (plans.length <= 1) {
        result.push({ isGroup: false, plan: plans[0] })
      } else {
        const byGb = new Map()
        for (const p of plans) {
          // bytesim/maya/besim: keep all (data × days) combinations; other carriers: keep cheapest per GB.
          // Besim's Global bundles have e.g. 1GB/7d AND 1GB/365d — both need to show.
          // Unlimited plans (data_gb null) are differentiated by days so VOYE-style
          // 3GB/יום × {3,7,10,15,20,30}-day variants don't collapse into one card.
          const keepAll = p.carrier === 'bytesim' || p.carrier === 'maya' || p.carrier === 'besim'
          const isUnlimited = p.data_gb == null
          const gbKey = keepAll
            ? p.plan_name
            : (isUnlimited ? `unl-${p.days ?? 0}` : p.data_gb)
          if (!byGb.has(gbKey) || (!keepAll && p.price < byGb.get(gbKey).price)) byGb.set(gbKey, p)
        }
        const unique = [...byGb.values()].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
        // bytesim/besim: destination shown as product label extracted from plan_name
        // airalo: destination shows Discover vs Discover+ to mirror Airalo's site tabs
        let destination
        if (unique[0].carrier === 'bytesim' || unique[0].carrier === 'besim') {
          const parts = unique[0].plan_name?.split(' – ') || []
          destination = parts.slice(0, -2).join(' – ') || unique[0].extras[0]
        } else if (unique[0].carrier === 'airalo') {
          const isPlus = (unique[0].plan_name || '').includes('Discover+')
          const opLabel = isPlus ? 'Airalo Discover+ — דאטה ושיחות' : 'Airalo Discover — דאטה'
          destination = `${opLabel} (${unique[0].extras[0]})`
        } else {
          destination = unique[0].extras[0]
        }
        result.push({ isGroup: true, carrier: unique[0].carrier, destination, plans: unique })
      }
    }
    return [...result, ...singles]
  }, [filteredPlans, tab])

  // Regions for global tab
  const globalRegions = useMemo(() => {
    if (tab !== 'global') return []
    let src = plans.global
    if (filters.globalProvider !== 'all') {
      const ids = filters.globalProvider === 'airalo' ? ['airalo', 'airalo_local', 'airalo_regional'] : [filters.globalProvider]
      src = src.filter(p => ids.includes(p.carrier))
    }
    return [...new Set(
      src
        .filter(p => p.extras && p.extras[0] && (KNOWN_REGIONS.has(p.extras[0]) || isLargeMultiCountryRegion(p.extras[0])))
        .map(p => normalizeRegionLabel(p.extras[0]))
    )].sort((a, b) => a.localeCompare(b, 'he'))
  }, [plans.global, tab, filters.globalProvider])

  // Destinations for global tab
  const globalDestinations = useMemo(() => {
    if (tab !== 'global') return []
    let src = plans.global
    if (filters.globalProvider !== 'all') {
      const ids = filters.globalProvider === 'airalo' ? ['airalo', 'airalo_local', 'airalo_regional'] : [filters.globalProvider]
      src = src.filter(p => ids.includes(p.carrier))
    }
    const destSet = new Set()
    for (const p of src) {
      if (MULTI_COUNTRY_CARRIERS.has(p.carrier)) {
        const coverage = getPlanCoverage(p)
        if (coverage) {
          for (const c of coverage) destSet.add(c)
        } else if (p.extras && p.extras[0] && !/\d/.test(p.extras[0]) && !KNOWN_REGIONS.has(p.extras[0])) {
          // single-country plan from a multi-country carrier — add directly
          destSet.add(p.extras[0])
        }
      } else if (p.extras && p.extras[0] && !/\d/.test(p.extras[0]) && !KNOWN_REGIONS.has(p.extras[0])) {
        destSet.add(p.extras[0])
      }
    }
    return [...destSet].sort((a, b) => a.localeCompare(b, 'he'))
  }, [plans.global, tab, filters.globalProvider])

  // Content services list
  const contentServices = useMemo(() => {
    return [...new Set(plans.content.map(p => p.service).filter(Boolean))]
  }, [plans.content])

  const handleScrape = () => triggerScrape()

  const setFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setVisibleCount(50)
  }

  const resetFilters = () => {
    setFilters({ carrier: 'all', gb: 'all', sort: 'price_asc', gen: 'all', roaming: 'all',
      globalProvider: 'all', destination: 'all', region: 'all', days: 'all',
      contentCarrier: 'all', contentService: 'all' })
    setVisibleCount(50)
  }

  // Provider stats — shown when a single carrier/provider is selected
  const providerStats = useMemo(() => {
    const active =
      ((tab === 'domestic' || tab === 'abroad') && filters.carrier !== 'all') ||
      (tab === 'global' && filters.globalProvider !== 'all')
    if (!active || filteredPlans.length === 0) return null
    const prices = filteredPlans.map(p => Number(p.price)).filter(p => p > 0)
    if (prices.length === 0) return null
    const avg = prices.reduce((a, b) => a + b, 0) / prices.length
    const min = Math.min(...prices)
    return { count: filteredPlans.length, avg, min }
  }, [filteredPlans, filters, tab])

  const exportToExcel = useCallback(async () => {
    if (!filteredPlans.length) return
    // Dynamic-import xlsx (~80KB) only when user clicks export
    const XLSX = await import('xlsx')
    const TAB_NAMES = { domestic: 'חבילות סלולר', abroad: 'חו"ל', global: 'גלובלי', content: 'תוכן' }
    const CARRIER_HEB = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks', travelsim: 'Travel Sim', gomoworld: 'GoMoWorld', tasim: 'Tasim', maya: 'Maya Mobile', bcengi: 'Bcengi', esim70: 'eSIM70', jetpack: 'Jetpack', breez: 'Breez' }
    const GB_HEB = { 'all': 'הכל', '0-5': '0-5GB', '5-15': '5-15GB', '15-100': '15-100GB', '100+': '100+GB', 'unlimited': 'ללא הגבלה' }
    const DAYS_HEB = { 'all': 'הכל', '1-7': '1-7 ימים', '8-14': '8-14 ימים', '15-30': '15-30 ימים', '30+': '30+ ימים' }

    // Build filter summary title
    const parts = [`קטגוריה: ${TAB_NAMES[tab]}`]
    if (filters.carrier !== 'all') parts.push(`ספק: ${CARRIER_HEB[filters.carrier] || filters.carrier}`)
    if (filters.globalProvider !== 'all') parts.push(`ספק: ${CARRIER_HEB[filters.globalProvider] || filters.globalProvider}`)
    if (filters.region !== 'all') parts.push(`אזור: ${filters.region}`)
    if (filters.destination !== 'all') parts.push(`מדינה: ${filters.destination}`)
    if (filters.gb !== 'all') parts.push(`גלישה: ${GB_HEB[filters.gb] || filters.gb}`)
    if (filters.days !== 'all') parts.push(`תקופה: ${DAYS_HEB[filters.days] || filters.days}`)
    if (filters.gen !== 'all') parts.push(`דור: ${filters.gen === '5g' ? 'דור 5' : 'דור 4'}`)
    if (filters.roaming === 'yes') parts.push('כולל חו"ל')
    if (filters.contentService !== 'all') parts.push(`שירות: ${filters.contentService}`)
    const filterTitle = parts.join(' | ')

    // Build rows — fixed columns only
    const rows = filteredPlans.map(p => ({
      'ספק': CARRIER_HEB[p.carrier] || p.carrier,
      'שם חבילה': p.plan_name || p.service || '',
      'מחיר ₪': typeof p.price === 'string' ? p.price.replace('₪', '') : p.price,
      'גלישה GB': p.data_gb === null ? 'ללא הגבלה' : p.data_gb,
      'ימים': p.days || '',
      'דקות': p.minutes || '',
      'SMS': p.sms || '',
    }))

    // Create sheet with title row first
    const ws = XLSX.utils.aoa_to_sheet([[filterTitle], [`${filteredPlans.length} חבילות | ${new Date().toLocaleDateString('he-IL')}`], []])
    // Merge title row across all columns
    ws['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 6 } }, { s: { r: 1, c: 0 }, e: { r: 1, c: 6 } }]
    // Append data rows starting at row 4
    XLSX.utils.sheet_add_json(ws, rows, { origin: 'A4' })
    // Column widths
    ws['!cols'] = [{ wch: 15 }, { wch: 35 }, { wch: 12 }, { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 10 }]

    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, TAB_NAMES[tab] || tab)
    XLSX.writeFile(wb, `mass-market-${tab}-${new Date().toISOString().slice(0, 10)}.xlsx`)
  }, [filteredPlans, tab, filters])

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 pb-20 md:pb-6">
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          {lastUpdate && (
            <p className="text-[11px] text-gray-400">
              עדכון: {new Date(lastUpdate).toLocaleDateString('he-IL')} {lastUpdate.slice(11, 16)}
            </p>
          )}
          {usdRate && (
            <p className="text-[11px] text-gray-400">שער דולר: ₪{usdRate.toFixed(2)}</p>
          )}
          {eurRate && (
            <p className="text-[11px] text-gray-400">שער אירו: ₪{eurRate.toFixed(2)}</p>
          )}
          {gbpRate && (
            <p className="text-[11px] text-gray-400">שער פאונד: ₪{gbpRate.toFixed(2)}</p>
          )}
        </div>
        {isAdmin && (
          <div className="flex flex-col items-center gap-0.5">
            <button
              onClick={handleScrape}
              disabled={scraping}
              className="inline-flex items-center gap-1 text-[11px] text-moca-sub hover:text-moca-bolt disabled:opacity-50 transition-colors"
            >
              {scraping ? (
                <><svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.22-8.56" /></svg> מעדכן...</>
              ) : (
                <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg> עדכן</>
              )}
            </button>
            {scraping && countdown > 0 && (
              <span className="text-[11px] font-mono font-bold text-moca-bolt">{Math.floor(countdown / 60)}:{(countdown % 60).toString().padStart(2, '0')}</span>
            )}
          </div>
        )}
      </div>

      {/* Live scrape progress — shows during update */}
      {isAdmin && <ScrapeProgressPanel />}

      {/* Competitive snapshot — domestic plans only */}
      {tab === 'domestic' && (
        <CompetitorBoard
          plans={plans.domestic}
          changes={changes.domestic}
          carrierIds={visibleCarrierIds}
          oursCarrier={workspace?.mvno_carrier}
          onRowClick={(carrierId) => {
            setFilter('carrier', carrierId)
            setFiltersOpen(true)
          }}
        />
      )}

      {/* Market movers — only above plan tabs */}
      {['domestic', 'abroad', 'global'].includes(tab) && (
        <MarketMoversWidget
          tab={tab}
          visibleCarriers={tab === 'global' ? [] : visibleCarrierIds}
          onMoverClick={(m) => {
            setTab(m.plan_type)
            if (m.plan_type === 'global') {
              setFilter('globalProvider', m.carrier)
            } else {
              setFilter('carrier', m.carrier)
            }
            setFiltersOpen(true)
            setHighlightPlan(m.plan_name)
            setVisibleCount(5000)
          }}
        />
      )}

      {/* Tabs — slim underline style */}
      <div className="flex justify-center gap-0 mb-6 border-b border-gray-200">
        {visibleTabs.map(t => (
          <button
            key={t.id}
            onClick={() => { setTab(t.id); setVisibleCount(50); setFilter('carrier', 'all'); setFilter('globalProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }}
            className={`relative px-4 py-2.5 text-[13px] font-medium transition-all duration-150
              ${tab === t.id
                ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-2 after:h-[2px] after:bg-moca-bolt after:rounded-full'
                : 'text-moca-muted hover:text-moca-bolt'
              }`}
          >
            <span className="hidden sm:inline-flex items-center gap-1.5">{TAB_ICONS[t.id]}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Filter strip — hidden on banners tab which has no plan filters */}
      <div className="mb-4" style={tab === 'banners' || tab === 'history' || tab === 'news' ? {display:'none'} : undefined}>
        {/* Toggle + results count row */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className="text-xs text-moca-sub hover:text-moca-bolt flex items-center gap-1.5 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
              </svg>
              <span>{filtersOpen ? 'סגור סינון' : 'סינון'}</span>
              {activeFilterCount > 0 && (
                <span className="bg-moca-bolt text-white text-[9px] px-1.5 py-0.5 rounded-full min-w-[16px] text-center">{activeFilterCount}</span>
              )}
            </button>
            {activeFilterCount > 0 && (
              <button
                onClick={resetFilters}
                className="text-xs font-medium bg-moca-bolt text-white px-2.5 py-1 rounded-lg hover:bg-moca-text transition-colors"
              >
                איפוס
              </button>
            )}

            <button
              onClick={() => setOnlyWatched(v => !v)}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-lg border transition-colors ${
                onlyWatched
                  ? 'bg-amber-50 border-amber-300 text-amber-700'
                  : 'bg-white border-moca-border/50 text-moca-sub hover:border-moca-bolt/40'
              }`}
              title={onlyWatched ? 'הצג הכל' : 'הצג רק חבילות במעקב'}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill={onlyWatched ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
              <span>המעקב שלי</span>
              {watchItems.length > 0 && (
                <span className="bg-amber-100 text-amber-700 text-[9px] px-1 py-px rounded-full">{watchItems.length}</span>
              )}
            </button>

            <SavedViewsMenu
              tab={tab}
              filters={filters}
              onApply={(view) => {
                if (view.tab && ['domestic','abroad','global','content'].includes(view.tab)) {
                  setTab(view.tab)
                }
                if (view.filters && typeof view.filters === 'object') {
                  setFilters(f => ({ ...f, ...view.filters }))
                  setVisibleCount(50)
                }
                setFiltersOpen(true)
              }}
            />

            {/* Change dot legend */}
            <div className="flex items-center gap-2 border-r border-moca-border/40 pr-2 mr-1">
              <span className="flex items-center gap-1 text-[10px] text-moca-sub">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block flex-shrink-0" />
                חבילה חדשה
              </span>
              <span className="flex items-center gap-1 text-[10px] text-moca-sub">
                <span className="w-2 h-2 rounded-full bg-red-400 inline-block flex-shrink-0" />
                חבילה הוסרה
              </span>
              <span className="flex items-center gap-1 text-[10px] text-moca-sub">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block flex-shrink-0" />
                שינוי מחיר
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[11px] text-gray-400">{tab === 'banners' ? `${banners.length} ספקים` : tab === 'global' ? `${displayItems.length} כרטיסים` : `${filteredPlans.length} חבילות`}</span>
            {filteredPlans.length > 0 && (
              <button onClick={exportToExcel} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-moca-sub hover:text-moca-text hover:bg-moca-cream transition-all duration-150" title="ייצוא ל-Excel">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                Excel
              </button>
            )}
          </div>
        </div>

        {/* Expandable filter rows — 2-column layout */}
        {filtersOpen && (
          <div className="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-3 py-3 border-t border-gray-100 animate-slide-down items-start relative" style={{overflow: 'visible'}}>
            {/* Right column — Filters */}
            <div className="space-y-2" style={{overflow: 'visible'}}>
              {/* Domestic: Row 1 = גלישה | גלישה בחו"ל */}
              {tab === 'domestic' && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">גלישה</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '0-5', '5-15', '15-100', '100+', 'unlimited'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? 'הכל' : v === 'unlimited' ? 'ללא הגבלה' : `${v}GB`} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
                      ))}
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">גלישה בחו"ל</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label="כולם" active={filters.roaming === 'all'} onClick={() => setFilter('roaming', 'all')} />
                      <FilterTag label='כולל חו"ל' active={filters.roaming === 'yes'} onClick={() => setFilter('roaming', 'yes')} />
                    </div>
                  </div>
                </div>
              )}

              {/* Domestic: Row 2 = דור רשת | מיון */}
              {tab === 'domestic' && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">דור רשת</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label="כולם" active={filters.gen === 'all'} onClick={() => setFilter('gen', 'all')} />
                      <FilterTag label="4G" active={filters.gen === '4g'} onClick={() => setFilter('gen', '4g')} />
                      <FilterTag label="5G" active={filters.gen === '5g'} onClick={() => setFilter('gen', '5g')} />
                      <FilterTag label="5G מתועדף" active={filters.gen === '5g_priority'} onClick={() => setFilter('gen', '5g_priority')} />
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">מיון</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label="מחיר ↑" active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
                      <FilterTag label="מחיר ↓" active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
                      <FilterTag label="GB ↑" active={filters.sort === 'gb_asc'} onClick={() => setFilter('sort', 'gb_asc')} />
                      <FilterTag label="GB ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
                      <FilterTag label="₪/GB ↑" active={filters.sort === 'ppgb_asc'} onClick={() => setFilter('sort', 'ppgb_asc')} />
                      <FilterTag label="₪/GB ↓" active={filters.sort === 'ppgb_desc'} onClick={() => setFilter('sort', 'ppgb_desc')} />
                    </div>
                  </div>
                </div>
              )}

              {/* Global: Row 1 = אזור | מדינה */}
              {tab === 'global' && (globalRegions.length > 0 || globalDestinations.length > 0) && (
                <div className="grid grid-cols-2 gap-3">
                  {globalRegions.length > 0 && (
                    <div className="border border-moca-border/60 rounded-xl p-2.5">
                      <p className="text-[11px] font-medium text-gray-500 mb-1">אזור</p>
                      <SearchableSelect
                        value={filters.region}
                        onChange={val => { setFilter('region', val); if (val !== 'all') setFilter('destination', 'all') }}
                        options={globalRegions.map(r => ({ value: r, label: r }))}
                        placeholder={`כל האזורים (${globalRegions.length})`}
                      />
                    </div>
                  )}
                  {globalDestinations.length > 0 && (
                    <div className="border border-moca-border/60 rounded-xl p-2.5">
                      <p className="text-[11px] font-medium text-gray-500 mb-1">מדינה</p>
                      <SearchableSelect
                        value={filters.destination}
                        onChange={val => { setFilter('destination', val); if (val !== 'all') setFilter('region', 'all') }}
                        options={globalDestinations.map(c => ({ value: c, label: c }))}
                        placeholder={`כל המדינות (${globalDestinations.length})`}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Abroad/Global: Row 2 = גלישה | תוקף */}
              {(tab === 'abroad' || tab === 'global') && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">גלישה</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '0-5', '5-15', '15-100', '100+', 'unlimited'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? 'הכל' : v === 'unlimited' ? 'ללא הגבלה' : `${v}GB`} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
                      ))}
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">תוקף</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '1-7', '8-14', '15-30', '30+'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? 'הכל' : `${v} ימים`} active={filters.days === v} onClick={() => setFilter('days', v)} />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Abroad/Global: Sort row — same FilterTag style */}
              {(tab === 'abroad' || tab === 'global') && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <p className="text-[11px] font-medium text-gray-500 mb-1.5">מיון</p>
                  <div className="flex flex-wrap gap-1">
                    <FilterTag label="מחיר ↑" active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
                    <FilterTag label="מחיר ↓" active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
                    <FilterTag label="GB ↑" active={filters.sort === 'gb_asc'} onClick={() => setFilter('sort', 'gb_asc')} />
                    <FilterTag label="GB ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
                  </div>
                </div>
              )}

              {/* Content service filter (content tab) */}
              {tab === 'content' && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <p className="text-[11px] font-medium text-gray-500 mb-1.5">שירות</p>
                  <div className="flex flex-wrap gap-1">
                    <FilterTag label="כולם" active={filters.contentService === 'all'} onClick={() => setFilter('contentService', 'all')} />
                    {contentServices.map(s => (
                      <FilterTag key={s} label={s} active={filters.contentService === s} onClick={() => setFilter('contentService', s)} />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Left column — Carriers/Providers */}
            <div>
              {/* Domestic / Abroad carriers */}
              {(tab === 'domestic' || tab === 'abroad') && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[11px] font-medium text-gray-500">ספקים</p>
                    <button
                      onClick={() => setFilter('carrier', 'all')}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.carrier === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      כולם
                    </button>
                  </div>
                  <div className={`grid gap-1 ${tab === 'domestic' || tab === 'abroad' ? 'grid-cols-2' : 'grid-cols-4'}`}>
                    {(tab === 'abroad' ? CARRIERS.filter(c => c.id !== 'xphone' && c.id !== 'neptucom') : CARRIERS)
                      .filter(c => visibleCarrierIds.includes(c.id))
                      .map(c => {
                      const cnt = plans[tab]?.filter(p => p.carrier === c.id).length || 0
                      return (
                        <button
                          key={c.id}
                          onClick={() => cnt > 0 ? setFilter('carrier', c.id) : null}
                          className={`px-1 py-1 rounded-md text-[10px] font-medium text-center transition-all duration-150 truncate ${
                            filters.carrier === c.id ? 'bg-gray-900 text-white' :
                            cnt === 0 ? 'text-moca-border cursor-default' :
                            'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                          }`}
                        >
                          {c.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Global providers */}
              {tab === 'global' && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[11px] font-medium text-gray-500">ספקים</p>
                    <button
                      onClick={() => { setFilter('globalProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.globalProvider === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      כולם
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    {GLOBAL_PROVIDERS.map(p => {
                      const cnt = plans.global?.filter(x => x.carrier === p.id).length || 0
                      if (!cnt) return null
                      return (
                        <button
                          key={p.id}
                          onClick={() => { setFilter('globalProvider', p.id); setFilter('destination', 'all'); setFilter('region', 'all') }}
                          className={`px-1 py-1 rounded-md text-[10px] font-medium text-center transition-all duration-150 ${
                            filters.globalProvider === p.id ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                          }`}
                        >
                          {p.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Content carriers */}
              {tab === 'content' && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[11px] font-medium text-gray-500">ספקים</p>
                    <button
                      onClick={() => setFilter('contentCarrier', 'all')}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.contentCarrier === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      כולם
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1">
                    {['cellcom', 'partner', 'hotmobile', 'pelephone', 'wecom', 'golan'].map(c => (
                      <button
                        key={c}
                        onClick={() => setFilter('contentCarrier', c)}
                        className={`px-1 py-1 rounded-md text-[10px] font-medium text-center transition-all duration-150 truncate ${
                          filters.contentCarrier === c ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                        }`}
                      >
                        {CARRIERS.find(x => x.id === c)?.label || c}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Resellers */}
              {tab === 'resellers' && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[11px] font-medium text-gray-500">משווקים</p>
                    <button
                      onClick={() => setFilter('reseller', 'all')}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.reseller === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      כולם
                    </button>
                  </div>
                  <div className="grid grid-cols-1 gap-1">
                    {RESELLERS.map(r => {
                      const cnt = plans.resellers?.filter(p => p.reseller_id === r.id).length || 0
                      return (
                        <button
                          key={r.id}
                          onClick={() => cnt > 0 ? setFilter('reseller', r.id) : null}
                          className={`px-1 py-1 rounded-md text-[10px] font-medium text-center transition-all duration-150 truncate ${
                            filters.reseller === r.id ? 'bg-gray-900 text-white' :
                            cnt === 0 ? 'text-moca-border cursor-default' :
                            'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                          }`}
                        >
                          {r.label} {cnt > 0 ? `(${cnt})` : ''}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-20"><Spinner /></div>
      )}

      {/* Provider stats strip — when single carrier/provider selected */}
      {!loading && providerStats && (
        <div className="mb-3 flex items-center gap-3 px-1 text-sm text-right flex-wrap" dir="rtl">
          <span className="text-gray-500">{providerStats.count} חבילות</span>
          <span className="text-gray-300">·</span>
          <span className="text-gray-500">ממוצע: <strong className="text-gray-700">&#8362;{providerStats.avg.toFixed(0)}</strong></span>
          <span className="text-gray-300">·</span>
          <span className="text-gray-500">מינימום: <strong className="text-emerald-600">&#8362;{providerStats.min}</strong></span>
          <div className="mr-auto">
            <CarrierAIInsights carrierId={tab === 'global' ? filters.globalProvider : filters.carrier} />
          </div>
        </div>
      )}

      {/* Plan cards grid */}
      {!loading && tab !== 'content' && tab !== 'banners' && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {displayItems.slice(0, visibleCount).map((item, i) => {
              if (item.isGroup) {
                const repPlan = item.plans[0]
                const groupKey = `${item.carrier}|${repPlan.plan_name}`
                const groupCompareKey = `${groupKey}|${tab}`
                return (
                  <GroupedPlanCard
                    key={`group-${item.carrier}-${item.destination}`}
                    carrier={item.carrier}
                    destination={item.destination}
                    plans={item.plans}
                    trendInfo={trendMap.get(groupKey) || null}
                    isInCompare={compareMap.has(groupCompareKey)}
                    onCompareToggle={toggleCompare}
                    repPlan={repPlan}
                    tabId={tab}
                  />
                )
              }
              const plan = item.plan
              const key = `${plan.carrier}|${plan.plan_name}`
              const compareKey = `${key}|${tab}`
              return (
                <PlanCard
                  key={key + i}
                  plan={plan}
                  type={tab}
                  changeType={changeLookup[key]}
                  trendInfo={trendMap.get(key) || null}
                  isInCompare={compareMap.has(compareKey)}
                  onCompareToggle={toggleCompare}
                  highlighted={highlightPlan && (() => {
                    const h = highlightPlan.toLowerCase().replace(/[\s\-–]+/g, ' ')
                    const name = (plan.plan_name || '').toLowerCase().replace(/[\s\-–]+/g, ' ')
                    if (plan.carrier === highlightPlan) return true
                    if (name.includes(h)) return true
                    if (h.length > 5 && name.includes(h.slice(0, 15))) return true
                    const firstWord = h.split(' ')[0]
                    if (firstWord.length > 2 && name.includes(firstWord)) return true
                    return false
                  })()}
                />
              )
            })}
          </div>
          {visibleCount < displayItems.length && (
            <div className="text-center mt-4">
              <button
                onClick={() => setVisibleCount(prev => prev + 500)}
                className="text-sm text-moca-bolt hover:text-moca-dark px-4 py-2 rounded-lg border border-moca-border hover:bg-moca-cream transition-colors"
              >
                {'\u05D4\u05E6\u05D2 \u05E2\u05D5\u05D3'} ({displayItems.length - visibleCount} {'\u05E0\u05D5\u05E1\u05E4\u05D9\u05DD'})
              </button>
            </div>
          )}
        </>
      )}

      {/* Content: grouped by service */}
      {!loading && tab === 'content' && (() => {
        const services = [...new Set(filteredPlans.map(p => p.service).filter(Boolean))]
        const NA = ['לא נמצא', 'שגיאה', 'לא זמין']
        return services.map(svc => {
          const svcPlans = filteredPlans.filter(p => p.service === svc)
            .filter(p => !(p.price && NA.some(v => String(p.price).includes(v))))
          if (!svcPlans.length) return null
          return (
            <div key={svc} className="mb-8">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 pb-2 border-b border-gray-100">{svc}</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {svcPlans.map((plan, i) => {
                  const key = `${plan.service}|${plan.carrier}`
                  return (
                    <PlanCard
                      key={key + i}
                      plan={plan}
                      type="content"
                      changeType={changeLookup[key]}
                    />
                  )
                })}
              </div>
            </div>
          )
        })
      })()}

      {!loading && tab === 'banners' && (
        <div>
          {/* info strip */}
          <div className="mb-4 px-1 flex items-center gap-2 text-xs text-moca-muted">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" />
            </svg>
            <span>צילומי מסך אוטומטיים של עמודי הבית והחנות של הספקים - מתעדכנים כל יום בשעה 08:00</span>
          </div>

          {bannersLoaded && banners.length === 0 && (
            <div className="text-center text-moca-muted py-16 text-sm">
              אין באנרים זמינים עדיין — הם יצולמו בשעה 08:00
            </div>
          )}

          <h2
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 18,
              fontWeight: 800,
              color: 'var(--color-moca-dark)',
              margin: '0 0 14px',
              letterSpacing: -0.3,
              textAlign: 'right',
            }}
          >
            עמוד ראשי
          </h2>
          <div className="mb-8">
            <BannerMosaic banners={banners} source="home" />
          </div>

          {storeBanners.length > 0 && (
            <>
              <h2
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: 18,
                  fontWeight: 800,
                  color: 'var(--color-moca-dark)',
                  margin: '0 0 14px',
                  letterSpacing: -0.3,
                  textAlign: 'right',
                }}
              >
                חנות ציוד קצה
              </h2>
              <BannerMosaic banners={storeBanners} source="store" />
            </>
          )}
        </div>
      )}

      {tab === 'history' && (
        <Suspense fallback={<div className="flex justify-center py-20"><Spinner /></div>}>
          <HistoryTab />
        </Suspense>
      )}

      {tab === 'news' && (
        <Suspense fallback={<div className="flex justify-center py-20"><Spinner /></div>}>
          <NewsTab />
        </Suspense>
      )}

      {!loading && filteredPlans.length === 0 && tab !== 'banners' && tab !== 'history' && tab !== 'news' && (
        <div className="text-center py-20 text-gray-400">
          <p className="text-3xl mb-3 opacity-40">&#128269;</p>
          <p className="text-sm">לא נמצאו חבילות בסינון הנוכחי</p>
        </div>
      )}

      {/* Country modal */}
      <CountryModal
        open={!!countryModal}
        onClose={() => setCountryModal(null)}
        title={countryModal?.title}
        countries={countryModal?.countries}
      />

      {/* Compare bottom bar — also shows SavedComparesMenu when no plans selected */}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 animate-fade-in">
        {compareMap.size > 0 ? (
          <div className="bg-white rounded-2xl shadow-2xl border border-gray-200 px-5 py-3 flex items-center gap-4" dir="rtl">
            <span className="text-sm font-semibold text-gray-700">{compareMap.size} חבילות נבחרו</span>
            <button
              onClick={() => setShowCompareDrawer(true)}
              className="bg-[#5c3317] hover:bg-[#7a4520] text-white text-sm font-medium px-4 py-1.5 rounded-xl transition-colors"
            >
              השווה
            </button>
            <SavedComparesMenu
              comparePlans={[...compareMap.values()]}
              onApply={applyCompareSet}
            />
            <button
              onClick={() => setCompareMap(new Map())}
              className="text-gray-400 hover:text-red-500 transition-colors text-lg leading-none"
              title="נקה בחירה"
            >
              ✕
            </button>
          </div>
        ) : null}
      </div>

      {/* Compare drawer */}
      {showCompareDrawer && (
        <div className="fixed inset-0 z-[9998] animate-fade-in" onClick={() => setShowCompareDrawer(false)}>
          <div className="fixed inset-0 bg-black/40" />
          <div
            className="fixed inset-x-0 bottom-0 bg-white rounded-t-2xl shadow-2xl max-h-[85vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white border-b border-gray-100 px-5 py-4 flex items-center justify-between" dir="rtl">
              <h2 className="text-base font-bold text-gray-800">השוואת חבילות</h2>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    const win = window.open('', '_blank')
                    const CARRIER_HEB = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', neptucom: 'Neptucom', tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks', voye: 'VOYE', orbit: 'Orbit', travelsim: 'Travel Sim' }
                    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
                    const getExtras = (plan) => {
                      if (!plan.extras) return []
                      const filtered = plan.extras.filter(e => e && typeof e === 'string' && !e.startsWith('__info__|'))
                      if (plan.carrier === 'orbit' && filtered.length > 1) return []
                      return filtered
                    }
                    const getPlanInfo = (plan) => {
                      const marker = plan.extras?.find(e => typeof e === 'string' && e.startsWith('__info__|'))
                      if (marker) return marker.slice('__info__|'.length)
                      return plan.plan_info || null
                    }
                    const html = `<html dir="rtl"><head><meta charset="utf-8"><title>השוואת חבילות — MOCA</title>
<style>body{font-family:Arial,sans-serif;padding:24px;direction:rtl;background:#f9f4ee;color:#1a1a1a}
h1{font-size:20px;font-weight:700;margin-bottom:20px;color:#5c3317}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
.card{background:white;border:1px solid #e5e0d8;border-radius:14px;padding:18px;page-break-inside:avoid;text-align:right}
.carrier{font-size:11px;color:#999;margin-bottom:4px}
.name{font-size:13px;font-weight:600;color:#333;margin-bottom:10px;line-height:1.4}
.price{font-size:28px;font-weight:700;color:#1a1a1a;margin-bottom:4px}
.info{font-size:12px;color:#777;margin-bottom:8px}
.extras{margin-top:10px;padding-top:10px;border-top:1px solid #f0e8dc;list-style:none;padding-right:0}
.extras li{font-size:11px;color:#666;line-height:1.5;padding:2px 0;position:relative;padding-right:14px}
.extras li:before{content:"✦";position:absolute;right:0;color:#c9b893}
.plan-info{margin-top:10px;padding-top:10px;border-top:1px solid #f0e8dc;font-size:11px;color:#666;line-height:1.5;white-space:pre-line}
.plan-info-title{font-size:10px;font-weight:600;color:#5c3317;margin-bottom:4px;text-transform:uppercase}
@media print{body{background:white}.card{break-inside:avoid}}</style></head><body>
<h1>השוואת חבילות — MOCA</h1>
<div class="grid">
${[...compareMap.values()].map(({ plan, planType }) => {
  const extras = getExtras(plan)
  const planInfo = getPlanInfo(plan)
  return `
<div class="card">
  <div class="carrier">${esc(CARRIER_HEB[plan.carrier] || plan.carrier)} · ${planType === 'domestic' ? 'סלולר' : planType === 'abroad' ? 'חו"ל' : 'גלובלי'}</div>
  <div class="name">${esc(plan.plan_name || plan.service || '')}</div>
  <div class="price">₪${esc(plan.price)}</div>
  <div class="info">${plan.data_gb === null ? 'ללא הגבלה' : esc(plan.data_gb || '') + 'GB'}${plan.days ? ' · ' + esc(plan.days) + ' ימים' : ''}${plan.minutes ? ' · ' + esc(plan.minutes) + ' דקות' : ''}${plan.sms ? ' · ' + esc(plan.sms) + ' SMS' : ''}</div>
  ${extras.length > 0 ? `<ul class="extras">${extras.map(e => `<li>${esc(e)}</li>`).join('')}</ul>` : ''}
  ${planInfo ? `<div class="plan-info"><div class="plan-info-title">תנאי התוכנית</div>${esc(planInfo)}</div>` : ''}
</div>`
}).join('')}
</div>
<script>setTimeout(()=>window.print(),300)</script></body></html>`
                    win.document.write(html)
                    win.document.close()
                  }}
                  className="text-xs text-moca-sub hover:text-moca-bolt border border-moca-border/40 rounded-lg px-3 py-1.5 transition-colors hover:bg-moca-cream flex items-center gap-1.5"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>
                    <rect x="6" y="14" width="12" height="8"/>
                  </svg>
                  ייצוא PDF
                </button>
                <button onClick={() => setShowCompareDrawer(false)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&#10005;</button>
              </div>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {[...compareMap.values()].map(({ plan, planType }, i) => (
                  <div key={i} className="relative">
                    <button
                      onClick={() => toggleCompare(plan, planType)}
                      title="הסר מהשוואה"
                      className="absolute -top-2 -right-2 z-10 w-6 h-6 flex items-center justify-center text-white bg-red-500 hover:bg-red-600 rounded-full shadow-md border-2 border-white transition-colors"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                    <PlanCard plan={plan} type={planType} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
