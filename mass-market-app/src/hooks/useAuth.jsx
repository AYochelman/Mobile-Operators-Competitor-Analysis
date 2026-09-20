import { useState, useEffect, createContext, useContext } from 'react'
import { supabase } from '../lib/supabase'
import { api } from '../lib/api'

const AuthContext = createContext(null)

const DEV_MODE = import.meta.env.VITE_DEV_AUTH === 'true'
const API_BASE  = import.meta.env.VITE_API_URL || ''

const ADMIN_EMAILS = ['alon.yoch@gmail.com']

// Default workspace returned when backend is unreachable or for dev mode.
// Matches the 'moca-internal' workspace seeded by migration 001.
const DEFAULT_WORKSPACE = {
  slug: 'moca-internal',
  name: 'MOCA Internal',
  mvno_carrier: null,
  brand_config: {},
  feature_flags: {},
  hide_self_carrier: false,
  active: true,
}

/**
 * Resolve the signed-in user's role + workspace from the backend.
 *
 * Always returns a usable context so the app keeps working, but ALSO reports
 * whether that context is authoritative. Four different situations used to
 * collapse into a bare `role: 'viewer'` that the UI could not tell apart from
 * a real viewer account — so a dead Flask / tunnel silently stripped the admin
 * menus and looked like a permissions change:
 *   1. the request failed (offline, tunnel down, CORS, 5xx)
 *   2. it timed out
 *   3. it returned 200 with no `role` field
 *   4. the backend answered `viewer` because the JWT carried no identity
 *      (api/account.py returns `reason: no_jwt | no_email` for those)
 * `degraded` marks 1-4; only a clean answer with a real role is authoritative.
 */
async function fetchContextFromBackend(accessToken, userEmail) {
  let res
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    try {
      res = await fetch(`${API_BASE}/api/my-context`, {
        signal: controller.signal,
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'ngrok-skip-browser-warning': 'true',
        },
      })
    } finally {
      clearTimeout(timeout)
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    // 200 but the server could not identify the caller, or sent no role at all.
    const serverReason = data?.reason || (data?.role ? null : 'no_role_in_response')
    return {
      role: data?.role || 'viewer',
      workspaceId: data?.workspace_id || null,
      workspace: data?.workspace || null,
      degraded: serverReason ? { reason: serverReason, status: res.status } : null,
    }
  } catch (err) {
    // Backend unreachable — keep the app usable, but say so out loud.
    // The local email shortcut still grants admin so the operator is not locked
    // out of their own tooling while the tunnel is down.
    const fallbackRole = (userEmail && ADMIN_EMAILS.includes(userEmail.toLowerCase()))
      ? 'admin' : 'viewer'
    const reason = err?.name === 'AbortError' ? 'timeout'
      : /^HTTP /.test(err?.message || '') ? err.message.toLowerCase().replace(' ', '_')
      : 'unreachable'
    return {
      role: fallbackRole,
      workspaceId: null,
      workspace: DEFAULT_WORKSPACE,
      degraded: { reason, status: res?.status ?? null, fallbackRole },
    }
  }
}

const VIEW_AS_STORAGE_KEY = 'moca_view_as_workspace'

export function AuthProvider({ children }) {
  const [user, setUser]           = useState(null)
  const [role, setRole]           = useState(null)
  const [workspace, setWorkspace] = useState(null)
  const [workspaceId, setWorkspaceId] = useState(null)
  const [loading, setLoading]     = useState(true)
  // Non-null when the role on screen is a fallback rather than the server's
  // answer — drives <AuthDegradedBanner> so missing menus are explained.
  const [contextDegraded, setContextDegraded] = useState(null)
  const [viewAs, setViewAs]       = useState(() => {
    try {
      const raw = sessionStorage.getItem(VIEW_AS_STORAGE_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })

  const enterViewAs = (ws) => {
    try { sessionStorage.setItem(VIEW_AS_STORAGE_KEY, JSON.stringify(ws)) } catch {}
    setViewAs(ws)
  }
  const exitViewAs = () => {
    try { sessionStorage.removeItem(VIEW_AS_STORAGE_KEY) } catch {}
    setViewAs(null)
  }

  useEffect(() => {
    if (!supabase) {
      if (DEV_MODE) {
        setUser({ email: 'alon.yoch@gmail.com', id: 'dev' })
        setRole('super_admin')
        setWorkspace(DEFAULT_WORKSPACE)
        setContextDegraded(null)
      }
      setLoading(false)
      return
    }

    // Non-blocking: sets user synchronously, loads role/workspace in the
    // background. Any long await inside onAuthStateChange can stall
    // signInWithPassword from resolving (Supabase v2 internal lock).
    const applyContext = (session) => {
      setUser(session.user)
      localStorage.setItem('auth_token', session.access_token)
      api.setSessionCookie(session.access_token).catch(() => {})
      fetchContextFromBackend(session.access_token, session.user.email)
        .then(ctx => {
          setRole(ctx.role); setWorkspace(ctx.workspace); setWorkspaceId(ctx.workspaceId)
          setContextDegraded(ctx.degraded || null)
        })
        .catch((err) => {
          // fetchContextFromBackend handles its own errors; this only fires on a
          // bug in the .then above. Never silently pretend the user is a viewer.
          setRole('viewer'); setWorkspace(DEFAULT_WORKSPACE); setWorkspaceId(null)
          setContextDegraded({ reason: 'client_error', status: null, detail: err?.message })
        })
    }

    // Supabase v2 auto-refreshes tokens in the background and fires
    // onAuthStateChange with fresh sessions — no manual refresh needed.
    // Always subscribe so real sign-ins work even when DEV_MODE is on.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (session?.user) {
          sessionStorage.removeItem('dev_logged_out')
          applyContext(session)
          setLoading(false)
          // Best-effort login beacon — only on a real sign-in (not token refresh
          // / session restore), deduped per browser session so opening tabs or
          // refreshing doesn't inflate the count. Super-admin logins are dropped
          // server-side. (RouteTracker records page views separately.)
          if (event === 'SIGNED_IN') {
            try {
              const uid = session.user.id
              if (sessionStorage.getItem('moca_login_beaconed') !== uid) {
                sessionStorage.setItem('moca_login_beaconed', uid)
                api.trackActivity('login').catch(() => {})
              }
            } catch { /* ignore */ }
          }
        } else if (DEV_MODE && !sessionStorage.getItem('dev_logged_out')) {
          // DEV_MODE: Supabase fires INITIAL_SESSION with a null session on every
          // load (there's no real session). Re-assert the dev super_admin rather
          // than clobbering the user getSession() installs — otherwise a hard
          // reload of any gated route momentarily sees user=null and bounces to
          // /login → /home. Only a real sign-out (dev_logged_out) clears it.
          setUser({ email: 'alon.yoch@gmail.com', id: 'dev' })
          setRole('super_admin')
          setWorkspace(DEFAULT_WORKSPACE)
          setLoading(false)
        } else {
          setUser(null)
          setRole(null)
          setWorkspace(null)
          setWorkspaceId(null)
          setContextDegraded(null)
          localStorage.removeItem('auth_token')
          try { sessionStorage.removeItem('moca_login_beaconed') } catch { /* ignore */ }
          api.clearSessionCookie().catch(() => {})
          setLoading(false)
        }
      }
    )

    // Kick off initial session check. A timeout guard guarantees `loading`
    // flips to false even if getSession() hangs for any reason — without
    // this, the app gets stuck on the spinner and the user can never log in.
    const bootTimeout = setTimeout(() => setLoading(false), 3000)
    supabase.auth.getSession().then(({ data: { session } }) => {
      clearTimeout(bootTimeout)
      if (session?.user) {
        applyContext(session)
      } else if (DEV_MODE && !sessionStorage.getItem('dev_logged_out')) {
        setUser({ email: 'alon.yoch@gmail.com', id: 'dev' })
        setRole('super_admin')
        setWorkspace(DEFAULT_WORKSPACE)
      }
      setLoading(false)
    }).catch(() => {
      clearTimeout(bootTimeout)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email, password) => {
    // DEV_MODE previously short-circuited here — but then the login form would
    // appear to do nothing with no error. Always hit Supabase so real users
    // (e.g. a Partner pilot tester) can authenticate even when the local env
    // has VITE_DEV_AUTH=true for the developer's own convenience.
    if (!supabase) throw new Error('Supabase not configured')
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signOut = async () => {
    if (supabase) await supabase.auth.signOut().catch(() => {})
    setUser(null)
    setRole(null)
    setWorkspace(null)
    setViewAs(null)
    try { sessionStorage.removeItem(VIEW_AS_STORAGE_KEY) } catch {}
    try { sessionStorage.removeItem('moca_login_beaconed') } catch {}
    localStorage.removeItem('auth_token')
    // Remember explicit logout for the tab session so DEV_MODE doesn't auto-re-login.
    sessionStorage.setItem('dev_logged_out', '1')
    api.clearSessionCookie().catch(() => {})
  }

  // Self-service password change for the logged-in user. Verifies the current
  // password first (re-auth) so an unattended logged-in browser can't have its
  // password silently changed, then updates via Supabase (no email).
  const changePassword = async (currentPassword, newPassword) => {
    if (!supabase) throw new Error('Supabase לא מוגדר')
    const email = user?.email
    if (!email) throw new Error('לא מחובר')
    const { error: verifyErr } = await supabase.auth.signInWithPassword({ email, password: currentPassword })
    if (verifyErr) throw new Error('הסיסמה הנוכחית שגויה')
    const { error } = await supabase.auth.updateUser({ password: newPassword })
    if (error) throw error
  }

  // "Forgot password": email the user a recovery link that lands on
  // /reset-password (where they set a new password). The only Supabase email
  // in the user lifecycle — user-initiated, unlike the confirmation email we
  // dropped from user creation.
  const sendPasswordReset = async (email) => {
    if (!supabase) throw new Error('Supabase לא מוגדר')
    const redirectTo = `${window.location.origin}/reset-password`
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo })
    if (error) throw error
  }

  /**
   * Re-resolve role + workspace from the backend. Exposed so the degraded
   * banner can offer "נסו שוב" instead of making the user sign out and back
   * in just to pick up a role the server failed to return the first time.
   */
  const retryContext = async () => {
    if (!supabase) return
    const { data: { session } } = await supabase.auth.getSession()
    if (!session?.user) return
    const ctx = await fetchContextFromBackend(session.access_token, session.user.email)
    setRole(ctx.role)
    setWorkspace(ctx.workspace)
    setWorkspaceId(ctx.workspaceId)
    setContextDegraded(ctx.degraded || null)
  }

  // View-as: super_admin may impersonate a workspace's visual context
  // (brand, feature_flags, visible_carriers). Role stays super_admin so they
  // can still navigate admin pages and exit view-as at any time.
  const isSuperAdmin = role === 'super_admin'
  const effectiveWorkspace = (isSuperAdmin && viewAs) ? viewAs : workspace

  const value = {
    user, role, workspaceId, loading, signIn, signOut, changePassword, sendPasswordReset,
    contextDegraded, retryContext,
    workspace: effectiveWorkspace,
    realWorkspace: workspace,
    viewAs: (isSuperAdmin ? viewAs : null),
    enterViewAs, exitViewAs,
    isAdmin:      role === 'admin' || role === 'super_admin',
    isSuperAdmin,
  }
  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
