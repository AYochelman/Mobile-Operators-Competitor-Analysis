import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { API_BASE } from '../../lib/api'
import { getCarrierColor, getCarrierName } from './carrierMeta'

const CARRIER_GRADIENT = {
  partner:   'linear-gradient(135deg,#e8003d,#ff6b8a)',
  pelephone: 'linear-gradient(135deg,#ff6600,#ffaa44)',
  hotmobile: 'linear-gradient(135deg,#e3001e,#ff5555)',
  cellcom:   'linear-gradient(135deg,#003b7a,#0077cc)',
  mobile019: 'linear-gradient(135deg,#1a1a1a,#555)',
  xphone:    'linear-gradient(135deg,#6a0dad,#b44fec)',
  wecom:     'linear-gradient(135deg,#006633,#22bb66)',
  neptucom:  'linear-gradient(135deg,#004488,#2277cc)',
}

function formatFullDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('he-IL', {
    weekday: 'short',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function Fact({ label, value }) {
  return (
    <div
      style={{
        background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 10,
        padding: '10px 12px',
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: 'var(--color-moca-muted)',
          fontWeight: 800,
          letterSpacing: 0.5,
          textTransform: 'uppercase',
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 13.5, color: 'var(--color-moca-dark)', fontWeight: 700, marginTop: 3 }}>
        {value}
      </div>
    </div>
  )
}

/**
 * Slide-in detail drawer for a banner — replaces the centered modal pattern.
 *
 * Per design handoff:
 *   - Width 480px, max 92vw
 *   - Slides in from RTL start (right) with 250ms ease
 *   - Backdrop: rgba(40,30,15,0.35) + 2px blur
 *   - Click outside / Esc to close
 *   - Contains: large preview, facts grid, action buttons
 */
export default function BannerDrawer({ banner, onClose }) {
  const [imgError, setImgError] = useState(false)

  // Reset image error state when banner changes (otherwise the next banner
  // would inherit the previous one's failure flag).
  useEffect(() => { setImgError(false) }, [banner?.image_url])

  // Esc to close + lock body scroll while open
  useEffect(() => {
    if (!banner) return
    document.body.style.overflow = 'hidden'
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', onKey)
    }
  }, [banner, onClose])

  if (!banner) return null

  const { carrier, name, url, image_url, scraped_at } = banner
  const displayName = name || getCarrierName(carrier)
  const accentColor = banner.color || getCarrierColor(carrier)
  const resolvedImageUrl = image_url ? `${API_BASE}${image_url}` : null
  const hasImage = resolvedImageUrl && !imgError
  const isStore = banner.kind === 'store' || (banner.carrier && banner.carrier.endsWith('_store'))

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9100,
        background: 'rgba(40,30,15,0.35)',
        backdropFilter: 'blur(2px)',
        WebkitBackdropFilter: 'blur(2px)',
        display: 'flex',
        // RTL start = physical right. flex-start in RTL flex puts the drawer on the right.
        justifyContent: 'flex-start',
        animation: 'fadeIn 200ms var(--ease-out)',
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`באנר ${displayName}`}
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 480,
          maxWidth: '92vw',
          height: '100%',
          background: 'var(--color-moca-cream)',
          padding: '22px 26px',
          overflow: 'auto',
          boxShadow: 'var(--sh-drawer)',
          direction: 'rtl',
          animation: 'drawerSlideIn 250ms var(--ease-out)',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 10.5,
                color: 'var(--color-moca-muted)',
                fontWeight: 800,
                letterSpacing: 0.8,
                textTransform: 'uppercase',
              }}
            >
              באנר · {isStore ? 'חנות ציוד' : 'עמוד ראשי'}
            </div>
            <h2
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 24,
                margin: '4px 0 2px',
                color: 'var(--color-moca-dark)',
                letterSpacing: -0.4,
                fontWeight: 800,
              }}
            >
              {displayName}
            </h2>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--color-moca-sub)' }}>
              <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: '50%', background: accentColor, display: 'inline-block' }} />
              {formatFullDate(scraped_at)}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="סגור"
            style={{
              width: 32,
              height: 32,
              borderRadius: 999,
              background: 'var(--color-moca-white, #fff)',
              border: '1px solid var(--color-moca-border)',
              color: 'var(--color-moca-sub)',
              fontSize: 18,
              fontWeight: 600,
              cursor: 'pointer',
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'inherit',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Preview */}
        <div
          style={{
            marginTop: 16,
            borderRadius: 14,
            overflow: 'hidden',
            border: '1px solid var(--color-moca-border)',
            aspectRatio: '16 / 9',
            background: 'var(--color-moca-white, #fff)',
          }}
        >
          {hasImage ? (
            <img
              src={resolvedImageUrl}
              alt={`באנר ${displayName}`}
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              onError={() => setImgError(true)}
            />
          ) : (
            <div
              style={{
                width: '100%',
                height: '100%',
                background: CARRIER_GRADIENT[carrier] || 'linear-gradient(135deg, #c4a882, #8a6a4a)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'rgba(255,255,255,0.9)',
                fontSize: 22,
                fontWeight: 800,
              }}
            >
              {displayName}
            </div>
          )}
        </div>

        {/* Facts */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 16 }}>
          <Fact label="מפעיל" value={displayName} />
          <Fact label="מקור" value={isStore ? 'חנות ציוד קצה' : 'עמוד ראשי'} />
          <Fact label="צולם" value={formatFullDate(scraped_at)} />
          <Fact label="עדכון תמונה" value={banner.changed_today ? 'התמונה השתנתה היום' : 'יציבה'} />
        </div>

        {/* Actions */}
        <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                padding: '11px 14px',
                borderRadius: 10,
                background: 'var(--color-moca-bolt)',
                color: '#fff',
                fontSize: 13,
                fontWeight: 700,
                textDecoration: 'none',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              פתח את עמוד {displayName}
            </a>
          )}
          {hasImage && (
            <a
              href={resolvedImageUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                padding: '11px 14px',
                borderRadius: 10,
                background: 'var(--color-moca-white, #fff)',
                color: 'var(--color-moca-text)',
                fontSize: 13,
                fontWeight: 700,
                textDecoration: 'none',
                border: '1px solid var(--color-moca-border)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.35-4.35" />
              </svg>
              הגדל את הצילום
            </a>
          )}
        </div>
      </aside>
    </div>,
    document.body
  )
}
