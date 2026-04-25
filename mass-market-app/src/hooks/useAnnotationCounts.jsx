import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api'
import { useAuth } from './useAuth'

const AnnotationCountsContext = createContext(null)

export function AnnotationCountsProvider({ children }) {
  const { user } = useAuth()
  const [counts, setCounts] = useState({})

  const reload = useCallback(async () => {
    if (!user) { setCounts({}); return }
    try {
      const data = await api.getAnnotationCounts()
      setCounts(data || {})
    } catch {
      setCounts({})
    }
  }, [user])

  useEffect(() => { reload() }, [reload])

  const countFor = (carrier, planType, planName) =>
    counts[`${carrier}|${planType}|${planName}`] || 0

  return (
    <AnnotationCountsContext.Provider value={{ counts, countFor, reload }}>
      {children}
    </AnnotationCountsContext.Provider>
  )
}

export function useAnnotationCounts() {
  const ctx = useContext(AnnotationCountsContext)
  if (!ctx) throw new Error('useAnnotationCounts must be used within AnnotationCountsProvider')
  return ctx
}
