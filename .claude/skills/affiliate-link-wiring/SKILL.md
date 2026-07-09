---
name: affiliate-link-wiring
description: >-
  Wire a new (or fix an existing) affiliate tracking link end-to-end in MOCA: the
  config.json affiliate registry, the /go/<provider> redirect dispatch in app.py,
  per-destination deep-links or SubIds, the frontend affiliateLinks.js button map,
  the coupon seed, 302 verification, and the CRM sync. Use whenever a provider
  approves an affiliate application, sends a tracking link or coupon code, when a
  /go link 404s or redirects without attribution, when adding per-destination
  deep-links or Sub-IDs, or when the user mentions Impact/TUNE/Everflow/Puremium
  links, "לינק מעקב", or "לחווט את הלינק". provider-status-sync deliberately does
  NOT cover the wiring itself - this skill does.
---

# Affiliate Link Wiring (/go, deep-links, coupons)

Money flows through this path. A link wired without attribution params is a silent
leak (looks monetized, earns $0), and a link only in the frontend never fires for
the B2C page or the hotel portals. Wire all layers, verify the 302, then sync the CRM.

## Architecture - who resolves what

- **`/go/<provider>` + `/go/<provider>/<plan_id>`** → `affiliate_redirect()` in app.py
  (~line 1814). Reads `dest` (Hebrew destination), `src` (channel), `hotel`, `plan`,
  `campaign`; logs the click (`log_affiliate_click`, + `log_guest_event` when `hotel`
  is set); then runs a **per-provider dispatch chain** - each branch returns a deep
  link or None; the fallthrough is `_guest_provider_dest()` (~1337) which reads
  `load_config()["affiliate"][provider]["base_url"]`.
- **config.json `affiliate` block**: dict keyed by provider slug; per-provider keys
  are `tag` (publisher id; some use `referral_code`), `base_url` (the tracking link),
  optional `note`/`network`. **`load_config()` is mtime-cached** - editing config.json
  takes effect on the next request, NO Flask restart needed.
- **Frontend `mass-market-app/src/data/affiliateLinks.js`**: `AFFILIATE_PROVIDERS`
  (Set gating the purchase button) + `AFFILIATE_URLS` (carrier → URL). Consumed by
  PlanCard.jsx / GroupedPlanCard.jsx, which link **directly** (not via /go). The /go
  route serves `EsimComparePage` (`api.esimGoUrl`) and `GuestPortalPage`
  (`api.guestGoUrl`) - so backend wiring is live for B2C/hotels immediately, while
  the dashboard button needs a build + deploy.
- **Coupons**: `seed_coupons.py` (`COUPONS` list; fields `carrier`, `code`, optional
  `discount_label`, `is_active`, `source_url`, `notes`, `external_offer_url`,
  `partner_name`, `expires_at`) → `python seed_coupons.py` → `/api/coupons`
  (cached 5 min) → `useCoupons` → PlanCard pill. Also embedded in `/api/esim/compare`.

## Runbook - wiring a newly approved provider

1. **Obtain the link.** Impact providers: generate a TrackingLink via the Impact
   dashboard's "Create a link" widget in Chrome (Alon logs in; publisher account
   **7205658**). Other networks send the link by email.
2. **config.json**: add the `affiliate.<provider_id>` block (`tag`, `base_url`,
   `note`). Provider id must match the scraper carrier id. Live immediately.
3. **Pick the deep-link pattern** (the dispatch branch you add in `affiliate_redirect`):

   | Merchant site has... | Pattern | Reference implementation |
   |---|---|---|
   | Real per-country pages | Hardcoded dest → TrackingLink dict | `_VOYE_DEST_DEEPLINKS` + `_voye_deeplink_url` (~1546) |
   | Small fixed plan catalog | Per-plan dict keyed by plan attrs | `_MAYA_PLAN_DEEPLINKS` keyed (region, days) (~1508) |
   | Single page / SPA accordion, URL never changes | Append Sub-IDs to `base_url` | Impact: `_orbit_subid_url` (subId1=dest, subId2=src, subId3=hotel, ~1682); Everflow: `_gigsky_deeplink_url` (sub1/sub2/sub5, ~1726) |
   | Deep-link via network `url=` override | Puremium/HasOffers style | `_gomoworld_deeplink_url` (~1774) - `aff_c?...&url=<encoded dest page>` |
   | Nothing special | Generic `base_url` only | no branch needed - fallthrough handles it |

   For dest → slug conversion, invert the scraper's existing slug→Hebrew map lazily
   (e.g. `_ORBIT_HEB_TO_EN` from `scraper.ORBIT_NAME_TO_HEBREW`) - never duplicate
   the country list. Unknown dest must return None so the generic fallback fires.
4. **Frontend**: add the provider to `AFFILIATE_PROVIDERS` and `AFFILIATE_URLS` in
   affiliateLinks.js. Then `npm run build` - the dashboard button goes live only
   after deploy (use the deploy-live skill).
5. **Coupon** (if a code exists): add the row to seed_coupons.py, run
   `python seed_coupons.py`. A code that earns a competitor (third-party code) gets
   `is_active: False` + a note, not deletion.
6. **Restart caveat**: config.json changes are live without restart, but **app.py
   code changes** (a new dispatch branch) need the elevated Flask restart -
   `schtasks /end /tn CellularComparison` + `/run` (see CLAUDE.md "After Code Changes").

## Verify - never declare done without a 302 check

```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" "http://localhost:5000/go/<id>"
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" "http://localhost:5000/go/<id>?dest=יוון&src=esim"
```

Expect `302` and a Location carrying the network's attribution marker:

| Network | Marker in the redirect chain |
|---|---|
| Impact (Voye/Ubigi/Maya/bcengi/Orbit) | tracking domain (`*.pxf.io` / `*.sjv.io` / `go.ubigi.com`), lands with `irpid=7205658` |
| Impact SubId branches | `subId1`=dest slug, `subId2`=src, `subId3`=hotel |
| Everflow (GigSky, aloSIM) | `sub1`/`sub2`/`sub5`, `aff_id` |
| TUNE/HasOffers (Saily, GoMoWorld/Puremium) | `aff_c?offer_id=...&aff_id=...`, optional `aff_sub` |
| UpPromote/Shopify (Breeze) | `sca_ref=<tag>` |

A redirect to the merchant's bare homepage with none of these = leak, not done.
Also verify the deep-link branch: a known dest should land on the country/plan page,
an unknown dest on the generic base_url.

## Finish the job (same turn)

- **CRM**: run the provider-status-sync skill - `has_tracking_link: True`, clear
  `is_leak`, move the row toward LIVE, append the dated note.
- **Deploy** the frontend button (deploy-live skill) or tell the user it's pending.
- Commit convention: `feat(affiliate): ...` / `chore(affiliate): refresh provider-status CRM (...)` - offer, don't commit unasked.

## Constraints

- Never invent slugs for deep-links - verify each generated URL resolves (HTTP 200
  on the merchant page) before shipping the dict.
- Pelephone brands (Tuki, GlobalSIM) are deliberately out of affiliate scope.
- Don't print config.json secrets into chat/commits; reference keys by name.
