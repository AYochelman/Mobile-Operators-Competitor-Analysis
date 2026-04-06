import { useState } from 'react'
import Button from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'

export default function SettingsPage() {
  const { isAdmin } = useAuth()
  const [scraping, setScraping] = useState(false)
  const [result, setResult] = useState(null)

  if (!isAdmin) return <div className="p-8 text-center text-gray-400">אין גישה</div>

  const handleScrape = async (type) => {
    setScraping(true)
    setResult(null)
    try {
      const res = await api.scrapeAll()
      setResult(res)
    } catch (err) {
      setResult({ error: err.message })
    }
    setScraping(false)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      <h1 className="text-xl font-bold">⚙️ הגדרות מערכת</h1>

      {/* Scrape controls */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-bold text-sm mb-3">🔄 סקרייפרים</h2>
        <p className="text-xs text-gray-400 mb-4">עדכון כל הנתונים אורך כ-4 דקות</p>
        <Button onClick={handleScrape} disabled={scraping}>
          {scraping ? '⏳ מעדכן...' : '🔄 עדכן את כל הנתונים'}
        </Button>
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
