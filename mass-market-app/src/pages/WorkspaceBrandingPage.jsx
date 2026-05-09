import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'
import Button from '../components/ui/Button'

const FIELDS = [
  { key: 'app_title',        label: 'שם האפליקציה',        type: 'text',  placeholder: 'MOCA' },
  { key: 'logo_url',         label: 'כתובת לוגו (URL)',     type: 'url',   placeholder: 'https://...' },
  { key: 'primary_color',    label: 'צבע ראשי (hex)',       type: 'color', placeholder: '#5c3317' },
  { key: 'secondary_color',  label: 'צבע משני (hex)',       type: 'color', placeholder: '#5c3317' },
]

export default function WorkspaceBrandingPage() {
  const { workspace } = useAuth()
  const cfg = workspace?.brand_config || {}

  const [form, setForm]     = useState({
    app_title:         cfg.app_title         || '',
    logo_url:          cfg.logo_url          || '',
    primary_color:     cfg.primary_color     || '',
    secondary_color:   cfg.secondary_color   || '',
    slack_webhook_url: cfg.slack_webhook_url || '',
  })
  const [saving, setSaving]   = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError]     = useState(null)
  const [slackTestStatus, setSlackTestStatus] = useState(null)

  const save = async (e) => {
    e.preventDefault()
    setSaving(true); setError(null); setSuccess(false)
    try {
      await api.updateWorkspaceBranding(form)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const testSlack = async () => {
    setSlackTestStatus({ loading: true })
    try {
      const res = await api.testSlackWebhook(form.slack_webhook_url)
      setSlackTestStatus(res.ok ? { success: true } : { error: 'Slack webhook נכשל — בדוק את ה-URL' })
    } catch (err) {
      setSlackTestStatus({ error: err.message })
    }
    setTimeout(() => setSlackTestStatus(null), 5000)
  }

  return (
    <div className="max-w-xl mx-auto p-6">
      <p className="text-sm text-gray-600 mb-6">
        התאמה אישית של מראה האפליקציה עבור <strong>{workspace?.name}</strong>
      </p>

      <form onSubmit={save} className="bg-white rounded-xl border border-moca-border p-5 space-y-4">
        {FIELDS.map(f => (
          <div key={f.key}>
            <label className="block text-sm font-medium text-gray-700 mb-1">{f.label}</label>
            {f.type === 'color' ? (
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={form[f.key] || '#5c3317'}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  className="h-8 w-12 rounded border border-moca-border cursor-pointer"
                />
                <input
                  type="text"
                  value={form[f.key]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="flex-1 px-3 py-1.5 text-sm border border-moca-border rounded font-mono"
                />
                {form[f.key] && (
                  <button type="button" onClick={() => setForm(p => ({ ...p, [f.key]: '' }))}
                    className="text-xs text-gray-400 hover:text-red-500">נקה</button>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <input
                  type={f.type}
                  value={form[f.key]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="flex-1 px-3 py-1.5 text-sm border border-moca-border rounded"
                />
                {form[f.key] && (
                  <button type="button" onClick={() => setForm(p => ({ ...p, [f.key]: '' }))}
                    className="text-xs text-gray-400 hover:text-red-500">נקה</button>
                )}
              </div>
            )}
          </div>
        ))}

        {form.logo_url && (
          <div className="pt-1">
            <p className="text-xs text-gray-500 mb-1">תצוגה מקדימה של לוגו:</p>
            <img src={form.logo_url} alt="לוגו" className="h-10 object-contain rounded border border-moca-border/40 bg-gray-50 p-1" />
          </div>
        )}

        {/* Slack/Teams webhook integration */}
        <div className="pt-3 border-t border-moca-border/30">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Slack / Teams Webhook URL
          </label>
          <p className="text-[11px] text-gray-500 mb-2">
            התראות על שינויים בחבילות יישלחו לערוץ זה. ב-Slack: Apps → Incoming Webhooks. ב-Teams: Connectors → Incoming Webhook.
          </p>
          <div className="flex items-center gap-2">
            <input
              type="url"
              value={form.slack_webhook_url}
              onChange={e => setForm(p => ({ ...p, slack_webhook_url: e.target.value }))}
              placeholder="https://hooks.slack.com/services/..."
              className="flex-1 px-3 py-1.5 text-sm border border-moca-border rounded font-mono"
              dir="ltr"
            />
            {form.slack_webhook_url && (
              <button type="button" onClick={() => setForm(p => ({ ...p, slack_webhook_url: '' }))}
                className="text-xs text-gray-400 hover:text-red-500">נקה</button>
            )}
          </div>
          {form.slack_webhook_url && (
            <button
              type="button"
              onClick={testSlack}
              disabled={slackTestStatus?.loading}
              className="mt-2 text-xs px-3 py-1 rounded bg-moca-cream border border-moca-border/50 text-moca-sub hover:bg-moca-sand transition-colors disabled:opacity-50"
            >
              {slackTestStatus?.loading ? 'שולח...' : 'שלח הודעת בדיקה'}
            </button>
          )}
          {slackTestStatus?.success && <p className="text-xs text-green-600 mt-1.5">✓ ההודעה נשלחה בהצלחה</p>}
          {slackTestStatus?.error   && <p className="text-xs text-red-600 mt-1.5">✗ {slackTestStatus.error}</p>}
        </div>

        {error   && <p className="text-xs text-red-600">{error}</p>}
        {success && <p className="text-xs text-green-600">השינויים נשמרו בהצלחה</p>}

        <div className="pt-2 border-t border-moca-border/30 flex justify-start">
          <Button type="submit" disabled={saving} variant="primary" size="sm">
            {saving ? 'שומר…' : 'שמור שינויים'}
          </Button>
        </div>
      </form>

      <p className="text-xs text-gray-400 mt-3 text-center">
        השינויים יכנסו לתוקף בכניסה הבאה לאפליקציה.
      </p>
    </div>
  )
}
