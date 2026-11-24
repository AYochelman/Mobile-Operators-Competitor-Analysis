"""Carrier / e-store / global-provider banner screenshots and the Time Machine archive endpoints.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import json
import os
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
from flask import Blueprint
bp = Blueprint("banners", __name__)


@bp.route("/api/banners")
@core.limiter.limit("60 per minute")
def api_banners():
    """Return metadata for all carrier homepage banner screenshots."""
    banners_dir = os.path.join(os.path.dirname(os.path.abspath(core.__file__)), "data", "banners")
    result = []
    for carrier, meta in core.CARRIER_DISPLAY.items():
        png_path = os.path.join(banners_dir, f"{carrier}.png")
        scraped_at = None
        image_url = None
        if os.path.exists(png_path):
            mtime = os.path.getmtime(png_path)
            scraped_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            # ?v=<mtime> busts the PWA CacheFirst entry whenever the file changes.
            image_url = f"/banners/{carrier}.png?v={int(mtime)}"
        result.append({
            "carrier":    carrier,
            "name":       meta["name"],
            "url":        meta["url"],
            "color":      meta["color"],
            "image_url":  image_url,
            "scraped_at": scraped_at,
        })
    return core._public_cache(jsonify(core._filter_hidden_carrier(result)), 600)


@bp.route("/api/store-banners")
@core.limiter.limit("60 per minute")
def api_store_banners():
    """Return metadata for carrier e-store banner screenshots."""
    banners_dir = os.path.join(os.path.dirname(os.path.abspath(core.__file__)), "data", "banners")
    result = []
    for carrier, meta in core.CARRIER_STORE_DISPLAY.items():
        png_path = os.path.join(banners_dir, f"{carrier}_store.png")
        scraped_at = None
        image_url = None
        if os.path.exists(png_path):
            mtime = os.path.getmtime(png_path)
            scraped_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            image_url = f"/banners/{carrier}_store.png?v={int(mtime)}"
        result.append({
            "carrier":    carrier,
            "name":       meta["name"],
            "url":        meta["url"],
            "color":      meta["color"],
            "image_url":  image_url,
            "scraped_at": scraped_at,
        })
    return core._public_cache(jsonify(core._filter_hidden_carrier(result)), 600)


@bp.route("/api/global-banners")
@core.limiter.limit("60 per minute")
def api_global_banners():
    """Return metadata for global eSIM provider homepage banner screenshots.

    Providers + homepage URLs come from scraper.GLOBAL_BANNER_URLS; display
    name/color come from _GUEST_PROVIDER_META (same source that drives the
    provider chips). Files are {provider}_global.png in data/banners/.
    """
    from scraper import GLOBAL_BANNER_URLS
    banners_dir = os.path.join(os.path.dirname(os.path.abspath(core.__file__)), "data", "banners")
    # Freshness state (provider -> {hash, changed_at}) written by the scraper.
    state = {}
    try:
        with open(os.path.join(banners_dir, "_global_banner_state.json"), "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    now = datetime.now(timezone.utc)
    result = []
    for provider, url in GLOBAL_BANNER_URLS.items():
        meta = core._GUEST_PROVIDER_META.get(provider, {})
        png_path = os.path.join(banners_dir, f"{provider}_global.png")
        scraped_at = None
        image_url = None
        if os.path.exists(png_path):
            mtime = os.path.getmtime(png_path)
            scraped_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            image_url = f"/banners/{provider}_global.png?v={int(mtime)}"
        # changed_at = last time the homepage campaign visibly changed (perceptual
        # hash drift). changed_recently drives the "התעדכן" freshness badge.
        changed_at = (state.get(provider) or {}).get("changed_at")
        changed_recently = False
        if changed_at:
            try:
                changed_recently = (now - datetime.fromisoformat(changed_at)).total_seconds() <= 48 * 3600
            except Exception:
                changed_recently = False
        result.append({
            "carrier":    provider,
            "name":       meta.get("label") or provider,
            "url":        meta.get("url") or (f"https://{meta['domain']}" if meta.get("domain") else url),
            "color":      meta.get("color") or "#8a6a4a",
            "image_url":  image_url,
            "scraped_at": scraped_at,
            "changed_at": changed_at,
            "changed_recently": changed_recently,
            "changed_today": changed_recently,
        })
    return core._public_cache(jsonify(core._filter_hidden_carrier(result)), 600)


def banner_vision_sources(scope="domestic"):
    """The screenshots banner_vision.py may read, as [{key, carrier, kind, name, file}].
    scope: domestic (homepages + e-stores) | global | all."""
    out = []
    if scope in ("domestic", "all"):
        for carrier, meta in core.CARRIER_DISPLAY.items():
            out.append({"key": carrier, "carrier": carrier, "kind": "home",
                        "name": meta["name"], "file": f"{carrier}.png"})
        for carrier, meta in core.CARRIER_STORE_DISPLAY.items():
            out.append({"key": f"{carrier}_store", "carrier": carrier, "kind": "store",
                        "name": meta["name"], "file": f"{carrier}_store.png"})
    if scope in ("global", "all"):
        from scraper import GLOBAL_BANNER_URLS
        for provider in GLOBAL_BANNER_URLS:
            meta = core._GUEST_PROVIDER_META.get(provider, {})
            out.append({"key": f"{provider}_global", "carrier": provider, "kind": "global",
                        "name": meta.get("label") or provider, "file": f"{provider}_global.png"})
    return out


def run_banner_vision_job(config=None, dry_run=False, limit=None, scope=None, force=False):
    """Read the banners whose image changed (banner_vision.py) and Telegram the
    campaign switches. Called after the banner capture of every scheduled scrape."""
    import banner_vision as _bv
    config = config or core.load_config()
    banners_dir = os.path.join(os.path.dirname(os.path.abspath(core.__file__)), "data", "banners")
    scope = scope or config.get("banner_vision_scope") or "domestic"
    out = _bv.run(config, banners_dir, banner_vision_sources(scope), db_path=core._db_path(),
                  record=lambda model, body: core._record_claude_call("banner_vision", model, body),
                  dry_run=dry_run, limit=limit, force=force)
    if out.get("changed") and not dry_run and config.get("banner_vision_notify", True):
        try:
            from notifier import send_notification
            send_notification(_bv.changes_message(out["changed"]), config)
        except Exception as exc:
            core.logger.warning("banner vision: notify failed: %s", exc)
    return out


@bp.route("/api/banner-insights")
@core.limiter.limit("60 per minute")
def api_banner_insights():
    """What the banner screenshots say: the current reading per banner and the
    campaign switches of the last `days` days (banner_vision.py).
    ?scope=domestic|global|all &days=30"""
    import banner_vision as _bv
    scope = request.args.get("scope", "domestic")
    if scope not in ("domestic", "global", "all"):
        return jsonify({"error": "scope must be domestic/global/all"}), 400
    try:
        days = max(1, min(int(request.args.get("days", 30)), 180))
    except (ValueError, TypeError):
        days = 30
    keys = {s["key"]: s for s in banner_vision_sources(scope)}
    hidden = core._hidden_carrier_for_request()
    ok = lambda r: r["banner_key"] in keys and r["carrier"] != hidden
    name = lambda r: dict(r, name=keys[r["banner_key"]]["name"])
    latest = {k: name(r) for k, r in _bv.latest_rows(core._db_path()).items() if ok(r)}
    changes = [name(r) for r in _bv.recent_changes(days, core._db_path()) if ok(r)]
    return core._public_cache(jsonify({"scope": scope, "days": days, "latest": latest, "changes": changes}), 300)


@bp.route("/api/banner-insights/run-now", methods=["GET", "POST"])
@core.require_api_key_or_query
def api_banner_insights_run_now():
    """Manual trigger / preview. &dry_run=true lists what WOULD be read (no API
    call, no cost); &limit=N caps the readings; &scope=...; &force=true ignores
    the unchanged-image and once-a-day guards."""
    flag = lambda k: request.args.get(k, "").lower() in ("1", "true", "yes")
    try:
        limit = int(request.args["limit"]) if request.args.get("limit") else None
    except ValueError:
        limit = None
    return jsonify(run_banner_vision_job(dry_run=flag("dry_run"), limit=limit,
                                         scope=request.args.get("scope") or None, force=flag("force")))


@bp.route("/api/archive")
@core.limiter.limit("60 per minute")
def api_archive():
    """
    GET /api/archive?carrier=<id>&date=<YYYY-MM-DD>

    Returns the latest plan snapshots and banner info for the given
    carrier on or before the requested date.
    """
    carrier = request.args.get("carrier", "").strip()
    date_str = request.args.get("date", "").strip()
    if not carrier or not date_str:
        return jsonify({"error": "carrier and date are required"}), 400

    # Block direct URL access to the workspace's own carrier. Matches the
    # filtering applied to list endpoints — a Partner user shouldn't be able
    # to `?carrier=partner` their way around the hide_self_carrier flag.
    hidden = core._hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({"error": "carrier not available for this workspace"}), 403

    plan_rows = core.get_archive_plans(carrier, date_str, db_path=core._db_path())
    banner_rows = core.get_archive_banners(carrier, date_str, db_path=core._db_path())

    plans_by_type = {}
    for row in plan_rows:
        plans_by_type[row["plan_type"]] = {
            "snapshot_date": row["snapshot_date"],
            "plans": row["plans"],
        }

    banners = {}
    for b in banner_rows:
        key = "store" if b["is_store"] else "homepage"
        banners[key] = {
            "archive_date": b["archive_date"],
            "url": f"/archive-banners/{b['file_path'].replace(os.sep, '/')}",
        }

    return jsonify({
        "carrier": carrier,
        "date": date_str,
        "plans": plans_by_type,
        "banners": banners,
    })


@bp.route("/api/archive/date-range")
@core.limiter.limit("60 per minute")
def api_archive_date_range():
    """Returns the earliest and latest dates available in the archive."""
    return jsonify(core.get_archive_date_range(db_path=core._db_path()))


_ARCHIVE_BANNER_ROOT = os.path.realpath(os.path.join(
    os.path.dirname(os.path.abspath(core.__file__)), "data", "archive", "banners"
))


@bp.route("/archive-banners/<path:filepath>")
def serve_archive_banner(filepath):
    """Serve archived banner PNG files. Contained strictly to data/archive/banners/."""
    # Stored DB paths are relative to the app root (e.g. "data/archive/banners/<carrier>/<date>.png").
    # Strip the leading data/archive/banners/ prefix if present so we can contain to that root.
    norm = filepath.replace("\\", "/").lstrip("/")
    prefix = "data/archive/banners/"
    if norm.startswith(prefix):
        norm = norm[len(prefix):]

    # Reject absolute paths and obvious traversal early
    if not norm or norm.startswith(("/", "\\")) or ":" in norm:
        abort(404)

    full = os.path.realpath(os.path.join(_ARCHIVE_BANNER_ROOT, norm))
    if not (full == _ARCHIVE_BANNER_ROOT or full.startswith(_ARCHIVE_BANNER_ROOT + os.sep)):
        abort(404)
    if not os.path.isfile(full):
        abort(404)
    # Use the file's own directory so send_from_directory never sees a subpath
    return send_from_directory(os.path.dirname(full), os.path.basename(full))
