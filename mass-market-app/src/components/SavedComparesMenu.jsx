import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../lib/api'

/**
 * Saved comparison sets — stored as saved_views with filters_json containing
 * { kind: 'compare', plans: [{carrier, plan_name, plan_type}, ...] }
 *
 * Names are prefixed with "[CMP] " in the DB so SavedViewsMenu can filter them out.
 */
const PREFIX = '[CMP] '

export default function SavedComparesMenu({ comparePlans, onApply, onSaved }) {
  const [items, setItems] = useState([])
  const [open, setOpen]   = useState(false)
  const [naming, setNaming] = useState(false)
  const [newName, setNewName] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr]       = useState(null)
  const wrapRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const all = await api.getSavedViews()
      const compares = (all || []).filter(v => v.name?.startsWith(PREFIX))
      setItems(compares)
    } catch (e) {
      setErr(e.message)
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
    if (!name || comparePlans.length === 0) return
    setSaving(true); setErr(null)
    try {
      const plans = comparePlans.map(({ plan, planType }) => ({
        carrier:   plan.carrier,
        plan_name: plan.plan_name || plan.service || '',
        plan_type: planType,
      }))
      await api.createSavedView(PREFIX + name, { kind: 'compare', plans })
      setNewName(''); setNaming(false)
      await load()
      onSaved?.()
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
      setItems(vs => vs.filter(v => v.id !== id))
    } catch (e) {
      setErr(e.message)
    }
  }

  const apply = (item) => {
    try {
      const parsed = JSON.parse(item.filters_json || '{}')
      if (parsed?.kind === 'compare' && Array.isArray(parsed.plans)) {
        onApply?.(parsed.plans)
        setOpen(false)
      } else {
        setErr('פורמט סט לא תקין')
      }
    } catch {
      setErr('סט פגום')
    }
  }

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="text-xs text-moca-sub hover:text-moca-bolt border border-moca-border/40 rounded-lg px-3 py-1.5 transition-colors hover:bg-moca-cream flex items-center gap-1.5"
        title="סטים שמורים"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
        סטים שמורים
        {items.length > 0 && (
          <span className="bg-moca-cream text-moca-sub text-[9px] px-1.5 py-0.5 rounded-full min-w-[16px] text-center">{items.length}</span>
        )}
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-moca-border rounded-xl shadow-lg z-[9999] p-3 animate-fade-in-up text-right" dir="rtl">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-700">סטים שמורים</p>
            {!naming && comparePlans.length > 0 && (
              <button
                onClick={() => { setNaming(true); setNewName(''); setErr(null) }}
                className="text-[11px] text-moca-bolt hover:underline"
              >
                + שמור סט נוכחי ({comparePlans.length})
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
                placeholder="שם הסט"
                maxLength={50}
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

          {items.length === 0 ? (
            <p className="text-[11px] text-gray-400 py-2 text-center">אין סטים שמורים</p>
          ) : (
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {items.map(v => {
                let planCount = 0
                try { planCount = JSON.parse(v.filters_json || '{}').plans?.length || 0 } catch {}
                return (
                  <div key={v.id} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-moca-cream/50 group">
                    <button
                      onClick={() => apply(v)}
                      className="flex-1 text-right text-xs text-gray-700 truncate"
                      title={v.name.slice(PREFIX.length)}
                    >
                      {v.name.slice(PREFIX.length)}
                      <span className="text-gray-400 mr-1.5">({planCount})</span>
                    </button>
                    <button
                      onClick={() => remove(v.id)}
                      className="text-gray-300 hover:text-red-500 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                      title="מחק"
                    >✕</button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
