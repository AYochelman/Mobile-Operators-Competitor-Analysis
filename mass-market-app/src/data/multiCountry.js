/**
 * Multi-country provider logic — single source of truth.
 *
 * Some global eSIM providers sell a single plan that covers many countries
 * (e.g. SimTLV, TravelSim, Airalo regional plans, GoMoWorld zones). The
 * dashboard's country/region filter needs to know which countries each plan
 * actually covers so users can find them by destination.
 *
 * Adding a new multi-country provider:
 *   1. Add the carrier id to MULTI_COUNTRY_CARRIERS below.
 *   2. Add a branch to getPlanCoverage() that returns the country list.
 *   3. Add the country list to data/globalCountries.js if it doesn't exist.
 *
 * This file is consumed by both DashboardPage and ComparePage so the two
 * pages stay in sync. Previously the same logic lived in two places (with
 * subtle drift) — see the audit MOCA_AUDIT_2026-05-01.md, finding C11.
 */

import {
  AIRALO_DISCOVER, AIRALO_REGION_MAP, GLOBALESIM_AFRICA, GLOBALESIM_ASIA,
  GLOBALESIM_NORTH_AMERICA, GLOBALESIM_SOUTH_AMERICA, GLOBALESIM_OCEANIA,
  GLOBALESIM_EUROPE, GLOBALESIM_GLOBAL_REGION, TUKI_COUNTRIES, GLOBALESIM_COUNTRIES,
  PELEPHONE_GLOBAL_COUNTRIES, ESIMO_COUNTRIES, SIMTLV_COUNTRIES,
  WORLD8_WORLDWIDE, WORLD8_EUROPE_USA, XPHONE_EUROPE, XPHONE_WORLD,
  ORBIT_COUNTRIES, TRAVELSIM_GLOBAL, TRAVELSIM_USA, TRAVELSIM_ME,
  GOMOWORLD_EUROPE, GOMOWORLD_LATIN_AMERICA, GOMOWORLD_SOUTHEAST_ASIA,
  GOMOWORLD_FRENCH_ANTILLES, GOMOWORLD_NETHERLANDS_ANTILLES, GOMOWORLD_NORTH_AMERICA,
  MAYA_GLOBAL, MAYA_OCEANIA,
} from './globalCountries'

/** Carriers where one plan covers many countries. The dashboard expands
 * these into the destination dropdown via getPlanCoverage(). */
export const MULTI_COUNTRY_CARRIERS = new Set([
  'travelsim', 'xphone_global', 'simtlv', 'world8', 'airalo',
  'airalo_regional', 'pelephone_global', 'esimo', 'globalesim',
  'gomoworld', 'maya',
])

const GLOBALESIM_REGION_MAP = {
  'אפריקה': GLOBALESIM_AFRICA,
  'אסיה': GLOBALESIM_ASIA,
  'צפון אמריקה': GLOBALESIM_NORTH_AMERICA,
  'דרום אמריקה': GLOBALESIM_SOUTH_AMERICA,
  'אוקיאניה': GLOBALESIM_OCEANIA,
  'אירופה': GLOBALESIM_EUROPE,
  'גלובלי': GLOBALESIM_GLOBAL_REGION,
}

const GOMOWORLD_ZONE_MAP = {
  'אירופה': GOMOWORLD_EUROPE,
  'אמריקה הלטינית': GOMOWORLD_LATIN_AMERICA,
  'דרום מזרח אסיה': GOMOWORLD_SOUTHEAST_ASIA,
  'האנטילים הצרפתיים': GOMOWORLD_FRENCH_ANTILLES,
  'אנטילים הולנדיים': GOMOWORLD_NETHERLANDS_ANTILLES,
  'צפון אמריקה': GOMOWORLD_NORTH_AMERICA,
}

/** Returns string[] of canonical country names this plan covers, or null
 * for single-country plans (caller should fall back to extras[0]). */
export function getPlanCoverage(plan) {
  const carrier = plan.carrier
  const dest = plan.extras?.[0] || ''
  const name = plan.plan_name || ''
  if (carrier === 'travelsim') {
    if (dest === 'ארצות הברית') return TRAVELSIM_USA
    if (dest === 'המזרח התיכון') return TRAVELSIM_ME
    return TRAVELSIM_GLOBAL
  }
  if (carrier === 'xphone_global') {
    return dest.startsWith('אירופה') ? XPHONE_EUROPE : XPHONE_WORLD
  }
  if (carrier === 'simtlv') return SIMTLV_COUNTRIES
  if (carrier === 'world8') {
    return (name.includes('אירופה') || name.includes('Europe')) ? WORLD8_EUROPE_USA : WORLD8_WORLDWIDE
  }
  if (carrier === 'airalo') return AIRALO_DISCOVER
  if (carrier === 'airalo_regional') return AIRALO_REGION_MAP[dest] || null
  if (carrier === 'pelephone_global') return PELEPHONE_GLOBAL_COUNTRIES
  if (carrier === 'esimo') return ESIMO_COUNTRIES
  if (carrier === 'globalesim') return GLOBALESIM_REGION_MAP[dest] || GLOBALESIM_GLOBAL_REGION
  if (carrier === 'gomoworld') return GOMOWORLD_ZONE_MAP[dest] || null
  if (carrier === 'maya') {
    if (dest === 'גלובלי') return MAYA_GLOBAL
    if (dest === 'אוקיאניה') return MAYA_OCEANIA
    return null
  }
  return null
}

/** Static country lists for ComparePage's country filter. Used when the
 * data itself doesn't carry per-plan country info. Mirrors what
 * getPlanCoverage() returns for the same carrier. */
export const CARRIER_COUNTRY_LISTS = {
  tuki: TUKI_COUNTRIES,
  globalesim: GLOBALESIM_COUNTRIES,
  airalo: AIRALO_DISCOVER,
  pelephone_global: PELEPHONE_GLOBAL_COUNTRIES,
  esimo: ESIMO_COUNTRIES,
  simtlv: SIMTLV_COUNTRIES,
  world8: [...new Set([...WORLD8_WORLDWIDE, ...WORLD8_EUROPE_USA])],
  xphone_global: [...new Set([...XPHONE_EUROPE, ...XPHONE_WORLD])],
  orbit: ORBIT_COUNTRIES,
  travelsim: [...new Set([...TRAVELSIM_GLOBAL, ...TRAVELSIM_USA, ...TRAVELSIM_ME])],
}

/** Region keywords that should be treated as regions (not country names)
 * when parsing extras[0]. Single source of truth — DashboardPage and
 * ComparePage both consume this so they can't drift. */
export const KNOWN_REGIONS = new Set([
  'אירופה','אסיה','אסיה ואוקיאניה','אפריקה','גלובלי','קריביים','איי הקריביים',
  'אמריקה הלטינית','צפון אמריקה','המזרח התיכון','המזרח התיכון וצפון אפריקה',
  'דרום מזרח אסיה','סקנדינביה','בלקן','מזרח אירופה','מרכז אמריקה','אוקיאניה',
  'סין + הונג קונג + מקאו','יפן וקוריאה','יפן וסין',
  'אסיה פסיפיק','מרכז אסיה','צפון אפריקה',
  'שוויץ+','גוודלופ','קפריסין+',
  'אמריקה הדרומית','דרום אמריקה',
  'צפון ודרום אמריקה','מדינות האיים הקריביים',
  'אירופה — גלישה בלבד','אירופה — גולשים ומדברים',
  '167+ מדינות','156+ מדינות',
  'ספארי אפריקה','האיחוד האירופי ובריטניה',
  'הקריביים','כלל העולם',
  // Breeze regions
  'אירופה+','אמריקה המרכזית','הבלקן','חבר המדינות',
  'אירופה וארה"ב','פורטוגל וספרד','המזרח התיכון לייט','אירופה לייט',
  // Additional from older lists (kept to avoid drift)
  'איי התעלה','האנטילים הצרפתיים','אנטילים הולנדיים',
])
