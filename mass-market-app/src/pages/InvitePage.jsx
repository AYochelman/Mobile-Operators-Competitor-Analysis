import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import Logo from '../components/Logo'

export default function InvitePage() {
  const { token } = useParams()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [invite, setInvite]     = useState(null)
  const [loadErr, setLoadErr]   = useState(null)
  const [accepting, setAccepting] = useState(false)
  const [accepted, setAccepted]   = useState(false)
  const [acceptErr, setAcceptErr] = useState(null)

  useEffect(() => {
    api.getInvite(token)
      .then(setInvite)
      .catch(e => setLoadErr(e.message))
  }, [token])

  const accept = async () => {
    if (!user) {
      sessionStorage.setItem('pending_invite', token)
      navigate('/login')
      return
    }
    setAccepting(true); setAcceptErr(null)
    try {
      await api.acceptInvite(token)
      setAccepted(true)
      setTimeout(() => navigate('/'), 2500)
    } catch (e) {
      setAcceptErr(e.message)
    } finally {
      setAccepting(false)
    }
  }

  const roleHe = invite?.role === 'admin' ? 'מנהל' : 'צופה'

  return (
    <div className="min-h-screen bg-moca-bg flex flex-col items-center justify-center p-6">
      <div className="mb-8">
        <Logo size="md" showSubtext={false} />
      </div>

      <div className="bg-white rounded-2xl border border-moca-border shadow-sm p-8 w-full max-w-md text-center">
        {authLoading || (!invite && !loadErr) ? (
          <p className="text-gray-500 text-sm">טוען…</p>

        ) : loadErr ? (
          <>
            <div className="text-4xl mb-4">🔗</div>
            <h1 className="text-xl font-bold text-red-600 mb-2">קישור לא תקין</h1>
            <p className="text-sm text-gray-500">{loadErr}</p>
          </>

        ) : accepted ? (
          <>
            <div className="text-4xl mb-4">✅</div>
            <h1 className="text-xl font-bold mb-2">ברוך הבא!</h1>
            <p className="text-sm text-gray-500">הצטרפת בהצלחה ל-{invite.workspace_name}. מעביר לדשבורד…</p>
          </>

        ) : (
          <>
            <div className="text-4xl mb-4">📩</div>
            <h1 className="text-xl font-bold mb-1">הוזמנת ל-MOCA</h1>
            <p className="text-gray-600 text-sm mb-6">
              הצטרף ל-workspace <strong>{invite.workspace_name}</strong> בתפקיד <strong>{roleHe}</strong>
            </p>

            {acceptErr && (
              <p className="text-xs text-red-600 mb-4">{acceptErr}</p>
            )}

            {!user && (
              <p className="text-xs text-gray-400 mb-3">
                יש להתחבר לחשבון MOCA לפני ההצטרפות
              </p>
            )}

            <button
              onClick={accept}
              disabled={accepting}
              className="w-full py-2.5 px-4 bg-moca-bolt text-white rounded-lg text-sm font-medium hover:bg-moca-dark transition-colors disabled:opacity-60"
            >
              {accepting ? 'מצטרף…' : user ? 'הצטרף ל-Workspace' : 'כנס והצטרף'}
            </button>

            <p className="text-xs text-gray-400 mt-4">
              תוקף ההזמנה עד {new Date(invite.expires_at).toLocaleDateString('he-IL')}
            </p>
          </>
        )}
      </div>
    </div>
  )
}
