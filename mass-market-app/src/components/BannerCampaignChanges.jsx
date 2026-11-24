import { useLang } from '../hooks/useLanguage'
import { CarrierChip } from './moca'
import { campaignTypeLabel } from '../data/campaignTypes'

/**
 * "What changed on the banners" - the campaign switches banner_vision.py found
 * in the last 30 days, newest first. `data` is the /api/banner-insights payload
 * ({ latest, changes }); null while loading. Renders nothing until at least one
 * banner has been read, so a server that never ran the reader shows no empty box.
 */
function fmtDay(iso, lang) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(lang === 'he' ? 'he-IL' : 'en-GB', { day: 'numeric', month: 'short' })
}

export default function BannerCampaignChanges({ data }) {
  const { tt, lang } = useLang()
  if (!data || Object.keys(data.latest || {}).length === 0) return null
  const changes = (data.changes || []).slice(0, 8)
  const withPrice = (text, price) => [text, price].filter(Boolean).join(' · ')

  return (
    <section
      style={{
        background: '#fff', border: '1px solid var(--color-moca-border)', borderRadius: 14,
        boxShadow: 'var(--sh-card)', padding: 16, marginBottom: 24, textAlign: 'right',
      }}
    >
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: 'var(--color-moca-dark)' }}>
          {tt('מה השתנה בקמפיינים', 'What changed in the campaigns')}
        </h2>
        <span style={{ fontSize: 11.5, color: 'var(--color-moca-muted)' }}>
          {tt(`${data.days} הימים האחרונים · קריאה אוטומטית של הצילומים`, `Last ${data.days} days · automatic reading of the screenshots`)}
        </span>
      </header>
      {changes.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12.5, color: 'var(--color-moca-muted)' }}>
          {tt('לא זוהה קמפיין חדש בתקופה. לחיצה על באנר מציגה מה כתוב בו כרגע.', 'No new campaign was detected in the period. Click a banner to see what it says now.')}
        </p>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {changes.map((c) => (
            <li key={c.id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', borderTop: '1px solid var(--color-moca-cream)', paddingTop: 8 }}>
              <CarrierChip id={c.carrier} size={26} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 12, color: 'var(--color-moca-sub)' }}>
                  <b style={{ color: 'var(--color-moca-dark)' }}>{c.name}</b>
                  {c.kind === 'store' ? ` · ${tt('חנות', 'Store')}` : ''}
                  {' · '}{campaignTypeLabel(c.campaign_type, tt)}
                  {' · '}{fmtDay(c.first_seen_at, lang)}
                </div>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--color-moca-dark)', marginTop: 2 }}>
                  {withPrice(c.headline || c.offer, c.price_text) || tt('ללא הצעה מזוהה', 'No offer detected')}
                </div>
                {c.prev_headline && (
                  <div style={{ fontSize: 12, color: 'var(--color-moca-muted)', marginTop: 2 }}>
                    {tt('קודם', 'Before')}: {withPrice(c.prev_headline, c.prev_price_text)}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
