import { useState, useEffect } from 'react'
import { api } from '../lib/api'

function Stat({ label, value, sub, color = 'text-gray-800' }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className={`text-2xl font-bold ${color} mb-0.5 tabular-nums`}>{value ?? '—'}</div>
      <div className="text-sm font-medium text-gray-600">{label}</div>
      {sub && <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function fmt(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleString('he-IL', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function HealthPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const load = () => {
    setLoading(true); setErr(null)
    api.getHealth()
      .then(setData)
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
    </div>
  )
  if (err) return <div className="text-center py-20 text-red-500 text-sm">{err}</div>
  if (!data) return null

  return (
    <div className="max-w-4xl mx-auto px-4 py-6" dir="rtl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-800">Health Dashboard</h1>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-gray-400">עודכן: {fmt(data.generated_at)}</span>
          <button
            onClick={load}
            className="text-sm text-moca-bolt hover:text-moca-dark border border-moca-border/60 px-3 py-1.5 rounded-lg hover:bg-moca-cream transition-colors"
          >
            רענן
          </button>
        </div>
      </div>

      <div className={`rounded-xl p-3 mb-6 flex items-center gap-2 text-sm font-medium border ${
        data.ok ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'
      }`}>
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${data.ok ? 'bg-emerald-500' : 'bg-red-500'}`} />
        {data.ok ? 'כל המערכות פועלות תקין' : 'יש בעיה — בדוק לוגים'}
      </div>

      <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">חבילות ב-DB</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat label="סלולר" value={data.plans_count?.domestic} color="text-blue-700" />
        <Stat label='חו"ל' value={data.plans_count?.abroad} color="text-orange-700" />
        <Stat label="גלובלי" value={data.plans_count?.global} color="text-purple-700" />
        <Stat label="תוכן" value={data.plans_count?.content} color="text-teal-700" />
      </div>

      <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">אופרציה</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        <Stat label="גודל DB" value={data.db_size_mb != null ? `${data.db_size_mb} MB` : null} />
        <Stat label="עדכון אחרון" value={fmt(data.last_scrape)} sub="MAX(scraped_at)" />
        <Stat label="Scheduled jobs" value={data.scheduled_jobs} />
        <Stat label="Digest אחרון" value={fmt(data.last_digest_sent)} />
        <Stat label="Scrape ידני אחרון" value={fmt(data.last_manual_scrape)} />
      </div>

      {data.workspaces_total != null && (
        <>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Workspaces</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <Stat label="סה״כ" value={data.workspaces_total} />
            <Stat label="פעילים" value={data.workspaces_active} color="text-emerald-700" />
            <Stat label="מושעים" value={(data.workspaces_total || 0) - (data.workspaces_active || 0)} color="text-red-600" />
          </div>
        </>
      )}
    </div>
  )
}
