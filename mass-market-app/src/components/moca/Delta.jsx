/**
 * Price/value delta pill with up/down arrow.
 *
 * Semantic: in MOCA's competitive context a price drop by a competitor is
 * BAD news for us — so positive values use the "up" color (warm red) and
 * negative values use the "down" color (green). `value === 0` or null
 * renders an em-dash.
 *
 * <Delta value={+5} />          → ▲ +5₪ (warm red)
 * <Delta value={-10} size="md"/> → ▼ -10₪ (green, larger)
 * <Delta value={0} />           → —
 * <Delta value={5} suffix="%" /> → ▲ +5%
 */
export default function Delta({ value, size = 'sm', suffix = '₪' }) {
  if (value === 0 || value == null) {
    return (
      <span
        className="tnum"
        style={{
          fontSize: size === 'sm' ? 11 : 13,
          fontWeight: 600,
          color: 'var(--color-moca-muted)',
        }}
      >
        -
      </span>
    )
  }

  const up = value > 0
  // Filled tint pill: soft background from the up/down family + a darker text
  // shade from the same family. Far more legible at a glance than bare colored
  // text — a competitor's price move reads instantly. Semantic unchanged
  // (up = warm red = bad for us, down = green = good for us).
  const color = up ? '#9a3320' : '#3f6c34'
  const bg = up ? 'rgba(180, 71, 45, 0.12)' : 'rgba(74, 124, 63, 0.13)'
  const arrow = up ? '▲' : '▼'
  const sign = up ? '+' : ''

  return (
    <span
      className="tnum"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontSize: size === 'sm' ? 11 : 12.5,
        fontWeight: 700,
        color,
        background: bg,
        padding: size === 'sm' ? '2px 8px' : '3px 10px',
        borderRadius: 999,
        direction: 'ltr',
      }}
    >
      <span style={{ fontSize: size === 'sm' ? 8 : 10 }}>{arrow}</span>
      {sign}{value}{suffix}
    </span>
  )
}
