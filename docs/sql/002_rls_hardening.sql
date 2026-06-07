-- ============================================================================
-- Migration 002 — RLS hardening for user_roles & workspaces
-- Target: Supabase Postgres (public schema). Run once via Supabase SQL Editor.
-- Idempotent — safe to re-run.
--
-- WHY THIS EXISTS
--   001 created `user_roles` / `workspaces` but defined no RLS. RLS was later
--   added in the Supabase dashboard and was MISCONFIGURED:
--     • user_roles had `allow_select USING (true)` → the public anon key (which
--       ships in the frontend JS bundle) could read EVERY user_id / role /
--       workspace_id, including which account is super_admin.
--     • user_roles had `allow_update_by_service USING (auth.uid() = user_id)`
--       and the `authenticated` role held UPDATE on the `role` column → ANY
--       logged-in user could PATCH their own row to role='super_admin' (the
--       Flask backend trusts this table for require_super_admin). Full privesc.
--   Discovered + fixed live on 2026-06-07; this file codifies that fix so a
--   fresh environment (or a re-run of 001) cannot silently reopen the hole.
--
-- WHY REVOKE IS SAFE
--   The Flask backend reads/writes these tables via a PRIVILEGED (postgres)
--   connection that BYPASSES RLS, and the React frontend NEVER queries them
--   directly (all access goes through Flask). So the PostgREST roles `anon`
--   and `authenticated` need ZERO direct access. The new-user trigger
--   handle_new_user_roles() is SECURITY DEFINER, so it keeps working too.
-- ============================================================================

-- 1. Remove all direct client (PostgREST) access — the decisive fix.
REVOKE ALL ON public.user_roles FROM anon, authenticated;
REVOKE ALL ON public.workspaces  FROM anon, authenticated;

-- 2. Drop the permissive policies (now moot without grants; dropping them means
--    a future accidental re-GRANT cannot silently re-expose the data).
DROP POLICY IF EXISTS allow_select            ON public.user_roles;
DROP POLICY IF EXISTS allow_update_by_service ON public.user_roles;
DROP POLICY IF EXISTS allow_insert_own        ON public.user_roles;

-- 3. Keep RLS enabled (deny-by-default) as defense in depth.
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces  ENABLE ROW LEVEL SECURITY;

-- ── Verification (run with the public anon key — all must be denied) ─────────
--   curl "$SUPABASE_URL/rest/v1/user_roles?select=*" -H "apikey: $ANON" -H "Authorization: Bearer $ANON"
--     → {"code":"42501", ... "permission denied for table user_roles"} (HTTP 401)
--   curl "$SUPABASE_URL/rest/v1/workspaces?select=*"  -H "apikey: $ANON" -H "Authorization: Bearer $ANON"
--     → permission denied (HTTP 401)
-- The Flask backend (privileged connection) is unaffected — role resolution
-- via /api/my-context keeps working.
