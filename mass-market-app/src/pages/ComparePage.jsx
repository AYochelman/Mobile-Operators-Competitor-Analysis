import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import FilterTag from '../components/ui/FilterTag'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

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
  ],
}

const COMPARE_MODES = {
  domestic: [
    { id: 'gb_range', label: 'טווח גלישה' },
    { id: 'cheapest', label: 'המחיר הזול ביותר' },
    { id: 'plan_count', label: 'כמות חבילות' },
  ],
  abroad: [
    { id: 'gb_range', label: 'טווח גלישה' },
    { id: 'days_range', label: 'תוקף חבילה' },
    { id: 'cheapest', label: 'המחיר הזול ביותר' },
  ],
  global: [
    { id: 'gb_range', label: 'טווח גלישה' },
    { id: 'days_range', label: 'תוקף חבילה' },
    { id: 'cheapest', label: 'המחיר הזול ביותר' },
    { id: 'country_count', label: 'כמות מדינות' },
  ],
}

export default function ComparePage() {
  const [tab, setTab] = useState('domestic')
  const [compareMode, setCompareMode] = useState('gb_range')
  const [selectedCarriers, setSelectedCarriers] = useState([])
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

  // Reset carriers and mode when tab changes
  useEffect(() => {
    setSelectedCarriers([])
    setCompareMode('gb_range')
  }, [tab])

  const plans = allData[tab] || []
  const carrierOptions = CARRIERS_BY_TAB[tab] || []
  const modes = COMPARE_MODES[tab] || []

  // Available carriers (only those with plans)
  const availableCarriers = useMemo(() => {
    const inData = new Set(plans.map(p => p.carrier))
    return carrierOptions.filter(c => inData.has(c.id))
  }, [plans, carrierOptions])

  const getLabel = (id) => {
    const c = carrierOptions.find(x => x.id === id)
    return c ? c.label : id
  }
  const getColor = (id) => {
    const c = carrierOptions.find(x => x.id === id)
    return c ? c.color : '#888'
  }

  const chartData = useMemo(() => {
    if (selectedCarriers.length === 0) return []
    const filtered = plans.filter(p => selectedCarriers.includes(p.carrier))

    if (compareMode === 'gb_range') {
      const ranges = tab === 'domestic'
        ? ['ללא הגבלה', '0-100GB', '100-500GB', '500+GB']
        : ['ללא הגבלה', '0-5GB', '5-15GB', '15+GB']
      return ranges.map(range => {
        const row = { name: range }
        selectedCarriers.forEach(c => {
          const cp = filtered.filter(p => p.carrier === c)
          let matched
          if (range === 'ללא הגבלה') matched = cp.filter(p => p.data_gb === null)
          else if (range === '0-100GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb <= 100)
          else if (range === '100-500GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb > 100 && p.data_gb <= 500)
          else if (range === '500+GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb > 500)
          else if (range === '0-5GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb <= 5)
          else if (range === '5-15GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb > 5 && p.data_gb <= 15)
          else if (range === '15+GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb > 15)
          else matched = []
          row[c] = matched.length ? Math.round(matched.reduce((s, p) => s + (p.price || 0), 0) / matched.length) : null
        })
        return row
      })
    }

    if (compareMode === 'days_range') {
      const ranges = ['1-7 ימים', '8-30 ימים', '30+ ימים']
      return ranges.map(range => {
        const row = { name: range }
        selectedCarriers.forEach(c => {
          const cp = filtered.filter(p => p.carrier === c)
          let matched
          if (range === '1-7 ימים') matched = cp.filter(p => p.days && p.days <= 7)
          else if (range === '8-30 ימים') matched = cp.filter(p => p.days && p.days > 7 && p.days <= 30)
          else matched = cp.filter(p => p.days && p.days > 30)
          row[c] = matched.length ? Math.round(matched.reduce((s, p) => s + (p.price || 0), 0) / matched.length) : null
        })
        return row
      })
    }

    if (compareMode === 'cheapest') {
      return [{ name: 'מחיר מינימום', ...Object.fromEntries(
        selectedCarriers.map(c => {
          const cp = filtered.filter(p => p.carrier === c && p.price)
          const min = cp.length ? Math.min(...cp.map(p => p.price)) : null
          return [c, min]
        })
      )}, { name: 'מחיר ממוצע', ...Object.fromEntries(
        selectedCarriers.map(c => {
          const cp = filtered.filter(p => p.carrier === c && p.price)
          const avg = cp.length ? Math.round(cp.reduce((s, p) => s + p.price, 0) / cp.length) : null
          return [c, avg]
        })
      )}, { name: 'מחיר מקסימום', ...Object.fromEntries(
        selectedCarriers.map(c => {
          const cp = filtered.filter(p => p.carrier === c && p.price)
          const max = cp.length ? Math.max(...cp.map(p => p.price)) : null
          return [c, max]
        })
      )}]
    }

    if (compareMode === 'plan_count') {
      return [{ name: 'כמות חבילות', ...Object.fromEntries(
        selectedCarriers.map(c => [c, filtered.filter(p => p.carrier === c).length])
      )}]
    }

    if (compareMode === 'country_count') {
      return [{ name: 'מדינות', ...Object.fromEntries(
        selectedCarriers.map(c => {
          const countries = new Set(filtered.filter(p => p.carrier === c && p.extras && p.extras[0]).map(p => p.extras[0]))
          return [c, countries.size]
        })
      )}]
    }

    return []
  }, [plans, selectedCarriers, compareMode, tab])

  const yLabel = compareMode === 'plan_count' || compareMode === 'country_count' ? '' : '₪'
  const tooltipFormat = (val) => {
    if (val === null) return '—'
    if (compareMode === 'plan_count') return `${val} חבילות`
    if (compareMode === 'country_count') return `${val} מדינות`
    return `₪${val}`
  }

  if (loading) return <div className="flex justify-center py-16"><Spinner /></div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-4">⚖️ השוואת מחירים</h1>

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

      {/* Compare mode */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <p className="text-xs font-medium text-gray-500 mb-2">השווה לפי:</p>
        <div className="flex flex-wrap gap-1.5">
          {modes.map(m => (
            <FilterTag key={m.id} label={m.label} active={compareMode === m.id} onClick={() => setCompareMode(m.id)} />
          ))}
        </div>
      </div>

      {/* Carrier selection */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
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

      {/* Chart */}
      {selectedCarriers.length > 0 && chartData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-bold mb-4">
            {compareMode === 'gb_range' && 'מחיר ממוצע לפי טווח גלישה'}
            {compareMode === 'days_range' && 'מחיר ממוצע לפי תוקף חבילה'}
            {compareMode === 'cheapest' && 'טווח מחירים (מינימום / ממוצע / מקסימום)'}
            {compareMode === 'plan_count' && 'כמות חבילות לפי ספק'}
            {compareMode === 'country_count' && 'כמות מדינות לפי ספק'}
          </h2>
          <div style={{ direction: 'ltr' }}>
            <ResponsiveContainer width="100%" height={380}>
              <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis label={yLabel ? { value: yLabel, position: 'insideTopLeft' } : undefined} tick={{ fontSize: 12 }} />
                <Tooltip formatter={tooltipFormat} />
                <Legend />
                {selectedCarriers.map(c => (
                  <Bar key={c} dataKey={c} name={getLabel(c)} fill={getColor(c)} radius={[4, 4, 0, 0]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
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
