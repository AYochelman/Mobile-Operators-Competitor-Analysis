import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import LandingHeroShot from '../components/LandingHeroShot'
import FeatureShowcase from '../components/FeatureShowcase'
import featPrice from '../assets/feat-price.webp'
import featCampaigns from '../assets/feat-campaigns.webp'
import featRoaming from '../assets/feat-roaming.webp'
import featAlerts from '../assets/feat-alerts.webp'
import featAlertsEn from '../assets/feat-alerts-en.webp'
import featTimemachine from '../assets/feat-timemachine.webp'
import featAi from '../assets/feat-ai.webp'
import featAiChat from '../assets/feat-ai-chat.webp'

/* ─────────────────────────────────────────────────────────────
   MOCA public marketing landing page (served at "/" for anonymous
   visitors; logged-in users are redirected to /home). Content ported
   from pitch/index.html with the code-verified numbers (10 operators,
   27 eSIM, 2×/day).

   BILINGUAL (he/en): all copy lives in COPY[lang]. The page is rendered
   in two ways and the toggle must work in BOTH:
   • SPA / dev — React state (`lang`) drives it; the toggle button's
     onClick flips state. `forceLang` is undefined here.
   • Static prerender (the LIVE page at "/") — has NO React. The build
     renders this component TWICE (forceLang 'he' + 'en'); prerender-
     landing.mjs wraps each in a [data-lang-root] div and injects a
     vanilla script that flips visibility on `[data-lang-toggle]` clicks.
   The button carries BOTH onClick (SPA) and data-lang-toggle (static);
   only one mechanism is present in any given build, so they never clash.
   ───────────────────────────────────────────────────────────── */

// Language-neutral per-feature metadata (icon + screenshot + intrinsic
// w/h so the browser reserves space → no layout shift). Text comes from
// COPY[lang].features and is merged in by index.
const FEAT_META = [
  { ic: '💰', img: featPrice, w: 954, h2: 720 },
  { ic: '📸', img: featCampaigns, w: 1000, h2: 427 },
  { ic: '✈️', img: featRoaming, w: 904, h2: 720 },
  { ic: '🔔', img: featAlerts, imgEn: featAlertsEn, w: 408, h2: 820 },
  { ic: '🕰️', img: featTimemachine, w: 952, h2: 720 },
  { ic: '🤖', img: featAi, w: 1000, h2: 701, overlay: featAiChat, ow: 369, oh: 325 },
]

const COPY = {
  he: {
    dir: 'rtl',
    title: 'MOCA — מודיעין תחרותי לשוק הסלולר',
    toLang: 'EN',
    toLangAria: 'Switch to English',
    signIn: 'כניסה למערכת',
    kicker: 'Mobile Operators · Competitor Analysis',
    h1a: 'כל מהלך תחרותי בשוק הסלולר —',
    h1b: 'על המסך שלך, לפני שהוא משפיע עליך.',
    heroSub:
      'מערכת מודיעין תחרותי שעוקבת אוטומטית אחרי כל השוק — פעמיים ביום — ושולחת התראה ברגע שמתחרה מזיז מחיר, מחליף קמפיין או משיק חבילה.',
    heroAlt: 'מערכת MOCA — קיר הבאנרים של המתחרים בזמן אמת',
    stats: [
      { n: '10', l: 'מפעילים סלולריים' },
      { n: '27', l: 'ספקי eSIM גלובליים' },
      { n: '2×', l: 'סריקות מלאות ביום' },
      { n: 'דקות', l: 'מאירוע להתראה' },
    ],
    painKicker: 'המצב היום',
    painH: 'מודיעין תחרותי שמתבסס על עבודה ידנית — איטי, חלקי ויקר',
    painSub: 'בשוק שבו מלחמת מחירים רצה בזמן אמת, ההחלטות מתקבלות על תמונה של אתמול.',
    pains: [
      { t: 'זמן תגובה', p: 'מנהל מוצר נכנס ידנית לאתרים בבוקר. עד שמישהו מבחין בהורדת מחיר — עברו שעות או יום.' },
      { t: 'כיסוי חלקי', p: 'בודקים מחירים, אבל מי עוקב אחרי הקריאייטיב, הבאנרים, ה-eSIM הגלובלי והמשווקים?' },
      { t: 'אין היסטוריה', p: '"מה סלקום פרסם לפני שלושה שבועות?" אף אחד לא יודע. אין ארכיון, אין מגמות.' },
      { t: 'עלות מחקר', p: 'חברת מחקר חיצונית נותנת דוח חודשי — שמתיישן ברגע שהוא נשלח.' },
    ],
    featKicker: 'מה MOCA עושה',
    featH: 'מודיעין מלא, אוטומטי, בזמן אמת',
    featSub: 'לא עוד טבלת מחירים — שכבת מודיעין שלמה על כל מה שהמתחרים עושים בחוץ.',
    features: [
      { h: 'מעקב מחירים חי', p: 'כל חבילה אצל כל מתחרה. שינוי מסומן אדום (רע לנו) / ירוק (טוב לנו) ונשלח להתראה.' },
      { h: 'ניטור קמפיינים', p: 'צילום יומי של עמודי הבית וה-e-stores. רואים מתי כל מתחרה החליף באנר ומה הוא דוחף.' },
      { h: 'הגנת נדידה ו-eSIM', p: '27 ספקי eSIM גלובליים על מאות מדינות — בדיוק היכן שהכנסות הנדידה נשחקות.' },
      { h: 'התראות בזמן אמת', p: 'וואטסאפ / טלגרם / מייל / Web Push. דדופ חכם — בלי ספאם, רק אירועים אמיתיים.' },
      { h: 'מכונת זמן', p: 'בחר מתחרה ותאריך — וראה איך נראה האתר, החבילות והמחירים שלו באותו יום.' },
      { h: 'ניתוח AI', p: 'צ\'אט חכם, מטריצת מיצוב תחרותי, "מי זז הכי הרבה" ומגמות מחיר — לא רק נתון גולמי.' },
    ],
    spotKicker: 'הזווית האסטרטגית',
    spotH: 'הכנסות הנדידה שלך נשחקות — ואתה לא רואה את מי שאוכל אותן',
    spotP:
      'ספקי ה-eSIM הגלובליים (Airalo, Holafly, Saily, Orbit ועוד) מתמחרים מתחת לחבילות הנדידה שלך, מדינה אחר מדינה. MOCA הוא המקום היחיד שבו תראה את התמחור שלהם מול שלך — בזמן אמת.',
    spotStat: 'ספקי eSIM גלובליים',
    spotStatSub: 'על מאות מדינות, מנוטרים אוטומטית',
    cmpKicker: 'למה MOCA ולא Excel או חברת מחקר',
    cmpH: 'הבידול',
    cmpCols: { cat: 'קטגוריה', old: 'מה שיש היום', neu: 'MOCA' },
    compare: [
      { k: 'תדירות', old: 'בדיקה ידנית, מתי שמתפנים', neu: 'אוטומטי, פעמיים ביום, כל השוק' },
      { k: 'היקף', old: 'מחירים בלבד', neu: 'מחיר + קריאייטיב + חדשות + משווקים + eSIM' },
      { k: 'מהירות תגובה', old: 'שעות עד יום', neu: 'התראה תוך דקות' },
      { k: 'היסטוריה', old: 'אין', neu: 'ארכיון מלא + מכונת זמן' },
      { k: 'תובנות', old: 'נתון גולמי', neu: 'ניתוח AI + מטריצת מיצוב + מגמות' },
    ],
    pilotBadge: 'הצעת הפיילוט',
    pilotH: 'שבוע. חיבור מלא למערכת. אפס סיכון.',
    pilotP:
      'אנחנו מחברים מעקב על כל הספקים בשוק, ושולחים לצוות התראות בזמן אמת לוואטסאפ. אם זה לא חוסך לכם ישיבת בוקר אחת לפחות — אין לכם צורך במערכת!',
    pilotCta: 'קביעת פגישה ←',
    pilotNote: 'בוחרים שעה פנויה — ישר ביומן, אישור מיידי',
    footer: 'MOCA · Mobile Operators Competitor Analysis · מודיעין תחרותי לשוק הסלולר הישראלי',
  },
  en: {
    dir: 'ltr',
    title: 'MOCA — Competitive Intelligence for Mobile Operators',
    toLang: 'עברית',
    toLangAria: 'עבור לעברית',
    signIn: 'Sign in',
    kicker: 'Mobile Operators · Competitor Analysis',
    h1a: 'Every competitive move in the mobile market —',
    h1b: 'on your screen, before it reaches you.',
    heroSub:
      'A competitive-intelligence platform that automatically tracks the entire market — twice a day — and alerts you the moment a competitor moves a price, swaps a campaign, or launches a plan.',
    heroAlt: 'The MOCA platform — a live wall of competitors’ marketing banners',
    stats: [
      { n: '10', l: 'mobile operators' },
      { n: '27', l: 'global eSIM providers' },
      { n: '2×', l: 'full scans per day' },
      { n: 'minutes', l: 'from event to alert' },
    ],
    painKicker: 'The status quo',
    painH: 'Competitive intelligence built on manual work — slow, partial, expensive',
    painSub: 'In a market where the price war runs in real time, decisions get made on yesterday’s snapshot.',
    pains: [
      { t: 'Reaction time', p: 'A product manager checks competitor sites by hand each morning. By the time someone spots a price cut, hours — or a day — have passed.' },
      { t: 'Partial coverage', p: 'You track prices — but who’s watching the creative, the banners, the global eSIMs, and the resellers?' },
      { t: 'No history', p: '“What was Cellcom advertising three weeks ago?” Nobody knows. No archive, no trends.' },
      { t: 'Research cost', p: 'An outside research firm sends a monthly report — already stale the moment it lands.' },
    ],
    featKicker: 'What MOCA does',
    featH: 'Complete intelligence — automated, in real time',
    featSub: 'Not one more price sheet — a full intelligence layer over everything your competitors do in the open.',
    features: [
      { h: 'Live price tracking', p: 'Every plan from every competitor. Each change flagged red (bad for you) or green (good for you) and pushed to an alert.' },
      { h: 'Campaign monitoring', p: 'Daily screenshots of every homepage and e-store. See exactly when a competitor swaps a banner — and what they’re pushing.' },
      { h: 'Roaming & eSIM defense', p: '27 global eSIM providers across hundreds of countries — exactly where your roaming revenue is being eroded.' },
      { h: 'Real-time alerts', p: 'WhatsApp / Telegram / email / web push. Smart dedup — no spam, only the events that matter.' },
      { h: 'Time machine', p: 'Pick a competitor and a date — and see exactly how their site, plans, and prices looked that day.' },
      { h: 'AI analysis', p: 'A smart chat, a competitive-positioning matrix, a “who moved most” view, and price trends — not just raw data.' },
    ],
    spotKicker: 'The strategic angle',
    spotH: 'Global eSIMs are undercutting your roaming — and you’re flying blind',
    spotP:
      'Global eSIM providers (Airalo, Holafly, Saily, Orbit, and more) price below your roaming bundles, country by country. MOCA is the one place you’ll see their pricing against yours — in real time.',
    spotStat: 'global eSIM providers',
    spotStatSub: 'across hundreds of countries, monitored automatically',
    cmpKicker: 'Why MOCA, not Excel or a research firm',
    cmpH: 'The difference',
    cmpCols: { cat: 'Category', old: 'What you have today', neu: 'MOCA' },
    compare: [
      { k: 'Frequency', old: 'Manual checks, whenever there’s time', neu: 'Automatic, twice a day, the whole market' },
      { k: 'Scope', old: 'Prices only', neu: 'Price + creative + news + resellers + eSIM' },
      { k: 'Reaction speed', old: 'Hours to a day', neu: 'Alerted within minutes' },
      { k: 'History', old: 'None', neu: 'Full archive + time machine' },
      { k: 'Insights', old: 'Raw data', neu: 'AI analysis + positioning matrix + trends' },
    ],
    pilotBadge: 'The pilot offer',
    pilotH: 'One week. Full access. Zero risk.',
    pilotP:
      'We connect tracking across every provider in the market and send your team real-time alerts on WhatsApp. If it doesn’t save you at least one morning meeting — you don’t need the system.',
    pilotCta: 'Book a meeting →',
    pilotNote: 'Pick an open slot — straight into the calendar, instant confirmation',
    footer: 'MOCA · Mobile Operators Competitor Analysis · Competitive intelligence for the Israeli mobile market',
  },
}

// Mocha-latte hero (option C) — lighter than the original espresso, white text stays crisp.
const HERO_BG = 'linear-gradient(160deg,#6b3d1c 0%,#8a5733 55%,#a06d45 100%)'
const SPOT_BG = 'linear-gradient(135deg,#4a2a13,#5c3317)'
const HILITE = '#f3b07a'

// CTA: opens the public Google Calendar booking page to schedule a demo meeting.
const MEETING_LINK = 'https://calendar.app.google/cbHs54g5MKzCi4A58'

// Initial language: forceLang (prerender) wins; otherwise honor ?lang= / a
// stored preference so a link like mocaintel.com/?lang=en opens in English.
function initialLang(forceLang) {
  if (forceLang === 'he' || forceLang === 'en') return forceLang
  if (typeof window !== 'undefined') {
    try {
      const u = new URLSearchParams(window.location.search).get('lang')
      if (u === 'en' || u === 'he') return u
      const s = localStorage.getItem('moca_lang')
      if (s === 'en' || s === 'he') return s
    } catch { /* ignore */ }
  }
  return 'he'
}

export default function LandingPage({ forceLang }) {
  const [lang, setLang] = useState(() => initialLang(forceLang))
  const t = COPY[lang]

  useEffect(() => {
    document.title = t.title
  }, [t.title])

  function toggleLang() {
    const next = lang === 'he' ? 'en' : 'he'
    setLang(next)
    try { localStorage.setItem('moca_lang', next) } catch { /* ignore */ }
  }

  const features = t.features.map((f, i) => {
    const meta = FEAT_META[i]
    // The alerts screenshot is a localized Telegram capture — swap to the
    // English twin in EN so the mockup reads in the visitor's language.
    const img = lang === 'en' && meta.imgEn ? meta.imgEn : meta.img
    return { ...meta, ...f, img }
  })

  return (
    <div dir={t.dir} lang={lang} className="min-h-screen bg-moca-bg text-moca-text font-body">
      {/* ── Top nav ── */}
      <nav className="absolute top-0 inset-x-0 z-10">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-[#f5ede0]">
            <span className="grid place-items-center w-9 h-9 rounded-xl bg-moca-bolt shadow-lg">
              <svg width="15" height="14" viewBox="0 0 48 46" fill="none" aria-hidden="true">
                <path fill="#fff" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"/>
              </svg>
            </span>
            <span className="font-display font-black text-xl tracking-wide">MOCA</span>
          </div>
          <div className="flex items-center gap-3">
            <button type="button"
                    data-lang-toggle
                    onClick={toggleLang}
                    aria-label={t.toLangAria}
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#f5ede0] border border-[#f5ede0]/35 hover:border-[#f5ede0]/70 hover:bg-white/10 px-3.5 py-2 rounded-full transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18"/>
              </svg>
              {t.toLang}
            </button>
            <Link to="/login"
                  className="text-sm font-semibold text-[#3b1f0d] bg-[#f3b07a] hover:bg-[#f0a463] px-4 py-2 rounded-full transition-colors">
              {t.signIn}
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <header className="relative overflow-hidden text-[#f5ede0] pt-28 pb-20" style={{ background: HERO_BG }}>
        <div aria-hidden
             className="absolute -right-32 -top-32 w-[380px] h-[380px] rounded-full pointer-events-none"
             style={{ background: 'radial-gradient(circle,rgba(201,98,47,.35),transparent 70%)' }} />
        <div className="relative max-w-6xl mx-auto px-6">
          <div className="grid lg:grid-cols-[1.18fr_0.82fr] gap-10 lg:gap-6 items-center">
          <div>
          <div className="text-[13px] font-semibold tracking-[3px] uppercase text-[#e8d5bc]/90 mb-3.5">
            {t.kicker}
          </div>
          <h1 className="font-display font-medium text-white leading-[1.12] text-4xl md:text-[54px] max-w-[760px]">
            {t.h1a}{' '}
            <span style={{ color: HILITE }}>{t.h1b}</span>
          </h1>
          <p className="mt-5 text-lg md:text-xl font-light text-[#f0e2d0] max-w-[680px]">
            {t.heroSub}
          </p>
          <div className="mt-9 flex flex-wrap lg:flex-nowrap gap-x-6 gap-y-4">
            {t.stats.map((s) => (
              <div key={s.l}>
                <div className="font-display font-black text-3xl md:text-[40px]" style={{ color: HILITE }}>{s.n}</div>
                <div className="text-sm text-[#e8d5bc]/85 whitespace-nowrap">{s.l}</div>
              </div>
            ))}
          </div>
          </div>
          <div className="mt-4 lg:mt-0 flex justify-center">
            <LandingHeroShot alt={t.heroAlt} />
          </div>
          </div>
        </div>
      </header>

      {/* ── Pain ── */}
      <section className="py-16 bg-moca-cream border-y border-moca-border">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-[13px] font-bold tracking-[2.5px] uppercase text-moca-hot mb-2.5">{t.painKicker}</div>
          <h2 className="font-display text-3xl md:text-4xl text-moca-dark mb-2">
            {t.painH}
          </h2>
          <p className="text-moca-sub text-lg text-balance mb-9">
            {t.painSub}
          </p>
          <div className="grid md:grid-cols-2 gap-5">
            {t.pains.map((c) => (
              <div key={c.t} className="bg-moca-bg border border-moca-border rounded-2xl p-6 shadow-card">
                <div className="flex items-center gap-2 text-moca-up font-extrabold text-[15px] mb-1.5">
                  <span>✕</span>{c.t}
                </div>
                <p className="text-moca-text text-base">{c.p}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-[13px] font-bold tracking-[2.5px] uppercase text-moca-hot mb-2.5">{t.featKicker}</div>
          <h2 className="font-display text-3xl md:text-4xl text-moca-dark mb-2">{t.featH}</h2>
          <p className="text-moca-sub text-lg max-w-[640px] mb-9">
            {t.featSub}
          </p>
          <FeatureShowcase items={features} />
        </div>
      </section>

      {/* ── eSIM spotlight ── */}
      <section className="pb-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="rounded-3xl p-8 md:p-12 grid md:grid-cols-[1.3fr_1fr] gap-10 items-center text-[#f5ede0]"
               style={{ background: SPOT_BG }}>
            <div>
              <div className="text-[13px] font-bold tracking-[2.5px] uppercase mb-2.5" style={{ color: HILITE }}>
                {t.spotKicker}
              </div>
              <h2 className="font-display text-white text-2xl md:text-[32px] leading-tight">
                {t.spotH}
              </h2>
              <p className="mt-3.5 text-[#f0e2d0] text-[17px] font-light">
                {t.spotP}
              </p>
            </div>
            <div className="text-center">
              <div className="font-display font-black leading-none text-[64px]" style={{ color: HILITE }}>27</div>
              <div className="mt-2 text-base text-[#e8d5bc]">{t.spotStat}<br />{t.spotStatSub}</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Compare table ── */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-[13px] font-bold tracking-[2.5px] uppercase text-moca-hot mb-2.5">
            {t.cmpKicker}
          </div>
          <h2 className="font-display text-3xl md:text-4xl text-moca-dark mb-9">{t.cmpH}</h2>
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 border border-moca-border rounded-2xl overflow-hidden bg-white shadow-card">
              <thead>
                <tr>
                  <th className="bg-moca-bolt text-white font-bold text-[15px] text-start px-5 py-4">{t.cmpCols.cat}</th>
                  <th className="bg-moca-bolt text-white/80 font-bold text-[15px] text-start px-5 py-4">{t.cmpCols.old}</th>
                  <th className="bg-moca-bolt text-white font-bold text-[15px] text-start px-5 py-4">{t.cmpCols.neu}</th>
                </tr>
              </thead>
              <tbody>
                {t.compare.map((r, i) => (
                  <tr key={r.k} className={i % 2 ? 'bg-moca-mist' : ''}>
                    <td className="px-5 py-4 text-base font-semibold text-moca-dark text-start">{r.k}</td>
                    <td className="px-5 py-4 text-base text-moca-up text-start">{r.old}</td>
                    <td className="px-5 py-4 text-base text-moca-down font-semibold text-start">{r.neu}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Pilot offer ── */}
      <section className="py-16 bg-moca-cream border-t border-moca-border text-center">
        <div className="max-w-6xl mx-auto px-6">
          <span className="inline-block bg-moca-hot text-white text-[11px] font-bold tracking-wide uppercase px-2.5 py-1 rounded-md mb-4">
            {t.pilotBadge}
          </span>
          <h2 className="font-display text-3xl md:text-[34px] text-moca-dark mb-3">{t.pilotH}</h2>
          <p className="text-moca-sub text-lg max-w-[600px] mx-auto">
            {t.pilotP}
          </p>
          <a href={MEETING_LINK} target="_blank" rel="noopener noreferrer"
             className="inline-block mt-7 bg-moca-bolt hover:bg-moca-dark text-white font-bold text-[17px] px-10 py-4 rounded-full shadow-xl transition-colors">
            {t.pilotCta}
          </a>
          <p className="mt-3 text-sm text-moca-muted">{t.pilotNote}</p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="py-7 text-center text-moca-muted text-[13px]">
        {t.footer}
      </footer>
    </div>
  )
}
