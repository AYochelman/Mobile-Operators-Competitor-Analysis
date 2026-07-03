import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { initTikTokPixel, trackTikTok } from '../lib/tiktokPixel'
import { DEST_ISO_BY_HE, DEST_BY_HE, destLabel, destInHe } from '../data/hotelDestinations'
import { PROVIDER_LOGOS } from '../data/providerLogos'
import BoltMark from '../components/BoltMark'

/* ════════════════════════════════════════════════════════════════════════
   MOCA eSIM — public B2C price-comparison page  (route: /esim-deals)
   A free, no-login consumer tool: pick where you're flying, get the cheapest
   live global-eSIM deals, compared across 30+ providers. Monetized through the
   Flask /go affiliate redirect (no hotel attribution). MOCA-branded, HE default
   + EN, mobile-first. Standalone visual world — all CSS scoped under #esim-app.
   Data: /api/esim/destinations (picker) + /api/esim/compare?destination=<he>.
   ════════════════════════════════════════════════════════════════════════ */

const SYM = { USD: '$', EUR: '€', GBP: '£', ILS: '₪' }
const sym = (c) => SYM[c] || (c ? c + ' ' : '')
const fmtNum = (n) => {
  if (n == null) return ''
  const r = Math.round(n * 100) / 100
  return Number.isInteger(r) ? String(r) : r.toFixed(2).replace(/0$/, '')
}

// Curated quick-picks: the most common Israeli outbound destinations + Europe.
// Filtered at runtime to those that actually carry live deals.
const POPULAR = [
  'ארצות הברית', 'איטליה', 'יוון', 'תאילנד', 'יפן', 'צרפת',
  'ספרד', 'גאורגיה', 'טורקיה', 'איחוד האמירויות', 'בריטניה', 'אירופה',
]

// Cruise is a synthetic, always-pinned "destination" (not a country) — the backend
// folds every provider's cruise bucket (Maya, VOYE) into this one Hebrew key. It has
// no ISO flag (→ ship icon) and its English name isn't derivable from a country code,
// so resolve the label locally; every other destination defers to destLabel().
const CRUISE_HE = 'קרוז'
const destName = (he, lang) => (he === CRUISE_HE ? (lang === 'he' ? 'קרוז' : 'Cruise') : destLabel(he, lang))

const T = {
  he: {
    dir: 'rtl', other: 'EN', otherLang: 'en',
    brandTag: 'השוואת eSIM',
    heroTitle: 'כמה תשלמו על אינטרנט בטיול הבא?',
    heroTitleDest: 'חבילות eSIM {inCountry}',
    heroSub: 'השוואת מחירים חינמית, בלי הרשמה. מוצאים את החבילה המשתלמת ביותר לטיול, מ-30+ ספקי eSIM גלובליים.',
    updated: 'המחירים עודכנו',
    pickTitle: 'לאן טסים?',
    pickSub: 'בחרו יעד ונראה לכם את החבילות הזולות ביותר',
    searchPh: 'חיפוש יעד…',
    popular: 'יעדים פופולריים',
    noResults: 'לא נמצא יעד בשם הזה',
    change: 'שינוי יעד',
    from: 'החל מ-',
    deals: 'חבילות',
    comparing: 'משווים {n} חבילות בשוק',
    wizTitle: 'מתאימים לטיול שלכם',
    qDays: 'לכמה זמן?',
    qData: 'כמה דאטה צריך?',
    topPicks: 'ההמלצות שלנו',
    tripSummary: '{n} חבילות · {days} · {data}',
    allDeals: 'כל החבילות',
    helpTitle: 'פעם ראשונה עם eSIM?',
    h1b: 'רוכשים אונליין - 2 דקות', h1s: 'בלי חנות ובלי תור. משלמים בכרטיס וזהו.',
    h2b: 'סורקים QR שמגיע במייל', h2s: 'הטלפון מתקין את החבילה אוטומטית.',
    h3b: 'נוחתים מחוברים', h3s: 'וואטסאפ והמספר מהבית ממשיכים לעבוד במקביל.',
    compat: 'עובד באייפון XS ומעלה, גלקסי S20 ומעלה, פיקסל 3 ומעלה. מתקינים עוד לפני הטיסה ונוחתים כבר עם אינטרנט.',
    trust: 'מושווה על פני <b>למעלה מ-30 ספקי eSIM גלובליים</b><br>מתעדכן פעמיים ביום על ידי מנוע המודיעין של MOCA',
    disclaim: 'מדגם ממחירי השוק החיים. המחיר הסופי מוצג בעמוד הספק. ייתכן שנקבל עמלה על רכישה דרך הקישורים, ללא עלות נוספת לכם.',
    days: [{ v: 3, l: '3 ימים' }, { v: 7, l: 'שבוע' }, { v: 14, l: 'שבועיים' }, { v: 30, l: 'חודש' }],
    data: [{ v: 3, l: 'קל', s: '3GB · ניווט והודעות' }, { v: 10, l: 'רגיל', s: '10GB · + רשתות' }, { v: 20, l: 'כבד', s: '20GB · + וידאו' }, { v: 'unl', l: 'ללא הגבלה', s: 'בלי לחשוב' }],
    filters: [{ v: 'all', l: 'הכל' }, { v: 'esim', l: 'eSIM' }, { v: 'unl', l: 'ללא הגבלה' }],
    badges: ['הכי משתלם', 'הזול ביותר', 'הכי הרבה דאטה', 'כדאי גם'],
    unlimited: 'ללא הגבלה', daysU: 'ימים', dayU: 'יום', get: 'למעבר לרכישה ↗', perGB: '/GB',
    perks: { instant: 'eSIM מיידי', unlimited: 'דאטה ללא הגבלה' },
    empty: 'אין חבילות שמתאימות לסינון הזה - נסו אפשרות אחרת.',
    emptyDest: 'אין כרגע חבילות ליעד הזה. נסו יעד אחר.',
    loading: 'טוענים את ההצעות המשתלמות…',
    couponLabel: 'קוד {code} · {pct} הנחה', couponNoPct: 'קוד הנחה: {code}', couponCopy: 'העתקה', couponCopied: 'הועתק ✓',
    poweredFree: 'חינם תמיד · ללא הרשמה',
  },
  en: {
    dir: 'ltr', other: 'עב', otherLang: 'he',
    brandTag: 'eSIM Compare',
    heroTitle: 'How much will data cost on your next trip?',
    heroTitleDest: 'eSIM plans for {country}',
    heroSub: 'Free price comparison, no sign-up. Find the best-value plan for your trip across 30+ global eSIM providers.',
    updated: 'Prices updated',
    pickTitle: 'Where are you flying?',
    pickSub: 'Pick a destination and we’ll show the cheapest plans',
    searchPh: 'Search a destination…',
    popular: 'Popular destinations',
    noResults: 'No destination by that name',
    change: 'Change destination',
    from: 'from',
    deals: 'deals',
    comparing: 'comparing {n} market plans',
    wizTitle: 'Matched to your trip',
    qDays: 'How long?',
    qData: 'How much data?',
    topPicks: 'Our picks',
    tripSummary: '{n} deals · {days} · {data}',
    allDeals: 'All deals',
    helpTitle: 'New to eSIM?',
    h1b: 'Buy online — 2 minutes', h1s: 'No store, no queue. Pay by card and you’re done.',
    h2b: 'Scan the QR you get by email', h2s: 'Your phone installs the plan automatically.',
    h3b: 'Land connected', h3s: 'Keep WhatsApp and your home number active alongside.',
    compat: 'Works on iPhone XS and newer, Samsung Galaxy S20+, Google Pixel 3+. Install before you fly and you land already online.',
    trust: 'Compared across <b>30+ global eSIM providers</b><br>Refreshed twice a day by MOCA market intelligence',
    disclaim: 'Sample of live market prices. Final price is shown on the provider’s page. We may earn a commission on purchases made through these links, at no extra cost to you.',
    days: [{ v: 3, l: '3 days' }, { v: 7, l: '1 week' }, { v: 14, l: '2 weeks' }, { v: 30, l: '1 month' }],
    data: [{ v: 3, l: 'Light', s: '3GB · maps & chat' }, { v: 10, l: 'Regular', s: '10GB · + social' }, { v: 20, l: 'Heavy', s: '20GB · + video' }, { v: 'unl', l: 'Unlimited', s: 'no limits' }],
    filters: [{ v: 'all', l: 'All' }, { v: 'esim', l: 'eSIM' }, { v: 'unl', l: 'Unlimited' }],
    badges: ['BEST VALUE', 'CHEAPEST', 'MAX DATA', 'ALSO GREAT'],
    unlimited: 'Unlimited', daysU: 'days', dayU: 'day', get: 'Get this deal ↗', perGB: '/GB',
    perks: { instant: 'Instant eSIM', unlimited: 'Unlimited data' },
    empty: 'No deals match this filter — try another option.',
    emptyDest: 'No deals for this destination right now. Try another one.',
    loading: 'Loading the best deals…',
    couponLabel: 'Code {code} · {pct} off', couponNoPct: 'Discount code: {code}', couponCopy: 'copy', couponCopied: 'copied ✓',
    poweredFree: 'Always free · no sign-up',
  },
}

const DATE_LOCALES = { en: 'en-GB', he: 'he-IL' }

const CSS = `
#esim-app{--c1:#5c3317;--c2:#c9622f;--bg:#f9f4ee;--cream:#f5ede0;--ink:#3b1f0d;--sub:#8a6a4a;--muted:#a08468;--line:#e0cdb5;--card:#fff;--down:#4a7c3f;--r:20px;
  font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--ink);min-height:100dvh;-webkit-font-smoothing:antialiased}
#esim-app *{box-sizing:border-box;margin:0;padding:0}
#esim-app .page{max-width:560px;margin:0 auto;min-height:100dvh;display:flex;flex-direction:column}
#esim-app .hero{position:relative;overflow:hidden;color:#fff;background:linear-gradient(150deg,var(--c1),color-mix(in srgb,var(--c1),#000 32%));padding:22px 22px 30px;border-radius:0 0 30px 30px}
#esim-app .hero::before{content:"";position:absolute;inset:auto -70px -120px auto;width:260px;height:260px;border-radius:50%;background:color-mix(in srgb,var(--c2),transparent 70%)}
#esim-app .hero::after{content:"";position:absolute;top:-90px;inset-inline-start:-60px;width:220px;height:220px;border-radius:50%;background:color-mix(in srgb,#fff,transparent 90%)}
#esim-app .hero>*{position:relative;z-index:1}
#esim-app .hero-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:26px}
#esim-app .brand{display:flex;align-items:center;gap:10px}
#esim-app .bolt{width:40px;height:40px;border-radius:12px;background:#fff;color:var(--c1);display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 4px 14px rgba(0,0,0,.25)}
#esim-app .brand-name{font-weight:800;font-size:17px;line-height:1;letter-spacing:.3px}
#esim-app .brand-tag{font-size:10px;letter-spacing:2.2px;opacity:.78;font-weight:600;margin-top:3px}
#esim-app .lang{border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.12);color:#fff;border-radius:999px;padding:6px 14px;font:inherit;font-weight:700;font-size:13px;cursor:pointer}
#esim-app .hero h1{font-size:25px;font-weight:800;line-height:1.2;margin-bottom:9px}
#esim-app .hero p{font-size:14.5px;line-height:1.5;opacity:.9;max-width:40ch}
#esim-app .updated{display:inline-flex;align-items:center;gap:7px;margin-top:16px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18);padding:6px 12px;border-radius:999px;font-size:12px;font-weight:600}
#esim-app .dot{width:7px;height:7px;border-radius:50%;background:#7fd99b;box-shadow:0 0 0 3px rgba(127,217,155,.25);animation:epulse 2s infinite}
@keyframes epulse{50%{box-shadow:0 0 0 6px rgba(127,217,155,.08)}}
#esim-app main{padding:18px 16px 8px;display:flex;flex-direction:column;gap:20px;flex:1}
#esim-app .card{background:var(--card);border-radius:var(--r);padding:18px;box-shadow:0 6px 24px rgba(70,45,20,.07)}
#esim-app .sec{font-size:17px;font-weight:800;margin-bottom:12px}
#esim-app .picker{margin-top:-26px}
#esim-app .picker h2{font-size:18px;font-weight:800;margin-bottom:3px}
#esim-app .picker .psub{font-size:13px;color:var(--sub);font-weight:600;margin-bottom:14px}
#esim-app .search-wrap{position:relative}
#esim-app .search{width:100%;border:1.6px solid var(--line);background:var(--bg);border-radius:14px;padding:13px 44px 13px 14px;font:inherit;font-size:15px;font-weight:600;color:var(--ink);outline:none;transition:border-color .15s,box-shadow .15s}
#esim-app[dir=ltr] .search{padding:13px 14px 13px 44px}
#esim-app .search:focus{border-color:var(--c2);box-shadow:0 0 0 3px color-mix(in srgb,var(--c2),transparent 82%)}
#esim-app .search-ic{position:absolute;inset-inline-end:14px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none}
#esim-app .results{margin-top:8px;border:1px solid var(--line);border-radius:14px;overflow:hidden;max-height:298px;overflow-y:auto}
#esim-app .res{display:flex;align-items:center;gap:11px;width:100%;border:0;border-bottom:1px solid var(--cream);background:#fff;padding:11px 14px;font:inherit;cursor:pointer;text-align:start;transition:background .12s}
#esim-app .res:last-child{border-bottom:0}
#esim-app .res:hover,#esim-app .res:focus-visible{background:var(--cream)}
#esim-app .res .flag{font-size:21px;flex:none;width:26px;text-align:center}
#esim-app .res .rname{flex:1;min-width:0;font-weight:700;font-size:14.5px}
#esim-app .res .rprice{font-size:12px;color:var(--sub);font-weight:700;white-space:nowrap}
#esim-app .res .rprice b{color:var(--down);font-size:13px}
#esim-app .no-res{padding:18px;text-align:center;color:var(--sub);font-weight:600;font-size:13.5px}
#esim-app .pop-lbl{font-size:12px;font-weight:700;color:var(--sub);margin:16px 0 9px}
#esim-app .pops{display:flex;gap:8px;flex-wrap:wrap}
#esim-app .pop{display:inline-flex;align-items:center;gap:7px;border:1.5px solid var(--line);background:#fff;border-radius:999px;cursor:pointer;padding:8px 13px;font:inherit;font-size:13.5px;font-weight:700;color:var(--ink);transition:all .14s}
#esim-app .pop:hover{border-color:var(--c2);background:var(--cream)}
#esim-app .pop .flag{font-size:16px}
#esim-app .dest-bar{display:flex;align-items:center;gap:12px;background:var(--card);border-radius:var(--r);padding:14px 16px;box-shadow:0 6px 24px rgba(70,45,20,.07)}
#esim-app .dest-bar .flag{font-size:30px;flex:none}
#esim-app .flag-img{display:inline-block;vertical-align:middle;height:15px;width:auto;border-radius:2px;box-shadow:0 0 0 .5px rgba(0,0,0,.16)}
#esim-app .res .flag-img{width:24px;height:auto;flex:none}
#esim-app .pop .flag-img{height:13px}
#esim-app .dest-bar .flag-img{height:24px;border-radius:4px;flex:none}
#esim-app .dest-bar .dmeta{flex:1;min-width:0}
#esim-app .dest-bar .dname{font-weight:800;font-size:18px}
#esim-app .dest-bar .dcount{font-size:12.5px;color:var(--sub);font-weight:600;margin-top:1px}
#esim-app .dest-bar .changeb{border:1.4px solid var(--line);background:#fff;color:var(--c1);border-radius:11px;cursor:pointer;padding:8px 13px;font:inherit;font-weight:700;font-size:12.5px;white-space:nowrap}
#esim-app .dest-bar .changeb:hover{border-color:var(--c2)}
#esim-app .trip-sum{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;color:var(--c1);background:color-mix(in srgb,var(--c1),#fff 90%);border:1px solid color-mix(in srgb,var(--c1),#fff 78%);padding:5px 11px;border-radius:999px;margin-bottom:12px}
#esim-app .wizard h2{font-size:16.5px;font-weight:800;margin-bottom:4px}
#esim-app .wizard .q{font-size:13px;font-weight:700;color:var(--sub);margin:14px 0 8px}
#esim-app .chips{display:flex;gap:8px;flex-wrap:wrap}
#esim-app .chip{border:1.5px solid var(--line);background:#fff;border-radius:14px;cursor:pointer;padding:9px 13px;font:inherit;font-size:13.5px;font-weight:700;color:var(--ink);transition:all .15s;flex:1 1 auto;text-align:center;min-width:74px}
#esim-app .chip small{display:block;font-size:10.5px;font-weight:600;color:var(--sub);margin-top:2px}
#esim-app .chip.on{background:var(--c1);border-color:var(--c1);color:#fff}
#esim-app .chip.on small{color:rgba(255,255,255,.78)}
#esim-app .pick{background:var(--card);border-radius:var(--r);padding:16px;margin-bottom:10px;box-shadow:0 6px 24px rgba(70,45,20,.07);border:1.5px solid transparent;position:relative}
#esim-app .pick.first{border-color:var(--c2);box-shadow:0 10px 30px color-mix(in srgb,var(--c2),transparent 74%)}
#esim-app .badge{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:1px;padding:4px 10px;border-radius:999px;margin-bottom:10px;text-transform:uppercase;margin-inline-end:6px}
#esim-app .badge.b1{background:color-mix(in srgb,var(--c2),#fff 75%);color:color-mix(in srgb,var(--c2),#000 35%)}
#esim-app .badge.b2{background:#e3f3e9;color:#246b43}
#esim-app .badge.b3{background:#efe7f7;color:#6b3fa0}
#esim-app .badge.b4{background:var(--cream);color:var(--sub)}
#esim-app .deal-row{display:flex;align-items:center;gap:12px}
#esim-app .pchip{width:42px;height:42px;border-radius:13px;flex:none;color:#fff;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;letter-spacing:.4px}
#esim-app .pchip.logo{background:#fff;border:1.5px solid;padding:5px}
#esim-app .pchip.logo img{width:100%;height:100%;object-fit:contain;display:block}
#esim-app .deal-info{flex:1;min-width:0}
#esim-app .deal-provider{font-weight:800;font-size:14.5px}
#esim-app .deal-meta{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:12.5px;color:var(--sub);font-weight:600;margin-top:2px;line-height:1.5}
#esim-app .deal-meta .deal-sep{opacity:.45}
#esim-app .deal-price{text-align:end}
#esim-app[dir=rtl] .deal-price{text-align:start}
#esim-app .price-main{font-weight:800;font-size:18px;white-space:nowrap}
#esim-app .price-sub{font-size:11.5px;color:var(--sub);font-weight:600;white-space:nowrap}
#esim-app .tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
#esim-app .tag{font-size:10.5px;font-weight:700;background:var(--bg);border:1px solid var(--line);color:var(--sub);padding:3px 9px;border-radius:999px}
#esim-app .get{margin-top:12px;width:100%;border:0;border-radius:13px;cursor:pointer;background:var(--c1);color:#fff;font:inherit;font-weight:800;font-size:14px;padding:12px;transition:transform .12s,opacity .12s}
#esim-app .get:hover{opacity:.94}
#esim-app .get:active{transform:scale(.985);opacity:.9}
#esim-app .all-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;flex-wrap:wrap}
#esim-app .filters{display:flex;gap:7px;flex-wrap:wrap}
#esim-app .fpill{border:1.5px solid var(--line);background:#fff;border-radius:999px;cursor:pointer;padding:6px 13px;font:inherit;font-size:12.5px;font-weight:700;color:var(--sub)}
#esim-app .fpill.on{background:var(--ink);border-color:var(--ink);color:#fff}
#esim-app .deal{background:var(--card);border-radius:16px;padding:13px 14px;margin-bottom:8px;box-shadow:0 3px 12px rgba(70,45,20,.05)}
#esim-app .deal .get{margin-top:0;width:auto;padding:9px 15px;font-size:12.5px;border-radius:11px}
#esim-app .deal-bottom{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:10px}
#esim-app .empty{padding:26px;text-align:center;color:var(--sub);font-weight:600;font-size:13.5px}
#esim-app .esim-help h2{font-size:15.5px;font-weight:800;margin-bottom:12px}
#esim-app .step{display:flex;gap:12px;align-items:flex-start;margin-bottom:12px}
#esim-app .step:last-of-type{margin-bottom:8px}
#esim-app .snum{width:26px;height:26px;border-radius:9px;background:color-mix(in srgb,var(--c1),#fff 88%);color:var(--c1);font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;flex:none;margin-top:1px}
#esim-app .step b{display:block;font-size:13.5px}
#esim-app .step span{font-size:12.5px;color:var(--sub);line-height:1.4}
#esim-app .compat{font-size:11.5px;color:var(--sub);border-top:1px dashed var(--line);padding-top:10px;margin-top:4px}
#esim-app .trust{text-align:center;font-size:12px;color:var(--sub);font-weight:600;line-height:1.6;padding:4px 18px}
#esim-app .trust b{color:var(--ink)}
#esim-app footer{padding:18px 16px 30px;text-align:center}
#esim-app .powered{font-size:12.5px;color:var(--sub);font-weight:600}
#esim-app .powered b{color:var(--ink)}
#esim-app .freepill{display:inline-block;margin-bottom:8px;font-size:11.5px;font-weight:800;letter-spacing:.4px;color:var(--down);background:#e3f3e9;border-radius:999px;padding:4px 12px}
#esim-app .disclaim{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.5;max-width:46ch;margin-inline:auto}
#esim-app .splash{min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;color:var(--c1);text-align:center;padding:30px}
#esim-app .spin{width:34px;height:34px;border-radius:50%;border:3px solid color-mix(in srgb,var(--c1),transparent 78%);border-top-color:var(--c1);animation:espin .8s linear infinite}
@keyframes espin{to{transform:rotate(360deg)}}
#esim-app .reveal{animation:efade .35s ease both}
@keyframes efade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
#esim-app .coupon{display:flex;align-items:center;gap:8px;width:100%;margin-top:10px;border:1.5px dashed color-mix(in srgb,var(--c2),#fff 35%);background:color-mix(in srgb,var(--c2),#fff 90%);color:color-mix(in srgb,var(--c2),#000 32%);border-radius:12px;padding:8px 11px;font:inherit;font-weight:800;font-size:12.5px;cursor:pointer;text-align:start;transition:transform .12s}
#esim-app .coupon:active{transform:scale(.99)}
#esim-app .coupon svg{flex:none;width:15px;height:15px}
#esim-app .coupon .ctxt{flex:1;min-width:0}
#esim-app .coupon .ccopy{font-size:10.5px;font-weight:700;background:#fff;border-radius:8px;padding:3px 8px;white-space:nowrap}
`

// Real flag image (flagcdn.com SVG) keyed by the destination's ISO code. Emoji
// flags are NOT rendered on Windows (they fall back to the 2-letter code), so we
// use images. Europe → the EU flag; regions / non-ISO destinations / a failed
// load → a globe emoji (which Windows does render). CSS sizes it per context.
function Flag({ he }) {
  const [err, setErr] = useState(false)
  // Cruise has no country flag — a ship emoji (renders fine on Windows, unlike the
  // regional-indicator flag emojis) stands in for it.
  if (he === CRUISE_HE) return <span className="flag" aria-hidden="true">🚢</span>
  const iso = he === 'אירופה' ? 'eu' : (DEST_ISO_BY_HE[he] || '').toLowerCase()
  if (iso && !err) {
    return (
      <img className="flag-img" src={`https://flagcdn.com/${iso}.svg`} alt="" aria-hidden="true"
        loading="lazy" onError={() => setErr(true)} />
    )
  }
  return <span className="flag" aria-hidden="true">🌍</span>
}

function gbLabel(d, t) {
  if (d.gb == null) return t.unlimited
  if (d.gb < 1) return `${Math.round(d.gb * 1024)}MB`
  return `${+d.gb}GB`
}

// Provider tile: real logo (curated local file by provider id, else DuckDuckGo
// favicon CDN by domain) on a white chip with a brand-colored ring; falls back to
// the colored monogram on missing/failed logo. Local logos win because the favicon
// CDN serves a generic placeholder (HTTP 200) for unknown domains, so onError
// never fires — see data/providerLogos.js.
function ProviderLogo({ pv, provider, mono }) {
  const [err, setErr] = useState(false)
  const src = PROVIDER_LOGOS[provider] || (pv.domain ? `https://icons.duckduckgo.com/ip3/${pv.domain}.ico` : null)
  if (src && !err) {
    return (
      <div className="pchip logo" style={{ borderColor: pv.color }}>
        <img src={src} alt="" loading="lazy" onError={() => setErr(true)} />
      </div>
    )
  }
  return <div className="pchip" style={{ background: pv.color }}>{mono}</div>
}

// Discount-code pill (e.g. Saily MOCA 10%). Tap to copy. Skips link-out coupons.
function CouponPill({ coupon, t }) {
  const [copied, setCopied] = useState(false)
  if (!coupon || !coupon.code || coupon.external_offer_url) return null
  const pct = (coupon.discount_label || '').match(/\d+%/)
  const label = (pct ? t.couponLabel : t.couponNoPct)
    .replace('{code}', coupon.code).replace('{pct}', pct ? pct[0] : '')
  const copy = () => {
    if (!navigator.clipboard) return
    navigator.clipboard.writeText(coupon.code)
      .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })
      .catch(() => {})
  }
  return (
    <button type="button" className="coupon" onClick={copy} aria-label={label}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2 2 2 0 0 0 0 4 2 2 0 0 1-2 2H5a2 2 0 0 1-2-2 2 2 0 0 0 0-4" />
        <path d="M15 6v12" />
      </svg>
      <span className="ctxt"><bdi>{label}</bdi></span>
      <span className="ccopy">{copied ? t.couponCopied : t.couponCopy}</span>
    </button>
  )
}

// Read a URL/query param at first render (SPA-only page, so window is defined).
function _initParam(key) {
  try { return new URLSearchParams(window.location.search).get(key) } catch { return null }
}

export default function EsimComparePage() {
  const [params, setParams] = useSearchParams()
  // Language + destination are derived from the URL (?lang / ?dest) or stored
  // pref at first render, so per-destination deep links are shareable.
  const [lang, setLang] = useState(() => {
    const wanted = _initParam('lang')
    if (['he', 'en'].includes(wanted)) return wanted
    try { const s = localStorage.getItem('esim_lang'); if (['he', 'en'].includes(s)) return s } catch { /* ignore */ }
    return 'he'
  })
  const [destList, setDestList] = useState([])      // [{destination,count,min_price}]
  const [dest, setDest] = useState(() => _initParam('dest') || null) // canonical Hebrew string
  const [data, setData] = useState(null)            // /api/esim/compare payload
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [stay, setStay] = useState(7)
  const [dataNeed, setDataNeed] = useState(10)
  const [filter, setFilter] = useState('all')
  const resultsRef = useRef(null)
  // Campaign tag captured from the landing URL (utm), forwarded to /go on each
  // deal tap so a click is attributable to the specific post/video that drove it.
  const [campaign] = useState(() => _initParam('campaign') || _initParam('utm_campaign') || _initParam('utm_source') || '')
  // Anonymous analytics: a per-session token + acquisition source (utm_source,
  // else referrer host, else 'direct'). Powers the B2C traffic dashboard.
  const [sid] = useState(() => {
    try {
      let s = sessionStorage.getItem('esim_sid')
      if (!s) { s = Math.random().toString(36).slice(2) + Date.now().toString(36); sessionStorage.setItem('esim_sid', s) }
      return s
    } catch { return '' }
  })
  const acq = useMemo(() => {
    let ref = ''
    try { ref = document.referrer ? new URL(document.referrer).hostname.replace(/^www\./, '') : '' } catch { /* ignore */ }
    return { src: _initParam('utm_source') || ref || 'direct', referrer: ref }
  }, [])
  const viewedRef = useRef(false)

  const t = T[lang] || T.he

  // Load the destination catalog once (for the picker).
  useEffect(() => {
    let alive = true
    api.getEsimDestinations().then((list) => { if (alive) setDestList(Array.isArray(list) ? list : []) }).catch(() => {})
    return () => { alive = false }
  }, [])

  // Anonymous page-view beacon, once per mount (ref-guarded against StrictMode).
  useEffect(() => {
    if (viewedRef.current) return
    viewedRef.current = true
    // TikTok Pixel: load + PageView (powers "Landing page view" optimization and
    // a retargeting audience). No-op unless VITE_TIKTOK_PIXEL_ID is set.
    initTikTokPixel()
    api.trackEsim({ type: 'page_view', sid, src: acq.src, campaign, lang,
      destination: dest || undefined, referrer: acq.referrer || undefined })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Fetch deals whenever the chosen destination changes (clearDest resets data).
  useEffect(() => {
    if (!dest) return
    let alive = true
    setLoading(true)
    setData(null)
    api.getEsimCompare(dest)
      .then((d) => { if (alive) { setData(d); setLoading(false) } })
      .catch(() => { if (alive) { setData({ deals: [], providers: {}, coupons: {} }); setLoading(false) } })
    return () => { alive = false }
  }, [dest])

  // Document direction/lang/title (this is a standalone full-page experience).
  useEffect(() => {
    const html = document.documentElement
    const prevDir = html.dir, prevLang = html.lang, prevTitle = document.title
    html.dir = t.dir
    html.lang = lang
    const cl = dest ? destName(dest, lang) : null
    document.title = cl
      ? (lang === 'he' ? `חבילות eSIM ל${cl} - השוואת מחירים | MOCA` : `eSIM plans for ${cl} - price comparison | MOCA`)
      : (lang === 'he' ? 'השוואת מחירי eSIM לטיול בחו"ל - חינם | MOCA' : 'Compare eSIM prices for your trip - free | MOCA')
    return () => { html.dir = prevDir; html.lang = prevLang; document.title = prevTitle }
  }, [lang, dest, t.dir])

  // SEO: this page ships the generic index.html <head>, whose canonical points at
  // the site root - which makes Google treat /esim-deals (and the esim.mocaintel.com
  // mirror) as a duplicate of the homepage and drop it. Rewrite the canonical to a
  // self-referencing apex URL + set a page-specific description. Googlebot renders
  // JS, so this is read. The canonical stays the base /esim-deals (no ?dest) so all
  // destination variants consolidate onto one indexable URL. The prerendered
  // esim.html shell already carries the same tags for the raw (pre-JS) HTML; this
  // covers the SPA index.html shell (subdomain root, super-admin preview, etc.).
  useEffect(() => {
    const CANON = 'https://mocaintel.com/esim-deals'
    const DESC = lang === 'he'
      ? 'השוואת מחירי eSIM חינמית לטיול בחו"ל, בלי הרשמה. מוצאים את החבילה המשתלמת ביותר מתוך למעלה מ-30 ספקי eSIM גלובליים, מתעדכן פעמיים ביום.'
      : 'Free eSIM price comparison for your trip abroad, no sign-up. Find the best-value plan across 30+ global eSIM providers, refreshed twice a day.'
    const head = document.head

    let canon = head.querySelector('link[rel="canonical"]')
    const madeCanon = !canon
    const prevHref = canon ? canon.getAttribute('href') : null
    if (!canon) { canon = document.createElement('link'); canon.rel = 'canonical'; head.appendChild(canon) }
    canon.setAttribute('href', CANON)

    let desc = head.querySelector('meta[name="description"]')
    const madeDesc = !desc
    const prevDesc = desc ? desc.getAttribute('content') : null
    if (!desc) { desc = document.createElement('meta'); desc.setAttribute('name', 'description'); head.appendChild(desc) }
    desc.setAttribute('content', DESC)

    return () => {
      if (madeCanon) canon.remove()
      else if (prevHref != null) canon.setAttribute('href', prevHref)
      if (madeDesc) desc.remove()
      else if (prevDesc != null) desc.setAttribute('content', prevDesc)
    }
  }, [lang])

  const switchLang = () => {
    const nl = t.otherLang
    setLang(nl)
    try { localStorage.setItem('esim_lang', nl) } catch { /* ignore */ }
  }

  const chooseDest = (he) => {
    setDest(he)
    setQuery('')
    setFilter('all')
    api.trackEsim({ type: 'destination_pick', sid, destination: he, src: acq.src, campaign, lang })
    const next = new URLSearchParams(params)
    next.set('dest', he)
    setParams(next, { replace: true })
    requestAnimationFrame(() => {
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60)
    })
  }
  const clearDest = () => {
    setDest(null)
    setData(null)
    const next = new URLSearchParams(params)
    next.delete('dest')
    setParams(next, { replace: true })
  }

  // Destinations that actually carry deals, enriched for the picker.
  const destByHe = useMemo(() => {
    const m = {}
    for (const d of destList) m[d.destination] = d
    return m
  }, [destList])

  // Searchable list: only deal-bearing destinations, labeled + sorted by name.
  const searchable = useMemo(() => {
    return destList
      .filter((d) => d.destination)
      .map((d) => ({
        he: d.destination,
        label: destName(d.destination, lang),
        count: d.count,
        min: d.min_price,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, lang === 'he' ? 'he' : 'en'))
  }, [destList, lang])

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return searchable
      .filter((d) => d.he.toLowerCase().includes(q) || (d.label || '').toLowerCase().includes(q))
      .slice(0, 40)
  }, [query, searchable])

  const popular = useMemo(() => {
    const inList = (he) => destByHe[he]
    const picks = POPULAR.filter(inList)
    // top up from the most-covered destinations if the curated list is thin
    if (picks.length < 8) {
      for (const d of destList) {
        if (picks.length >= 10) break
        if (d.destination === 'ישראל' || picks.includes(d.destination)) continue
        if (DEST_BY_HE[d.destination]) picks.push(d.destination)
      }
    }
    // Cruise is pinned first (like USA) whenever it actually carries deals.
    const pinned = destByHe[CRUISE_HE]
      ? [CRUISE_HE, ...picks.filter((he) => he !== CRUISE_HE)]
      : picks
    return pinned.slice(0, 12).map((he) => ({ he, label: destName(he, lang) }))
  }, [destByHe, destList, lang])

  const fx = data?.fx || { usd: 3.7, eur: 4.0, gbp: 4.7 }
  const deals = data?.deals || []
  const providers = data?.providers || {}
  const coupons = data?.coupons || {}
  const destInfo = dest ? destByHe[dest] : null
  const fillCountry = (s) => (s || '')
    .replace(/\{inCountry\}/g, destInHe(dest || ''))
    .replace(/\{country\}/g, dest ? destName(dest, lang) : '')

  // Accurate ₪ headline: the stored `price` column uses a stale scrape-time rate
  // (~20% low), so convert the native original_price with the live FX instead.
  // ILS-native deals (no original/foreign currency) keep their stored price.
  const RATE = { USD: fx.usd, EUR: fx.eur, GBP: fx.gbp }
  const ils = (d) => {
    if (!d) return 0
    if (d.currency === 'ILS' || !d.original_price) return d.price || 0
    const r = RATE[d.currency]
    return r ? d.original_price * r : (d.price || 0)
  }
  const priceMain = (d) => `₪${fmtNum(Math.round(ils(d)))}`
  const priceSub = (d) => (d.currency && d.currency !== 'ILS' && d.original_price)
    ? `${sym(d.currency)}${fmtNum(d.original_price)}`
    : ''
  const metaLine = (d) => {
    const bits = [gbLabel(d, t)]
    if (d.days) bits.push(`${d.days} ${d.days === 1 ? t.dayU : t.daysU}`)
    if (d.gb && d.gb >= 1) bits.push(`₪${fmtNum(Math.round((ils(d) / d.gb) * 10) / 10)}${t.perGB}`)
    return bits
  }

  const fitsTrip = (d) => {
    if (d.days != null && d.days < stay) return false
    if (dataNeed === 'unl') return d.gb == null || d.gb >= 50
    return d.gb == null || d.gb >= dataNeed
  }
  const eligible = useMemo(() => deals.filter(fitsTrip), [deals, stay, dataNeed]) // eslint-disable-line react-hooks/exhaustive-deps

  const picks = useMemo(() => {
    if (!eligible.length) return []
    const need = dataNeed === 'unl' ? null : dataNeed
    const idx = (d) => deals.indexOf(d)
    const fit = (d) => ils(d)
      + (d.gb == null && need != null ? 14 : 0)
      + Math.max(0, (d.days || stay) - stay) * 0.12
      + (d.gb && need ? Math.max(0, d.gb - need) * 0.3 : 0)
    const byFit = [...eligible].sort((a, b) => fit(a) - fit(b))
    const byPrice = [...eligible].sort((a, b) => ils(a) - ils(b))
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
    let rows = [...eligible]
    if (filter === 'esim') rows = rows.filter((d) => d.form === 'esim')
    if (filter === 'unl') rows = rows.filter((d) => d.gb == null)
    return rows.sort((a, b) => ils(a) - ils(b))
  }, [eligible, filter])

  const tripSummary = useMemo(() => {
    const stayOpt = t.days.find((o) => o.v === stay)
    const stayLabel = stayOpt ? stayOpt.l : `${stay} ${stay === 1 ? t.dayU : t.daysU}`
    const dataLabel = dataNeed === 'unl' ? t.unlimited : `${dataNeed}GB`
    return t.tripSummary.replace('{n}', String(eligible.length)).replace('{days}', stayLabel).replace('{data}', dataLabel)
  }, [t, stay, dataNeed, eligible.length])

  const openDeal = (d) => {
    // TikTok conversion signal: the affiliate tap is the money event. No-op
    // unless the pixel is configured. Lets the campaign optimize toward clicks.
    trackTikTok('ClickButton', {
      content_type: 'product',
      content_id: d.provider,
      content_name: d.plan_name,
      description: dest || undefined,
    })
    window.open(api.esimGoUrl(d.provider, d.plan_name, lang, dest, campaign), '_blank', 'noopener')
  }

  const updated = data?.updated_at ? new Date(data.updated_at) : null
  const updatedStr = updated
    ? `${t.updated}: ${updated.toLocaleDateString(DATE_LOCALES[lang], { day: 'numeric', month: 'short' })} · ${updated.toLocaleTimeString(DATE_LOCALES[lang], { hour: '2-digit', minute: '2-digit' })}`
    : ''
  const cls = ['b1', 'b2', 'b3', 'b4']

  const DealCore = ({ d }) => {
    const pv = providers[d.provider] || { label: d.provider, color: '#5c3317' }
    const mono = (pv.label || d.provider).replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || 'GE'
    return (
      <>
        <div className="deal-row">
          <ProviderLogo pv={pv} provider={d.provider} mono={mono} />
          <div className="deal-info">
            <div className="deal-provider"><bdi>{pv.label}</bdi></div>
            <div className="deal-meta">{metaLine(d).flatMap((x, i) => i === 0
              ? [<bdi key={`v${i}`}>{x}</bdi>]
              : [<span key={`s${i}`} className="deal-sep" aria-hidden="true">·</span>, <bdi key={`v${i}`}>{x}</bdi>])}</div>
          </div>
          <div className="deal-price">
            <div className="price-main" dir="ltr">{priceMain(d)}</div>
            {priceSub(d) && <div className="price-sub" dir="ltr">{priceSub(d)}</div>}
          </div>
        </div>
        <div className="tags">{(d.perks || []).map((k) => t.perks[k] && <span className="tag" key={k}>{t.perks[k]}</span>)}</div>
        <CouponPill coupon={coupons[d.provider]} t={t} />
      </>
    )
  }

  return (
    <div id="esim-app" dir={t.dir}>
      <style>{CSS}</style>
      <div className="page">
        <header className="hero">
          <div className="hero-top">
            <div className="brand">
              <div className="bolt"><BoltMark size={22} /></div>
              <div>
                <div className="brand-name">MOCA</div>
                <div className="brand-tag">{t.brandTag}</div>
              </div>
            </div>
            <button type="button" className="lang" onClick={switchLang}>{t.other}</button>
          </div>
          <h1>{dest ? fillCountry(t.heroTitleDest) : t.heroTitle}</h1>
          <p>{t.heroSub}</p>
          {dest && updatedStr && <div className="updated"><span className="dot" /><span>{updatedStr}</span></div>}
        </header>

        <main>
          {/* ── Destination picker (the entry point) ─────────────────────── */}
          {!dest ? (
            <section className="card picker">
              <h2>{t.pickTitle}</h2>
              <div className="psub">{t.pickSub}</div>
              <div className="search-wrap">
                <input
                  className="search" type="text" value={query} placeholder={t.searchPh}
                  onChange={(e) => setQuery(e.target.value)} autoComplete="off"
                  aria-label={t.pickTitle}
                />
                <svg className="search-ic" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                  <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
                </svg>
              </div>
              {query.trim() && (
                results.length ? (
                  <div className="results">
                    {results.map((d) => (
                      <button type="button" className="res" key={d.he} onClick={() => chooseDest(d.he)}>
                        <Flag he={d.he} />
                        <span className="rname"><bdi>{d.label}</bdi></span>
                        <span className="rprice">{d.count} {t.deals}</span>
                      </button>
                    ))}
                  </div>
                ) : <div className="no-res">{t.noResults}</div>
              )}
              {!query.trim() && popular.length > 0 && (
                <>
                  <div className="pop-lbl">{t.popular}</div>
                  <div className="pops">
                    {popular.map((d) => (
                      <button type="button" className="pop" key={d.he} onClick={() => chooseDest(d.he)}>
                        <Flag he={d.he} /><bdi>{d.label}</bdi>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </section>
          ) : (
            <section className="dest-bar reveal" ref={resultsRef}>
              <Flag he={dest} />
              <div className="dmeta">
                <div className="dname"><bdi>{destName(dest, lang)}</bdi></div>
                {destInfo && <div className="dcount">{t.comparing.replace('{n}', destInfo.count)}</div>}
              </div>
              <button type="button" className="changeb" onClick={clearDest}>{t.change}</button>
            </section>
          )}

          {/* ── Results (after a destination is chosen) ──────────────────── */}
          {dest && loading && (
            <div className="splash"><div className="spin" /><div style={{ fontWeight: 700 }}>{t.loading}</div></div>
          )}

          {dest && !loading && deals.length === 0 && (
            <div className="card empty">{t.emptyDest}</div>
          )}

          {dest && !loading && deals.length > 0 && (
            <>
              <section className="card wizard reveal">
                <h2>{t.wizTitle}</h2>
                <div className="q">{t.qDays}</div>
                <div className="chips">
                  {t.days.map((o) => (
                    <button key={o.v} type="button" className={`chip${o.v === stay ? ' on' : ''}`} onClick={() => setStay(o.v)}>{o.l}</button>
                  ))}
                </div>
                <div className="q">{t.qData}</div>
                <div className="chips">
                  {t.data.map((o) => (
                    <button key={o.v} type="button" className={`chip${String(o.v) === String(dataNeed) ? ' on' : ''}`}
                      onClick={() => setDataNeed(o.v === 'unl' ? 'unl' : o.v)}>
                      {o.l}<small>{o.s}</small>
                    </button>
                  ))}
                </div>
              </section>

              <section className="reveal">
                <h2 className="sec" style={{ marginBottom: 6 }}>{t.topPicks}</h2>
                <div className="trip-sum">{tripSummary}</div>
                {picks.length ? picks.map(({ d, badges }, i) => (
                  <div className={`pick${i === 0 ? ' first' : ''}`} key={i}>
                    {badges.map((b) => <span className={`badge ${cls[b]}`} key={b}>{t.badges[b]}</span>)}
                    <DealCore d={d} />
                    <button type="button" className="get" onClick={() => openDeal(d)}>{t.get}</button>
                  </div>
                )) : <div className="card empty">{t.empty}</div>}
              </section>

              <section className="reveal">
                <div className="all-head">
                  <h2 className="sec" style={{ marginBottom: 0 }}>{t.allDeals}</h2>
                  <div className="filters">
                    {t.filters.map((o) => (
                      <button key={o.v} type="button" className={`fpill${o.v === filter ? ' on' : ''}`} onClick={() => setFilter(o.v)}>{o.l}</button>
                    ))}
                  </div>
                </div>
                {list.length ? list.map((d, i) => (
                  <div className="deal" key={i}>
                    <DealCore d={d} />
                    <div className="deal-bottom">
                      <span className="tag">{d.form === 'esim' ? 'eSIM' : 'SIM'}</span>
                      <button type="button" className="get" onClick={() => openDeal(d)}>{t.get}</button>
                    </div>
                  </div>
                )) : <div className="card empty">{t.empty}</div>}
              </section>
            </>
          )}

          {/* ── eSIM education + trust (always shown) ────────────────────── */}
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
          <div className="freepill">{t.poweredFree}</div>
          <div className="powered">Powered by <b>MOCA</b> ⚡ Market Intelligence</div>
          <div className="disclaim">{t.disclaim}</div>
        </footer>
      </div>
    </div>
  )
}
