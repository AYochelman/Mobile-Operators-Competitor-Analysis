import { useMemo } from 'react'
import CarrierChip from './CarrierChip'
import Sparkline from './Sparkline'
import Delta from './Delta'
import { getCarrierColor, getCarrierName } from './carrierMeta'
import { useCarrierPriceTrend } from '../../hooks/useCarrierPriceTrend'

// Shared 5-column grid: [carrier+meta] [sparkline] [min] [avg] [position vs ours]
const GRID_COLS = 'minmax(160px, 1.4fr) 110px 60px 90px 100px'

/**
 * At-a-glance competitive snapshot — one row per carrier.
 *
 * Data is derived from already-loaded dashboard state (plans + changes), so
 * the board doesn't issue any extra API calls. Rows show plan count, average
 * monthly price, cheapest plan, recent change count, and position vs. "ours"
 * (the workspace's mvno_carrier).
 *
 * <CompetitorBoard
 *    plans={plans.domestic}
 *    changes={changes.domestic}
 *    carrierIds={['pelephone', 'cellcom', 'partner', ...]}
 *    oursCarrier={workspace?.mvno_carrier}
 *    onRowClick={(carrierId) => setFilter('carrier', carrierId)}
 * />
 */

function buildSnapshots(plans, carrierIds, changes) {
  const recent24h = Date.now() - 24 * 60 * 60 * 1000
  const recent7d  = Date.now() - 7 * 24 * 60 * 60 * 1000

  // Bucket plans + changes per carrier in a single pass each
  const planBuckets = new Map()
  for (const p of plans || []) {
    if (!p?.carrier) continue
    const arr = planBuckets.get(p.carrier) || []
    arr.push(p)
    planBuckets.set(p.carrier, arr)
  }

  const changeBuckets = new Map()
  for (const c of changes || []) {
    if (!c?.carrier) continue
    const arr = changeBuckets.get(c.carrier) || []
    arr.push(c)
    changeBuckets.set(c.carrier, arr)
  }

  return carrierIds.map((id) => {
    const carrierPlans = planBuckets.get(id) || []
    const prices = carrierPlans
      .map((p) => Number(p.price))
      .filter((n) => Number.isFinite(n) && n > 0)

    const avg = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null
    const min = prices.length ? Math.min(...prices) : null

    const carrierChanges = changeBuckets.get(id) || []
    let changes24h = 0
    let netDelta = 0
    let changes7d = 0
    for (const c of carrierChanges) {
      const ts = c.changed_at ? new Date(c.changed_at).getTime() : 0
      if (ts >= recent7d) changes7d++
      if (ts >= recent24h) {
        changes24h++
        if (c.change_type === 'price_change') {
          const oldVal = Number(c.old_val)
          const newVal = Number(c.new_val)
          if (Number.isFinite(oldVal) && Number.isFinite(newVal)) {
            netDelta += newVal - oldVal
          }
        }
      }
    }

    return {
      carrier: id,
      plans: carrierPlans.length,
      avg: avg != null ? Math.round(avg) : null,
      min,
      changes24h,
      changes7d,
      netDelta24h: Math.round(netDelta),
    }
  })
}

// Trim a long series to the last N points so all sparklines render at a
// consistent visual scale even if some carriers have months of history.
function trimSeries(points, maxPoints = 30) {
  if (!points || points.length <= maxPoints) return points
  return points.slice(points.length - maxPoints)
}

function CompetitorRow({ row, isOurs, oursAvg, onRowClick }) {
  const empty = row.plans === 0
  const trend = useCarrierPriceTrend(row.carrier, 'domestic')
  const sparkData = trend ? trimSeries(trend) : null
  const sparkColor = isOurs ? 'var(--color-moca-bolt)' : getCarrierColor(row.carrier)

  return (
    <button
      type="button"
      onClick={() => onRowClick && !empty && onRowClick(row.carrier)}
      disabled={empty || !onRowClick}
      style={{
        width: '100%',
        display: 'grid',
        gridTemplateColumns: GRID_COLS,
        gap: 10,
        padding: '12px 18px',
        background: isOurs ? 'var(--color-moca-cream)' : 'transparent',
        border: 'none',
        borderBottom: '1px solid var(--color-moca-border)',
        cursor: empty || !onRowClick ? 'default' : 'pointer',
        textAlign: 'right',
        fontFamily: 'inherit',
        color: 'inherit',
        position: 'relative',
        transition: 'background 120ms ease',
        opacity: empty ? 0.5 : 1,
      }}
      onMouseEnter={(e) => {
        if (!isOurs && !empty && onRowClick) e.currentTarget.style.background = 'var(--color-moca-mist)'
      }}
      onMouseLeave={(e) => {
        if (!isOurs && !empty && onRowClick) e.currentTarget.style.background = 'transparent'
      }}
    >
      {isOurs && (
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            insetInlineStart: 0,
            top: 0,
            bottom: 0,
            width: 3,
            background: 'var(--color-moca-bolt)',
          }}
        />
      )}

      {/* Carrier */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <CarrierChip id={row.carrier} size={28} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-moca-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {getCarrierName(row.carrier)}
            {isOurs && (
              <span style={{ color: 'var(--color-moca-bolt)', marginInlineStart: 6, fontSize: 10.5, fontWeight: 700 }}>· שלנו</span>
            )}
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', marginTop: 1 }}>
            {empty
              ? 'אין מסלולים זמינים'
              : `${row.plans} מסלולים${row.changes7d > 0 ? ` · ${row.changes7d} שינויים · 7 ימים` : ''}`}
          </div>
        </div>
      </div>

      {/* Sparkline */}
      <div style={{ alignSelf: 'center', display: 'flex', alignItems: 'center' }}>
        {sparkData && sparkData.length >= 2 ? (
          <Sparkline data={sparkData} color={sparkColor} w={110} h={26} fill strokeWidth={1.6} />
        ) : (
          <span style={{ fontSize: 10, color: 'var(--color-moca-muted)' }}>
            {trend === undefined ? '…' : '—'}
          </span>
        )}
      </div>

      {/* Min price */}
      <div className="tnum" style={{ textAlign: 'left', fontSize: 13, color: 'var(--color-moca-sub)', alignSelf: 'center', direction: 'ltr' }}>
        {row.min != null ? `${row.min}₪` : '—'}
      </div>

      {/* Avg price */}
      <div className="tnum" style={{ textAlign: 'left', alignSelf: 'center' }}>
        <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--color-moca-dark)', direction: 'ltr', letterSpacing: -0.2 }}>
          {row.avg != null ? `${row.avg}₪` : '—'}
        </div>
        {row.netDelta24h !== 0 && (
          <div style={{ marginTop: 2 }}>
            <Delta value={row.netDelta24h} suffix="₪" />
          </div>
        )}
      </div>

      {/* Position vs ours */}
      <div style={{ textAlign: 'left', alignSelf: 'center' }}>
        {isOurs ? (
          <span style={{ fontSize: 10.5, color: 'var(--color-moca-bolt)', fontWeight: 700 }}>BENCHMARK</span>
        ) : (
          <PositionLabel row={row} oursAvg={oursAvg} />
        )}
      </div>
    </button>
  )
}

function PositionLabel({ row, oursAvg }) {
  if (oursAvg == null || row.avg == null || row.carrier === undefined) return null
  if (row.avg === oursAvg) {
    return <span style={{ color: 'var(--color-moca-muted)' }}>—</span>
  }
  const diff = oursAvg - row.avg // positive = competitor is cheaper than us = bad for us
  const cheaper = diff > 0
  return (
    <span
      className="tnum"
      style={{
        fontSize: 11,
        fontWeight: 700,
        color: cheaper ? 'var(--color-moca-up)' : 'var(--color-moca-down)',
      }}
    >
      {cheaper ? `זול ב-${diff}₪` : `יקר ב-${-diff}₪`}
    </span>
  )
}

export default function CompetitorBoard({
  plans,
  changes,
  carrierIds,
  oursCarrier,
  onRowClick,
  title = 'סקירה תחרותית',
  subtitle = 'תמונת מצב לפי מתחרה — מבוסס על המסלולים שכרגע על המסך',
}) {
  const snapshots = useMemo(
    () => buildSnapshots(plans, carrierIds, changes),
    [plans, carrierIds, changes],
  )

  const oursRow = snapshots.find((s) => s.carrier === oursCarrier)
  const oursAvg = oursRow?.avg ?? null

  // Sort: ours first, then cheapest avg, nulls last
  const sorted = [...snapshots].sort((a, b) => {
    if (a.carrier === oursCarrier) return -1
    if (b.carrier === oursCarrier) return 1
    if (a.avg == null) return 1
    if (b.avg == null) return -1
    return a.avg - b.avg
  })

  const hasAnyData = snapshots.some((s) => s.plans > 0)
  if (!hasAnyData) return null

  return (
    <section
      style={{
        background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 14,
        boxShadow: 'var(--sh-card)',
        marginBottom: 22,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <header
        style={{
          padding: '14px 18px 12px',
          borderBottom: '1px solid var(--color-moca-border)',
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div
            style={{
              fontSize: 9.5,
              color: 'var(--color-moca-muted)',
              fontWeight: 800,
              letterSpacing: 0.6,
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            ניטור · חבילות סלולר
          </div>
          <h2
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 18,
              fontWeight: 800,
              color: 'var(--color-moca-dark)',
              margin: 0,
              letterSpacing: -0.3,
            }}
          >
            {title}
          </h2>
          {subtitle && (
            <p style={{ fontSize: 12, color: 'var(--color-moca-sub)', margin: '4px 0 0' }}>
              {subtitle}
            </p>
          )}
        </div>
        {oursAvg != null && (
          <div className="tnum" style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 0.4, textTransform: 'uppercase' }}>
              ממוצע שלך
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--color-moca-bolt)', direction: 'ltr', letterSpacing: -0.4 }}>
              {oursAvg}₪
            </div>
          </div>
        )}
      </header>

      {/* Column headers */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: GRID_COLS,
          gap: 10,
          padding: '8px 18px',
          borderBottom: '1px solid var(--color-moca-border)',
          background: 'var(--color-moca-mist)',
          fontSize: 10,
          fontWeight: 800,
          color: 'var(--color-moca-muted)',
          letterSpacing: 0.4,
          textTransform: 'uppercase',
        }}
      >
        <span>מתחרה</span>
        <span>מגמת מחיר</span>
        <span style={{ textAlign: 'left' }}>מ-</span>
        <span style={{ textAlign: 'left' }}>ממוצע</span>
        <span style={{ textAlign: 'left' }}>ביחס לשלך</span>
      </div>

      {/* Rows */}
      <div>
        {sorted.map((row) => (
          <CompetitorRow
            key={row.carrier}
            row={row}
            isOurs={row.carrier === oursCarrier}
            oursAvg={oursAvg}
            onRowClick={onRowClick}
          />
        ))}
      </div>
    </section>
  )
}
