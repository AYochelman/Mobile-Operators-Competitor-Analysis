// Multi-country global providers and their per-plan coverage lists.
// Extracted from DashboardPage.jsx (2026-09). When adding a multi-country
// provider: add its arrays to globalCountries.js, its id to MULTI_COUNTRY_CARRIERS
// and a branch in getPlanCoverage() (ComparePage mirrors this in CARRIER_COUNTRY_LISTS).
import {
  TRAVELSIM_GLOBAL, TRAVELSIM_USA, TRAVELSIM_ME,
  SIMTLV_COUNTRIES, PELEPHONE_GLOBAL_COUNTRIES, ESIMO_REGION_MAP,
  WORLD8_EUROPE_USA, WORLD8_WORLDWIDE,
  XPHONE_EUROPE, XPHONE_WORLD,
  AIRALO_DISCOVER,
  AIRALO_REGION_MAP,
  TERMINAL_EUROPE, TERMINAL_ASIA, TERMINAL_NORTH_AMERICA,
  TERMINAL_SOUTH_AMERICA, TERMINAL_AFRICA, TERMINAL_OCEANIA, TERMINAL_GLOBAL_REGION,
  GOMOWORLD_EUROPE, GOMOWORLD_LATIN_AMERICA, GOMOWORLD_SOUTHEAST_ASIA,
  GOMOWORLD_FRENCH_ANTILLES, GOMOWORLD_NETHERLANDS_ANTILLES, GOMOWORLD_NORTH_AMERICA,
  MAYA_GLOBAL, MAYA_OCEANIA,
  BESIM_REGION_MAP,
  BESTCONNECT_REGION_MAP,
  ESIMPLUS_REGION_MAP,
  SEVEN_G_REGION_MAP,
  GIGSKY_REGION_MAP,
  ESIMGENIUS_REGION_MAP,
  ESIMAX_REGION_MAP, ESIMAX_EUROPE_30,
  VENTERRA_REGION_MAP,
  SIMZOL_REGION_MAP,
} from './globalCountries'

// Carriers where one plan covers many countries (zone/global plans)
export const MULTI_COUNTRY_CARRIERS = new Set([
  'travelsim', 'xphone_global', 'simtlv', 'world8', 'airalo', 'airalo_regional',
  'pelephone_global', 'esimo', 'terminalesim', 'gomoworld', 'maya', 'besim',
  'bestconnect', 'esimplus', 'seven_g', 'gigsky', 'esimgenius', 'esimax',
  'venterrasim', 'simzol',
])

const TERMINAL_REGION_MAP = {
  'אפריקה': TERMINAL_AFRICA,
  'אסיה': TERMINAL_ASIA,
  'צפון אמריקה': TERMINAL_NORTH_AMERICA,
  'דרום אמריקה': TERMINAL_SOUTH_AMERICA,
  'אוקיאניה': TERMINAL_OCEANIA,
  'אירופה': TERMINAL_EUROPE,
  'גלובלי': TERMINAL_GLOBAL_REGION,
}

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
  if (carrier === 'simtlv') {
    // Only the 127-country bundles expand to the full coverage list.
    // Per-country and regional catalog plans (extras[0] = country name or
    // 'אירופה (N מדינות)' label) return null → extras[0] equality fallback.
    return dest === '127 מדינות' ? SIMTLV_COUNTRIES : null
  }
  if (carrier === 'world8') {
    return (name.includes('אירופה') || name.includes('Europe')) ? WORLD8_EUROPE_USA : WORLD8_WORLDWIDE
  }
  if (carrier === 'airalo') return AIRALO_DISCOVER
  if (carrier === 'airalo_regional') return AIRALO_REGION_MAP[dest] || null
  if (carrier === 'pelephone_global') return PELEPHONE_GLOBAL_COUNTRIES
  if (carrier === 'esimo') {
    // Regional/global products expand to their coverage list; per-country plans
    // return null → the destination filter falls back to extras[0] equality.
    return ESIMO_REGION_MAP[dest] || null
  }
  if (carrier === 'terminalesim') return TERMINAL_REGION_MAP[dest] || null
  if (carrier === 'gomoworld') {
    const GOMOWORLD_ZONE_MAP = {
      'אירופה': GOMOWORLD_EUROPE, 'אמריקה הלטינית': GOMOWORLD_LATIN_AMERICA,
      'דרום מזרח אסיה': GOMOWORLD_SOUTHEAST_ASIA, 'האנטילים הצרפתיים': GOMOWORLD_FRENCH_ANTILLES,
      'אנטילים הולנדיים': GOMOWORLD_NETHERLANDS_ANTILLES, 'צפון אמריקה': GOMOWORLD_NORTH_AMERICA,
    }
    return GOMOWORLD_ZONE_MAP[dest] || null
  }
  if (carrier === 'maya') {
    if (dest === 'גלובלי') return MAYA_GLOBAL
    if (dest === 'אוקיאניה') return MAYA_OCEANIA
    return null
  }
  if (carrier === 'besim') {
    // Per-country plans: extras[0] is a country name (not a region) — return null so the
    // dashboard's destination-filter falls back to direct-equality matching on extras[0].
    // Regional/global bundles: extras[0] is a canonical region name → expand via the map.
    return BESIM_REGION_MAP[dest] || null
  }
  if (carrier === 'bestconnect') return BESTCONNECT_REGION_MAP[dest] || null
  if (carrier === 'esimplus') return ESIMPLUS_REGION_MAP[dest] || null
  if (carrier === 'gigsky') {
    // Regional + global bundles expand to their coverage list. Per-country plans
    // and cruise labels ("קרוז - …") aren't keys → null → extras[0] equality /
    // unified cruise filter handle them.
    return GIGSKY_REGION_MAP[dest] || null
  }
  if (carrier === 'esimgenius') {
    // Regional + global bundles expand to their coverage list; per-country
    // plans return null → extras[0] equality.
    return ESIMGENIUS_REGION_MAP[dest] || null
  }
  if (carrier === 'esimax') {
    // "אירופה 30+" shares dest 'אירופה' with the full-Europe bundle but covers
    // fewer countries — match it by plan-name prefix before the dest lookup.
    if (name.startsWith('אירופה 30+')) return ESIMAX_EUROPE_30
    return ESIMAX_REGION_MAP[dest] || null
  }
  if (carrier === 'venterrasim') {
    // Coverage varies per bundle within one destination (Europe 33/35/41 areas,
    // Asia 7/20, South America 6/20), so the map is keyed by the plan_name title.
    const title = name.split(' – ')[0].replace(/\u200f/g, '').trim()
    return VENTERRA_REGION_MAP[title] || null
  }
  if (carrier === 'simzol') {
    // 'גלובלי' covers two products with different country lists (eSIM packages
    // vs the physical 'פלטינום' SIM), so key on the plan_name title.
    const title = name.split(' – ')[0].replace(/\u200f/g, '').trim()
    return SIMZOL_REGION_MAP[title] || null
  }
  if (carrier === 'seven_g') {
    // plan_name first segment is the English region name (e.g. "Asia (12 areas)")
    const regionName = (name || '').split(' – ')[0]?.trim() || ''
    return SEVEN_G_REGION_MAP[regionName] || null
  }
  return null
}
