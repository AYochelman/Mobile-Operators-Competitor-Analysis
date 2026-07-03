import { useState } from 'react'
import Modal from './ui/Modal'
import Button from './ui/Button'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'

// Self-service password change for the logged-in user. Opened from the profile
// menu. Verifies the current password, then updates via Supabase (no email).
export default function ChangePasswordModal({ open, onClose }) {
  const { changePassword } = useAuth()
  const { tt } = useLang()
  const [current, setCurrent] = useState('')
  const [next, setNext]       = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError]     = useState('')
  const [busy, setBusy]       = useState(false)
  const [done, setDone]       = useState(false)

  const close = () => {
    setCurrent(''); setNext(''); setConfirm(''); setError(''); setDone(false); setBusy(false)
    onClose()
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (next.length < 6)   { setError(tt('הסיסמה החדשה חייבת להכיל לפחות 6 תווים', 'The new password must be at least 6 characters')); return }
    if (next !== confirm)  { setError(tt('הסיסמאות אינן תואמות', 'Passwords do not match')); return }
    if (next === current)  { setError(tt('הסיסמה החדשה זהה לנוכחית', 'The new password is the same as the current one')); return }
    setBusy(true)
    try {
      await changePassword(current, next)
      setDone(true)
    } catch (err) {
      setError(err.message || tt('שגיאה בעדכון הסיסמה', 'Error updating password'))
    } finally {
      setBusy(false)
    }
  }

  const inputCls = 'w-full border border-moca-border rounded-lg px-3 py-2 text-sm bg-moca-mist focus:outline-none focus:ring-2 focus:ring-moca-bolt/30 focus:border-moca-bolt'

  return (
    <Modal open={open} onClose={close} title={tt('שינוי סיסמה', 'Change password')} maxWidth="max-w-sm">
      {done ? (
        <div className="text-center py-4 space-y-4">
          <div className="text-3xl text-moca-down">✓</div>
          <p className="text-sm text-moca-text">{tt('הסיסמה עודכנה בהצלחה.', 'Password updated successfully.')}</p>
          <Button size="sm" onClick={close}>{tt('סגור', 'Close')}</Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="block text-xs text-moca-sub mb-1 text-right">{tt('סיסמה נוכחית', 'Current password')}</label>
            <input type="password" value={current} onChange={e => setCurrent(e.target.value)} className={inputCls} dir="ltr" autoComplete="current-password" required />
          </div>
          <div>
            <label className="block text-xs text-moca-sub mb-1 text-right">{tt('סיסמה חדשה', 'New password')}</label>
            <input type="password" value={next} onChange={e => setNext(e.target.value)} className={inputCls} dir="ltr" autoComplete="new-password" placeholder={tt('לפחות 6 תווים', 'At least 6 characters')} required />
          </div>
          <div>
            <label className="block text-xs text-moca-sub mb-1 text-right">{tt('אימות סיסמה חדשה', 'Confirm new password')}</label>
            <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} className={inputCls} dir="ltr" autoComplete="new-password" required />
          </div>
          {error && <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2 text-right">{error}</p>}
          <div className="flex gap-2 justify-start pt-1">
            <Button type="submit" size="sm" disabled={busy}>{busy ? tt('מעדכן...', 'Updating...') : tt('עדכן סיסמה', 'Update password')}</Button>
            <Button type="button" size="sm" variant="secondary" onClick={close}>{tt('ביטול', 'Cancel')}</Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
