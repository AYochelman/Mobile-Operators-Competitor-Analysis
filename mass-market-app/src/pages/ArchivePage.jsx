import { useState, useEffect } from 'react'
import { api, API_BASE } from '../lib/api'
import PlanCard from '../components/PlanCard'
import BannerCard from '../components/BannerCard'

// All carriers / providers that may appear in the archive
const ALL_PROVIDERS = [
  // ── Domestic ────────────────────────────────────────────────
  { id: 'partner',          label: 'פרטנר',          color: '#e8003d' },
  { id: 'pelephone',        label: 'פלאפון',          color: '#ff6600' },
  { id: 'hotmobile',        label: 'הוט מובייל',      color: '#e3001e' },
  { id: 'cellcom',          label: 'סלקום',           color: '#003b7a' },
  { id: 'mobile019',        label: '019 מובייל',      color: '#555555' },
  { id: 'xphone',           label: 'XPhone',          color: '#6a0dad' },
  { id: 'wecom',            label: 'וי-קום',          color: '#006633' },
  { id: 'neptucom',         label: 'נפטוקום',         color: '#004488' },
  { id: 'golan',            label: 'גולן טלקום',      color: '#009688' },
  { id: 'rami_levy',        label: 'רמי לוי',          color: '#e32032' },
  // ── Global eSIM ─────────────────────────────────────────────
  { id: 'tuki',             label: 'טוקי',            color: '#0066cc' },
  { id: 'globalesim',       label: 'GlobaleSIM',      color: '#0099aa' },
  { id: 'airalo',           label: 'Airalo',          color: '#33cc77' },
  { id: 'pelephone_global', label: 'פלאפון גלובל',   color: '#ff6600' },
  { id: 'esimo',            label: 'eSIMo',           color: '#7700cc' },
  { id: 'simtlv',           label: 'SimTLV',          color: '#cc4400' },
  { id: 'world8',           label: 'World8',          color: '#005599' },
  { id: 'xphone_global',    label: 'XPhone גלובל',   color: '#6a0dad' },
  { id: 'saily',            label: 'Saily',           color: '#00aacc' },
  { id: 'holafly',          label: 'Holafly',         color: '#ff9900' },
  { id: 'esimio',           label: 'eSIMio',          color: '#aa0077' },
  { id: 'sparks',           label: 'Sparks',          color: '#ff4400' },
  { id: 'voye',             label: 'Voye',            color: '#009966' },
  { id: 'orbit',            label: 'Orbit',           color: '#003366' },
  { id: 'travelsim',        label: 'TravelSIM',       color: '#336600' },
  { id: 'gomoworld',        label: 'GoMoWorld',       color: '#0891b2' },
  { id: 'tasim',            label: 'Tasim',           color: '#7c3aed' },
  { id: 'maya',             label: 'Maya Mobile',     color: '#0f766e' },
  { id: 'bcengi',         label: 'Bcengi',         color: '#1d4ed8' },
  { id: 'esim70',         label: 'eSIM70',         color: '#10b981' },
  { id: 'jetpack',        label: 'Jetpack',        color: '#0ea5e9' },
  { id: 'breez',          label: 'Breeze',          color: '#06b6d4' },
  { id: 'bytesim',        label: 'ByteSim',        color: '#00b490' },
  { id: 'besim',          label: 'Besim',          color: '#0ea5a4' },
]

const PLAN_TYPE_LABELS = {
  domestic: 'חבילות סלולר',
  abroad:   'חו"ל',
  global:   'גלובלי',
  content:  'תוכן',
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function ArchivePage() {
  const [carrier, setCarrier]   = useState('')
  const [date, setDate]         = useState(todayIso())
  const [result, setResult]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [dateRange, setDateRange] = useState(null)

  // Fetch available date range for the min/max hint
  useEffect(() => {
    api.getArchiveDateRange()
      .then(setDateRange)
      .catch(() => {}) // non-critical
  }, [])

  async function handleSearch() {
    if (!carrier || !date) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.getArchive(carrier, date)
      setResult(data)
    } catch (e) {
      setError(e.message || 'שגיאה בטעינת הארכיב')
    } finally {
      setLoading(false)
    }
  }

  const providerInfo = ALL_PROVIDERS.find(p => p.id === carrier)
  const hasData = result && (
    Object.keys(result.plans || {}).length > 0 ||
    Object.keys(result.banners || {}).length > 0
  )

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Page identity is owned by the Topbar — keep only the subtitle hint. */}
      <p className="text-[13px] text-moca-muted mb-6">
        חבילות ובאנרים של ספק בתאריך נבחר
      </p>

      {/* Filter row */}
      <div className="bg-white border border-moca-border/60 rounded-xl p-4 mb-6 flex flex-wrap gap-3 items-end">
        {/* Carrier selector */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-[11px] font-medium text-gray-500 mb-1.5">ספק</label>
          <select
            value={carrier}
            onChange={e => { setCarrier(e.target.value); setResult(null) }}
            className="w-full border border-moca-border/60 rounded-lg px-3 py-2 text-[13px] text-moca-text bg-white focus:outline-none focus:ring-1 focus:ring-moca-bolt/40"
          >
            <option value="">בחר ספק...</option>
            {ALL_PROVIDERS.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>

        {/* Date picker */}
        <div className="flex-1 min-w-[160px]">
          <label className="block text-[11px] font-medium text-gray-500 mb-1.5">
            תאריך
            {dateRange?.min && (
              <span className="font-normal text-moca-muted mr-1">
                ({dateRange.min} – {dateRange.max})
              </span>
            )}
          </label>
          <input
            type="date"
            value={date}
            max={todayIso()}
            min={dateRange?.min || undefined}
            onChange={e => { setDate(e.target.value); setResult(null) }}
            className="w-full border border-moca-border/60 rounded-lg px-3 py-2 text-[13px] text-moca-text bg-white focus:outline-none focus:ring-1 focus:ring-moca-bolt/40"
          />
        </div>

        {/* Search button */}
        <button
          onClick={handleSearch}
          disabled={!carrier || !date || loading}
          className="px-5 py-2 bg-moca-bolt text-white text-[13px] font-medium rounded-lg
                     hover:bg-moca-bolt/90 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors whitespace-nowrap"
        >
          {loading ? 'טוען...' : 'חפש'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 text-[13px] text-red-600">
          {error}
        </div>
      )}

      {/* No data message */}
      {result && !hasData && (
        <div className="bg-white border border-moca-border/60 rounded-xl p-8 text-center text-moca-muted text-[13px]">
          אין נתונים שמורים עבור <strong className="text-moca-text">{providerInfo?.label || carrier}</strong> בתאריך {date} או לפניו.
          <br />
          <span className="text-[11px] mt-1 block">הארכיב שומר נתונים מרגע הפעלתו, ומעדכן רק כאשר מתרחש שינוי.</span>
        </div>
      )}

      {/* Results */}
      {result && hasData && (
        <div className="space-y-8">
          {/* Provider header */}
          {providerInfo && (
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ background: providerInfo.color }}
              />
              <h2 className="text-base font-semibold text-moca-text">{providerInfo.label}</h2>
              <span className="text-[11px] text-moca-muted">— נתונים מ-{date} ולפניו</span>
            </div>
          )}

          {/* Banners */}
          {(result.banners?.homepage || result.banners?.store) && (
            <section>
              <h3 className="text-[13px] font-medium text-gray-500 mb-3">באנרים</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {result.banners.homepage && (
                  <div>
                    <p className="text-[11px] text-moca-muted mb-1.5">
                      דף בית — {result.banners.homepage.archive_date}
                    </p>
                    <BannerCard banner={{
                      carrier,
                      name: providerInfo?.label || carrier,
                      url: '#',
                      color: providerInfo?.color || '#888',
                      image_url: result.banners.homepage.url,
                      scraped_at: result.banners.homepage.archive_date,
                    }} />
                  </div>
                )}
                {result.banners.store && (
                  <div>
                    <p className="text-[11px] text-moca-muted mb-1.5">
                      חנות — {result.banners.store.archive_date}
                    </p>
                    <BannerCard banner={{
                      carrier,
                      name: providerInfo?.label || carrier,
                      url: '#',
                      color: providerInfo?.color || '#888',
                      image_url: result.banners.store.url,
                      scraped_at: result.banners.store.archive_date,
                    }} />
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Plan sections per type */}
          {Object.entries(result.plans).map(([planType, data]) => (
            <section key={planType}>
              <div className="flex items-center gap-2 mb-3">
                <h3 className="text-[13px] font-medium text-gray-500">
                  {PLAN_TYPE_LABELS[planType] || planType}
                </h3>
                <span className="text-[11px] text-moca-muted">
                  — snapshot מ-{data.snapshot_date} · {data.plans.length} חבילות
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {data.plans.map((plan, i) => (
                  <PlanCard key={i} plan={plan} type={planType} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Empty state — nothing searched yet */}
      {!result && !loading && !error && (
        <div className="bg-white border border-dashed border-moca-border rounded-xl p-12 text-center text-moca-muted">
          <svg className="mx-auto mb-3 opacity-30" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="10"/>
          </svg>
          <p className="text-[13px]">בחר ספק ותאריך כדי לצפות בנתונים היסטוריים</p>
        </div>
      )}
    </div>
  )
}
