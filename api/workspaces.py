"""Super-admin + workspace-admin management: users (direct-DB provisioning), workspaces, invites, digest trigger, branding, Slack test, audit log.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import json
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
logger = core.logger
from flask import Blueprint
bp = Blueprint("workspaces", __name__)


@bp.route("/api/users")
@core.require_admin
@core.limiter.limit("20 per minute")
def api_get_users():
    """List users from Supabase via direct DB connection.

    Cross-tenant scoping: a workspace `admin` sees only users assigned to their
    OWN workspace; super_admin (and the trusted server-admin key) get the full
    cross-workspace list. Without this scope, any workspace admin could read
    every user's email + role across all carrier workspaces — a cross-tenant
    info leak. Mirrors the ownership pattern in _can_manage_workspace_users.
    """
    try:
        # Decide scope from the caller's role. The dedicated server-admin key
        # (_is_server_admin_request) is the trusted MOCA operator → full list,
        # same as super_admin. scope_ws_id is None when the full list is allowed.
        scope_ws_id = None
        if not core._is_server_admin_request():
            ctx = core._get_user_context(core._current_user_email())
            if ctx.get('role') != 'super_admin':
                scope_ws_id = ctx.get('workspace_id')
                if not scope_ws_id:
                    # Workspace admin with no workspace assigned: show nothing
                    # rather than leaking the global user list.
                    return jsonify([])

        conn = core._supabase_conn()
        cur = conn.cursor()
        if scope_ws_id is None:
            cur.execute("""
                SELECT u.id, u.email, u.created_at, COALESCE(r.role, 'viewer') as role, u.last_sign_in_at
                FROM auth.users u
                LEFT JOIN public.user_roles r ON u.id = r.user_id
                ORDER BY u.created_at DESC
            """)
        else:
            cur.execute("""
                SELECT u.id, u.email, u.created_at, COALESCE(r.role, 'viewer') as role, u.last_sign_in_at
                FROM public.user_roles r
                JOIN auth.users u ON u.id = r.user_id
                WHERE r.workspace_id = %s
                ORDER BY u.created_at DESC
            """, (scope_ws_id,))
        users = [{'id': str(row[0]), 'email': row[1], 'created_at': str(row[2]), 'role': row[3], 'last_sign_in_at': str(row[4]) if row[4] else None} for row in cur.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        logger.error(f"get users failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/users", methods=["POST"])
@core.require_super_admin
@core.limiter.limit("10 per minute")
def api_create_user():
    """Create a new user directly in Supabase Postgres. super_admin / server-admin-key ONLY.

    Provisions the auth identity by writing auth.users + auth.identities + a
    (workspace-less) public.user_roles row in one transaction — the same thing
    GoTrue's admin API does internally, with the email pre-confirmed.

    We deliberately do NOT use the public /auth/v1/signup flow anymore: it sends
    a confirmation email on every create (which we then redundantly force-
    confirmed anyway), and Supabase's shared email sender rate-limits those to a
    few per hour — so onboarding more than ~2 users in a row failed with
    "email rate limit exceeded" (HTTP 429 -> generic "Failed to create user").
    Direct provisioning sends NO email; onboarding mail is our own Welcome email,
    fired by the workspace-assign step (send_welcome_email).

    Restricted to the MOCA operator — a workspace `admin` must never mint
    accounts (the role row here has no workspace_id, i.e. a global/workspace-less
    role, and there's no cross-tenant ownership check). Workspace admins add
    people to their OWN workspace via POST /api/workspaces/<id>/users (assign an
    existing user) or an invite link — both gated by _can_manage_workspace_users.
    """
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role', 'viewer')
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if role not in ('admin', 'viewer'):
        # Never allow minting a super_admin via the API — that role is DB-only.
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    conn = None
    try:
        import uuid as _uuid
        user_id = str(_uuid.uuid4())
        conn = core._supabase_conn()
        cur = conn.cursor()
        # Reject duplicates up front (mirrors GoTrue's 422 with a clear message).
        cur.execute("SELECT 1 FROM auth.users WHERE LOWER(email) = %s", (email,))
        if cur.fetchone():
            conn.close()
            return jsonify({"error": f"user {email} already exists"}), 409
        # 1) auth.users — email pre-confirmed; confirmed_at is a GENERATED column
        #    (omit it); password hashed with bcrypt (cost 10) via pgcrypto.
        cur.execute("""
            INSERT INTO auth.users (
                instance_id, id, aud, role, email, encrypted_password,
                email_confirmed_at, confirmation_token, recovery_token,
                email_change_token_new, email_change, email_change_token_current,
                phone_change, phone_change_token, reauthentication_token,
                raw_app_meta_data, raw_user_meta_data,
                created_at, updated_at, email_change_confirm_status,
                is_sso_user, is_anonymous
            ) VALUES (
                '00000000-0000-0000-0000-000000000000', %s,
                'authenticated', 'authenticated', %s, crypt(%s, gen_salt('bf', 10)),
                now(), '', '', '', '', '', '', '', '',
                '{"provider":"email","providers":["email"]}'::jsonb,
                jsonb_build_object('sub', %s, 'email', %s, 'email_verified', true, 'phone_verified', false),
                now(), now(), 0, false, false
            )
        """, (user_id, email, password, user_id, email))
        # 2) auth.identities — the `email` column is GENERATED (omit it).
        cur.execute("""
            INSERT INTO auth.identities (
                id, provider_id, user_id, identity_data, provider,
                last_sign_in_at, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), %s, %s,
                jsonb_build_object('sub', %s, 'email', %s, 'email_verified', true, 'phone_verified', false),
                'email', now(), now(), now()
            )
        """, (user_id, user_id, user_id, email))
        # 3) global (workspace-less) role row — workspace assignment happens later.
        cur.execute("INSERT INTO public.user_roles (user_id, role) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role", (user_id, role))
        conn.commit()
        conn.close()
        logger.info(f"AUDIT create_user: email={email!r} role={role!r} new_user_id={user_id!r} by_ip={request.remote_addr}")
        return jsonify({"status": "created", "user_id": user_id}), 201
    except Exception as e:
        try:
            if conn:
                conn.rollback()
                conn.close()
        except Exception:
            pass
        logger.error(f"create user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/users/<user_id>", methods=["DELETE"])
@core.require_super_admin
@core.limiter.limit("10 per minute")
def api_delete_user(user_id):
    """Delete a user from Supabase. super_admin / server-admin-key ONLY.

    Operates on an arbitrary user id with no workspace-ownership check, so a
    workspace `admin` must not reach it — otherwise a Partner admin could delete
    a Cellcom user (cross-tenant). Workspace admins remove members from their own
    workspace via DELETE /api/workspaces/<id>/users/<uid> (gated by
    _can_manage_workspace_users), which only un-assigns within that workspace.
    """
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute('DELETE FROM public.user_roles WHERE user_id = %s', (user_id,))
        cur.execute('DELETE FROM auth.users WHERE id = %s', (user_id,))
        conn.close()
        logger.info(f"AUDIT delete_user: user_id={user_id!r} by_ip={request.remote_addr}")
        return jsonify({"status": "deleted"})
    except Exception as e:
        logger.error(f"delete user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/users/<user_id>/role", methods=["POST"])
@core.require_super_admin
@core.limiter.limit("20 per minute")
def api_update_user_role(user_id):
    """Update a user's role. super_admin / server-admin-key ONLY.

    Re-roles an arbitrary user id with no workspace-ownership check, so a
    workspace `admin` must not reach it (cross-tenant: a Partner admin could
    promote/demote a Cellcom user). Workspace admins set a member's role within
    their own workspace via POST /api/workspaces/<id>/users (gated by
    _can_manage_workspace_users). The last-super_admin guard below still applies.
    """
    data = request.get_json(force=True)
    role = data.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be admin or viewer"}), 400
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        # Guard: don't remove the last super_admin. This endpoint can only set
        # admin/viewer, so demoting the final super_admin would lock everyone out
        # of super-admin-only management with no UI path to restore it.
        if core._user_is_super_admin(cur, user_id):
            cur.execute("SELECT COUNT(*) FROM public.user_roles WHERE role = 'super_admin'")
            if cur.fetchone()[0] <= 1:
                conn.close()
                return jsonify({"error": "לא ניתן להוריד את ה-super_admin האחרון במערכת — חייב להישאר לפחות אחד."}), 409
        cur.execute("INSERT INTO public.user_roles (user_id, role) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET role = %s", (user_id, role, role))
        conn.close()
        logger.info(f"AUDIT update_role: user_id={user_id!r} new_role={role!r} by_ip={request.remote_addr}")
        return jsonify({"status": "updated", "role": role})
    except Exception as e:
        logger.error(f"update role failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/users/<user_id>/password", methods=["POST"])
@core.require_super_admin
@core.limiter.limit("20 per minute")
def api_set_user_password(user_id):
    """Set a user's password directly. super_admin / server-admin-key ONLY.

    Admin-driven reset for a user who's locked out — writes the bcrypt hash
    straight to auth.users (same mechanism as api_create_user), so it sends NO
    email and isn't subject to Supabase's email rate limit. The user can sign in
    with the new password immediately. No workspace-ownership check (mirrors the
    other bare /api/users* writes), so it's operator-only; workspace admins
    manage their own team via the workspace endpoints.
    """
    data = request.get_json(force=True) or {}
    password = data.get('password') or ''
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    conn = None
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("UPDATE auth.users SET encrypted_password = crypt(%s, gen_salt('bf', 10)), updated_at = now() WHERE id = %s", (password, user_id))
        updated = cur.rowcount
        conn.close()
        if not updated:
            return jsonify({"error": "user not found"}), 404
        logger.info(f"AUDIT set_user_password: user_id={user_id!r} by_ip={request.remote_addr}")
        return jsonify({"status": "updated"})
    except Exception as e:
        try:
            if conn:
                conn.close()
        except Exception:
            pass
        logger.error(f"set user password failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces", methods=["GET"])
@core.require_super_admin
@core.limiter.limit("30 per minute")
def api_list_workspaces():
    """List all workspaces with user count, last login, trial info, and monthly refresh count."""
    try:
        conn = core._supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT w.id, w.slug, w.name, w.mvno_carrier,
                   w.brand_config, w.feature_flags,
                   w.hide_self_carrier, w.active, w.created_at,
                   COUNT(r.user_id) AS user_count,
                   MAX(u.last_sign_in_at) AS last_login,
                   w.trial_ends_at,
                   COALESCE(w.visible_carriers, '[]'::jsonb),
                   COALESCE(w.digest_frequency, 'weekly')
            FROM public.workspaces w
            LEFT JOIN public.user_roles r ON r.workspace_id = w.id
            LEFT JOIN auth.users u ON u.id = r.user_id
            GROUP BY w.id
            ORDER BY w.created_at ASC
        """)
        rows = cur.fetchall()
        conn.close()

        # Fetch monthly refresh counts from SQLite for all workspaces
        from datetime import datetime as _dt, timezone as _tz
        month_prefix = _dt.now(_tz.utc).strftime('%Y-%m')
        all_entries = core.get_audit_log(limit=2000, db_path=core._db_path())
        refresh_by_ws = {}
        for e in all_entries:
            if e['action'] == 'refresh_triggered' and (e['created_at'] or '').startswith(month_prefix):
                ws = e['workspace_id'] or ''
                refresh_by_ws[ws] = refresh_by_ws.get(ws, 0) + 1

        workspaces = []
        for row in rows:
            ws_id = str(row[0])
            trial_ends_at = row[11]
            trial_expired = False
            if trial_ends_at:
                now_utc = _dt.now(_tz.utc)
                te = trial_ends_at if hasattr(trial_ends_at, 'tzinfo') else trial_ends_at.replace(tzinfo=_tz.utc)
                trial_expired = now_utc > te
            vc_raw = row[12]
            vc_list = json.loads(vc_raw) if isinstance(vc_raw, str) else (list(vc_raw) if vc_raw else [])
            workspaces.append({
                'id':                ws_id,
                'slug':              row[1],
                'name':              row[2],
                'mvno_carrier':      row[3],
                'brand_config':      row[4] or {},
                'feature_flags':     row[5] or {},
                'hide_self_carrier': bool(row[6]),
                'active':            bool(row[7]),
                'created_at':        str(row[8]),
                'user_count':        row[9],
                'last_login':        row[10].isoformat() if row[10] else None,
                'trial_ends_at':     trial_ends_at.isoformat() if trial_ends_at else None,
                'trial_expired':     trial_expired,
                'visible_carriers':  vc_list,
                'digest_frequency':  row[13] or 'weekly',
                'refresh_count_month': refresh_by_ws.get(ws_id, 0),
                'refresh_limit':       None if row[1] == 'moca-internal' else core.MONTHLY_REFRESH_LIMIT,
            })
        return jsonify(workspaces)
    except Exception as e:
        logger.error(f"list workspaces failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces", methods=["POST"])
@core.require_super_admin
@core.limiter.limit("10 per minute")
def api_create_workspace():
    """Create a new workspace. Body: {slug, name, mvno_carrier?, brand_config?,
    feature_flags?, hide_self_carrier?}."""
    data = request.get_json(force=True) or {}
    slug = (data.get('slug') or '').strip().lower()
    name = (data.get('name') or '').strip()
    if not slug or not name:
        return jsonify({"error": "slug and name are required"}), 400
    # slug: lowercase alphanumeric + hyphens, 2–40 chars
    import re as _re
    if not _re.fullmatch(r'[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?', slug):
        return jsonify({"error": "slug must be lowercase alphanumeric/hyphens (2-40 chars)"}), 400
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.workspaces (slug, name, mvno_carrier, brand_config,
                                           feature_flags, hide_self_carrier)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
            RETURNING id
        """, (
            slug, name, data.get('mvno_carrier') or None,
            json.dumps(data.get('brand_config') or {}),
            json.dumps(data.get('feature_flags') or {}),
            bool(data.get('hide_self_carrier', True)),
        ))
        new_id = str(cur.fetchone()[0])
        conn.close()
        actor = core._current_user_email() or ''
        core.log_audit('workspace_created', actor_email=actor, workspace_id=new_id,
                  details=f'slug={slug!r} name={name!r}', db_path=core._db_path())
        logger.info(f"AUDIT create_workspace: slug={slug!r} id={new_id} by_ip={request.remote_addr}")
        return jsonify({"status": "created", "id": new_id}), 201
    except Exception as e:
        msg = str(e)
        if 'unique' in msg.lower() or 'duplicate' in msg.lower():
            return jsonify({"error": f"slug '{slug}' already exists"}), 409
        logger.error(f"create workspace failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces/<workspace_id>", methods=["PATCH"])
@core.require_super_admin
@core.limiter.limit("20 per minute")
def api_update_workspace(workspace_id):
    """Update a workspace. Body may include any subset of: name, mvno_carrier,
    brand_config, feature_flags, hide_self_carrier, active."""
    data = request.get_json(force=True) or {}
    allowed = {'name', 'mvno_carrier', 'brand_config', 'feature_flags',
               'hide_self_carrier', 'active', 'trial_ends_at', 'visible_carriers',
               'digest_frequency'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "no updatable fields provided"}), 400
    if 'digest_frequency' in updates and updates['digest_frequency'] not in ('weekly', 'monthly', 'off'):
        return jsonify({"error": "digest_frequency must be weekly/monthly/off"}), 400
    sets, params = [], []
    for k, v in updates.items():
        if k in ('brand_config', 'feature_flags'):
            sets.append(f"{k} = %s::jsonb")
            params.append(json.dumps(v or {}))
        elif k == 'visible_carriers':
            sets.append(f"{k} = %s::jsonb")
            params.append(json.dumps(v or []))
        elif k in ('hide_self_carrier', 'active'):
            sets.append(f"{k} = %s")
            params.append(bool(v))
        else:
            sets.append(f"{k} = %s")
            params.append(v or None)
    params.append(workspace_id)
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            f"UPDATE public.workspaces SET {', '.join(sets)} WHERE id = %s",
            params
        )
        updated = cur.rowcount
        conn.close()
        if updated == 0:
            return jsonify({"error": "workspace not found"}), 404
        actor = core._current_user_email() or ''
        core.log_audit('workspace_updated', actor_email=actor, workspace_id=workspace_id,
                  details=str(list(updates.keys())), db_path=core._db_path())
        logger.info(f"AUDIT update_workspace: id={workspace_id} fields={list(updates.keys())}")
        return jsonify({"status": "updated"})
    except Exception as e:
        logger.error(f"update workspace failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces/<workspace_id>/users", methods=["GET"])
@core.require_auth
@core.limiter.limit("30 per minute")
def api_workspace_users(workspace_id):
    """List users assigned to a workspace."""
    if not core._can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    try:
        conn = core._supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.created_at, r.role, u.last_sign_in_at
            FROM public.user_roles r
            JOIN auth.users u ON u.id = r.user_id
            WHERE r.workspace_id = %s
            ORDER BY u.email
        """, (workspace_id,))
        users = [{
            'id':              str(row[0]),
            'email':           row[1],
            'created_at':      str(row[2]),
            'role':            row[3],
            'last_sign_in_at': str(row[4]) if row[4] else None,
        } for row in cur.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        logger.error(f"list workspace users failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces/<workspace_id>/users", methods=["POST"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_assign_workspace_user(workspace_id):
    """Assign an existing Supabase user (by email) to this workspace.
    Body: {email, role: 'admin'|'viewer'} (defaults to 'viewer')."""
    if not core._can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    role = data.get('role', 'viewer')
    if not email:
        return jsonify({"error": "email required"}), 400
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        # Look up user id
        cur.execute("SELECT id FROM auth.users WHERE LOWER(email) = %s", (email,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": f"no user with email {email!r}"}), 404
        user_id = row[0]
        # Guard: never demote a super_admin via workspace assignment. user_roles
        # has UNIQUE(user_id), so writing a workspace role here would overwrite
        # their global super_admin — a silent self-lockout (this endpoint only
        # grants admin/viewer, so it can't be reversed from the UI).
        if core._user_is_super_admin(cur, user_id):
            conn.close()
            return jsonify({"error": "לא ניתן לשייך משתמש בעל הרשאת super_admin לאזור — הפעולה הייתה מוחקת את ההרשאה הגלובלית שלו. לשינוי מכוון, השתמש בניהול התפקידים."}), 409
        # Verify workspace exists
        cur.execute("SELECT 1 FROM public.workspaces WHERE id = %s", (workspace_id,))
        if not cur.fetchone():
            conn.close()
            return jsonify({"error": "workspace not found"}), 404
        # Upsert role + workspace
        cur.execute("""
            INSERT INTO public.user_roles (user_id, role, workspace_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
              SET role = EXCLUDED.role, workspace_id = EXCLUDED.workspace_id
        """, (user_id, role, workspace_id))
        # Fetch workspace name for welcome email
        cur.execute("SELECT name FROM public.workspaces WHERE id = %s", (workspace_id,))
        ws_row = cur.fetchone()
        ws_name = ws_row[0] if ws_row else ''
        conn.close()
        actor = core._current_user_email() or ''
        core.log_audit('user_assigned', actor_email=actor, target_email=email,
                  workspace_id=workspace_id, details=f'role={role}', db_path=core._db_path())
        logger.info(f"AUDIT assign_workspace_user: email={email!r} workspace={workspace_id} role={role}")
        # Send welcome email in background (non-blocking)
        try:
            from notifier import send_welcome_email as _send_welcome
            import threading as _threading
            _threading.Thread(
                target=_send_welcome,
                args=(email, ws_name, role, core.load_config()),
                daemon=True,
            ).start()
        except Exception as _we:
            logger.warning(f"welcome email skipped: {_we}")
        return jsonify({"status": "assigned", "user_id": str(user_id)}), 201
    except Exception as e:
        logger.error(f"assign workspace user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces/<workspace_id>/users/<user_id>", methods=["DELETE"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_unassign_workspace_user(workspace_id, user_id):
    """Unassign a user from a workspace by moving them to 'moca-internal' as viewer.
    We never orphan users (NULL workspace_id is reserved for super_admin)."""
    if not core._can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT id FROM public.workspaces WHERE slug = 'moca-internal'")
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "moca-internal workspace missing"}), 500
        internal_id = row[0]
        cur.execute("""
            UPDATE public.user_roles
            SET workspace_id = %s, role = 'viewer'
            WHERE user_id = %s AND workspace_id = %s
        """, (internal_id, user_id, workspace_id))
        affected = cur.rowcount
        conn.close()
        if affected == 0:
            return jsonify({"error": "user not in this workspace"}), 404
        actor = core._current_user_email() or ''
        core.log_audit('user_removed', actor_email=actor, target_email=user_id,
                  workspace_id=workspace_id, details=f'moved to moca-internal',
                  db_path=core._db_path())
        logger.info(f"AUDIT unassign_workspace_user: user={user_id} from={workspace_id}")
        return jsonify({"status": "moved to moca-internal"})
    except Exception as e:
        logger.error(f"unassign workspace user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces/<workspace_id>/invite", methods=["POST"])
@core.require_auth
@core.limiter.limit("10 per minute")
def api_create_invite(workspace_id):
    """Create a single-use invite link for this workspace.
    Body: {role: 'admin'|'viewer'} — defaults to 'viewer'."""
    if not core._can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json(force=True) or {}
    role = data.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    creator = core._current_user_email() or ''
    token = core.create_workspace_invite(workspace_id, role=role, created_by=creator, db_path=core._db_path())
    core.log_audit('invite_created', actor_email=creator, workspace_id=workspace_id,
              details=f'role={role}', db_path=core._db_path())
    return jsonify({"token": token, "role": role}), 201


@bp.route("/api/workspaces/<workspace_id>/invite-bulk", methods=["POST"])
@core.require_auth
@core.limiter.limit("5 per minute")
def api_create_invite_bulk(workspace_id):
    """Bulk-create invite links. Body: {emails: [...], role: 'admin'|'viewer'}.
    Emails are only used as labels (the token itself is not bound to an email) —
    useful for onboarding a whole team at once with one copy-ready table."""
    if not core._can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json(force=True) or {}
    role = data.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    raw_emails = data.get('emails') or []
    if not isinstance(raw_emails, list) or not raw_emails:
        return jsonify({"error": "emails array required"}), 400
    if len(raw_emails) > 50:
        return jsonify({"error": "max 50 emails per batch"}), 400
    import re as _re
    email_rx = _re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    creator = core._current_user_email() or ''
    results = []
    seen = set()
    for raw in raw_emails:
        email = (raw or '').strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        if not email_rx.match(email):
            results.append({"email": email, "error": "invalid email"})
            continue
        try:
            token = core.create_workspace_invite(workspace_id, role=role, created_by=creator, db_path=core._db_path())
            results.append({"email": email, "token": token})
        except Exception as e:
            logger.error(f"bulk invite create failed for {email}: {e}")
            results.append({"email": email, "error": "could not create"})
    ok_count = sum(1 for r in results if r.get('token'))
    if ok_count > 0:
        core.log_audit('invite_created', actor_email=creator, workspace_id=workspace_id,
                  details=f'bulk: {ok_count} invites, role={role}', db_path=core._db_path())
    return jsonify({"role": role, "results": results, "created": ok_count}), 201


@bp.route("/api/invite/<token>", methods=["GET"])
@core.limiter.limit("30 per minute")
def api_get_invite(token):
    """Public — validate invite token and return workspace name + role."""
    from datetime import datetime as _dt, timezone as _tz
    invite = core.get_workspace_invite(token, db_path=core._db_path())
    if not invite:
        return jsonify({"error": "קישור לא תקין"}), 404
    if invite['used_at']:
        return jsonify({"error": "קישור זה כבר נוצל"}), 410
    if _dt.fromisoformat(invite['expires_at']) < _dt.now(_tz.utc):
        return jsonify({"error": "קישור פג תוקף"}), 410
    # Fetch workspace name
    try:
        conn = core._supabase_conn()
        cur = conn.cursor()
        cur.execute("SELECT name FROM public.workspaces WHERE id = %s", (invite['workspace_id'],))
        row = cur.fetchone()
        conn.close()
        ws_name = row[0] if row else ''
    except Exception:
        ws_name = ''
    return jsonify({"workspace_name": ws_name, "role": invite['role'],
                    "expires_at": invite['expires_at']})


@bp.route("/api/invite/<token>/accept", methods=["POST"])
@core.require_auth
@core.limiter.limit("10 per minute")
def api_accept_invite(token):
    """Authenticated user accepts an invite — assigns them to the workspace."""
    from datetime import datetime as _dt, timezone as _tz
    invite = core.get_workspace_invite(token, db_path=core._db_path())
    if not invite:
        return jsonify({"error": "קישור לא תקין"}), 404
    if invite['used_at']:
        return jsonify({"error": "קישור זה כבר נוצל"}), 410
    if _dt.fromisoformat(invite['expires_at']) < _dt.now(_tz.utc):
        return jsonify({"error": "קישור פג תוקף"}), 410

    email = core._current_user_email()
    if not email:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT id FROM auth.users WHERE LOWER(email) = %s", (email.lower(),))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "user not found"}), 404
        user_id = row[0]
        # Guard: a super_admin accepting a workspace invite must not be demoted
        # (UNIQUE(user_id) would overwrite their global role). Leave the invite
        # unused so it can still be redeemed by an intended workspace member.
        if core._user_is_super_admin(cur, user_id):
            conn.close()
            return jsonify({"error": "אתה super_admin — קישורי הזמנה אינם משנים את ההרשאה הגלובלית שלך."}), 409
        cur.execute("""
            INSERT INTO public.user_roles (user_id, role, workspace_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
              SET role = EXCLUDED.role, workspace_id = EXCLUDED.workspace_id
        """, (user_id, invite['role'], invite['workspace_id']))
        cur.execute("SELECT name FROM public.workspaces WHERE id = %s", (invite['workspace_id'],))
        ws_row = cur.fetchone()
        ws_name = ws_row[0] if ws_row else 'MOCA'
        conn.close()
        core.use_workspace_invite(token, used_by=email, db_path=core._db_path())
        core.log_audit('invite_accepted', actor_email=email, workspace_id=invite['workspace_id'],
                  details=f'role={invite["role"]}', db_path=core._db_path())
        # Send welcome email (same as manual assignment)
        try:
            from notifier import send_welcome_email as _send_welcome
            import threading as _threading
            _threading.Thread(
                target=_send_welcome,
                args=(email, ws_name, invite['role'], core.load_config()),
                daemon=True,
            ).start()
        except Exception as _we:
            logger.warning(f"invite welcome email skipped: {_we}")
        return jsonify({"status": "accepted", "role": invite['role'],
                        "workspace_id": invite['workspace_id']})
    except Exception as e:
        logger.error(f"accept invite failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspaces/<workspace_id>/trigger-digest", methods=["POST"])
@core.require_super_admin
@core.limiter.limit("5 per minute")
def api_trigger_digest(workspace_id):
    """Manually trigger the weekly digest for a specific workspace (super_admin only)."""
    from notifier import send_weekly_digest as _send_digest
    from db import get_history_changes as _ghc
    from datetime import datetime as _dt, timedelta as _td
    _cfg = core.load_config()
    _from = (_dt.now() - _td(days=7)).strftime('%Y-%m-%d')
    try:
        conn = core._supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT name, mvno_carrier, hide_self_carrier,
                   COALESCE(visible_carriers, '[]'::jsonb),
                   COALESCE(brand_config, '{}'::jsonb)
            FROM public.workspaces WHERE id = %s AND active = TRUE
        """, (workspace_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "workspace not found or inactive"}), 404
        ws_name, mvno_carrier, hide_self, vc_raw, bc_raw = row
        visible_carriers = json.loads(vc_raw) if isinstance(vc_raw, str) else (list(vc_raw) if vc_raw else [])
        brand_config = json.loads(bc_raw) if isinstance(bc_raw, str) else (dict(bc_raw) if bc_raw else {})
        cur.execute("""
            SELECT u.email FROM auth.users u
            JOIN public.user_roles r ON r.user_id = u.id
            WHERE r.workspace_id = %s AND COALESCE(r.digest_opt_out, FALSE) = FALSE
        """, (workspace_id,))
        emails = [r[0] for r in cur.fetchall() if r[0]]
        conn.close()
        if not emails:
            return jsonify({"error": "no users in workspace (or all opted out)"}), 400
        all_changes = []
        for ptype in ('domestic', 'abroad', 'global'):
            ch = _ghc('', ptype, _from, '', db_path=core._db_path())
            if visible_carriers:
                ch = [c for c in ch if c.get('carrier') in visible_carriers]
            elif hide_self and mvno_carrier:
                ch = [c for c in ch if c.get('carrier') != mvno_carrier]
            all_changes.extend(ch)
        if not all_changes:
            return jsonify({"status": "skipped", "reason": "no changes in last 7 days"})
        ok = _send_digest(emails, ws_name, all_changes, _cfg, brand_config=brand_config)
        actor = core._current_user_email() or ''
        core.log_audit('digest_sent', actor_email=actor, workspace_id=workspace_id,
                  details=f'{len(all_changes)} changes → {len(emails)} users', db_path=core._db_path())
        return jsonify({"status": "sent" if ok else "partial", "emails": len(emails), "changes": len(all_changes)})
    except Exception as e:
        logger.error(f"trigger digest failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspace/branding", methods=["PATCH"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_workspace_branding():
    """Update brand_config for the caller's own workspace.
    Body: {primary_color?, secondary_color?, app_title?, logo_url?}
    Workspace admins (non-super) can update their own workspace only."""
    # g.jwt_payload is None when API key was also present (dev mode sends both).
    # Fall back to parsing Bearer JWT directly so we know who the caller is.
    email = core._current_user_email() or ''
    if not email:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            _p = core._verify_supabase_jwt(auth_header[7:])
            if _p:
                email = (_p.get('email') or '').strip().lower()
    if not email:
        return jsonify({"error": "Unauthorized"}), 403
    ctx = core._get_user_context(email)
    role = ctx.get('role', 'viewer')
    ws_id = ctx.get('workspace_id')
    if role not in ('admin', 'super_admin') or not ws_id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(force=True) or {}
    allowed_keys = {'primary_color', 'secondary_color', 'app_title', 'logo_url', 'slack_webhook_url'}
    updates = {k: v for k, v in data.items() if k in allowed_keys}
    if not updates:
        return jsonify({"error": "no valid fields provided"}), 400

    # Validate colour values (must be hex colour or empty string)
    import re as _re
    for colour_key in ('primary_color', 'secondary_color'):
        if colour_key in updates and updates[colour_key]:
            if not _re.match(r'^#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?$', updates[colour_key]):
                return jsonify({"error": f"invalid hex colour for {colour_key}"}), 400

    # Validate Slack webhook URL — must be HTTPS to a known incoming-webhook host
    if updates.get('slack_webhook_url'):
        if not core._is_valid_slack_webhook(updates['slack_webhook_url']):
            return jsonify({"error": "slack_webhook_url must be a Slack or Teams incoming-webhook HTTPS URL"}), 400

    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT brand_config FROM public.workspaces WHERE id = %s", (ws_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "workspace not found"}), 404
        import json as _json
        existing = row[0] or {}
        merged = {**existing, **updates}
        # Remove keys that were explicitly set to empty string (clear the field)
        merged = {k: v for k, v in merged.items() if v not in (None, '')}
        cur.execute(
            "UPDATE public.workspaces SET brand_config = %s::jsonb WHERE id = %s",
            (_json.dumps(merged), ws_id)
        )
        conn.close()
        core.log_audit('branding_updated', actor_email=email, workspace_id=ws_id,
                  details=str(list(updates.keys())), db_path=core._db_path())
        logger.info(f"AUDIT branding_updated: workspace={ws_id} by={email!r} fields={list(updates.keys())}")
        return jsonify({"status": "updated", "brand_config": merged})
    except Exception as e:
        logger.error(f"workspace branding update failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/workspace/slack-test", methods=["POST"])
@core.require_auth
@core.limiter.limit("5 per minute")
def api_workspace_slack_test():
    """Send a test message to the workspace's configured Slack/Teams webhook.
    Body: {webhook_url?} — if provided, tests this URL without saving."""
    from notifier import send_slack
    email = core._current_user_email() or ''
    if not email:
        return jsonify({"error": "Unauthorized"}), 403
    ctx = core._get_user_context(email)
    role = ctx.get('role', 'viewer')
    ws_id = ctx.get('workspace_id')
    if role not in ('admin', 'super_admin') or not ws_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Caller can pass a URL to test before saving, or rely on stored config.
    # NOTE: any URL accepted from the request body MUST be validated against the
    # Slack/Teams allowlist to prevent SSRF (e.g. http://169.254.169.254/...).
    data = request.get_json(silent=True) or {}
    webhook_url = (data.get('webhook_url') or '').strip()
    if webhook_url and not core._is_valid_slack_webhook(webhook_url):
        return jsonify({
            "error": "webhook_url must be a Slack or Teams incoming-webhook HTTPS URL"
        }), 400
    if not webhook_url:
        try:
            conn = core._supabase_conn()
            cur = conn.cursor()
            cur.execute("SELECT brand_config FROM public.workspaces WHERE id = %s", (ws_id,))
            row = cur.fetchone()
            conn.close()
            bc = row[0] if row else {}
            if isinstance(bc, str):
                import json as _json
                bc = _json.loads(bc)
            webhook_url = (bc or {}).get('slack_webhook_url') or ''
        except Exception:
            webhook_url = ''
    if not webhook_url:
        return jsonify({"error": "no webhook configured"}), 400

    msg = f"✅ MOCA Slack integration test — workspace {ctx.get('workspace', {}).get('name', '')} · sent by {email}"
    ok = send_slack(msg, webhook_url)
    return jsonify({"status": "sent" if ok else "failed", "ok": ok})


@bp.route("/api/audit-log", methods=["GET"])
@core.require_super_admin
@core.limiter.limit("30 per minute")
def api_audit_log():
    """Return the audit log. Optional query params: limit (default 200),
    workspace_id (filter to a specific workspace)."""
    limit = min(int(request.args.get('limit', 200)), 1000)
    ws_filter = request.args.get('workspace_id') or None
    entries = core.get_audit_log(limit=limit, workspace_id=ws_filter, db_path=core._db_path())
    return jsonify(entries)
