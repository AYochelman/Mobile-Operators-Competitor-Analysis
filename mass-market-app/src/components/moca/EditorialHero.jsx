import { useNavigate } from 'react-router-dom'
import CarrierChip from './CarrierChip'
import { getCarrierName } from './carrierMeta'

/**
 * Lead-story card per the design's Editorial Deep dashboard.
 *
 * Takes the biggest 24h competitor change + our closest matching plan and
 * renders it as a "magazine cover": kicker / headline / narrative / actions
 * on the left, side-by-side comparison cards on the right.
 *
 * Empty state (no significant change in last 24h): still renders a calm
 * placeholder rather than collapsing — the dashboard top should never feel
 * unanchored.
 */

function fmtHoursAgo(iso) {
  if (!iso) return ''
  const ms = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(ms / (60 * 60 * 1000))
  if (hours < 1) return 'הרגע'
  if (hours === 1) return 'לפני שעה'
  if (hours < 24) return `לפני ${hours} שעות`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'אתמול' : `לפני ${days} ימים`
}

function buildHeadline(change) {
  if (!change) return null
  const carrier = getCarrierName(change.carrier)
  const name = change.plan_name || ''
  const oldVal = Number(change.old_val)
  const newVal = Number(change.new_val)

  if (change.change_type === 'price_change' && Number.isFinite(oldVal) && Number.isFinite(newVal)) {
    const diff = oldVal - newVal
    if (diff > 0) {
      return {
        kicker: `שינוי משמעותי בשוק · ${fmtHoursAgo(change.changed_at)}`,
        title: (
          <>
            {carrier} חתכה את <span style={{ color: 'var(--color-moca-down)', textDecoration: 'underline', textDecorationColor: 'var(--color-moca-down)', textUnderlineOffset: 4 }}>{name} ב-{diff}₪</span>
          </>
        ),
        body: `המחיר החדש (${newVal}₪) ירידה של ${Math.round((diff / oldVal) * 100)}% מהמחיר הקודם. ${carrier} מציבה לחץ תחרותי על מסלולים בקטגוריה דומה.`,
      }
    }
    if (diff < 0) {
      return {
        kicker: `התייקרות · ${fmtHoursAgo(change.changed_at)}`,
        title: (
          <>
            {carrier} העלתה את <span style={{ color: 'var(--color-moca-up)' }}>{name} ב-{-diff}₪</span> — הפוך ממגמת השוק
          </>
        ),
        body: `המחיר החדש (${newVal}₪) — עליה של ${Math.round((-diff / oldVal) * 100)}% מהמחיר הקודם. ייתכן שזה אות לעיכוב במהלך תחרותי או שינוי במיצוב.`,
      }
    }
  }

  if (change.change_type === 'new_plan') {
    return {
      kicker: `מסלול חדש · ${fmtHoursAgo(change.changed_at)}`,
      title: (
        <>
          {carrier} השיקה את <span style={{ color: 'var(--color-moca-hot)' }}>{name}</span> במחיר {newVal}₪
        </>
      ),
      body: `מסלול חדש שנכנס לשוק. ${carrier} מרחיבה את הסל התחרותי שלה.`,
    }
  }

  if (change.change_type === 'removed_plan') {
    return {
      kicker: `מסלול הוסר · ${fmtHoursAgo(change.changed_at)}`,
      title: <>{carrier} הסירה את <span style={{ color: 'var(--color-moca-muted)' }}>{name}</span></>,
      body: `המסלול לא מופיע יותר באתר ${carrier}.`,
    }
  }

  return null
}

function ComparisonCard({ plan, carrierId, label, accent, oldPrice }) {
  if (!plan) {
    return (
      <div
        style={{
          flex: 1,
          padding: 14,
          background: 'var(--color-moca-mist)',
          borderRadius: 10,
          border: '1px dashed var(--color-moca-border)',
          minWidth: 0,
        }}
      >
        <div style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>אין מסלול תואם להשוואה</div>
      </div>
    )
  }
  return (
    <div
      style={{
        flex: 1,
        padding: 14,
        background: accent ? 'rgba(74,124,63,0.08)' : 'var(--color-moca-mist)',
        borderRadius: 10,
        border: accent ? '1px solid rgba(74,124,63,0.3)' : '1px solid transparent',
        minWidth: 0,
      }}
    >
      <CarrierChip id={carrierId} size={24} showName bold />
      <div style={{ fontSize: 11, color: 'var(--color-moca-muted)', marginTop: 10 }}>
        {label || (plan.plan_name || '')}
      </div>
      <div className="tnum" style={{ display: 'flex', alignItems: 'baseline', gap: 6, direction: 'ltr', marginTop: 2 }}>
        {oldPrice != null && (
          <span style={{ fontSize: 13, color: 'var(--color-moca-muted)', textDecoration: 'line-through' }}>{oldPrice}₪</span>
        )}
        <span style={{ fontSize: 26, fontWeight: 800, color: accent ? 'var(--color-moca-down)' : 'var(--color-moca-dark)', letterSpacing: -0.5 }}>
          {plan.price}₪
        </span>
      </div>
      <div style={{ fontSize: 10.5, color: 'var(--color-moca-muted)', marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {plan.data_gb === null ? 'ללא הגבלה' : plan.data_gb >= 1 ? `${plan.data_gb}GB` : `${Math.round(plan.data_gb * 1024)}MB`}
        {plan.minutes ? ` · ${plan.minutes} דק׳` : ' · ללא הגבלה'}
      </div>
    </div>
  )
}

export default function EditorialHero({ leadChange, oursCarrier, onAnalyze, onPositioning, onWeeklyReport }) {
  const navigate = useNavigate()
  const headline = buildHeadline(leadChange?.change)

  if (!headline || !leadChange) {
    return (
      <div
        className="px-5 py-6 md:px-7 md:py-8"
        style={{
          background: 'linear-gradient(135deg, var(--color-moca-cream) 0%, var(--color-moca-sand) 100%)',
          borderBottom: '1px solid var(--color-moca-border)',
        }}
      >
        <div style={{ maxWidth: 720 }}>
          <div style={{ fontSize: 11, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 10 }}>
            ברוכים הבאים · MOCA
          </div>
          <h1 className="text-[22px] md:text-[30px]" style={{ fontFamily: 'var(--font-display)', fontWeight: 800, color: 'var(--color-moca-dark)', letterSpacing: -0.5, lineHeight: 1.2, margin: 0 }}>
            אין שינויים משמעותיים ב-24 שעות האחרונות
          </h1>
          <p style={{ fontSize: 14, color: 'var(--color-moca-sub)', lineHeight: 1.65, marginTop: 12, maxWidth: 520 }}>
            השוק שקט. כשמתחרה משנה משהו משמעותי — מחיר, מסלול חדש, הוצאה — תראה זאת כאן בראש העמוד.
          </p>
        </div>
      </div>
    )
  }

  const competitor = leadChange.competitorPlan
  const ours = leadChange.oursPlan
  const oldPriceForCompetitor = leadChange.change.change_type === 'price_change' ? Number(leadChange.change.old_val) : null

  return (
    <div
      className="px-5 py-6 md:px-7 md:py-8"
      style={{
        background: 'linear-gradient(135deg, var(--color-moca-cream) 0%, var(--color-moca-sand) 100%)',
        borderBottom: '1px solid var(--color-moca-border)',
      }}
    >
      <div className="grid grid-cols-1 md:[grid-template-columns:1fr_min(380px,40%)] gap-6 md:gap-7 items-stretch md:items-center max-w-[1320px] mx-auto">
        {/* Story */}
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, color: 'var(--color-moca-bolt)', fontWeight: 800, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 10 }}>
            ◆ {headline.kicker}
          </div>
          <h1
            className="text-[22px] md:text-[32px]"
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 800,
              color: 'var(--color-moca-dark)',
              letterSpacing: -0.6,
              lineHeight: 1.2,
              margin: 0,
              marginBottom: 14,
              textWrap: 'pretty',
            }}
          >
            {headline.title}
          </h1>
          <p
            style={{
              fontSize: 14,
              color: 'var(--color-moca-sub)',
              lineHeight: 1.65,
              marginBottom: 18,
              maxWidth: 560,
              textWrap: 'pretty',
            }}
          >
            {headline.body}
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={() => onAnalyze ? onAnalyze() : navigate(`/plans?carrier=${leadChange.change.carrier}`)}
              style={{
                padding: '10px 18px',
                borderRadius: 10,
                background: 'var(--color-moca-bolt)',
                color: '#fff',
                border: 'none',
                fontWeight: 700,
                fontSize: 13,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              נתח השוואה
            </button>
            <button
              onClick={() => onPositioning ? onPositioning() : navigate('/positioning')}
              style={{
                padding: '10px 18px',
                borderRadius: 10,
                background: 'rgba(255,255,255,0.7)',
                color: 'var(--color-moca-bolt)',
                border: '1px solid var(--color-moca-border)',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              מפת מיצוב
            </button>
            <button
              onClick={() => onWeeklyReport ? onWeeklyReport() : navigate('/executive-summary')}
              style={{
                padding: '10px 18px',
                borderRadius: 10,
                background: 'rgba(255,255,255,0.7)',
                color: 'var(--color-moca-bolt)',
                border: '1px solid var(--color-moca-border)',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              דוח שבועי
            </button>
          </div>
        </div>

        {/* Comparison panel */}
        <div
          style={{
            background: 'var(--color-moca-white, #fff)',
            borderRadius: 14,
            padding: 18,
            boxShadow: '0 4px 20px rgba(60,40,20,0.08)',
            minWidth: 0,
          }}
        >
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 800,
              color: 'var(--color-moca-muted)',
              letterSpacing: 0.6,
              textTransform: 'uppercase',
              marginBottom: 14,
            }}
          >
            ההשוואה המיידית
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>
            <ComparisonCard
              plan={ours}
              carrierId={oursCarrier}
              label={ours?.plan_name || 'אין מסלול שלך'}
            />
            <div style={{ display: 'flex', alignItems: 'center', color: 'var(--color-moca-muted)', fontSize: 16, fontWeight: 600 }}>vs</div>
            <ComparisonCard
              plan={competitor}
              carrierId={leadChange.change.carrier}
              label={competitor?.plan_name || leadChange.change.plan_name}
              accent
              oldPrice={oldPriceForCompetitor}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
