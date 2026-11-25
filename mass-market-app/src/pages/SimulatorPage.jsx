import { useMemo, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'
import { useAgentDeskData } from '../hooks/useAgentDeskData'
import { BUNDLED_SERVICES, buildDraft, servicePrices, simulatePlan } from '../hooks/useSimulator'
import { CarrierChip, PageHeader } from '../components/moca'
import { getCarrierName } from '../components/moca/carrierMeta'
import { DOMESTIC_LABELS } from '../data/carrierLabels'
import Spinner from '../components/ui/Spinner'

/**
 * /simulator - the launch simulator ("סימולטור השקה").
 *
 * A product manager types a plan that does not exist yet (price, data, promo,
 * perks) and sees where it would land in today's market: who already gives at
 * least the same data for no more money, whom it would beat, the price it has
 * to hit, and whether it clashes with our own rate card. Nothing is saved and
 * nothing is sent to the server - it reads the same feeds as /agent-desk and
 * all the maths is in hooks/useSimulator.js.
 */

const OURS_KEY = 'moca_sim_ours_carrier'
const EMPTY = { price: '', gb: '', unlimited: false, promoPrice: '', promoMonths: '', abroadGb: '', network: 'none', minutesUnlimited: true, voucher: '', freeApps: false, appsValue: '', countPerks: false, svc: {}, svcValue: {} }

const SERVICE_LABELS = {
  cyber: ['סייבר רשתי', 'Network cyber protection'],
  watch: ['eSIM לשעון', 'Watch eSIM'],
  song: ['שיר בהמתנה', 'Ring-back tone'],
  antivirus: ['אנטי וירוס', 'Antivirus'],
}

const EDGE_LABELS = {
  ...SERVICE_LABELS,
  abroad: ['חו״ל', 'roaming'],
  network: ['5G', '5G'],
  minutes: ['דקות', 'minutes'],
  voucher: ['שובר לציוד קצה', 'device voucher'],
  apps: ['גלישה חינם באפליקציות', 'free app browsing'],
}

const ils = (n) => (Number.isFinite(n) ? `₪${(Math.round(n * 10) / 10).toLocaleString('en-US')}` : '-')
const ilsR = (n) => (Number.isFinite(n) ? `₪${Math.round(n).toLocaleString('en-US')}` : '-')

function fmtGb(gb, tt) {
  if (gb === Infinity) return tt('ללא הגבלה', 'Unlimited')
  if (gb == null) return '-'
  return `${Math.round(gb).toLocaleString('en-US')}GB`
}

function Num({ children, style }) {
  return <span className="tnum" style={{ direction: 'ltr', unicodeBidi: 'isolate', display: 'inline-block', ...style }}>{children}</span>
}

function Card({ title, hint, children }) {
  return (
    <section className="sim-card">
      {title && (
        <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: 'var(--color-moca-dark)' }}>{title}</h2>
          {hint && <span style={{ fontSize: 11.5, color: 'var(--color-moca-muted)' }}>{hint}</span>}
        </header>
      )}
      {children}
    </section>
  )
}

function Field({ label, children, hint }) {
  return (
    <label className="sim-field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}

function PlanRow({ plan, tt, aside }) {
  return (
    <li className="sim-row">
      <CarrierChip id={plan.carrier} size={24} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className="sim-name">{getCarrierName(plan.carrier)} · {plan.plan_name}</div>
        <div className="sim-sub">
          <Num>{ils(plan.promoPrice || plan.price)}</Num> {tt('לחודש', '/mo')} · <Num>{fmtGb(plan.gb, tt)}</Num>
          {plan.promoPrice && plan.promoMonths ? <> · {tt(`מבצע ל-${plan.promoMonths} ח׳, אח״כ`, `promo ${plan.promoMonths} mo, then`)} <Num>{ils(plan.price)}</Num></> : null}
        </div>
      </div>
      {aside}
    </li>
  )
}

const VERDICTS = {
  leader:    { tone: 'win',  he: 'אין בשוק חבילה שנותנת לפחות אותו נפח במחיר שנתי נמוך או שווה', en: 'No plan in the market gives at least this data for the same yearly cost or less' },
  contested: { tone: 'warn', he: 'יש מתחרה אחד או שניים שנותנים לפחות אותו נפח בפחות כסף', en: 'One or two competitors give at least this data for less' },
  dominated: { tone: 'loss', he: 'כמה מתחרים כבר נותנים לפחות אותו נפח בפחות כסף', en: 'Several competitors already give at least this data for less' },
  alone:     { tone: 'win',  he: 'אף מתחרה לא מציע נפח כזה או גבוה ממנו', en: 'No competitor offers this much data or more' },
}

function Results({ sim, ours, tt }) {
  const v = VERDICTS[sim.verdict]
  const d = sim.draft
  const gapToTarget = sim.targetMonthly != null ? d.yearCost / 12 - sim.targetMonthly : null
  return (
    <>
      <section className={`sim-card sim-verdict ${v.tone}`} role="status" aria-live="polite">
        <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--color-moca-dark)' }}>{tt(v.he, v.en)}</div>
        <div className="sim-tiles">
          <div>
            <small>{d.perksCounted ? tt('עלות שנה ראשונה, אחרי הטבות', 'First-year cost, after perks') : tt('עלות שנה ראשונה', 'First-year cost')}</small>
            <b><Num>{ilsR(d.yearCost)}</Num></b>
            {d.perksCounted && <small>{tt('לפני הטבות', 'Before perks')} <Num>{ilsR(d.grossYearCost)}</Num></small>}
          </div>
          <div><small>{tt('מקום בין החבילות המקבילות', 'Rank among comparable plans')}</small><b><Num>{sim.rank}</Num> {tt('מתוך', 'of')} <Num>{sim.rankOf}</Num></b></div>
          <div><small>{tt('זול יותר מ', 'Cheaper than')}</small><b>{sim.cheaperThanPct == null ? '-' : <><Num>{sim.cheaperThanPct}%</Num> {tt('מהשוק', 'of the market')}</>}</b></div>
          <div>
            <small>{tt('מחיר יעד כדי להוביל', 'Price to lead')}</small>
            <b>{sim.targetMonthly == null ? '-' : <><Num>{ils(sim.targetMonthly)}</Num> {tt('לחודש', '/mo')}</>}</b>
          </div>
        </div>
        {d.perksValue > 0 && (
          <p className="sim-note">
            {tt('שווי ההטבות בשנה הראשונה: ', 'Perks value over year one: ')}<Num style={{ fontWeight: 800 }}>{ilsR(d.perksValue)}</Num>
            {' ('}
            {[
              d.voucherValue > 0 && tt(`שובר לציוד קצה ${ilsR(d.voucherValue)}`, `device voucher ${ilsR(d.voucherValue)}`),
              d.appsMonthly > 0 && tt(`גלישה חינם באפליקציות ${ils(d.appsMonthly)} לחודש`, `free app browsing ${ils(d.appsMonthly)}/mo`),
              ...d.services.filter((s) => s.monthly > 0).map((s) => tt(`${SERVICE_LABELS[s.id][0]} ${ils(s.monthly)} לחודש`, `${SERVICE_LABELS[s.id][1]} ${ils(s.monthly)}/mo`)),
            ].filter(Boolean).join(' + ')}
            {'). '}
            {d.perksCounted
              ? tt('השווי הופחת מעלות השנה הראשונה של החבילה החדשה. הטבות של מתחרים לא מתומחרות, ולכן ההשוואה נוטה לטובתנו.', 'It was deducted from the new plan\'s first-year cost. Competitors\' perks are not priced, so the comparison leans in our favour.')
              : tt('השווי לא משוקלל בדירוג. אפשר להפעיל את השקלול בטופס.', 'It is not weighed into the ranking. You can switch that on in the form.')}
          </p>
        )}
        {gapToTarget != null && gapToTarget > 0.05 && sim.cheapestComparable && (
          <p className="sim-note">
            {tt(
              `כדי להשתוות לחבילה המקבילה הזולה ביותר (${getCarrierName(sim.cheapestComparable.carrier)}), העלות החודשית הממוצעת בשנה הראשונה צריכה לרדת ב-${ils(gapToTarget)}.`,
              `To match the cheapest comparable plan (${getCarrierName(sim.cheapestComparable.carrier)}), the average monthly cost over year one has to drop by ${ils(gapToTarget)}.`,
            )}
          </p>
        )}
      </section>

      <Card title={tt('הסולם', 'The ladder')} hint={tt('חבילות עם לפחות אותו נפח, לפי עלות שנה ראשונה', 'Plans with at least the same data, by first-year cost')}>
        <ol className="sim-list">
          {sim.ladder.map((p) => p.isDraft ? (
            <li key="draft" className="sim-row draft">
              <span className="sim-you">{tt('החבילה החדשה', 'New plan')}</span>
              <div style={{ flex: 1 }} className="sim-sub"><Num>{ils(d.promoPrice || d.price)}</Num> {tt('לחודש', '/mo')} · <Num>{fmtGb(d.gb, tt)}</Num></div>
              <Num style={{ fontWeight: 800 }}>{ilsR(d.yearCost)}</Num>
            </li>
          ) : (
            <PlanRow key={p.key} plan={p} tt={tt} aside={<Num style={{ fontWeight: 700, color: 'var(--color-moca-sub)' }}>{ilsR(p.yearCost)}</Num>} />
          ))}
        </ol>
      </Card>

      <div className="sim-two">
        <Card title={tt('מי עדיף עליה', 'Who beats it')} hint={tt('לפחות אותו נפח, בפחות כסף', 'At least the same data, for less')}>
          {sim.dominators.length === 0
            ? <p className="sim-empty">{tt('אין כזה במחירון הרשמי של המתחרים.', 'None on the competitors\' official rate cards.')}</p>
            : (
              <ul className="sim-list">
                {sim.dominators.slice(0, 6).map(({ plan, edges }) => (
                  <PlanRow key={plan.key} plan={plan} tt={tt} aside={
                    <span style={{ textAlign: 'end' }}>
                      <span className="sim-pill loss"><Num>{ilsR(d.yearCost - plan.yearCost)}</Num> {tt('זול יותר בשנה', 'cheaper / yr')}</span>
                      {edges.length > 0 && (
                        <span className="sim-edge">
                          {tt('היתרון שלנו: ', 'Our edge: ')}
                          {edges.map((e) => tt(...EDGE_LABELS[e])).join(', ')}
                        </span>
                      )}
                    </span>
                  } />
                ))}
              </ul>
            )}
          {sim.dominators.length > 6 && <p className="sim-empty">{tt(`ועוד ${sim.dominators.length - 6} חבילות`, `and ${sim.dominators.length - 6} more`)}</p>}
        </Card>

        <Card title={tt('את מי היא מנצחת', 'Whom it beats')} hint={tt('נותנת לפחות אותו נפח, בפחות כסף', 'Gives at least the same data, for less')}>
          {sim.beaten.length === 0
            ? <p className="sim-empty">{tt('החבילה לא עדיפה על אף חבילה קיימת של מתחרה.', 'It does not beat any existing competitor plan.')}</p>
            : (
              <ul className="sim-list">
                {sim.beaten.slice(0, 6).map((plan) => (
                  <PlanRow key={plan.key} plan={plan} tt={tt} aside={<span className="sim-pill win"><Num>{ilsR(plan.yearCost - d.yearCost)}</Num> {tt('יקר יותר בשנה', 'pricier / yr')}</span>} />
                ))}
              </ul>
            )}
          {sim.beaten.length > 6 && <p className="sim-empty">{tt(`ועוד ${sim.beaten.length - 6} חבילות`, `and ${sim.beaten.length - 6} more`)}</p>}
        </Card>
      </div>

      <Card title={tt('מול כל מתחרה', 'Against each competitor')} hint={tt('החבילה הזולה ביותר של כל מתחרה עם לפחות אותו נפח', 'Each competitor\'s cheapest plan with at least the same data')}>
        <div className="sim-table-wrap">
          <table className="sim-table">
            <thead><tr>
              <th>{tt('מתחרה', 'Competitor')}</th><th>{tt('חבילה', 'Plan')}</th><th>{tt('נפח', 'Data')}</th>
              <th>{tt('שנה ראשונה', 'Year one')}</th><th>{tt('פער שנתי', 'Yearly gap')}</th>
            </tr></thead>
            <tbody>
              {sim.perCarrier.map((r) => (
                <tr key={r.carrier}>
                  <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><CarrierChip id={r.carrier} size={22} />{getCarrierName(r.carrier)}</span></td>
                  {r.plan ? (
                    <>
                      <td>{r.plan.plan_name}</td>
                      <td><Num>{fmtGb(r.plan.gb, tt)}</Num></td>
                      <td><Num>{ilsR(r.plan.yearCost)}</Num></td>
                      <td>
                        <span className={`sim-pill ${r.yearGap > 0.5 ? 'win' : r.yearGap < -0.5 ? 'loss' : 'muted'}`}>
                          {Math.abs(r.yearGap) <= 0.5
                            ? tt('שווה', 'Equal')
                            : <><Num>{ilsR(Math.abs(r.yearGap))}</Num> {r.yearGap > 0 ? tt('לטובתנו', 'in our favour') : tt('לטובתם', 'in their favour')}</>}
                        </span>
                      </td>
                    </>
                  ) : <td colSpan={4} style={{ color: 'var(--color-moca-muted)' }}>{tt('אין חבילה עם נפח כזה', 'No plan with this much data')}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {ours && (sim.ownClash.undercut.length > 0 || sim.ownClash.redundant.length > 0) && (
        <Card title={tt('מול המחירון שלנו', 'Against our own rate card')} hint={getCarrierName(ours)}>
          {sim.ownClash.redundant.length > 0 && (
            <>
              <p className="sim-note">{tt('חבילות קיימות שלנו שכבר נותנות לפחות אותו נפח בפחות כסף, כך שהחבילה החדשה מיותרת לידן:', 'Existing plans of ours that already give at least this data for less, making the new plan redundant:')}</p>
              <ul className="sim-list">{sim.ownClash.redundant.slice(0, 4).map((p) => <PlanRow key={p.key} plan={p} tt={tt} aside={<Num>{ilsR(p.yearCost)}</Num>} />)}</ul>
            </>
          )}
          {sim.ownClash.undercut.length > 0 && (
            <>
              <p className="sim-note">{tt('חבילות קיימות שלנו שהחבילה החדשה עדיפה עליהן, ולקוחות עשויים לעבור מהן אליה:', 'Existing plans of ours the new plan beats - customers may move from them to it:')}</p>
              <ul className="sim-list">{sim.ownClash.undercut.slice(0, 4).map((p) => <PlanRow key={p.key} plan={p} tt={tt} aside={<Num>{ilsR(p.yearCost)}</Num>} />)}</ul>
            </>
          )}
        </Card>
      )}

      {sim.btl.length > 0 && (
        <Card title={tt('מתחת לקו', 'Below the line')} hint={tt('הצעות משווקים ודפי נחיתה שעדיפות על החבילה', 'Reseller and landing-page offers that beat the plan')}>
          <ul className="sim-list">
            {sim.btl.slice(0, 5).map((p) => <PlanRow key={p.key} plan={p} tt={tt} aside={<span className="sim-pill loss"><Num>{ilsR(d.yearCost - p.yearCost)}</Num> {tt('זול יותר בשנה', 'cheaper / yr')}</span>} />)}
          </ul>
        </Card>
      )}
    </>
  )
}

export default function SimulatorPage() {
  const { tt, lang } = useLang()
  const { workspace } = useAuth()
  const [override, setOverride] = useState(() => { try { return localStorage.getItem(OURS_KEY) } catch { return null } })
  const ours = (override ?? workspace?.mvno_carrier) || null
  const pickOurs = (id) => { setOverride(id); try { localStorage.setItem(OURS_KEY, id || '') } catch { /* private mode */ } }

  const { loading, error, data, reload } = useAgentDeskData(ours)
  const [form, setForm] = useState(EMPTY)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const setSvc = (group, id) => (e) => setForm((f) => ({ ...f, [group]: { ...f[group], [id]: e.target.type === 'checkbox' ? e.target.checked : e.target.value } }))

  const svcPrices = useMemo(() => servicePrices(data?.content, ours), [data, ours])
  const draft = useMemo(() => buildDraft(form, svcPrices), [form, svcPrices])
  const sim = useMemo(() => (data && draft ? simulatePlan(draft, data.domestic, ours, data.resellers) : null), [data, draft, ours])
  const carrierOptions = useMemo(
    () => Object.keys(DOMESTIC_LABELS).map((id) => ({ id, label: getCarrierName(id) })).sort((a, b) => a.label.localeCompare(b.label, 'he')),
    [],
  )
  const promoBad = Number(form.promoPrice) > 0 && Number(form.price) > 0 && Number(form.promoPrice) >= Number(form.price)

  return (
    <>
      <PageHeader
        kicker={tt('תכנון מוצר', 'Product planning')}
        title={tt('סימולטור השקה', 'Launch simulator')}
        subtitle={tt('הזינו חבילה שעוד לא קיימת וראו איפה היא תעמוד בשוק של היום. שום דבר לא נשמר.', 'Type a plan that does not exist yet and see where it would stand in today\'s market. Nothing is saved.')}
      />
      <div dir={lang === 'he' ? 'rtl' : 'ltr'} className="max-w-6xl mx-auto px-4 py-4 pb-20 md:pb-8 sim-page">
        {loading && <div style={{ padding: '70px 0', textAlign: 'center' }} role="status" aria-live="polite"><Spinner /></div>}
        {!loading && error && (
          <Card><p className="sim-empty">{tt('טעינת הנתונים נכשלה.', 'Failed to load data.')} <button type="button" className="sim-link" onClick={reload}>{tt('נסו שוב', 'Retry')}</button></p></Card>
        )}
        {!loading && !error && data && (
          <div className="sim-grid">
            <div className="sim-form">
              <Card title={tt('החבילה החדשה', 'The new plan')}>
                <Field label={tt('החברה שלנו', 'Our carrier')} hint={tt('החבילות שלה לא נספרות כמתחרות', 'Its plans are not counted as competitors')}>
                  <select value={ours || ''} onChange={(e) => pickOurs(e.target.value)} className="sim-input">
                    <option value="">{tt('ללא (כל השוק)', 'None (whole market)')}</option>
                    {carrierOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                  </select>
                </Field>
                <Field label={tt('מחיר מחירון לחודש (₪)', 'List price per month (₪)')}>
                  <input className="sim-input" type="number" inputMode="decimal" min="1" step="0.1" value={form.price} onChange={set('price')} placeholder="39.9" />
                </Field>
                <Field label={tt('נפח גלישה (GB)', 'Data (GB)')}>
                  <input className="sim-input" type="number" inputMode="decimal" min="1" value={form.unlimited ? '' : form.gb} onChange={set('gb')} disabled={form.unlimited} placeholder="500" />
                </Field>
                <label className="sim-check"><input type="checkbox" checked={form.unlimited} onChange={set('unlimited')} /> {tt('גלישה ללא הגבלה', 'Unlimited data')}</label>
                <div className="sim-pair">
                  <Field label={tt('מחיר מבצע (₪)', 'Promo price (₪)')}>
                    <input className="sim-input" type="number" inputMode="decimal" min="0" step="0.1" value={form.promoPrice} onChange={set('promoPrice')} placeholder={tt('אין', 'None')} />
                  </Field>
                  <Field label={tt('חודשי מבצע', 'Promo months')}>
                    <input className="sim-input" type="number" inputMode="numeric" min="0" max="12" value={form.promoMonths} onChange={set('promoMonths')} placeholder="3" />
                  </Field>
                </div>
                {promoBad && <p className="sim-err" role="alert">{tt('מחיר המבצע צריך להיות נמוך ממחיר המחירון.', 'The promo price has to be below the list price.')}</p>}
                <Field label={tt('גלישה בחו״ל כלולה (GB)', 'Bundled roaming data (GB)')}>
                  <input className="sim-input" type="number" inputMode="decimal" min="0" value={form.abroadGb} onChange={set('abroadGb')} placeholder="0" />
                </Field>
                <Field label={tt('רשת', 'Network')}>
                  <select className="sim-input" value={form.network} onChange={set('network')}>
                    <option value="none">{tt('ללא 5G', 'No 5G')}</option>
                    <option value="basic">5G</option>
                    <option value="max">{tt('5G עם תעדוף', '5G with priority')}</option>
                  </select>
                </Field>
                <label className="sim-check"><input type="checkbox" checked={form.minutesUnlimited} onChange={set('minutesUnlimited')} /> {tt('דקות ללא הגבלה', 'Unlimited minutes')}</label>
                <fieldset className="sim-perks">
                  <legend>{tt('הטבות שוות כסף', 'Perks worth money')}</legend>
                  <Field label={tt('שובר לרכישת ציוד קצה (₪)', 'Device purchase voucher (₪)')} hint={tt('סכום חד-פעמי', 'One-time amount')}>
                    <input className="sim-input" type="number" inputMode="decimal" min="0" step="10" value={form.voucher} onChange={set('voucher')} placeholder="0" />
                  </Field>
                  <label className="sim-check"><input type="checkbox" checked={form.freeApps} onChange={set('freeApps')} /> {tt('גלישה חינם באפליקציות מובילות', 'Free browsing in leading apps')}</label>
                  {form.freeApps && (
                    <Field label={tt('שווי הגלישה באפליקציות (₪ לחודש)', 'App browsing value (₪ per month)')} hint={tt('הערכה שלכם. ריק = יוצג כיתרון בלי שווי כספי', 'Your estimate. Empty = shown as an edge with no money value')}>
                      <input className="sim-input" type="number" inputMode="decimal" min="0" step="0.5" value={form.appsValue} onChange={set('appsValue')} placeholder="0" />
                    </Field>
                  )}
                  <div className="sim-svc-title">{tt('שירותים ללא תשלום נוסף', 'Services at no extra charge')}</div>
                  {BUNDLED_SERVICES.map((s) => {
                    const sp = svcPrices[s.id] || {}
                    const label = tt(...SERVICE_LABELS[s.id])
                    return (
                      <div key={s.id} className="sim-svc">
                        <label className="sim-check"><input type="checkbox" checked={!!form.svc[s.id]} onChange={setSvc('svc', s.id)} /> {label}</label>
                        {form.svc[s.id] && (
                          <Field
                            label={tt('שווי (₪ לחודש)', 'Value (₪ per month)')}
                            hint={sp.suggested == null
                              ? tt('אין מחיר שוק לשירות הזה, הזינו הערכה', 'No market price for this service, enter an estimate')
                              : sp.ours != null
                                ? tt(`ריק = המחיר שלנו היום, ${ils(sp.ours)}. חציון השוק ${ils(sp.median)}`, `Empty = our price today, ${ils(sp.ours)}. Market median ${ils(sp.median)}`)
                                : tt(`ריק = חציון השוק, ${ils(sp.median)} (${sp.n} חברות)`, `Empty = market median, ${ils(sp.median)} (${sp.n} carriers)`)}
                          >
                            <input className="sim-input" type="number" inputMode="decimal" min="0" step="0.5" aria-label={`${label} - ${tt('שווי לחודש', 'value per month')}`}
                              value={form.svcValue[s.id] ?? ''} onChange={setSvc('svcValue', s.id)} placeholder={sp.suggested != null ? String(sp.suggested) : '0'} />
                          </Field>
                        )}
                      </div>
                    )
                  })}
                  <label className="sim-check" style={{ marginBottom: 0, marginTop: 4 }}>
                    <input type="checkbox" checked={form.countPerks} onChange={set('countPerks')} /> {tt('להפחית את שווי ההטבות מעלות השנה הראשונה', 'Deduct the perks value from the first-year cost')}
                  </label>
                </fieldset>
                <button type="button" className="sim-link" onClick={() => setForm(EMPTY)} style={{ marginTop: 6 }}>{tt('ניקוי הטופס', 'Clear form')}</button>
              </Card>
              <p className="sim-foot">
                {tt(
                  `ההשוואה מול ${data.domestic.length} חבילות במחירון הרשמי, לפי עלות שנה ראשונה (חודשי מבצע במחיר המבצע). חבילות שיחות בלבד לא נכללות. הטבות שאינן מחיר ונפח מוצגות כיתרון, לא משוקללות בדירוג. הטבות שוות כסף (שובר, גלישה באפליקציות, שירותים ללא תשלום) מופחתות מהעלות רק אם בחרתם בכך.`,
                  `Compared with ${data.domestic.length} official rate-card plans on first-year cost (promo months at the promo price). Voice-only plans are excluded. Perks other than price and data are shown as an edge, not weighed into the ranking. Perks worth money (voucher, app browsing, free services) are deducted from the cost only if you choose so.`,
                )}
                {data.updatedHours != null && data.updatedHours > 36 ? ' ' + tt(`שימו לב: הנתונים עודכנו לפני ${data.updatedHours} שעות.`, `Note: the data was updated ${data.updatedHours} hours ago.`) : ''}
              </p>
            </div>
            <div className="sim-results">
              {sim
                ? <Results sim={sim} ours={ours} tt={tt} />
                : <Card><p className="sim-empty">{tt('הזינו מחיר ונפח כדי לראות את התוצאה.', 'Enter a price and data amount to see the result.')}</p></Card>}
            </div>
          </div>
        )}
      </div>

      <style>{`
        .sim-grid { display: grid; grid-template-columns: 1fr; gap: 14px; align-items: start; }
        @media (min-width: 900px) { .sim-grid { grid-template-columns: 300px minmax(0, 1fr); } .sim-form { position: sticky; top: 76px; } }
        .sim-results { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
        .sim-card { background: #fff; border: 1px solid var(--color-moca-border); border-radius: 14px; box-shadow: var(--sh-card); padding: 16px; min-width: 0; }
        .sim-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: 700; color: var(--color-moca-sub); margin-bottom: 10px; }
        .sim-field small { font-weight: 400; font-size: 11px; color: var(--color-moca-muted); }
        .sim-input { background: #fff; border: 1px solid var(--color-moca-border); border-radius: 9px; padding: 8px 11px; font: inherit; font-size: 14px; color: var(--color-moca-dark); width: 100%; min-width: 0; }
        .sim-input:disabled { background: var(--color-moca-mist); }
        .sim-input:focus-visible, .sim-link:focus-visible { outline: 3px solid var(--color-moca-bolt); outline-offset: 1px; }
        .sim-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .sim-check { display: flex; align-items: center; gap: 7px; font-size: 13px; color: var(--color-moca-text); margin: 0 0 12px; cursor: pointer; }
        .sim-perks { border: 1px dashed var(--color-moca-border); border-radius: 10px; padding: 10px 11px 11px; margin: 2px 0 10px; min-width: 0; }
        .sim-perks legend { font-size: 12px; font-weight: 800; color: var(--color-moca-dark); padding: 0 6px; }
        .sim-perks .sim-check { align-items: flex-start; line-height: 1.35; }
        .sim-perks .sim-check input { margin-top: 2px; flex: none; }
        .sim-svc-title { font-size: 12px; font-weight: 700; color: var(--color-moca-sub); margin: 4px 0 8px; padding-top: 10px; border-top: 1px solid var(--color-moca-cream); }
        .sim-svc .sim-check { margin-bottom: 8px; }
        .sim-err { font-size: 12px; color: #8f3520; margin: -4px 0 10px; }
        .sim-foot { font-size: 11.5px; line-height: 1.6; color: var(--color-moca-muted); margin: 10px 4px 0; }
        .sim-link { background: none; border: none; padding: 0; font: inherit; font-size: 12px; font-weight: 700; color: var(--color-moca-bolt); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
        .sim-verdict { border-inline-start-width: 5px; }
        .sim-verdict.win { border-inline-start-color: #4a7c3f; }
        .sim-verdict.warn { border-inline-start-color: #c9622f; }
        .sim-verdict.loss { border-inline-start-color: #b4472d; }
        .sim-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 12px; }
        .sim-tiles > div { background: var(--color-moca-mist); border-radius: 10px; padding: 10px 12px; display: flex; flex-direction: column; gap: 3px; }
        .sim-tiles small { font-size: 11.5px; color: var(--color-moca-sub); }
        .sim-tiles b { font-size: 17px; font-weight: 800; color: var(--color-moca-dark); }
        .sim-note { font-size: 12.5px; line-height: 1.6; color: var(--color-moca-text); margin: 10px 0 8px; }
        .sim-empty { font-size: 12.5px; color: var(--color-moca-muted); margin: 6px 0; line-height: 1.6; }
        .sim-two { display: grid; grid-template-columns: 1fr; gap: 14px; }
        @media (min-width: 1100px) { .sim-two { grid-template-columns: 1fr 1fr; } }
        .sim-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
        .sim-row { display: flex; align-items: center; gap: 9px; border: 1px solid var(--color-moca-border); border-radius: 10px; padding: 8px 10px; min-width: 0; }
        .sim-row.draft { border-color: var(--color-moca-bolt); background: var(--color-moca-cream); box-shadow: inset 0 0 0 1px var(--color-moca-bolt); }
        .sim-you { font-size: 11.5px; font-weight: 800; color: #fff; background: var(--color-moca-bolt); border-radius: 999px; padding: 2px 9px; white-space: nowrap; }
        .sim-name { font-size: 12.5px; font-weight: 700; color: var(--color-moca-dark); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .sim-sub { font-size: 12px; color: var(--color-moca-sub); }
        .sim-pill { font-size: 11px; font-weight: 700; border-radius: 999px; padding: 2px 8px; white-space: nowrap; display: inline-block; }
        .sim-pill.win { background: #e5efe0; color: #3d6a33; }
        .sim-pill.loss { background: #f6e1db; color: #8f3520; }
        .sim-pill.muted { background: var(--color-moca-cream); color: var(--color-moca-sub); }
        .sim-edge { display: block; font-size: 11px; color: var(--color-moca-sub); margin-top: 3px; }
        .sim-table-wrap { overflow-x: auto; }
        .sim-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
        .sim-table th { text-align: start; font-size: 11px; font-weight: 800; color: var(--color-moca-muted); padding: 6px 8px; border-bottom: 1px solid var(--color-moca-border); white-space: nowrap; }
        .sim-table td { padding: 7px 8px; border-bottom: 1px solid var(--color-moca-cream); color: var(--color-moca-text); vertical-align: middle; }
      `}</style>
    </>
  )
}
