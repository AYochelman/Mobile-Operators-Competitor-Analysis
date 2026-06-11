"""Seed reseller_plans with offers transcribed from social-media of Israeli cellular resellers.

Strict filters per user requirements (2026-04-29):
  - Page active in last 2 years (2024-04 onwards)
  - Price NOT advertised on the carrier's own rate card

Findings after thorough scan (24 candidate accounts checked):
  - @m.pelephone (Instagram) → REJECTED. Last post May 2022 (~4 years old). Fails 2-year filter.
  - @cellcomshefamr (Instagram, 316 posts) → KEEP partial. Active through June 2024 (within window).
      11 most-recent post captions are Eid greetings, store hours, product showcases — NO captioned prices.
      Prices visible only in image overlays (Arabic/Hebrew burnt-in text), require manual transcription.
      "5G ₪39 / 3 months" → REJECTED. Cellcom's own join page advertises ₪39.9 for 5G/2 months → effectively duplicate.
      "₪35 / 200 minutes" → KEPT. Cellcom's smallest published plan is ₪44.9 (4G Basic, 3500 min).
                            No carrier-side equivalent for a 200-minute kosher-style plan at this price.
  - Pattern accounts (cellcom<city>, pelephone_<city>) → all empty/non-existent.
  - DVCOM (Netivot), Royal Phone, Itan Tikshoret, Target Call → telesales call centers, no public prices online.
  - Myphone, Cellcom-ishka, S-Romi, Comy → not selling cellular plans (devices/insurance/B2B/comedy).

Conclusion (2026-04): Israeli cellular resellers do NOT publish unique pricing on social media.

UPDATE 2026-06-11: a broad web sweep DID find below-the-line pricing — on reseller
WEBSITES (tiber, zol-li, kamaze, tikshoretishit), carrier-owned landing pages
(Partner lobby, Rami Levy hever/landing, WeCom sim-data, ClubDeal) and Facebook
Ad Library campaigns. The auto-scrapeable sources live in btl_scrapers.py and
refresh daily at 08:15; THIS file holds only manual-refresh sources (Facebook
ads, login-gated club pages, low-churn comparison pages) — re-verify quarterly.

Re-runnable: UPSERTs by (reseller_id, carrier, plan_name).
"""
from datetime import datetime
from db import init_db, save_reseller_plans


# Verified unique reseller-only prices.
# Manual transcription from Instagram image overlays — re-verify quarterly.
PLANS = [
    {
        "reseller_id": "cellcomshefamr",
        "carrier": "cellcom",
        "plan_name": "200 דקות במחיר מבצע (משווק מקומי)",
        "price": 35.0,
        "data_gb": None,
        "minutes": 200,
        "sms": None,
        "extras": [
            "משווק מקומי שפרעם",
            "קו טלפון בלבד — 200 דקות",
            "אין מקבילה במחירון הציבורי של סלקום (מינימום 44.9 ₪)",
        ],
        "source_url": "https://www.instagram.com/cellcomshefamr/",
        "seen_at": "2024-06",  # latest post window where this offer appeared
    },
    {
        # Zoro (zorro.press) — affiliate page that promotes Partner. Their FB ad
        # ("מבצע 48 שעות, ללקוחות חדשים בלבד") routes to Partner via Zoro's
        # affiliate channel. The 2-line discounted price is not advertised on
        # partner.co.il's standard rate card (which shows Golden 5G 500GB @ 39.90
        # for single line and Royal 5G 800GB @ 39.90 for 3+ lines).
        "reseller_id": "zorro",
        "carrier": "partner",
        "plan_name": "300GB ב-2 קווים — מבצע משווק",
        "price": 29.9,
        "data_gb": 300,
        "minutes": None,  # 3000 = effectively unlimited
        "sms": None,  # 3000 = effectively unlimited
        "extras": [
            "₪29.90 לקו ב-2 קווים ומעלה (₪39.90 לקו יחיד)",
            "ללקוחות חדשים בלבד",
            "5G • שיחות ו-SMS ללא הגבלה",
            "200 דקות לחו\"ל ל-42 יעדים נבחרים",
            "מחיר קבוע לשנה, ללא התחייבות",
            "דמי הקמה חד-פעמיים: ₪9.90",
            "מקודם עם דחיפות \"48 שעות\" בפייסבוק",
            "מחיר 2-הקווים לא במחירון הציבורי של פרטנר",
        ],
        "source_url": "https://www.facebook.com/ZorroPricesCompare/",
        "seen_at": "2026-05",
    },
    # ─────────────────────────────────────────────────────────────────────
    # Rami Levy Communications — dedicated lead-gen landing page (3 packages)
    #   https://landing-mobile.rami-levy.co.il/landing/
    # Added 2026-06 per explicit user request: track this landing page as a
    # "reseller" source even though it is Rami Levy's OWN page and the offers
    # overlap the official rate card (the Xtreme package is identical to the
    # public "1000GB Xtreme" @ ₪55). Because of that overlap — and because the
    # kosher ₪14.9 plan stores data_gb=None (treated as ∞ by the dominance
    # filter, which would then dominate every priced rami_levy reseller plan) —
    # reseller_id "rami_levy_landing" is whitelisted in
    # db.ALWAYS_SHOW_RESELLER_IDS so all 3 stay visible in the משווקים tab.
    # Prices are the headline totals the page advertises (the package names
    # encode them: "2 ב-40", "3 ב-80").
    # ─────────────────────────────────────────────────────────────────────
    {
        "reseller_id": "rami_levy_landing",
        "carrier": "rami_levy",
        "plan_name": "זוגות 2 ב-40",
        "price": 40.0,
        "data_gb": 200,
        "minutes": 2500,
        "sms": 2500,
        "extras": [
            "מבצע זוגות — 2 קווים, רשת 5G",
            "₪40 לשני הקווים (₪20 לקו)",
            "חודש במתנה למצטרפים חדשים",
            "תוקף: 12 חודשים",
            "בכפוף לתקנון המבצע והסכם ההתקשרות (ט.ל.ח)",
        ],
        "source_url": "https://landing-mobile.rami-levy.co.il/landing/",
        "seen_at": "2026-06",
    },
    {
        "reseller_id": "rami_levy_landing",
        "carrier": "rami_levy",
        "plan_name": "טריפל 3 ב-80",
        "price": 80.0,
        "data_gb": 600,
        "minutes": 5000,
        "sms": 5000,
        "extras": [
            "מבצע טריפל — 3 קווים, רשת 5G",
            "₪80 לשלושת הקווים (₪26.7 לקו)",
            "תוקף: 24 חודשים",
            "בכפוף לתקנון המבצע והסכם ההתקשרות (ט.ל.ח)",
        ],
        "source_url": "https://landing-mobile.rami-levy.co.il/landing/",
        "seen_at": "2026-06",
    },
    {
        "reseller_id": "rami_levy_landing",
        "carrier": "rami_levy",
        "plan_name": "Xtreme – 1000GB",
        "price": 55.0,
        "data_gb": 1000,
        "minutes": 2500,
        "sms": 2500,
        "extras": [
            "חבילת Xtreme — קו יחיד, רשת 5G",
            "תוקף: 24 חודשים",
            "זהה לחבילת 1000GB Xtreme שבמחירון הרשמי (₪55)",
            "בכפוף לתקנון המבצע והסכם ההתקשרות (ט.ל.ח)",
        ],
        "source_url": "https://landing-mobile.rami-levy.co.il/landing/",
        "seen_at": "2026-06",
    },
    # ─────────────────────────────────────────────────────────────────────
    # 2026-06-11 web sweep — manual-refresh sources only (auto-scraped
    # sources — tiber/zol_li/kamaze/partner_site/rami_levy_hever/wecom_site/
    # tikshoretishit/clubdeal — are populated daily by btl_scrapers.py).
    # ─────────────────────────────────────────────────────────────────────
    {
        # sell-zoll.co.il — broker/comparison page, Cellcom dealer-channel
        # multi-line plan. Page is static but low-churn; manual refresh.
        "reseller_id": "sell_zoll",
        "carrier": "cellcom",
        "plan_name": "200GB — שני קווים ומעלה",
        "price": 34.9,
        "data_gb": 200,
        "minutes": 3000,
        "sms": 3000,
        "extras": [
            "34.90 ₪ לקו ב-2 קווים ומעלה, לשנה הראשונה",
            "לאחר שנה: 49 ₪ לחודש",
            "3,000 דקות + 100 דקות לחו\"ל",
            "סים ומשלוח ללא עלות",
        ],
        "source_url": "https://sell-zoll.co.il/cellular",
        "seen_at": "2026-06-11",
    },
    {
        # kamazeole — Golan family bundle (3 lines). The dominance filter would
        # hide it (total ₪99 > any single-line plan) so the id is whitelisted
        # in db.ALWAYS_SHOW_RESELLER_IDS; structurally it's a per-line winner.
        "reseller_id": "kamazeole",
        "carrier": "golan",
        "plan_name": "משפחתית — 3 קווים 1500GB",
        "price": 99.0,
        "data_gb": 1500,
        "minutes": None,
        "sms": None,
        "extras": [
            "99 ₪ לחודש בהצטרפות 3 קווים (33 ₪ לקו)",
            "500GB גלישה לכל קו במשפחה",
            "1GB גלישה בחו\"ל מתנה בכל חודש",
            "חיבור eSIM מיידי",
            "לא מופיעה בדף ה-offers הרשמי של גולן",
        ],
        "source_url": "https://www.kamazeole.co.il/packages/cell/company/13/golan-telecom/golan-telecom-1500gb-family-plan",
        "seen_at": "2026-06-11",
    },
    {
        # "אנלייזר - פשוט לחסוך" — lead-gen broker advertising a Cellcom-implied
        # 800GB deal via active Facebook ads (Library IDs 978489331480733,
        # 1002340219151495, running since 28.5/2.6.2026). The continuation
        # price (49 ₪ fixed) is not on Cellcom's rate card.
        "reseller_id": "analizer",
        "carrier": "cellcom",
        "plan_name": "800GB דור 5 — דרך המתווך אנלייזר",
        "price": 39.9,
        "data_gb": 800,
        "minutes": 5000,
        "sms": 5000,
        "extras": [
            "39.9 ₪ לחודשיים הראשונים, לאחר מכן 49 ₪ במחיר קבוע",
            "מודעות פייסבוק פעילות (מאי-יוני 2026)",
            "סים + שליח חינם, אפליקציות חופשיות",
            "\"חברת הסלולר הגדולה בישראל, 3.6 מיליון לקוחות\" = סלקום (משתמע)",
        ],
        "source_url": "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IL&q=%D7%92%D7%99%D7%92%D7%94%20%D7%9C%D7%97%D7%95%D7%93%D7%A9&search_type=keyword_unordered&media_type=all",
        "seen_at": "2026-06-11",
    },
    {
        # Official Pelephone Facebook campaign (Library ID 1275298018098297,
        # running since 18.5.2026) — 300GB at 29.90, below the public rate
        # card's 39.9 floor. Same offer family as pelephone-join's 300GB.
        "reseller_id": "pelephone_fb",
        "carrier": "pelephone",
        "plan_name": "300GB + eSIM — קמפיין פייסבוק",
        "price": 29.9,
        "data_gb": 300,
        "minutes": None,
        "sms": None,
        "extras": [
            "מודעה רשמית של פלאפון, פעילה מ-18.5.2026",
            "מתחת לרצפת המחירון הרשמי (39.9 ₪)",
            "הצטרפות דרך טופס לידים במודעה",
        ],
        "source_url": "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IL&q=%D7%92%D7%99%D7%92%D7%94%20%D7%9C%D7%97%D7%95%D7%93%D7%A9&search_type=keyword_unordered&media_type=all",
        "seen_at": "2026-06-11",
    },
    {
        # Rami Levy credit-card holders' benefit — the base "זוג ב-50" plan IS
        # on the rate card, but the 2-free-months + free connection benefit is
        # landing-page-only. Whitelisted in ALWAYS_SHOW_RESELLER_IDS.
        "reseller_id": "rami_levy_cc",
        "carrier": "rami_levy",
        "plan_name": "זוג קווים ב-50 ₪ — הטבת כרטיס אשראי",
        "price": 50.0,
        "data_gb": 250,
        "minutes": None,
        "sms": None,
        "extras": [
            "חודשיים ראשונים + דמי חיבור חינם — למשלמים בכרטיס אשראי רמי לוי בלבד",
            "לאחר מכן 22 חודשים ב-50 ₪ לזוג קווים",
            "דמי מעבר חד-פעמיים 9.90 ₪",
            "תומך דור 5",
        ],
        "source_url": "https://mobile.rami-levy.co.il/Home/Landing/",
        "seen_at": "2026-06-11",
    },
]


if __name__ == "__main__":
    init_db()
    # Wipe stale entries from previous, broader seed
    from db import _connect
    conn = _connect()
    try:
        conn.execute("DELETE FROM reseller_plans WHERE reseller_id = ?", ("m_pelephone",))
        conn.execute(
            "DELETE FROM reseller_plans WHERE reseller_id = ? AND plan_name LIKE ?",
            ("cellcomshefamr", "5G%")
        )
        conn.execute(
            "DELETE FROM reseller_plans WHERE reseller_id = ? AND plan_name = ?",
            ("cellcomshefamr", "200 דקות במחיר מבצע")
        )
        conn.commit()
    finally:
        conn.close()
    save_reseller_plans(PLANS)
    print(f"Seeded {len(PLANS)} reseller plans (after pruning stale entries).")
