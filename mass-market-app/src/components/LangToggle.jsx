import { useLang } from '../hooks/useLanguage'

/**
 * Hebrew ⇄ English UI language toggle pill.
 *
 * Shows the language you can switch TO (like the B2C page): "EN" while the UI
 * is Hebrew, "עב" while it's English. Two visual variants:
 *   variant="chrome"  — bordered pill for the desktop topbar
 *   variant="ghost"   — lighter pill for the mobile header
 */
export default function LangToggle({ variant = 'chrome', className = '' }) {
  const { lang, toggle } = useLang()
  const nextLabel = lang === 'he' ? 'EN' : 'עב'
  const title = lang === 'he' ? 'Switch to English' : 'החלף לעברית'

  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontWeight: 700,
    borderRadius: 999,
    transition: 'background 120ms ease, color 120ms ease, border-color 120ms ease',
  }

  const chrome = {
    ...base,
    height: 34,
    padding: '0 12px',
    fontSize: 12.5,
    background: 'var(--color-moca-white, #fff)',
    border: '1px solid var(--color-moca-border)',
    color: 'var(--color-moca-sub)',
  }

  const ghost = {
    ...base,
    height: 28,
    padding: '0 10px',
    fontSize: 12,
    background: 'var(--color-moca-cream)',
    border: '1px solid var(--color-moca-border)',
    color: 'var(--color-moca-bolt)',
  }

  const style = variant === 'ghost' ? ghost : chrome

  return (
    <button
      type="button"
      onClick={toggle}
      title={title}
      aria-label={title}
      className={className}
      style={style}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--color-moca-bolt)'
        e.currentTarget.style.color = 'var(--color-moca-bolt)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--color-moca-border)'
        e.currentTarget.style.color = variant === 'ghost' ? 'var(--color-moca-bolt)' : 'var(--color-moca-sub)'
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
      {nextLabel}
    </button>
  )
}
