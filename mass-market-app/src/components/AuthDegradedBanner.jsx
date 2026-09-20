import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'

/**
 * Shown when the role on screen is a FALLBACK, not the server's answer.
 *
 * The bug this fixes: `/api/my-context` failing (Flask down, tunnel down,
 * timeout, or a JWT with no identity) used to drop the user to `viewer`
 * silently. Every admin menu vanished and the UI gave no hint why — it looked
 * exactly like a permissions change. Now the app still works in the degraded
 * role, but says so and offers a retry that doesn't require signing out.
 */

const REASON_TEXT = {
  unreachable:        { he: 'השרת אינו זמין',                    en: 'the server is unreachable' },
  timeout:            { he: 'השרת לא הגיב בזמן',                 en: 'the server timed out' },
  http_401:           { he: 'ההזדהות לא התקבלה',                 en: 'authentication was rejected' },
  http_403:           { he: 'ההרשאה נדחתה',                      en: 'authorization was refused' },
  no_jwt:             { he: 'הבקשה הגיעה בלי זהות משתמש',        en: 'the request carried no user identity' },
  no_email:           { he: 'לא נמצאה כתובת מייל בהזדהות',       en: 'the sign-in carried no email' },
  no_role_in_response:{ he: 'השרת לא החזיר תפקיד',               en: 'the server returned no role' },
  db_error:           { he: 'השרת לא הצליח לקרוא את מסד ההרשאות', en: 'the server could not read the permissions database' },
  client_error:       { he: 'שגיאה בצד הדפדפן',                  en: 'a client-side error' },
}

export default function AuthDegradedBanner() {
  const { contextDegraded, retryContext, role } = useAuth()
  const { tt, lang } = useLang()
  const [busy, setBusy] = useState(false)

  if (!contextDegraded) return null

  const r = REASON_TEXT[contextDegraded.reason]
  const why = r ? (lang === 'he' ? r.he : r.en) : contextDegraded.reason

  const retry = async () => {
    setBusy(true)
    try { await retryContext() } finally { setBusy(false) }
  }

  return (
    <div role="status" style={{ background: 'var(--color-moca-up)', color: '#fff', fontSize: 13 }}>
      <div style={{
        maxWidth: 1320, margin: '0 auto', padding: '8px 16px',
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
      }}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0 }}>
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12" y2="17.01" />
        </svg>
        <span style={{ minWidth: 0, flex: 1 }}>
          <strong>{tt('לא ניתן לאמת את ההרשאות שלך', 'Could not verify your permissions')}</strong>
          {' — '}{why}.{' '}
          {tt(
            `אתה מוצג כרגע כ-${role || 'viewer'}, וייתכן שחלק מהתפריטים חסרים.`,
            `You are shown as ${role || 'viewer'}, so some menus may be missing.`,
          )}
        </span>
        <button
          onClick={retry}
          disabled={busy}
          style={{
            background: 'rgba(255,255,255,0.16)', color: '#fff', border: 'none',
            borderRadius: 8, padding: '5px 13px', fontSize: 12.5, fontWeight: 700,
            cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1, whiteSpace: 'nowrap',
          }}
        >
          {busy ? tt('בודק…', 'Checking…') : tt('נסו שוב', 'Retry')}
        </button>
      </div>
    </div>
  )
}
