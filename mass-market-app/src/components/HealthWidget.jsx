import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'

function timeAgo(iso, tt) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  if (isNaN(diff) || diff < 0) return '—'
  const m = Math.round(diff / 60000)
  if (m < 1)    return tt('זה עתה', 'just now')
  if (m < 60)   return tt(`לפני ${m} דק׳`, `${m} min ago`)
  const h = Math.round(m / 60)
  if (h < 24)   return tt(`לפני ${h} שעות`, `${h} h ago`)
  const d = Math.round(h / 24)
  return tt(`לפני ${d} ימים`, `${d} days ago`)
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
  const { tt } = useLang()
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

  if (loading) return <div className="bg-white rounded-xl border border-gray-200 p-4 text-xs text-gray-400">{tt('טוען מצב מערכת…', 'Loading system status…')}</div>
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
          <h2 className="font-bold text-sm">{tt('מצב המערכת', 'System status')}</h2>
        </div>
        <button onClick={load} className="text-[11px] text-moca-sub hover:text-moca-bolt" title={tt('רענן', 'Refresh')}>↻</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label={tt('סריקה אחרונה', 'Last scrape')}       value={timeAgo(h?.last_scrape, tt)}       warn={scrapeWarn} />
        <Stat label={tt("דייג'סט אחרון", 'Last digest')}     value={timeAgo(h?.last_digest_sent, tt)} />
        <Stat label={tt('גודל DB', 'DB size')}           value={h?.db_size_mb != null ? `${h.db_size_mb} MB` : '—'} />
        <Stat label={tt('עבודות מתוזמנות', 'Scheduled jobs')}    value={h?.scheduled_jobs ?? '—'} />
        <Stat label="Workspaces"        value={`${h?.workspaces_active ?? 0} / ${h?.workspaces_total ?? 0}`} />
        <Stat label={tt('סה״כ חבילות', 'Total plans')}       value={plansSum ?? '—'} />
        <Stat label={tt('חבילות סלולר', 'Cellular plans')}      value={h?.plans_count?.domestic ?? '—'} />
        <Stat label={tt('חבילות גלובלי', 'Global plans')}     value={h?.plans_count?.global ?? '—'} />
      </div>
    </div>
  )
}
