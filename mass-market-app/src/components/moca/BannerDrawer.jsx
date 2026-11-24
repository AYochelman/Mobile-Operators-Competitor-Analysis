import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useLang } from '../../hooks/useLanguage'
import { useApiImage } from '../../hooks/useApiImage'
import { getCarrierColor, getCarrierName } from './carrierMeta'
import { campaignTypeLabel } from '../../data/campaignTypes'

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
  if (!iso) return '-'
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
 * The automatic reading of a banner: headline, offer, price, conditions. The
 * text is a machine transcription of a screenshot, so it is labelled as such
 * and a low-confidence reading says why instead of showing a guess.
 */
function BannerReading({ insight, tt }) {
  const line = { fontSize: 13, color: 'var(--color-moca-text)', lineHeight: 1.55, margin: '6px 0 0' }
  const unreadable = insight.confidence === 'low' || !insight.has_offer
  return (
    <section
      style={{
        marginTop: 16, background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)', borderRadius: 12, padding: '12px 14px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 0.5 }}>
          {tt('מה כתוב בבאנר', 'What the banner says')}
        </span>
        {!unreadable && (
          <span style={{ fontSize: 11, fontWeight: 700, background: 'var(--color-moca-cream)', color: 'var(--color-moca-sub)', borderRadius: 999, padding: '1px 8px' }}>
            {campaignTypeLabel(insight.campaign_type, tt)}
          </span>
        )}
      </div>
      {unreadable ? (
        <p style={line}>
          {insight.obstruction
            ? `${tt('לא ניתן היה לקרוא את ההצעה', 'The offer could not be read')}: ${insight.obstruction}`
            : tt('לא זוהתה הצעה שיווקית בצילום.', 'No promotional offer was found in the screenshot.')}
        </p>
      ) : (
        <>
          {insight.headline && <p style={{ ...line, fontSize: 15, fontWeight: 800, color: 'var(--color-moca-dark)' }}>{insight.headline}</p>}
          {insight.offer && <p style={line}>{insight.offer}</p>}
          {insight.price_text && <p style={{ ...line, fontWeight: 700 }}>{tt('מחיר', 'Price')}: {insight.price_text}</p>}
          {insight.fine_print && <p style={{ ...line, fontSize: 12, color: 'var(--color-moca-sub)' }}>{tt('תנאים', 'Conditions')}: {insight.fine_print}</p>}
          {insight.cta && <p style={{ ...line, fontSize: 12, color: 'var(--color-moca-sub)' }}>{tt('כפתור', 'Button')}: {insight.cta}</p>}
        </>
      )}
      <p style={{ ...line, fontSize: 11, color: 'var(--color-moca-muted)' }}>
        {tt('קריאה אוטומטית של הצילום. באתר עם באנר מתחלף מוצגת השקופית שנתפסה בצילום.', 'Automatic reading of the screenshot. On a rotating banner this is the slide the capture caught.')}
      </p>
    </section>
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
  const { tt } = useLang()
  // Blob-fetched (useApiImage) so the ngrok interstitial can't eat the <img>.
  // Called before the early return below - hooks must run unconditionally.
  // The hook's error state is per-path, so banner switches reset it inherently.
  const { src: drawerImgSrc, error: drawerImgError } = useApiImage(banner?.image_url)

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

  const { carrier, name, url, scraped_at } = banner
  const displayName = name || getCarrierName(carrier)
  const accentColor = banner.color || getCarrierColor(carrier)
  const hasImage = drawerImgSrc && !drawerImgError
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
      aria-label={`${tt('באנר', 'Banner')} ${displayName}`}
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
              {tt('באנר', 'Banner')} · {isStore ? tt('חנות ציוד', 'Equipment store') : tt('עמוד ראשי', 'Homepage')}
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
            aria-label={tt('סגור', 'Close')}
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
              src={drawerImgSrc}
              alt={`${tt('באנר', 'Banner')} ${displayName}`}
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
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

        {/* What the screenshot says - read by banner_vision.py */}
        {banner.insight && <BannerReading insight={banner.insight} tt={tt} />}

        {/* Facts */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 16 }}>
          <Fact label={tt('מפעיל', 'Operator')} value={displayName} />
          <Fact label={tt('מקור', 'Source')} value={isStore ? tt('חנות ציוד קצה', 'Device store') : tt('עמוד ראשי', 'Homepage')} />
          <Fact label={tt('צולם', 'Captured')} value={formatFullDate(scraped_at)} />
          <Fact label={tt('עדכון תמונה', 'Image update')} value={banner.changed_today ? tt('התמונה השתנתה היום', 'Image changed today') : tt('יציבה', 'Stable')} />
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
              {tt('פתח את עמוד', 'Open page of')} {displayName}
            </a>
          )}
          {hasImage && (
            <a
              href={drawerImgSrc}
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
              {tt('הגדל את הצילום', 'Enlarge screenshot')}
            </a>
          )}
        </div>
      </aside>
    </div>,
    document.body
  )
}
