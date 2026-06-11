import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'

/* ════════════════════════════════════════════════════════════════════════
   MOCA Guest Connect — public marketing landing  (route: /hotels)
   Hebrew RTL pitch: hero · live branded demo · how-it-works · ROI calculator ·
   pricing · FAQ · lead form (→ /api/hotels/lead). Mocha-latte design system,
   scoped under #hl-app. No auth.
   ════════════════════════════════════════════════════════════════════════ */

const DEMO_BRANDS = [
  { slug: 'demo', label: 'Coastline Hotels', sub: 'דמו · טרקוטה', a: '#26170f', b: '#d16938' },
  { slug: 'demo-navy', label: 'Harbor & Pearl', sub: 'דמו · נייבי וזהב', a: '#0e2a47', b: '#c8a24b' },
  { slug: 'demo-verde', label: 'Galil Verde', sub: 'דמו · ירוק', a: '#1d4d3b', b: '#9ec27a' },
  { slug: 'demo-urban', label: 'TLV Urban', sub: 'דמו · מונוכרום', a: '#17171c', b: '#d9c8ae' },
]

const HL_CSS = `
#hl-app{--bg:#f9f4ee;--cream:#f5ede0;--mist:#faf5ee;--sand:#e8d5bc;--border:#e0cdb5;--bolt:#5c3317;--dark:#4a2a13;--text:#3b1f0d;--sub:#8a6a4a;--muted:#a08468;--up:#b4472d;--down:#4a7c3f;--hot:#c9622f;--sh-card:0 4px 18px rgba(74,42,19,.07);--sh-hover:0 12px 34px rgba(74,42,19,.13);--font-display:'Frank Ruhl Libre',serif;
  font-family:'Assistant',system-ui,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;direction:rtl}
#hl-app *{box-sizing:border-box;margin:0;padding:0}
#hl-app .wrap{max-width:1140px;margin:0 auto;padding:0 22px}
#hl-app section{padding:70px 0}
#hl-app section[id]{scroll-margin-top:80px}
#hl-app h2.title{font-family:var(--font-display);font-size:clamp(26px,3.4vw,38px);font-weight:900;color:var(--dark);line-height:1.2}
#hl-app .kicker{font-size:12.5px;font-weight:800;letter-spacing:2.5px;color:var(--hot);text-transform:uppercase;margin-bottom:12px}
#hl-app .lead{font-size:17px;color:var(--sub);line-height:1.6;margin-top:14px;max-width:62ch}
#hl-app .topbar{position:sticky;top:0;z-index:40;background:rgba(249,244,238,.86);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
#hl-app .topbar .wrap{display:flex;align-items:center;justify-content:space-between;height:64px}
#hl-app .logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:17px;color:var(--dark);text-decoration:none}
#hl-app .logo .bolt{width:34px;height:34px;border-radius:11px;background:var(--bolt);color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px}
#hl-app .logo small{font-weight:700;color:var(--hot);font-size:11px;letter-spacing:1.6px;display:block;margin-top:1px}
#hl-app nav{display:flex;gap:22px}
#hl-app nav a{color:var(--sub);text-decoration:none;font-weight:700;font-size:14px}
#hl-app nav a:hover{color:var(--dark)}
#hl-app .btn{display:inline-block;border:0;cursor:pointer;text-decoration:none;text-align:center;background:var(--bolt);color:#fff;font:inherit;font-weight:800;font-size:14.5px;padding:11px 22px;border-radius:13px;transition:transform .12s,box-shadow .2s}
#hl-app .btn:hover{transform:translateY(-1px);box-shadow:var(--sh-hover)}
#hl-app .btn.ghost{background:transparent;color:var(--bolt);border:1.5px solid var(--border)}
#hl-app .btn.ghost:hover{border-color:var(--bolt)}
@media (max-width:840px){#hl-app nav{display:none}}
#hl-app .hero{padding:80px 0 64px;position:relative;overflow:hidden}
#hl-app .hero::before{content:"";position:absolute;top:-140px;inset-inline-start:-120px;width:380px;height:380px;border-radius:50%;background:radial-gradient(circle,rgba(201,98,47,.12),transparent 65%)}
#hl-app .hero::after{content:"";position:absolute;bottom:-180px;inset-inline-end:-100px;width:420px;height:420px;border-radius:50%;background:radial-gradient(circle,rgba(92,51,23,.10),transparent 65%)}
#hl-app .hero .wrap{position:relative;z-index:1;text-align:center;display:flex;flex-direction:column;align-items:center}
#hl-app .hero h1{font-family:var(--font-display);font-weight:900;color:var(--dark);font-size:clamp(30px,5vw,54px);line-height:1.15;max-width:26ch}
#hl-app .hero h1 em{font-style:normal;color:var(--hot)}
#hl-app .hero .lead{text-align:center;margin-inline:auto}
#hl-app .cta-row{display:flex;gap:14px;margin-top:30px;flex-wrap:wrap;justify-content:center}
#hl-app .stats{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-top:36px}
#hl-app .stat{background:#fff;border:1px solid var(--border);border-radius:999px;padding:9px 18px;font-size:13.5px;font-weight:700;color:var(--sub);box-shadow:var(--sh-card)}
#hl-app .stat b{color:var(--dark)}
#hl-app #demo{background:linear-gradient(180deg,var(--cream),var(--bg));border-block:1px solid var(--border)}
#hl-app .demo-grid{display:grid;grid-template-columns:1fr 440px;gap:46px;align-items:center;margin-top:36px}
@media (max-width:980px){#hl-app .demo-grid{grid-template-columns:1fr}}
#hl-app .controls h3{font-size:16px;font-weight:800;color:var(--dark);margin-bottom:12px}
#hl-app .brand-btns{display:flex;flex-direction:column;gap:9px}
#hl-app .brand-btn{display:flex;align-items:center;gap:13px;background:#fff;border:1.5px solid var(--border);border-radius:15px;padding:13px 16px;cursor:pointer;font:inherit;font-weight:700;font-size:14.5px;color:var(--text);transition:all .15s;text-align:start}
#hl-app .brand-btn:hover{box-shadow:var(--sh-card)}
#hl-app .brand-btn.on{border-color:var(--bolt);box-shadow:var(--sh-hover)}
#hl-app .brand-btn .sw{width:30px;height:30px;border-radius:50%;flex:none;box-shadow:inset 0 0 0 2px rgba(255,255,255,.55)}
#hl-app .brand-btn small{display:block;font-size:11.5px;color:var(--muted);font-weight:600}
#hl-app .mini-row{display:flex;gap:10px;align-items:center;margin-top:20px;flex-wrap:wrap}
#hl-app .seg{display:flex;background:#fff;border:1.5px solid var(--border);border-radius:999px;padding:3px}
#hl-app .seg button{border:0;background:transparent;font:inherit;font-weight:800;font-size:12.5px;color:var(--sub);padding:6px 14px;border-radius:999px;cursor:pointer}
#hl-app .seg button.on{background:var(--bolt);color:#fff}
#hl-app .open-full{font-size:13.5px;font-weight:700;color:var(--bolt);text-decoration:none}
#hl-app .phone-wrap{display:flex;justify-content:center}
#hl-app .phone{width:380px;height:760px;border-radius:50px;background:#17171b;border:11px solid #17171b;box-shadow:0 30px 70px rgba(40,20,5,.30),inset 0 0 0 2px #2c2c33;position:relative;overflow:hidden;flex:none}
#hl-app .phone .notch{position:absolute;top:9px;left:50%;transform:translateX(-50%);width:118px;height:25px;background:#17171b;border-radius:999px;z-index:3}
#hl-app .phone iframe{width:100%;height:100%;border:0;background:#fff;border-radius:40px}
@media (max-width:980px){#hl-app .phone{transform:scale(.82);transform-origin:top center}#hl-app .phone-wrap{height:640px;overflow:hidden}}
#hl-app .steps{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:40px}
@media (max-width:840px){#hl-app .steps{grid-template-columns:1fr}}
#hl-app .stepc{background:#fff;border:1px solid var(--border);border-radius:20px;padding:26px;box-shadow:var(--sh-card);position:relative}
#hl-app .stepc .n{width:38px;height:38px;border-radius:13px;background:var(--cream);color:var(--bolt);font-weight:800;font-size:17px;display:flex;align-items:center;justify-content:center;margin-bottom:16px;border:1px solid var(--sand)}
#hl-app .stepc h3{font-size:17px;font-weight:800;color:var(--dark);margin-bottom:8px}
#hl-app .stepc p{font-size:14px;color:var(--sub);line-height:1.55}
#hl-app .stepc .emoji{position:absolute;top:24px;inset-inline-end:22px;font-size:26px;opacity:.9}
#hl-app #value{background:var(--mist);border-block:1px solid var(--border)}
#hl-app .vgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-top:40px}
#hl-app .vcard{background:#fff;border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:var(--sh-card);transition:transform .15s,box-shadow .2s}
#hl-app .vcard:hover{transform:translateY(-3px);box-shadow:var(--sh-hover)}
#hl-app .vcard .ic{font-size:26px;margin-bottom:12px}
#hl-app .vcard h3{font-size:15.5px;font-weight:800;color:var(--dark);margin-bottom:6px}
#hl-app .vcard p{font-size:13.5px;color:var(--sub);line-height:1.5}
#hl-app .roi-grid{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:40px;align-items:start}
@media (max-width:900px){#hl-app .roi-grid{grid-template-columns:1fr}}
#hl-app .sliders{display:flex;flex-direction:column;gap:18px}
#hl-app .slider label{display:flex;justify-content:space-between;font-size:14px;font-weight:700;color:var(--text);margin-bottom:8px}
#hl-app .slider label output{color:var(--bolt);font-weight:800}
#hl-app input[type=range]{width:100%;appearance:none;height:7px;border-radius:999px;background:var(--sand);outline:none;cursor:pointer}
#hl-app input[type=range]::-webkit-slider-thumb{appearance:none;width:22px;height:22px;border-radius:50%;background:var(--bolt);border:3px solid #fff;box-shadow:0 2px 8px rgba(74,42,19,.35)}
#hl-app input[type=range]::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:var(--bolt);border:3px solid #fff}
#hl-app .results{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:520px){#hl-app .results{grid-template-columns:1fr}}
#hl-app .rcard{background:#fff;border:1px solid var(--border);border-radius:18px;padding:20px;box-shadow:var(--sh-card)}
#hl-app .rcard .lbl{font-size:12.5px;font-weight:700;color:var(--sub);margin-bottom:6px}
#hl-app .rcard .val{font-family:var(--font-display);font-size:30px;font-weight:900;color:var(--dark);line-height:1.1}
#hl-app .rcard .val small{font-size:15px;font-weight:700;color:var(--muted)}
#hl-app .rcard.money{background:linear-gradient(150deg,#fff,var(--cream));border-color:var(--sand)}
#hl-app .rcard.money .val{color:var(--down)}
#hl-app .assume{font-size:12.5px;color:var(--muted);margin-top:18px;line-height:1.6}
#hl-app .pilot{margin-top:40px;background:linear-gradient(135deg,var(--bolt),#7a4a24);color:#fff;border-radius:22px;padding:26px 30px;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;box-shadow:var(--sh-hover)}
#hl-app .pilot h3{font-family:var(--font-display);font-size:23px;font-weight:900;margin-bottom:5px}
#hl-app .pilot p{font-size:14.5px;opacity:.85}
#hl-app .pilot .btn{background:#fff;color:var(--bolt)}
#hl-app .tiers{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:26px}
@media (max-width:900px){#hl-app .tiers{grid-template-columns:1fr}}
#hl-app .tier{background:#fff;border:1.5px solid var(--border);border-radius:22px;padding:28px;box-shadow:var(--sh-card);position:relative;display:flex;flex-direction:column}
#hl-app .tier.pop{border-color:var(--hot)}
#hl-app .tier .pop-tag{position:absolute;top:-12px;inset-inline-start:24px;background:var(--hot);color:#fff;font-size:11.5px;font-weight:800;padding:4px 13px;border-radius:999px;letter-spacing:.6px}
#hl-app .tier h3{font-size:17px;font-weight:800;color:var(--dark)}
#hl-app .tier .aud{font-size:13px;color:var(--muted);font-weight:600;margin-top:2px}
#hl-app .tier .price{font-family:var(--font-display);font-size:38px;font-weight:900;color:var(--dark);margin:16px 0 2px}
#hl-app .tier .price small{font-size:14px;color:var(--muted);font-weight:700;font-family:'Assistant'}
#hl-app .tier ul{list-style:none;margin:18px 0 22px;display:flex;flex-direction:column;gap:9px;flex:1}
#hl-app .tier li{font-size:13.5px;color:var(--sub);font-weight:600;display:flex;gap:8px;align-items:flex-start}
#hl-app .tier li::before{content:"✓";color:var(--down);font-weight:800}
#hl-app .tier .btn{width:100%}
#hl-app .faq{max-width:760px;margin:36px auto 0;display:flex;flex-direction:column;gap:10px}
#hl-app details{background:#fff;border:1px solid var(--border);border-radius:15px;padding:17px 20px;box-shadow:var(--sh-card)}
#hl-app summary{cursor:pointer;font-weight:800;font-size:15px;color:var(--dark);list-style:none;display:flex;justify-content:space-between;align-items:center;gap:12px}
#hl-app summary::after{content:"+";font-size:20px;color:var(--hot);font-weight:700;transition:transform .2s}
#hl-app details[open] summary::after{transform:rotate(45deg)}
#hl-app details p{margin-top:11px;font-size:14px;color:var(--sub);line-height:1.6}
#hl-app #contact{background:var(--mist);border-block:1px solid var(--border)}
#hl-app .lead-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:40px;margin-top:36px;align-items:start}
@media (max-width:900px){#hl-app .lead-grid{grid-template-columns:1fr}}
#hl-app .form{background:#fff;border:1px solid var(--border);border-radius:22px;padding:28px;box-shadow:var(--sh-card)}
#hl-app .frow{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:520px){#hl-app .frow{grid-template-columns:1fr}}
#hl-app .field{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}
#hl-app .field label{font-size:13px;font-weight:700;color:var(--text)}
#hl-app .field input,#hl-app .field textarea{font:inherit;font-size:14px;padding:11px 13px;border:1.5px solid var(--border);border-radius:12px;background:var(--bg);color:var(--text);width:100%}
#hl-app .field input:focus,#hl-app .field textarea:focus{outline:none;border-color:var(--bolt)}
#hl-app .form .btn{width:100%;margin-top:4px}
#hl-app .ok{background:#e3f3e9;border:1px solid #bfe3cd;color:#246b43;border-radius:14px;padding:18px;font-weight:700;text-align:center;font-size:14.5px}
#hl-app .err{color:var(--up);font-size:13px;font-weight:700;margin-top:8px}
#hl-app footer{border-top:1px solid var(--border);background:var(--cream)}
#hl-app footer .wrap{padding:26px 22px;display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
#hl-app footer .f-logo{font-weight:800;color:var(--dark);font-size:15px}
#hl-app footer .f-logo span{color:var(--hot)}
#hl-app footer small{color:var(--muted);font-size:12px;font-weight:600;line-height:1.5}
`

const fmtIL = (n) => Math.round(n).toLocaleString('he-IL')

export default function HotelsLandingPage() {
  const [brand, setBrand] = useState('demo')
  const [demoLang, setDemoLang] = useState('en')
  const [roi, setRoi] = useState({ props: 5, rooms: 90, occ: 72, foreign: 45, comm: 18 })
  const [lead, setLead] = useState({ hotel_name: '', contact_name: '', email: '', phone: '', rooms: '', message: '' })
  const [sent, setSent] = useState(false)
  const [sending, setSending] = useState(false)
  const [err, setErr] = useState('')

  // Smooth "elevator" scroll when the topbar nav anchors are clicked. Scoped to
  // this standalone page via an inline style on <html> with cleanup on unmount,
  // so it doesn't leak into the rest of the app (the original index.html mockup
  // had a global `html{scroll-behavior:smooth}` that the React port had dropped).
  useEffect(() => {
    document.title = 'MOCA Guest Connect — חיבור לאינטרנט לאורחי המלון'
    const html = document.documentElement
    const prev = html.style.scrollBehavior
    html.style.scrollBehavior = 'smooth'
    return () => { html.style.scrollBehavior = prev }
  }, [])

  const guestUrl = `/guest/${brand}?lang=${demoLang}`

  const calc = useMemo(() => {
    const roomNights = roi.props * roi.rooms * 30.4 * (roi.occ / 100)
    const relevant = roomNights * (roi.foreign / 100)
    const scans = relevant * 0.15
    const buys = scans * 0.20
    const hotelYear = buys * roi.comm * 0.5 * 12
    return { scans, buys, hotelYear, saved: scans * 12 }
  }, [roi])

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    if (!lead.email.trim() && !lead.phone.trim()) { setErr('נא להשאיר אימייל או טלפון ליצירת קשר.'); return }
    setSending(true)
    try {
      await api.submitHotelLead(lead)
      setSent(true)
    } catch (e2) {
      setErr(e2.message || 'שליחה נכשלה — נסו שוב או כתבו ל-Helpdesk@mocaintel.com')
    } finally {
      setSending(false)
    }
  }

  const upd = (k) => (e) => setLead((s) => ({ ...s, [k]: e.target.value }))

  return (
    <div id="hl-app">
      <style>{HL_CSS}</style>

      <div className="topbar">
        <div className="wrap">
          <a className="logo" href="#top"><span className="bolt">⚡</span><span>MOCA<small>GUEST CONNECT</small></span></a>
          <nav>
            <a href="#demo">הדגמה חיה</a>
            <a href="#how">איך זה עובד</a>
            <a href="#roi">מחשבון רווח</a>
            <a href="#pricing">תמחור</a>
            <a href="#contact">צרו קשר</a>
          </nav>
          <a className="btn" href="#contact">פיילוט 60 יום חינם</a>
        </div>
      </div>

      <header className="hero" id="top">
        <div className="wrap">
          <div className="kicker">MOCA GUEST CONNECT · לבתי מלון ומארחי תיירים</div>
          <h1>האורח נוחת ושואל ״איך מתחברים?״<br />המלון שלכם עונה — <em>ומרוויח</em>.</h1>
          <p className="lead">פורטל ממותג בצבעי המלון שמשווה לאורח, בזמן אמת, את כל חבילות ה-eSIM והסים לתיירים בישראל — 27 ספקים גלובליים ו-10 מפעילים מקומיים, מתעדכן פעמיים ביום. בלי מלאי, בלי תפעול — ועם עמלה למלון על כל רכישה.</p>
          <div className="cta-row">
            <a className="btn" href="#demo">▶ צפו בהדגמה החיה</a>
            <a className="btn ghost" href="#contact">תיאום שיחת היכרות</a>
          </div>
          <div className="stats">
            <div className="stat"><b>27</b> ספקי eSIM גלובליים</div>
            <div className="stat"><b>10</b> מפעילים ישראליים</div>
            <div className="stat">עדכון מחירים <b>×2 ביום</b></div>
            <div className="stat">התקנה תוך <b>48 שעות</b></div>
            <div className="stat"><b>0</b> תפעול למלון</div>
          </div>
        </div>
      </header>

      <section id="demo">
        <div className="wrap">
          <div className="kicker">הדגמה חיה</div>
          <h2 className="title">ככה זה נראה לאורח שלכם</h2>
          <p className="lead">זה לא סרטון — זה הפורטל עצמו, על דאטה חיה. ממותג בצבעי המלון, ולכל מותג ברשת אפשר פורטל בצבעים שלו באותה קלות. החליפו מותג ושפה ותראו.</p>
          <div className="demo-grid">
            <div className="controls">
              <h3>בחרו מותג (מיתוג חי)</h3>
              <div className="brand-btns">
                {DEMO_BRANDS.map((p) => (
                  <button key={p.slug} type="button" className={`brand-btn${p.slug === brand ? ' on' : ''}`} onClick={() => setBrand(p.slug)}>
                    <span className="sw" style={{ background: `linear-gradient(135deg, ${p.a} 50%, ${p.b} 50%)` }} />
                    <span>{p.label}<small>{p.sub}</small></span>
                  </button>
                ))}
              </div>
              <div className="mini-row">
                <h3 style={{ margin: 0 }}>שפת האורח:</h3>
                <div className="seg">
                  <button type="button" className={demoLang === 'en' ? 'on' : ''} onClick={() => setDemoLang('en')}>English</button>
                  <button type="button" className={demoLang === 'he' ? 'on' : ''} onClick={() => setDemoLang('he')}>עברית</button>
                </div>
                <a className="open-full" href={guestUrl} target="_blank" rel="noopener">פתיחה במסך מלא ↗</a>
              </div>
            </div>
            <div className="phone-wrap">
              <div className="phone">
                <div className="notch" />
                <iframe key={guestUrl} src={guestUrl} title="Guest portal demo" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="how">
        <div className="wrap">
          <div className="kicker">איך זה עובד</div>
          <h2 className="title">שלושה צעדים, אפס תפעול</h2>
          <div className="steps">
            <div className="stepc"><span className="emoji">📱</span><div className="n">1</div><h3>QR בחדר ובצ׳ק-אין</h3><p>מעמדים ממותגים בחדרים ובדלפק, קישור באתר ובהודעת הוואטסאפ שלפני ההגעה. אנחנו מספקים את הכל מעוצב ומוכן להדפסה.</p></div>
            <div className="stepc"><span className="emoji">🛒</span><div className="n">2</div><h3>האורח משווה ורוכש</h3><p>בוחר משך שהות ונפח גלישה, מקבל את ההצעות המשתלמות בשוק — בשפה שלו, במחיר של היום — ורוכש ישירות מהספק. התמיכה על הספק, לא עליכם.</p></div>
            <div className="stepc"><span className="emoji">💰</span><div className="n">3</div><h3>המלון מרוויח ולומד</h3><p>כל רכישה מתויגת בקוד ההפניה של המלון ומזכה אתכם בעמלה. בנוסף — דשבורד אנליטיקה על קהל האורחים: מדינות מקור, ביקושים ושעות שיא.</p></div>
          </div>
        </div>
      </section>

      <section id="value">
        <div className="wrap">
          <div className="kicker">למה זה משתלם</div>
          <h2 className="title">חמישה דברים שהמלון מקבל</h2>
          <div className="vgrid">
            <div className="vcard"><div className="ic">🛎️</div><h3>שירות לאורח</h3><p>תשובה מקצועית ועדכנית לשאלה הנפוצה ביותר בדלפק — בלי להעסיק את הקבלה.</p></div>
            <div className="vcard"><div className="ic">💸</div><h3>הכנסה פסיבית</h3><p>עמלת הפניה על כל רכישת eSIM שמקורה ב-QR של המלון. חלוקה שקופה 50/50.</p></div>
            <div className="vcard"><div className="ic">🎨</div><h3>מיתוג מלא</h3><p>הפורטל בצבעי המלון ובלוגו שלו — נראה כשירות של המלון, לא של צד שלישי.</p></div>
            <div className="vcard"><div className="ic">🧘</div><h3>אפס תפעול</h3><p>אין מלאי, אין סים פיזי, אין תמיכה טכנית. הספק מטפל בלקוח מקצה לקצה.</p></div>
            <div className="vcard"><div className="ic">📊</div><h3>אנליטיקה</h3><p>כמה סרקו, מה חיפשו ומאילו מדינות הגיעו — דאטה שיווקי אנונימי על קהל האורחים.</p></div>
          </div>
        </div>
      </section>

      <section id="roi">
        <div className="wrap">
          <div className="kicker">מחשבון רווח</div>
          <h2 className="title">כמה זה שווה למלון שלכם?</h2>
          <p className="lead">הזיזו את המחוונים לפי הנתונים שלכם — החישוב מתעדכן מיד.</p>
          <div className="roi-grid">
            <div className="sliders">
              <div className="slider"><label>מספר נכסים <output>{roi.props}</output></label><input type="range" min="1" max="40" step="1" value={roi.props} onChange={(e) => setRoi((s) => ({ ...s, props: +e.target.value }))} /></div>
              <div className="slider"><label>חדרים לנכס (ממוצע) <output>{roi.rooms}</output></label><input type="range" min="20" max="400" step="5" value={roi.rooms} onChange={(e) => setRoi((s) => ({ ...s, rooms: +e.target.value }))} /></div>
              <div className="slider"><label>תפוסה <output>{roi.occ}%</output></label><input type="range" min="40" max="95" step="1" value={roi.occ} onChange={(e) => setRoi((s) => ({ ...s, occ: +e.target.value }))} /></div>
              <div className="slider"><label>שיעור אורחים מחו״ל <output>{roi.foreign}%</output></label><input type="range" min="10" max="90" step="5" value={roi.foreign} onChange={(e) => setRoi((s) => ({ ...s, foreign: +e.target.value }))} /></div>
              <div className="slider"><label>עמלה ממוצעת לרכישה <output>₪{roi.comm}</output></label><input type="range" min="8" max="35" step="1" value={roi.comm} onChange={(e) => setRoi((s) => ({ ...s, comm: +e.target.value }))} /></div>
            </div>
            <div>
              <div className="results">
                <div className="rcard"><div className="lbl">סריקות QR בחודש</div><div className="val">{fmtIL(calc.scans)}</div></div>
                <div className="rcard"><div className="lbl">רכישות בחודש</div><div className="val">{fmtIL(calc.buys)}</div></div>
                <div className="rcard money"><div className="lbl">הכנסת עמלות שנתית</div><div className="val">₪{fmtIL(calc.hotelYear)}<small> / שנה</small></div></div>
                <div className="rcard"><div className="lbl">פניות דלפק שנחסכות בשנה</div><div className="val">{fmtIL(calc.saved)}</div></div>
              </div>
              <p className="assume">הנחות שמרניות, מכוילות בפיילוט: 15% מהלינות הרלוונטיות סורקות · 20% מהסורקים רוכשים · חלק המלון 50% מהעמלה · 30.4 לילות בחודש. בנוסף לעמלות: שיפור חוויית האורח והביקורות — בלי עלות תפעולית.</p>
            </div>
          </div>
        </div>
      </section>

      <section id="pricing">
        <div className="wrap">
          <div className="kicker">תמחור</div>
          <h2 className="title">מסלולים פשוטים, בלי הפתעות</h2>
          <div className="pilot">
            <div>
              <h3>פיילוט 60 יום בנכס אחד — חינם לחלוטין</h3>
              <p>בלי כרטיס אשראי · התקנה ביום אחד · יציאה בהודעה של 30 יום · מרחיבים רק כשהדאטה מצדיקה</p>
            </div>
            <a className="btn" href="#contact">מתחילים פיילוט</a>
          </div>
          <div className="tiers">
            <div className="tier">
              <h3>Starter</h3><div className="aud">הוסטל · מלון בוטיק קטן</div>
              <div className="price">₪290<small> / חודש לנכס</small></div>
              <ul><li>פורטל אורח ממותג + QR</li><li>השוואה חיה, עדכון פעמיים ביום</li><li>2 שפות (אנגלית + עברית)</li><li>חלוקת עמלות 50/50</li></ul>
              <a className="btn ghost" href="#contact">דברו איתנו</a>
            </div>
            <div className="tier pop">
              <span className="pop-tag">הכי פופולרי</span>
              <h3>Pro</h3><div className="aud">מלון בינוני וגדול</div>
              <div className="price">₪590<small> / חודש לנכס</small></div>
              <ul><li>כל מה שב-Starter</li><li>דשבורד אנליטיקת אורחים</li><li>המלצות מותאמות לפרופיל האורח</li><li>4 שפות (+ צרפתית, רוסית)</li><li>מעמדי QR מודפסים ממותגים</li></ul>
              <a className="btn" href="#contact">דברו איתנו</a>
            </div>
            <div className="tier">
              <h3>Chain</h3><div className="aud">רשת · ניהול ריבוי נכסים</div>
              <div className="price">מ-₪390<small> / חודש לנכס</small></div>
              <ul><li>כל מה שב-Pro</li><li>ניהול מרוכז לכל הנכסים</li><li>דוח חודשי להנהלת הרשת</li><li>SLA ייעודי ומנהל לקוח</li><li>תמחור מדורג לפי היקף</li></ul>
              <a className="btn ghost" href="#contact">דברו איתנו</a>
            </div>
          </div>
          <div className="faq">
            <details><summary>צריך צוות טכני או אינטגרציה מצד המלון?</summary><p>לא. ה-onboarding כולו עלינו: דף ממותג, קוד QR ומעמדים מעוצבים — מוכנים תוך 48 שעות. אין התקנה במערכות המלון ואין תלות ב-PMS.</p></details>
            <details><summary>מה עם פרטיות האורחים (GDPR)?</summary><p>הפורטל פתוח ללא הרשמה וללא איסוף פרטים אישיים. האנליטיקה אנונימית ומצרפית בלבד — מספרי סריקות, שפות ומדינות מקור, לעולם לא זהות של אורח.</p></details>
            <details><summary>יש לנו כבר שיתוף פעולה עם מפעיל</summary><p>מצוין — אפשר להציג את ההצעה שלכם ראשונה ולתת לאורח שקיפות על כל השאר. השוואה ניטרלית בונה אמון. וכשהאורח קונה בכל מקרה — עדיף שהמלון ירוויח.</p></details>
            <details><summary>המחירים באמת מתעדכנים? מי עומד מאחורי זה?</summary><p>כן. Guest Connect רץ על MOCA — מערכת מודיעין תחרותי שסורקת את כל שוק הסלולר הישראלי ו-27 ספקי eSIM גלובליים פעמיים ביום.</p></details>
          </div>
        </div>
      </section>

      <section id="contact">
        <div className="wrap">
          <div className="kicker">בואו נתחיל</div>
          <h2 className="title">פיילוט 60 יום, בלי עלות ובלי התחייבות</h2>
          <div className="lead-grid">
            <div>
              <p className="lead">השאירו פרטים ונחזור אליכם עם דמו ממותג בצבעי המלון שלכם והצעת פיילוט. אם האורחים לא משתמשים — נפרדים כידידים. אם כן — יש לכם שירות חדש לאורח ומקור הכנסה חדש.</p>
              <p className="lead" style={{ fontSize: 14.5 }}>מעדיפים לכתוב? <a href="mailto:Helpdesk@mocaintel.com?subject=MOCA Guest Connect" style={{ color: 'var(--bolt)', fontWeight: 800 }}>Helpdesk@mocaintel.com</a></p>
            </div>
            {sent ? (
              <div className="form"><div className="ok">תודה! קיבלנו את הפנייה ונחזור אליכם בקרוב 🎉<br />מייל אישור נשלח אם השארתם כתובת.</div></div>
            ) : (
              <form className="form" onSubmit={submit}>
                <div className="frow">
                  <div className="field"><label>שם המלון / הרשת</label><input value={lead.hotel_name} onChange={upd('hotel_name')} placeholder="מלון לדוגמה" /></div>
                  <div className="field"><label>איש קשר</label><input value={lead.contact_name} onChange={upd('contact_name')} placeholder="שם מלא" /></div>
                </div>
                <div className="frow">
                  <div className="field"><label>אימייל</label><input type="email" value={lead.email} onChange={upd('email')} placeholder="you@hotel.co.il" /></div>
                  <div className="field"><label>טלפון</label><input type="tel" value={lead.phone} onChange={upd('phone')} placeholder="050-0000000" /></div>
                </div>
                <div className="field"><label>מספר חדרים (בערך)</label><input type="number" min="1" value={lead.rooms} onChange={upd('rooms')} placeholder="90" /></div>
                <div className="field"><label>הודעה (לא חובה)</label><textarea rows="3" value={lead.message} onChange={upd('message')} placeholder="ספרו לנו על הנכס" /></div>
                <button className="btn" type="submit" disabled={sending}>{sending ? 'שולח…' : 'קבעו לי דמו ופיילוט ↗'}</button>
                {err && <div className="err">{err}</div>}
              </form>
            )}
          </div>
        </div>
      </section>

      <footer>
        <div className="wrap">
          <div className="f-logo">MOCA <span>Guest Connect</span> ⚡</div>
          <small>השוואת קישוריות חיה לתיירים בישראל · mocaintel.com · Helpdesk@mocaintel.com · המחירים בהדגמה נדגמים משוק חי ולהמחשה</small>
        </div>
      </footer>
    </div>
  )
}
