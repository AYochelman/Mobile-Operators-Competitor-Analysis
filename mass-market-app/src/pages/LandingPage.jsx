import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import LandingHeroShot from '../components/LandingHeroShot'
import FeatureShowcase from '../components/FeatureShowcase'
import featPrice from '../assets/feat-price.webp'
import featCampaigns from '../assets/feat-campaigns.webp'
import featRoaming from '../assets/feat-roaming.webp'
import featAlerts from '../assets/feat-alerts.webp'
import featTimemachine from '../assets/feat-timemachine.webp'
import featAi from '../assets/feat-ai.webp'
import featAiChat from '../assets/feat-ai-chat.webp'

/* ─────────────────────────────────────────────────────────────
   MOCA public marketing landing page (served at "/" for anonymous
   visitors; logged-in users are redirected to /dashboard by HomeGate
   in App.jsx). Content ported from pitch/index.html with the
   code-verified numbers (10 operators, 27 eSIM, 2×/day).
   ───────────────────────────────────────────────────────────── */

const HERO_STATS = [
  { n: '10', l: 'מפעילים סלולריים' },
  { n: '27', l: 'ספקי eSIM גלובליים' },
  { n: '2×', l: 'סריקות מלאות ביום' },
  { n: 'דקות', l: 'מאירוע להתראה' },
]

const PAINS = [
  { t: 'זמן תגובה', p: 'מנהל מוצר נכנס ידנית לאתרים בבוקר. עד שמישהו מבחין בהורדת מחיר — עברו שעות או יום.' },
  { t: 'כיסוי חלקי', p: 'בודקים מחירים, אבל מי עוקב אחרי הקריאייטיב, הבאנרים, ה-eSIM הגלובלי והמשווקים?' },
  { t: 'אין היסטוריה', p: '"מה סלקום פרסם לפני שלושה שבועות?" אף אחד לא יודע. אין ארכיון, אין מגמות.' },
  { t: 'עלות מחקר', p: 'חברת מחקר חיצונית נותנת דוח חודשי — שמתיישן ברגע שהוא נשלח.' },
]

// w/h = intrinsic pixel dimensions of each screenshot (ow/oh for the overlay),
// passed to <img> so the browser reserves space before load → no layout shift.
const FEATURES = [
  { ic: '💰', h: 'מעקב מחירים חי', p: 'כל חבילה אצל כל מתחרה. שינוי מסומן אדום (רע לנו) / ירוק (טוב לנו) ונשלח להתראה.', img: featPrice, w: 954, h2: 720 },
  { ic: '📸', h: 'ניטור קמפיינים', p: 'צילום יומי של עמודי הבית וה-e-stores. רואים מתי כל מתחרה החליף באנר ומה הוא דוחף.', img: featCampaigns, w: 1000, h2: 427 },
  { ic: '✈️', h: 'הגנת נדידה ו-eSIM', p: '27 ספקי eSIM גלובליים על מאות מדינות — בדיוק היכן שהכנסות הנדידה נשחקות.', img: featRoaming, w: 904, h2: 720 },
  { ic: '🔔', h: 'התראות בזמן אמת', p: 'וואטסאפ / טלגרם / מייל / Web Push. דדופ חכם — בלי ספאם, רק אירועים אמיתיים.', img: featAlerts, w: 408, h2: 820 },
  { ic: '🕰️', h: 'מכונת זמן', p: 'בחר מתחרה ותאריך — וראה איך נראה האתר, החבילות והמחירים שלו באותו יום.', img: featTimemachine, w: 952, h2: 720 },
  { ic: '🤖', h: 'ניתוח AI', p: 'צ\'אט חכם, מטריצת מיצוב תחרותי, "מי זז הכי הרבה" ומגמות מחיר — לא רק נתון גולמי.', img: featAi, w: 1000, h2: 701, overlay: featAiChat, ow: 369, oh: 325 },
]

const COMPARE = [
  { k: 'תדירות', old: 'בדיקה ידנית, מתי שמתפנים', neu: 'אוטומטי, פעמיים ביום, כל השוק' },
  { k: 'היקף', old: 'מחירים בלבד', neu: 'מחיר + קריאייטיב + חדשות + משווקים + eSIM' },
  { k: 'מהירות תגובה', old: 'שעות עד יום', neu: 'התראה תוך דקות' },
  { k: 'היסטוריה', old: 'אין', neu: 'ארכיון מלא + מכונת זמן' },
  { k: 'תובנות', old: 'נתון גולמי', neu: 'ניתוח AI + מטריצת מיצוב + מגמות' },
]

// Mocha-latte hero (option C) — lighter than the original espresso, white text stays crisp.
const HERO_BG = 'linear-gradient(160deg,#6b3d1c 0%,#8a5733 55%,#a06d45 100%)'
const SPOT_BG = 'linear-gradient(135deg,#4a2a13,#5c3317)'
const HILITE = '#f3b07a'

// CTA: opens the public Google Calendar booking page to schedule a demo meeting.
const MEETING_LINK = 'https://calendar.app.google/cbHs54g5MKzCi4A58'

export default function LandingPage() {
  useEffect(() => {
    document.title = 'MOCA — מודיעין תחרותי לשוק הסלולר'
  }, [])

  return (
    <div className="min-h-screen bg-moca-bg text-moca-text font-body">
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
            <Link to="/login"
                  className="text-sm font-semibold text-[#3b1f0d] bg-[#f3b07a] hover:bg-[#f0a463] px-4 py-2 rounded-full transition-colors">
              כניסה למערכת
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
          <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-10 lg:gap-6 items-center">
          <div>
          <div className="text-[13px] font-semibold tracking-[3px] uppercase text-[#e8d5bc]/90 mb-3.5">
            Mobile Operators · Competitor Analysis
          </div>
          <h1 className="font-display font-medium text-white leading-[1.12] text-4xl md:text-[54px] max-w-[760px]">
            כל מהלך תחרותי בשוק הסלולר —{' '}
            <span style={{ color: HILITE }}>על המסך שלך, לפני שהוא משפיע עליך.</span>
          </h1>
          <p className="mt-5 text-lg md:text-xl font-light text-[#f0e2d0] max-w-[680px]">
            מערכת מודיעין תחרותי שעוקבת אוטומטית אחרי כל השוק — פעמיים ביום — ושולחת התראה ברגע שמתחרה
            מזיז מחיר, מחליף קמפיין או משיק חבילה.
          </p>
          <div className="mt-9 flex flex-wrap gap-8">
            {HERO_STATS.map((s) => (
              <div key={s.l}>
                <div className="font-display font-black text-3xl md:text-[40px]" style={{ color: HILITE }}>{s.n}</div>
                <div className="text-sm text-[#e8d5bc]/85">{s.l}</div>
              </div>
            ))}
          </div>
          </div>
          <div className="mt-4 lg:mt-0 flex justify-center">
            <LandingHeroShot />
          </div>
          </div>
        </div>
      </header>

      {/* ── Pain ── */}
      <section className="py-16 bg-moca-cream border-y border-moca-border">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-[13px] font-bold tracking-[2.5px] uppercase text-moca-hot mb-2.5">המצב היום</div>
          <h2 className="font-display text-3xl md:text-4xl text-moca-dark mb-2">
            מודיעין תחרותי שמתבסס על עבודה ידנית — איטי, חלקי ויקר
          </h2>
          <p className="text-moca-sub text-lg max-w-[640px] mb-9">
            בשוק שבו מלחמת מחירים רצה בזמן אמת, ההחלטות מתקבלות על תמונה של אתמול.
          </p>
          <div className="grid md:grid-cols-2 gap-5">
            {PAINS.map((c) => (
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
          <div className="text-[13px] font-bold tracking-[2.5px] uppercase text-moca-hot mb-2.5">מה MOCA עושה</div>
          <h2 className="font-display text-3xl md:text-4xl text-moca-dark mb-2">מודיעין מלא, אוטומטי, בזמן אמת</h2>
          <p className="text-moca-sub text-lg max-w-[640px] mb-9">
            לא עוד טבלת מחירים — שכבת מודיעין שלמה על כל מה שהמתחרים עושים בחוץ.
          </p>
          <FeatureShowcase items={FEATURES} />
        </div>
      </section>

      {/* ── eSIM spotlight ── */}
      <section className="pb-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="rounded-3xl p-8 md:p-12 grid md:grid-cols-[1.3fr_1fr] gap-10 items-center text-[#f5ede0]"
               style={{ background: SPOT_BG }}>
            <div>
              <div className="text-[13px] font-bold tracking-[2.5px] uppercase mb-2.5" style={{ color: HILITE }}>
                הזווית האסטרטגית
              </div>
              <h2 className="font-display text-white text-2xl md:text-[32px] leading-tight">
                הכנסות הנדידה שלך נשחקות — ואתה לא רואה את מי שאוכל אותן
              </h2>
              <p className="mt-3.5 text-[#f0e2d0] text-[17px] font-light">
                ספקי ה-eSIM הגלובליים (Airalo, Holafly, Saily, Orbit ועוד) מתמחרים מתחת לחבילות הנדידה שלך,
                מדינה אחר מדינה. MOCA הוא המקום היחיד שבו תראה את התמחור שלהם מול שלך — בזמן אמת.
              </p>
            </div>
            <div className="text-center">
              <div className="font-display font-black leading-none text-[64px]" style={{ color: HILITE }}>27</div>
              <div className="mt-2 text-base text-[#e8d5bc]">ספקי eSIM גלובליים<br />על מאות מדינות, מנוטרים אוטומטית</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Compare table ── */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-[13px] font-bold tracking-[2.5px] uppercase text-moca-hot mb-2.5">
            למה MOCA ולא Excel או חברת מחקר
          </div>
          <h2 className="font-display text-3xl md:text-4xl text-moca-dark mb-9">הבידול</h2>
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 border border-moca-border rounded-2xl overflow-hidden bg-white shadow-card">
              <thead>
                <tr>
                  <th className="bg-moca-bolt text-white font-bold text-[15px] text-right px-5 py-4">קטגוריה</th>
                  <th className="bg-moca-bolt text-white/80 font-bold text-[15px] text-right px-5 py-4">מה שיש היום</th>
                  <th className="bg-moca-bolt text-white font-bold text-[15px] text-right px-5 py-4">MOCA</th>
                </tr>
              </thead>
              <tbody>
                {COMPARE.map((r, i) => (
                  <tr key={r.k} className={i % 2 ? 'bg-moca-mist' : ''}>
                    <td className="px-5 py-4 text-base font-semibold text-moca-dark text-right">{r.k}</td>
                    <td className="px-5 py-4 text-base text-moca-up text-right">{r.old}</td>
                    <td className="px-5 py-4 text-base text-moca-down font-semibold text-right">{r.neu}</td>
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
            הצעת הפיילוט
          </span>
          <h2 className="font-display text-3xl md:text-[34px] text-moca-dark mb-3">שבוע. חיבור מלא למערכת. אפס סיכון.</h2>
          <p className="text-moca-sub text-lg max-w-[600px] mx-auto">
            אנחנו מחברים מעקב על כל הספקים בשוק, ושולחים לצוות התראות בזמן אמת לוואטסאפ. אם זה לא חוסך לכם ישיבת בוקר אחת לפחות — אין לכם צורך במערכת!
          </p>
          <a href={MEETING_LINK} target="_blank" rel="noopener noreferrer"
             className="inline-block mt-7 bg-moca-bolt hover:bg-moca-dark text-white font-bold text-[17px] px-10 py-4 rounded-full shadow-xl transition-colors">
            קביעת פגישה ←
          </a>
          <p className="mt-3 text-sm text-moca-muted">בוחרים שעה פנויה — ישר ביומן, אישור מיידי</p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="py-7 text-center text-moca-muted text-[13px]">
        MOCA · Mobile Operators Competitor Analysis · מודיעין תחרותי לשוק הסלולר הישראלי
      </footer>
    </div>
  )
}
