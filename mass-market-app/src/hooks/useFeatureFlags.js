import { useAuth } from './useAuth'

export function useFeatureFlags() {
  const { workspace, isSuperAdmin, viewAs } = useAuth()
  // Super-admin normally sees everything — EXCEPT while impersonating a
  // workspace via "view as" (צופה כ), where the whole point is to preview
  // exactly what that client sees, feature_flags included. `workspace` here is
  // already the impersonated workspace (effectiveWorkspace in useAuth).
  if (isSuperAdmin && !viewAs) return {}
  return workspace?.feature_flags || {}
}
