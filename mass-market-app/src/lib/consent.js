// Cookie / tracking consent (2026-09-11).
//
// Israel has no standalone cookie law, but the Privacy Protection Authority's
// position is that NON-essential cookies and tracking pixels need active opt-in
// consent. MOCA's public pages set no third-party cookies by themselves; the
// only optional tracker is the TikTok pixel on /esim-deals, which is now loaded
// ONLY after the visitor accepts "marketing" here. First-party essentials
// (language, session token, alert settings, auth cookie) never need consent.
//
// Storage: localStorage key `moca_consent` = { v, marketing, analytics, ts }.
// `v` is the policy version the visitor answered to; bumping CONSENT_VERSION
// re-asks everyone (do that when the cookie policy materially changes).
//
// The consent record lives only in the visitor's browser - it is never sent to
// the server (nothing to reconcile, nothing to leak).

export const CONSENT_VERSION = '2026-09-11'
const KEY = 'moca_consent'
const listeners = new Set()

export function readConsent() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const c = JSON.parse(raw)
    if (!c || c.v !== CONSENT_VERSION) return null
    return c
  } catch {
    return null
  }
}

export function saveConsent({ marketing = false, analytics = true } = {}) {
  const c = { v: CONSENT_VERSION, marketing: !!marketing, analytics: !!analytics, ts: Date.now() }
  try { localStorage.setItem(KEY, JSON.stringify(c)) } catch { /* private mode etc. */ }
  listeners.forEach((fn) => { try { fn(c) } catch { /* ignore */ } })
  return c
}

export function clearConsent() {
  try { localStorage.removeItem(KEY) } catch { /* ignore */ }
  listeners.forEach((fn) => { try { fn(null) } catch { /* ignore */ } })
}

/** True only when the visitor explicitly accepted marketing trackers. */
export function hasMarketingConsent() {
  return !!readConsent()?.marketing
}

/** Subscribe to consent changes (returns an unsubscribe fn). */
export function onConsentChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
