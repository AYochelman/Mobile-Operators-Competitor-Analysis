import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { DOMESTIC_LABELS } from '../../data/carrierLabels'
import CarrierChip from './CarrierChip'

/**
 * Quick-action modal to set the workspace's mvno_carrier — the "my carrier"
 * field that drives the BENCHMARK accent, the Editorial Hero comparison,
 * and the bottom-right pinned chip.
 *
 * The full workspace editor is at /admin/workspaces, but it's a heavy multi-
 * step UI. This modal exposes JUST the carrier selector — one PATCH call,
 * one source of truth.
 *
 * Requires super_admin (the underlying endpoint is gated at the backend).
 */
export default function MyCarrierModal({ open, onClose }) {
  const { workspace, isSuperAdmin } = useAuth()
  // For super_admins without a user_roles.workspace_id, fetch the workspace
  // list so they can pick which one to bind the carrier to. Regular admins
  // always have their own workspace assigned.
  const [workspaces, setWorkspaces] = useState(null)
  const [pickedWsId, setPickedWsId] = useState(workspace?.id || '')
  const wsId = workspace?.id || pickedWsId
  const pickedWs = workspaces?.find((w) => w.id === pickedWsId)
  const effectiveWs = workspace?.id ? workspace : pickedWs
  const initialCarrier = effectiveWs?.mvno_carrier || ''
  const [selected, setSelected] = useState(initialCarrier)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Reset on open + lock body scroll + Esc to close
  useEffect(() => {
    if (!open) return
    setSelected(effectiveWs?.mvno_carrier || '')
    setError(null)
    document.body.style.overflow = 'hidden'
    const onKey = (e) => { if (e.key === 'Escape' && !saving) onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', onKey)
    }
  }, [open, effectiveWs?.mvno_carrier, onClose, saving])

  // Lazy-load workspace list when super_admin opens the modal without a
  // bound workspace. Single fetch per modal session.
  useEffect(() => {
    if (!open) return
    if (workspace?.id) return  // already bound, no need to list
    if (!isSuperAdmin) return  // only super_admin can list/edit other workspaces
    if (workspaces) return     // already loaded
    api.getWorkspaces()
      .then((res) => {
        const list = Array.isArray(res) ? res : (res?.workspaces || [])
        setWorkspaces(list)
        if (list.length > 0 && !pickedWsId) {
          setPickedWsId(list[0].id)
        }
      })
      .catch((e) => setError(`לא הצלחתי לטעון את רשימת ה-workspaces: ${e.message}`))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, workspace?.id, isSuperAdmin])

  if (!open) return null

  const handleSave = async () => {
    if (!wsId) {
      setError('לא נמצא workspace_id — אין workspace זמין לעדכון')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await api.updateWorkspace(wsId, { mvno_carrier: selected || null })
      // For a super_admin without a bound workspace, also stash a "view-as"
      // preference so the dashboard immediately reflects the new carrier
      // (otherwise their `workspace.mvno_carrier` stays null after reload).
      // useAuth reads viewAs from sessionStorage (key: moca_view_as_workspace).
      if (!workspace?.id && pickedWs) {
        try {
          sessionStorage.setItem('moca_view_as_workspace', JSON.stringify({
            ...pickedWs,
            mvno_carrier: selected || null,
          }))
        } catch { /* quota — ignore */ }
      }
      // Force a reload so useAuth re-fetches /api/my-context with the new value.
      window.location.reload()
    } catch (e) {
      setError(e.message || 'שגיאה בשמירה')
      setSaving(false)
    }
  }

  // Sort carrier options alphabetically by display label (Hebrew-aware)
  const carrierOptions = Object.entries(DOMESTIC_LABELS)
    .map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label, 'he'))

  return createPortal(
    <div
      onClick={() => { if (!saving) onClose() }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9100,
        background: 'rgba(40,30,15,0.45)',
        backdropFilter: 'blur(3px)',
        WebkitBackdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
        animation: 'fadeIn 200ms var(--ease-out)',
      }}
      role="dialog"
      aria-modal="true"
      aria-label="הגדר את הספק שלי"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(480px, 92vw)',
          background: 'var(--color-moca-bg)',
          borderRadius: 16,
          padding: 26,
          boxShadow: 'var(--sh-modal)',
          animation: 'fadeInUp 250ms var(--ease-out)',
          direction: 'rtl',
        }}
      >
        <div style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 0.7, textTransform: 'uppercase', marginBottom: 6 }}>
          {effectiveWs?.name || 'Workspace'}
        </div>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 800, color: 'var(--color-moca-dark)', margin: 0, letterSpacing: -0.4 }}>
          הגדר את הספק שלי
        </h2>
        <p style={{ fontSize: 13, color: 'var(--color-moca-sub)', margin: '8px 0 18px', lineHeight: 1.55 }}>
          בחר את המתחרה שאת המסלולים שלו אתה מנהל. הוא יודגש בכל מקום באפליקציה
          (BENCHMARK, השוואה מיידית, כרטיס pinned), ושינויים שלו לא יופיעו כשינויים תחרותיים.
        </p>

        {/* Workspace selector — only shown when super_admin without a bound workspace.
            Regular admins always have one workspace and don't see this. */}
        {!workspace?.id && isSuperAdmin && (
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 10.5, color: 'var(--color-moca-muted)', fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', marginBottom: 6 }}>
              workspace ליעד
            </label>
            {workspaces ? (
              workspaces.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--color-moca-sub)', padding: 10, background: 'var(--color-moca-cream)', borderRadius: 8 }}>
                  אין workspaces במערכת — צור אחד ב-/admin/workspaces
                </div>
              ) : (
                <select
                  value={pickedWsId}
                  onChange={(e) => setPickedWsId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 8,
                    border: '1px solid var(--color-moca-border)',
                    background: 'var(--color-moca-white, #fff)',
                    color: 'var(--color-moca-text)',
                    fontSize: 13,
                    fontFamily: 'inherit',
                    cursor: 'pointer',
                  }}
                >
                  {workspaces.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}{w.mvno_carrier ? ` · ${w.mvno_carrier}` : ''}
                    </option>
                  ))}
                </select>
              )
            ) : (
              <div style={{ fontSize: 12, color: 'var(--color-moca-muted)' }}>טוען workspaces…</div>
            )}
          </div>
        )}

        {/* Carrier picker — radio cards for visual richness */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 16 }}>
          {carrierOptions.map(({ id, label }) => {
            const isActive = selected === id
            return (
              <button
                key={id}
                type="button"
                onClick={() => setSelected(id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 12px',
                  borderRadius: 10,
                  border: `1.5px solid ${isActive ? 'var(--color-moca-bolt)' : 'var(--color-moca-border)'}`,
                  background: isActive ? 'var(--color-moca-cream)' : 'var(--color-moca-white, #fff)',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  textAlign: 'right',
                  transition: 'all 120ms ease',
                }}
              >
                <CarrierChip id={id} size={26} />
                <span style={{ flex: 1, fontSize: 13, fontWeight: isActive ? 700 : 500, color: 'var(--color-moca-dark)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {label}
                </span>
                {isActive && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-moca-bolt)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </button>
            )
          })}
        </div>

        {/* Clear option */}
        {initialCarrier && (
          <button
            type="button"
            onClick={() => setSelected('')}
            style={{
              fontSize: 11.5,
              color: selected === '' ? 'var(--color-moca-up)' : 'var(--color-moca-muted)',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'inherit',
              padding: '4px 0',
              marginBottom: 14,
            }}
          >
            {selected === '' ? '✓ ' : ''}אל תגדיר ספק ראשי (נקה)
          </button>
        )}

        {error && (
          <div style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 10,
            padding: 10,
            color: '#b91c1c',
            fontSize: 12,
            marginBottom: 14,
          }}>{error}</div>
        )}

        {!isSuperAdmin && (
          <div style={{
            background: 'var(--color-moca-cream)',
            border: '1px solid var(--color-moca-border)',
            borderRadius: 10,
            padding: 10,
            color: 'var(--color-moca-sub)',
            fontSize: 11.5,
            marginBottom: 14,
            lineHeight: 1.5,
          }}>
            ⚠ שינוי ספק ראשי דורש הרשאת super_admin (ה-API גוטר את זה ברמה הזאת).
            אם אתה admin רגיל, פנה ל-super_admin להחיל את הבחירה.
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-start' }}>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || selected === initialCarrier}
            style={{
              padding: '10px 22px',
              borderRadius: 10,
              background: 'var(--color-moca-bolt)',
              color: '#fff',
              border: 'none',
              fontSize: 13,
              fontWeight: 700,
              cursor: saving || selected === initialCarrier ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              opacity: saving || selected === initialCarrier ? 0.5 : 1,
            }}
          >
            {saving ? 'שומר…' : 'שמור'}
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            style={{
              padding: '10px 22px',
              borderRadius: 10,
              background: 'transparent',
              color: 'var(--color-moca-text)',
              border: '1px solid var(--color-moca-border)',
              fontSize: 13,
              fontWeight: 600,
              cursor: saving ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
            }}
          >
            ביטול
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
