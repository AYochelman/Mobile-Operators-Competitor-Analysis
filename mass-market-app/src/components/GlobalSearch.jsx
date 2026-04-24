import { useState, useEffect, useRef, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'

const CARRIER_LABELS = {
  partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום',
  mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', neptucom: 'Neptucom',
  tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM',
  esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global',
  saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks',
  voye: 'VOYE', orbit: 'Orbit', travelsim: 'TravelSim',
}
const TYPE_LABELS = { domestic: 'סלולר', abroad: 'חו"ל', global: 'גלובלי' }

function matchScore(plan, terms) {
  if (terms.length === 0) return 0
  const hay = [
    plan.plan_name || '',
    CARRIER_LABELS[plan.carrier] || '',
    plan.carrier || '',
    String(plan.price || ''),
    String(plan.data_gb || ''),
  ].join(' ').toLowerCase()
  let score = 0
  for (const t of terms) {
    if (!hay.includes(t)) return 0  // must match ALL terms
    score += 1
    if ((plan.plan_name || '').toLowerCase().includes(t)) score += 2
  }
  return score
}

export default function GlobalSearch() {
  const navigate = useNavigate()
  const { isSuperAdmin } = useAuth()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [data, setData] = useState({ plans: [], news: [], workspaces: [] })
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  // Keyboard shortcut — Ctrl+K / Cmd+K (use e.code so Hebrew keyboard layout
  // still triggers on the physical K key, which otherwise produces 'ל').
  // Also support '/' as a fallback (works regardless of layout).
  useEffect(() => {
    const onKey = (e) => {
      const isTyping = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName || '')
      if ((e.ctrlKey || e.metaKey) && e.code === 'KeyK') {
        e.preventDefault()
        setOpen(o => !o)
      } else if (e.key === '/' && !e.ctrlKey && !e.metaKey && !isTyping) {
        e.preventDefault()
        setOpen(true)
      } else if (e.key === 'Escape' && open) {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  // Lazy-load data on first open
  useEffect(() => {
    if (!open || loaded || loading) return
    setLoading(true)
    const jobs = [
      api.getPlans().then(p => p.map(x => ({ ...x, plan_type: 'domestic' }))).catch(() => []),
      api.getAbroadPlans().then(p => p.map(x => ({ ...x, plan_type: 'abroad' }))).catch(() => []),
      api.getGlobalPlans().then(p => p.map(x => ({ ...x, plan_type: 'global' }))).catch(() => []),
      api.getNews().then(n => n || []).catch(() => []),
      isSuperAdmin ? api.getWorkspaces().catch(() => []) : Promise.resolve([]),
    ]
    Promise.all(jobs).then(([d, a, g, news, ws]) => {
      setData({ plans: [...d, ...a, ...g], news, workspaces: ws })
      setLoaded(true)
    }).finally(() => setLoading(false))
  }, [open, loaded, loading, isSuperAdmin])

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 10)
    else { setQ(''); setSelectedIdx(0) }
  }, [open])

  const results = useMemo(() => {
    const terms = q.trim().toLowerCase().split(/\s+/).filter(Boolean)
    if (terms.length === 0) return { plans: [], news: [], workspaces: [] }

    const matchesTerms = (text) => {
      const hay = (text || '').toLowerCase()
      return terms.every(t => hay.includes(t))
    }

    const planResults = data.plans
      .map(p => ({ ...p, __score: matchScore(p, terms) }))
      .filter(p => p.__score > 0)
      .sort((a, b) => b.__score - a.__score)
      .slice(0, 12)

    const newsResults = data.news
      .filter(n => matchesTerms(`${n.headline || ''} ${n.carrier || ''} ${n.source || ''}`))
      .slice(0, 5)

    const wsResults = data.workspaces
      .filter(w => matchesTerms(`${w.name || ''} ${w.slug || ''} ${w.mvno_carrier || ''}`))
      .slice(0, 5)

    return { plans: planResults, news: newsResults, workspaces: wsResults }
  }, [q, data])

  const flatResults = useMemo(() => [
    ...results.plans.map(p => ({ kind: 'plan', item: p })),
    ...results.news.map(n => ({ kind: 'news', item: n })),
    ...results.workspaces.map(w => ({ kind: 'workspace', item: w })),
  ], [results])

  useEffect(() => { setSelectedIdx(0) }, [q])

  const onKeyDownInput = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx(i => Math.min(i + 1, flatResults.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && flatResults[selectedIdx]) {
      e.preventDefault()
      goTo(flatResults[selectedIdx])
    }
  }

  const goTo = (r) => {
    setOpen(false)
    if (r.kind === 'plan') {
      const p = r.item
      const params = new URLSearchParams({
        tab: p.plan_type,
        carrier: p.carrier,
        highlight: p.plan_name,
      })
      navigate(`/?${params}`)
    } else if (r.kind === 'news') {
      window.open(r.item.url, '_blank', 'noopener,noreferrer')
    } else if (r.kind === 'workspace') {
      navigate('/admin/workspaces')
    }
  }

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[9999] animate-fade-in" onClick={() => setOpen(false)}>
      <div className="fixed inset-0 bg-black/40" />
      <div className="fixed top-[15vh] left-1/2 -translate-x-1/2 w-full max-w-xl px-4" onClick={e => e.stopPropagation()}>
        <div className="bg-white rounded-xl shadow-2xl overflow-hidden">
          {/* Search input */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gray-400 flex-shrink-0">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={q}
              onChange={e => setQ(e.target.value)}
              onKeyDown={onKeyDownInput}
              placeholder="חפש חבילה, ספק, ידיעה..."
              className="flex-1 bg-transparent outline-none text-sm"
            />
            <kbd className="text-[10px] font-mono bg-gray-100 text-gray-500 rounded px-1.5 py-0.5">ESC</kbd>
          </div>

          {/* Results */}
          <div className="max-h-[60vh] overflow-y-auto">
            {loading && !loaded && (
              <div className="px-4 py-8 text-center text-sm text-gray-400">טוען אינדקס…</div>
            )}
            {loaded && q.trim() === '' && (
              <div className="px-4 py-8 text-center text-sm text-gray-400">
                הקלד לחיפוש בחבילות, ספקים, חדשות{isSuperAdmin ? ', workspaces' : ''}
                <div className="mt-3 text-[11px] text-gray-300">
                  <kbd className="font-mono bg-gray-100 text-gray-500 rounded px-1.5 py-0.5 mx-0.5">↑</kbd>
                  <kbd className="font-mono bg-gray-100 text-gray-500 rounded px-1.5 py-0.5 mx-0.5">↓</kbd>
                  ניווט ·
                  <kbd className="font-mono bg-gray-100 text-gray-500 rounded px-1.5 py-0.5 mx-0.5 mr-2">↵</kbd>
                  בחר
                </div>
              </div>
            )}
            {loaded && q.trim() !== '' && flatResults.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-gray-400">אין תוצאות עבור "{q}"</div>
            )}

            {results.plans.length > 0 && (
              <div className="border-b border-gray-100">
                <p className="text-[10px] font-semibold uppercase text-gray-400 px-4 pt-3 pb-1 tracking-wider">חבילות</p>
                {results.plans.map((p, i) => {
                  const idx = i
                  const sel = idx === selectedIdx
                  return (
                    <button
                      key={`plan-${p.carrier}-${p.plan_name}-${i}`}
                      onClick={() => goTo({ kind: 'plan', item: p })}
                      onMouseEnter={() => setSelectedIdx(idx)}
                      className={`w-full text-right px-4 py-2 flex items-center justify-between gap-3 ${sel ? 'bg-moca-cream' : 'hover:bg-gray-50'}`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-800 truncate">{p.plan_name}</p>
                        <p className="text-[11px] text-gray-500 mt-0.5">
                          {CARRIER_LABELS[p.carrier] || p.carrier}
                          <span className="mx-1.5 text-gray-300">·</span>
                          {TYPE_LABELS[p.plan_type] || p.plan_type}
                          {p.data_gb ? <><span className="mx-1.5 text-gray-300">·</span>{p.data_gb}GB</> : null}
                        </p>
                      </div>
                      <span className="text-sm font-bold text-moca-espresso flex-shrink-0" dir="ltr">₪{p.price}</span>
                    </button>
                  )
                })}
              </div>
            )}

            {results.news.length > 0 && (
              <div className="border-b border-gray-100">
                <p className="text-[10px] font-semibold uppercase text-gray-400 px-4 pt-3 pb-1 tracking-wider">חדשות</p>
                {results.news.map((n, i) => {
                  const idx = results.plans.length + i
                  const sel = idx === selectedIdx
                  return (
                    <button
                      key={`news-${n.url || i}`}
                      onClick={() => goTo({ kind: 'news', item: n })}
                      onMouseEnter={() => setSelectedIdx(idx)}
                      className={`w-full text-right px-4 py-2 ${sel ? 'bg-moca-cream' : 'hover:bg-gray-50'}`}
                    >
                      <p className="text-sm text-gray-800 truncate">{n.headline}</p>
                      <p className="text-[11px] text-gray-500 mt-0.5">
                        {CARRIER_LABELS[n.carrier] || n.carrier}
                        {n.source && <><span className="mx-1.5 text-gray-300">·</span>{n.source}</>}
                      </p>
                    </button>
                  )
                })}
              </div>
            )}

            {results.workspaces.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold uppercase text-gray-400 px-4 pt-3 pb-1 tracking-wider">Workspaces</p>
                {results.workspaces.map((w, i) => {
                  const idx = results.plans.length + results.news.length + i
                  const sel = idx === selectedIdx
                  return (
                    <button
                      key={`ws-${w.id}`}
                      onClick={() => goTo({ kind: 'workspace', item: w })}
                      onMouseEnter={() => setSelectedIdx(idx)}
                      className={`w-full text-right px-4 py-2 flex items-center justify-between gap-3 ${sel ? 'bg-moca-cream' : 'hover:bg-gray-50'}`}
                    >
                      <div>
                        <p className="text-sm font-semibold text-gray-800">{w.name}</p>
                        <code className="text-[11px] text-gray-500 font-mono">{w.slug}</code>
                      </div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${w.active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                        {w.active ? 'פעיל' : 'מושעה'}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}
