import { useState, useRef, useEffect } from 'react'

export default function SearchableSelect({ value, onChange, options, placeholder = 'בחר...', className = '' }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef(null)
  const inputRef = useRef(null)

  // Close on click outside
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Focus search input when opened
  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus()
  }, [open])

  const filtered = search
    ? options.filter(o => o.label.includes(search))
    : options

  const selectedLabel = value === 'all'
    ? placeholder
    : (options.find(o => o.value === value)?.label || value)

  return (
    <div ref={ref} className={`relative ${className}`}>
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

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 top-full mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg max-h-[250px] overflow-hidden animate-slide-down">
          {/* Search input */}
          <div className="p-1.5 border-b border-gray-100">
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
          <div className="overflow-y-auto max-h-[200px]">
            {/* "All" option */}
            <button
              onClick={() => { onChange('all'); setOpen(false); setSearch('') }}
              className={`w-full text-right px-2.5 py-1.5 text-xs hover:bg-moca-cream transition-colors ${
                value === 'all' ? 'bg-moca-cream font-medium text-moca-text' : 'text-gray-600'
              }`}
            >
              {placeholder}
            </button>

            {filtered.map(o => (
              <button
                key={o.value}
                onClick={() => { onChange(o.value); setOpen(false); setSearch('') }}
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
        </div>
      )}
    </div>
  )
}
