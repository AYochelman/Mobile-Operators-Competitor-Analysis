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
  MyCarrierModal,
} from '../components/moca'
import { getCarrierColor, getCarrierName } from '../components/moca/carrierMeta'
import Spinner from '../components/ui/Spinner'
import { useLang } from '../hooks/useLanguage'

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
  { id: 'new',     label: 'חבילות חדשות',    predicate: (c) => c.change_type === 'new_plan' },
  { id: 'price',   label: 'שינויי מחיר',      predicate: (c) => c.change_type === 'price_change' },
  { id: 'extras',  label: 'שינויים בהטבות',   predicate: (c) => c.change_type === 'extras_change' },
  { id: 'removed', label: 'חבילות שהוסרו',    predicate: (c) => c.change_type === 'removed_plan' },
  { id: 'all',     label: 'הכל',             predicate: () => true },
]

// English labels for the filter pills, keyed by FILTERS id (the Hebrew lives in
// FILTERS.label so the array stays the single source of ids/predicates).
const FILTER_LABELS_EN = {
  new: 'New plans',
  price: 'Price changes',
  extras: 'Benefits changes',
  removed: 'Removed plans',
  all: 'All',
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
function fmtAgo(iso, tt) {
  if (!iso) return ''
  const ms = Date.now() - new Date(iso).getTime()
  const h = Math.floor(ms / (60 * 60 * 1000))
  if (h < 1) return tt('הרגע', 'just now')
  if (h < 24) return tt(`לפני ${h} שעות`, `${h} hours ago`)
  const d = Math.floor(h / 24)
  return d === 1 ? tt('אתמול', 'yesterday') : tt(`לפני ${d} ימים`, `${d} days ago`)
}

/**
 * Parse a Python list-repr string into a JS string array.
 * `extras_change` events store old_val/new_val as `str(list)` (db.py), so the
 * API hands us something like `['דקות ללא הגבלה', '6GB גלישה בחו"ל']`. Python
 * uses single quotes by default, double quotes when an item contains an
 * apostrophe; Hebrew/Unicode is emitted verbatim. Falls back to a single-item
 * array for any non-list string.
 */
function parsePyList(raw) {
  if (Array.isArray(raw)) return raw.map((x) => String(x))
  if (typeof raw !== 'string') return []
  const s = raw.trim()
  if (!s.startsWith('[') || !s.endsWith(']')) return s ? [s] : []
  const body = s.slice(1, -1)
  const items = []
  let i = 0
  while (i < body.length) {
    while (i < body.length && (body[i] === ' ' || body[i] === ',' || body[i] === '\t')) i++
    if (i >= body.length) break
    const q = body[i]
    if (q !== "'" && q !== '"') { items.push(body.slice(i).trim()); break }
    i++
    let buf = ''
    while (i < body.length) {
      const ch = body[i]
      if (ch === '\\' && i + 1 < body.length) {
        const next = body[i + 1]
        // Python repr() escapes non-printable chars — crucially NBSP (\xa0)
        // and bidi marks (‎/‏) — which appear verbatim in scraped
        // benefit strings. Decode \xHH / \uHHHH / \UHHHHHHHH back to the real
        // character; otherwise the literal "xa0" text leaks into the UI.
        if (next === 'x' && /^[0-9a-fA-F]{2}$/.test(body.slice(i + 2, i + 4))) {
          buf += String.fromCharCode(parseInt(body.slice(i + 2, i + 4), 16)); i += 4; continue
        }
        if (next === 'u' && /^[0-9a-fA-F]{4}$/.test(body.slice(i + 2, i + 6))) {
          buf += String.fromCharCode(parseInt(body.slice(i + 2, i + 6), 16)); i += 6; continue
        }
        if (next === 'U' && /^[0-9a-fA-F]{8}$/.test(body.slice(i + 2, i + 10))) {
          buf += String.fromCodePoint(parseInt(body.slice(i + 2, i + 10), 16)); i += 10; continue
        }
        buf += next === 'n' ? '\n' : next === 't' ? '\t' : next === 'r' ? '\r' : next
        i += 2
        continue
      }
      if (ch === q) { i++; break }
      buf += ch
      i++
    }
    items.push(buf)
  }
  return items
}

/**
 * Filler tokens that carry no essence — connectors and the "at no extra cost"
 * family. Dropping them lets "X ללא עלות" and "X ללא תוספת תשלום" (and a comma
 * vs "ו-" separator, and a reordered app list) collapse to the same signature,
 * so a pure rewording isn't reported as a benefit change.
 */
const BENEFIT_FILLERS = new Set([
  'ללא', 'תוספת', 'תשלום', 'עלות', 'נוספת', 'נוסף', 'חינם',
  'כלול', 'כלולה', 'כלולים', 'כולל', 'כוללת',
  'שירות', 'שירותים', 'בתכנית', 'בתוכנית', 'בחבילה', 'במסלול',
  'של', 'את', 'עם', 'גם', 'ה', 'ו', 'ב', 'ל',
])

/**
 * Canonical signature of one benefit string. Splits on list separators (comma,
 * bullet, slash, "ו-"…) into independent items, normalizes each (lower-case,
 * strip 6,000→6000 grouping + punctuation, drop filler words) keeping word
 * order *within* an item, then sorts the items. So an app list reordered or a
 * separator/filler reworded collapses to the same signature — but a number
 * swapped against its noun ("100 דקות ל-50 יעדים" vs "50…ל-100…") does NOT,
 * because each item's internal order is preserved. Guards against hiding a
 * real change as if it were cosmetic.
 */
function benefitSignature(s) {
  const segments = String(s)
    .toLowerCase()
    .replace(/(?<=\d),(?=\d)/g, '')               // 6,000 → 6000 before splitting on comma
    .split(/\s*(?:[,;\/|•·]|ו-)\s*/)         // independent list items
    .map((seg) => seg
      .replace(/[:."'()[\]\-–—]/g, ' ')           // strip remaining punctuation
      .split(/\s+/)
      .filter(Boolean)
      .filter((t) => !BENEFIT_FILLERS.has(t))
      .join(' ')                                  // keep word order within an item
      .trim())
    .filter(Boolean)
  return segments.sort().join('|')                // order-insensitive across items
}

/**
 * Diff two extras lists, suppressing text-only churn. An old item and a new
 * item with the same {@link benefitSignature} cancel out (reordered/reworded —
 * no essence change). What survives is genuinely added / removed.
 * Returns { added, removed } as the original (display) strings.
 */
function materialDiff(oldVal, newVal) {
  const oldArr = parsePyList(oldVal)
  const newArr = parsePyList(newVal)
  const oldSigs = oldArr.map(benefitSignature)
  const newSigs = newArr.map(benefitSignature)

  const tally = (sigs) => sigs.reduce((m, sig) => m.set(sig, (m.get(sig) || 0) + 1), new Map())
  const newAvail = tally(newSigs)
  const oldAvail = tally(oldSigs)

  const removed = oldArr.filter((item, i) => {
    const sig = oldSigs[i]
    if ((newAvail.get(sig) || 0) > 0) { newAvail.set(sig, newAvail.get(sig) - 1); return false }
    return true
  })
  const added = newArr.filter((item, i) => {
    const sig = newSigs[i]
    if ((oldAvail.get(sig) || 0) > 0) { oldAvail.set(sig, oldAvail.get(sig) - 1); return false }
    return true
  })
  return { added, removed }
}

/** The added/removed benefit lines shown under an `extras_change` row.
 *  `diff` is the precomputed material diff (text-only churn already removed).
 *  added = green "+" (benefit gained), removed = muted strike-through "−". */
function BenefitDiffRows({ diff }) {
  const { added = [], removed = [] } = diff || {}
  if (added.length === 0 && removed.length === 0) return null

  const line = (text, kind, key) => (
    <div key={key} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, textAlign: 'right' }}>
      <span
        aria-hidden="true"
        style={{
          flexShrink: 0,
          marginTop: 1,
          width: 15,
          height: 15,
          borderRadius: 4,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 12,
          fontWeight: 900,
          lineHeight: 1,
          color: '#fff',
          background: kind === 'added' ? 'var(--color-moca-down)' : 'var(--color-moca-up)',
        }}
      >
        {kind === 'added' ? '+' : '−'}
      </span>
      <span
        dir="rtl"
        style={{
          fontSize: 11.5,
          lineHeight: 1.35,
          color: kind === 'added' ? 'var(--color-moca-text)' : 'var(--color-moca-muted)',
          textDecoration: kind === 'removed' ? 'line-through' : 'none',
          // Benefit strings mix Hebrew + numbers + ₪ + Latin + a trailing "*";
          // isolate each line so the bidi algorithm doesn't scramble them
          // (e.g. "100 ₪ ... בפלאפון *").
          unicodeBidi: 'isolate',
        }}
      >
        {/* Normalize whitespace: scraped values embed NBSP ( ) which
            force-glues "100 ₪ לרכישת" into one non-breaking run that can't wrap
            and reorders badly in some browsers. Collapse to plain spaces. */}
        {String(text).replace(/\s+/g, ' ').trim()}
      </span>
    </div>
  )

  return (
    <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 3 }}>
      {added.map((t, idx) => line(t, 'added', `a${idx}`))}
      {removed.map((t, idx) => line(t, 'removed', `r${idx}`))}
    </div>
  )
}

/** Recent-changes feed with scope toggle (carriers / global eSIM) + filter pills. */
function ChangeFeed({ changes, globalChanges, onItemClick }) {
  const { tt } = useLang()
  const [scope, setScope] = useState('operators')
  const [filter, setFilter] = useState('new')

  // Global scrapes never log new_plan/removed_plan (dropped by design in the 3
  // global scrape paths), so those pills are structurally empty — hide them.
  const scopeFilters = scope === 'global'
    ? FILTERS.filter((f) => ['price', 'extras', 'all'].includes(f.id))
    : FILTERS

  const switchScope = (next) => {
    if (next === scope) return
    setScope(next)
    setFilter(next === 'global' ? 'price' : 'new')
  }

  // Enrich extras_change rows with a material (noise-suppressed) diff and drop
  // the ones that turn out to be text-only churn — reordered or reworded
  // benefits with no change in essence. Counts and rows both derive from this,
  // so the "שינויים בהטבות" tally reflects real changes only.
  const enriched = useMemo(() => {
    const source = scope === 'global' ? (globalChanges || []) : (changes || [])
    return source
      .map((c) => (
        c.change_type === 'extras_change'
          ? { c, diff: materialDiff(c.old_val, c.new_val) }
          : { c, diff: null }
      ))
      .filter(({ diff }) => !diff || diff.added.length > 0 || diff.removed.length > 0)
  }, [scope, globalChanges, changes])

  const filtered = useMemo(() => {
    const pred = FILTERS.find((f) => f.id === filter)?.predicate || (() => true)
    return enriched.filter((e) => pred(e.c)).slice(0, 12)
  }, [enriched, filter])

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
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
            {tt('שינויים אחרונים', 'Recent changes')}
          </h2>
          {/* Scope toggle — carriers vs global eSIM providers */}
          <div style={{ display: 'inline-flex', border: '1px solid var(--color-moca-border)', borderRadius: 999, overflow: 'hidden' }}>
            {[
              { id: 'operators', he: 'מפעילים', en: 'Carriers' },
              { id: 'global', he: 'ספקי eSIM', en: 'eSIM providers' },
            ].map((s) => (
              <button
                key={s.id}
                onClick={() => switchScope(s.id)}
                style={{
                  padding: '4px 12px',
                  border: 'none',
                  background: scope === s.id ? 'var(--color-moca-dark)' : 'transparent',
                  color: scope === s.id ? '#fff' : 'var(--color-moca-sub)',
                  fontSize: 11.5,
                  fontWeight: scope === s.id ? 700 : 500,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                {tt(s.he, s.en)}
              </button>
            ))}
          </div>
        </div>
        <span style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>{tt('לחץ על כל שורה לפרטים', 'Click any row for details')}</span>
      </header>

      {/* Filter pills */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {scopeFilters.map((f) => {
          const active = filter === f.id
          const matches = enriched.filter((e) => f.predicate(e.c)).length
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
              {tt(f.label, FILTER_LABELS_EN[f.id])}
              <span className="tnum" style={{ opacity: 0.7, fontSize: 10 }}>· {matches}</span>
            </button>
          )
        })}
      </div>

      {/* Items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {filtered.length === 0 && (
          <div style={{ padding: '20px 12px', textAlign: 'center', color: 'var(--color-moca-muted)', fontSize: 13 }}>
            {tt('אין שינויים בקטגוריה זו', 'No changes in this category')}
          </div>
        )}
        {filtered.map(({ c, diff }, i) => {
          const oldVal = Number(c.old_val)
          const newVal = Number(c.new_val)
          const isHot = priceImpact(c) >= 10
          const isNew = c.change_type === 'new_plan'
          const isUp = isPriceUp(c)

          return (
            <button
              key={`${c.carrier}-${c.plan_name}-${c.changed_at}-${i}`}
              onClick={() => onItemClick && onItemClick(c)}
              className="w-full grid gap-2 md:gap-3 px-2 py-2.5 grid-cols-[28px_1fr_72px] md:grid-cols-[40px_1fr_100px_90px] items-center text-right"
              style={{
                borderTop: i === 0 ? 'none' : '1px solid var(--color-moca-border)',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-moca-mist)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              <div className="tnum" style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 700, direction: 'ltr', textAlign: 'left' }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, flexWrap: 'wrap' }}>
                  <CarrierChip id={c.carrier} size={26} showName logo />
                  <span style={{ color: 'var(--color-moca-muted)' }}>·</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-moca-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0, flex: '1 1 0%' }}>
                    {c.plan_name}
                  </span>
                  {c.scope === 'abroad' && <Tag color="var(--color-moca-sub)">{tt('חו"ל', 'Roaming')}</Tag>}
                  {isHot && <Tag color="var(--color-moca-hot)">HOT</Tag>}
                  {isNew && <Tag color="var(--color-moca-down)">NEW</Tag>}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>
                  {c.change_type === 'price_change' && (isUp ? tt('עליית מחיר', 'Price increase') : tt('ירידת מחיר', 'Price drop'))}
                  {c.change_type === 'new_plan' && tt('מסלול חדש', 'New plan')}
                  {c.change_type === 'removed_plan' && tt('הוסר', 'Removed')}
                  {c.change_type === 'extras_change' && tt('שינוי הטבות', 'Benefits change')}
                  {c.change_type === 'details_change' && `${tt('שינוי פרטים', 'Details change')} - ${c.old_val} ← ${c.new_val}`}
                  <span className="md:hidden" style={{ marginInlineStart: 6, opacity: 0.7 }}>· {fmtAgo(c.changed_at, tt)}</span>
                </div>
                {c.change_type === 'extras_change' && <BenefitDiffRows diff={diff} />}
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
              <div className="hidden md:block" style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', textAlign: 'left' }}>
                {fmtAgo(c.changed_at, tt)}
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
  const { tt } = useLang()
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
          {tt('אין מסלולים במעקב. סמן ★ על מסלול בעמוד "השוואת מסלולים" כדי להוסיף.', 'No plans on your watchlist. Star ★ a plan on the "Plan comparison" page to add it.')}
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
 *  - Without carrier (super_admin): CTA → /admin/workspaces (the only place
 *    that can set mvno_carrier — /workspace/settings only edits brand_config).
 *  - Without carrier (regular admin): CTA → /workspace/settings (best they can
 *    do; they can't change mvno_carrier without a super_admin's help).
 *  - Without carrier (viewer): hidden (no dead CTA). */
function OursPinned({ carrierId, isAdmin, isSuperAdmin, onOpenCarrierModal }) {
  const { tt } = useLang()
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
    if (!isAdmin && !isSuperAdmin) return null  // viewers without carrier — no dead CTA
    // super_admin → open MyCarrierModal (one-click fix from this CTA)
    // admin       → fall back to /workspace/settings; the underlying API gates
    //               carrier change to super_admin so admins can't actually set it
    const handler = isSuperAdmin
      ? () => onOpenCarrierModal && onOpenCarrierModal()
      : () => navigate('/workspace/settings')
    const titleText = isSuperAdmin
      ? tt('בחר את הספק שלי - נשמר ל-workspace.mvno_carrier', 'Choose my carrier - saved to workspace.mvno_carrier')
      : tt('הגדר את הספק שלי בעמוד מיתוג (דורש super_admin)', 'Set my carrier on the branding page (requires super_admin)')
    return (
      <button
        type="button"
        onClick={handler}
        title={titleText}
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
            {tt('הגדר ספק שלי', 'Set my carrier')}
          </div>
          <div style={{ fontSize: 9.5, color: 'var(--color-moca-muted)', fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase' }}>
            {tt('לחץ להגדרה', 'Click to set')}
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
          {tt('הספק שלי', 'My carrier')}
        </div>
      </div>
    </div>
  )
}

export default function EditorialDashboardPage() {
  const { tt } = useLang()
  const { workspace, isAdmin, isSuperAdmin } = useAuth()
  const flags = useFeatureFlags()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [carrierModalOpen, setCarrierModalOpen] = useState(false)

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

  // Heatmap rows — all domestic carriers visible to this workspace (up to 10)
  const heatmapCarriers = useMemo(
    () => visibleCarriers.slice(0, 10),
    [visibleCarriers],
  )

  const { loading, plans, leadChange, kpis, heatmap, recentChanges, globalRecentChanges } =
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
            label={tt('שינויים היום', 'Changes today')}
            value={kpis.changesToday}
            delta={kpis.changesDelta}
          />
          <KpiCard
            label={tt('מחיר ממוצע', 'Average price')}
            value={kpis.avgPrice != null ? `${kpis.avgPrice}₪` : '-'}
            delta={kpis.avgPriceDelta}
            neutral={kpis.avgPriceDelta == null}
          />
          <KpiCard
            label={tt('מסלולים חדשים · שבוע', 'New plans · week')}
            value={kpis.newPlans}
            delta={kpis.newPlansDelta}
          />
          {oursCarrier && kpis.oursVsMarketPct != null ? (
            <KpiCard
              label={`${getCarrierName(oursCarrier)} ${tt('vs שוק', 'vs market')}`}
              value={`${kpis.oursVsMarketPct > 0 ? '+' : ''}${kpis.oursVsMarketPct}%`}
              neutral
              accent={kpis.oursVsMarketPct > 0 ? 'var(--color-moca-up)' : 'var(--color-moca-down)'}
            />
          ) : (
            <KpiCard label={tt('ספק שלך', 'Your carrier')} value="-" neutral note={tt('הגדר workspace.mvno_carrier', 'Set workspace.mvno_carrier')} />
          )}
        </div>

        {/* Heatmap + Watchlist row */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-5">
          <ChangeHeatmap
            data={heatmap}
            onCellClick={(c) => {
              navigate(`/plans?carrier=${c.carrier}&highlight=${encodeURIComponent(c.plan_name || '')}`)
            }}
          />
          <WatchlistSidebar plans={plans} />
        </div>

        {/* Recent changes feed */}
        <ChangeFeed
          changes={recentChanges}
          globalChanges={globalRecentChanges}
          onItemClick={(c) => {
            const base = c.scope === 'abroad' ? '/roaming' : c.scope === 'global' ? '/esim' : '/plans'
            navigate(`${base}?carrier=${c.carrier}&highlight=${encodeURIComponent(c.plan_name || '')}`)
          }}
        />
      </div>

      {/* Pinned "ours" chip */}
      <OursPinned
        carrierId={oursCarrier}
        isAdmin={isAdmin}
        isSuperAdmin={isSuperAdmin}
        onOpenCarrierModal={() => setCarrierModalOpen(true)}
      />
      <MyCarrierModal open={carrierModalOpen} onClose={() => setCarrierModalOpen(false)} />
    </div>
  )
}
