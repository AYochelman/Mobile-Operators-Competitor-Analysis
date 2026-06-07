import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import { carrierLabel } from '../data/carrierLabels'

/* ─────────────────────────────────────────────────────────────
   "ברשתות החברתיות" — dedicated social-sentiment page.
   Moved out of the executive report (ExecutiveSummaryPage) so it
   gets its own space. Fed by api.getSocialSentiment().
   ───────────────────────────────────────────────────────────── */

const SENTIMENT_BADGE = {
  positive: 'bg-emerald-50 text-emerald-700',
  negative: 'bg-red-50 text-red-700',
  mixed:    'bg-amber-50 text-amber-700',
  neutral:  'bg-gray-100 text-gray-500',
}
const SENTIMENT_LABEL = { positive: 'חיובי', negative: 'שלילי', mixed: 'מעורב', neutral: 'ניטרלי' }
const PLATFORM_SHORT = { facebook: 'FB', instagram: 'IG', twitter: 'X', youtube: 'YT', tiktok: 'TT' }

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })
}

function UsersIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  )
}

function SentimentCard({ row }) {
  const badgeCls   = SENTIMENT_BADGE[row.sentiment] || SENTIMENT_BADGE.neutral
  const label      = SENTIMENT_LABEL[row.sentiment] || 'ניטרלי'
  const platforms  = Object.keys(row.platform_data || {}).filter(k => k !== '_counts')
  const counts     = row.platform_data?._counts || null
  const totalPosts = platforms.reduce((sum, p) => sum + (row.platform_data[p]?.length || 0), 0)
  return (
    <div className="bg-moca-bg rounded-xl p-4 border border-moca-border/40">
      <div className="flex items-center justify-between mb-1.5">
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${badgeCls}`}>{label}</span>
        <span className="text-sm font-semibold text-moca-text">{carrierLabel(row.carrier)}</span>
      </div>
      <p className="text-xs text-moca-text leading-relaxed text-right">{row.narrative}</p>

      <div className="flex items-end justify-between mt-3 flex-wrap gap-1">
        <div className="flex items-center gap-1 flex-wrap">
          {platforms.map(p => (
            <span key={p} className="text-[10px] text-moca-sub bg-white px-1 py-0.5 rounded border border-moca-border/40">
              {PLATFORM_SHORT[p] || p} {row.platform_data[p]?.length || 0}
            </span>
          ))}
        </div>
        <div className="text-right">
          <div className="text-[10px] text-moca-sub mb-0.5">{totalPosts} תגובות נותחו</div>
          {totalPosts > 0 && (
            <div className="flex items-center gap-1 justify-end">
              <span className="inline-flex items-center gap-0.5 text-[10px] text-emerald-600 bg-emerald-50 px-1 py-0.5 rounded" title="חיוביות"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />{counts?.positive ?? 0}</span>
              <span className="inline-flex items-center gap-0.5 text-[10px] text-red-600 bg-red-50 px-1 py-0.5 rounded" title="שליליות"><span className="w-1.5 h-1.5 rounded-full bg-red-400 inline-block" />{counts?.negative ?? 0}</span>
              <span className="inline-flex items-center gap-0.5 text-[10px] text-gray-500 bg-gray-100 px-1 py-0.5 rounded" title="ניטרליות"><span className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block" />{counts?.neutral ?? 0}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function SocialPage() {
  const { isAdmin } = useAuth()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  async function load() {
    try { setRows(await api.getSocialSentiment()) }
    catch { /* 404 = not generated yet → rows stays [] */ }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try { await api.refreshSocialSentiment(); await load() }
    catch (err) { console.error('sentiment refresh failed', err) }
    finally { setRefreshing(false) }
  }

  // Pelephone pinned first (matches the previous executive-report ordering)
  const sorted = [...rows].sort((a, b) => {
    if (a.carrier === 'pelephone') return -1
    if (b.carrier === 'pelephone') return 1
    return 0
  })

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-1">
        <div className="flex items-center gap-2">
          <span className="text-moca-bolt"><UsersIcon /></span>
          <h1 className="text-2xl font-display font-bold text-moca-text text-right">ברשתות החברתיות</h1>
        </div>
        {isAdmin && (
          <button onClick={handleRefresh} disabled={refreshing}
            className="text-[11px] px-3 py-1.5 rounded-lg border border-moca-border text-moca-muted hover:text-moca-bolt hover:border-moca-bolt transition-colors disabled:opacity-50 shrink-0">
            {refreshing ? 'מרענן...' : 'רענן עכשיו'}
          </button>
        )}
      </div>
      <p className="text-sm text-moca-sub text-right mb-6">
        ניתוח סנטימנט ותגובות גולשים ברשתות החברתיות, לפי מפעיל
        {rows[0]?.generated_at && <span className="text-moca-muted"> · עודכן {formatDate(rows[0].generated_at)}</span>}
      </p>

      {/* Body */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[0, 1, 2, 3].map(i => <div key={i} className="h-28 bg-gray-100 rounded-xl animate-pulse" />)}
        </div>
      ) : sorted.length === 0 ? (
        <div className="bg-white rounded-xl p-12 text-center border border-moca-border/40">
          <div className="text-4xl mb-3">🕗</div>
          <p className="text-moca-muted text-sm">הניתוח ייווצר ב-08:00 הקרוב</p>
          {isAdmin && (
            <button onClick={handleRefresh} disabled={refreshing}
              className="mt-4 px-4 py-2 rounded-lg bg-moca-bolt text-white text-sm hover:bg-[#7a4a28] transition-colors disabled:opacity-50">
              {refreshing ? 'מייצר ניתוח...' : 'צור עכשיו'}
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {sorted.map(row => <SentimentCard key={row.carrier} row={row} />)}
        </div>
      )}
    </div>
  )
}
