"""Hotel Guest Connect: /api/guest/<slug> portal + QR, hotel CRUD, analytics and lead capture.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
from flask import Blueprint
bp = Blueprint("hotels", __name__)


def _guest_ip_hash():
    ip = core._client_ip() or ""
    api_key = core.load_config().get("api_key", "")
    return hmac.new(api_key.encode(), ip.encode(), hashlib.sha256).hexdigest()


def _qr_svg(data, color="#111111", scale=10, border=3):
    """Branded QR as a compact single-path SVG. Quiet zone via `border`."""
    import qrcode
    qr = qrcode.QRCode(border=border, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    size = len(matrix) * scale
    seg = []
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                seg.append(f"M{x*scale} {y*scale}h{scale}v{scale}h{-scale}z")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}" shape-rendering="crispEdges" role="img" '
            f'aria-label="Guest portal QR">'
            f'<rect width="{size}" height="{size}" fill="#ffffff"/>'
            f'<path d="{"".join(seg)}" fill="{color}"/></svg>')


@bp.route("/api/guest/<slug>")
@core.limiter.limit("120 per minute")
def api_guest_portal(slug):
    """Public guest portal payload: hotel branding + live Israel deal feed."""
    hotel = core.get_hotel(slug, db_path=core._db_path())
    if not hotel or not hotel.get("active"):
        return jsonify({"error": "Guest portal not found"}), 404
    destination = hotel.get("country") or "ישראל"
    deals, providers, updated_at = core._assemble_guest_deals(db_path=core._db_path(), destination=destination)
    try:
        from scraper import _get_usd_to_ils
        fx = _get_usd_to_ils()
    except Exception:
        fx = 3.7
    # Discount codes for the providers in this feed (e.g. Saily MOCA 10%), first
    # active code per carrier (matches the main app's PlanCard behaviour).
    provs_in_feed = {d["provider"] for d in deals}
    guest_coupons = {}
    for c in core.get_active_coupons(db_path=core._db_path()):
        car = c["carrier"]
        if car in provs_in_feed and car not in guest_coupons:
            guest_coupons[car] = {
                "code": c["code"],
                "discount_label": c.get("discount_label"),
                "external_offer_url": c.get("external_offer_url"),
                "partner_name": c.get("partner_name"),
            }
    payload = {
        "hotel": {
            "slug": hotel["slug"], "name": hotel["name"], "tagline": hotel.get("tagline"),
            "brand": {
                "primary": hotel.get("brand_primary"), "secondary": hotel.get("brand_secondary"),
                "bg": hotel.get("brand_bg"), "mono": hotel.get("mono"),
                "logo_url": hotel.get("logo_url"),
            },
            "languages": hotel.get("languages") or ["en", "he"],
            "default_lang": hotel.get("default_lang") or "en",
            "country": destination,
        },
        "deals": deals,
        "providers": providers,
        "coupons": guest_coupons,
        "fx": round(fx, 3),
        "updated_at": updated_at or datetime.now(timezone.utc).isoformat(),
    }
    return core._public_cache(jsonify(payload), 300)


_GUEST_CLIENT_EVENTS = {"view", "scan", "engage"}


@bp.route("/api/guest/<slug>/event", methods=["POST"])
@core.limiter.limit("240 per minute")
def api_guest_event(slug):
    """Anonymous guest-portal beacon (view / scan / engage). 204, never errors."""
    if not core.get_hotel(slug, db_path=core._db_path()):
        return ("", 204)
    data = request.get_json(silent=True) or {}
    et = (data.get("event_type") or "").strip()
    if et not in _GUEST_CLIENT_EVENTS:
        return ("", 204)
    core.log_guest_event(
        slug, et, lang=(data.get("lang") or None),
        country=(request.headers.get("Accept-Language", "")[:8] or None),
        ip_hash=_guest_ip_hash(), user_agent=request.headers.get("User-Agent"),
        db_path=core._db_path(),
    )
    return ("", 204)


@bp.route("/api/guest/<slug>/qr.svg")
@core.limiter.limit("60 per minute")
def api_guest_qr(slug):
    """Branded QR (SVG) that deep-links to the hotel's guest portal."""
    hotel = core.get_hotel(slug, db_path=core._db_path())
    if not hotel:
        abort(404)
    base = (request.args.get("base") or "https://mocaintel.com").rstrip("/")
    url = f"{base}/guest/{slug}?via=qr"
    color = hotel.get("brand_primary") or "#5c3317"
    # brand_primary is admin-set but never validated as a color; it's reflected
    # verbatim into the SVG's fill="…". Restrict to a hex literal so a malformed
    # value can't inject markup into the image/svg+xml response.
    import re as _re
    if not _re.fullmatch(r"#[0-9A-Fa-f]{3,8}", color):
        color = "#5c3317"
    try:
        svg = _qr_svg(url, color=color)
    except Exception:
        core.app.logger.warning("QR generation failed (is 'qrcode' installed?)", exc_info=True)
        return jsonify({"error": "QR generation unavailable"}), 503
    resp = Response(svg, mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@bp.route("/api/hotels", methods=["GET"])
@core.require_api_key_or_super_admin
@core.limiter.limit("60 per minute")
def api_hotels_list():
    return jsonify(core.list_hotels(db_path=core._db_path()))


@bp.route("/api/hotels", methods=["POST"])
@core.require_api_key_or_super_admin
@core.limiter.limit("30 per minute")
def api_hotels_create():
    data = request.get_json(silent=True) or {}
    try:
        hotel = core.upsert_hotel(data, db_path=core._db_path())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(hotel), 201


@bp.route("/api/hotels/<slug>", methods=["PATCH"])
@core.require_api_key_or_super_admin
@core.limiter.limit("30 per minute")
def api_hotels_update(slug):
    existing = core.get_hotel(slug, db_path=core._db_path())
    if not existing:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    merged = {**existing, **data, "slug": slug}
    try:
        hotel = core.upsert_hotel(merged, db_path=core._db_path())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(hotel)


@bp.route("/api/hotels/<slug>", methods=["DELETE"])
@core.require_api_key_or_super_admin
@core.limiter.limit("30 per minute")
def api_hotels_delete(slug):
    core.delete_hotel(slug, db_path=core._db_path())
    return ("", 204)


@bp.route("/api/hotels/<slug>/analytics")
@core.require_api_key_or_super_admin
@core.limiter.limit("60 per minute")
def api_hotels_analytics(slug):
    try:
        days = max(0, min(int(request.args.get("days", 30)), 365))
    except (ValueError, TypeError):
        days = 30
    return jsonify(core.get_guest_analytics(slug, days=days, db_path=core._db_path()))


@bp.route("/api/hotels/leads")
@core.require_api_key_or_super_admin
@core.limiter.limit("60 per minute")
def api_hotels_leads():
    return jsonify(core.get_hotel_leads(db_path=core._db_path()))


def _notify_hotel_lead(lead):
    msg = (
        "🏨 ליד חדש — MOCA Guest Connect\n"
        f"מלון: {lead.get('hotel_name') or '—'}\n"
        f"איש קשר: {lead.get('contact_name') or '—'}\n"
        f"אימייל: {lead.get('email') or '—'}\n"
        f"טלפון: {lead.get('phone') or '—'}\n"
        f"חדרים: {lead.get('rooms') or '—'}\n"
        f"הודעה: {lead.get('message') or '—'}"
    )
    try:
        import notifier
        notifier.send_notification(msg, core.load_config())
    except Exception:
        core.app.logger.warning("hotel lead telegram failed", exc_info=True)


@bp.route("/api/hotels/lead", methods=["POST"])
@core.limiter.limit("10 per minute")
def api_hotels_lead():
    """Public lead capture from the /hotels marketing landing form."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not email and not phone:
        return jsonify({"error": "email or phone required"}), 400
    # Documented consent: the form's unchecked-by-default box (see privacy policy
    # "פניות מבתי מלון"); the lead is stored and forwarded to the operator's
    # internal channels (email/Telegram) only after it.
    if data.get("consent") is not True:
        return jsonify({"error": "consent required"}), 400
    try:
        rooms = int(data["rooms"]) if str(data.get("rooms", "")).strip() else None
    except (ValueError, TypeError):
        rooms = None
    lead = {
        "hotel_name": (data.get("hotel_name") or "")[:200],
        "contact_name": (data.get("contact_name") or "")[:200],
        "email": email[:200], "phone": phone[:60], "rooms": rooms,
        "message": (data.get("message") or "")[:2000], "source": "/hotels",
        "consent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "consent_version": str(data.get("consent_version") or "")[:40] or "unversioned",
    }
    core.save_hotel_lead(lead, db_path=core._db_path())
    _notify_hotel_lead(lead)
    return jsonify({"ok": True})
