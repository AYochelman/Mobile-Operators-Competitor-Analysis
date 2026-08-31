/**
 * Carrier / provider id → official homepage URL.
 *
 * The click-out target for plan cards: the B2B dashboard's "לאתר הספק" button
 * (PlanCard) and the public /mobile-deals consumer page's carrier CTA. Global
 * eSIM providers with an affiliate program are routed through /go instead
 * (see data/affiliateLinks.js) — these URLs are the unattributed fallback.
 * Moved out of PlanCard.jsx so non-component files can import it without
 * tripping react-refresh's only-export-components rule.
 */
export const CARRIER_HOME_URLS = {
  partner:         'https://www.partner.net.il',
  pelephone:       'https://www.pelephone.co.il',
  hotmobile:       'https://www.hotmobile.co.il',
  cellcom:         'https://www.cellcom.co.il',
  mobile019:       'https://www.019mobile.co.il',
  xphone:          'https://www.xphone.co.il',
  wecom:           'https://we-com.co.il',
  neptucom:        'https://www.neptucom.com',
  golan:           'https://www.golantelecom.co.il',
  rami_levy:       'https://mobile.rami-levy.co.il',
  tuki:            'https://tuki.co.il',
  terminalesim:    'https://terminalesim.com',
  airalo:          'https://www.airalo.com',
  pelephone_global:'https://www.pelephone.co.il',
  esimo:           'https://esimo.co.il',
  simtlv:          'https://www.simtlv.co.il',
  world8:          'https://world8.com',
  xphone_global:   'https://www.xphone.co.il',
  saily:           'https://saily.com',
  holafly:         'https://esim.holafly.com',
  esimio:          'https://esim.io',
  sparks:          'https://sparksesim.com',
  voye:            'https://voyeglobal.com',
  yesim:           'https://yesim.app',
  nomad:           'https://www.nomadesim.com',
  ubigi:           'https://www.ubigi.com',
  alosim:          'https://alosim.com',
  orbit:           'https://www.orbitmobile.com',
  travelsim:       'https://www.travelsim.com',
  gomoworld:       'https://www.gomoworld.com',
  tasim:           'https://www.tasim.us',
  maya:            'https://maya.net/esim',
  esim70:          'https://www.esim70.com',
  jetpack:         'https://www.jetpacglobal.com',
  besim:           'https://besim.co.il',
  seven_g:         'https://7g.app',
  bestconnect:     'https://bestconnect.online',
  esimplus:        'https://esimplus.me',
}
