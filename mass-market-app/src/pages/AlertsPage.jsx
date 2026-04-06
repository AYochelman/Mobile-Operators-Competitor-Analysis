import { useState } from 'react'
import Button from '../components/ui/Button'

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([])

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-4">🔔 התראות מחיר</h1>

      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center">
        <p className="text-4xl mb-3">🔔</p>
        <p className="text-gray-600 mb-4">הגדר התראות מחיר אישיות</p>
        <p className="text-sm text-gray-400 mb-4">קבל התראה כשמחיר חבילה יורד מתחת לסכום שתגדיר</p>
        <Button variant="primary">➕ הוספת התראה</Button>
      </div>

      {alerts.length > 0 && (
        <div className="mt-4 space-y-2">
          {alerts.map((a, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-4 flex justify-between items-center">
              <div>
                <p className="font-medium text-sm">{a.carrier} — {a.plan}</p>
                <p className="text-xs text-gray-400">הודע כשמחיר &lt; ₪{a.threshold}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setAlerts(prev => prev.filter((_, j) => j !== i))}>🗑️</Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
