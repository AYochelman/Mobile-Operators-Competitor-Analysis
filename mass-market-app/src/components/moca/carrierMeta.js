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
