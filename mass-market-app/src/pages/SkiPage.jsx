// "גלישה לגולשים" (/ski) - data packages for ski trips.
//
// A VIEW over data the app already has, no scraper of its own: the global eSIM
// catalog (/api/global-plans) and the Israeli carriers' roaming packages
// (/api/abroad-plans), cut down to the 20 countries that have ski resorts on
// WeSki (data/skiResorts.js). Coverage is sold per country, so picking a resort
// only picks its country.
import { useState, useEffect, useMemo, useRef, startTransition } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { filterAndSortPlans, groupGlobalDisplayItems } from '../hooks/useDashboardPlans'
import { MULTI_COUNTRY_CARRIERS, getPlanCoverage } from '../data/planCoverage'
import { getCountriesForAbroadPlan } from '../data/abroadCountries'
import { destKey, isCruiseDest } from '../data/destI18n'
import { DOMESTIC_LABELS } from '../data/carrierLabels'
import { SKI_COUNTRIES, SKI_RESORT_COUNT, resortLabel } from '../data/skiResorts'
import PlanCard from '../components/PlanCard'
import GroupedPlanCard from '../components/GroupedPlanCard'
import FilterTag from '../components/ui/FilterTag'
import SearchableSelect from '../components/ui/SearchableSelect'
import Spinner from '../components/ui/Spinner'

const DOMESTIC_IDS = Object.keys(DOMESTIC_LABELS)
const SKI_KEYS = new Map(SKI_COUNTRIES.map(c => [destKey(c.he), c.id]))
const PAGE = 60

// A package worth quoting for a ski week: at least a week long and 5GB (or
// unlimited). The raw catalog minimum is a ~1 ₪ one-day package, which says nothing.
const isSkiWeek = (p) => (p.days ?? 0) >= 7 && (p.data_gb == null || p.data_gb >= 5)

/** country id -> global plans that cover it (multi-country bundles expanded). */
function indexGlobal(plans) {
  const out = new Map(SKI_COUNTRIES.map(c => [c.id, []]))
  for (const p of plans) {
    const dest = p.extras?.[0]
    if (!dest || isCruiseDest(dest)) continue
    const coverage = MULTI_COUNTRY_CARRIERS.has(p.carrier) ? getPlanCoverage(p) : null
    if (coverage) {
      const seen = new Set()
      for (const c of coverage) {
        const id = SKI_KEYS.get(destKey(c))
        if (id && !seen.has(id)) { seen.add(id); out.get(id).push(p) }
      }
    } else {
      const id = SKI_KEYS.get(destKey(dest))
      if (id) out.get(id).push(p)
    }
  }
  return out
}

/** country id -> roaming packages of the Israeli carriers valid there. */
function indexAbroad(plans) {
  const out = new Map(SKI_COUNTRIES.map(c => [c.id, []]))
  for (const p of plans) {
    const info = getCountriesForAbroadPlan(p)
    // A carrier without a country list (xphone) names the country in extras[0].
    const countries = info?.countries || (p.extras?.[0] ? [p.extras[0]] : [])
    const seen = new Set()
    for (const c of countries) {
      const id = SKI_KEYS.get(destKey(c))
      if (id && !seen.has(id)) { seen.add(id); out.get(id).push(p) }
    }
  }
  return out
}

const minPrice = (list) => list.reduce((m, p) => (p.price != null && p.price < m ? p.price : m), Infinity)
const fmt = (n) => (Number.isFinite(n) ? `₪${Math.round(n)}` : null)

function Box({ label, children }) {
  return (
    <div className="border border-moca-border/60 rounded-xl p-2.5">
      <p className="text-[11px] font-medium text-gray-500 mb-1.5 text-right">{label}</p>
      <div className="flex flex-wrap gap-1">{children}</div>
    </div>
  )
}

export default function SkiPage() {
  const { tt, lang } = useLang()
  const flags = useFeatureFlags()
  const visibleCarrierIds = useVisibleCarriers(DOMESTIC_IDS)
  const [params, setParams] = useSearchParams()

  const showGlobal = !flags.hide_global
  const showAbroad = !flags.hide_abroad

  const [globalPlans, setGlobalPlans] = useState([])
  const [abroadPlans, setAbroadPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const countryId = SKI_COUNTRIES.some(c => c.id === params.get('country')) ? params.get('country') : null
  const country = SKI_COUNTRIES.find(c => c.id === countryId) || null
  const resort = country && country.resorts.includes(params.get('resort')) ? params.get('resort') : null

  const [filters, setFilters] = useState({ kind: 'all', week: true, gb: 'all', days: 'all', sort: 'price_asc' })
  const [showAllResorts, setShowAllResorts] = useState(false)
  const [limit, setLimit] = useState({ global: PAGE, abroad: PAGE })
  const plansRef = useRef(null)
  const pickedRef = useRef(false)

  // The picker is 20 cards tall on a phone - after a pick (not on a deep link)
  // bring the packages into view once they have rendered.
  useEffect(() => {
    if (!pickedRef.current) return
    pickedRef.current = false
    plansRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [countryId])

  const setFilter = (k, v) => startTransition(() => {
    setFilters(prev => ({ ...prev, [k]: v }))
    setLimit({ global: PAGE, abroad: PAGE })
  })

  const pick = (id, resortName) => {
    const next = {}
    if (id) next.country = id
    if (id && resortName) next.resort = resortName
    setParams(next, { replace: false })
    setShowAllResorts(false)
    setLimit({ global: PAGE, abroad: PAGE })
    pickedRef.current = !!id
  }

  useEffect(() => {
    let alive = true
    Promise.all([
      showGlobal ? api.getGlobalPlans() : Promise.resolve([]),
      showAbroad ? api.getAbroadPlans() : Promise.resolve([]),
    ]).then(([g, a]) => {
      if (!alive) return
      setGlobalPlans(Array.isArray(g) ? g : [])
      setAbroadPlans(Array.isArray(a) ? a : [])
      setLoading(false)
    }).catch(() => { if (alive) { setError(true); setLoading(false) } })
    return () => { alive = false }
  }, [showGlobal, showAbroad, reloadKey])

  const visibleKey = visibleCarrierIds.join(',')
  const globalByCountry = useMemo(() => indexGlobal(globalPlans), [globalPlans])
  const abroadByCountry = useMemo(
    () => indexAbroad(abroadPlans.filter(p => visibleCarrierIds.includes(p.carrier))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [abroadPlans, visibleKey],
  )

  // One summary row per country for the picker.
  const summaries = useMemo(() => SKI_COUNTRIES.map(c => {
    const g = globalByCountry.get(c.id) || []
    const a = abroadByCountry.get(c.id) || []
    return {
      ...c,
      plans: g.length + a.length,
      providers: new Set([...g, ...a].map(p => p.carrier)).size,
      weekFrom: minPrice(g.filter(isSkiWeek)),
      roamFrom: minPrice(a),
    }
  }), [globalByCountry, abroadByCountry])

  const resortOptions = useMemo(() => SKI_COUNTRIES.flatMap(c => c.resorts.map(r => ({
    value: `${c.id}|${r}`,
    label: `${resortLabel(r, lang)} · ${lang === 'he' ? c.he : c.en}`,
  }))), [lang])

  // filterAndSortPlans is the dashboard's own pipeline; the country cut already
  // happened in the index, so only GB / days / sort are left for it to do.
  const pipelineFilters = useMemo(() => ({
    carrier: 'all', gen: 'all', roaming: 'all', globalProvider: 'all', israeliProvider: 'all',
    region: 'all', destination: 'all', gb: filters.gb, days: filters.days, sort: filters.sort,
  }), [filters.gb, filters.days, filters.sort])

  const globalItems = useMemo(() => {
    if (!countryId || filters.kind === 'abroad') return []
    const pool = globalByCountry.get(countryId) || []
    const list = filterAndSortPlans(filters.week ? pool.filter(isSkiWeek) : pool, 'global', pipelineFilters, {})
    return groupGlobalDisplayItems(list, 'global')
  }, [countryId, filters.kind, filters.week, globalByCountry, pipelineFilters])

  const abroadItems = useMemo(() => {
    if (!countryId || filters.kind === 'global') return []
    const pool = abroadByCountry.get(countryId) || []
    // On roaming rows a NULL data_gb is a voice-minutes package, not unlimited data.
    const week = (p) => (p.days ?? 0) >= 7 && p.data_gb != null && p.data_gb >= 5
    return filterAndSortPlans(filters.week ? pool.filter(week) : pool, 'abroad', pipelineFilters,
      { visibleCarrierIds: DOMESTIC_IDS, carrierIds: DOMESTIC_IDS })
  }, [countryId, filters.kind, filters.week, abroadByCountry, pipelineFilters])

  if (loading) return <div className="flex justify-center py-20"><Spinner /></div>

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="font-display text-lg font-bold text-moca-dark">{tt('לא הצלחנו לטעון את החבילות', 'Could not load the plans')}</p>
        <button type="button" onClick={() => { setError(false); setLoading(true); setReloadKey(k => k + 1) }}
          className="mt-4 text-[13px] font-semibold text-white bg-moca-bolt rounded-lg px-4 py-2 hover:bg-[#7a4520]">
          {tt('לנסות שוב', 'Try again')}
        </button>
      </div>
    )
  }

  const cName = (c) => (lang === 'he' ? c.he : c.en)
  const resorts = country ? (showAllResorts ? country.resorts : country.resorts.slice(0, 14)) : []

  return (
    <div dir={lang === 'he' ? 'rtl' : 'ltr'} className="max-w-6xl mx-auto px-4 py-6 pb-20 md:pb-6">
      {/* Intro + resort search */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <p className="text-sm text-moca-sub text-right">
          {tt(
            `חבילות גלישה לחופשת סקי: ${SKI_RESORT_COUNT} אתרי סקי ב-${SKI_COUNTRIES.length} מדינות.`,
            `Data packages for a ski trip: ${SKI_RESORT_COUNT} resorts in ${SKI_COUNTRIES.length} countries.`,
          )}
        </p>
        <SearchableSelect
          className="w-full sm:w-80"
          size="md"
          value={resort ? `${countryId}|${resort}` : 'all'}
          onChange={(v) => {
            if (v === 'all') return pick(countryId, null)
            const [id, name] = v.split('|')
            pick(id, name)
          }}
          options={resortOptions}
          placeholder={tt('חיפוש אתר סקי...', 'Find a ski resort...')}
        />
      </div>

      {/* Country picker */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-5">
        {summaries.map(c => {
          const active = c.id === countryId
          const from = fmt(c.weekFrom)
          return (
            <button
              key={c.id}
              type="button"
              aria-pressed={active}
              onClick={() => pick(active ? null : c.id, null)}
              className={`text-right rounded-xl border px-3 py-2.5 transition-colors ${
                active
                  ? 'bg-moca-bolt border-moca-bolt text-moca-cream'
                  : 'bg-white border-moca-border/60 text-moca-text hover:bg-moca-cream'
              }`}
            >
              <div className="font-display font-bold text-[15px] leading-tight">{cName(c)}</div>
              <div className={`text-[11px] mt-0.5 ${active ? 'text-moca-cream/80' : 'text-moca-sub'}`}>
                {c.resorts.length} {tt('אתרי סקי', 'resorts')} · {c.providers} {tt('ספקים', 'providers')}
              </div>
              <div className={`text-[12px] mt-1 font-semibold ${active ? 'text-moca-cream' : 'text-moca-dark'}`}>
                {from ? tt(`שבוע סקי מ-${from}`, `Ski week from ${from}`) : tt('אין חבילת שבוע', 'No week package')}
              </div>
            </button>
          )
        })}
      </div>

      {!country && (
        <div className="text-center py-10 text-sm text-moca-sub">
          {tt('בחרו מדינה או אתר סקי כדי לראות את החבילות. "שבוע סקי" = eSIM ל-7 ימים ומעלה עם 5GB לפחות.',
              'Pick a country or a resort to see the packages. "Ski week" = an eSIM of 7+ days with at least 5GB.')}
        </div>
      )}

      {country && (
        <>
          {/* Resorts of the selected country */}
          <div ref={plansRef} className="border border-moca-border/60 rounded-xl p-2.5 mb-3 scroll-mt-20">
            <p className="text-[11px] font-medium text-gray-500 mb-1.5 text-right">
              {tt(`אתרי הסקי ב${country.he} (${country.resorts.length})`, `Ski resorts in ${country.en} (${country.resorts.length})`)}
              {' · '}
              {tt('הכיסוי נמכר לפי מדינה, אז החבילות זהות בכל האתרים', 'coverage is sold per country, so the packages are the same at every resort')}
            </p>
            <div className="flex flex-wrap gap-1">
              {resorts.map(r => (
                <FilterTag key={r} label={resortLabel(r, lang)} active={resort === r}
                  onClick={() => pick(countryId, resort === r ? null : r)} />
              ))}
              {country.resorts.length > 14 && (
                <button type="button" onClick={() => setShowAllResorts(v => !v)}
                  className="px-2.5 py-1 rounded-md text-xs font-semibold text-moca-bolt hover:bg-moca-cream">
                  {showAllResorts ? tt('פחות', 'Less') : tt(`עוד ${country.resorts.length - 14}`, `${country.resorts.length - 14} more`)}
                </button>
              )}
            </div>
          </div>

          {/* Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
            {showGlobal && showAbroad && (
              <Box label={tt('סוג חבילה', 'Package type')}>
                <FilterTag label={tt('הכל', 'All')} active={filters.kind === 'all'} onClick={() => setFilter('kind', 'all')} />
                <FilterTag label={tt('eSIM בינלאומי', 'International eSIM')} active={filters.kind === 'global'} onClick={() => setFilter('kind', 'global')} />
                <FilterTag label={tt('חבילות חו״ל של המפעילים', 'Carrier roaming')} active={filters.kind === 'abroad'} onClick={() => setFilter('kind', 'abroad')} />
              </Box>
            )}
            <Box label={tt('התאמה לחופשה', 'Trip fit')}>
              <FilterTag label={tt('שבוע סקי (7+ ימים, 5GB+)', 'Ski week (7+ days, 5GB+)')} active={filters.week} onClick={() => setFilter('week', true)} />
              <FilterTag label={tt('כל החבילות', 'All packages')} active={!filters.week} onClick={() => setFilter('week', false)} />
            </Box>
            <Box label={tt('מיון', 'Sort')}>
              <FilterTag label={tt('מחיר ↑', 'Price ↑')} active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
              <FilterTag label={tt('מחיר ↓', 'Price ↓')} active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
              <FilterTag label={tt('תמורה (₪ ל-GB) ↑', 'Value (₪/GB) ↑')} active={filters.sort === 'ppgb_asc'} onClick={() => setFilter('sort', 'ppgb_asc')} />
              <FilterTag label="GB ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
            </Box>
            <Box label={tt('גלישה', 'Data')}>
              {[['all', tt('הכל', 'All')], ['0-5', tt('עד 5GB', 'Up to 5GB')], ['5-15', '5-15GB'], ['15-50', '15-50GB'], ['50+', tt('מעל 50GB', 'Over 50GB')], ['unlimited', tt('ללא הגבלה', 'Unlimited')]].map(([v, label]) => (
                <FilterTag key={v} label={label} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
              ))}
            </Box>
            <Box label={tt('תוקף', 'Validity')}>
              {['all', '1-7', '8-14', '15-30', '30+'].map(v => (
                <FilterTag key={v} label={v === 'all' ? tt('הכל', 'All') : tt(`${v} ימים`, `${v} days`)} active={filters.days === v} onClick={() => setFilter('days', v)} />
              ))}
            </Box>
          </div>

          {/* International eSIM */}
          {showGlobal && filters.kind !== 'abroad' && (
            <Section
              title={tt(`eSIM בינלאומי ל${country.he}`, `International eSIM for ${country.en}`)}
              count={globalItems.length}
              note={tt('כרטיס לכל ספק ויעד, עם סולם הנפחים בתוכו', 'one card per provider and destination, with its data ladder inside')}
              tt={tt}
            >
              {globalItems.slice(0, limit.global).map((item, i) => item.isGroup ? (
                <GroupedPlanCard
                  key={`g-${item.carrier}-${item.destination}`}
                  carrier={item.carrier}
                  destination={item.destination}
                  plans={item.plans}
                  repPlan={item.plans[0]}
                  tabId="global"
                />
              ) : (
                <PlanCard key={`${item.plan.carrier}|${item.plan.plan_name}|${i}`} plan={item.plan} type="global" />
              ))}
              <More shown={limit.global} total={globalItems.length} tt={tt}
                onMore={() => setLimit(l => ({ ...l, global: l.global + PAGE }))} />
            </Section>
          )}

          {/* Israeli carriers' roaming */}
          {showAbroad && filters.kind !== 'global' && (
            <Section
              title={tt(`חבילות חו״ל של המפעילים בישראל ל${country.he}`, `Israeli carriers' roaming for ${country.en}`)}
              count={abroadItems.length}
              note={tt('נשארים עם המספר הישראלי, חלקן כוללות דקות שיחה ו-SMS', 'keep your Israeli number; some include minutes and SMS')}
              tt={tt}
            >
              {abroadItems.slice(0, limit.abroad).map((plan, i) => (
                <PlanCard key={`${plan.carrier}|${plan.plan_name}|${i}`} plan={plan} type="abroad" />
              ))}
              <More shown={limit.abroad} total={abroadItems.length} tt={tt}
                onMore={() => setLimit(l => ({ ...l, abroad: l.abroad + PAGE }))} />
            </Section>
          )}
        </>
      )}

      <p className="text-[11px] text-moca-muted text-right mt-8">
        {tt('המחירים והנפחים מתעדכנים מסריקת הספקים פעמיים ביום.',
            'Prices and allowances come from the twice-daily provider scrape.')}
      </p>
    </div>
  )
}

function Section({ title, count, note, children, tt }) {
  return (
    <section className="mb-8">
      <div className="flex flex-wrap items-baseline gap-x-2 mb-3 pb-2 border-b border-moca-border/60">
        <h2 className="font-display text-[17px] font-bold text-moca-dark">{title}</h2>
        <span className="text-xs text-moca-sub" role="status">{count} {tt('תוצאות', 'results')}</span>
        <span className="text-xs text-moca-muted">· {note}</span>
      </div>
      {count === 0 ? (
        <p className="text-sm text-moca-sub py-6 text-center">{tt('אין חבילות שתואמות לסינון', 'No packages match the filters')}</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{children}</div>
      )}
    </section>
  )
}

function More({ shown, total, onMore, tt }) {
  if (shown >= total) return null
  return (
    <div className="col-span-full text-center">
      <button type="button" onClick={onMore}
        className="text-sm text-moca-bolt hover:text-moca-dark px-4 py-2 rounded-lg border border-moca-border hover:bg-moca-cream transition-colors">
        {tt('הצג עוד', 'Show more')} ({total - shown})
      </button>
    </div>
  )
}
