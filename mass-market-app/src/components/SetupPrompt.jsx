import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'

// sessionStorage key: holds the id of the user whose setup status was already
// checked in this tab, so the check runs once per sign-in, not per navigation.
export const SETUP_CHECKED_KEY = 'moca_setup_checked'

/**
 * First-login prompt for the dashboard setup wizard. Renders nothing: once per
 * session it asks the server whether this user ever completed (or skipped) the
 * wizard, and if not, sends them to /setup?welcome=1. Super-admins are never
 * prompted, and a degraded auth context (role not verified) never triggers it.
 */
export default function SetupPrompt() {
  const { user, role, isSuperAdmin, contextDegraded } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    if (!user?.id || role == null || isSuperAdmin || contextDegraded) return
    if (pathname === '/setup') return
    try { if (sessionStorage.getItem(SETUP_CHECKED_KEY) === user.id) return } catch { /* ignore */ }
    let cancelled = false
    api.getDashboardSetup()
      .then(data => {
        if (cancelled) return
        try { sessionStorage.setItem(SETUP_CHECKED_KEY, user.id) } catch { /* ignore */ }
        if (!data?.user?.completed_at && !data?.user?.dismissed_at) {
          navigate('/setup?welcome=1', { replace: true })
        }
      })
      .catch(() => { /* backend unreachable: try again on the next navigation */ })
    return () => { cancelled = true }
    // pathname is deliberately not a dependency: one check per sign-in is enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, role, isSuperAdmin, contextDegraded])

  return null
}
