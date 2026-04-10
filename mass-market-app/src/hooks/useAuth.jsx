import { useState, useEffect, createContext, useContext } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext(null)

// Dev mode: only when explicitly enabled via env var
const DEV_MODE = import.meta.env.VITE_DEV_AUTH === 'true'
const API_BASE = import.meta.env.VITE_API_URL || ''

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [role, setRole] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (DEV_MODE) {
      // Local dev only — explicit opt-in via VITE_DEV_AUTH=true
      setUser({ email: 'alon.yoch@gmail.com', id: 'dev' })
      setRole('admin')
      setLoading(false)
      return
    }
    if (!supabase) {
      // Supabase not configured — stay logged out (no admin fallback)
      setLoading(false)
      return
    }

    // Production: fetch role from Flask backend (bypasses Supabase RLS)
    const fetchRole = async (accessToken) => {
      try {
        const res = await fetch(`${API_BASE}/api/my-role`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'ngrok-skip-browser-warning': 'true',
          }
        })
        const data = await res.json()
        return data?.role || 'viewer'
      } catch {
        return 'viewer'
      }
    }

    // Check localStorage first (sync, no network needed)
    const stored = JSON.parse(localStorage.getItem('sb-gmfefvjdmgzluwffzrzj-auth-token') || 'null')
    if (!stored?.access_token) {
      // No stored session — show login immediately, skip Supabase entirely
      setLoading(false)
      // Still listen for future sign-ins
      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        async (_event, session) => {
          if (session?.user) {
            localStorage.setItem('auth_token', session.access_token)
            setUser(session.user)
            setRole(await fetchRole(session.access_token))
          } else {
            localStorage.removeItem('auth_token')
            setUser(null)
            setRole(null)
          }
          setLoading(false)
        }
      )
      return () => subscription.unsubscribe()
    }

    // Has stored token — let Supabase validate it
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        if (session?.user) {
          localStorage.setItem('auth_token', session.access_token)
          setUser(session.user)
          setRole(await fetchRole(session.access_token))
        } else {
          localStorage.removeItem('auth_token')
          setUser(null)
          setRole(null)
        }
        setLoading(false)
      }
    )
    // Fallback: if Supabase doesn't fire within 3s, show login
    const timeout = setTimeout(() => setLoading(false), 3000)
    return () => { clearTimeout(timeout); subscription.unsubscribe() }
  }, [])

  const signIn = async (email, password) => {
    if (DEV_MODE) return
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signOut = async () => {
    if (!DEV_MODE && supabase) {
      await supabase.auth.signOut()
    }
    setUser(null)
    setRole(null)
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
