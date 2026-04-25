import { useState, useCallback } from 'react'
import { api } from '../lib/api'
import Modal from './ui/Modal'
import { ALL_CARRIER_LABELS as CARRIER_NAMES } from '../data/carrierLabels'

export default function CarrierAIInsights({ carrierId }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState(null)

  const carrierName = CARRIER_NAMES[carrierId] || carrierId

  const loadInsights = useCallback(async () => {
    setLoading(true)
    setError(null)
    setAnswer('')
    const prompt = `תן לי דוח תחרותי תמציתי וממוקד על ${carrierName}.

תוכן רצוי (בסדר הזה):
1. **מצב נוכחי** — מספר חבילות פעילות וטווחי מחירים (ביתי וחו"ל בנפרד)
2. **אסטרטגיה** — מה הספק מנסה לעשות? (תחרות במחיר, פרימיום, data-heavy, חו"ל וכד')
3. **שינויים אחרונים** — מה קרה בחבילות שלו לאחרונה (אם יש בנתונים)
4. **מול המתחרים** — שני משפטים על נקודות חוזק וחולשה ביחס לאחרים
5. **הזדמנויות** — 1-3 פעולות שהמתחרים יכולים לנצל

דרישות איכות (חובה):
- כתוב בעברית תקנית בלבד. אל תמציא מילים. אל תתרגם ישירות מאנגלית — אם אתה לא בטוח במונח, השתמש בעברית פשוטה או השאר באנגלית.
- בדוק כל משפט לפני שאתה כותב אותו. אם משהו נשמע מוזר — נסח מחדש.
- השתמש במונחי הענף הנכונים: "חבילת גלישה", "דקות שיחה", "הודעות SMS", "גלישה בחו\\"ל".
- אורך כולל: עד 220 מילים.
- פורמט: כותרות מודגשות (## כותרת), נקודות קצרות תחת כל כותרת.`
    try {
      // Explicitly request Sonnet for higher Hebrew quality
      const res = await api.chat(prompt, 'sonnet')
      setAnswer(res?.answer || res?.response || res?.text || JSON.stringify(res))
    } catch (e) {
      setError(e.message || 'שגיאה בטעינת הסיכום')
    } finally {
      setLoading(false)
    }
  }, [carrierName])

  const handleOpen = () => {
    setOpen(true)
    if (!answer && !loading) loadInsights()
  }

  return (
    <>
      <button
        onClick={handleOpen}
        title={`דוח AI תחרותי על ${carrierName}`}
        className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-purple-200 bg-gradient-to-l from-purple-50 to-white text-purple-700 hover:from-purple-100 transition-all font-medium"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
        דוח AI על {carrierName}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={`דוח תחרותי — ${carrierName}`} maxWidth="max-w-2xl">
        <div className="text-right">
          {loading && (
            <div className="flex flex-col items-center py-12 gap-3">
              <div className="animate-spin h-8 w-8 border-4 border-purple-500 border-t-transparent rounded-full" />
              <p className="text-xs text-gray-500">Claude מנתח את הנתונים...</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
              {error}
              <button onClick={loadInsights} className="block mt-2 text-xs text-red-600 underline">נסה שוב</button>
            </div>
          )}

          {!loading && !error && answer && (
            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
              {answer}
              <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
                <button
                  onClick={loadInsights}
                  className="text-xs text-purple-600 hover:text-purple-800 transition-colors flex items-center gap-1"
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                  </svg>
                  רענן דוח
                </button>
                <span className="text-[10px] text-gray-400">נוצר על ידי Claude · {new Date().toLocaleString('he-IL')}</span>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </>
  )
}
