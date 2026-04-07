import { useState, useEffect, useMemo, useCallback } from 'react'
import { api } from '../lib/api'
import * as XLSX from 'xlsx'
import PlanCard from '../components/PlanCard'
import CountryModal from '../components/CountryModal'
import FilterTag from '../components/ui/FilterTag'
import Badge from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'
import Button from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'

const TABS = [
  { id: 'domestic', label: 'חבילות סלולר', icon: '📱' },
  { id: 'abroad', label: 'חו"ל', icon: '✈️' },
  { id: 'global', label: 'גלובלי', icon: '🌍' },
  { id: 'content', label: 'תוכן', icon: '📺' },
]

const KNOWN_REGIONS = new Set([
  'אירופה','אסיה','אסיה ואוקיאניה','אפריקה','גלובלי','קריביים','איי הקריביים',
  'אמריקה הלטינית','צפון אמריקה','המזרח התיכון','המזרח התיכון וצפון אפריקה',
  'דרום מזרח אסיה','סקנדינביה','בלקן','מזרח אירופה','מרכז אמריקה','אוקיאניה',
  'סין + הונג קונג + מקאו','יפן וקוריאה','יפן וסין',
  'אסיה פסיפיק','מרכז אסיה','צפון אפריקה',
  'אירופה+','שוויץ+','גוודלופ','קפריסין+',
  'אמריקה הדרומית','דרום אמריקה',
  'אמריקה הדרומית','דרום אמריקה',
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
  { id: 'sparks', label: 'Sparks' },
]

export default function DashboardPage() {
  const { isAdmin } = useAuth()
  const [tab, setTab] = useState('domestic')
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [plans, setPlans] = useState({ domestic: [], abroad: [], global: [], content: [] })
  const [changes, setChanges] = useState({ domestic: [], abroad: [], global: [], content: [] })
  const [filters, setFilters] = useState({
    carrier: 'all', gb: 'all', sort: 'price_asc', gen: 'all', roaming: 'all',
    globalProvider: 'all', destination: 'all', region: 'all', days: 'all',
    contentCarrier: 'all', contentService: 'all',
  })
  const [countryModal, setCountryModal] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (tab === 'domestic' || tab === 'abroad') {
      if (filters.carrier !== 'all') count++
    }
    if (tab === 'domestic') {
      if (filters.gen !== 'all') count++
      if (filters.roaming !== 'all') count++
    }
    if (tab === 'global') {
      if (filters.globalProvider !== 'all') count++
      if (filters.region !== 'all') count++
      if (filters.destination !== 'all') count++
    }
    if (tab === 'content') {
      if (filters.contentCarrier !== 'all') count++
      if (filters.contentService !== 'all') count++
    }
    if (tab !== 'content') {
      if (filters.gb !== 'all') count++
      if (filters.days !== 'all') count++
    }
    return count
  }, [filters, tab])

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
    if (tab === 'domestic' && f.gen !== 'all') {
      if (f.gen === '5g') result = result.filter(p => (p.plan_name && p.plan_name.includes('5G')) || (p.extras && p.extras.some(e => e.includes('5G'))))
      if (f.gen === '4g') result = result.filter(p => !(p.plan_name && p.plan_name.includes('5G')) && !(p.extras && p.extras.some(e => e.includes('5G'))))
    }
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

    if (f.gb !== 'all' && tab !== 'content') {
      if (f.gb === 'unlimited') result = result.filter(p => p.data_gb === null)
      else if (f.gb === '0-5') result = result.filter(p => p.data_gb !== null && p.data_gb <= 5)
      else if (f.gb === '5-15') result = result.filter(p => p.data_gb !== null && p.data_gb > 5 && p.data_gb <= 15)
      else if (f.gb === '15-100') result = result.filter(p => p.data_gb !== null && p.data_gb > 15 && p.data_gb <= 100)
      else if (f.gb === '100+') result = result.filter(p => p.data_gb !== null && p.data_gb > 100)
    }

    if (f.days !== 'all' && (tab === 'abroad' || tab === 'global')) {
      if (f.days === '1-7') result = result.filter(p => p.days && p.days <= 7)
      else if (f.days === '8-30') result = result.filter(p => p.days && p.days > 7 && p.days <= 30)
      else if (f.days === '30+') result = result.filter(p => p.days && p.days > 30)
    }

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

  // Destinations for global tab
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
      setPlans({ domestic: [], abroad: [], global: [], content: [] })
      setChanges({ domestic: [], abroad: [], global: [], content: [] })
      loadTab(tab)
    } catch (err) { console.error(err) }
    setScraping(false)
  }

  const setFilter = (key, value) => setFilters(prev => ({ ...prev, [key]: value }))

  const exportToExcel = useCallback(() => {
    if (!filteredPlans.length) return
    const TAB_NAMES = { domestic: 'חבילות סלולר', abroad: 'חו"ל', global: 'גלובלי', content: 'תוכן' }
    const CARRIER_HEB = { partner: 'פרטנר', pelephone: 'פלאפון', hotmobile: 'הוט מובייל', cellcom: 'סלקום', mobile019: '019', xphone: 'XPhone', wecom: 'We-Com', tuki: 'Tuki', globalesim: 'GlobaleSIM', airalo: 'Airalo', pelephone_global: 'GlobalSIM', esimo: 'eSIMo', simtlv: 'SimTLV', world8: '8 World', xphone_global: 'XPhone Global', saily: 'Saily', holafly: 'Holafly', esimio: 'eSIM.io', sparks: 'Sparks' }
    const GB_HEB = { 'all': 'הכל', '0-5': '0-5GB', '5-15': '5-15GB', '15-100': '15-100GB', '100+': '100+GB', 'unlimited': 'ללא הגבלה' }
    const DAYS_HEB = { 'all': 'הכל', '1-7': '1-7 ימים', '8-30': '8-30 ימים', '30+': '30+ ימים' }

    // Build filter summary title
    const parts = [`קטגוריה: ${TAB_NAMES[tab]}`]
    if (filters.carrier !== 'all') parts.push(`ספק: ${CARRIER_HEB[filters.carrier] || filters.carrier}`)
    if (filters.globalProvider !== 'all') parts.push(`ספק: ${CARRIER_HEB[filters.globalProvider] || filters.globalProvider}`)
    if (filters.region !== 'all') parts.push(`אזור: ${filters.region}`)
    if (filters.destination !== 'all') parts.push(`מדינה: ${filters.destination}`)
    if (filters.gb !== 'all') parts.push(`גלישה: ${GB_HEB[filters.gb] || filters.gb}`)
    if (filters.days !== 'all') parts.push(`תקופה: ${DAYS_HEB[filters.days] || filters.days}`)
    if (filters.gen !== 'all') parts.push(`דור: ${filters.gen === '5g' ? 'דור 5' : 'דור 4'}`)
    if (filters.roaming === 'yes') parts.push('כולל חו"ל')
    if (filters.contentService !== 'all') parts.push(`שירות: ${filters.contentService}`)
    const filterTitle = parts.join(' | ')

    // Build rows — fixed columns only
    const rows = filteredPlans.map(p => ({
      'ספק': CARRIER_HEB[p.carrier] || p.carrier,
      'שם חבילה': p.plan_name || p.service || '',
      'מחיר ₪': typeof p.price === 'string' ? p.price.replace('₪', '') : p.price,
      'גלישה GB': p.data_gb === null ? 'ללא הגבלה' : p.data_gb,
      'ימים': p.days || '',
      'דקות': p.minutes || '',
      'SMS': p.sms || '',
    }))

    // Create sheet with title row first
    const ws = XLSX.utils.aoa_to_sheet([[filterTitle], [`${filteredPlans.length} חבילות | ${new Date().toLocaleDateString('he-IL')}`], []])
    // Merge title row across all columns
    ws['!merges'] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 6 } }, { s: { r: 1, c: 0 }, e: { r: 1, c: 6 } }]
    // Append data rows starting at row 4
    XLSX.utils.sheet_add_json(ws, rows, { origin: 'A4' })
    // Column widths
    ws['!cols'] = [{ wch: 15 }, { wch: 35 }, { wch: 12 }, { wch: 12 }, { wch: 10 }, { wch: 10 }, { wch: 10 }]

    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, TAB_NAMES[tab] || tab)
    XLSX.writeFile(wb, `mass-market-${tab}-${new Date().toISOString().slice(0, 10)}.xlsx`)
  }, [filteredPlans, tab, filters])

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 pb-20 md:pb-6">
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          {lastUpdate && (
            <p className="text-[11px] text-gray-400">
              עדכון: {new Date(lastUpdate).toLocaleDateString('he-IL')} {lastUpdate.slice(11, 16)}
            </p>
          )}
        </div>
        {isAdmin && (
          <button
            onClick={handleScrape}
            disabled={scraping}
            className="text-[11px] text-gray-400 hover:text-gray-600 disabled:opacity-50 transition-colors"
          >
            {scraping ? '⏳ מעדכן...' : '🔄 עדכן'}
          </button>
        )}
      </div>

      {/* Tabs — slim underline style */}
      <div className="flex justify-center gap-0 mb-6 border-b border-gray-200">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => { setTab(t.id); setFilter('carrier', 'all'); setFilter('globalProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }}
            className={`relative px-4 py-2.5 text-[13px] font-medium transition-all duration-150
              ${tab === t.id
                ? 'text-gray-900 after:absolute after:bottom-0 after:inset-x-2 after:h-[2px] after:bg-gray-900 after:rounded-full'
                : 'text-gray-400 hover:text-gray-600'
              }`}
          >
            <span className="hidden sm:inline">{t.icon} </span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Filter strip */}
      <div className="mb-4">
        {/* Toggle + results count row */}
        <div className="flex items-center justify-between mb-2">
          <button
            onClick={() => setFiltersOpen(!filtersOpen)}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1.5 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
            </svg>
            <span>סינון</span>
            {activeFilterCount > 0 && (
              <span className="bg-gray-900 text-white text-[9px] px-1.5 py-0.5 rounded-full min-w-[16px] text-center">{activeFilterCount}</span>
            )}
          </button>

          <div className="flex items-center gap-3">
            <span className="text-[11px] text-gray-400">{filteredPlans.length} חבילות</span>
            {filteredPlans.length > 0 && (
              <button onClick={exportToExcel} className="text-[11px] text-blue-500 hover:text-blue-700 transition-colors" title="ייצוא ל-Excel">
                📥 Excel
              </button>
            )}
            {/* Sort pills */}
            {tab !== 'content' && (
              <div className="flex items-center gap-0.5">
                <FilterTag label="מחיר ↑" active={filters.sort === 'price_asc'} onClick={() => setFilter('sort', 'price_asc')} />
                <FilterTag label="מחיר ↓" active={filters.sort === 'price_desc'} onClick={() => setFilter('sort', 'price_desc')} />
                <FilterTag label="GB ↓" active={filters.sort === 'gb_desc'} onClick={() => setFilter('sort', 'gb_desc')} />
              </div>
            )}
          </div>
        </div>

        {/* Expandable filter rows */}
        {filtersOpen && (
          <div className="space-y-3 py-3 border-t border-gray-100 animate-in fade-in duration-200">
            {/* Carrier/Provider */}
            {(tab === 'domestic' || tab === 'abroad') && (
              <div>
                <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">חברה</p>
                <div className="flex flex-wrap gap-1">
                  <FilterTag label="כולם" active={filters.carrier === 'all'} onClick={() => setFilter('carrier', 'all')} />
                  {CARRIERS.map(c => {
                    const cnt = plans[tab]?.filter(p => p.carrier === c.id).length || 0
                    if (!cnt) return null
                    return <FilterTag key={c.id} label={c.label} active={filters.carrier === c.id} onClick={() => setFilter('carrier', c.id)} />
                  })}
                </div>
              </div>
            )}

            {tab === 'global' && (
              <div>
                <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">ספק</p>
                <div className="flex flex-wrap gap-1">
                  <FilterTag label="כולם" active={filters.globalProvider === 'all'} onClick={() => { setFilter('globalProvider', 'all'); setFilter('destination', 'all'); setFilter('region', 'all') }} />
                  {GLOBAL_PROVIDERS.map(p => {
                    const cnt = plans.global?.filter(x => x.carrier === p.id).length || 0
                    if (!cnt) return null
                    return <FilterTag key={p.id} label={p.label} active={filters.globalProvider === p.id} onClick={() => { setFilter('globalProvider', p.id); setFilter('destination', 'all'); setFilter('region', 'all') }} />
                  })}
                </div>
              </div>
            )}

            {tab === 'global' && globalRegions.length > 0 && (
              <div>
                <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">אזור</p>
                <select
                  value={filters.region}
                  onChange={e => { setFilter('region', e.target.value); if (e.target.value !== 'all') setFilter('destination', 'all') }}
                  className={`border rounded-lg px-2.5 py-1 text-xs transition-colors ${filters.region !== 'all' ? 'border-gray-900 bg-gray-50 text-gray-900' : 'border-gray-200 text-gray-500'}`}
                >
                  <option value="all">כל האזורים ({globalRegions.length})</option>
                  {globalRegions.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            )}

            {tab === 'global' && globalDestinations.length > 0 && (
              <div>
                <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">מדינה</p>
                <select
                  value={filters.destination}
                  onChange={e => { setFilter('destination', e.target.value); if (e.target.value !== 'all') setFilter('region', 'all') }}
                  className={`border rounded-lg px-2.5 py-1 text-xs transition-colors ${filters.destination !== 'all' ? 'border-gray-900 bg-gray-50 text-gray-900' : 'border-gray-200 text-gray-500'}`}
                >
                  <option value="all">כל המדינות ({globalDestinations.length})</option>
                  {globalDestinations.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            )}

            {tab === 'content' && (
              <>
                <div>
                  <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">חברה</p>
                  <div className="flex flex-wrap gap-1">
                    <FilterTag label="כולם" active={filters.contentCarrier === 'all'} onClick={() => setFilter('contentCarrier', 'all')} />
                    {['cellcom', 'partner', 'hotmobile', 'pelephone'].map(c => (
                      <FilterTag key={c} label={CARRIERS.find(x => x.id === c)?.label || c} active={filters.contentCarrier === c} onClick={() => setFilter('contentCarrier', c)} />
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">שירות</p>
                  <div className="flex flex-wrap gap-1">
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
              <div className="flex flex-wrap gap-6">
                <div>
                  <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">דור רשת</p>
                  <div className="flex flex-wrap gap-1">
                    <FilterTag label="כולם" active={filters.gen === 'all'} onClick={() => setFilter('gen', 'all')} />
                    <FilterTag label="4G" active={filters.gen === '4g'} onClick={() => setFilter('gen', '4g')} />
                    <FilterTag label="5G" active={filters.gen === '5g'} onClick={() => setFilter('gen', '5g')} />
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">גלישה בחו"ל</p>
                  <div className="flex flex-wrap gap-1">
                    <FilterTag label="כולם" active={filters.roaming === 'all'} onClick={() => setFilter('roaming', 'all')} />
                    <FilterTag label="כולל חו״ל" active={filters.roaming === 'yes'} onClick={() => setFilter('roaming', 'yes')} />
                  </div>
                </div>
              </div>
            )}

            {/* GB + Days */}
            {tab !== 'content' && (
              <div className="flex flex-wrap gap-6">
                <div>
                  <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">גלישה</p>
                  <div className="flex flex-wrap gap-1">
                    {['all', '0-5', '5-15', '15-100', '100+', 'unlimited'].map(v => (
                      <FilterTag key={v} label={v === 'all' ? 'הכל' : v === 'unlimited' ? 'ללא הגבלה' : `${v}GB`} active={filters.gb === v} onClick={() => setFilter('gb', v)} />
                    ))}
                  </div>
                </div>
                {(tab === 'abroad' || tab === 'global') && (
                  <div>
                    <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1.5">תקופה</p>
                    <div className="flex flex-wrap gap-1">
                      {['all', '1-7', '8-30', '30+'].map(v => (
                        <FilterTag key={v} label={v === 'all' ? 'הכל' : v === '30+' ? '30+ ימים' : `${v} ימים`} active={filters.days === v} onClick={() => setFilter('days', v)} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-20"><Spinner /></div>
      )}

      {/* Plan cards grid */}
      {!loading && tab !== 'content' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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
            <div key={svc} className="mb-8">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 pb-2 border-b border-gray-100">{svc}</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
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
        <div className="text-center py-20 text-gray-400">
          <p className="text-3xl mb-3 opacity-40">&#128269;</p>
          <p className="text-sm">לא נמצאו חבילות בסינון הנוכחי</p>
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
