import { getCarrierColor, getCarrierName } from './carrierMeta'

/**
 * 8-carrier × 14-day heatmap. Cell intensity = number of changes that
 * (carrier, day). Color comes from the carrier's brand color (mvnoBrandColors).
 *
 * Pure presentational — pass `data` from useDashboardData.heatmap.
 *
 * <ChangeHeatmap data={{ carriers, days, cells, maxCount }} />
 */

const CELL_HEIGHT = 22
const CELL_GAP = 2

function dayLabel(iso) {
  // "MM/DD" — short for axis labels
  const [, mm, dd] = iso.split('-')
  return `${dd}/${mm}`
}

export default function ChangeHeatmap({ data }) {
  if (!data || data.carriers.length === 0) return null
  const { carriers, days, cells, maxCount } = data

  return (
    <section
      style={{
        background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 14,
        boxShadow: 'var(--sh-card)',
        padding: '16px 18px',
      }}
    >
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        <h2
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 16,
            fontWeight: 800,
            color: 'var(--color-moca-dark)',
            letterSpacing: -0.2,
            margin: 0,
          }}
        >
          עוצמת שינויים · Heatmap
        </h2>
        <span style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>
          {days.length} ימים אחרונים · רוחב הריבוע = מספר שינויים
        </span>
      </header>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(90px, 130px) 1fr',
          gap: 10,
          alignItems: 'stretch',
        }}
      >
        {/* Carrier name column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: CELL_GAP, paddingTop: 18 }}>
          {carriers.map((id) => (
            <div
              key={id}
              style={{
                height: CELL_HEIGHT,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--color-moca-text)',
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: getCarrierColor(id),
                  flexShrink: 0,
                }}
              />
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {getCarrierName(id)}
              </span>
            </div>
          ))}
        </div>

        {/* Heatmap grid */}
        <div style={{ overflowX: 'auto' }}>
          {/* Day headers */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${days.length}, minmax(20px, 1fr))`,
              gap: CELL_GAP,
              marginBottom: 4,
            }}
          >
            {days.map((d, i) => (
              <div
                key={d}
                className="tnum"
                style={{
                  fontSize: 9,
                  color: 'var(--color-moca-muted)',
                  textAlign: 'center',
                  fontWeight: 700,
                  letterSpacing: 0.2,
                  direction: 'ltr',
                  // Show every other label on small screens (avoid clutter)
                  visibility: i % 2 === 0 ? 'visible' : 'hidden',
                }}
              >
                {dayLabel(d)}
              </div>
            ))}
          </div>

          {/* Rows */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: CELL_GAP }}>
            {carriers.map((id) => {
              const carrierColor = getCarrierColor(id)
              return (
                <div
                  key={id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: `repeat(${days.length}, minmax(20px, 1fr))`,
                    gap: CELL_GAP,
                  }}
                >
                  {days.map((d) => {
                    const count = cells.get(`${id}|${d}`) || 0
                    const intensity = maxCount > 0 ? count / maxCount : 0
                    const opacity = count === 0 ? 0.08 : 0.25 + intensity * 0.7
                    return (
                      <div
                        key={d}
                        title={count ? `${count} שינויים · ${dayLabel(d)}` : `אין שינויים · ${dayLabel(d)}`}
                        style={{
                          height: CELL_HEIGHT,
                          borderRadius: 4,
                          background: count === 0 ? 'var(--color-moca-cream)' : carrierColor,
                          opacity: count === 0 ? 1 : opacity,
                          transition: 'opacity 120ms ease',
                          cursor: count > 0 ? 'help' : 'default',
                        }}
                      />
                    )
                  })}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
