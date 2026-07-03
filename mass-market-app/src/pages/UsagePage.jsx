import { useState, useEffect, useCallback } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'

const ENDPOINT_LABELS = {
  chat:              'צ׳אט AI',
  history_analyze:   'ניתוח היסטוריה',
  executive_summary: 'דוח מנהלים',
  social_sentiment:  'סנטימנט חברתי',
}

const ENDPOINT_LABELS_EN = {
  chat:              'AI Chat',
  history_analyze:   'History analysis',
  executive_summary: 'Executive report',
  social_sentiment:  'Social sentiment',
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

function fmtDays(n, tt = (he) => he) {
  if (n == null) return '—'
  if (n <= 0)    return tt('נוצל', 'Depleted')
  if (n < 1)     return tt('פחות מיום', 'Less than a day')
  if (n >= 365)  return `~${(n / 365).toFixed(1)} ${tt('שנים', 'years')}`
  if (n >= 60)   return `~${Math.round(n / 30)} ${tt('חודשים', 'months')}`
  return `~${Math.round(n)} ${tt('ימים', 'days')}`
}

function fmtDateHe(iso, locale = 'he-IL') {
  if (!iso) return ''
  try {
    return new Date(`${iso}T00:00:00`).toLocaleDateString(locale, {
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
  const { tt } = useLang()
  const total = rows.reduce((s, r) => s + (r.cost_usd || 0), 0)
  return (
    <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-moca-border">
        <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>{title}</h3>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>{tt('אין נתונים', 'No data')}</p>
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
                    {r.calls} {tt('קריאות', 'calls')}
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
  const { tt } = useLang()
  if (!official) return null
  const windowLbl = windowDays === 0 ? tt('כל התקופה', 'All time') : `${windowDays || 30} ${tt('הימים האחרונים', 'days')}`

  if (!official.configured) {
    return (
      <div className="mb-4 rounded-lg p-3 text-xs leading-relaxed" style={{ background: 'var(--color-moca-mist)', color: 'var(--color-moca-sub)' }}>
        💡 {tt('להצגת', 'To display')} <span className="font-semibold">{tt('הוצאה רשמית מ-Anthropic', 'official spend from Anthropic')}</span>: {tt('הוסף ל-config.json את', 'add to config.json the')}{' '}
        <code className="font-mono">anthropic_admin_key</code> ({tt('מפתח Admin של ארגון,', 'organization Admin key,')} <code className="font-mono">sk-ant-admin…</code> — {tt('לא זמין לחשבון יחיד) והפעל מחדש את Flask. זו הוצאה, לא יתרה.', 'not available for individual accounts), then restart Flask. This is spend, not balance.')}
      </div>
    )
  }
  if (official.error || official.total_usd == null) {
    const auth = official.status === 401 || official.status === 403
    return (
      <div className="mb-4 rounded-lg p-3 text-xs leading-relaxed" style={{ background: 'var(--color-moca-mist)', color: 'var(--color-moca-up)' }}>
        ⚠️ {tt('לא ניתן למשוך הוצאה רשמית מ-Anthropic', 'Could not fetch official spend from Anthropic')} ({official.error || tt('שגיאה', 'error')}).
        {auth && tt(' המפתח אינו תקין או שאין הרשאת ארגון — חשבונות יחיד לא תומכים ב-Admin API.', ' The key is invalid or lacks organization permission — individual accounts do not support the Admin API.')}
      </div>
    )
  }
  return (
    <div className="mb-4 rounded-lg p-3 flex items-center justify-between gap-3" style={{ background: 'var(--color-moca-mist)' }}>
      <div className="text-right">
        <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
          {tt('הוצאה רשמית · Anthropic', 'Official spend · Anthropic')}
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
  const { tt, lang } = useLang()
  const dateLocale = lang === 'he' ? 'he-IL' : 'en-US'
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
      setErr(e?.message || tt('שגיאה בשמירה', 'Error saving'))
    } finally {
      setBusy(false)
    }
  }

  const fc        = budget?.forecast || {}
  const pct       = budget?.pct_used ?? 0
  const barColor  = pct >= 85 ? 'var(--color-moca-up)'
                  : pct >= 60 ? 'var(--color-moca-hot)'
                  :             'var(--color-moca-down)'
  const windowLbl = fc.window_days === 0 ? tt('כל התקופה', 'All time') : `${fc.window_days || 30} ${tt('הימים האחרונים', 'days')}`

  // ── setup / edit form ──
  if (editing) {
    return (
      <div className="rounded-xl border border-moca-border bg-white p-5">
        <OfficialSpend official={official} windowDays={windowDays} />
        <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--color-moca-dark)' }}>
          {configured ? tt('עריכת תקציב', 'Edit budget') : tt('הגדרת תקציב Claude', 'Set Claude budget')}
        </h3>
        <p className="text-xs mb-4" style={{ color: 'var(--color-moca-sub)' }}>
          {tt('הזן את סכום הקרדיט שטענת ב-Anthropic (USD). היתרה תחושב אוטומטית בהפחתת כל השימוש שתועד מקומית.', 'Enter the credit amount you topped up at Anthropic (USD). The balance is computed automatically by subtracting all locally-logged usage.')}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-right">
            <span className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-moca-muted)' }}>{tt('תקציב כולל ($)', 'Total budget ($)')}</span>
            <input
              type="number" min="0" step="0.01" value={total}
              onChange={(e) => setTotal(e.target.value)}
              placeholder={tt('לדוגמה: 50', 'e.g. 50')}
              className="w-36 rounded-lg border border-moca-border px-3 py-2 text-sm tnum"
              style={{ background: 'var(--color-moca-mist)', color: 'var(--color-moca-dark)' }}
            />
          </label>
          <label className="block text-right">
            <span className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-moca-muted)' }}>{tt('ספירה מתאריך (אופציונלי)', 'Count from date (optional)')}</span>
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
            {busy ? tt('שומר…', 'Saving…') : tt('שמירה', 'Save')}
          </button>
          {configured && (
            <>
              <button
                onClick={() => setEditing(false)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-semibold border border-moca-border"
                style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
              >
                {tt('ביטול', 'Cancel')}
              </button>
              <button
                onClick={() => submit(true)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-semibold"
                style={{ color: 'var(--color-moca-up)' }}
              >
                {tt('נקה תקציב', 'Clear budget')}
              </button>
            </>
          )}
        </div>
        <p className="text-[11px] mt-3" style={{ color: 'var(--color-moca-muted)' }}>
          {tt('תאריך הספירה שימושי אחרי טעינת קרדיט מחדש — השימוש נספר רק ממנו והלאה. ל-Anthropic אין API ליתרה; הסכום הרשמי ב-console.anthropic.com/settings/billing.', 'The count-from date is useful after a credit top-up — usage is only counted from it onward. Anthropic has no balance API; the official amount is at console.anthropic.com/settings/billing.')}
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
            {tt('יתרת תקציב', 'Budget balance')}
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold tnum" style={{ color: 'var(--color-moca-dark)' }}>
              {fmtUSD(budget.remaining_usd)}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-moca-sub)' }}>
              {tt('מתוך', 'of')} {fmtUSD(budget.total_usd)}
            </span>
          </div>
        </div>
        <button
          onClick={() => setEditing(true)}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-moca-border shrink-0"
          style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
        >
          {tt('ערוך', 'Edit')}
        </button>
      </div>

      {/* usage progress */}
      <div className="mt-3 h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--color-moca-cream)' }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, pct)}%`, background: barColor }} />
      </div>
      <div className="mt-1.5 flex items-center justify-between text-xs" style={{ color: 'var(--color-moca-sub)' }}>
        <span className="tnum">{tt('נוצל', 'Used')} {fmtUSD(budget.spent_usd)} ({pct}%)</span>
        {budget.as_of && <span>{tt('נספר מ-', 'Counted from ')}{fmtDateHe(budget.as_of, dateLocale)}</span>}
      </div>

      {/* depletion forecast */}
      <div className="mt-4 pt-4 border-t border-moca-border flex flex-wrap items-baseline gap-x-6 gap-y-1.5">
        <div className="text-right">
          <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
            {tt('זמן לסיום היתרה', 'Time to depletion')}
          </div>
          <div
            className="mt-0.5 text-xl font-bold"
            style={{ color: noForecast ? 'var(--color-moca-muted)' : (fc.days_left <= 14 ? 'var(--color-moca-up)' : 'var(--color-moca-dark)') }}
          >
            {noForecast ? tt('אין מספיק נתונים', 'Not enough data') : fmtDays(fc.days_left, tt)}
          </div>
        </div>
        {!noForecast && (
          <div className="text-xs" style={{ color: 'var(--color-moca-sub)' }}>
            {tt('בקצב', 'At the pace of')} {windowLbl} (~{fmtUSD(fc.daily_burn_usd)} {tt('ליום', 'per day')})
            {fc.depletion_date && fc.days_left > 0 && (
              <> · {tt('צפי לסיום בתאריך', 'projected depletion on')} <span className="font-semibold" style={{ color: 'var(--color-moca-text)' }}>{fmtDateHe(fc.depletion_date, dateLocale)}</span></>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function UsagePage() {
  const { tt } = useLang()
  const WINDOW_LABELS = {
    7: tt('7 ימים', '7 days'), 30: tt('30 ימים', '30 days'),
    90: tt('90 ימים', '90 days'), 0: tt('הכל', 'All'),
  }
  const endpointLabel = (id) => tt(ENDPOINT_LABELS[id] || id, ENDPOINT_LABELS_EN[id] || id)
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
      setError(e.message || tt('שגיאה', 'Error'))
    } finally {
      setLoading(false)
    }
  }, [days, tt])

  useEffect(() => { load() }, [load])

  const saveBudget = useCallback(async (total, asOf) => {
    await api.setClaudeUsageBudget(total, asOf)
    await load()
  }, [load])

  if (loading) {
    return <div className="p-6 text-sm" style={{ color: 'var(--color-moca-muted)' }}>{tt('טוען…', 'Loading…')}</div>
  }
  if (error) {
    return <div className="p-6 text-sm text-red-600">{tt('שגיאה:', 'Error:')} {error}</div>
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
            {tt('מעקב מקומי על שימוש ב-Anthropic API. עלות מחושבת לפי מחירון Anthropic (USD).', 'Local tracking of Anthropic API usage. Cost is computed per Anthropic pricing (USD).')}
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
              {WINDOW_LABELS[w.days] ?? w.label}
            </button>
          ))}
          <button
            onClick={load}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-moca-border"
            style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
            title={tt('רענן', 'Refresh')}
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
          label={tt('עלות מצטברת', 'Total cost')}
          value={fmtUSD(total.cost_usd)}
          sub={`${total.calls || 0} ${tt('קריאות', 'calls')}`}
        />
        <StatCard
          label={tt('טוקני קלט', 'Input tokens')}
          value={fmtTok(totalInputTokens)}
          sub={`${tt('כולל', 'incl.')} ${fmtTok(total.cache_read_tokens)} ${tt('מ-cache', 'from cache')}`}
        />
        <StatCard
          label={tt('טוקני פלט', 'Output tokens')}
          value={fmtTok(total.output_tokens)}
        />
        <StatCard
          label={tt('חלון זמן', 'Time window')}
          value={summary?.window_days === 0 ? tt('הכל', 'All') : `${summary?.window_days || 30} ${tt('ימים', 'days')}`}
        />
      </div>

      {/* Daily chart */}
      <div className="rounded-xl border border-moca-border bg-white p-4">
        <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--color-moca-dark)' }}>
          {tt('עלות יומית', 'Daily cost')}
        </h3>
        {chartData.length === 0 ? (
          <p className="text-sm py-8 text-center" style={{ color: 'var(--color-moca-muted)' }}>
            {tt('עדיין אין נתוני שימוש. הקריאות הבאות לצ׳אט / ניתוח היסטוריה / scheduler יירשמו אוטומטית.', 'No usage data yet. The next calls to chat / history analysis / scheduler will be logged automatically.')}
          </p>
        ) : (
          <div style={{ width: '100%', height: 260, direction: 'ltr' }}>
            <ResponsiveContainer>
              <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-moca-border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--color-moca-sub)' }} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--color-moca-sub)' }} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  formatter={(v, name) => name === 'cost' ? [`$${v}`, tt('עלות', 'Cost')] : [v, tt('קריאות', 'Calls')]}
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
          title={tt('פילוח לפי מודל', 'Breakdown by model')}
          rows={summary?.by_model || []}
          labelKey="model"
          labelMap={MODEL_LABELS}
        />
        <BreakdownTable
          title={tt('פילוח לפי endpoint', 'Breakdown by endpoint')}
          rows={summary?.by_endpoint || []}
          labelKey="endpoint"
          labelMap={Object.fromEntries(Object.keys(ENDPOINT_LABELS).map((k) => [k, endpointLabel(k)]))}
        />
      </div>

      {/* Recent calls */}
      <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-moca-border">
          <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>
            {tt('קריאות אחרונות', 'Recent calls')} {hasMoreRecent && !showAllRecent
              ? `(${shownRecent.length} ${tt('מתוך', 'of')} ${recent.length})`
              : `(${recent.length})`}
          </h3>
        </div>
        {recent.length === 0 ? (
          <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>{tt('אין קריאות בטווח הזה', 'No calls in this range')}</p>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead style={{ background: 'var(--color-moca-mist)' }}>
                <tr>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>{tt('זמן', 'Time')}</th>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>endpoint</th>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>{tt('מודל', 'Model')}</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>{tt('קלט', 'Input')}</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>cache</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>{tt('פלט', 'Output')}</th>
                  <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>{tt('עלות', 'Cost')}</th>
                  <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>{tt('משתמש', 'User')}</th>
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
                      {endpointLabel(r.endpoint)}
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
                {showAllRecent ? tt('הצג פחות', 'Show less') : tt(`הצג את כל ${recent.length} הקריאות`, `Show all ${recent.length} calls`)}
              </button>
            </div>
          )}
          </>
        )}
      </div>

      {/* Pricing note */}
      <div className="rounded-xl border border-moca-border bg-white p-4 text-xs" style={{ color: 'var(--color-moca-sub)' }}>
        <p className="mb-2 font-semibold" style={{ color: 'var(--color-moca-dark)' }}>{tt('הערה', 'Note')}</p>
        <p>{summary?.note}</p>
        {summary?.pricing && (
          <details className="mt-3">
            <summary className="cursor-pointer font-semibold" style={{ color: 'var(--color-moca-text)' }}>{tt('מחירון נוכחי ($ per 1M tokens)', 'Current pricing ($ per 1M tokens)')}</summary>
            <table className="mt-2 text-xs">
              <thead>
                <tr style={{ color: 'var(--color-moca-muted)' }}>
                  <th className="text-start py-1 pe-4">{tt('מודל', 'Model')}</th>
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
