# -*- coding: utf-8 -*-
"""Seed provider_deals — the super-admin "סטטוס ספקים" relationship/commission CRM.

One row per tracked provider: did we reach out, is a deal signed and what % we
take, and what action is still on us. Coupon liveness is NOT stored here — the
dashboard joins it live from provider_coupons so "is there a coupon in the air"
is always accurate. `coupon_note` only adds the nuance (why none, or that a live
coupon is third-party and earns us nothing).

Re-runnable: UPSERTs by provider_id. Maintain this file as deals move — re-run:
    python seed_provider_deals.py

Fields:
  outreach_status : not_contacted | contacted | in_discussion | approved | declined | live
  agreement_status: none | pending | signed | live
  commission_pct  : our commission % (number) — leave None for flat-fee/unknown
  priority        : high | med | low   (high = needs action from us now)
  is_leak         : looks monetized but earns us $0 (fix or clean up)

Sources folded in: seed_coupons.py, affiliateLinks.js, config.json affiliate
registry, and the affiliate-outreach log (memory + Hotel/outreach/*). Snapshot
as of 2026-07-02 — update as threads advance.
"""
from db import init_db, upsert_provider_deal

DEALS = [
    # ══ LIVE & EARNING (green) ════════════════════════════════════════════════
    {
        "provider_id": "voye", "display_name": "Voye Global", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-06-22",
        "contact": "collab@voyeglobal.com", "program_network": "Impact",
        "agreement_status": "live", "commission_pct": 15,
        "commission_note": "15% עמלה, Last-Click 30 יום (Impact acct 7205658)",
        "coupon_note": "קוד MOCA = 15% הנחת לקוח, חי ומזכה אותנו.",
        "has_tracking_link": True, "priority": "low",
        "next_actions": "לעדכן את Voye ש-live; ממתינים לקריאייטיבים (לוגו/באנרים) מהם.",
        "notes": "מאושר ופעיל מ-2026-06-15. לינק /go/voye מחובר.",
    },
    {
        "provider_id": "saily", "display_name": "Saily", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-06-16",
        "contact": "affiliate@sailymedia.com", "program_network": "TUNE (Nord)",
        "agreement_status": "live", "commission_pct": None,
        "commission_note": "קופון לקוח 10%; עמלת אפיליאייט דרך Nord (לא ננקב אחוז).",
        "coupon_note": "קוד MOCA = 10% הנחה, חי ומזכה אותנו. קודי צד-ג' הושבתו.",
        "has_tracking_link": True, "priority": "low",
        "next_actions": "רשות: לחווט checkout deep-link ל-attribution נקי יותר.",
        "notes": "Nord Security. מגבלת PPC: אין הצעות על מילות מפתח ממותגות.",
    },
    {
        "provider_id": "alosim", "display_name": "aloSIM", "category": "global",
        "outreach_status": "approved", "outreach_last_at": "2026-06-23",
        "contact": "Celine Solomon / AffinityClick", "program_network": "Everflow",
        "agreement_status": "live", "commission_pct": None,
        "commission_note": "$5 לכל מכירה (affid 1652, offer 9).",
        "coupon_note": "קוד MOCA = 15% הנחה על רכישה ראשונה, חי ומזכה אותנו.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "לענות ל-Celine: לבקש Sub-ID לכל שיבוץ (חוב תגובה).",
        "notes": "מאושר 2026-06-17.",
    },
    {
        "provider_id": "seven_g", "display_name": "7G", "category": "global",
        "is_israeli": True, "outreach_status": "live", "outreach_last_at": "2026-06-30",
        "contact": "office@7g.app", "program_network": "עצמאי (Branch)",
        "agreement_status": "live", "commission_pct": 15,
        "commission_note": "15% עמלה / 15% הנחה (alonyo15). קיימים גם 10/20 ו-20/10.",
        "coupon_note": "קוד alonyo15 = 15% הנחה, חי ומזכה אותנו (זמני).",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "לבקש מ-7G קוד מאוחד בשם MOCA שיחליף את alonyoXX, ואז להחליף ב-seed_coupons.",
        "notes": "חשבון שותף נוצר אוטומטית 2026-06-30.",
    },
    {
        "provider_id": "terminalesim", "display_name": "Terminal eSIM", "category": "global",
        "is_israeli": True, "outreach_status": "live", "outreach_last_at": "2026-07-02",
        "contact": "WhatsApp 054-4322104", "program_network": "עצמאי (attribution בקוד)",
        "agreement_status": "live", "commission_pct": 10,
        "commission_note": "10% עמלה על לידים שהומרו (הזמנות עם הקוד MOCA).",
        "coupon_note": "קוד MOCA = 15% הנחה, חי. ה-attribution הוא דרך הקוד עצמו (אין לינק tracking).",
        "has_tracking_link": False, "priority": "med",
        "next_actions": "רשות: לוגו public/logos/terminalesim.png; העלאת dist ל-Netlify (frontend).",
        "notes": "החליף את GlobaleSIM 2026-07. ~2,481 חבילות נסרקות.",
    },
    {
        "provider_id": "bcengi", "display_name": "BCengi", "category": "global",
        "outreach_status": "approved", "outreach_last_at": "2026-06-30",
        "contact": "support@bcengi.com", "program_network": "Impact",
        "agreement_status": "live", "commission_pct": 15,
        "commission_note": "15% עמלה על Refill + רכישה אונליין, 30 יום.",
        "coupon_note": "אין קוד MOCA ייעודי - יש רק קוד גנרי (DFB) שלא מזכה אותנו ספציפית.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "לבקש קופון ממותג MOCA (כרגע רק DFB גנרי).",
        "notes": "מאושר 2026-06-30. רץ על Impact (sjv.io, אותו acct כמו Voye).",
    },

    # ══ IN DISCUSSION / PENDING (yellow) ══════════════════════════════════════
    {
        "provider_id": "airalo", "display_name": "Airalo", "category": "global",
        "outreach_status": "in_discussion", "outreach_last_at": "2026-06-21",
        "contact": "guy.dor@airalo.com", "program_network": "Impact / ישיר",
        "agreement_status": "pending", "commission_pct": 15,
        "commission_note": "15% עמלה, cookie 30 יום (מודל Reseller Link).",
        "coupon_note": "קוד GOODAY = קוד אישי דרך Gooday (מזכה את Gooday, לא אותנו). אין קוד MOCA; לינק Impact נדחה (Brand alignment); מו\"מ ישיר עם Guy Dor.",
        "has_tracking_link": False, "is_leak": True, "priority": "high",
        "next_actions": "חוב תגובה ל-Guy Dor: להחליט - להשיק reseller link עכשיו ו/או לקבל הפניה לצוות ה-Affiliate ל-deep links.",
        "notes": "מופיע כממומן (כפתור רכישה) אך הלינק הוא דף הבית ללא tracking - כרגע לא מזכה.",
    },
    {
        "provider_id": "maya", "display_name": "Maya Mobile", "category": "global",
        "outreach_status": "approved", "outreach_last_at": "2026-07-02",
        "contact": "bskrzypek@maya.net", "program_network": "Impact",
        "agreement_status": "signed", "commission_pct": 17,
        "commission_note": "15%-20% עמלה (Impact acct 7205658 אושר).",
        "coupon_note": "שיחה בוצעה 2026-07-02 - סגרנו על קופון (MOCA10, 10% רכישה ראשונה) + API. Bart ישלח מייל שסוגר קצוות עם אישור שהקופון באוויר.",
        "has_tracking_link": False, "priority": "high",
        "next_actions": "ממתינים למייל האישור מ-Bart שהקופון באוויר; אז להזין קופון ב-seed_coupons, לחווט לינק Impact ולחבר את ה-API (plans.json).",
        "notes": "פריצת דרך 2026-06-26. שיחה נסגרה 2026-07-02 (קופון + API). API plans.json יעבור ל-real-time ביולי.",
    },
    {
        "provider_id": "ubigi", "display_name": "Ubigi", "category": "global",
        "outreach_status": "approved", "outreach_last_at": "2026-06-30",
        "contact": "cynthia.razafindrakoto@transatel.com", "program_network": "Impact",
        "agreement_status": "signed", "commission_pct": None,
        "commission_note": "חוזה אושר ב-Impact 2026-06-30, cookie 60 יום. אחוז ייסגר.",
        "coupon_note": "Cynthia מקימה קוד MOCA; לינק tracking חובר, ממתין לקוד קופון.",
        "has_tracking_link": True, "priority": "high",
        "next_actions": "לינק Impact (go.ubigi.com/MKgJG3) חובר ב-AFFILIATE_URLS.ubigi + config.json (2026-07-03). כשמגיע קוד הקופון: להזין ב-seed_coupons.",
        "notes": "כבר ספק נסרק. Sub-ID לכל מלון + deep links אושרו כאפשריים.",
    },
    {
        "provider_id": "yesim", "display_name": "Yesim", "category": "global",
        "outreach_status": "approved", "outreach_last_at": "2026-06-19",
        "contact": "Bogdan (Head of Affiliate)", "program_network": "עצמאי (partner_id 4804)",
        "agreement_status": "signed", "commission_pct": 10,
        "commission_note": "מ-10% recurring, עולה ל-15%+ עם ווליום.",
        "coupon_note": "אין קוד עדיין; לבקש קוד MOCA.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "לענות/לקבוע שיחת setup עם Bogdan; לבקש קוד קידום MOCA.",
        "notes": "כבר ספק נסרק (partner_id 4804 מחובר).",
    },
    {
        "provider_id": "nomad", "display_name": "Nomad", "category": "global",
        "outreach_status": "in_discussion", "outreach_last_at": "2026-06-30",
        "contact": "georgia.ellison@lotusflare.com", "program_network": "Impact",
        "agreement_status": "pending", "commission_pct": 10,
        "commission_note": "~10% עמלה, 30 יום (בכפוף לאישור מחדש).",
        "coupon_note": "אין קוד. לינק Impact נדחה אוטומטית; בבדיקה חוזרת אחרי שליחת מדיה-פאק.",
        "has_tracking_link": False, "priority": "med",
        "next_actions": "להמתין לפסיקת Georgia; להציע one-pager PDF אם תרצה פורמט.",
        "notes": "כבר ספק נסרק (כרטיס מידע בלבד עד אישור).",
    },
    {
        "provider_id": "bnesim", "display_name": "BNESIM", "category": "global",
        "outreach_status": "approved", "outreach_last_at": "2026-07-02",
        "contact": "gianluca.giacomini@bnesim.com", "program_network": "עצמאי (SignWell)",
        "agreement_status": "signed", "commission_pct": 15,
        "commission_note": "10%-20% לפי ווליום + lifetime, כולל חידושים ו-top-ups.",
        "coupon_note": "קוד MOCA (עד 20% הנחה) - ממתין לאישור.",
        "has_tracking_link": False, "priority": "med",
        "next_actions": "ההסכם נחתם דו-צדדית (SignWell, שני הצדדים Completed). כשמגיע לינק tracking + קוד MOCA: לחווט affiliateLinks.js + config.json affiliate.bnesim + להזין קופון ב-seed_coupons.",
        "notes": "BNESIM != Besim. כבר ספק נסרק (scrape_bnesim_global). כרגע כרטיס מידע בלבד - אין לינק אפיליאייט/קופון, /go/bnesim נופל לדף הבית (עדיין לא מזכה).",
    },
    {
        "provider_id": "besim", "display_name": "BeSIM", "category": "global",
        "is_israeli": True, "outreach_status": "in_discussion", "outreach_last_at": "2026-07-01",
        "contact": "miro@besim.co.il", "program_network": "גמיש (Impact/עצמאי)",
        "agreement_status": "pending", "commission_pct": None,
        "commission_note": "המודל ייסגר בשיחה עם Miro (מנכ\"ל).",
        "coupon_note": "קוד MOCA - ממתין לסגירת מודל.",
        "has_tracking_link": False, "priority": "med",
        "next_actions": "בשיחה: לסכם מודל + לקבל לינק/קופון, ואז לחווט config.affiliate.besim + להזין קופון.",
        "notes": "כבר ספק נסרק. לינק /go/besim תוקן ל-besim.co.il (2026-07-01).",
    },
    {
        "provider_id": "esimio", "display_name": "eSIM.io", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-07-01",
        "contact": "info@esim.io (Desk360 #91126)", "program_network": "לא ידוע",
        "agreement_status": "pending", "commission_pct": None,
        "commission_note": "טרם נמסרו תנאים.",
        "coupon_note": "טופס שותפות (Google Form) הוגש; ממתין לתשובת partnerships.",
        "has_tracking_link": False, "priority": "low",
        "next_actions": "להמתין לתשובת צוות השותפויות.",
        "notes": "כבר ספק נסרק.",
    },

    # ══ COLD OUTREACH SENT — awaiting reply (2026-06-30 batch) ════════════════
    {
        "provider_id": "breez", "display_name": "Breeze", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "business@breezesim.com", "program_network": "UpPromote + AWIN",
        "agreement_status": "none", "commission_pct": 20,
        "commission_note": "20% recurring/lifetime, 30 יום (לפי התוכנית שלהם).",
        "coupon_note": "פנייה קרה נשלחה; ממתין לתשובה.",
        "priority": "low", "next_actions": "מעקב אם אין תשובה.",
    },
    {
        "provider_id": "esimplus", "display_name": "eSIM Plus", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "support.esim@appvillis.com", "program_network": "אין (הוצע להקים)",
        "agreement_status": "none", "commission_pct": None,
        "coupon_note": "פנייה קרה; אין תוכנית פומבית, הצענו להקים.",
        "priority": "low", "next_actions": "מעקב.",
        "notes": "Appvillis (ליטא). כבר ספק נסרק.",
    },
    {
        "provider_id": "esim70", "display_name": "eSIM70", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "support@esim70.com", "program_network": "אין",
        "agreement_status": "none", "coupon_note": "פנייה קרה; ממתין.",
        "priority": "low", "next_actions": "מעקב.", "notes": "כבר ספק נסרק.",
    },
    {
        "provider_id": "esimo", "display_name": "eSIMo", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "media@esimo.io (Mike Din)", "program_network": "Impact",
        "agreement_status": "none", "commission_pct": None,
        "coupon_note": "פנייה קרה נשלחה; ממתין.",
        "priority": "low", "next_actions": "מעקב.", "notes": "כבר ספק נסרק.",
    },
    {
        "provider_id": "simtlv", "display_name": "SimTLV", "category": "global",
        "is_israeli": True, "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "dor@simtlv.co.il", "program_network": "לא ידוע",
        "agreement_status": "none", "coupon_note": "הופנינו ל-dor@; ממתין.",
        "priority": "low", "next_actions": "מעקב מול dor@simtlv.co.il.",
        "notes": "כבר ספק נסרק. ARIDAR, קרית ביאליק.",
    },
    {
        "provider_id": "world8", "display_name": "8 World", "category": "global",
        "is_israeli": True, "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "world8@roaming.co.il", "program_network": "לא ידוע",
        "agreement_status": "none", "coupon_note": "פנייה נשלחה; ממתין.",
        "priority": "low", "next_actions": "מעקב.",
        "notes": "Global Roaming Ltd. כבר ספק נסרק.",
    },
    {
        "provider_id": "xphone_global", "display_name": "XPhone Global", "category": "global",
        "is_israeli": True, "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "pniot@xphone.co.il", "program_network": "לא ידוע",
        "agreement_status": "none", "coupon_note": "פנייה נשלחה; ממתין.",
        "priority": "low", "next_actions": "מעקב.",
        "notes": "MVNO על HOT; כבר מנוטר כמפעיל.",
    },
    {
        "provider_id": "travelsim", "display_name": "Travel Sim", "category": "global",
        "is_israeli": True, "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "travelsimobile@hotmobile.co.il", "program_network": "לא ידוע",
        "agreement_status": "none", "coupon_note": "פנייה נשלחה; ממתין.",
        "priority": "low", "next_actions": "מעקב.",
        "notes": "מוצר של HOT Mobile. כבר ספק נסרק.",
    },
    {
        "provider_id": "tasim", "display_name": "Tasim", "category": "global",
        "is_israeli": True, "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "support@tasim.us", "program_network": "לא ידוע",
        "agreement_status": "none", "coupon_note": "פנייה נשלחה; ממתין.",
        "priority": "low", "next_actions": "מעקב.",
        "notes": "נישת ארה\"ב לישראלים. כבר ספק נסרק.",
    },
    {
        "provider_id": "bestconnect", "display_name": "Best Connect", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "info@bestconnect.online (לא מאומת)", "program_network": "לא ידוע",
        "agreement_status": "none",
        "coupon_note": "פנייה נשלחה לכתובת לא מאומתת; לאמת איש קשר.",
        "priority": "low", "next_actions": "לאמת כתובת קשר אמיתית (האתר 403).",
        "notes": "כבר ספק נסרק.",
    },

    # ── bounced / need a valid contact ──
    {
        "provider_id": "orbit", "display_name": "Orbit", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "business@orbitesim.com (bounced)", "program_network": "FirstPromoter",
        "agreement_status": "none", "commission_pct": 18,
        "commission_note": "15-22% מדורג, מינימום $50.",
        "coupon_note": "המייל חזר (bounced); צריך איש קשר תקין.",
        "priority": "low", "next_actions": "למצוא כתובת תקינה (החנות היא orbitesim.com).",
        "notes": "כבר ספק נסרק (REST API).",
    },
    {
        "provider_id": "bytesim", "display_name": "ByteSIM", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "support@bytesim.com (bounced)", "program_network": "עצמאי",
        "agreement_status": "none", "commission_pct": 10,
        "commission_note": "10% / 30 יום (תוכנית פנימית).",
        "coupon_note": "המייל חזר (bounced); צריך איש קשר תקין.",
        "priority": "low", "next_actions": "הרשמה ב-bytesim.com/affiliate-program/sign-up.",
        "notes": "כבר ספק נסרק.",
    },
    {
        "provider_id": "jetpack", "display_name": "Jetpac", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "טופס Jetffiliate באתר", "program_network": "עצמאי",
        "agreement_status": "none", "commission_pct": 15,
        "commission_note": "~15% / 30 יום.",
        "coupon_note": "המייל חזר (bounced); הרשמה דרך הטופס באתר.",
        "priority": "low", "next_actions": "למלא את טופס Jetffiliate ב-jetpacglobal.com/affiliates.",
        "notes": "כבר ספק נסרק.",
    },

    # ══ DECLINED ══════════════════════════════════════════════════════════════
    {
        "provider_id": "sparks", "display_name": "Sparks", "category": "global",
        "is_israeli": True, "outreach_status": "declined", "outreach_last_at": "2026-06-30",
        "contact": "contact-us1-support@sparks.travel", "program_network": "אין (B2B בלבד)",
        "agreement_status": "none",
        "coupon_note": "נדחה - עובדים רק עם משווקים גדולים בהתחייבות חודשית.",
        "priority": "low", "next_actions": "אין. חברה ישראלית (פתח תקווה), B2B בלבד.",
        "notes": "כבר ספק נסרק.",
    },

    # ══ NOT CONTACTED ═════════════════════════════════════════════════════════
    {
        "provider_id": "holafly", "display_name": "Holafly", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "Impact dashboard", "program_network": "Impact",
        "agreement_status": "none", "commission_pct": None,
        "commission_note": "אין הסכם פעיל (הוגש ב-Impact 06-13, ללא אישור).",
        "coupon_note": "3 קופונים חיים אך של צד-ג' (ADAMANDLINDS וכו') - מזכים מתחרה, לא אותנו!",
        "has_tracking_link": False, "is_leak": True, "priority": "high",
        "next_actions": "להחליט: (א) לרדוף אחרי חוזה Impact ללינק+קוד MOCA, או (ב) לנקות - להשבית את 3 קופוני צד-ג' ב-seed_coupons ולהסיר את holafly מ-AFFILIATE_PROVIDERS.",
        "notes": "דליפה: נראה ממומן (בכפתור רכישה + קופונים) אך הלינק הוא דף הבית placeholder והקופונים מזכים מתחרים.",
    },
    {
        "provider_id": "gomoworld", "display_name": "GoMoWorld", "category": "global",
        "outreach_status": "not_contacted", "program_network": "לא ידוע",
        "agreement_status": "none",
        "coupon_note": "טרם פנינו.",
        "priority": "low", "next_actions": "לחקור איש קשר + לפנות.",
        "notes": "כבר ספק נסרק.",
    },
    {
        "provider_id": "flexiroam", "display_name": "Flexiroam", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "partner@flexiroam.com", "program_network": "Post Affiliate Pro",
        "agreement_status": "none", "commission_pct": 17,
        "commission_note": "15%-20% מדורג, מינימום תשלום $500, 30 יום.",
        "coupon_note": "פנייה נשלחה; פורטל ההרשמה חוסם בוטים - לעשות ידנית.",
        "priority": "low", "next_actions": "מעקב / הרשמה ידנית בפורטל.",
        "notes": "לא ספק נסרק כרגע.",
    },
    {
        "provider_id": "instabridge", "display_name": "Instabridge", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-06-30",
        "contact": "press@instabridge.com", "program_network": "CJ Affiliate",
        "agreement_status": "none", "commission_pct": 10,
        "commission_note": "~10% (ערוץ רשמי = CJ Affiliate).",
        "coupon_note": "רק תיבת PRESS מאומתת; להגיש גם דרך CJ.",
        "priority": "low", "next_actions": "להגיש בקשה ב-CJ Affiliate.",
        "notes": "לא ספק נסרק כרגע.",
    },
    {
        "provider_id": "gigsky", "display_name": "GigSky", "category": "global",
        "outreach_status": "in_discussion", "outreach_last_at": "2026-06-17",
        "contact": "Alex Dufort (Head of Partnerships)", "program_network": "Everflow",
        "agreement_status": "pending", "commission_pct": 10,
        "commission_note": "~10% (טרם פורסם רשמית).",
        "coupon_note": "אין קוד; לבקש קוד + Sub-ID.",
        "priority": "med", "next_actions": "לענות/שיחה אופציונלית; להשלים Legal Entity Type בטופס.",
        "notes": "לא ספק נסרק כרגע.",
    },
]


def main():
    init_db()
    for d in DEALS:
        pid = d.pop("provider_id")
        upsert_provider_deal(pid, **d)
        flag = "  [LEAK]" if d.get("is_leak") else ""
        print(f"  upserted  {pid:16s}  {d.get('outreach_status',''):14s}  "
              f"{d.get('agreement_status',''):8s}{flag}")
    print(f"\nDone. {len(DEALS)} provider deals seeded.")


if __name__ == "__main__":
    main()
