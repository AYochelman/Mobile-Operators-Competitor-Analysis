import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'
import { ISRAELI_GLOBAL_PROVIDERS } from '../data/carrierLabels'
import BannerMosaic from '../components/moca/BannerMosaic'

/* ─────────────────────────────────────────────────────────────
   "באנרים גלובליים" — homepage banner screenshots of every global
   eSIM provider, captured on the same schedule as the domestic
   carrier banners. Fed by api.getGlobalBanners() → /api/global-banners.
   Split into international (first) + Israeli, each sorted A→Z.
   Banners whose homepage campaign changed recently get a freshness badge.
   ───────────────────────────────────────────────────────────── */

function Spinner() {
  return (
    <div
      style={{
        width: 28, height: 28, borderRadius: '50%',
        border: '3px solid var(--color-moca-border)',
        borderTopColor: 'var(--color-moca-bolt)',
        animation: 'spin 0.8s linear infinite',
      }}
    />
  )
}

function SectionHeading({ children, count }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '0 0 14px' }}>
      <h2
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 18,
          fontWeight: 800,
          color: 'var(--color-moca-dark)',
          letterSpacing: -0.3,
          textAlign: 'right',
          margin: 0,
        }}
      >
        {children}
      </h2>
      {count != null && (
        <span style={{ fontSize: 12, color: 'var(--color-moca-muted)', fontWeight: 700 }}>{count}</span>
      )}
    </div>
  )
}

export default function GlobalBannersPage() {
  const { tt } = useLang()
  const [banners, setBanners] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    api.getGlobalBanners()
      .then((data) => { if (alive) setBanners(Array.isArray(data) ? data : []) })
      .catch((err) => console.error(err))
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  // Split international vs Israeli, each sorted A→Z by display name.
  const { international, israeli } = useMemo(() => {
    const byName = (a, b) => (a.name || a.carrier).localeCompare(b.name || b.carrier, 'en', { sensitivity: 'base' })
    const intl = [], isr = []
    for (const b of banners) {
      (ISRAELI_GLOBAL_PROVIDERS.has(b.carrier) ? isr : intl).push(b)
    }
    intl.sort(byName)
    isr.sort(byName)
    return { international: intl, israeli: isr }
  }, [banners])

  const freshCount = useMemo(() => banners.filter(b => b.changed_recently).length, [banners])

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 22,
          fontWeight: 800,
          color: 'var(--color-moca-dark)',
          letterSpacing: -0.4,
          margin: '0 0 6px',
          textAlign: 'right',
        }}
      >
        {tt('באנרים גלובליים', 'Global banners')}
      </h1>

      {/* info strip */}
      <div className="mb-5 px-1 flex items-center gap-2 text-xs text-moca-muted flex-wrap">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" />
        </svg>
        <span>{tt('צילומי מסך אוטומטיים של עמוד הבית של ספקי ה-eSIM הגלובליים - מתעדכנים יחד עם דגימת הספקים המקומיים', 'Automatic homepage screenshots of the global eSIM providers - refreshed together with the domestic-provider capture')}</span>
        {freshCount > 0 && (
          <span
            style={{
              background: 'var(--color-moca-hot)', color: '#fff', fontWeight: 800,
              fontSize: 10, padding: '2px 8px', borderRadius: 999, letterSpacing: 0.2,
            }}
          >
            {tt(`${freshCount} התעדכנו`, `${freshCount} updated`)}
          </span>
        )}
      </div>

      {loading && (
        <div className="flex justify-center py-20"><Spinner /></div>
      )}

      {!loading && banners.length === 0 && (
        <div className="text-center text-moca-muted py-16 text-sm">
          {tt('אין באנרים זמינים עדיין - הם יצולמו בדגימה הבאה', 'No banners available yet - they will be captured on the next run')}
        </div>
      )}

      {!loading && international.length > 0 && (
        <div className="mb-8">
          <SectionHeading count={international.length}>{tt('בינלאומיים', 'International')}</SectionHeading>
          <BannerMosaic banners={international} source="home" />
        </div>
      )}

      {!loading && israeli.length > 0 && (
        <div>
          <SectionHeading count={israeli.length}>{tt('ישראליים', 'Israeli')}</SectionHeading>
          <BannerMosaic banners={israeli} source="home" />
        </div>
      )}
    </div>
  )
}
