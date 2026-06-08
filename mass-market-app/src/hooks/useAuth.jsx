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

async function fetchContextFromBackend(accessToken, userEmail) {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    const res = await fetch(`${API_BASE}/api/my-context`, {
      signal: controller.signal,
      credentials: 'include',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'ngrok-skip-browser-warning': 'true',
      },
    })
    clearTimeout(timeout)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    return {
      role: data?.role || 'viewer',
      workspaceId: data?.workspace_id || null,
      workspace: data?.workspace || null,
    }
  } catch {
    // Backend unreachable — degrade gracefully.
    // Local email shortcut gives you admin access if network is down.
    const fallbackRole = (userEmail && ADMIN_EMAILS.includes(userEmail.toLowerCase()))
      ? 'admin' : 'viewer'
    return { role: fallbackRole, workspaceId: null, workspace: DEFAULT_WORKSPACE }
  }
}

const VIEW_AS_STORAGE_KEY = 'moca_view_as_workspace'

export function AuthProvider({ children }) {
  const [user, setUser]           = useState(null)
  const [role, setRole]           = useState(null)
  const [workspace, setWorkspace] = useState(null)
  const [workspaceId, setWorkspaceId] = useState(null)
  const [loading, setLoading]     = useState(true)
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
        .then(ctx => { setRole(ctx.role); setWorkspace(ctx.workspace); setWorkspaceId(ctx.workspaceId) })
        .catch(() => { setRole('viewer'); setWorkspace(DEFAULT_WORKSPACE); setWorkspaceId(null) })
    }

    // Supabase v2 auto-refreshes tokens in the background and fires
    // onAuthStateChange with fresh sessions — no manual refresh needed.
    // Always subscribe so real sign-ins work even when DEV_MODE is on.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (session?.user) {
          sessionStorage.removeItem('dev_logged_out')
          applyContext(session)
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
        } else {
          setUser(null)
          setRole(null)
          setWorkspace(null)
          setWorkspaceId(null)
          localStorage.removeItem('auth_token')
          try { sessionStorage.removeItem('moca_login_beaconed') } catch { /* ignore */ }
          api.clearSessionCookie().catch(() => {})
        }
        setLoading(false)
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

  // View-as: super_admin may impersonate a workspace's visual context
  // (brand, feature_flags, visible_carriers). Role stays super_admin so they
  // can still navigate admin pages and exit view-as at any time.
  const isSuperAdmin = role === 'super_admin'
  const effectiveWorkspace = (isSuperAdmin && viewAs) ? viewAs : workspace

  const value = {
    user, role, workspaceId, loading, signIn, signOut, changePassword, sendPasswordReset,
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
