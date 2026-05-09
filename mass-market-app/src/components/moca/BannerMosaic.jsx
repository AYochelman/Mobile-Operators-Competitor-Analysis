import { useState } from 'react'
import BannerTile from './BannerTile'
import BannerDrawer from './BannerDrawer'

/**
 * Multi-column mosaic of banner tiles. Click a tile → drawer slides in.
 *
 * Per design handoff:
 *   - column-count: 3 (responsive to 2 at <1100px, 1 at <640px)
 *   - column-fill: balance (default)
 *   - tiles use break-inside: avoid + 14px bottom margin
 *
 * Encapsulates drawer state — caller only passes the banner array.
 */
export default function BannerMosaic({ banners, source = 'home' }) {
  const [active, setActive] = useState(null)

  if (!banners || banners.length === 0) return null

  const handleClick = (banner) => {
    // Per-banner kind wins; otherwise fall back to the mosaic's `source` prop.
    // (Archive views pre-tag each banner because the same mosaic mixes home
    // + store; the dashboard banners tab uses a single source per mosaic.)
    if (banner?.kind === 'home' || banner?.kind === 'store') {
      setActive(banner)
    } else {
      setActive({ ...banner, kind: source === 'store' ? 'store' : 'home' })
    }
  }

  return (
    <>
      <div
        className="moca-banner-mosaic"
        style={{
          // Inline column-count is overridden by CSS @media for responsiveness.
          columnCount: 3,
          columnGap: 14,
          // Slight padding so tile shadows aren't clipped at column edges
          padding: '2px 0',
        }}
      >
        {banners.map((banner) => (
          <BannerTile
            key={`${banner.carrier}-${banner.image_url || banner.scraped_at || ''}`}
            banner={banner}
            onClick={handleClick}
          />
        ))}
      </div>

      {/* Responsive column-count via media queries — inline @media isn't
          possible, so we ship a styled-element <style> tag once. */}
      <style>{`
        @media (max-width: 1100px) {
          .moca-banner-mosaic { column-count: 2 !important; }
        }
        @media (max-width: 640px) {
          .moca-banner-mosaic { column-count: 1 !important; }
        }
      `}</style>

      <BannerDrawer banner={active} onClose={() => setActive(null)} />
    </>
  )
}
