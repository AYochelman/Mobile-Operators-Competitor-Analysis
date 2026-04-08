import { useState, useEffect, useRef } from 'react'
import Button from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'

export default function SettingsPage() {
  const { isAdmin, user } = useAuth()
  const [scraping, setScraping] = useState(false)
  const [result, setResult] = useState(null)
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef(null)

  // User management state
  const [users, setUsers] = useState([])
  const [usersLoading, setUsersLoading] = useState(true)
  const [usersError, setUsersError] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('viewer')
  const [addingUser, setAddingUser] = useState(false)
  const [addError, setAddError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [togglingId, setTogglingId] = useState(null)

  if (!isAdmin) return <div className="p-8 text-center text-gray-400">אין גישה</div>

  const SCRAPE_DURATION = 5 * 60

  const startCountdown = () => {
    setCountdown(SCRAPE_DURATION)
    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const handleScrape = async () => {
    setScraping(true)
    setResult(null)
    startCountdown()
    try {
      const res = await api.scrapeAll()
      setResult(res)
    } catch (err) {
      setResult({ error: err.message })
    }
    setScraping(false)
    setCountdown(0)
    if (timerRef.current) clearInterval(timerRef.current)
  }

  // Load users
  const loadUsers = async () => {
    setUsersLoading(true)
    setUsersError(null)
    try {
      const data = await api.getUsers()
      setUsers(data)
    } catch (err) {
      setUsersError(err.message)
    }
    setUsersLoading(false)
  }

  useEffect(() => {
    loadUsers()
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  // Add user
  const handleAddUser = async (e) => {
    e.preventDefault()
    setAddingUser(true)
    setAddError(null)
    try {
      await api.createUser({ email: newEmail, password: newPassword, role: newRole })
      setNewEmail('')
      setNewPassword('')
      setNewRole('viewer')
      setShowAddForm(false)
      await loadUsers()
    } catch (err) {
      setAddError(err.message)
    }
    setAddingUser(false)
  }

  // Delete user
  const handleDelete = async (id) => {
    setDeletingId(id)
    try {
      await api.deleteUser(id)
      setConfirmDeleteId(null)
      await loadUsers()
    } catch (err) {
      alert(err.message)
    }
    setDeletingId(null)
  }

  // Toggle role
  const handleToggleRole = async (u) => {
    setTogglingId(u.id)
    const newRole = u.role === 'admin' ? 'viewer' : 'admin'
    try {
      await api.updateUserRole(u.id, newRole)
      await loadUsers()
    } catch (err) {
      alert(err.message)
    }
    setTogglingId(null)
  }

  const isSelf = (u) => u.email === user?.email

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">

      {/* Scrape controls */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-bold text-sm mb-3">סקרייפרים</h2>
        <p className="text-xs text-gray-400 mb-4">עדכון כל הנתונים אורך כ-5 דקות</p>

        <div className="flex items-center gap-3">
          <Button onClick={handleScrape} disabled={scraping}>
            {scraping ? 'מעדכן...' : 'עדכן את כל הנתונים'}
          </Button>

          {scraping && countdown > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-2xl font-mono font-bold text-blue-600">{formatTime(countdown)}</span>
              <span className="text-xs text-gray-400">נותרו</span>
            </div>
          )}
        </div>

        {result && (
          <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm">
            {result.error ? (
              <p className="text-red-600">{result.error}</p>
            ) : (
              <p className="text-green-600">עדכון הסתיים — {result.total_plans || '?'} חבילות, {result.total_changes || 0} שינויים</p>
            )}
          </div>
        )}
      </div>

      {/* Schedule info */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-bold text-sm mb-3">תזמון</h2>
        <div className="text-sm text-gray-600 space-y-1">
          <p>סקרייפ אוטומטי: <strong>10:00</strong> ו-<strong>16:00</strong></p>
          <p>דוח Excel יומי: <strong>09:00</strong></p>
          <p>התראות: Telegram + Web Push בלבד על שינויים</p>
        </div>
      </div>

      {/* Users */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-sm">ניהול משתמשים</h2>
          <Button size="sm" onClick={() => { setShowAddForm(!showAddForm); setAddError(null) }}>
            {showAddForm ? 'ביטול' : 'הוספת משתמש'}
          </Button>
        </div>

        {/* Add user form */}
        {showAddForm && (
          <form onSubmit={handleAddUser} className="mb-4 p-3 bg-gray-50 rounded-lg space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">אימייל</label>
              <input
                type="email"
                required
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="user@example.com"
                dir="ltr"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">סיסמה</label>
              <input
                type="password"
                required
                minLength={6}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="לפחות 6 תווים"
                dir="ltr"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">תפקיד</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setNewRole('viewer')}
                  className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                    newRole === 'viewer'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  צופה
                </button>
                <button
                  type="button"
                  onClick={() => setNewRole('admin')}
                  className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                    newRole === 'admin'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  מנהל
                </button>
              </div>
            </div>
            {addError && <p className="text-red-600 text-xs">{addError}</p>}
            <Button type="submit" size="sm" disabled={addingUser}>
              {addingUser ? 'יוצר...' : 'צור משתמש'}
            </Button>
          </form>
        )}

        {/* Users table */}
        {usersLoading ? (
          <p className="text-sm text-gray-400">טוען...</p>
        ) : usersError ? (
          <div className="text-sm text-red-600">
            <p>{usersError}</p>
            <button onClick={loadUsers} className="text-blue-600 underline text-xs mt-1">נסה שוב</button>
          </div>
        ) : users.length === 0 ? (
          <p className="text-sm text-gray-400">אין משתמשים</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-gray-500 text-xs">
                  <th className="text-right py-2 pr-1 font-medium w-1/2">אימייל</th>
                  <th className="text-right py-2 font-medium">תפקיד</th>
                  <th className="py-2 pl-1 w-16"></th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} className="border-b border-gray-100 last:border-0">
                    <td className="py-2.5 pr-1 text-gray-800" dir="ltr">
                      {u.email}
                      {isSelf(u) && <span className="text-xs text-gray-400 mr-1">(אתה)</span>}
                    </td>
                    <td className="py-2.5">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                        u.role === 'admin'
                          ? 'bg-purple-100 text-purple-700'
                          : 'bg-gray-100 text-gray-600'
                      }`}>
                        {u.role === 'admin' ? 'מנהל' : 'צופה'}
                      </span>
                    </td>
                    <td className="py-2.5 pl-1">
                      <div className="flex items-center gap-1.5">
                        {!isSelf(u) && (
                          <>
                            <button
                              onClick={() => handleToggleRole(u)}
                              disabled={togglingId === u.id}
                              className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                              title={u.role === 'admin' ? 'הורד למצפה' : 'הפוך למנהל'}
                            >
                              {togglingId === u.id ? '...' : u.role === 'admin' ? 'הורד לצופה' : 'הפוך למנהל'}
                            </button>

                            {confirmDeleteId === u.id ? (
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleDelete(u.id)}
                                  disabled={deletingId === u.id}
                                  className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                                >
                                  {deletingId === u.id ? '...' : 'אשר מחיקה'}
                                </button>
                                <button
                                  onClick={() => setConfirmDeleteId(null)}
                                  className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 transition-colors"
                                >
                                  בטל
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDeleteId(u.id)}
                                className="text-xs px-2 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50 transition-colors"
                              >
                                מחק
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
