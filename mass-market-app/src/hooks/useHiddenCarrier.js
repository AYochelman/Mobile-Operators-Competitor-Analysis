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

// Convenience: filter a carrier-id list applying both visible_carriers scoping
// (allowlist) and hide_self_carrier (denylist). Super-admins bypass both.
export function useVisibleCarriers(carrierIds) {
  const { workspace, isSuperAdmin } = useAuth()
  if (isSuperAdmin) return carrierIds

  let result = carrierIds

  // Allowlist: if workspace defines specific visible carriers, restrict to those
  const allowed = workspace?.visible_carriers
  if (allowed?.length > 0) {
    result = result.filter(c => allowed.includes(c))
  }

  // Denylist: always hide self-carrier
  const hidden = (workspace?.hide_self_carrier && workspace?.mvno_carrier) || null
  if (hidden) result = result.filter(c => c !== hidden)

  return result
}
