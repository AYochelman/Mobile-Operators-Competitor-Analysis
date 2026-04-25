import { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import { useAnnotationCounts } from '../hooks/useAnnotationCounts'
import Modal from './ui/Modal'

export default function AnnotationsModal({ open, onClose, carrier, planName, planType, planLabel }) {
  const { user } = useAuth()
  const { reload: reloadCounts } = useAnnotationCounts()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [draft, setDraft] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editText, setEditText] = useState('')

  const load = useCallback(async () => {
    if (!open || !carrier || !planName) return
    setLoading(true)
    try {
      const data = await api.getAnnotations(carrier, planName, planType)
      setItems(data || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [open, carrier, planName, planType])

  useEffect(() => { load() }, [load])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    try {
      await api.addAnnotation({ carrier, plan_name: planName, plan_type: planType, note: text })
      setDraft('')
      await load()
      reloadCounts()
    } catch (err) {
      alert(err.message || 'שגיאה בהוספת הערה')
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('למחוק הערה זו?')) return
    try {
      await api.deleteAnnotation(id)
      await load()
      reloadCounts()
    } catch (err) {
      alert(err.message || 'שגיאה במחיקה')
    }
  }

  const startEdit = (a) => {
    setEditingId(a.id)
    setEditText(a.note)
  }

  const handleEditSave = async (id) => {
    const text = editText.trim()
    if (!text) return
    try {
      await api.updateAnnotation(id, text)
      setEditingId(null)
      await load()
    } catch (err) {
      alert(err.message || 'שגיאה בעדכון')
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`הערות צוות — ${planLabel || planName}`} maxWidth="max-w-lg">
      <div className="text-right space-y-3">
        {loading && (
          <p className="text-xs text-gray-400 text-center py-4">טוען הערות...</p>
        )}

        {!loading && items.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">אין הערות עדיין. הוסף הערה ראשונה למטה.</p>
        )}

        {!loading && items.length > 0 && (
          <ul className="space-y-2 max-h-80 overflow-y-auto pr-1">
            {items.map(a => (
              <li key={a.id} className="bg-moca-cream/40 border border-moca-border/40 rounded-lg p-3">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="text-[11px] text-gray-500">
                    <strong className="text-gray-700">{a.user_email}</strong>
                    <span className="mx-1.5 text-gray-300">·</span>
                    {new Date(a.created_at).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' })}
                    {a.updated_at && <span className="mr-1 text-gray-400">(עודכן)</span>}
                  </div>
                  {a.user_email === user?.email && editingId !== a.id && (
                    <div className="flex items-center gap-1.5 text-[10px]">
                      <button onClick={() => startEdit(a)} className="text-blue-500 hover:text-blue-700">ערוך</button>
                      <button onClick={() => handleDelete(a.id)} className="text-red-500 hover:text-red-700">מחק</button>
                    </div>
                  )}
                </div>
                {editingId === a.id ? (
                  <div>
                    <textarea
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      className="w-full text-sm text-gray-700 bg-white border border-moca-border/60 rounded p-2 focus:outline-none focus:border-moca-bolt resize-none"
                      rows={3}
                      maxLength={1000}
                    />
                    <div className="flex items-center gap-2 mt-1">
                      <button onClick={() => handleEditSave(a.id)} className="text-[11px] bg-moca-bolt text-white px-2 py-1 rounded hover:bg-moca-dark">שמור</button>
                      <button onClick={() => setEditingId(null)} className="text-[11px] text-gray-500 hover:text-gray-700">בטל</button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{a.note}</p>
                )}
              </li>
            ))}
          </ul>
        )}

        <form onSubmit={handleSubmit} className="border-t border-gray-100 pt-3 mt-3">
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            placeholder="הוסף הערה לצוות..."
            className="w-full text-sm bg-white border border-moca-border/60 rounded-lg p-2.5 focus:outline-none focus:border-moca-bolt resize-none"
            rows={3}
            maxLength={1000}
          />
          <div className="flex items-center justify-between mt-1.5">
            <span className="text-[10px] text-gray-400">{draft.length}/1000 · גלוי לכל הצוות שלך</span>
            <button
              type="submit"
              disabled={!draft.trim()}
              className="text-xs bg-moca-bolt text-white px-3 py-1.5 rounded-lg hover:bg-moca-dark disabled:opacity-40 disabled:cursor-not-allowed"
            >
              הוסף הערה
            </button>
          </div>
        </form>
      </div>
    </Modal>
  )
}
