/**
 * MOCA design-system primitives — barrel export.
 *
 * Usage:
 *   import { CarrierChip, Sparkline, Delta, Tag, PageHeader } from '@/components/moca'
 */

// Primitives
export { default as CarrierChip } from './CarrierChip'
export { default as Sparkline } from './Sparkline'
export { default as Delta } from './Delta'
export { default as Tag } from './Tag'
export { default as PageHeader } from './PageHeader'

// Shell
export { default as Sidebar } from './Sidebar'
export { default as Topbar } from './Topbar'
export { default as TimeMachineModal } from './TimeMachineModal'

// Widgets
export { default as CompetitorBoard } from './CompetitorBoard'
export { default as BannerMosaic } from './BannerMosaic'
export { default as BannerTile } from './BannerTile'
export { default as BannerDrawer } from './BannerDrawer'

// Editorial Deep dashboard pieces
export { default as EditorialHero } from './EditorialHero'
export { default as KpiCard } from './KpiCard'
export { default as ChangeHeatmap } from './ChangeHeatmap'

// Workspace utilities
export { default as MyCarrierModal } from './MyCarrierModal'

// Helpers
export { getCarrierColor, getCarrierLetter, getCarrierName } from './carrierMeta'
export { resolveRouteMeta, ROUTE_META } from './routeMeta'
