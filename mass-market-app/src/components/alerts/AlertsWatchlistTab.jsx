import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { useWatchlist } from '../../hooks/useWatchlist'
import Badge from '../ui/Badge'
import Spinner from '../ui/Spinner'
import { ALL_CARRIER_LABELS as CARRIER_LABELS } from '../../data/carrierLabels'

const TYPE_LABELS = { domestic: 'סלולר', abroad: 'חו"ל', global: 'גלובלי' }
const CHANGE_LABELS = { new_plan: 'חדש', price_change: 'שינוי מחיר', removed_plan: 'הוסרה', extras_change: 'שינוי פרטים', details_change: 'עדכון' }
const CHANGE_COLORS = { new_plan: 'green', price_change: 'amber', removed_plan: 'red', extras_change: 'blue', details_change: 'blue' }

const keyOf = (p) => `${p.plan_type}|${p.carrier}|${p.plan_name}`

export default function AlertsWatchlistTab() {
  const { items: watchItems, loaded } = useWatchlist()
  const navigate = useNavigate()
  const [rawChanges, setRawChanges] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getChanges(100).catch(() => []),
      api.getAbroadChanges().catch(() => []),
      api.getGlobalChanges().catch(() => []),
    ]).then(([domestic, abroad, global]) => {
      setRawChanges([
        ...(Array.isArray(domestic) ? domestic : []).map(c => ({ ...c, plan_type: 'domestic' })),
        ...(Array.isArray(abroad) ? abroad : []).map(c => ({ ...c, plan_type: 'abroad' })),
        ...(Array.isArray(global) ? global : []).map(c => ({ ...c, plan_type: 'global' })),
      ])
      setLoading(false)
    })
  }, [])

  const watchedChanges = useMemo(() => {
    if (!loaded) return []
    const watchedKeys = new Set(watchItems.map(keyOf))
    return rawChanges
      .filter(c => watchedKeys.has(keyOf(c)))
      .sort((a, b) => (b.changed_at || '').localeCompare(a.changed_at || ''))
  }, [rawChanges, watchItems, loaded])

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div className="mb-6 text-right">
        <h1 className="text-xl font-bold text-gray-900">התראות מעקב</h1>
        <p className="text-xs text-gray-400 mt-0.5">שינויים בחבילות שאתה עוקב אחריהן</p>
      </div>

      {(loading || !loaded) && <div className="flex justify-center py-20"><Spinner /></div>}

      {!loading && loaded && watchItems.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <p className="text-4xl mb-3 opacity-40">&#11088;</p>
          <p className="text-sm">עדיין לא עוקב אחר חבילות</p>
          <p className="text-xs mt-1 text-gray-300">לחץ על &#11088; בכרטיס חבילה כדי להוסיף למעקב</p>
        </div>
      )}

      {!loading && loaded && watchItems.length > 0 && watchedChanges.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <p className="text-4xl mb-3 opacity-40">&#10003;</p>
          <p className="text-sm">אין שינויים חדשים בחבילות שבמעקב</p>
        </div>
      )}

      {!loading && loaded && watchedChanges.length > 0 && (
        <div className="space-y-2">
          {watchedChanges.map((c, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 text-right hover-lift">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <Badge color={CHANGE_COLORS[c.change_type] || 'gray'}>{CHANGE_LABELS[c.change_type] || c.change_type}</Badge>
                    <Badge color="gray">{TYPE_LABELS[c.plan_type]}</Badge>
                    {c.changed_at && (
                      <span className="text-[10px] text-gray-400">
                        {new Date(c.changed_at).toLocaleDateString('he-IL')} {c.changed_at.slice(11, 16)}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-semibold text-gray-800 mb-0.5">{c.plan_name}</p>
                  <p className="text-xs text-gray-500">{CARRIER_LABELS[c.carrier] || c.carrier}</p>
                  {c.change_type === 'price_change' && c.old_val && c.new_val && (
                    <p className="text-xs text-gray-400 mt-1.5 flex items-center gap-1.5">
                      <span className="line-through text-red-400">&#8362;{c.old_val}</span>
                      <span className="text-gray-300">&#8594;</span>
                      <span className="text-emerald-600 font-semibold">&#8362;{c.new_val}</span>
                    </p>
                  )}
                </div>
                <button
                  onClick={() => {
                    // Map plan_type to phase-9 clean route; legacy ?tab= is the
                    // fallback for types without a dedicated route (content, etc).
                    const PATH = { domestic: '/plans', abroad: '/roaming', global: '/esim' }
                    const base = PATH[c.plan_type] || `/?tab=${c.plan_type}`
                    const sep = base.includes('?') ? '&' : '?'
                    navigate(`${base}${sep}carrier=${c.carrier}&highlight=${encodeURIComponent(c.plan_name || '')}`)
                  }}
                  className="shrink-0 text-xs text-moca-bolt hover:text-moca-dark transition-colors px-2.5 py-1.5 rounded-lg border border-moca-border/50 hover:bg-moca-cream"
                >
                  צפה
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
