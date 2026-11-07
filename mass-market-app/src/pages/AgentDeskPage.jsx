import { useMemo, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'
import { useAgentDeskData, matchCompetitorPlans, counterOffers, talkingPoints, callScript, OBJECTIONS } from '../hooks/useAgentDeskData'
import { CarrierChip, PageHeader } from '../components/moca'
import { getCarrierName } from '../components/moca/carrierMeta'
import { DOMESTIC_LABELS } from '../data/carrierLabels'
import Spinner from '../components/ui/Spinner'

/**
 * /agent-desk - the first-line support rep's screen ("עמדת נציג").
 *
 * Built for a desktop agent on a live call with a customer who complains the
 * price is high or that a competitor gives more. One screen, three answers:
 *   1. Claim checker  - pick the competitor the customer named, type the
 *                       price / GB they quoted, see the real plan(s).
 *   2. Our answer     - ranked counter-offers from OUR rate card, compared on
 *                       first-year cost (promo months included), plus factual
 *                       talking points (wins / caveats / where they win).
 *   3. Context        - the full market table (domestic / roaming / content),
 *                       what competitors changed this week, and reseller
 *                       offers the customer may have seen in an ad.
 * Any plan in the table or the rail can be clicked into the checker.
 *
 * "Our carrier" = a per-browser pick (localStorage), defaulting to the
 * workspace's mvno_carrier - same pattern as /cockpit.
 */

const OURS_KEY = 'moca_agent_ours_carrier'

const ils = (n) => (Number.isFinite(n) ? `₪${(Math.round(n * 100) / 100).toLocaleString('en-US')}` : '—')

function fmtGb(gb, tt) {
  if (gb === Infinity) return tt('ללא הגבלה', 'Unlimited')
  if (gb == null) return tt('ללא גלישה', 'No data')
  if (gb < 1) return `${Math.round(gb * 1024)}MB`
  return `${Math.round(gb).toLocaleString('en-US')}GB`
}

function fmtMinutes(m, tt) {
  if (m === Infinity) return tt('ללא הגבלה', 'Unlimited')
  if (m == null) return '—'
  return m.toLocaleString('en-US')
}

function Num({ children, style }) {
  return <span className="tnum" style={{ direction: 'ltr', unicodeBidi: 'isolate', display: 'inline-block', ...style }}>{children}</span>
}

function Card({ title, hint, aside, children, style, pad = 16 }) {
  return (
    <section className="ad-card" style={{ padding: pad, ...style }}>
      {(title || aside) && (
        <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          {title && <h2 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: 'var(--color-moca-dark)' }}>{title}</h2>}
          {hint && <span style={{ fontSize: 11.5, color: 'var(--color-moca-muted)' }}>{hint}</span>}
          {aside && <span style={{ marginInlineStart: 'auto', display: 'inline-flex', gap: 6, alignItems: 'center' }}>{aside}</span>}
        </header>
      )}
      {children}
    </section>
  )
}

function Empty({ children }) {
  return <div style={{ padding: '18px 6px', textAlign: 'center', fontSize: 12.5, color: 'var(--color-moca-muted)', lineHeight: 1.6 }}>{children}</div>
}

function Seg({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} className="ad-seg">
      {options.map((o) => (
        <button key={o.id} type="button" aria-pressed={value === o.id} onClick={() => onChange(o.id)} className={value === o.id ? 'on' : ''}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

function PromoNote({ plan, tt }) {
  if (!plan.promoPrice || !plan.promoMonths) return null
  return (
    <span className="ad-pill warn">
      {tt(`${ils(plan.promoPrice)} ל-${plan.promoMonths} ח׳, אח״כ ${ils(plan.price)}`, `${ils(plan.promoPrice)} for ${plan.promoMonths} mo, then ${ils(plan.price)}`)}
    </span>
  )
}

function TermsLink({ plan, tt }) {
  const href = plan.source === 'reseller' ? plan.sourceUrl : plan.termsUrl
  if (!href) return null
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="ad-link" onClick={(e) => e.stopPropagation()}>
      {plan.source === 'reseller' ? tt('למקור', 'Source') : tt('תנאים', 'Terms')}
    </a>
  )
}

/** One-line plan facts: price · data · minutes · roaming · 5G. */
function PlanFacts({ plan, tt, big = false }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
      <Num style={{ fontSize: big ? 22 : 16, fontWeight: 800, color: 'var(--color-moca-dark)' }}>
        {ils(plan.promoPrice || plan.price)}
      </Num>
      <span style={{ fontSize: 12, color: 'var(--color-moca-sub)' }}>{tt('לחודש', '/mo')}</span>
      <span className="ad-fact"><Num>{fmtGb(plan.gb, tt)}</Num></span>
      {plan.minutes != null && <span className="ad-fact">{tt('דקות', 'Min')} <Num>{fmtMinutes(plan.minutes, tt)}</Num></span>}
      {plan.abroadGb > 0 && <span className="ad-fact">{tt('חו״ל', 'Roaming')} <Num>{plan.abroadGb}GB</Num></span>}
      {plan.network !== 'none' && <span className="ad-fact">{plan.network === 'max' ? tt('5G מתועדף', '5G priority') : '5G'}</span>}
    </div>
  )
}

// ── 1. top bar ───────────────────────────────────────────────────────────

function DeskBar({ ours, onOurs, data, tt }) {
  const options = useMemo(
    () => Object.keys(DOMESTIC_LABELS).map((id) => ({ id, label: getCarrierName(id) })).sort((a, b) => a.label.localeCompare(b.label, 'he')),
    [],
  )
  const stale = data.updatedHours == null || data.updatedHours > 36
  const t = data.weekly.totals
  return (
    <div className="ad-card ad-bar">
      <label htmlFor="ad-ours" style={{ fontSize: 12, fontWeight: 800, color: 'var(--color-moca-sub)' }}>{tt('אני נציג/ה של', 'I represent')}</label>
      <select id="ad-ours" value={ours || ''} onChange={(e) => onOurs(e.target.value)} className="ad-input" style={{ fontWeight: 800, minWidth: 170 }}>
        <option value="">{tt('בחרו חברה…', 'Choose a carrier…')}</option>
        {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      {ours && <CarrierChip id={ours} size={28} />}
      <span className="ad-sep" />
      <span style={{ fontSize: 12.5, color: 'var(--color-moca-sub)' }}>
        {tt('השבוע אצל המתחרים:', 'Competitors this week:')}{' '}
        <b style={{ color: 'var(--color-moca-dark)' }}>
          {t.changes
            ? tt(`${t.drops} הורדות · ${t.newPlans} השקות · ${t.rises} העלאות`, `${t.drops} cuts · ${t.newPlans} launches · ${t.rises} rises`)
            : tt('שקט', 'quiet')}
        </b>
      </span>
      <span style={{ marginInlineStart: 'auto' }} className={`ad-pill ${stale ? 'loss' : 'muted'}`} role="status">
        {data.updatedHours == null
          ? tt('אין נתוני עדכון', 'No update data')
          : data.updatedHours < 1 ? tt('עודכן הרגע', 'Updated just now') : tt(`עודכן לפני ${data.updatedHours} ש׳`, `Updated ${data.updatedHours}h ago`)}
      </span>
    </div>
  )
}

// ── 2. claim checker + our answer ────────────────────────────────────────

function ClaimChecker({ data, ours, target, setTarget, claim, setClaim, tt }) {
  const competitorIds = useMemo(() => data.carriers.filter((c) => c !== ours).sort((a, b) => getCarrierName(a).localeCompare(getCarrierName(b), 'he')), [data.carriers, ours])
  const pool = claim.carrier === '__resellers' ? data.resellers : data.competitors
  const gbVal = claim.unlimited ? Infinity : Number(claim.gb) || null
  const matches = useMemo(
    () => matchCompetitorPlans(pool, { carrier: claim.carrier === '__resellers' ? null : claim.carrier, price: Number(claim.price) || null, gb: gbVal }).slice(0, 6),
    [pool, claim.carrier, claim.price, gbVal],
  )
  const typed = Number(claim.price) > 0 || gbVal
  const active = claim.carrier || typed

  // An explicit pick (a clicked card / table row) wins; otherwise the best
  // match for what the rep typed. Typing clears the explicit pick (see set).
  const shown = target && !matches.some((m) => m.key === target.key) ? [target, ...matches.slice(0, 5)] : matches
  const effective = target || (active ? matches[0] || null : null)

  const set = (patch) => { setTarget(null); setClaim((c) => ({ ...c, ...patch })) }

  return (
    <Card title={tt('מה הלקוח אומר?', 'What is the customer saying?')} hint={tt('בחרו את המתחרה שהוזכר והקלידו את המחיר / הגלישה ששמעתם', 'Pick the competitor mentioned and type the price / data you heard')}
      aside={active ? <button type="button" className="ad-link" onClick={() => { setClaim({ carrier: '', price: '', gb: '', unlimited: false }); setTarget(null) }}>{tt('ניקוי', 'Clear')}</button> : null}>
      <div className="ad-chips" role="group" aria-label={tt('מתחרה', 'Competitor')}>
        {competitorIds.map((id) => (
          <button key={id} type="button" aria-pressed={claim.carrier === id} className={`ad-chip ${claim.carrier === id ? 'on' : ''}`} onClick={() => set({ carrier: claim.carrier === id ? '' : id })}>
            <CarrierChip id={id} size={20} showName />
          </button>
        ))}
        {data.resellers.length > 0 && (
          <button type="button" aria-pressed={claim.carrier === '__resellers'} className={`ad-chip ${claim.carrier === '__resellers' ? 'on' : ''}`} onClick={() => set({ carrier: claim.carrier === '__resellers' ? '' : '__resellers' })}>
            {tt('ראה פרסומת / משווק', 'Saw an ad / reseller')}
          </button>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap', marginTop: 12 }}>
        <label className="ad-field">
          <span>{tt('מחיר שציין (₪ לחודש)', 'Price quoted (₪/mo)')}</span>
          <input className="ad-input tnum" inputMode="decimal" value={claim.price} placeholder="29.9" onChange={(e) => set({ price: e.target.value.replace(/[^\d.]/g, '') })} style={{ width: 120 }} />
        </label>
        <label className="ad-field">
          <span>{tt('גלישה (GB)', 'Data (GB)')}</span>
          <input className="ad-input tnum" inputMode="numeric" value={claim.unlimited ? '' : claim.gb} disabled={claim.unlimited} placeholder="1000" onChange={(e) => set({ gb: e.target.value.replace(/[^\d.]/g, '') })} style={{ width: 120 }} />
        </label>
        <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', fontSize: 12.5, color: 'var(--color-moca-text)', paddingBottom: 9, cursor: 'pointer' }}>
          <input type="checkbox" checked={claim.unlimited} onChange={(e) => set({ unlimited: e.target.checked })} />
          {tt('ללא הגבלה', 'Unlimited')}
        </label>
      </div>

      <div className="ad-split" style={{ marginTop: 14 }}>
        <div>
          <div className="ad-subhead">{tt('אצל המתחרה', 'At the competitor')}</div>
          {!active && <Empty>{tt('בחרו מתחרה או הקלידו מחיר, או לחצו על כל תוכנית בטבלת השוק למטה.', 'Pick a competitor or type a price, or click any plan in the market table below.')}</Empty>}
          {active && !matches.length && <Empty>{tt('לא נמצאה תוכנית תואמת. ייתכן שזו הצעה אישית או מבצע שאינו באתר.', 'No matching plan. It may be a personal offer or a promo not on their site.')}</Empty>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {active && shown.map((p) => (
              <button key={p.key} type="button" aria-pressed={effective?.key === p.key} className={`ad-opt ${effective?.key === p.key ? 'on' : ''}`} onClick={() => setTarget(p)}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <CarrierChip id={p.carrier} size={18} showName bold />
                  <span style={{ fontSize: 12, color: 'var(--color-moca-sub)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.plan_name}</span>
                  <span style={{ marginInlineStart: 'auto' }}><TermsLink plan={p} tt={tt} /></span>
                </div>
                <PlanFacts plan={p} tt={tt} />
                {(p.promoPrice || p.source === 'reseller') && (
                  <div style={{ marginTop: 5, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <PromoNote plan={p} tt={tt} />
                    {p.source === 'reseller' && <span className="ad-pill muted">{tt('הצעת משווק', 'Reseller offer')}</span>}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        <OurAnswer key={effective?.key || 'none'} data={data} ours={ours} target={effective} claimPrice={claim.price} tt={tt} />
      </div>
    </Card>
  )
}

const TAG_LABEL = {
  beats: ['משתלם יותר', 'Better value'],
  more: ['יותר גלישה, יקר יותר', 'More data, costs more'],
  cheaper: ['זול יותר, פחות גלישה', 'Cheaper, less data'],
}

function OurAnswer({ data, ours, target, claimPrice, tt }) {
  const offers = useMemo(() => counterOffers(data.ours, target), [data.ours, target])
  const [pick, setPick] = useState(0)
  const [copied, setCopied] = useState(false)
  const chosen = (offers[pick] || offers[0])?.plan || null
  const points = useMemo(() => talkingPoints(chosen, target, tt), [chosen, target, tt])
  const [view, setView] = useState('script')
  const [step, setStep] = useState(0)
  const [objection, setObjection] = useState(null)
  const tag = (offers[pick] || offers[0])?.tag
  const script = useMemo(
    () => callScript(chosen, target, { tag, offers, theirName: target ? getCarrierName(target.carrier) : '', claimPrice, objection }, tt),
    [chosen, target, tag, offers, claimPrice, objection, tt],
  )

  const copy = () => {
    const obj = OBJECTIONS.find((o) => o.id === objection)
    const text = [
      `${getCarrierName(target.carrier)} - ${target.plan_name}: ${ils(target.promoPrice || target.price)}, ${fmtGb(target.gb, tt)}`,
      `${tt('הצעה', 'Offer')}: ${chosen.plan_name}: ${ils(chosen.promoPrice || chosen.price)}, ${fmtGb(chosen.gb, tt)}`,
      ...points.map((p) => `• ${p.text}`),
      ...(obj ? [`${tt('התנגדות', 'Pushback')}: ${tt(obj.he, obj.en)}`] : []),
    ].join('\n')
    navigator.clipboard?.writeText(text).then(() => setCopied(true)).catch(() => {})
  }

  return (
    <div className="ad-answer">
      <div className="ad-subhead">{tt('מה אנחנו מציעים', 'What we offer')}</div>
      {!ours && <Empty>{tt('בחרו למעלה את החברה שאתם מייצגים כדי לראות הצעות נגד.', 'Choose the carrier you represent (top bar) to see counter-offers.')}</Empty>}
      {ours && !target && <Empty>{tt('ההצעה שלנו תופיע כאן ברגע שתיבחר תוכנית של מתחרה.', 'Our offer appears here once a competitor plan is selected.')}</Empty>}
      {ours && target && !offers.length && (
        <Empty>{tt('אין לנו כרגע תוכנית דומה. שקלו העברה למחלקת שימור.', 'We have no comparable plan right now. Consider escalating to retention.')}</Empty>
      )}
      {ours && target && offers.length > 0 && (
        <>
          {offers[0].tag !== 'beats' && (
            <div className="ad-pill loss" style={{ display: 'block', marginBottom: 8, padding: '7px 10px', lineHeight: 1.5 }}>
              {tt('אין לנו תוכנית שמשתווה במחיר ובגלישה. הציגו את היתרונות, ואם הלקוח מתעקש - העבירו לשימור.', 'No plan of ours matches on both price and data. Lead with the advantages; if the customer insists, escalate to retention.')}
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {offers.map((o, i) => (
              <button key={o.plan.key} type="button" aria-pressed={pick === i} className={`ad-tab ${pick === i ? 'on' : ''}`} onClick={() => setPick(i)}>
                {tt(...TAG_LABEL[o.tag])}
              </button>
            ))}
          </div>
          <div className="ad-offer">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <CarrierChip id={chosen.carrier} size={20} />
              <b style={{ fontSize: 14, color: 'var(--color-moca-dark)' }}>{chosen.plan_name}</b>
              <span style={{ marginInlineStart: 'auto' }}><TermsLink plan={chosen} tt={tt} /></span>
            </div>
            <PlanFacts plan={chosen} tt={tt} big />
            <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <PromoNote plan={chosen} tt={tt} />
              <span style={{ fontSize: 11.5, color: 'var(--color-moca-sub)' }}>
                {tt('שנה ראשונה:', 'Year one:')} <Num>{ils(chosen.yearCost)}</Num> {tt('מול', 'vs')} <Num>{ils(target.yearCost)}</Num>
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', marginTop: 12, marginBottom: 6 }}>
            <span className="ad-subhead" style={{ margin: 0 }}>{tt('מה להגיד ללקוח', 'What to tell the customer')}</span>
            <button type="button" className="ad-link" style={{ marginInlineStart: 'auto' }} onClick={copy}>{copied ? tt('הועתק ✓', 'Copied ✓') : tt('העתקה לתיעוד', 'Copy for notes')}</button>
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }} role="tablist" aria-label={tt('תצוגה', 'View')}>
            <button type="button" role="tab" aria-selected={view === 'script'} className={`ad-tab ${view === 'script' ? 'on' : ''}`} onClick={() => setView('script')}>{tt('תסריט שיחה', 'Call script')}</button>
            <button type="button" role="tab" aria-selected={view === 'points'} className={`ad-tab ${view === 'points' ? 'on' : ''}`} onClick={() => setView('points')}>{tt('נקודות מהירות', 'Quick points')}</button>
          </div>
          {view === 'script' ? (
            <CallScript stages={script} step={step} setStep={setStep} objection={objection} setObjection={setObjection} tt={tt} />
          ) : (
            <ul className="ad-points">
              {points.map((p, i) => (
                <li key={i} className={p.tone}>
                  <span aria-hidden="true" className="ic">{p.tone === 'win' ? '✓' : p.tone === 'warn' ? '!' : '–'}</span>
                  <span>{p.text}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

/**
 * The live call script: numbered stages, the current one expanded, the ones
 * already said collapsed. Picking a pushback appends a tailored answer stage
 * and jumps to it. Content comes from callScript() and rebuilds whenever the
 * competitor plan or the chosen offer changes.
 */
function CallScript({ stages, step, setStep, objection, setObjection, tt }) {
  const cur = Math.min(step, stages.length - 1)
  const closeIdx = stages.findIndex((s) => s.id === 'close')
  return (
    <div className="ad-script">
      <ol>
        {stages.map((s, i) => {
          const state = i === cur ? 'cur' : i < cur ? 'done' : 'next'
          return (
            <li key={s.id} className={state}>
              <button type="button" className="ad-script-h" aria-expanded={state === 'cur'} onClick={() => setStep(i)}>
                <span className="n" aria-hidden="true">{state === 'done' ? '✓' : i + 1}</span>
                <span>{s.title}</span>
              </button>
              {state === 'cur' && (
                <div className="ad-script-b">
                  {s.lines.map((l, j) => (
                    l.kind === 'say'
                      ? <p key={j} className="say">{l.text}</p>
                      : <p key={j} className="note"><b>{tt('לנציג:', 'Rep:')}</b> {l.text}</p>
                  ))}
                  {i < stages.length - 1 && (
                    <button type="button" className="ad-link" onClick={() => setStep(i + 1)}>{tt('נאמר, לשלב הבא ←', 'Said it, next step →')}</button>
                  )}
                </div>
              )}
            </li>
          )
        })}
      </ol>
      {cur >= closeIdx && (
        <div style={{ marginTop: 10 }}>
          <div className="ad-subhead" style={{ marginBottom: 6 }}>{tt('יש התנגדות? בחרו מה נאמר:', 'Pushback? Pick what was said:')}</div>
          <div className="ad-chips" role="group" aria-label={tt('התנגדות', 'Pushback')}>
            {OBJECTIONS.map((o) => (
              <button key={o.id} type="button" aria-pressed={objection === o.id} className={`ad-chip ${objection === o.id ? 'on' : ''}`}
                onClick={() => { const next = objection === o.id ? null : o.id; setObjection(next); setStep(next ? closeIdx + 1 : closeIdx) }}>
                {tt(o.he, o.en)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 3. market table ──────────────────────────────────────────────────────

const GB_BUCKETS = [
  { id: 'all', he: 'הכל', en: 'All', test: () => true },
  { id: 's', he: 'עד 50GB', en: '≤50GB', test: (p) => p.gb != null && p.gb !== Infinity && p.gb <= 50 },
  { id: 'm', he: '51-300GB', en: '51-300GB', test: (p) => p.gb > 50 && p.gb <= 300 && p.gb !== Infinity },
  { id: 'l', he: '300GB+', en: '300GB+', test: (p) => p.gb > 300 && p.gb !== Infinity },
  { id: 'u', he: 'ללא הגבלה', en: 'Unlimited', test: (p) => p.gb === Infinity },
  { id: 'v', he: 'כשר / שיחות', en: 'Kosher / voice', test: (p) => p.gb == null },
]

function DomesticTable({ data, ours, target, onPick, tt, lang }) {
  const [bucket, setBucket] = useState('all')
  const [sort, setSort] = useState('price')
  const [q, setQ] = useState('')
  const rows = useMemo(() => {
    const b = GB_BUCKETS.find((x) => x.id === bucket)
    const needle = q.trim().toLowerCase()
    const list = data.domestic.filter((p) => b.test(p) && (!needle || `${p.plan_name} ${getCarrierName(p.carrier)}`.toLowerCase().includes(needle)))
    const gbK = (g) => (g === Infinity ? 1e6 : g ?? -1)
    const cmp = {
      price: (a, z) => (a.promoPrice || a.price) - (z.promoPrice || z.price),
      gb: (a, z) => gbK(z.gb) - gbK(a.gb) || a.price - z.price,
      carrier: (a, z) => getCarrierName(a.carrier).localeCompare(getCarrierName(z.carrier), 'he') || a.price - z.price,
    }[sort]
    return list.sort(cmp)
  }, [data.domestic, bucket, sort, q])

  const th = (id, he, en) => (
    <th scope="col">
      {id ? <button type="button" className={`ad-th ${sort === id ? 'on' : ''}`} onClick={() => setSort(id)} aria-pressed={sort === id}>{tt(he, en)}{sort === id ? ' ▾' : ''}</button> : tt(he, en)}
    </th>
  )

  return (
    <>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
        <Seg label={tt('נפח גלישה', 'Data volume')} value={bucket} onChange={setBucket} options={GB_BUCKETS.map((b) => ({ id: b.id, label: lang === 'he' ? b.he : b.en }))} />
        <input className="ad-input" placeholder={tt('חיפוש תוכנית…', 'Search plans…')} value={q} onChange={(e) => setQ(e.target.value)} aria-label={tt('חיפוש תוכנית', 'Search plans')} style={{ marginInlineStart: 'auto', width: 190 }} />
      </div>
      <div className="ad-table-wrap">
        <table className="ad-table">
          <thead>
            <tr>
              {th('carrier', 'חברה', 'Carrier')}
              {th(null, 'תוכנית', 'Plan')}
              {th('price', 'מחיר', 'Price')}
              {th('gb', 'גלישה', 'Data')}
              {th(null, 'דקות', 'Minutes')}
              {th(null, 'חו״ל', 'Roaming')}
              {th(null, '5G', '5G')}
              {th(null, '', '')}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const isOurs = p.carrier === ours
              return (
                <tr key={p.key} className={`${isOurs ? 'ours' : ''} ${target?.key === p.key ? 'sel' : ''}`} onClick={() => !isOurs && onPick(p)} title={isOurs ? '' : tt('לחצו כדי להשוות להצעה שלנו', 'Click to compare with our offer')} style={{ cursor: isOurs ? 'default' : 'pointer' }}>
                  <td><CarrierChip id={p.carrier} size={20} showName bold={isOurs} /></td>
                  <td className="name">{p.plan_name}</td>
                  <td>
                    <Num style={{ fontWeight: 800 }}>{ils(p.promoPrice || p.price)}</Num>
                    {p.promoPrice && <div style={{ fontSize: 10.5, color: '#9a4419' }}>{tt(`אח״כ ${ils(p.price)}`, `then ${ils(p.price)}`)}</div>}
                  </td>
                  <td><Num>{fmtGb(p.gb, tt)}</Num></td>
                  <td><Num>{fmtMinutes(p.minutes, tt)}</Num></td>
                  <td>{p.abroadGb ? <Num>{p.abroadGb}GB</Num> : '—'}</td>
                  <td>{p.network === 'max' ? tt('מתועדף', 'Priority') : p.network === 'basic' ? '✓' : '—'}</td>
                  <td><TermsLink plan={p} tt={tt} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {!rows.length && <Empty>{tt('אין תוכניות בסינון הזה', 'No plans in this filter')}</Empty>}
      </div>
    </>
  )
}

function AbroadTable({ data, ours, tt }) {
  const [q, setQ] = useState('')
  const rows = useMemo(() => {
    const needle = q.trim()
    return data.abroad
      .filter((p) => Number(p.price) > 0 && (!needle || `${p.plan_name} ${getCarrierName(p.carrier)} ${(p.extras || []).join(' ')}`.includes(needle)))
      .sort((a, b) => (Number(a.days) || 0) - (Number(b.days) || 0) || a.price - b.price)
  }, [data.abroad, q])
  return (
    <>
      <div style={{ display: 'flex', marginBottom: 10 }}>
        <input className="ad-input" placeholder={tt('חיפוש חבילה / יעד…', 'Search package / destination…')} value={q} onChange={(e) => setQ(e.target.value)} aria-label={tt('חיפוש חבילה', 'Search package')} style={{ marginInlineStart: 'auto', width: 220 }} />
      </div>
      <div className="ad-table-wrap">
        <table className="ad-table">
          <thead><tr><th>{tt('חברה', 'Carrier')}</th><th>{tt('חבילה', 'Package')}</th><th>{tt('ימים', 'Days')}</th><th>{tt('גלישה', 'Data')}</th><th>{tt('דקות', 'Minutes')}</th><th>{tt('מחיר', 'Price')}</th><th /></tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={`${p.carrier}|${p.plan_name}`} className={p.carrier === ours ? 'ours' : ''}>
                <td><CarrierChip id={p.carrier} size={20} showName bold={p.carrier === ours} /></td>
                <td className="name">{p.plan_name}</td>
                <td><Num>{p.days ?? '—'}</Num></td>
                {/* NULL data on a roaming row = a voice-minutes package, not unlimited */}
                <td><Num>{p.data_gb == null ? tt('שיחות בלבד', 'Voice only') : fmtGb(Number(p.data_gb) >= 9999 ? Infinity : Number(p.data_gb), tt)}</Num></td>
                <td><Num>{p.minutes ?? '—'}</Num></td>
                <td><Num style={{ fontWeight: 800 }}>{ils(Number(p.price))}</Num></td>
                <td>{p.terms_url && <a className="ad-link" href={p.terms_url} target="_blank" rel="noopener noreferrer">{tt('תנאים', 'Terms')}</a>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <Empty>{tt('אין חבילות', 'No packages')}</Empty>}
      </div>
    </>
  )
}

/** Content services as a service × carrier matrix - "is the cyber service free there?" */
function ContentMatrix({ data, ours, tt }) {
  const { services, carriers, cell } = useMemo(() => {
    const services = [...new Set(data.content.map((c) => c.service))]
    const carriers = [...new Set(data.content.map((c) => c.carrier))].sort((a, b) => (a === ours ? -1 : b === ours ? 1 : 0))
    const cell = new Map(data.content.map((c) => [`${c.service}|${c.carrier}`, c]))
    return { services, carriers, cell }
  }, [data.content, ours])
  if (!services.length) return <Empty>{tt('אין נתוני שירותים', 'No service data')}</Empty>
  return (
    <div className="ad-table-wrap">
      <table className="ad-table">
        <thead>
          <tr>
            <th>{tt('שירות', 'Service')}</th>
            {carriers.map((c) => <th key={c} className={c === ours ? 'ours-col' : ''}><CarrierChip id={c} size={20} showName bold={c === ours} /></th>)}
          </tr>
        </thead>
        <tbody>
          {services.map((s) => (
            <tr key={s}>
              <td className="name" style={{ fontWeight: 700 }}>{s}</td>
              {carriers.map((c) => {
                const v = cell.get(`${s}|${c}`)
                return (
                  <td key={c} className={c === ours ? 'ours-col' : ''}>
                    {v ? (
                      <>
                        <Num style={{ fontWeight: 700 }}>{v.price || '—'}</Num>
                        {v.free_trial && <div style={{ fontSize: 10.5, color: '#3d6a33' }}>{v.free_trial}</div>}
                      </>
                    ) : <span style={{ color: 'var(--color-moca-muted)' }}>{tt('לא מוצע', 'Not offered')}</span>}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── 4. rail ──────────────────────────────────────────────────────────────

const KIND = {
  drop: ['הוזל', 'Cut', 'win'],
  rise: ['התייקר', 'Rise', 'loss'],
  new: ['חדש', 'New', 'warn'],
  removed: ['הוסר', 'Removed', 'muted'],
  extras: ['הטבות', 'Benefits', 'muted'],
}

function WeeklyRail({ data, tt }) {
  // Benefit diffs can carry the scraper's internal "__info__|…" terms blob - never show it.
  const firstBenefit = (list) => (list || []).find((x) => typeof x === 'string' && !x.startsWith('__info__|'))
  const rows = data.weekly.groups.flatMap((g) => g.rows)
    .filter((r) => r.kind !== 'extras' || firstBenefit(r.diff.added) || firstBenefit(r.diff.removed))
    .sort((a, b) => b.ts - a.ts).slice(0, 12)
  return (
    <Card title={tt('השתנה השבוע אצל המתחרים', 'Changed this week at competitors')} hint={tt('כדי שלא תופתעו בשיחה', 'So nothing surprises you on a call')}>
      {!rows.length && <Empty>{tt('לא היו שינויים השבוע', 'No changes this week')}</Empty>}
      <ul className="ad-feed">
        {rows.map((r, i) => {
          const [he, en, tone] = KIND[r.kind]
          return (
            <li key={i}>
              <CarrierChip id={r.carrier} size={18} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--color-moca-dark)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {r.plan_name}{r.scope === 'abroad' && <span style={{ fontWeight: 400, color: 'var(--color-moca-muted)' }}> · {tt('חו״ל', 'roaming')}</span>}
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--color-moca-sub)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {(r.kind === 'drop' || r.kind === 'rise') && <><Num>{ils(r.oldPrice)}</Num> ← <Num>{ils(r.newPrice)}</Num></>}
                  {r.kind === 'new' && Number.isFinite(r.newPrice) && <Num>{ils(r.newPrice)}</Num>}
                  {r.kind === 'extras' && (firstBenefit(r.diff.added) ? `+ ${firstBenefit(r.diff.added)}` : `- ${firstBenefit(r.diff.removed)}`)}
                </div>
              </div>
              <span className={`ad-pill ${tone}`}>{tt(he, en)}</span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

function ResellerRail({ data, onPick, tt }) {
  const rows = useMemo(() => data.resellers.slice().sort((a, b) => a.price - b.price).slice(0, 8), [data.resellers])
  if (!rows.length) return null
  return (
    <Card title={tt('מבצעים מתחת לקו', 'Below-the-line offers')} hint={tt('פרסומות ודפי נחיתה שלקוחות מצטטים', 'Ads and landing pages customers quote')}>
      <ul className="ad-feed">
        {rows.map((p) => (
          <li key={p.key} className="click" onClick={() => onPick(p)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') onPick(p) }}>
            <CarrierChip id={p.carrier} size={18} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--color-moca-dark)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.plan_name}</div>
              <div style={{ fontSize: 11.5, color: 'var(--color-moca-sub)' }}><Num>{fmtGb(p.gb, tt)}</Num></div>
            </div>
            <Num style={{ fontWeight: 800, color: 'var(--color-moca-dark)' }}>{ils(p.price)}</Num>
          </li>
        ))}
      </ul>
    </Card>
  )
}

// ── page ─────────────────────────────────────────────────────────────────

export default function AgentDeskPage() {
  const { tt, lang } = useLang()
  const { workspace } = useAuth()
  const [override, setOverride] = useState(() => { try { return localStorage.getItem(OURS_KEY) } catch { return null } })
  const ours = (override ?? workspace?.mvno_carrier) || null
  const pickOurs = (id) => { setOverride(id); try { localStorage.setItem(OURS_KEY, id || '') } catch { /* private mode */ } }

  const { loading, error, data, reload } = useAgentDeskData(ours)
  const [target, setTarget] = useState(null)
  const [claim, setClaim] = useState({ carrier: '', price: '', gb: '', unlimited: false })
  const [tab, setTab] = useState('domestic')

  // A row clicked in the table / rail drives the checker: point the claim at
  // that carrier (so the match list contains it) and select it.
  const pickPlan = (p) => {
    setClaim({ carrier: p.source === 'reseller' ? '__resellers' : p.carrier, price: '', gb: '', unlimited: false })
    setTarget(p)
    document.getElementById('ad-checker')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <>
      <PageHeader
        kicker={tt('שירות לקוחות', 'Customer care')}
        title={tt('עמדת נציג', 'Agent desk')}
        subtitle={tt('כל מה שצריך מול לקוח שמשווה למתחרים: מה באמת מציעים שם, מה אנחנו מציעים, ומה להגיד.', 'Everything for a customer comparing to competitors: what they really offer, what we offer, and what to say.')}
      />
      <div className="ad-page">
        {loading && <div style={{ padding: '70px 0', textAlign: 'center' }} role="status" aria-live="polite"><Spinner /></div>}
        {!loading && error && (
          <Card><Empty>{tt('טעינת הנתונים נכשלה.', 'Failed to load data.')} <button type="button" className="ad-link" onClick={reload}>{tt('נסו שוב', 'Retry')}</button></Empty></Card>
        )}
        {!loading && !error && data && (
          <>
            <DeskBar ours={ours} onOurs={pickOurs} data={data} tt={tt} />
            <div className="ad-grid">
              <div className="ad-main">
                <div id="ad-checker" style={{ scrollMarginTop: 80 }}>
                  <ClaimChecker data={data} ours={ours} target={target} setTarget={setTarget} claim={claim} setClaim={setClaim} tt={tt} />
                </div>
                <Card
                  title={tt('מפת השוק', 'Market map')}
                  hint={tab === 'domestic' ? tt('לחצו על שורה כדי להשוות אותה להצעה שלנו', 'Click a row to compare it with our offer') : null}
                  aside={<Seg label={tt('קטגוריה', 'Category')} value={tab} onChange={setTab} options={[
                    { id: 'domestic', label: tt('סלולר', 'Domestic') },
                    { id: 'abroad', label: tt('חבילות חו״ל', 'Roaming') },
                    { id: 'content', label: tt('שירותי תוכן', 'Services') },
                  ]} />}
                >
                  {tab === 'domestic' && <DomesticTable data={data} ours={ours} target={target} onPick={pickPlan} tt={tt} lang={lang} />}
                  {tab === 'abroad' && <AbroadTable data={data} ours={ours} tt={tt} />}
                  {tab === 'content' && <ContentMatrix data={data} ours={ours} tt={tt} />}
                </Card>
              </div>
              <aside className="ad-rail">
                <WeeklyRail data={data} tt={tt} />
                <ResellerRail data={data} onPick={pickPlan} tt={tt} />
              </aside>
            </div>
          </>
        )}
      </div>

      <style>{`
        .ad-page { max-width: 1480px; margin: 0 auto; padding: 16px 28px 40px; display: flex; flex-direction: column; gap: 14px; }
        .ad-card { background: #fff; border: 1px solid var(--color-moca-border); border-radius: 14px; box-shadow: var(--sh-card); min-width: 0; }
        .ad-bar { display: flex; align-items: center; gap: 10px; padding: 10px 14px; flex-wrap: wrap; position: sticky; top: 8px; z-index: 5; }
        .ad-sep { width: 1px; height: 22px; background: var(--color-moca-border); }
        .ad-grid { display: grid; grid-template-columns: 1fr; gap: 14px; align-items: start; }
        @media (min-width: 1180px) { .ad-grid { grid-template-columns: minmax(0, 1fr) 330px; } }
        .ad-main, .ad-rail { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
        .ad-split { display: grid; grid-template-columns: 1fr; gap: 16px; }
        @media (min-width: 900px) { .ad-split { grid-template-columns: 1fr 1.1fr; } }
        .ad-subhead { font-size: 11px; font-weight: 800; letter-spacing: .5px; color: var(--color-moca-muted); margin-bottom: 8px; text-transform: uppercase; }
        .ad-input { background: #fff; border: 1px solid var(--color-moca-border); border-radius: 9px; padding: 8px 11px; font: inherit; font-size: 13px; color: var(--color-moca-dark); }
        .ad-input:disabled { background: var(--color-moca-mist); }
        .ad-field { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 700; color: var(--color-moca-sub); }
        .ad-chips { display: flex; flex-wrap: wrap; gap: 6px; }
        .ad-chip { border: 1px solid var(--color-moca-border); background: #fff; border-radius: 999px; padding: 4px 10px 4px 8px; cursor: pointer; font: inherit; font-size: 12.5px; color: var(--color-moca-text); display: inline-flex; align-items: center; }
        .ad-chip:hover { background: var(--color-moca-mist); }
        .ad-chip.on { border-color: var(--color-moca-bolt); background: var(--color-moca-cream); box-shadow: inset 0 0 0 1px var(--color-moca-bolt); }
        .ad-opt { text-align: start; border: 1px solid var(--color-moca-border); background: #fff; border-radius: 10px; padding: 9px 11px; cursor: pointer; font: inherit; width: 100%; }
        .ad-opt:hover { background: var(--color-moca-mist); }
        .ad-opt.on { border-color: var(--color-moca-bolt); box-shadow: inset 0 0 0 1px var(--color-moca-bolt); background: var(--color-moca-cream); }
        .ad-answer { background: var(--color-moca-mist); border: 1px solid var(--color-moca-sand); border-radius: 12px; padding: 12px 14px; min-width: 0; }
        .ad-offer { background: #fff; border: 1px solid var(--color-moca-border); border-radius: 10px; padding: 10px 12px; }
        .ad-tab { border: 1px solid var(--color-moca-border); background: #fff; border-radius: 8px; padding: 5px 10px; font: inherit; font-size: 12px; font-weight: 700; color: var(--color-moca-sub); cursor: pointer; }
        .ad-tab.on { background: var(--color-moca-bolt); border-color: var(--color-moca-bolt); color: #fff; }
        .ad-fact { font-size: 12px; color: var(--color-moca-text); background: var(--color-moca-cream); border-radius: 6px; padding: 2px 7px; }
        .ad-pill { font-size: 11px; font-weight: 700; border-radius: 999px; padding: 2px 8px; white-space: nowrap; }
        .ad-pill.warn { background: #fbe9dc; color: #9a4419; }
        .ad-pill.win { background: #e5efe0; color: #3d6a33; }
        .ad-pill.loss { background: #f6e1db; color: #8f3520; white-space: normal; }
        .ad-pill.muted { background: var(--color-moca-cream); color: var(--color-moca-sub); }
        .ad-link { background: none; border: none; padding: 0; font: inherit; font-size: 12px; font-weight: 700; color: var(--color-moca-bolt); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
        .ad-script ol { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
        .ad-script li { background: #fff; border: 1px solid var(--color-moca-border); border-radius: 10px; overflow: hidden; }
        .ad-script li.cur { border-color: var(--color-moca-bolt); box-shadow: 0 0 0 1px var(--color-moca-bolt); }
        .ad-script li.done .ad-script-h { color: var(--color-moca-sub); }
        .ad-script-h { display: flex; align-items: center; gap: 8px; width: 100%; background: none; border: 0; padding: 7px 10px; font: inherit; font-size: 12.5px; font-weight: 700; color: var(--color-moca-dark); cursor: pointer; text-align: start; }
        .ad-script-h .n { flex: 0 0 20px; height: 20px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; background: var(--color-moca-cream); color: var(--color-moca-sub); }
        .ad-script li.cur .n { background: var(--color-moca-bolt); color: #fff; }
        .ad-script li.done .n { background: #e5efe0; color: #3d6a33; }
        .ad-script-b { padding: 0 12px 10px; display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
        .ad-script-b .say { margin: 0; font-size: 14px; line-height: 1.6; color: var(--color-moca-text); background: var(--color-moca-mist); border-inline-start: 3px solid var(--color-moca-bolt); border-radius: 6px; padding: 7px 10px; align-self: stretch; }
        .ad-script-b .note { margin: 0; font-size: 12px; line-height: 1.5; color: var(--color-moca-sub); }
        .ad-points { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
        .ad-points li { display: flex; gap: 8px; align-items: flex-start; font-size: 13px; line-height: 1.5; color: var(--color-moca-text); background: #fff; border-radius: 8px; padding: 6px 9px; border: 1px solid var(--color-moca-border); }
        .ad-points .ic { flex: 0 0 18px; height: 18px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; margin-top: 1px; }
        .ad-points .win .ic { background: #e5efe0; color: #3d6a33; }
        .ad-points .warn .ic { background: #fbe9dc; color: #9a4419; }
        .ad-points .loss { color: var(--color-moca-sub); }
        .ad-points .loss .ic { background: var(--color-moca-cream); color: var(--color-moca-sub); }
        .ad-seg { display: inline-flex; background: var(--color-moca-cream); border-radius: 9px; padding: 3px; gap: 2px; flex-wrap: wrap; }
        .ad-seg button { border: none; background: none; border-radius: 7px; padding: 5px 10px; font: inherit; font-size: 12px; font-weight: 700; color: var(--color-moca-sub); cursor: pointer; }
        .ad-seg button.on { background: #fff; color: var(--color-moca-dark); box-shadow: 0 1px 2px rgba(60,30,10,.12); }
        .ad-table-wrap { overflow: auto; max-height: 560px; border: 1px solid var(--color-moca-border); border-radius: 10px; }
        .ad-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
        .ad-table th { position: sticky; top: 0; background: var(--color-moca-cream); text-align: start; font-size: 11px; font-weight: 800; color: var(--color-moca-sub); padding: 8px 10px; white-space: nowrap; z-index: 1; }
        .ad-table td { padding: 7px 10px; border-top: 1px solid #f0e6d9; vertical-align: middle; white-space: nowrap; color: var(--color-moca-text); }
        .ad-table td.name { white-space: normal; min-width: 160px; }
        .ad-table tbody tr:hover { background: var(--color-moca-mist); }
        .ad-table tr.ours { background: rgba(201, 98, 47, 0.07); }
        .ad-table tr.sel { box-shadow: inset 3px 0 0 var(--color-moca-bolt); background: var(--color-moca-cream); }
        .ad-table .ours-col { background: rgba(201, 98, 47, 0.07); }
        .ad-th { background: none; border: none; padding: 0; font: inherit; font-size: 11px; font-weight: 800; color: var(--color-moca-sub); cursor: pointer; }
        .ad-th.on { color: var(--color-moca-dark); }
        .ad-feed { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
        .ad-feed li { display: flex; align-items: center; gap: 9px; padding: 7px 2px; border-top: 1px solid #f0e6d9; }
        .ad-feed li:first-child { border-top: none; }
        .ad-feed li.click { cursor: pointer; border-radius: 8px; }
        .ad-feed li.click:hover { background: var(--color-moca-mist); }
        .ad-page :focus-visible { outline: 3px solid var(--color-moca-bolt); outline-offset: 2px; }
        @media (max-width: 700px) { .ad-page { padding: 12px 14px 32px; } .ad-bar { position: static; } }
      `}</style>
    </>
  )
}
