import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceDot,
} from 'recharts'
import Modal from './ui/Modal'
import Spinner from './ui/Spinner'
import { api } from '../lib/api'

function formatDate(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y.slice(2)}`
}

function StatBox({ label, value, color = 'text-gray-800' }) {
  return (
    <div className="bg-moca-cream/50 rounded-lg p-3 text-center">
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-[11px] text-gray-500 mt-0.5">{label}</div>
    </div>
  )
}

export default function PriceHistoryModal({ open, onClose, carrier, planName, planType = 'domestic', currentPrice }) {
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [points, setPoints]   = useState([])

  // Plan types tracked by the history pipeline. Others (e.g. 'resellers') skip the API call
  // and render the empty state directly — there's no historical series for them.
  const HAS_HISTORY = ['domestic', 'abroad', 'global', 'content']

  useEffect(() => {
    if (!open || !carrier || !planName) return
    if (!HAS_HISTORY.includes(planType)) {
      setLoading(false); setError(null); setPoints([])
      return
    }
    let cancelled = false
    setLoading(true); setError(null); setPoints([])
    api.getHistoryPriceSeries(carrier, planType, planName, '')
      .then(res => {
        if (cancelled) return
        const series = (res?.series || [])
        const match = series.find(s => s.plan_name === planName) || series[0]
        setPoints(match?.points || [])
      })
      .catch(e => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [open, carrier, planName, planType])

  const chartData = useMemo(() => points.map(p => ({ date: p.date, price: p.price })), [points])

  const stats = useMemo(() => {
    if (chartData.length === 0) return null
    const prices = chartData.map(p => p.price)
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const first = prices[0]
    const last = prices[prices.length - 1]
    const delta = last - first
    const deltaPct = first ? (delta / first) * 100 : 0
    return { min, max, first, last, delta, deltaPct }
  }, [chartData])

  const minIdx = useMemo(() => {
    if (!stats) return -1
    return chartData.findIndex(p => p.price === stats.min)
  }, [chartData, stats])
  const maxIdx = useMemo(() => {
    if (!stats) return -1
    return chartData.findIndex(p => p.price === stats.max)
  }, [chartData, stats])

  return (
    <Modal open={open} onClose={onClose} title="היסטוריית מחיר" maxWidth="max-w-2xl">
      <div className="mb-3">
        <p className="text-sm font-semibold text-gray-800">{planName}</p>
        <p className="text-xs text-gray-500 mt-0.5">{carrier}</p>
      </div>

      {loading ? (
        <div className="py-10 flex justify-center"><Spinner /></div>
      ) : error ? (
        <p className="text-sm text-red-600 py-6 text-center">שגיאה: {error}</p>
      ) : chartData.length === 0 ? (
        <div className="py-8 text-center text-sm text-gray-500">
          <p>אין שינויי מחיר מתועדים לתוכנית זו.</p>
          {currentPrice && (
            <p className="mt-2 text-gray-400">מחיר נוכחי: <strong className="text-gray-700">₪{currentPrice}</strong></p>
          )}
        </div>
      ) : (
        <>
          {stats && (
            <div className="grid grid-cols-4 gap-2 mb-4">
              <StatBox label="מחיר נוכחי" value={`₪${stats.last.toFixed(2)}`} color="text-moca-espresso" />
              <StatBox label="מינימום" value={`₪${stats.min.toFixed(2)}`} color="text-emerald-600" />
              <StatBox label="מקסימום" value={`₪${stats.max.toFixed(2)}`} color="text-red-600" />
              <StatBox
                label="שינוי מצטבר"
                value={`${stats.delta >= 0 ? '+' : ''}${stats.deltaPct.toFixed(1)}%`}
                color={stats.delta > 0 ? 'text-red-600' : stats.delta < 0 ? 'text-emerald-600' : 'text-gray-600'}
              />
            </div>
          )}

          <div className="h-64 -mx-2" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5d8c5" />
                <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={v => `₪${v}`} tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                <Tooltip
                  labelFormatter={formatDate}
                  formatter={(value) => [`₪${value}`, 'מחיר']}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5d8c5' }}
                />
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#5c3317"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#5c3317' }}
                  activeDot={{ r: 5 }}
                />
                {minIdx >= 0 && stats.min !== stats.max && (
                  <ReferenceDot x={chartData[minIdx].date} y={stats.min} r={5} fill="#10b981" stroke="#fff" strokeWidth={2} />
                )}
                {maxIdx >= 0 && stats.min !== stats.max && (
                  <ReferenceDot x={chartData[maxIdx].date} y={stats.max} r={5} fill="#ef4444" stroke="#fff" strokeWidth={2} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <p className="text-[11px] text-gray-400 text-center mt-3">
            {chartData.length} נקודות · {formatDate(chartData[0].date)} – {formatDate(chartData[chartData.length - 1].date)}
          </p>
        </>
      )}
    </Modal>
  )
}
