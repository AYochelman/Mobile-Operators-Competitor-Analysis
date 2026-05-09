import { useEffect } from 'react'
import { createPortal } from 'react-dom'

/**
 * Time Machine modal — placeholder. Full implementation (date picker + carrier
 * dropdown + historical banner/plan rendering) lands in a later phase.
 */
export default function TimeMachineModal({ open, onClose }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9000,
        background: 'rgba(40,30,15,0.35)',
        backdropFilter: 'blur(2px)',
        WebkitBackdropFilter: 'blur(2px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        animation: 'fadeIn 200ms var(--ease-out)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(520px, 92vw)',
          background: 'var(--color-moca-bg)',
          borderRadius: 16,
          padding: 28,
          boxShadow: 'var(--sh-modal)',
          textAlign: 'center',
          animation: 'fadeInUp 250ms var(--ease-out)',
        }}
      >
        <div
          aria-hidden="true"
          style={{
            width: 56,
            height: 56,
            borderRadius: 999,
            background: 'var(--color-moca-cream)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-moca-bolt)',
            margin: '0 auto 14px',
          }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
            <path d="M3.5 8.5 6 6" />
          </svg>
        </div>
        <h2
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 22,
            fontWeight: 800,
            color: 'var(--color-moca-dark)',
            margin: '0 0 6px',
            letterSpacing: -0.4,
          }}
        >
          צפה בעבר
        </h2>
        <p
          style={{
            fontSize: 13.5,
            color: 'var(--color-moca-sub)',
            margin: '0 0 18px',
            lineHeight: 1.55,
          }}
        >
          בקרוב — בחירת תאריך + מתחרה תציג את הבאנרים והמסלולים שהיו פעילים באותו יום, עם השוואה למצב הנוכחי.
        </p>
        <button
          onClick={onClose}
          style={{
            padding: '9px 20px',
            borderRadius: 10,
            background: 'var(--color-moca-bolt)',
            color: '#fff',
            border: 'none',
            fontSize: 13,
            fontWeight: 700,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          סגור
        </button>
      </div>
    </div>,
    document.body
  )
}
