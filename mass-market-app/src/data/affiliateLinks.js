// Canonical affiliate config for global eSIM providers — SINGLE SOURCE OF TRUTH.
// Imported by PlanCard and GroupedPlanCard. These used to keep separate copies
// that drifted (Saily's tracking link was updated in PlanCard but GroupedPlanCard
// still pointed at saily.com with no tracking, and Voye was missing from the
// grouped view) — keep all affiliate links here only.
//
// A provider in AFFILIATE_PROVIDERS renders a "רכישה / דרך MOCA" button. Providers
// with a signed tracking link redirect with attribution; the rest fall back to the
// provider homepage until their program link is wired.
export const AFFILIATE_PROVIDERS = new Set([
  'airalo', 'airalo_local', 'airalo_regional', 'holafly', 'saily', 'terminalesim', 'voye', 'yesim', 'alosim', 'seven_g', 'bcengi', 'maya', 'ubigi',
])

export const AFFILIATE_URLS = {
  airalo:          'https://www.airalo.com',
  airalo_local:    'https://www.airalo.com',
  airalo_regional: 'https://www.airalo.com',
  holafly:         'https://esim.holafly.com',
  saily:           'https://go.saily.site/aff_c?offer_id=101&aff_id=14705', // Saily affiliate tracking (offer_id 101, aff_id 14705)
  terminalesim:    'https://terminalesim.com',
  voye:            'https://voyeglobalconnectivity.pxf.io/AgB9dx', // Voye Impact tracking (acct 7205658, 15% / 30-day) → deep-links to voyeglobal.com/he Hebrew landing
  yesim:           'https://yesim.app/?partner_id=4804', // Yesim own program (partner_id 4804, ~10% recurring, 30-day)
  alosim:          'https://alosim.com/?oid=9&affid=1652', // aloSIM Everflow (affid 1652, $5/sale). Country deep-links: alosim.com/{country}-esim/?oid=9&affid=1652
  seven_g:         'https://esim-7g.app.link/alonyo_link', // 7G partner referral link (Branch slug "alonyo"). Coupon alonyo15 = 15% off / 15% commission; pending rename to MOCA.
  bcengi:          'https://bcengi.sjv.io/c/7447920/3242903/41060', // bcengi Impact tracking link (acct 7205658). 15% on Automated Refill + Online Purchase, 30-day. No MOCA coupon yet (generic DFB code only).
  maya:            'https://mayamobile.pxf.io/oNV1xn', // Maya Impact tracking link (acct 7205658, 15-20% comm) → deep-links to maya.net/esim/plans. MOCA10 coupon also attributes.
  ubigi:           'https://go.ubigi.com/MKgJG3', // Ubigi (Transatel/NTT) Impact tracking link (acct 7205658, 10% first purchase / 60-day) → deep-links to cellulardata.ubigi.com plans page.
}

export const affiliateUrlFor = (carrier) => AFFILIATE_URLS[carrier] || `https://www.${carrier}.com`
