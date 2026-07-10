import { useState } from 'react'
import { useLang } from '../hooks/useLanguage'

// Standalone helper (not a component) — can't use the useLang hook, so it reads
// the current UI language straight from localStorage (same key as useLanguage).
function _logoLang() {
  try { return localStorage.getItem('moca_lang') === 'en' ? 'en' : 'he' } catch { return 'he' }
}
function _logoT(he, en) { return _logoLang() === 'en' ? en : he }

// Logo upload limits. The logo is stored inline in brand_config (Supabase) as a
// data: URI, so we resize raster images down to a small bounding box to keep the
// workspace row tiny (it's fetched on every auth/context load). SVGs are vectors —
// stored as-is so they stay crisp at any size.
const LOGO_MAX_W = 480          // px — bounding box for resized raster logos
const LOGO_MAX_H = 160          // px
const LOGO_MAX_SRC_BYTES = 4 * 1024 * 1024   // reject source files larger than 4MB
const LOGO_MAX_SVG_BYTES = 256 * 1024        // reject SVGs larger than 256KB (kept inline as-is)

// Read a user-picked image file and return a compact data: URI suitable for storing
// in brand_config.logo_url. Raster images are drawn to a canvas at a bounded size and
// re-encoded as PNG (preserves transparency); SVGs are returned verbatim.
export function fileToLogoDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) return reject(new Error(_logoT('הקובץ חייב להיות תמונה', 'The file must be an image')))

    if (file.type === 'image/svg+xml') {
      if (file.size > LOGO_MAX_SVG_BYTES) return reject(new Error(_logoT('קובץ ה-SVG גדול מדי (מקסימום 256KB)', 'The SVG file is too large (max 256KB)')))
      const r = new FileReader()
      r.onload = () => resolve(r.result)                 // data:image/svg+xml;base64,...
      r.onerror = () => reject(new Error(_logoT('קריאת הקובץ נכשלה', 'Failed to read the file')))
      r.readAsDataURL(file)
      return
    }

    if (file.size > LOGO_MAX_SRC_BYTES) return reject(new Error(_logoT('הקובץ גדול מדי (מקסימום 4MB)', 'The file is too large (max 4MB)')))
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      const scale = Math.min(1, LOGO_MAX_W / img.width, LOGO_MAX_H / img.height)
      const w = Math.max(1, Math.round(img.width * scale))
      const h = Math.max(1, Math.round(img.height * scale))
      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      canvas.getContext('2d').drawImage(img, 0, 0, w, h)
      try {
        resolve(canvas.toDataURL('image/png'))
      } catch {
        reject(new Error(_logoT('עיבוד התמונה נכשל', 'Image processing failed')))
      }
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error(_logoT('טעינת התמונה נכשלה', 'Image loading failed'))) }
    img.src = url
  })
}

// Logo input: a URL field for hosted images PLUS a file picker that inlines the chosen
// file as a resized data: URI. When a file has been uploaded the raw (long) data URI is
// hidden behind a chip instead of dumping base64 into the text box. The value flows back
// through `onChange(value)` — store it in brand_config.logo_url as-is.
export default function LogoField({ value, onChange }) {
  const { tt } = useLang()
  const [busy, setBusy] = useState(false)
  const [err, setErr]   = useState(null)
  const isData = (value || '').startsWith('data:')

  const pick = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''                                  // allow re-selecting the same file
    if (!file) return
    setErr(null); setBusy(true)
    try {
      onChange(await fileToLogoDataUrl(file))
    } catch (ex) {
      setErr(ex.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2">
      {isData ? (
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 rounded bg-green-50 text-green-700 border border-green-200 text-xs">✓ {tt('קובץ לוגו הועלה', 'Logo file uploaded')}</span>
          <button type="button" onClick={() => onChange('')} className="text-xs text-gray-400 hover:text-red-500">{tt('נקה', 'Clear')}</button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <input
            type="url"
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder="https://..."
            className="flex-1 px-3 py-1.5 text-sm border border-moca-border rounded"
            dir="ltr"
          />
          {value && (
            <button type="button" onClick={() => onChange('')} className="text-xs text-gray-400 hover:text-red-500">{tt('נקה', 'Clear')}</button>
          )}
        </div>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <label className={`inline-flex items-center gap-1.5 cursor-pointer text-xs px-3 py-1.5 rounded bg-moca-cream border border-moca-border/50 text-moca-sub hover:bg-moca-sand transition-colors ${busy ? 'opacity-50 pointer-events-none' : ''}`}>
          {busy ? tt('מעלה…', 'Uploading…') : (isData ? tt('החלף קובץ', 'Replace file') : tt('או העלה קובץ מהמחשב', 'Or upload a file from your computer'))}
          <input type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif" onChange={pick} className="hidden" disabled={busy} />
        </label>
        <span className="text-[11px] text-gray-400">PNG · SVG · JPG - {tt('יוקטן אוטומטית', 'auto-resized')}</span>
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
    </div>
  )
}
