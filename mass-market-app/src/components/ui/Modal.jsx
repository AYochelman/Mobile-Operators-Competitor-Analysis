import { useEffect, useRef, useId } from 'react'
import { createPortal } from 'react-dom'

export default function Modal({ open, onClose, title, children, maxWidth = 'max-w-lg' }) {
  const titleId = useId()
  const dialogRef = useRef(null)
  const previousFocusRef = useRef(null)

  // Lock body scroll while open + remember the element to restore focus to.
  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
      // Restore focus to whatever opened the modal so keyboard users don't
      // get stranded on document.body.
      if (previousFocusRef.current && typeof previousFocusRef.current.focus === 'function') {
        previousFocusRef.current.focus()
      }
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  // ESC closes; Tab is trapped inside the dialog so keyboard users can't tab
  // out into the page behind the backdrop.
  useEffect(() => {
    if (!open) return
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose?.()
        return
      }
      if (e.key === 'Tab' && dialogRef.current) {
        const focusables = dialogRef.current.querySelectorAll(
          'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        if (focusables.length === 0) return
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    // Move focus into the dialog after mount so the close button (or first
    // focusable child) is reachable immediately.
    setTimeout(() => {
      const focusable = dialogRef.current?.querySelector(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
      focusable?.focus?.()
    }, 0)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 animate-fade-in" onClick={onClose}>
      <div className="fixed inset-0 bg-black/40" aria-hidden="true" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`relative bg-white rounded-xl shadow-xl ${maxWidth} w-full max-h-[80vh] overflow-y-auto p-6 animate-fade-in-up`}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 id={titleId} className="text-lg font-bold text-gray-900">{title}</h3>
          <button
            onClick={onClose}
            aria-label="סגור"
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          >&times;</button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  )
}
