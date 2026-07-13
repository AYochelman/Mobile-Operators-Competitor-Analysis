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
as of 2026-07-03 — update as threads advance.
"""
from db import init_db, upsert_provider_deal

DEALS = [
    # ══ LIVE & EARNING (green) ════════════════════════════════════════════════
    {
        "provider_id": "gomoworld", "display_name": "GoMoWorld", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-07-10",
        "contact": "Rana Doula (Partnership Manager, Puremium) rdoula@puremium.com / team@puremium.com; login my.puremium.com (Affiliate ID 1968)",
        "program_network": "Puremium SAS (פלטפורמת HasOffers/TUNE)",
        "agreement_status": "live", "commission_pct": 15,
        "commission_note": "15% עמלה על כל המרה ראשונה (Rana אישרה בכתב 06/07). חלון cookie 30 יום ללינק המעקב; לקוד עצמו אין חלון (חל ב-checkout). תשלום ב-EUR. Offer 23 עולמי, תוקף עד 06/2028.",
        "coupon_note": "קוד MOCA = 10% הנחת לקוח, חי ומזכה אותנו (Rana אישרה 06/07; מוזן ב-seed_coupons, חי ב-/api/coupons).",
        "has_tracking_link": True, "priority": "low",
        "next_actions": "ממתינים לתשובה על בקשת הקישור (עמוד שותפים/בלוג, מייל 10/07; אם שקט עד ~17/07 - תזכורת). רשות (בצד שלנו): deep-links פר-יעד (Rana שלחה מדריך; מנגנון url_id בממשק - ליצור לינק per-dest ולמפות ב-app.py כמו Voye/Breeze) + Sub-ID פר-מלון (aff_sub5). ממתינים מ-Rana: נכסי מותג (לוגו/באנרים) - בקשה נשלחה 06/07.",
        "notes": "eircom Limited (eir, אירלנד). כבר ספק נסרק. תוכנית השותפים מנוהלת ע\"י Puremium (פריז) על HasOffers/TUNE. 03/07 הרשמה, 06/07 אושר + אלון התחבר + חובר LIVE: config.json affiliate.gomoworld + affiliateLinks.js (Affiliate ID 1968, לינק 'https://www.puremium1.com/aff_c?offer_id=23&aff_id=1968'), /go/gomoworld 302 מאומת, build+Netlify עלו (כפתור חי), קופון MOCA 10% נזרע וחי. Rana נתנה גם לינקים ENG/FR עם aff_sub5=MOCA ו-url_id (עמוד יעדים). 06/07: אלון שלח תשובה ל-Rana שמאשרת את התנאים (15%/10%/30 יום) + ביקש נכסי מותג. 10/07: נשלח מייל בקשת-קישור (אזכור MOCA בעמוד השותפים/בלוג) במסגרת מהלך ה-SEO של עמודי היעדים.",
    },
    {
        "provider_id": "voye", "display_name": "Voye Global", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-07-10",
        "contact": "collab@voyeglobal.com", "program_network": "Impact",
        "agreement_status": "live", "commission_pct": 15,
        "commission_note": "15% עמלה, Last-Click 30 יום (Impact acct 7205658)",
        "coupon_note": "קוד MOCA = 15% הנחת לקוח, חי ומזכה אותנו.",
        "has_tracking_link": True, "priority": "low",
        "next_actions": "ממתינים לתשובה על בקשת הקישור (עמוד שותפים, מייל 10/07) + לקריאייטיבים; אם שקט עד ~17/07 - תזכורת.",
        "notes": "מאושר ופעיל מ-2026-06-15. לינק /go/voye מחובר. Deep-links פר-יעד (03/07): נוצרו ב-Impact 16 TrackingLinks ליעדים המובילים (voyeglobal.com/he/esim/<country>/) וחוברו ב-app.py (_VOYE_DEST_DEEPLINKS, מפתח לפי dest); /go/voye?dest= מוביל לעמוד המדינה עם attribution, שאר היעדים נופלים ללינק הגנרי. מכסה B2C + מלונות. מאומת 16/16. 10/07: נשלח מייל בקשת-קישור + עדכון על עמודי היעדים החדשים + תזכורת קריאייטיבים.",
    },
    {
        "provider_id": "orbit", "display_name": "Orbit", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-07-08",
        "contact": "Impact (brand Orbit Mobile 32966 / Orbit Mobile Limited 6117688)", "program_network": "Impact",
        "agreement_status": "live", "commission_pct": 20,
        "commission_note": "20% עמלה, ייחוס קליק 30 יום (Impact acct 7205658, brand Orbit Mobile). קודם סומן FirstPromoter 15-22% - בפועל רץ על Impact.",
        "coupon_note": "אין קוד MOCA עדיין - לבקש מ-Orbit. ייחוס עובד דרך לינק ה-tracking.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "חובר 08/07: לינק Impact https://orbitmobile.sjv.io/k4kN50 ב-config.json affiliate.orbit + affiliateLinks.js; /go/orbit 302 מאומת (הבסיס חי מיד). deep-links פר-מדינה לא אפשריים (ל-orbitmobile.com אין עמודי מדינה - SPA accordion, ה-URL לא משתנה), אז במקום זה חובר SubId פר-יעד (subId1=יעד, subId2=src, subId3=hotel) ל-app.py כמו bcengi - דיווח פר-יעד ב-Impact. פתוח: (1) אתחול Flask מורשה (restart_flask.bat כ-admin) כדי שברנץ ה-SubId ייכנס לתוקף - כרגע קונסולת watchdog תקועה elevated (PID ישן) מריצה קוד ישן על :5000, (2) Alon לגרור dist ל-Netlify לכפתור בדשבורד, (3) לבקש קוד קופון MOCA מ-Orbit.",
        "notes": "כבר ספק נסרק (REST API, be.orbitmobile.com, 195 מדינות + 9 zones). מצטרפים דרך Impact (brand Orbit Mobile), לא FirstPromoter. האתר הנכון orbitmobile.com. 03/07 בקשת הצטרפות הוגשה. 08/07: Orbit אישרו (מייל Impact 'You're All Set - Let's Launch' + ערכת Affiliate Toolkit ב-Google Drive) → לינק נוצר ב-Impact 'Create a link' וחובר LIVE (backend מזכה מיד, load_config לפי mtime). /go/orbit מוביל דרך acct 7205658 לדף הבית orbitmobile.com. 08/07 נבדק חי: orbitmobile.com הוא SPA שבו בחירת מדינה פותחת accordion באותו עמוד (URL נשאר /en/plans/top-destinations) - אין עמוד ייעודי למדינה, לכן deep-links פר-מדינה בסגנון Voye/Ubigi לא רלוונטיים; במקום זה _orbit_subid_url מצרף SubId פר-יעד לדיווח. B2C /esim-deals + פורטלי מלונות כבר מעבירים dest ל-/go גנרית.",
    },
    {
        "provider_id": "saily", "display_name": "Saily", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-07-10",
        "contact": "affiliate@sailymedia.com", "program_network": "TUNE (Nord)",
        "agreement_status": "live", "commission_pct": None,
        "commission_note": "קופון לקוח 10%; עמלת אפיליאייט דרך Nord (לא ננקב אחוז).",
        "coupon_note": "קוד MOCA = 10% הנחה, חי ומזכה אותנו. קודי צד-ג' הושבתו.",
        "has_tracking_link": True, "priority": "low",
        "next_actions": "ממתינים לתשובה על בקשת הקישור (עמוד שותפים/spotlight, מייל 10/07); אם שקט עד ~17/07 - תזכורת.",
        "notes": "Nord Security. מגבלת PPC: אין הצעות על מילות מפתח ממותגות. 2026-07-03: /go/saily מנתב דרך ה-checkout deep-link כשידוע plan token, ומעביר קוד מלון כ-aff_sub ל-attribution לכל מלון. 10/07: נשלח מייל בקשת-קישור (עמוד שותפים) במסגרת מהלך ה-SEO; הודגש שאין הפרת מדיניות ה-PPC.",
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
        "outreach_status": "approved", "outreach_last_at": "2026-07-10",
        "contact": "support@bcengi.com", "program_network": "Impact",
        "agreement_status": "live", "commission_pct": 15,
        "commission_note": "15% עמלה על Refill + רכישה אונליין, 30 יום.",
        "coupon_note": "אין קוד MOCA ייעודי - יש רק קוד גנרי (DFB) שלא מזכה אותנו ספציפית.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "ממתינים לתשובה על בקשת הקישור (מייל 10/07; אם שקט עד ~17/07 - תזכורת) + לבקש קופון ממותג MOCA (כרגע רק DFB גנרי).",
        "notes": "מאושר 2026-06-30. רץ על Impact (sjv.io, אותו acct כמו Voye). "
                 "מעקב פר-יעד נכנס 2026-07-04: לאתר אין דפי יעד (עמוד תמחור אחד), "
                 "אז /go/bcengi מצרף SubIds ללינק היחיד (subId1=יעד, subId2=מקור, "
                 "subId3=מלון) - דיווח פר-יעד בדוחות Impact בלי לינקים נפרדים. "
                 "10/07: נשלח מייל בקשת-קישור (עמוד שותפים/בלוג) במסגרת מהלך ה-SEO.",
    },
    {
        "provider_id": "bytesim", "display_name": "ByteSIM", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-07-03",
        "contact": "bytesim.com/affiliate-program (self-serve, referral_code 8F68HJS3KPDU)",
        "program_network": "עצמאי (תוכנית פנימית, self-serve)",
        "agreement_status": "live", "commission_pct": 10,
        "commission_note": "עד 10% עמלה למכירה (תוכנית פנימית, הרשמה עצמית - ללא מו\"מ).",
        "coupon_note": "קוד MOCA פעיל שוב 2026-07-03: 5% הנחת לקוח, מאומת ב-checkout (2.42$- על סאב-טוטל 48.35$). מצטבר על 5% מבצע קיץ האוטומטי שלהם. ByteSim אישרו שהמבצע נוסף אך תקלת אישור חסמה אותו, ותוקן. ה-attribution גם דרך הלינק (referral_code).",
        "has_tracking_link": True, "priority": "low",
        "next_actions": "אין - הקופון פעיל. תווית ה-5% נמשכת חי מ-/api/coupons (אין צורך בפריסת Netlify); מופיעה בעמוד הציבורי תוך ~5 דק' (client cache).",
        "notes": "נרשמנו לתוכנית האפיליאייט הפנימית 2026-07-03 (referral_code 8F68HJS3KPDU). לינק /go/bytesim + AFFILIATE_URLS.bytesim + קוד MOCA חוברו. החליף את הפנייה הקרה שחזרה (support@bytesim.com bounced).",
    },
    {
        "provider_id": "maya", "display_name": "Maya Mobile", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-07-03",
        "contact": "bskrzypek@maya.net", "program_network": "Impact",
        "agreement_status": "live", "commission_pct": 17,
        "commission_note": "15%-20% עמלה (Impact acct 7205658).",
        "coupon_note": "קוד MOCA10 = 10% הנחה לרכישה ראשונה. Bart אישר בכתב (מייל 2026-07-02) שהקוד חי; כבר מוזן ב-seed_coupons ומזכה אותנו. קיים גם לינק tracking של Impact (mayamobile.pxf.io/oNV1xn) - הזיכוי דרך הלינק וגם דרך הקוד.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "1) פיילוט B2B (חדש 2026-07-03): נשלח ל-Bart דשבורד ממותג בצבעי Maya לשבוע ניסיון + פרטי כניסה (מייל 03/07, סיסמה עודכנה ידנית); מעקב ~2026-07-10 לאיסוף פידבק ולדון בהמשך/מנוי בתשלום. 2) לוודא ש-MOCA10 מוצג בעמוד הציבורי (הרצת seed_coupons + פריסה). 3) API - הושלם. תיעוד ה-Partner Reference (v0.2 draft, AI-generated) נסקר 03/07: מאשר ש-assets.maya.net/affiliates/plans.json הוא ה-endpoint היחיד (JSON סטטי ב-CDN, ללא auth, אין real-time - poll שבועי מספיק), ואנחנו כבר קוראים אותו נכון (8 חבילות + מחירים תואמים). בוצע 03/07: השיפור שהדוק המליץ עליו הושלם - יוצרו ב-Impact 8 TrackingLinks (אחד לכל חבילה) וחוברו ב-app.py (_MAYA_PLAN_DEEPLINKS + _maya_deeplink_url), כך ש-/go/maya?plan= מוביל ל-deep-link לחבילה המדויקת (כמו Saily). מכסה את עמוד ה-B2C ופורטלי המלונות; הדשבורד הפנימי נשאר על הלינק הגנרי (כמו Saily). מאומת חי: 302 לכל חבילה + 8 הלינקים נפתרים לעמוד הנכון.",
        "notes": "פריצת דרך 2026-06-26. שיחה + מייל אישור 2026-07-02: MOCA10 חי + Direct Link ל-API + תיעוד Affiliate API מצורף (מייבא 8 חבילות: 4 roaming גלובלי + 4 שייט). לינק tracking של Impact (mayamobile.pxf.io/oNV1xn) כבר מחווט ב-affiliateLinks.js + config.affiliate.maya; /go/maya מאומת 302 → הלינק. פיילוט B2B 2026-07-03: הוקם דשבורד ייעודי ל-Bart בצבעי המותג של Maya, גישת שבוע להשוואת מחירי מתחרים ליעדים בעולם; פרטי כניסה נשלחו במייל (יוזר bskrzypek@maya.net), הסיסמה עודכנה ידנית. ה-API מחובר ומאומת: scrape_maya_global מייבא את 8 החבילות מ-assets.maya.net/affiliates/plans.json (feed סטטי ב-CDN, ללא auth). תיעוד ה-Partner Reference v0.2 נסקר 03/07 ומאשר שאנחנו על ה-endpoint הנכון והיחיד (אין real-time). איש קשר טכני/schema: jean.m@maya.net (Bart = partnerships). Deep-links פר-חבילה: 8 TrackingLinks נוצרו ב-Impact וחוברו ב-app.py (_MAYA_PLAN_DEEPLINKS), /go/maya?plan= מוביל לחבילה המדויקת - מכסה B2C + מלונות (03/07).",
    },

    {
        "provider_id": "breez", "display_name": "Breeze", "category": "global",
        "outreach_status": "live", "outreach_last_at": "2026-07-10",
        "contact": "affiliates@breezesim.com", "program_network": "UpPromote",
        "agreement_status": "live", "commission_pct": 20,
        "commission_note": "תוכנית Default פעילה: 20.00% קבוע, Lifetime=Yes (כל הזמנה כולל חידושים+טופ-אפים, cookie 30 יום). מאומת בדשבורד 06/07 (Program details); טבלת product-commission ריקה = אין חריגות פר-מוצר. תשלום ב-28 לחודש דרך BACS/PayPal, BACS מינימום $250. יש 2 חלופות בתוכנית: 10%עמלה+10%הנחת-לקוח, או 0%עמלה+20%הנחה - אנחנו על ה-20% (הכי משתלם לאתר השוואה).",
        "coupon_note": "אין קופון קבוע. קודי קופון לשותפים מופיעים בדשבורד רק כש-Breeze מריצה מבצע עונתי - לבדוק תקופתית ולהזין ב-seed_coupons כשקיים.",
        "has_tracking_link": True, "priority": "low",
        "next_actions": "ממתינים לתשובה על בקשת הקישור (עמוד שותפים/בלוג, מייל 10/07; אם שקט עד ~17/07 - תזכורת). אזהרה: אסור להצביע מודעות בתשלום (טיקטוק/גוגל) ישירות על לינק ה-sca_ref - חייב לנתב דרך עמוד ממותג משלנו (esim.mocaintel.com), אחרת השהיית חשבון; MOCA כבר תואם. אופציונלי: API catalogue לבקשה; להגדיר PayPal ב-Settings>Payment.",
        "notes": "כבר ספק נסרק. פנייה קרה 30/06 ללא מענה; 05/07 הוגשה בקשה דרך טופס התוכנית והתקבל לינק tracking (breezesim.com?sca_ref=11756847.LeXawwdfKwAOA, אומת בדשבורד). חווט 05/07: affiliateLinks.js + config.affiliate.breez; /go/breez מאומת 302. גייד רשמי נקרא 06/07. deep-links פר-יעד חוברו 06/07: 205 עמודי מוצר Shopify (scraper.BREEZ_HEB_TO_HANDLE + _breez_deeplink_url ב-app.py), /go/breez?dest= מנתב לעמוד המדינה עם sca_ref (+sca_source=hotel/src) - עובד ב-B2C ובפורטל המלונות ללא rebuild. שתי רשתות UpPromote(שלנו)+AWIN; חינם, לא-בלעדי; דף נחיתה ממותג ל->5,000 ביקורים/חודש. 10/07: נשלח מייל בקשת-קישור (עמוד שותפים/בלוג) במסגרת מהלך ה-SEO.",
    },

    # ══ IN DISCUSSION / PENDING (yellow) ══════════════════════════════════════
    {
        "provider_id": "airalo", "display_name": "Airalo", "category": "global",
        "outreach_status": "in_discussion", "outreach_last_at": "2026-07-10",
        "contact": "growth@airalo.com (Affiliate); guy.dor@airalo.com (Partnerships)", "program_network": "Impact / ישיר",
        "agreement_status": "pending", "commission_pct": 15,
        "commission_note": "15% עמלה, cookie 30 יום (מודל Reseller Link).",
        "coupon_note": "קוד GOODAY = קוד אישי דרך Gooday (מזכה את Gooday, לא אותנו). אין קוד MOCA; לינק Impact נדחה (Brand alignment); הבקשה הועברה לצוות ה-growth/affiliate.",
        "has_tracking_link": False, "is_leak": True, "priority": "high",
        "next_actions": "תזכורת נשלחה 10/07 ל-growth@airalo.com (CC Guy) על המייל מ-05/07 (אישור בקשת Impact + deep links + Sub-ID למלונות + נכסי מותג). ממתינים לתשובה; אם שקט עד ~17/07 - תזכורת נוספת או בדיקת סטטוס בדשבורד Impact (acct 7205658).",
        "notes": "מופיע כממומן (כפתור רכישה) אך הלינק הוא דף הבית ללא tracking - כרגע לא מזכה. ציר זמן: בקשת partners.airalo.com (מס' 16367) נסגרה 24/06 בסיבה 'Interested in Affiliate' (ניתוב למסלול אפיליאייט, לא דחייה עניינית); Guy ענה 05/07 בלי הפניה חמה - ביקש לפנות ישירות ל-growth@airalo.com; תשובה נשלחה 05/07 באותו שרשור (To growth@, CC Guy) עם כל ההקשר; תזכורת נשלחה 10/07 (To growth@, CC Guy) - עדיין אין מענה.",
    },
    {
        "provider_id": "ubigi", "display_name": "Ubigi", "category": "global",
        "outreach_status": "approved", "outreach_last_at": "2026-07-03",
        "contact": "cynthia.razafindrakoto@transatel.com", "program_network": "Impact",
        "agreement_status": "live", "commission_pct": 10,
        "commission_note": "10% על רכישה ראשונה, cookie 60 יום (Impact acct 7205658).",
        "coupon_note": "קוד MOCA חי (10% הנחה ללקוח חדש, 60 יום עמלה) - אושר במייל מ-Cynthia 2026-07-09, נזרע ב-seed_coupons (#303). לינק tracking עודכן ל-go.ubigi.com/5kqGL1 (הלינק הרשמי שסיפקה Cynthia, מחליף את MKgJG3 שנוצר עצמאית) - /go/ubigi מאומת 302.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "הושלם - קופון + לינק רשמי חוברו ואומתו 2026-07-10. אין פעולה פתוחה.",
        "notes": "כבר ספק נסרק. Sub-ID לכל מלון + deep links אושרו כאפשריים (מייל Cynthia 07-09: Shared ID field ב-Impact). לינק שני (go.ubigi.com/vDWBGO) נוצר 07-03 = כפול (אותו acct 7205658); הוחלף 07-10 בלינק הרשמי 5kqGL1 שסיפקה Cynthia ישירות. Deep-links פר-יעד (03/07): נוצרו ב-Impact 14 TrackingLinks ליעדים המובילים (cellulardata.ubigi.com/...?destination=<iso3>) וחוברו ב-app.py (_UBIGI_DEST_DEEPLINKS, מפתח לפי dest); /go/ubigi?dest= מוביל לעמוד היעד עם attribution (utm_source=7205658), שאר היעדים נופלים ללינק הגנרי. מאומת 14/14. הורחב 07-10 ב-3 יעדים נוספים (אירופה MKkqe2, קנדה DWq6xa, גלובלי L05LkL - נוצרו ב-Impact Create-a-Link, מאומתים 302 עם utm_source=7205658), עכשיו 17/17 בכיסוי מלא כמו Voye. מייל 07-09 גם צירף לוגו (שחור/לבן) - שחור חובר 07-10 (public/logos/ubigi.svg, providerLogos.js + carrierMeta.js, גודל אייקון בכרטיסיות הוגדל 15% ל-37px). ה-'API docs' שצורף הוא לא API עצמאי של Ubigi - זה מדריך ליצירת access token ל-Impact Product Catalog API (מוגבל 200 מוצרים/קריאה, catalog ID 19558 EN/USD); scrape_ubigi_global שלנו כבר סורק ישירות מול ה-WooCommerce Store API הציבורי של cellulardata.ubigi.com בלי אימות ובלי הגבלת עמוד, אז זה לא משפר את הסריקה. ערך אפשרי עתידי: ה-Impact catalog כולל URLs עם attribution מובנה לכל מוצר, מה שיכול להחליף את ה-14 deep-links הידניים בכיסוי מלא - לא דחוף, טעון הקמת access token.",
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
        "outreach_status": "approved", "outreach_last_at": "2026-07-06",
        "contact": "georgia.ellison@lotusflare.com (Affiliate Manager UK & EMEA, LotusFlare)", "program_network": "Impact",
        "agreement_status": "signed", "commission_pct": 15,
        "commission_note": "החוזה אושר 06/07, נכנס לתוקף 07/07 10:00 EEST (=שעון ישראל). Online Sale: 15% ללקוח חדש / 10% ללקוח קיים (all-other 15%), USD. Last-click, cookie 30 יום. גם iOS In-App Sale 10-15%. Impact acct 7205658, program 34279.",
        "coupon_note": "אין קוד עדיין. Georgia ביקשה לדון ב-next steps (קוד MOCA + deep-links) אחרי שנשלים את ה-setup.",
        "has_tracking_link": False, "priority": "high",
        "next_actions": "תלוי-זמן: החוזה פעיל מ-07/07 10:00 שעון ישראל בלבד - עד אז Nomad לא מופיע ב-'Create a link' של Impact ואי אפשר לייצר tracking link. מ-07/07 10:00: 1) לייצר tracking link ל-Nomad (nomadesim.pxf.io/…, landing = www.nomadesim.com). 2) לחווט config.json affiliate.nomad = {tag 7205658, base_url} → /go/nomad מזכה (בלי שינוי app.py). 3) להוסיף nomad ל-AFFILIATE_PROVIDERS/AFFILIATE_URLS (affiliateLinks.js) + rebuild לכפתור בדשבורד. 4) לענות ל-Georgia שהושלם setup + לתאם קוד MOCA + אחוז הנחה ללקוח + deep-links + Sub-ID למלונות.",
        "notes": "כבר ספק נסרק (כרטיס מידע בלבד עד חיווט tracking). ציר זמן: פנייה 27/06 → דחייה אוטומטית ('quality issue with media property'); media-pack 30/06 → Georgia הרחיבה הצעה 06/07. 06/07 Alon אישר את החוזה ב-Impact; אומת בדשבורד שהחוזה מופיע תחת 'Upcoming contract changes' עם 'The contract takes effect on July 7, 2026, 10:00 EEST' → מאושר, נכנס לתוקף מחר. תנאים נצפו ישירות בדף החוזה (15%/10%, 30 יום). הקישור לא ניתן ליצירה היום כי החוזה עדיין לא פעיל.",
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
        "outreach_status": "contacted", "outreach_last_at": "2026-07-10",
        "contact": "info@esim.io (Desk360 #91126 + טופס אתר 10/07)", "program_network": "לא ידוע",
        "agreement_status": "pending", "commission_pct": None,
        "commission_note": "טרם נמסרו תנאים.",
        "coupon_note": "טופס שותפות (Google Form) הוגש 01/07; ממתין לתשובת partnerships.",
        "has_tracking_link": False, "priority": "low",
        "next_actions": "להמתין לתשובת צוות השותפויות; אם שקט עד ~24/07 - תזכורת נוספת.",
        "notes": "כבר ספק נסרק. 01/07 טופס Google Form הוגש (Desk360 #91126). 10/07 פנייה נוספת דרך טופס יצירת קשר באתר (Subject: Affiliate program) - נשלחה בהצלחה.",
    },

    # ══ COLD OUTREACH SENT — awaiting reply (2026-06-30 batch) ════════════════
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
        "outreach_status": "not_contacted", "outreach_last_at": "2026-07-03",
        "contact": "support@esim70.com (לא תקין - bounce)", "program_network": "אין",
        "agreement_status": "none",
        "coupon_note": "הפנייה הקרה מ-30/06 לא הגיעה: bounce סופי 03/07 אחרי 3 ימי ניסיונות (השרת דחה). בפועל לא נוצר קשר.",
        "priority": "low", "next_actions": "למצוא ערוץ קשר חלופי (טופס/צ'אט באתר esim70.com) ולשלוח שוב.",
        "notes": "כבר ספק נסרק.",
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
        "is_israeli": True, "outreach_status": "contacted", "outreach_last_at": "2026-07-03",
        "contact": "support@tasim.us", "program_network": "לא ידוע",
        "agreement_status": "none", "coupon_note": "מייל אפילייט בעברית נשלח 03/07 (קופון MOCA + tracking/Sub-ID + דיפ-לינקים + תנאי עמלה); ממתין.",
        "priority": "low", "next_actions": "מעקב; אם אין מענה תוך כשבוע - תזכורת.",
        "notes": "נישת ארה\"ב לישראלים. כבר ספק נסרק.",
    },
    {
        "provider_id": "bestconnect", "display_name": "Best Connect", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-07-06",
        "contact": "info@bestconnect.online (מאומת) + טופס שותפים bestconnect.online/corporate-contact",
        "program_network": "עצמאי (in-house partner console)",
        "agreement_status": "none", "commission_pct": None,
        "commission_note": "לא פורסם אחוז (rev-share/fixed); נשאל בפנייה.",
        "coupon_note": "נרשמנו דרך תוכנית האפיליאייט שלהם (03/07); לא ענו למייל, אז נשלחה פנייה 2 דרך טופס corporate-contact (מסלול Affiliates) 06/07 - ממתין לתגובה. (ה-403 הקודם היה חסימת בוטים, לא אתר מת - הכתובת מאומתת.)",
        "priority": "med", "next_actions": "פנייה 2 נשלחה 06/07 דרך טופס השותפים כי לא ענו למייל; ביקשנו לינק tracking + תנאי עמלה + קוד MOCA. אם שקט עד ~13/07 - תזכורת / ערוץ אחר.",
        "notes": "Best Connect Online, LLC (ניו יורק/דלאוור; תפעול כנראה איסטנבול). כבר ספק נסרק. 06/07: מולא ונשלח טופס corporate-contact (Affiliates) כ-follow-up לאי-מענה למייל.",
    },

    # ── bounced / need a valid contact ──
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
        "outreach_status": "contacted", "outreach_last_at": "2026-07-11",
        "contact": "partnerships.mkt@holafly.com (הופנינו לכאן ע\"י צוות ה-Affiliate; לפני כן: Impact dashboard)", "program_network": "Impact",
        "agreement_status": "none", "commission_pct": None,
        "commission_note": "אין הסכם פעיל (הוגש ב-Impact 06-13, ללא אישור).",
        "coupon_note": "3 קופוני צד-ג' (ADAMANDLINDS וכו') הושבתו 07-03 - כבר לא מרונדרים. אין קוד MOCA משלנו עד לחוזה.",
        "has_tracking_link": False, "is_leak": False, "priority": "med",
        "next_actions": "בוצע ניקוי הדליפה (11/07): holafly ירד מ-AFFILIATE_PROVIDERS + הוסר בלוק ה-?ref המזויף מ-config → עכשיו כרטיס מידע בלבד. ממתינים לתשובת partnerships.mkt@holafly.com; אם שקט עד ~18/07 תזכורת. אם יאשרו חוזה - לחווט לינק Impact אמיתי + קוד MOCA ולהחזיר את holafly ל-AFFILIATE_PROVIDERS.",
        "notes": "10/07 - צוות ה-Affiliate החזיר את מייל המעקב (30/06) כ'מחלקה לא נכונה' והפנה ל-partnerships.mkt@holafly.com. 11/07 - נשלח מעקב ממוען מחדש לכתובת הנכונה. 11/07 - נוקתה הדליפה: holafly ירד מ-AFFILIATE_PROVIDERS/URLS (נפרס ל-Netlify, chunk PlanCard-uWxE5ZeK, fingerprint main-D3F6MnW8) + הוסר בלוק ה-?ref המזויף מ-config.json (/go/holafly → esim.holafly.com/esim-israel/ אמיתי) + 3 קופוני צד-ג' מושבתים ב-DB. אפס דליפה - כרטיס מידע בלבד.",
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
        "outreach_status": "live", "outreach_last_at": "2026-07-08",
        "contact": "Alex Dufort (Head of Partnerships)", "program_network": "Everflow",
        "agreement_status": "live", "commission_pct": 15,
        "commission_note": "15% revshare על רכישות; בנוסף CPA: GigSky One $25, VISA benefit $4, תוכנית חינם $3.",
        "coupon_note": "קוד MOCA15 (15% הנחה) אושר ופעיל (Alex, 06/07). Sub-ID נתמך דרך תיבת ה-vanity ב-Everflow.",
        "has_tracking_link": True, "priority": "med",
        "next_actions": "מסמך ה-deep-link התקבל 08/07. פתוח (בצד שלנו): להטמיע נחיתה פר-מדינה - gigskyapp://home/explore?serviceRegionId=<ISO>&category=Countries עטוף ב-Singular smart-link (gigsky.sng.link/Euypu/<id>) - ולוודא ששמירת ה-attribution ב-Everflow נשמרת (url override / הפניית לינק Everflow ל-sng.link עם המאקרו). לשים לב: זה deep-link לאפליקציה (לא web), לברר עם Alex fallback ל-web/דסקטופ. להשלים Billing ב-Everflow.",
        "notes": "ספק נסרק (1698 חבילות, מופיע בהשוואת eSIM). קופון MOCA15 הוטמע (seed_coupons.py). לינק Everflow חובר 06/07 (plans.gigsky.com/273MKQ4/2CTPL/, aff 273MKQ4 offer 2CTPL); /go/gigsky מצרף sub1=יעד(ISO)/sub2=src/sub5=hotel, מאומת חי. גישה לתיקיית assets אושרה 06/07. פתוח: להשלים Billing ב-Everflow (Company Settings). 08/07: Alex שיתף Google Doc 'how to Deeplink capability'. הפורמט = Singular smart-link https://gigsky.sng.link/Euypu/<id>?_dl=<urlencoded gigskyapp://...>&_forward_params=2&_smtype=3; מדינה = gigskyapp://home/explore?serviceRegionId=<CountryCode>&category=Countries (serviceRegionId=קוד ISO למדינה; PlanBundleId לאזורי/עולמי). Everflow מזריק מאקרו דינמי (affiliate_id/transaction_id/offer_id) בתוך ה-sng.link. 10/07: נסגר פער בפרונט - gigsky היה חסר ב-affiliateLinks.js (AFFILIATE_PROVIDERS+AFFILIATE_URLS), כך שכפתור הרכישה בכרטיס הדשבורד נפל ל-gigsky.com ללא attribution (דלף רק בדשבורד; B2C/‏go תמיד עבד). נוסף, נבנה ונפרס לאוויר (fingerprint main-Djz6BYUq.js, chunk PlanCard-BrtWeYZJ.js מאומת חי).",
    },
    {
        "provider_id": "nisim", "display_name": "Nisim eSIM", "category": "global",
        "is_israeli": True,
        "outreach_status": "contacted", "outreach_last_at": "2026-07-11",
        "contact": "טופס יצירת קשר באתר (nisim-esim.co.il/צור-קשר); אין מייל פומבי. וואטסאפ עסקי: 054-5051525, טלפון: 073-4730730",
        "agreement_status": "none",
        "coupon_note": "אין קופון. תוכנית שותפים בבירור (נשאל בפנייה).",
        "has_tracking_link": False, "priority": "med",
        "next_actions": "נשלחה פניית שיתוף פעולה דרך טופס יצירת הקשר (11/07, אושר 'השליחה בוצעה בהצלחה') - להמתין לחזרה במייל/טלפון; אם שקט עד ~20/07, פנייה בוואטסאפ העסקי.",
        "notes": "ספק ישראלי (נוסף 11/07/2026): חנות WooCommerce, ~489 חבילות ILS, ~90 מדינות + 11 מוצרים אזוריים/גלובליים (סריקת Store API טהורה, כולל וריאציות עם תוויות עברית 'ימים:'). מסונן: מוצרי TEST + מבצעי משפחה מרובי-קווים. כתובת: אריאל שרון 4, גבעתיים.",
    },
    {
        "provider_id": "esimgenius", "display_name": "eSIM Genius", "category": "global",
        "outreach_status": "contacted", "outreach_last_at": "2026-07-11",
        "contact": "hello@esimgenius.ai",
        "agreement_status": "none",
        "coupon_note": "אין קופון. תוכנית שותפים בבירור (נשאל במייל).",
        "has_tracking_link": False, "priority": "med",
        "next_actions": "מייל היכרות נשלח ל-hello@esimgenius.ai (11/07) - שיתוף פעולה / לינק מעקב / קופון MOCA. להמתין לתשובה; אם שקט עד ~18/07, מייל תזכורת.",
        "notes": "ספק נסרק (נוסף 11/07/2026): ~2,580 חבילות, ~180 מדינות + 5 חבילות אזוריות/גלובליות (esimgenius.ai, Next.js, סריקת HTTP טהורה מה-RSC). מחירים בדולר, כולל מסלולי ללא הגבלה. אין עמוד עברית ייעודי אבל האתר מתורגם (he/). אתר חדש יחסית (sitemap מ-06/2026).",
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
