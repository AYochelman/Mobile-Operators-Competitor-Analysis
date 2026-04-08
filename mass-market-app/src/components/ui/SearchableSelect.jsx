import { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'

export default function SearchableSelect({ value, onChange, options, placeholder = 'בחר...', className = '' }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })
  const triggerRef = useRef(null)
  const dropdownRef = useRef(null)
  const inputRef = useRef(null)

  // Calculate position when opening
  const updatePosition = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      setPos({
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
      })
    }
  }, [])

  // Close on click outside
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (triggerRef.current?.contains(e.target)) return
      if (dropdownRef.current?.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Focus input + calc position when opened
  useEffect(() => {
    if (open) {
      updatePosition()
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open, updatePosition])

  // Update position on scroll/resize
  useEffect(() => {
    if (!open) return
    const onScroll = () => updatePosition()
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
  }, [open, updatePosition])

  const filtered = search
    ? options.filter(o => o.label.includes(search))
    : options

  const selectedLabel = value === 'all'
    ? placeholder
    : (options.find(o => o.value === value)?.label || value)

  const handleSelect = (val) => {
    onChange(val)
    setOpen(false)
    setSearch('')
  }

  return (
    <div ref={triggerRef} className={`relative ${className}`}>
      {/* Trigger button */}
      <button
        onClick={() => { setOpen(!open); setSearch('') }}
        className={`w-full border rounded-lg px-2 py-1 text-xs text-right flex items-center justify-between ${
          value !== 'all' ? 'border-moca-bolt bg-moca-mist' : 'border-gray-200 bg-white'
        }`}
      >
        <span className="truncate">{selectedLabel}</span>
        <span className="text-gray-400 text-[10px] mr-1">{open ? '▴' : '▾'}</span>
      </button>

      {/* Dropdown via Portal */}
      {open && createPortal(
        <div
          ref={dropdownRef}
          className="bg-white rounded-lg border border-gray-200 shadow-2xl max-h-[220px] overflow-hidden"
          style={{
            position: 'fixed',
            zIndex: 99999,
            top: pos.top,
            left: pos.left,
            width: pos.width,
          }}
        >
          {/* Search input */}
          <div className="p-1.5 border-b border-gray-100 sticky top-0 bg-white">
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="חפש..."
              className="w-full border border-gray-200 rounded px-2 py-1 text-xs outline-none focus:border-moca-bolt"
            />
          </div>

          {/* Options list */}
          <div className="overflow-y-auto max-h-[170px]">
            <button
              onClick={() => handleSelect('all')}
              className={`w-full text-right px-2.5 py-1.5 text-xs hover:bg-moca-cream transition-colors ${
                value === 'all' ? 'bg-moca-cream font-medium text-moca-text' : 'text-gray-600'
              }`}
            >
              {placeholder}
            </button>

            {filtered.map(o => (
              <button
                key={o.value}
                onClick={() => handleSelect(o.value)}
                className={`w-full text-right px-2.5 py-1.5 text-xs hover:bg-moca-cream transition-colors ${
                  value === o.value ? 'bg-moca-cream font-medium text-moca-text' : 'text-gray-600'
                }`}
              >
                {o.label}
              </button>
            ))}

            {filtered.length === 0 && (
              <p className="px-2.5 py-2 text-xs text-gray-400 text-center">לא נמצאו תוצאות</p>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
