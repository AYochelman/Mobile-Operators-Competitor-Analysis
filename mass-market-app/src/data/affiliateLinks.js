// Canonical affiliate config for global eSIM providers — SINGLE SOURCE OF TRUTH.
// Imported by PlanCard and GroupedPlanCard. These used to keep separate copies
// that drifted (Saily's tracking link was updated in PlanCard but GroupedPlanCard
// still pointed at saily.com with no tracking, and Voye was missing from the
// grouped view) — keep all affiliate links here only.
//
// A provider in AFFILIATE_PROVIDERS renders a "רכישה / דרך MOCA" button. Providers
// with a signed tracking link redirect with attribution; the rest fall back to the
// provider homepage until their program link is wired.
// NB: `holafly` is deliberately NOT here — we have NO active Holafly affiliate
// agreement (applied via Impact 2026-06-13, no approval since). Its old entry
// pointed the "רכישה דרך MOCA" button at the bare homepage with no attribution
// (a leak: looked monetized, earned $0). Re-add ONLY once a real Holafly
// tracking link is wired (then also un-comment config.json affiliate.holafly).
export const AFFILIATE_PROVIDERS = new Set([
  'airalo', 'airalo_local', 'airalo_regional', 'saily', 'terminalesim', 'voye', 'yesim', 'alosim', 'seven_g', 'bcengi', 'maya', 'ubigi', 'bytesim', 'breez', 'gigsky', 'gomoworld', 'orbit',
])

export const AFFILIATE_URLS = {
  airalo:          'https://www.airalo.com',
  airalo_local:    'https://www.airalo.com',
  airalo_regional: 'https://www.airalo.com',
  saily:           'https://go.saily.site/aff_c?offer_id=101&aff_id=14705', // Saily affiliate tracking (offer_id 101, aff_id 14705)
  terminalesim:    'https://terminalesim.com',
  voye:            'https://voyeglobalconnectivity.pxf.io/AgB9dx', // Voye Impact tracking (acct 7205658, 15% / 30-day) → deep-links to voyeglobal.com/he Hebrew landing
  yesim:           'https://yesim.app/?partner_id=4804', // Yesim own program (partner_id 4804, ~10% recurring, 30-day)
  alosim:          'https://alosim.com/?oid=9&affid=1652', // aloSIM Everflow (affid 1652, $5/sale). Country deep-links: alosim.com/{country}-esim/?oid=9&affid=1652
  seven_g:         'https://esim-7g.app.link/alonyo_link', // 7G partner referral link (Branch slug "alonyo"). Coupon alonyo15 = 15% off / 15% commission; pending rename to MOCA.
  bcengi:          'https://bcengi.sjv.io/c/7447920/3242903/41060', // bcengi Impact tracking link (acct 7205658). 15% on Automated Refill + Online Purchase, 30-day. No MOCA coupon yet (generic DFB code only). Per-destination: bcengi.com has NO country pages, so /go/bcengi appends Impact SubIds (subId1=dest) to this one link instead of separate TrackingLinks.
  maya:            'https://mayamobile.pxf.io/oNV1xn', // Maya Impact tracking link (acct 7205658, 15-20% comm) → deep-links to maya.net/esim/plans. MOCA10 coupon also attributes.
  ubigi:           'https://go.ubigi.com/5kqGL1', // Ubigi (Transatel/NTT) Impact tracking link (acct 7205658, 10% first purchase / 60-day) → deep-links to cellulardata.ubigi.com plans page. Link issued directly by Cynthia Razafindrakoto (Ubigi Affiliate Manager) 2026-07-09, replacing the earlier self-generated MKgJG3.
  bytesim:         'https://bytesim.com/affiliate-program/sell-product?source_type=sales_plugin_af&slt=sales_plugin_af&productPage=1&referral_code=8F68HJS3KPDU', // ByteSim in-house affiliate program (referral_code 8F68HJS3KPDU, "up to 10% per sale"). Personal-store sell link; coupon "Moca" also attributes.
  breez:           'https://breezesim.com?sca_ref=11756847.LeXawwdfKwAOA', // Breeze UpPromote tracking link (sca_ref 11756847, 20% recurring/lifetime, 30-day). No MOCA coupon yet.
  gigsky:          'https://plans.gigsky.com/273MKQ4/2CTPL/', // GigSky via Everflow (aff 273MKQ4). 15% revshare + CPA (GigSky One $25 / VISA $4 / free $3). Coupon MOCA15 = 15% off. Sub-IDs (sub1=dest/sub2=src/sub5=hotel) attach on /go/gigsky; dashboard links direct to the tracking link.
  gomoworld:       'https://www.puremium1.com/aff_c?offer_id=23&aff_id=1968', // GoMoWorld via PUREMIUM (HasOffers/TUNE) offer 23, Affiliate ID 1968. 15% CPS every sale, payout EUR. Coupon MOCA set on offer (customer discount % pending Rana Doula). Portal supports Add Deep Link + Sub-ID for future per-dest/per-hotel.
  orbit:           'https://orbitmobile.sjv.io/k4kN50', // Orbit Mobile Impact tracking link (acct 7205658, 20% comm / 30-day click) → deep-links to orbitmobile.com. Approved 2026-07-08. MOCA coupon pending.
}

export const affiliateUrlFor = (carrier) => AFFILIATE_URLS[carrier] || `https://www.${carrier}.com`
