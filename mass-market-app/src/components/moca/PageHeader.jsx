/**
 * Standard page top section per MOCA design handoff.
 *
 * <PageHeader
 *    kicker="ניטור"
 *    title="דשבורד"
 *    subtitle="תמונת מצב יומית של 8 המתחרים"
 *    actions={<button>...</button>}
 *    tabs={[{ id: 'all', label: 'הכל', count: 12 }, ...]}
 *    activeTab="all"
 *    onTabChange={setActiveTab}
 * />
 */
export default function PageHeader({
  kicker,
  title,
  subtitle,
  actions,
  tabs,
  activeTab,
  onTabChange,
}) {
  return (
    <div className="px-8 pt-6 pb-0 max-w-[1320px] mx-auto">
      <div
        className="flex items-start gap-4"
        style={{ marginBottom: subtitle ? 14 : 10 }}
      >
        <div className="flex-1 min-w-0">
          {kicker && (
            <div
              style={{
                fontSize: 10.5,
                color: 'var(--color-moca-muted)',
                fontWeight: 800,
                letterSpacing: 0.6,
                textTransform: 'uppercase',
                marginBottom: 6,
              }}
            >
              {kicker}
            </div>
          )}
          {title && (
            <h1
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 26,
                fontWeight: 800,
                color: 'var(--color-moca-dark)',
                letterSpacing: -0.5,
                margin: 0,
                lineHeight: 1.15,
              }}
            >
              {title}
            </h1>
          )}
          {subtitle && (
            <p
              style={{
                fontSize: 13,
                color: 'var(--color-moca-sub)',
                margin: '6px 0 0',
                lineHeight: 1.5,
                maxWidth: 720,
                textWrap: 'pretty',
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex gap-2 flex-shrink-0 items-center">
            {actions}
          </div>
        )}
      </div>

      {tabs && (
        <div
          className="flex gap-0.5 mt-1"
          style={{ borderBottom: '1px solid var(--color-moca-border)' }}
        >
          {tabs.map((t) => {
            const active = activeTab === t.id
            return (
              <button
                key={t.id}
                onClick={() => onTabChange && onTabChange(t.id)}
                style={{
                  padding: '10px 14px',
                  border: 'none',
                  background: 'transparent',
                  color: active ? 'var(--color-moca-bolt)' : 'var(--color-moca-sub)',
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  borderBottom: `2px solid ${active ? 'var(--color-moca-bolt)' : 'transparent'}`,
                  marginBottom: -1,
                  transition: 'all 120ms ease',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                {t.label}
                {t.count != null && (
                  <span
                    className="tnum"
                    style={{
                      fontSize: 10.5,
                      padding: '1px 6px',
                      borderRadius: 999,
                      background: active
                        ? 'rgba(92, 51, 23, 0.09)'
                        : 'var(--color-moca-cream)',
                      color: active ? 'var(--color-moca-bolt)' : 'var(--color-moca-muted)',
                      fontWeight: 700,
                    }}
                  >
                    {t.count}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
