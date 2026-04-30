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

Conclusion: Israeli cellular resellers do NOT publish unique pricing on social media. The carriers
control the rate card; resellers earn commissions, not pricing flexibility. The single confirmed
unique deal is the cellcomshefamr 200-minute plan, which is a niche local promo for Arab-Israeli
customers in Shfar'am that doesn't appear in Cellcom's standard catalog.

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
