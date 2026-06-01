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

const RECENT_PREVIEW = 20   // rows shown by default
const RECENT_FETCH   = 100  // rows fetched for the expanded "comprehensive" view

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

function fmtDays(n) {
  if (n == null) return '—'
  if (n <= 0)    return 'נוצל'
  if (n < 1)     return 'פחות מיום'
  if (n >= 365)  return `~${(n / 365).toFixed(1)} שנים`
  if (n >= 60)   return `~${Math.round(n / 30)} חודשים`
  return `~${Math.round(n)} ימים`
}

function fmtDateHe(iso) {
  if (!iso) return ''
  try {
    return new Date(`${iso}T00:00:00`).toLocaleDateString('he-IL', {
      day: 'numeric', month: 'long', year: 'numeric',
    })
  } catch {
    return iso
  }
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

function OfficialSpend({ official, windowDays }) {
  if (!official) return null
  const windowLbl = windowDays === 0 ? 'כל התקופה' : `${windowDays || 30} הימים האחרונים`

  if (!official.configured) {
    return (
      <div className="mb-4 rounded-lg p-3 text-xs leading-relaxed" style={{ background: 'var(--color-moca-mist)', color: 'var(--color-moca-sub)' }}>
        💡 להצגת <span className="font-semibold">הוצאה רשמית מ-Anthropic</span>: הוסף ל-config.json את{' '}
        <code className="font-mono">anthropic_admin_key</code> (מפתח Admin של ארגון, <code className="font-mono">sk-ant-admin…</code> — לא זמין לחשבון יחיד) והפעל מחדש את Flask. זו הוצאה, לא יתרה.
      </div>
    )
  }
  if (official.error || official.total_usd == null) {
    const auth = official.status === 401 || official.status === 403
    return (
      <div className="mb-4 rounded-lg p-3 text-xs leading-relaxed" style={{ background: 'var(--color-moca-mist)', color: 'var(--color-moca-up)' }}>
        ⚠️ לא ניתן למשוך הוצאה רשמית מ-Anthropic ({official.error || 'שגיאה'}).
        {auth && ' המפתח אינו תקין או שאין הרשאת ארגון — חשבונות יחיד לא תומכים ב-Admin API.'}
      </div>
    )
  }
  return (
    <div className="mb-4 rounded-lg p-3 flex items-center justify-between gap-3" style={{ background: 'var(--color-moca-mist)' }}>
      <div className="text-right">
        <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
          הוצאה רשמית · Anthropic
        </div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--color-moca-sub)' }}>{windowLbl}</div>
      </div>
      <div className="text-2xl font-bold tnum" style={{ color: 'var(--color-moca-dark)' }}>
        {fmtUSD(official.total_usd)}
      </div>
    </div>
  )
}

function BudgetPanel({ budget, official, windowDays, onSave }) {
  const configured = !!budget?.configured
  const [editing, setEditing] = useState(!configured)
  const [total, setTotal]     = useState(budget?.total_usd ?? '')
  const [asOf, setAsOf]       = useState(budget?.as_of ?? '')
  const [busy, setBusy]       = useState(false)
  const [err, setErr]         = useState(null)

  // Keep inputs synced with the saved budget when it changes (e.g. after save).
  useEffect(() => {
    setTotal(budget?.total_usd ?? '')
    setAsOf(budget?.as_of ?? '')
  }, [budget?.total_usd, budget?.as_of])

  const submit = async (clear = false) => {
    setBusy(true); setErr(null)
    try {
      await onSave(clear ? null : Number(total), clear ? null : (asOf || null))
      setEditing(clear)  // after a clear, reopen the setup form; after save, close it
    } catch (e) {
      setErr(e?.message || 'שגיאה בשמירה')
    } finally {
      setBusy(false)
    }
  }

  const fc        = budget?.forecast || {}
  const pct       = budget?.pct_used ?? 0
  const barColor  = pct >= 85 ? 'var(--color-moca-up)'
                  : pct >= 60 ? 'var(--color-moca-hot)'
                  :             'var(--color-moca-down)'
  const windowLbl = fc.window_days === 0 ? 'כל התקופה' : `${fc.window_days || 30} הימים האחרונים`

  // ── setup / edit form ──
  if (editing) {
    return (
      <div className="rounded-xl border border-moca-border bg-white p-5">
        <OfficialSpend official={official} windowDays={windowDays} />
        <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--color-moca-dark)' }}>
          {configured ? 'עריכת תקציב' : 'הגדרת תקציב Claude'}
        </h3>
        <p className="text-xs mb-4" style={{ color: 'var(--color-moca-sub)' }}>
          הזן את סכום הקרדיט שטענת ב-Anthropic (USD). היתרה תחושב אוטומטית בהפחתת כל השימוש שתועד מקומית.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-right">
            <span className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-moca-muted)' }}>תקציב כולל ($)</span>
            <input
              type="number" min="0" step="0.01" value={total}
              onChange={(e) => setTotal(e.target.value)}
              placeholder="לדוגמה: 50"
              className="w-36 rounded-lg border border-moca-border px-3 py-2 text-sm tnum"
              style={{ background: 'var(--color-moca-mist)', color: 'var(--color-moca-dark)' }}
            />
          </label>
          <label className="block text-right">
            <span className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-moca-muted)' }}>ספירה מתאריך (אופציונלי)</span>
            <input
              type="date" value={asOf || ''}
              onChange={(e) => setAsOf(e.target.value)}
              className="rounded-lg border border-moca-border px-3 py-2 text-sm tnum"
              style={{ background: 'var(--color-moca-mist)', color: 'var(--color-moca-dark)' }}
            />
          </label>
          <button
            onClick={() => submit(false)}
            disabled={busy || !total || Number(total) <= 0}
            className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--color-moca-bolt)', color: '#fff' }}
          >
            {busy ? 'שומר…' : 'שמירה'}
          </button>
          {configured && (
            <>
              <button
                onClick={() => setEditing(false)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-semibold border border-moca-border"
                style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
              >
                ביטול
              </button>
              <button
                onClick={() => submit(true)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-semibold"
                style={{ color: 'var(--color-moca-up)' }}
              >
                נקה תקציב
              </button>
            </>
          )}
        </div>
        <p className="text-[11px] mt-3" style={{ color: 'var(--color-moca-muted)' }}>
          תאריך הספירה שימושי אחרי טעינת קרדיט מחדש — השימוש נספר רק ממנו והלאה. ל-Anthropic אין API ליתרה; הסכום הרשמי ב-console.anthropic.com/settings/billing.
        </p>
        {err && <p className="text-xs mt-2 text-red-600">{err}</p>}
      </div>
    )
  }

  // ── summary view ──
  const noForecast = fc.days_left == null
  return (
    <div className="rounded-xl border border-moca-border bg-white p-5">
      <OfficialSpend official={official} windowDays={windowDays} />
      <div className="flex items-start justify-between gap-3">
        <div className="text-right">
          <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
            יתרת תקציב
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold tnum" style={{ color: 'var(--color-moca-dark)' }}>
              {fmtUSD(budget.remaining_usd)}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-moca-sub)' }}>
              מתוך {fmtUSD(budget.total_usd)}
            </span>
          </div>
        </div>
        <button
          onClick={() => setEditing(true)}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-moca-border shrink-0"
          style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
        >
          ערוך
        </button>
      </div>

      {/* usage progress */}
      <div className="mt-3 h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--color-moca-cream)' }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, pct)}%`, background: barColor }} />
      </div>
      <div className="mt-1.5 flex items-center justify-between text-xs" style={{ color: 'var(--color-moca-sub)' }}>
        <span className="tnum">נוצל {fmtUSD(budget.spent_usd)} ({pct}%)</span>
        {budget.as_of && <span>נספר מ-{fmtDateHe(budget.as_of)}</span>}
      </div>

      {/* depletion forecast */}
      <div className="mt-4 pt-4 border-t border-moca-border flex flex-wrap items-baseline gap-x-6 gap-y-1.5">
        <div className="text-right">
          <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
            זמן לסיום היתרה
          </div>
          <div
            className="mt-0.5 text-xl font-bold"
            style={{ color: noForecast ? 'var(--color-moca-muted)' : (fc.days_left <= 14 ? 'var(--color-moca-up)' : 'var(--color-moca-dark)') }}
          >
            {noForecast ? 'אין מספיק נתונים' : fmtDays(fc.days_left)}
          </div>
        </div>
        {!noForecast && (
          <div className="text-xs" style={{ color: 'var(--color-moca-sub)' }}>
            בקצב {windowLbl} (~{fmtUSD(fc.daily_burn_usd)} ליום)
            {fc.depletion_date && fc.days_left > 0 && (
              <> · צפי לסיום בתאריך <span className="font-semibold" style={{ color: 'var(--color-moca-text)' }}>{fmtDateHe(fc.depletion_date)}</span></>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function UsagePage() {
  const [days, setDays]       = useState(30)
  const [summary, setSummary] = useState(null)
  const [recent, setRecent]   = useState([])
  const [showAllRecent, setShowAllRecent] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [official, setOfficial] = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [s, r, oc] = await Promise.all([
        api.getClaudeUsageSummary(days),
        api.getClaudeUsageRecent(RECENT_FETCH),
        api.getOfficialCost(days).catch(() => null),  // resilient: never breaks the page
      ])
      setSummary(s)
      setRecent(r.calls || [])
      setOfficial(oc)
    } catch (e) {
      setError(e.message || 'שגיאה')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  const saveBudget = useCallback(async (total, asOf) => {
    await api.setClaudeUsageBudget(total, asOf)
    await load()
  }, [load])

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

  const shownRecent = showAllRecent ? recent : recent.slice(0, RECENT_PREVIEW)
  const hasMoreRecent = recent.length > RECENT_PREVIEW

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

      {/* Budget: remaining balance + depletion forecast */}
      <BudgetPanel budget={summary?.budget} official={official} windowDays={summary?.window_days} onSave={saveBudget} />

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
            קריאות אחרונות {hasMoreRecent && !showAllRecent
              ? `(${shownRecent.length} מתוך ${recent.length})`
              : `(${recent.length})`}
          </h3>
        </div>
        {recent.length === 0 ? (
          <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>אין קריאות בטווח הזה</p>
        ) : (
          <>
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
                {shownRecent.map((r, i) => (
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
          {hasMoreRecent && (
            <div className="px-4 py-3 border-t border-moca-border text-center">
              <button
                onClick={() => setShowAllRecent((v) => !v)}
                className="text-xs font-semibold px-4 py-1.5 rounded-lg border border-moca-border transition-colors"
                style={{ color: 'var(--color-moca-bolt)', background: 'var(--color-moca-mist)' }}
              >
                {showAllRecent ? 'הצג פחות' : `הצג את כל ${recent.length} הקריאות`}
              </button>
            </div>
          )}
          </>
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
