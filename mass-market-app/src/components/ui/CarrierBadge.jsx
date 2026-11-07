import { getBrandColor } from '../moca/carrierMeta'

// Provider-name pill tinted in the provider's logo color (13% alpha background,
// solid text). Same look the content cards introduced; used on every card that
// identifies a provider so the pill matches the logo next to it.
export default function CarrierBadge({ carrier, children, className = '' }) {
  const color = getBrandColor(carrier)
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold tracking-wide ${className}`}
      style={{ backgroundColor: color + '22', color }}
    >
      {children}
    </span>
  )
}
