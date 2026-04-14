import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'

const CATEGORIES = [
  { id: 'domestic', label: 'חבילות סלולר', icon: '📱' },
  { id: 'abroad',   label: 'חו"ל',          icon: '✈️' },
  { id: 'global',   label: 'גלובלי',         icon: '🌍' },
  { id: 'content',  label: 'תוכן',           icon: '📺' },
]

const CARRIER_NAMES = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל',
  cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'וי-קום',
  neptucom: 'נפטוקום', tuki: 'Tuki', globalesim: 'GlobaleSIM',
  airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo',
  simtlv: 'SimTLV', world8: 'World8', saily: 'Saily', holafly: 'Holafly',
  esimio: 'eSIMio', sparks: 'Sparks', voye: 'Voye', orbit: 'Orbit',
  travelsim: 'TravelSim',
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

function SummarySection({ data, onRefresh, refreshing, isAdmin }) {
  const { category, metrics, narrative, generated_at } = data
  const meta = CATEGORIES.find(c => c.id === category) || { label: category, icon: '📋' }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-moca-border/40 p-5 mb-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{meta.icon}</span>
          <h2 className="text-lg font-semibold text-moca-text">{meta.label}</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-moca-sub">עודכן: {formatDate(generated_at)}</span>
          {isAdmin && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="text-[11px] px-2 py-1 rounded-lg border border-moca-border text-moca-muted hover:text-moca-bolt hover:border-moca-bolt transition-colors disabled:opacity-50"
            >
              {refreshing ? 'מרענן...' : 'רענן עכשיו'}
            </button>
          )}
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#5c3317' }}>
          <div className="text-lg mb-1">🏆</div>
          <div className="text-[10px] opacity-80 mb-1">המשתלם ביותר</div>
          <div className="text-sm font-bold">{carrierName(metrics.cheapest?.carrier)}</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.cheapest?.value} {metrics.cheapest?.unit}
          </div>
        </div>
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#b85c1a' }}>
          <div className="text-lg mb-1">🔥</div>
          <div className="text-[10px] opacity-80 mb-1">האגרסיבי ביותר</div>
          <div className="text-sm font-bold">{carrierName(metrics.most_aggressive?.carrier)}</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.most_aggressive?.changes} הורדות מחיר
          </div>
        </div>
        <div className="rounded-xl p-3 text-center text-white" style={{ background: '#c47a3a' }}>
          <div className="text-lg mb-1">📊</div>
          <div className="text-[10px] opacity-80 mb-1">שינויים השבוע</div>
          <div className="text-sm font-bold">{metrics.weekly_changes?.total} שינויים</div>
          <div className="text-[10px] opacity-70 mt-1">
            {metrics.weekly_changes?.drops} ירידות · {metrics.weekly_changes?.rises} עליות
          </div>
        </div>
      </div>

      {/* Bar chart */}
      {metrics.chart_data?.length > 0 && (
        <div className="bg-[#f9f4ee] rounded-xl p-4 mb-4">
          <div className="text-[11px] text-moca-sub font-semibold mb-3 text-right">
            {metrics.cheapest?.unit} לפי ספק
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
                  formatter={(value) => [`${value} ${metrics.cheapest?.unit}`, 'ערך']}
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

      {/* Claude narrative */}
      <div className="bg-white rounded-xl p-4 border-r-4 border-[#5c3317] shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm">🤖</span>
          <span className="text-[11px] text-moca-sub font-semibold">ניתוח AI</span>
        </div>
        <p className="text-sm text-moca-text leading-relaxed text-right">{narrative}</p>
      </div>
    </div>
  )
}

function SkeletonSection() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-moca-border/40 p-5 mb-5 animate-pulse">
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

function SkeletonSentiment() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-moca-border/40 p-5 mb-5 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 bg-gray-200 rounded" />
        <div className="h-4 bg-gray-200 rounded w-40" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {[0, 1, 2, 3, 4, 5].map(i => (
          <div key={i} className="h-24 bg-gray-100 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

const SENTIMENT_CONFIG = {
  positive: { color: 'green',  label: 'חיובי'   },
  negative: { color: 'red',    label: 'שלילי'   },
  mixed:    { color: 'orange', label: 'מעורב'   },
  neutral:  { color: 'gray',   label: 'ניטרלי'  },
}

function CarrierSentimentCard({ row }) {
  const cfg = SENTIMENT_CONFIG[row.sentiment] || SENTIMENT_CONFIG.neutral
  const badgeColors = {
    green:  'bg-emerald-50 text-emerald-700',
    red:    'bg-red-50 text-red-700',
    orange: 'bg-amber-50 text-amber-700',
    gray:   'bg-gray-100 text-gray-500',
  }
  const platforms = Object.keys(row.platform_data || {})

  return (
    <div className="bg-[#f9f4ee] rounded-xl p-4 border-r-4 border-[#5c3317]">
      <div className="flex items-center justify-between mb-2">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold ${badgeColors[cfg.color]}`}>
          {cfg.label}
        </span>
        <span className="text-sm font-semibold text-moca-text">{CARRIER_NAMES[row.carrier] || row.carrier}</span>
      </div>
      <p className="text-sm text-moca-text leading-relaxed text-right mb-2">{row.narrative}</p>
      <div className="flex items-center gap-1.5 justify-end flex-wrap">
        {platforms.map(p => (
          <span key={p} className="text-[10px] text-moca-sub bg-white px-1.5 py-0.5 rounded border border-moca-border/40">
            {p === 'facebook' ? 'FB' : p === 'instagram' ? 'IG' : p === 'twitter' ? 'X' : p === 'youtube' ? 'YT' : p === 'tiktok' ? 'TT' : p}
            {' '}{row.platform_data[p]?.length || 0}
          </span>
        ))}
        <span className="text-[10px] text-moca-sub">{formatDate(row.generated_at)}</span>
      </div>
    </div>
  )
}

function SentimentSection({ sentiments, isAdmin, onRefresh, refreshing }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-moca-border/40 p-5 mb-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🌐</span>
          <h2 className="text-lg font-semibold text-moca-text">הלך רוח ברשתות החברתיות</h2>
        </div>
        {isAdmin && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="text-[11px] px-2 py-1 rounded-lg border border-moca-border text-moca-muted hover:text-moca-bolt hover:border-moca-bolt transition-colors disabled:opacity-50"
          >
            {refreshing ? 'מרענן...' : 'רענן עכשיו'}
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {sentiments.map(row => (
          <CarrierSentimentCard key={row.carrier} row={row} />
        ))}
      </div>
    </div>
  )
}

export default function ExecutiveSummaryPage() {
  const { isAdmin } = useAuth()
  const [summaries, setSummaries] = useState([])
  const [loading, setLoading] = useState(true)
  const [notGenerated, setNotGenerated] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  // Social sentiment state
  const [sentiments, setSentiments] = useState([])
  const [sentimentLoading, setSentimentLoading] = useState(true)
  const [sentimentNotGenerated, setSentimentNotGenerated] = useState(false)
  const [sentimentRefreshing, setSentimentRefreshing] = useState(false)

  async function load() {
    try {
      const data = await api.getExecutiveSummary()
      const ordered = CATEGORIES.map(c => data.find(d => d.category === c.id)).filter(Boolean)
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

  async function loadSentiment() {
    try {
      const data = await api.getSocialSentiment()
      setSentiments(data)
      setSentimentNotGenerated(false)
    } catch (err) {
      if (err.message === 'not_generated_yet' || err.message === 'HTTP 404') {
        setSentimentNotGenerated(true)
      }
    } finally {
      setSentimentLoading(false)
    }
  }

  useEffect(() => { load(); loadSentiment() }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await api.refreshExecutiveSummary()
      await load()
    } catch (err) {
      console.error('refresh failed', err)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleSentimentRefresh() {
    setSentimentRefreshing(true)
    try {
      await api.refreshSocialSentiment()
      await loadSentiment()
    } catch (err) {
      console.error('sentiment refresh failed', err)
    } finally {
      setSentimentRefreshing(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-moca-text mb-6 text-right">תקציר מנהלים</h1>
        {[0, 1, 2, 3].map(i => <SkeletonSection key={i} />)}
      </div>
    )
  }

  if (notGenerated) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-moca-text mb-6 text-right">תקציר מנהלים</h1>
        <div className="bg-white rounded-xl p-12 text-center border border-moca-border/40">
          <div className="text-4xl mb-3">🕗</div>
          <p className="text-moca-muted text-sm">הניתוח ייווצר ב-08:00 הקרוב</p>
          {isAdmin && (
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="mt-4 px-4 py-2 rounded-lg bg-[#5c3317] text-white text-sm hover:bg-[#7a4a28] transition-colors disabled:opacity-50"
            >
              {refreshing ? 'מייצר ניתוח...' : 'צור עכשיו'}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-moca-text mb-6 text-right">תקציר מנהלים</h1>
      {summaries.map(s => (
        <SummarySection
          key={s.category}
          data={s}
          onRefresh={handleRefresh}
          refreshing={refreshing}
          isAdmin={isAdmin}
        />
      ))}

      {/* Social sentiment section */}
      {sentimentLoading ? (
        <SkeletonSentiment />
      ) : sentimentNotGenerated ? (
        <div className="bg-white rounded-xl shadow-sm border border-moca-border/40 p-5 mb-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-2xl">🌐</span>
            <h2 className="text-lg font-semibold text-moca-text">הלך רוח ברשתות החברתיות</h2>
          </div>
          <div className="text-center py-8">
            <div className="text-3xl mb-2">🕗</div>
            <p className="text-moca-muted text-sm">הניתוח ייווצר ב-08:10 הקרוב</p>
            {isAdmin && (
              <button
                onClick={handleSentimentRefresh}
                disabled={sentimentRefreshing}
                className="mt-3 px-4 py-2 rounded-lg bg-[#5c3317] text-white text-sm hover:bg-[#7a4a28] transition-colors disabled:opacity-50"
              >
                {sentimentRefreshing ? 'מייצר...' : 'צור עכשיו'}
              </button>
            )}
          </div>
        </div>
      ) : sentiments.length > 0 ? (
        <SentimentSection
          sentiments={sentiments}
          isAdmin={isAdmin}
          onRefresh={handleSentimentRefresh}
          refreshing={sentimentRefreshing}
        />
      ) : null}
    </div>
  )
}
