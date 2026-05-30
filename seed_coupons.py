"""Seed provider_coupons with verified discount codes for global eSIM providers.

Codes below were verified via public listings (cybernews, tomsguide, techradar, gizmodo,
adamandlinds, stephandpete) on 2026-05-27. Re-run quarterly to refresh expiry windows
or replace dead codes. Re-runnable: UPSERTs by (carrier, code).

When you obtain a personal affiliate code (registered under our own account via
Saily / Holafly / Airalo partner programs), add it here with a clear note in the
`notes` field and disable the third-party codes — our codes are the only ones that
generate commission for us.
"""
from db import init_db, upsert_coupon


# Verified active 2026-05. expires_at left None for codes the partner lists as
# "evergreen / no fixed end date" — flip to a YYYY-MM-DD if the source page says so.
COUPONS = [
    # ── Saily (NordVPN's eSIM brand) ──────────────────────────────────────
    {
        "carrier": "saily",
        "code": "GIZMODO",
        "discount_label": "15% הנחה",
        "source_url": "https://gizmodo.com/best-esim-provider/saily-coupon",
        "notes": "Highest verified Saily discount as of May 2026 (Gizmodo affiliate). Replace with our own code once we register to Saily's partner program.",
    },
    {
        "carrier": "saily",
        "code": "TECHNOVICE",
        "discount_label": "10% הנחה",
        "source_url": "https://www.technovice.net/en/post/saily-coupon-codes-2026-tested",
        "notes": "Backup 10% code in case GIZMODO stops working.",
    },
    {
        "carrier": "saily",
        "code": "ESIMP",
        "discount_label": "10% הנחה",
        "source_url": "https://esimplanet.io/en/promos/saily",
        "notes": "Backup 10% code.",
    },

    # ── Holafly ───────────────────────────────────────────────────────────
    {
        "carrier": "holafly",
        "code": "ADAMANDLINDS",
        "discount_label": "10% חודשי / 5% חבילה",
        "source_url": "https://www.adamandlinds.com/blog/holafly-discount-code-2026/",
        "notes": "10% off monthly subscription plans, 5% off regional/destination eSIMs.",
    },
    {
        "carrier": "holafly",
        "code": "STEPHANDPETE",
        "discount_label": "5% / 10% שנתי",
        "source_url": "https://stephandpete.co/blog/blog/holafly-march-2026-codes",
        "notes": "5% on standard eSIMs, 10% on annual plans. Verified March 2026.",
    },
    {
        "carrier": "holafly",
        "code": "MYESIMNOW5",
        "discount_label": "5% הנחה",
        "source_url": "https://cybernews.com/esim-coupon-codes/holafly/",
        "notes": "Backup 5% code from cybernews list.",
    },

    # ── Airalo via Gooday (external offer — per-user code) ────────────────
    # Gooday issues a unique single-use 20%-off code after phone verification, so
    # we can't seed a static code. Instead we render a link-out tile that sends
    # the user to gooday's Airalo page where they get a personal code.
    # See https://www.gooday.co.il/הטבות/Airalo
    {
        "carrier": "airalo",
        "code": "GOODAY",  # synthetic — satisfies UNIQUE(carrier, code); not shown when external_offer_url is set
        "discount_label": "20% הנחה (קוד אישי)",
        "partner_name": "גודיי",
        "external_offer_url": "https://www.gooday.co.il/%D7%94%D7%98%D7%91%D7%95%D7%AA/Airalo",
        "source_url": "https://www.gooday.co.il/%D7%94%D7%98%D7%91%D7%95%D7%AA/Airalo",
        "notes": "Per-user single-use code, requires phone+email verification on Gooday. Max 4 codes/month per phone.",
    },
]


def main():
    init_db()
    for c in COUPONS:
        cid = upsert_coupon(
            carrier=c["carrier"],
            code=c["code"],
            discount_label=c.get("discount_label"),
            expires_at=c.get("expires_at"),
            source_url=c.get("source_url"),
            is_active=True,
            notes=c.get("notes"),
            external_offer_url=c.get("external_offer_url"),
            partner_name=c.get("partner_name"),
        )
        print(f"  upserted #{cid}  {c['carrier']:10s}  {c['code']:18s}  {c.get('discount_label','')}")
    print(f"\nDone. {len(COUPONS)} coupons seeded.")


if __name__ == "__main__":
    main()
