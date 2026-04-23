-- ============================================================================
-- Migration 001 — Workspaces & multi-tenant foundation
-- Target: Supabase Postgres (public schema)
-- Run once via Supabase SQL Editor. Idempotent.
--
-- What this does:
--   1. Creates `workspaces` table (one row per MVNO customer)
--   2. Seeds a default 'moca-internal' workspace for existing users
--   3. Adds `workspace_id` to `user_roles` and backfills it
--   4. Adds 'super_admin' as a valid role (cross-workspace access)
--   5. Trigger that gives every new user access to 'moca-internal' by default
--      (until we disable that behavior and invite users explicitly)
-- ============================================================================

-- ── 1. workspaces table ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.workspaces (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                TEXT        UNIQUE NOT NULL,      -- 'partner', 'cellcom', 'moca-internal'
  name                TEXT        NOT NULL,             -- 'Partner Intelligence'
  mvno_carrier        TEXT,                             -- 'partner' | NULL for internal
  brand_config        JSONB       NOT NULL DEFAULT '{}'::jsonb,
  feature_flags       JSONB       NOT NULL DEFAULT '{}'::jsonb,
  hide_self_carrier   BOOLEAN     NOT NULL DEFAULT true,
  active              BOOLEAN     NOT NULL DEFAULT true,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.workspaces IS
  'Per-customer configuration. One row per MVNO buying the MOCA product.';
COMMENT ON COLUMN public.workspaces.mvno_carrier IS
  'Carrier id of the workspace owner (matches carrier ids used in scraper.py / app.py CARRIER_DISPLAY). NULL for moca-internal.';
COMMENT ON COLUMN public.workspaces.brand_config IS
  'JSON: {logo_url, primary_color, secondary_color, app_title}';
COMMENT ON COLUMN public.workspaces.feature_flags IS
  'JSON: {chat: bool, news: bool, executive_summary: bool, alerts: bool, ...}';

-- ── 2. Seed default workspace ──────────────────────────────────────────────
INSERT INTO public.workspaces (slug, name, mvno_carrier, hide_self_carrier)
VALUES ('moca-internal', 'MOCA Internal', NULL, false)
ON CONFLICT (slug) DO NOTHING;

-- ── 3. Add workspace_id to user_roles ──────────────────────────────────────
ALTER TABLE public.user_roles
  ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES public.workspaces(id);

-- Backfill existing users to moca-internal
UPDATE public.user_roles
SET workspace_id = (SELECT id FROM public.workspaces WHERE slug = 'moca-internal')
WHERE workspace_id IS NULL;

-- ── 4. Role values ─────────────────────────────────────────────────────────
-- Valid roles:
--   super_admin — cross-workspace (the MOCA operator). workspace_id MAY be NULL.
--   admin       — admin inside one workspace (can manage users of that workspace)
--   viewer      — read-only inside one workspace
-- If an older CHECK constraint existed (admin/viewer only), replace it:
ALTER TABLE public.user_roles DROP CONSTRAINT IF EXISTS user_roles_role_check;
ALTER TABLE public.user_roles
  ADD CONSTRAINT user_roles_role_check
  CHECK (role IN ('super_admin', 'admin', 'viewer'));

-- ── 5. Auto-provision new sign-ups into moca-internal ──────────────────────
-- Safe default: everyone who signs up lands in moca-internal as 'viewer'.
-- You (super_admin) can then reassign them to a customer workspace.
CREATE OR REPLACE FUNCTION public.handle_new_user_roles()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.user_roles (user_id, role, workspace_id)
  VALUES (
    NEW.id,
    'viewer',
    (SELECT id FROM public.workspaces WHERE slug = 'moca-internal')
  )
  ON CONFLICT (user_id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created_assign_workspace ON auth.users;
CREATE TRIGGER on_auth_user_created_assign_workspace
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user_roles();

-- ── Verification queries (run manually to sanity-check) ────────────────────
-- SELECT * FROM public.workspaces;
-- SELECT u.email, r.role, w.slug FROM auth.users u
--   JOIN public.user_roles r ON r.user_id = u.id
--   LEFT JOIN public.workspaces w ON w.id = r.workspace_id
--   ORDER BY r.role;
