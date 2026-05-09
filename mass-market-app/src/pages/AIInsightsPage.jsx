import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { DOMESTIC_LABELS, carrierLabel } from '../data/carrierLabels'
import { CarrierChip, Tag } from '../components/moca'
import { getCarrierColor } from '../components/moca/carrierMeta'

/**
 * Per-carrier AI insight feed. Each row pulls a focused Hebrew competitive
 * report from Claude (Sonnet) on demand — clicking "טען דוח AI" expands the
 * card with the full text inline.
 *
 * Activity counters (plans / changes-7d) are derived from /api/plans and
 * /api/changes so the feed shows real signal without waiting for AI.
 */

const REPORT_PROMPT = (carrierName) => `תן לי דוח תחרותי תמציתי וממוקד על ${carrierName}.

תוכן רצוי (בסדר הזה):
1. **מצב נוכחי** — מספר חבילות פעילות וטווחי מחירים (ביתי וחו"ל בנפרד)
2. **אסטרטגיה** — מה הספק מנסה לעשות? (תחרות במחיר, פרימיום, data-heavy, חו"ל וכד')
3. **שינויים אחרונים** — מה קרה בחבילות שלו לאחרונה (אם יש בנתונים)
4. **מול המתחרים** — שני משפטים על נקודות חוזק וחולשה ביחס לאחרים
5. **הזדמנויות** — 1-3 פעולות שהמתחרים יכולים לנצל

דרישות איכות (חובה):
- כתוב בעברית תקנית בלבד. אל תמציא מילים. אל תתרגם ישירות מאנגלית — אם אתה לא בטוח במונח, השתמש בעברית פשוטה או השאר באנגלית.
- בדוק כל משפט לפני שאתה כותב אותו. אם משהו נשמע מוזר — נסח מחדש.
- השתמש במונחי הענף הנכונים: "חבילת גלישה", "דקות שיחה", "הודעות SMS", "גלישה בחו\\"ל".
- אורך כולל: עד 220 מילים.
- פורמט: כותרות מודגשות (## כותרת), נקודות קצרות תחת כל כותרת.`

function CarrierInsightCard({ carrierId, planCount, changes7d, accentColor }) {
  const carrierName = carrierLabel(carrierId)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [report, setReport] = useState('')
  const [generatedAt, setGeneratedAt] = useState(null)

  async function loadReport() {
    setLoading(true)
    setError(null)
    setReport('')
    try {
      const res = await api.chat(REPORT_PROMPT(carrierName), 'sonnet')
      setReport(res?.answer || res?.response || res?.text || JSON.stringify(res))
      setGeneratedAt(new Date())
    } catch (e) {
      setError(e.message || 'שגיאה בטעינת הדוח')
    } finally {
      setLoading(false)
    }
  }

  function toggle() {
    const next = !open
    setOpen(next)
    if (next && !report && !loading) loadReport()
  }

  const hasActivity = changes7d > 0
  const isHot = changes7d >= 3

  return (
    <article
      style={{
        background: 'var(--color-moca-white, #fff)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 14,
        boxShadow: 'var(--sh-card)',
        overflow: 'hidden',
        position: 'relative',
        transition: 'box-shadow 160ms var(--ease-out)',
      }}
    >
      {/* Carrier color accent strip */}
      <span
        aria-hidden="true"
        style={{
          position: 'absolute',
          insetInlineStart: 0,
          top: 0,
          bottom: 0,
          width: 3,
          background: accentColor,
        }}
      />

      <header
        style={{
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
          <CarrierChip id={carrierId} size={36} />
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 16,
                fontWeight: 800,
                color: 'var(--color-moca-dark)',
                letterSpacing: -0.2,
                lineHeight: 1.2,
              }}
            >
              {carrierName}
            </div>
            <div
              className="tnum"
              style={{
                fontSize: 11,
                color: 'var(--color-moca-muted)',
                marginTop: 2,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
              }}
            >
              <span>{planCount} מסלולים</span>
              {hasActivity && (
                <>
                  <span aria-hidden="true">·</span>
                  <span style={{ color: isHot ? 'var(--color-moca-up)' : 'var(--color-moca-sub)', fontWeight: 700 }}>
                    {changes7d} שינויים · 7 ימים
                  </span>
                </>
              )}
              {isHot && <Tag color="var(--color-moca-up)">HOT</Tag>}
            </div>
          </div>
        </div>

        <button
          onClick={toggle}
          disabled={loading}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 14px',
            borderRadius: 10,
            border: '1px solid var(--color-moca-border)',
            background: open ? 'var(--color-moca-cream)' : 'var(--color-moca-white, #fff)',
            color: open ? 'var(--color-moca-bolt)' : 'var(--color-moca-text)',
            fontSize: 12.5,
            fontWeight: 700,
            cursor: loading ? 'wait' : 'pointer',
            fontFamily: 'inherit',
            transition: 'all 120ms ease',
            flexShrink: 0,
            opacity: loading ? 0.7 : 1,
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3v2M12 19v2M5 12H3M21 12h-2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" />
            <circle cx="12" cy="12" r="4" />
          </svg>
          {loading ? 'מנתח…' : (open ? (report ? 'הסתר דוח' : 'טוען…') : 'טען דוח AI')}
        </button>
      </header>

      {open && (
        <div
          style={{
            padding: '0 18px 18px',
            borderTop: '1px solid var(--color-moca-border)',
          }}
        >
          {loading && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '28px 14px',
                gap: 12,
                color: 'var(--color-moca-muted)',
              }}
            >
              <div
                className="animate-spin"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 999,
                  border: '3px solid var(--color-moca-border)',
                  borderTopColor: 'var(--color-moca-bolt)',
                }}
              />
              <p style={{ fontSize: 12, margin: 0 }}>Claude מנתח את הנתונים…</p>
            </div>
          )}

          {error && !loading && (
            <div
              style={{
                marginTop: 14,
                padding: 12,
                borderRadius: 10,
                background: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#b91c1c',
                fontSize: 13,
              }}
            >
              {error}{' '}
              <button
                onClick={loadReport}
                style={{
                  marginInlineStart: 8,
                  fontSize: 11,
                  textDecoration: 'underline',
                  background: 'transparent',
                  border: 'none',
                  color: '#b91c1c',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                נסה שוב
              </button>
            </div>
          )}

          {!loading && !error && report && (
            <div
              style={{
                marginTop: 14,
                fontSize: 13.5,
                color: 'var(--color-moca-text)',
                lineHeight: 1.65,
                whiteSpace: 'pre-line',
              }}
            >
              {report}
              <div
                style={{
                  marginTop: 16,
                  paddingTop: 12,
                  borderTop: '1px solid var(--color-moca-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  flexWrap: 'wrap',
                }}
              >
                <button
                  onClick={loadReport}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 11.5,
                    color: 'var(--color-moca-bolt)',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    fontWeight: 600,
                  }}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="23 4 23 10 17 10" />
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                  </svg>
                  רענן דוח
                </button>
                {generatedAt && (
                  <span style={{ fontSize: 10, color: 'var(--color-moca-muted)' }}>
                    Claude Sonnet · {generatedAt.toLocaleString('he-IL', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  )
}

function FeedSummary({ totalPlans, totalChanges7d, hotCount }) {
  return (
    <div
      style={{
        background: 'var(--color-moca-cream)',
        border: '1px solid var(--color-moca-border)',
        borderRadius: 14,
        padding: '14px 18px',
        display: 'flex',
        gap: 28,
        alignItems: 'center',
        flexWrap: 'wrap',
        marginBottom: 18,
      }}
    >
      <div className="tnum">
        <div style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 0.6, textTransform: 'uppercase' }}>
          מסלולים תחת מעקב
        </div>
        <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-moca-dark)', letterSpacing: -0.4, lineHeight: 1.1, marginTop: 2 }}>
          {totalPlans}
        </div>
      </div>
      <div className="tnum">
        <div style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 0.6, textTransform: 'uppercase' }}>
          שינויים · 7 ימים
        </div>
        <div style={{ fontSize: 24, fontWeight: 800, color: totalChanges7d > 0 ? 'var(--color-moca-up)' : 'var(--color-moca-dark)', letterSpacing: -0.4, lineHeight: 1.1, marginTop: 2, direction: 'ltr' }}>
          {totalChanges7d}
        </div>
      </div>
      {hotCount > 0 && (
        <div className="tnum">
          <div style={{ fontSize: 10, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 0.6, textTransform: 'uppercase' }}>
            מתחרים פעילים
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-moca-hot)', letterSpacing: -0.4, lineHeight: 1.1, marginTop: 2 }}>
            {hotCount}
          </div>
        </div>
      )}
    </div>
  )
}

export default function AIInsightsPage() {
  const allDomestic = Object.keys(DOMESTIC_LABELS)
  const carriers = useVisibleCarriers(allDomestic)

  const [plans, setPlans]         = useState([])
  const [changes, setChanges]     = useState([])
  const [loading, setLoading]     = useState(true)

  // Pull plans + changes once so each card can show real activity stats.
  useEffect(() => {
    let alive = true
    Promise.all([
      api.getPlans().catch(() => []),
      api.getChanges(500).catch(() => []),
    ]).then(([planData, changeData]) => {
      if (!alive) return
      setPlans(Array.isArray(planData) ? planData : (planData?.plans || []))
      setChanges(Array.isArray(changeData) ? changeData : (changeData?.changes || []))
      setLoading(false)
    })
    return () => { alive = false }
  }, [])

  // Derive per-carrier stats (memo so we don't recompute on every render)
  const stats = useMemo(() => {
    const recent7d = Date.now() - 7 * 24 * 60 * 60 * 1000
    const planBuckets = new Map()
    for (const p of plans) {
      if (!p?.carrier) continue
      planBuckets.set(p.carrier, (planBuckets.get(p.carrier) || 0) + 1)
    }
    const changeBuckets = new Map()
    for (const c of changes) {
      if (!c?.carrier) continue
      const ts = c.changed_at ? new Date(c.changed_at).getTime() : 0
      if (ts < recent7d) continue
      changeBuckets.set(c.carrier, (changeBuckets.get(c.carrier) || 0) + 1)
    }
    return { planBuckets, changeBuckets }
  }, [plans, changes])

  // Sort: HOT (most-active) first, then by plan count
  const sortedCarriers = useMemo(() => {
    return [...carriers].sort((a, b) => {
      const aChanges = stats.changeBuckets.get(a) || 0
      const bChanges = stats.changeBuckets.get(b) || 0
      if (aChanges !== bChanges) return bChanges - aChanges
      const aPlans = stats.planBuckets.get(a) || 0
      const bPlans = stats.planBuckets.get(b) || 0
      return bPlans - aPlans
    })
  }, [carriers, stats])

  const totalPlans = Array.from(stats.planBuckets.values()).reduce((a, b) => a + b, 0)
  const totalChanges7d = Array.from(stats.changeBuckets.values()).reduce((a, b) => a + b, 0)
  const hotCount = sortedCarriers.filter((id) => (stats.changeBuckets.get(id) || 0) >= 3).length

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 md:py-8">
      {/* Page header */}
      <div style={{ marginBottom: 18 }}>
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--color-moca-muted)',
            fontWeight: 800,
            letterSpacing: 0.6,
            textTransform: 'uppercase',
            marginBottom: 4,
          }}
        >
          תובנות · ניתוח Claude
        </div>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 28,
            fontWeight: 800,
            color: 'var(--color-moca-dark)',
            letterSpacing: -0.5,
            margin: 0,
            lineHeight: 1.15,
          }}
        >
          AI Insights
        </h1>
        <p
          style={{
            fontSize: 13.5,
            color: 'var(--color-moca-sub)',
            margin: '6px 0 0',
            lineHeight: 1.55,
            maxWidth: 640,
          }}
        >
          דוח תחרותי לכל מתחרה — מצב נוכחי, אסטרטגיה, שינויים אחרונים והזדמנויות. הדוחות נטענים בלחיצה ומיוצרים על ידי Claude Sonnet.
        </p>
      </div>

      {!loading && (
        <FeedSummary
          totalPlans={totalPlans}
          totalChanges7d={totalChanges7d}
          hotCount={hotCount}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {sortedCarriers.map((id) => (
          <CarrierInsightCard
            key={id}
            carrierId={id}
            planCount={stats.planBuckets.get(id) || 0}
            changes7d={stats.changeBuckets.get(id) || 0}
            accentColor={getCarrierColor(id)}
          />
        ))}
      </div>

      {sortedCarriers.length === 0 && !loading && (
        <div
          style={{
            background: 'var(--color-moca-white, #fff)',
            border: '1px dashed var(--color-moca-border)',
            borderRadius: 12,
            padding: '32px 18px',
            textAlign: 'center',
            color: 'var(--color-moca-muted)',
            fontSize: 13,
          }}
        >
          אין מתחרים זמינים בטלסקופ הנוכחי.
        </div>
      )}
    </div>
  )
}
