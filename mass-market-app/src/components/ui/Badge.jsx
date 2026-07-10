// Badge palette warmed into the MOCA mocha-latte family. Each role keeps a
// distinguishable hue (so eSIM/roaming/priority still read apart), but the tints
// sit on the warm cream surfaces instead of the cold default Tailwind blues/
// violets. Pill shape (rounded-full) matches the rest of the design system.
export default function Badge({ children, color = 'gray', className = '' }) {
  const colors = {
    gray:   'bg-moca-cream text-moca-bolt',
    blue:   'bg-[#e8eef2] text-[#3a5f77]',   // roaming / חו״ל — muted warm blue
    green:  'bg-[#e7f0e2] text-[#3f6c34]',   // eSIM — moca-down green
    orange: 'bg-[#f6e3d3] text-[#a5461f]',   // moca-hot family
    red:    'bg-[#f6e0da] text-[#9a3320]',   // moca-up family
    purple: 'bg-[#efe6d6] text-moca-bolt',   // priority / 5G — brand espresso
    pink:   'bg-[#f6ddd0] text-[#8f3f1c]',
    teal:   'bg-[#e2efe9] text-[#2f6b57]',
    amber:  'bg-[#f6e3d3] text-[#a5461f]',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide ${colors[color] || colors.gray} ${className}`}>
      {children}
    </span>
  )
}
