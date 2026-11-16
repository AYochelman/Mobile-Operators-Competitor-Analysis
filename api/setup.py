"""Dashboard setup wizard (/setup): load / save the workspace-level and user-level
answers, send a test message, and the scheduled personal-alert dispatcher.

Names defined in app.py are referenced as `core.<name>` (late-bound), like the
other blueprints; the validation + dispatch logic lives in dashboard_setup.py.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
from flask import jsonify, request
from flask import Blueprint
import dashboard_setup as ds

logger = core.logger
bp = Blueprint("dashsetup", __name__)


def _setup_identity():
    """(email, context) of the caller, or (None, None) for an identity-less call."""
    email = core._current_user_email()
    if not email:
        return None, None
    return email, core._get_user_context(email)


def _setup_row(scope, owner):
    import db
    row = db.get_dashboard_setup(scope, owner, db_path=core._db_path()) if owner else None
    return row or {"config": {}, "completed_at": None, "dismissed_at": None, "updated_at": None}


@bp.route("/api/dashboard-setup", methods=["GET"])
@core.require_auth
@core.limiter.limit("60 per minute")
def api_dashboard_setup_get():
    """Everything the wizard needs: both saved configs, what the caller may edit,
    and which sections the operator locked (hidden by the workspace's own flags)."""
    email, ctx = _setup_identity()
    if not email:
        return jsonify({"error": "auth required"}), 401
    ws = ctx.get("workspace") or {}
    ws_id = ctx.get("workspace_id")
    role = ctx.get("role", "viewer")
    ws_row = _setup_row("workspace", ws_id)
    user_row = _setup_row("user", email)
    user_cfg = user_row["config"] or {}
    return jsonify({
        "role": role,
        "can_edit_workspace": bool(ws_id) and role in ("admin", "super_admin"),
        "workspace": {
            "id": ws_id,
            "name": ws.get("name"),
            "mvno_carrier": ws.get("mvno_carrier"),
            "hide_self_carrier": bool(ws.get("hide_self_carrier")),
            "visible_carriers": ws.get("visible_carriers") or [],
            "locked_flags": ws.get("feature_flags") or {},
            "config": ws_row["config"],
            "completed_at": ws_row["completed_at"],
        },
        "user": {
            "email": email,
            "config": user_cfg,
            "completed_at": user_row["completed_at"],
            "dismissed_at": user_row["dismissed_at"],
        },
        "defaults": ds.DEFAULT_USER_CONFIG,
    })


@bp.route("/api/dashboard-setup/workspace", methods=["PUT"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_dashboard_setup_workspace():
    """Save the workspace-level answers. Admins of the workspace only; a section
    the operator hid through feature_flags can never be re-opened from here."""
    import db
    email, ctx = _setup_identity()
    if not email:
        return jsonify({"error": "auth required"}), 401
    ws_id = ctx.get("workspace_id")
    if not ws_id or ctx.get("role") not in ("admin", "super_admin"):
        return jsonify({"error": "Unauthorized"}), 403
    locked = (ctx.get("workspace") or {}).get("feature_flags") or {}
    try:
        cfg = ds.clean_workspace_config(request.get_json(force=True) or {}, locked_flags=locked)
    except ds.SetupError as e:
        return jsonify({"error": str(e)}), 400
    db.save_dashboard_setup("workspace", ws_id, cfg, updated_by=email, db_path=core._db_path())
    # Every member's cached context carries the old dashboard_config.
    core._USER_CONTEXT_CACHE.clear()
    core.log_audit('dashboard_setup_saved', actor_email=email, workspace_id=ws_id,
                   details=f"hidden={sorted(p for p, s in cfg['sections'].items() if s == 'hidden')} "
                           f"focus={sorted(p for p, s in cfg['sections'].items() if s == 'focus')}",
                   db_path=core._db_path())
    return jsonify({"status": "saved", "config": cfg})


@bp.route("/api/dashboard-setup/user", methods=["PUT"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_dashboard_setup_user():
    """Save the caller's own alert preferences (channels, recipients, frequency,
    categories, events, quiet hours, language)."""
    import db
    from datetime import datetime
    email, _ctx = _setup_identity()
    if not email:
        return jsonify({"error": "auth required"}), 401
    try:
        cfg = ds.clean_user_config(request.get_json(force=True) or {}, default_email=email)
    except ds.SetupError as e:
        return jsonify({"error": str(e)}), 400
    path = core._db_path()
    prev = (db.get_dashboard_setup("user", email, db_path=path) or {}).get("config") or {}
    db.save_dashboard_setup("user", email, cfg, updated_by=email, db_path=path)
    # A channel that was just switched on starts counting from now, so the first
    # message never replays days of old changes.
    now_iso = datetime.now().isoformat()
    for ch in ds.CHANNELS:
        was_on = bool(((prev.get("channels") or {}).get(ch) or {}).get("enabled"))
        if cfg["channels"][ch]["enabled"] and not was_on:
            db.set_alert_cursor(email, ch, now_iso, db_path=path)
    return jsonify({"status": "saved", "config": cfg})


@bp.route("/api/dashboard-setup/dismiss", methods=["POST"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_dashboard_setup_dismiss():
    """The user skipped the first-login prompt - do not show it again."""
    import db
    email, _ctx = _setup_identity()
    if not email:
        return jsonify({"error": "auth required"}), 401
    db.dismiss_dashboard_setup("user", email, db_path=core._db_path())
    return jsonify({"status": "dismissed"})


@bp.route("/api/dashboard-setup/test", methods=["POST"])
@core.require_auth
@core.limiter.limit("3 per minute; 12 per day")
def api_dashboard_setup_test():
    """Send the fixed test message to the address / number typed in the wizard,
    so the user knows the channel works before relying on it."""
    email, _ctx = _setup_identity()
    if not email:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True) or {}
    channel = data.get("channel")
    lang = "en" if data.get("lang") == "en" else "he"
    try:
        if channel == "email":
            target = str(data.get("address") or email).strip().lower()
            if not ds._RE_EMAIL.match(target):
                raise ds.SetupError("bad email")
        elif channel == "whatsapp":
            target = ds.normalize_phone(data.get("phone"))
            if not target:
                raise ds.SetupError("bad phone")
        else:
            return jsonify({"error": "bad channel"}), 400
    except ds.SetupError as e:
        return jsonify({"error": str(e)}), 400
    try:
        ok = ds.send_test(channel, target, lang, core.load_config())
    except Exception as e:
        logger.error(f"dashboard setup test send failed: {e}", exc_info=True)
        ok = False
    logger.info(f"AUDIT dashboard_setup_test: by={email!r} channel={channel} ok={ok}")
    if not ok:
        return jsonify({"error": "send failed"}), 502
    return jsonify({"status": "sent"})


@bp.route("/api/dashboard-setup/user", methods=["DELETE"])
@core.require_auth
@core.limiter.limit("10 per minute")
def api_dashboard_setup_user_reset():
    """Erase the caller's own alert preferences (address, number, cursors).
    The row is replaced by a bare "dismissed" marker so the first-login prompt
    does not come back for someone who reset on purpose."""
    import db
    email, _ctx = _setup_identity()
    if not email:
        return jsonify({"error": "auth required"}), 401
    db.delete_dashboard_setup("user", email, db_path=core._db_path())
    db.dismiss_dashboard_setup("user", email, db_path=core._db_path())
    logger.info(f"AUDIT dashboard_setup_user_reset: by={email!r}")
    return jsonify({"status": "reset"})


@bp.route("/api/dashboard-setup/workspace", methods=["DELETE"])
@core.require_auth
@core.limiter.limit("10 per minute")
def api_dashboard_setup_workspace_reset():
    """Back to the default dashboard for the caller's whole workspace (admins
    only). Members' personal alert preferences are not touched."""
    import db
    email, ctx = _setup_identity()
    if not email:
        return jsonify({"error": "auth required"}), 401
    ws_id = ctx.get("workspace_id")
    if not ws_id or ctx.get("role") not in ("admin", "super_admin"):
        return jsonify({"error": "Unauthorized"}), 403
    db.delete_dashboard_setup("workspace", ws_id, db_path=core._db_path())
    core._USER_CONTEXT_CACHE.clear()
    core.log_audit('dashboard_setup_reset', actor_email=email, workspace_id=ws_id,
                   details='workspace view reset by its admin', db_path=core._db_path())
    return jsonify({"status": "reset"})


def _workspace_member_emails(workspace_id):
    """Lower-cased e-mails of every user assigned to a workspace (Supabase)."""
    conn = core._supabase_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT LOWER(u.email) FROM auth.users u
            JOIN public.user_roles r ON r.user_id = u.id
            WHERE r.workspace_id = %s
        """, (workspace_id,))
        return [r[0] for r in cur.fetchall() if r[0]]
    finally:
        conn.close()


@bp.route("/api/workspaces/<workspace_id>/dashboard-setup", methods=["DELETE"])
@core.require_super_admin
@core.limiter.limit("10 per minute")
def api_workspace_dashboard_setup_reset(workspace_id):
    """Operator reset of a customer's wizard answers. Always clears the
    workspace-level view; `?include_users=true` also erases every member's
    personal alert preferences (they are prompted by the wizard again)."""
    import db
    include_users = (request.args.get("include_users") or "").lower() == "true"
    emails = []
    if include_users:
        try:
            # Resolve the members BEFORE deleting anything: a failed lookup
            # must not leave the reset half done.
            emails = _workspace_member_emails(workspace_id)
        except Exception as e:
            logger.error(f"dashboard setup reset: member lookup failed: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500
    path = core._db_path()
    had_workspace = db.get_dashboard_setup("workspace", workspace_id, db_path=path) is not None
    db.delete_dashboard_setup("workspace", workspace_id, db_path=path)
    users_reset = 0
    for em in emails:
        if db.get_dashboard_setup("user", em, db_path=path) is not None:
            db.delete_dashboard_setup("user", em, db_path=path)
            users_reset += 1
    core._USER_CONTEXT_CACHE.clear()
    core.log_audit('dashboard_setup_reset', actor_email=core._current_user_email() or '',
                   workspace_id=workspace_id,
                   details=f'operator reset: workspace={had_workspace} users={users_reset}',
                   db_path=path)
    return jsonify({"status": "reset", "workspace_reset": had_workspace, "users_reset": users_reset})


def run_dashboard_alerts_job(dry_run=False, only_email=None):
    """Scheduled every 15 minutes: deliver the personal change alerts that are
    due (see dashboard_setup.run_dispatch). Returns the dispatch report."""
    try:
        report = ds.run_dispatch(core.load_config(), core._get_user_context,
                                 dry_run=dry_run, db_path=core._db_path(), only_email=only_email)
        sent = sum(1 for r in report if r.get("status") == "sent")
        failed = sum(1 for r in report if r.get("status") in ("failed", "error"))
        if sent or failed:
            logger.info(f"Dashboard alerts: {sent} sent, {failed} failed ({len(report)} channels checked)")
        return report
    except Exception as e:
        logger.error(f"Dashboard alerts job failed: {e}", exc_info=True)
        return []


@bp.route("/api/dashboard-setup/run-now", methods=["GET", "POST"])
@core.require_api_key_or_query
def api_dashboard_setup_run_now():
    """Operator preview / manual run of the dispatcher. Dry run unless
    `send=true`; `email=` limits it to one user."""
    send = (request.args.get("send") or "").lower() == "true"
    only = (request.args.get("email") or "").strip().lower() or None
    report = run_dashboard_alerts_job(dry_run=not send, only_email=only)
    return jsonify({"dry_run": not send, "report": report})
