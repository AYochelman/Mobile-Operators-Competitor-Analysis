import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'

/**
 * Fires a best-effort `page_view` beacon on each authenticated route change,
 * powering the super-admin user-activity dashboard. Mounted inside <Layout>,
 * so it only runs for logged-in users (never the public landing / login pages).
 * Super-admins (the operator) are skipped — their own navigation isn't recorded
 * (the backend drops it too, this just avoids needless requests). Renders null.
 */
export default function RouteTracker() {
  const { pathname } = useLocation()
  const { user, isSuperAdmin } = useAuth()
  const lastPath = useRef(null)

  useEffect(() => {
    if (!user || isSuperAdmin) return
    if (lastPath.current === pathname) return  // dedupe consecutive same-path views
    lastPath.current = pathname
    api.trackActivity('page_view', pathname).catch(() => {})
  }, [pathname, user, isSuperAdmin])

  return null
}
