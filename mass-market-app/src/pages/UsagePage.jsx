import { useState, useEffect, useCallback } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../lib/api'

const ENDPOINT_LABELS = {
  chat:              'צ׳אט AI',
  history_analyze:   'ניתוח היסטוריה',
  executive_summary: 'דוח מנהלים',
  social_sentiment:  'סנטימנט חברתי',
}

const MODEL_LABELS = {
  'claude-sonnet-4-6':         'Sonnet 4.6',
  'claude-haiku-4-5-20251001': 'Haiku 4.5',
  'claude-opus-4-7':           'Opus 4.7',
}

const WINDOWS = [
  { label: '7 ימים',   days: 7 },
  { label: '30 ימים',  days: 30 },
  { label: '90 ימים',  days: 90 },
  { label: 'הכל',      days: 0 },
]

function fmtUSD(v) {
  if (v == null) return '$0'
  if (v < 0.01)  return `$${v.toFixed(6)}`
  if (v < 1)     return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

function fmtTok(n) {
  if (n == null) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-moca-border bg-white p-4">
      <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold" style={{ color: 'var(--color-moca-dark)' }}>
        {value}
      </div>
      {sub && (
        <div className="mt-1 text-xs" style={{ color: 'var(--color-moca-sub)' }}>
          {sub}
        </div>
      )}
    </div>
  )
}

function BreakdownTable({ title, rows, labelKey, labelMap }) {
  const total = rows.reduce((s, r) => s + (r.cost_usd || 0), 0)
  return (
    <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-moca-border">
        <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>{title}</h3>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>אין נתונים</p>
      ) : (
        <table className="w-full text-sm">
          <tbody>
            {rows.map((r) => {
              const pct = total > 0 ? ((r.cost_usd || 0) / total) * 100 : 0
              return (
                <tr key={r[labelKey]} className="border-t border-moca-border first:border-t-0">
                  <td className="px-4 py-2.5" style={{ color: 'var(--color-moca-text)' }}>
                    {labelMap[r[labelKey]] || r[labelKey]}
                  </td>
                  <td className="px-4 py-2.5 text-end tnum" style={{ color: 'var(--color-moca-sub)' }}>
                    {r.calls} קריאות
                  </td>
                  <td className="px-4 py-2.5 text-end tnum font-semibold" style={{ color: 'var(--color-moca-dark)' }}>
                    {fmtUSD(r.cost_usd)}
                  </td>
                  <td className="px-4 py-2.5 text-end tnum text-xs" style={{ color: 'var(--color-moca-muted)' }}>
                    {pct.toFixed(1)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function UsagePage() {
  const [days, setDays]       = useState(30)
  const [summary, setSummary] = useState(null)
  const [recent, setRecent]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [s, r] = await Promise.all([
        api.getClaudeUsageSummary(days),
        api.getClaudeUsageRecent(50),
      ])
      setSummary(s)
      setRecent(r.calls || [])
    } catch (e) {
      setError(e.message || 'שגיאה')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  if (loading) {
    return <div className="p-6 text-sm" style={{ color: 'var(--color-moca-muted)' }}>טוען…</div>
  }
  if (error) {
    return <div className="p-6 text-sm text-red-600">שגיאה: {error}</div>
  }

  const total = summary?.total || {}
  const totalInputTokens = (total.input_tokens || 0) + (total.cache_read_tokens || 0) + (total.cache_creation_tokens || 0)

  const chartData = (summary?.by_day || [])
    .slice()
    .reverse()
    .map((d) => ({ day: d.day.slice(5), cost: Number((d.cost_usd || 0).toFixed(4)), calls: d.calls }))

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header + window selector */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <p className="text-sm" style={{ color: 'var(--color-moca-sub)' }}>
            מעקב מקומי על שימוש ב-Anthropic API. עלות מחושבת לפי מחירון Anthropic (USD).
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              onClick={() => setDays(w.days)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
              style={{
                background: days === w.days ? 'var(--color-moca-bolt)' : 'var(--color-moca-cream)',
                color:      days === w.days ? '#fff'                  : 'var(--color-moca-text)',
                border:     '1px solid var(--color-moca-border)',
              }}
            >
              {w.label}
            </button>
          ))}
          <button
            onClick={load}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-moca-border"
            style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
            title="רענן"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="עלות מצטברת"
          value={fmtUSD(total.cost_usd)}
          sub={`${total.calls || 0} קריאות`}
        />
        <StatCard
          label="טוקני קלט"
          value={fmtTok(totalInputTokens)}
          sub={`כולל ${fmtTok(total.cache_read_tokens)} מ-cache`}
        />
        <StatCard
          label="טוקני פלט"
          value={fmtTok(total.output_tokens)}
        />
        <StatCard
          label="חלון זמן"
          value={summary?.window_days === 0 ? 'הכל' : `${summary?.window_days || 30} ימים`}
        />
      </div>

      {/* Daily chart */}
      <div className="rounded-xl border border-moca-border bg-white p-4">
        <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--color-moca-dark)' }}>
          עלות יומית
        </h3>
        {chartData.length === 0 ? (
          <p className="text-sm py-8 text-center" style={{ color: 'var(--color-moca-muted)' }}>
            עדיין אין נתוני שימוש. הקריאות הבאות לצ׳אט / ניתוח היסטוריה / scheduler יירשמו אוטומטית.
          </p>
        ) : (
          <div style={{ width: '100%', height: 260, direction: 'ltr' }}>
            <ResponsiveContainer>
              <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-moca-border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--color-moca-sub)' }} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--color-moca-sub)' }} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  formatter={(v, name) => name === 'cost' ? [`$${v}`, 'עלות'] : [v, 'קריאות']}
                  contentStyle={{
                    background: '#fff',
                    border: '1px solid var(--color-moca-border)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="cost" fill="var(--color-moca-bolt)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Breakdowns */}
      <div className="grid md:grid-cols-2 gap-4">
        <BreakdownTable
          title="פילוח לפי מודל"
          rows={summary?.by_model || []}
          labelKey="model"
          labelMap={MODEL_LABELS}
        />
        <BreakdownTable
          title="פילוח לפי endpoint"
          rows={summary?.by_endpoint || []}
          labelKey="endpoint"
          labelMap={ENDPOINT_LABELS}
        />
      </div>

      {/* Recent calls */}
      <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-moca-border">
          <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>
            קריאות אחרונות ({recent.length})
          </h3>
        </div>
        {recent.length === 0 ? (
          <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>אין קריאות בטווח הזה</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead style={{ background: 'var(--color-moca-mist)' }}>
                <tr>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>זמן</th>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>endpoint</th>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>מודל</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>קלט</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>cache</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>פלט</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>עלות</th>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>משתמש</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((r, i) => (
                  <tr key={i} className="border-t border-moca-border">
                    <td className="px-3 py-2 text-xs tnum" style={{ color: 'var(--color-moca-sub)' }}>
                      {new Date(r.called_at).toLocaleString('he-IL', {
                        month: '2-digit', day: '2-digit',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </td>
                    <td className="px-3 py-2" style={{ color: 'var(--color-moca-text)' }}>
                      {ENDPOINT_LABELS[r.endpoint] || r.endpoint}
                    </td>
                    <td className="px-3 py-2 text-xs" style={{ color: 'var(--color-moca-sub)' }}>
                      {MODEL_LABELS[r.model] || r.model}
                    </td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtTok(r.input_tokens)}</td>
                    <td className="px-3 py-2 text-end tnum text-xs" style={{ color: 'var(--color-moca-sub)' }}>{fmtTok(r.cache_read_tokens)}</td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtTok(r.output_tokens)}</td>
                    <td className="px-3 py-2 text-end tnum font-semibold" style={{ color: 'var(--color-moca-dark)' }}>{fmtUSD(r.cost_usd)}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: 'var(--color-moca-muted)' }}>
                      {r.user_email || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pricing note */}
      <div className="rounded-xl border border-moca-border bg-white p-4 text-xs" style={{ color: 'var(--color-moca-sub)' }}>
        <p className="mb-2 font-semibold" style={{ color: 'var(--color-moca-dark)' }}>הערה</p>
        <p>{summary?.note}</p>
        {summary?.pricing && (
          <details className="mt-3">
            <summary className="cursor-pointer font-semibold" style={{ color: 'var(--color-moca-text)' }}>מחירון נוכחי ($ per 1M tokens)</summary>
            <table className="mt-2 text-xs">
              <thead>
                <tr style={{ color: 'var(--color-moca-muted)' }}>
                  <th className="text-start py-1 pe-4">מודל</th>
                  <th className="text-end py-1 pe-4">input</th>
                  <th className="text-end py-1 pe-4">output</th>
                  <th className="text-end py-1 pe-4">cache read</th>
                  <th className="text-end py-1">cache write</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary.pricing).map(([model, p]) => (
                  <tr key={model}>
                    <td className="py-1 pe-4">{MODEL_LABELS[model] || model}</td>
                    <td className="py-1 pe-4 text-end tnum">${p.input}</td>
                    <td className="py-1 pe-4 text-end tnum">${p.output}</td>
                    <td className="py-1 pe-4 text-end tnum">${p.cache_read}</td>
                    <td className="py-1 text-end tnum">${p.cache_write}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
      </div>
    </div>
  )
}
