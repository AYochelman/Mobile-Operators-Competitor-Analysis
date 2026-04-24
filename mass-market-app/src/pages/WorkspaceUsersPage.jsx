import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'
import Button from '../components/ui/Button'

export default function WorkspaceUsersPage() {
  const { workspace } = useAuth()
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [newEmail, setNewEmail]  = useState('')
  const [newRole, setNewRole]    = useState('viewer')
  const [assigning, setAssigning] = useState(false)
  const [formError, setFormError] = useState(null)

  const wsId = workspace?.id

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

  const unassign = async (userId) => {
    if (!confirm('להסיר את המשתמש מה-workspace?')) return
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
      <div className="mb-6">
        <h1 className="text-2xl font-bold">הצוות שלנו</h1>
        <p className="text-sm text-gray-600 mt-1">
          ניהול משתמשים עבור workspace <strong>{workspace?.name}</strong>
        </p>
      </div>

      <div className="bg-white rounded-xl border border-moca-border p-5 space-y-4">
        {loading ? (
          <p className="text-gray-500 text-sm">טוען…</p>
        ) : error ? (
          <p className="text-red-600 text-sm">שגיאה: {error}</p>
        ) : users.length === 0 ? (
          <p className="text-gray-500 text-sm">אין משתמשים ב-workspace זה.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b">
                <th className="text-right py-1.5">אימייל</th>
                <th className="text-right py-1.5">תפקיד</th>
                <th className="text-right py-1.5">כניסה אחרונה</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b border-moca-border/30">
                  <td className="py-2">{u.email}</td>
                  <td className="py-2">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      u.role === 'admin' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'
                    }`}>{u.role}</span>
                  </td>
                  <td className="py-2 text-xs text-gray-500">
                    {u.last_sign_in_at ? new Date(u.last_sign_in_at).toLocaleDateString('he-IL') : '—'}
                  </td>
                  <td className="py-2 text-left">
                    <button onClick={() => unassign(u.id)}
                      className="text-xs text-red-500 hover:underline">הסרה</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="pt-3 border-t border-moca-border/30">
          <h3 className="text-sm font-semibold mb-3">הוספת משתמש</h3>
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
              {assigning ? '…' : 'הוסף'}
            </Button>
          </form>
          {formError && <p className="text-xs text-red-600 mt-2">{formError}</p>}
        </div>
      </div>
    </div>
  )
}
