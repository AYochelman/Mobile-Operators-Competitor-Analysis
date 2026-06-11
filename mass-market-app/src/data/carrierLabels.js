/**
 * Canonical carrier ID → Hebrew/display label.
 *
 * Single source of truth. ALL components that need to translate a carrier
 * identifier to its display name MUST import from here. Add new carriers in
 * one place and they will appear everywhere.
 *
 * Mirror in app.py: `_CARRIER_NAMES` (keep in sync).
 */

export const DOMESTIC_LABELS = {
  partner:    'פרטנר',
  pelephone:  'פלאפון',
  hotmobile:  'הוט מובייל',
  cellcom:    'סלקום',
  mobile019:  '019',
  xphone:     'XPhone',
  wecom:      'We-Com',
  neptucom:   'Neptucom',
  golan:      'גולן טלקום',
  rami_levy:  'רמי לוי תקשורת',
}

export const GLOBAL_LABELS = {
  seven_g:          '7G',
  tuki:             'Tuki',
  globalesim:       'GlobaleSIM',
  airalo:           'Airalo',
  airalo_local:     'Airalo',          // alias — backend stores three rows for Airalo
  airalo_regional:  'Airalo',          // alias
  pelephone_global: 'GlobalSIM',
  esimo:            'eSIMo',
  simtlv:           'SimTLV',
  world8:           '8 World',
  xphone_global:    'XPhone Global',
  saily:            'Saily',
  holafly:          'Holafly',
  esimio:           'eSIM.io',
  sparks:           'Sparks',
  voye:             'VOYE',
  orbit:            'Orbit',
  travelsim:        'Travel Sim',
  gomoworld:        'GoMoWorld',
  tasim:            'Tasim',
  maya:             'Maya Mobile',
  bcengi:           'Bcengi',
  esim70:           'eSIM70',
  jetpack:          'Jetpack',
  breez:            'Breeze',
  bytesim:          'ByteSim',
  bestconnect:      'Best Connect',
  besim:            'Besim',
  esimplus:         'eSIM Plus',
}

/**
 * Global eSIM providers that are Israeli (Hebrew-facing site).
 * Verified 2026-06-11 against the live sites + the domains scraped in scraper.py:
 * .co.il domains, or a Hebrew interface — tasim.us is lang=he (targets Israelis
 * visiting the USA); 7g.app serves a full Hebrew locale ("שמירת מספר ישראלי בחו״ל").
 * Tuki + GlobalSIM are Pelephone brands.
 * Deliberately EXCLUDED: breez (ILS pricing + Israeli-targeted, but English-only
 * site), holafly/airalo (full Hebrew locale, but foreign companies).
 * Drives the "סוג ספק" filter on the global (eSIM) tab.
 */
export const ISRAELI_GLOBAL_PROVIDERS = new Set([
  'tuki', 'pelephone_global', 'globalesim', 'simtlv', 'world8',
  'xphone_global', 'travelsim', 'besim', 'tasim', 'seven_g',
])

/**
 * US operators selling prepaid plans suitable for inbound tourists —
 * drives the "נוחתים בארה"ב" tab. Data is seeded (seed_usa_tourist.py),
 * not scraped. Mirror in app.py: `_CARRIER_NAMES`.
 */
export const USA_LABELS = {
  tmobile_prepaid: 'T-Mobile Prepaid',
  att_prepaid:     'AT&T Prepaid',
  verizon_prepaid: 'Verizon Prepaid',
  mint:            'Mint Mobile',
  ultra:           'Ultra Mobile',
  lyca_usa:        'Lycamobile USA',
  tello:           'Tello',
  metro:           'Metro by T-Mobile',
  simple_mobile:   'Simple Mobile',
  cricket:         'Cricket Wireless',
  h2o:             'H2O Wireless',
  visible:         'Visible',
  us_mobile:       'US Mobile',
  red_pocket:      'Red Pocket',
  straight_talk:   'Straight Talk',
  total_wireless:  'Total Wireless',
  boost:           'Boost Mobile',
}

export const ALL_CARRIER_LABELS = {
  ...DOMESTIC_LABELS,
  ...GLOBAL_LABELS,
  ...USA_LABELS,
}

export function carrierLabel(id) {
  return ALL_CARRIER_LABELS[id] || id
}
