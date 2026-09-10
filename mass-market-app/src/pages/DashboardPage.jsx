import { useState, useEffect, useMemo, useCallback, useRef, startTransition, lazy, Suspense } from 'react'
import { useSearchParams, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useScrape } from '../hooks/useScrape'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { useDashboardPlans } from '../hooks/useDashboardPlans'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
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
import { useLang } from '../hooks/useLanguage'
import { CRUISE_VALUE } from '../data/destI18n'
import { ISRAELI_GLOBAL_PROVIDERS, USA_LABELS, GLOBAL_PROVIDERS } from '../data/carrierLabels'

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
  usa: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3.5c-.5-.5-2.5 0-4 1.5L13.5 8 5.2 6.2c-.5-.1-.9.2-.9.7l.3.5L8 11l-3 1-1 1 .5.5L8 15l1 3.5.5.5 1-1 1-3 3.5 2.7.5.3c.5 0 .8-.4.7-.9z"/>
    </svg>
  ),
}

const TABS = [
  { id: 'domestic', label: 'חבילות סלולר' },
  { id: 'abroad', label: 'חו"ל' },
  { id: 'global', label: 'גלובלי' },
  { id: 'usa', label: 'נוחתים בארה"ב' },
  { id: 'resellers', label: 'משווקים' },
  { id: 'content', label: 'תוכן' },
  { id: 'banners', label: 'באנרים ראשיים' },
  { id: 'history', label: 'היסטוריה' },
  { id: 'news', label: '\u05d1\u05d7\u05d3\u05e9\u05d5\u05ea' },
]

// English display labels for the tab bar (keyed by tab id). Display-only \u2014
// the tab identity is the id; these never feed logic/comparisons.
const TAB_LABELS_EN = {
  domestic: 'Mobile Plans',
  abroad: 'Roaming',
  global: 'Global',
  usa: 'Landing in USA',
  resellers: 'Resellers',
  content: 'Content',
  banners: 'Main Banners',
  history: 'History',
  news: 'News',
}

const RESELLERS = [
  { id: 'pelephon4u',     label: '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df \u05ea\u05e7\u05e9\u05d5\u05e8\u05ea \u05dc\u05de\u05e6\u05d8\u05e8\u05e4\u05d9\u05dd \u05d7\u05d3\u05e9\u05d9\u05dd', underlying: 'pelephone',
    source_url: 'https://pelephon4u.co.il/' },
  { id: 'pelephone_join', label: '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df Join (\u05de\u05d1\u05e6\u05e2\u05d9\u05dd)',          underlying: 'pelephone',
    source_url: 'https://pelephone-join.co.il/\u05e4\u05dc\u05d0\u05e4\u05d5\u05df-\u05de\u05d1\u05e6\u05e2\u05d9\u05dd/' },
  { id: 'cellcomshefamr', label: '\u05e1\u05dc\u05e7\u05d5\u05dd \u05e9\u05e4\u05e8\u05e2\u05dd',                   underlying: 'cellcom',
    source_url: 'https://www.instagram.com/cellcomshefamr/' },
  { id: 'zorro',          label: '\u05d6\u05d5\u05e8\u05d5 \u2014 \u05d4\u05e9\u05d5\u05d5\u05d0\u05d4 \u05d5\u05d4\u05d5\u05d6\u05dc\u05d4 \u05e9\u05dc \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05ea\u05e7\u05e9\u05d5\u05e8\u05ea', underlying: 'partner',
    source_url: 'https://www.facebook.com/ZorroPricesCompare/' },
  { id: 'rami_levy_landing', label: '\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9 \u05ea\u05e7\u05e9\u05d5\u05e8\u05ea \u2014 \u05d3\u05e3 \u05e0\u05d7\u05d9\u05ea\u05d4', underlying: 'rami_levy',
    source_url: 'https://landing-mobile.rami-levy.co.il/landing/' },
  // \u2500\u2500 2026-06-11 web sweep: below-the-line sources (btl_scrapers.py + seed) \u2500\u2500
  { id: 'pelephone_cellphone', label: '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df Deal', underlying: 'pelephone',
    source_url: 'https://pelephone-deal.co.il/' },
  { id: 'tiber',          label: '\u05d8\u05d9\u05d1\u05e8 \u2014 \u05e7\u05d0\u05e9\u05d1\u05e7 (\u05e4\u05dc\u05d0\u05e4\u05d5\u05df/\u05e4\u05e8\u05d8\u05e0\u05e8/\u05d2\u05d5\u05dc\u05df/019)', underlying: 'pelephone',
    source_url: 'https://tiber.co.il/Shop/Details/\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea-\u05e1\u05dc\u05d5\u05dc\u05e8' },
  { id: 'zol_li',         label: '\u05d6\u05d5\u05dc-\u05dc\u05d9 \u2014 \u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc \u05e2\u05e8\u05d5\u05e5 \u05de\u05e9\u05d5\u05d5\u05e7\u05d9\u05dd', underlying: 'hotmobile',
    source_url: 'https://www.zol-li.co.il/\u05d4\u05d5\u05d8-\u05de\u05d5\u05d1\u05d9\u05d9\u05dc-\u05e1\u05dc\u05d5\u05dc\u05e8/' },
  { id: 'kamaze',         label: '\u05db\u05de\u05d4 \u05d6\u05d4 \u2014 \u05de\u05e1\u05dc\u05d5\u05dc\u05d9 \u05de\u05e9\u05d5\u05d5\u05e7\u05d9\u05dd (\u05e1\u05dc\u05e7\u05d5\u05dd/\u05e4\u05e8\u05d8\u05e0\u05e8)', underlying: 'cellcom',
    source_url: 'https://www.kamaze.co.il/' },
  { id: 'kamazeole',      label: '\u05db\u05de\u05d4 \u05d6\u05d4 \u05e2\u05d5\u05dc\u05d4 \u2014 \u05d2\u05d5\u05dc\u05df \u05de\u05e9\u05e4\u05d7\u05ea\u05d9\u05ea', underlying: 'golan',
    source_url: 'https://www.kamazeole.co.il/' },
  { id: 'sell_zoll',      label: 'sell-zoll \u2014 \u05de\u05ea\u05d5\u05d5\u05da \u05e1\u05dc\u05e7\u05d5\u05dd', underlying: 'cellcom',
    source_url: 'https://sell-zoll.co.il/cellular' },
  { id: 'tikshoretishit', label: '\u05ea\u05e7\u05e9\u05d5\u05e8\u05ea \u05d0\u05d9\u05e9\u05d9\u05ea \u2014 \u05d2\u05d5\u05dc\u05df 750GB', underlying: 'golan',
    source_url: 'https://tikshoretishit.co.il/' },
  { id: 'clubdeal',       label: 'ClubDeal \u2014 \u05de\u05d5\u05e2\u05d3\u05d5\u05df \u05e4\u05dc\u05d0\u05e4\u05d5\u05df', underlying: 'pelephone',
    source_url: 'https://clubdeal.co.il/pelephone/' },
  { id: 'partner_site',   label: '\u05e4\u05e8\u05d8\u05e0\u05e8 \u2014 \u05d3\u05e3 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea (\u05ea\u05e0\u05d0\u05d9\u05dd \u05de\u05ea\u05d7\u05ea \u05dc\u05e7\u05d5)', underlying: 'partner',
    source_url: 'https://www.partner.co.il/n/cellularsale/lobby' },
  { id: 'wecom_site',     label: '\u05d5\u05d9-\u05e7\u05d5\u05dd \u2014 \u05e1\u05d9\u05dd \u05d3\u05d0\u05d8\u05d4', underlying: 'wecom',
    source_url: 'https://we-com.co.il/sim-data/' },
  { id: 'rami_levy_hever', label: '\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9 \u2014 \u05de\u05d5\u05e2\u05d3\u05d5\u05df \u05d7\u05d1\u05e8', underlying: 'rami_levy',
    source_url: 'https://mobile.rami-levy.co.il/Home/Hever' },
  { id: 'rami_levy_cc',   label: '\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9 \u2014 \u05d4\u05d8\u05d1\u05ea \u05db\u05e8\u05d8\u05d9\u05e1 \u05d0\u05e9\u05e8\u05d0\u05d9', underlying: 'rami_levy',
    source_url: 'https://mobile.rami-levy.co.il/Home/Landing/' },
  { id: 'pelephone_fb',   label: '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df \u2014 \u05e7\u05de\u05e4\u05d9\u05d9\u05df \u05e4\u05d9\u05d9\u05e1\u05d1\u05d5\u05e7', underlying: 'pelephone',
    source_url: 'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IL&q=\u05e4\u05dc\u05d0\u05e4\u05d5\u05df&search_type=keyword_unordered' },
  { id: 'analizer',       label: '\u05d0\u05e0\u05dc\u05d9\u05d9\u05d6\u05e8 \u2014 \u05de\u05ea\u05d5\u05d5\u05da (\u05e1\u05dc\u05e7\u05d5\u05dd)', underlying: 'cellcom',
    source_url: 'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IL&q=\u05d0\u05e0\u05dc\u05d9\u05d9\u05d6\u05e8&search_type=keyword_unordered' },
]

// US operators on the "\u05e0\u05d5\u05d7\u05ea\u05d9\u05dd \u05d1\u05d0\u05e8\u05d4"\u05d1" tab. `net` groups them by the underlying
// network for the network filter. Order: Big-3 / tourist-dedicated first.
const USA_OPERATORS = [
  { id: 'tmobile_prepaid', label: 'T-Mobile Prepaid', net: 'T-Mobile' },
  { id: 'att_prepaid',     label: 'AT&T Prepaid',     net: 'AT&T' },
  { id: 'verizon_prepaid', label: 'Verizon Prepaid',  net: 'Verizon' },
  { id: 'ultra',           label: 'Ultra Mobile',     net: 'T-Mobile' },
  { id: 'cricket',         label: 'Cricket Wireless', net: 'AT&T' },
  { id: 'h2o',             label: 'H2O Wireless',     net: 'AT&T' },
  { id: 'visible',         label: 'Visible',          net: 'Verizon' },
  { id: 'us_mobile',       label: 'US Mobile',        net: '\u05e8\u05d1-\u05e8\u05e9\u05ea\u05d9' },
  { id: 'red_pocket',      label: 'Red Pocket',       net: '\u05e8\u05d1-\u05e8\u05e9\u05ea\u05d9' },
  { id: 'straight_talk',   label: 'Straight Talk',    net: 'Verizon' },
  { id: 'total_wireless',  label: 'Total Wireless',   net: 'Verizon' },
  { id: 'boost',           label: 'Boost Mobile',     net: 'Boost' },
  { id: 'mint',            label: 'Mint Mobile',      net: 'T-Mobile' },
  { id: 'tello',           label: 'Tello',            net: 'T-Mobile' },
  { id: 'metro',           label: 'Metro by T-Mobile', net: 'T-Mobile' },
  { id: 'lyca_usa',        label: 'Lycamobile USA',   net: 'T-Mobile' },
  { id: 'simple_mobile',   label: 'Simple Mobile',    net: 'Verizon' },
]
const USA_NETWORKS = ['T-Mobile', 'AT&T', 'Verizon', 'Boost', '\u05e8\u05d1-\u05e8\u05e9\u05ea\u05d9']

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

const CARRIER_IDS = CARRIERS.map(c => c.id)

// GLOBAL_PROVIDERS (the global-tab provider filter chips) is derived from the single
// source of truth in data/carrierLabels — add a provider there, not here.

export default function DashboardPage() {
  const { tt, lang } = useLang()
  const { isAdmin, workspace } = useAuth()
  const { scraping, countdown, triggerScrape } = useScrape()
  const visibleCarrierIds = useVisibleCarriers(CARRIER_IDS)
  const flags = useFeatureFlags()
  const { items: watchItems, isWatched } = useWatchlist()
  const [onlyWatched, setOnlyWatched] = useState(false)
  const visibleTabs = useMemo(() => TABS.filter(t => !flags['hide_' + t.id]), [flags])
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()

  // Pathname → locked tab (per phase-9 clean routes /plans /roaming /esim /banners /history).
  // When set, the tab navigation is hidden and the in-page tab can't be switched —
  // the URL is the source of truth.
  const TAB_ROUTES = {
    '/plans':     'domestic',
    '/roaming':   'abroad',
    '/esim':      'global',
    '/usa':       'usa',
    '/resellers': 'resellers',
    '/content':   'content',
    '/news':      'news',
    '/banners':   'banners',
    '/history':   'history',
  }
  const TAB_TO_PATH = {
    domestic:  '/plans',
    abroad:    '/roaming',
    global:    '/esim',
    usa:       '/usa',
    resellers: '/resellers',
    content:   '/content',
    news:      '/news',
    banners:   '/banners',
    history:   '/history',
  }
  const lockedTab = useMemo(() => TAB_ROUTES[location.pathname] || null, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  const [tab, _setTab] = useState(lockedTab || searchParams.get('tab') || 'domestic')

  // When on a locked route, switching tabs has to navigate — otherwise our
  // own useEffect below would snap the tab back to whatever the URL says.
  // Off a locked route we mutate state in place (and let setSearchParams
  // mirror it for legacy bookmarks).
  const setTab = useCallback((nextTab) => {
    if (lockedTab && nextTab !== lockedTab && TAB_TO_PATH[nextTab]) {
      const qs = location.search
      navigate(`${TAB_TO_PATH[nextTab]}${qs}`)
      return
    }
    _setTab(nextTab)
  }, [lockedTab, navigate, location.search]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reflect lockedTab into local state on path change so loadTab() fires.
  useEffect(() => {
    if (lockedTab && tab !== lockedTab) _setTab(lockedTab)
  }, [lockedTab]) // eslint-disable-line react-hooks/exhaustive-deps

  // If active tab gets hidden by feature flags, fall back to first visible tab
  useEffect(() => {
    if (flags['hide_' + tab]) {
      const first = TABS.find(t => !flags['hide_' + t.id])
      if (first) setTab(first.id)
    }
  }, [flags]) // eslint-disable-line react-hooks/exhaustive-deps
  const [loading, setLoading] = useState(true)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [plans, setPlans] = useState({ domestic: [], abroad: [], global: [], content: [], resellers: [], usa: [] })
  const [changes, setChanges] = useState({ domestic: [], abroad: [], global: [], content: [] })
  const [filters, setFilters] = useState({
    carrier: 'all', gb: 'all', sort: 'price_asc', gen: 'all', roaming: 'all',
    globalProvider: 'all', destination: 'all', region: 'all', days: 'all',
    israeliProvider: 'all', contentCarrier: 'all', contentService: 'all', reseller: 'all',
    usaOperator: 'all', usaNetwork: 'all',
  })
  const [countryModal, setCountryModal] = useState(null)
  const [highlightPlan, setHighlightPlan] = useState(null)
  const [usdRate, setUsdRate] = useState(null)
  const [eurRate, setEurRate] = useState(null)
  const [gbpRate, setGbpRate] = useState(null)
  const [visibleCount, setVisibleCount] = useState(50)
  const loadIdRef = useRef(0)  // incremented on every loadTab call; stale loads bail early
  const [trendMap, setTrendMap] = useState(new Map())   // carrier|plan_name → {pct_change}
  const [sparkMap, setSparkMap] = useState(null)        // carrier|plan_name → points[] (batch sparkline data; null until loaded)
  const [compareMap, setCompareMap] = useState(new Map()) // key → {plan, planType}
  const [showCompareDrawer, setShowCompareDrawer] = useState(false)
  const [banners, setBanners] = useState([])
  const [bannersLoaded, setBannersLoaded] = useState(false)
  const [storeBanners, setStoreBanners] = useState([])
  const [storeBannersLoaded, setStoreBannersLoaded] = useState(false)

  // Freshest scrape time of the plans currently shown — drives the "עדכון" stamp.
  // Plan tabs carry scraped_at; content/banners/history/news don't, so it hides there.
  const lastUpdate = useMemo(() => {
    const times = (plans[tab] || []).map(x => x.scraped_at).filter(Boolean)
    return times.length ? times.reduce((a, b) => (a > b ? a : b)) : null
  }, [plans, tab])

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
      if (filters.israeliProvider !== 'all') count++
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
    if (tab === 'usa') {
      if (filters.usaOperator !== 'all') count++
      if (filters.usaNetwork !== 'all') count++
    }
    if (tab !== 'content') {
      if (filters.gb !== 'all') count++
      if (filters.days !== 'all') count++
    }
    return count
  }, [filters, tab])

  // Load data
  // Apply URL params from chat navigation / change-feed clicks.
  // Two URL shapes converge here:
  //   legacy: /?tab=domestic&carrier=partner&highlight=X
  //   clean : /plans?carrier=partner&highlight=X   (tab implicit via lockedTab)
  useEffect(() => {
    const urlTab = searchParams.get('tab')
    const urlCarrier = searchParams.get('carrier')
    const urlHighlight = searchParams.get('highlight')
    if (!urlTab && !urlCarrier && !urlHighlight) return

    const validTabs = ['domestic', 'abroad', 'global', 'content', 'resellers', 'usa']
    const targetTab = urlTab && validTabs.includes(urlTab)
      ? urlTab
      : (lockedTab && validTabs.includes(lockedTab) ? lockedTab : null)

    if (!targetTab) {
      setSearchParams({}, { replace: true })
      return
    }

    if (urlTab) setTab(targetTab)

    if (urlCarrier) {
      if (targetTab === 'global') {
        setFilter('globalProvider', urlCarrier)
      } else if (targetTab === 'usa') {
        setFilter('usaOperator', urlCarrier)
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
  }, [searchParams, lockedTab]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadTab(tab) }, [tab])
  useEffect(() => {
    const base = import.meta.env.VITE_API_URL || ''
    const controller = new AbortController()
    const CACHE_KEY = 'moca_fx_rates'
    const CACHE_TTL = 60 * 60 * 1000 // 1 hour

    const applyRates = (d) => {
      if (controller.signal.aborted) return
      setUsdRate(d.usd)
      setEurRate(d.eur)
      if (d.gbp) setGbpRate(d.gbp)
    }

    // Serve from localStorage cache if fresh
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null')
      if (cached && Date.now() - cached.ts < CACHE_TTL) {
        applyRates(cached)
        return () => controller.abort()
      }
    } catch { /* ignore corrupt cache */ }

    fetch(`${base}/api/exchange-rates`, {
      headers: { 'ngrok-skip-browser-warning': 'true' },
      signal: controller.signal,
    })
      .then(r => r.json())
      .then(d => {
        if (controller.signal.aborted) return
        // Persist to cache with timestamp
        try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ...d, ts: Date.now() })) } catch { /* quota */ }
        applyRates(d)
        if (!d.gbp) {
          // Flask not yet updated — fetch GBP→ILS directly
          fetch('https://open.er-api.com/v6/latest/GBP', { signal: controller.signal })
            .then(r2 => r2.json())
            .then(d2 => {
              if (!controller.signal.aborted && d2.rates?.ILS) setGbpRate(d2.rates.ILS)
            })
            .catch(() => {})
        }
      })
      .catch(() => {})

    return () => controller.abort()
  }, [])

  // Fetch market movers for trend badges — deferred 1s so critical plan data loads first
  useEffect(() => {
    const timer = setTimeout(() => {
      api.getMarketMovers(7, 20)
        .then(res => {
          const map = new Map()
          for (const m of res?.movers || []) {
            map.set(`${m.carrier}|${m.plan_name}`, { pct_change: m.pct_change })
          }
          setTrendMap(map)
        })
        .catch(() => {})
    }, 1000)
    return () => clearTimeout(timer)
  }, [])

  // Batch-load all sparkline series for the current tab in ONE request (replaces
  // the previous fetch-per-card N+1 in SparklineMini). Only the tabs that show a
  // sparkline (domestic/abroad/global) need it; others get an empty map so cards
  // render no line and issue no request.
  useEffect(() => {
    if (!['domestic', 'abroad', 'global'].includes(tab)) { setSparkMap(new Map()); return }
    let cancelled = false
    setSparkMap(null)
    api.getPriceSeriesBatch(tab)
      .then(res => {
        if (cancelled) return
        const map = new Map()
        for (const [k, pts] of Object.entries(res?.series || {})) map.set(k, pts)
        setSparkMap(map)
      })
      .catch(() => { if (!cancelled) setSparkMap(new Map()) })
    return () => { cancelled = true }
  }, [tab])

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
    const id = ++loadIdRef.current
    setLoading(true)
    try {
      if (t === 'domestic' && plans.domestic.length === 0) {
        const [p, c] = await Promise.all([api.getPlans(), api.getChanges()])
        if (id !== loadIdRef.current) return  // tab changed while fetching
        setPlans(prev => ({ ...prev, domestic: p }))
        setChanges(prev => ({ ...prev, domestic: c }))
      } else if (t === 'abroad' && plans.abroad.length === 0) {
        const [p, c] = await Promise.all([api.getAbroadPlans(), api.getAbroadChanges()])
        if (id !== loadIdRef.current) return
        setPlans(prev => ({ ...prev, abroad: p }))
        setChanges(prev => ({ ...prev, abroad: c }))
      } else if (t === 'global' && plans.global.length === 0) {
        const [p, c] = await Promise.all([api.getGlobalPlans(), api.getGlobalChanges()])
        if (id !== loadIdRef.current) return
        setPlans(prev => ({ ...prev, global: p }))
        setChanges(prev => ({ ...prev, global: c }))
      } else if (t === 'resellers' && plans.resellers.length === 0) {
        const p = await api.getResellerPlans()
        if (id !== loadIdRef.current) return
        // Tag each plan with its underlying carrier label and reseller name in extras for PlanCard rendering
        const enriched = p.map(plan => {
          const reseller = RESELLERS.find(r => r.id === plan.reseller_id)
          const resellerLabel = reseller ? reseller.label : plan.reseller_id
          const tag = `משווק: ${resellerLabel}`
          return { ...plan, extras: [tag, ...(plan.extras || [])] }
        })
        setPlans(prev => ({ ...prev, resellers: enriched }))
      } else if (t === 'usa' && plans.usa.length === 0) {
        const p = await api.getUsaPlans()
        if (id !== loadIdRef.current) return
        setPlans(prev => ({ ...prev, usa: p }))
      } else if (t === 'content' && plans.content.length === 0) {
        const p = await api.getContentPlans()
        if (id !== loadIdRef.current) return
        setPlans(prev => ({ ...prev, content: p }))
      } else if (t === 'banners' && !bannersLoaded) {
        const data = await api.getBanners()
        if (id !== loadIdRef.current) return
        setBanners(data)
        setBannersLoaded(true)
      }
      if (t === 'banners' && !storeBannersLoaded) {
        const data = await api.getStoreBanners()
        if (id !== loadIdRef.current) return
        setStoreBanners(data)
        setStoreBannersLoaded(true)
      }
    } catch (err) { console.error(err) }
    if (id === loadIdRef.current) setLoading(false)
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

  // Filter / sort / group / destination pipeline - pure functions + memo hook
  // (hooks/useDashboardPlans.js); DashboardPage only wires state in and cards out.
  const { filteredPlans, displayItems, regionOptions, destinationOptions } = useDashboardPlans({
    plans, tab, filters, visibleCarrierIds, carrierIds: CARRIER_IDS, usaOperators: USA_OPERATORS,
    onlyWatched, isWatched, watchItems, lang,
  })

  // Content services list
  const contentServices = useMemo(() => {
    return [...new Set(plans.content.map(p => p.service).filter(Boolean))]
  }, [plans.content])

  const handleScrape = () => triggerScrape()

  const setFilter = (key, value) => {
    startTransition(() => {
      setFilters(prev => ({ ...prev, [key]: value }))
      setVisibleCount(50)
    })
  }

  const resetFilters = () => {
    startTransition(() => {
      setFilters({ carrier: 'all', gb: 'all', sort: 'price_asc', gen: 'all', roaming: 'all',
        globalProvider: 'all', destination: 'all', region: 'all', days: 'all',
        israeliProvider: 'all', contentCarrier: 'all', contentService: 'all', reseller: 'all',
        usaOperator: 'all', usaNetwork: 'all' })
      setVisibleCount(50)
    })
  }

  // Provider stats — shown when a single carrier/provider is selected
  const providerStats = useMemo(() => {
    const active =
      ((tab === 'domestic' || tab === 'abroad') && filters.carrier !== 'all') ||
      (tab === 'global' && filters.globalProvider !== 'all') ||
      (tab === 'usa' && filters.usaOperator !== 'all')
    if (!active || filteredPlans.length === 0) return null
    const prices = filteredPlans.map(p => Number(p.price)).filter(p => p > 0)
    if (prices.length === 0) return null
    const avg = prices.reduce((a, b) => a + b, 0) / prices.length
    const min = Math.min(...prices)
    return { count: filteredPlans.length, avg, min }
  }, [filteredPlans, filters, tab])

  // Pre-compute highlight tokens once — avoids repeating toLowerCase/replace inside every PlanCard render
  const highlightMatcher = useMemo(() => {
    if (!highlightPlan) return null
    const h = highlightPlan.toLowerCase().replace(/[\s\-–]+/g, ' ')
    return { h, prefix: h.length > 5 ? h.slice(0, 15) : null, firstWord: h.split(' ')[0] }
  }, [highlightPlan])

  const exportToExcel = useCallback(async () => {
    if (!filteredPlans.length) return
    // Dynamic-import xlsx (~80KB) only when user clicks export
    const XLSX = await import('xlsx')
    const TAB_NAMES = { domestic: 'חבילות סלולר', abroad: 'חו"ל', global: 'גלובלי', content: 'תוכן', usa: 'נוחתים בארה"ב' }
    const CARRIER_HEB = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', tuki: 'Tuki', terminalesim: 'Terminal eSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks', travelsim: 'Travel Sim', gomoworld: 'GoMoWorld', tasim: 'Tasim', maya: 'Maya Mobile', bcengi: 'Bcengi', esim70: 'eSIM70', jetpack: 'Jetpack', breez: 'Breez' }
    const GB_HEB = { 'all': 'הכל', '0-5': '0-5GB', '5-15': '5-15GB', '15-100': '15-100GB', '100+': '100+GB', 'unlimited': 'ללא הגבלה' }
    const DAYS_HEB = { 'all': 'הכל', '1-7': '1-7 ימים', '8-14': '8-14 ימים', '15-30': '15-30 ימים', '30+': '30+ ימים' }

    // Build filter summary title
    const parts = [`קטגוריה: ${TAB_NAMES[tab]}`]
    if (filters.carrier !== 'all') parts.push(`ספק: ${CARRIER_HEB[filters.carrier] || filters.carrier}`)
    if (filters.globalProvider !== 'all') parts.push(`ספק: ${CARRIER_HEB[filters.globalProvider] || filters.globalProvider}`)
    if (filters.israeliProvider !== 'all') parts.push(filters.israeliProvider === 'israeli' ? 'ספקים ישראליים' : 'ספקים בינלאומיים')
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
    api.trackActivity('export', null, JSON.stringify({ tab, count: filteredPlans.length })).catch(() => {})
  }, [filteredPlans, tab, filters])

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 pb-20 md:pb-6">
      {/* Header row — context meta + admin scrape trigger.
          Page identity (kicker + title) lives in the Topbar. */}
      <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 tnum">
          {lastUpdate && (
            <span className="text-[11px] text-moca-muted">
              <span className="font-bold uppercase tracking-wider text-[9px] me-1">{tt('עדכון', 'Updated')}</span>
              {new Date(lastUpdate).toLocaleDateString('he-IL')} {lastUpdate.slice(11, 16)}
            </span>
          )}
          {usdRate && (
            <span className="text-[11px] text-moca-muted" dir="ltr">USD ₪{usdRate.toFixed(2)}</span>
          )}
          {eurRate && (
            <span className="text-[11px] text-moca-muted" dir="ltr">EUR ₪{eurRate.toFixed(2)}</span>
          )}
          {gbpRate && (
            <span className="text-[11px] text-moca-muted" dir="ltr">GBP ₪{gbpRate.toFixed(2)}</span>
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
                <><svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.22-8.56" /></svg> {tt('מעדכן...', 'Updating...')}</>
              ) : (
                <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg> {tt('עדכן', 'Update')}</>
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

      {/* Tabs — hidden on dedicated routes (/plans, /roaming, /esim, /banners, /history)
          where the URL itself is the tab selector. */}
      {!lockedTab && (
        <div className="flex justify-center gap-0 mb-6 border-b border-gray-200">
          {visibleTabs.map(t => (
            <button
              key={t.id}
              onClick={() => { setTab(t.id); setVisibleCount(50); setFilter('carrier', 'all'); setFilter('globalProvider', 'all'); setFilter('israeliProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }}
              className={`relative px-4 py-2.5 text-[13px] font-medium transition-all duration-150
                ${tab === t.id
                  ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-2 after:h-[2px] after:bg-moca-bolt after:rounded-full'
                  : 'text-moca-muted hover:text-moca-bolt'
                }`}
            >
              <span className="hidden sm:inline-flex items-center gap-1.5">{TAB_ICONS[t.id]}</span>
              {tt(t.label, TAB_LABELS_EN[t.id] || t.label)}
            </button>
          ))}
        </div>
      )}

      {/* Filter strip — hidden on banners tab which has no plan filters */}
      <div className="mb-4" style={tab === 'banners' || tab === 'history' || tab === 'news' ? {display:'none'} : undefined}>
        {/* Toggle + results count row */}
        <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className="text-xs text-moca-sub hover:text-moca-bolt flex items-center gap-1.5 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
              </svg>
              <span>{filtersOpen ? tt('סגור סינון', 'Close filters') : tt('סינון', 'Filters')}</span>
              {activeFilterCount > 0 && (
                <span className="bg-moca-bolt text-white text-[9px] px-1.5 py-0.5 rounded-full min-w-[16px] text-center">{activeFilterCount}</span>
              )}
            </button>
            {activeFilterCount > 0 && (
              <button
                onClick={resetFilters}
                className="text-xs font-medium bg-moca-bolt text-white px-2.5 py-1 rounded-lg hover:bg-moca-text transition-colors"
              >
                {tt('איפוס', 'Reset')}
              </button>
            )}

            <button
              onClick={() => setOnlyWatched(v => !v)}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-lg border transition-colors ${
                onlyWatched
                  ? 'bg-amber-50 border-amber-300 text-amber-700'
                  : 'bg-white border-moca-border/50 text-moca-sub hover:border-moca-bolt/40'
              }`}
              title={onlyWatched ? tt('הצג הכל', 'Show all') : tt('הצג רק חבילות במעקב', 'Show watched plans only')}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill={onlyWatched ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
              <span>{tt('המעקב שלי', 'My watchlist')}</span>
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

            {/* Change dot legend — hidden on mobile to save horizontal space */}
            <div className="hidden md:flex items-center gap-2 border-r border-moca-border/40 pr-2 mr-1">
              <span className="flex items-center gap-1 text-[10px] text-moca-sub">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block flex-shrink-0" />
                {tt('חבילה חדשה', 'New plan')}
              </span>
              <span className="flex items-center gap-1 text-[10px] text-moca-sub">
                <span className="w-2 h-2 rounded-full bg-red-400 inline-block flex-shrink-0" />
                {tt('חבילה הוסרה', 'Plan removed')}
              </span>
              <span className="flex items-center gap-1 text-[10px] text-moca-sub">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block flex-shrink-0" />
                {tt('שינוי מחיר', 'Price change')}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[11px] text-gray-400">{tab === 'banners' ? `${banners.length} ${tt('ספקים', 'providers')}` : tab === 'global' ? `${displayItems.length} ${tt('כרטיסים', 'cards')}` : `${filteredPlans.length} ${tt('חבילות', 'plans')}`}</span>
            {filteredPlans.length > 0 && (
              <button onClick={exportToExcel} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-moca-sub hover:text-moca-text hover:bg-moca-cream transition-all duration-150" title={tt('ייצוא ל-Excel', 'Export to Excel')}>
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
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('גלישה', 'Data')}</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '0-5', '5-15', '15-100', '100+', 'unlimited'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? tt('הכל', 'All') : v === 'unlimited' ? tt('ללא הגבלה', 'Unlimited') : `${v}GB`} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
                      ))}
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('גלישה בחו"ל', 'Roaming data')}</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label={tt('כולם', 'All')} active={filters.roaming === 'all'} onClick={() => setFilter('roaming', 'all')} />
                      <FilterTag label={tt('כולל חו"ל', 'Incl. roaming')} active={filters.roaming === 'yes'} onClick={() => setFilter('roaming', 'yes')} />
                    </div>
                  </div>
                </div>
              )}

              {/* Domestic: Row 2 = דור רשת | מיון */}
              {tab === 'domestic' && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('דור רשת', 'Network gen')}</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label={tt('כולם', 'All')} active={filters.gen === 'all'} onClick={() => setFilter('gen', 'all')} />
                      <FilterTag label="4G" active={filters.gen === '4g'} onClick={() => setFilter('gen', '4g')} />
                      <FilterTag label="5G" active={filters.gen === '5g'} onClick={() => setFilter('gen', '5g')} />
                      <FilterTag label={tt('5G מתועדף', '5G Priority')} active={filters.gen === '5g_priority'} onClick={() => setFilter('gen', '5g_priority')} />
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('מיון', 'Sort')}</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label={tt('מחיר ↑', 'Price ↑')} active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
                      <FilterTag label={tt('מחיר ↓', 'Price ↓')} active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
                      <FilterTag label="GB ↑" active={filters.sort === 'gb_asc'} onClick={() => setFilter('sort', 'gb_asc')} />
                      <FilterTag label="GB ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
                      <FilterTag label="₪/GB ↑" active={filters.sort === 'ppgb_asc'} onClick={() => setFilter('sort', 'ppgb_asc')} />
                      <FilterTag label="₪/GB ↓" active={filters.sort === 'ppgb_desc'} onClick={() => setFilter('sort', 'ppgb_desc')} />
                    </div>
                  </div>
                </div>
              )}

              {/* Global: Row 1 = אזור | מדינה */}
              {tab === 'global' && (regionOptions.length > 0 || destinationOptions.length > 0) && (
                <div className="grid grid-cols-2 gap-3">
                  {regionOptions.length > 0 && (
                    <div className="border border-moca-border/60 rounded-xl p-2.5">
                      <p className="text-[11px] font-medium text-gray-500 mb-1">{tt('אזור', 'Region')}</p>
                      <SearchableSelect
                        value={filters.region}
                        onChange={val => { setFilter('region', val); if (val !== 'all') setFilter('destination', 'all') }}
                        options={regionOptions}
                        placeholder={tt(`כל האזורים (${regionOptions.length})`, `All regions (${regionOptions.length})`)}
                      />
                    </div>
                  )}
                  {destinationOptions.length > 0 && (
                    <div className="border border-moca-border/60 rounded-xl p-2.5">
                      <p className="text-[11px] font-medium text-gray-500 mb-1">{tt('מדינה', 'Country')}</p>
                      <SearchableSelect
                        value={filters.destination}
                        onChange={val => { setFilter('destination', val); if (val !== 'all') setFilter('region', 'all') }}
                        options={destinationOptions}
                        placeholder={tt(`כל המדינות (${destinationOptions.length})`, `All countries (${destinationOptions.length})`)}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Abroad/Global: Row 2 = גלישה | תוקף */}
              {(tab === 'abroad' || tab === 'global') && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('גלישה', 'Data')}</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '0-5', '5-15', '15-100', '100+', 'unlimited'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? tt('הכל', 'All') : v === 'unlimited' ? tt('ללא הגבלה', 'Unlimited') : `${v}GB`} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
                      ))}
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('תוקף', 'Validity')}</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '1-7', '8-14', '15-30', '30+'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? tt('הכל', 'All') : tt(`${v} ימים`, `${v} days`)} active={filters.days === v} onClick={() => setFilter('days', v)} />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Abroad/Global: Row 3 = מיון, with סוג ספק beside it on the global tab */}
              {(tab === 'abroad' || tab === 'global') && (
                <div className={tab === 'global' ? 'grid grid-cols-2 gap-3' : ''}>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('מיון', 'Sort')}</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label={tt('מחיר ↑', 'Price ↑')} active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
                      <FilterTag label={tt('מחיר ↓', 'Price ↓')} active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
                      <FilterTag label="GB ↑" active={filters.sort === 'gb_asc'} onClick={() => setFilter('sort', 'gb_asc')} />
                      <FilterTag label="GB ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
                    </div>
                  </div>
                  {/* סוג ספק — ישראלי (אתר בעברית) / בינלאומי. The list lives in carrierLabels.js */}
                  {tab === 'global' && (
                    <div className="border border-moca-border/60 rounded-xl p-2.5">
                      <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('סוג ספק', 'Provider type')}</p>
                      <div className="flex flex-wrap gap-1">
                        {[['all', tt('הכל', 'All')], ['israeli', tt('ספק ישראלי', 'Israeli provider')], ['foreign', tt('ספק בינלאומי', 'International provider')]].map(([v, label]) => (
                          <FilterTag
                            key={v}
                            label={label}
                            active={filters.israeliProvider === v}
                            onClick={() => {
                              setFilter('israeliProvider', v)
                              // Drop a selected provider that contradicts the new scope (would yield 0 results)
                              if (v !== 'all' && filters.globalProvider !== 'all' &&
                                  ISRAELI_GLOBAL_PROVIDERS.has(filters.globalProvider) !== (v === 'israeli')) {
                                setFilter('globalProvider', 'all')
                              }
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* USA: Row 1 = גלישה | תוקף */}
              {tab === 'usa' && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('גלישה', 'Data')}</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '0-5', '5-15', '15-100', 'unlimited'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? tt('הכל', 'All') : v === 'unlimited' ? tt('ללא הגבלה', 'Unlimited') : `${v}GB`} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
                      ))}
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('תוקף', 'Validity')}</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '1-7', '8-14', '15-30', '30+'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? tt('הכל', 'All') : tt(`${v} ימים`, `${v} days`)} active={filters.days === v} onClick={() => setFilter('days', v)} />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* USA: Row 2 = מיון | רשת */}
              {tab === 'usa' && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('מיון', 'Sort')}</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label={tt('מחיר ↑', 'Price ↑')} active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
                      <FilterTag label={tt('מחיר ↓', 'Price ↓')} active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
                      <FilterTag label="GB ↑" active={filters.sort === 'gb_asc'} onClick={() => setFilter('sort', 'gb_asc')} />
                      <FilterTag label="GB ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
                    </div>
                  </div>
                  <div className="border border-moca-border/60 rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('רשת', 'Network')}</p>
                    <div className="flex flex-wrap gap-1">
                      <FilterTag label={tt('כל הרשתות', 'All networks')} active={filters.usaNetwork === 'all'} onClick={() => { setFilter('usaNetwork', 'all'); setFilter('usaOperator', 'all') }} />
                      {USA_NETWORKS.map(n => (
                        <FilterTag key={n} label={n} active={filters.usaNetwork === n} onClick={() => { setFilter('usaNetwork', n); setFilter('usaOperator', 'all') }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Content service filter (content tab) */}
              {tab === 'content' && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('שירות', 'Service')}</p>
                  <div className="flex flex-wrap gap-1">
                    <FilterTag label={tt('כולם', 'All')} active={filters.contentService === 'all'} onClick={() => setFilter('contentService', 'all')} />
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
                    <p className="text-[11px] font-medium text-gray-500">{tt('ספקים', 'Providers')}</p>
                    <button
                      onClick={() => setFilter('carrier', 'all')}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.carrier === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      {tt('כולם', 'All')}
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
                    <p className="text-[11px] font-medium text-gray-500">{tt('ספקים', 'Providers')}</p>
                    <button
                      onClick={() => { setFilter('globalProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.globalProvider === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      {tt('כולם', 'All')}
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    {GLOBAL_PROVIDERS.map(p => {
                      // Respect the סוג ספק scope — show only providers on the selected side
                      if (filters.israeliProvider !== 'all' &&
                          ISRAELI_GLOBAL_PROVIDERS.has(p.id) !== (filters.israeliProvider === 'israeli')) return null
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

              {/* USA operators */}
              {tab === 'usa' && (
                <div className="border border-moca-border/60 rounded-xl p-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[11px] font-medium text-gray-500">{tt('מפעילים', 'Operators')}</p>
                    <button
                      onClick={() => { setFilter('usaOperator', 'all'); setFilter('usaNetwork', 'all') }}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.usaOperator === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      {tt('כולם', 'All')}
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1">
                    {USA_OPERATORS
                      .filter(o => filters.usaNetwork === 'all' || o.net === filters.usaNetwork)
                      .map(o => {
                        const cnt = plans.usa?.filter(p => p.carrier === o.id).length || 0
                        return (
                          <button
                            key={o.id}
                            onClick={() => cnt > 0 ? setFilter('usaOperator', o.id) : null}
                            className={`px-1 py-1 rounded-md text-[10px] font-medium text-center transition-all duration-150 truncate ${
                              filters.usaOperator === o.id ? 'bg-gray-900 text-white' :
                              cnt === 0 ? 'text-moca-border cursor-default' :
                              'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                            }`}
                          >
                            {o.label} {cnt > 0 ? `(${cnt})` : ''}
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
                    <p className="text-[11px] font-medium text-gray-500">{tt('ספקים', 'Providers')}</p>
                    <button
                      onClick={() => setFilter('contentCarrier', 'all')}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.contentCarrier === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      {tt('כולם', 'All')}
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
                    <p className="text-[11px] font-medium text-gray-500">{tt('משווקים', 'Resellers')}</p>
                    <button
                      onClick={() => setFilter('reseller', 'all')}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 ${
                        filters.reseller === 'all' ? 'bg-gray-900 text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                      }`}
                    >
                      {tt('כולם', 'All')}
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
          <span className="text-gray-500">{providerStats.count} {tt('חבילות', 'plans')}</span>
          <span className="text-gray-300">·</span>
          <span className="text-gray-500">{tt('ממוצע:', 'Avg:')} <strong className="text-gray-700">&#8362;{providerStats.avg.toFixed(0)}</strong></span>
          <span className="text-gray-300">·</span>
          <span className="text-gray-500">{tt('מינימום:', 'Min:')} <strong className="text-emerald-600">&#8362;{providerStats.min}</strong></span>
          <div className="mr-auto">
            <CarrierAIInsights carrierId={tab === 'global' ? filters.globalProvider : tab === 'usa' ? filters.usaOperator : filters.carrier} />
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
                  sparkPoints={sparkMap ? (sparkMap.get(key) || null) : null}
                  isInCompare={compareMap.has(compareKey)}
                  onCompareToggle={toggleCompare}
                  highlighted={highlightMatcher && (() => {
                    const name = (plan.plan_name || '').toLowerCase().replace(/[\s\-–]+/g, ' ')
                    if (plan.carrier === highlightPlan) return true
                    if (name.includes(highlightMatcher.h)) return true
                    if (highlightMatcher.prefix && name.includes(highlightMatcher.prefix)) return true
                    if (highlightMatcher.firstWord.length > 2 && name.includes(highlightMatcher.firstWord)) return true
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
                {tt('\u05D4\u05E6\u05D2 \u05E2\u05D5\u05D3', 'Show more')} ({displayItems.length - visibleCount} {tt('\u05E0\u05D5\u05E1\u05E4\u05D9\u05DD', 'more')})
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
            <span>{tt('צילומי מסך אוטומטיים של עמודי הבית והחנות של הספקים - מתעדכנים כל יום בשעה 08:00', 'Automatic screenshots of providers\' homepages and stores - updated daily at 08:00')}</span>
          </div>

          {bannersLoaded && banners.length === 0 && (
            <div className="text-center text-moca-muted py-16 text-sm">
              {tt('אין באנרים זמינים עדיין - הם יצולמו בשעה 08:00', 'No banners available yet - they will be captured at 08:00')}
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
            {tt('עמוד ראשי', 'Homepage')}
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
                {tt('חנות ציוד קצה', 'Device store')}
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
        <div className="text-center py-20 animate-fade-in">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-moca-cream border border-moca-sand grid place-items-center">
            <svg width="24" height="23" viewBox="0 0 48 46" fill="none" aria-hidden="true">
              <path fill="var(--color-moca-bolt)" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"/>
            </svg>
          </div>
          <p className="font-display text-lg font-bold text-moca-dark mt-4">{tt('אין חבילות שתואמות', 'No matching plans')}</p>
          <p className="text-sm text-moca-sub mt-1">{tt('נסו להרחיב את טווח המחיר או להסיר סינון', 'Try widening the price range or clearing a filter')}</p>
          <button
            type="button"
            onClick={resetFilters}
            className="inline-flex items-center gap-1.5 mt-4 text-[13px] font-semibold text-white bg-moca-bolt rounded-lg px-4 py-2 transition-colors hover:bg-[#7a4520]"
          >
            {tt('איפוס סינון', 'Reset filters')}
          </button>
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
            <span className="text-sm font-semibold text-gray-700">{compareMap.size} {tt('חבילות נבחרו', 'plans selected')}</span>
            <button
              onClick={() => setShowCompareDrawer(true)}
              className="bg-moca-bolt hover:bg-[#7a4520] text-white text-sm font-medium px-4 py-1.5 rounded-xl transition-colors"
            >
              {tt('השווה', 'Compare')}
            </button>
            <SavedComparesMenu
              comparePlans={[...compareMap.values()]}
              onApply={applyCompareSet}
            />
            <button
              onClick={() => setCompareMap(new Map())}
              className="text-gray-400 hover:text-red-500 transition-colors text-lg leading-none"
              title={tt('נקה בחירה', 'Clear selection')}
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
              <h2 className="text-base font-bold text-gray-800">{tt('השוואת חבילות', 'Plan comparison')}</h2>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    const win = window.open('', '_blank')
                    if (!win) { alert(tt('חלון ההדפסה נחסם. אפשרו חלונות קופצים ונסו שוב.', 'The print window was blocked - allow pop-ups and try again.')); return }
                    const CARRIER_HEB = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', neptucom: 'Neptucom', tuki: 'Tuki', terminalesim: 'Terminal eSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks', voye: 'VOYE', orbit: 'Orbit', travelsim: 'Travel Sim' }
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
                    const html = `<html dir="rtl"><head><meta charset="utf-8"><title>השוואת חבילות - MOCA</title>
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
<h1>השוואת חבילות - MOCA</h1>
<div class="grid">
${[...compareMap.values()].map(({ plan, planType }) => {
  const extras = getExtras(plan)
  const planInfo = getPlanInfo(plan)
  return `
<div class="card">
  <div class="carrier">${esc(CARRIER_HEB[plan.carrier] || plan.carrier)} · ${planType === 'domestic' ? 'סלולר' : planType === 'abroad' ? 'חו"ל' : 'גלובלי'}</div>
  <div class="name">${esc(plan.plan_name || plan.service || '')}</div>
  <div class="price">₪${esc(plan.price)}</div>
  <div class="info">${plan.data_gb === null ? 'ללא הגבלה' : esc(plan.data_gb ? Number(plan.data_gb).toLocaleString('en-US') : '') + 'GB'}${plan.days ? ' · ' + esc(plan.days) + ' ימים' : ''}${plan.minutes ? ' · ' + esc(Number(plan.minutes).toLocaleString('en-US')) + ' דקות' : ''}${plan.sms ? ' · ' + esc(plan.sms) + ' SMS' : ''}</div>
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
                  {tt('ייצוא PDF', 'Export PDF')}
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
                      title={tt('הסר מהשוואה', 'Remove from comparison')}
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
