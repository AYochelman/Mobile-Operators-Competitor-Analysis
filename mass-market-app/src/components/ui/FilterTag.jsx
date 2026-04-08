export default function FilterTag({ label, active, onClick, count }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
        ${active
          ? 'bg-moca-bolt text-moca-cream'
          : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
        }`}
    >
      {label}
    </button>
  )
}
