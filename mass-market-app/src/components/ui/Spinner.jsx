export default function Spinner({ size = 'md', className = '' }) {
  const sizes = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' }
  return <div className={`animate-spin ${sizes[size]} border-4 border-blue-500 border-t-transparent rounded-full ${className}`} />
}
