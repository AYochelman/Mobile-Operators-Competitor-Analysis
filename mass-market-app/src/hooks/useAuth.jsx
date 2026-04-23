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

export function AuthProvider({ children }) {
  const [user, setUser]         = useState(null)
  const [role, setRole]         = useState(null)
  const [workspace, setWorkspace] = useState(null)
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    if (DEV_MODE) {
      setUser({ email: 'alon.yoch@gmail.com', id: 'dev' })
      setRole('super_admin')
      setWorkspace(DEFAULT_WORKSPACE)
      setLoading(false)
      return
    }
    if (!supabase) { setLoading(false); return }

    const applyContext = async (session) => {
      setUser(session.user)
      localStorage.setItem('auth_token', session.access_token)
      api.setSessionCookie(session.access_token).catch(() => {})
      const ctx = await fetchContextFromBackend(session.access_token, session.user.email)
      setRole(ctx.role)
      setWorkspace(ctx.workspace)
    }

    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (session?.user) {
        let activeSession = session
        if (!session.expires_at || Date.now() / 1000 > session.expires_at - 60) {
          const { data: refreshed } = await supabase.auth.refreshSession()
          if (refreshed?.session) activeSession = refreshed.session
        }
        await applyContext(activeSession)
      }
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (session?.user) {
          await applyContext(session)
        } else {
          setUser(null)
          setRole(null)
          setWorkspace(null)
          localStorage.removeItem('auth_token')
          api.clearSessionCookie().catch(() => {})
        }
        setLoading(false)
      }
    )

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
    localStorage.removeItem('auth_token')
    api.clearSessionCookie().catch(() => {})
  }

  const value = {
    user, role, workspace, loading, signIn, signOut,
    isAdmin:      role === 'admin' || role === 'super_admin',
    isSuperAdmin: role === 'super_admin',
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
