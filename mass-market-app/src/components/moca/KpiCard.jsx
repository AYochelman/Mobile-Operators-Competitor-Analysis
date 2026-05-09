import Delta from './Delta'

/**
 * Single KPI tile — label, big value, optional delta vs previous period.
 * Designed to sit in a 4-column row on the Editorial Deep dashboard.
 *
 * <KpiCard label="שינויים היום" value="14" delta={+3} />
 * <KpiCard label="פלאפון vs שוק" value="+28%" neutral />
 */
export default function KpiCard({ label, value, delta, deltaSuffix = '', neutral = false, note, accent }) {
  return (
    <div
      style={{
        background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 14,
        padding: '14px 16px',
        position: 'relative',
        boxShadow: 'var(--sh-card)',
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
      <div
        className="tnum"
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 10,
          marginTop: 6,
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 26,
            fontWeight: 800,
            color: accent || 'var(--color-moca-dark)',
            letterSpacing: -0.5,
            lineHeight: 1.1,
            direction: 'ltr',
          }}
        >
          {value}
        </div>
        {!neutral && delta != null && delta !== 0 && (
          <Delta value={delta} suffix={deltaSuffix} />
        )}
      </div>
      {note && (
        <div style={{ fontSize: 11, color: 'var(--color-moca-muted)', marginTop: 4 }}>
          {note}
        </div>
      )}
    </div>
  )
}
