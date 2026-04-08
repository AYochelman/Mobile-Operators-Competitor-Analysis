const BOLT_PATH = 'M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z'

const CONFIG = {
  xs: { boltW: 16, boltH: 15, wordmarkSize: null, subtextSize: null },
  sm: { boltW: 20, boltH: 19, wordmarkSize: 14,   subtextSize: null },
  md: { boltW: 28, boltH: 27, wordmarkSize: 18,   subtextSize: 9   },
}

export default function Logo({ size = 'md' }) {
  const { boltW, boltH, wordmarkSize, subtextSize } = CONFIG[size]

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width={boltW} height={boltH} viewBox="0 0 48 46" fill="none" aria-hidden="true">
        <path fill="var(--color-moca-bolt)" d={BOLT_PATH} />
      </svg>

      {wordmarkSize && (
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
          <span style={{
            fontSize: wordmarkSize,
            fontWeight: 900,
            color: 'var(--color-moca-text)',
            letterSpacing: '-0.02em',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          }}>
            MOCA
          </span>
          {subtextSize && (
            <span style={{
              fontSize: subtextSize,
              fontWeight: 400,
              color: 'var(--color-moca-sub)',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              letterSpacing: '0.01em',
            }}>
              by Alon Yochelman
            </span>
          )}
        </div>
      )}
    </div>
  )
}
