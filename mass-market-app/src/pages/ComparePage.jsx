import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function ComparePage() {
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCarriers, setSelectedCarriers] = useState([])

  useEffect(() => {
    api.getPlans().then(p => { setPlans(p); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const carriers = useMemo(() => [...new Set(plans.map(p => p.carrier))], [plans])
  const LABELS = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com' }
  const COLORS = { partner: '#e91e63', pelephone: '#2196f3', hotmobile: '#ff5722', cellcom: '#4caf50', mobile019: '#9c27b0', xphone: '#0d9488', wecom: '#d97706' }

  const chartData = useMemo(() => {
    if (selectedCarriers.length === 0) return []
    const filtered = plans.filter(p => selectedCarriers.includes(p.carrier))
    // Group by GB range
    const ranges = ['ללא הגבלה', '0-100GB', '100-500GB', '500+GB']
    return ranges.map(range => {
      const row = { name: range }
      selectedCarriers.forEach(c => {
        const cp = filtered.filter(p => p.carrier === c)
        let matched
        if (range === 'ללא הגבלה') matched = cp.filter(p => p.data_gb === null)
        else if (range === '0-100GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb <= 100)
        else if (range === '100-500GB') matched = cp.filter(p => p.data_gb !== null && p.data_gb > 100 && p.data_gb <= 500)
        else matched = cp.filter(p => p.data_gb !== null && p.data_gb > 500)
        const avg = matched.length ? Math.round(matched.reduce((s, p) => s + (p.price || 0), 0) / matched.length) : null
        row[c] = avg
      })
      return row
    })
  }, [plans, selectedCarriers])

  if (loading) return <div className="flex justify-center py-16"><Spinner /></div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-4">⚖️ השוואת מחירים</h1>

      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
        <p className="text-sm font-medium text-gray-600 mb-3">בחר חברות להשוואה:</p>
        <div className="flex flex-wrap gap-2">
          {carriers.map(c => (
            <button
              key={c}
              onClick={() => setSelectedCarriers(prev =>
                prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]
              )}
              className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                selectedCarriers.includes(c) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {LABELS[c] || c}
            </button>
          ))}
        </div>
      </div>

      {selectedCarriers.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-bold mb-4">מחיר ממוצע לפי טווח גלישה</h2>
          <div style={{ direction: 'ltr' }}>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis label={{ value: '₪', position: 'insideTopLeft' }} />
                <Tooltip formatter={(val) => val ? `₪${val}` : '—'} />
                <Legend />
                {selectedCarriers.map(c => (
                  <Bar key={c} dataKey={c} name={LABELS[c]} fill={COLORS[c] || '#888'} radius={[4, 4, 0, 0]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {selectedCarriers.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">⚖️</p>
          <p>בחר לפחות חברה אחת להשוואה</p>
        </div>
      )}
    </div>
  )
}
