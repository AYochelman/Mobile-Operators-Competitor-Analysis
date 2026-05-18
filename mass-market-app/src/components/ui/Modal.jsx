import { useEffect } from 'react'
import { createPortal } from 'react-dom'

export default function Modal({ open, onClose, title, children, maxWidth = 'max-w-lg' }) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-2 md:p-4 animate-fade-in" onClick={onClose}>
      <div className="fixed inset-0 bg-black/40" />
      <div className={`relative bg-white rounded-xl shadow-xl ${maxWidth} w-full max-h-[92vh] md:max-h-[80vh] overflow-y-auto p-4 md:p-6 animate-fade-in-up`} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4 gap-3">
          <h3 className="text-base md:text-lg font-bold text-gray-900 min-w-0 truncate">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none flex-shrink-0">&times;</button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  )
}
