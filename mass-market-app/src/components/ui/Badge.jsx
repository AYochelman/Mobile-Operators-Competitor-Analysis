export default function Badge({ children, color = 'gray', className = '' }) {
  const colors = {
    gray: 'bg-gray-100 text-gray-700',
    blue: 'bg-blue-100 text-blue-700',
    green: 'bg-green-100 text-green-700',
    orange: 'bg-orange-100 text-orange-700',
    red: 'bg-red-100 text-red-700',
    purple: 'bg-purple-100 text-purple-700',
    pink: 'bg-pink-100 text-pink-700',
    teal: 'bg-teal-100 text-teal-700',
    amber: 'bg-amber-100 text-amber-700',
  }
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors[color] || colors.gray} ${className}`}>{children}</span>
}
