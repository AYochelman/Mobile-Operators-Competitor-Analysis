import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function TrendsPage() {
  const [changes, setChanges] = useState([])
  const [loading, setLoading] = useState(true)
  const [carrier, setCarrier] = useState('all')

  useEffect(() => {
    api.getChanges(500).then(c => { setChanges(c); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const LABELS = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com' }

  const priceChanges = changes.filter(c => c.change_type === 'price_change' && (carrier === 'all' || c.carrier === carrier))

  // Group by date
  const byDate = {}
  priceChanges.forEach(c => {
    const date = c.changed_at?.slice(0, 10) || 'unknown'
    if (!byDate[date]) byDate[date] = { date, count: 0, up: 0, down: 0 }
    byDate[date].count++
    const oldV = parseFloat(c.old_val) || 0
    const newV = parseFloat(c.new_val) || 0
    if (newV > oldV) byDate[date].up++
    else byDate[date].down++
  })
  const chartData = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))

  if (loading) return <div className="flex justify-center py-16"><Spinner /></div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-4">📈 מגמות מחירים</h1>

      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
        <select
          value={carrier}
          onChange={e => setCarrier(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="all">כל הספקים</option>
          {Object.entries(LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {chartData.length > 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-bold mb-4">שינויי מחיר לפי תאריך</h2>
          <div style={{ direction: 'ltr' }}>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="up" name="עליות" stroke="#ef4444" strokeWidth={2} />
                <Line type="monotone" dataKey="down" name="ירידות" stroke="#22c55e" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">📉</p>
          <p>אין נתוני שינויי מחיר להצגה</p>
        </div>
      )}

      {/* Recent changes list */}
      <div className="mt-6 bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="text-sm font-bold mb-4">שינויים אחרונים ({priceChanges.length})</h2>
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {priceChanges.slice(0, 50).map((c, i) => (
            <div key={i} className="flex items-center justify-between text-sm border-b border-gray-50 pb-2">
              <div>
                <span className="font-medium">{LABELS[c.carrier] || c.carrier}</span>
                <span className="text-gray-400 mx-2">—</span>
                <span className="text-gray-600">{c.plan_name}</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-gray-400">₪{c.old_val}</span>
                <span>→</span>
                <span className={parseFloat(c.new_val) < parseFloat(c.old_val) ? 'text-green-600 font-bold' : 'text-red-600 font-bold'}>
                  ₪{c.new_val}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
