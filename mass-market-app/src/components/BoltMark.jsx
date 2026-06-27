import { BOLT_PATH } from './Logo'

/* The MOCA lightning-bolt mark as a standalone inline SVG that inherits the
   current text color (fill="currentColor"). Lets the scoped standalone pages
   (guest portal, /hotels landing, /esim-deals B2C) show the real app logo
   inside their brand chip instead of the ⚡ emoji. SSR-safe (pure render). */
export default function BoltMark({ size = 20, className }) {
  return (
    <svg
      width={size}
      height={Math.round((size * 46) / 48)}
      viewBox="0 0 48 46"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path fill="currentColor" d={BOLT_PATH} />
    </svg>
  )
}
