import { createContext, useContext, useState, useRef, useCallback } from 'react'
import { api, API_BASE } from '../lib/api'

const ScrapeContext = createContext(null)

const _DEV_API_KEY = import.meta.env.VITE_DEV_API_KEY || ''

export function ScrapeProvider({ children }) {
  const [scraping, setScraping]   = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [toast, setToast]         = useState(null) // { type: 'success'|'error', message, detail }
  const [progress, setProgress]   = useState([])   // array of {at, stage, status, count, message}
  const timerRef    = useRef(null)
  const dismissRef  = useRef(null)
  const sseRef      = useRef(null)  // AbortController for fetch-based SSE

  const _closeSse = () => {
    if (sseRef.current) { sseRef.current.abort(); sseRef.current = null }
  }

  // EventSource doesn't support custom headers, so JWT (stored in localStorage)
  // can't be sent — the server returns 401 and no events arrive.
  // Use fetch streaming instead so we can attach Authorization + API key headers.
  const _openSse = (onEvent) => {
    _closeSse()
    const controller = new AbortController()
    sseRef.current = controller
    const headers = { 'ngrok-skip-browser-warning': 'true' }
    const token = localStorage.getItem('auth_token')
    if (token) headers['Authorization'] = `Bearer ${token}`
    if (_DEV_API_KEY) headers['X-API-Key'] = _DEV_API_KEY

    fetch(`${API_BASE}/api/scrape-progress/stream`, {
      headers,
      credentials: 'include',
      signal: controller.signal,
    }).then(res => {
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      function pump() {
        return reader.read().then(({ done, value }) => {
          if (done) return
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const ev = JSON.parse(line.slice(6))
              if (ev.stage === '__done__' || ev.stage === '__timeout__' || ev.stage === '__idle__') {
                controller.abort(); return
              }
              onEvent(ev)
            } catch {}
          }
          return pump()
        }).catch(() => {})
      }
      return pump()
    }).catch(() => {})
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
    _openSse(ev => setProgress(prev => [...prev, ev]))

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
