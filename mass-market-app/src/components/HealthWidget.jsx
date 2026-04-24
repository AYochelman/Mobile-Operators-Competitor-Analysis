import { useState, useEffect } from 'react'
import { api } from '../lib/api'

function timeAgo(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  if (isNaN(diff) || diff < 0) return '—'
  const m = Math.round(diff / 60000)
  if (m < 1)    return 'זה עתה'
  if (m < 60)   return `לפני ${m} דק׳`
  const h = Math.round(m / 60)
  if (h < 24)   return `לפני ${h} שעות`
  const d = Math.round(h / 24)
  return `לפני ${d} ימים`
}

function Stat({ label, value, warn }) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] text-gray-500">{label}</span>
      <span className={`text-sm font-semibold mt-0.5 ${warn ? 'text-amber-600' : 'text-gray-800'}`}>{value}</span>
    </div>
  )
}

export default function HealthWidget() {
  const [h, setH] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const load = () => {
    setLoading(true); setErr(null)
    api.getHealth()
      .then(setH)
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  if (loading) return <div className="bg-white rounded-xl border border-gray-200 p-4 text-xs text-gray-400">טוען מצב מערכת…</div>
  if (err) return null  // likely 401 — not super_admin; hide silently

  // Warn if last scrape is older than 24h
  const scrapeAgeMs = h?.last_scrape ? (Date.now() - new Date(h.last_scrape).getTime()) : Infinity
  const scrapeWarn = scrapeAgeMs > 26 * 3600 * 1000  // 26h grace (schedule is ~10h + ~6h)

  const plansSum = h?.plans_count
    ? Object.values(h.plans_count).filter(n => typeof n === 'number').reduce((a, b) => a + b, 0)
    : null

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${scrapeWarn ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
          <h2 className="font-bold text-sm">מצב המערכת</h2>
        </div>
        <button onClick={load} className="text-[11px] text-moca-sub hover:text-moca-bolt" title="רענן">↻</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="סריקה אחרונה"       value={timeAgo(h?.last_scrape)}       warn={scrapeWarn} />
        <Stat label="דייג'סט אחרון"     value={timeAgo(h?.last_digest_sent)} />
        <Stat label="גודל DB"           value={h?.db_size_mb != null ? `${h.db_size_mb} MB` : '—'} />
        <Stat label="עבודות מתוזמנות"    value={h?.scheduled_jobs ?? '—'} />
        <Stat label="Workspaces"        value={`${h?.workspaces_active ?? 0} / ${h?.workspaces_total ?? 0}`} />
        <Stat label="סה״כ חבילות"       value={plansSum ?? '—'} />
        <Stat label="חבילות סלולר"      value={h?.plans_count?.domestic ?? '—'} />
        <Stat label="חבילות גלובלי"     value={h?.plans_count?.global ?? '—'} />
      </div>
    </div>
  )
}
