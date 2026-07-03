import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'

const CATEGORY_ICONS = {
  domestic: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="2" width="14" height="20" rx="2" ry="2" /><line x1="12" y1="18" x2="12" y2="18.01" />
    </svg>
  ),
  abroad: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />
    </svg>
  ),
  global: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  content: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="15" rx="2" ry="2" /><polyline points="17 2 12 7 7 2" />
    </svg>
  ),
}

const CATEGORIES = [
  { id: 'domestic', label: 'חבילות סלולר' },
  { id: 'abroad',   label: 'חו"ל'          },
  { id: 'global',   label: 'גלובלי'         },
  { id: 'content',  label: 'תוכן'           },
]

const CARRIER_NAMES = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל',
  cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'וי-קום',
  neptucom: 'נפטוקום', golan: 'גולן טלקום', tuki: 'Tuki', terminalesim: 'Terminal eSIM',
  airalo: 'Airalo', airalo_local: 'Airalo', airalo_regional: 'Airalo',
  pelephone_global: 'GlobalSIM', esimo: 'eSIMo',
  simtlv: 'SimTLV', world8: 'World8', saily: 'Saily', holafly: 'Holafly',
  esimio: 'eSIMio', sparks: 'Sparks', voye: 'Voye', orbit: 'Orbit',
  yesim: 'Yesim', nomad: 'Nomad', ubigi: 'Ubigi', alosim: 'aloSIM',
  travelsim: 'TravelSim', gomoworld: 'GoMoWorld', tasim: 'Tasim',
  maya: 'Maya Mobile',
  bcengi: 'Bcengi',
  esim70: 'eSIM70',
  jetpack: 'Jetpack',
  breez: 'Breeze',
  bytesim: 'ByteSim',
  besim: 'Besim',
  seven_g: '7G eSIM',
  bestconnect: 'Best Connect',
  esimplus: 'eSIM Plus',
  rami_levy: 'רמי לוי',
}

// Merge Airalo variants (airalo / airalo_local / airalo_regional) → 'airalo'
const CARRIER_ALIAS = { airalo_local: 'airalo', airalo_regional: 'airalo' }
function normalizeCarrierId(id) { return CARRIER_ALIAS[id] || id }

function mergeChartData(chartData) {
  if (!chartData) return chartData
  const merged = {}
  for (const item of chartData) {
    const id = normalizeCarrierId(item.carrier)
    if (merged[id]) {
      merged[id].count++
      merged[id].total += item.value
      merged[id].value = merged[id].total / merged[id].count
    } else {
      merged[id] = { ...item, carrier: id, total: item.value, count: 1 }
    }
  }
  return Object.values(merged)
    .map(({ total, count, ...rest }) => rest) // eslint-disable-line no-unused-vars
    .sort((a, b) => a.value - b.value)
}

const BAR_COLORS = ['#5c3317', '#7a4a28', '#9a6040', '#b87c58', '#d4a07a', '#e8c9a8']

function carrierName(id) {
  return CARRIER_NAMES[id] || id
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })
}

// ── Inline SVG icons matching the app's SVG style ─────────────────────────

function SparkleIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>
    </svg>
  )
}

// ── Individual category summary section ───────────────────────────────────

const CATEGORY_LABELS_EN = {
  domestic: 'Cellular plans',
  abroad:   'Roaming',
  global:   'Global',
  content:  'Content',
}

function SummarySection({ data, onRefresh, refreshing, isAdmin }) {
  const { tt } = useLang()
  const { category, metrics, narrative, generated_at } = data
  const meta = CATEGORIES.find(c => c.id === category) || { label: category }
  const categoryLabel = tt(meta.label, CATEGORY_LABELS_EN[category] || meta.label)
  const icon = CATEGORY_ICONS[category] || null

  return (
    <div className="bg-white rounded-xl shadow-card border border-moca-border/40 p-5 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {icon && (
            <span className="text-moca-text">{icon}</span>
          )}
          <h2 className="text-lg font-display font-semibold text-moca-text">{categoryLabel}</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-moca-sub">{tt('עודכן', 'Updated')}: {formatDate(generated_at)}</span>
          {isAdmin && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="text-[11px] px-2 py-1 rounded-lg border border-moca-border text-moca-muted hover:text-moca-bolt hover:border-moca-bolt transition-colors disabled:opacity-50"
            >
              {refreshing ? tt('מרענן...', 'Refreshing...') : tt('רענן עכשיו', 'Refresh now')}
            </button>
          )}
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#5c3317' }}>
          <div className="flex justify-center mb-1.5">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="6"/>
              <path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/>
            </svg>
          </div>
          <div className="text-[10px] opacity-80 mb-1">{tt('המשתלם ביותר', 'Best value')}</div>
          <div className="text-sm font-bold">{carrierName(metrics.cheapest?.carrier)}</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.cheapest?.value} {metrics.cheapest?.unit}
          </div>
        </div>
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#b85c1a' }}>
          <div className="flex justify-center mb-1.5">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
          </div>
          <div className="text-[10px] opacity-80 mb-1">{tt('האגרסיבי ביותר', 'Most aggressive')}</div>
          <div className="text-sm font-bold">
            {metrics.most_aggressive?.changes > 0
              ? carrierName(metrics.most_aggressive?.carrier)
              : '—'}
          </div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.most_aggressive?.changes > 0
              ? tt(`${metrics.most_aggressive.changes} הורדות מחיר`, `${metrics.most_aggressive.changes} price drops`)
              : tt('אין הורדות מחיר', 'No price drops')}
          </div>
        </div>
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#c47a3a' }}>
          <div className="flex justify-center mb-1.5">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"/>
              <line x1="12" y1="20" x2="12" y2="4"/>
              <line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
          </div>
          <div className="text-[10px] opacity-80 mb-1">{tt('שינויים השבוע', 'Changes this week')}</div>
          <div className="text-sm font-bold">{metrics.weekly_changes?.total} {tt('שינויים', 'changes')}</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.weekly_changes?.drops} {tt('ירידות', 'drops')} · {metrics.weekly_changes?.rises} {tt('עליות', 'rises')}
          </div>
        </div>
      </div>

      {/* Bar chart */}
      {metrics.chart_data?.length > 0 && (
        <div className="bg-moca-bg rounded-xl p-4 mb-4">
          <div className="text-[11px] text-moca-sub font-semibold mb-3 text-right">
            {metrics.cheapest?.unit} {tt('לפי ספק', 'by carrier')}
          </div>
          <div dir="ltr">
            <ResponsiveContainer width="100%" height={metrics.chart_data.length * 36 + 20}>
              <BarChart
                data={[...metrics.chart_data].reverse()}
                layout="vertical"
                margin={{ top: 0, right: 12, bottom: 0, left: 8 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="carrier"
                  tickFormatter={carrierName}
                  width={110}
                  orientation="left"
                  tick={{ fontSize: 12, fill: '#5c3317', fontWeight: 500 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(value) => [`${value} ${metrics.cheapest?.unit}`, tt('ערך', 'Value')]}
                  labelFormatter={carrierName}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {[...metrics.chart_data].reverse().map((_, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* AI narrative — flex-1 so the box grows to align card bottom edges */}
      <div className="bg-white rounded-xl p-4 border-r-4 border-moca-bolt shadow-sm flex-1">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-moca-sub"><SparkleIcon /></span>
          <span className="text-[11px] text-moca-sub font-semibold">{tt('ניתוח AI', 'AI analysis')}</span>
        </div>
        <p className="text-sm text-moca-text leading-relaxed text-right">{narrative}</p>
      </div>
    </div>
  )
}

function SkeletonSection() {
  return (
    <div className="bg-white rounded-xl shadow-card border border-moca-border/40 p-5 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 bg-gray-200 rounded" />
        <div className="h-4 bg-gray-200 rounded w-32" />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[0, 1, 2].map(i => (
          <div key={i} className="h-20 bg-gray-200 rounded-xl" />
        ))}
      </div>
      <div className="h-32 bg-gray-100 rounded-xl mb-4" />
      <div className="h-24 bg-gray-100 rounded-xl" />
    </div>
  )
}

export default function ExecutiveSummaryPage() {
  const { isAdmin } = useAuth()
  const { tt } = useLang()
  const [summaries, setSummaries] = useState([])
  const [loading, setLoading] = useState(true)
  const [notGenerated, setNotGenerated] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  async function load() {
    try {
      const data = await api.getExecutiveSummary()
      const ordered = CATEGORIES.map(c => {
        const d = data.find(d => d.category === c.id)
        if (!d) return null
        // Merge Airalo variants in chart + normalize metric carrier IDs
        if (d.metrics?.chart_data) d.metrics.chart_data = mergeChartData(d.metrics.chart_data)
        if (d.metrics?.cheapest?.carrier) d.metrics.cheapest.carrier = normalizeCarrierId(d.metrics.cheapest.carrier)
        if (d.metrics?.most_aggressive?.carrier) d.metrics.most_aggressive.carrier = normalizeCarrierId(d.metrics.most_aggressive.carrier)
        return d
      }).filter(Boolean)
      setSummaries(ordered)
      setNotGenerated(false)
    } catch (err) {
      if (err.message === 'not_generated_yet' || err.message === 'HTTP 404') {
        setNotGenerated(true)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try { await api.refreshExecutiveSummary(); await load() }
    catch (err) { console.error('refresh failed', err) }
    finally { setRefreshing(false) }
  }

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="grid lg:grid-cols-2 gap-5 items-start">
          {[0, 1, 2, 3].map(i => <SkeletonSection key={i} />)}
        </div>
      </div>
    )
  }

  if (notGenerated) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <div className="bg-white rounded-xl p-12 text-center border border-moca-border/40">
          <div className="text-4xl mb-3">🕗</div>
          <p className="text-moca-muted text-sm">{tt('הניתוח ייווצר ב-08:00 הקרוב', 'The analysis will be generated at the next 08:00')}</p>
          {isAdmin && (
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="mt-4 px-4 py-2 rounded-lg bg-moca-bolt text-white text-sm hover:bg-[#7a4a28] transition-colors disabled:opacity-50"
            >
              {refreshing ? tt('מייצר ניתוח...', 'Generating analysis...') : tt('צור עכשיו', 'Generate now')}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-display font-bold text-moca-text mb-6 text-right">{tt('תקציר מנהלים', 'Executive Summary')}</h1>

      {/* Category summaries — 2-up grid on desktop; items-stretch keeps row-mates equal height */}
      <div className="grid lg:grid-cols-2 gap-5 items-stretch mb-5">
        {summaries.map(s => (
          <SummarySection
            key={s.category}
            data={s}
            onRefresh={handleRefresh}
            refreshing={refreshing}
            isAdmin={isAdmin}
          />
        ))}
      </div>
    </div>
  )
}
