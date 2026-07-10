import { useEffect, useMemo, useState, useCallback } from 'react'
import { api, API_BASE } from '../lib/api'
import { HOTEL_DESTINATIONS, destLabel } from '../data/hotelDestinations'
import { useLang } from '../hooks/useLanguage'

/* ════════════════════════════════════════════════════════════════════════
   MOCA Guest Connect — operator console  (route: /admin/hotels, super_admin)
   Create/manage hotel guest portals, preview branding, view per-hotel
   anonymous analytics, and generate the branded QR.
   ════════════════════════════════════════════════════════════════════════ */

const BLANK = {
  slug: '', name: '', tagline: '', brand_primary: '#26170f', brand_secondary: '#d16938',
  brand_bg: '#f4f1ee', mono: '', default_lang: 'en', languages: ['en', 'he'],
  commission_note: '50/50', contact_email: '', active: true, country: 'ישראל',
}
const LANGS = [{ id: 'en', l: 'English' }, { id: 'he', l: 'עברית' }, { id: 'fr', l: 'Français' }, { id: 'ru', l: 'Русский' }]
// Destination dropdown options — "קפריסין · Cyprus". value = canonical Hebrew
// (matches the DB feed filter); English shown for quick scanning.
const DEST_OPTIONS = HOTEL_DESTINATIONS.map((d) => ({ he: d.he, label: `${d.he} · ${destLabel(d.he, 'en')}` }))
const DEST_HE_SET = new Set(DEST_OPTIONS.map((o) => o.he))
const PUBLIC_ORIGIN = typeof window !== 'undefined' && /mocaintel\.com$/.test(window.location.hostname)
  ? window.location.origin : 'https://mocaintel.com'

function slugify(s) {
  return (s || '').toLowerCase().trim()
    .replace(/[^a-z0-9֐-׿\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').slice(0, 40)
}

function Stat({ label, value, accent }) {
  return (
    <div className="bg-white rounded-2xl border border-[var(--color-moca-border)] p-4 shadow-sm">
      <div className="text-xs font-bold text-[var(--color-moca-sub)]">{label}</div>
      <div className="text-2xl font-extrabold mt-1" style={{ color: accent || 'var(--color-moca-dark)' }}>{value}</div>
    </div>
  )
}

export default function HotelsAdminPage() {
  const { tt } = useLang()
  const [hotels, setHotels] = useState([])
  const [sel, setSel] = useState(null)         // slug | 'new' | null
  const [form, setForm] = useState(BLANK)
  const [isNew, setIsNew] = useState(false)
  const [analytics, setAnalytics] = useState(null)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const loadHotels = useCallback(async () => {
    setLoading(true); setErr('')
    try { setHotels(await api.getHotels()) }
    catch (e) { setErr(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadHotels() }, [loadHotels])

  const portalUrl = useMemo(() => sel && !isNew ? `${PUBLIC_ORIGIN}/guest/${form.slug}` : '', [sel, isNew, form.slug])

  const openHotel = (h) => {
    setIsNew(false); setSel(h.slug); setMsg(''); setErr('')
    setForm({ ...BLANK, ...h, languages: h.languages || ['en', 'he'] })
    setAnalytics(null)
    loadAnalytics(h.slug, days)
  }
  const openNew = () => {
    setIsNew(true); setSel('new'); setMsg(''); setErr(''); setAnalytics(null); setForm(BLANK)
  }

  const loadAnalytics = async (slug, d) => {
    try { setAnalytics(await api.getHotelAnalytics(slug, d)) }
    catch { setAnalytics(null) }
  }
  useEffect(() => { if (sel && !isNew) loadAnalytics(form.slug, days) }, [days]) // eslint-disable-line

  const set = (k, v) => setForm((s) => ({ ...s, [k]: v }))
  const toggleLang = (id) => setForm((s) => ({
    ...s, languages: s.languages.includes(id) ? s.languages.filter((x) => x !== id) : [...s.languages, id],
  }))

  const save = async () => {
    setErr(''); setMsg('')
    if (!form.name.trim()) { setErr(tt('שם המלון חובה.', 'Hotel name is required.')); return }
    const slug = isNew ? slugify(form.slug || form.name) : form.slug
    if (!slug) { setErr(tt('Slug חובה (אותיות לטיניות/מספרים).', 'Slug is required (Latin letters/numbers).')); return }
    if (!form.languages.length) { setErr(tt('בחרו לפחות שפה אחת.', 'Select at least one language.')); return }
    setSaving(true)
    try {
      const payload = { ...form, slug }
      if (isNew) { await api.createHotel(payload); setMsg(tt('הפורטל נוצר ✓', 'Portal created ✓')) }
      else { await api.updateHotel(slug, payload); setMsg(tt('נשמר ✓', 'Saved ✓')) }
      await loadHotels()
      setIsNew(false); setSel(slug); setForm((s) => ({ ...s, slug }))
      if (!isNew) loadAnalytics(slug, days)
    } catch (e) {
      setErr(e.message || tt('שמירה נכשלה', 'Save failed'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!sel || isNew) return
    if (!window.confirm(tt(`למחוק את הפורטל של ${form.name}? פעולה זו אינה הפיכה.`, `Delete the portal for ${form.name}? This action is irreversible.`))) return
    try { await api.deleteHotel(form.slug); await loadHotels(); setSel(null); setMsg(tt('נמחק', 'Deleted')) }
    catch (e) { setErr(e.message) }
  }

  const copyLink = () => { navigator.clipboard?.writeText(portalUrl); setMsg(tt('הקישור הועתק ✓', 'Link copied ✓')) }

  const downloadQr = async () => {
    try {
      const res = await fetch(api.guestQrUrl(form.slug, PUBLIC_ORIGIN))
      const svg = await res.text()
      const blob = new Blob([svg], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${form.slug}-guest-qr.svg`; a.click()
      URL.revokeObjectURL(url)
    } catch { setErr(tt('הורדת ה-QR נכשלה', 'QR download failed')) }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-1">
        <div>
          <div className="text-xs font-extrabold tracking-widest text-[var(--color-moca-hot)] uppercase">Guest Connect</div>
          <h1 className="text-2xl font-extrabold text-[var(--color-moca-dark)] font-[var(--font-display)]">{tt('פורטלי אורחים - מלונות', 'Guest portals - hotels')}</h1>
        </div>
        <div className="flex gap-2">
          <a href="/hotels" target="_blank" rel="noopener"
            className="px-4 py-2 rounded-xl border border-[var(--color-moca-border)] text-[var(--color-moca-bolt)] font-bold text-sm hover:border-[var(--color-moca-bolt)]">
            {tt('דף השיווק ↗', 'Marketing page ↗')}
          </a>
          <button onClick={openNew}
            className="px-4 py-2 rounded-xl bg-[var(--color-moca-bolt)] text-white font-bold text-sm hover:opacity-90">
            {tt('+ פורטל חדש', '+ New portal')}
          </button>
        </div>
      </div>
      <p className="text-sm text-[var(--color-moca-sub)] mb-5">{tt('ניהול הפורטלים הממותגים, אנליטיקת אורחים אנונימית, ומחולל ה-QR. כל פורטל זמין בכתובת', 'Manage the branded portals, anonymous guest analytics, and the QR generator. Each portal is available at')} <code className="text-xs">/guest/&lt;slug&gt;</code>.</p>

      {err && <div className="mb-4 rounded-xl bg-red-50 border border-red-200 text-red-700 px-4 py-2 text-sm font-semibold">{err}</div>}
      {msg && <div className="mb-4 rounded-xl bg-green-50 border border-green-200 text-green-700 px-4 py-2 text-sm font-semibold">{msg}</div>}

      <div className="grid md:grid-cols-[300px_1fr] gap-5 items-start">
        {/* list */}
        <div className="bg-white rounded-2xl border border-[var(--color-moca-border)] shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--color-moca-border)] text-sm font-extrabold text-[var(--color-moca-dark)]">
            {tt('הפורטלים', 'Portals')} ({hotels.length})
          </div>
          {loading ? (
            <div className="p-5 text-sm text-[var(--color-moca-sub)]">{tt('טוען…', 'Loading…')}</div>
          ) : hotels.length === 0 ? (
            <div className="p-5 text-sm text-[var(--color-moca-sub)]">{tt('אין פורטלים עדיין. צרו את הראשון →', 'No portals yet. Create the first one →')}</div>
          ) : (
            <ul className="max-h-[60vh] overflow-auto">
              {hotels.map((h) => (
                <li key={h.slug}>
                  <button onClick={() => openHotel(h)}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-start hover:bg-[var(--color-moca-cream)] ${sel === h.slug ? 'bg-[var(--color-moca-cream)]' : ''}`}>
                    <span className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-extrabold flex-none"
                      style={{ background: h.brand_primary || '#5c3317' }}>
                      {h.mono || (h.name || '?').slice(0, 2).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-bold text-[var(--color-moca-dark)] truncate">{h.name}</span>
                      <span className="block text-xs text-[var(--color-moca-sub)] truncate">/guest/{h.slug}</span>
                    </span>
                    {!h.active && <span className="text-[10px] font-bold text-red-500">{tt('מושהה', 'Suspended')}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* detail */}
        {sel ? (
          <div className="space-y-5">
            {/* editor */}
            <div className="bg-white rounded-2xl border border-[var(--color-moca-border)] shadow-sm p-5">
              <h2 className="text-lg font-extrabold text-[var(--color-moca-dark)] mb-4">
                {isNew ? tt('פורטל חדש', 'New portal') : `${tt('עריכה', 'Edit')} - ${form.name}`}
              </h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label={tt('שם המלון / הרשת', 'Hotel / chain name')}>
                  <input className="inp" value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Coastline Hotels" />
                </Field>
                <Field label={tt('Slug (כתובת הפורטל)', 'Slug (portal address)')}>
                  <input className="inp font-mono" disabled={!isNew} value={form.slug}
                    onChange={(e) => set('slug', slugify(e.target.value))} placeholder="coastline" />
                </Field>
                <Field label={tt('מדינת היעד - הפורטל יציג חבילות גלישה למדינה זו בלבד', 'Destination country - the portal will show data plans for this country only')} full>
                  <select className="inp" value={form.country || 'ישראל'} onChange={(e) => set('country', e.target.value)}>
                    {form.country && !DEST_HE_SET.has(form.country) && (
                      <option value={form.country}>{`${form.country} · ${destLabel(form.country, 'en')}`}</option>
                    )}
                    {DEST_OPTIONS.map((o) => <option key={o.he} value={o.he}>{o.label}</option>)}
                  </select>
                </Field>
                <Field label={tt('כותרת (Tagline)', 'Tagline')} full>
                  <input className="inp" value={form.tagline || ''} onChange={(e) => set('tagline', e.target.value)}
                    placeholder="Stay connected in Israel" />
                </Field>
                <Field label={tt('צבע ראשי (כהה)', 'Primary color (dark)')}>
                  <ColorInput value={form.brand_primary} onChange={(v) => set('brand_primary', v)} />
                </Field>
                <Field label={tt('צבע משני (הדגשה)', 'Secondary color (accent)')}>
                  <ColorInput value={form.brand_secondary} onChange={(v) => set('brand_secondary', v)} />
                </Field>
                <Field label={tt('רקע עמוד', 'Page background')}>
                  <ColorInput value={form.brand_bg} onChange={(v) => set('brand_bg', v)} />
                </Field>
                <Field label={tt('מונוגרמה (1-3 תווים)', 'Monogram (1-3 chars)')}>
                  <input className="inp" maxLength={3} value={form.mono || ''} onChange={(e) => set('mono', e.target.value)} placeholder="CH" />
                </Field>
                <Field label={tt('שפת ברירת מחדל', 'Default language')}>
                  <select className="inp" value={form.default_lang} onChange={(e) => set('default_lang', e.target.value)}>
                    {LANGS.map((l) => <option key={l.id} value={l.id}>{l.l}</option>)}
                  </select>
                </Field>
                <Field label={tt('הערת עמלה (פנימי)', 'Commission note (internal)')}>
                  <input className="inp" value={form.commission_note || ''} onChange={(e) => set('commission_note', e.target.value)} placeholder="50/50" />
                </Field>
                <Field label={tt('שפות זמינות', 'Available languages')} full>
                  <div className="flex gap-2 flex-wrap">
                    {LANGS.map((l) => (
                      <button key={l.id} type="button" onClick={() => toggleLang(l.id)}
                        className={`px-3 py-1.5 rounded-full text-sm font-bold border ${form.languages.includes(l.id)
                          ? 'bg-[var(--color-moca-bolt)] text-white border-[var(--color-moca-bolt)]'
                          : 'bg-white text-[var(--color-moca-sub)] border-[var(--color-moca-border)]'}`}>
                        {l.l}
                      </button>
                    ))}
                  </div>
                </Field>
                <Field label={tt('סטטוס', 'Status')} full>
                  <label className="flex items-center gap-2 text-sm font-semibold text-[var(--color-moca-text)]">
                    <input type="checkbox" checked={form.active} onChange={(e) => set('active', e.target.checked)} />
                    {tt('פעיל (גלוי לאורחים)', 'Active (visible to guests)')}
                  </label>
                </Field>
              </div>

              {/* brand preview */}
              <div className="mt-4 rounded-xl overflow-hidden border border-[var(--color-moca-border)]">
                <div className="p-4 flex items-center gap-3" style={{ background: form.brand_primary, color: '#fff' }}>
                  <span className="w-10 h-10 rounded-xl bg-white flex items-center justify-center font-extrabold"
                    style={{ color: form.brand_primary }}>{form.mono || (form.name || '?').slice(0, 2).toUpperCase()}</span>
                  <div>
                    <div className="font-bold text-sm">{form.name || tt('שם המלון', 'Hotel name')}</div>
                    <div className="text-[10px] tracking-widest opacity-75">GUEST CONNECT</div>
                  </div>
                  <span className="ms-auto px-3 py-1 rounded-full text-xs font-bold" style={{ background: form.brand_secondary, color: '#fff' }}>{tt('תצוגה', 'Preview')}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-5 flex-wrap">
                <button onClick={save} disabled={saving}
                  className="px-5 py-2.5 rounded-xl bg-[var(--color-moca-bolt)] text-white font-bold text-sm hover:opacity-90 disabled:opacity-60">
                  {saving ? tt('שומר…', 'Saving…') : isNew ? tt('יצירת פורטל', 'Create portal') : tt('שמירה', 'Save')}
                </button>
                {!isNew && (
                  <>
                    <a href={`/guest/${form.slug}`} target="_blank" rel="noopener"
                      className="px-4 py-2.5 rounded-xl border border-[var(--color-moca-border)] text-[var(--color-moca-bolt)] font-bold text-sm hover:border-[var(--color-moca-bolt)]">
                      {tt('פתח פורטל ↗', 'Open portal ↗')}
                    </a>
                    <button onClick={copyLink} className="px-4 py-2.5 rounded-xl border border-[var(--color-moca-border)] text-[var(--color-moca-sub)] font-bold text-sm hover:border-[var(--color-moca-bolt)]">{tt('העתק קישור', 'Copy link')}</button>
                    <button onClick={remove} className="px-4 py-2.5 rounded-xl text-red-600 font-bold text-sm hover:bg-red-50 ms-auto">{tt('מחיקה', 'Delete')}</button>
                  </>
                )}
              </div>
            </div>

            {/* QR + analytics (existing hotels only) */}
            {!isNew && (
              <div className="grid md:grid-cols-[220px_1fr] gap-5 items-start">
                <div className="bg-white rounded-2xl border border-[var(--color-moca-border)] shadow-sm p-5 text-center">
                  <div className="text-sm font-extrabold text-[var(--color-moca-dark)] mb-3">{tt('קוד QR לחדר', 'Room QR code')}</div>
                  <img src={api.guestQrUrl(form.slug, PUBLIC_ORIGIN)} alt="QR" className="w-40 h-40 mx-auto rounded-lg border border-[var(--color-moca-border)]" />
                  <button onClick={downloadQr} className="mt-3 w-full px-3 py-2 rounded-xl bg-[var(--color-moca-cream)] text-[var(--color-moca-bolt)] font-bold text-sm hover:opacity-90">{tt('הורדת SVG להדפסה', 'Download SVG for print')}</button>
                  <div className="text-[11px] text-[var(--color-moca-muted)] mt-2 break-all">{portalUrl}</div>
                </div>

                <div className="bg-white rounded-2xl border border-[var(--color-moca-border)] shadow-sm p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="text-sm font-extrabold text-[var(--color-moca-dark)]">{tt('אנליטיקה (אנונימי)', 'Analytics (anonymous)')}</div>
                    <select className="text-sm border border-[var(--color-moca-border)] rounded-lg px-2 py-1 bg-white"
                      value={days} onChange={(e) => setDays(+e.target.value)}>
                      <option value={7}>{tt('7 ימים', '7 days')}</option>
                      <option value={30}>{tt('30 ימים', '30 days')}</option>
                      <option value={90}>{tt('90 ימים', '90 days')}</option>
                      <option value={0}>{tt('מאז ומתמיד', 'All time')}</option>
                    </select>
                  </div>
                  {!analytics ? (
                    <div className="text-sm text-[var(--color-moca-sub)]">{tt('טוען…', 'Loading…')}</div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <Stat label={tt('פתיחות', 'Opens')} value={analytics.funnel.opens} />
                        <Stat label={tt('סריקות QR', 'QR scans')} value={analytics.totals.scan} />
                        <Stat label={tt('השוואות', 'Comparisons')} value={analytics.funnel.engaged} />
                        <Stat label={tt('רכישות (קליקים)', 'Purchases (clicks)')} value={analytics.funnel.clicks} accent="var(--color-moca-down)" />
                      </div>
                      <FunnelRow f={analytics.funnel} />
                      <div className="grid sm:grid-cols-2 gap-4 mt-4">
                        <MiniBars title={tt('ספקים מובילים (קליקים)', 'Top providers (clicks)')} rows={analytics.by_provider.map((p) => ({ label: p.provider, n: p.clicks }))} empty={tt('אין קליקים עדיין', 'No clicks yet')} />
                        <MiniBars title={tt('שפת אורחים', 'Guest language')} rows={analytics.by_lang.map((p) => ({ label: p.lang, n: p.count }))} empty={tt('אין נתונים עדיין', 'No data yet')} />
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-[var(--color-moca-border)] shadow-sm p-10 text-center text-[var(--color-moca-sub)]">
            {tt('בחרו פורטל מהרשימה או צרו פורטל חדש כדי להתחיל.', 'Select a portal from the list or create a new one to get started.')}
          </div>
        )}
      </div>

      <style>{`#root .inp{width:100%;font-size:14px;padding:9px 11px;border:1.5px solid var(--color-moca-border);border-radius:10px;background:var(--color-moca-bg);color:var(--color-moca-text)}
        #root .inp:focus{outline:none;border-color:var(--color-moca-bolt)}
        #root .inp:disabled{opacity:.6}`}</style>
    </div>
  )
}

function Field({ label, full, children }) {
  return (
    <div className={full ? 'sm:col-span-2' : ''}>
      <label className="block text-xs font-bold text-[var(--color-moca-text)] mb-1.5">{label}</label>
      {children}
    </div>
  )
}

function ColorInput({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <input type="color" value={value || '#000000'} onChange={(e) => onChange(e.target.value)}
        className="w-10 h-9 rounded-lg border border-[var(--color-moca-border)] bg-white cursor-pointer flex-none" />
      <input className="inp font-mono" value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder="#26170f" />
    </div>
  )
}

function FunnelRow({ f }) {
  const { tt } = useLang()
  const max = Math.max(f.opens, 1)
  const rows = [
    { l: tt('פתיחות', 'Opens'), n: f.opens }, { l: tt('השוואות', 'Comparisons'), n: f.engaged }, { l: tt('רכישות', 'Purchases'), n: f.clicks },
  ]
  return (
    <div className="mt-4 space-y-2">
      {rows.map((r) => (
        <div key={r.l}>
          <div className="flex justify-between text-xs font-bold text-[var(--color-moca-text)] mb-1">
            <span>{r.l}</span><span className="text-[var(--color-moca-sub)]">{r.n} · {Math.round((r.n / max) * 100)}%</span>
          </div>
          <div className="h-3 rounded-full bg-[var(--color-moca-cream)] overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${(r.n / max) * 100}%`, background: 'linear-gradient(90deg,var(--color-moca-bolt),var(--color-moca-hot))' }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function MiniBars({ title, rows, empty }) {
  const max = Math.max(...rows.map((r) => r.n), 1)
  return (
    <div>
      <div className="text-xs font-extrabold text-[var(--color-moca-dark)] mb-2">{title}</div>
      {rows.length === 0 ? (
        <div className="text-xs text-[var(--color-moca-muted)]">{empty}</div>
      ) : (
        <div className="space-y-1.5">
          {rows.slice(0, 6).map((r) => (
            <div key={r.label} className="flex items-center gap-2 text-xs font-bold">
              <span className="w-24 truncate text-[var(--color-moca-text)]">{r.label}</span>
              <div className="flex-1 h-2.5 rounded-full bg-[var(--color-moca-cream)] overflow-hidden">
                <div className="h-full rounded-full bg-[var(--color-moca-bolt)]" style={{ width: `${(r.n / max) * 100}%` }} />
              </div>
              <span className="w-8 text-[var(--color-moca-sub)] text-end">{r.n}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
