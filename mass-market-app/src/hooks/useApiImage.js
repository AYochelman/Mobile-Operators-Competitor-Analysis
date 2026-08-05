import { useEffect, useState } from 'react'
import { API_BASE } from '../lib/api'

/**
 * Load an API-served image (banner screenshots under /banners/...) as a blob
 * object-URL instead of a plain <img src>.
 *
 * Why: with the ngrok-free ingress, any browser-looking request WITHOUT the
 * ngrok-skip-browser-warning header gets ngrok's HTML interstitial instead of
 * the file - and <img> tags cannot send custom headers, so every banner
 * screenshot silently "failed" into its gradient fallback (2026-08-05).
 * fetch() CAN send the header, so we fetch the blob and hand the component a
 * local object URL. Harmless in dev (same-origin Vite proxy) and under a
 * Cloudflare ingress (the header is simply ignored).
 *
 * Returns { src, error }: src is null while loading; error flips true on any
 * network failure or when an HTML (interstitial) response sneaks through -
 * callers keep their existing fallback rendering for both states. A result is
 * only surfaced when it belongs to the CURRENT path (compared at render time),
 * so switching banners never shows the previous banner's image or error.
 */
export function useApiImage(path) {
  const [loaded, setLoaded] = useState({ path: null, src: null, error: false })

  useEffect(() => {
    if (!path) return undefined
    let alive = true
    let objectUrl = null
    fetch(`${API_BASE}${path}`, { headers: { 'ngrok-skip-browser-warning': 'true' } })
      .then((r) => {
        const ct = r.headers.get('content-type') || ''
        if (!r.ok || ct.includes('text/html')) throw new Error(`bad image response (${r.status} ${ct})`)
        return r.blob()
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        if (alive) setLoaded({ path, src: objectUrl, error: false })
      })
      .catch(() => { if (alive) setLoaded({ path, src: null, error: true }) })
    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [path])

  if (!path || loaded.path !== path) return { src: null, error: false }
  return { src: loaded.src, error: loaded.error }
}
