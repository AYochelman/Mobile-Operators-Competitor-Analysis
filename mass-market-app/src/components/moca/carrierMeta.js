/**
 * Carrier metadata for MOCA design-system primitives.
 *
 * Single source for the avatar chip color + glyph used by <CarrierChip>.
 * Colors are sourced from `mvnoBrandColors.js` (the real brand colors,
 * already used by `BrandThemeApplier`) so the chip matches workspace theming.
 *
 * `CHIP_LETTERS` overrides the auto-derived first letter where two carriers
 * share the same first character (e.g. partner + pelephone both start with פ).
 */

import { MVNO_BRAND_COLORS } from '../../data/mvnoBrandColors'
import { ALL_CARRIER_LABELS } from '../../data/carrierLabels'

const CHIP_LETTERS = {
  partner:    'פר',
  pelephone:  'פל',
  cellcom:    'ס',
  hotmobile:  'H',
  mobile019:  '019',
  xphone:     'X',
  wecom:      'W',
  neptucom:   'N',
  golan:      'ג',
  rami_levy:  'רל',
}

const FALLBACK_COLOR = '#a08468'

export function getCarrierColor(id) {
  return MVNO_BRAND_COLORS[id]?.primary || FALLBACK_COLOR
}

export function getCarrierLetter(id) {
  if (CHIP_LETTERS[id]) return CHIP_LETTERS[id]
  const label = ALL_CARRIER_LABELS[id] || id
  return label.charAt(0).toUpperCase()
}

export function getCarrierName(id) {
  return ALL_CARRIER_LABELS[id] || id
}

/**
 * Carrier id → brand logo path (served from `public/logos/`).
 * Single source of truth — consumed by <PlanCard> and by <CarrierChip logo />.
 * Keep mobile019→019.png and xphone→xphone_global.png mappings (no dedicated files).
 */
export const CARRIER_LOGOS = {
  // Domestic
  neptucom:         '/logos/neptucom.png',
  partner:          '/logos/partner.png',
  pelephone:        '/logos/pelephone.png',
  hotmobile:        '/logos/hotmobile.png',
  cellcom:          '/logos/cellcom.png',
  mobile019:        '/logos/019.png',
  xphone:           '/logos/xphone_global.png',
  wecom:            '/logos/wecom.png',
  golan:            '/logos/golan.png',
  rami_levy:        '/logos/rami_levy.png',
  // Global eSIM
  tuki:             '/logos/tuki.png',
  terminalesim:     '/logos/terminalesim.png',
  gigsky:           '/logos/gigsky.png',
  esimgenius:       '/logos/esimgenius.png',
  nisim:            '/logos/nisim.png',
  esimax:           '/logos/esimax.png',
  venterrasim:      '/logos/venterrasim.png',
  simzol:           '/logos/simzol.png',
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
  ubigi:            '/logos/ubigi.svg',
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
  bnesim:           '/logos/bnesim.png',
  seven_g:          '/logos/seven_g.png',
  bestconnect:      '/logos/bestconnect.png',
  esimplus:         '/logos/esimplus.png',
}

export function getCarrierLogo(id) {
  return CARRIER_LOGOS[id] || null
}
