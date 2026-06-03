import { useState } from 'react'
import { getCarrierColor, getCarrierLetter, getCarrierName, getCarrierLogo } from './carrierMeta'

/**
 * Carrier avatar — shows the real brand LOGO by default, falling back to a
 * color + first-letter glyph when the carrier has no logo (or the image fails
 * to load). Pass `logo={false}` to force the letter glyph.
 *
 * <CarrierChip id="cellcom" />                       — logo tile (letter fallback)
 * <CarrierChip id="cellcom" showName />              — logo + name
 * <CarrierChip id="cellcom" size={32} showName bold /> — larger, bold name
 * <CarrierChip id="pelephone" showName ours />       — adds "•" marker for our carrier
 * <CarrierChip id="cellcomshefamr" logo={false} />   — force the letter glyph
 */
export default function CarrierChip({
  id,
  size = 24,
  showName = false,
  bold = false,
  ours = false,
  logo = true,
}) {
  const [imgFailed, setImgFailed] = useState(false)
  if (!id) return null
  const color = getCarrierColor(id)
  const letter = getCarrierLetter(id)
  const name = getCarrierName(id)
  const fontSize = Math.round(size * 0.42)
  const logoSrc = logo ? getCarrierLogo(id) : null
  const showLogo = logoSrc && !imgFailed

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      {showLogo ? (
        <span
          aria-hidden={showName ? 'true' : undefined}
          style={{
            width: size,
            height: size,
            borderRadius: Math.round(size * 0.28),
            background: '#fff',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            overflow: 'hidden',
            border: '1px solid var(--color-moca-border)',
          }}
        >
          <img
            src={logoSrc}
            alt={showName ? '' : name}
            loading="lazy"
            decoding="async"
            onError={() => setImgFailed(true)}
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
          />
        </span>
      ) : (
        <span
          aria-hidden="true"
          style={{
            width: size,
            height: size,
            borderRadius: size / 2,
            background: color,
            color: '#fff',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize,
            fontWeight: 700,
            flexShrink: 0,
            letterSpacing: letter.length > 1 ? -0.3 : 0,
          }}
        >
          {letter}
        </span>
      )}
      {showName && (
        <span
          style={{
            fontSize: 13,
            fontWeight: bold ? 700 : 500,
            color: 'var(--color-moca-text)',
          }}
        >
          {name}
          {ours && (
            <span style={{ color: 'var(--color-moca-bolt)', marginInlineStart: 4, fontWeight: 700 }}>
              •
            </span>
          )}
        </span>
      )}
    </span>
  )
}
