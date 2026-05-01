import { createClient } from '@supabase/supabase-js'

// Supabase anon key is public (safe to include in client code), but it MUST
// come from VITE_SUPABASE_ANON_KEY at build time. The previous hardcoded
// fallback was an HS256-signed key from before the 2026-04-25 hardening
// sprint that migrated the project to ES256 — that fallback is no longer
// valid and would mask config errors. Fail loud instead.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY

let supabase = null
if (!supabaseUrl || !supabaseKey) {
  // Don't throw — useAuth.jsx handles the null client gracefully (dev mode
  // can still operate via VITE_DEV_AUTH=true). But warn loudly so a missing
  // env var in production doesn't silently fall through to a stale key.
  // eslint-disable-next-line no-console
  console.error(
    '[supabase] VITE_SUPABASE_URL and/or VITE_SUPABASE_ANON_KEY are missing. ' +
    'Set them in .env for local dev or in your hosting provider env vars for production.'
  )
} else {
  supabase = createClient(supabaseUrl, supabaseKey)
}

export { supabase }
