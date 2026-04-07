import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import FilterTag from '../components/ui/FilterTag'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import {
  AIRALO_DISCOVER, GLOBALESIM_COUNTRIES, TUKI_COUNTRIES, SIMTLV_COUNTRIES,
  PELEPHONE_GLOBAL_COUNTRIES, ESIMO_COUNTRIES, WORLD8_WORLDWIDE, WORLD8_EUROPE_USA,
  XPHONE_EUROPE, XPHONE_WORLD, getCountriesForPlan
} from '../data/globalCountries'

const TABS = [
  { id: 'domestic', label: 'Mass Market' },
  { id: 'abroad', label: 'חו"ל' },
  { id: 'global', label: 'גלובלי' },
]

const CARRIERS_BY_TAB = {
  domestic: [
    { id: 'partner', label: 'פרטנר', color: '#e91e63' },
    { id: 'pelephone', label: 'פלאפון', color: '#2196f3' },
    { id: 'hotmobile', label: 'הוט מובייל', color: '#ff5722' },
    { id: 'cellcom', label: 'סלקום', color: '#4caf50' },
    { id: 'mobile019', label: '019', color: '#9c27b0' },
    { id: 'xphone', label: 'XPhone', color: '#0d9488' },
    { id: 'wecom', label: 'We-Com', color: '#d97706' },
  ],
  abroad: [
    { id: 'partner', label: 'פרטנר', color: '#e91e63' },
    { id: 'pelephone', label: 'פלאפון', color: '#2196f3' },
    { id: 'hotmobile', label: 'הוט מובייל', color: '#ff5722' },
    { id: 'cellcom', label: 'סלקום', color: '#4caf50' },
    { id: 'mobile019', label: '019', color: '#9c27b0' },
    { id: 'xphone', label: 'XPhone', color: '#0d9488' },
    { id: 'wecom', label: 'We-Com', color: '#d97706' },
  ],
  global: [
    { id: 'tuki', label: 'Tuki', color: '#3b82f6' },
    { id: 'globalesim', label: 'GlobaleSIM', color: '#22c55e' },
    { id: 'airalo', label: 'Airalo', color: '#f97316' },
    { id: 'pelephone_global', label: 'GlobalSIM', color: '#2196f3' },
    { id: 'esimo', label: 'eSIMo', color: '#a855f7' },
    { id: 'simtlv', label: 'SimTLV', color: '#ef4444' },
    { id: 'world8', label: '8 World', color: '#0d9488' },
    { id: 'xphone_global', label: 'XPhone Global', color: '#14b8a6' },
    { id: 'saily', label: 'Saily', color: '#7c3aed' },
    { id: 'holafly', label: 'Holafly', color: '#ea580c' },
    { id: 'esimio', label: 'eSIM.io', color: '#2563eb' },
    { id: 'sparks', label: 'Sparks', color: '#f59e0b' },
  ],
}

const KNOWN_REGIONS = new Set([
  'אירופה','אסיה','אסיה ואוקיאניה','אפריקה','גלובלי','קריביים','איי הקריביים',
  'אמריקה הלטינית','צפון אמריקה','המזרח התיכון','המזרח התיכון וצפון אפריקה',
  'דרום מזרח אסיה','סקנדינביה','בלקן','מזרח אירופה','מרכז אמריקה','אוקיאניה',
  'סין + הונג קונג + מקאו','יפן וקוריאה','יפן וסין',
  'אסיה פסיפיק','מרכז אסיה','צפון אפריקה',
  'אמריקה הדרומית','דרום אמריקה',
])

export default function ComparePage() {
  const [tab, setTab] = useState('domestic')
  const [selectedCarriers, setSelectedCarriers] = useState([])
  const [gbFilter, setGbFilter] = useState('all')
  const [daysFilter, setDaysFilter] = useState('all')
  const [regionFilter, setRegionFilter] = useState('all')
  const [destinationFilter, setDestinationFilter] = useState('all')
  const [sortBy, setSortBy] = useState('price_asc')
  const [allData, setAllData] = useState({ domestic: [], abroad: [], global: [] })
  const [loading, setLoading] = useState(true)

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

  const resetFilters = () => {
    setSelectedCarriers([])
    setGbFilter('all')
    setDaysFilter('all')
    setRegionFilter('all')
    setDestinationFilter('all')
    setSortBy('price_asc')
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

  // Static country lists for carriers that don't store country in extras
  const CARRIER_COUNTRY_LISTS = useMemo(() => ({
    tuki: TUKI_COUNTRIES,
    globalesim: GLOBALESIM_COUNTRIES,
    airalo: AIRALO_DISCOVER,
    pelephone_global: PELEPHONE_GLOBAL_COUNTRIES,
    esimo: ESIMO_COUNTRIES,
    simtlv: SIMTLV_COUNTRIES,
    world8: [...new Set([...WORLD8_WORLDWIDE, ...WORLD8_EUROPE_USA])],
    xphone_global: [...new Set([...XPHONE_EUROPE, ...XPHONE_WORLD])],
  }), [])

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
    let result = plans.filter(p => selectedCarriers.includes(p.carrier))

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
      else if (daysFilter === '8-30') result = result.filter(p => p.days && p.days > 7 && p.days <= 30)
      else if (daysFilter === '30+') result = result.filter(p => p.days && p.days > 30)
    }

    if (sortBy === 'price_asc') result = [...result].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    else if (sortBy === 'price_desc') result = [...result].sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
    else if (sortBy === 'gb_desc') result = [...result].sort((a, b) => (b.data_gb ?? 99999) - (a.data_gb ?? 99999))

    return result
  }, [plans, selectedCarriers, gbFilter, daysFilter, sortBy, showDays])

  // Chart: average price per carrier
  const chartData = useMemo(() => {
    if (selectedCarriers.length === 0) return []

    return selectedCarriers.map(c => {
      const cp = filteredPlans.filter(p => p.carrier === c && p.price)
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

  const GB_OPTIONS = tab === 'domestic'
    ? [['all', 'הכל'], ['0-5', '0-5GB'], ['5-15', '5-15GB'], ['15-100', '15-100GB'], ['100+', '100+GB'], ['unlimited', 'ללא הגבלה']]
    : [['all', 'הכל'], ['0-5', '0-5GB'], ['5-15', '5-15GB'], ['15-100', '15-100GB'], ['unlimited', 'ללא הגבלה']]

  if (loading) return <div className="flex justify-center py-16"><Spinner /></div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">⚖️ השוואת מחירים</h1>
        {(selectedCarriers.length > 0 || gbFilter !== 'all' || daysFilter !== 'all' || regionFilter !== 'all' || destinationFilter !== 'all') && (
          <button onClick={resetFilters} className="text-xs text-red-500 hover:text-red-700 transition-colors">
            🔄 איפוס
          </button>
        )}
      </div>

      {/* Tab selector */}
      <div className="flex gap-1 mb-4">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t.id ? 'bg-gray-900 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Carrier selection */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-medium text-gray-500">בחר ספקים:</p>
          <button
            onClick={() => setSelectedCarriers(prev => prev.length === availableCarriers.length ? [] : availableCarriers.map(c => c.id))}
            className="text-[11px] text-blue-500 hover:text-blue-700"
          >
            {selectedCarriers.length === availableCarriers.length ? 'נקה הכל' : 'בחר הכל'}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {availableCarriers.map(c => (
            <button
              key={c.id}
              onClick={() => setSelectedCarriers(prev =>
                prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id]
              )}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                selectedCarriers.includes(c.id) ? 'text-white border-transparent' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
              style={selectedCarriers.includes(c.id) ? { backgroundColor: c.color, borderColor: c.color } : {}}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filters — all combinable */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 space-y-3">
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">גלישה</p>
          <div className="flex flex-wrap gap-1.5">
            {GB_OPTIONS.map(([val, label]) => (
              <FilterTag key={val} label={label} active={gbFilter === val} onClick={() => setGbFilter(val)} />
            ))}
          </div>
        </div>

        {showDays && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">תוקף</p>
            <div className="flex flex-wrap gap-1.5">
              {[['all', 'הכל'], ['1-7', '1-7 ימים'], ['8-30', '8-30 ימים'], ['30+', '30+ ימים']].map(([val, label]) => (
                <FilterTag key={val} label={label} active={daysFilter === val} onClick={() => setDaysFilter(val)} />
              ))}
            </div>
          </div>
        )}

        {tab === 'global' && availableRegions.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">אזור</p>
            <select
              value={regionFilter}
              onChange={e => {
                const val = e.target.value
                setRegionFilter(val)
                if (val !== 'all') {
                  setDestinationFilter('all')
                  // Auto-select carriers that have plans for this region
                  const regionCarriers = [...new Set(plans.filter(p => p.extras && p.extras[0] === val).map(p => p.carrier))]
                  setSelectedCarriers(regionCarriers)
                }
              }}
              className={`border rounded-lg px-3 py-1.5 text-xs ${regionFilter !== 'all' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
            >
              <option value="all">כל האזורים ({availableRegions.length})</option>
              {availableRegions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        )}

        {tab === 'global' && availableDestinations.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">מדינה</p>
            <select
              value={destinationFilter}
              onChange={e => {
                const val = e.target.value
                setDestinationFilter(val)
                if (val !== 'all') {
                  setRegionFilter('all')
                  // Auto-select carriers that cover this country
                  const carriers = countryCarrierMap[val]
                  if (carriers) setSelectedCarriers([...carriers])
                }
              }}
              className={`border rounded-lg px-3 py-1.5 text-xs ${destinationFilter !== 'all' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
            >
              <option value="all">כל המדינות ({availableDestinations.length})</option>
              {availableDestinations.map(c => {
                const n = countryCarrierMap[c] ? countryCarrierMap[c].size : 0
                return <option key={c} value={c}>{c} ({n} ספקים)</option>
              })}
            </select>
          </div>
        )}

        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">מיון</p>
          <div className="flex flex-wrap gap-1.5">
            <FilterTag label="מחיר ↑" active={sortBy === 'price_asc'} onClick={() => setSortBy('price_asc')} />
            <FilterTag label="מחיר ↓" active={sortBy === 'price_desc'} onClick={() => setSortBy('price_desc')} />
            <FilterTag label="GB ↓" active={sortBy === 'gb_desc'} onClick={() => setSortBy('gb_desc')} />
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
              <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis label={{ value: '₪', position: 'insideTopLeft' }} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(val) => `₪${val}`} />
                <Legend />
                <Bar dataKey="מחיר מינימום" fill="#22c55e" radius={[4, 4, 0, 0]} />
                <Bar dataKey="מחיר ממוצע" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="מחיר מקסימום" fill="#ef4444" radius={[4, 4, 0, 0]} />
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
                {filteredPlans.slice(0, 50).map((p, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="px-4 py-2 text-xs">
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium text-white" style={{ backgroundColor: getColor(p.carrier) }}>
                        {getLabel(p.carrier)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-700"><bdi>{p.plan_name}</bdi></td>
                    <td className="px-4 py-2 text-xs font-bold text-gray-900">₪{p.price}</td>
                    <td className="px-4 py-2 text-xs text-gray-600">{p.data_gb === null ? 'ללא הגבלה' : `${p.data_gb}GB`}</td>
                    {showDays && <td className="px-4 py-2 text-xs text-gray-600">{p.days || '—'}</td>}
                    <td className="px-4 py-2 text-xs text-gray-600">{p.minutes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filteredPlans.length > 50 && (
            <p className="text-center text-[11px] text-gray-400 py-2">מציג 50 מתוך {filteredPlans.length}</p>
          )}
        </div>
      )}

      {selectedCarriers.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">⚖️</p>
          <p>בחר לפחות ספק אחד להשוואה</p>
        </div>
      )}
    </div>
  )
}
