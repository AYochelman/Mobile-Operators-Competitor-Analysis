export default function Badge({ children, color = 'gray', className = '' }) {
  const colors = {
    gray:   'bg-moca-cream text-moca-bolt',
    blue:   'bg-blue-50 text-blue-600',
    green:  'bg-emerald-50 text-emerald-600',
    orange: 'bg-amber-50 text-amber-600',
    red:    'bg-red-50 text-red-600',
    purple: 'bg-violet-50 text-violet-600',
    pink:   'bg-pink-50 text-pink-600',
    teal:   'bg-teal-50 text-teal-600',
    amber:  'bg-amber-50 text-amber-600',
  }
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold tracking-wide ${colors[color] || colors.gray} ${className}`}>
      {children}
    </span>
  )
}
