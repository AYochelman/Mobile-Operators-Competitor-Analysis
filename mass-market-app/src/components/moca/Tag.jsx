/**
 * Compact uppercase pill — used for status/category labels:
 * NEW, HOT, PRICE UP, EXTRAS+, TOP, etc.
 *
 * <Tag>NEW</Tag>                                         — default warm orange
 * <Tag color="var(--color-moca-up)">PRICE UP</Tag>       — warm red
 * <Tag color="var(--color-moca-down)">PRICE DOWN</Tag>   — green
 * <Tag color="var(--color-moca-bolt)">TOP</Tag>          — brand espresso
 */
export default function Tag({ children, color }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 7px',
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 800,
        letterSpacing: 0.5,
        background: color || 'var(--color-moca-hot)',
        color: '#fff',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  )
}
