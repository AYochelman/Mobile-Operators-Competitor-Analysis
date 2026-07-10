import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useWatchlist } from '../../hooks/useWatchlist'
import { useLang } from '../../hooks/useLanguage'
import { resolveRouteMeta } from './routeMeta'
import ChangePasswordModal from '../ChangePasswordModal'
import LangToggle from '../LangToggle'

/**
 * Top bar (desktop only) per MOCA design handoff.
 * Shows page kicker + title, LIVE indicator, search button, time-machine
 * placeholder, alerts CTA, and the user menu.
 */

function LiveDot() {
  return (
    <span
      title="Live data"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 10,
        fontWeight: 800,
        color: 'var(--color-moca-down)',
        letterSpacing: 0.6,
        textTransform: 'uppercase',
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 7,
          height: 7,
          borderRadius: 999,
          background: 'var(--color-moca-down)',
          boxShadow: '0 0 0 3px rgba(74,124,63,0.18)',
          animation: 'gentlePulse 1.8s var(--ease-in-out) infinite',
        }}
      />
      LIVE
    </span>
  )
}

function IconButton({ title, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 34,
        height: 34,
        borderRadius: 10,
        background: 'transparent',
        border: '1px solid var(--color-moca-border)',
        color: 'var(--color-moca-sub)',
        cursor: 'pointer',
        transition: 'background 120ms ease, color 120ms ease, border-color 120ms ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--color-moca-mist)'
        e.currentTarget.style.color = 'var(--color-moca-bolt)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'var(--color-moca-sub)'
      }}
    >
      {children}
    </button>
  )
}

function ProfileMenu({ user, isAdmin, isSuperAdmin, signOut, workspace }) {
  const [open, setOpen] = useState(false)
  const [showChangePw, setShowChangePw] = useState(false)
  const { tt } = useLang()
  const navigate = useNavigate()
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onEsc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  const go = (path) => { setOpen(false); navigate(path) }
  const initial = (user?.email || '?')[0]?.toUpperCase()
  const itemCls = 'w-full text-start px-3 py-2 text-[12px] text-moca-text hover:bg-moca-cream rounded-md transition-colors flex items-center justify-between'
  const supportHref =
    'mailto:Helpdesk@mocaintel.com?subject=' +
    encodeURIComponent(tt('פנייה לתמיכה', 'Support request') + (workspace?.name ? ` – ${workspace.name}` : ''))

  return (
    <>
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        title={user?.email || tt('פרופיל', 'Profile')}
        aria-haspopup="menu"
        aria-expanded={open}
        style={{
          width: 34,
          height: 34,
          borderRadius: 999,
          background: 'var(--color-moca-cream)',
          color: 'var(--color-moca-bolt)',
          border: '1px solid var(--color-moca-border)',
          fontSize: 13,
          fontWeight: 700,
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {initial}
      </button>
      {open && (
        <div className="absolute top-full mt-1 min-w-[200px] bg-white rounded-xl shadow-popover border border-moca-border/40 p-1.5 z-50 animate-fade-in" style={{ insetInlineEnd: 0 }}>
          <button onClick={() => go('/preferences')} className={itemCls}>{tt('העדפות', 'Preferences')}</button>
          <button onClick={() => go('/alerts?tab=watchlist')} className={itemCls}>{tt('הגדרות התראות', 'Alert settings')}</button>
          <button onClick={() => { setOpen(false); setShowChangePw(true) }} className={itemCls}>{tt('שינוי סיסמה', 'Change password')}</button>
          {isAdmin && !isSuperAdmin && (
            <>
              <div className="h-px bg-moca-border/30 my-1" />
              <button onClick={() => go('/workspace/users')} className={itemCls}>{tt('הצוות', 'Team')}</button>
              <button onClick={() => go('/workspace/settings')} className={itemCls}>{tt('מיתוג Workspace', 'Workspace branding')}</button>
            </>
          )}
          {isAdmin && (
            <button onClick={() => go('/settings')} className={itemCls}>{tt('הגדרות מערכת', 'System settings')}</button>
          )}
          {isSuperAdmin && (
            <>
              <div className="h-px bg-moca-border/30 my-1" />
              <button onClick={() => go('/admin/workspaces')} className={itemCls}>Workspaces</button>
              <button onClick={() => go('/admin/audit')} className={itemCls}>{tt('יומן ביקורת', 'Audit log')}</button>
              <button onClick={() => go('/admin/hotels')} className={itemCls}>{tt('פורטלי אורחים', 'Guest portals')}</button>
              <div className="h-px bg-moca-border/30 my-1" />
              <div className="px-3 pt-1 pb-0.5 text-[10px] font-bold text-moca-muted uppercase tracking-wide">B2C</div>
              <button
                onClick={() => { setOpen(false); window.open('/esim-deals', '_blank', 'noopener') }}
                className={itemCls}
              >
                <span>{tt('עמוד eSIM (B2C)', 'eSIM page (B2C)')}</span>
                <span className="opacity-50">↗</span>
              </button>
              <button onClick={() => go('/admin/esim')} className={itemCls}>{tt('דשבורד eSIM (B2C)', 'eSIM dashboard (B2C)')}</button>
              <button onClick={() => go('/admin/deals')} className={itemCls}>{tt('סטטוס ספקים', 'Provider status')}</button>
              <button onClick={() => go('/usage')} className={itemCls}>{tt('שימוש ב-Claude', 'Claude usage')}</button>
            </>
          )}
          <div className="h-px bg-moca-border/30 my-1" />
          <a href={supportHref} onClick={() => setOpen(false)} className={itemCls}>{tt('פנייה לתמיכה', 'Contact support')}</a>
          <button onClick={() => { setOpen(false); signOut() }} className={`${itemCls} text-red-600 hover:bg-red-50`}>{tt('יציאה', 'Sign out')}</button>
        </div>
      )}
    </div>
      <ChangePasswordModal open={showChangePw} onClose={() => setShowChangePw(false)} />
    </>
  )
}

function openGlobalSearch() {
  window.dispatchEvent(new KeyboardEvent('keydown', {
    ctrlKey: true,
    code: 'KeyK',
    key: 'k',
    bubbles: true,
  }))
}

export default function Topbar({ onTimeMachine }) {
  const { user, isAdmin, isSuperAdmin, signOut, workspace } = useAuth()
  const { changesCount } = useWatchlist()
  const { lang, tt } = useLang()
  const location = useLocation()
  const meta = resolveRouteMeta(location.pathname, location.search, lang)

  return (
    <header
      className="hidden md:flex"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 25,
        background: 'rgba(249, 244, 238, 0.85)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        borderBottom: '1px solid var(--color-moca-border)',
        padding: '12px 28px',
        alignItems: 'center',
        gap: 14,
        minHeight: 60,
      }}
    >
      {/* Title block */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {meta.kicker && (
          <div
            style={{
              fontSize: 9.5,
              color: 'var(--color-moca-muted)',
              fontWeight: 800,
              letterSpacing: 0.6,
              textTransform: 'uppercase',
              marginBottom: 2,
            }}
          >
            {meta.kicker}
          </div>
        )}
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 20,
            fontWeight: 800,
            color: 'var(--color-moca-dark)',
            letterSpacing: -0.4,
            margin: 0,
            lineHeight: 1.2,
            display: 'flex',
            alignItems: 'baseline',
            gap: 12,
          }}
        >
          {meta.title}
          <LiveDot />
        </h1>
      </div>

      {/* Action cluster */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {/* Search */}
        <button
          type="button"
          onClick={openGlobalSearch}
          title={tt('חיפוש מתקדם · Ctrl+K', 'Advanced search · Ctrl+K')}
          aria-label={tt('חיפוש מתקדם', 'Advanced search')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 12px',
            borderRadius: 10,
            background: 'var(--color-moca-white, #fff)',
            border: '1px solid var(--color-moca-border)',
            color: 'var(--color-moca-sub)',
            fontSize: 12.5,
            cursor: 'pointer',
            fontFamily: 'inherit',
            transition: 'border-color 120ms ease',
            minWidth: 200,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--color-moca-bolt)' }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-moca-border)' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <span style={{ flex: 1, textAlign: 'start' }}>{tt('חיפוש…', 'Search…')}</span>
          <kbd style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, background: 'var(--color-moca-cream)', color: 'var(--color-moca-muted)', fontFamily: 'inherit' }}>Ctrl K</kbd>
        </button>

        {/* UI language toggle (Hebrew ⇄ English) */}
        <LangToggle variant="chrome" />

        {/* Time Machine — placeholder for now (modal lands in a later phase) */}
        <IconButton title={tt('מכונת זמן · Time Machine', 'Time Machine')} onClick={onTimeMachine}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
            <path d="M3.5 8.5 6 6" />
          </svg>
        </IconButton>

        {/* Watchlist alerts */}
        <NavLink
          to="/alerts?tab=watchlist"
          title={tt('התראות מעקב', 'Watchlist alerts')}
          aria-label={tt('התראות מעקב', 'Watchlist alerts')}
          style={{
            position: 'relative',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 34,
            height: 34,
            borderRadius: 10,
            background: 'transparent',
            border: '1px solid var(--color-moca-border)',
            color: 'var(--color-moca-sub)',
            textDecoration: 'none',
            transition: 'background 120ms ease, color 120ms ease',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          {changesCount > 0 && (
            <span
              className="tnum"
              style={{
                position: 'absolute',
                top: -4,
                left: -4,
                minWidth: 16,
                height: 16,
                background: 'var(--color-moca-up)',
                color: '#fff',
                fontSize: 9,
                fontWeight: 800,
                borderRadius: 999,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0 4px',
                lineHeight: 1,
                boxShadow: '0 0 0 2px var(--color-moca-bg)',
              }}
            >
              {changesCount > 9 ? '9+' : changesCount}
            </span>
          )}
        </NavLink>

        {/* User menu */}
        <ProfileMenu user={user} isAdmin={isAdmin} isSuperAdmin={isSuperAdmin} signOut={signOut} workspace={workspace} />
      </div>
    </header>
  )
}
