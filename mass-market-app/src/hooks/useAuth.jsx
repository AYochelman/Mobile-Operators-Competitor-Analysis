import { useState, useEffect, createContext, useContext } from 'react'
import { supabase } from '../lib/supabase'
import { api } from '../lib/api'

const AuthContext = createContext(null)

const DEV_MODE = import.meta.env.VITE_DEV_AUTH === 'true'
const API_BASE  = import.meta.env.VITE_API_URL || ''

async function fetchRoleFromBackend(accessToken) {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    const res = await fetch(`${API_BASE}/api/my-role`, {
      signal: controller.signal,
      credentials: 'include',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'ngrok-skip-browser-warning': 'true',
      },
    })
    clearTimeout(timeout)
    const data = await res.json()
    return data?.role || 'viewer'
  } catch {
    return 'viewer'
  }
}

export function AuthProvider({ children }) {
  const [user, setUser]     = useState(null)
  const [role, setRole]     = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (DEV_MODE) {
      setUser({ email: 'alon.yoch@gmail.com', id: 'dev' })
      setRole('admin')
      setLoading(false)
      return
    }
    if (!supabase) { setLoading(false); return }

    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (session?.user) {
        let activeSession = session
        if (!session.expires_at || Date.now() / 1000 > session.expires_at - 60) {
          const { data: refreshed } = await supabase.auth.refreshSession()
          if (refreshed?.session) activeSession = refreshed.session
        }
        setUser(activeSession.user)
        localStorage.setItem('auth_token', activeSession.access_token)
        api.setSessionCookie(activeSession.access_token).catch(() => {})
        const r = await fetchRoleFromBackend(activeSession.access_token)
        setRole(r)
      }
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (session?.user) {
          setUser(session.user)
          localStorage.setItem('auth_token', session.access_token)
          api.setSessionCookie(session.access_token).catch(() => {})
          const r = await fetchRoleFromBackend(session.access_token)
          setRole(r)
        } else {
          setUser(null)
          setRole(null)
          localStorage.removeItem('auth_token')
          api.clearSessionCookie().catch(() => {})
        }
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email, password) => {
    if (DEV_MODE) return
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signOut = async () => {
    if (!DEV_MODE && supabase) await supabase.auth.signOut()
    setUser(null)
    setRole(null)
    localStorage.removeItem('auth_token')
    api.clearSessionCookie().catch(() => {})
  }

  return (
    <AuthContext.Provider value={{ user, role, loading, signIn, signOut, isAdmin: role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
