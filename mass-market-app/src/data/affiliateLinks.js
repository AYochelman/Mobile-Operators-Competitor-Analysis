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
  'airalo', 'airalo_local', 'airalo_regional', 'holafly', 'saily', 'globalesim', 'voye', 'yesim', 'alosim',
])

export const AFFILIATE_URLS = {
  airalo:          'https://www.airalo.com',
  airalo_local:    'https://www.airalo.com',
  airalo_regional: 'https://www.airalo.com',
  holafly:         'https://esim.holafly.com',
  saily:           'https://go.saily.site/aff_c?offer_id=101&aff_id=14705', // Saily affiliate tracking (offer_id 101, aff_id 14705)
  globalesim:      'https://globalesim.com',
  voye:            'https://voyeglobalconnectivity.pxf.io/QYAoKa', // Voye Impact tracking (acct 7205658, 15% / 30-day)
  yesim:           'https://yesim.app/?partner_id=4804', // Yesim own program (partner_id 4804, ~10% recurring, 30-day)
  alosim:          'https://alosim.com/?oid=9&affid=1652', // aloSIM Everflow (affid 1652, $5/sale). Country deep-links: alosim.com/{country}-esim/?oid=9&affid=1652
}

export const affiliateUrlFor = (carrier) => AFFILIATE_URLS[carrier] || `https://www.${carrier}.com`
