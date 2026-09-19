"""Session / account endpoints: VAPID key, auth cookie session, Web Push subscriptions, my-role, preferences, context, contact form.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import time as _time
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
logger = core.logger
from flask import Blueprint
bp = Blueprint("account", __name__)


@bp.route("/api/push/vapid-public-key")
def api_vapid_public_key():
    return jsonify({"publicKey": core.load_config().get("vapid_public_key", "")})


@bp.route("/api/auth/session", methods=["POST"])
@core.limiter.limit("20 per minute")
def api_auth_session():
    """Receive a valid Supabase JWT from the frontend and persist it as an httpOnly cookie.
    The cookie is used by Flask to authenticate API requests without exposing
    the token to JavaScript (mitigates XSS-based token theft)."""
    data = request.get_json(force=True) or {}
    token = data.get("access_token", "").strip()
    if not token:
        return jsonify({"error": "access_token required"}), 400
    payload = core._verify_supabase_jwt(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401
    exp = payload.get("exp")
    max_age = max(0, int(exp - _time.time())) if exp else 3600
    resp = make_response(jsonify({"status": "ok"}))
    resp.set_cookie(
        "auth_token", token,
        httponly=True,
        secure=True,
        samesite="None",   # Required for cross-origin (Netlify → ngrok)
        max_age=max_age,
        path="/api/",
    )
    return resp


@bp.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Clear the httpOnly auth cookie on logout."""
    resp = make_response(jsonify({"status": "ok"}))
    resp.set_cookie("auth_token", "", httponly=True, secure=True,
                    samesite="None", max_age=0, path="/api/")
    return resp


@bp.route("/api/push/subscribe", methods=["POST"])
@core.require_auth
@core.limiter.limit("10 per minute")
def api_push_subscribe():
    from db import save_push_subscription
    data = request.get_json(force=True) or {}
    endpoint = data.get("endpoint")
    p256dh   = data.get("keys", {}).get("p256dh")
    auth     = data.get("keys", {}).get("auth")
    if not all([endpoint, p256dh, auth]):
        return jsonify({"error": "missing fields"}), 400
    user_email = core._current_user_email()
    if user_email is None:
        # Server-to-server subscriptions must name their owner
        user_email = (data.get("user_email") or "").strip().lower() or None
    # Resolve the carrier this subscription should not receive push for
    hidden_carrier = None
    if user_email:
        ctx = core._get_user_context(user_email)
        ws = ctx.get('workspace') or {}
        if ws.get('hide_self_carrier') and ws.get('mvno_carrier'):
            hidden_carrier = ws['mvno_carrier']
    save_push_subscription(endpoint, p256dh, auth, user_email=user_email,
                           hidden_carrier=hidden_carrier, db_path=core._db_path())
    return jsonify({"status": "subscribed"}), 201


@bp.route("/api/push/unsubscribe", methods=["DELETE"])
@core.require_auth
@core.limiter.limit("10 per minute")
def api_push_unsubscribe():
    from db import delete_push_subscription
    data = request.get_json(force=True) or {}
    endpoint = data.get("endpoint")
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400
    # JWT callers can only unsubscribe endpoints they own; API-key can unsubscribe any
    user_email = core._current_user_email()
    deleted = delete_push_subscription(endpoint, user_email=user_email, db_path=core._db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "unsubscribed"}), 200


@bp.route("/api/push/test")
@core.require_api_key
def api_push_test():
    """Debug: send a test push notification to all subscribed devices."""
    config = core.load_config()
    from notifier import send_push_notifications
    fake = [{"carrier": "partner", "plan_name": "טסט", "change_type": "price_change",
             "old_val": 100, "new_val": 90}]
    n = send_push_notifications(fake, config, core._db_path())
    return jsonify({"sent": n})


@bp.route("/api/my-role")
@core.require_auth
@core.limiter.limit("60 per minute")
def api_my_role():
    """Legacy endpoint — prefer /api/my-context. Returns only the role.

    Identity is taken exclusively from the verified JWT. API-key callers
    have no user identity and receive role='viewer' (no escalation possible
    via the X-User-Email request header)."""
    payload = getattr(g, 'jwt_payload', None)
    if not payload:
        return jsonify({"role": "viewer"})
    email = (payload.get('email') or '').strip().lower()
    if not email:
        return jsonify({"role": "viewer"})
    return jsonify({"role": core._get_user_context(email)["role"]})


@bp.route("/api/my-preferences", methods=["PATCH"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_update_my_preferences():
    """Update per-user preferences. Currently supports: {digest_opt_out: bool}."""
    email = core._current_user_email()
    if not email:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True) or {}
    if 'digest_opt_out' not in data:
        return jsonify({"error": "no updatable fields provided"}), 400
    opt_out = bool(data['digest_opt_out'])
    try:
        conn = core._supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            UPDATE public.user_roles r
            SET digest_opt_out = %s
            FROM auth.users u
            WHERE r.user_id = u.id AND LOWER(u.email) = %s
        """, (opt_out, email))
        updated = cur.rowcount
        conn.close()
        return jsonify({"status": "updated", "digest_opt_out": opt_out, "rows": updated})
    except Exception as e:
        logger.error(f"update preferences failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/my-context")
@core.require_auth
@core.limiter.limit("60 per minute")
def api_my_context():
    """Return the authenticated user's role and workspace configuration.

    Response shape:
      { role, workspace_id, workspace: {slug, name, mvno_carrier, brand_config,
                                        feature_flags, hide_self_carrier, active} | null }

    super_admin users may have workspace=null (cross-workspace view).
    A non-null workspace with active=false means the customer has been
    suspended — the frontend should show a friendly 'contact us' screen.

    Identity is taken exclusively from the verified JWT. API-key callers
    have no user identity and receive an empty context (no escalation via
    the X-User-Email request header)."""
    # `reason` marks a viewer that is a FALLBACK (we could not identify the
    # caller) rather than a real viewer account. Without it the frontend cannot
    # tell "you are a viewer" from "we do not know who you are", and an
    # identity-less token silently strips every admin menu. Additive field —
    # older clients ignore it.
    payload = getattr(g, 'jwt_payload', None)
    if not payload:
        return jsonify({"role": "viewer", "workspace_id": None, "workspace": None,
                        "reason": "no_jwt"})
    email = (payload.get('email') or '').strip().lower()
    if not email:
        return jsonify({"role": "viewer", "workspace_id": None, "workspace": None,
                        "reason": "no_email"})
    return jsonify(core._get_user_context(email))


@bp.route("/api/contact", methods=["POST"])
@core.require_auth
@core.limiter.limit("3 per minute")
def api_contact():
    """In-app contact form — forwards the requester's message to the MOCA
    operator via email (Resend SMTP). Intentionally bypasses the workspace `active`
    gate (ProtectedRoute level), so a suspended user CAN ask to be reinstated.
    Rate-limited strictly to prevent abuse."""
    data = request.get_json(force=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    if len(message) > 4000:
        return jsonify({"error": "message too long (max 4000 chars)"}), 400

    from_email = core._current_user_email() or ''
    if not from_email:
        # API-key auth short-circuited require_auth; still try the Bearer JWT for the email.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            _p = core._verify_supabase_jwt(auth_header[7:])
            if _p:
                from_email = (_p.get('email') or '').strip().lower()
    if not from_email:
        return jsonify({"error": "authenticated email required"}), 401

    # Best-effort workspace label for the admin's inbox preview
    ctx = core._get_user_context(from_email)
    ws_name = (ctx.get('workspace') or {}).get('name') or ''

    try:
        from notifier import send_contact_email
        ok = send_contact_email(from_email, ws_name, message, core.load_config())
        if not ok:
            return jsonify({"error": "failed to send — check email configuration"}), 500
        logger.info(f"AUDIT contact_sent: from={from_email} ws={ws_name!r}")
        return jsonify({"status": "sent"})
    except Exception as e:
        logger.error(f"api_contact failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
