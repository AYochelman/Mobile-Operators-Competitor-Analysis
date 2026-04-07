import { useState, useEffect, useRef } from 'react'
import Button from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'

export default function SettingsPage() {
  const { isAdmin } = useAuth()
  const [scraping, setScraping] = useState(false)
  const [result, setResult] = useState(null)
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef(null)

  if (!isAdmin) return <div className="p-8 text-center text-gray-400">אין גישה</div>

  const SCRAPE_DURATION = 5 * 60 // 5 minutes in seconds

  const startCountdown = () => {
    setCountdown(SCRAPE_DURATION)
    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const handleScrape = async () => {
    setScraping(true)
    setResult(null)
    startCountdown()
    try {
      const res = await api.scrapeAll()
      setResult(res)
    } catch (err) {
      setResult({ error: err.message })
    }
    setScraping(false)
    setCountdown(0)
    if (timerRef.current) clearInterval(timerRef.current)
  }

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      <h1 className="text-xl font-bold">⚙️ הגדרות מערכת</h1>

      {/* Scrape controls */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-bold text-sm mb-3">🔄 סקרייפרים</h2>
        <p className="text-xs text-gray-400 mb-4">עדכון כל הנתונים אורך כ-5 דקות</p>

        <div className="flex items-center gap-3">
          <Button onClick={handleScrape} disabled={scraping}>
            {scraping ? '⏳ מעדכן...' : '🔄 עדכן את כל הנתונים'}
          </Button>

          {scraping && countdown > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-2xl font-mono font-bold text-blue-600">{formatTime(countdown)}</span>
              <span className="text-xs text-gray-400">נותרו</span>
            </div>
          )}
        </div>

        {result && (
          <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm">
            {result.error ? (
              <p className="text-red-600">❌ {result.error}</p>
            ) : (
              <p className="text-green-600">✅ עדכון הסתיים — {result.total_plans || '?'} חבילות, {result.total_changes || 0} שינויים</p>
            )}
          </div>
        )}
      </div>

      {/* Schedule info */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-bold text-sm mb-3">⏰ תזמון</h2>
        <div className="text-sm text-gray-600 space-y-1">
          <p>• סקרייפ אוטומטי: <strong>10:00</strong> ו-<strong>16:00</strong></p>
          <p>• דוח Excel יומי: <strong>09:00</strong></p>
          <p>• התראות: Telegram + Web Push בלבד על שינויים</p>
        </div>
      </div>

      {/* Users */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-bold text-sm mb-3">👥 משתמשים</h2>
        <p className="text-sm text-gray-400">ניהול משתמשים — בקרוב</p>
      </div>
    </div>
  )
}
