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
        —
      </span>
    )
  }

  const up = value > 0
  const color = up ? 'var(--color-moca-up)' : 'var(--color-moca-down)'
  const arrow = up ? '▲' : '▼'
  const sign = up ? '+' : ''

  return (
    <span
      className="tnum"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
        fontSize: size === 'sm' ? 11 : 13,
        fontWeight: 700,
        color,
        direction: 'ltr',
      }}
    >
      <span style={{ fontSize: size === 'sm' ? 8 : 10 }}>{arrow}</span>
      {sign}{value}{suffix}
    </span>
  )
}
