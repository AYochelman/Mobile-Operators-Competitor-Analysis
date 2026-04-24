import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api'
import { useAuth } from './useAuth'

const WatchlistContext = createContext(null)

const keyOf = (p) => `${p.plan_type}|${p.carrier}|${p.plan_name}`

export function WatchlistProvider({ children }) {
  const { user } = useAuth()
  const [items, setItems] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [changesCount, setChangesCount] = useState(0)

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

  // Count recent changes for watched plans (last 7 days)
  useEffect(() => {
    if (!loaded || items.length === 0) { setChangesCount(0); return }
    const watchedKeys = new Set(items.map(keyOf))
    Promise.all([
      api.getChanges(100).catch(() => []),
      api.getAbroadChanges().catch(() => []),
      api.getGlobalChanges().catch(() => []),
    ]).then(([domestic, abroad, global]) => {
      const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
      const all = [
        ...(Array.isArray(domestic) ? domestic : []).map(c => ({ ...c, plan_type: 'domestic' })),
        ...(Array.isArray(abroad) ? abroad : []).map(c => ({ ...c, plan_type: 'abroad' })),
        ...(Array.isArray(global) ? global : []).map(c => ({ ...c, plan_type: 'global' })),
      ]
      const count = all.filter(c => c.changed_at >= cutoff && watchedKeys.has(keyOf(c))).length
      setChangesCount(count)
    })
  }, [loaded, items])

  const keys = new Set(items.map(keyOf))
  const isWatched = (plan) => keys.has(keyOf(plan))

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
    <WatchlistContext.Provider value={{ items, loaded, isWatched, toggle, reload: load, changesCount }}>
      {children}
    </WatchlistContext.Provider>
  )
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext)
  if (!ctx) throw new Error('useWatchlist must be used within WatchlistProvider')
  return ctx
}
