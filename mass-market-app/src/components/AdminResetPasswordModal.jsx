import { useState } from 'react'
import Modal from './ui/Modal'
import Button from './ui/Button'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'

// Super-admin sets a new password for a locked-out user. Writes directly via
// the backend (no email). Shows the new password so the admin can hand it over.
function genPassword() {
  // Unambiguous chars only (no O/0/I/l) — easy to read out / type.
  const chars = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let s = ''
  for (let i = 0; i < 8; i++) s += chars[Math.floor(Math.random() * chars.length)]
  return 'Moca-' + s
}

export default function AdminResetPasswordModal({ user, onClose }) {
  const { tt } = useLang()
  const [password, setPassword] = useState(genPassword)
  const [busy, setBusy]     = useState(false)
  const [error, setError]   = useState('')
  const [done, setDone]     = useState(false)
  const [copied, setCopied] = useState(false)

  if (!user) return null

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 6) { setError(tt('הסיסמה חייבת להכיל לפחות 6 תווים', 'The password must be at least 6 characters')); return }
    setBusy(true)
    try {
      await api.adminSetPassword(user.id, password)
      setDone(true)
    } catch (err) {
      setError(err.message || tt('שגיאה באיפוס הסיסמה', 'Error resetting password'))
    } finally {
      setBusy(false)
    }
  }

  const copy = () => {
    try {
      navigator.clipboard.writeText(password)
      setCopied(true); setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }

  const inputCls = 'flex-1 border border-moca-border rounded-lg px-3 py-2 text-sm bg-moca-mist focus:outline-none focus:ring-2 focus:ring-moca-bolt/30 focus:border-moca-bolt font-mono'

  return (
    <Modal open={!!user} onClose={onClose} title={tt('איפוס סיסמה', 'Reset password')} maxWidth="max-w-sm">
      <p className="text-xs text-moca-sub mb-3 text-right leading-relaxed">
        {tt('קביעת סיסמה חדשה עבור ', 'Set a new password for ')}<span dir="ltr" className="font-medium text-moca-text">{user.email}</span>{tt('. לא נשלח מייל — מסור את הסיסמה למשתמש והמלץ להחליף אותה בכניסה.', '. No email will be sent — hand the password to the user and recommend they change it on sign-in.')}
      </p>
      {done ? (
        <div className="space-y-3">
          <div className="bg-moca-cream rounded-lg p-3 text-center">
            <p className="text-xs text-moca-sub mb-1">{tt('הסיסמה אופסה. הסיסמה החדשה:', 'Password reset. The new password:')}</p>
            <p dir="ltr" className="font-mono text-base font-bold text-moca-text select-all">{password}</p>
          </div>
          <div className="flex gap-2 justify-start">
            <Button size="sm" onClick={copy}>{copied ? tt('הועתק ✓', 'Copied ✓') : tt('העתק', 'Copy')}</Button>
            <Button size="sm" variant="secondary" onClick={onClose}>{tt('סגור', 'Close')}</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <div className="flex gap-2">
            <input type="text" value={password} onChange={e => setPassword(e.target.value)} className={inputCls} dir="ltr" />
            <Button type="button" size="sm" variant="secondary" onClick={() => setPassword(genPassword())}>{tt('הגרל', 'Generate')}</Button>
          </div>
          {error && <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2 text-right">{error}</p>}
          <div className="flex gap-2 justify-start pt-1">
            <Button type="submit" size="sm" disabled={busy}>{busy ? tt('מאפס...', 'Resetting...') : tt('אפס סיסמה', 'Reset password')}</Button>
            <Button type="button" size="sm" variant="secondary" onClick={onClose}>{tt('ביטול', 'Cancel')}</Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
