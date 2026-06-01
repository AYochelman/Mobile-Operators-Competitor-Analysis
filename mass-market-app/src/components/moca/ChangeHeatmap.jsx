import { useEffect, useState } from 'react'
import { getCarrierColor, getCarrierName } from './carrierMeta'

/**
 * Domestic-carrier × 14-day heatmap (up to 10 rows). Cell intensity = number
 * of changes that (carrier, day). Color comes from the carrier's brand color (mvnoBrandColors).
 *
 * Pure presentational — pass `data` from useDashboardData.heatmap.
 * Pass `onCellClick(change)` to navigate when a cell is clicked. Cells with
 * one change navigate immediately; cells with multiple open a picker popover.
 *
 * <ChangeHeatmap data={...} onCellClick={c => ...} />
 */

const CELL_HEIGHT = 22
const CELL_GAP = 2

function dayLabel(iso) {
  const [, mm, dd] = iso.split('-')
  return `${dd}/${mm}`
}

function changeTypeLabel(c) {
  if (c.change_type === 'price_change') {
    return Number(c.new_val) < Number(c.old_val) ? 'ירידת מחיר' : 'עליית מחיר'
  }
  if (c.change_type === 'new_plan') return 'מסלול חדש'
  if (c.change_type === 'removed_plan') return 'הוסר'
  if (c.change_type === 'extras_change') return 'שינוי הטבות'
  if (c.change_type === 'details_change') return 'שינוי פרטים'
  return 'שינוי'
}

function changePriceText(c) {
  if (c.change_type === 'price_change') {
    return `${c.old_val}→${c.new_val}₪`
  }
  if (c.change_type === 'extras_change' || c.change_type === 'details_change') return ''
  const n = Number(c.new_val)
  if (Number.isFinite(n) && n > 0) return `${n}₪`
  return ''
}

function buildTooltip(changes, day) {
  const lines = [
    `${dayLabel(day)} · ${changes.length} ${changes.length === 1 ? 'שינוי' : 'שינויים'}`,
  ]
  for (const c of changes.slice(0, 10)) {
    const label = changeTypeLabel(c)
    const price = changePriceText(c)
    const name = c.plan_name || ''
    lines.push(`• ${label}${price ? ' ' + price : ''} — ${name}`)
  }
  if (changes.length > 10) lines.push(`+ ${changes.length - 10} נוספים`)
  return lines.join('\n')
}

function HeatmapPopover({ popover, onPick }) {
  const { changes, rect } = popover
  const maxWidth = 300
  const cellCenterX = rect.left + rect.width / 2
  const left = Math.max(8, Math.min(window.innerWidth - maxWidth - 8, cellCenterX - maxWidth / 2))
  const top = Math.min(window.innerHeight - 320, rect.bottom + 6)

  return (
    <div
      data-heatmap-popover
      style={{
        position: 'fixed',
        top,
        left,
        zIndex: 1000,
        background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 10,
        boxShadow: 'var(--sh-popover, 0 8px 24px rgba(0,0,0,0.15))',
        padding: 6,
        minWidth: 220,
        maxWidth,
        direction: 'rtl',
      }}
      role="menu"
    >
      <div style={{ padding: '4px 8px 6px', fontSize: 11, color: 'var(--color-moca-muted)', fontWeight: 700 }}>
        {changes.length} שינויים · בחר מסלול
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 280, overflowY: 'auto' }}>
        {changes.map((c, i) => (
          <button
            key={`${c.plan_name}-${c.change_type}-${i}`}
            type="button"
            onClick={() => onPick(c)}
            style={{
              padding: '6px 8px',
              borderRadius: 6,
              cursor: 'pointer',
              display: 'block',
              fontFamily: 'inherit',
              background: 'transparent',
              border: 'none',
              textAlign: 'right',
              width: '100%',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-moca-mist)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
          >
            <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--color-moca-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {c.plan_name}
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', marginTop: 2 }}>
              {changeTypeLabel(c)}{changePriceText(c) ? ' · ' + changePriceText(c) : ''}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

export default function ChangeHeatmap({ data, onCellClick }) {
  const [popover, setPopover] = useState(null)

  useEffect(() => {
    if (!popover) return
    function onDocMouseDown(e) {
      if (e.target.closest && e.target.closest('[data-heatmap-popover]')) return
      setPopover(null)
    }
    function onEsc(e) { if (e.key === 'Escape') setPopover(null) }
    document.addEventListener('mousedown', onDocMouseDown)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocMouseDown)
      document.removeEventListener('keydown', onEsc)
    }
  }, [popover])

  if (!data || data.carriers.length === 0) return null
  const { carriers, days, cells, maxCount } = data

  function handleCellClick(e, cellChanges) {
    if (!cellChanges || cellChanges.length === 0) return
    if (cellChanges.length === 1) {
      onCellClick && onCellClick(cellChanges[0])
      return
    }
    const rect = e.currentTarget.getBoundingClientRect()
    setPopover({ changes: cellChanges, rect })
  }

  function pickFromPopover(c) {
    setPopover(null)
    onCellClick && onCellClick(c)
  }

  return (
    <>
      <section
        className="px-3 py-4 md:px-[18px] md:py-4"
        style={{
          background: 'var(--color-moca-white, #fff)',
          border: '1px solid var(--color-moca-border)',
          borderRadius: 14,
          boxShadow: 'var(--sh-card)',
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
            {days.length} ימים אחרונים · ריחוף לפרטים · לחיצה למסלול
          </span>
        </header>

        <div
          className="grid gap-2 md:gap-2.5 grid-cols-[80px_1fr] md:grid-cols-[minmax(90px,130px)_1fr] items-stretch"
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
                const carrierName = getCarrierName(id)
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
                      const cellChanges = cells.get(`${id}|${d}`) || []
                      const count = cellChanges.length
                      const intensity = maxCount > 0 ? count / maxCount : 0
                      const opacity = count === 0 ? 0.08 : 0.25 + intensity * 0.7
                      const hasChanges = count > 0
                      const tooltip = hasChanges
                        ? `${carrierName}\n${buildTooltip(cellChanges, d)}`
                        : `אין שינויים · ${dayLabel(d)}`
                      return (
                        <button
                          type="button"
                          key={d}
                          title={tooltip}
                          aria-label={tooltip}
                          disabled={!hasChanges}
                          onClick={hasChanges ? (e) => handleCellClick(e, cellChanges) : undefined}
                          style={{
                            height: CELL_HEIGHT,
                            borderRadius: 4,
                            background: count === 0 ? 'var(--color-moca-cream)' : carrierColor,
                            opacity: count === 0 ? 1 : opacity,
                            transition: 'opacity 120ms ease, transform 120ms ease',
                            cursor: hasChanges ? 'pointer' : 'default',
                            border: 'none',
                            padding: 0,
                            margin: 0,
                            display: 'block',
                            width: '100%',
                          }}
                          onMouseEnter={hasChanges ? (e) => { e.currentTarget.style.transform = 'scale(1.08)' } : undefined}
                          onMouseLeave={hasChanges ? (e) => { e.currentTarget.style.transform = 'scale(1)' } : undefined}
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

      {popover && <HeatmapPopover popover={popover} onPick={pickFromPopover} />}
    </>
  )
}
