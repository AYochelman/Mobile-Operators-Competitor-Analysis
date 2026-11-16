import { useMemo } from 'react'
import { useAuth } from './useAuth'
import { effectiveFlags } from '../data/navFlags'

const NO_FLAGS = {}

export function useFeatureFlags() {
  const { workspace, isSuperAdmin, viewAs } = useAuth()
  // Super-admin normally sees everything — EXCEPT while impersonating a
  // workspace via "view as" (צופה כ), where the whole point is to preview
  // exactly what that client sees, feature_flags included. `workspace` here is
  // already the impersonated workspace (effectiveWorkspace in useAuth).
  const bypass = isSuperAdmin && !viewAs
  // Operator flags (feature_flags) + the sections the customer's own admin hid
  // in the /setup wizard (dashboard_config). Memoized so the object keeps its
  // identity between renders.
  return useMemo(() => (bypass ? NO_FLAGS : effectiveFlags(workspace)), [bypass, workspace])
}
