"""Public /esim-deals consumer API: destinations, compare feed, event beacons, destination price-drop push alerts, analytics.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
from flask import Blueprint
bp = Blueprint("esim", __name__)


@bp.route("/api/esim/destinations")
@core.limiter.limit("60 per minute")
def api_esim_destinations():
    """Destinations that currently have live global-eSIM deals, for the consumer
    destination picker: canonical Hebrew name + deal count + cheapest price."""
    dests = core.get_esim_destinations(db_path=core._db_path())
    return core._public_cache(jsonify(dests), 600)


@bp.route("/api/esim/compare")
@core.limiter.limit("60 per minute")
def api_esim_compare():
    """Public consumer feed: cheapest live global-eSIM deals for a destination.
    Same shape as the guest portal minus hotel branding, global providers only."""
    destination = (request.args.get("destination") or core.ISRAEL_HE).strip()
    deals, providers, updated_at = core._assemble_guest_deals(
        db_path=core._db_path(), destination=destination, include_local=False)
    # Live FX so the consumer page can show an accurate ₪ headline computed from
    # each deal's native original_price (the stored `price` column uses a stale
    # scrape-time rate and understates by ~20%).
    try:
        from scraper import _get_usd_to_ils, _get_eur_to_ils, _get_gbp_to_ils
        fx = {"usd": round(_get_usd_to_ils(), 3), "eur": round(_get_eur_to_ils(), 3),
              "gbp": round(_get_gbp_to_ils(), 3)}
    except Exception:
        fx = {"usd": 3.7, "eur": 4.0, "gbp": 4.7}
    # First active discount code per provider in the feed (matches PlanCard).
    provs_in_feed = {d["provider"] for d in deals}
    coupons = {}
    for c in core.get_active_coupons(db_path=core._db_path()):
        car = c["carrier"]
        if car in provs_in_feed and car not in coupons:
            coupons[car] = {
                "code": c["code"], "discount_label": c.get("discount_label"),
                "external_offer_url": c.get("external_offer_url"),
                "partner_name": c.get("partner_name"),
            }
    payload = {
        "destination": destination,
        "deals": deals,
        "providers": providers,
        "coupons": coupons,
        "fx": fx,
        "updated_at": updated_at or datetime.now(timezone.utc).isoformat(),
    }
    return core._public_cache(jsonify(payload), 300)


@bp.route("/api/esim/event", methods=["POST"])
@core.limiter.limit("240 per minute")
def api_esim_event():
    """Anonymous traffic beacon from the public B2C eSIM page (page_view /
    destination_pick). No auth, no PII — ip hashed, sid is a random session token.
    Deal clicks are logged separately by the /go redirect (src='esim')."""
    body = request.get_json(silent=True) or {}
    etype = (body.get("type") or "").strip()
    if etype not in ("page_view", "destination_pick", "pwa_install"):
        return jsonify({"ok": False}), 400
    core.log_esim_event(
        etype,
        sid=body.get("sid"),
        destination=(body.get("destination") or None),
        src=(body.get("src") or None),
        campaign=(body.get("campaign") or None),
        lang=(body.get("lang") or None),
        referrer=(body.get("referrer") or None),
        ip_hash=core._guest_ip_hash(),
        db_path=core._db_path(),
    )
    return jsonify({"ok": True})


@bp.route("/api/esim/push/subscribe", methods=["POST"])
@core.limiter.limit("10 per minute")
def api_esim_push_subscribe():
    """Public (no auth): destination price-drop alert from the B2C eSIM page.
    Body: { subscription: {endpoint, keys:{p256dh,auth}}, destination, lang }.
    One alert per device — re-subscribing moves the alert to the new destination.
    The baseline is the destination's current cheapest TRIP-SIZED ₪ price
    (db.get_esim_alert_floor), so the first push only fires on a genuine
    post-subscribe drop (see notify_esim_price_drops)."""
    from db import save_esim_push_subscription
    body = request.get_json(silent=True) or {}
    sub = body.get("subscription") or {}
    endpoint = (sub.get("endpoint") or "").strip()
    keys = sub.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    destination = (body.get("destination") or "").strip()
    lang = body.get("lang") if body.get("lang") in ("he", "en") else "he"
    if not all([endpoint, p256dh, auth, destination]) or len(destination) > 80:
        return jsonify({"error": "missing fields"}), 400
    if not endpoint.startswith("https://"):
        return jsonify({"error": "bad endpoint"}), 400
    # Only destinations that actually carry live deals are subscribable (also
    # blocks junk rows from hand-crafted requests).
    live = {d["destination"] for d in core.get_esim_destinations(db_path=core._db_path())}
    if destination not in live:
        return jsonify({"error": "unknown destination"}), 400
    from db import get_esim_alert_floor
    baseline = get_esim_alert_floor(destination, db_path=core._db_path())
    save_esim_push_subscription(endpoint, p256dh, auth, destination, lang=lang,
                                baseline_price=baseline, db_path=core._db_path())
    core.log_esim_event("push_subscribe", sid=body.get("sid"), destination=destination,
                   src=(body.get("src") or None), campaign=(body.get("campaign") or None),
                   lang=lang, ip_hash=core._guest_ip_hash(), db_path=core._db_path())
    return jsonify({"status": "subscribed", "baseline": baseline}), 201


@bp.route("/api/esim/push/unsubscribe", methods=["DELETE", "POST"])
@core.limiter.limit("10 per minute")
def api_esim_push_unsubscribe():
    """Public: remove a B2C price-drop subscription by its push endpoint."""
    from db import delete_esim_push_subscription
    body = request.get_json(silent=True) or {}
    endpoint = (body.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400
    deleted = delete_esim_push_subscription(endpoint, db_path=core._db_path())
    return jsonify({"status": "unsubscribed", "deleted": deleted}), 200


@bp.route("/api/esim/analytics")
@core.require_api_key_or_super_admin
@core.limiter.limit("60 per minute")
def api_esim_analytics():
    """B2C eSIM traffic dashboard: views / sessions / picks / clicks funnel by day,
    destination, source and campaign. Admin-only (dev key or super_admin JWT)."""
    try:
        days = max(0, min(int(request.args.get("days", 30)), 365))
    except (ValueError, TypeError):
        days = 30
    return jsonify(core.get_esim_analytics(days=days, db_path=core._db_path()))
