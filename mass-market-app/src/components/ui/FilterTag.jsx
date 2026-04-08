export default function FilterTag({ label, active, onClick, count }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
        ${active
          ? 'bg-[#5c3317] text-[#f5ede0]'
          : 'text-[#8a6a4a] hover:text-[#3b1f0d] hover:bg-[#f5ede0]'
        }`}
    >
      {label}
    </button>
  )
}
