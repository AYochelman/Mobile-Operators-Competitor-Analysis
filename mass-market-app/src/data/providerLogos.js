// Single source of truth for the small square provider-logo chips on the public
// eSIM compare page (EsimComparePage) and the hotel guest portal (GuestPortalPage).
// Keyed by the scraper carrier id (the `provider` field in the /api/esim/compare
// and guest-portal feeds), NOT by domain.
//
// Why prefer these over the favicon CDN: the DuckDuckGo favicon service returns a
// generic globe/arrow placeholder with HTTP 200 for domains it has no real icon
// for, so the chip's <img onError> fallback never fires and the provider shows a
// grey arrow instead of a logo (e.g. BeSIM, Tasim). A curated local
// file always renders the real brand mark. Files live in public/logos/.
//
// Mirrors CARRIER_LOGOS in components/GroupedPlanCard.jsx (the dashboard's larger
// logo render) — kept separate because the chip is a uniform 42px square, so Tuki
// uses the square icon variant here while GroupedPlanCard uses the wide wordmark.
export const PROVIDER_LOGOS = {
  // global eSIM providers
  tuki:             '/logos/tuki-icon.png', // square icon (tuki.png is a wide wordmark)
  terminalesim:     '/logos/terminalesim.png',
  airalo:           '/logos/airalo.png',
  airalo_local:     '/logos/airalo.png',
  airalo_regional:  '/logos/airalo.png',
  pelephone_global: '/logos/pelephone_global.png',
  esimo:            '/logos/esimo.png',
  simtlv:           '/logos/simtlv.png',
  world8:           '/logos/world8.png',
  xphone_global:    '/logos/xphone_global.png',
  saily:            '/logos/saily.png',
  holafly:          '/logos/holafly.png',
  esimio:           '/logos/esimio.png',
  sparks:           '/logos/sparks.png',
  voye:             '/logos/voye.png',
  yesim:            '/logos/yesim.png',
  nomad:            '/logos/nomad.png',
  ubigi:            '/logos/ubigi.png',
  alosim:           '/logos/alosim.png',
  orbit:            '/logos/orbit.png',
  travelsim:        '/logos/travelsim.png',
  gomoworld:        '/logos/gomoworld.png',
  tasim:            '/logos/tasim.png',
  maya:             '/logos/maya.png',
  bcengi:           '/logos/bcengi.png',
  esim70:           '/logos/esim70.png',
  jetpack:          '/logos/jetpack.png',
  breez:            '/logos/breez.png',
  bytesim:          '/logos/bytesim.png',
  besim:            '/logos/besim.png',
  seven_g:          '/logos/seven_g.png',
  bestconnect:      '/logos/bestconnect.png',
  esimplus:         '/logos/esimplus.png',
  // local Israeli tourist SIMs (guest portal, include_local feed)
  mobile019:        '/logos/019.png',
  partner:          '/logos/partner.png',
  cellcom:          '/logos/cellcom.png',
  hot:              '/logos/hotmobile.png',
}
