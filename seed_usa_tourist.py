"""Seed usa_tourist_plans — US operators selling prepaid plans an INCOMING
TOURIST can buy (powers the "נוחתים בארה"ב" tab).

Researched live, June 2026 (3 parallel web-research passes). Prices are the
upfront FIRST-MONTH single-line USD price BEFORE any AutoPay discount (the
amount a 1-4 week visitor actually pays); AutoPay/promo prices are noted in the
Hebrew extras bullets. Each plan stores original_price (USD) + currency 'USD';
`price` is the live USD→ILS conversion (matches the global_plans convention so
PlanCard shows ₪ as the headline and "$X" underneath).

Scope = US carriers + MVNOs where a foreigner can activate WITHOUT a US
SSN/ID/credit-check (passport in-store, or eSIM/SIM-kit online). The two genuine
TOURIST-DEDICATED products are flagged "⭐ חבילת תיירים ייעודית":
  - T-Mobile U.S. Pass eSIM (launched 2026-05-18 — first Big-3 visitor product
    since the old $30 Tourist Plan; buy + activate inside the US only)
  - Ultra Mobile Tourist 21-Day (one-time, non-renewable, ZIP-code activation)

Israel angle: h2o Wireless includes UNLIMITED calling to Israel on every plan —
the standout for Israeli visitors. Verizon Unlimited Plus (Global Choice) and
T-Mobile Unlimited Plus (intl texting to 215+) also reach Israel.

SEEDED 2026-06-11 (2nd research pass): Mint, Tello, Metro, Lycamobile USA,
Simple Mobile. NOTE: Simple Mobile now runs on the VERIZON network (Tracfone →
Verizon "Verizon Value" relaunch), NOT T-Mobile. Lyca USA + Simple Mobile both
include UNLIMITED calling to Israel on every plan (the Israeli-visitor angle).
Out of scope here: the pre-arrival tourist-eSIM resellers (WorldSIM/SimCorner/
Simify/ETravelSim/ESIMUSA) and airport kiosks (TripTel@SFO, SIMs-on-the-Go@JFK) —
they resell T-Mobile/AT&T local service and overlap MOCA's existing global-eSIM tab.

Re-runnable: UPSERTs by (carrier, plan_name).
"""
from db import init_db, save_usa_tourist_plans


# original_price = upfront first-month USD; data_gb: None = unlimited, else GB.
# minutes/sms left None — "unlimited US calls/text" is conveyed in the extras
# bullets so the info line stays clean (GB · validity).
PLANS = [
    # ─────────────────────────────────────────────────────────────────────
    # T-Mobile Prepaid — the most tourist-friendly Big-3 carrier.
    #   U.S. Pass = the purpose-built visitor eSIM line (no ID, no auto-renew,
    #   buy+activate inside the US; activates the moment you buy → buy on arrival).
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "U.S. Pass 7-Day eSIM", "original_price": 25.0,
        "data_gb": None, "days": 7, "esim": True,
        "extras": [
            "⭐ חבילת תיירים ייעודית (הושקה 5/2026)",
            "גלישה ללא הגבלה ב-5G (50GB מהיר ואז מהירות מופחתת)",
            "נקודה חמה (Hotspot): 14GB",
            "שיחות ו-SMS ללא הגבלה בארה\"ב, מקסיקו וקנדה",
            "eSIM בלבד · ללא תעודה אמריקאית · ללא חידוש אוטומטי",
            "לרכישה והפעלה רק בתוך ארה\"ב (כרטיסי אשראי זרים נתמכים חלקית)",
        ],
        "source_url": "https://prepaid.t-mobile.com/prepaid-plans/esim-usa-travel-plans",
    },
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "U.S. Pass 10-Day eSIM", "original_price": 30.0,
        "data_gb": None, "days": 10, "esim": True,
        "extras": [
            "⭐ חבילת תיירים ייעודית (הושקה 5/2026)",
            "גלישה ללא הגבלה ב-5G (50GB מהיר ואז מהירות מופחתת)",
            "נקודה חמה (Hotspot): 20GB",
            "שיחות ו-SMS ללא הגבלה בארה\"ב, מקסיקו וקנדה",
            "eSIM בלבד · ללא תעודה אמריקאית · ללא חידוש אוטומטי",
        ],
        "source_url": "https://prepaid.t-mobile.com/prepaid-plans/esim-usa-travel-plans",
    },
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "U.S. Pass 14-Day eSIM", "original_price": 35.0,
        "data_gb": None, "days": 14, "esim": True,
        "extras": [
            "⭐ חבילת תיירים ייעודית (הושקה 5/2026)",
            "גלישה ללא הגבלה ב-5G (50GB מהיר ואז מהירות מופחתת)",
            "נקודה חמה (Hotspot): 28GB",
            "שיחות ו-SMS ללא הגבלה בארה\"ב, מקסיקו וקנדה",
            "eSIM בלבד · ללא תעודה אמריקאית · ללא חידוש אוטומטי",
        ],
        "source_url": "https://prepaid.t-mobile.com/prepaid-plans/esim-usa-travel-plans",
    },
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "U.S. Pass 30-Day eSIM", "original_price": 50.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "⭐ חבילת תיירים ייעודית (הושקה 5/2026)",
            "גלישה ללא הגבלה ב-5G (50GB מהיר ואז מהירות מופחתת)",
            "נקודה חמה (Hotspot): 50GB",
            "שיחות ו-SMS ללא הגבלה בארה\"ב, מקסיקו וקנדה + 5GB במקסיקו/קנדה",
            "eSIM בלבד · ללא תעודה אמריקאית · כולל הטבות T-Mobile Tuesdays",
        ],
        "source_url": "https://prepaid.t-mobile.com/prepaid-plans/esim-usa-travel-plans",
    },
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "Connect by T-Mobile 8GB", "original_price": 25.0,
        "data_gb": 8, "days": 30, "esim": False,
        "extras": [
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "החבילה הזולה ברשת ארצית גדולה",
            "נמכרת כ-SIM פיזי (לא eSIM); ללא תעודה אמריקאית",
            "תוספות בתשלום: מקסיקו/קנדה $5, חיוג בינ\"ל $15",
            "לא כולל המחיר מסים ואגרות",
        ],
        "source_url": "https://prepaid.t-mobile.com/connect",
    },
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "Connect by T-Mobile 12GB", "original_price": 35.0,
        "data_gb": 12, "days": 30, "esim": False,
        "extras": [
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נמכרת כ-SIM פיזי (לא eSIM); ללא תעודה אמריקאית",
            "עדיפות רשת נמוכה יותר מחבילות T-Mobile הרגילות",
            "לא כולל המחיר מסים ואגרות",
        ],
        "source_url": "https://prepaid.t-mobile.com/connect",
    },
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "T-Mobile Prepaid Unlimited", "original_price": 55.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (50GB מהיר ואז מהירות מופחתת)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה במהירות 3G",
            "$50 לחודש ב-AutoPay (חודש ראשון $55 + מסים)",
            "ניתן להפעלה כ-eSIM ללא תעודה אמריקאית",
        ],
        "source_url": "https://prepaid.t-mobile.com/prepaid-plans",
    },
    {
        "carrier": "tmobile_prepaid", "network": "T-Mobile",
        "plan_name": "T-Mobile Prepaid Unlimited Plus", "original_price": 65.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (50GB מהיר)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "SMS ללא הגבלה ל-215+ מדינות — כולל ישראל",
            "שיחות ללא הגבלה למקסיקו וקנדה",
            "נקודה חמה (Hotspot): 5GB מהיר",
            "$60 לחודש ב-AutoPay (חודש ראשון $65 + מסים)",
        ],
        "source_url": "https://prepaid.t-mobile.com/prepaid-plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # AT&T Prepaid — no tourist SKU, but open to visitors (passport in-store,
    # no SSN/credit check). Flat "+tax" pricing, NO AutoPay discount since the
    # Nov-2024 refresh. Foreign cards often fail online → buy in-store / SIM kit.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "att_prepaid", "network": "AT&T",
        "plan_name": "AT&T Prepaid Unlimited Saver", "original_price": 35.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (30GB עד 3Mbps ואז 1.5Mbps)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "SMS ללא הגבלה ל-230+ מדינות — כולל ישראל",
            "מחיר שטוח $35 + מסים (אין משחקי AutoPay)",
            "ניתן לקנות בחנות/ערכת SIM ללא תעודה אמריקאית",
        ],
        "source_url": "https://www.att.com/prepaid/plans/",
    },
    {
        "carrier": "att_prepaid", "network": "AT&T",
        "plan_name": "AT&T Prepaid Unlimited Enhanced Plus", "original_price": 45.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה במהירות מלאה (האטה בעומס)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 10GB מהיר",
            "25GB גלישה במקסיקו וקנדה",
            "SMS ללא הגבלה ל-230+ מדינות כולל ישראל",
            "הבחירה המשתלמת של AT&T לתייר עתיר-גלישה",
        ],
        "source_url": "https://www.att.com/prepaid/plans/",
    },
    {
        "carrier": "att_prepaid", "network": "AT&T",
        "plan_name": "AT&T Prepaid Unlimited Ultra", "original_price": 60.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה שלעולם לא מואטת (Premium)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 30GB מהיר",
            "500 דקות חיוג ל-30+ מדינות + SMS ל-230+",
            "25GB במקסיקו/קנדה · סטרימינג 4K",
            "מחיר שטוח $60 + מסים",
        ],
        "source_url": "https://www.att.com/prepaid/plans/",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Verizon Prepaid — strongest rural/national-park coverage. Catch for
    # tourists: the $10 AutoPay discount only kicks in from month 2, so a
    # 1-month visitor always pays the higher first-month price (shown here).
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "verizon_prepaid", "network": "Verizon",
        "plan_name": "Verizon Prepaid 15GB", "original_price": 45.0,
        "data_gb": 15, "days": 30, "esim": True,
        "extras": [
            "15GB ב-5G Nationwide",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה כלולה (מתוך ה-15GB)",
            "שימוש במקסיקו וקנדה כלול (2GB/יום מהיר)",
            "חודש ראשון $45; יורד ל-$35 רק עם AutoPay מחודש 2",
            "תשלום eSIM: כרטיס אמריקאי / Apple Pay / PayPal",
        ],
        "source_url": "https://www.verizon.com/plans/prepaid/",
    },
    {
        "carrier": "verizon_prepaid", "network": "Verizon",
        "plan_name": "Verizon Prepaid Unlimited", "original_price": 60.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה ב-5G Nationwide",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה: 5GB ואז 600Kbps",
            "מקסיקו וקנדה כלולות",
            "חודש ראשון $60; $50 עם AutoPay מחודש 2",
        ],
        "source_url": "https://www.verizon.com/plans/prepaid/",
    },
    {
        "carrier": "verizon_prepaid", "network": "Verizon",
        "plan_name": "Verizon Prepaid Unlimited Plus", "original_price": 70.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה כולל 5G Ultra Wideband (50GB Premium)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 25GB מהיר",
            "Global Choice — 180 דק'/חודש למדינה נבחרת (ישראל ברשימה)",
            "חודש ראשון $70; $60 עם AutoPay מחודש 2",
        ],
        "source_url": "https://www.verizon.com/plans/prepaid/",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Cricket Wireless (AT&T-owned) — 5,000+ stores; in-store cash purchase is
    # the easiest path for visitors. Taxes/fees INCLUDED in the price.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "cricket", "network": "AT&T",
        "plan_name": "Cricket Sensible 10GB", "original_price": 35.0,
        "data_gb": 10, "days": 30, "esim": True,
        "extras": [
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "מסים ואגרות כלולים במחיר",
            "128Kbps אחרי 10GB",
            "רכישה במזומן בחנות — הנוחה ביותר לתיירים",
        ],
        "source_url": "https://www.cricketwireless.com/cell-phone-plans",
    },
    {
        "carrier": "cricket", "network": "AT&T",
        "plan_name": "Cricket Smart Unlimited", "original_price": 50.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (האטה אפשרית בעומס)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 15GB",
            "SMS ל-200+ מדינות (חיוג לישראל דורש תוספת)",
            "מסים ואגרות כלולים במחיר",
        ],
        "source_url": "https://www.cricketwireless.com/cell-phone-plans",
    },
    {
        "carrier": "cricket", "network": "AT&T",
        "plan_name": "Cricket Supreme Unlimited", "original_price": 60.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה במהירות מלאה (העדיפות הגבוהה של Cricket)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 50GB",
            "כולל HBO Max Basic",
            "מסים ואגרות כלולים במחיר",
        ],
        "source_url": "https://www.cricketwireless.com/cell-phone-plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # h2o Wireless (AT&T network) — THE standout for Israeli visitors: every
    # plan includes UNLIMITED international calling to 100+ countries incl.
    # Israel. eSIM available, foreign cards generally accepted, ships abroad.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "h2o", "network": "AT&T",
        "plan_name": "h2o $20 Monthly", "original_price": 20.0,
        "data_gb": 3, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות בינ\"ל ללא הגבלה ל-100+ מדינות כולל ישראל",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 2GB",
            "ערך מצוין לתייר בשימוש קל",
            "ניתן להפעלה כ-eSIM; כרטיסי אשראי זרים מתקבלים בד\"כ",
        ],
        "source_url": "https://www.h2owireless.com/plan/monthly",
    },
    {
        "carrier": "h2o", "network": "AT&T",
        "plan_name": "h2o $30 Monthly", "original_price": 30.0,
        "data_gb": 10, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות בינ\"ל ללא הגבלה ל-100+ מדינות כולל ישראל",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 5GB",
            "נקודת המתיקות לביקור של 2-4 שבועות עם שיחות הביתה",
            "ניתן להפעלה כ-eSIM; נשלח גם לחו\"ל דרך משווקים",
        ],
        "source_url": "https://www.h2owireless.com/plan/monthly",
    },
    {
        "carrier": "h2o", "network": "AT&T",
        "plan_name": "h2o $40 Monthly", "original_price": 40.0,
        "data_gb": 20, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות בינ\"ל ללא הגבלה ל-100+ מדינות כולל ישראל",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "20GB מהיר ואז 256Kbps",
            "ניתן להפעלה כ-eSIM",
        ],
        "source_url": "https://www.h2owireless.com/plan/monthly",
    },
    {
        "carrier": "h2o", "network": "AT&T",
        "plan_name": "h2o $50 Unlimited", "original_price": 50.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות בינ\"ל ללא הגבלה ל-100+ מדינות כולל ישראל",
            "גלישה ללא הגבלה (60GB מהיר ואז מהירות מופחתת)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "~$10 קרדיט בינ\"ל ליעדים בתשלום-לדקה",
        ],
        "source_url": "https://www.h2owireless.com/plan/monthly",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Visible (Verizon-owned, eSIM-first, online-only). WEAK fit for foreigners:
    # requires a US payment method (foreign cards rejected; workaround
    # PayPal/Venmo/US gift card). Taxes included. Flagged in bullets.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "visible", "network": "Verizon",
        "plan_name": "Visible", "original_price": 25.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (עדיפות רגילה ברשת Verizon)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה ללא הגבלה עד 5Mbps",
            "מסים ואגרות כלולים — $25 הכל-כלול",
            "⚠️ דורש אמצעי תשלום אמריקאי (PayPal/Venmo כעקיפה)",
        ],
        "source_url": "https://www.visible.com/plans",
    },
    {
        "carrier": "visible", "network": "Verizon",
        "plan_name": "Visible+ Pro", "original_price": 45.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה ב-5G Ultra Wideband (Premium)",
            "שיחות ל-85+ מדינות (500 דק'/חודש) + SMS ל-200+",
            "נקודה חמה ללא הגבלה עד 15Mbps",
            "וידאו 4K · מסים כלולים",
            "⚠️ דורש אמצעי תשלום אמריקאי",
        ],
        "source_url": "https://www.visible.com/plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # US Mobile — best fully-online option: instant eSIM + a 30-day FREE trial
    # eSIM to test coverage, choice of all 3 networks (Warp=Verizon,
    # LightSpeed=T-Mobile, DarkStar=AT&T). Prices exclude ~$2-4 tax.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "us_mobile", "network": "Verizon / T-Mobile / AT&T",
        "plan_name": "US Mobile Unlimited Starter", "original_price": 22.5,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (בחירת רשת: Verizon / T-Mobile / AT&T)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב + שיחות/SMS בינ\"ל",
            "נקודה חמה (Hotspot): 20GB + 1GB גלישה בינ\"ל",
            "eSIM מיידי + ניסיון חינם ל-30 יום לבדיקת כיסוי",
            "ללא תעודה אמריקאית (נדרש מיקוד אמריקאי ל-E911)",
        ],
        "source_url": "https://www.usmobile.com/plans",
    },
    {
        "carrier": "us_mobile", "network": "Verizon / T-Mobile / AT&T",
        "plan_name": "US Mobile Unlimited Premium", "original_price": 32.5,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה בעדיפות עליונה (בחירת רשת)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב + בינ\"ל",
            "נקודה חמה ללא הגבלה + 20GB גלישה בינ\"ל",
            "כולל eSIM גלישה בינ\"ל חינם ליעדים רבים",
            "eSIM מיידי · ללא תעודה אמריקאית",
        ],
        "source_url": "https://www.usmobile.com/plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Red Pocket — choice of all 3 networks, same price. No setup/activation
    # fees, no US ID. Amazon/eBay kit purchase is the clean foreign-card route.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "red_pocket", "network": "AT&T / T-Mobile / Verizon",
        "plan_name": "Red Pocket Plus 20GB", "original_price": 20.0,
        "data_gb": 20, "days": 30, "esim": True,
        "extras": [
            "20GB ב-5G (בחירת רשת מבין השלוש)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "שיחות בינ\"ל ללא הגבלה ל-20+ מדינות · נדידה ב-60+",
            "יחס מחיר/GB מצוין לביקור חודשי",
            "רכישה דרך Amazon/eBay עוקפת חסימת כרטיס זר",
        ],
        "source_url": "https://blog.redpocket.com/blog/2026-prepaid-cell-phone-plan-guide-costs-features-and-savings",
    },
    {
        "carrier": "red_pocket", "network": "AT&T / T-Mobile / Verizon",
        "plan_name": "Red Pocket Premium Unlimited", "original_price": 30.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (50GB Premium ב-5G)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "שיחות בינ\"ל ללא הגבלה ל-80+ מדינות",
            "נקודה חמה (Hotspot): 10GB",
        ],
        "source_url": "https://blog.redpocket.com/blog/2026-prepaid-cell-phone-plan-guide-costs-features-and-savings",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Straight Talk (Verizon / Tracfone) — the Walmart cash route is the
    # visitor-proof path: $1 SIM kit + refill card, activate with any US ZIP.
    # Prices EXCLUDE taxes. Rebranded Bronze/Silver/Gold/Platinum (Apr 2026).
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "straight_talk", "network": "Verizon",
        "plan_name": "Straight Talk Silver Unlimited", "original_price": 45.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (ללא Premium)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "שיחות ללא הגבלה למקסיקו וקנדה",
            "נקודה חמה (Hotspot): 10GB",
            "נמכרת בכל Walmart — הפעלה במזומן ללא תעודה",
        ],
        "source_url": "https://www.straighttalk.com/all-plans",
    },
    {
        "carrier": "straight_talk", "network": "Verizon",
        "plan_name": "Straight Talk Gold Unlimited", "original_price": 55.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה בעדיפות (Premium)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 30GB",
            "כולל מנוי Walmart+ · וידאו 1080p",
            "נמכרת בכל Walmart",
        ],
        "source_url": "https://www.straighttalk.com/all-plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Total Wireless (Verizon) — taxes INCLUDED. Cash SIM kit at Walmart/Target.
    # All plans: unlimited intl calling to 85+, texting to 200+, free MX/CA.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "total_wireless", "network": "Verizon",
        "plan_name": "Total Base 5G Unlimited", "original_price": 40.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה ב-5G",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "שיחות בינ\"ל ללא הגבלה ל-85+ יעדים · SMS ל-200+",
            "נקודה חמה (Hotspot): 5GB · נדידה במקסיקו/קנדה",
            "מסים ואגרות כלולים במחיר",
        ],
        "source_url": "https://www.totalwireless.com/plans",
    },
    {
        "carrier": "total_wireless", "network": "Verizon",
        "plan_name": "Total 5G Unlimited", "original_price": 55.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה כולל 5G Ultra Wideband (Premium)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "שיחות בינ\"ל ל-85+ יעדים · SMS ל-200+",
            "נקודה חמה (Hotspot): 15GB",
            "$50 ב-AutoPay · מסים כלולים · 6 חודשי Disney+",
        ],
        "source_url": "https://www.totalwireless.com/plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Boost Mobile (Boost native 5G + AT&T roaming). Online eSIM activation, no
    # store/US-ID needed. Global Connection = the visitor tier for calling home.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "boost", "network": "Boost 5G + AT&T",
        "plan_name": "Boost Unlimited", "original_price": 25.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (30GB Premium ואז 512Kbps)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "החבילה הזולה של מותג גדול",
            "הפעלת eSIM אונליין ללא תעודה אמריקאית",
        ],
        "source_url": "https://www.boostmobile.com/plans/prepaid-plans",
    },
    {
        "carrier": "boost", "network": "Boost 5G + AT&T",
        "plan_name": "Boost Global Connection", "original_price": 40.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (40GB Premium ואז 512Kbps)",
            "שיחות ו-SMS בינ\"ל ללא הגבלה ל-100+ מדינות",
            "1GB גלישה בנדידה גלובלית",
            "הדרגה של Boost שבנויה לתיירים שמתקשרים הביתה",
            "הפעלת eSIM אונליין ללא תעודה אמריקאית",
        ],
        "source_url": "https://www.boostmobile.com/plans/prepaid-plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Ultra Mobile Tourist (T-Mobile) — a genuine 21-day, one-time,
    # non-renewable tourist SKU. ZIP-code activation, new US number, no credit
    # check. Sold as a physical SIM kit.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "ultra", "network": "T-Mobile",
        "plan_name": "Ultra Mobile Tourist 21-Day", "original_price": 30.0,
        "data_gb": 2, "days": 21, "esim": False,
        "extras": [
            "⭐ חבילת תיירים ייעודית — חד-פעמית, 21 יום, ללא חידוש",
            "מספר טלפון אמריקאי חדש; הפעלה במיקוד אמריקאי בלבד",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "100 דקות בינ\"ל ל-90+ יעדים + SMS בינ\"ל ללא הגבלה",
            "ללא בדיקת אשראי · נמכרת כערכת SIM פיזית",
        ],
        "source_url": "https://www.ultramobile.com/tourist/",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Mint Mobile (T-Mobile network) — sold in 3/6/12-month PREPAID BUNDLES
    # (3-month minimum, paid upfront); the intro per-month rate applies to the
    # first 3 months for new customers, then renews higher. Data tiers were
    # bumped 2026-06-10 (now 6/17/23GB + Unlimited). The 7-day free-trial eSIM
    # is the zero-risk way for a tourist to test coverage on landing. Israel
    # calling is NOT on-plan (UpRoam pay-as-you-go credit, app-only rate).
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "mint", "network": "T-Mobile",
        "plan_name": "Mint 7-Day Free Trial eSIM", "original_price": 0.0,
        "data_gb": 250 / 1024, "days": 7, "esim": True,
        "extras": [
            "⭐ ניסיון חינם — 250MB + 250 דקות + 250 SMS, עד 7 ימים",
            "הדרך האפס-סיכון לבדוק כיסוי T-Mobile מרגע הנחיתה",
            "הפעלת eSIM מיידית דרך אפליקציית Mint (נדרש כרטיס לאימות, מחויב רק אם ממשיכים)",
            "כמות גלישה לבדיקת רשת בלבד — לא חבילת נסיעה",
            "ללא תעודה אמריקאית · כרטיסי אשראי זרים/PayPal מתקבלים",
        ],
        "source_url": "https://www.mintmobile.com/trial-plan-terms-conditions/",
    },
    {
        "carrier": "mint", "network": "T-Mobile",
        "plan_name": "Mint 6GB", "original_price": 15.0,
        "data_gb": 6, "days": 30, "esim": True,
        "extras": [
            "$15 לחודש במחיר היכרות (3 חודשים ראשונים) — $45 מראש ל-3 חודשים",
            "6GB מהיר לחודש ואז 128Kbps",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נמכר במינימום 3 חודשים מראש (הגלישה מתאפסת מדי חודש)",
            "eSIM · ללא תעודה אמריקאית · כרטיס זר/PayPal",
        ],
        "source_url": "https://www.mintmobile.com/plans/",
    },
    {
        "carrier": "mint", "network": "T-Mobile",
        "plan_name": "Mint 17GB", "original_price": 20.0,
        "data_gb": 17, "days": 30, "esim": True,
        "extras": [
            "$20 לחודש במחיר היכרות (3 חודשים ראשונים) — $60 מראש ל-3 חודשים",
            "17GB מהיר לחודש ואז 128Kbps",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה כלולה (מתוך ה-17GB)",
            "נמכר במינימום 3 חודשים מראש · eSIM · ללא תעודה אמריקאית",
        ],
        "source_url": "https://www.mintmobile.com/plans/",
    },
    {
        "carrier": "mint", "network": "T-Mobile",
        "plan_name": "Mint Unlimited", "original_price": 30.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "$30 לחודש במחיר היכרות (3 חודשים ראשונים) — $90 מראש ל-3 חודשים",
            "גלישה ללא הגבלה (עדיפות רשת משנית בעומס)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 20GB",
            "מחיר רגיל לאחר ההיכרות ~$40/חודש · eSIM",
        ],
        "source_url": "https://www.mintmobile.com/plans/",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Tello (T-Mobile network) — flexible BUILD-YOUR-OWN prepaid: pick data +
    # minutes independently, billed monthly, no contract, no credit check.
    # Unlimited US text on every plan. eSIM must be ACTIVATED inside the US.
    # Israel calling is NOT free — pay-as-you-go (landline 2.9¢, mobile 9.5¢).
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "tello", "network": "T-Mobile",
        "plan_name": "Tello 2GB", "original_price": 10.0,
        "data_gb": 2, "days": 30, "esim": True,
        "extras": [
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "בניית חבילה גמישה: בוחרים גלישה + דקות בנפרד (החל מ-$5)",
            "נקודה חמה כלולה (מתוך הגלישה)",
            "eSIM · ללא בדיקת אשראי · PayPal/Apple Pay/Google Pay",
            "⚠️ הפעלת eSIM אפשרית רק מתוך ארה\"ב",
        ],
        "source_url": "https://tello.com/buy/custom_plans",
    },
    {
        "carrier": "tello", "network": "T-Mobile",
        "plan_name": "Tello 5GB", "original_price": 14.0,
        "data_gb": 5, "days": 30, "esim": True,
        "extras": [
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "$10 לחודש הראשון (מחיר היכרות)",
            "5GB גלישה · נקודה חמה כלולה",
            "eSIM · ללא תעודה אמריקאית · ללא בדיקת אשראי",
            "שיחות לישראל בתשלום: קווי 2.9¢/דק', נייד 9.5¢/דק' (לא כלול)",
        ],
        "source_url": "https://tello.com/plans",
    },
    {
        "carrier": "tello", "network": "T-Mobile",
        "plan_name": "Tello Unlimited", "original_price": 25.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (50GB מהיר ואז מהירות מופחתת)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 10GB",
            "$15 לחודש ב-3 החודשים הראשונים (מחיר היכרות)",
            "שיחות חינם ל-60+ מדינות — ישראל לא ברשימה (חיוג בתשלום/WhatsApp)",
        ],
        "source_url": "https://tello.com/buy/esim",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Metro by T-Mobile — T-Mobile's flagship IN-STORE prepaid brand. Walk in
    # with a PASSPORT (no SSN/credit check), cash accepted ($25 in-store
    # activation fee). Taxes & fees INCLUDED in the price. AutoPay needs a US
    # card, so a tourist pays the +$5 first-month rate shown here. eSIM
    # supported (activate inside the US). Israel calling = Global Voice+ add-on.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "metro", "network": "T-Mobile",
        "plan_name": "Metro Unlimited (entry)", "original_price": 30.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה ב-5G",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "$25 לחודש ב-AutoPay (חודש ראשון $30) · מסים ואגרות כלולים במחיר",
            "הפעלה בחנות עם דרכון — ללא תעודה אמריקאית (אגרת הפעלה $25)",
            "eSIM נתמך (הפעלה מתוך ארה\"ב)",
        ],
        "source_url": "https://www.metrobyt-mobile.com/phone-plans",
    },
    {
        "carrier": "metro", "network": "T-Mobile",
        "plan_name": "Metro Unlimited + 10GB Hotspot", "original_price": 35.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה ב-5G",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 10GB",
            "$30 לחודש ב-AutoPay (חודש ראשון $35) · מסים כלולים",
            "הפעלה בחנות עם דרכון · eSIM נתמך",
        ],
        "source_url": "https://www.metrobyt-mobile.com/phone-plans",
    },
    {
        "carrier": "metro", "network": "T-Mobile",
        "plan_name": "Metro Unlimited Best Value", "original_price": 65.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "גלישה ללא הגבלה (5G פרימיום — ללא האטה)",
            "שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 25GB",
            "כולל Amazon Prime + 100GB Google One",
            "SMS בינ\"ל ל-210+ יעדים (שיחות לישראל: תוספת Global Voice+ ב-$20)",
            "$60 לחודש ב-AutoPay (חודש ראשון $65) · מסים כלולים",
        ],
        "source_url": "https://www.metrobyt-mobile.com/phone-plans",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Lycamobile USA (T-Mobile network) — built around INTERNATIONAL CALLING.
    # 🇮🇱 Every national plan ($19+) includes UNLIMITED calls to Israel
    # (landlines + most mobiles) — the standout for an Israeli visitor.
    # Carve-outs: Israeli mobile prefixes 056/059 (97256/97259) are NOT
    # unlimited, and "unlimited" = first 10 unique numbers per country/cycle.
    # eSIM, no SSN/credit check, also sold at airport kiosks.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "lyca_usa", "network": "T-Mobile",
        "plan_name": "Lyca $19 Unlimited Intl", "original_price": 19.0,
        "data_gb": 5, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (קווי + רוב הניידים)",
            "5GB גלישה · שיחות ו-SMS ללא הגבלה בארה\"ב",
            "שיחות ללא הגבלה ל-~100 מדינות + קרדיט בינ\"ל מתנה",
            "חריג ישראל: ניידים 056/059 לא כלולים; 'ללא הגבלה' = עד 10 מספרים שונים למדינה",
            "eSIM · ללא תעודה אמריקאית · זמין גם בקיוסקים בשדה התעופה",
        ],
        "source_url": "https://www.lycamobile.us/en/plan-types/national-plans/",
    },
    {
        "carrier": "lyca_usa", "network": "T-Mobile",
        "plan_name": "Lyca $29 Unlimited Intl", "original_price": 29.0,
        "data_gb": 15, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (קווי + רוב הניידים)",
            "15GB גלישה · שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 10GB · נדידה במקסיקו/קנדה",
            "שיחות ללא הגבלה ל-~100 מדינות",
            "חריג: ניידים ישראליים 056/059 אינם כלולים (חיוג בתשלום)",
        ],
        "source_url": "https://www.lycamobile.us/en/plan-types/national-plans/",
    },
    {
        "carrier": "lyca_usa", "network": "T-Mobile",
        "plan_name": "Lyca $39 High Data Intl", "original_price": 39.0,
        "data_gb": 25, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (קווי + רוב הניידים)",
            "25GB גלישה · שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 10GB · נדידה במקסיקו/קנדה",
            "שיחות ללא הגבלה ל-~100 מדינות",
            "eSIM · ללא תעודה אמריקאית",
        ],
        "source_url": "https://www.lycamobile.us/en/plan-types/national-plans/",
    },
    {
        "carrier": "lyca_usa", "network": "T-Mobile",
        "plan_name": "Lyca $59 Intl", "original_price": 59.0,
        "data_gb": 60, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (קווי + רוב הניידים)",
            "60GB גלישה · שיחות ו-SMS ללא הגבלה בארה\"ב",
            "נקודה חמה (Hotspot): 25GB",
            "שיחות ללא הגבלה ל-85+ מדינות",
            "חריג: ניידים ישראליים 056/059 אינם כלולים; 'ללא הגבלה' = עד 10 מספרים/מדינה",
        ],
        "source_url": "https://www.lycamobile.us/en/plan-types/national-plans/",
    },

    # ─────────────────────────────────────────────────────────────────────
    # Simple Mobile — Tracfone brand now on the VERIZON network (the 2025
    # "Verizon Value" relaunch moved it off T-Mobile). Unlimited US talk/text +
    # unlimited global texting on every tier; 🇮🇱 Israel IS in the unlimited
    # intl-calling list (even the $25 plan), capped at 15 unique numbers per
    # 30-day cycle. eSIM (Verizon-compatible), no SSN, cash SIM kit at Walmart.
    # ─────────────────────────────────────────────────────────────────────
    {
        "carrier": "simple_mobile", "network": "Verizon",
        "plan_name": "Simple Mobile $25 (15GB)", "original_price": 25.0,
        "data_gb": 15, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (ל-100+ מדינות) + קרדיט בינ\"ל $10",
            "15GB מהיר ואז מהירות מופחתת",
            "שיחות ו-SMS ללא הגבלה בארה\"ב + SMS בינ\"ל ללא הגבלה",
            "מגבלה: עד 15 מספרים בינ\"ל שונים בכל מחזור 30 יום",
            "eSIM (תואם Verizon) · ללא תעודה אמריקאית · ערכת SIM במזומן ב-Walmart",
        ],
        "source_url": "https://www.simplemobile.com/cell-phone-plans",
    },
    {
        "carrier": "simple_mobile", "network": "Verizon",
        "plan_name": "Simple Mobile $40 (30GB)", "original_price": 40.0,
        "data_gb": 30, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (ל-125+ מדינות) + קרדיט בינ\"ל $10",
            "30GB מהיר ואז מהירות מופחתת",
            "שיחות ו-SMS ללא הגבלה בארה\"ב + SMS בינ\"ל ללא הגבלה",
            "ערך מצוין לתייר עם שיחות הביתה לישראל",
            "eSIM (תואם Verizon) · ערכת SIM במזומן ב-Walmart",
        ],
        "source_url": "https://www.simplemobile.com/cell-phone-plans",
    },
    {
        "carrier": "simple_mobile", "network": "Verizon",
        "plan_name": "Simple Mobile $50 Unlimited World", "original_price": 50.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (ל-200+ מדינות) + קרדיט בינ\"ל $10",
            "גלישה ללא הגבלה ברשת Verizon",
            "שיחות ו-SMS ללא הגבלה בארה\"ב + SMS בינ\"ל ללא הגבלה",
            "נדידה ב-~16 מדינות (בעיקר אמריקה הלטינית)",
            "eSIM (תואם Verizon) · ללא תעודה אמריקאית",
        ],
        "source_url": "https://www.simplemobile.com/cell-phone-plans",
    },
    {
        "carrier": "simple_mobile", "network": "Verizon",
        "plan_name": "Simple Mobile $60 Unlimited World+", "original_price": 60.0,
        "data_gb": None, "days": 30, "esim": True,
        "extras": [
            "🇮🇱 שיחות ללא הגבלה לישראל כלולות (ל-200+ מדינות) + קרדיט בינ\"ל $20",
            "גלישה ללא הגבלה כולל Verizon 5G Ultra Wideband",
            "שיחות ו-SMS ללא הגבלה בארה\"ב + SMS בינ\"ל ללא הגבלה",
            "נדידה בינ\"ל ב-140+ מדינות — מצוין למי שממשיך לטייל",
            "eSIM (תואם Verizon) · ערכת SIM במזומן ב-Walmart",
        ],
        "source_url": "https://www.simplemobile.com/cell-phone-plans",
    },
]


def _attach_ils_prices(plans):
    """Convert each plan's USD original_price → ILS `price` at the live rate.
    Mirrors the global_plans convention (price=ILS, original_price=USD)."""
    try:
        from scraper import _get_usd_to_ils
        rate = _get_usd_to_ils()
    except Exception as exc:  # network/import failure → conservative fallback
        rate = 3.7
        print(f"[warn] USD→ILS fetch failed ({exc}); using fallback {rate}")
    print(f"USD→ILS rate: {rate}")
    for p in plans:
        usd = p.get("original_price")
        p["currency"] = "USD"
        p["price"] = round(usd * rate, 2) if usd is not None else None
    return plans


if __name__ == "__main__":
    init_db()
    save_usa_tourist_plans(_attach_ils_prices(PLANS))
    operators = sorted({p["carrier"] for p in PLANS})
    print(f"Seeded {len(PLANS)} US tourist plans across {len(operators)} operators:")
    print("  " + ", ".join(operators))
