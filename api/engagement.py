"""Per-user engagement: alerts, watchlist, saved views, activity beacons, annotations, coupons, provider deals CRM.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import json
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
import re as _re_webhook
logger = core.logger
from flask import Blueprint
bp = Blueprint("engagement", __name__)


@bp.route("/api/alerts", methods=["GET"])
@core.require_auth
@core.limiter.limit("60 per minute")
def api_get_alerts():
    """Return alerts owned by the authenticated user.
    Identity is taken from the verified JWT; API-key callers MUST pass
    ?user_email= explicitly. Unscoped queries (which would expose every
    user's alerts) are rejected."""
    user_email = core._current_user_email()
    if user_email is None:
        # Server-to-server (API key) — explicit user_email is required.
        user_email = (request.args.get("user_email") or "").strip().lower() or None
        if not user_email:
            return jsonify({"error": "user_email required for API-key callers"}), 400
    alerts = core.get_price_alerts(user_email=user_email, db_path=core._db_path())
    return jsonify(alerts)


@bp.route("/api/alerts", methods=["POST"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_create_alert():
    data = request.get_json(force=True) or {}
    user_email = core._current_user_email()
    if user_email is None:
        # Server-to-server must provide the target user explicitly
        user_email = (data.get("user_email") or "").strip().lower()
        if not user_email:
            return jsonify({"error": "user_email required for API-key callers"}), 400
    try:
        core.save_price_alert(
            user_email=user_email,
            tab=data.get("tab", "domestic"),
            carrier=data.get("carrier", ""),
            plan_pattern=data.get("plan_pattern", ""),
            threshold=float(data.get("threshold", 0)),
            db_path=core._db_path()
        )
        _track_user_action(user_email, 'alert_created', {
            "carrier": data.get("carrier", ""),
            "plan_pattern": data.get("plan_pattern", ""),
            "threshold": data.get("threshold"),
        })
        return jsonify({"status": "created"}), 201
    except Exception as e:
        logger.error(f"create alert failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
@core.require_auth
def api_delete_alert(alert_id):
    """Delete an alert. JWT callers can only delete their own alerts;
    API-key callers MUST pass ?user_email= so the delete remains scoped
    (otherwise an unscoped delete bypasses the per-user IDOR check)."""
    user_email = core._current_user_email()
    if user_email is None:
        user_email = (request.args.get("user_email") or "").strip().lower() or None
        if not user_email:
            return jsonify({"error": "user_email required for API-key callers"}), 400
    deleted = core.delete_price_alert(alert_id, user_email=user_email, db_path=core._db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


@bp.route("/api/watchlist", methods=["GET"])
@core.require_auth
@core.limiter.limit("60 per minute")
def api_get_watchlist():
    from db import get_watchlist as _gwl
    user_email = core._current_user_email()
    if not user_email:
        return jsonify([])
    return jsonify(_gwl(user_email, db_path=core._db_path()))


@bp.route("/api/watchlist", methods=["POST"])
@core.require_auth
@core.limiter.limit("30 per minute")
def api_add_to_watchlist():
    from db import add_to_watchlist as _awl
    user_email = core._current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True) or {}
    carrier   = (data.get('carrier') or '').strip()
    plan_name = (data.get('plan_name') or '').strip()
    plan_type = (data.get('plan_type') or '').strip()
    if not all([carrier, plan_name, plan_type]):
        return jsonify({"error": "carrier, plan_name, plan_type required"}), 400
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({"error": "plan_type must be domestic/abroad/global/content"}), 400
    try:
        _awl(user_email, carrier, plan_name, plan_type, db_path=core._db_path())
        _track_user_action(user_email, 'watchlist_added', {
            "carrier": carrier, "plan_name": plan_name, "plan_type": plan_type,
        })
        return jsonify({"status": "added"}), 201
    except Exception as e:
        logger.error(f"add watchlist failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/watchlist", methods=["DELETE"])
@core.require_auth
def api_remove_from_watchlist():
    from db import remove_from_watchlist as _rwl
    user_email = core._current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True) or {}
    deleted = _rwl(user_email, data.get('carrier', ''), data.get('plan_name', ''),
                   data.get('plan_type', ''), db_path=core._db_path())
    if deleted:
        _track_user_action(user_email, 'watchlist_removed', {
            "carrier": data.get('carrier', ''), "plan_name": data.get('plan_name', ''),
        })
    return jsonify({"status": "deleted", "rows": deleted})


@bp.route("/api/saved-views", methods=["GET"])
@core.require_auth
@core.limiter.limit("60 per minute")
def api_get_saved_views():
    from db import get_saved_views as _gsv
    user_email = core._current_user_email()
    if not user_email:
        return jsonify([])
    return jsonify(_gsv(user_email, db_path=core._db_path()))


@bp.route("/api/saved-views", methods=["POST"])
@core.require_auth
@core.limiter.limit("20 per minute")
def api_create_saved_view():
    from db import save_view as _sv
    user_email = core._current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    filters = data.get('filters')
    if not name or len(name) > 60:
        return jsonify({"error": "name required (max 60 chars)"}), 400
    if not isinstance(filters, dict):
        return jsonify({"error": "filters must be an object"}), 400
    try:
        view_id = _sv(user_email, name, json.dumps(filters, ensure_ascii=False), db_path=core._db_path())
        if filters.get('kind') == 'compare':
            _track_user_action(user_email, 'comparison_saved', {
                "name": name, "count": len(filters.get('plans') or []),
            })
        return jsonify({"status": "saved", "id": view_id}), 201
    except Exception as e:
        logger.error(f"save view failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/saved-views/<int:view_id>", methods=["DELETE"])
@core.require_auth
def api_delete_saved_view(view_id):
    from db import delete_saved_view as _dsv
    user_email = core._current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    deleted = _dsv(view_id, user_email, db_path=core._db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


_ACTIVITY_CLIENT_EVENTS = {'login', 'page_view', 'search', 'export'}


def _track_user_action(user_email, event_type, details=None):
    """Best-effort server-side activity log for a user action (alert / watchlist
    / comparison). Skips super-admins (operator's own activity is never
    recorded) and never raises into the calling request handler."""
    if not user_email:
        return
    try:
        ctx = core._get_user_context(user_email)
        if ctx.get('role') == 'super_admin':
            return
        core.log_user_activity(
            user_email=user_email,
            event_type=event_type,
            workspace_id=ctx.get('workspace_id'),
            details=json.dumps(details, ensure_ascii=False) if details else None,
            user_agent=request.headers.get('User-Agent'),
            db_path=core._db_path(),
        )
    except Exception:
        pass


@bp.route("/api/activity", methods=["POST"])
@core.require_auth
@core.limiter.limit("240 per minute")
def api_track_activity():
    """Best-effort client activity beacon (login / page_view). Identity is
    ALWAYS derived server-side from the JWT — any client-supplied identity is
    ignored. Super-admins are intentionally NOT recorded. Action events
    (alerts/watchlist/comparisons) are logged server-side in their own
    handlers, not here. Returns 204 and never hard-errors."""
    user_email = core._current_user_email()
    if not user_email:
        return ("", 204)  # API-key-only caller without a JWT — nothing to attribute
    ctx = core._get_user_context(user_email)
    if ctx.get('role') == 'super_admin':
        return ("", 204)  # exclude super-admins (operator's own activity)
    data = request.get_json(silent=True) or {}
    event_type = (data.get('event_type') or '').strip()
    if event_type not in _ACTIVITY_CLIENT_EVENTS:
        return ("", 204)  # silently ignore unknown / non-beacon event types
    path = (data.get('path') or '')[:300] or None
    details = data.get('details')
    if details is not None:
        details = str(details)[:500] or None
    core.log_user_activity(
        user_email=user_email,
        event_type=event_type,
        workspace_id=ctx.get('workspace_id'),
        path=path,
        details=details,
        user_agent=request.headers.get('User-Agent'),
        db_path=core._db_path(),
    )
    return ("", 204)


@bp.route("/api/annotations", methods=["GET"])
@core.require_auth
@core.limiter.limit("60 per minute")
def api_get_annotations():
    """Return annotations for current workspace, optionally filtered to a plan."""
    from db import get_annotations as _ga
    user_email_for_ctx = core._current_user_email() or ''
    ctx = core._get_user_context(user_email_for_ctx) if user_email_for_ctx else {}
    ws_id = ctx.get('workspace_id')
    carrier   = request.args.get('carrier')
    plan_name = request.args.get('plan_name')
    plan_type = request.args.get('plan_type')
    return jsonify(_ga(ws_id, carrier=carrier, plan_name=plan_name, plan_type=plan_type, db_path=core._db_path()))


@bp.route("/api/annotations/counts", methods=["GET"])
@core.require_auth
@core.limiter.limit("60 per minute")
def api_annotation_counts():
    """Return annotation counts grouped by plan key for the workspace."""
    from db import get_annotation_counts as _gac
    user_email_for_ctx = core._current_user_email() or ''
    ctx = core._get_user_context(user_email_for_ctx) if user_email_for_ctx else {}
    ws_id = ctx.get('workspace_id')
    return jsonify(_gac(ws_id, db_path=core._db_path()))


@bp.route("/api/annotations", methods=["POST"])
@core.require_auth
@core.limiter.limit("30 per minute")
def api_add_annotation():
    from db import add_annotation as _aa
    user_email = core._current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    ctx = core._get_user_context(user_email)
    ws_id = ctx.get('workspace_id')
    data = request.get_json(force=True) or {}
    carrier   = (data.get('carrier') or '').strip()
    plan_name = (data.get('plan_name') or '').strip()
    plan_type = (data.get('plan_type') or '').strip()
    note      = (data.get('note') or '').strip()
    if not carrier or not plan_name or not plan_type:
        return jsonify({"error": "carrier/plan_name/plan_type required"}), 400
    if not note or len(note) > 1000:
        return jsonify({"error": "note required (max 1000 chars)"}), 400
    try:
        new_id = _aa(ws_id, user_email, carrier, plan_name, plan_type, note, db_path=core._db_path())
        _track_user_action(user_email, 'annotation_added', {"carrier": carrier, "plan_name": plan_name})
        return jsonify({"status": "added", "id": new_id}), 201
    except Exception as exc:
        logger.error(f"add annotation failed: {exc}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/annotations/<int:ann_id>", methods=["PATCH"])
@core.require_auth
def api_update_annotation(ann_id):
    from db import update_annotation as _ua
    user_email = core._current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    ctx = core._get_user_context(user_email)
    ws_id = ctx.get('workspace_id')
    data = request.get_json(force=True) or {}
    note = (data.get('note') or '').strip()
    if not note or len(note) > 1000:
        return jsonify({"error": "note required (max 1000 chars)"}), 400
    updated = _ua(ann_id, ws_id, user_email, note, db_path=core._db_path())
    if updated == 0:
        return jsonify({"error": "not found or not author"}), 404
    return jsonify({"status": "updated"})


@bp.route("/api/annotations/<int:ann_id>", methods=["DELETE"])
@core.require_auth
def api_delete_annotation(ann_id):
    from db import delete_annotation as _da
    user_email = core._current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    ctx = core._get_user_context(user_email)
    ws_id = ctx.get('workspace_id')
    deleted = _da(ann_id, ws_id, user_email, db_path=core._db_path())
    if deleted == 0:
        return jsonify({"error": "not found or not author"}), 404
    return jsonify({"status": "deleted"})


_COUPON_CARRIER_RE = _re_webhook.compile(r'^[a-z0-9_]{2,30}$')


_COUPON_CODE_RE    = _re_webhook.compile(r'^[A-Za-z0-9_\-]{2,40}$')


def _validate_coupon_payload(data, partial=False):
    """Return (cleaned_dict, error_msg). `partial=True` for PATCH (omit any field)."""
    out = {}
    if "carrier" in data or not partial:
        c = (data.get("carrier") or "").strip().lower()
        if not _COUPON_CARRIER_RE.match(c):
            return None, "invalid carrier (lowercase a-z0-9_, 2-30 chars)"
        out["carrier"] = c
    if "code" in data or not partial:
        code = (data.get("code") or "").strip()
        if not _COUPON_CODE_RE.match(code):
            return None, "invalid code (A-Z0-9_- only, 2-40 chars)"
        out["code"] = code
    if "discount_label" in data:
        out["discount_label"] = (data.get("discount_label") or "").strip()[:80] or None
    if "expires_at" in data:
        v = (data.get("expires_at") or "").strip()
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                return None, "expires_at must be YYYY-MM-DD or empty"
        out["expires_at"] = v or None
    if "source_url" in data:
        u = (data.get("source_url") or "").strip()
        if u and not (u.startswith("http://") or u.startswith("https://")):
            return None, "source_url must start with http(s)://"
        out["source_url"] = u[:500] or None
    if "is_active" in data:
        out["is_active"] = bool(data.get("is_active"))
    if "notes" in data:
        out["notes"] = (data.get("notes") or "").strip()[:500] or None
    if "external_offer_url" in data:
        u = (data.get("external_offer_url") or "").strip()
        if u and not (u.startswith("http://") or u.startswith("https://")):
            return None, "external_offer_url must start with http(s)://"
        out["external_offer_url"] = u[:500] or None
    if "partner_name" in data:
        out["partner_name"] = (data.get("partner_name") or "").strip()[:80] or None
    return out, None


@bp.route("/api/coupons", methods=["GET"])
@core.limiter.limit("120 per minute")
def api_get_coupons():
    """Public: active, non-expired coupons. Cached for 5 min on the client."""
    coupons = core.get_active_coupons(db_path=core._db_path())
    resp = jsonify(coupons)
    return core._public_cache(resp, 300)


@bp.route("/api/coupons/all", methods=["GET"])
@core.require_api_key_or_super_admin
def api_get_all_coupons():
    """Admin: every coupon row including inactive / expired."""
    return jsonify(core.get_all_coupons(db_path=core._db_path()))


@bp.route("/api/coupons", methods=["POST"])
@core.require_api_key_or_super_admin
def api_create_coupon():
    data = request.get_json(force=True) or {}
    cleaned, err = _validate_coupon_payload(data, partial=False)
    if err:
        return jsonify({"error": err}), 400
    try:
        new_id = core.upsert_coupon(
            cleaned["carrier"], cleaned["code"],
            discount_label=cleaned.get("discount_label"),
            expires_at=cleaned.get("expires_at"),
            source_url=cleaned.get("source_url"),
            is_active=cleaned.get("is_active", True),
            notes=cleaned.get("notes"),
            external_offer_url=cleaned.get("external_offer_url"),
            partner_name=cleaned.get("partner_name"),
            db_path=core._db_path(),
        )
        return jsonify({"status": "saved", "id": new_id}), 201
    except Exception as exc:
        logger.error(f"create coupon failed: {exc}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/coupons/<int:coupon_id>", methods=["PATCH"])
@core.require_api_key_or_super_admin
def api_update_coupon(coupon_id):
    data = request.get_json(force=True) or {}
    cleaned, err = _validate_coupon_payload(data, partial=True)
    if err:
        return jsonify({"error": err}), 400
    if not cleaned:
        return jsonify({"error": "no editable fields supplied"}), 400
    updated = core.update_coupon(coupon_id, cleaned, db_path=core._db_path())
    if updated == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "updated"})


@bp.route("/api/coupons/<int:coupon_id>", methods=["DELETE"])
@core.require_api_key_or_super_admin
def api_delete_coupon(coupon_id):
    deleted = core.delete_coupon(coupon_id, db_path=core._db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


@bp.route("/api/provider-deals", methods=["GET"])
@core.require_api_key_or_super_admin
def api_provider_deals():
    """Provider relationship/commission status, one row per tracked provider.

    Merges the manually curated CRM rows (seed_provider_deals.py) with two LIVE
    signals so the dashboard is always accurate without editing the seed:
      - coupon liveness from provider_coupons (is there a coupon in the air?)
      - affiliate clicks in the last 30d (is a live deal getting traffic?)
    """
    dbp = core._db_path()
    deals = core.get_provider_deals(db_path=dbp)

    # First live (active, non-expired) coupon per carrier.
    coupon_by_carrier = {}
    for c in core.get_active_coupons(db_path=dbp):
        car = c.get("carrier")
        if car and car not in coupon_by_carrier:
            coupon_by_carrier[car] = c

    # Clicks per provider over the last 30 days (attribution health).
    clicks_by_provider = {}
    try:
        for row in core.get_affiliate_stats(days=30, db_path=dbp):
            clicks_by_provider[row["provider"]] = \
                clicks_by_provider.get(row["provider"], 0) + row.get("clicks", 0)
    except Exception as exc:  # never fail the dashboard on a stats hiccup
        logger.warning(f"provider-deals: click stats unavailable: {exc}")

    for d in deals:
        pid = d["provider_id"]
        cp = coupon_by_carrier.get(pid)
        d["coupon_live"]     = bool(cp)
        d["coupon_code"]     = cp.get("code") if cp else None
        d["coupon_discount"] = cp.get("discount_label") if cp else None
        d["clicks_30d"]      = clicks_by_provider.get(pid, 0)

    return jsonify({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deals": deals,
    })
