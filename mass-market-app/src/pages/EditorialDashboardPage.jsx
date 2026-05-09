import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { useWatchlist } from '../hooks/useWatchlist'
import { useDashboardData } from '../hooks/useDashboardData'
import { DOMESTIC_LABELS, carrierLabel } from '../data/carrierLabels'
import {
  CarrierChip,
  EditorialHero,
  KpiCard,
  ChangeHeatmap,
  Tag,
} from '../components/moca'
import { getCarrierColor, getCarrierName } from '../components/moca/carrierMeta'
import Spinner from '../components/ui/Spinner'

/**
 * Editorial Deep dashboard — the new "/" route per the design's flagship
 * variant (v4 in DEFAULT_VARIANTS). Composes EditorialHero + KPI row +
 * ChangeHeatmap + Watchlist + Recent-changes feed + "ours" pinned chip.
 *
 * Backwards compat: legacy `?tab=X` URLs land here, which would break the
 * old behaviour. We detect that on mount and redirect to the matching
 * clean route (added in phase 9).
 */

const TAB_TO_PATH = {
  domestic:  '/plans',
  abroad:    '/roaming',
  global:    '/esim',
  banners:   '/banners',
  history:   '/history',
}

const FILTERS = [
  { id: 'all',     label: 'הכל',           predicate: () => true },
  { id: 'down',    label: 'הזולות',         predicate: (c) => isPriceDown(c) },
  { id: 'new',     label: 'חדשים',          predicate: (c) => c.change_type === 'new_plan' },
  { id: 'up',      label: 'עליות',           predicate: (c) => isPriceUp(c) },
  { id: 'high',    label: 'השפעה גבוה',     predicate: (c) => priceImpact(c) >= 10 },
]

function isPriceDown(c) {
  if (c?.change_type !== 'price_change') return false
  return Number(c.new_val) < Number(c.old_val)
}
function isPriceUp(c) {
  if (c?.change_type !== 'price_change') return false
  return Number(c.new_val) > Number(c.old_val)
}
function priceImpact(c) {
  if (c?.change_type === 'new_plan' || c?.change_type === 'removed_plan') return 100
  if (c?.change_type !== 'price_change') return 0
  const o = Number(c.old_val)
  const n = Number(c.new_val)
  if (!Number.isFinite(o) || !Number.isFinite(n) || o <= 0) return 0
  return Math.abs((n - o) / o) * 100
}
function fmtAgo(iso) {
  if (!iso) return ''
  const ms = Date.now() - new Date(iso).getTime()
  const h = Math.floor(ms / (60 * 60 * 1000))
  if (h < 1) return 'הרגע'
  if (h < 24) return `לפני ${h} שעות`
  const d = Math.floor(h / 24)
  return d === 1 ? 'אתמול' : `לפני ${d} ימים`
}

/** Recent-changes feed with filter pills. */
function ChangeFeed({ changes, onItemClick }) {
  const [filter, setFilter] = useState('all')
  const filtered = useMemo(() => {
    const pred = FILTERS.find((f) => f.id === filter)?.predicate || (() => true)
    return changes.filter(pred).slice(0, 12)
  }, [changes, filter])

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
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
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
          שינויים אחרונים
        </h2>
        <span style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>לחץ על כל שורה לפרטים</span>
      </header>

      {/* Filter pills */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {FILTERS.map((f) => {
          const active = filter === f.id
          const matches = changes.filter(f.predicate).length
          return (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              style={{
                padding: '4px 10px',
                borderRadius: 999,
                border: '1px solid var(--color-moca-border)',
                background: active ? 'var(--color-moca-bolt)' : 'transparent',
                color: active ? '#fff' : 'var(--color-moca-text)',
                fontSize: 11.5,
                fontWeight: active ? 700 : 500,
                cursor: 'pointer',
                fontFamily: 'inherit',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              {f.label}
              <span className="tnum" style={{ opacity: 0.7, fontSize: 10 }}>· {matches}</span>
            </button>
          )
        })}
      </div>

      {/* Items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {filtered.length === 0 && (
          <div style={{ padding: '20px 12px', textAlign: 'center', color: 'var(--color-moca-muted)', fontSize: 13 }}>
            אין שינויים בקטגוריה זו
          </div>
        )}
        {filtered.map((c, i) => {
          const oldVal = Number(c.old_val)
          const newVal = Number(c.new_val)
          const isHot = priceImpact(c) >= 10
          const isNew = c.change_type === 'new_plan'
          const isUp = isPriceUp(c)

          return (
            <button
              key={`${c.carrier}-${c.plan_name}-${c.changed_at}-${i}`}
              onClick={() => onItemClick && onItemClick(c)}
              style={{
                display: 'grid',
                gridTemplateColumns: '40px 1fr 100px 90px',
                gap: 12,
                alignItems: 'center',
                padding: '10px 8px',
                borderTop: i === 0 ? 'none' : '1px solid var(--color-moca-border)',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'right',
                fontFamily: 'inherit',
                width: '100%',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-moca-mist)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              <div className="tnum" style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 700, direction: 'ltr', textAlign: 'left' }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  <CarrierChip id={c.carrier} size={20} showName />
                  <span style={{ color: 'var(--color-moca-muted)' }}>·</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-moca-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {c.plan_name}
                  </span>
                  {isHot && <Tag color="var(--color-moca-hot)">HOT</Tag>}
                  {isNew && <Tag color="var(--color-moca-down)">NEW</Tag>}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>
                  {c.change_type === 'price_change' && (isUp ? 'עליית מחיר' : 'ירידת מחיר')}
                  {c.change_type === 'new_plan' && 'מסלול חדש'}
                  {c.change_type === 'removed_plan' && 'הוסר'}
                  {c.change_type === 'extras_change' && 'שינוי הטבות'}
                </div>
              </div>
              <div className="tnum" style={{ direction: 'ltr', textAlign: 'left' }}>
                {Number.isFinite(newVal) && (
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, justifyContent: 'flex-end' }}>
                    {Number.isFinite(oldVal) && c.change_type === 'price_change' && (
                      <span style={{ fontSize: 11, color: 'var(--color-moca-muted)', textDecoration: 'line-through' }}>{oldVal}₪</span>
                    )}
                    <span style={{ fontSize: 16, fontWeight: 800, color: isUp ? 'var(--color-moca-up)' : 'var(--color-moca-down)', letterSpacing: -0.2 }}>
                      {newVal}₪
                    </span>
                  </div>
                )}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', textAlign: 'left' }}>
                {fmtAgo(c.changed_at)}
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

/** Watchlist sidebar — shows the user's pinned plans. */
function WatchlistSidebar({ plans }) {
  const { items } = useWatchlist()
  if (!items || items.length === 0) {
    return (
      <section
        style={{
          background: 'var(--color-moca-white, #fff)',
          border: '1px solid var(--color-moca-border)',
          borderRadius: 14,
          boxShadow: 'var(--sh-card)',
          padding: '16px 18px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 8 }}>
          ★ Watchlist
        </div>
        <p style={{ fontSize: 12, color: 'var(--color-moca-sub)', margin: 0 }}>
          אין מסלולים במעקב. סמן ★ על מסלול בעמוד "השוואת מסלולים" כדי להוסיף.
        </p>
      </section>
    )
  }
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 800, color: 'var(--color-moca-dark)', margin: 0 }}>
          ★ Watchlist
        </h3>
        <span className="tnum" style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>{items.length}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.slice(0, 6).map((it, idx) => {
          const live = plans.find((p) => p.carrier === it.carrier && p.plan_name === it.plan_name)
          return (
            <div
              key={`${it.carrier}-${it.plan_name}-${idx}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 10px',
                background: 'var(--color-moca-mist)',
                borderRadius: 10,
              }}
            >
              <CarrierChip id={it.carrier} size={20} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-moca-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {it.plan_name}
                </div>
              </div>
              {live?.price != null && (
                <span className="tnum" style={{ fontSize: 12, fontWeight: 800, color: 'var(--color-moca-bolt)', direction: 'ltr' }}>
                  {live.price}₪
                </span>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

/** Bottom-right pinned "ours" chip per the design. Always visible:
 *  - With carrier: shows the workspace's mvno_carrier as a permanent reminder
 *  - Without carrier: invites the user to configure mvno_carrier (admin only,
 *    so non-admin users don't get a dead CTA). */
function OursPinned({ carrierId, isAdmin }) {
  const navigate = useNavigate()

  // Same fixed positioning for both states. RTL: insetInlineStart = right edge.
  const baseStyle = {
    position: 'fixed',
    insetBlockEnd: 16,
    insetInlineStart: 16,
    zIndex: 30,
    background: 'var(--color-moca-white, #fff)',
    border: '1px solid var(--color-moca-border)',
    borderRadius: 999,
    padding: '8px 14px 8px 12px',
    boxShadow: 'var(--sh-card-hover)',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 10,
    fontFamily: 'inherit',
    color: 'inherit',
    textAlign: 'inherit',
  }

  if (!carrierId) {
    if (!isAdmin) return null  // viewers without carrier — no dead CTA
    return (
      <button
        type="button"
        onClick={() => navigate('/workspace/settings')}
        title="הגדר את הספק שלי כדי לראות אותו מודגש בכל מקום"
        style={{ ...baseStyle, cursor: 'pointer', border: '1px dashed var(--color-moca-border)' }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 26,
            height: 26,
            borderRadius: 999,
            background: 'var(--color-moca-cream)',
            color: 'var(--color-moca-bolt)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            fontWeight: 700,
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          +
        </span>
        <div>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--color-moca-bolt)' }}>
            הגדר ספק שלי
          </div>
          <div style={{ fontSize: 9.5, color: 'var(--color-moca-muted)', fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase' }}>
            לחץ להגדרה
          </div>
        </div>
      </button>
    )
  }

  return (
    <div style={baseStyle}>
      <CarrierChip id={carrierId} size={26} />
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-moca-dark)' }}>
          {getCarrierName(carrierId)}
        </div>
        <div style={{ fontSize: 9.5, color: 'var(--color-moca-muted)', fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase' }}>
          הספק שלי
        </div>
      </div>
    </div>
  )
}

export default function EditorialDashboardPage() {
  const { workspace, isAdmin } = useAuth()
  const flags = useFeatureFlags()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Legacy /?tab=X URL → redirect to clean route (phase 9).
  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab && TAB_TO_PATH[tab]) {
      const carrier = searchParams.get('carrier')
      const highlight = searchParams.get('highlight')
      let qs = ''
      if (carrier || highlight) {
        const p = new URLSearchParams()
        if (carrier) p.set('carrier', carrier)
        if (highlight) p.set('highlight', highlight)
        qs = `?${p.toString()}`
      }
      navigate(`${TAB_TO_PATH[tab]}${qs}`, { replace: true })
    }
  }, [searchParams, navigate])

  const oursCarrier = workspace?.mvno_carrier
  const allDomestic = useMemo(() => Object.keys(DOMESTIC_LABELS), [])
  const visibleCarriers = useVisibleCarriers(allDomestic)

  // For the heatmap we want a stable 8-carrier set — domestic only, visible to this workspace
  const heatmapCarriers = useMemo(
    () => visibleCarriers.slice(0, 8),
    [visibleCarriers],
  )

  const { loading, plans, leadChange, kpis, heatmap, recentChanges } =
    useDashboardData(oursCarrier, heatmapCarriers)

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  return (
    <div>
      {/* Editorial hero — full-bleed top */}
      <EditorialHero leadChange={leadChange} oursCarrier={oursCarrier} />

      <div className="max-w-[1320px] mx-auto px-6 py-6 pb-20 md:pb-6 flex flex-col gap-5">
        {/* KPI strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard
            label="שינויים היום"
            value={kpis.changesToday}
            delta={kpis.changesDelta}
          />
          <KpiCard
            label="מחיר ממוצע"
            value={kpis.avgPrice != null ? `${kpis.avgPrice}₪` : '—'}
            delta={kpis.avgPriceDelta}
            neutral={kpis.avgPriceDelta == null}
          />
          <KpiCard
            label="מסלולים חדשים · שבוע"
            value={kpis.newPlans}
            delta={kpis.newPlansDelta}
          />
          {oursCarrier && kpis.oursVsMarketPct != null ? (
            <KpiCard
              label={`${getCarrierName(oursCarrier)} vs שוק`}
              value={`${kpis.oursVsMarketPct > 0 ? '+' : ''}${kpis.oursVsMarketPct}%`}
              neutral
              accent={kpis.oursVsMarketPct > 0 ? 'var(--color-moca-up)' : 'var(--color-moca-down)'}
            />
          ) : (
            <KpiCard label="ספק שלך" value="—" neutral note="הגדר workspace.mvno_carrier" />
          )}
        </div>

        {/* Heatmap + Watchlist row */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-5">
          <ChangeHeatmap data={heatmap} />
          <WatchlistSidebar plans={plans} />
        </div>

        {/* Recent changes feed */}
        <ChangeFeed
          changes={recentChanges}
          onItemClick={(c) => {
            navigate(`/plans?carrier=${c.carrier}&highlight=${encodeURIComponent(c.plan_name || '')}`)
          }}
        />
      </div>

      {/* Pinned "ours" chip */}
      <OursPinned carrierId={oursCarrier} isAdmin={isAdmin} />
    </div>
  )
}
