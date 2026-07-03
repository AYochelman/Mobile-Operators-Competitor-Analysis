import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../lib/api'
import { useAuth } from './useAuth'

const WatchlistContext = createContext(null)

const keyOf = (p) => `${p.plan_type}|${p.carrier}|${p.plan_name}`

const SEVEN_DAYS = 7 * 24 * 60 * 60 * 1000

// `changed_at` is written server-side as `datetime.now().isoformat()` — LOCAL
// time, 'T' separator, no 'Z'. We store the "seen" cutoff in the same shape so a
// plain lexical string compare (which is what we use below) stays correct at
// second granularity instead of skewing by the UTC offset (toISOString would).
const localIso = (d = new Date()) => {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
const defaultSeen = () => localIso(new Date(Date.now() - SEVEN_DAYS))

// Per-user "last acknowledged" timestamp for watched-plan changes (localStorage).
// The sidebar badge counts changes newer than this; the watchlist alerts tab
// clears it via markChangesSeen() so the badge doesn't nag forever.
const seenKey = (user) => `moca_watchlist_seen_${user?.id || user?.email || 'anon'}`
const readSeen = (user) => { try { return localStorage.getItem(seenKey(user)) } catch { return null } }
const writeSeen = (user, iso) => { try { localStorage.setItem(seenKey(user), iso) } catch { /* ignore */ } }

export function WatchlistProvider({ children }) {
  const { user } = useAuth()
  const [items, setItems] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [changes, setChanges] = useState([])
  const [changesReady, setChangesReady] = useState(false)
  // "Seen" cutoff — watched-plan changes newer than this are unread. Defaults to
  // 7 days ago for a fresh browser (matches the previous badge behavior) until
  // the user acknowledges them; persisted per user once acknowledged.
  const [lastSeen, setLastSeen] = useState(defaultSeen)

  // Load the persisted "seen" timestamp once the user is known
  useEffect(() => {
    setLastSeen(readSeen(user) || defaultSeen())
  }, [user])

  const load = useCallback(async () => {
    if (!user) { setItems([]); setLoaded(true); return }
    try {
      const data = await api.getWatchlist()
      setItems(data || [])
    } catch {
      setItems([])
    } finally {
      setLoaded(true)
    }
  }, [user])

  useEffect(() => { load() }, [load])

  // Fetch recent changes once when the user loads. Shared with the watchlist
  // alerts tab so the badge and the list always agree.
  useEffect(() => {
    if (!user) { setChanges([]); setChangesReady(true); return }
    let cancelled = false
    setChangesReady(false)
    Promise.all([
      api.getChanges(100).catch(() => []),
      api.getAbroadChanges().catch(() => []),
      api.getGlobalChanges().catch(() => []),
    ]).then(([domestic, abroad, global]) => {
      if (cancelled) return
      setChanges([
        ...(Array.isArray(domestic) ? domestic : []).map(c => ({ ...c, plan_type: 'domestic' })),
        ...(Array.isArray(abroad) ? abroad : []).map(c => ({ ...c, plan_type: 'abroad' })),
        ...(Array.isArray(global) ? global : []).map(c => ({ ...c, plan_type: 'global' })),
      ])
      setChangesReady(true)
    })
    return () => { cancelled = true }
  }, [user])

  // Unread = watched-plan changes newer than the acknowledged cutoff
  const changesCount = useMemo(() => {
    if (!loaded || items.length === 0) return 0
    const watchedKeys = new Set(items.map(keyOf))
    return changes.filter(c => watchedKeys.has(keyOf(c)) && (c.changed_at || '') > lastSeen).length
  }, [loaded, items, changes, lastSeen])

  // Acknowledge everything up to "now" — future changes still surface
  const markChangesSeen = useCallback(() => {
    const now = localIso()
    setLastSeen(now)
    writeSeen(user, now)
  }, [user])

  // Memoized so `isWatched`'s identity is stable across unrelated provider
  // re-renders (changes/lastSeen updates). DashboardPage's filteredPlans useMemo
  // depends on isWatched — without this it re-ran the full filter+sort+regex
  // pipeline on every provider render.
  const keys = useMemo(() => new Set(items.map(keyOf)), [items])
  const isWatched = useCallback((plan) => keys.has(keyOf(plan)), [keys])

  const toggle = async (plan) => {
    const payload = { carrier: plan.carrier, plan_name: plan.plan_name, plan_type: plan.plan_type }
    if (isWatched(payload)) {
      setItems(xs => xs.filter(x => keyOf(x) !== keyOf(payload)))
      try { await api.removeFromWatchlist(payload) } catch { load() }
    } else {
      const entry = { ...payload, added_at: new Date().toISOString() }
      setItems(xs => [entry, ...xs])
      try { await api.addToWatchlist(payload) } catch { load() }
    }
  }

  return (
    <WatchlistContext.Provider value={{ items, loaded, isWatched, toggle, reload: load, changes, changesReady, changesCount, lastSeen, markChangesSeen }}>
      {children}
    </WatchlistContext.Provider>
  )
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext)
  if (!ctx) throw new Error('useWatchlist must be used within WatchlistProvider')
  return ctx
}
