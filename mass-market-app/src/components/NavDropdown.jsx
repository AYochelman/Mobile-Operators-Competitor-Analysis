import { useState, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

export default function NavDropdown({ label, isActive = false, children }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const location = useLocation()

  // Close on route change
  useEffect(() => { setOpen(false) }, [location.pathname, location.search])

  // Close on outside click + Escape
  useEffect(() => {
    if (!open) return
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    function onKey(e) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`px-3 py-1.5 text-[13px] font-medium transition-all duration-150 inline-flex items-center gap-1 relative ${
          isActive
            ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-3 after:h-[1.5px] after:bg-moca-bolt after:rounded-full'
            : 'text-moca-muted hover:text-moca-bolt'
        }`}
      >
        {label}
        <svg
          width="10" height="10" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round"
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute top-full mt-1 right-0 min-w-[180px] bg-white border border-moca-border/60 rounded-lg shadow-lg py-1 z-50"
        >
          {children}
        </div>
      )}
    </div>
  )
}
