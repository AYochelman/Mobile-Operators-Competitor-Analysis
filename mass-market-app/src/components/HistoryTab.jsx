import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import * as XLSX from 'xlsx'
import { api } from '../lib/api'
import Spinner from './ui/Spinner'

const DOMESTIC_CARRIERS = [
  { id: 'partner',   label: 'פרטנר' },
  { id: 'pelephone', label: 'פלאפון' },
  { id: 'hotmobile', label: 'הוט מובייל' },
  { id: 'cellcom',   label: 'סלקום' },
  { id: 'mobile019', label: '019' },
  { id: 'xphone',    label: 'XPhone' },
  { id: 'wecom',     label: 'We-Com' },
  { id: 'neptucom',  label: 'Neptucom' },
  { id: 'golan',     label: 'גולן טלקום' },
  { id: 'rami_levy', label: 'רמי לוי' },
]

const GLOBAL_CARRIERS = [
  { id: 'tuki',             label: 'Tuki' },
  { id: 'globalesim',       label: 'GlobaleSIM' },
  { id: 'airalo',           label: 'Airalo' },
  { id: 'pelephone_global', label: 'GlobalSIM' },
  { id: 'esimo',            label: 'eSIMo' },
  { id: 'simtlv',           label: 'SimTLV' },
  { id: 'world8',           label: '8 World' },
  { id: 'xphone_global',    label: 'XPhone Global' },
  { id: 'saily',            label: 'Saily' },
  { id: 'holafly',          label: 'Holafly' },
  { id: 'esimio',           label: 'eSIM.io' },
  { id: 'sparks',           label: 'Sparks' },
  { id: 'voye',             label: 'VOYE' },
  { id: 'orbit',            label: 'Orbit' },
  { id: 'travelsim',        label: 'Travel Sim' },
  { id: 'gomoworld',        label: 'GoMoWorld' },
  { id: 'tasim',            label: 'Tasim' },
  { id: 'maya',             label: 'Maya Mobile' },
  { id: 'bcengi',         label: 'Bcengi' },
  { id: 'esim70',         label: 'eSIM70' },
  { id: 'jetpack',        label: 'Jetpack' },
  { id: 'breez',          label: 'Breeze' },
  { id: 'bytesim',        label: 'ByteSim' },
  { id: 'besim',          label: 'Besim' },
]

const CARRIERS_BY_TYPE = {
  domestic: DOMESTIC_CARRIERS,
  abroad:   DOMESTIC_CARRIERS,
  global:   GLOBAL_CARRIERS,
  content:  DOMESTIC_CARRIERS,
}

const PLAN_TYPE_LABELS = {
  domestic: 'מקומי',
  abroad:   'חו"ל',
  global:   'גלובלי',
  content:  'תוכן',
}

const LINE_COLORS = [
  '#5c3317','#b06030','#e0956a','#d4845a',
  '#c87040','#a05828','#8a4820','#6e3818','#521e08','#3a0e00',
]

const BADGE_CONFIG = {
  price_change: {
    up:   { label: '⬆ עלייה', cls: 'bg-red-100 text-red-700' },
    down: { label: '⬇ ירידה', cls: 'bg-green-100 text-green-700' },
  },
  new_plan:      { label: '✦ חדש',    cls: 'bg-blue-100 text-blue-700' },
  removed_plan:  { label: '✕ הוסר',   cls: 'bg-orange-100 text-orange-700' },
  extras_change: { label: '✎ פרטים',  cls: 'bg-gray-100 text-gray-600' },
  details_change:{ label: '✎ פרטים',  cls: 'bg-gray-100 text-gray-600' },
}

function rangeToFrom(range) {
  const now = new Date()
  if (range === '30d')  { const d = new Date(now); d.setDate(d.getDate() - 30);        return d.toISOString().slice(0, 10) }
  if (range === '90d')  { const d = new Date(now); d.setDate(d.getDate() - 90);        return d.toISOString().slice(0, 10) }
  if (range === 'year') { const d = new Date(now); d.setFullYear(d.getFullYear() - 1); return d.toISOString().slice(0, 10) }
  return ''
}

function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-moca-border rounded-lg p-2 text-xs shadow-sm">
      <div className="font-semibold text-moca-text mb-1">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: ₪{p.value}
        </div>
      ))}
    </div>
  )
}

function Badge({ change }) {
  if (change.change_type === 'price_change') {
    const up = parseFloat(change.new_val) > parseFloat(change.old_val)
    const b = BADGE_CONFIG.price_change[up ? 'up' : 'down']
    return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${b.cls}`}>{b.label}</span>
  }
  const b = BADGE_CONFIG[change.change_type] || { label: change.change_type, cls: 'bg-gray-100 text-gray-500' }
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${b.cls}`}>{b.label}</span>
}

function Delta({ change }) {
  if (change.change_type !== 'price_change') return <span>—</span>
  try {
    const d = parseFloat(change.new_val) - parseFloat(change.old_val)
    const cls = d > 0 ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'
    return <span className={cls}>{d > 0 ? '+' : ''}₪{d.toFixed(0)}</span>
  } catch {
    return <span>—</span>
  }
}

export default function HistoryTab() {
  const [carrier,  setCarrier]  = useState('pelephone')
  const [planType, setPlanType] = useState('domestic')
  const [planName, setPlanName] = useState('all')
  const [range,    setRange]    = useState('year')
  const [changes,  setChanges]  = useState([])
  const [series,   setSeries]   = useState([])
  const [summary,  setSummary]  = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [analysis,       setAnalysis]       = useState(null)
  const [analyzeLoading, setAnalyzeLoading] = useState(false)

  // Reset plan selection when carrier or plan type changes
  useEffect(() => {
    setPlanName('all')
    setAnalysis(null)
    setAnalyzeLoading(false)
  }, [carrier, planType])

  useEffect(() => {
    if (!carrier) return
    setAnalysis(null)
    setLoading(true)
    const from = rangeToFrom(range)
    Promise.all([
      api.getHistoryChanges(carrier, planType, from),
      api.getHistoryPriceSeries(carrier, planType, planName === 'all' ? '' : planName, from),
    ])
      .then(([changesRes, seriesRes]) => {
        setChanges(changesRes.changes  || [])
        setSummary(changesRes.summary  || null)
        setSeries(seriesRes.series     || [])
      })
      .catch(() => { setChanges([]); setSummary(null); setSeries([]) })
      .finally(() => setLoading(false))
  }, [carrier, planType, planName, range])

  // Unique plan names from current changes data (for drill-down dropdown)
  const planOptions = useMemo(
    () => [...new Set(changes.map(c => c.plan_name))].sort(),
    [changes]
  )

  // Reset planName when options change and current selection is no longer valid
  useEffect(() => {
    if (planName !== 'all' && !planOptions.includes(planName)) {
      setPlanName('all')
    }
  }, [planOptions, planName])

  // Merge all series onto a shared date axis for Recharts
  const chartData = useMemo(() => {
    if (!series.length) return []
    const dateSet = new Set()
    series.forEach(s => s.points.forEach(p => dateSet.add(p.date)))
    return [...dateSet].sort().map(date => {
      const row = { date }
      series.forEach(s => {
        const before = s.points.filter(p => p.date <= date)
        if (before.length) row[s.plan_name] = before[before.length - 1].price
      })
      return row
    })
  }, [series])

  async function handleAnalyze() {
    setAnalyzeLoading(true)
    try {
      const from = rangeToFrom(range)
      const res = await api.analyzeHistory(carrier, planType, from)
      setAnalysis(
        res.analysis ?? 'אין מספיק נתונים לניתוח עבור הפילטרים הנבחרים.'
      )
    } catch {
      setAnalysis('שגיאה בניתוח. נסה שוב.')
    } finally {
      setAnalyzeLoading(false)
    }
  }

  function exportToExcel() {
    const rows = changes.map(c => ({
      'תאריך':  c.changed_at?.slice(0, 10),
      'חבילה':  c.plan_name,
      'שינוי':  c.change_type,
      'לפני':   c.old_val,
      'אחרי':   c.new_val,
    }))
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'היסטוריה')
    XLSX.writeFile(wb, `history-${carrier}-${planType}.xlsx`)
  }

  const carriers = CARRIERS_BY_TYPE[planType] || DOMESTIC_CARRIERS

  return (
    <div>
      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 items-end mb-4 bg-white border border-moca-border/60 rounded-xl p-3">
        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide">מפעיל</span>
          <select
            value={carrier}
            onChange={e => setCarrier(e.target.value)}
            className="border border-moca-border rounded-lg px-2 py-1.5 text-sm bg-moca-cream text-moca-text"
          >
            {carriers.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide">סוג</span>
          <select
            value={planType}
            onChange={e => setPlanType(e.target.value)}
            className="border border-moca-border rounded-lg px-2 py-1.5 text-sm bg-moca-cream text-moca-text"
          >
            {Object.entries(PLAN_TYPE_LABELS).map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide">חבילה</span>
          <select
            value={planName}
            onChange={e => setPlanName(e.target.value)}
            className="border border-moca-border rounded-lg px-2 py-1.5 text-sm bg-moca-cream text-moca-text min-w-[160px]"
          >
            <option value="all">כל החבילות</option>
            {planOptions.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>

        <div className="flex gap-1.5 items-center">
          {[['30d','30י׳'],['90d','90י׳'],['year','שנה'],['all','הכל']].map(([val, lbl]) => (
            <button
              key={val}
              onClick={() => setRange(val)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                range === val
                  ? 'bg-moca-text text-white border-moca-text'
                  : 'border-moca-border text-moca-sub hover:border-moca-bolt hover:text-moca-bolt'
              }`}
            >
              {lbl}
            </button>
          ))}
        </div>

        <button
          onClick={handleAnalyze}
          disabled={analyzeLoading || loading || changes.length === 0}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-moca-border text-moca-sub hover:text-moca-text hover:bg-moca-cream transition-all disabled:opacity-40 mr-auto"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2"
               strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="10" rx="2"/>
            <circle cx="12" cy="5" r="2"/>
            <path d="M12 7v4"/>
            <line x1="8" y1="16" x2="8" y2="16"/>
            <line x1="16" y1="16" x2="16" y2="16"/>
          </svg>
          {analyzeLoading ? 'מנתח...' : 'ניתוח AI'}
        </button>
      </div>

      {loading && (
        <div className="flex justify-center py-10"><Spinner /></div>
      )}

      {!loading && (
        <>
          {/* Summary cards */}
          {summary && (
            <div className="grid grid-cols-4 gap-3 mb-4">
              {[
                { label: 'כל השינויים', value: summary.total,        sub: 'בתקופה הנבחרת', cls: '' },
                { label: 'עליות',        value: summary.price_up,     sub: 'מחיר עלה',      cls: 'text-red-600' },
                { label: 'ירידות',       value: summary.price_down,   sub: 'מחיר ירד',      cls: 'text-green-600' },
                { label: 'חדש / הוסר',  value: `${summary.new_plans} / ${summary.removed_plans}`, sub: 'חבילות', cls: '' },
              ].map(({ label, value, sub, cls }) => (
                <div key={label} className="bg-white border border-moca-border/60 rounded-xl p-3">
                  <div className="text-[10px] font-semibold uppercase text-moca-muted tracking-wide mb-1">{label}</div>
                  <div className={`text-2xl font-bold ${cls || 'text-moca-text'}`}>{value}</div>
                  <div className="text-[11px] text-moca-muted mt-0.5">{sub}</div>
                </div>
              ))}
            </div>
          )}

          {/* AI Analysis panel */}
          {analysis !== null && (
            <div className="bg-moca-cream border border-moca-border/60 rounded-xl p-4 mb-4 text-right">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-moca-text font-semibold text-sm">
                  <span>ניתוח AI</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" strokeWidth="2"
                       strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 3l1.88 5.76a1 1 0 0 0 .95.69h6.06l-4.9 3.56a1 1 0 0 0-.36 1.12L17.5 20l-4.9-3.56a1 1 0 0 0-1.18 0L6.5 20l1.88-5.87a1 1 0 0 0-.36-1.12L3.11 9.45h6.06a1 1 0 0 0 .95-.69L12 3z"/>
                  </svg>
                </div>
                <button
                  onClick={() => setAnalysis(null)}
                  className="text-moca-muted hover:text-moca-text transition-colors"
                  aria-label="סגור ניתוח"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" strokeWidth="2"
                       strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
              <p className="text-moca-text text-sm leading-relaxed">{analysis}</p>
            </div>
          )}

          {/* Price chart — shown only when series data exists */}
          {series.length > 0 && (
            <div className="bg-white border border-moca-border/60 rounded-xl p-4 mb-4">
              <div className="text-sm font-bold text-moca-text mb-0.5">מגמת מחיר (₪)</div>
              <div className="text-xs text-moca-muted mb-3">כל נקודה = שינוי מחיר שזוהה</div>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0e8de" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tickFormatter={v => `₪${v}`} tick={{ fontSize: 10 }} width={45} />
                  <Tooltip content={<PriceTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px' }} />
                  {series.map((s, i) => (
                    <Line
                      key={s.plan_name}
                      type="stepAfter"
                      dataKey={s.plan_name}
                      stroke={LINE_COLORS[i % LINE_COLORS.length]}
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Empty state — no changes at all */}
          {changes.length === 0 && (
            <div className="bg-white border border-moca-border/60 rounded-xl p-8 text-center mb-4">
              <div className="text-moca-muted text-sm">אין נתוני שינויים לתקופה הנבחרת.</div>
              <div className="text-moca-muted text-xs mt-1">הנתונים יצטברו עם הזמן עם כל סריקה.</div>
            </div>
          )}

          {/* Change log table */}
          {changes.length > 0 && (
            <div className="bg-white border border-moca-border/60 rounded-xl p-4">
              <div className="flex justify-between items-center mb-3">
                <div className="text-sm font-bold text-moca-text">לוג שינויים</div>
                <button
                  onClick={exportToExcel}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-moca-sub hover:text-moca-text hover:bg-moca-cream transition-all"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Excel
                </button>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b-2 border-moca-border">
                    {['תאריך','חבילה','שינוי','לפני','אחרי','דלתא'].map(h => (
                      <th key={h} className="text-right pb-2 px-2 text-[11px] font-semibold uppercase text-moca-muted tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {changes.map((c, i) => (
                    <tr key={i} className="border-b border-moca-bg hover:bg-moca-bg/50">
                      <td className="py-2 px-2 text-xs text-moca-muted">{c.changed_at?.slice(0, 10)}</td>
                      <td className="py-2 px-2 font-medium">{c.plan_name}</td>
                      <td className="py-2 px-2"><Badge change={c} /></td>
                      <td className="py-2 px-2 text-xs line-through text-moca-muted">{c.old_val ? `₪${c.old_val}` : '—'}</td>
                      <td className="py-2 px-2 font-semibold">{c.new_val ? `₪${c.new_val}` : '—'}</td>
                      <td className="py-2 px-2"><Delta change={c} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
