import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import FilterTag from '../components/ui/FilterTag'
import SearchableSelect from '../components/ui/SearchableSelect'
import { PageHeader } from '../components/moca'
import { getCarrierColor } from '../components/moca/carrierMeta'
import { MVNO_BRAND_COLORS } from '../data/mvnoBrandColors'
import { has5G as detect5G, hasMaxPriority } from '../data/networkPriority'
import { getAppsForPlan } from '../data/abroadApps'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import {
  AIRALO_DISCOVER, AIRALO_REGION_MAP, TUKI_COUNTRIES, SIMTLV_COUNTRIES,
  PELEPHONE_GLOBAL_COUNTRIES, ESIMO_COUNTRIES, WORLD8_WORLDWIDE, WORLD8_EUROPE_USA,
  XPHONE_EUROPE, XPHONE_WORLD, ORBIT_COUNTRIES, TRAVELSIM_GLOBAL, TRAVELSIM_USA, TRAVELSIM_ME,
  GIGSKY_GLOBAL, ESIMGENIUS_GLOBAL, ESIMAX_GLOBAL,
  getCountriesForPlan
} from '../data/globalCountries'
import { GLOBAL_PROVIDERS_WITH_COLOR } from '../data/carrierLabels'
import { useLang } from '../hooks/useLanguage'
import { destKey, dedupeDestOptions, isCruiseDest, cruiseLabel, CRUISE_VALUE } from '../data/destI18n'

const TABS = [
  { id: 'domestic', label: 'חבילות סלולר' },
  { id: 'abroad', label: 'חו"ל' },
  { id: 'global', label: 'גלובלי' },
]

const CARRIERS_BY_TAB = {
  domestic: [
    { id: 'partner',   label: 'פרטנר' },
    { id: 'pelephone', label: 'פלאפון' },
    { id: 'hotmobile', label: 'הוט מובייל' },
    { id: 'cellcom',   label: 'סלקום' },
    { id: 'mobile019', label: '019' },
    { id: 'xphone',    label: 'XPhone' },
    { id: 'wecom',     label: 'We-Com' },
    { id: 'neptucom',  label: 'Neptucom' },
    { id: 'golan',     label: 'גולן טלקום' },
    { id: 'rami_levy', label: 'רמי לוי' },
  ],
  abroad: [
    { id: 'partner',   label: 'פרטנר' },
    { id: 'pelephone', label: 'פלאפון' },
    { id: 'hotmobile', label: 'הוט מובייל' },
    { id: 'cellcom',   label: 'סלקום' },
    { id: 'mobile019', label: '019' },
    { id: 'xphone',    label: 'XPhone' },
    { id: 'wecom',     label: 'We-Com' },
    { id: 'neptucom',  label: 'Neptucom' },
    { id: 'golan',     label: 'גולן טלקום' },
    { id: 'rami_levy', label: 'רמי לוי' },
  ],
  // Global providers (+ their per-provider chart colors) are derived from the single
  // source of truth in data/carrierLabels — add a provider there, not here.
  global: GLOBAL_PROVIDERS_WITH_COLOR,
}

const KNOWN_REGIONS = new Set([
  'אירופה','אסיה','אסיה ואוקיאניה','אפריקה','גלובלי','קריביים','איי הקריביים',
  'אמריקה הלטינית','צפון אמריקה','המזרח התיכון','המזרח התיכון וצפון אפריקה',
  'דרום מזרח אסיה','סקנדינביה','בלקן','מזרח אירופה','מרכז אמריקה','אוקיאניה',
  'סין + הונג קונג + מקאו','יפן וקוריאה','יפן וסין',
  'אסיה פסיפיק','מרכז אסיה','צפון אפריקה',
  'אמריקה הדרומית','דרום אמריקה',
  'שוויץ+','גוודלופ','קפריסין+',
  'צפון ודרום אמריקה','מדינות האיים הקריביים',
  'אירופה — גלישה בלבד','אירופה — גולשים ומדברים',
  '167+ מדינות','156+ מדינות',
  'ספארי אפריקה','האיחוד האירופי ובריטניה',
  'איי התעלה','האנטילים הצרפתיים','אנטילים הולנדיים',
  'כלל העולם',
  'אירופה+','חבר המדינות','אמריקה המרכזית','אירופה וארה"ב','פורטוגל וספרד',
  'המזרח התיכון לייט','אירופה לייט','גלובלי',
  // Best Connect regional
  'טורקיה ואיי יוון',
  // eSIM Plus regional
  'המזרח התיכון ואפריקה','האמריקות',
  // SimTLV catalog regional bundles
  'אירופה (32 מדינות)','אירופה (33 מדינות)','אירופה (37 מדינות)',
  'גלובלי (36 מדינות)','גלובלי (37 מדינות)','גלובלי (41 מדינות)',
  'גלובלי (47 מדינות)','גלובלי (58 מדינות)','גלובלי (84 מדינות)',
  'דרום אמריקה (11 מדינות)',
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
  if (!region) return region
  const r = String(region)
  // English legacy names from old DB scrapes (Best Connect, 7G, eSIM Plus)
  if (r === 'Africa') return 'אפריקה'
  if (r === 'Caribbean Islands' || r === 'הקריבי') return 'איי הקריביים'
  if (r === 'GCC' || r === 'Gulf Region') return 'המזרח התיכון'
  if (r === 'Oceania') return 'אוקיאניה'
  if (r === 'Balkan' || r === 'Balkans') return 'בלקן'
  if (r === 'Central Asia') return 'מרכז אסיה'
  if (r === 'North America') return 'צפון אמריקה'
  if (r === 'Middle East') return 'המזרח התיכון'
  if (r === 'Middle East and North Africa' || r === 'Middle East & North Africa') return 'המזרח התיכון וצפון אפריקה'
  if (r === 'Americas' || r === 'Americas + US + CA') return 'האמריקות'
  if (/^Global (Light|Max|Standard|Premium|Plus)$/i.test(r)) return 'גלובלי'
  if (r.includes('אירופה') || /^Europe/i.test(r)) return 'אירופה'
  // "גלובלי (47 מדינות)" etc. (SimTLV) fold into the unified global entry
  if (r.includes('גלובלי')) return 'גלובלי'
  return region
}

export default function ComparePage() {
  const { tt, lang } = useLang()
  const navigate = useNavigate()
  const [tab, setTab] = useState('domestic')
  const [selectedCarriers, setSelectedCarriers] = useState([])
  const [gbFilter, setGbFilter] = useState('all')
  const [daysFilter, setDaysFilter] = useState('all')
  const [regionFilter, setRegionFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [destinationFilter, setDestinationFilter] = useState('all')
  const [sortBy, setSortBy] = useState('price_asc')
  const [roamingFilter, setRoamingFilter] = useState('all')
  const [genFilter, setGenFilter] = useState('all')
  const [appsFilter, setAppsFilter] = useState('all')
  const [allData, setAllData] = useState({ domestic: [], abroad: [], global: [] })
  const [loading, setLoading] = useState(true)
  const [tableVisibleCount, setTableVisibleCount] = useState(50)

  useEffect(() => {
    Promise.all([
      api.getPlans(),
      api.getAbroadPlans(),
      api.getGlobalPlans(),
    ]).then(([domestic, abroad, global]) => {
      setAllData({ domestic, abroad, global })
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    resetFilters()
  }, [tab])

  // Reset table pagination when filters change
  useEffect(() => {
    setTableVisibleCount(50)
  }, [selectedCarriers, gbFilter, daysFilter, regionFilter, destinationFilter, sortBy, genFilter, appsFilter])

  const resetFilters = () => {
    setSelectedCarriers([])
    setGbFilter('all')
    setDaysFilter('all')
    setRegionFilter('all')
    setDestinationFilter('all')
    setSearchQuery('')
    setSortBy('price_asc')
    setRoamingFilter('all')
    setGenFilter('all')
    setAppsFilter('all')
    setTableVisibleCount(50)
  }

  const plans = allData[tab] || []
  const carrierOptions = CARRIERS_BY_TAB[tab] || []
  const showDays = tab === 'abroad' || tab === 'global'

  const availableCarriers = useMemo(() => {
    const inData = new Set(plans.map(p => p.carrier))
    return carrierOptions.filter(c => inData.has(c.id))
  }, [plans, carrierOptions])

  const getLabel = (id) => carrierOptions.find(x => x.id === id)?.label || id
  // For domestic/abroad MVNOs use the real brand color via getCarrierColor()
  // (same source of truth as CarrierChip, CompetitorBoard, PositioningPage).
  // For global providers — not in MVNO_BRAND_COLORS — fall back to the per-provider
  // color from the registry (CARRIERS_BY_TAB.global, derived in data/carrierLabels).
  const getColor = (id) => {
    if (MVNO_BRAND_COLORS[id]) return getCarrierColor(id)
    return carrierOptions.find(x => x.id === id)?.color || '#888'
  }

  // Clicking a result row deep-links to that plan on the dashboard: matching tab
  // (domestic/abroad/global), carrier filter applied, and the plan highlighted.
  // Same param shape DashboardPage consumes from GlobalSearch / ChatPanel.
  const goToPlan = (p) => {
    navigate(`/?${new URLSearchParams({ tab, carrier: p.carrier, highlight: p.plan_name })}`)
  }

  // Static country lists for carriers that don't store country in extras
  const CARRIER_COUNTRY_LISTS = useMemo(() => ({
    tuki: TUKI_COUNTRIES,
    airalo: AIRALO_DISCOVER,
    pelephone_global: PELEPHONE_GLOBAL_COUNTRIES,
    esimo: ESIMO_COUNTRIES,
    simtlv: SIMTLV_COUNTRIES,
    world8: [...new Set([...WORLD8_WORLDWIDE, ...WORLD8_EUROPE_USA])],
    xphone_global: [...new Set([...XPHONE_EUROPE, ...XPHONE_WORLD])],
    orbit: ORBIT_COUNTRIES,
    travelsim: [...new Set([...TRAVELSIM_GLOBAL, ...TRAVELSIM_USA, ...TRAVELSIM_ME])],
    gigsky: GIGSKY_GLOBAL,
    esimgenius: ESIMGENIUS_GLOBAL,
    esimax: ESIMAX_GLOBAL,
  }), [])

  // Build complete country → carriers mapping
  const { availableRegions, availableDestinations, countryCarrierMap, hasCruise } = useMemo(() => {
    if (tab !== 'global') return { availableRegions: [], availableDestinations: [], countryCarrierMap: {}, hasCruise: false }

    // Keyed by canonical English (destKey) so spelling variants of the same
    // country collapse into one entry; heByKey keeps a representative Hebrew.
    const map = {} // destKey → Set of carrier ids
    const heByKey = {} // destKey → representative Hebrew name
    const addCountry = (heName, carrier) => {
      // Cruise packages are surfaced via the single synthetic "Cruise" option.
      if (isCruiseDest(heName)) return
      const k = destKey(heName)
      if (!k) return
      if (!map[k]) { map[k] = new Set(); heByKey[k] = heName }
      map[k].add(carrier)
    }

    // From extras[0] (saily, holafly, esimio per-country plans)
    plans.forEach(p => {
      if (p.extras && p.extras[0] && !/\d/.test(p.extras[0]) && !KNOWN_REGIONS.has(normalizeRegionLabel(p.extras[0]))) {
        addCountry(p.extras[0], p.carrier)
      }
    })

    // From static country lists (tuki, airalo, etc.)
    Object.entries(CARRIER_COUNTRY_LISTS).forEach(([carrier, countries]) => {
      // Only add if carrier has plans in data
      if (plans.some(p => p.carrier === carrier)) {
        countries.forEach(country => addCountry(country, carrier))
      }
    })

    // Also index saily/holafly/esimio regional plans' included countries
    plans.forEach(p => {
      if (p.extras && p.extras[0] && KNOWN_REGIONS.has(normalizeRegionLabel(p.extras[0]))) {
        const data = getCountriesForPlan(p)
        if (data && data.countries) {
          data.countries.forEach(country => addCountry(country, p.carrier))
        }
      }
    })

    const regions = [...new Set(
      plans
        .filter(p => p.extras && p.extras[0] && (KNOWN_REGIONS.has(normalizeRegionLabel(p.extras[0])) || isLargeMultiCountryRegion(p.extras[0])))
        .map(p => normalizeRegionLabel(p.extras[0]))
    )].sort((a, b) => a.localeCompare(b, 'he'))
    // Representative Hebrew per canonical country (already de-duplicated).
    const destinations = Object.values(heByKey).sort((a, b) => a.localeCompare(b, 'he'))
    const hasCruise = plans.some(p => p.extras && isCruiseDest(p.extras[0]))

    return { availableRegions: regions, availableDestinations: destinations, countryCarrierMap: map, hasCruise }
  }, [plans, tab, CARRIER_COUNTRY_LISTS])

  // Localized, de-duplicated dropdown options.
  const regionOptions = useMemo(() => dedupeDestOptions(availableRegions, lang), [availableRegions, lang])
  const destinationOptions = useMemo(() => {
    const opts = availableDestinations
      .map(heRep => {
        const k = destKey(heRep)
        const n = countryCarrierMap[k] ? countryCarrierMap[k].size : 0
        return { value: heRep, label: `${lang === 'he' ? heRep : k} (${n})` }
      })
      .sort((a, b) => a.label.localeCompare(b.label, lang === 'he' ? 'he' : 'en'))
    // Pin the unified "Cruise" option at the top when cruise packages exist.
    return hasCruise ? [{ value: CRUISE_VALUE, label: cruiseLabel(lang) }, ...opts] : opts
  }, [availableDestinations, countryCarrierMap, hasCruise, lang])

  // Filter + sort plans
  const filteredPlans = useMemo(() => {
    const expandedCarriers = selectedCarriers.flatMap(c => c === 'airalo' ? ['airalo', 'airalo_local', 'airalo_regional'] : [c])
    let result = plans.filter(p => expandedCarriers.includes(p.carrier))

    if (gbFilter !== 'all') {
      if (gbFilter === 'unlimited') result = result.filter(p => p.data_gb === null)
      else if (gbFilter === '0-5') result = result.filter(p => p.data_gb !== null && p.data_gb <= 5)
      else if (gbFilter === '5-15') result = result.filter(p => p.data_gb !== null && p.data_gb > 5 && p.data_gb <= 15)
      else if (gbFilter === '15-100') result = result.filter(p => p.data_gb !== null && p.data_gb > 15 && p.data_gb <= 100)
      else if (gbFilter === '100+') result = result.filter(p => p.data_gb !== null && p.data_gb > 100)
    }

    if (regionFilter !== 'all') {
      const rTarget = destKey(regionFilter)
      result = result.filter(p => p.extras && destKey(normalizeRegionLabel(p.extras[0])) === rTarget)
    } else if (destinationFilter === CRUISE_VALUE) {
      // Unified "Cruise" filter — matches every provider's cruise-at-sea package.
      result = result.filter(p => p.extras && isCruiseDest(p.extras[0]))
    } else if (destinationFilter !== 'all') {
      // Compare via canonical English key so the selected representative spelling
      // matches plans tagged with any of its de-duplicated variants.
      const dTarget = destKey(destinationFilter)
      const carriersForCountry = countryCarrierMap[dTarget] || new Set()
      result = result.filter(p => {
        if (!carriersForCountry.has(p.carrier)) return false

        const ext = p.extras && p.extras[0]

        // Per-country plan (extras[0] = country name, not a region)
        if (ext && !KNOWN_REGIONS.has(ext) && !/\d/.test(ext)) {
          return destKey(ext) === dTarget
        }

        // Regional plan (extras[0] = region name like "אירופה")
        if (ext && KNOWN_REGIONS.has(ext)) {
          const regionData = getCountriesForPlan(p)
          if (regionData && regionData.countries) {
            return regionData.countries.some(c => destKey(c) === dTarget)
          }
          return false
        }

        // Global carriers without extras (tuki, airalo, simtlv, etc.)
        // — already verified via carriersForCountry
        return true
      })
    }

    if (showDays && daysFilter !== 'all') {
      if (daysFilter === '1-7') result = result.filter(p => p.days && p.days <= 7)
      else if (daysFilter === '8-14') result = result.filter(p => p.days && p.days > 7 && p.days <= 14)
      else if (daysFilter === '15-30') result = result.filter(p => p.days && p.days > 14 && p.days <= 30)
      else if (daysFilter === '30+') result = result.filter(p => p.days && p.days > 30)
    }

    if (tab === 'domestic' && roamingFilter === 'yes') {
      // Match plans with actual included abroad data — either quantified
      // ("5GB גלישה בחו\"ל") or marked כלול/כולל. Pay-per-use routes like
      // Pelephone's "מסלול חו\"ל Travel" are excluded by design.
      result = result.filter(p => p.extras && p.extras.some(e => {
        const hasIntl = /חו"ל|חו״ל/.test(e)
        if (!hasIntl) return false
        const hasQuantifiedData = /\d+/.test(e) && /GB|גלישה/i.test(e)
        const hasIncludedTag = /(?:כלול(?:ה|ים)?|כולל)/.test(e)
        return hasQuantifiedData || hasIncludedTag
      }))
    }
    if (tab === 'domestic' && genFilter === '5g') {
      result = result.filter(p => detect5G(p) && !hasMaxPriority(p))
    }
    if (tab === 'domestic' && genFilter === '5g_priority') {
      result = result.filter(hasMaxPriority)
    }
    if (tab === 'domestic' && genFilter === '4g') {
      result = result.filter(p => !detect5G(p))
    }

    // גלישה חופשית באפליקציות נבחרות — getAppsForPlan() returns null for plans
    // without the free-apps benefit (and for all global providers, hence hidden there).
    if (tab !== 'global' && appsFilter !== 'all') {
      const wantApps = appsFilter === 'yes'
      result = result.filter(p => (getAppsForPlan(p) !== null) === wantApps)
    }

    if (sortBy === 'price_asc') result = [...result].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    else if (sortBy === 'price_desc') result = [...result].sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
    else if (sortBy === 'gb_asc') result = [...result].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
    else if (sortBy === 'gb_desc') result = [...result].sort((a, b) => (b.data_gb ?? 99999) - (a.data_gb ?? 99999))

    return result
  }, [plans, selectedCarriers, gbFilter, daysFilter, sortBy, showDays, roamingFilter, genFilter, appsFilter, tab])

  // Chart: average price per carrier
  const chartData = useMemo(() => {
    if (selectedCarriers.length === 0) return []

    return selectedCarriers.map(c => {
      const cids = c === 'airalo' ? ['airalo', 'airalo_local', 'airalo_regional'] : [c]
      const cp = filteredPlans.filter(p => cids.includes(p.carrier) && p.price)
      if (!cp.length) return null
      return {
        name: getLabel(c),
        'מחיר מינימום': Math.min(...cp.map(p => p.price)),
        'מחיר ממוצע': Math.round(cp.reduce((s, p) => s + p.price, 0) / cp.length),
        'מחיר מקסימום': Math.max(...cp.map(p => p.price)),
        fill: getColor(c),
      }
    }).filter(Boolean)
  }, [filteredPlans, selectedCarriers])

  const activeFilterCount = (selectedCarriers.length > 0 ? 1 : 0)
    + (gbFilter !== 'all' ? 1 : 0)
    + (daysFilter !== 'all' ? 1 : 0)
    + (regionFilter !== 'all' ? 1 : 0)
    + (destinationFilter !== 'all' ? 1 : 0)
    + (roamingFilter !== 'all' ? 1 : 0)
    + (genFilter !== 'all' ? 1 : 0)
    + (appsFilter !== 'all' ? 1 : 0)

  const GB_OPTIONS = tab === 'domestic'
    ? [['all', tt('הכל', 'All')], ['0-5', '0-5GB'], ['5-15', '5-15GB'], ['15-100', '15-100GB'], ['100+', '100+GB'], ['unlimited', tt('ללא הגבלה', 'Unlimited')]]
    : [['all', tt('הכל', 'All')], ['0-5', '0-5GB'], ['5-15', '5-15GB'], ['15-100', '15-100GB'], ['unlimited', tt('ללא הגבלה', 'Unlimited')]]

  const TAB_LABELS = {
    domestic: tt('חבילות סלולר', 'Cellular Plans'),
    abroad: tt('חו"ל', 'Roaming'),
    global: tt('גלובלי', 'Global'),
  }
  const translatedTabs = TABS.map(t => ({ ...t, label: TAB_LABELS[t.id] ?? t.label }))

  if (loading) return <div className="flex justify-center py-16"><Spinner /></div>

  return (
    <>
      <PageHeader
        tabs={translatedTabs}
        activeTab={tab}
        onTabChange={setTab}
      />
      <div className="max-w-5xl mx-auto px-4 py-6">

      {/* Filter count + reset row */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-moca-sub flex items-center gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" /></svg>
          {tt('סינון', 'Filter')}
          {activeFilterCount > 0 && (
            <span className="bg-moca-bolt text-white text-[9px] px-1.5 py-0.5 rounded-full min-w-[16px] text-center">{activeFilterCount}</span>
          )}
        </span>
        {activeFilterCount > 0 && (
          <button onClick={resetFilters} className="text-xs font-medium bg-moca-bolt text-white px-2.5 py-1 rounded-lg hover:bg-moca-text transition-colors">
            {tt('איפוס', 'Reset')}
          </button>
        )}
      </div>

      {/* Two-column filters: right = filters, left = carriers */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_320px] gap-3 mb-4 items-start">
        {/* Right column — Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-3 space-y-2">
          {tab === 'global' && (
            <>
              {/* Region + Country side by side with searchable dropdowns */}
              <div className="grid grid-cols-2 gap-2">
                {regionOptions.length > 0 && (
                  <div>
                    <p className="text-[11px] font-medium text-gray-500 mb-1">{tt('אזור', 'Region')}</p>
                    <SearchableSelect
                      value={regionFilter}
                      onChange={val => {
                        setRegionFilter(val)
                        if (val !== 'all') {
                          setDestinationFilter('all')
                          const rTarget = destKey(val)
                          const regionCarriers = [...new Set(plans.filter(p => p.extras && destKey(normalizeRegionLabel(p.extras[0])) === rTarget).map(p => p.carrier))]
                          setSelectedCarriers(regionCarriers)
                        }
                      }}
                      options={regionOptions}
                      placeholder={`${tt('כל האזורים', 'All regions')} (${regionOptions.length})`}
                    />
                  </div>
                )}
                {destinationOptions.length > 0 && (
                  <div>
                    <p className="text-[11px] font-medium text-gray-500 mb-1">{tt('מדינה', 'Country')}</p>
                    <SearchableSelect
                      value={destinationFilter}
                      onChange={val => {
                        setDestinationFilter(val)
                        if (val !== 'all') {
                          setRegionFilter('all')
                          if (val === CRUISE_VALUE) {
                            const cruiseCarriers = [...new Set(plans.filter(p => p.extras && isCruiseDest(p.extras[0])).map(p => p.carrier))]
                            setSelectedCarriers(cruiseCarriers)
                          } else {
                            const carriers = countryCarrierMap[destKey(val)]
                            if (carriers) setSelectedCarriers([...carriers])
                          }
                        }
                      }}
                      options={destinationOptions}
                      placeholder={`${tt('כל המדינות', 'All countries')} (${destinationOptions.length})`}
                    />
                  </div>
                )}
              </div>
            </>
          )}

          <div className={showDays ? 'grid grid-cols-2 gap-3' : tab === 'domestic' ? 'grid grid-cols-2 gap-3' : ''}>
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('גלישה', 'Data')}</p>
              <div className="flex flex-wrap gap-1">
                {GB_OPTIONS.map(([val, label]) => (
                  <FilterTag key={val} label={label} active={gbFilter === val} onClick={() => setGbFilter(val)} />
                ))}
              </div>
            </div>
          {tab === 'domestic' && (
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('גלישה בחו"ל', 'Roaming data')}</p>
              <div className="flex flex-wrap gap-1">
                <FilterTag label={tt('כולם', 'All')} active={roamingFilter === 'all'} onClick={() => setRoamingFilter('all')} />
                <FilterTag label={tt('כולל חו"ל', 'Includes roaming')} active={roamingFilter === 'yes'} onClick={() => setRoamingFilter('yes')} />
              </div>
            </div>
          )}
          {tab === 'domestic' && (
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('דור רשת', 'Network generation')}</p>
              <div className="flex flex-wrap gap-1">
                <FilterTag label={tt('הכל', 'All')} active={genFilter === 'all'} onClick={() => setGenFilter('all')} />
                <FilterTag label="4G" active={genFilter === '4g'} onClick={() => setGenFilter('4g')} />
                <FilterTag label="5G" active={genFilter === '5g'} onClick={() => setGenFilter('5g')} />
                <FilterTag label={tt('5G מתועדף', '5G Priority')} active={genFilter === '5g_priority'} onClick={() => setGenFilter('5g_priority')} />
              </div>
            </div>
          )}

          {showDays && (
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('תוקף', 'Validity')}</p>
              <div className="flex flex-wrap gap-1">
                {[['all', tt('הכל', 'All')], ['1-7', tt('1-7 ימים', '1-7 days')], ['8-14', tt('8-14 ימים', '8-14 days')], ['15-30', tt('15-30 ימים', '15-30 days')], ['30+', tt('30+ ימים', '30+ days')]].map(([val, label]) => (
                  <FilterTag key={val} label={label} active={daysFilter === val} onClick={() => setDaysFilter(val)} />
                ))}
              </div>
            </div>
          )}
          {tab !== 'global' && (
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('גלישה חופשית באפליקציות', 'Free in-app browsing')}</p>
              <div className="flex flex-wrap gap-1">
                <FilterTag label={tt('הכל', 'All')} active={appsFilter === 'all'} onClick={() => setAppsFilter('all')} />
                <FilterTag label={tt('כן', 'Yes')} active={appsFilter === 'yes'} onClick={() => setAppsFilter('yes')} />
                <FilterTag label={tt('לא', 'No')} active={appsFilter === 'no'} onClick={() => setAppsFilter('no')} />
              </div>
            </div>
          )}
          </div>

          <div>
            <p className="text-[11px] font-medium text-gray-500 mb-1.5">{tt('מיון', 'Sort')}</p>
            <div className="flex flex-wrap gap-1">
              <FilterTag label={tt('מחיר ↑', 'Price ↑')} active={sortBy === 'price_asc'} onClick={() => setSortBy('price_asc')} />
              <FilterTag label={tt('מחיר ↓', 'Price ↓')} active={sortBy === 'price_desc'} onClick={() => setSortBy('price_desc')} />
              <FilterTag label="GB ↑" active={sortBy === 'gb_asc'} onClick={() => setSortBy('gb_asc')} />
              <FilterTag label="GB ↓" active={sortBy === 'gb_desc'} onClick={() => setSortBy('gb_desc')} />
          </div>
        </div>
      </div>

        {/* Left column — Carriers */}
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[11px] font-medium text-gray-500">{tt('ספקים', 'Providers')}</p>
            <button
              onClick={() => setSelectedCarriers(prev => prev.length === availableCarriers.length ? [] : availableCarriers.map(c => c.id))}
              className="text-[10px] text-moca-sub hover:text-moca-text"
            >
              {selectedCarriers.length === availableCarriers.length ? tt('נקה', 'Clear') : tt('הכל', 'All')}
            </button>
          </div>
          <div className={`grid gap-1 ${tab === 'domestic' || tab === 'abroad' ? 'grid-cols-2' : 'grid-cols-3'}`}>
            {availableCarriers.map(c => (
              <button
                key={c.id}
                onClick={() => setSelectedCarriers(prev =>
                  prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id]
                )}
                className={`px-1 py-1.5 rounded-md text-[11px] font-medium text-center transition-all duration-150 truncate ${
                  selectedCarriers.includes(c.id) ? 'text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
                }`}
                style={selectedCarriers.includes(c.id) ? { backgroundColor: getColor(c.id) } : {}}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results count */}
      {selectedCarriers.length > 0 && (
        <p className="text-[11px] text-gray-400 mb-3">{filteredPlans.length} {tt('חבילות נמצאו', 'plans found')}</p>
      )}

      {/* Chart: price range per carrier */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <h2
            className="mb-4 text-right"
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 16,
              fontWeight: 700,
              color: 'var(--color-moca-dark)',
              letterSpacing: -0.2,
              margin: '0 0 14px',
            }}
          >
            {tt('טווח מחירים לפי ספק', 'Price range by provider')}
            <span style={{ marginInlineStart: 8, fontSize: 11, fontWeight: 500, color: 'var(--color-moca-muted)', fontFamily: 'var(--font-body)' }}>
              {tt('מינימום · ממוצע · מקסימום', 'Min · Avg · Max')}
            </span>
          </h2>
          <div style={{ direction: 'ltr' }}>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }} barGap={1} barCategoryGap="15%">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} angle={-25} textAnchor="end" height={50} />
                <YAxis label={{ value: '₪', position: 'insideTopLeft' }} tick={{ fontSize: 11 }} width={40} />
                <Tooltip formatter={(val) => `₪${val}`} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="מחיר מינימום" fill="#22c55e" radius={[3, 3, 0, 0]} maxBarSize={28} />
                <Bar dataKey="מחיר ממוצע" fill="#3b82f6" radius={[3, 3, 0, 0]} maxBarSize={28} />
                <Bar dataKey="מחיר מקסימום" fill="#ef4444" radius={[3, 3, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Comparison table */}
      {filteredPlans.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-2 border-b border-gray-100">
            <p className="text-[11px] text-moca-sub flex items-center gap-1.5">
              <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
              {tt('לחצו על שורה למעבר לחבילה בלשונית הרלוונטית', 'Click a row to jump to the plan in the relevant tab')}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" dir="rtl">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">{tt('ספק', 'Provider')}</th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">{tt('שם חבילה', 'Plan name')}</th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">{tt('מחיר ₪', 'Price ₪')}</th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">{tt('גלישה', 'Data')}</th>
                  {showDays && <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">{tt('ימים', 'Days')}</th>}
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">{tt('דקות', 'Minutes')}</th>
                </tr>
              </thead>
              <tbody>
                {filteredPlans.slice(0, tableVisibleCount).map((p, i) => (
                  <tr
                    key={i}
                    onClick={() => goToPlan(p)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToPlan(p) } }}
                    tabIndex={0}
                    role="link"
                    title={tt(`מעבר לחבילה "${p.plan_name}" בלשונית הרלוונטית`, `Go to plan "${p.plan_name}" in the relevant tab`)}
                    className="border-b border-gray-50 hover:bg-moca-cream/60 focus:bg-moca-cream focus:outline-none cursor-pointer transition-colors">
                    <td className="px-4 py-2 text-xs">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium text-white" style={{ backgroundColor: getColor(p.carrier) }}>
                        {getLabel(p.carrier)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-700" dir="rtl" style={{unicodeBidi: 'plaintext'}}>
                      {p.plan_name}
                      {tab === 'domestic' && hasMaxPriority(p) && (
                        <span className="inline-flex items-center px-1.5 py-0.5 mr-1.5 align-middle text-[9px] font-bold rounded bg-violet-50 text-violet-600 leading-none tracking-wide whitespace-nowrap">{tt('5G מתועדף', '5G Priority')}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs font-bold text-gray-900">₪{p.price}</td>
                    <td className="px-4 py-2 text-xs text-gray-600">{p.data_gb === null ? tt('ללא הגבלה', 'Unlimited') : `${Number(p.data_gb).toLocaleString('en-US')}GB`}</td>
                    {showDays && <td className="px-4 py-2 text-xs text-gray-600">{p.days || '-'}</td>}
                    <td className="px-4 py-2 text-xs text-gray-600">{p.minutes ? Number(p.minutes).toLocaleString('en-US') : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {tableVisibleCount < filteredPlans.length && (
            <div className="text-center py-2">
              <button
                onClick={() => setTableVisibleCount(prev => prev + 50)}
                className="text-sm text-moca-bolt hover:text-moca-dark px-4 py-2 rounded-lg border border-moca-border hover:bg-moca-cream transition-colors"
              >
                {tt('\u05D4\u05E6\u05D2 \u05E2\u05D5\u05D3', 'Show more')} ({filteredPlans.length - tableVisibleCount} {tt('\u05E0\u05D5\u05E1\u05E4\u05D9\u05DD', 'more')})
              </button>
            </div>
          )}
        </div>
      )}

      {selectedCarriers.length === 0 && (
        <div className="text-center py-16 text-moca-muted">
          <svg className="mx-auto mb-3 w-10 h-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3v18" /><path d="M4 7h16" /><path d="M4 7l3 8h0a4 4 0 0 0 3.5 2h0A4 4 0 0 0 14 15h0l3-8" /><circle cx="7" cy="15" r="3" /><circle cx="17" cy="15" r="3" />
          </svg>
          <p className="text-sm">{tt('בחר לפחות ספק אחד להשוואה', 'Select at least one provider to compare')}</p>
        </div>
      )}
      </div>
    </>
  )
}
