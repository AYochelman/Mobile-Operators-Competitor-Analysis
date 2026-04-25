import { createContext, useContext, useState, useRef, useCallback } from 'react'
import { api, API_BASE } from '../lib/api'

const ScrapeContext = createContext(null)

export function ScrapeProvider({ children }) {
  const [scraping, setScraping]   = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [toast, setToast]         = useState(null) // { type: 'success'|'error', message, detail }
  const [progress, setProgress]   = useState([])   // array of {at, stage, status, count, message}
  const timerRef    = useRef(null)
  const dismissRef  = useRef(null)
  const sseRef      = useRef(null)

  const _closeSse = () => {
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null }
  }

  const _openSse = () => {
    _closeSse()
    try {
      const es = new EventSource(`${API_BASE}/api/scrape-progress/stream`, { withCredentials: true })
      es.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data)
          if (ev.stage === '__done__' || ev.stage === '__timeout__' || ev.stage === '__idle__') {
            es.close(); return
          }
          setProgress(prev => [...prev, ev])
        } catch {}
      }
      es.onerror = () => { es.close() }
      sseRef.current = es
    } catch {}
  }

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
    setProgress([])
    _openSse()

    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { clearInterval(timerRef.current); return 0 }
        return prev - 1
      })
    }, 1000)

    try {
      const res = await api.scrapeAll()
      _clearTimers()
      _closeSse()
      setScraping(false)
      setCountdown(0)
      const total   = res.total_plans   ?? '—'
      const changes = res.total_changes ?? 0
      const quotaNote = res.quota_limit
        ? ` · רענונים החודש: ${res.quota_used}/${res.quota_limit}`
        : ''
      setToast({
        type: 'success',
        message: 'הנתונים עודכנו בהצלחה',
        detail: `${total} תכניות · ${changes} שינויים${quotaNote}`,
      })
      dismissRef.current = setTimeout(() => setToast(null), 8000)
    } catch (err) {
      _clearTimers()
      _closeSse()
      setScraping(false)
      setCountdown(0)
      const isQuota = err.message?.includes('מכסת')
      setToast({
        type: 'error',
        message: isQuota ? 'מכסת הרענון החודשית מוצתה' : 'שגיאה בעדכון הנתונים',
        detail: err.message,
      })
      dismissRef.current = setTimeout(() => setToast(null), isQuota ? 12000 : 8000)
    }
  }, [scraping])

  const dismissToast = useCallback(() => {
    if (dismissRef.current) clearTimeout(dismissRef.current)
    setToast(null)
  }, [])

  return (
    <ScrapeContext.Provider value={{ scraping, countdown, toast, progress, triggerScrape, dismissToast }}>
      {children}
    </ScrapeContext.Provider>
  )
}

export function useScrape() {
  const ctx = useContext(ScrapeContext)
  if (!ctx) throw new Error('useScrape must be used inside ScrapeProvider')
  return ctx
}
