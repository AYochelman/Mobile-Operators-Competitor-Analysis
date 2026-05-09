import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, API_BASE } from '../../lib/api'
import { DOMESTIC_LABELS, GLOBAL_LABELS } from '../../data/carrierLabels'
import { getCarrierColor } from './carrierMeta'
import CarrierChip from './CarrierChip'

/**
 * Time Machine — modal that loads a historical snapshot for a (carrier, date)
 * pair via /api/archive. Replaces the earlier "בקרוב" placeholder.
 */

const PLAN_TYPE_LABELS = {
  domestic: 'חבילות סלולר',
  abroad:   'חו״ל',
  global:   'גלובלי',
  content:  'תוכן',
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function PlanRow({ plan, isContent }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 80px',
        gap: 12,
        alignItems: 'baseline',
        padding: '10px 14px',
        background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 10,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--color-moca-dark)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {plan.plan_name || plan.service || '—'}
        </div>
        {!isContent && (plan.data_gb != null || plan.minutes || plan.days) && (
          <div style={{ fontSize: 11, color: 'var(--color-moca-muted)', marginTop: 2 }}>
            {plan.data_gb === null && 'ללא הגבלה'}
            {plan.data_gb != null && plan.data_gb >= 1 && `${plan.data_gb}GB`}
            {plan.data_gb != null && plan.data_gb < 1 && `${Math.round(plan.data_gb * 1024)}MB`}
            {plan.days ? ` · ${plan.days} ימים` : ''}
            {plan.minutes ? ` · ${plan.minutes} דק׳` : ''}
          </div>
        )}
      </div>
      <div
        className="tnum"
        style={{
          fontSize: 15,
          fontWeight: 800,
          color: 'var(--color-moca-bolt)',
          direction: 'ltr',
          textAlign: 'left',
        }}
      >
        {plan.price != null ? `${plan.price}${plan.currency && plan.currency !== 'ILS' ? plan.currency : '₪'}` : '—'}
      </div>
    </div>
  )
}

function ArchiveBannerPreview({ archiveDate, url, label }) {
  if (!url) return null
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--color-moca-muted)', marginBottom: 6 }}>
        {label} · {archiveDate}
      </div>
      <div
        style={{
          width: '100%',
          aspectRatio: '16 / 9',
          borderRadius: 10,
          overflow: 'hidden',
          background: 'var(--color-moca-cream)',
          border: '1px solid var(--color-moca-border)',
        }}
      >
        <img
          src={`${API_BASE}${url}`}
          alt={label}
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          loading="lazy"
        />
      </div>
    </div>
  )
}

export default function TimeMachineModal({ open, onClose }) {
  const [carrier, setCarrier]     = useState('')
  const [date, setDate]           = useState(todayIso())
  const [result, setResult]       = useState(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [dateRange, setDateRange] = useState(null)

  // Fetch available date range when modal opens
  useEffect(() => {
    if (!open) return
    api.getArchiveDateRange().then(setDateRange).catch(() => {})
  }, [open])

  // Esc to close + body scroll lock
  useEffect(() => {
    if (!open) return
    document.body.style.overflow = 'hidden'
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  // Reset transient state when modal closes
  useEffect(() => {
    if (open) return
    setResult(null)
    setError(null)
    setLoading(false)
  }, [open])

  if (!open) return null

  async function runSearch() {
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

  // Carriers — domestic first (most relevant for Time Machine), then global
  const domesticOpts = Object.entries(DOMESTIC_LABELS)
  const globalOpts = Object.entries(GLOBAL_LABELS).filter(([id]) => id !== 'airalo_local' && id !== 'airalo_regional')

  const hasData = result && (
    Object.keys(result.plans || {}).length > 0 ||
    Object.keys(result.banners || {}).length > 0
  )

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9000,
        background: 'rgba(40,30,15,0.45)',
        backdropFilter: 'blur(3px)',
        WebkitBackdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
        animation: 'fadeIn 200ms var(--ease-out)',
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Time Machine"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 880,
          maxHeight: '92vh',
          background: 'var(--color-moca-bg)',
          borderRadius: 16,
          boxShadow: 'var(--sh-modal)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'fadeInUp 250ms var(--ease-out)',
        }}
      >
        {/* Header */}
        <header
          style={{
            padding: '16px 22px 14px',
            borderBottom: '1px solid var(--color-moca-border)',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            gap: 12,
            background: 'var(--color-moca-cream)',
          }}
        >
          <div>
            <div
              style={{
                fontSize: 10,
                color: 'var(--color-moca-muted)',
                fontWeight: 800,
                letterSpacing: 0.7,
                textTransform: 'uppercase',
                marginBottom: 4,
              }}
            >
              כלים · ארכיב חי
            </div>
            <h2
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 22,
                fontWeight: 800,
                color: 'var(--color-moca-dark)',
                margin: 0,
                letterSpacing: -0.4,
              }}
            >
              צפה בעבר
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="סגור"
            style={{
              width: 34,
              height: 34,
              borderRadius: 999,
              background: 'var(--color-moca-white, #fff)',
              border: '1px solid var(--color-moca-border)',
              color: 'var(--color-moca-sub)',
              fontSize: 20,
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'inherit',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </header>

        {/* Filter row */}
        <div
          style={{
            padding: '14px 22px',
            borderBottom: '1px solid var(--color-moca-border)',
            display: 'flex',
            gap: 12,
            flexWrap: 'wrap',
            alignItems: 'flex-end',
          }}
        >
          <div style={{ flex: '1 1 200px', minWidth: 180 }}>
            <label style={{ display: 'block', fontSize: 10.5, color: 'var(--color-moca-muted)', fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', marginBottom: 6 }}>
              מתחרה
            </label>
            <select
              value={carrier}
              onChange={(e) => { setCarrier(e.target.value); setResult(null) }}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 10,
                border: '1px solid var(--color-moca-border)',
                background: 'var(--color-moca-white, #fff)',
                color: 'var(--color-moca-text)',
                fontSize: 13,
                fontFamily: 'inherit',
                cursor: 'pointer',
              }}
            >
              <option value="">בחר מתחרה…</option>
              <optgroup label="ישראל">
                {domesticOpts.map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </optgroup>
              <optgroup label="גלובלי">
                {globalOpts.map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </optgroup>
            </select>
          </div>

          <div style={{ flex: '1 1 160px', minWidth: 150 }}>
            <label style={{ display: 'block', fontSize: 10.5, color: 'var(--color-moca-muted)', fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', marginBottom: 6 }}>
              תאריך
              {dateRange?.min && (
                <span style={{ fontWeight: 500, marginInlineStart: 6, textTransform: 'none', letterSpacing: 0 }}>
                  ({dateRange.min} – {dateRange.max})
                </span>
              )}
            </label>
            <input
              type="date"
              value={date}
              max={todayIso()}
              min={dateRange?.min || undefined}
              onChange={(e) => { setDate(e.target.value); setResult(null) }}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 10,
                border: '1px solid var(--color-moca-border)',
                background: 'var(--color-moca-white, #fff)',
                color: 'var(--color-moca-text)',
                fontSize: 13,
                fontFamily: 'inherit',
              }}
            />
          </div>

          <button
            onClick={runSearch}
            disabled={!carrier || !date || loading}
            style={{
              padding: '10px 22px',
              borderRadius: 10,
              background: 'var(--color-moca-bolt)',
              color: '#fff',
              fontSize: 13,
              fontWeight: 700,
              cursor: !carrier || !date || loading ? 'not-allowed' : 'pointer',
              border: 'none',
              fontFamily: 'inherit',
              opacity: !carrier || !date || loading ? 0.5 : 1,
              transition: 'opacity 120ms ease',
              flexShrink: 0,
            }}
          >
            {loading ? 'טוען…' : 'הצג snapshot'}
          </button>
        </div>

        {/* Results */}
        <div style={{ flex: 1, minHeight: 240, overflowY: 'auto', padding: '18px 22px', background: 'var(--color-moca-bg)' }}>
          {!result && !loading && !error && (
            <div
              style={{
                textAlign: 'center',
                padding: '40px 20px',
                color: 'var(--color-moca-muted)',
                fontSize: 13,
              }}
            >
              <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.35, marginBottom: 10 }}>
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
                <path d="M3.5 8.5 6 6" />
              </svg>
              <p style={{ margin: 0 }}>בחר מתחרה ותאריך כדי לצפות במצב שהיה באותו יום.</p>
            </div>
          )}

          {error && (
            <div
              style={{
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: 10,
                padding: 12,
                color: '#b91c1c',
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          {result && !hasData && (
            <div
              style={{
                background: 'var(--color-moca-white, #fff)',
                border: '1px dashed var(--color-moca-border)',
                borderRadius: 12,
                padding: '24px 18px',
                textAlign: 'center',
                color: 'var(--color-moca-muted)',
                fontSize: 13,
                lineHeight: 1.5,
              }}
            >
              אין נתונים שמורים עבור <strong style={{ color: 'var(--color-moca-text)' }}>{carrier}</strong> בתאריך {date} או לפניו.
              <br />
              <span style={{ fontSize: 11, marginTop: 4, display: 'inline-block' }}>
                הארכיב נשמר רק כאשר מתרחש שינוי.
              </span>
            </div>
          )}

          {result && hasData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
              {/* Carrier header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <CarrierChip id={carrier} size={28} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-moca-dark)' }}>
                    {DOMESTIC_LABELS[carrier] || GLOBAL_LABELS[carrier] || carrier}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>
                    snapshot מ-{date} ולפניו
                  </div>
                </div>
              </div>

              {/* Banners */}
              {(result.banners?.homepage || result.banners?.store) && (
                <section>
                  <h3
                    style={{
                      fontSize: 10.5,
                      color: 'var(--color-moca-muted)',
                      fontWeight: 800,
                      letterSpacing: 0.6,
                      textTransform: 'uppercase',
                      margin: '0 0 10px',
                    }}
                  >
                    באנרים
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: result.banners.homepage && result.banners.store ? '1fr 1fr' : '1fr', gap: 12 }}>
                    {result.banners.homepage && (
                      <ArchiveBannerPreview
                        archiveDate={result.banners.homepage.archive_date}
                        url={result.banners.homepage.url}
                        label="עמוד ראשי"
                      />
                    )}
                    {result.banners.store && (
                      <ArchiveBannerPreview
                        archiveDate={result.banners.store.archive_date}
                        url={result.banners.store.url}
                        label="חנות ציוד"
                      />
                    )}
                  </div>
                </section>
              )}

              {/* Plans per type */}
              {Object.entries(result.plans).map(([planType, data]) => (
                <section key={planType}>
                  <h3
                    style={{
                      fontSize: 10.5,
                      color: 'var(--color-moca-muted)',
                      fontWeight: 800,
                      letterSpacing: 0.6,
                      textTransform: 'uppercase',
                      margin: '0 0 8px',
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 8,
                    }}
                  >
                    {PLAN_TYPE_LABELS[planType] || planType}
                    <span style={{ fontWeight: 500, fontSize: 10.5, letterSpacing: 0, textTransform: 'none', color: 'var(--color-moca-muted)' }}>
                      snapshot מ-{data.snapshot_date} · {data.plans.length} מסלולים
                    </span>
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 8 }}>
                    {data.plans.map((plan, i) => (
                      <PlanRow key={i} plan={plan} isContent={planType === 'content'} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
