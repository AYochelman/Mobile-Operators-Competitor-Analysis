import { useMemo, useState } from 'react'
import { api } from '../lib/api'
import { planTrip, coverageOf } from '../lib/tripPlanner'
import { DEST_ISO_BY_HE, destLabel } from '../data/hotelDestinations'
import { isCruiseDest } from '../data/destI18n'
import { PROVIDER_LOGOS } from '../data/providerLogos'

/**
 * Multi-destination trip planner for /esim-deals (lazy-loaded: it pulls in the
 * per-provider coverage lists, which the single-destination page never needs).
 *
 * The traveller lists the countries of the trip and the days in each; the
 * planner answers with the cheapest combination - one eSIM per country, one
 * regional / global bundle, or a mix - next to the price of the two plain
 * alternatives, so the saving is visible and checkable. Server: POST
 * /api/esim/trip (esim_trip.py); the split itself: lib/tripPlanner.js.
 */

const TX = {
  he: {
    title: 'טיול עם כמה יעדים',
    sub: 'מוסיפים את המדינות לפי סדר הטיול ומקבלים את השילוב הזול ביותר: חבילה לכל מדינה, חבילה אזורית אחת, או שילוב.',
    country: 'מדינה', days: 'ימים', pick: 'בחירת מדינה', add: 'הוספת יעד', remove: 'הסרת היעד',
    data: 'כמה גלישה לכל הטיול?', unl: 'ללא הגבלה', go: 'חישוב השילוב הזול ביותר', busy: 'מחשבים…',
    errPick: 'יש לבחור מדינה לכל יעד.', errDays: 'מספר הימים בכל יעד צריך להיות בין 1 ל-90, ועד 90 ימים בסך הכול.',
    errDup: 'אותה מדינה מופיעה ברצף פעמיים. אפשר לאחד את הימים ליעד אחד.',
    errLoad: 'לא ניתן היה לחשב כרגע. נסו שוב בעוד רגע.',
    none: 'לא נמצאה חבילה שמתאימה לכל היעדים באורך ובנפח שנבחרו. אפשר לנסות פחות גלישה או לבדוק כל מדינה בנפרד.',
    best: 'השילוב הזול ביותר', total: 'סך הכול', saving: 'חיסכון של {x} לעומת חבילה נפרדת לכל מדינה',
    sameAsSeparate: 'במסלול הזה חבילה נפרדת לכל מדינה היא האפשרות הזולה ביותר.',
    altSeparate: 'חבילה נפרדת לכל מדינה', altSingle: 'חבילה אחת לכל הטיול', altNone: 'אין חבילה אחת שמכסה את כל היעדים',
    covers: 'מכסה', bundle: 'חבילה אזורית', buy: 'לרכישה', day: 'יום', dayPl: 'ימים', unlimited: 'ללא הגבלה',
    countriesN: '{n} מדינות בחבילה',
    note: 'הכיסוי של חבילות אזוריות נלקח מרשימות המדינות שהספקים מפרסמים. לפני רכישה כדאי לוודא באתר הספק שהמדינות שלכם כלולות. חלוקת הגלישה בין היעדים היא לפי מספר הימים.',
    close: 'סגירה',
  },
  en: {
    title: 'A trip with several destinations',
    sub: 'Add the countries in the order of your trip and get the cheapest combination: a plan per country, one regional bundle, or a mix.',
    country: 'Country', days: 'Days', pick: 'Choose a country', add: 'Add a destination', remove: 'Remove destination',
    data: 'How much data for the whole trip?', unl: 'Unlimited', go: 'Find the cheapest combination', busy: 'Calculating…',
    errPick: 'Choose a country for every destination.', errDays: 'Each stay has to be 1 to 90 days, and the trip at most 90 days.',
    errDup: 'The same country appears twice in a row. Merge the days into one destination.',
    errLoad: 'Could not calculate right now. Try again in a moment.',
    none: 'No plan fits every destination at the length and data you chose. Try less data, or check each country separately.',
    best: 'Cheapest combination', total: 'Total', saving: '{x} less than a separate plan per country',
    sameAsSeparate: 'For this route a separate plan per country is the cheapest option.',
    altSeparate: 'A separate plan per country', altSingle: 'One plan for the whole trip', altNone: 'No single plan covers every destination',
    covers: 'Covers', bundle: 'Regional bundle', buy: 'Buy', day: 'day', dayPl: 'days', unlimited: 'Unlimited',
    countriesN: '{n} countries in the bundle',
    note: 'Regional bundle coverage comes from the country lists the providers publish. Before buying, check on the provider site that your countries are included. Data is split between destinations by days.',
    close: 'Close',
  },
}

const GB_OPTS = [5, 10, 20, 'unl']
const ils0 = (n) => `₪${Math.round(n).toLocaleString('en-US')}`

function ProvChip({ pv, provider }) {
  const [err, setErr] = useState(false)
  const src = PROVIDER_LOGOS[provider] || (pv.domain ? `https://icons.duckduckgo.com/ip3/${pv.domain}.ico` : null)
  if (src && !err) {
    return <div className="pchip logo" style={{ borderColor: pv.color }}><img src={src} alt="" loading="lazy" onError={() => setErr(true)} /></div>
  }
  const mono = (pv.label || provider).replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || 'GE'
  return <div className="pchip" style={{ background: pv.color }}>{mono}</div>
}

export default function EsimTripPlanner({ destList, lang, campaign, onClose }) {
  const t = TX[lang] || TX.he
  const [legs, setLegs] = useState([{ destination: '', days: 7 }, { destination: '', days: 7 }])
  const [gb, setGb] = useState(10)
  const [state, setState] = useState({ busy: false, error: '', result: null, payload: null, asked: null })

  // Countries = destinations with an ISO code; everything else that is not a
  // cruise label is a bundle destination (regions, "global", "N countries").
  const { countries, bundleDests } = useMemo(() => {
    const cs = [], bs = []
    for (const d of destList || []) {
      const he = d.destination
      if (!he) continue
      if (DEST_ISO_BY_HE[he]) cs.push({ he, label: destLabel(he, lang) })
      else if (!isCruiseDest(he)) bs.push(he)
    }
    cs.sort((a, b) => a.label.localeCompare(b.label, lang === 'he' ? 'he' : 'en'))
    return { countries: cs, bundleDests: bs }
  }, [destList, lang])

  const setLeg = (i, patch) => {
    setLegs((ls) => ls.map((l, k) => (k === i ? { ...l, ...patch } : l)))
    setState((s) => ({ ...s, error: '' }))
  }
  const addLeg = () => setLegs((ls) => (ls.length >= 5 ? ls : [...ls, { destination: '', days: 7 }]))
  const removeLeg = (i) => setLegs((ls) => (ls.length <= 2 ? ls : ls.filter((_, k) => k !== i)))

  const run = () => {
    const clean = legs.map((l) => ({ destination: l.destination, days: Number(l.days) }))
    if (clean.some((l) => !l.destination)) return setState((s) => ({ ...s, error: t.errPick }))
    if (clean.some((l) => !Number.isInteger(l.days) || l.days < 1 || l.days > 90) || clean.reduce((a, l) => a + l.days, 0) > 90) {
      return setState((s) => ({ ...s, error: t.errDays }))
    }
    if (clean.some((l, i) => i > 0 && l.destination === clean[i - 1].destination)) return setState((s) => ({ ...s, error: t.errDup }))
    setState({ busy: true, error: '', result: null, payload: null, asked: null })
    api.getEsimTrip(clean, gb, bundleDests)
      .then((payload) => setState({ busy: false, error: '', payload, asked: clean, result: planTrip(clean, payload.segments) }))
      .catch(() => setState({ busy: false, error: t.errLoad, result: null, payload: null, asked: null }))
  }

  const { busy, error, result, payload, asked } = state
  const providers = payload?.providers || {}
  const name = (he) => destLabel(he, lang)
  const dealMeta = (d) => `${d.gb == null ? t.unlimited : `${+d.gb}GB`} · ${d.days} ${d.days === 1 ? t.day : t.dayPl}`
  const open = (d, dest) => window.open(api.esimGoUrl(d.provider, d.plan_name, lang, dest, campaign), '_blank', 'noopener')

  return (
    <section className="card tp" aria-labelledby="tp-title">
      <div className="tp-head">
        <h2 id="tp-title">{t.title}</h2>
        {onClose && <button type="button" className="tp-x" onClick={onClose} aria-label={t.close}>×</button>}
      </div>
      <p className="tp-sub">{t.sub}</p>

      <ol className="tp-legs">
        {legs.map((l, i) => (
          <li key={i}>
            <span className="tp-n" aria-hidden="true">{i + 1}</span>
            <label className="tp-f tp-grow">
              <span>{t.country}</span>
              <select value={l.destination} onChange={(e) => setLeg(i, { destination: e.target.value })}>
                <option value="">{t.pick}</option>
                {countries.map((c) => <option key={c.he} value={c.he}>{c.label}</option>)}
              </select>
            </label>
            <label className="tp-f tp-days">
              <span>{t.days}</span>
              <input type="number" inputMode="numeric" min="1" max="90" value={l.days} onChange={(e) => setLeg(i, { days: e.target.value })} />
            </label>
            {legs.length > 2 && (
              <button type="button" className="tp-rm" onClick={() => removeLeg(i)} aria-label={`${t.remove} ${i + 1}`}>×</button>
            )}
          </li>
        ))}
      </ol>
      {legs.length < 5 && <button type="button" className="tp-add" onClick={addLeg}>+ {t.add}</button>}

      <div className="tp-q">{t.data}</div>
      <div className="chips" role="group" aria-label={t.data}>
        {GB_OPTS.map((v) => (
          <button key={v} type="button" className={`chip ${gb === v ? 'on' : ''}`} aria-pressed={gb === v} onClick={() => setGb(v)}>
            {v === 'unl' ? t.unl : `${v}GB`}
          </button>
        ))}
      </div>

      {error && <p className="tp-err" role="alert">{error}</p>}
      <button type="button" className="tp-go" onClick={run} disabled={busy}>{busy ? t.busy : t.go}</button>

      <div aria-live="polite">
        {payload && !result && <p className="tp-none">{t.none}</p>}
        {payload && result && (
          <div className="tp-res">
            <div className="tp-res-head">
              <span className="badge b1">{t.best}</span>
              <span className="tp-total" dir="ltr">{ils0(result.total)}</span>
            </div>
            {result.parts.map((p) => {
              const pv = providers[p.deal.provider] || { label: p.deal.provider, color: '#5c3317' }
              const covered = asked.slice(p.from, p.to + 1).map((x) => name(x.destination))
              const cov = p.bundle ? coverageOf(p.deal) : null
              return (
                <div className="pick" key={`${p.from}-${p.to}`}>
                  <div className="tp-cov">
                    {t.covers}: <b>{covered.join(' + ')}</b>
                    {p.bundle && <span className="tp-tag">{t.bundle}: {name(p.deal.dest)}</span>}
                  </div>
                  <div className="deal-row">
                    <ProvChip pv={pv} provider={p.deal.provider} />
                    <div className="deal-info">
                      <div className="deal-provider"><bdi>{pv.label}</bdi></div>
                      <div className="deal-meta"><bdi>{dealMeta(p.deal)}</bdi>{cov ? <> · {t.countriesN.replace('{n}', cov.length)}</> : null}</div>
                    </div>
                    <div className="deal-price"><div className="price-main" dir="ltr">{ils0(p.deal.ils)}</div></div>
                  </div>
                  <button type="button" className="tp-buy" onClick={() => open(p.deal, p.bundle ? p.deal.dest : asked[p.from].destination)}>
                    {t.buy} · <bdi>{pv.label}</bdi>
                  </button>
                </div>
              )
            })}
            <p className="tp-save">
              {result.saving >= 1 ? t.saving.replace('{x}', ils0(result.saving)) : (result.separate ? t.sameAsSeparate : '')}
            </p>
            <ul className="tp-alts">
              {result.separate && <li><span>{t.altSeparate}</span><b dir="ltr">{ils0(result.separate.total)}</b></li>}
              <li><span>{t.altSingle}</span>{result.single ? <b dir="ltr">{ils0(result.single.total)}</b> : <em>{t.altNone}</em>}</li>
            </ul>
            <p className="tp-note">{t.note}</p>
          </div>
        )}
      </div>

      <style>{`
        #esim-app .tp-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
        #esim-app .tp h2{font-size:18px;font-weight:800}
        #esim-app .tp-x,#esim-app .tp-rm{border:1.5px solid var(--line);background:#fff;color:var(--sub);border-radius:999px;width:34px;height:34px;font:inherit;font-size:18px;line-height:1;cursor:pointer;flex:none}
        #esim-app .tp-sub{font-size:13px;color:var(--sub);font-weight:600;margin:4px 0 14px;line-height:1.5}
        #esim-app .tp-legs{list-style:none;display:flex;flex-direction:column;gap:10px}
        #esim-app .tp-legs li{display:flex;align-items:flex-end;gap:8px}
        #esim-app .tp-n{flex:none;width:24px;height:24px;border-radius:50%;background:var(--cream);color:var(--c1);font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center;margin-bottom:10px}
        #esim-app .tp-f{display:flex;flex-direction:column;gap:4px;font-size:11.5px;font-weight:700;color:var(--sub);min-width:0}
        #esim-app .tp-grow{flex:1}
        #esim-app .tp-days{width:68px;flex:none}
        #esim-app .tp-f select,#esim-app .tp-f input{width:100%;border:1.6px solid var(--line);background:var(--bg);border-radius:12px;padding:11px 10px;font:inherit;font-size:15px;font-weight:600;color:var(--ink);min-width:0}
        #esim-app .tp-rm{margin-bottom:5px}
        #esim-app .tp-add{margin-top:10px;border:1.5px dashed var(--line);background:none;color:var(--c1);border-radius:12px;padding:9px 13px;font:inherit;font-size:13px;font-weight:700;cursor:pointer;width:100%}
        #esim-app .tp-q{font-size:13px;font-weight:700;color:var(--c1);margin:16px 0 8px}
        #esim-app .tp-err{color:#8f3520;font-size:13px;font-weight:700;margin-top:12px}
        #esim-app .tp-go,#esim-app .tp-buy{width:100%;border:0;border-radius:14px;background:var(--c1);color:#fff;font:inherit;font-weight:800;cursor:pointer}
        #esim-app .tp-go{margin-top:14px;padding:14px;font-size:15px}
        #esim-app .tp-go:disabled{opacity:.6;cursor:default}
        #esim-app .tp-buy{margin-top:12px;padding:11px;font-size:14px}
        #esim-app .tp-res{margin-top:18px}
        #esim-app .tp-res-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}
        #esim-app .tp-res-head .badge{margin:0}
        #esim-app .tp-total{font-size:24px;font-weight:800;color:var(--c1)}
        #esim-app .tp .pick{border-color:var(--line);box-shadow:none}
        #esim-app .tp-cov{font-size:12.5px;color:var(--sub);font-weight:600;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
        #esim-app .tp-cov b{color:var(--ink)}
        #esim-app .tp-tag{background:var(--cream);color:var(--c1);border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:700}
        #esim-app .tp-save{font-size:13.5px;font-weight:800;color:var(--down-text);margin:4px 0 10px}
        #esim-app .tp-alts{list-style:none;border-top:1px solid var(--cream);padding-top:10px;display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--sub);font-weight:600}
        #esim-app .tp-alts li{display:flex;justify-content:space-between;gap:10px}
        #esim-app .tp-alts b{color:var(--ink)}
        #esim-app .tp-alts em{font-style:normal;color:var(--muted)}
        #esim-app .tp-note,#esim-app .tp-none{font-size:12px;color:var(--muted);line-height:1.55;margin-top:12px}
        #esim-app .tp-none{font-size:13.5px;color:var(--ink);font-weight:600}
      `}</style>
    </section>
  )
}
