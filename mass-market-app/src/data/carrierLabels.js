/**
 * Canonical carrier ID → Hebrew/display label.
 *
 * Single source of truth. ALL components that need to translate a carrier
 * identifier to its display name MUST import from here (PlanCard, GroupedPlanCard,
 * ComparePage, TimeMachineModal). Add new carriers in one place and they will
 * appear everywhere — no more local GLOBAL_LABELS copies drifting out of sync.
 *
 * Mirrors in app.py: `_CARRIER_NAMES` and `_HISTORY_CARRIER_NAMES` (keep in sync).
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

/**
 * GLOBAL PROVIDER REGISTRY — the SINGLE SOURCE OF TRUTH for global eSIM providers.
 *
 * Add a new global provider as ONE row here and it propagates to every frontend
 * list automatically — no more editing five hand-maintained copies (which is how
 * a provider ends up in the data/API yet missing from chips, labels, colors, or
 * the affiliate button). Everything below this array is *derived*:
 *   - GLOBAL_LABELS        (id → label)            — PlanCard, GroupedPlanCard, TimeMachineModal
 *   - GLOBAL_COLORS        (id → Badge token)      — PlanCard / GroupedPlanCard provider badge
 *   - GLOBAL_CHART_COLORS  (id → hex)              — ComparePage chart series/legend
 *   - GLOBAL_PROVIDERS         ([{id,label}])      — DashboardPage + AlertsPriceTab filter chips
 *   - GLOBAL_PROVIDERS_WITH_COLOR ([{id,label,color:hex}]) — ComparePage CARRIERS_BY_TAB.global
 *   - ISRAELI_GLOBAL_PROVIDERS (Set)               — derived from the `israeli` flag
 *
 * Fields per row:
 *   id         — canonical carrier id (matches the scraper + DB `carrier` column)
 *   label      — display name (brand-cased Latin or Hebrew)
 *   color      — Badge color token for the provider chip on cards (omit/null → gray)
 *   chartColor — hex used as the per-provider series color in the compare chart
 *   israeli    — true for Israeli (Hebrew-facing) providers; drives the "סוג ספק" filter
 *   aliases    — extra carrier ids sharing this row's label+color (e.g. Airalo stores
 *                local/regional/global as three DB rows). Filter chips/charts use only `id`.
 *
 * Row order = display order of the provider filter chips (alphabetical by label,
 * with the most recently added providers appended at the end).
 *
 * ⚠️ SERVER-SIDE MIRRORS live in app.py and are NOT derived from this file — when you
 * add a provider here you must still update, by hand, app.py's `_CARRIER_NAMES`,
 * `_HISTORY_CARRIER_NAMES`, `_GUEST_PROVIDER_META`, and the scraper registration in
 * `scrape_all_global`.
 *
 * `israeli` flag verified 2026-06-11 against the live sites + the domains scraped in
 * scraper.py: .co.il domains or a Hebrew interface — tasim.us is lang=he (targets
 * Israelis visiting the USA); 7g.app serves a full Hebrew locale. Tuki + GlobalSIM are
 * Pelephone brands. Deliberately NOT israeli: breez (ILS + Israeli-targeted but
 * English-only site), holafly/airalo (full Hebrew locale, but foreign companies).
 */
export const GLOBAL_PROVIDERS_REGISTRY = [
  { id: 'seven_g',          label: '7G',           color: 'violet',  chartColor: '#7c3aed', israeli: true,  aliases: [] },
  { id: 'world8',           label: '8 World',      color: 'teal',    chartColor: '#0d9488', israeli: true },
  { id: 'airalo',           label: 'Airalo',       color: 'orange',  chartColor: '#f97316', israeli: false, aliases: ['airalo_local', 'airalo_regional'] },
  { id: 'bcengi',           label: 'Bcengi',       color: null,      chartColor: '#1d4ed8', israeli: false },
  { id: 'besim',            label: 'Besim',        color: 'teal',    chartColor: '#0ea5a4', israeli: true },
  { id: 'bestconnect',      label: 'Best Connect', color: 'blue',    chartColor: '#0f766e', israeli: false },
  { id: 'bnesim',           label: 'BNESIM',       color: 'blue',    chartColor: '#1e3a8a', israeli: false },
  { id: 'breez',            label: 'Breeze',       color: 'cyan',    chartColor: '#06b6d4', israeli: false },
  { id: 'bytesim',          label: 'ByteSim',      color: 'emerald', chartColor: '#00b490', israeli: false },
  { id: 'esimplus',         label: 'eSIM Plus',    color: 'blue',    chartColor: '#059669', israeli: false },
  { id: 'esimio',           label: 'eSIM.io',      color: 'blue',    chartColor: '#2563eb', israeli: false },
  { id: 'esim70',           label: 'eSIM70',       color: 'emerald', chartColor: '#10b981', israeli: false },
  { id: 'esimo',            label: 'eSIMo',        color: 'purple',  chartColor: '#a855f7', israeli: false },
  { id: 'terminalesim',     label: 'Terminal eSIM', color: 'green',  chartColor: '#22c55e', israeli: true },
  { id: 'pelephone_global', label: 'GlobalSIM',    color: 'blue',    chartColor: '#2196f3', israeli: true },
  { id: 'gomoworld',        label: 'GoMoWorld',    color: 'cyan',    chartColor: '#0891b2', israeli: false },
  { id: 'holafly',          label: 'Holafly',      color: 'orange',  chartColor: '#ea580c', israeli: false },
  { id: 'jetpack',          label: 'Jetpack',      color: 'sky',     chartColor: '#0ea5e9', israeli: false },
  { id: 'maya',             label: 'Maya Mobile',  color: 'teal',    chartColor: '#0f766e', israeli: false },
  { id: 'orbit',            label: 'Orbit',        color: 'indigo',  chartColor: '#6366f1', israeli: false },
  { id: 'saily',            label: 'Saily',        color: 'purple',  chartColor: '#7c3aed', israeli: false },
  { id: 'simtlv',           label: 'SimTLV',       color: 'red',     chartColor: '#ef4444', israeli: true },
  { id: 'sparks',           label: 'Sparks',       color: 'amber',   chartColor: '#f59e0b', israeli: false },
  { id: 'tasim',            label: 'Tasim',        color: 'violet',  chartColor: '#7c3aed', israeli: true },
  { id: 'travelsim',        label: 'Travel Sim',   color: 'teal',    chartColor: '#0d9488', israeli: true },
  { id: 'tuki',             label: 'Tuki',         color: 'blue',    chartColor: '#3b82f6', israeli: true },
  { id: 'voye',             label: 'VOYE',         color: 'pink',    chartColor: '#ec4899', israeli: false },
  { id: 'xphone_global',    label: 'XPhone Global',color: 'teal',    chartColor: '#14b8a6', israeli: true },
  { id: 'yesim',            label: 'Yesim',        color: 'orange',  chartColor: '#f97316', israeli: false },
  { id: 'nomad',            label: 'Nomad',        color: 'green',   chartColor: '#16a34a', israeli: false },
  { id: 'ubigi',            label: 'Ubigi',        color: 'sky',     chartColor: '#2563eb', israeli: false },
  { id: 'alosim',           label: 'aloSIM',       color: 'red',     chartColor: '#dc2626', israeli: false },
]

// --- Derived lists (do not hand-edit; change GLOBAL_PROVIDERS_REGISTRY above) -------

// id → display label, including each provider's aliases (e.g. airalo_local → 'Airalo').
export const GLOBAL_LABELS = Object.fromEntries(
  GLOBAL_PROVIDERS_REGISTRY.flatMap(p => [
    [p.id, p.label],
    ...(p.aliases || []).map(a => [a, p.label]),
  ])
)

// id → Badge color token for the provider chip on cards. Providers with no color
// (e.g. bcengi) are omitted so the Badge falls back to its default gray. Aliases
// inherit the parent provider's color.
export const GLOBAL_COLORS = Object.fromEntries(
  GLOBAL_PROVIDERS_REGISTRY.flatMap(p =>
    p.color
      ? [[p.id, p.color], ...(p.aliases || []).map(a => [a, p.color])]
      : []
  )
)

// id → hex, the per-provider series color used by the compare chart.
export const GLOBAL_CHART_COLORS = Object.fromEntries(
  GLOBAL_PROVIDERS_REGISTRY.map(p => [p.id, p.chartColor])
)

// [{ id, label }] — provider filter chips on the dashboard + alerts (no aliases).
export const GLOBAL_PROVIDERS = GLOBAL_PROVIDERS_REGISTRY.map(({ id, label }) => ({ id, label }))

// [{ id, label, color }] — ComparePage CARRIERS_BY_TAB.global (color = chart hex).
export const GLOBAL_PROVIDERS_WITH_COLOR = GLOBAL_PROVIDERS_REGISTRY.map(
  ({ id, label, chartColor }) => ({ id, label, color: chartColor })
)

/**
 * Global eSIM providers that are Israeli (Hebrew-facing site) — derived from the
 * `israeli` flag. Drives the "סוג ספק" filter on the global (eSIM) tab.
 */
export const ISRAELI_GLOBAL_PROVIDERS = new Set(
  GLOBAL_PROVIDERS_REGISTRY.filter(p => p.israeli).map(p => p.id)
)

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
