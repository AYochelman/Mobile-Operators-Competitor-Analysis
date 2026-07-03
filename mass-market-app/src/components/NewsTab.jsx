import { useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'
import { getCarrierColor } from './moca/carrierMeta'
// Inline SVG icons (lucide-react not installed)
function Newspaper({ size = 24, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z"/>
      <line x1="7" y1="8" x2="17" y2="8"/>
      <line x1="7" y1="12" x2="17" y2="12"/>
      <line x1="7" y1="16" x2="13" y2="16"/>
    </svg>
  )
}
function Calendar({ size = 24, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
  )
}
function ExternalLink({ size = 24, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/>
      <line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  )
}
import Spinner from './ui/Spinner'

const CARRIERS = [
  { id: 'all',       label: '\u05d4\u05db\u05dc' },
  { id: 'partner',   label: '\u05e4\u05e8\u05d8\u05e0\u05e8' },
  { id: 'pelephone', label: '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df' },
  { id: 'hotmobile', label: '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc' },
  { id: 'cellcom',   label: '\u05e1\u05dc\u05e7\u05d5\u05dd' },
  { id: 'mobile019', label: '019' },
  { id: 'xphone',    label: 'XPhone' },
  { id: 'wecom',     label: 'We-Com' },
  { id: 'neptucom',  label: 'Neptucom' },
  { id: 'golan',     label: 'גולן טלקום' },
  { id: 'rami_levy', label: 'רמי לוי' },
  { id: 'breez',     label: 'Breeze' },
  { id: 'bytesim',   label: 'ByteSim' },
  { id: 'besim',     label: 'Besim' },
]


const CARRIER_LABEL = Object.fromEntries(CARRIERS.map(c => [c.id, c.label]))

const DATE_FILTERS = [
  { id: 'all',   label: 'הכל',           label_en: 'All',           ms: null },
  { id: 'today', label: 'היום',          label_en: 'Today',         ms: 24 * 60 * 60 * 1000 },
  { id: 'week',  label: 'בשבוע האחרון',  label_en: 'Past week',     ms: 7  * 24 * 60 * 60 * 1000 },
  { id: 'month', label: 'בחודש האחרון',  label_en: 'Past month',    ms: 30 * 24 * 60 * 60 * 1000 },
  { id: 'year',  label: 'בשנה האחרונה',  label_en: 'Past year',     ms: 365 * 24 * 60 * 60 * 1000 },
]

function isWithinPeriod(pubDateStr, period) {
  if (period === 'all' || !pubDateStr) return true
  const f = DATE_FILTERS.find(f => f.id === period)
  if (!f?.ms) return true
  try {
    return new Date(pubDateStr).getTime() >= Date.now() - f.ms
  } catch { return true }
}

function formatRelativeDate(pubDateStr, tt) {
  if (!pubDateStr) return ''
  try {
    const d    = new Date(pubDateStr)
    const diff = Date.now() - d.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60)  return tt(`\u05dc\u05e4\u05e0\u05d9 ${mins} \u05d3\u05e7\u05d5\u05ea`, `${mins} min ago`)
    const hours = Math.floor(mins / 60)
    if (hours < 24) return tt(`\u05dc\u05e4\u05e0\u05d9 ${hours} \u05e9\u05e2\u05d5\u05ea`, `${hours}h ago`)
    const days  = Math.floor(hours / 24)
    if (days === 1) return tt('\u05d0\u05ea\u05de\u05d5\u05dc', 'Yesterday')
    if (days < 7)   return tt(`\u05dc\u05e4\u05e0\u05d9 ${days} \u05d9\u05de\u05d9\u05dd`, `${days} days ago`)
    return d.toLocaleDateString('he-IL')
  } catch {
    return ''
  }
}

export default function NewsTab() {
  const { tt } = useLang()
  const [articles, setArticles]           = useState([])
  const [loading, setLoading]             = useState(true)
  const [error, setError]                 = useState(null)
  const [carrierFilter, setCarrierFilter] = useState('all')
  const [dateFilter, setDateFilter]       = useState('all')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getNews()
      setArticles(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = articles
    .filter(a => carrierFilter === 'all' || a.carrier === carrierFilter)
    .filter(a => isWithinPeriod(a.published_at, dateFilter))

  const fetchedAt = articles[0]?.fetched_at
    ? new Date(articles[0].fetched_at).toLocaleString('he-IL')
    : null

  if (loading) return (
    <div className="flex justify-center py-20"><Spinner /></div>
  )

  if (error) return (
    <div className="text-center py-20 text-red-500">
      <p className="mb-3">{tt('שגיאה בטעינת החדשות', 'Error loading news')}</p>
      <button onClick={load} className="text-sm underline">{tt('נסה שוב', 'Try again')}</button>
    </div>
  )

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <Newspaper size={20} className="text-moca-bolt" />
        <h2 className="text-xl font-bold text-moca-bolt">{tt('בחדשות', 'In the News')}</h2>
      </div>
      <p className="text-sm text-[#8b6b52] mb-4">
        {tt('אזכורי חברות הסלולר בעיתונות הישראלית', 'Cellular carrier mentions in the Israeli press')}
      </p>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 mb-3 items-center" dir="rtl">
        <span className="text-sm text-[#8b6b52] font-medium">
          {tt('סינון לפי חברה:', 'Filter by carrier:')}
        </span>
        {CARRIERS.map(c => (
          <button
            key={c.id}
            onClick={() => setCarrierFilter(c.id)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
              ${carrierFilter === c.id
                ? 'bg-moca-bolt text-white border-moca-bolt'
                : 'bg-white text-moca-bolt border-[#d4bfa8] hover:bg-moca-cream'
              }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Date filter bar */}
      <div className="flex flex-wrap gap-2 mb-4 items-center" dir="rtl">
        <span className="text-sm text-[#8b6b52] font-medium">
          {tt('סינון לפי תאריך:', 'Filter by date:')}
        </span>
        {DATE_FILTERS.map(f => (
          <button
            key={f.id}
            onClick={() => setDateFilter(f.id)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
              ${dateFilter === f.id
                ? 'bg-moca-bolt text-white border-moca-bolt'
                : 'bg-white text-moca-bolt border-[#d4bfa8] hover:bg-moca-cream'
              }`}
          >
            {tt(f.label, f.label_en)}
          </button>
        ))}
      </div>

      {/* Last updated */}
      {fetchedAt && (
        <p className="text-xs text-[#a08060] mb-4 flex items-center gap-1">
          <Calendar size={12} />
          {tt('עודכן לאחרונה:', 'Last updated:')} {fetchedAt} · {filtered.length} {tt('כתבות', 'articles')}
        </p>
      )}

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <Newspaper size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{tt('לא נמצאו כתבות', 'No articles found')}</p>
        </div>
      )}

      {/* News grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((article, i) => (
          <a
            key={article.url + i}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-white rounded-xl border border-[#e8d9c8] p-4 hover:shadow-card-hover hover:border-[#c4a882] transition-all block"
          >
            {/* Source + date */}
            <div className="flex justify-between items-start mb-2 gap-2">
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-moca-cream text-moca-bolt">
                {article.source || tt('\u05d7\u05d3\u05e9\u05d5\u05ea', 'News')}
              </span>
              <span className="text-xs text-[#a08060] flex items-center gap-1 whitespace-nowrap">
                <Calendar size={11} />
                {formatRelativeDate(article.published_at, tt)}
              </span>
            </div>

            {/* Headline */}
            <p className="font-semibold text-sm text-[#2d1f14] leading-snug mb-3 line-clamp-3" title={article.headline}>
              {article.headline}
            </p>

            {/* Carrier tag + link icon */}
            <div className="flex items-center justify-between">
              <span
                className="text-xs px-2 py-0.5 rounded font-medium"
                style={{
                  backgroundColor: getCarrierColor(article.carrier) + '22',
                  color: getCarrierColor(article.carrier),
                }}
              >
                {CARRIER_LABEL[article.carrier] || article.carrier}
              </span>
              <ExternalLink size={13} className="text-[#a08060]" />
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
