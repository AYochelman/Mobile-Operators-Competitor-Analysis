import { useAuth } from './useAuth'

export function useFeatureFlags() {
  const { workspace, isSuperAdmin } = useAuth()
  if (isSuperAdmin) return {}   // super_admin always sees everything
  return workspace?.feature_flags || {}
}
