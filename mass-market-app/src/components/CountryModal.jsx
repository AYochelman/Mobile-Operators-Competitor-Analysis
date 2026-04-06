import Modal from './ui/Modal'

export default function CountryModal({ open, onClose, title, countries }) {
  if (!countries) return null
  return (
    <Modal open={open} onClose={onClose} title={`🌍 ${title} — מדינות כלולות`} maxWidth="max-w-xl">
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
