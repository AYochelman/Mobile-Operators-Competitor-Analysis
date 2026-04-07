import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import PlanCard from '../components/PlanCard'
import CountryModal from '../components/CountryModal'
import FilterTag from '../components/ui/FilterTag'
import Badge from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'
import Button from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'

const TABS = [
  { id: 'domestic', label: '📱 חבילות Mass Market' },
  { id: 'abroad', label: '✈️ חבילות חו"ל' },
  { id: 'global', label: '🌍 חבילות גלובליות' },
  { id: 'content', label: '📺 שירותי תוכן' },
]

const KNOWN_REGIONS = new Set([
  'אירופה','אסיה','אסיה ואוקיאניה','אפריקה','גלובלי','קריביים','איי הקריביים',
  'אמריקה הלטינית','צפון אמריקה','המזרח התיכון','המזרח התיכון וצפון אפריקה',
  'דרום מזרח אסיה','סקנדינביה','בלקן','מזרח אירופה','מרכז אמריקה','אוקיאניה',
  'סין + הונג קונג + מקאו','יפן וקוריאה','יפן וסין',
  'אסיה פסיפיק','מרכז אסיה','צפון אפריקה',
])

const CARRIERS = [
  { id: 'partner', label: 'פרטנר' }, { id: 'pelephone', label: 'פלאפון' },
  { id: 'hotmobile', label: 'הוט מובייל' }, { id: 'cellcom', label: 'סלקום' },
  { id: 'mobile019', label: '019' }, { id: 'xphone', label: 'XPhone' },
  { id: 'wecom', label: 'We-Com' },
]

const GLOBAL_PROVIDERS = [
  { id: 'tuki', label: 'Tuki' }, { id: 'globalesim', label: 'GlobaleSIM' },
  { id: 'airalo', label: 'Airalo' }, { id: 'pelephone_global', label: 'GlobalSIM' },
  { id: 'esimo', label: 'eSIMo' }, { id: 'simtlv', label: 'SimTLV' },
  { id: 'world8', label: '8 World' }, { id: 'xphone_global', label: 'XPhone Global' },
  { id: 'saily', label: 'Saily' }, { id: 'holafly', label: 'Holafly' },
  { id: 'esimio', label: 'eSIM.io' },
]

export default function DashboardPage() {
  const { isAdmin } = useAuth()
  const [tab, setTab] = useState('domestic')
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [plans, setPlans] = useState({ domestic: [], abroad: [], global: [], content: [] })
  const [changes, setChanges] = useState({ domestic: [], abroad: [], global: [], content: [] })
  const [filters, setFilters] = useState({
    carrier: 'all', gb: 'all', sort: 'price_asc', gen: 'all', roaming: 'all',
    globalProvider: 'all', destination: 'all', region: 'all', days: 'all',
    contentCarrier: 'all', contentService: 'all',
  })
  const [countryModal, setCountryModal] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  // Load data
  useEffect(() => { loadTab(tab) }, [tab])

  async function loadTab(t) {
    setLoading(true)
    try {
      if (t === 'domestic' && plans.domestic.length === 0) {
        const [p, c] = await Promise.all([api.getPlans(), api.getChanges()])
        setPlans(prev => ({ ...prev, domestic: p }))
        setChanges(prev => ({ ...prev, domestic: c }))
        if (p.length) {
          const times = p.map(x => x.scraped_at).filter(Boolean).sort()
          setLastUpdate(times.at(-1))
        }
      } else if (t === 'abroad' && plans.abroad.length === 0) {
        const [p, c] = await Promise.all([api.getAbroadPlans(), api.getAbroadChanges()])
        setPlans(prev => ({ ...prev, abroad: p }))
        setChanges(prev => ({ ...prev, abroad: c }))
      } else if (t === 'global' && plans.global.length === 0) {
        const [p, c] = await Promise.all([api.getGlobalPlans(), api.getGlobalChanges()])
        setPlans(prev => ({ ...prev, global: p }))
        setChanges(prev => ({ ...prev, global: c }))
      } else if (t === 'content' && plans.content.length === 0) {
        const p = await api.getContentPlans()
        setPlans(prev => ({ ...prev, content: p }))
      }
    } catch (err) { console.error(err) }
    setLoading(false)
  }

  // Build change lookup
  const changeLookup = useMemo(() => {
    const key = tab === 'content' ? 'content' : tab
    const lookup = {}
    const cutoff = new Date(Date.now() - (tab === 'domestic' ? 24 : 168) * 60 * 60 * 1000).toISOString()
    ;(changes[key] || []).forEach(c => {
      if (c.changed_at >= cutoff) {
        const k = `${c.carrier}|${c.plan_name}`
        lookup[k] = c.change_type
      }
    })
    return lookup
  }, [changes, tab])

  // Filter + sort plans
  const filteredPlans = useMemo(() => {
    let result = plans[tab] || []
    const f = filters

    if (tab === 'domestic' || tab === 'abroad') {
      if (f.carrier !== 'all') result = result.filter(p => p.carrier === f.carrier)
    }
    // Gen (5G) filter — domestic only
    if (tab === 'domestic' && f.gen !== 'all') {
      if (f.gen === '5g') result = result.filter(p => (p.plan_name && p.plan_name.includes('5G')) || (p.extras && p.extras.some(e => e.includes('5G'))))
      if (f.gen === '4g') result = result.filter(p => !(p.plan_name && p.plan_name.includes('5G')) && !(p.extras && p.extras.some(e => e.includes('5G'))))
    }
    // Roaming filter — domestic only
    if (tab === 'domestic' && f.roaming === 'yes') {
      result = result.filter(p => p.extras && p.extras.some(e => /חו"ל|חו״ל/.test(e) && /\d+/.test(e) && /GB|גלישה/i.test(e)))
    }
    if (tab === 'global') {
      if (f.globalProvider !== 'all') result = result.filter(p => p.carrier === f.globalProvider)
      if (f.region !== 'all') result = result.filter(p => p.extras && p.extras[0] === f.region)
      else if (f.destination !== 'all') result = result.filter(p => p.extras && p.extras[0] === f.destination)
    }
    if (tab === 'content') {
      const NA = ['לא נמצא', 'שגיאה', 'לא זמין']
      if (f.contentCarrier !== 'all') result = result.filter(p => p.carrier === f.contentCarrier)
      if (f.contentService !== 'all') result = result.filter(p => p.service === f.contentService)
      result = result.filter(p => !p.price || !NA.some(v => String(p.price).includes(v)))
    }

    // GB filter
    if (f.gb !== 'all' && tab !== 'content') {
      if (f.gb === 'unlimited') result = result.filter(p => p.data_gb === null)
      else if (f.gb === '0-5') result = result.filter(p => p.data_gb !== null && p.data_gb <= 5)
      else if (f.gb === '5-15') result = result.filter(p => p.data_gb !== null && p.data_gb > 5 && p.data_gb <= 15)
      else if (f.gb === '15-100') result = result.filter(p => p.data_gb !== null && p.data_gb > 15 && p.data_gb <= 100)
      else if (f.gb === '100+') result = result.filter(p => p.data_gb !== null && p.data_gb > 100)
    }

    // Days filter (abroad/global)
    if (f.days !== 'all' && (tab === 'abroad' || tab === 'global')) {
      if (f.days === '1-7') result = result.filter(p => p.days && p.days <= 7)
      else if (f.days === '8-30') result = result.filter(p => p.days && p.days > 7 && p.days <= 30)
      else if (f.days === '30+') result = result.filter(p => p.days && p.days > 30)
    }

    // Sort
    if (f.sort === 'price_asc') result = [...result].sort((a, b) => (a.price ?? 9999) - (b.price ?? 9999))
    else if (f.sort === 'price_desc') result = [...result].sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
    else if (f.sort === 'gb_desc') result = [...result].sort((a, b) => (b.data_gb ?? 99999) - (a.data_gb ?? 99999))

    return result
  }, [plans, tab, filters])

  // Regions for global tab
  const globalRegions = useMemo(() => {
    if (tab !== 'global') return []
    let src = plans.global
    if (filters.globalProvider !== 'all') src = src.filter(p => p.carrier === filters.globalProvider)
    return [...new Set(src.filter(p => p.extras && p.extras[0] && KNOWN_REGIONS.has(p.extras[0])).map(p => p.extras[0]))].sort((a, b) => a.localeCompare(b, 'he'))
  }, [plans.global, tab, filters.globalProvider])

  // Destinations (countries only, exclude regions) for global tab
  const globalDestinations = useMemo(() => {
    if (tab !== 'global') return []
    let src = plans.global
    if (filters.globalProvider !== 'all') src = src.filter(p => p.carrier === filters.globalProvider)
    return [...new Set(src.filter(p => p.extras && p.extras[0] && !/\d/.test(p.extras[0]) && !KNOWN_REGIONS.has(p.extras[0])).map(p => p.extras[0]))].sort((a, b) => a.localeCompare(b, 'he'))
  }, [plans.global, tab, filters.globalProvider])

  // Content services list
  const contentServices = useMemo(() => {
    return [...new Set(plans.content.map(p => p.service).filter(Boolean))]
  }, [plans.content])

  const handleScrape = async () => {
    setScraping(true)
    try {
      await api.scrapeAll()
      // Reload current tab
      setPlans({ domestic: [], abroad: [], global: [], content: [] })
      setChanges({ domestic: [], abroad: [], global: [], content: [] })
      loadTab(tab)
    } catch (err) { console.error(err) }
    setScraping(false)
  }

  const setFilter = (key, value) => setFilters(prev => ({ ...prev, [key]: value }))

  return (
    <div className="max-w-7xl mx-auto px-4 py-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          {lastUpdate && (
            <p className="text-sm text-gray-600">
              עדכון אחרון: {new Date(lastUpdate).toLocaleDateString('he-IL')} {lastUpdate.slice(11, 16)}
            </p>
          )}
        </div>
        {isAdmin && (
          <Button variant="primary" size="sm" onClick={handleScrape} disabled={scraping}>
            {scraping ? '⏳ מעדכן...' : '🔄 עדכן הכל'}
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex justify-center gap-1 overflow-x-auto pb-2 mb-4 scrollbar-hide">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => { setTab(t.id); setFilter('carrier', 'all'); setFilter('globalProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }}
            className={`whitespace-nowrap px-4 py-2 rounded-lg text-sm font-medium transition-colors flex-shrink-0
              ${tab === t.id ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 space-y-3">
        {/* Carrier/Provider filter */}
        {(tab === 'domestic' || tab === 'abroad') && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">חברה</p>
            <div className="flex flex-wrap gap-1.5">
              <FilterTag label="כולם" active={filters.carrier === 'all'} onClick={() => setFilter('carrier', 'all')} count={plans[tab]?.length} />
              {CARRIERS.map(c => {
                const cnt = plans[tab]?.filter(p => p.carrier === c.id).length || 0
                if (!cnt) return null
                return <FilterTag key={c.id} label={c.label} active={filters.carrier === c.id} onClick={() => setFilter('carrier', c.id)} count={cnt} />
              })}
            </div>
          </div>
        )}

        {tab === 'global' && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">ספק</p>
            <div className="flex flex-wrap gap-1.5">
              <FilterTag label="כולם" active={filters.globalProvider === 'all'} onClick={() => { setFilter('globalProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }} count={plans.global?.length} />
              {GLOBAL_PROVIDERS.map(p => {
                const cnt = plans.global?.filter(x => x.carrier === p.id).length || 0
                if (!cnt) return null
                return <FilterTag key={p.id} label={p.label} active={filters.globalProvider === p.id} onClick={() => { setFilter('globalProvider', p.id); setFilter('destination', 'all'); setFilter('region', 'all') }} count={cnt} />
              })}
            </div>
          </div>
        )}

        {tab === 'global' && globalRegions.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">אזור</p>
            <select
              value={filters.region}
              onChange={e => { setFilter('region', e.target.value); if (e.target.value !== 'all') setFilter('destination', 'all') }}
              className={`border rounded-lg px-3 py-1.5 text-sm ${filters.region !== 'all' ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}`}
            >
              <option value="all">כל האזורים ({globalRegions.length})</option>
              {globalRegions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        )}

        {tab === 'global' && globalDestinations.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">מדינה</p>
            <select
              value={filters.destination}
              onChange={e => { setFilter('destination', e.target.value); if (e.target.value !== 'all') setFilter('region', 'all') }}
              className={`border rounded-lg px-3 py-1.5 text-sm ${filters.destination !== 'all' ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}`}
            >
              <option value="all">כל המדינות ({globalDestinations.length})</option>
              {globalDestinations.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}

        {tab === 'content' && (
          <>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">חברה</p>
              <div className="flex flex-wrap gap-1.5">
                <FilterTag label="כולם" active={filters.contentCarrier === 'all'} onClick={() => setFilter('contentCarrier', 'all')} />
                {['cellcom', 'partner', 'hotmobile', 'pelephone'].map(c => (
                  <FilterTag key={c} label={CARRIERS.find(x => x.id === c)?.label || c} active={filters.contentCarrier === c} onClick={() => setFilter('contentCarrier', c)} />
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">שירות</p>
              <div className="flex flex-wrap gap-1.5">
                <FilterTag label="כולם" active={filters.contentService === 'all'} onClick={() => setFilter('contentService', 'all')} />
                {contentServices.map(s => (
                  <FilterTag key={s} label={s} active={filters.contentService === s} onClick={() => setFilter('contentService', s)} />
                ))}
              </div>
            </div>
          </>
        )}

        {/* Gen + Roaming (domestic only) */}
        {tab === 'domestic' && (
          <div className="flex flex-wrap gap-4">
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">דור רשת</p>
              <div className="flex flex-wrap gap-1.5">
                <FilterTag label="כולם" active={filters.gen === 'all'} onClick={() => setFilter('gen', 'all')} />
                <FilterTag label="דור 4" active={filters.gen === '4g'} onClick={() => setFilter('gen', '4g')} />
                <FilterTag label="דור 5" active={filters.gen === '5g'} onClick={() => setFilter('gen', '5g')} />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">גלישה בחו"ל</p>
              <div className="flex flex-wrap gap-1.5">
                <FilterTag label="כולם" active={filters.roaming === 'all'} onClick={() => setFilter('roaming', 'all')} />
                <FilterTag label="כולל חו״ל" active={filters.roaming === 'yes'} onClick={() => setFilter('roaming', 'yes')} />
              </div>
            </div>
          </div>
        )}

        {/* GB + Days + Sort (shared) */}
        {tab !== 'content' && (
          <div className="flex flex-wrap gap-4">
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">גלישה</p>
              <div className="flex flex-wrap gap-1.5">
                {['all', '0-5', '5-15', '15-100', '100+', 'unlimited'].map(v => (
                  <FilterTag key={v} label={v === 'all' ? 'הכל' : v === 'unlimited' ? 'ללא הגבלה' : `${v}GB`} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
                ))}
              </div>
            </div>
            {(tab === 'abroad' || tab === 'global') && (
              <div>
                <p className="text-xs font-medium text-gray-500 mb-2">תקופה</p>
                <div className="flex flex-wrap gap-1.5">
                  {['all', '1-7', '8-30', '30+'].map(v => (
                    <FilterTag key={v} label={v === 'all' ? 'הכל' : v === '30+' ? '30+ ימים' : `${v} ימים`} active={filters.days === v} onClick={() => setFilter('days', v)} />
                  ))}
                </div>
              </div>
            )}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">מיון</p>
              <div className="flex flex-wrap gap-1.5">
                <FilterTag label="מחיר ↑" active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
                <FilterTag label="מחיר ↓" active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
                <FilterTag label="גלישה ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Results count */}
      <p className="text-xs text-gray-400 mb-3">{filteredPlans.length} חבילות</p>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-16"><Spinner /></div>
      )}

      {/* Plan cards grid */}
      {!loading && tab !== 'content' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filteredPlans.map((plan, i) => {
            const key = `${plan.carrier}|${plan.plan_name}`
            return (
              <PlanCard
                key={key + i}
                plan={plan}
                type={tab}
                changeType={changeLookup[key]}
              />
            )
          })}
        </div>
      )}

      {/* Content: grouped by service */}
      {!loading && tab === 'content' && (() => {
        const services = [...new Set(filteredPlans.map(p => p.service).filter(Boolean))]
        const NA = ['לא נמצא', 'שגיאה', 'לא זמין']
        return services.map(svc => {
          const svcPlans = filteredPlans.filter(p => p.service === svc)
            .filter(p => !(p.price && NA.some(v => String(p.price).includes(v))))
          if (!svcPlans.length) return null
          return (
            <div key={svc} className="mb-6">
              <h2 className="text-sm font-bold text-gray-700 mb-2 border-b border-gray-200 pb-1">{svc}</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {svcPlans.map((plan, i) => {
                  const key = `${plan.service}|${plan.carrier}`
                  return (
                    <PlanCard
                      key={key + i}
                      plan={plan}
                      type="content"
                      changeType={changeLookup[key]}
                    />
                  )
                })}
              </div>
            </div>
          )
        })
      })()}

      {!loading && filteredPlans.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">🔍</p>
          <p>לא נמצאו חבילות בסינון הנוכחי</p>
        </div>
      )}

      {/* Country modal */}
      <CountryModal
        open={!!countryModal}
        onClose={() => setCountryModal(null)}
        title={countryModal?.title}
        countries={countryModal?.countries}
      />
    </div>
  )
}
