export default function Button({ children, variant = 'primary', size = 'md', className = '', ...props }) {
  const base = 'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed hover-press'
  const variants = {
    primary:   'bg-[#5c3317] text-white hover:bg-[#4a2a13] focus:ring-[#5c3317]',
    secondary: 'bg-[#f5ede0] text-[#3b1f0d] hover:bg-[#e8d5bc] focus:ring-[#5c3317] border border-[#e0cdb5]',
    danger:    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
    ghost:     'text-[#5c3317] hover:bg-[#f5ede0] focus:ring-[#5c3317]',
  }
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  }
  return <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...props}>{children}</button>
}
