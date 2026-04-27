import { createContext, useContext, useState, useRef, useCallback } from 'react'
import { api } from '../lib/api'

const ScrapeContext = createContext(null)

export function ScrapeProvider({ children }) {
  const [scraping, setScraping]   = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [toast, setToast]         = useState(null)
  const [progress, setProgress]   = useState([])
  const timerRef   = useRef(null)
  const pollRef    = useRef(null)
  const dismissRef = useRef(null)

  const _clearTimers = () => {
    if (timerRef.current)   clearInterval(timerRef.current)
    if (pollRef.current)    clearInterval(pollRef.current)
    if (dismissRef.current) clearTimeout(dismissRef.current)
  }

  // Poll /api/scrape-progress/state every 2s via fetchApi (handles auth correctly).
  // SSE via EventSource was unusable: no custom-header support meant the JWT
  // (kept in localStorage by Supabase) was never forwarded → 401 on every connect.
  // Fetch-streaming failed for the same reason when auth_token wasn't set, and
  // is also buffered by ngrok. Polling avoids all of these issues.
  const _startPolling = () => {
    let seenIdx = 0
    pollRef.current = setInterval(async () => {
      try {
        const data = await api.scrapeProgress()
        const log = data.log || []
        if (log.length > seenIdx) {
          const newEvents = log.slice(seenIdx)
          seenIdx = log.length
          setProgress(prev => [...prev, ...newEvents])
        }
      } catch {}
    }, 2000)
  }

  const triggerScrape = useCallback(async () => {
    if (scraping) return
    _clearTimers()
    setScraping(true)
    setCountdown(12 * 60)
    setToast(null)
    setProgress([])
    _startPolling()

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
