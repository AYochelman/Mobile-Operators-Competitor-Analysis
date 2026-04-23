import { useAuth } from './useAuth'

// Returns the carrier id the current workspace wants hidden (self-carrier),
// or null. Backend already filters data — this hook is a UX failsafe so
// hardcoded carrier dropdowns/lists don't show an option that returns empty.
export function useHiddenCarrier() {
  const { workspace, isSuperAdmin } = useAuth()
  if (isSuperAdmin) return null
  if (!workspace?.hide_self_carrier) return null
  return workspace.mvno_carrier || null
}

// Convenience: filter a carrier-id list, stripping the hidden one.
export function useVisibleCarriers(carrierIds) {
  const hidden = useHiddenCarrier()
  if (!hidden) return carrierIds
  return carrierIds.filter(c => c !== hidden)
}
