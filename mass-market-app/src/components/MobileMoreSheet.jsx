import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

export default function MobileMoreSheet({ open, onClose, sections, title = 'תפריט' }) {
  const location = useLocation()

  // Close on route change — onClose intentionally excluded to avoid effect re-run on every render
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (open) onClose() }, [location.pathname, location.search])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    function onKey(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      <div
        className="md:hidden fixed inset-0 bg-black/40 z-50"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-white rounded-t-2xl shadow-2xl max-h-[80vh] overflow-y-auto"
      >
        <div className="sticky top-0 bg-white border-b border-moca-border/60 px-4 py-3 flex items-center justify-between">
          <span className="text-sm font-semibold text-moca-text">{title}</span>
          <button
            onClick={onClose}
            className="text-moca-muted hover:text-moca-text p-1"
            aria-label="סגור"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="px-2 py-2 pb-6">
          {(() => {
            const visibleSections = sections.filter(s => s.items.length > 0)
            const showSectionTitles = visibleSections.length > 1
            return visibleSections.map(section => (
              <div key={section.title} className="mb-2">
                {showSectionTitles && (
                  <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-moca-sub">
                    {section.title}
                  </div>
                )}
                <div className="space-y-0.5">
                  {section.items}
                </div>
              </div>
            ))
          })()}
        </div>
      </div>
    </>
  )
}
