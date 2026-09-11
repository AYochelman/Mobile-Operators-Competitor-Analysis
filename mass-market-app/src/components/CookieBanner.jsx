// Non-blocking cookie/tracking consent bar for the public consumer pages.
//
// Shows ONLY when (a) an optional tracker is configured for this build
// (`tiktokPixelEnabled()`, i.e. VITE_TIKTOK_PIXEL_ID is set) and (b) the
// visitor has not answered the current CONSENT_VERSION yet. With no optional
// tracker configured there is nothing to consent to, so the bar stays hidden
// and the page just links to /cookies from its footer.
//
// Accessibility: a labelled `role="region"` (not a modal - it never traps
// focus or blocks the page), real <button>s, Escape = "essential only".
import { useEffect, useState } from 'react'
import { readConsent, saveConsent } from '../lib/consent'
import { tiktokPixelEnabled } from '../lib/tiktokPixel'

const COPY = {
  he: {
    title: 'עוגיות ומדידה',
    body: 'האתר משתמש בעוגיות הכרחיות בלבד כברירת מחדל. באישורכם נפעיל גם פיקסל מדידה שיווקי (TikTok) שעוזר לנו למדוד קמפיינים. אפשר לשנות את הבחירה בכל רגע בעמוד',
    link: 'מדיניות העוגיות',
    accept: 'אישור הכל',
    essential: 'רק הכרחיות',
  },
  en: {
    title: 'Cookies & measurement',
    body: 'By default this site uses essential cookies only. With your consent we also load a marketing measurement pixel (TikTok) that helps us measure campaigns. You can change your choice at any time on the',
    link: 'cookie policy page',
    accept: 'Accept all',
    essential: 'Essential only',
  },
}

export default function CookieBanner({ lang = 'he' }) {
  const [open, setOpen] = useState(false)
  const t = COPY[lang] || COPY.he

  useEffect(() => {
    if (!tiktokPixelEnabled()) return
    if (!readConsent()) setOpen(true)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') { saveConsent({ marketing: false }); setOpen(false) } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (!open) return null
  const dir = lang === 'en' ? 'ltr' : 'rtl'
  const decide = (marketing) => { saveConsent({ marketing }); setOpen(false) }

  return (
    <section
      role="region"
      aria-labelledby="cookie-banner-title"
      dir={dir}
      style={{
        position: 'fixed', insetInlineStart: 12, insetInlineEnd: 12, bottom: 12, zIndex: 60,
        maxWidth: 560, margin: '0 auto', background: '#fff', color: '#3b1f0d',
        border: '1.5px solid #a08468', borderRadius: 14, padding: '14px 16px',
        boxShadow: '0 10px 30px rgba(59,31,13,.18)', fontSize: 14, lineHeight: 1.55,
        fontFamily: "'Assistant', system-ui, sans-serif",
      }}
    >
      <h2 id="cookie-banner-title" style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 800, color: '#4a2a13' }}>{t.title}</h2>
      <p style={{ margin: '0 0 10px' }}>
        {t.body}{' '}
        <a href={`/cookies${lang === 'en' ? '?lang=en' : ''}`} style={{ color: '#8f3f16', fontWeight: 700 }}>{t.link}</a>.
      </p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => decide(true)}
          style={{ background: '#5c3317', color: '#fff', border: 0, borderRadius: 10, padding: '9px 16px', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}
        >
          {t.accept}
        </button>
        <button
          type="button"
          onClick={() => decide(false)}
          style={{ background: '#fff', color: '#5c3317', border: '1.5px solid #5c3317', borderRadius: 10, padding: '9px 16px', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}
        >
          {t.essential}
        </button>
      </div>
    </section>
  )
}
