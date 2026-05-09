import { getCarrierColor, getCarrierLetter, getCarrierName } from './carrierMeta'

/**
 * Circular carrier avatar with brand color + first-letter glyph.
 *
 * <CarrierChip id="cellcom" />                       — chip only
 * <CarrierChip id="cellcom" showName />              — chip + name
 * <CarrierChip id="cellcom" size={32} showName bold /> — larger, bold name
 * <CarrierChip id="pelephone" showName ours />       — adds "•" marker for our carrier
 */
export default function CarrierChip({
  id,
  size = 24,
  showName = false,
  bold = false,
  ours = false,
}) {
  if (!id) return null
  const color = getCarrierColor(id)
  const letter = getCarrierLetter(id)
  const name = getCarrierName(id)
  const fontSize = Math.round(size * 0.42)

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
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
