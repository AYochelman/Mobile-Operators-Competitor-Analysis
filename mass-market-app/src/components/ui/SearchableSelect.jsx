import { useState, useRef, useEffect, useCallback, useMemo, useId } from 'react'
import { createPortal } from 'react-dom'

export default function SearchableSelect({ value, onChange, options, placeholder = 'בחר...', className = '', size = 'sm' }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })
  const [activeIdx, setActiveIdx] = useState(-1)
  const triggerRef = useRef(null)
  // Separate ref for the actual <button> trigger so we can return focus to
  // it when the dropdown closes (triggerRef is on the wrapping div for
  // positioning getBoundingClientRect — divs aren't focusable by default).
  const triggerButtonRef = useRef(null)
  const dropdownRef = useRef(null)
  const inputRef = useRef(null)
  const listboxId = useId()
  const optionIdPrefix = useId()

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
      setActiveIdx(-1)
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

  const filtered = useMemo(
    () => (search ? options.filter(o => o.label.includes(search)) : options),
    [search, options]
  )

  // Items as appear in the listbox: synthetic "all" entry then filtered options.
  const items = useMemo(
    () => [{ value: 'all', label: placeholder }, ...filtered],
    [filtered, placeholder]
  )

  // Reset highlight when the filtered list changes (typing in search).
  useEffect(() => {
    setActiveIdx(items.length > 0 ? 0 : -1)
  }, [search, items.length])

  const selectedLabel = value === 'all'
    ? placeholder
    : (options.find(o => o.value === value)?.label || value)

  const handleSelect = (val) => {
    onChange(val)
    setOpen(false)
    setSearch('')
    // Return focus to the trigger so keyboard users continue from a known
    // anchor instead of the document body.
    setTimeout(() => triggerButtonRef.current?.focus(), 0)
  }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx(i => (items.length === 0 ? -1 : (i + 1) % items.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx(i => (items.length === 0 ? -1 : (i - 1 + items.length) % items.length))
    } else if (e.key === 'Enter') {
      if (activeIdx >= 0 && activeIdx < items.length) {
        e.preventDefault()
        handleSelect(items[activeIdx].value)
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(false)
      setSearch('')
      setTimeout(() => triggerButtonRef.current?.focus(), 0)
    } else if (e.key === 'Home') {
      e.preventDefault()
      setActiveIdx(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      setActiveIdx(items.length - 1)
    }
  }

  const onTriggerKeyDown = (e) => {
    // Open on ArrowDown / Enter / Space when closed, like a native combobox.
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault()
      setOpen(true)
      setSearch('')
    }
  }

  const activeOptionId = activeIdx >= 0 ? `${optionIdPrefix}-${activeIdx}` : undefined

  return (
    <div ref={triggerRef} className={`relative ${className}`}>
      {/* Trigger button */}
      <button
        ref={triggerButtonRef}
        onClick={() => { setOpen(!open); setSearch('') }}
        onKeyDown={onTriggerKeyDown}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        className={`w-full border rounded-lg text-right flex items-center justify-between ${
          size === 'md' ? 'px-3 py-2 text-sm' : 'px-2 py-1 text-xs'
        } ${
          value !== 'all' ? 'border-moca-bolt bg-moca-mist' : 'border-gray-200 bg-white'
        }`}
      >
        <span className="truncate">{selectedLabel}</span>
        <span className={`text-gray-400 mr-1 ${size === 'md' ? 'text-sm' : 'text-[10px]'}`} aria-hidden="true">{open ? '▴' : '▾'}</span>
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
              onKeyDown={onKeyDown}
              placeholder="חפש..."
              aria-controls={listboxId}
              aria-activedescendant={activeOptionId}
              aria-autocomplete="list"
              className="w-full border border-gray-200 rounded px-2 py-1 text-xs outline-none focus:border-moca-bolt"
            />
          </div>

          {/* Options list */}
          <div
            id={listboxId}
            role="listbox"
            className="overflow-y-auto max-h-[170px]"
          >
            {items.map((o, idx) => {
              const isAll = o.value === 'all'
              const isSelected = isAll ? value === 'all' : value === o.value
              const isActive = idx === activeIdx
              const optId = `${optionIdPrefix}-${idx}`
              return (
                <button
                  key={isAll ? '__all__' : o.value}
                  id={optId}
                  role="option"
                  aria-selected={isSelected}
                  type="button"
                  onClick={() => handleSelect(o.value)}
                  onMouseEnter={() => setActiveIdx(idx)}
                  className={`w-full text-right px-2.5 py-1.5 text-xs transition-colors ${
                    isActive
                      ? 'bg-moca-cream'
                      : isSelected
                        ? 'bg-moca-cream font-medium text-moca-text'
                        : 'text-gray-600 hover:bg-moca-cream'
                  }`}
                >
                  {o.label}
                </button>
              )
            })}

            {filtered.length === 0 && (
              <p className="px-2.5 py-2 text-xs text-gray-400 text-center" role="status">לא נמצאו תוצאות</p>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
