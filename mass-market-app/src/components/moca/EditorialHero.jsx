import { useNavigate } from 'react-router-dom'
import CarrierChip from './CarrierChip'
import { getCarrierName } from './carrierMeta'
import { useLang } from '../../hooks/useLanguage'

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

function fmtHoursAgo(iso, tt) {
  if (!iso) return ''
  const ms = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(ms / (60 * 60 * 1000))
  if (hours < 1) return tt('הרגע', 'just now')
  if (hours === 1) return tt('לפני שעה', '1 hour ago')
  if (hours < 24) return tt(`לפני ${hours} שעות`, `${hours} hours ago`)
  const days = Math.floor(hours / 24)
  return days === 1 ? tt('אתמול', 'yesterday') : tt(`לפני ${days} ימים`, `${days} days ago`)
}

function buildHeadline(change, tt) {
  if (!change) return null
  const carrier = getCarrierName(change.carrier)
  const name = change.plan_name || ''
  const oldVal = Number(change.old_val)
  const newVal = Number(change.new_val)

  if (change.change_type === 'price_change' && Number.isFinite(oldVal) && Number.isFinite(newVal)) {
    const diff = oldVal - newVal
    if (diff > 0) {
      return {
        kicker: `${tt('שינוי משמעותי בשוק', 'Significant market move')} · ${fmtHoursAgo(change.changed_at, tt)}`,
        title: (
          <>
            {carrier} {tt('חתכה את', 'cut')} <span style={{ color: 'var(--color-moca-down)', textDecoration: 'underline', textDecorationColor: 'var(--color-moca-down)', textUnderlineOffset: 4 }}>{name} {tt('ב-', 'by ')}{diff}₪</span>
          </>
        ),
        body: `${tt('המחיר החדש', 'The new price')} (${newVal}₪) ${tt('ירידה של', 'a drop of')} ${Math.round((diff / oldVal) * 100)}% ${tt('מהמחיר הקודם', 'from the previous price')}. ${carrier} ${tt('מציבה לחץ תחרותי על מסלולים בקטגוריה דומה', 'is putting competitive pressure on plans in a similar category')}.`,
      }
    }
    if (diff < 0) {
      return {
        kicker: `${tt('התייקרות', 'Price hike')} · ${fmtHoursAgo(change.changed_at, tt)}`,
        title: (
          <>
            {carrier} {tt('העלתה את', 'raised')} <span style={{ color: 'var(--color-moca-up)' }}>{name} {tt('ב-', 'by ')}{-diff}₪</span> — {tt('הפוך ממגמת השוק', 'against the market trend')}
          </>
        ),
        body: `${tt('המחיר החדש', 'The new price')} (${newVal}₪) — ${tt('עליה של', 'an increase of')} ${Math.round((-diff / oldVal) * 100)}% ${tt('מהמחיר הקודם', 'from the previous price')}. ${tt('ייתכן שזה אות לעיכוב במהלך תחרותי או שינוי במיצוב', 'This may signal a pause in a competitive move or a repositioning')}.`,
      }
    }
  }

  if (change.change_type === 'new_plan') {
    return {
      kicker: `${tt('מסלול חדש', 'New plan')} · ${fmtHoursAgo(change.changed_at, tt)}`,
      title: (
        <>
          {carrier} {tt('השיקה את', 'launched')} <span style={{ color: 'var(--color-moca-hot)' }}>{name}</span> {tt('במחיר', 'at')} {newVal}₪
        </>
      ),
      body: `${tt('מסלול חדש שנכנס לשוק', 'A new plan has entered the market')}. ${carrier} ${tt('מרחיבה את הסל התחרותי שלה', 'is expanding its competitive lineup')}.`,
    }
  }

  if (change.change_type === 'removed_plan') {
    return {
      kicker: `${tt('מסלול הוסר', 'Plan removed')} · ${fmtHoursAgo(change.changed_at, tt)}`,
      title: <>{carrier} {tt('הסירה את', 'removed')} <span style={{ color: 'var(--color-moca-muted)' }}>{name}</span></>,
      body: `${tt('המסלול לא מופיע יותר באתר', 'The plan no longer appears on the site of')} ${carrier}.`,
    }
  }

  return null
}

function ComparisonCard({ plan, carrierId, label, accent, oldPrice }) {
  const { tt } = useLang()
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
        <div style={{ fontSize: 11, color: 'var(--color-moca-muted)' }}>{tt('אין מסלול תואם להשוואה', 'No matching plan to compare')}</div>
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
        {plan.data_gb === null ? tt('ללא הגבלה', 'Unlimited') : plan.data_gb >= 1 ? `${Number(plan.data_gb).toLocaleString('en-US')}GB` : `${Math.round(plan.data_gb * 1024)}MB`}
        {plan.minutes ? ` · ${Number(plan.minutes).toLocaleString('en-US')} ${tt('דק׳', 'min')}` : ` · ${tt('ללא הגבלה', 'Unlimited')}`}
      </div>
    </div>
  )
}

export default function EditorialHero({ leadChange, oursCarrier, onAnalyze, onPositioning, onWeeklyReport }) {
  const { tt } = useLang()
  const navigate = useNavigate()
  const headline = buildHeadline(leadChange?.change, tt)

  if (!headline || !leadChange) {
    return (
      <div
        className="py-6 md:py-8"
        style={{
          background: 'linear-gradient(135deg, var(--color-moca-cream) 0%, var(--color-moca-sand) 100%)',
          borderBottom: '1px solid var(--color-moca-border)',
        }}
      >
        <div className="max-w-[1320px] mx-auto px-6">
          <div style={{ maxWidth: 720 }}>
            <div style={{ fontSize: 11, color: 'var(--color-moca-muted)', fontWeight: 800, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 10 }}>
              {tt('ברוכים הבאים · MOCA', 'Welcome · MOCA')}
            </div>
            <h1 className="text-[22px] md:text-[30px]" style={{ fontFamily: 'var(--font-display)', fontWeight: 800, color: 'var(--color-moca-dark)', letterSpacing: -0.5, lineHeight: 1.2, margin: 0 }}>
              {tt('אין שינויים משמעותיים ב-24 שעות האחרונות', 'No significant changes in the last 24 hours')}
            </h1>
            <p style={{ fontSize: 14, color: 'var(--color-moca-sub)', lineHeight: 1.65, marginTop: 12, maxWidth: 520 }}>
              {tt('השוק שקט. כשמתחרה משנה משהו משמעותי — מחיר, מסלול חדש, הוצאה — תראה זאת כאן בראש העמוד.', 'The market is quiet. When a competitor makes a significant move — a price, a new plan, a removal — you will see it here at the top of the page.')}
            </p>
          </div>
        </div>
      </div>
    )
  }

  const competitor = leadChange.competitorPlan
  const ours = leadChange.oursPlan
  const oldPriceForCompetitor = leadChange.change.change_type === 'price_change' ? Number(leadChange.change.old_val) : null

  return (
    <div
      className="py-6 md:py-8"
      style={{
        background: 'linear-gradient(135deg, var(--color-moca-cream) 0%, var(--color-moca-sand) 100%)',
        borderBottom: '1px solid var(--color-moca-border)',
      }}
    >
      <div className="max-w-[1320px] mx-auto px-6 grid grid-cols-1 md:[grid-template-columns:1fr_min(380px,40%)] gap-6 md:gap-7 items-stretch md:items-center">
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
              {tt('נתח השוואה', 'Analyze comparison')}
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
              {tt('מפת מיצוב', 'Positioning map')}
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
              {tt('דוח שבועי', 'Weekly report')}
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
            {tt('ההשוואה המיידית', 'Head-to-head comparison')}
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>
            <ComparisonCard
              plan={ours}
              carrierId={oursCarrier}
              label={ours?.plan_name || tt('אין מסלול שלך', 'No plan of yours')}
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
