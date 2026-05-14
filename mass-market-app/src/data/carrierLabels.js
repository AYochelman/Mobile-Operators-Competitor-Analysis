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

export const ALL_CARRIER_LABELS = {
  ...DOMESTIC_LABELS,
  ...GLOBAL_LABELS,
}

export function carrierLabel(id) {
  return ALL_CARRIER_LABELS[id] || id
}
