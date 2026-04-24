import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../lib/api'

export default function SavedViewsMenu({ tab, filters, onApply }) {
  const [views, setViews]       = useState([])
  const [open, setOpen]         = useState(false)
  const [naming, setNaming]     = useState(false)
  const [newName, setNewName]   = useState('')
  const [saving, setSaving]     = useState(false)
  const [err, setErr]           = useState(null)
  const [loaded, setLoaded]     = useState(false)
  const wrapRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await api.getSavedViews()
      setViews(data || [])
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!open) return
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false); setNaming(false); setErr(null)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  const save = async () => {
    const name = newName.trim()
    if (!name) return
    setSaving(true); setErr(null)
    try {
      await api.createSavedView(name, { tab, filters })
      setNewName(''); setNaming(false)
      await load()
    } catch (e) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    setErr(null)
    try {
      await api.deleteSavedView(id)
      setViews(vs => vs.filter(v => v.id !== id))
    } catch (e) {
      setErr(e.message)
    }
  }

  const apply = (view) => {
    try {
      const parsed = JSON.parse(view.filters_json || '{}')
      onApply?.(parsed)
      setOpen(false)
    } catch {
      setErr('תצוגה פגומה')
    }
  }

  if (!loaded) return null

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="text-xs text-moca-sub hover:text-moca-bolt flex items-center gap-1.5 transition-colors"
        title="תצוגות שמורות"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
        <span>תצוגות שמורות</span>
        {views.length > 0 && (
          <span className="bg-moca-cream text-moca-sub text-[9px] px-1.5 py-0.5 rounded-full min-w-[16px] text-center">{views.length}</span>
        )}
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1 w-72 bg-white border border-moca-border rounded-xl shadow-lg z-50 p-3 animate-fade-in-up">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-700">תצוגות שמורות</p>
            {!naming && (
              <button
                onClick={() => { setNaming(true); setNewName(''); setErr(null) }}
                className="text-[11px] text-moca-bolt hover:underline"
              >
                + שמור פילטר נוכחי
              </button>
            )}
          </div>

          {naming && (
            <div className="flex gap-1.5 mb-3">
              <input
                type="text"
                autoFocus
                value={newName}
                onChange={e => setNewName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setNaming(false); setErr(null) } }}
                placeholder="שם התצוגה"
                maxLength={60}
                className="flex-1 px-2 py-1 text-xs border border-moca-border rounded"
              />
              <button
                onClick={save}
                disabled={saving || !newName.trim()}
                className="text-[11px] bg-moca-bolt text-white px-2 py-1 rounded disabled:opacity-50"
              >
                {saving ? '…' : 'שמור'}
              </button>
              <button
                onClick={() => { setNaming(false); setErr(null) }}
                className="text-[11px] text-gray-400 px-1"
              >✕</button>
            </div>
          )}

          {err && <p className="text-[11px] text-red-600 mb-2">{err}</p>}

          {views.length === 0 ? (
            <p className="text-[11px] text-gray-400 py-2 text-center">אין תצוגות שמורות</p>
          ) : (
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {views.map(v => (
                <div key={v.id} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-moca-cream/50 group">
                  <button
                    onClick={() => apply(v)}
                    className="flex-1 text-right text-xs text-gray-700 truncate"
                    title={v.name}
                  >{v.name}</button>
                  <button
                    onClick={() => remove(v.id)}
                    className="text-gray-300 hover:text-red-500 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    title="מחק"
                  >✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
