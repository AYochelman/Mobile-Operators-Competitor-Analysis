import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { carrierLabel } from '../data/carrierLabels'
import { CARRIER_LOGOS, getCarrierColor } from '../components/moca/carrierMeta'
import { CARRIER_HOME_URLS } from '../data/carrierHomeUrls'
import { getCountriesForAbroadPlan } from '../data/abroadCountries'
import { getAppsForPlan } from '../data/abroadApps'
import BoltMark from '../components/BoltMark'
import { miniMarkup } from '../lib/miniMarkup'

/* ════════════════════════════════════════════════════════════════════════
   MOCA Mobile — public B2C domestic-plans comparison page (route: /mobile-deals)
   The domestic twin of /esim-deals: a free, no-login consumer tool comparing
   the official rate-card plans of all 10 Israeli carriers, plus their roaming
   packages and content services. Click-out goes straight to the carrier's own
   site (no affiliate programs exist for domestic carriers) with an anonymous
   carrier_click beacon. HE default + EN, mobile-first, all CSS scoped under
   #mobile-app. Data: /api/mobile/compare (normalized server-side) +
   /api/abroad-plans + /api/content-plans.
   ════════════════════════════════════════════════════════════════════════ */

const fmtNum = (n) => {
  if (n == null) return ''
  const r = Math.round(n * 100) / 100
  return Number.isInteger(r) ? String(r) : r.toFixed(2).replace(/0$/, '')
}

const T = {
  he: {
    dir: 'rtl', other: 'EN', otherLang: 'en',
    brandTag: 'השוואת חבילות סלולר',
    heroTitle: 'כמה עולה חבילת סלולר היום?',
    heroSub: 'השוואת מחירים חינמית של חבילות הסלולר בישראל, בלי הרשמה. כל 10 המפעילים, מחירים שנאספים מאתרי המפעילים פעמיים ביום.',
    updated: 'המחירים עודכנו',
    tabs: [
      { v: 'domestic', l: 'סלולר בישראל' },
      { v: 'roaming', l: 'חבילות לחו"ל' },
      { v: 'content', l: 'שירותים נוספים' },
    ],
    wizTitle: 'מתאימים לצרכים שלכם',
    qBudget: 'כמה לשלם בחודש?',
    budget: [
      { v: 'all', l: 'הכול' }, { v: 20, l: 'עד ₪20' },
      { v: 40, l: 'עד ₪40' }, { v: 60, l: 'עד ₪60' },
    ],
    qGb: 'כמה גלישה צריך?',
    gb: [
      { v: 'all', l: 'הכול' }, { v: '100', l: 'עד 100GB' },
      { v: '500', l: '100-500GB' }, { v: '500+', l: '500GB ומעלה' },
      { v: 'unl', l: 'ללא הגבלה' },
    ],
    qGen: 'איזו רשת?',
    gen: [
      { v: 'all', l: 'הכול' }, { v: '5g', l: '5G' }, { v: '5gp', l: '5G מתועדף' },
    ],
    qMore: 'הטבות וסינונים',
    facetChips: [
      { v: 'roaming', l: 'כולל גלישה בחו"ל' }, { v: 'esim', l: 'eSIM' },
      { v: 'apps', l: 'אפליקציות חינם' }, { v: 'kosher', l: 'מסלול כשר' },
    ],
    byCarrier: 'לפי מפעיל',
    sortLabel: 'מיון',
    sorts: [
      { v: 'price_asc', l: 'מהזול ליקר' }, { v: 'price_desc', l: 'מהיקר לזול' },
      { v: 'gb_desc', l: 'הכי הרבה גלישה' }, { v: 'ppgb', l: '₪ לכל GB' },
    ],
    topPicks: 'ההמלצות שלנו',
    badges: ['המשתלמת ביותר', 'הזולה ביותר', 'ללא הגבלה במחיר הטוב ביותר'],
    allPlans: 'כל החבילות',
    resultsN: '{n} חבילות מתאימות',
    perMonth: 'לחודש',
    unlimited: 'ללא הגבלה', noData: 'ללא גלישה', voiceOnly: 'מסלול שיחות בלבד',
    minutesU: 'דקות', daysU: 'ימים', dayU: 'יום', perGB: '/GB',
    promoLine: '{m} חודשים ראשונים ב-₪{p}',
    conditional: 'מחיר מותנה',
    conditionalHint: 'המחיר תלוי בתנאים (מספר קווים / מועדון) - הפרטים המלאים בכפתור "פרטים"',
    details: 'פרטים', close: 'סגירה', terms: 'עיקרי התוכנית (PDF)',
    goto: 'לאתר {carrier} ↗',
    empty: 'אין חבילות שמתאימות לסינון הזה - נסו לשנות אותו.',
    loading: 'טוענים את החבילות…',
    alertTitle: 'לקבל התראה כשמחיר יורד?',
    alertSub: 'נשלח התראה כשחבילת סלולר מוזלת. התראה אחת לכל מכשיר, בלי ספאם.',
    alertAll: 'כל המפעילים',
    alertBtn: 'הפעלת התראה', alertBusy: 'רק רגע…',
    alertOn: 'התראת ירידת מחיר פעילה',
    alertOnSub: 'נעדכן ברגע שחבילה מוזלת. אפשר לבטל בכל רגע.',
    alertOff: 'ביטול',
    alertDenied: 'ההתראות חסומות בדפדפן הזה - צריך לאפשר אותן בהגדרות האתר ולנסות שוב.',
    alertErr: 'לא הצלחנו להפעיל את ההתראה. נסו שוב בעוד רגע.',
    remBell: 'עדכונים על המסלול הזה',
    remTitle: 'עדכונים על המסלול הזה',
    remSub: 'השאירו מייל או וואטסאפ ונעדכן אתכם. בלי ספאם - בכל הודעה יש קישור הסרה.',
    remOpt1: 'חבילה דומה במחיר טוב יותר',
    remOpt1Sub: 'נשווה מול כל המפעילים ונעדכן כשמופיעה חבילה עם לפחות אותה גלישה במחיר נמוך יותר.',
    remOpt2: 'תזכורת לסיום תקופת המסלול',
    remOpt2Sub: 'נזכיר לפני שתקופת המסלול מסתיימת, כדי שתספיקו לשמר תנאים או להשוות.',
    remEndDate: 'תאריך סיום המסלול',
    remWhen: 'מתי להזכיר?',
    remDays: [
      { v: 3, l: '3 ימים לפני' }, { v: 7, l: 'שבוע לפני' },
      { v: 14, l: 'שבועיים לפני' }, { v: 30, l: 'חודש לפני' },
    ],
    remOffers: 'לצרף לתזכורת גם הצעות דומות מהשוק',
    remEmail: 'אימייל',
    remPhone: 'וואטסאפ (מספר נייד)',
    remContactHint: 'מספיק למלא אחד מהשניים.',
    remPaid: 'כמה אתם משלמים בפועל בחודש? (לא חובה)',
    remPaidHint: 'אם המחיר שלכם שונה מהמחירון - נשווה מול מה שאתם באמת משלמים.',
    remSubmit: 'הרשמה לעדכונים',
    remBusy: 'רק רגע…',
    remOkTitle: 'ההרשמה הושלמה!',
    remOkEmail: 'נעדכן אתכם במייל.',
    remOkWa: 'נעדכן אתכם בוואטסאפ.',
    remOkBoth: 'נעדכן אתכם במייל ובוואטסאפ.',
    remErr: 'ההרשמה לא הצליחה. בדקו את הפרטים ונסו שוב.',
    remErrContact: 'צריך למלא אימייל או מספר וואטסאפ.',
    remErrKinds: 'בחרו לפחות סוג עדכון אחד.',
    remErrDate: 'בחרו תאריך סיום עתידי.',
    remPrivacy: 'הפרטים משמשים רק לשליחת העדכונים שביקשתם, ולא מועברים לאף גורם אחר.',
    // Per-plan-type overrides for the reminder modal (roaming packages are
    // one-time buys; content dates are user-chosen, e.g. a free-trial end).
    remByType: {
      roaming: {
        opt1: 'חבילת חו"ל דומה במחיר טוב יותר',
        opt1Sub: 'נשווה מול חבילות החו"ל של כל המפעילים ונעדכן כשמופיעה חבילה עם לפחות אותה גלישה ואותם ימים במחיר נמוך יותר.',
        opt2: 'תזכורת לסיום החבילה',
        opt2Sub: 'נזכיר לפני שהחבילה מסתיימת - כדי שתספיקו לחדש או להשוות להמשך הנסיעה.',
        endDate: 'תאריך סיום החבילה',
        hidePaid: true,
      },
      content: {
        opt1: 'אותו שירות במחיר טוב יותר',
        opt1Sub: 'נעדכן כשאותו שירות מוצע אצל מפעיל אחר במחיר נמוך יותר.',
        opt2: 'תזכורת לתאריך שתבחרו',
        opt2Sub: 'למשל לפני סיום תקופת ניסיון חינם - כדי להחליט בזמן אם להמשיך או לבטל.',
        endDate: 'תאריך',
      },
    },
    roamTitle: 'חבילות חו"ל של המפעילים',
    roamSub: 'חבילות גלישה ושיחות לחו"ל על המספר הקיים - בלי להחליף סים.',
    roamSearch: 'חיפוש יעד (למשל יוון)…',
    countriesN: '{n} מדינות',
    appsN: 'גלישה חופשית ב-{n} אפליקציות',
    esimCross: 'טסים לחו"ל? כדאי להשוות גם eSIM גלובלי',
    esimCrossSub: 'חבילות eSIM ל-190+ יעדים מ-38 ספקים, לרוב זולות משמעותית מחבילות נדידה.',
    esimCrossBtn: 'להשוואת eSIM ↗',
    contentTitle: 'שירותים נוספים של המפעילים',
    contentSub: 'שירותי תוכן נלווים - סייבר, נורטון, שיר בהמתנה ועוד - והמחיר אצל כל מפעיל.',
    freeTrial: 'ניסיון חינם',
    trust: 'משווים את כל <b>10 מפעילי הסלולר בישראל</b><br>מתעדכן פעמיים ביום על ידי מנוע המודיעין של MOCA',
    disclaim: 'המחירים נאספים אוטומטית מאתרי המפעילים ומתעדכנים פעמיים ביום. המחיר המחייב הוא המחיר שמוצג באתר המפעיל.',
    poweredFree: 'חינם תמיד · ללא הרשמה',
    privacyL: 'מדיניות פרטיות', termsL: 'תנאי שימוש',
  },
  en: {
    dir: 'ltr', other: 'עב', otherLang: 'he',
    brandTag: 'Mobile Plan Compare',
    heroTitle: 'How much should a mobile plan cost?',
    heroSub: 'Free comparison of Israeli mobile plans, no sign-up. All 10 carriers, with prices collected from the carriers’ sites twice a day.',
    updated: 'Prices updated',
    tabs: [
      { v: 'domestic', l: 'Plans in Israel' },
      { v: 'roaming', l: 'Roaming abroad' },
      { v: 'content', l: 'Add-on services' },
    ],
    wizTitle: 'Matched to your needs',
    qBudget: 'Monthly budget?',
    budget: [
      { v: 'all', l: 'Any' }, { v: 20, l: 'Up to ₪20' },
      { v: 40, l: 'Up to ₪40' }, { v: 60, l: 'Up to ₪60' },
    ],
    qGb: 'How much data?',
    gb: [
      { v: 'all', l: 'Any' }, { v: '100', l: 'Up to 100GB' },
      { v: '500', l: '100-500GB' }, { v: '500+', l: '500GB+' },
      { v: 'unl', l: 'Unlimited' },
    ],
    qGen: 'Network?',
    gen: [
      { v: 'all', l: 'Any' }, { v: '5g', l: '5G' }, { v: '5gp', l: 'Priority 5G' },
    ],
    qMore: 'Perks & filters',
    facetChips: [
      { v: 'roaming', l: 'Roaming included' }, { v: 'esim', l: 'eSIM' },
      { v: 'apps', l: 'Free apps' }, { v: 'kosher', l: 'Kosher plan' },
    ],
    byCarrier: 'By carrier',
    sortLabel: 'Sort',
    sorts: [
      { v: 'price_asc', l: 'Cheapest first' }, { v: 'price_desc', l: 'Priciest first' },
      { v: 'gb_desc', l: 'Most data' }, { v: 'ppgb', l: '₪ per GB' },
    ],
    topPicks: 'Our picks',
    badges: ['BEST VALUE', 'CHEAPEST', 'BEST UNLIMITED'],
    allPlans: 'All plans',
    resultsN: '{n} matching plans',
    perMonth: 'per month',
    unlimited: 'Unlimited', noData: 'No data', voiceOnly: 'Voice-only plan',
    minutesU: 'minutes', daysU: 'days', dayU: 'day', perGB: '/GB',
    promoLine: 'First {m} months at ₪{p}',
    conditional: 'Conditional price',
    conditionalHint: 'Price depends on conditions (number of lines / club membership) - full details under "Details"',
    details: 'Details', close: 'Close', terms: 'Plan terms (PDF)',
    goto: 'Visit {carrier} ↗',
    empty: 'No plans match this filter - try changing it.',
    loading: 'Loading plans…',
    alertTitle: 'Get an alert when prices drop?',
    alertSub: 'We notify you when a mobile plan gets cheaper. One alert per device, no spam.',
    alertAll: 'All carriers',
    alertBtn: 'Enable alert', alertBusy: 'One sec…',
    alertOn: 'Price-drop alert is active',
    alertOnSub: 'We ping you the moment a plan gets cheaper. Cancel anytime.',
    alertOff: 'Cancel',
    alertDenied: 'Notifications are blocked in this browser - allow them in site settings and try again.',
    alertErr: 'Could not enable the alert. Try again in a moment.',
    remBell: 'Get updates on this plan',
    remTitle: 'Get updates on this plan',
    remSub: 'Leave an email or WhatsApp number and we will keep you posted. No spam - every message has an unsubscribe link.',
    remOpt1: 'A similar plan at a better price',
    remOpt1Sub: 'We compare all carriers and alert you when a plan with at least the same data shows up for less.',
    remOpt2: 'Reminder before your plan term ends',
    remOpt2Sub: 'We remind you before the term ends, so you have time to renegotiate or compare.',
    remEndDate: 'Plan term end date',
    remWhen: 'When should we remind you?',
    remDays: [
      { v: 3, l: '3 days before' }, { v: 7, l: 'A week before' },
      { v: 14, l: 'Two weeks before' }, { v: 30, l: 'A month before' },
    ],
    remOffers: 'Attach similar market offers to the reminder',
    remEmail: 'Email',
    remPhone: 'WhatsApp (mobile number)',
    remContactHint: 'Filling in just one of the two is enough.',
    remPaid: 'What do you actually pay per month? (optional)',
    remPaidHint: 'If your price differs from the rate card - we compare against what you really pay.',
    remSubmit: 'Sign up for updates',
    remBusy: 'One sec…',
    remOkTitle: 'You are signed up!',
    remOkEmail: 'We will update you by email.',
    remOkWa: 'We will update you on WhatsApp.',
    remOkBoth: 'We will update you by email and WhatsApp.',
    remErr: 'Signup failed. Check the details and try again.',
    remErrContact: 'Enter an email or a WhatsApp number.',
    remErrKinds: 'Pick at least one update type.',
    remErrDate: 'Pick a future end date.',
    remPrivacy: 'Your details are used only for the updates you asked for, and are never shared.',
    remByType: {
      roaming: {
        opt1: 'A similar roaming package at a better price',
        opt1Sub: 'We compare all carriers and alert you when a package with at least the same data and days shows up for less.',
        opt2: 'Reminder before the package ends',
        opt2Sub: 'We remind you before the package expires - so you can top up or compare for the rest of the trip.',
        endDate: 'Package end date',
        hidePaid: true,
      },
      content: {
        opt1: 'The same service at a better price',
        opt1Sub: 'We alert you when this service is offered by another carrier for less.',
        opt2: 'A reminder on a date you pick',
        opt2Sub: 'For example before a free trial ends - so you can decide in time whether to keep or cancel.',
        endDate: 'Date',
      },
    },
    roamTitle: 'Carrier roaming packages',
    roamSub: 'Data & calls abroad on your existing number - no SIM swap.',
    roamSearch: 'Search a destination (e.g. Greece)…',
    countriesN: '{n} countries',
    appsN: 'Free browsing in {n} apps',
    esimCross: 'Flying abroad? Compare global eSIMs too',
    esimCrossSub: 'eSIM plans for 190+ destinations from 38 providers, often far cheaper than roaming.',
    esimCrossBtn: 'Compare eSIMs ↗',
    contentTitle: 'Carrier add-on services',
    contentSub: 'Content add-ons - cyber protection, Norton, ringback tones and more - priced per carrier.',
    freeTrial: 'Free trial',
    trust: 'Comparing all <b>10 Israeli mobile carriers</b><br>Refreshed twice a day by MOCA market intelligence',
    disclaim: 'Prices are collected automatically from the carriers’ sites and refreshed twice a day. The binding price is the one shown on the carrier’s site.',
    poweredFree: 'Always free · no sign-up',
    privacyL: 'Privacy policy', termsL: 'Terms of use',
  },
}

const DATE_LOCALES = { en: 'en-GB', he: 'he-IL' }

const CSS = `
#mobile-app{--c1:#5c3317;--c2:#c9622f;--bg:#f9f4ee;--cream:#f5ede0;--ink:#3b1f0d;--sub:#8a6a4a;--muted:#a08468;--line:#e0cdb5;--card:#fff;--down:#4a7c3f;--warn:#b4472d;--r:20px;
  font-family:'Assistant',system-ui,-apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--ink);min-height:100dvh;-webkit-font-smoothing:antialiased}
#mobile-app *{box-sizing:border-box;margin:0;padding:0}
#mobile-app .page{max-width:560px;margin:0 auto;min-height:100dvh;display:flex;flex-direction:column}
#mobile-app .hero{position:relative;overflow:hidden;color:#fff;background:linear-gradient(150deg,var(--c1),color-mix(in srgb,var(--c1),#000 32%));padding:22px 22px 26px;border-radius:0 0 30px 30px}
#mobile-app .hero::before{content:"";position:absolute;inset:auto -70px -120px auto;width:260px;height:260px;border-radius:50%;background:color-mix(in srgb,var(--c2),transparent 70%)}
#mobile-app .hero::after{content:"";position:absolute;top:-90px;inset-inline-start:-60px;width:220px;height:220px;border-radius:50%;background:color-mix(in srgb,#fff,transparent 90%)}
#mobile-app .hero>*{position:relative;z-index:1}
#mobile-app .hero-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:22px}
#mobile-app .brand{display:flex;align-items:center;gap:10px}
#mobile-app .bolt{width:40px;height:40px;border-radius:12px;background:#fff;color:var(--c1);display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 4px 14px rgba(0,0,0,.25)}
#mobile-app .brand-name{font-weight:800;font-size:17px;line-height:1;letter-spacing:.3px}
#mobile-app .brand-tag{font-size:10px;letter-spacing:2.2px;opacity:.78;font-weight:600;margin-top:3px}
#mobile-app .lang{border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.12);color:#fff;border-radius:999px;padding:6px 14px;font:inherit;font-weight:700;font-size:13px;cursor:pointer}
#mobile-app .hero h1{font-size:25px;font-weight:800;line-height:1.2;margin-bottom:9px}
#mobile-app .hero p{font-size:14.5px;line-height:1.5;opacity:.9;max-width:42ch}
#mobile-app .updated{display:inline-flex;align-items:center;gap:7px;margin-top:14px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18);padding:6px 12px;border-radius:999px;font-size:12px;font-weight:600}
#mobile-app .dot{width:7px;height:7px;border-radius:50%;background:#7fd99b;box-shadow:0 0 0 3px rgba(127,217,155,.25);animation:mpulse 2s infinite}
@keyframes mpulse{50%{box-shadow:0 0 0 6px rgba(127,217,155,.08)}}
#mobile-app main{padding:14px 16px 8px;display:flex;flex-direction:column;gap:18px;flex:1}
#mobile-app .card{background:var(--card);border-radius:var(--r);padding:18px;box-shadow:0 6px 24px rgba(70,45,20,.07)}
#mobile-app .sec{font-size:17px;font-weight:700;margin-bottom:12px}
#mobile-app .tabs{display:flex;gap:8px;margin-top:6px}
#mobile-app .tab{flex:1;border:1.5px solid var(--line);background:var(--card);border-radius:14px;cursor:pointer;padding:11px 8px;font:inherit;font-size:13.5px;font-weight:700;color:var(--sub);box-shadow:0 6px 24px rgba(70,45,20,.07);transition:all .15s}
#mobile-app .tab.on{background:var(--c1);border-color:var(--c1);color:#fff}
#mobile-app .wizard h2{font-size:16.5px;font-weight:800;margin-bottom:4px}
#mobile-app .q{font-size:13px;font-weight:700;color:var(--c1);margin:14px 0 8px}
#mobile-app .chips{display:flex;gap:8px;flex-wrap:wrap}
#mobile-app .chip{border:1.5px solid var(--line);background:rgba(255,255,255,.55);border-radius:14px;cursor:pointer;padding:9px 13px;font:inherit;font-size:13.5px;font-weight:700;color:var(--ink);transition:all .15s;flex:1 1 auto;text-align:center;min-width:64px}
#mobile-app .chip.on{background:var(--c1);border-color:var(--c1);color:#fff}
#mobile-app .fchip{border:1.5px solid var(--line);background:#fff;border-radius:999px;cursor:pointer;padding:7px 13px;font:inherit;font-size:12.5px;font-weight:700;color:var(--sub);transition:all .15s}
#mobile-app .fchip.on{background:color-mix(in srgb,var(--c2),#fff 82%);border-color:var(--c2);color:color-mix(in srgb,var(--c2),#000 30%)}
#mobile-app .carrier-row{display:flex;gap:7px;flex-wrap:wrap}
#mobile-app .cpick{display:inline-flex;align-items:center;gap:6px;border:1.5px solid var(--line);background:#fff;border-radius:999px;cursor:pointer;padding:5px 11px 5px 7px;font:inherit;font-size:12px;font-weight:700;color:var(--ink);transition:all .15s}
#mobile-app[dir=rtl] .cpick{padding:5px 7px 5px 11px}
#mobile-app .cpick img{width:20px;height:20px;object-fit:contain;border-radius:6px;background:#fff}
#mobile-app .cpick.on{border-color:var(--c1);background:var(--cream);box-shadow:inset 0 0 0 1px var(--c1)}
#mobile-app .list-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;flex-wrap:wrap}
#mobile-app .count-pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;color:var(--c1);background:color-mix(in srgb,var(--c1),#fff 90%);border:1px solid color-mix(in srgb,var(--c1),#fff 78%);padding:5px 11px;border-radius:999px}
#mobile-app .sort-select{position:relative}
#mobile-app .sort-select select{appearance:none;-webkit-appearance:none;border:1.5px solid var(--line);background:#fff;color:var(--c1);border-radius:999px;padding-block:6px;padding-inline-start:13px;padding-inline-end:30px;font:inherit;font-size:12.5px;font-weight:700;cursor:pointer;outline:none;max-width:190px;text-overflow:ellipsis}
#mobile-app .sort-select .chev{position:absolute;inset-inline-end:11px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--muted)}
#mobile-app .pick{background:var(--card);border-radius:var(--r);padding:16px;margin-bottom:10px;box-shadow:0 6px 24px rgba(70,45,20,.07);border:1.5px solid transparent}
#mobile-app .pick.first{border-color:var(--c2);box-shadow:0 10px 30px color-mix(in srgb,var(--c2),transparent 74%)}
#mobile-app .badge{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.6px;padding:4px 10px;border-radius:999px;margin-bottom:10px;margin-inline-end:6px}
#mobile-app .badge.b1{background:color-mix(in srgb,var(--c2),#fff 75%);color:color-mix(in srgb,var(--c2),#000 35%)}
#mobile-app .badge.b2{background:#e3f3e9;color:#246b43}
#mobile-app .badge.b3{background:#efe7f7;color:#6b3fa0}
#mobile-app .deal{background:var(--card);border-radius:16px;padding:13px 14px;margin-bottom:8px;box-shadow:0 3px 12px rgba(70,45,20,.05)}
#mobile-app .deal-row{display:flex;align-items:center;gap:12px}
#mobile-app .pchip{width:42px;height:42px;border-radius:13px;flex:none;color:#fff;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;letter-spacing:.4px}
#mobile-app .pchip.logo{background:#fff;border:1.5px solid;padding:5px}
#mobile-app .pchip.logo img{width:100%;height:100%;object-fit:contain;display:block}
#mobile-app .deal-info{flex:1;min-width:0}
#mobile-app .deal-provider{font-weight:800;font-size:14.5px}
#mobile-app .deal-name{font-size:12.5px;color:var(--sub);font-weight:700;margin-top:1px}
#mobile-app .deal-meta{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:12.5px;color:var(--sub);font-weight:600;margin-top:2px;line-height:1.5}
#mobile-app .deal-meta .deal-sep{opacity:.45}
#mobile-app .deal-price{text-align:end}
#mobile-app[dir=rtl] .deal-price{text-align:start}
#mobile-app .price-main{font-weight:800;font-size:18px;white-space:nowrap}
#mobile-app .price-sub{font-size:11px;color:var(--sub);font-weight:600;white-space:nowrap}
#mobile-app .price-promo{font-size:11px;color:var(--down);font-weight:700;white-space:nowrap}
#mobile-app .tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
#mobile-app .tag{font-size:10.5px;font-weight:700;background:var(--bg);border:1px solid var(--line);color:var(--sub);padding:3px 9px;border-radius:999px}
#mobile-app .tag.warn{background:color-mix(in srgb,var(--warn),#fff 90%);border-color:color-mix(in srgb,var(--warn),#fff 55%);color:var(--warn)}
#mobile-app .deal-bottom{display:flex;align-items:center;gap:8px;margin-top:11px}
#mobile-app .get{flex:1;border:0;border-radius:11px;cursor:pointer;background:var(--c1);color:#fff;font:inherit;font-weight:800;font-size:13px;padding:10px 15px;transition:transform .12s,opacity .12s}
#mobile-app .get:hover{opacity:.94}
#mobile-app .get:active{transform:scale(.985);opacity:.9}
#mobile-app .ghost{border:1.5px solid var(--line);background:#fff;color:var(--c1);border-radius:11px;cursor:pointer;font:inherit;font-weight:700;font-size:13px;padding:9px 14px;transition:all .15s}
#mobile-app .ghost:hover{border-color:var(--c2)}
#mobile-app .empty{padding:26px;text-align:center;color:var(--sub);font-weight:600;font-size:13.5px}
#mobile-app .search-wrap{position:relative;margin-bottom:12px}
#mobile-app .search{width:100%;border:1.6px solid var(--line);background:var(--bg);border-radius:14px;padding:12px 44px 12px 14px;font:inherit;font-size:15px;font-weight:600;color:var(--ink);outline:none}
#mobile-app[dir=ltr] .search{padding:12px 14px 12px 44px}
#mobile-app .search:focus{border-color:var(--c2);box-shadow:0 0 0 3px color-mix(in srgb,var(--c2),transparent 82%)}
#mobile-app .search-ic{position:absolute;inset-inline-end:14px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none}
#mobile-app .cross{display:flex;align-items:center;gap:12px;background:linear-gradient(135deg,color-mix(in srgb,var(--c2),#fff 88%),#fff);border:1.5px solid color-mix(in srgb,var(--c2),#fff 60%)}
#mobile-app .cross .alert-tx b{font-size:14px}
#mobile-app .cross-btn{border:0;border-radius:12px;background:var(--c2);color:#fff;font:inherit;font-weight:800;font-size:12.5px;padding:10px 14px;cursor:pointer;white-space:nowrap}
#mobile-app .svc-row{display:flex;align-items:center;gap:11px;padding:10px 0;border-bottom:1px dashed var(--line)}
#mobile-app .svc-row:last-child{border-bottom:0}
#mobile-app .svc-row .pchip{width:36px;height:36px;border-radius:11px}
#mobile-app .svc-meta{flex:1;min-width:0}
#mobile-app .svc-carrier{font-weight:800;font-size:13.5px}
#mobile-app .svc-note{font-size:11.5px;color:var(--sub);font-weight:600;line-height:1.4;margin-top:1px}
#mobile-app .svc-price{font-weight:800;font-size:14px;white-space:nowrap}
#mobile-app .trial{display:inline-block;font-size:10px;font-weight:800;background:#e3f3e9;color:#246b43;border-radius:999px;padding:2px 8px;margin-inline-start:6px}
#mobile-app .alertcard{display:flex;align-items:center;gap:12px;position:relative;flex-wrap:wrap}
#mobile-app .alert-ic{width:42px;height:42px;border-radius:13px;background:color-mix(in srgb,var(--c2),#fff 82%);color:var(--c2);display:flex;align-items:center;justify-content:center;flex:none}
#mobile-app .alert-ic.ok{background:#e3f3e9;color:#246b43}
#mobile-app .alert-tx{flex:1;min-width:0}
#mobile-app .alert-tx b{display:block;font-size:14px;line-height:1.35}
#mobile-app .alert-tx span{display:block;font-size:12.5px;color:var(--sub);line-height:1.45;margin-top:2px}
#mobile-app .alert-btn{border:0;border-radius:12px;background:var(--c1);color:#fff;font:inherit;font-weight:800;font-size:12.5px;padding:10px 14px;cursor:pointer;white-space:nowrap;transition:opacity .12s}
#mobile-app .alert-btn:disabled{opacity:.6;cursor:default}
#mobile-app .alert-off{border:1.5px solid var(--line);background:#fff;color:var(--sub);border-radius:12px;font:inherit;font-weight:700;font-size:12px;padding:8px 12px;cursor:pointer;white-space:nowrap}
#mobile-app .alert-select{border:1.5px solid var(--line);background:#fff;color:var(--c1);border-radius:12px;font:inherit;font-weight:700;font-size:12.5px;padding:8px 10px;cursor:pointer;outline:none;max-width:150px}
#mobile-app .modal-ov{position:fixed;inset:0;background:rgba(40,25,10,.45);z-index:60;display:flex;align-items:flex-end;justify-content:center;animation:mfade .2s ease}
@media(min-width:560px){#mobile-app .modal-ov{align-items:center}}
#mobile-app .modal{background:var(--card);border-radius:22px 22px 0 0;width:100%;max-width:560px;max-height:86dvh;overflow-y:auto;padding:20px;position:relative;animation:mup .25s ease}
@media(min-width:560px){#mobile-app .modal{border-radius:22px}}
@keyframes mup{from{transform:translateY(24px);opacity:0}}
@keyframes mfade{from{opacity:0}}
#mobile-app .modal-x{position:absolute;top:12px;inset-inline-end:14px;border:0;background:var(--cream);color:var(--sub);width:30px;height:30px;border-radius:50%;font-size:13px;cursor:pointer}
#mobile-app .modal-head{display:flex;align-items:center;gap:12px;margin-bottom:10px;padding-inline-end:36px}
#mobile-app .modal-carrier{font-weight:800;font-size:15px}
#mobile-app .modal-name{font-size:13px;color:var(--sub);font-weight:700}
#mobile-app .modal-price{font-weight:800;font-size:22px;margin-bottom:12px}
#mobile-app .modal-list{list-style:none;display:flex;flex-direction:column;gap:7px;margin-bottom:12px}
#mobile-app .modal-list li{font-size:13px;line-height:1.5;padding-inline-start:18px;position:relative;color:var(--ink)}
#mobile-app .modal-list li::before{content:"✓";position:absolute;inset-inline-start:0;color:var(--down);font-weight:800}
#mobile-app .modal-info{background:var(--bg);border:1px solid var(--line);border-radius:14px;padding:12px 14px;font-size:12.5px;line-height:1.65;color:var(--sub);margin-bottom:12px;display:flex;flex-direction:column;gap:4px}
#mobile-app .modal-info a{color:var(--c1);font-weight:700}
#mobile-app .modal-terms{display:inline-block;font-size:13px;font-weight:700;color:var(--c1);text-decoration:underline;margin-bottom:4px}
#mobile-app .trust{text-align:center;font-size:12px;color:var(--sub);font-weight:600;line-height:1.6;padding:4px 18px}
#mobile-app .trust b{color:var(--ink)}
#mobile-app footer{padding:18px 16px 30px;text-align:center}
#mobile-app .powered{font-size:12.5px;color:var(--sub);font-weight:600}
#mobile-app .powered b{color:var(--ink)}
#mobile-app .freepill{display:inline-block;margin-bottom:8px;font-size:11.5px;font-weight:800;letter-spacing:.4px;color:var(--down);background:#e3f3e9;border-radius:999px;padding:4px 12px}
#mobile-app .disclaim{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.5;max-width:48ch;margin-inline:auto}
#mobile-app .splash{min-height:50vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;color:var(--c1);text-align:center;padding:30px}
#mobile-app .spin{width:34px;height:34px;border-radius:50%;border:3px solid color-mix(in srgb,var(--c1),transparent 78%);border-top-color:var(--c1);animation:mspin .8s linear infinite}
@keyframes mspin{to{transform:rotate(360deg)}}
#mobile-app .reveal{animation:mreveal .35s ease both}
@keyframes mreveal{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
#mobile-app .bell-btn{display:inline-flex;align-items:center;justify-content:center;border:1.5px solid var(--line);background:#fff;color:var(--c1);border-radius:11px;cursor:pointer;padding:9px 11px;transition:all .15s;flex:none}
#mobile-app .bell-btn:hover{border-color:var(--c2)}
#mobile-app .bell-btn.sm{padding:6px 8px;border-radius:9px}
#mobile-app .bell-btn.sm svg{width:15px;height:15px}
#mobile-app .rem-opt{border:1.5px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:10px;cursor:pointer;transition:all .15s}
#mobile-app .rem-opt.on{border-color:var(--c1);background:var(--cream)}
#mobile-app .rem-opt-head{display:flex;gap:10px;align-items:flex-start;font-weight:800;font-size:14px;line-height:1.35}
#mobile-app .rem-opt-head input{margin-top:2px;accent-color:var(--c1);width:16px;height:16px;flex:none}
#mobile-app .rem-opt-sub{font-size:12.5px;font-weight:600;color:var(--sub);margin-top:4px;line-height:1.5;padding-inline-start:26px}
#mobile-app .rem-ext{margin-top:10px;padding-inline-start:26px;display:flex;flex-direction:column;gap:9px}
#mobile-app .rem-row{display:flex;gap:8px;flex-wrap:wrap}
#mobile-app .rem-field{display:flex;flex-direction:column;gap:4px;flex:1;min-width:145px}
#mobile-app .rem-field label{font-size:12px;font-weight:700;color:var(--c1)}
#mobile-app .rem-input{width:100%;border:1.6px solid var(--line);background:var(--bg);border-radius:12px;padding:10px 12px;font:inherit;font-size:14px;font-weight:600;color:var(--ink);outline:none}
#mobile-app .rem-input:focus{border-color:var(--c2);box-shadow:0 0 0 3px color-mix(in srgb,var(--c2),transparent 82%)}
#mobile-app .rem-check{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:700;cursor:pointer}
#mobile-app .rem-check input{accent-color:var(--c1);width:15px;height:15px;flex:none}
#mobile-app .rem-hint{font-size:11.5px;color:var(--muted);font-weight:600;margin-top:4px}
#mobile-app .rem-err{color:var(--warn);font-size:12.5px;font-weight:700;margin-top:8px}
#mobile-app .rem-submit{width:100%;border:0;border-radius:12px;cursor:pointer;background:var(--c1);color:#fff;font:inherit;font-weight:800;font-size:14px;padding:12px 16px;margin-top:12px;transition:opacity .12s}
#mobile-app .rem-submit:disabled{opacity:.6;cursor:default}
#mobile-app .rem-privacy{font-size:11px;color:var(--muted);font-weight:600;margin-top:10px;line-height:1.5;text-align:center}
#mobile-app .rem-ok{text-align:center;padding:14px 4px 4px}
#mobile-app .rem-ok-ic{width:52px;height:52px;border-radius:50%;background:#e3f3e9;color:#246b43;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;font-size:24px}
#mobile-app .rem-ok b{display:block;font-size:16px;margin-bottom:5px}
#mobile-app .rem-ok span{font-size:13px;color:var(--sub);font-weight:600}
`

// Read a URL/query param at first render (SPA-only page, so window is defined).
function _initParam(key) {
  try { return new URLSearchParams(window.location.search).get(key) } catch { return null }
}

const PUSH_SUPPORTED = typeof window !== 'undefined' &&
  'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

function urlB64ToUint8Array(s) {
  const pad = '='.repeat((4 - (s.length % 4)) % 4)
  const b64 = (s + pad).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(b64)
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)))
}

const BellIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
  </svg>
)

// Carrier tile: real logo from public/logos (CARRIER_LOGOS) on a white chip with
// a brand-colored ring; falls back to a colored 2-letter monogram.
function CarrierLogo({ carrier, size }) {
  const [err, setErr] = useState(false)
  const src = CARRIER_LOGOS[carrier]
  const color = getCarrierColor(carrier)
  const style = size ? { width: size, height: size } : undefined
  if (src && !err) {
    return (
      <div className="pchip logo" style={{ borderColor: color, ...style }}>
        <img src={src} alt="" loading="lazy" onError={() => setErr(true)} />
      </div>
    )
  }
  return <div className="pchip" style={{ background: color, ...style }}>{(carrierLabel(carrier) || carrier).slice(0, 2)}</div>
}

// GB headline for a normalized feed plan (server already folded 10000→unlimited
// and flagged the voice-only kosher rows).
function gbLabel(p, t) {
  if (p.voice_only) return t.noData
  if (p.unlimited || p.data_gb == null) return t.unlimited
  if (p.data_gb < 1) return `${Math.round(p.data_gb * 1024)}MB`
  return `${(+p.data_gb).toLocaleString()}GB`
}

// "מחיר יורד? נעדכן" — one domestic alert per device, keyed carrier-or-all.
// Re-subscribing MOVES the alert (server UPSERTs by endpoint).
function PriceAlertCard({ t, lang, meta, carriers }) {
  const [status, setStatus] = useState('idle') // idle | busy | on | denied | error
  const [carrier, setCarrier] = useState('all')
  useEffect(() => {
    let alive = true
    if (!PUSH_SUPPORTED) return undefined
    try {
      if (localStorage.getItem('mobile_push_carrier') && Notification.permission === 'granted') {
        navigator.serviceWorker.getRegistration()
          .then((reg) => reg && reg.pushManager.getSubscription())
          .then((sub) => { if (alive && sub) setStatus('on') })
          .catch(() => {})
      }
    } catch { /* ignore */ }
    return () => { alive = false }
  }, [])

  if (!PUSH_SUPPORTED) return null

  const subscribe = async () => {
    setStatus('busy')
    try {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') { setStatus('denied'); return }
      const reg = await navigator.serviceWorker.getRegistration()
      if (!reg) throw new Error('no service worker')
      let sub = await reg.pushManager.getSubscription()
      if (!sub) {
        const { publicKey } = await api.getVapidKey()
        if (!publicKey) throw new Error('no vapid key')
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlB64ToUint8Array(publicKey),
        })
      }
      await api.mobilePushSubscribe(sub.toJSON(), carrier, lang, meta)
      try { localStorage.setItem('mobile_push_carrier', carrier) } catch { /* ignore */ }
      setStatus('on')
    } catch { setStatus('error') }
  }

  const unsubscribe = async () => {
    setStatus('busy')
    try {
      const reg = await navigator.serviceWorker.getRegistration()
      const sub = reg && await reg.pushManager.getSubscription()
      if (sub) {
        await api.mobilePushUnsubscribe(sub.endpoint).catch(() => {})
        await sub.unsubscribe().catch(() => {})
      }
    } catch { /* ignore */ }
    try { localStorage.removeItem('mobile_push_carrier') } catch { /* ignore */ }
    setStatus('idle')
  }

  if (status === 'on') {
    return (
      <section className="card alertcard reveal">
        <div className="alert-ic ok"><BellIcon /></div>
        <div className="alert-tx">
          <b>{t.alertOn}</b>
          <span>{t.alertOnSub}</span>
        </div>
        <button type="button" className="alert-off" onClick={unsubscribe}>{t.alertOff}</button>
      </section>
    )
  }
  return (
    <section className="card alertcard reveal">
      <div className="alert-ic"><BellIcon /></div>
      <div className="alert-tx">
        <b>{t.alertTitle}</b>
        <span>{status === 'denied' ? t.alertDenied : status === 'error' ? t.alertErr : t.alertSub}</span>
      </div>
      <select className="alert-select" value={carrier} onChange={(e) => setCarrier(e.target.value)} aria-label={t.byCarrier}>
        <option value="all">{t.alertAll}</option>
        {(carriers || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <button type="button" className="alert-btn" onClick={subscribe} disabled={status === 'busy'}>
        {status === 'busy' ? t.alertBusy : t.alertBtn}
      </button>
    </section>
  )
}

// Full-details bottom sheet: every benefit bullet + the __info__ terms blob
// (lines shaped "label|https://…" become links, mirroring PlanCard) + the
// terms-PDF link. Works for both domestic (normalized feed) and roaming rows.
function DetailsModal({ plan, t, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  if (!plan) return null
  const infoLines = (plan.info || '').split('\n').map((l) => l.trim()).filter(Boolean)
  return (
    <div className="modal-ov" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-x" onClick={onClose} aria-label={t.close}>✕</button>
        <div className="modal-head">
          <CarrierLogo carrier={plan.carrier} />
          <div>
            <div className="modal-carrier"><bdi>{carrierLabel(plan.carrier)}</bdi></div>
            <div className="modal-name"><bdi>{plan.plan_name}</bdi></div>
          </div>
        </div>
        {plan.price != null && <div className="modal-price" dir="ltr">₪{fmtNum(plan.price)}</div>}
        {(plan.extras || []).length > 0 && (
          <ul className="modal-list">
            {plan.extras.map((e, i) => <li key={i}><bdi>{e}</bdi></li>)}
          </ul>
        )}
        {infoLines.length > 0 && (
          <div className="modal-info">
            {infoLines.map((ln, i) => {
              const m = ln.match(/^(.*)\|(https?:\/\/\S+)\s*$/)
              return m
                ? <div key={i}><a href={m[2]} target="_blank" rel="noopener noreferrer">{(m[1] || m[2]).trim()}</a></div>
                : <div key={i}>{ln}</div>
            })}
          </div>
        )}
        {plan.terms_url && (
          <a className="modal-terms" href={plan.terms_url} target="_blank" rel="noopener noreferrer">{t.terms}</a>
        )}
      </div>
    </div>
  )
}

// Email/WhatsApp reminder signup for one plan: (1) a similar plan at a better
// price elsewhere, (2) an end-date reminder with optional retention offers.
// planType 'domestic' | 'roaming' | 'content' switches the copy (t.remByType)
// and what the server validates against; for 'content', plan_name carries the
// service name. Server snapshots price/data from the live data of the type;
// contact details go only to /api/mobile/reminders (see privacy policy).
function ReminderModal({ plan, planType = 'domestic', t, lang, meta, onClose }) {
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [paid, setPaid] = useState('')
  const [wantDeal, setWantDeal] = useState(true)
  const [wantEnd, setWantEnd] = useState(false)
  const [endDate, setEndDate] = useState('')
  const [daysBefore, setDaysBefore] = useState(7)
  const [offers, setOffers] = useState(true)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null) // channel string after success
  const [err, setErr] = useState(null)

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const todayISO = new Date().toISOString().slice(0, 10)

  // Per-type copy overrides; anything not overridden falls back to the
  // domestic strings.
  const ov = t.remByType?.[planType] || {}
  const tx = {
    opt1: ov.opt1 || t.remOpt1, opt1Sub: ov.opt1Sub || t.remOpt1Sub,
    opt2: ov.opt2 || t.remOpt2, opt2Sub: ov.opt2Sub || t.remOpt2Sub,
    endDate: ov.endDate || t.remEndDate,
  }
  const showPaid = !ov.hidePaid

  const submit = async (e) => {
    e.preventDefault()
    const kinds = [...(wantDeal ? ['better_deal'] : []), ...(wantEnd ? ['plan_end'] : [])]
    const em = email.trim(), ph = phone.trim()
    if (!kinds.length) { setErr(t.remErrKinds); return }
    if (!em && !ph) { setErr(t.remErrContact); return }
    if (wantEnd && (!endDate || endDate < todayISO)) { setErr(t.remErrDate); return }
    setErr(null)
    setBusy(true)
    try {
      const paidNum = Number(paid)
      await api.mobileReminderSubscribe({
        email: em || undefined,
        phone: ph || undefined,
        paid_price: showPaid && paid && Number.isFinite(paidNum) && paidNum > 0 ? paidNum : undefined,
        kinds,
        plan_type: planType,
        carrier: plan.carrier,
        plan_name: plan.plan_name,
        end_date: wantEnd ? endDate : undefined,
        remind_days_before: wantEnd ? daysBefore : undefined,
        include_offers: wantEnd ? offers : undefined,
        lang,
        ...meta,
      })
      setDone(em && ph ? t.remOkBoth : em ? t.remOkEmail : t.remOkWa)
    } catch {
      setErr(t.remErr)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-ov" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-x" onClick={onClose} aria-label={t.close}>✕</button>
        <div className="modal-head">
          <CarrierLogo carrier={plan.carrier} />
          <div>
            <div className="modal-carrier">{t.remTitle}</div>
            <div className="modal-name"><bdi>{carrierLabel(plan.carrier)} - {plan.plan_name}</bdi></div>
          </div>
        </div>
        {done ? (
          <div className="rem-ok reveal">
            <div className="rem-ok-ic">✓</div>
            <b>{t.remOkTitle}</b>
            <span>{done}</span>
          </div>
        ) : (
          <form onSubmit={submit} noValidate>
            <p style={{ fontSize: 13, color: 'var(--sub)', fontWeight: 600, lineHeight: 1.5, marginBottom: 14 }}>{t.remSub}</p>

            <div className={`rem-opt${wantDeal ? ' on' : ''}`} onClick={() => setWantDeal(!wantDeal)}>
              <div className="rem-opt-head">
                <input type="checkbox" checked={wantDeal} onChange={(e) => setWantDeal(e.target.checked)}
                  onClick={(e) => e.stopPropagation()} />
                <span>{tx.opt1}</span>
              </div>
              <div className="rem-opt-sub">{tx.opt1Sub}</div>
            </div>

            <div className={`rem-opt${wantEnd ? ' on' : ''}`} onClick={() => setWantEnd(!wantEnd)}>
              <div className="rem-opt-head">
                <input type="checkbox" checked={wantEnd} onChange={(e) => setWantEnd(e.target.checked)}
                  onClick={(e) => e.stopPropagation()} />
                <span>{tx.opt2}</span>
              </div>
              <div className="rem-opt-sub">{tx.opt2Sub}</div>
              {wantEnd && (
                <div className="rem-ext" onClick={(e) => e.stopPropagation()}>
                  <div className="rem-row">
                    <div className="rem-field">
                      <label htmlFor="rem-end">{tx.endDate}</label>
                      <input id="rem-end" className="rem-input" type="date" min={todayISO}
                        value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                    </div>
                    <div className="rem-field">
                      <label htmlFor="rem-days">{t.remWhen}</label>
                      <select id="rem-days" className="rem-input" value={daysBefore}
                        onChange={(e) => setDaysBefore(Number(e.target.value))}>
                        {t.remDays.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                      </select>
                    </div>
                  </div>
                  <label className="rem-check">
                    <input type="checkbox" checked={offers} onChange={(e) => setOffers(e.target.checked)} />
                    <span>{t.remOffers}</span>
                  </label>
                </div>
              )}
            </div>

            <div className="rem-row" style={{ marginTop: 14 }}>
              <div className="rem-field">
                <label htmlFor="rem-email">{t.remEmail}</label>
                <input id="rem-email" className="rem-input" type="email" dir="ltr" value={email}
                  placeholder="you@mail.com" autoComplete="email"
                  onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="rem-field">
                <label htmlFor="rem-phone">{t.remPhone}</label>
                <input id="rem-phone" className="rem-input" type="tel" dir="ltr" value={phone}
                  placeholder="050-1234567" autoComplete="tel"
                  onChange={(e) => setPhone(e.target.value)} />
              </div>
            </div>
            <div className="rem-hint">{t.remContactHint}</div>

            {showPaid && (
              <div className="rem-field" style={{ marginTop: 12 }}>
                <label htmlFor="rem-paid">{t.remPaid}</label>
                <input id="rem-paid" className="rem-input" type="number" dir="ltr" inputMode="decimal"
                  min="5" max="500" step="0.1" value={paid} placeholder="₪"
                  onChange={(e) => setPaid(e.target.value)} />
                <div className="rem-hint" style={{ marginTop: 2 }}>{t.remPaidHint}</div>
              </div>
            )}

            {err && <div className="rem-err" role="alert">{err}</div>}
            <button type="submit" className="rem-submit" disabled={busy}>
              {busy ? t.remBusy : t.remSubmit}
            </button>
            <div className="rem-privacy">
              {t.remPrivacy}{' '}
              <a href={`/privacy${lang === 'en' ? '?lang=en' : ''}`} target="_blank" rel="noopener noreferrer"
                style={{ color: 'var(--c1)' }}>{t.privacyL}</a>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

const TABS = ['domestic', 'roaming', 'content']

export default function MobileComparePage() {
  const [params, setParams] = useSearchParams()
  // Language shares the consumer-pages preference key (esim_lang) so the eSIM
  // page, the legal pages and this page stay in one language across visits.
  const [lang, setLang] = useState(() => {
    const wanted = _initParam('lang')
    if (['he', 'en'].includes(wanted)) return wanted
    try { const s = localStorage.getItem('esim_lang'); if (['he', 'en'].includes(s)) return s } catch { /* ignore */ }
    return 'he'
  })
  const [tab, setTab] = useState(() => (TABS.includes(_initParam('tab')) ? _initParam('tab') : 'domestic'))
  const [data, setData] = useState(null)          // /api/mobile/compare payload
  const [abroad, setAbroad] = useState(null)      // roaming rows (normalized), null = not fetched
  const [content, setContent] = useState(null)    // content-services rows
  const [detail, setDetail] = useState(null)      // plan in the details modal
  const [remindFor, setRemindFor] = useState(null) // { plan, type } in the reminder-signup modal

  // Domestic filters
  const [budget, setBudget] = useState('all')
  const [gbTier, setGbTier] = useState('all')
  const [gen, setGen] = useState('all')
  const [facetsOn, setFacetsOn] = useState(() => new Set())
  const [selCarriers, setSelCarriers] = useState(() => new Set())
  const [sort, setSort] = useState('price_asc')
  // Roaming filters
  const [roamQ, setRoamQ] = useState('')
  const [roamCarrier, setRoamCarrier] = useState('all')

  // Anonymous analytics: per-session token + acquisition source + campaign tag.
  const [campaign] = useState(() => _initParam('campaign') || _initParam('utm_campaign') || _initParam('utm_source') || '')
  const [sid] = useState(() => {
    try {
      let s = sessionStorage.getItem('mobile_sid')
      if (!s) { s = Math.random().toString(36).slice(2) + Date.now().toString(36); sessionStorage.setItem('mobile_sid', s) }
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

  // Main domestic feed, once on mount.
  useEffect(() => {
    let alive = true
    api.getMobileCompare()
      .then((d) => { if (alive) setData(d && Array.isArray(d.plans) ? d : { plans: [], carriers: [] }) })
      .catch(() => { if (alive) setData({ plans: [], carriers: [] }) })
    return () => { alive = false }
  }, [])

  // Roaming rows arrive raw from /api/abroad-plans — extract the __info__ blob
  // into .info (like the server does for domestic) so DetailsModal is uniform.
  useEffect(() => {
    if (tab !== 'roaming' || abroad !== null) return
    let alive = true
    api.getAbroadPlans()
      .then((rows) => {
        if (!alive) return
        setAbroad((Array.isArray(rows) ? rows : []).map((p) => {
          let info = null
          const vis = []
          for (const e of p.extras || []) {
            if (typeof e === 'string' && e.startsWith('__info__|')) info = e.split('|').slice(1).join('|')
            else vis.push(e)
          }
          return { ...p, extras: vis, info, terms_url: p.terms_url || p.url || null }
        }))
      })
      .catch(() => { if (alive) setAbroad([]) })
    return () => { alive = false }
  }, [tab, abroad])

  useEffect(() => {
    if (tab !== 'content' || content !== null) return
    let alive = true
    api.getContentPlans()
      .then((rows) => { if (alive) setContent(Array.isArray(rows) ? rows : []) })
      .catch(() => { if (alive) setContent([]) })
    return () => { alive = false }
  }, [tab, content])

  // Anonymous page-view beacon, once per mount (ref-guarded against StrictMode).
  useEffect(() => {
    if (viewedRef.current) return
    viewedRef.current = true
    api.trackMobile({ type: 'page_view', sid, tab, src: acq.src, campaign, lang,
      referrer: acq.referrer || undefined })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Document direction/lang/title (standalone full-page experience).
  useEffect(() => {
    const html = document.documentElement
    const prevDir = html.dir, prevLang = html.lang, prevTitle = document.title
    html.dir = t.dir
    html.lang = lang
    document.title = lang === 'he'
      ? 'השוואת חבילות סלולר בישראל - כל המפעילים במקום אחד | MOCA'
      : 'Compare mobile plans in Israel - all carriers in one place | MOCA'
    return () => { html.dir = prevDir; html.lang = prevLang; document.title = prevTitle }
  }, [lang, t.dir])

  // SEO: the SPA shell's canonical points at the site root — rewrite it to a
  // self-referencing apex URL + a page-specific description (same fix as
  // /esim-deals; the prerendered mobile.html shell carries these in raw HTML).
  useEffect(() => {
    const CANON = 'https://mocaintel.com/mobile-deals'
    const DESC = lang === 'he'
      ? 'השוואת מחירים חינמית של חבילות סלולר בישראל, בלי הרשמה. מחירים, נפחי גלישה, 5G והטבות מכל 10 המפעילים, מתעדכן פעמיים ביום.'
      : 'Free comparison of Israeli mobile plans, no sign-up. Prices, data, 5G and perks across all 10 carriers, refreshed twice a day.'
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

  const pickTab = (v) => {
    if (v === tab) return
    setTab(v)
    setDetail(null)
    api.trackMobile({ type: 'tab_pick', sid, tab: v, src: acq.src, campaign, lang })
    const next = new URLSearchParams(params)
    if (v === 'domestic') next.delete('tab'); else next.set('tab', v)
    setParams(next, { replace: true })
  }

  const toggleFacet = (v) => setFacetsOn((prev) => {
    const next = new Set(prev)
    if (next.has(v)) next.delete(v); else next.add(v)
    return next
  })
  const toggleCarrier = (id) => setSelCarriers((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  const openCarrier = (p, fromTab) => {
    api.trackMobile({ type: 'carrier_click', sid, carrier: p.carrier, tab: fromTab, src: acq.src, campaign, lang })
    const url = CARRIER_HOME_URLS[p.carrier]
    if (url) window.open(url, '_blank', 'noopener')
  }

  // Cross-link to the eSIM consumer page. RELATIVE on the shared SPA hosts
  // (apex path / netlify domain / localhost dev) — a hardcoded absolute
  // mocaintel.com URL breaks whenever that domain is down. Only the future
  // mobile.* subdomain (whose catch-all serves THIS page for every path)
  // needs the absolute apex URL.
  const esimHref = (typeof window !== 'undefined' && window.location.hostname.startsWith('mobile.')
    ? 'https://mocaintel.com/esim-deals'
    : '/esim-deals') + (lang === 'en' ? '?lang=en' : '')

  const plansD = useMemo(() => data?.plans || [], [data])
  const carriers = data?.carriers || []

  // ── Domestic filter pipeline ─────────────────────────────────────────────
  const filtered = useMemo(() => {
    let rows = plansD
    // Voice-only kosher plans are hidden unless the kosher toggle is on —
    // keeps "cheapest" honest (a ₪10 no-data plan is not a cheap data plan).
    if (!facetsOn.has('kosher')) rows = rows.filter((p) => !p.voice_only)
    if (budget !== 'all') rows = rows.filter((p) => (p.price ?? 9999) <= budget)
    if (gbTier === 'unl') rows = rows.filter((p) => p.unlimited)
    else if (gbTier === '100') rows = rows.filter((p) => !p.unlimited && !p.voice_only && p.data_gb != null && p.data_gb <= 100)
    else if (gbTier === '500') rows = rows.filter((p) => !p.unlimited && p.data_gb != null && p.data_gb > 100 && p.data_gb <= 500)
    else if (gbTier === '500+') rows = rows.filter((p) => !p.unlimited && p.data_gb != null && p.data_gb > 500)
    if (gen === '5g') rows = rows.filter((p) => p.facets.five_g && !p.facets.five_g_priority)
    else if (gen === '5gp') rows = rows.filter((p) => p.facets.five_g_priority)
    if (facetsOn.has('roaming')) rows = rows.filter((p) => p.facets.roaming)
    if (facetsOn.has('esim')) rows = rows.filter((p) => p.facets.esim)
    if (facetsOn.has('apps')) rows = rows.filter((p) => p.facets.free_apps)
    if (facetsOn.has('kosher')) rows = rows.filter((p) => p.facets.kosher)
    if (selCarriers.size) rows = rows.filter((p) => selCarriers.has(p.carrier))
    return rows
  }, [plansD, budget, gbTier, gen, facetsOn, selCarriers])

  const gbVal = (p) => (p.unlimited ? Number.MAX_SAFE_INTEGER : (p.data_gb ?? -1))
  const list = useMemo(() => {
    const rows = [...filtered]
    if (sort === 'price_asc') rows.sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    else if (sort === 'price_desc') rows.sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
    else if (sort === 'gb_desc') rows.sort((a, b) => (gbVal(b) - gbVal(a)) || ((a.price ?? 9999) - (b.price ?? 9999)))
    else if (sort === 'ppgb') rows.sort((a, b) => (a.price_per_gb ?? Infinity) - (b.price_per_gb ?? Infinity))
    return rows
  }, [filtered, sort])

  // Top picks: honest winners only — conditional-price and voice-only rows can't
  // headline (their advertised ₪ isn't the price a single line actually pays).
  const picks = useMemo(() => {
    if (!filtered.length) return []
    const honest = filtered.filter((p) => !p.voice_only && !p.price_conditional)
    const byPpgb = honest.filter((p) => p.price_per_gb != null).sort((a, b) => a.price_per_gb - b.price_per_gb)
    const byPrice = [...honest].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    const unl = honest.filter((p) => p.unlimited).sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    const out = []
    const seen = new Set()
    const add = (p, b) => { if (p && !seen.has(p.id)) { seen.add(p.id); out.push({ p, b }) } }
    add(byPpgb[0], 0); add(byPrice[0], 1); add(unl[0], 2)
    return out
  }, [filtered])

  // ── Roaming filter pipeline ──────────────────────────────────────────────
  const roamList = useMemo(() => {
    if (!abroad) return []
    let rows = abroad
    if (roamCarrier !== 'all') rows = rows.filter((p) => p.carrier === roamCarrier)
    const q = roamQ.trim()
    if (q) {
      rows = rows.filter((p) => {
        if ((p.plan_name || '').includes(q)) return true
        if ((p.extras || []).some((e) => e.includes(q))) return true
        const cc = getCountriesForAbroadPlan(p)
        return !!(cc && cc.countries && cc.countries.some((c) => c.includes(q)))
      })
    }
    return [...rows].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
  }, [abroad, roamCarrier, roamQ])

  const roamCarriers = useMemo(() => {
    const seen = []
    for (const p of abroad || []) if (!seen.includes(p.carrier)) seen.push(p.carrier)
    return seen
  }, [abroad])

  // ── Content services, grouped by service ─────────────────────────────────
  const contentByService = useMemo(() => {
    const NA = ['לא נמצא', 'שגיאה', 'לא זמין']
    const map = new Map()
    for (const p of content || []) {
      if (p.price && NA.some((v) => String(p.price).includes(v))) continue
      if (!map.has(p.service)) map.set(p.service, [])
      map.get(p.service).push(p)
    }
    return [...map.entries()]
  }, [content])

  const updated = data?.updated_at ? new Date(data.updated_at) : null
  const updatedStr = updated && !Number.isNaN(+updated)
    ? `${t.updated}: ${updated.toLocaleDateString(DATE_LOCALES[lang], { day: 'numeric', month: 'short' })} · ${updated.toLocaleTimeString(DATE_LOCALES[lang], { hour: '2-digit', minute: '2-digit' })}`
    : ''
  const badgeCls = ['b1', 'b2', 'b3']

  const minutesLine = (p) => {
    if (!p.minutes) return null
    const n = Number(String(p.minutes).replace(/[,\s]/g, ''))
    return Number.isFinite(n) && n > 0 ? `${n.toLocaleString()} ${t.minutesU}` : String(p.minutes)
  }

  // Shared card body for a domestic plan.
  const PlanCore = ({ p }) => (
    <>
      <div className="deal-row">
        <CarrierLogo carrier={p.carrier} />
        <div className="deal-info">
          <div className="deal-provider"><bdi>{carrierLabel(p.carrier)}</bdi></div>
          <div className="deal-name"><bdi>{p.plan_name}</bdi></div>
          <div className="deal-meta">
            <bdi>{gbLabel(p, t)}</bdi>
            {minutesLine(p) && <><span className="deal-sep" aria-hidden="true">·</span><bdi>{minutesLine(p)}</bdi></>}
            {p.price_per_gb != null && <><span className="deal-sep" aria-hidden="true">·</span><bdi dir="ltr">₪{fmtNum(p.price_per_gb)}{t.perGB}</bdi></>}
          </div>
        </div>
        <div className="deal-price">
          <div className="price-main" dir="ltr">₪{fmtNum(p.price)}</div>
          <div className="price-sub">{t.perMonth}</div>
          {p.promo_price != null && p.promo_months != null && (
            <div className="price-promo">
              {t.promoLine.replace('{m}', String(p.promo_months)).replace('{p}', fmtNum(p.promo_price))}
            </div>
          )}
        </div>
      </div>
      {(p.chips.length > 0 || p.price_conditional || p.voice_only) && (
        <div className="tags">
          {p.voice_only && <span className="tag warn">{t.voiceOnly}</span>}
          {p.price_conditional && <span className="tag warn" title={t.conditionalHint}>{t.conditional}</span>}
          {p.chips.map((c, i) => <span className="tag" key={i}><bdi>{c}</bdi></span>)}
        </div>
      )}
      <div className="deal-bottom">
        <button type="button" className="get" onClick={() => openCarrier(p, 'domestic')}>
          {t.goto.replace('{carrier}', carrierLabel(p.carrier))}
        </button>
        <button type="button" className="ghost" onClick={() => setDetail(p)}>{t.details}</button>
        <button type="button" className="bell-btn" title={t.remBell} aria-label={t.remBell}
          onClick={() => setRemindFor({ plan: p, type: 'domestic' })}><BellIcon /></button>
      </div>
    </>
  )

  return (
    <div id="mobile-app" dir={t.dir}>
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
          <h1>{t.heroTitle}</h1>
          <p>{t.heroSub}</p>
          {updatedStr && <div className="updated"><span className="dot" /><span>{updatedStr}</span></div>}
        </header>

        <main>
          <div className="tabs" role="tablist">
            {t.tabs.map((o) => (
              <button key={o.v} type="button" role="tab" aria-selected={tab === o.v}
                className={`tab${tab === o.v ? ' on' : ''}`} onClick={() => pickTab(o.v)}>{o.l}</button>
            ))}
          </div>

          {/* ══ Domestic tab ══════════════════════════════════════════════ */}
          {tab === 'domestic' && (data === null ? (
            <div className="splash"><div className="spin" /><div style={{ fontWeight: 700 }}>{t.loading}</div></div>
          ) : (
            <>
              <section className="card wizard reveal">
                <h2>{t.wizTitle}</h2>
                <div className="q">{t.qBudget}</div>
                <div className="chips">
                  {t.budget.map((o) => (
                    <button key={o.v} type="button" className={`chip${o.v === budget ? ' on' : ''}`} onClick={() => setBudget(o.v)}>{o.l}</button>
                  ))}
                </div>
                <div className="q">{t.qGb}</div>
                <div className="chips">
                  {t.gb.map((o) => (
                    <button key={o.v} type="button" className={`chip${o.v === gbTier ? ' on' : ''}`} onClick={() => setGbTier(o.v)}>{o.l}</button>
                  ))}
                </div>
                <div className="q">{t.qGen}</div>
                <div className="chips">
                  {t.gen.map((o) => (
                    <button key={o.v} type="button" className={`chip${o.v === gen ? ' on' : ''}`} onClick={() => setGen(o.v)}>{o.l}</button>
                  ))}
                </div>
                <div className="q">{t.qMore}</div>
                <div className="carrier-row">
                  {t.facetChips.map((o) => (
                    <button key={o.v} type="button" className={`fchip${facetsOn.has(o.v) ? ' on' : ''}`}
                      aria-pressed={facetsOn.has(o.v)} onClick={() => toggleFacet(o.v)}>{o.l}</button>
                  ))}
                </div>
                {carriers.length > 1 && (
                  <>
                    <div className="q">{t.byCarrier}</div>
                    <div className="carrier-row">
                      {carriers.map((c) => {
                        const bc = getCarrierColor(c.id)
                        const on = selCarriers.has(c.id)
                        return (
                          <button key={c.id} type="button" className={`cpick${on ? ' on' : ''}`}
                            style={on ? { borderColor: bc, boxShadow: `inset 0 0 0 1px ${bc}`, background: `color-mix(in srgb, ${bc}, #fff 88%)` } : undefined}
                            aria-pressed={on} onClick={() => toggleCarrier(c.id)}>
                            {CARRIER_LOGOS[c.id] && <img src={CARRIER_LOGOS[c.id]} alt="" loading="lazy" />}
                            <bdi>{c.name}</bdi>
                          </button>
                        )
                      })}
                    </div>
                  </>
                )}
              </section>

              {picks.length > 0 && (
                <section className="reveal">
                  <h2 className="sec" style={{ marginBottom: 8 }}>{t.topPicks}</h2>
                  {picks.map(({ p, b }, i) => (
                    <div className={`pick${i === 0 ? ' first' : ''}`} key={p.id}>
                      <span className={`badge ${badgeCls[b]}`}>{t.badges[b]}</span>
                      <PlanCore p={p} />
                    </div>
                  ))}
                </section>
              )}

              <section className="reveal">
                <div className="list-head">
                  <h2 className="sec" style={{ marginBottom: 0 }}>{t.allPlans}</h2>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span className="count-pill">{t.resultsN.replace('{n}', String(list.length))}</span>
                    <div className="sort-select">
                      <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label={t.sortLabel}>
                        {t.sorts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
                      </select>
                      <svg className="chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
                    </div>
                  </div>
                </div>
                {list.length ? list.map((p) => (
                  <div className="deal" key={p.id}><PlanCore p={p} /></div>
                )) : <div className="card empty">{t.empty}</div>}
              </section>

              <PriceAlertCard t={t} lang={lang} meta={{ sid, src: acq.src, campaign }} carriers={carriers} />
            </>
          ))}

          {/* ══ Roaming tab ═══════════════════════════════════════════════ */}
          {tab === 'roaming' && (
            <>
              <section className="card cross reveal">
                <div className="alert-tx">
                  <b>{t.esimCross}</b>
                  <span>{t.esimCrossSub}</span>
                </div>
                <button type="button" className="cross-btn"
                  onClick={() => window.open(esimHref, '_blank', 'noopener')}>
                  {t.esimCrossBtn}
                </button>
              </section>

              {abroad === null ? (
                <div className="splash"><div className="spin" /><div style={{ fontWeight: 700 }}>{t.loading}</div></div>
              ) : (
                <section className="reveal">
                  <h2 className="sec">{t.roamTitle}</h2>
                  <p style={{ fontSize: 13, color: 'var(--sub)', fontWeight: 600, marginTop: -6, marginBottom: 12 }}>{t.roamSub}</p>
                  <div className="search-wrap">
                    <input className="search" type="text" value={roamQ} placeholder={t.roamSearch}
                      onChange={(e) => setRoamQ(e.target.value)} autoComplete="off" aria-label={t.roamSearch} />
                    <svg className="search-ic" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                      <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
                    </svg>
                  </div>
                  {roamCarriers.length > 1 && (
                    <div className="carrier-row" style={{ marginBottom: 12 }}>
                      <button type="button" className={`cpick${roamCarrier === 'all' ? ' on' : ''}`} onClick={() => setRoamCarrier('all')}>{t.alertAll}</button>
                      {roamCarriers.map((id) => {
                        const bc = getCarrierColor(id)
                        const on = roamCarrier === id
                        return (
                          <button key={id} type="button" className={`cpick${on ? ' on' : ''}`}
                            style={on ? { borderColor: bc, boxShadow: `inset 0 0 0 1px ${bc}`, background: `color-mix(in srgb, ${bc}, #fff 88%)` } : undefined}
                            onClick={() => setRoamCarrier(id)}>
                            {CARRIER_LOGOS[id] && <img src={CARRIER_LOGOS[id]} alt="" loading="lazy" />}
                            <bdi>{carrierLabel(id)}</bdi>
                          </button>
                        )
                      })}
                    </div>
                  )}
                  {roamList.length ? roamList.map((p, i) => {
                    const cc = getCountriesForAbroadPlan(p)
                    const apps = getAppsForPlan(p)
                    return (
                      <div className="deal" key={`${p.carrier}|${p.plan_name}|${i}`}>
                        <div className="deal-row">
                          <CarrierLogo carrier={p.carrier} />
                          <div className="deal-info">
                            <div className="deal-provider"><bdi>{carrierLabel(p.carrier)}</bdi></div>
                            <div className="deal-name"><bdi>{p.plan_name}</bdi></div>
                            <div className="deal-meta">
                              {p.data_gb != null && <bdi>{p.data_gb < 1 ? `${Math.round(p.data_gb * 1024)}MB` : `${+p.data_gb}GB`}</bdi>}
                              {/* NULL data_gb on abroad rows = voice-minutes package (no data), not unlimited */}
                              {p.data_gb == null && !p.minutes && <bdi>{t.unlimited}</bdi>}
                              {p.days != null && <>{(p.data_gb != null || !p.minutes) && <span className="deal-sep" aria-hidden="true">·</span>}<bdi>{p.days} {p.days === 1 ? t.dayU : t.daysU}</bdi></>}
                              {p.minutes != null && p.minutes !== '' && <><span className="deal-sep" aria-hidden="true">·</span><bdi>{p.minutes} {t.minutesU}</bdi></>}
                            </div>
                          </div>
                          <div className="deal-price">
                            <div className="price-main" dir="ltr">₪{fmtNum(p.price)}</div>
                          </div>
                        </div>
                        {(cc?.countries?.length || apps) && (
                          <div className="tags">
                            {cc?.countries?.length > 0 && <span className="tag">{t.countriesN.replace('{n}', String(cc.countries.length))}</span>}
                            {apps?.apps?.length > 0 && <span className="tag">{t.appsN.replace('{n}', String(apps.apps.length))}</span>}
                          </div>
                        )}
                        <div className="deal-bottom">
                          <button type="button" className="get" onClick={() => openCarrier(p, 'roaming')}>
                            {t.goto.replace('{carrier}', carrierLabel(p.carrier))}
                          </button>
                          {(p.info || p.terms_url || (p.extras || []).length > 0) && (
                            <button type="button" className="ghost" onClick={() => setDetail(p)}>{t.details}</button>
                          )}
                          <button type="button" className="bell-btn" title={t.remBell} aria-label={t.remBell}
                            onClick={() => setRemindFor({ plan: p, type: 'roaming' })}><BellIcon /></button>
                        </div>
                      </div>
                    )
                  }) : <div className="card empty">{t.empty}</div>}
                </section>
              )}
            </>
          )}

          {/* ══ Content-services tab ══════════════════════════════════════ */}
          {tab === 'content' && (content === null ? (
            <div className="splash"><div className="spin" /><div style={{ fontWeight: 700 }}>{t.loading}</div></div>
          ) : (
            <section className="reveal">
              <h2 className="sec">{t.contentTitle}</h2>
              <p style={{ fontSize: 13, color: 'var(--sub)', fontWeight: 600, marginTop: -6, marginBottom: 12 }}>{t.contentSub}</p>
              {contentByService.length ? contentByService.map(([service, rows]) => (
                <div className="card" key={service} style={{ marginBottom: 10 }}>
                  <h3 style={{ fontSize: 14.5, fontWeight: 800, marginBottom: 6 }}><bdi>{service}</bdi></h3>
                  {rows.map((p, i) => (
                    <div className="svc-row" key={`${p.carrier}|${i}`}>
                      <CarrierLogo carrier={p.carrier} size={36} />
                      <div className="svc-meta">
                        <div className="svc-carrier">
                          <bdi>{carrierLabel(p.carrier)}</bdi>
                          {p.free_trial && <span className="trial">{t.freeTrial}: {p.free_trial}</span>}
                        </div>
                        {p.note && <div className="svc-note"><bdi>{p.note}</bdi></div>}
                      </div>
                      <div className="svc-price"><bdi>{p.price}</bdi></div>
                      <button type="button" className="bell-btn sm" title={t.remBell} aria-label={t.remBell}
                        onClick={() => setRemindFor({ plan: { carrier: p.carrier, plan_name: p.service }, type: 'content' })}>
                        <BellIcon /></button>
                    </div>
                  ))}
                </div>
              )) : <div className="card empty">{t.empty}</div>}
            </section>
          ))}

          <div className="trust">{miniMarkup(t.trust)}</div>
        </main>

        <footer>
          <div className="freepill">{t.poweredFree}</div>
          <div className="powered">Powered by <b>MOCA</b> ⚡ Market Intelligence</div>
          {/* Crawlable cross-link into the eSIM consumer cluster (internal-link SEO) */}
          <div style={{ margin: '10px 0', fontSize: 13 }}>
            <a href={esimHref}>{t.esimCross}</a>
          </div>
          <div className="disclaim">{t.disclaim}</div>
          <div style={{ marginTop: 10, fontSize: 12 }}>
            <a href={`/privacy${lang === 'en' ? '?lang=en' : ''}`}>{t.privacyL}</a>
            {' · '}
            <a href={`/terms${lang === 'en' ? '?lang=en' : ''}`}>{t.termsL}</a>
          </div>
        </footer>
      </div>

      {detail && <DetailsModal plan={detail} t={t} onClose={() => setDetail(null)} />}
      {remindFor && (
        <ReminderModal plan={remindFor.plan} planType={remindFor.type} t={t} lang={lang}
          meta={{ sid, src: acq.src, campaign }}
          onClose={() => setRemindFor(null)} />
      )}
    </div>
  )
}
