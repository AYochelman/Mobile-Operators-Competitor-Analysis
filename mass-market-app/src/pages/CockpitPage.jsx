import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot,
} from 'recharts'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'
import { useCockpitData } from '../hooks/useCockpitData'
import { CarrierChip, PageHeader, Delta, MyCarrierModal } from '../components/moca'
import { getCarrierName } from '../components/moca/carrierMeta'
import Spinner from '../components/ui/Spinner'

/**
 * /cockpit — the executive (סמנכ"ל) situation room.
 *
 * One screen that answers four questions and nothing else:
 *   1. Where do we stand?      → verdict bar + positioning ladder
 *   2. What moved that matters? → material moves, impact-ranked
 *   3. Where is the risk?       → threat / opportunity / attention signals
 *   4. Can I trust this?        → data freshness footer
 *
 * Deliberately NOT another feed. /"/" (EditorialDashboardPage) is the
 * analyst's activity view; this page ranks by business impact and hides
 * everything below the threshold. Reads only existing endpoints — the whole
 * data layer lives in hooks/useCockpitData.js.
 */

// ── chart palette ────────────────────────────────────────────────────────
// Validated with the dataviz skill's validate_palette.js against the white
// card surface. Findings that shaped these choices:
//   · #c9622f  → PASSES every check as a SINGLE emphasis hue.
//   · Any second warm brown paired with it FAILS the normal-vision floor
//     (ΔE ~12, needs ≥15) — the mocha family is all one hue, so two browns
//     can never be two categorical series.
// Hence: one colored series (ours) + the market as a DASHED NEUTRAL
// reference line, which is chrome rather than a categorical peer, plus a
// single-hue ladder where length carries the magnitude and only "ours" is
// tinted. No rank-coloured ramp anywhere.
const CV = {
  ours: '#5c3317',   // brand bolt — single high-contrast series line
  ref: '#a99680',    // market median — dashed, recessive, direct-labelled
  bar: '#cdb69b',    // ladder bars: neutral, magnitude is the length
  barOurs: '#c9622f',// validated emphasis hue, only ever on our own bar
  grid: '#efe6da',
}

const WINDOWS = [7, 30, 90]

function fmtPpgb(n) {
  return Number.isFinite(n) ? `₪${n.toFixed(2)}` : '—'
}
function fmtDay(iso, lang) {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  return lang === 'he' ? `${Number(d)}.${Number(m)}` : `${Number(m)}/${Number(d)}`
}
function fmtAgo(hours, tt) {
  if (hours == null) return tt('אין נתונים', 'no data')
  if (hours < 1) return tt('הרגע', 'just now')
  if (hours < 24) return tt(`לפני ${hours} שעות`, `${hours}h ago`)
  const d = Math.round(hours / 24)
  return d === 1 ? tt('אתמול', 'yesterday') : tt(`לפני ${d} ימים`, `${d}d ago`)
}

// ── shared shells ────────────────────────────────────────────────────────

function Card({ title, hint, children, pad = 18, style }) {
  return (
    <section
      style={{
        background: '#fff',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 16,
        boxShadow: 'var(--sh-card)',
        padding: pad,
        minWidth: 0,
        ...style,
      }}
    >
      {(title || hint) && (
        <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 14 }}>
          {title && (
            <h2 style={{
              margin: 0, fontSize: 13.5, fontWeight: 800,
              color: 'var(--color-moca-dark)', letterSpacing: -0.2,
            }}>{title}</h2>
          )}
          {hint && (
            <span style={{ fontSize: 11, color: 'var(--color-moca-muted)', marginInlineStart: 'auto' }}>
              {hint}
            </span>
          )}
        </header>
      )}
      {children}
    </section>
  )
}

function Empty({ children }) {
  return (
    <div style={{
      padding: '22px 8px', textAlign: 'center', fontSize: 12.5,
      color: 'var(--color-moca-muted)', lineHeight: 1.6,
    }}>
      {children}
    </div>
  )
}

function Stat({ label, value, sub, delta, deltaSuffix = '%', accent }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid var(--color-moca-border)',
      borderRadius: 14, padding: '13px 15px', boxShadow: 'var(--sh-card)', minWidth: 0,
    }}>
      <div style={{
        fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800,
        letterSpacing: 0.5, textTransform: 'uppercase',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 7 }}>
        <span className="tnum" style={{
          fontSize: 25, fontWeight: 800, lineHeight: 1.05,
          color: accent || 'var(--color-moca-dark)', letterSpacing: -0.6, direction: 'ltr',
        }}>{value}</span>
        {delta != null && <Delta value={delta} suffix={deltaSuffix} />}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: 'var(--color-moca-sub)', marginTop: 5, lineHeight: 1.45 }}>
          {sub}
        </div>
      )}
    </div>
  )
}

// ── 1. verdict ───────────────────────────────────────────────────────────

/**
 * The single sentence the exec reads first. Never invents a position: with no
 * mvno_carrier set it states the market instead and offers the one-click fix.
 */
function VerdictBar({ data, oursCarrier, days, onPickCarrier, canPickCarrier }) {
  const { tt, lang } = useLang()
  const { ladderInfo, activity } = data
  const { rank, total, ours, vsMedianPct, cheapest, marketMedian } = ladderInfo

  const activityClause = tt(
    `${activity.drops} הורדות מחיר ו-${activity.newPlans} השקות ב-${days} הימים האחרונים`,
    `${activity.drops} price cuts and ${activity.newPlans} launches in the last ${days} days`,
  )

  let headline
  if (ours && rank) {
    const cheaper = vsMedianPct != null && vsMedianPct < 0
    const gap = vsMedianPct == null ? null : Math.abs(vsMedianPct).toFixed(0)
    headline = (
      <>
        {getCarrierName(oursCarrier)}{' '}
        <strong style={{ fontWeight: 800 }}>
          {tt(`במקום ${rank} מתוך ${total}`, `ranked ${rank} of ${total}`)}
        </strong>{' '}
        {tt('במדד ₪/GB', 'on the ₪/GB index')}
        {gap != null && (
          <>
            {' — '}
            <span style={{ color: cheaper ? 'var(--color-moca-down)' : 'var(--color-moca-up)', fontWeight: 700 }}>
              {gap}% {cheaper ? tt('זול', 'below') : tt('יקר', 'above')}
            </span>{' '}
            {tt('מחציון השוק', 'the market median')}
          </>
        )}.
      </>
    )
  } else {
    headline = (
      <>
        {tt('חציון השוק עומד על', 'The market median sits at')}{' '}
        <strong style={{ fontWeight: 800, direction: 'ltr', display: 'inline-block' }}>
          {fmtPpgb(marketMedian)}/GB
        </strong>
        {cheapest && (
          <>
            {' · '}{tt('המוביל', 'led by')} {getCarrierName(cheapest.carrier)}{' '}
            <span style={{ direction: 'ltr', display: 'inline-block' }}>{fmtPpgb(cheapest.ppgb)}/GB</span>
          </>
        )}.
      </>
    )
  }

  return (
    <div style={{
      background: 'linear-gradient(135deg, #fffdfa 0%, var(--color-moca-cream) 100%)',
      border: '1px solid var(--color-moca-border)',
      borderRadius: 16, padding: '18px 20px', boxShadow: 'var(--sh-card)',
      display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
    }}>
      {ours && <CarrierChip id={oursCarrier} size={38} ours />}
      <div style={{ flex: 1, minWidth: 260 }}>
        <div style={{
          fontSize: 10, fontWeight: 800, letterSpacing: 0.6,
          textTransform: 'uppercase', color: 'var(--color-moca-muted)', marginBottom: 5,
        }}>
          {tt('שורה תחתונה', 'Bottom line')}
        </div>
        <p style={{
          margin: 0, fontSize: 17, lineHeight: 1.5,
          color: 'var(--color-moca-dark)', fontWeight: 500, textWrap: 'pretty',
        }}>
          {headline}
        </p>
        <p style={{ margin: '6px 0 0', fontSize: 12.5, color: 'var(--color-moca-sub)' }}>
          {activityClause}
        </p>
      </div>
      {!ours && canPickCarrier && (
        <button
          onClick={onPickCarrier}
          style={{
            background: 'var(--color-moca-bolt)', color: '#fff', border: 'none',
            borderRadius: 10, padding: '9px 15px', fontSize: 12.5,
            fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap',
          }}
        >
          {tt('הגדר את הספק שלי', 'Set my carrier')}
        </button>
      )}
      {!ours && !canPickCarrier && (
        <span style={{ fontSize: 11.5, color: 'var(--color-moca-muted)', maxWidth: 200, lineHeight: 1.5 }}>
          {lang === 'he'
            ? 'לתצוגה יחסית — בקשו ממנהל המערכת להגדיר את הספק שלכם'
            : 'For a relative view, ask an admin to set your carrier'}
        </span>
      )}
    </div>
  )
}

// ── 2. trend chart ───────────────────────────────────────────────────────

function TrendTooltip({ active, payload, label, tt, lang }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#fff', border: '1px solid var(--color-moca-border)',
      borderRadius: 10, padding: '9px 12px', boxShadow: 'var(--sh-popover)',
      fontSize: 12, direction: lang === 'he' ? 'rtl' : 'ltr',
    }}>
      <div style={{ fontWeight: 800, marginBottom: 6, color: 'var(--color-moca-dark)' }}>
        {fmtDay(label, lang)}
      </div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 3 }}>
          <span style={{
            width: 9, height: 9, borderRadius: 2, flexShrink: 0,
            background: p.dataKey === 'ours' ? CV.ours : CV.ref,
          }} />
          <span style={{ color: 'var(--color-moca-sub)' }}>
            {p.dataKey === 'ours' ? tt('אנחנו', 'Us') : tt('חציון השוק', 'Market median')}
          </span>
          <span className="tnum" style={{
            fontWeight: 800, color: 'var(--color-moca-dark)',
            marginInlineStart: 'auto', direction: 'ltr',
          }}>
            {fmtPpgb(p.value)}
          </span>
        </div>
      ))}
    </div>
  )
}

function LegendSwatch({ dashed, color, label, value, delta }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 11.5 }}>
      <svg width="20" height="8" aria-hidden="true" style={{ flexShrink: 0 }}>
        <line
          x1="0" y1="4" x2="20" y2="4" stroke={color} strokeWidth="2.5"
          strokeDasharray={dashed ? '4 3' : undefined} strokeLinecap="round"
        />
      </svg>
      <span style={{ color: 'var(--color-moca-sub)' }}>{label}</span>
      {value != null && (
        <span className="tnum" style={{ fontWeight: 800, color: 'var(--color-moca-dark)', direction: 'ltr' }}>
          {fmtPpgb(value)}
        </span>
      )}
      {delta != null && <Delta value={delta} suffix="%" />}
    </span>
  )
}

function TrendCard({ data, oursCarrier, days }) {
  const { tt, lang } = useLang()
  const { trend, marketTrendPct, oursTrendPct } = data

  const last = trend.length ? trend[trend.length - 1] : null
  const lastOurs = useMemo(() => {
    for (let i = trend.length - 1; i >= 0; i--) if (Number.isFinite(trend[i].ours)) return trend[i]
    return null
  }, [trend])

  return (
    <Card
      title={tt('מדד המחיר בשוק', 'Market price index')}
      hint={tt(`₪/GB · ${days} ימים`, `₪/GB · ${days} days`)}
    >
      {trend.length < 2 ? (
        <Empty>
          {tt(
            'אין עדיין מספיק נקודות היסטוריה לתקופה הזו. הטבלה היומית נבנית ב-08:50 וב-18:30.',
            'Not enough daily history for this window yet. The daily table is built at 08:50 and 18:30.',
          )}
        </Empty>
      ) : (
        <>
          <div style={{
            display: 'flex', gap: 18, flexWrap: 'wrap',
            marginBottom: 12, alignItems: 'center',
          }}>
            {oursCarrier && lastOurs && (
              <LegendSwatch
                color={CV.ours}
                label={getCarrierName(oursCarrier)}
                value={lastOurs.ours}
                delta={oursTrendPct}
              />
            )}
            <LegendSwatch
              dashed
              color={CV.ref}
              label={tt('חציון השוק', 'Market median')}
              value={last?.market}
              delta={marketTrendPct}
            />
          </div>

          {/* LTR wrapper: a time axis reads left→right even inside the RTL shell. */}
          <div style={{ direction: 'ltr', width: '100%', height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 8, right: 14, left: -8, bottom: 0 }}>
                <CartesianGrid stroke={CV.grid} vertical={false} />
                <XAxis
                  dataKey="day"
                  tickFormatter={(d) => fmtDay(d, lang)}
                  tick={{ fontSize: 10.5, fill: 'var(--color-moca-muted)' }}
                  axisLine={{ stroke: CV.grid }}
                  tickLine={false}
                  minTickGap={28}
                />
                <YAxis
                  tick={{ fontSize: 10.5, fill: 'var(--color-moca-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                  tickFormatter={(v) => `₪${v}`}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  content={<TrendTooltip tt={tt} lang={lang} />}
                  cursor={{ stroke: 'var(--color-moca-sand)', strokeWidth: 1 }}
                />
                {/* Market = dashed neutral reference, not a categorical peer. */}
                <Line
                  type="monotone" dataKey="market" stroke={CV.ref} strokeWidth={2}
                  strokeDasharray="5 4" dot={false} activeDot={{ r: 4, fill: CV.ref }}
                  isAnimationActive={false} name="market"
                />
                {oursCarrier && (
                  <Line
                    type="monotone" dataKey="ours" stroke={CV.ours} strokeWidth={2.5}
                    dot={false} connectNulls
                    activeDot={{ r: 5, fill: CV.ours, stroke: '#fff', strokeWidth: 2 }}
                    isAnimationActive={false} name="ours"
                  />
                )}
                {/* Direct label anchor on the latest point (≤4 series rule). */}
                {last && (
                  <ReferenceDot
                    x={last.day} y={last.market} r={3}
                    fill={CV.ref} stroke="#fff" strokeWidth={1.5} isFront
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p style={{ margin: '10px 0 0', fontSize: 11, color: 'var(--color-moca-muted)', lineHeight: 1.5 }}>
            {tt(
              'ההצעה הזולה ביותר (₪/GB) של כל מפעיל, חציון על פני השוק. ימים שבהם דיווחו פחות משלושה מפעילים מושמטים.',
              "Each carrier's cheapest ₪/GB offer, median across the market. Days with fewer than three reporting carriers are dropped.",
            )}
          </p>
        </>
      )}
    </Card>
  )
}

// ── 3. material moves ────────────────────────────────────────────────────

const SCOPE_LABEL = {
  domestic: { he: 'סלולר', en: 'Domestic' },
  abroad: { he: 'חו״ל', en: 'Roaming' },
  global: { he: 'eSIM', en: 'eSIM' },
}

function MoversCard({ data, oursCarrier, days }) {
  const { tt, lang } = useLang()
  const navigate = useNavigate()
  const movers = data.movers || []

  return (
    <Card
      title={tt('מהלכים מהותיים', 'Material moves')}
      hint={tt(`שינוי מעל 5% · ${days} ימים`, `>5% change · ${days} days`)}
    >
      {!movers.length ? (
        <Empty>{tt('לא נרשמו שינויי מחיר מהותיים בתקופה.', 'No material price moves in this window.')}</Empty>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {movers.slice(0, 6).map((m) => {
            const isOurs = oursCarrier && m.carrier === oursCarrier
            const scope = SCOPE_LABEL[m.plan_type]
            return (
              <li
                key={`${m.carrier}|${m.plan_name}|${m.plan_type}`}
                style={{
                  display: 'flex', alignItems: 'center', gap: 11,
                  padding: '9px 10px', borderRadius: 10,
                  background: isOurs ? 'rgba(201, 98, 47, 0.07)' : 'transparent',
                  boxShadow: isOurs ? 'inset 0 0 0 1px rgba(201, 98, 47, 0.22)' : 'none',
                }}
              >
                <CarrierChip id={m.carrier} size={26} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 12.5, fontWeight: 700, color: 'var(--color-moca-dark)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {m.plan_name}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', marginTop: 2 }}>
                    {getCarrierName(m.carrier)}
                    {scope && <> · {lang === 'he' ? scope.he : scope.en}</>}
                    {isOurs && <> · <strong style={{ color: 'var(--color-moca-hot-text)' }}>{tt('אנחנו', 'us')}</strong></>}
                  </div>
                </div>
                <span className="tnum" style={{
                  fontSize: 11.5, color: 'var(--color-moca-sub)',
                  direction: 'ltr', whiteSpace: 'nowrap',
                }}>
                  {Math.round(m.old_price)}₪ → <strong style={{ color: 'var(--color-moca-dark)' }}>{Math.round(m.new_price)}₪</strong>
                </span>
                <Delta value={m.pct_change} suffix="%" />
              </li>
            )
          })}
        </ul>
      )}
      <button
        onClick={() => navigate('/history')}
        style={{
          marginTop: 12, background: 'transparent', border: 'none', padding: 0,
          color: 'var(--color-moca-bolt)', fontSize: 12, fontWeight: 700, cursor: 'pointer',
        }}
      >
        {tt('כל היסטוריית השינויים ←', 'Full change history →')}
      </button>
    </Card>
  )
}

// ── 4. positioning ladder ────────────────────────────────────────────────

function LadderCard({ data, oursCarrier }) {
  const { tt } = useLang()
  const { ladder, marketMedian } = data.ladderInfo
  if (!ladder.length) {
    return (
      <Card title={tt('סולם המיצוב', 'Positioning ladder')}>
        <Empty>{tt('אין נתוני מחיר זמינים.', 'No price data available.')}</Empty>
      </Card>
    )
  }

  const max = ladder[ladder.length - 1].ppgb

  return (
    <Card
      title={tt('סולם המיצוב', 'Positioning ladder')}
      hint={tt('₪/GB משוקלל', 'Weighted ₪/GB')}
    >
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 7 }}>
        {ladder.map((row, i) => {
          const isOurs = oursCarrier && row.carrier === oursCarrier
          const pct = max > 0 ? Math.max(3, (row.ppgb / max) * 100) : 0
          return (
            <li
              key={row.carrier}
              title={`${getCarrierName(row.carrier)} · ${fmtPpgb(row.ppgb)}/GB · ${row.plans} ${tt('חבילות', 'plans')}`}
              style={{ display: 'flex', alignItems: 'center', gap: 10 }}
            >
              <span className="tnum" style={{
                fontSize: 10, color: 'var(--color-moca-muted)', width: 14,
                textAlign: 'center', flexShrink: 0, fontWeight: 700,
              }}>{i + 1}</span>
              <span style={{
                fontSize: 11.5, width: 78, flexShrink: 0,
                fontWeight: isOurs ? 800 : 600,
                color: isOurs ? 'var(--color-moca-hot-text)' : 'var(--color-moca-text)',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {getCarrierName(row.carrier)}
              </span>
              {/* Logical inset keeps the fill anchored to the RTL start edge. */}
              <span style={{
                position: 'relative', flex: 1, height: 9,
                background: 'var(--color-moca-cream)', borderRadius: 999, minWidth: 40,
              }}>
                <span style={{
                  position: 'absolute', insetInlineStart: 0, top: 0, bottom: 0,
                  width: `${pct}%`, borderRadius: 999,
                  background: isOurs ? CV.barOurs : CV.bar,
                }} />
              </span>
              <span className="tnum" style={{
                fontSize: 11.5, width: 48, textAlign: 'end', flexShrink: 0, direction: 'ltr',
                fontWeight: isOurs ? 800 : 600,
                color: isOurs ? 'var(--color-moca-hot-text)' : 'var(--color-moca-sub)',
              }}>
                {row.ppgb.toFixed(2)}
              </span>
            </li>
          )
        })}
      </ul>
      {marketMedian != null && (
        <p style={{ margin: '12px 0 0', fontSize: 11, color: 'var(--color-moca-muted)' }}>
          {tt('חציון השוק', 'Market median')}:{' '}
          <strong className="tnum" style={{ color: 'var(--color-moca-sub)', direction: 'ltr', display: 'inline-block' }}>
            {fmtPpgb(marketMedian)}/GB
          </strong>
        </p>
      )}
    </Card>
  )
}

// ── 5. signals ───────────────────────────────────────────────────────────

function SignalCard({ tone, kicker, title, body }) {
  const tint = {
    threat: { bg: 'rgba(180, 71, 45, 0.06)', bar: 'var(--color-moca-up)', ink: '#9a3320' },
    opportunity: { bg: 'rgba(74, 124, 63, 0.07)', bar: 'var(--color-moca-down)', ink: '#3f6c34' },
    attention: { bg: 'rgba(201, 98, 47, 0.07)', bar: 'var(--color-moca-hot)', ink: 'var(--color-moca-hot-text)' },
    calm: { bg: 'var(--color-moca-mist, #faf5ee)', bar: 'var(--color-moca-sand)', ink: 'var(--color-moca-sub)' },
  }[tone] || {}
  return (
    <div style={{
      background: tint.bg, border: '1px solid var(--color-moca-border)',
      borderRadius: 14, padding: '13px 15px', position: 'relative',
      overflow: 'hidden', minWidth: 0,
    }}>
      <span aria-hidden="true" style={{
        position: 'absolute', insetInlineStart: 0, top: 0, bottom: 0,
        width: 3, background: tint.bar,
      }} />
      <div style={{
        fontSize: 10, fontWeight: 800, letterSpacing: 0.5,
        textTransform: 'uppercase', color: tint.ink, marginBottom: 5,
      }}>{kicker}</div>
      <div style={{
        fontSize: 14, fontWeight: 700, color: 'var(--color-moca-dark)',
        lineHeight: 1.35, marginBottom: 4,
      }}>{title}</div>
      <div style={{ fontSize: 11.5, color: 'var(--color-moca-sub)', lineHeight: 1.5 }}>{body}</div>
    </div>
  )
}

function SignalsRow({ data, days }) {
  const { tt } = useLang()
  const { threat, opportunity, attention } = data.signals

  return (
    <div style={{
      display: 'grid', gap: 14,
      gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
    }}>
      {threat ? (
        <SignalCard
          tone="threat"
          kicker={tt('איום', 'Threat')}
          title={tt(
            `${getCarrierName(threat.carrier)} מורידה מחירים`,
            `${getCarrierName(threat.carrier)} is cutting prices`,
          )}
          body={tt(
            `${threat.drops} הורדות מחיר ב-${days} הימים האחרונים` +
              (threat.newPlans ? ` וגם ${threat.newPlans} חבילות חדשות` : ''),
            `${threat.drops} price cuts in the last ${days} days` +
              (threat.newPlans ? `, plus ${threat.newPlans} new plans` : ''),
          )}
        />
      ) : (
        <SignalCard
          tone="calm"
          kicker={tt('איום', 'Threat')}
          title={tt('אין מהלך אגרסיבי', 'No aggressive move')}
          body={tt('אף מתחרה לא הוריד יותר ממחיר אחד בתקופה.', 'No competitor cut more than one price in this window.')}
        />
      )}

      {opportunity && (
        <SignalCard
          tone="opportunity"
          kicker={tt('הזדמנות', 'Opportunity')}
          title={
            opportunity.weLead
              ? tt('אנחנו הזולים בשוק', 'We lead on price')
              : tt(`${getCarrierName(opportunity.carrier)} מוביל את המחיר`, `${getCarrierName(opportunity.carrier)} leads on price`)
          }
          body={
            opportunity.weLead
              ? tt(
                  `המחיר המשוקלל שלנו ${fmtPpgb(opportunity.ppgb)}/GB — הנמוך בשוק. נכס להגנה.`,
                  `Our weighted rate is ${fmtPpgb(opportunity.ppgb)}/GB — the market's lowest. An asset to defend.`,
                )
              : tt(
                  `${fmtPpgb(opportunity.ppgb)}/GB` +
                    (opportunity.gapPct != null ? ` — פער של ${Math.abs(opportunity.gapPct).toFixed(0)}% מאיתנו.` : '.'),
                  `${fmtPpgb(opportunity.ppgb)}/GB` +
                    (opportunity.gapPct != null ? ` — a ${Math.abs(opportunity.gapPct).toFixed(0)}% gap from us.` : '.'),
                )
          }
        />
      )}

      {attention ? (
        <SignalCard
          tone="attention"
          kicker={tt('שימו לב', 'Attention')}
          title={tt('נתונים לא עדכניים', 'Data is going stale')}
          body={tt(
            `${attention.stale.map((s) => s.label).join(', ')} — לא עודכנו בזמן. ייתכן שסקרייפר תקוע.`,
            `${attention.stale.map((s) => s.labelEn).join(', ')} — not refreshed on time. A scraper may be stuck.`,
          )}
        />
      ) : (
        <SignalCard
          tone="calm"
          kicker={tt('איכות נתונים', 'Data quality')}
          title={tt('כל המקורות עדכניים', 'All sources current')}
          body={tt('כל הקטגוריות נסרקו בחלון הזמן התקין.', 'Every category scraped within its expected window.')}
        />
      )}
    </div>
  )
}

// ── 6. AI read-out + freshness ───────────────────────────────────────────

function NarrativeCard({ data }) {
  const { tt, lang } = useLang()
  const { narrative, freshness, counts } = data

  return (
    <Card
      title={tt('קריאת המצב', 'The read')}
      hint={narrative?.generated_at
        ? new Date(narrative.generated_at).toLocaleString(lang === 'he' ? 'he-IL' : 'en-GB', {
            day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
          })
        : undefined}
    >
      {narrative?.narrative ? (
        <p style={{
          margin: 0, fontSize: 13.5, lineHeight: 1.75,
          color: 'var(--color-moca-text)', textWrap: 'pretty',
        }}>
          {narrative.narrative}
        </p>
      ) : (
        <Empty>
          {tt(
            'סיכום ה-AI מתחדש מדי בוקר ב-08:05.',
            'The AI read-out regenerates every morning at 08:05.',
          )}
        </Empty>
      )}

      <div style={{
        marginTop: 16, paddingTop: 13, borderTop: '1px solid var(--color-moca-border)',
        display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center',
      }}>
        <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: 0.5, textTransform: 'uppercase', color: 'var(--color-moca-muted)' }}>
          {tt('טריות הנתונים', 'Data freshness')}
        </span>
        {freshness.map((f) => {
          const stale = f.hours != null && f.hours > f.limit
          return (
            <span key={f.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5 }}>
              <span aria-hidden="true" style={{
                width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                background: stale ? 'var(--color-moca-up)' : 'var(--color-moca-down)',
              }} />
              <span style={{ color: 'var(--color-moca-sub)' }}>{lang === 'he' ? f.label : f.labelEn}</span>
              <span style={{ color: stale ? 'var(--color-moca-up)' : 'var(--color-moca-muted)', fontWeight: stale ? 700 : 500 }}>
                {fmtAgo(f.hours, tt)}
              </span>
            </span>
          )
        })}
        <span className="tnum" style={{ fontSize: 11, color: 'var(--color-moca-muted)', marginInlineStart: 'auto' }}>
          {tt(
            `${counts.domestic + counts.abroad + counts.global} חבילות במעקב · ${counts.carriers} מפעילים`,
            `${counts.domestic + counts.abroad + counts.global} plans tracked · ${counts.carriers} carriers`,
          )}
        </span>
      </div>
    </Card>
  )
}

// ── page ─────────────────────────────────────────────────────────────────

export default function CockpitPage() {
  const { tt } = useLang()
  const { workspace, isSuperAdmin } = useAuth()
  const [days, setDays] = useState(30)
  const [carrierModalOpen, setCarrierModalOpen] = useState(false)
  const oursCarrier = workspace?.mvno_carrier || null
  const { loading, error, data, reload } = useCockpitData(oursCarrier, days)

  const periodPicker = (
    <div
      role="group"
      aria-label={tt('טווח זמן', 'Time range')}
      style={{
        display: 'inline-flex', background: '#fff', borderRadius: 10,
        border: '1px solid var(--color-moca-border)', padding: 2, gap: 2,
      }}
    >
      {WINDOWS.map((w) => {
        const active = w === days
        return (
          <button
            key={w}
            onClick={() => setDays(w)}
            aria-pressed={active}
            style={{
              border: 'none', cursor: 'pointer', borderRadius: 8,
              padding: '6px 13px', fontSize: 12, fontWeight: active ? 800 : 600,
              background: active ? 'var(--color-moca-bolt)' : 'transparent',
              color: active ? '#fff' : 'var(--color-moca-sub)',
              transition: 'background 120ms ease, color 120ms ease',
            }}
          >
            {tt(`${w} ימים`, `${w}d`)}
          </button>
        )
      })}
    </div>
  )

  return (
    <>
      <PageHeader
        kicker={tt('הנהלה', 'Executive')}
        title={tt('חדר מצב', 'Situation room')}
        subtitle={tt(
          'תמונת השוק ברמת הנהלה — היכן אנחנו עומדים, מה זז, ומה דורש החלטה.',
          'The market at executive altitude — where we stand, what moved, and what needs a decision.',
        )}
        actions={periodPicker}
      />

      <div style={{
        padding: '18px 32px 40px', maxWidth: 1320, margin: '0 auto',
        display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        {loading && (
          <div style={{ padding: '70px 0', textAlign: 'center' }} role="status" aria-live="polite">
            <Spinner />
          </div>
        )}

        {!loading && error && (
          <Card>
            <Empty>
              {tt('טעינת הנתונים נכשלה.', 'Failed to load data.')}{' '}
              <button
                onClick={reload}
                style={{
                  background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                  color: 'var(--color-moca-bolt)', fontWeight: 700, fontSize: 12.5,
                }}
              >
                {tt('נסו שוב', 'Retry')}
              </button>
            </Empty>
          </Card>
        )}

        {!loading && !error && data && (
          <>
            <VerdictBar
              data={data}
              oursCarrier={oursCarrier}
              days={days}
              canPickCarrier={isSuperAdmin}
              onPickCarrier={() => setCarrierModalOpen(true)}
            />

            {/* KPI row — five tiles, hard cap. Anything else belongs deeper. */}
            <div style={{
              display: 'grid', gap: 12,
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            }}>
              <Stat
                label={tt('חציון שוק ₪/GB', 'Market median ₪/GB')}
                value={data.ladderInfo.marketMedian != null ? data.ladderInfo.marketMedian.toFixed(2) : '—'}
                delta={data.marketTrendPct}
                sub={tt(`על פני ${data.ladderInfo.total} מפעילים`, `across ${data.ladderInfo.total} carriers`)}
              />
              <Stat
                label={tt('המיצוב שלנו', 'Our position')}
                value={data.ladderInfo.rank ? `${data.ladderInfo.rank}/${data.ladderInfo.total}` : '—'}
                accent={data.ladderInfo.rank ? 'var(--color-moca-hot-text)' : undefined}
                sub={data.ladderInfo.ours
                  ? tt(`${fmtPpgb(data.ladderInfo.ours.ppgb)}/GB משוקלל`, `${fmtPpgb(data.ladderInfo.ours.ppgb)}/GB weighted`)
                  : tt('לא הוגדר ספק', 'No carrier set')}
              />
              <Stat
                label={tt('פער מהזול בשוק', 'Gap to cheapest')}
                value={data.ladderInfo.vsCheapestPct != null
                  ? `${data.ladderInfo.vsCheapestPct > 0 ? '+' : ''}${data.ladderInfo.vsCheapestPct.toFixed(0)}%`
                  : '—'}
                accent={data.ladderInfo.vsCheapestPct > 0 ? 'var(--color-moca-up)' : 'var(--color-moca-down)'}
                sub={data.ladderInfo.cheapest
                  ? tt(`מול ${getCarrierName(data.ladderInfo.cheapest.carrier)}`, `vs ${getCarrierName(data.ladderInfo.cheapest.carrier)}`)
                  : undefined}
              />
              <Stat
                label={tt('הורדות מחיר', 'Price cuts')}
                value={data.activity.drops}
                sub={tt(
                  `${data.activity.rises} עליות · ${data.activity.oursDrops} שלנו`,
                  `${data.activity.rises} rises · ${data.activity.oursDrops} ours`,
                )}
              />
              <Stat
                label={tt('השקות חדשות', 'New launches')}
                value={data.activity.newPlans}
                sub={tt(`${data.activity.removed} חבילות הוסרו`, `${data.activity.removed} plans removed`)}
              />
            </div>

            <TrendCard data={data} oursCarrier={oursCarrier} days={days} />

            {/* Movers gets the wider column — it is the page's action list. */}
            <div className="cockpit-split" style={{ display: 'grid', gap: 16 }}>
              <MoversCard data={data} oursCarrier={oursCarrier} days={days} />
              <LadderCard data={data} oursCarrier={oursCarrier} />
            </div>

            <SignalsRow data={data} days={days} />
            <NarrativeCard data={data} />
          </>
        )}
      </div>

      <MyCarrierModal open={carrierModalOpen} onClose={() => setCarrierModalOpen(false)} />

      <style>{`
        .cockpit-split { grid-template-columns: 1fr; }
        @media (min-width: 1000px) {
          .cockpit-split { grid-template-columns: 1.35fr 1fr; }
        }
      `}</style>
    </>
  )
}
