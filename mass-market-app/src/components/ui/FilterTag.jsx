export default function FilterTag({ label, active, onClick, count }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
        ${active
          ? 'bg-gray-900 text-white'
          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
        }`}
    >
      {label}
    </button>
  )
}
