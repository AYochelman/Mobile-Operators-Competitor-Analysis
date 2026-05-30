import { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'

// Module-level cache + in-flight coalescing. /api/coupons is public and the
// list is short (handful of rows), so one fetch per session is plenty. Cards
// across all tabs share the same Promise.
let _cache = null            // { carrier: { code, discount_label, ... } }
let _inflight = null         // Promise resolving to the cache
let _subscribers = new Set() // setState fns to notify on refresh

async function _load(force = false) {
  if (_cache && !force) return _cache
  if (_inflight) return _inflight
  _inflight = api.getCoupons()
    .then(rows => {
      // First-wins index: if two active codes exist for the same carrier, the
      // first one in the API response (sorted by code A-Z) is the one shown.
      // Admins should disable extras to control which surfaces.
      const idx = {}
      ;(rows || []).forEach(r => { if (!idx[r.carrier]) idx[r.carrier] = r })
      _cache = idx
      _subscribers.forEach(fn => fn(_cache))
      return _cache
    })
    .catch(() => { _cache = {}; return _cache })
    .finally(() => { _inflight = null })
  return _inflight
}

/** Call after admin edits/creates/deletes a coupon so cards refresh. */
export function refreshCoupons() {
  return _load(true)
}

/**
 * Returns { couponFor(carrier), coupons, loading }.
 * `couponFor(carrier)` returns the coupon object or null.
 */
export function useCoupons() {
  const [coupons, setCoupons] = useState(_cache || {})
  const [loading, setLoading] = useState(_cache == null)

  useEffect(() => {
    _subscribers.add(setCoupons)
    if (_cache == null) _load().then(() => setLoading(false))
    else setLoading(false)
    return () => { _subscribers.delete(setCoupons) }
  }, [])

  const couponFor = useCallback(
    (carrier) => (carrier && coupons[carrier]) || null,
    [coupons]
  )

  return { coupons, couponFor, loading }
}
