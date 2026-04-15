import { createContext, useContext, useState, useRef, useCallback } from 'react'
import { api } from '../lib/api'

const ScrapeContext = createContext(null)

export function ScrapeProvider({ children }) {
  const [scraping, setScraping]   = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [toast, setToast]         = useState(null) // { type: 'success'|'error', message, detail }
  const timerRef    = useRef(null)
  const dismissRef  = useRef(null)

  const _clearTimers = () => {
    if (timerRef.current)   clearInterval(timerRef.current)
    if (dismissRef.current) clearTimeout(dismissRef.current)
  }

  const triggerScrape = useCallback(async () => {
    if (scraping) return
    _clearTimers()
    setScraping(true)
    setCountdown(12 * 60)
    setToast(null)

    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { clearInterval(timerRef.current); return 0 }
        return prev - 1
      })
    }, 1000)

    try {
      const res = await api.scrapeAll()
      _clearTimers()
      setScraping(false)
      setCountdown(0)
      const total   = res.total_plans   ?? '—'
      const changes = res.total_changes ?? 0
      setToast({
        type: 'success',
        message: 'הנתונים עודכנו בהצלחה',
        detail: `${total} תכניות · ${changes} שינויים`,
      })
      dismissRef.current = setTimeout(() => setToast(null), 8000)
    } catch (err) {
      _clearTimers()
      setScraping(false)
      setCountdown(0)
      setToast({ type: 'error', message: 'שגיאה בעדכון הנתונים', detail: err.message })
      dismissRef.current = setTimeout(() => setToast(null), 8000)
    }
  }, [scraping])

  const dismissToast = useCallback(() => {
    if (dismissRef.current) clearTimeout(dismissRef.current)
    setToast(null)
  }, [])

  return (
    <ScrapeContext.Provider value={{ scraping, countdown, toast, triggerScrape, dismissToast }}>
      {children}
    </ScrapeContext.Provider>
  )
}

export function useScrape() {
  const ctx = useContext(ScrapeContext)
  if (!ctx) throw new Error('useScrape must be used inside ScrapeProvider')
  return ctx
}
