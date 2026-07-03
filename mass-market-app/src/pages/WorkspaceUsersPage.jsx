import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'
import Button from '../components/ui/Button'
import { useLang } from '../hooks/useLanguage'

export default function WorkspaceUsersPage() {
  const { workspace, workspaceId } = useAuth()
  const { tt } = useLang()
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [newEmail, setNewEmail]  = useState('')
  const [newRole, setNewRole]    = useState('viewer')
  const [assigning, setAssigning] = useState(false)
  const [formError, setFormError] = useState(null)
  const [inviteRole, setInviteRole]     = useState('viewer')
  const [inviteLink, setInviteLink]     = useState(null)
  const [creatingInvite, setCreatingInvite] = useState(false)
  const [copied, setCopied]             = useState(false)

  const wsId = workspaceId

  const load = useCallback(async () => {
    if (!wsId) return
    setLoading(true); setError(null)
    try {
      setUsers(await api.getWorkspaceUsers(wsId))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [wsId])

  useEffect(() => { load() }, [load])

  const assign = async (e) => {
    e.preventDefault()
    if (!newEmail.trim()) return
    setAssigning(true); setFormError(null)
    try {
      await api.assignWorkspaceUser(wsId, newEmail.trim(), newRole)
      setNewEmail('')
      await load()
    } catch (e) {
      setFormError(e.message)
    } finally {
      setAssigning(false)
    }
  }

  const createInvite = async () => {
    setCreatingInvite(true); setInviteLink(null)
    try {
      const res = await api.createInvite(wsId, inviteRole)
      const base = window.location.origin
      setInviteLink(`${base}/invite/${res.token}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setCreatingInvite(false)
    }
  }

  const copyLink = () => {
    navigator.clipboard.writeText(inviteLink).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const unassign = async (userId) => {
    if (!confirm(tt('להסיר את המשתמש מה-workspace?', 'Remove this user from the workspace?'))) return
    setError(null)
    try {
      await api.unassignWorkspaceUser(wsId, userId)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <p className="text-sm text-gray-600 mb-6">
        {tt('ניהול משתמשים עבור workspace', 'User management for workspace')} <strong>{workspace?.name}</strong>
      </p>

      <div className="bg-white rounded-xl border border-moca-border p-5 space-y-4">
        {loading ? (
          <p className="text-gray-500 text-sm">{tt('טוען…', 'Loading…')}</p>
        ) : error ? (
          <p className="text-red-600 text-sm">{tt('שגיאה', 'Error')}: {error}</p>
        ) : users.length === 0 ? (
          <p className="text-gray-500 text-sm">{tt('אין משתמשים ב-workspace זה.', 'No users in this workspace.')}</p>
        ) : (
          <div className="-mx-4 px-4 overflow-x-auto md:mx-0 md:px-0">
            <table className="w-full text-sm min-w-[480px] md:min-w-0">
              <thead>
                <tr className="text-xs text-gray-500 border-b">
                  <th className="text-right py-1.5 whitespace-nowrap">{tt('אימייל', 'Email')}</th>
                  <th className="text-right py-1.5 whitespace-nowrap">{tt('תפקיד', 'Role')}</th>
                  <th className="text-right py-1.5 whitespace-nowrap">{tt('כניסה אחרונה', 'Last sign-in')}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} className="border-b border-moca-border/30">
                    <td className="py-2 whitespace-nowrap" dir="ltr">{u.email}</td>
                    <td className="py-2">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.role === 'admin' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'
                      }`}>{u.role}</span>
                    </td>
                    <td className="py-2 text-xs text-gray-500 whitespace-nowrap">
                      {u.last_sign_in_at ? new Date(u.last_sign_in_at).toLocaleDateString('he-IL') : '—'}
                    </td>
                    <td className="py-2 text-left">
                      <button onClick={() => unassign(u.id)}
                        className="text-xs text-red-500 hover:underline">{tt('הסרה', 'Remove')}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="pt-3 border-t border-moca-border/30">
          <h3 className="text-sm font-semibold mb-3">{tt('הוספת משתמש קיים', 'Add existing user')}</h3>
          <form onSubmit={assign} className="flex gap-2 flex-wrap items-center">
            <input type="email" required placeholder="email@example.com"
              value={newEmail} onChange={e => setNewEmail(e.target.value)}
              className="px-3 py-1.5 text-sm border border-moca-border rounded flex-1 min-w-[220px]" />
            <select value={newRole} onChange={e => setNewRole(e.target.value)}
              className="px-2 py-1.5 text-sm border border-moca-border rounded">
              <option value="viewer">viewer</option>
              <option value="admin">admin</option>
            </select>
            <Button type="submit" disabled={assigning} variant="primary" size="sm">
              {assigning ? '…' : tt('הוסף', 'Add')}
            </Button>
          </form>
          {formError && <p className="text-xs text-red-600 mt-2">{formError}</p>}
        </div>

        <div className="pt-3 border-t border-moca-border/30">
          <h3 className="text-sm font-semibold mb-3">{tt('קישור הזמנה', 'Invite link')}</h3>
          <div className="flex gap-2 items-center flex-wrap">
            <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
              className="px-2 py-1.5 text-sm border border-moca-border rounded">
              <option value="viewer">viewer</option>
              <option value="admin">admin</option>
            </select>
            <Button onClick={createInvite} disabled={creatingInvite} variant="secondary" size="sm">
              {creatingInvite ? '…' : tt('צור לינק', 'Create link')}
            </Button>
          </div>
          {inviteLink && (
            <div className="mt-2 flex items-center gap-2">
              <input readOnly value={inviteLink}
                className="flex-1 px-2 py-1 text-xs border border-moca-border rounded font-mono bg-gray-50 min-w-0" />
              <button onClick={copyLink}
                className="text-xs px-2 py-1 rounded border border-moca-border hover:bg-moca-cream transition-colors whitespace-nowrap">
                {copied ? tt('הועתק ✓', 'Copied ✓') : tt('העתק', 'Copy')}
              </button>
            </div>
          )}
          <p className="text-xs text-gray-400 mt-1.5">{tt('תוקף: 7 ימים · שימוש חד-פעמי', 'Valid for 7 days · single use')}</p>
        </div>
      </div>
    </div>
  )
}
