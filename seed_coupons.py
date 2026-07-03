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
    # OUR OWN affiliate code (aff_id 14705). Confirmed live for 10% by the Saily
    # Affiliate Team on 2026-06-16. This is the only Saily code that earns us
    # commission, so the third-party codes below are disabled (is_active=False).
    {
        "carrier": "saily",
        "code": "MOCA",
        "discount_label": "10% הנחה",
        "source_url": "https://saily.com/",
        "notes": "MOCA's own affiliate coupon (aff_id 14705). Confirmed live for 10% by Saily Affiliate Team 2026-06-16. Earns commission for us.",
    },
    {
        "carrier": "saily",
        "code": "GIZMODO",
        "discount_label": "15% הנחה",
        "is_active": False,
        "source_url": "https://gizmodo.com/best-esim-provider/saily-coupon",
        "notes": "DISABLED 2026-06-16 — superseded by our own MOCA code. Third-party (Gizmodo affiliate), earns us nothing.",
    },
    {
        "carrier": "saily",
        "code": "TECHNOVICE",
        "discount_label": "10% הנחה",
        "is_active": False,
        "source_url": "https://www.technovice.net/en/post/saily-coupon-codes-2026-tested",
        "notes": "DISABLED 2026-06-16 — superseded by our own MOCA code. Third-party, earns us nothing.",
    },
    {
        "carrier": "saily",
        "code": "ESIMP",
        "discount_label": "10% הנחה",
        "is_active": False,
        "source_url": "https://esimplanet.io/en/promos/saily",
        "notes": "DISABLED 2026-06-16 — superseded by our own MOCA code. Third-party, earns us nothing.",
    },

    # ── Voye Global ───────────────────────────────────────────────────────
    # OUR OWN affiliate code (Impact campaign 25196). Confirmed live for 15% by
    # the Voye Global Affiliate Team on 2026-06-22 ("the coupon code is active
    # and working, proceed with publishing"). Earns us 15% commission, 30-day
    # last-click; tracking link wired at /go/voye.
    {
        "carrier": "voye",
        "code": "MOCA",
        "discount_label": "15% הנחה",
        "source_url": "https://voyeglobal.com/",
        "notes": "MOCA's own affiliate coupon (Impact campaign 25196). Confirmed live for 15% customer discount by Voye Global Affiliate Team 2026-06-22. Earns 15% commission (30-day last-click) for us.",
    },

    # ── aloSIM (AffinityClick / Everflow) ─────────────────────────────────
    # OUR OWN affiliate code (affid 1652, offer 9). Confirmed live for 15% off
    # first purchase by Celine Solomon (AffinityClick) on 2026-06-23.
    # Commission: $5 per sale. Tracking link: alosim.com/?oid=9&affid=1652.
    {
        "carrier": "alosim",
        "code": "MOCA",
        "discount_label": "15% הנחה",
        "source_url": "https://alosim.com/",
        "notes": "MOCA's own affiliate coupon (Everflow affid 1652, offer 9). Confirmed 15% off first purchase by Celine Solomon / AffinityClick 2026-06-23. Earns $5/sale commission.",
    },

    # ── 7G eSIM ───────────────────────────────────────────────────────────
    # OUR OWN partner codes. 7G auto-provisioned the account on 2026-06-30 and
    # issued three codes trading discount vs commission: alonyo10 (10% off / 20%
    # commission), alonyo15 (15% off / 15% commission), alonyo20 (20% off / 10%
    # commission). alonyo15 is the PUBLIC code — the balanced split; alonyo10 and
    # alonyo20 are recorded here as inventory (is_active=False) so they show in the
    # admin coupons view but the public compare page keeps featuring alonyo15 (only
    # one active coupon per carrier surfaces publicly). Referral link wired at
    # /go/seven_g (Branch slug "alonyo"). Pending: asked 7G to rename to a unified
    # "MOCA" code (email 2026-06-30); swap `code` here once they confirm.
    {
        "carrier": "seven_g",
        "code": "alonyo15",
        "discount_label": "15% הנחה",
        "source_url": "https://7g.app/",
        "notes": "MOCA's own 7G partner code (15% off / 15% commission) — the PUBLIC code. Account auto-created 2026-06-30. Interim code; MOCA-unified rename requested from 7G, swap to MOCA when confirmed.",
    },
    {
        "carrier": "seven_g",
        "code": "alonyo10",
        "discount_label": "10% הנחה",
        "is_active": False,
        "source_url": "https://7g.app/",
        "notes": "MOCA's own 7G partner code (10% off / 20% commission) — max commission split. Inventory only; alonyo15 is the public code. Flip is_active to feature this split to customers.",
    },
    {
        "carrier": "seven_g",
        "code": "alonyo20",
        "discount_label": "20% הנחה",
        "is_active": False,
        "source_url": "https://7g.app/",
        "notes": "MOCA's own 7G partner code (20% off / 10% commission) — max customer discount split. Inventory only; alonyo15 is the public code. Flip is_active to feature this split to customers.",
    },

    # ── Terminal eSIM (terminalesim.com) ─────────────────────────────────
    # OUR OWN affiliate code. Terminal eSIM (which replaced GlobaleSIM in MOCA
    # 2026-07 at the operator's request) issued "MOCA" for 15% off. Provided by
    # the operator via WhatsApp (054-4322104).
    {
        "carrier": "terminalesim",
        "code": "MOCA",
        "discount_label": "15% הנחה",
        "source_url": "https://terminalesim.com/",
        "notes": "MOCA's own affiliate coupon for Terminal eSIM. 15% customer discount; earns MOCA 10% commission on converted leads (orders placed with code MOCA). Provided by the operator 2026-07 (WhatsApp 054-4322104). Terminal eSIM replaced GlobaleSIM.",
    },

    # ── Maya Mobile ───────────────────────────────────────────────────────
    # OUR OWN affiliate code (Impact, publisher acct 7205658). Bart Skrzypek
    # (Maya Partner Account Manager) confirmed MOCA10 LIVE on 2026-07-02 after
    # the Calendly call. 10% off for first-time customers; earns MOCA 15-20%
    # commission via Impact. Attribution is coupon-based (like Voye/terminalesim)
    # until the Impact TrackingLink is generated in the dashboard.
    {
        "carrier": "maya",
        "code": "MOCA10",
        "discount_label": "10% הנחה",
        "source_url": "https://maya.net/esim/plans",
        "notes": "MOCA's own affiliate coupon (Impact acct 7205658). Confirmed live for 10% off first-time customers by Bart Skrzypek / Maya 2026-07-02. Earns 15-20% commission. 6-char min forced MOCA10 (plain 'MOCA' rejected).",
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

    # ── ByteSim (in-house affiliate / personal-store program) — DISABLED ──
    # DISABLED 2026-07-03: at ByteSim checkout the code "Moca"/"moca" shows as
    # "Below coupon codes are unavailable" and applies NO discount (only their
    # automatic 5% Summer Sale). Queried ByteSim (draft to service@bytesim.com)
    # whether it's a real customer discount or referral-only. is_active=False so
    # the coupon pill stops rendering; re-enable + add a discount_label % ONLY if
    # ByteSim confirms a working customer discount. The affiliate LINK stays live
    # (/go/bytesim + AFFILIATE_URLS, referral_code 8F68HJS3KPDU) — attribution is
    # via the link, independent of this coupon.
    {
        "carrier": "bytesim",
        "code": "MOCA",
        "is_active": False,
        "source_url": "https://bytesim.com/",
        "notes": "DISABLED 2026-07-03 — code shows 'unavailable' at ByteSim checkout (no customer discount applied). Pending ByteSim's reply on whether it discounts the customer or is referral-only. Re-enable + add a % only if they confirm a working customer discount.",
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
            is_active=c.get("is_active", True),
            notes=c.get("notes"),
            external_offer_url=c.get("external_offer_url"),
            partner_name=c.get("partner_name"),
        )
        print(f"  upserted #{cid}  {c['carrier']:10s}  {c['code']:18s}  {c.get('discount_label','')}")
    print(f"\nDone. {len(COUPONS)} coupons seeded.")


if __name__ == "__main__":
    main()
