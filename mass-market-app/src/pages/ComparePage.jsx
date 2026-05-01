import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import FilterTag from '../components/ui/FilterTag'
import SearchableSelect from '../components/ui/SearchableSelect'
import { has5G as detect5G, hasMaxPriority } from '../data/networkPriority'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import {
  AIRALO_DISCOVER, AIRALO_REGION_MAP, GLOBALESIM_COUNTRIES, TUKI_COUNTRIES, SIMTLV_COUNTRIES,
  PELEPHONE_GLOBAL_COUNTRIES, ESIMO_COUNTRIES, WORLD8_WORLDWIDE, WORLD8_EUROPE_USA,
  XPHONE_EUROPE, XPHONE_WORLD, ORBIT_COUNTRIES, TRAVELSIM_GLOBAL, TRAVELSIM_USA, TRAVELSIM_ME,
  getCountriesForPlan
} from '../data/globalCountries'
import { DOMESTIC_LABELS, GLOBAL_LABELS } from '../data/carrierLabels'
import { KNOWN_REGIONS, CARRIER_COUNTRY_LISTS as MULTI_CARRIER_COUNTRY_LISTS } from '../data/multiCountry'

// Chart colors per carrier — kept here because they're specific to the
// comparison chart's visual identity. Labels come from carrierLabels.js
// (single source of truth).
const COMPARE_COLORS_DOMESTIC = {
  partner: '#e91e63', pelephone: '#2196f3', hotmobile: '#ff5722',
  cellcom: '#4caf50', mobile019: '#9c27b0', xphone: '#0d9488',
  wecom: '#d97706', neptucom: '#d97706', golan: '#009688', rami_levy: '#e32032',
}
const COMPARE_COLORS_GLOBAL = {
  tuki: '#3b82f6', globalesim: '#22c55e', airalo: '#f97316',
  pelephone_global: '#2196f3', esimo: '#a855f7', simtlv: '#ef4444',
  world8: '#0d9488', xphone_global: '#14b8a6', saily: '#7c3aed',
  holafly: '#ea580c', esimio: '#2563eb', sparks: '#f59e0b',
  voye: '#ec4899', orbit: '#6366f1', travelsim: '#0d9488',
  gomoworld: '#0891b2', tasim: '#7c3aed', maya: '#0f766e',
  bcengi: '#1d4ed8', esim70: '#10b981', jetpack: '#0ea5e9',
  breez: '#06b6d4', bytesim: '#00b490',
}

function _build(carrierIds, labelSource, colorSource) {
  return carrierIds
    .filter(id => id !== 'airalo_local' && id !== 'airalo_regional')
    .map(id => ({
      id,
      label: labelSource[id] || id,
      color: colorSource[id] || '#888',
    }))
}

const TABS = [
  { id: 'domestic', label: 'חבילות סלולר' },
  { id: 'abroad', label: 'חו"ל' },
  { id: 'global', label: 'גלובלי' },
]

// Domestic and abroad share the same carrier set. Global is the eSIM list.
// Built from the centralized labels — adding a new carrier in
// data/carrierLabels.js + adding an entry to COMPARE_COLORS_* above
// is enough; no other change needed here.
const _DOMESTIC_TAB = _build(Object.keys(DOMESTIC_LABELS), DOMESTIC_LABELS, COMPARE_COLORS_DOMESTIC)
const _GLOBAL_TAB = _build(Object.keys(GLOBAL_LABELS), GLOBAL_LABELS, COMPARE_COLORS_GLOBAL)
const CARRIERS_BY_TAB = {
  domestic: _DOMESTIC_TAB,
  abroad:   _DOMESTIC_TAB,
  global:   _GLOBAL_TAB,
}

// KNOWN_REGIONS imported from data/multiCountry.js (single source of truth).

export default function ComparePage() {
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
  }, [selectedCarriers, gbFilter, daysFilter, regionFilter, destinationFilter, sortBy, genFilter])

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
  const getColor = (id) => carrierOptions.find(x => x.id === id)?.color || '#888'

  // Pull from data/multiCountry.js (shared with DashboardPage). Wrapped in
  // useMemo only so the dependency array of the next useMemo can stay stable.
  const CARRIER_COUNTRY_LISTS = MULTI_CARRIER_COUNTRY_LISTS

  // Build complete country → carriers mapping
  const { availableRegions, availableDestinations, countryCarrierMap } = useMemo(() => {
    if (tab !== 'global') return { availableRegions: [], availableDestinations: [], countryCarrierMap: {} }

    const map = {} // country → Set of carrier ids

    // From extras[0] (saily, holafly, esimio per-country plans)
    plans.forEach(p => {
      if (p.extras && p.extras[0] && !/\d/.test(p.extras[0]) && !KNOWN_REGIONS.has(p.extras[0])) {
        if (!map[p.extras[0]]) map[p.extras[0]] = new Set()
        map[p.extras[0]].add(p.carrier)
      }
    })

    // From static country lists (tuki, airalo, globalesim, etc.)
    Object.entries(CARRIER_COUNTRY_LISTS).forEach(([carrier, countries]) => {
      // Only add if carrier has plans in data
      if (plans.some(p => p.carrier === carrier)) {
        countries.forEach(country => {
          if (!map[country]) map[country] = new Set()
          map[country].add(carrier)
        })
      }
    })

    // Also index saily/holafly/esimio regional plans' included countries
    plans.forEach(p => {
      if (p.extras && p.extras[0] && KNOWN_REGIONS.has(p.extras[0])) {
        const data = getCountriesForPlan(p)
        if (data && data.countries) {
          data.countries.forEach(country => {
            if (!map[country]) map[country] = new Set()
            map[country].add(p.carrier)
          })
        }
      }
    })

    const regions = [...new Set(plans.filter(p => p.extras && p.extras[0] && KNOWN_REGIONS.has(p.extras[0])).map(p => p.extras[0]))].sort((a, b) => a.localeCompare(b, 'he'))
    const destinations = Object.keys(map).sort((a, b) => a.localeCompare(b, 'he'))

    return { availableRegions: regions, availableDestinations: destinations, countryCarrierMap: map }
  }, [plans, tab, CARRIER_COUNTRY_LISTS])

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
      result = result.filter(p => p.extras && p.extras[0] === regionFilter)
    } else if (destinationFilter !== 'all') {
      const carriersForCountry = countryCarrierMap[destinationFilter] || new Set()
      result = result.filter(p => {
        if (!carriersForCountry.has(p.carrier)) return false

        const ext = p.extras && p.extras[0]

        // Per-country plan (extras[0] = country name, not a region)
        if (ext && !KNOWN_REGIONS.has(ext) && !/\d/.test(ext)) {
          return ext === destinationFilter
        }

        // Regional plan (extras[0] = region name like "אירופה")
        if (ext && KNOWN_REGIONS.has(ext)) {
          const regionData = getCountriesForPlan(p)
          if (regionData && regionData.countries) {
            return regionData.countries.includes(destinationFilter)
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
      result = result.filter(p => p.extras && p.extras.some(e => /חו"ל|חו״ל/.test(e) && /\d+/.test(e) && /GB|גלישה/i.test(e)))
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

    if (sortBy === 'price_asc') result = [...result].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    else if (sortBy === 'price_desc') result = [...result].sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
    else if (sortBy === 'gb_asc') result = [...result].sort((a, b) => (a.data_gb ?? 99999) - (b.data_gb ?? 99999))
    else if (sortBy === 'gb_desc') result = [...result].sort((a, b) => (b.data_gb ?? 99999) - (a.data_gb ?? 99999))

    return result
  }, [plans, selectedCarriers, gbFilter, daysFilter, sortBy, showDays, roamingFilter, genFilter, tab])

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

  const GB_OPTIONS = tab === 'domestic'
    ? [['all', 'הכל'], ['0-5', '0-5GB'], ['5-15', '5-15GB'], ['15-100', '15-100GB'], ['100+', '100+GB'], ['unlimited', 'ללא הגבלה']]
    : [['all', 'הכל'], ['0-5', '0-5GB'], ['5-15', '5-15GB'], ['15-100', '15-100GB'], ['unlimited', 'ללא הגבלה']]

  if (loading) return <div className="flex justify-center py-16"><Spinner /></div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      {/* Tab selector */}
      <div className="flex gap-1 mb-4">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t.id ? 'bg-moca-bolt text-white' : 'bg-white text-moca-sub border border-moca-border hover:bg-moca-cream hover:text-moca-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filter count + reset row */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-moca-sub flex items-center gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" /></svg>
          סינון
          {activeFilterCount > 0 && (
            <span className="bg-moca-bolt text-white text-[9px] px-1.5 py-0.5 rounded-full min-w-[16px] text-center">{activeFilterCount}</span>
          )}
        </span>
        {activeFilterCount > 0 && (
          <button onClick={resetFilters} className="text-xs font-medium bg-moca-bolt text-white px-2.5 py-1 rounded-lg hover:bg-moca-text transition-colors">
            איפוס
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
                {availableRegions.length > 0 && (
                  <div>
                    <p className="text-[11px] font-medium text-gray-500 mb-1">אזור</p>
                    <SearchableSelect
                      value={regionFilter}
                      onChange={val => {
                        setRegionFilter(val)
                        if (val !== 'all') {
                          setDestinationFilter('all')
                          const regionCarriers = [...new Set(plans.filter(p => p.extras && p.extras[0] === val).map(p => p.carrier))]
                          setSelectedCarriers(regionCarriers)
                        }
                      }}
                      options={availableRegions.map(r => ({ value: r, label: r }))}
                      placeholder={`כל האזורים (${availableRegions.length})`}
                    />
                  </div>
                )}
                {availableDestinations.length > 0 && (
                  <div>
                    <p className="text-[11px] font-medium text-gray-500 mb-1">מדינה</p>
                    <SearchableSelect
                      value={destinationFilter}
                      onChange={val => {
                        setDestinationFilter(val)
                        if (val !== 'all') {
                          setRegionFilter('all')
                          const carriers = countryCarrierMap[val]
                          if (carriers) setSelectedCarriers([...carriers])
                        }
                      }}
                      options={availableDestinations.map(c => {
                        const n = countryCarrierMap[c] ? countryCarrierMap[c].size : 0
                        return { value: c, label: `${c} (${n})` }
                      })}
                      placeholder={`כל המדינות (${availableDestinations.length})`}
                    />
                  </div>
                )}
              </div>
            </>
          )}

          <div className={showDays ? 'grid grid-cols-2 gap-3' : tab === 'domestic' ? 'grid grid-cols-2 gap-3' : ''}>
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">גלישה</p>
              <div className="flex flex-wrap gap-1">
                {GB_OPTIONS.map(([val, label]) => (
                  <FilterTag key={val} label={label} active={gbFilter === val} onClick={() => setGbFilter(val)} />
                ))}
              </div>
            </div>
          {tab === 'domestic' && (
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">גלישה בחו"ל</p>
              <div className="flex flex-wrap gap-1">
                <FilterTag label="כולם" active={roamingFilter === 'all'} onClick={() => setRoamingFilter('all')} />
                <FilterTag label='כולל חו"ל' active={roamingFilter === 'yes'} onClick={() => setRoamingFilter('yes')} />
              </div>
            </div>
          )}
          {tab === 'domestic' && (
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">דור רשת</p>
              <div className="flex flex-wrap gap-1">
                <FilterTag label="הכל" active={genFilter === 'all'} onClick={() => setGenFilter('all')} />
                <FilterTag label="4G" active={genFilter === '4g'} onClick={() => setGenFilter('4g')} />
                <FilterTag label="5G" active={genFilter === '5g'} onClick={() => setGenFilter('5g')} />
                <FilterTag label="5G מתועדף" active={genFilter === '5g_priority'} onClick={() => setGenFilter('5g_priority')} />
              </div>
            </div>
          )}

          {showDays && (
            <div>
              <p className="text-[11px] font-medium text-gray-500 mb-1.5">תוקף</p>
              <div className="flex flex-wrap gap-1">
                {[['all', 'הכל'], ['1-7', '1-7 ימים'], ['8-14', '8-14 ימים'], ['15-30', '15-30 ימים'], ['30+', '30+ ימים']].map(([val, label]) => (
                  <FilterTag key={val} label={label} active={daysFilter === val} onClick={() => setDaysFilter(val)} />
                ))}
              </div>
            </div>
          )}
          </div>

          <div>
            <p className="text-[11px] font-medium text-gray-500 mb-1.5">מיון</p>
            <div className="flex flex-wrap gap-1">
              <FilterTag label="מחיר ↑" active={sortBy === 'price_asc'} onClick={() => setSortBy('price_asc')} />
              <FilterTag label="מחיר ↓" active={sortBy === 'price_desc'} onClick={() => setSortBy('price_desc')} />
              <FilterTag label="GB ↑" active={sortBy === 'gb_asc'} onClick={() => setSortBy('gb_asc')} />
              <FilterTag label="GB ↓" active={sortBy === 'gb_desc'} onClick={() => setSortBy('gb_desc')} />
          </div>
        </div>
      </div>

        {/* Left column — Carriers */}
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[11px] font-medium text-gray-500">ספקים</p>
            <button
              onClick={() => setSelectedCarriers(prev => prev.length === availableCarriers.length ? [] : availableCarriers.map(c => c.id))}
              className="text-[10px] text-moca-sub hover:text-moca-text"
            >
              {selectedCarriers.length === availableCarriers.length ? 'נקה' : 'הכל'}
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
                style={selectedCarriers.includes(c.id) ? { backgroundColor: c.color } : {}}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results count */}
      {selectedCarriers.length > 0 && (
        <p className="text-[11px] text-gray-400 mb-3">{filteredPlans.length} חבילות נמצאו</p>
      )}

      {/* Chart: price range per carrier */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <h2 className="text-sm font-bold mb-4">טווח מחירים לפי ספק (מינימום / ממוצע / מקסימום)</h2>
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm" dir="rtl">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">ספק</th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">שם חבילה</th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">מחיר ₪</th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">גלישה</th>
                  {showDays && <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">ימים</th>}
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-gray-500">דקות</th>
                </tr>
              </thead>
              <tbody>
                {filteredPlans.slice(0, tableVisibleCount).map((p, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="px-4 py-2 text-xs">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium text-white" style={{ backgroundColor: getColor(p.carrier) }}>
                        {getLabel(p.carrier)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-700" dir="rtl" style={{unicodeBidi: 'plaintext'}}>{p.plan_name}</td>
                    <td className="px-4 py-2 text-xs font-bold text-gray-900">₪{p.price}</td>
                    <td className="px-4 py-2 text-xs text-gray-600">{p.data_gb === null ? 'ללא הגבלה' : `${p.data_gb}GB`}</td>
                    {showDays && <td className="px-4 py-2 text-xs text-gray-600">{p.days || '—'}</td>}
                    <td className="px-4 py-2 text-xs text-gray-600">{p.minutes || '—'}</td>
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
                {'\u05D4\u05E6\u05D2 \u05E2\u05D5\u05D3'} ({filteredPlans.length - tableVisibleCount} {'\u05E0\u05D5\u05E1\u05E4\u05D9\u05DD'})
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
          <p className="text-sm">בחר לפחות ספק אחד להשוואה</p>
        </div>
      )}
    </div>
  )
}
