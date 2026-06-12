import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'

/* ════════════════════════════════════════════════════════════════════════
   MOCA Guest Connect — public marketing landing  (route: /hotels)
   Bilingual HE/EN pitch: hero · live branded demo · how-it-works · ROI
   calculator · pricing · FAQ · lead form (→ /api/hotels/lead). Mocha-latte
   design system, scoped under #hl-app. No auth.

   BILINGUAL: all copy lives in COPY[lang]. This is a pure React SPA route
   (no prerender), so the language toggle is plain React state. Direction is
   driven by the `dir` attribute on #hl-app (NOT a hardcoded `direction:rtl`
   in the CSS) so the LTR/RTL flip works — the scoped CSS already uses logical
   properties (inset-inline-*, text-align:start) that follow `dir`.
   `?lang=en` / localStorage('moca_lang') pick the initial language (shared
   with the main landing), so mocaintel.com/hotels?lang=en opens in English.
   NB: `demoLang` (the embedded guest-portal iframe language) is a SEPARATE,
   independent control — it showcases that the guest portal itself is bilingual.
   ════════════════════════════════════════════════════════════════════════ */

const DEMO_BRANDS = [
  { slug: 'demo', label: 'Coastline Hotels', sub: { he: 'דמו · טרקוטה', en: 'Demo · Terracotta' }, a: '#26170f', b: '#d16938' },
  { slug: 'demo-navy', label: 'Harbor & Pearl', sub: { he: 'דמו · נייבי וזהב', en: 'Demo · Navy & Gold' }, a: '#0e2a47', b: '#c8a24b' },
  { slug: 'demo-verde', label: 'Galil Verde', sub: { he: 'דמו · ירוק', en: 'Demo · Green' }, a: '#1d4d3b', b: '#9ec27a' },
  { slug: 'demo-urban', label: 'TLV Urban', sub: { he: 'דמו · מונוכרום', en: 'Demo · Monochrome' }, a: '#17171c', b: '#d9c8ae' },
]

const COPY = {
  he: {
    dir: 'rtl',
    title: 'MOCA Guest Connect — חיבור לאינטרנט לאורחי המלון',
    toLang: 'EN',
    toLangAria: 'Switch to English',
    nav: { demo: 'הדגמה חיה', how: 'איך זה עובד', roi: 'מחשבון רווח', pricing: 'תמחור', contact: 'צרו קשר' },
    ctaPilot: 'פיילוט 60 יום חינם',
    heroKicker: 'MOCA GUEST CONNECT · לבתי מלון ומארחי תיירים',
    heroLine1: 'האורח נוחת ושואל ״איך מתחברים?״',
    heroLine2pre: 'המלון שלכם עונה — ',
    heroEm: 'ומרוויח',
    heroLine2post: '.',
    heroLead: 'פורטל ממותג בצבעי המלון שמשווה לאורח, בזמן אמת, את כל חבילות ה-eSIM והסים לתיירים בישראל — 27 ספקים גלובליים ו-10 מפעילים מקומיים, מתעדכן פעמיים ביום. בלי מלאי, בלי תפעול — ועם עמלה למלון על כל רכישה.',
    heroCtaDemo: '▶ צפו בהדגמה החיה',
    heroCtaContact: 'תיאום שיחת היכרות',
    stats: [
      { pre: '', b: '27', post: ' ספקי eSIM גלובליים' },
      { pre: '', b: '10', post: ' מפעילים ישראליים' },
      { pre: 'עדכון מחירים ', b: '×2 ביום', post: '' },
      { pre: 'התקנה תוך ', b: '48 שעות', post: '' },
      { pre: '', b: '0', post: ' תפעול למלון' },
    ],
    demoKicker: 'הדגמה חיה',
    demoTitle: 'ככה זה נראה לאורח שלכם',
    demoLead: 'זה לא סרטון — זה הפורטל עצמו, על דאטה חיה. ממותג בצבעי המלון, ולכל מותג ברשת אפשר פורטל בצבעים שלו באותה קלות. החליפו מותג ושפה ותראו.',
    demoBrandHeading: 'בחרו מותג (מיתוג חי)',
    demoGuestLang: 'שפת האורח:',
    demoOpenFull: 'פתיחה במסך מלא ↗',
    howKicker: 'איך זה עובד',
    howTitle: 'שלושה צעדים, אפס תפעול',
    steps: [
      { emoji: '📱', h: 'QR בחדר ובצ׳ק-אין', p: 'מעמדים ממותגים בחדרים ובדלפק, קישור באתר ובהודעת הוואטסאפ שלפני ההגעה. אנחנו מספקים את הכל מעוצב ומוכן להדפסה.' },
      { emoji: '🛒', h: 'האורח משווה ורוכש', p: 'בוחר משך שהות ונפח גלישה, מקבל את ההצעות המשתלמות בשוק — בשפה שלו, במחיר של היום — ורוכש ישירות מהספק. התמיכה על הספק, לא עליכם.' },
      { emoji: '💰', h: 'המלון מרוויח ולומד', p: 'כל רכישה מתויגת בקוד ההפניה של המלון ומזכה אתכם בעמלה. בנוסף — דשבורד אנליטיקה על קהל האורחים: מדינות מקור, ביקושים ושעות שיא.' },
    ],
    valueKicker: 'למה זה משתלם',
    valueTitle: 'חמישה דברים שהמלון מקבל',
    values: [
      { ic: '🛎️', h: 'שירות לאורח', p: 'תשובה מקצועית ועדכנית לשאלה הנפוצה ביותר בדלפק — בלי להעסיק את הקבלה.' },
      { ic: '💸', h: 'הכנסה פסיבית', p: 'עמלת הפניה על כל רכישת eSIM שמקורה ב-QR של המלון. חלוקה שקופה 50/50.' },
      { ic: '🎨', h: 'מיתוג מלא', p: 'הפורטל בצבעי המלון ובלוגו שלו — נראה כשירות של המלון, לא של צד שלישי.' },
      { ic: '🧘', h: 'אפס תפעול', p: 'אין מלאי, אין סים פיזי, אין תמיכה טכנית. הספק מטפל בלקוח מקצה לקצה.' },
      { ic: '📊', h: 'אנליטיקה', p: 'כמה סרקו, מה חיפשו ומאילו מדינות הגיעו — דאטה שיווקי אנונימי על קהל האורחים.' },
    ],
    roiKicker: 'מחשבון רווח',
    roiTitle: 'כמה זה שווה למלון שלכם?',
    roiLead: 'הזיזו את המחוונים לפי הנתונים שלכם — החישוב מתעדכן מיד.',
    roiProps: 'מספר נכסים',
    roiRooms: 'חדרים לנכס (ממוצע)',
    roiOcc: 'תפוסה',
    roiForeign: 'שיעור אורחים מחו״ל',
    roiComm: 'עמלה ממוצעת לרכישה',
    roiScans: 'סריקות QR בחודש',
    roiBuys: 'רכישות בחודש',
    roiYear: 'הכנסת עמלות שנתית',
    roiPerYear: ' / שנה',
    roiSaved: 'פניות דלפק שנחסכות בשנה',
    roiAssume: 'הנחות שמרניות, מכוילות בפיילוט: 15% מהלינות הרלוונטיות סורקות · 20% מהסורקים רוכשים · חלק המלון 50% מהעמלה · 30.4 לילות בחודש. בנוסף לעמלות: שיפור חוויית האורח והביקורות — בלי עלות תפעולית.',
    pricingKicker: 'תמחור',
    pricingTitle: 'מסלולים פשוטים, בלי הפתעות',
    pilotH: 'פיילוט 60 יום בנכס אחד — חינם לחלוטין',
    pilotP: 'בלי כרטיס אשראי · התקנה ביום אחד · יציאה בהודעה של 30 יום · מרחיבים רק כשהדאטה מצדיקה',
    pilotBtn: 'מתחילים פיילוט',
    popTag: 'הכי פופולרי',
    perProp: ' / חודש לנכס',
    tierBtn: 'דברו איתנו',
    tiers: [
      { name: 'Starter', aud: 'הוסטל · מלון בוטיק קטן', price: '₪290', pop: false, feats: ['פורטל אורח ממותג + QR', 'השוואה חיה, עדכון פעמיים ביום', '2 שפות (אנגלית + עברית)', 'חלוקת עמלות 50/50'] },
      { name: 'Pro', aud: 'מלון בינוני וגדול', price: '₪590', pop: true, feats: ['כל מה שב-Starter', 'דשבורד אנליטיקת אורחים', 'המלצות מותאמות לפרופיל האורח', '4 שפות (+ צרפתית, רוסית)', 'מעמדי QR מודפסים ממותגים'] },
      { name: 'Chain', aud: 'רשת · ניהול ריבוי נכסים', price: 'מ-₪390', pop: false, feats: ['כל מה שב-Pro', 'ניהול מרוכז לכל הנכסים', 'דוח חודשי להנהלת הרשת', 'SLA ייעודי ומנהל לקוח', 'תמחור מדורג לפי היקף'] },
    ],
    faqs: [
      { q: 'צריך צוות טכני או אינטגרציה מצד המלון?', a: 'לא. ה-onboarding כולו עלינו: דף ממותג, קוד QR ומעמדים מעוצבים — מוכנים תוך 48 שעות. אין התקנה במערכות המלון ואין תלות ב-PMS.' },
      { q: 'מה עם פרטיות האורחים (GDPR)?', a: 'הפורטל פתוח ללא הרשמה וללא איסוף פרטים אישיים. האנליטיקה אנונימית ומצרפית בלבד — מספרי סריקות, שפות ומדינות מקור, לעולם לא זהות של אורח.' },
      { q: 'יש לנו כבר שיתוף פעולה עם מפעיל', a: 'מצוין — אפשר להציג את ההצעה שלכם ראשונה ולתת לאורח שקיפות על כל השאר. השוואה ניטרלית בונה אמון. וכשהאורח קונה בכל מקרה — עדיף שהמלון ירוויח.' },
      { q: 'המחירים באמת מתעדכנים? מי עומד מאחורי זה?', a: 'כן. Guest Connect רץ על MOCA — מערכת מודיעין תחרותי שסורקת את כל שוק הסלולר הישראלי ו-27 ספקי eSIM גלובליים פעמיים ביום.' },
    ],
    contactKicker: 'בואו נתחיל',
    contactTitle: 'פיילוט 60 יום, בלי עלות ובלי התחייבות',
    contactLead: 'השאירו פרטים ונחזור אליכם עם דמו ממותג בצבעי המלון שלכם והצעת פיילוט. אם האורחים לא משתמשים — נפרדים כידידים. אם כן — יש לכם שירות חדש לאורח ומקור הכנסה חדש.',
    contactWrite: 'מעדיפים לכתוב? ',
    fHotel: 'שם המלון / הרשת', fHotelPh: 'מלון לדוגמה',
    fContact: 'איש קשר', fContactPh: 'שם מלא',
    fEmail: 'אימייל', fEmailPh: 'you@hotel.co.il',
    fPhone: 'טלפון', fPhonePh: '050-0000000',
    fRooms: 'מספר חדרים (בערך)', fRoomsPh: '90',
    fMsg: 'הודעה (לא חובה)', fMsgPh: 'ספרו לנו על הנכס',
    submit: 'קבעו לי דמו ופיילוט ↗',
    submitting: 'שולח…',
    okMain: 'תודה! קיבלנו את הפנייה ונחזור אליכם בקרוב 🎉',
    okSub: 'מייל אישור נשלח אם השארתם כתובת.',
    errNoContact: 'נא להשאיר אימייל או טלפון ליצירת קשר.',
    errFail: 'שליחה נכשלה — נסו שוב או כתבו ל-Helpdesk@mocaintel.com',
    footerSmall: 'השוואת קישוריות חיה לתיירים בישראל · mocaintel.com · Helpdesk@mocaintel.com · המחירים בהדגמה נדגמים משוק חי ולהמחשה',
  },
  en: {
    dir: 'ltr',
    title: 'MOCA Guest Connect — Wi-Fi & eSIM concierge for your hotel guests',
    toLang: 'עברית',
    toLangAria: 'עבור לעברית',
    nav: { demo: 'Live demo', how: 'How it works', roi: 'ROI calculator', pricing: 'Pricing', contact: 'Contact' },
    ctaPilot: 'Free 60-day pilot',
    heroKicker: 'MOCA GUEST CONNECT · FOR HOTELS & TOURISM HOSTS',
    heroLine1: 'Your guest lands and asks, “How do I get online?”',
    heroLine2pre: 'Your hotel answers — ',
    heroEm: 'and earns',
    heroLine2post: '.',
    heroLead: 'A portal branded in your hotel’s colors that shows guests, in real time, every eSIM and tourist SIM deal in Israel — 27 global providers and 10 local operators, refreshed twice a day. No inventory, no operations — and a commission to the hotel on every purchase.',
    heroCtaDemo: '▶ Watch the live demo',
    heroCtaContact: 'Book an intro call',
    stats: [
      { pre: '', b: '27', post: ' global eSIM providers' },
      { pre: '', b: '10', post: ' Israeli operators' },
      { pre: 'Prices refresh ', b: '2× a day', post: '' },
      { pre: 'Live within ', b: '48 hours', post: '' },
      { pre: '', b: '0', post: ' hotel operations' },
    ],
    demoKicker: 'Live demo',
    demoTitle: 'This is what your guest sees',
    demoLead: 'This isn’t a video — it’s the portal itself, on live data. Branded in your hotel’s colors, and every brand in your chain can have its own just as easily. Switch brand and language to see.',
    demoBrandHeading: 'Choose a brand (live theming)',
    demoGuestLang: 'Guest language:',
    demoOpenFull: 'Open full screen ↗',
    howKicker: 'How it works',
    howTitle: 'Three steps, zero operations',
    steps: [
      { emoji: '📱', h: 'QR in the room & at check-in', p: 'Branded stands in the rooms and at the desk, a link on your site and in the pre-arrival WhatsApp. We provide it all designed and print-ready.' },
      { emoji: '🛒', h: 'The guest compares and buys', p: 'They pick a stay length and data amount, get the best offers on the market — in their language, at today’s price — and buy directly from the provider. Support is on the provider, not on you.' },
      { emoji: '💰', h: 'The hotel earns and learns', p: 'Every purchase is tagged with the hotel’s referral code and earns you a commission. Plus an analytics dashboard on your guest audience: countries of origin, demand, and peak hours.' },
    ],
    valueKicker: 'Why it pays off',
    valueTitle: 'Five things the hotel gets',
    values: [
      { ic: '🛎️', h: 'Guest service', p: 'A professional, up-to-date answer to the most common question at the desk — without tying up the front desk.' },
      { ic: '💸', h: 'Passive income', p: 'A referral commission on every eSIM purchase that originates from the hotel’s QR. A transparent 50/50 split.' },
      { ic: '🎨', h: 'Full branding', p: 'The portal in your hotel’s colors and logo — it looks like the hotel’s own service, not a third party’s.' },
      { ic: '🧘', h: 'Zero operations', p: 'No inventory, no physical SIM, no tech support. The provider handles the customer end to end.' },
      { ic: '📊', h: 'Analytics', p: 'How many scanned, what they searched, and which countries they came from — anonymous marketing data on your guest audience.' },
    ],
    roiKicker: 'ROI calculator',
    roiTitle: 'What’s it worth to your hotel?',
    roiLead: 'Move the sliders to match your numbers — the result updates instantly.',
    roiProps: 'Number of properties',
    roiRooms: 'Rooms per property (avg.)',
    roiOcc: 'Occupancy',
    roiForeign: 'Share of overseas guests',
    roiComm: 'Avg. commission per purchase',
    roiScans: 'QR scans per month',
    roiBuys: 'Purchases per month',
    roiYear: 'Annual commission income',
    roiPerYear: ' / year',
    roiSaved: 'Desk inquiries saved per year',
    roiAssume: 'Conservative assumptions, calibrated in pilots: 15% of relevant room-nights scan · 20% of scanners buy · hotel share 50% of the commission · 30.4 nights per month. On top of commissions: a better guest experience and reviews — at no operational cost.',
    pricingKicker: 'Pricing',
    pricingTitle: 'Simple plans, no surprises',
    pilotH: 'A 60-day pilot at one property — completely free',
    pilotP: 'No credit card · live in one day · exit on 30 days’ notice · expand only when the data justifies it',
    pilotBtn: 'Start a pilot',
    popTag: 'Most popular',
    perProp: ' / month per property',
    tierBtn: 'Talk to us',
    tiers: [
      { name: 'Starter', aud: 'Hostel · small boutique hotel', price: '₪290', pop: false, feats: ['Branded guest portal + QR', 'Live comparison, refreshed twice a day', '2 languages (English + Hebrew)', '50/50 commission split'] },
      { name: 'Pro', aud: 'Mid-size & large hotel', price: '₪590', pop: true, feats: ['Everything in Starter', 'Guest analytics dashboard', 'Recommendations tailored to the guest profile', '4 languages (+ French, Russian)', 'Printed branded QR stands'] },
      { name: 'Chain', aud: 'Chain · multi-property management', price: 'from ₪390', pop: false, feats: ['Everything in Pro', 'Centralized management for all properties', 'Monthly report for chain management', 'Dedicated SLA & account manager', 'Volume-based tiered pricing'] },
    ],
    faqs: [
      { q: 'Does the hotel need a tech team or integration?', a: 'No. The entire onboarding is on us: a branded page, a QR code, and designed stands — ready within 48 hours. No installation in the hotel’s systems and no dependency on the PMS.' },
      { q: 'What about guest privacy (GDPR)?', a: 'The portal is open with no sign-up and no collection of personal details. The analytics are anonymous and aggregate only — scan counts, languages, and countries of origin, never a guest’s identity.' },
      { q: 'We already work with an operator', a: 'Great — you can show your offer first and give the guest transparency on everything else. A neutral comparison builds trust. And since the guest buys anyway — better that the hotel earns from it.' },
      { q: 'Do prices really update? Who’s behind this?', a: 'Yes. Guest Connect runs on MOCA — a competitive-intelligence system that scans the entire Israeli mobile market and 27 global eSIM providers twice a day.' },
    ],
    contactKicker: 'Let’s get started',
    contactTitle: 'A 60-day pilot — no cost, no commitment',
    contactLead: 'Leave your details and we’ll get back to you with a demo branded in your hotel’s colors and a pilot offer. If guests don’t use it — we part as friends. If they do — you’ve got a new guest service and a new revenue stream.',
    contactWrite: 'Prefer to write? ',
    fHotel: 'Hotel / chain name', fHotelPh: 'Sample Hotel',
    fContact: 'Contact name', fContactPh: 'Full name',
    fEmail: 'Email', fEmailPh: 'you@hotel.com',
    fPhone: 'Phone', fPhonePh: '+972 50 000 0000',
    fRooms: 'Number of rooms (approx.)', fRoomsPh: '90',
    fMsg: 'Message (optional)', fMsgPh: 'Tell us about the property',
    submit: 'Set up my demo & pilot ↗',
    submitting: 'Sending…',
    okMain: 'Thank you! We got your request and will be in touch soon 🎉',
    okSub: 'A confirmation email was sent if you left an address.',
    errNoContact: 'Please leave an email or phone number so we can reach you.',
    errFail: 'Submission failed — please try again or email Helpdesk@mocaintel.com',
    footerSmall: 'Live connectivity comparison for tourists in Israel · mocaintel.com · Helpdesk@mocaintel.com · Demo prices are sampled from a live market, for illustration',
  },
}

const HL_CSS = `
#hl-app{--bg:#f9f4ee;--cream:#f5ede0;--mist:#faf5ee;--sand:#e8d5bc;--border:#e0cdb5;--bolt:#5c3317;--dark:#4a2a13;--text:#3b1f0d;--sub:#8a6a4a;--muted:#a08468;--up:#b4472d;--down:#4a7c3f;--hot:#c9622f;--sh-card:0 4px 18px rgba(74,42,19,.07);--sh-hover:0 12px 34px rgba(74,42,19,.13);--font-display:'Frank Ruhl Libre',serif;
  font-family:'Assistant',system-ui,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased}
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
#hl-app .top-actions{display:flex;align-items:center;gap:10px}
#hl-app .lang-toggle{display:inline-flex;align-items:center;gap:6px;background:transparent;border:1.5px solid var(--border);color:var(--bolt);font:inherit;font-weight:800;font-size:13px;padding:9px 13px;border-radius:11px;cursor:pointer;transition:border-color .15s,background .15s}
#hl-app .lang-toggle:hover{border-color:var(--bolt);background:var(--cream)}
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

// Initial page language: ?lang= wins, then a stored preference (shared with the
// main landing via 'moca_lang'), else Hebrew. So mocaintel.com/hotels?lang=en
// opens directly in English — the link to send international prospects.
function initialLang() {
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

export default function HotelsLandingPage() {
  // Start deterministically in Hebrew so the prerendered server markup matches
  // the FIRST client render (clean hydration on /hotels). The visitor's real
  // language (?lang= / stored pref) is applied on mount in the effect below — a
  // brief swap only for ?lang=en deep-links; the Hebrew default never flashes.
  const [lang, setLang] = useState('he')
  const t = COPY[lang]
  const [brand, setBrand] = useState('demo')
  const [demoLang, setDemoLang] = useState('en')
  const [roi, setRoi] = useState({ props: 5, rooms: 90, occ: 72, foreign: 45, comm: 18 })
  const [lead, setLead] = useState({ hotel_name: '', contact_name: '', email: '', phone: '', rooms: '', message: '' })
  const [sent, setSent] = useState(false)
  const [sending, setSending] = useState(false)
  const [err, setErr] = useState('')

  // Apply the visitor's real language after hydration (client-only). SSR and the
  // first client render are deterministically Hebrew (see useState above), so
  // this runs post-mount and only swaps for ?lang=en / a stored preference.
  useEffect(() => {
    const want = initialLang()
    if (want !== 'he') setLang(want)
  }, [])

  // Smooth "elevator" scroll when the topbar nav anchors are clicked. Scoped to
  // this standalone page via an inline style on <html> with cleanup on unmount,
  // so it doesn't leak into the rest of the app (the original index.html mockup
  // had a global `html{scroll-behavior:smooth}` that the React port had dropped).
  useEffect(() => {
    document.title = t.title
    const html = document.documentElement
    // Keep the document element in sync with the active language so the
    // prerendered <html lang="he" dir="rtl"> follows an EN switch (scrollbar
    // side, :lang rules). The page's own RTL/LTR flip is scoped to #hl-app.
    html.lang = lang
    html.dir = t.dir
    const prev = html.style.scrollBehavior
    html.style.scrollBehavior = 'smooth'
    return () => { html.style.scrollBehavior = prev }
  }, [t.title, lang, t.dir])

  // SEO i18n: hreflang alternates + og:locale + a self-canonical for /hotels, so
  // Google indexes the Hebrew (/hotels) and English (/hotels?lang=en) variants as
  // a language pair. Two serving paths for /hotels: (1) the PRERENDERED hotels.html
  // already ships these tags statically in its <head>; (2) the SPA-fallback path
  // (index.html, e.g. client-side nav or offline) inherits the homepage canonical
  // and has NO hreflang. So inject hreflang/og:locale only when ABSENT — idempotent,
  // never duplicating after hydration — and always ensure the canonical points at
  // /hotels. Cleanup restores the original canonical and removes only OUR tags.
  useEffect(() => {
    const head = document.head
    const BASE = 'https://mocaintel.com/hotels'
    let canon = head.querySelector('link[rel="canonical"]')
    const createdCanon = !canon
    const prevCanon = canon ? canon.getAttribute('href') : null
    if (!canon) { canon = document.createElement('link'); canon.setAttribute('rel', 'canonical'); head.appendChild(canon) }
    const made = []
    const add = (tag, attrs) => {
      const el = document.createElement(tag)
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v)
      head.appendChild(el); made.push(el)
    }
    if (!head.querySelector('link[rel="alternate"][hreflang]')) {
      add('link', { rel: 'alternate', hreflang: 'he', href: BASE })
      add('link', { rel: 'alternate', hreflang: 'en', href: `${BASE}?lang=en` })
      add('link', { rel: 'alternate', hreflang: 'x-default', href: BASE })
    }
    if (!head.querySelector('meta[property="og:locale"]')) {
      add('meta', { property: 'og:locale', content: 'he_IL' })
      add('meta', { property: 'og:locale:alternate', content: 'en_US' })
    }
    return () => {
      made.forEach((el) => el.remove())
      if (createdCanon) canon.remove()
      else if (prevCanon !== null) canon.setAttribute('href', prevCanon)
    }
  }, [])

  // Keep the canonical self-referencing the active language variant.
  useEffect(() => {
    const canon = document.head.querySelector('link[rel="canonical"]')
    if (canon) canon.setAttribute('href', lang === 'en' ? 'https://mocaintel.com/hotels?lang=en' : 'https://mocaintel.com/hotels')
  }, [lang])

  function toggleLang() {
    const next = lang === 'he' ? 'en' : 'he'
    setLang(next)
    try { localStorage.setItem('moca_lang', next) } catch { /* ignore */ }
  }

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
    if (!lead.email.trim() && !lead.phone.trim()) { setErr(t.errNoContact); return }
    setSending(true)
    try {
      await api.submitHotelLead(lead)
      setSent(true)
    } catch (e2) {
      setErr(e2.message || t.errFail)
    } finally {
      setSending(false)
    }
  }

  const upd = (k) => (e) => setLead((s) => ({ ...s, [k]: e.target.value }))

  return (
    <div id="hl-app" dir={t.dir} lang={lang}>
      <style>{HL_CSS}</style>

      <div className="topbar">
        <div className="wrap">
          <a className="logo" href="#top"><span className="bolt">⚡</span><span>MOCA<small>GUEST CONNECT</small></span></a>
          <nav>
            <a href="#demo">{t.nav.demo}</a>
            <a href="#how">{t.nav.how}</a>
            <a href="#roi">{t.nav.roi}</a>
            <a href="#pricing">{t.nav.pricing}</a>
            <a href="#contact">{t.nav.contact}</a>
          </nav>
          <div className="top-actions">
            <button type="button" className="lang-toggle" onClick={toggleLang} aria-label={t.toLangAria}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18" />
              </svg>
              {t.toLang}
            </button>
            <a className="btn" href="#contact">{t.ctaPilot}</a>
          </div>
        </div>
      </div>

      <header className="hero" id="top">
        <div className="wrap">
          <div className="kicker">{t.heroKicker}</div>
          <h1>{t.heroLine1}<br />{t.heroLine2pre}<em>{t.heroEm}</em>{t.heroLine2post}</h1>
          <p className="lead">{t.heroLead}</p>
          <div className="cta-row">
            <a className="btn" href="#demo">{t.heroCtaDemo}</a>
            <a className="btn ghost" href="#contact">{t.heroCtaContact}</a>
          </div>
          <div className="stats">
            {t.stats.map((s, i) => (
              <div className="stat" key={i}>{s.pre}<b>{s.b}</b>{s.post}</div>
            ))}
          </div>
        </div>
      </header>

      <section id="demo">
        <div className="wrap">
          <div className="kicker">{t.demoKicker}</div>
          <h2 className="title">{t.demoTitle}</h2>
          <p className="lead">{t.demoLead}</p>
          <div className="demo-grid">
            <div className="controls">
              <h3>{t.demoBrandHeading}</h3>
              <div className="brand-btns">
                {DEMO_BRANDS.map((p) => (
                  <button key={p.slug} type="button" className={`brand-btn${p.slug === brand ? ' on' : ''}`} onClick={() => setBrand(p.slug)}>
                    <span className="sw" style={{ background: `linear-gradient(135deg, ${p.a} 50%, ${p.b} 50%)` }} />
                    <span>{p.label}<small>{p.sub[lang]}</small></span>
                  </button>
                ))}
              </div>
              <div className="mini-row">
                <h3 style={{ margin: 0 }}>{t.demoGuestLang}</h3>
                <div className="seg">
                  <button type="button" className={demoLang === 'en' ? 'on' : ''} onClick={() => setDemoLang('en')}>English</button>
                  <button type="button" className={demoLang === 'he' ? 'on' : ''} onClick={() => setDemoLang('he')}>עברית</button>
                </div>
                <a className="open-full" href={guestUrl} target="_blank" rel="noopener">{t.demoOpenFull}</a>
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
          <div className="kicker">{t.howKicker}</div>
          <h2 className="title">{t.howTitle}</h2>
          <div className="steps">
            {t.steps.map((s, i) => (
              <div className="stepc" key={i}><span className="emoji">{s.emoji}</span><div className="n">{i + 1}</div><h3>{s.h}</h3><p>{s.p}</p></div>
            ))}
          </div>
        </div>
      </section>

      <section id="value">
        <div className="wrap">
          <div className="kicker">{t.valueKicker}</div>
          <h2 className="title">{t.valueTitle}</h2>
          <div className="vgrid">
            {t.values.map((v, i) => (
              <div className="vcard" key={i}><div className="ic">{v.ic}</div><h3>{v.h}</h3><p>{v.p}</p></div>
            ))}
          </div>
        </div>
      </section>

      <section id="roi">
        <div className="wrap">
          <div className="kicker">{t.roiKicker}</div>
          <h2 className="title">{t.roiTitle}</h2>
          <p className="lead">{t.roiLead}</p>
          <div className="roi-grid">
            <div className="sliders">
              <div className="slider"><label>{t.roiProps} <output>{roi.props}</output></label><input type="range" min="1" max="40" step="1" value={roi.props} onChange={(e) => setRoi((s) => ({ ...s, props: +e.target.value }))} /></div>
              <div className="slider"><label>{t.roiRooms} <output>{roi.rooms}</output></label><input type="range" min="20" max="400" step="5" value={roi.rooms} onChange={(e) => setRoi((s) => ({ ...s, rooms: +e.target.value }))} /></div>
              <div className="slider"><label>{t.roiOcc} <output>{roi.occ}%</output></label><input type="range" min="40" max="95" step="1" value={roi.occ} onChange={(e) => setRoi((s) => ({ ...s, occ: +e.target.value }))} /></div>
              <div className="slider"><label>{t.roiForeign} <output>{roi.foreign}%</output></label><input type="range" min="10" max="90" step="5" value={roi.foreign} onChange={(e) => setRoi((s) => ({ ...s, foreign: +e.target.value }))} /></div>
              <div className="slider"><label>{t.roiComm} <output>₪{roi.comm}</output></label><input type="range" min="8" max="35" step="1" value={roi.comm} onChange={(e) => setRoi((s) => ({ ...s, comm: +e.target.value }))} /></div>
            </div>
            <div>
              <div className="results">
                <div className="rcard"><div className="lbl">{t.roiScans}</div><div className="val">{fmtIL(calc.scans)}</div></div>
                <div className="rcard"><div className="lbl">{t.roiBuys}</div><div className="val">{fmtIL(calc.buys)}</div></div>
                <div className="rcard money"><div className="lbl">{t.roiYear}</div><div className="val">₪{fmtIL(calc.hotelYear)}<small>{t.roiPerYear}</small></div></div>
                <div className="rcard"><div className="lbl">{t.roiSaved}</div><div className="val">{fmtIL(calc.saved)}</div></div>
              </div>
              <p className="assume">{t.roiAssume}</p>
            </div>
          </div>
        </div>
      </section>

      <section id="pricing">
        <div className="wrap">
          <div className="kicker">{t.pricingKicker}</div>
          <h2 className="title">{t.pricingTitle}</h2>
          <div className="pilot">
            <div>
              <h3>{t.pilotH}</h3>
              <p>{t.pilotP}</p>
            </div>
            <a className="btn" href="#contact">{t.pilotBtn}</a>
          </div>
          <div className="tiers">
            {t.tiers.map((tier) => (
              <div className={`tier${tier.pop ? ' pop' : ''}`} key={tier.name}>
                {tier.pop && <span className="pop-tag">{t.popTag}</span>}
                <h3>{tier.name}</h3><div className="aud">{tier.aud}</div>
                <div className="price">{tier.price}<small>{t.perProp}</small></div>
                <ul>{tier.feats.map((f, i) => <li key={i}>{f}</li>)}</ul>
                <a className={`btn${tier.pop ? '' : ' ghost'}`} href="#contact">{t.tierBtn}</a>
              </div>
            ))}
          </div>
          <div className="faq">
            {t.faqs.map((f, i) => (
              <details key={i}><summary>{f.q}</summary><p>{f.a}</p></details>
            ))}
          </div>
        </div>
      </section>

      <section id="contact">
        <div className="wrap">
          <div className="kicker">{t.contactKicker}</div>
          <h2 className="title">{t.contactTitle}</h2>
          <div className="lead-grid">
            <div>
              <p className="lead">{t.contactLead}</p>
              <p className="lead" style={{ fontSize: 14.5 }}>{t.contactWrite}<a href="mailto:Helpdesk@mocaintel.com?subject=MOCA Guest Connect" style={{ color: 'var(--bolt)', fontWeight: 800 }}>Helpdesk@mocaintel.com</a></p>
            </div>
            {sent ? (
              <div className="form"><div className="ok">{t.okMain}<br />{t.okSub}</div></div>
            ) : (
              <form className="form" onSubmit={submit}>
                <div className="frow">
                  <div className="field"><label>{t.fHotel}</label><input value={lead.hotel_name} onChange={upd('hotel_name')} placeholder={t.fHotelPh} /></div>
                  <div className="field"><label>{t.fContact}</label><input value={lead.contact_name} onChange={upd('contact_name')} placeholder={t.fContactPh} /></div>
                </div>
                <div className="frow">
                  <div className="field"><label>{t.fEmail}</label><input type="email" value={lead.email} onChange={upd('email')} placeholder={t.fEmailPh} /></div>
                  <div className="field"><label>{t.fPhone}</label><input type="tel" value={lead.phone} onChange={upd('phone')} placeholder={t.fPhonePh} /></div>
                </div>
                <div className="field"><label>{t.fRooms}</label><input type="number" min="1" value={lead.rooms} onChange={upd('rooms')} placeholder={t.fRoomsPh} /></div>
                <div className="field"><label>{t.fMsg}</label><textarea rows="3" value={lead.message} onChange={upd('message')} placeholder={t.fMsgPh} /></div>
                <button className="btn" type="submit" disabled={sending}>{sending ? t.submitting : t.submit}</button>
                {err && <div className="err">{err}</div>}
              </form>
            )}
          </div>
        </div>
      </section>

      <footer>
        <div className="wrap">
          <div className="f-logo">MOCA <span>Guest Connect</span> ⚡</div>
          <small>{t.footerSmall}</small>
        </div>
      </footer>
    </div>
  )
}
