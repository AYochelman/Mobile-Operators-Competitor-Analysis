import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'

/* ════════════════════════════════════════════════════════════════════════
   MOCA Guest Connect — public guest portal  (route: /guest/:slug)
   Mobile-first, EN/HE, branded per hotel from the API. Live Israel deal feed
   from /api/guest/<slug>; "Get this deal" routes through Flask /go so the hotel
   earns the affiliate commission. Anonymous engagement beacons only (no PII).
   Standalone visual world — all CSS scoped under #gc-app.
   ════════════════════════════════════════════════════════════════════════ */

const SYM = { USD: '$', EUR: '€', GBP: '£', ILS: '₪' }
const sym = (c) => SYM[c] || (c ? c + ' ' : '')
const fmtNum = (n) => {
  if (n == null) return ''
  const r = Math.round(n * 100) / 100
  return Number.isInteger(r) ? String(r) : r.toFixed(2).replace(/0$/, '')
}

const T = {
  en: {
    sub: 'The best SIM & eSIM deals for your trip — compared live, picked for you.',
    updated: 'Prices updated',
    wizTitle: 'Find your plan in 10 seconds',
    qDays: 'How long are you staying?',
    qData: 'How much data do you need?',
    topPicks: 'Top picks for your trip',
    allDeals: 'All deals',
    helpTitle: 'New to eSIM?',
    h1b: 'Buy online — takes 2 minutes', h1s: "No store, no queue. Pay by card and you're done.",
    h2b: 'Scan the QR code you get by email', h2s: 'Your phone installs the plan automatically.',
    h3b: 'Stay reachable', h3s: 'Keep WhatsApp and your home number active alongside.',
    compat: 'Works on iPhone XS and newer, Samsung Galaxy S20+, Google Pixel 3+. Prefer a physical SIM with an Israeli number? Filter for “Local SIM” above.',
    trust: 'Compared across <b>27 global eSIM providers</b> and <b>10 Israeli carriers</b><br>Refreshed twice a day by MOCA market intelligence',
    disclaim: 'Sample of live market prices. Final price is shown on the provider’s page.',
    days: [{ v: 3, l: '3 days' }, { v: 7, l: '1 week' }, { v: 14, l: '2 weeks' }, { v: 30, l: '1 month' }],
    data: [{ v: 3, l: 'Light', s: '3GB · maps & chat' }, { v: 10, l: 'Regular', s: '10GB · + social' }, { v: 20, l: 'Heavy', s: '20GB · + video' }, { v: 'unl', l: 'Unlimited', s: 'no limits at all' }],
    filters: [{ v: 'all', l: 'All' }, { v: 'esim', l: 'eSIM' }, { v: 'local', l: 'Local SIM' }, { v: 'unl', l: 'Unlimited' }],
    badges: ['BEST MATCH', 'CHEAPEST', 'MAX DATA', 'ALSO GREAT'],
    unlimited: 'Unlimited', daysU: 'days', dayU: 'day', get: 'Get this deal ↗', perGB: '/GB',
    esimTag: 'Global eSIM', localTag: 'Israeli carrier',
    perks: { instant: 'Instant eSIM', unlimited: 'Unlimited data', app: 'App support', hotspot: 'Hotspot', ilNumber: 'Israeli number', calls: 'Calls included', intlMin: 'Intl. minutes', airport: 'Airport pickup' },
    empty: 'No deals match this filter for your trip — try another option.',
    notFound: 'This guest portal is not available.',
    loading: 'Loading the best deals…',
  },
  he: {
    sub: 'חבילות ה-eSIM והסים המשתלמות ביותר לטיול — בהשוואה חיה, מותאם אישית.',
    updated: 'המחירים עודכנו',
    wizTitle: 'מציאת חבילה ב-10 שניות',
    qDays: 'כמה זמן נשארים בישראל?',
    qData: 'כמה דאטה צריך?',
    topPicks: 'ההצעות המובילות לטיול שלכם',
    allDeals: 'כל החבילות',
    helpTitle: 'פעם ראשונה עם eSIM?',
    h1b: 'רוכשים אונליין — לוקח 2 דקות', h1s: 'בלי חנות ובלי תור. משלמים בכרטיס וזהו.',
    h2b: 'סורקים את ה-QR שמגיע למייל', h2s: 'הטלפון מתקין את החבילה אוטומטית.',
    h3b: 'נשארים זמינים', h3s: 'וואטסאפ והמספר מהבית ממשיכים לעבוד במקביל.',
    compat: 'עובד באייפון XS ומעלה, גלקסי S20 ומעלה, פיקסל 3 ומעלה. מעדיפים סים פיזי עם מספר ישראלי? סננו לפי ״סים מקומי״ למעלה.',
    trust: 'מושווה על פני <b>27 ספקי eSIM גלובליים</b> ו-<b>10 מפעילים ישראליים</b><br>מתעדכן פעמיים ביום על ידי מנוע המודיעין של MOCA',
    disclaim: 'מדגם ממחירי השוק החיים. המחיר הסופי מוצג בעמוד הספק.',
    days: [{ v: 3, l: '3 ימים' }, { v: 7, l: 'שבוע' }, { v: 14, l: 'שבועיים' }, { v: 30, l: 'חודש' }],
    data: [{ v: 3, l: 'קל', s: '3GB · ניווט והודעות' }, { v: 10, l: 'רגיל', s: '10GB · + רשתות' }, { v: 20, l: 'כבד', s: '20GB · + וידאו' }, { v: 'unl', l: 'ללא הגבלה', s: 'בלי לחשוב בכלל' }],
    filters: [{ v: 'all', l: 'הכל' }, { v: 'esim', l: 'eSIM' }, { v: 'local', l: 'סים מקומי' }, { v: 'unl', l: 'ללא הגבלה' }],
    badges: ['ההתאמה הטובה ביותר', 'הזולה ביותר', 'הכי הרבה דאטה', 'כדאי גם'],
    unlimited: 'ללא הגבלה', daysU: 'ימים', dayU: 'יום', get: 'לרכישת החבילה ↗', perGB: '/GB',
    esimTag: 'eSIM גלובלי', localTag: 'מפעיל ישראלי',
    perks: { instant: 'eSIM מיידי', unlimited: 'דאטה ללא הגבלה', app: 'תמיכה באפליקציה', hotspot: 'שיתוף רשת', ilNumber: 'מספר ישראלי', calls: 'שיחות כלולות', intlMin: 'דקות לחו״ל', airport: 'איסוף בשדה' },
    empty: 'אין חבילות שמתאימות לסינון הזה — נסו אפשרות אחרת.',
    notFound: 'פורטל האורח הזה אינו זמין.',
    loading: 'טוענים את ההצעות המשתלמות…',
  },
}

const GC_CSS = `
#gc-app{--c1:#26170f;--c2:#d16938;--bgp:#f4f1ee;--ink:#1c2430;--sub:#5b6b7e;--line:#e6ebf2;--card:#fff;--r:20px;
  font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;background:var(--bgp);color:var(--ink);min-height:100dvh;-webkit-font-smoothing:antialiased}
#gc-app *{box-sizing:border-box;margin:0;padding:0}
#gc-app .page{max-width:480px;margin:0 auto;min-height:100dvh;display:flex;flex-direction:column}
#gc-app .hero{position:relative;overflow:hidden;color:#fff;background:linear-gradient(150deg,var(--c1),color-mix(in srgb,var(--c1),#000 30%));padding:46px 22px 30px;border-radius:0 0 30px 30px}
#gc-app .hero::before{content:"";position:absolute;inset:auto -70px -120px auto;width:260px;height:260px;border-radius:50%;background:color-mix(in srgb,var(--c2),transparent 72%)}
#gc-app .hero::after{content:"";position:absolute;top:-90px;inset-inline-start:-60px;width:220px;height:220px;border-radius:50%;background:color-mix(in srgb,#fff,transparent 90%)}
#gc-app .hero>*{position:relative;z-index:1}
#gc-app .hero-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:22px}
#gc-app .hotel-id{display:flex;align-items:center;gap:11px}
#gc-app .mono{width:46px;height:46px;border-radius:14px;background:#fff;color:var(--c1);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:17px;letter-spacing:.5px;box-shadow:0 4px 14px rgba(0,0,0,.25);overflow:hidden}
#gc-app .mono img{width:100%;height:100%;object-fit:contain}
#gc-app .hotel-name{font-weight:700;font-size:15.5px;line-height:1.15}
#gc-app .hotel-tag{font-size:10px;letter-spacing:2.2px;opacity:.75;font-weight:600;margin-top:2px}
#gc-app .lang{display:flex;background:rgba(255,255,255,.14);border-radius:999px;padding:3px}
#gc-app .lang button{border:0;background:transparent;color:#fff;opacity:.65;font:inherit;font-weight:700;font-size:12.5px;padding:5px 12px;border-radius:999px;cursor:pointer}
#gc-app .lang button.on{background:#fff;color:var(--c1);opacity:1}
#gc-app .hero h1{font-size:27px;font-weight:800;line-height:1.18;margin-bottom:8px}
#gc-app .hero p{font-size:14.5px;line-height:1.45;opacity:.85;max-width:34ch}
#gc-app .updated{display:inline-flex;align-items:center;gap:7px;margin-top:16px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18);padding:6px 12px;border-radius:999px;font-size:12px;font-weight:600}
#gc-app .dot{width:7px;height:7px;border-radius:50%;background:#5ad08a;box-shadow:0 0 0 3px rgba(90,208,138,.25);animation:gcpulse 2s infinite}
@keyframes gcpulse{50%{box-shadow:0 0 0 6px rgba(90,208,138,.08)}}
#gc-app main{padding:18px 16px 8px;display:flex;flex-direction:column;gap:20px;flex:1}
#gc-app .card{background:var(--card);border-radius:var(--r);padding:18px;box-shadow:0 6px 24px rgba(20,35,60,.07)}
#gc-app .sec{font-size:16.5px;font-weight:800;margin-bottom:12px}
#gc-app .wizard{margin-top:-26px}
#gc-app .wizard h2{font-size:16.5px;font-weight:800;margin-bottom:4px}
#gc-app .wizard .q{font-size:13px;font-weight:700;color:var(--sub);margin:14px 0 8px}
#gc-app .chips{display:flex;gap:8px;flex-wrap:wrap}
#gc-app .chip{border:1.5px solid var(--line);background:#fff;border-radius:14px;cursor:pointer;padding:9px 13px;font:inherit;font-size:13.5px;font-weight:700;color:var(--ink);transition:all .15s;flex:1 1 auto;text-align:center;min-width:74px}
#gc-app .chip small{display:block;font-size:10.5px;font-weight:600;color:var(--sub);margin-top:2px}
#gc-app .chip.on{background:var(--c1);border-color:var(--c1);color:#fff}
#gc-app .chip.on small{color:rgba(255,255,255,.75)}
#gc-app .pick{background:var(--card);border-radius:var(--r);padding:16px;margin-bottom:10px;box-shadow:0 6px 24px rgba(20,35,60,.07);border:1.5px solid transparent;position:relative}
#gc-app .pick.first{border-color:var(--c2);box-shadow:0 10px 30px color-mix(in srgb,var(--c2),transparent 72%)}
#gc-app .badge{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:1.1px;padding:4px 10px;border-radius:999px;margin-bottom:10px;text-transform:uppercase;margin-inline-end:6px}
#gc-app .badge.b1{background:color-mix(in srgb,var(--c2),#fff 75%);color:color-mix(in srgb,var(--c2),#000 35%)}
#gc-app .badge.b2{background:#e3f3e9;color:#246b43}
#gc-app .badge.b3{background:#e9ecfd;color:#3a4bbf}
#gc-app .badge.b4{background:#eef1f5;color:#5b6b7e}
#gc-app .deal-row{display:flex;align-items:center;gap:12px}
#gc-app .pchip{width:42px;height:42px;border-radius:13px;flex:none;color:#fff;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;letter-spacing:.4px}
#gc-app .deal-info{flex:1;min-width:0}
#gc-app .deal-provider{font-weight:800;font-size:14.5px}
#gc-app .deal-meta{font-size:12.5px;color:var(--sub);font-weight:600;margin-top:1px}
#gc-app .deal-price{text-align:end}
#gc-app .price-main{font-weight:800;font-size:17px;white-space:nowrap}
#gc-app .price-sub{font-size:11.5px;color:var(--sub);font-weight:600;white-space:nowrap}
#gc-app .tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
#gc-app .tag{font-size:10.5px;font-weight:700;background:var(--bgp);border:1px solid var(--line);color:var(--sub);padding:3px 9px;border-radius:999px}
#gc-app .get{margin-top:12px;width:100%;border:0;border-radius:13px;cursor:pointer;background:var(--c1);color:#fff;font:inherit;font-weight:800;font-size:14px;padding:11px;transition:transform .12s,opacity .12s}
#gc-app .get:active{transform:scale(.985);opacity:.9}
#gc-app .all-head{display:flex;flex-direction:column;gap:10px;margin-bottom:12px}
#gc-app .filters{display:flex;gap:7px;flex-wrap:wrap}
#gc-app .fpill{border:1.5px solid var(--line);background:#fff;border-radius:999px;cursor:pointer;padding:6px 13px;font:inherit;font-size:12.5px;font-weight:700;color:var(--sub)}
#gc-app .fpill.on{background:var(--ink);border-color:var(--ink);color:#fff}
#gc-app .deal{background:var(--card);border-radius:16px;padding:13px 14px;margin-bottom:8px;box-shadow:0 3px 12px rgba(20,35,60,.05)}
#gc-app .deal .get{margin-top:0;width:auto;padding:8px 14px;font-size:12.5px;border-radius:11px}
#gc-app .deal-bottom{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:10px}
#gc-app .empty{padding:26px;text-align:center;color:var(--sub);font-weight:600;font-size:13.5px}
#gc-app .esim-help h2{font-size:15.5px;font-weight:800;margin-bottom:12px}
#gc-app .step{display:flex;gap:12px;align-items:flex-start;margin-bottom:12px}
#gc-app .step:last-of-type{margin-bottom:8px}
#gc-app .snum{width:26px;height:26px;border-radius:9px;background:color-mix(in srgb,var(--c1),#fff 88%);color:var(--c1);font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;flex:none;margin-top:1px}
#gc-app .step b{display:block;font-size:13.5px}
#gc-app .step span{font-size:12.5px;color:var(--sub);line-height:1.4}
#gc-app .compat{font-size:11.5px;color:var(--sub);border-top:1px dashed var(--line);padding-top:10px;margin-top:4px}
#gc-app .trust{text-align:center;font-size:12px;color:var(--sub);font-weight:600;line-height:1.6;padding:4px 18px}
#gc-app .trust b{color:var(--ink)}
#gc-app footer{padding:18px 16px 26px;text-align:center}
#gc-app .powered{font-size:12.5px;color:var(--sub);font-weight:600}
#gc-app .powered b{color:var(--ink)}
#gc-app .disclaim{font-size:11px;color:#9aa7b5;margin-top:6px}
#gc-app .splash{min-height:100dvh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;color:var(--c1);text-align:center;padding:30px}
#gc-app .spin{width:34px;height:34px;border-radius:50%;border:3px solid color-mix(in srgb,var(--c1),transparent 78%);border-top-color:var(--c1);animation:gcspin .8s linear infinite}
@keyframes gcspin{to{transform:rotate(360deg)}}
#gc-app[dir="rtl"] .deal-price{text-align:start}
`

function gbLabel(d, t) {
  if (d.gb == null) return t.unlimited
  if (d.gb < 1) return `${Math.round(d.gb * 1024)}MB`
  return `${+d.gb}GB`
}

export default function GuestPortalPage() {
  const { slug } = useParams()
  const [params] = useSearchParams()
  const [data, setData] = useState(null)
  const [status, setStatus] = useState('loading') // loading | ok | notfound
  const [lang, setLang] = useState('en')
  const [stay, setStay] = useState(7)
  const [dataNeed, setDataNeed] = useState(10)
  const [filter, setFilter] = useState('all')
  const engagedRef = useRef(false)

  // Fetch portal + fire the open/scan beacon once.
  useEffect(() => {
    let alive = true
    api.getGuestPortal(slug)
      .then((d) => {
        if (!alive) return
        setData(d)
        const initLang = (params.get('lang') === 'he' || params.get('lang') === 'en')
          ? params.get('lang')
          : (d.hotel.default_lang || 'en')
        setLang(initLang)
        setStatus('ok')
        api.guestEvent(slug, params.get('via') === 'qr' ? 'scan' : 'view', initLang)
      })
      .catch(() => { if (alive) setStatus('notfound') })
    return () => { alive = false }
  }, [slug]) // eslint-disable-line react-hooks/exhaustive-deps

  // Apply document direction/lang for this standalone page.
  useEffect(() => {
    const prevDir = document.documentElement.dir
    const prevLang = document.documentElement.lang
    document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr'
    document.documentElement.lang = lang
    return () => { document.documentElement.dir = prevDir; document.documentElement.lang = prevLang }
  }, [lang])

  const t = T[lang]
  const fx = data?.fx || 3.7
  const deals = data?.deals || []
  const providers = data?.providers || {}

  const priceMain = (d) => d.currency === 'ILS'
    ? `₪${fmtNum(d.price)}`
    : `${sym(d.currency)}${fmtNum(d.original_price)}`
  const priceSub = (d) => d.currency === 'ILS'
    ? `≈ $${Math.round(d.price / fx)}`
    : `≈ ₪${Math.round(d.price)}`
  const metaLine = (d) => {
    const bits = [gbLabel(d, t)]
    if (d.days) bits.push(`${d.days} ${d.days === 1 ? t.dayU : t.daysU}`)
    bits.push(d.form === 'esim' ? 'eSIM' : 'SIM')
    if (d.gb && d.gb >= 1 && d.original_price) bits.push(`${sym(d.currency)}${fmtNum(d.original_price / d.gb)}${t.perGB}`)
    return bits
  }

  const eligible = useMemo(() => deals.filter((d) => {
    if (d.days < stay) return false
    if (dataNeed === 'unl') return d.gb == null || d.gb >= 50
    return d.gb == null || d.gb >= dataNeed
  }), [deals, stay, dataNeed])

  const picks = useMemo(() => {
    if (!eligible.length) return []
    const need = dataNeed === 'unl' ? null : dataNeed
    const idx = (d) => deals.indexOf(d)
    const fit = (d) => d.price
      + (d.gb == null && need != null ? 14 : 0)
      + Math.max(0, d.days - stay) * 0.12
      + (d.gb && need ? Math.max(0, d.gb - need) * 0.3 : 0)
    const byFit = [...eligible].sort((a, b) => fit(a) - fit(b))
    const byPrice = [...eligible].sort((a, b) => a.price - b.price)
    const byData = [...eligible].sort((a, b) =>
      ((b.gb == null ? 9999 : b.gb) - (a.gb == null ? 9999 : a.gb)) || (a.price - b.price))
    const winners = new Map()
    const add = (d, b) => { const k = idx(d); if (!winners.has(k)) winners.set(k, []); winners.get(k).push(b) }
    add(byFit[0], 0); add(byPrice[0], 1); add(byData[0], 2)
    for (const d of byFit) { if (winners.size >= 3) break; const k = idx(d); if (!winners.has(k)) winners.set(k, [3]) }
    return [...winners.entries()]
      .map(([k, badges]) => ({ d: deals[k], badges }))
      .sort((a, b) => Math.min(...a.badges) - Math.min(...b.badges))
  }, [eligible, deals, stay, dataNeed])

  const list = useMemo(() => {
    let rows = [...deals]
    if (filter === 'esim') rows = rows.filter((d) => d.form === 'esim')
    if (filter === 'local') rows = rows.filter((d) => d.kind === 'local')
    if (filter === 'unl') rows = rows.filter((d) => d.gb == null)
    return rows.sort((a, b) => a.price - b.price)
  }, [deals, filter])

  const engage = () => {
    if (!engagedRef.current) { engagedRef.current = true; api.guestEvent(slug, 'engage', lang) }
  }
  const openDeal = (d) => {
    engage()
    window.open(api.guestGoUrl(slug, d.provider, d.plan_name, lang), '_blank', 'noopener')
  }

  const DealCore = ({ d }) => {
    const pv = providers[d.provider] || { label: d.provider, color: '#5c3317' }
    const mono = (pv.label || d.provider).replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || 'GC'
    return (
      <>
        <div className="deal-row">
          <div className="pchip" style={{ background: pv.color }}>{mono}</div>
          <div className="deal-info">
            <div className="deal-provider"><bdi>{pv.label}</bdi></div>
            <div className="deal-meta">{metaLine(d).map((x, i) => <bdi key={i}>{i ? ' · ' : ''}{x}</bdi>)}</div>
          </div>
          <div className="deal-price">
            <div className="price-main" dir="ltr">{priceMain(d)}</div>
            <div className="price-sub" dir="ltr">{priceSub(d)}</div>
          </div>
        </div>
        <div className="tags">{(d.perks || []).map((k) => <span className="tag" key={k}>{t.perks[k] || k}</span>)}</div>
      </>
    )
  }

  if (status === 'loading') {
    return (
      <div id="gc-app"><style>{GC_CSS}</style>
        <div className="splash"><div className="spin" /><div style={{ fontWeight: 700 }}>{T.en.loading}</div></div>
      </div>
    )
  }
  if (status === 'notfound') {
    return (
      <div id="gc-app"><style>{GC_CSS}</style>
        <div className="splash">
          <div style={{ fontSize: 40 }}>🌐</div>
          <div style={{ fontWeight: 800, fontSize: 18 }}>{T.en.notFound}</div>
          <a href="/hotels" style={{ color: 'var(--c2)', fontWeight: 700 }}>MOCA Guest Connect →</a>
        </div>
      </div>
    )
  }

  const h = data.hotel
  const brand = h.brand || {}
  const styleVars = {
    ...(brand.primary ? { '--c1': brand.primary } : {}),
    ...(brand.secondary ? { '--c2': brand.secondary } : {}),
    ...(brand.bg ? { '--bgp': brand.bg } : {}),
  }
  const updated = data.updated_at ? new Date(data.updated_at) : null
  const updatedStr = updated
    ? `${t.updated}: ${updated.toLocaleDateString(lang === 'he' ? 'he-IL' : 'en-GB', { weekday: 'short', day: 'numeric', month: 'short' })} · ${updated.toLocaleTimeString(lang === 'he' ? 'he-IL' : 'en-GB', { hour: '2-digit', minute: '2-digit' })}`
    : ''
  const cls = ['b1', 'b2', 'b3', 'b4']

  return (
    <div id="gc-app" dir={lang === 'he' ? 'rtl' : 'ltr'} style={styleVars}>
      <style>{GC_CSS}</style>
      <div className="page">
        <header className="hero">
          <div className="hero-top">
            <div className="hotel-id">
              <div className="mono">{brand.logo_url ? <img src={brand.logo_url} alt="" /> : (brand.mono || h.name.slice(0, 2).toUpperCase())}</div>
              <div>
                <div className="hotel-name">{h.name}</div>
                <div className="hotel-tag">GUEST CONNECT</div>
              </div>
            </div>
            <div className="lang" role="group" aria-label="Language">
              <button type="button" className={lang === 'en' ? 'on' : ''} onClick={() => setLang('en')}>EN</button>
              <button type="button" className={lang === 'he' ? 'on' : ''} onClick={() => setLang('he')}>עב</button>
            </div>
          </div>
          <h1>{h.tagline || (lang === 'he' ? 'להישאר מחוברים בישראל' : 'Stay connected in Israel')}</h1>
          <p>{t.sub}</p>
          {updatedStr && <div className="updated"><span className="dot" /><span>{updatedStr}</span></div>}
        </header>

        <main>
          <section className="card wizard">
            <h2>{t.wizTitle}</h2>
            <div className="q">{t.qDays}</div>
            <div className="chips">
              {t.days.map((o) => (
                <button key={o.v} type="button" className={`chip${o.v === stay ? ' on' : ''}`}
                  onClick={() => { setStay(o.v); engage() }}>{o.l}</button>
              ))}
            </div>
            <div className="q">{t.qData}</div>
            <div className="chips">
              {t.data.map((o) => (
                <button key={o.v} type="button" className={`chip${String(o.v) === String(dataNeed) ? ' on' : ''}`}
                  onClick={() => { setDataNeed(o.v === 'unl' ? 'unl' : o.v); engage() }}>
                  {o.l}<small>{o.s}</small>
                </button>
              ))}
            </div>
          </section>

          <section>
            <h2 className="sec">{t.topPicks}</h2>
            {picks.length ? picks.map(({ d, badges }, i) => (
              <div className={`pick${i === 0 ? ' first' : ''}`} key={i}>
                {badges.map((b) => <span className={`badge ${cls[b]}`} key={b}>{t.badges[b]}</span>)}
                <DealCore d={d} />
                <button type="button" className="get" onClick={() => openDeal(d)}>{t.get}</button>
              </div>
            )) : <div className="card empty">{t.empty}</div>}
          </section>

          <section>
            <div className="all-head">
              <h2 className="sec" style={{ marginBottom: 0 }}>{t.allDeals}</h2>
              <div className="filters">
                {t.filters.map((o) => (
                  <button key={o.v} type="button" className={`fpill${o.v === filter ? ' on' : ''}`}
                    onClick={() => setFilter(o.v)}>{o.l}</button>
                ))}
              </div>
            </div>
            {list.length ? list.map((d, i) => (
              <div className="deal" key={i}>
                <DealCore d={d} />
                <div className="deal-bottom">
                  <span className="tag">{d.kind === 'local' ? t.localTag : t.esimTag}</span>
                  <button type="button" className="get" onClick={() => openDeal(d)}>{t.get}</button>
                </div>
              </div>
            )) : <div className="card empty">{t.empty}</div>}
          </section>

          <section className="card esim-help">
            <h2>{t.helpTitle}</h2>
            <div className="step"><div className="snum">1</div><div><b>{t.h1b}</b><span>{t.h1s}</span></div></div>
            <div className="step"><div className="snum">2</div><div><b>{t.h2b}</b><span>{t.h2s}</span></div></div>
            <div className="step"><div className="snum">3</div><div><b>{t.h3b}</b><span>{t.h3s}</span></div></div>
            <div className="compat">{t.compat}</div>
          </section>

          <div className="trust" dangerouslySetInnerHTML={{ __html: t.trust }} />
        </main>

        <footer>
          <div className="powered">{h.name} · Powered by <b>MOCA</b> Guest Connect ⚡</div>
          <div className="disclaim">{t.disclaim}</div>
        </footer>
      </div>
    </div>
  )
}
