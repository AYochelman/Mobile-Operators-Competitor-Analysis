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
import { DOMESTIC_LABELS } from '../data/carrierLabels'
import Spinner from '../components/ui/Spinner'

/**
 * /cockpit — the executive (סמנכ"ל) situation room.
 *
 * One screen that answers three questions and nothing else:
 *   1. Where do we stand?           → verdict bar + cost/volume tiles + ladder
 *   2. What did competitors change? → the fixed 7-day rubric
 *   3. Is it a trend?               → the price-history line
 * plus a one-line answer to "can I trust this?" (freshness footer).
 *
 * v2 (owner feedback): carriers are always shown as their brand LOGO
 * (CarrierChip), the ₪/GB ratio is gone in favour of two plain measures —
 * package COST (₪/month) and package VOLUME (GB) — and the movers list became
 * a weekly competitor-changes section. Reads only existing endpoints; the whole
 * data layer lives in hooks/useCockpitData.js.
 */

// Per-browser "compare against" pick from the verdict bar. Deliberately NOT
// the workspace's mvno_carrier: writing that needs super_admin, and this is a
// view preference, not account configuration.
const OURS_KEY = 'moca_cockpit_ours_carrier'

// ── chart palette ────────────────────────────────────────────────────────
// Validated with the dataviz skill's validate_palette.js against the white
// card surface: #c9622f PASSES every check as a SINGLE emphasis hue, and any
// second warm brown paired with it FAILS the normal-vision floor (ΔE ~12,
// needs ≥15) — the mocha family is one hue, so two browns can never be two
// categorical series. Hence one coloured series (ours) + the market as a
// DASHED NEUTRAL reference, and a single-hue ladder where only "ours" is
// tinted. No rank-coloured ramp anywhere.
const CV = {
  ours: '#5c3317',    // brand bolt — single high-contrast series line
  ref: '#a99680',     // market median — dashed, recessive, direct-labelled
  bar: '#cdb69b',     // ladder bars: neutral, magnitude is the length
  barOurs: '#c9622f', // validated emphasis hue, only ever on our own bar
  grid: '#efe6da',
}

const WINDOWS = [7, 30, 90]
const OURS_TINT = { background: 'rgba(201, 98, 47, 0.07)', boxShadow: 'inset 0 0 0 1px rgba(201, 98, 47, 0.22)' }

function fmtIls(n) {
  return Number.isFinite(n) ? `₪${Math.round(n).toLocaleString('en-US')}` : '—'
}
function fmtGb(v, tt) {
  if (v === Infinity) return tt('ללא הגבלה', 'Unlimited')
  if (!Number.isFinite(v)) return '—'
  return `${Math.round(v).toLocaleString('en-US')} GB`
}
function fmtDay(iso, lang) {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  return lang === 'he' ? `${Number(d)}.${Number(m)}` : `${Number(m)}/${Number(d)}`
}
function fmtAgoHours(hours, tt) {
  if (hours == null) return tt('אין נתונים', 'no data')
  if (hours < 1) return tt('הרגע', 'just now')
  if (hours < 24) return tt(`לפני ${hours} שעות`, `${hours}h ago`)
  const d = Math.round(hours / 24)
  return d === 1 ? tt('אתמול', 'yesterday') : tt(`לפני ${d} ימים`, `${d}d ago`)
}
function fmtAgoTs(ts, tt) {
  if (!ts) return ''
  return fmtAgoHours(Math.max(0, Math.round((Date.now() - ts) / 3_600_000)), tt)
}

/** Neutral first→last % for a price series — a move's direction is not good or bad
 *  by itself (it depends on who you are), so no red/green here. */
function TrendPct({ value }) {
  const style = { fontSize: 11, fontWeight: 700, color: 'var(--color-moca-sub)', direction: 'ltr', unicodeBidi: 'isolate' }
  if (!value) return <span className="tnum" style={style}>0%</span> // flat (or rounded to zero): no arrow
  const up = value > 0
  return (
    <span className="tnum" style={style}>
      {up ? '▲' : '▼'} {up ? '+' : ''}{value}%
    </span>
  )
}

/** Gap-vs-market clause: |gap| < 1% reads as "in line with", never "0% above". */
function gapClause(pct, tt, kind) {
  if (pct == null) return ''
  if (Math.abs(pct) < 1) return tt('כמו השוק', 'in line with market')
  const n = Math.abs(pct).toFixed(0)
  if (kind === 'volume') return tt(`${n}% ${pct > 0 ? 'יותר' : 'פחות'} מהשוק`, `${n}% ${pct > 0 ? 'more' : 'less'} than market`)
  return tt(`${n}% ${pct > 0 ? 'מעל' : 'מתחת'} לשוק`, `${n}% ${pct > 0 ? 'above' : 'below'} market`)
}

/** LTR-isolated number run inside Hebrew prose (keeps ₪/GB glued to digits). */
function Num({ children, style }) {
  return <span className="tnum" style={{ direction: 'ltr', unicodeBidi: 'isolate', display: 'inline-block', ...style }}>{children}</span>
}

// ── shared shells ────────────────────────────────────────────────────────

function Card({ title, hint, aside, children, pad = 18, style, id }) {
  return (
    <section
      id={id}
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
      {(title || hint || aside) && (
        <header style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
          {title && (
            <h2 style={{
              margin: 0, fontSize: 13.5, fontWeight: 800,
              color: 'var(--color-moca-dark)', letterSpacing: -0.2,
            }}>{title}</h2>
          )}
          {hint && (
            <span style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>{hint}</span>
          )}
          {aside && <span style={{ marginInlineStart: 'auto', display: 'inline-flex', alignItems: 'center', gap: 8 }}>{aside}</span>}
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

function Stat({ label, value, sub, accent, title }) {
  return (
    <div title={title} style={{
      background: '#fff', border: '1px solid var(--color-moca-border)',
      borderRadius: 14, padding: '13px 15px', boxShadow: 'var(--sh-card)', minWidth: 0,
    }}>
      <div style={{
        fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800,
        letterSpacing: 0.5, textTransform: 'uppercase',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{label}</div>
      <div className="tnum" style={{
        marginTop: 7, fontSize: 25, fontWeight: 800, lineHeight: 1.05,
        color: accent || 'var(--color-moca-dark)', letterSpacing: -0.6,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        <Num>{value}</Num>
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: 'var(--color-moca-sub)', marginTop: 6, lineHeight: 1.45, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {sub}
        </div>
      )}
    </div>
  )
}

/** Small logo + name, for tile sub-lines and headers. */
function ChipName({ id, size = 16, bold = false }) {
  return <CarrierChip id={id} size={size} showName bold={bold} />
}

// ── 1. verdict ───────────────────────────────────────────────────────────

function weeklyClause(totals, tt, competitorsOnly) {
  const who = competitorsOnly ? tt('השבוע אצל המתחרים', 'This week at competitors') : tt('השבוע בשוק', 'This week in the market')
  if (!totals.changes) return tt(`${who}: שקט — אף חבילה לא השתנתה.`, `${who}: quiet — no package changed.`)
  const parts = []
  if (totals.drops) parts.push(tt(`${totals.drops} הורדות מחיר`, `${totals.drops} price cuts`))
  if (totals.newPlans) parts.push(tt(`${totals.newPlans} השקות`, `${totals.newPlans} launches`))
  if (totals.rises) parts.push(tt(`${totals.rises} העלאות`, `${totals.rises} rises`))
  if (totals.removed) parts.push(tt(`${totals.removed} הסרות`, `${totals.removed} removals`))
  if (totals.extras) parts.push(tt(`${totals.extras} עדכוני הטבות`, `${totals.extras} benefit updates`))
  return `${who}: ${tt(`${totals.changes} שינויים`, `${totals.changes} changes`)} — ${parts.join(' · ')}`
}

/**
 * Inline "my carrier" picker for the verdict bar.
 *
 * The workspace-level `mvno_carrier` is super_admin-only (the API gates it), so
 * everyone else used to get a dead-end sentence here ("ask an admin"). This
 * select gives every reader the relative view on the spot: it sets a LOCAL
 * preference (kept in localStorage by CockpitPage) and never touches the
 * workspace. A super_admin still gets the link that makes the pick permanent
 * for the whole account, through MyCarrierModal.
 */
function CarrierPicker({ value, tracked, onChange, canPickCarrier, onPickCarrier }) {
  const { tt } = useLang()
  // Always list the full domestic registry (not only the carriers that happen
  // to rank today) so a workspace bound to a quiet carrier still shows itself.
  const options = useMemo(
    () => Object.keys(DOMESTIC_LABELS)
      .map((id) => ({ id, label: getCarrierName(id) }))
      .sort((a, b) => a.label.localeCompare(b.label, 'he')),
    [],
  )
  const known = options.some((o) => o.id === value)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 176 }}>
      <label
        htmlFor="cockpit-ours-carrier"
        style={{ fontSize: 10, fontWeight: 800, letterSpacing: 0.6, textTransform: 'uppercase', color: 'var(--color-moca-muted)' }}
      >
        {tt('השוואה מול', 'Compare against')}
      </label>
      <select
        id="cockpit-ours-carrier"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          background: 'var(--color-moca-white, #fff)', color: 'var(--color-moca-dark)',
          border: '1px solid var(--color-moca-border)', borderRadius: 10,
          padding: '9px 12px', fontSize: 13, fontWeight: 700,
          fontFamily: 'inherit', cursor: 'pointer', maxWidth: 220,
        }}
      >
        <option value="">{tt('כל השוק (ללא ספק שלי)', 'The whole market (no carrier)')}</option>
        {!known && value && <option value={value}>{getCarrierName(value)}</option>}
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.label}</option>
        ))}
      </select>
      {value && !tracked && (
        <span style={{ fontSize: 11, color: 'var(--color-moca-up)', maxWidth: 220, lineHeight: 1.45 }}>
          {tt('אין כרגע נתונים לספק הזה', 'No data for this carrier right now')}
        </span>
      )}
      {canPickCarrier ? (
        <button
          type="button"
          onClick={onPickCarrier}
          style={{
            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 11, fontWeight: 700, textAlign: 'start',
            color: 'var(--color-moca-bolt)', maxWidth: 220, lineHeight: 1.45,
          }}
        >
          {tt('קבעו כספק הקבוע של החשבון', 'Set as the account default')}
        </button>
      ) : (
        <span style={{ fontSize: 11, color: 'var(--color-moca-muted)', maxWidth: 220, lineHeight: 1.45 }}>
          {tt('הבחירה נשמרת בדפדפן הזה בלבד', 'Saved in this browser only')}
        </span>
      )}
    </div>
  )
}

/**
 * The single sentence the exec reads first. Never invents a position: with no
 * carrier picked (or that carrier absent from the feed) it states the market
 * instead and offers the picker.
 */
function VerdictBar({ data, oursCarrier, onPickCarrier, canPickCarrier, onSelectCarrier }) {
  const { tt } = useLang()
  const { costVolume: cv, weekly, stale } = data
  const ours = cv.ours

  let headline
  if (ours) {
    const pricier = cv.costGapPct != null && cv.costGapPct > 0
    const inLine = cv.costGapPct != null && Math.abs(cv.costGapPct) < 1
    const gap = cv.costGapPct == null ? null : Math.abs(cv.costGapPct).toFixed(0)
    headline = (
      <>
        {getCarrierName(oursCarrier)}{' '}
        {cv.rankCost != null ? (
          <><strong style={{ fontWeight: 800 }}>{tt(`במקום ${cv.rankCost} מתוך ${cv.total}`, `ranked ${cv.rankCost} of ${cv.total}`)}</strong>{' '}{tt('במחיר החבילה', 'on package price')}{' — '}</>
        ) : (
          <>{tt('חבילה טיפוסית:', 'typical package:')}{' '}</>
        )}
        <Num style={{ fontWeight: 700 }}>{fmtIls(ours.cost)}</Num> {tt('לחודש', '/month')}
        {gap != null && inLine && <>{', '}{tt('בקו אחד עם חציון השוק', 'in line with the market median')}</>}
        {gap != null && !inLine && (
          <>
            {', '}
            <span style={{ color: pricier ? 'var(--color-moca-up)' : 'var(--color-moca-down)', fontWeight: 700 }}>
              <Num>{gap}%</Num> {pricier ? tt('יקר', 'above') : tt('זול', 'below')}
            </span>{' '}
            {tt('מחציון השוק', 'the market median')}
          </>
        )}
        {cv.rankVol != null ? (
          <>
            {' — '}{tt('ו', 'and ')}<strong style={{ fontWeight: 800 }}>{tt(`במקום ${cv.rankVol} מתוך ${cv.total}`, `ranked ${cv.rankVol} of ${cv.total}`)}</strong>{' '}
            {tt('בנפח', 'on volume')} (<Num>{fmtGb(ours.volume, tt)}</Num>)
          </>
        ) : (
          <>{' — '}{tt('נפח טיפוסי', 'typical volume')} <Num>{fmtGb(ours.volume, tt)}</Num></>
        )}.
      </>
    )
  } else {
    headline = (
      <>
        {tt('חבילה טיפוסית בשוק עולה', 'A typical package in the market costs')}{' '}
        <Num style={{ fontWeight: 800 }}>{fmtIls(cv.marketCost)}</Num> {tt('לחודש ונותנת', 'a month and gives')}{' '}
        <Num style={{ fontWeight: 800 }}>{fmtGb(cv.marketVolume, tt)}</Num>.
        {cv.cheapest && (
          <>{' '}{tt('הזול:', 'Cheapest:')} <ChipName id={cv.cheapest.carrier} /> (<Num>{fmtIls(cv.cheapest.cost)}</Num>)</>
        )}
        {cv.mostGenerous && (
          <>{' · '}{tt('הנדיב:', 'Most generous:')} <ChipName id={cv.mostGenerous.carrier} /> (<Num>{fmtGb(cv.mostGenerous.volume, tt)}</Num>)</>
        )}
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
      {ours && (
        <span style={{ display: 'inline-flex', borderRadius: 14, boxShadow: `0 0 0 2px #fff, 0 0 0 4px ${CV.barOurs}` }}>
          <CarrierChip id={oursCarrier} size={40} />
        </span>
      )}
      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 5, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: 0.6, textTransform: 'uppercase', color: 'var(--color-moca-muted)' }}>
            {tt('שורה תחתונה', 'Bottom line')}
          </span>
          {stale.length > 0 && (
            <span
              title={stale.map((s) => `${s.label}: ${fmtAgoHours(s.hours, tt)}`).join(' · ')}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 700,
                color: '#9a3320', background: 'rgba(180, 71, 45, 0.12)', borderRadius: 999, padding: '2px 8px',
              }}
            >
              <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-moca-up)' }} />
              {tt('נתונים לא עדכניים', 'Data is stale')}
            </span>
          )}
        </div>
        <p style={{
          margin: 0, fontSize: 17, lineHeight: 1.55,
          color: 'var(--color-moca-dark)', fontWeight: 500, textWrap: 'pretty',
        }}>
          {headline}
        </p>
        <p style={{ margin: '6px 0 0', fontSize: 12.5, color: 'var(--color-moca-sub)' }}>
          {weeklyClause(weekly.totals, tt, !!oursCarrier)}
        </p>
      </div>
      <CarrierPicker
        value={oursCarrier || ''}
        tracked={!!ours}
        onChange={onSelectCarrier}
        canPickCarrier={canPickCarrier}
        onPickCarrier={onPickCarrier}
      />
    </div>
  )
}

// ── 2. KPI tiles — cost × volume, market × ours ──────────────────────────

// Every tile on this row is a MEDIAN, and the two "ours" tiles are medians of
// OUR OWN packages, not one real package - the price and the volume can come
// from two different rows. The labels are too short to carry that, so the
// tooltips do.
const MEDIAN_HINT = {
  cost: (tt) => tt(
    'לכל מפעיל מחושב תחילה חציון מחירי המחירון של חבילותיו, והערך כאן הוא החציון של המפעילים. כל מפעיל נספר פעם אחת, בלי קשר לכמות החבילות שלו. חבילות ללא גלישה וחבילות מתחת ל-1GB לא נכללות.',
    "Each carrier's median list price first, then the median across carriers. Every carrier counts once, however many packages it sells. Voice-only and sub-GB rows are excluded.",
  ),
  volume: (tt) => tt(
    'לכל מפעיל מחושב תחילה חציון הנפחים של חבילותיו, והערך כאן הוא החציון של המפעילים. חבילה ללא הגבלה נספרת כאינסוף.',
    "Each carrier's median volume first, then the median across carriers. An unlimited package counts as infinity.",
  ),
  oursCost: (tt) => tt(
    'חציון מחירי המחירון של החבילות שלנו, לא מחיר של חבילה מסוימת. המחיר והנפח עשויים להגיע משתי חבילות שונות.',
    'The median list price of our packages, not the price of any one package. This tile and the volume tile can come from two different packages.',
  ),
  oursVolume: (tt) => tt(
    'חציון הנפחים של החבילות שלנו, לא נפח של חבילה מסוימת. המחיר והנפח עשויים להגיע משתי חבילות שונות.',
    'The median volume of our packages, not the volume of any one package. This tile and the price tile can come from two different packages.',
  ),
  carrierCost: (tt) => tt(
    'החציון הפנימי של אותו מפעיל, לא מחיר של חבילה מסוימת.',
    "That carrier's own median, not the price of any one package.",
  ),
  carrierVolume: (tt) => tt(
    'החציון הפנימי של אותו מפעיל, לא נפח של חבילה מסוימת.',
    "That carrier's own median, not the volume of any one package.",
  ),
}

function KpiRow({ data }) {
  const { tt } = useLang()
  const cv = data.costVolume
  const ours = cv.ours

  const costSub = ours
    ? tt(
        (cv.rankCost != null ? `מקום ${cv.rankCost}/${cv.total} מהזול` : `מתוך ${cv.total} מפעילים`),
        (cv.rankCost != null ? `#${cv.rankCost}/${cv.total} cheapest` : `of ${cv.total} carriers`),
      ) + (cv.costGapPct != null ? ` · ${gapClause(cv.costGapPct, tt, 'cost')}` : '')
    : cv.cheapest ? <ChipName id={cv.cheapest.carrier} /> : null

  const volSub = ours
    ? tt(
        (cv.rankVol != null ? `מקום ${cv.rankVol}/${cv.total} מהנדיב` : `מתוך ${cv.total} מפעילים`) + (ours.unlimitedCount ? ` · ${ours.unlimitedCount} ללא הגבלה` : ''),
        (cv.rankVol != null ? `#${cv.rankVol}/${cv.total} most data` : `of ${cv.total} carriers`) + (ours.unlimitedCount ? ` · ${ours.unlimitedCount} unlimited` : ''),
      ) + (cv.volumeGapPct != null ? ` · ${gapClause(cv.volumeGapPct, tt, 'volume')}` : '')
    : cv.mostGenerous ? <ChipName id={cv.mostGenerous.carrier} /> : null

  return (
    <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }}>
      <Stat
        label={tt('מחיר חבילה בשוק', 'Market package price')}
        value={fmtIls(cv.marketCost)}
        sub={tt(`חציון של ${cv.total} מפעילים · מחירי מחירון`, `median of ${cv.total} carriers · list prices`)}
        title={MEDIAN_HINT.cost(tt)}
      />
      <Stat
        label={tt('נפח חבילה בשוק', 'Market package volume')}
        value={fmtGb(cv.marketVolume, tt)}
        sub={tt(`חציון של ${cv.total} מפעילים`, `median of ${cv.total} carriers`)
          + (cv.unlimitedCarriers
            ? tt(` · ${cv.unlimitedCarriers === 1 ? 'מפעיל אחד' : `${cv.unlimitedCarriers} מפעילים`} ללא הגבלה`, ` · ${cv.unlimitedCarriers} unlimited`)
            : '')}
        title={MEDIAN_HINT.volume(tt)}
      />
      <Stat
        label={ours ? tt('המחיר החציוני שלנו', 'Our median price') : tt('הזול בשוק', 'Cheapest in market')}
        value={fmtIls(ours ? ours.cost : cv.cheapest?.cost)}
        accent={ours ? 'var(--color-moca-hot-text)' : undefined}
        sub={costSub}
        title={ours ? MEDIAN_HINT.oursCost(tt) : MEDIAN_HINT.carrierCost(tt)}
      />
      <Stat
        label={ours ? tt('הנפח החציוני שלנו', 'Our median volume') : tt('הנדיב בשוק', 'Most data in market')}
        value={fmtGb(ours ? ours.volume : cv.mostGenerous?.volume, tt)}
        accent={ours ? 'var(--color-moca-hot-text)' : undefined}
        sub={volSub}
        title={ours ? MEDIAN_HINT.oursVolume(tt) : MEDIAN_HINT.carrierVolume(tt)}
      />
    </div>
  )
}

// ── 3. weekly competitor changes ─────────────────────────────────────────

const KIND_META = {
  drop:    { he: 'הורדת מחיר', en: 'Price cut',    color: 'var(--color-moca-down)' },
  new:     { he: 'חבילה חדשה', en: 'New package',  color: 'var(--color-moca-hot)' },
  rise:    { he: 'העלאת מחיר', en: 'Price rise',   color: 'var(--color-moca-up)' },
  removed: { he: 'הוסרה',      en: 'Removed',      color: 'var(--color-moca-muted)' },
  extras:  { he: 'הטבות עודכנו', en: 'Benefits updated', color: 'var(--color-moca-sub)' },
}
const GROUPS_CAP = 5
const ROWS_CAP = 4

function KindLabel({ kind, lang }) {
  const m = KIND_META[kind]
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 700, color: 'var(--color-moca-sub)', whiteSpace: 'nowrap', width: 84, flexShrink: 0 }}>
      <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: '50%', background: m.color, flexShrink: 0 }} />
      {lang === 'he' ? m.he : m.en}
    </span>
  )
}

/** The added/removed benefit lines under an extras row (max 2 shown). */
function DiffLines({ diff }) {
  const lines = [
    ...diff.added.map((t) => ({ t, sign: '+', color: 'var(--color-moca-down)' })),
    ...diff.removed.map((t) => ({ t, sign: '−', color: 'var(--color-moca-up)' })),
  ]
  const shown = lines.slice(0, 2)
  const more = lines.length - shown.length
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 3 }}>
      {shown.map((l, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 11, lineHeight: 1.35, color: 'var(--color-moca-sub)' }}>
          <span aria-hidden="true" style={{ color: '#fff', background: l.color, borderRadius: 3, width: 13, height: 13, fontSize: 10, fontWeight: 900, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>{l.sign}</span>
          <span dir="rtl" style={{ unicodeBidi: 'isolate', textDecoration: l.sign === '−' ? 'line-through' : 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {String(l.t).replace(/\s+/g, ' ').trim()}
          </span>
        </div>
      ))}
      {more > 0 && <span style={{ fontSize: 10.5, color: 'var(--color-moca-muted)' }}>+{more}</span>}
    </div>
  )
}

function ChangeRow({ row }) {
  const { tt, lang } = useLang()
  return (
    <li className="wk-row" style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '6px 0', borderTop: '1px solid var(--color-moca-mist, #faf5ee)' }}>
      <KindLabel kind={row.kind} lang={lang} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, minWidth: 0 }}>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--color-moca-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {row.plan_name}
          </span>
          <span style={{ fontSize: 10, color: 'var(--color-moca-muted)', flexShrink: 0 }}>
            {row.scope === 'abroad' ? tt('חו״ל · מחיר לחבילה', 'Roaming · per package') : tt('סלולר · לחודש', 'Domestic · per month')}
            {row.updates > 1 && <> · {tt(`${row.updates} עדכונים`, `${row.updates} updates`)}</>}
          </span>
        </div>
        {row.kind === 'extras' && row.diff && <DiffLines diff={row.diff} />}
      </div>
      <span className="tnum" style={{ fontSize: 11.5, color: 'var(--color-moca-sub)', whiteSpace: 'nowrap', direction: 'ltr', flexShrink: 0 }}>
        {(row.kind === 'drop' || row.kind === 'rise') && (
          <>{fmtIls(row.oldPrice)} → <strong style={{ color: 'var(--color-moca-dark)' }}>{fmtIls(row.newPrice)}</strong></>
        )}
        {row.kind === 'new' && <strong style={{ color: 'var(--color-moca-dark)' }}>{fmtIls(row.newPrice)}</strong>}
        {row.kind === 'removed' && row.oldPrice != null && <span style={{ textDecoration: 'line-through' }}>{fmtIls(row.oldPrice)}</span>}
      </span>
      {(row.kind === 'drop' || row.kind === 'rise') && <Delta value={row.pct} suffix="%" />}
      <span className="wk-ago" style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', whiteSpace: 'nowrap', flexShrink: 0, width: 64, textAlign: 'end' }}>
        {fmtAgoTs(row.ts, tt)}
      </span>
    </li>
  )
}

function groupSummary(g, tt) {
  const parts = []
  if (g.drops) parts.push(tt(`${g.drops} הורדות מחיר`, `${g.drops} cuts`))
  if (g.newPlans) parts.push(tt(`${g.newPlans} השקות`, `${g.newPlans} launches`))
  if (g.rises) parts.push(tt(`${g.rises} העלאות`, `${g.rises} rises`))
  if (g.removed) parts.push(tt(`${g.removed} הסרות`, `${g.removed} removals`))
  if (g.extras) parts.push(tt(`${g.extras} עדכוני הטבות`, `${g.extras} benefit updates`))
  return parts.join(' · ')
}

function CarrierGroup({ group }) {
  const { tt } = useLang()
  const [open, setOpen] = useState(false)
  const rows = open ? group.rows : group.rows.slice(0, ROWS_CAP)
  const hidden = group.rows.length - rows.length
  return (
    <li style={{ padding: '10px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4, flexWrap: 'wrap' }}>
        <CarrierChip id={group.carrier} size={28} showName bold />
        <span style={{ fontSize: 11, color: 'var(--color-moca-sub)' }}>{groupSummary(group, tt)}</span>
      </div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {rows.map((r) => <ChangeRow key={`${r.scope}|${r.plan_name}|${r.kind}`} row={r} />)}
      </ul>
      {hidden > 0 && (
        <button onClick={() => setOpen(true)} style={{ background: 'none', border: 'none', padding: '4px 0 0', cursor: 'pointer', fontSize: 11.5, fontWeight: 700, color: 'var(--color-moca-bolt)' }}>
          {tt(`+${hidden} שינויים נוספים`, `+${hidden} more changes`)}
        </button>
      )}
    </li>
  )
}

function WeeklyChangesCard({ data, oursCarrier }) {
  const { tt } = useLang()
  const navigate = useNavigate()
  const [allGroups, setAllGroups] = useState(false)
  const { weekly, freshness, stale } = data
  const groups = allGroups ? weekly.groups : weekly.groups.slice(0, GROUPS_CAP)
  const moreGroups = weekly.groups.length - groups.length
  const domesticFresh = freshness.find((f) => f.id === 'domestic')

  const title = oursCarrier ? tt('מה המתחרים שינו השבוע', 'What competitors changed this week') : tt('מה השתנה בשוק השבוע', 'What changed in the market this week')
  const hint = tt('7 ימים · סלולר + חו״ל', '7 days · domestic + roaming') + (oursCarrier ? tt(` · ללא ${getCarrierName(oursCarrier)}`, ` · excluding ${getCarrierName(oursCarrier)}`) : '')

  return (
    <Card
      id="weekly"
      title={title}
      hint={hint}
      aside={weekly.mostActive && (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--color-moca-sub)' }}>
          {tt('הפעיל ביותר השבוע:', 'Most active:')} <ChipName id={weekly.mostActive.carrier} size={18} bold />
        </span>
      )}
    >
      {weekly.truncated && (
        <p style={{ margin: '-6px 0 8px', fontSize: 11, color: 'var(--color-moca-muted)' }}>
          {tt('ייתכן שחסרים שינויים ישנים יותר מהשבוע (מגבלת 500 רשומות לפיד).', 'Older changes from this week may be missing (500-row feed cap).')}
        </p>
      )}
      {!weekly.groups.length ? (
        <Empty>
          {stale.length
            ? tt(
                `לא נרשמו שינויים — אבל הסריקה האחרונה הייתה ${fmtAgoHours(domesticFresh?.hours, tt)}. ייתכן שסקרייפר תקוע.`,
                `No changes recorded — but the last scrape was ${fmtAgoHours(domesticFresh?.hours, tt)}. A scraper may be stuck.`,
              )
            : tt(
                `שקט אצל המתחרים — אף חבילה לא השתנתה בשבוע האחרון. נסרק לאחרונה ${fmtAgoHours(domesticFresh?.hours, tt)}.`,
                `Quiet week — no competitor package changed. Last scraped ${fmtAgoHours(domesticFresh?.hours, tt)}.`,
              )}
        </Empty>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column' }}>
          {groups.map((g) => <CarrierGroup key={g.carrier} group={g} />)}
        </ul>
      )}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        {moreGroups > 0 && (
          <button onClick={() => setAllGroups(true)} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, fontWeight: 700, color: 'var(--color-moca-bolt)' }}>
            {tt(`הצג את כל המפעילים (+${moreGroups})`, `Show all carriers (+${moreGroups})`)}
          </button>
        )}
        <button onClick={() => navigate('/history')} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, fontWeight: 700, color: 'var(--color-moca-bolt)', marginInlineStart: 'auto' }}>
          {tt('כל היסטוריית השינויים ←', 'Full change history →')}
        </button>
      </div>
    </Card>
  )
}

// ── 4. cost & volume ladder ──────────────────────────────────────────────

function LadderCard({ data, oursCarrier }) {
  const { tt } = useLang()
  const cv = data.costVolume
  if (!cv.rows.length) {
    return (
      <Card title={tt('סולם המיצוב', 'Positioning ladder')}>
        <Empty>{tt('אין נתוני חבילות זמינים.', 'No package data available.')}</Empty>
      </Card>
    )
  }
  const maxCost = cv.rows[cv.rows.length - 1].cost
  const colHead = { fontSize: 10, fontWeight: 800, letterSpacing: 0.5, textTransform: 'uppercase', color: 'var(--color-moca-muted)' }

  return (
    <Card title={tt('סולם המיצוב', 'Positioning ladder')} hint={tt('מחיר חציוני · נפח טיפוסי', 'median price · typical volume')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span style={{ width: 14, flexShrink: 0 }} />
        <span style={{ flex: '0 1 104px', minWidth: 30 }} />
        <span style={{ ...colHead, flex: 1 }}>{tt('מחיר חבילה', 'Package price')}</span>
        {/* Same direction/shrink as the value cells below, so "end" is the same edge for header and numbers. */}
        <span style={{ ...colHead, width: 44, textAlign: 'end', direction: 'ltr', flexShrink: 0 }}>₪</span>
        <span style={{ ...colHead, width: 82, textAlign: 'end', direction: 'ltr', flexShrink: 0 }}>{tt('נפח', 'Volume')}</span>
      </div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {cv.rows.map((row) => {
          const isOurs = oursCarrier && row.carrier === oursCarrier
          const pct = maxCost > 0 ? Math.max(3, (row.cost / maxCost) * 100) : 0
          const title = `${getCarrierName(row.carrier)} · ${fmtIls(row.cost)} · ${fmtGb(row.volume, tt)} · ${row.packages} ${tt('חבילות', 'packages')}`
            + (row.packages < 2 ? ` · ${tt('מדגם קטן', 'small sample')}` : '')
            + (row.promoCount ? ` · ${row.promoCount} ${tt('במבצע (מחיר מחירון מוצג)', 'on promo (list price shown)')}` : '')
            + (row.excluded ? ` · ${row.excluded} ${tt('קול/עד 1GB לא נספרו', 'voice/sub-1GB excluded')}` : '')
          return (
            <li key={row.carrier} title={title} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '3px 6px', margin: '0 -6px', borderRadius: 9, ...(isOurs ? OURS_TINT : null) }}>
              <span className="tnum" style={{ fontSize: 10, color: 'var(--color-moca-muted)', width: 14, textAlign: 'center', flexShrink: 0, fontWeight: 700 }}>{row.rank}</span>
              <span style={{ flex: '0 1 104px', minWidth: 30, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ display: 'inline-flex', borderRadius: 8, boxShadow: isOurs ? `0 0 0 2px ${CV.barOurs}` : 'none', flexShrink: 0 }}>
                  <CarrierChip id={row.carrier} size={24} />
                </span>
                <span style={{ fontSize: 11, fontWeight: isOurs ? 800 : 600, color: isOurs ? 'var(--color-moca-hot-text)' : 'var(--color-moca-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {getCarrierName(row.carrier)}
                </span>
              </span>
              {/* Logical inset keeps the fill anchored to the RTL start edge. */}
              <span style={{ position: 'relative', flex: 1, height: 9, background: 'var(--color-moca-cream)', borderRadius: 999, minWidth: 40 }}>
                <span style={{ position: 'absolute', insetInlineStart: 0, top: 0, bottom: 0, width: `${pct}%`, borderRadius: 999, background: isOurs ? CV.barOurs : CV.bar }} />
              </span>
              <span className="tnum" style={{ fontSize: 11.5, width: 44, textAlign: 'end', flexShrink: 0, direction: 'ltr', fontWeight: isOurs ? 800 : 600, color: isOurs ? 'var(--color-moca-hot-text)' : 'var(--color-moca-sub)' }}>
                {fmtIls(row.cost)}
              </span>
              <span className="tnum" style={{ fontSize: 11.5, width: 82, textAlign: 'end', flexShrink: 0, direction: 'ltr', fontWeight: 700, color: 'var(--color-moca-dark)', whiteSpace: 'nowrap' }}>
                {row.volume === Infinity ? <span style={{ fontWeight: 800 }}>∞</span> : fmtGb(row.volume, tt)}
                {Number.isFinite(row.volume) && row.unlimitedCount > 0 && (
                  <span style={{ fontSize: 10, color: 'var(--color-moca-muted)', marginInlineStart: 4 }}>+{row.unlimitedCount}∞</span>
                )}
              </span>
            </li>
          )
        })}
      </ul>
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--color-moca-border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {cv.defender && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--color-moca-text)', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, color: 'var(--color-moca-hot-text)' }}>{tt('לשים לב:', 'Watch:')}</span>
            <ChipName id={cv.defender.carrier} bold />
            {tt('נותן', 'gives')} <Num style={{ fontWeight: 700 }}>{fmtGb(cv.defender.volume, tt)}</Num> {tt('ב-', 'at ')}<Num style={{ fontWeight: 700 }}>{fmtIls(cv.defender.cost)}</Num>
            {' — '}{tt('יותר נפח במחיר שלנו או פחות.', 'more data at our price or less.')}
          </div>
        )}
        <p style={{ margin: 0, fontSize: 11, color: 'var(--color-moca-muted)', lineHeight: 1.5 }}>
          {tt('חציון השוק', 'Market median')}: <Num style={{ fontWeight: 700 }}>{fmtIls(cv.marketCost)}</Num> · <Num style={{ fontWeight: 700 }}>{fmtGb(cv.marketVolume, tt)}</Num>
          {' · '}{tt('מחירי מחירון ללא מבצעים', 'list prices, no promos')}
          {cv.excludedTotal > 0 && <> · {tt(`${cv.excludedTotal} חבילות קול/עד 1GB לא נספרו`, `${cv.excludedTotal} voice/sub-1GB plans excluded`)}</>}
          {' · ∞ = '}{tt('ללא הגבלה', 'unlimited')}
        </p>
      </div>
    </Card>
  )
}

// ── 5. price trend ───────────────────────────────────────────────────────

function TrendTooltip({ active, payload, label, tt, lang, oursCarrier }) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload
  return (
    <div style={{
      background: '#fff', border: '1px solid var(--color-moca-border)',
      borderRadius: 10, padding: '9px 12px', boxShadow: 'var(--sh-popover)',
      fontSize: 12, direction: lang === 'he' ? 'rtl' : 'ltr', minWidth: 190,
    }}>
      <div style={{ fontWeight: 800, marginBottom: 6, color: 'var(--color-moca-dark)' }}>{fmtDay(label, lang)}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 4 }}>
          {p.dataKey === 'ours'
            ? <CarrierChip id={oursCarrier} size={16} showName />
            : <><span style={{ width: 14, height: 0, borderTop: `2px dashed ${CV.ref}` }} /><span style={{ color: 'var(--color-moca-sub)' }}>{tt('חציון השוק', 'Market median')}</span></>}
          <Num style={{ fontWeight: 800, color: 'var(--color-moca-dark)', marginInlineStart: 'auto' }}>{fmtIls(p.value)}</Num>
        </div>
      ))}
      {point?.floor != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--color-moca-border)', color: 'var(--color-moca-muted)', fontSize: 11 }}>
          {tt('הזול בשוק', 'Market floor')}: <CarrierChip id={point.floorCarrier} size={14} />
          <Num style={{ marginInlineStart: 'auto', fontWeight: 700, color: 'var(--color-moca-sub)' }}>{fmtIls(point.floor)}</Num>
        </div>
      )}
    </div>
  )
}

function TrendCard({ data, oursCarrier, days, setDays, busy }) {
  const { tt, lang } = useLang()
  const { trend, marketTrendPct, oursTrendPct } = data
  const last = trend.length ? trend[trend.length - 1] : null
  const lastOurs = useMemo(() => {
    for (let i = trend.length - 1; i >= 0; i--) if (Number.isFinite(trend[i].ours)) return trend[i]
    return null
  }, [trend])
  const oursPoints = useMemo(() => trend.filter((d) => Number.isFinite(d.ours)).length, [trend])
  const showOurs = !!oursCarrier && oursPoints >= 2
  const marketPoints = trend.length

  // Endpoint labels collide when the two lines end within ~3% of the Y range;
  // nudge ours upward in that case (the legend still carries both values).
  const yVals = trend.flatMap((d) => [d.market, showOurs ? d.ours : null]).filter(Number.isFinite)
  const yRange = yVals.length ? Math.max(...yVals) - Math.min(...yVals) : 0
  const collide = last && lastOurs && last.day === lastOurs.day && yRange > 0 && Math.abs(last.market - lastOurs.ours) < yRange * 0.03
  const labelStyle = { fontSize: 10.5, fontWeight: 800, fill: 'var(--color-moca-dark)' }

  const picker = (
    <div role="group" aria-label={tt('טווח הגרף', 'Chart range')} style={{ display: 'inline-flex', background: 'var(--color-moca-bg)', borderRadius: 9, border: '1px solid var(--color-moca-border)', padding: 2, gap: 2 }}>
      {WINDOWS.map((w) => {
        const active = w === days
        return (
          <button key={w} onClick={() => setDays(w)} aria-pressed={active} style={{
            border: 'none', cursor: 'pointer', borderRadius: 7, padding: '4px 10px', fontSize: 11.5, fontWeight: active ? 800 : 600,
            background: active ? 'var(--color-moca-bolt)' : 'transparent', color: active ? '#fff' : 'var(--color-moca-sub)',
            transition: 'background 120ms ease, color 120ms ease',
          }}>
            {tt(`${w} ימים`, `${w}d`)}
          </button>
        )
      })}
    </div>
  )

  return (
    <Card title={tt('מחיר חבילה ממוצע', 'Average package price')} hint={tt('₪ לחודש', '₪ / month')} aside={picker}>
      {trend.length < 2 ? (
        <Empty>
          {tt(
            'אין עדיין מספיק נקודות היסטוריה לתקופה הזו. הטבלה היומית נבנית ב-08:50 וב-18:30.',
            'Not enough daily history for this window yet. The daily table is built at 08:50 and 18:30.',
          )}
        </Empty>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center', fontSize: 11.5 }}>
            {showOurs && lastOurs && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                <svg width="20" height="8" aria-hidden="true"><line x1="0" y1="4" x2="20" y2="4" stroke={CV.ours} strokeWidth="2.5" strokeLinecap="round" /></svg>
                <CarrierChip id={oursCarrier} size={16} showName />
                <Num style={{ fontWeight: 800, color: 'var(--color-moca-dark)' }}>{fmtIls(lastOurs.ours)}</Num>
                {oursTrendPct != null && oursPoints >= 4 && <TrendPct value={oursTrendPct} />}
              </span>
            )}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
              <svg width="20" height="8" aria-hidden="true"><line x1="0" y1="4" x2="20" y2="4" stroke={CV.ref} strokeWidth="2.5" strokeDasharray="4 3" strokeLinecap="round" /></svg>
              <span style={{ color: 'var(--color-moca-sub)' }}>{tt('חציון השוק', 'Market median')}</span>
              <Num style={{ fontWeight: 800, color: 'var(--color-moca-dark)' }}>{fmtIls(last?.market)}</Num>
              {marketTrendPct != null && marketPoints >= 4 && <TrendPct value={marketTrendPct} />}
            </span>
          </div>

          {/* LTR wrapper: a time axis reads left→right even inside the RTL shell. */}
          <div aria-busy={busy || undefined} style={{ direction: 'ltr', width: '100%', height: 220, opacity: busy ? 0.45 : 1, transition: 'opacity 150ms ease' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 8, right: 48, left: -8, bottom: 0 }}>
                <CartesianGrid stroke={CV.grid} vertical={false} />
                <XAxis dataKey="day" tickFormatter={(d) => fmtDay(d, lang)} tick={{ fontSize: 10.5, fill: 'var(--color-moca-muted)' }} axisLine={{ stroke: CV.grid }} tickLine={false} minTickGap={28} />
                <YAxis tick={{ fontSize: 10.5, fill: 'var(--color-moca-muted)' }} axisLine={false} tickLine={false} width={44} tickFormatter={(v) => `₪${v}`} domain={['auto', 'auto']} />
                <Tooltip content={<TrendTooltip tt={tt} lang={lang} oursCarrier={oursCarrier} />} cursor={{ stroke: 'var(--color-moca-sand)', strokeWidth: 1 }} />
                {/* Market = dashed neutral reference, not a categorical peer. */}
                <Line type="monotone" dataKey="market" stroke={CV.ref} strokeWidth={2} strokeDasharray="5 4" dot={false} activeDot={{ r: 4, fill: CV.ref }} isAnimationActive={false} name="market" />
                {showOurs && (
                  <Line type="monotone" dataKey="ours" stroke={CV.ours} strokeWidth={2.5} dot={false} connectNulls activeDot={{ r: 5, fill: CV.ours, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false} name="ours" />
                )}
                {/* Direct labels on the last point of each line (≤4 series rule). */}
                {last && (
                  <ReferenceDot x={last.day} y={last.market} r={3.5} fill={CV.ref} stroke="#fff" strokeWidth={1.5} isFront
                    label={{ value: fmtIls(last.market), position: 'right', ...labelStyle, fill: 'var(--color-moca-sub)' }} />
                )}
                {showOurs && lastOurs && (
                  <ReferenceDot x={lastOurs.day} y={lastOurs.ours} r={4} fill={CV.ours} stroke="#fff" strokeWidth={2} isFront
                    label={{ value: fmtIls(lastOurs.ours), position: collide ? 'top' : 'right', ...labelStyle }} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p style={{ margin: '10px 0 0', fontSize: 11, color: 'var(--color-moca-muted)', lineHeight: 1.5 }}>
            {tt(
              'ממוצע מחירי המחירון של כל מפעיל, חציון על פני השוק. ימים עם פחות משלושה מפעילים מושמטים. היסטוריית נפח אינה נשמרת — הנפח מוצג לפי המצב הנוכחי בסולם המיצוב.',
              "Each carrier's mean list price, median across the market. Days with fewer than three reporting carriers are dropped. Volume history is not stored — volume is shown as of now in the ladder.",
            )}
          </p>
        </>
      )}
    </Card>
  )
}

// ── 6. freshness strip ───────────────────────────────────────────────────

function FreshnessStrip({ data }) {
  const { tt, lang } = useLang()
  const { freshness, counts } = data
  return (
    <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center', padding: '4px 6px 0' }}>
      <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: 0.5, textTransform: 'uppercase', color: 'var(--color-moca-muted)' }}>
        {tt('טריות הנתונים', 'Data freshness')}
      </span>
      {freshness.map((f) => {
        const stale = f.hours == null || f.hours > f.limit
        return (
          <span key={f.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5 }}>
            <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: stale ? 'var(--color-moca-up)' : 'var(--color-moca-down)' }} />
            <span style={{ color: 'var(--color-moca-sub)' }}>{lang === 'he' ? f.label : f.labelEn}</span>
            <span style={{ color: stale ? 'var(--color-moca-up)' : 'var(--color-moca-muted)', fontWeight: stale ? 700 : 500 }}>{fmtAgoHours(f.hours, tt)}</span>
          </span>
        )
      })}
      <span className="tnum" style={{ fontSize: 11, color: 'var(--color-moca-muted)', marginInlineStart: 'auto' }}>
        {tt(
          `${counts.domestic} חבילות סלולר + ${counts.abroad} חו״ל במעקב · ${counts.carriers} מפעילים`,
          `${counts.domestic} domestic + ${counts.abroad} roaming packages tracked · ${counts.carriers} carriers`,
        )}
      </span>
    </div>
  )
}

// ── page ─────────────────────────────────────────────────────────────────

export default function CockpitPage() {
  const { tt } = useLang()
  const { workspace, isSuperAdmin } = useAuth()
  const [days, setDays] = useState(30)
  const [carrierModalOpen, setCarrierModalOpen] = useState(false)
  // A reader without super_admin cannot write workspace.mvno_carrier, so the
  // verdict bar's picker keeps a per-browser override instead. Empty string =
  // "explicitly no carrier" (market view), null = "never picked, follow the
  // workspace" — they are NOT the same, hence the `?? `.
  const [carrierOverride, setCarrierOverride] = useState(() => {
    try { return localStorage.getItem(OURS_KEY) } catch { return null }
  })
  const oursCarrier = (carrierOverride ?? workspace?.mvno_carrier) || null
  const pickCarrier = (id) => {
    setCarrierOverride(id)
    try {
      if (id) localStorage.setItem(OURS_KEY, id)
      else localStorage.setItem(OURS_KEY, '')
    } catch { /* private mode / quota - the pick just won't survive a reload */ }
  }
  const { loading, trendLoading, error, data, reload } = useCockpitData(oursCarrier, days)

  return (
    <>
      <PageHeader
        kicker={tt('הנהלה', 'Executive')}
        title={tt('חדר מצב', 'Situation room')}
        subtitle={tt(
          'תמונת השוק ברמת הנהלה — כמה עולה חבילה, כמה היא נותנת, ומה המתחרים שינו השבוע.',
          'The market at executive altitude — what a package costs, what it gives, and what competitors changed this week.',
        )}
      />

      <div className="cockpit-page" style={{ maxWidth: 1320, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {loading && (
          <div style={{ padding: '70px 0', textAlign: 'center' }} role="status" aria-live="polite">
            <Spinner />
          </div>
        )}

        {!loading && error && (
          <Card>
            <Empty>
              {tt('טעינת הנתונים נכשלה.', 'Failed to load data.')}{' '}
              <button onClick={reload} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--color-moca-bolt)', fontWeight: 700, fontSize: 12.5 }}>
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
              canPickCarrier={isSuperAdmin}
              onPickCarrier={() => setCarrierModalOpen(true)}
              onSelectCarrier={pickCarrier}
            />
            <KpiRow data={data} />

            {/* The weekly rubric is the page's action list — it gets the wider column. */}
            <div className="cockpit-split" style={{ display: 'grid', gap: 16 }}>
              <WeeklyChangesCard data={data} oursCarrier={oursCarrier} />
              <LadderCard data={data} oursCarrier={oursCarrier} />
            </div>

            <TrendCard data={data} oursCarrier={oursCarrier} days={days} setDays={setDays} busy={trendLoading} />
            <FreshnessStrip data={data} />
          </>
        )}
      </div>

      <MyCarrierModal
        open={carrierModalOpen}
        onClose={() => setCarrierModalOpen(false)}
        onSaved={() => { try { localStorage.removeItem(OURS_KEY) } catch { /* nothing to clear */ } }}
      />

      <style>{`
        .cockpit-page { padding: 18px 32px 40px; }
        .cockpit-split { grid-template-columns: 1fr; }
        @media (min-width: 1000px) {
          .cockpit-split { grid-template-columns: 1.35fr 1fr; align-items: start; }
        }
        @media (max-width: 560px) {
          .cockpit-page { padding: 14px 16px 32px; }
          .wk-row { flex-wrap: wrap; }
          .wk-ago { display: none; }
        }
      `}</style>
    </>
  )
}
