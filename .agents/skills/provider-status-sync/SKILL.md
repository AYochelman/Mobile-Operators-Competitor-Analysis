---
name: provider-status-sync
description: >-
  Keep the super-admin "סטטוס ספקים" CRM (/admin/deals, seeded by seed_provider_deals.py)
  in sync with reality, WITHOUT waiting to be asked. Invoke whenever ANYTHING changes or
  advances with an eSIM/affiliate provider during a session: a provider email or WhatsApp
  is read or answered, an application is submitted/approved/declined, a coupon is
  confirmed/disabled/seeded, a tracking link or deep-links are generated or wired, a
  contract is signed, a call is held or scheduled, a provider is integrated, renamed, or
  retired, or an Impact-dashboard status changes. This applies even when the user only
  asked to "read the email" or "prepare a reply" — updating the CRM is part of finishing
  that task, not a separate request.
---

# Provider Status Sync ("סטטוס ספקים" CRM)

The operator's single source of truth on provider relationships is the `/admin/deals`
dashboard, fed by the `provider_deals` table, which is seeded from
**`seed_provider_deals.py`** (repo root). Codex's memory files are internal notes the
operator never sees — so a provider development that lands only in memory is invisible
to him. **A provider-related task is not done until the CRM row reflects it.**

## When to run (standing instruction)

Any time a session produces a *material change* to a provider relationship, update the
row in the same turn — do not wait for the user to say "עדכן סטטוס ספקים". Material
changes include:

- Inbound/outbound **email, WhatsApp, or call** that moves the thread (reply received,
  reply sent, follow-up sent, meeting booked/held)
- **Application state**: submitted / approved / declined / re-review / routed to another team
- **Coupon**: code promised, confirmed live, verified broken, disabled, seeded in seed_coupons.py
- **Tracking**: tracking link received or wired (`/go/<id>`, affiliateLinks.js, config.json),
  deep-links or Sub-ID added
- **Agreement**: contract sent / signed (one or both sides)
- **Catalog**: provider integrated as a tracked provider, rebranded, or retired

Not material (skip): routine scrape results, price changes, questions the user asks
*about* the CRM without new facts.

## How to update

1. **Find the row** in `seed_provider_deals.py` → `DEALS` by `provider_id`
   (ids match `GLOBAL_LABELS` in carrierLabels.js / `_CARRIER_NAMES` in app.py).
   No row yet → add a new dict; copy a neighbor's shape.
2. **Edit the fields** (semantics below). Write values in Hebrew, matching the file's
   existing style — this file uses literal Hebrew, not unicode escapes.
3. **Keep the row in the right section.** The file is grouped by stage under comment
   banners: `LIVE & EARNING` → `IN DISCUSSION / PENDING` → `COLD OUTREACH SENT` →
   `DECLINED` → `NOT CONTACTED`. When a deal changes stage, move its dict to the
   matching section so the file stays scannable.
4. **Re-run the seed** from the repo root:
   ```bash
   python seed_provider_deals.py
   ```
   Confirm the provider's line appears in the `upserted` output. No Flask restart is
   needed — the dashboard reads the DB per request.
5. **Tell the user in one line** what changed in the CRM (e.g. "עדכנתי את שורת Airalo
   בסטטוס ספקים: ...").

## Field semantics

| Field | Meaning |
|-------|---------|
| `display_name` | Human provider name shown in the dashboard (e.g. "Voye Global") |
| `category` | `"global"` for all eSIM providers (the only value in use today) |
| `program_network` | Affiliate platform the deal runs on (Impact / TUNE / Everflow / Puremium / in-house) — free text, may mix Hebrew |
| `outreach_status` | `not_contacted` \| `contacted` \| `in_discussion` \| `approved` \| `declined` \| `live` |
| `outreach_last_at` | `YYYY-MM-DD` of the **latest meaningful contact** (either direction) — bump it on every material email/call |
| `contact` | Current best contact (email/person/channel). If ownership moved (e.g. partnerships → affiliate team), put the new owner first |
| `agreement_status` | `none` \| `pending` \| `signed` \| `live` |
| `commission_pct` | Our commission % (number); `None` if flat-fee/unknown |
| `commission_note` | Terms nuance in Hebrew (cookie window, network, account) |
| `coupon_note` | Nuance only — coupon **liveness is NOT stored here** (the dashboard joins `provider_coupons` live). Use it for "why none", "third-party code earns us nothing", "code promised, pending" |
| `has_tracking_link` | True only when a real attribution link is wired (not a bare homepage) |
| `is_leak` | Looks monetized in the UI but earns us $0 — set/clear it when wiring or breaking links |
| `priority` | `high` = needs action from **us** now; `med` = waiting/minor; `low` = nothing owed |
| `next_actions` | What's pending and **who owes it** (us vs. them), with dates and a concrete nudge date if we're waiting (e.g. "אם שקט עד ~12/07 - תזכורת") |
| `notes` | Running timeline in Hebrew. **Append** dated events (DD/MM) rather than rewriting history |

## Event → field cheat sheet

- **Reply sent by us** → `outreach_last_at` = today; `next_actions` = "ממתינים לתשובת X;
  אם שקט עד ~<date> - תזכורת"; append to `notes`.
- **They approved / sent tracking link** → usually `outreach_status: approved`,
  `agreement_status: live`; once the link is wired: `has_tracking_link: True`, clear
  `is_leak`, consider moving toward `live` + section move.
- **Coupon confirmed & seeded** → update `coupon_note` (code, %, "חי ומזכה אותנו");
  the pill renders from `provider_coupons`, so also make sure seed_coupons.py ran.
- **Declined** → `outreach_status: declined`, move to the DECLINED section,
  `next_actions` = whether a re-pitch path exists.
- **Routed to another team/contact** → update `contact`, keep `outreach_status`
  (usually still `in_discussion`), record the routing in `notes`.
- **New provider integrated into MOCA (new scraper/GLOBAL_LABELS key)** → add a row in
  the NOT CONTACTED section (id must equal the new `GLOBAL_LABELS` key), and put the
  affiliate-outreach question in `next_actions` so the provider isn't a silent leak.
  Exception: Pelephone brands stay out (see Constraints).

## Companion updates (same turn)

- **Memory**: also append the development to the affiliate-log memory
  (`project_maya_affiliate_application.md`) so future sessions have the narrative.
- **Commit**: the repo convention is a `chore(affiliate): refresh provider-status CRM (...)`
  commit — offer it, but don't commit without the user asking (per AGENTS.md).
- **Out of scope for this skill**: wiring links/coupons themselves (affiliateLinks.js,
  config.json, seed_coupons.py) — do those as their own tasks; this skill only guarantees
  the CRM mirror is updated afterwards.

## Constraints

- **Never invent facts** to fill fields — if a commission % or contact is unknown, leave
  `None` / write "לא ידוע". The CRM's value is that it's trustworthy.
- **Pelephone brands (Tuki, GlobalSIM) stay out of the CRM** — deliberately excluded
  (the operator works at Pelephone); don't add rows for them.
- Dates in `outreach_last_at` are ISO (`YYYY-MM-DD`); dates inside Hebrew text use `DD/MM`.
