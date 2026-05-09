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

// Helpers
export { getCarrierColor, getCarrierLetter, getCarrierName } from './carrierMeta'
export { resolveRouteMeta, ROUTE_META } from './routeMeta'
