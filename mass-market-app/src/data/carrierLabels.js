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
}

export const ALL_CARRIER_LABELS = {
  ...DOMESTIC_LABELS,
  ...GLOBAL_LABELS,
}

export function carrierLabel(id) {
  return ALL_CARRIER_LABELS[id] || id
}

/** Reverse map: Hebrew/English label → { id, tab } for ChatPanel-style
 * carrier-name detection in free text. Includes lower-case + the id itself
 * as recognizable forms so users can write "saily" or "Saily" or
 * "Maya Mobile" interchangeably.
 *
 * Tab is 'domestic' for entries in DOMESTIC_LABELS, 'global' otherwise.
 */
export const CARRIER_NAME_TO_ID = (() => {
  const map = {}
  const add = (label, id, tab) => {
    if (!label) return
    map[label] = { id, tab }
    // Also include lower-case variant for English labels
    const lower = label.toLowerCase()
    if (lower !== label) map[lower] = { id, tab }
  }
  for (const [id, label] of Object.entries(DOMESTIC_LABELS)) {
    add(label, id, 'domestic')
    add(id, id, 'domestic')
  }
  for (const [id, label] of Object.entries(GLOBAL_LABELS)) {
    add(label, id, 'global')
    add(id, id, 'global')
  }
  return map
})()
