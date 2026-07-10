import { useState } from 'react'
import { API_BASE } from '../../lib/api'
import { useLang } from '../../hooks/useLanguage'
import { getCarrierColor, getCarrierName } from './carrierMeta'

// Fallback gradient per carrier when screenshot isn't available yet
const CARRIER_GRADIENT = {
  partner:   'linear-gradient(135deg,#2ed5c4,#1fa396)',
  pelephone: 'linear-gradient(135deg,#001fff,#0018cc)',
  hotmobile: 'linear-gradient(135deg,#e3001e,#b50018)',
  cellcom:   'linear-gradient(135deg,#9530ff,#7120cc)',
  mobile019: 'linear-gradient(135deg,#e8202a,#b81818)',
  xphone:    'linear-gradient(135deg,#2b9fd5,#1f75a0)',
  wecom:     'linear-gradient(135deg,#ff4500,#cc3600)',
  neptucom:  'linear-gradient(135deg,#29b6d6,#1d8ca3)',
  golan:     'linear-gradient(135deg,#cc1717,#a01212)',
  rami_levy: 'linear-gradient(135deg,#e8178a,#b51069)',
}

function formatDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('he-IL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function freshness(iso, tt) {
  if (!iso) return null
  const ageMs = Date.now() - new Date(iso).getTime()
  const days = ageMs / (24 * 60 * 60 * 1000)
  if (days < 1) return { label: tt('היום', 'Today'), fresh: true }
  if (days < 2) return { label: tt('אתמול', 'Yesterday'), fresh: true }
  const n = Math.floor(days)
  if (days < 7) return { label: tt(`לפני ${n} ימים`, `${n} days ago`), fresh: true }
  return { label: tt(`לפני ${n} ימים`, `${n} days ago`), fresh: false }
}

/**
 * Single banner tile in the mosaic.
 *
 * Click → calls `onClick(banner)` (parent shows the drawer).
 * Internal lift-on-hover animation per the design spec (transform 2px + shadow).
 */
export default function BannerTile({ banner, onClick }) {
  const { tt } = useLang()
  const [imgError, setImgError] = useState(false)
  const [hovered, setHovered] = useState(false)

  const { carrier, name, image_url, scraped_at } = banner
  const displayName = name || getCarrierName(carrier)
  const dotColor = banner.color || getCarrierColor(carrier)
  const resolvedImageUrl = image_url ? `${API_BASE}${image_url}` : null
  const hasImage = resolvedImageUrl && !imgError
  const age = freshness(scraped_at, tt)

  return (
    <button
      type="button"
      onClick={() => onClick && onClick(banner)}
      style={{
        position: 'relative',
        display: 'block',
        width: '100%',
        padding: 0,
        border: 'none',
        background: 'transparent',
        cursor: 'pointer',
        textAlign: 'right',
        direction: 'rtl',
        breakInside: 'avoid',
        WebkitColumnBreakInside: 'avoid',
        pageBreakInside: 'avoid',
        marginBottom: 14,
        fontFamily: 'inherit',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {banner.changed_recently && (
        <span
          style={{
            position: 'absolute',
            top: 8,
            insetInlineStart: 8,
            zIndex: 2,
            background: 'var(--color-moca-hot)',
            color: '#fff',
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: 0.3,
            padding: '3px 8px',
            borderRadius: 999,
            boxShadow: '0 1px 5px rgba(0,0,0,0.28)',
          }}
        >
          {tt('התעדכן', 'Updated')}
        </span>
      )}
      <div
        style={{
          width: '100%',
          aspectRatio: '16 / 9',
          borderRadius: 14,
          overflow: 'hidden',
          background: 'var(--color-moca-cream)',
          border: '1px solid var(--color-moca-border)',
          boxShadow: hovered ? 'var(--sh-card-hover)' : 'var(--sh-card)',
          transform: hovered ? 'translateY(-2px)' : 'translateY(0)',
          transition: 'transform 150ms var(--ease-out), box-shadow 150ms var(--ease-out)',
        }}
      >
        {hasImage ? (
          <img
            src={resolvedImageUrl}
            alt={`${tt('באנר', 'Banner')} ${displayName}`}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              display: 'block',
            }}
            loading="lazy"
            decoding="async"
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
              color: 'rgba(255,255,255,0.85)',
              fontSize: 18,
              fontWeight: 800,
            }}
          >
            {displayName}
          </div>
        )}
      </div>

      {/* Meta strip */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginTop: 8,
          fontSize: 11.5,
          color: 'var(--color-moca-muted)',
          flexWrap: 'wrap',
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: dotColor,
            flexShrink: 0,
          }}
        />
        <span style={{ fontWeight: 700, color: 'var(--color-moca-dark)' }}>{displayName}</span>
        {age && (
          <>
            <span>·</span>
            {age.fresh ? (
              <span
                style={{
                  background: '#fef3c7',
                  color: '#854d0e',
                  fontWeight: 700,
                  padding: '2px 7px',
                  borderRadius: 999,
                  fontSize: 10,
                  letterSpacing: 0.2,
                }}
              >
                {age.label}
              </span>
            ) : (
              <span>{age.label}</span>
            )}
          </>
        )}
      </div>
    </button>
  )
}
