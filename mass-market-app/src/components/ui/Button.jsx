export default function Button({ children, variant = 'primary', size = 'md', className = '', ...props }) {
  const base = 'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed hover-press'
  const variants = {
    primary:   'bg-moca-bolt text-white hover:bg-moca-dark focus:ring-moca-bolt',
    secondary: 'bg-moca-cream text-moca-text hover:bg-moca-sand focus:ring-moca-bolt border border-moca-border',
    danger:    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
    ghost:     'text-moca-bolt hover:bg-moca-cream focus:ring-moca-bolt',
  }
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  }
  return <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...props}>{children}</button>
}
