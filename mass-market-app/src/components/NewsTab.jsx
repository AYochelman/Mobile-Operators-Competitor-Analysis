import { useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api'
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
]

const CARRIER_TAG_COLORS = {
  partner:   'bg-blue-100 text-blue-700',
  pelephone: 'bg-pink-100 text-pink-700',
  hotmobile: 'bg-orange-100 text-orange-700',
  cellcom:   'bg-green-100 text-green-700',
  mobile019: 'bg-violet-100 text-violet-700',
  xphone:    'bg-sky-100 text-sky-700',
  wecom:     'bg-yellow-100 text-yellow-800',
  neptucom:  'bg-slate-100 text-slate-600',
}

const CARRIER_LABEL = Object.fromEntries(CARRIERS.map(c => [c.id, c.label]))

function formatRelativeDate(pubDateStr) {
  if (!pubDateStr) return ''
  try {
    const d    = new Date(pubDateStr)
    const diff = Date.now() - d.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60)  return `\u05dc\u05e4\u05e0\u05d9 ${mins} \u05d3\u05e7\u05d5\u05ea`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `\u05dc\u05e4\u05e0\u05d9 ${hours} \u05e9\u05e2\u05d5\u05ea`
    const days  = Math.floor(hours / 24)
    if (days === 1) return '\u05d0\u05ea\u05de\u05d5\u05dc'
    if (days < 7)   return `\u05dc\u05e4\u05e0\u05d9 ${days} \u05d9\u05de\u05d9\u05dd`
    return d.toLocaleDateString('he-IL')
  } catch {
    return ''
  }
}

export default function NewsTab() {
  const [articles, setArticles]           = useState([])
  const [loading, setLoading]             = useState(true)
  const [error, setError]                 = useState(null)
  const [carrierFilter, setCarrierFilter] = useState('all')

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

  const filtered = carrierFilter === 'all'
    ? articles
    : articles.filter(a => a.carrier === carrierFilter)

  const fetchedAt = articles[0]?.fetched_at
    ? new Date(articles[0].fetched_at).toLocaleString('he-IL')
    : null

  if (loading) return (
    <div className="flex justify-center py-20"><Spinner /></div>
  )

  if (error) return (
    <div className="text-center py-20 text-red-500">
      <p className="mb-3">\u05e9\u05d2\u05d9\u05d0\u05d4 \u05d1\u05d8\u05e2\u05d9\u05e0\u05ea \u05d4\u05d7\u05d3\u05e9\u05d5\u05ea</p>
      <button onClick={load} className="text-sm underline">\u05e0\u05e1\u05d4 \u05e9\u05d5\u05d1</button>
    </div>
  )

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <Newspaper size={20} className="text-[#5c3317]" />
        <h2 className="text-xl font-bold text-[#5c3317]">\u05d1\u05d7\u05d3\u05e9\u05d5\u05ea</h2>
      </div>
      <p className="text-sm text-[#8b6b52] mb-4">
        \u05d0\u05d6\u05db\u05d5\u05e8\u05d9 \u05d7\u05d1\u05e8\u05d5\u05ea \u05d4\u05e1\u05dc\u05d5\u05dc\u05e8 \u05d1\u05e2\u05d9\u05ea\u05d5\u05e0\u05d5\u05ea \u05d4\u05d9\u05e9\u05e8\u05d0\u05dc\u05d9\u05ea
      </p>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 mb-3 items-center" dir="rtl">
        <span className="text-sm text-[#8b6b52] font-medium">
          \u05e1\u05d9\u05e0\u05d5\u05df \u05dc\u05e4\u05d9 \u05d7\u05d1\u05e8\u05d4:
        </span>
        {CARRIERS.map(c => (
          <button
            key={c.id}
            onClick={() => setCarrierFilter(c.id)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
              ${carrierFilter === c.id
                ? 'bg-[#5c3317] text-white border-[#5c3317]'
                : 'bg-white text-[#5c3317] border-[#d4bfa8] hover:bg-[#f5ede0]'
              }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Last updated */}
      {fetchedAt && (
        <p className="text-xs text-[#a08060] mb-4 flex items-center gap-1">
          <Calendar size={12} />
          \u05e2\u05d5\u05d3\u05db\u05df \u05dc\u05d0\u05d7\u05e8\u05d5\u05e0\u05d4: {fetchedAt} · {filtered.length} \u05db\u05ea\u05d1\u05d5\u05ea
        </p>
      )}

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <Newspaper size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">\u05dc\u05d0 \u05e0\u05de\u05e6\u05d0\u05d5 \u05db\u05ea\u05d1\u05d5\u05ea</p>
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
            className="bg-white rounded-xl border border-[#e8d9c8] p-4 hover:shadow-md hover:border-[#c4a882] transition-all block"
          >
            {/* Source + date */}
            <div className="flex justify-between items-start mb-2 gap-2">
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-[#f5ede0] text-[#5c3317]">
                {article.source || '\u05d7\u05d3\u05e9\u05d5\u05ea'}
              </span>
              <span className="text-xs text-[#a08060] flex items-center gap-1 whitespace-nowrap">
                <Calendar size={11} />
                {formatRelativeDate(article.published_at)}
              </span>
            </div>

            {/* Headline */}
            <p className="font-semibold text-sm text-[#2d1f14] leading-snug mb-3 line-clamp-3" title={article.headline}>
              {article.headline}
            </p>

            {/* Carrier tag + link icon */}
            <div className="flex items-center justify-between">
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${CARRIER_TAG_COLORS[article.carrier] || 'bg-gray-100 text-gray-600'}`}>
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
