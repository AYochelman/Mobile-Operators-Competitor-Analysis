import { useOnlineStatus } from '../hooks/useOnlineStatus'
import { useLang } from '../hooks/useLanguage'

export default function OfflineBanner() {
  const isOnline = useOnlineStatus()
  const { tt } = useLang()
  if (isOnline) return null
  return (
    <div className="w-full bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-sm text-amber-800 font-medium">
      ⚡ {tt('אין חיבור לאינטרנט — מציג נתונים אחרונים', 'No internet connection — showing latest data')}
    </div>
  )
}
