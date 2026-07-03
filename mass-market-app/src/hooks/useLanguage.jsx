import { createContext, useContext, useState, useEffect, useCallback } from 'react'

/**
 * Global UI language (Hebrew ⇄ English) for the internal MOCA dashboard.
 *
 * Mirrors the B2C page's he/en pattern but applies it app-wide: the chosen
 * language flips the whole document direction (rtl for עברית, ltr for English)
 * and is persisted so it survives reloads.
 *
 * Two ways to translate:
 *   const { tt } = useLang()
 *   tt('שלום', 'Hello')          // inline he/en pair — co-located, no dict sync
 *   const { t } = useLang()
 *   t('nav.dashboard')           // central dictionary lookup (shared strings)
 *
 * Prefer `tt` for one-off page copy; use `t` only for strings shared across
 * many components (kept in DICT below).
 */

const LangContext = createContext(null)
const STORAGE_KEY = 'moca_lang'

// Small central dictionary for strings that recur across the chrome. Most copy
// uses inline tt() instead — this is only for truly shared labels.
const DICT = {
  'common.live':        { he: 'LIVE', en: 'LIVE' },
  'common.search':      { he: 'חיפוש…', en: 'Search…' },
  'common.searchAdv':   { he: 'חיפוש מתקדם', en: 'Advanced search' },
  'common.alerts':      { he: 'התראות', en: 'Alerts' },
  'common.profile':     { he: 'פרופיל', en: 'Profile' },
  'common.signOut':     { he: 'יציאה', en: 'Sign out' },
}

function initialLang() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'he' || saved === 'en') return saved
  } catch { /* localStorage unavailable */ }
  return 'he'
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(initialLang)
  const dir = lang === 'he' ? 'rtl' : 'ltr'

  useEffect(() => {
    const el = document.documentElement
    el.setAttribute('lang', lang)
    el.setAttribute('dir', dir)
    // Inline style overrides the `html { direction: rtl }` rule in index.css.
    el.style.direction = dir
    try { localStorage.setItem(STORAGE_KEY, lang) } catch { /* ignore */ }
  }, [lang, dir])

  const setLang = useCallback((l) => setLangState(l === 'en' ? 'en' : 'he'), [])
  const toggle = useCallback(() => setLangState((l) => (l === 'he' ? 'en' : 'he')), [])
  const tt = useCallback((he, en) => (lang === 'he' ? he : (en != null ? en : he)), [lang])
  const t = useCallback((key) => {
    const entry = DICT[key]
    if (!entry) return key
    return entry[lang] != null ? entry[lang] : (entry.he != null ? entry.he : key)
  }, [lang])

  return (
    <LangContext.Provider value={{ lang, dir, setLang, toggle, t, tt }}>
      {children}
    </LangContext.Provider>
  )
}

export function useLang() {
  const ctx = useContext(LangContext)
  if (!ctx) {
    // Safe fallback for anything rendered outside the provider — default HE.
    return {
      lang: 'he',
      dir: 'rtl',
      setLang: () => {},
      toggle: () => {},
      t: (k) => k,
      tt: (he) => he,
    }
  }
  return ctx
}
