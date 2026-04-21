import Modal from './ui/Modal'

const GlobeIcon = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg" style={{flexShrink:0}}>
    <circle cx="11" cy="11" r="9.5" stroke="#5c3317" strokeWidth="1.5"/>
    {/* horizontal lines */}
    <ellipse cx="11" cy="11" rx="9.5" ry="3.8" stroke="#5c3317" strokeWidth="1.25" fill="none"/>
    <line x1="1.5" y1="11" x2="20.5" y2="11" stroke="#5c3317" strokeWidth="1.25"/>
    {/* vertical meridian */}
    <ellipse cx="11" cy="11" rx="4" ry="9.5" stroke="#5c3317" strokeWidth="1.25" fill="none"/>
  </svg>
)

export default function CountryModal({ open, onClose, title, countries }) {
  if (!countries) return null
  return (
    <Modal open={open} onClose={onClose} title={<span className="flex items-center gap-2"><GlobeIcon />{title} — מדינות כלולות</span>} maxWidth="max-w-xl">
      <div className="flex flex-wrap gap-2">
        {countries.map(c => (
          <span key={c} className="px-2.5 py-1 bg-gray-100 text-gray-700 text-xs rounded-full border border-gray-200">
            {c}
          </span>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-4">{countries.length} מדינות</p>
    </Modal>
  )
}
