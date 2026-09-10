"""Manual scrape triggers (/api/scrape-*-now), scrape progress SSE stream + the change-feed endpoints they share.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import os
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
import threading as _threading_progress
logger = core.logger
from flask import Blueprint
bp = Blueprint("scrape", __name__)


@bp.route("/api/global-changes")
@core.limiter.limit("60 per minute")
def api_global_changes():
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 500))
    except (ValueError, TypeError):
        limit = 50
    changes = core.get_global_changes(limit=limit, db_path=core._db_path())
    return core._public_cache(jsonify(core._filter_hidden_carrier(changes)), 600)


@bp.route("/api/scrape-global-now")
@core.require_api_key_or_query
def api_scrape_global_now():
    """Manual trigger: scrape global eSIM packages, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_global_plans, save_global_changes, filter_already_notified
        from change_detector import detect_changes
        old_plans = core.get_global_plans(db_path=core._db_path())
        new_plans = sc.scrape_all_global()
        existing_changes = core.get_global_changes(limit=1, db_path=core._db_path())
        if not existing_changes:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_plans]
            save_global_changes(seed, db_path=core._db_path())
            changes = seed
        else:
            changes = detect_changes(old_plans, new_plans, per_group_extras=True)
            # Global providers scrape hundreds of per-country pages; partial failures make
            # plans flap new/removed every run (~6,700 phantom rows/day). Keep only the
            # meaningful signal (price/extras/details) for global — price_change still
            # powers the history charts. Domestic/abroad are unaffected.
            changes = [c for c in changes if c["change_type"] not in ("new_plan", "removed_plan")]
            changes = filter_already_notified(changes, 'global_changes', db_path=core._db_path())
            if changes:
                save_global_changes(changes, db_path=core._db_path())
        save_global_plans(new_plans, db_path=core._db_path())
        purge = core._purge_stale_global(new_plans, core.load_config(), db_path=core._db_path())
        core.arc.archive_global_plans(new_plans)
        # B2C destination price-drop pushes — state-based (baseline vs current min),
        # so it must run after save_global_plans on EVERY global scrape path.
        try:
            from notifier import notify_esim_price_drops
            notify_esim_price_drops(core.load_config(), db_path=core._db_path())
        except Exception as e:
            logger.warning(f"esim price-drop push failed: {e}")
        return jsonify({"plans": len(new_plans), "changes": len(changes),
                        "purged": purge["purged"], "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-global-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/abroad-changes")
@core.limiter.limit("60 per minute")
def api_abroad_changes():
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except (ValueError, TypeError):
        limit = 50
    changes = core.get_abroad_changes(limit=limit, db_path=core._db_path())
    return core._public_cache(jsonify(core._filter_hidden_carrier(changes)), 600)


@bp.route("/api/scrape-abroad-now")
@core.require_api_key_or_query
def api_scrape_abroad_now():
    """Manual trigger: scrape abroad packages, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_abroad_plans, save_abroad_changes, filter_already_notified
        from change_detector import detect_changes
        old_plans = core.get_abroad_plans(db_path=core._db_path())
        new_plans = sc.scrape_all_abroad()
        # If abroad_changes is empty (first run), seed all plans as new_plan
        existing_changes = core.get_abroad_changes(limit=1, db_path=core._db_path())
        if not existing_changes:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_plans]
            save_abroad_changes(seed, db_path=core._db_path())
            changes = seed
        else:
            changes = detect_changes(old_plans, new_plans)
            changes = filter_already_notified(changes, 'abroad_changes', db_path=core._db_path())
            if changes:
                save_abroad_changes(changes, db_path=core._db_path())
        save_abroad_plans(new_plans, db_path=core._db_path())
        core.arc.archive_abroad_plans(new_plans)
        from notifier import alert_missing_terms
        alert_missing_terms(changes, new_plans, 'abroad_plans', core.load_config())
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-abroad-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


_scrape_progress = {
    'log': [],          # list of {at, stage, status, count, message}
    'active': False,
    'started_at': None,
    'completed_at': None,
}


_scrape_lock = _threading_progress.Lock()


_scrape_signal = _threading_progress.Condition()


def _scrape_emit(stage, status='running', count=None, message=None):
    """Push a progress event to subscribers. Cheap; safe to call from scraper threads."""
    ev = {
        'at': datetime.now(timezone.utc).isoformat(),
        'stage': stage,
        'status': status,
        'count': count,
        'message': message,
    }
    with _scrape_lock:
        _scrape_progress['log'].append(ev)
    with _scrape_signal:
        _scrape_signal.notify_all()


def _scrape_start():
    """Atomically claim the single-scrape slot. Returns True if acquired, or
    False if a full scrape (manual OR scheduled) is already running — both the
    /api/scrape-all-now handler and the scheduled run_scrape_job share this flag,
    so a manual refresh can't run on top of the 07:30/17:00 scheduled scrape (two
    Playwright passes at once would double the load on the single box and let a
    half-written DB state emit spurious price_change/removed_plan events). Release
    with _scrape_finish()."""
    with _scrape_lock:
        if _scrape_progress.get('active'):
            return False
        _scrape_progress['log'] = []
        _scrape_progress['active'] = True
        _scrape_progress['started_at'] = datetime.now(timezone.utc).isoformat()
        _scrape_progress['completed_at'] = None
    with _scrape_signal:
        _scrape_signal.notify_all()
    return True


def _scrape_finish(error=None):
    with _scrape_lock:
        _scrape_progress['active'] = False
        _scrape_progress['completed_at'] = datetime.now(timezone.utc).isoformat()
        if error:
            _scrape_progress['error'] = str(error)
    with _scrape_signal:
        _scrape_signal.notify_all()


@bp.route("/api/scrape-progress/stream")
@core.require_auth
def api_scrape_progress_stream():
    """Server-Sent Events stream of scrape progress events."""
    def gen():
        import json as _json
        last_idx = 0
        # Replay any existing events first
        with _scrape_lock:
            for ev in _scrape_progress['log']:
                yield f"data: {_json.dumps(ev)}\n\n"
            last_idx = len(_scrape_progress['log'])
            active = _scrape_progress['active']
        # If idle with no history, wait up to ~16s for a scrape to start.
        # The client opens SSE before dispatching the scrape API call, so
        # without this wait the stream closes with __idle__ before the scrape begins.
        startup_loops = 0
        while not active and last_idx == 0 and startup_loops < 8:
            with _scrape_signal:
                _scrape_signal.wait(timeout=2.0)
            with _scrape_lock:
                new_events = _scrape_progress['log'][last_idx:]
                last_idx = len(_scrape_progress['log'])
                active = _scrape_progress['active']
            for ev in new_events:
                yield f"data: {_json.dumps(ev)}\n\n"
            startup_loops += 1
        if not active and last_idx == 0:
            yield f"data: {_json.dumps({'stage': '__idle__'})}\n\n"
            return
        # Stream new events as they arrive
        idle_loops = 0
        while True:
            with _scrape_signal:
                _scrape_signal.wait(timeout=2.0)
            with _scrape_lock:
                new_events = _scrape_progress['log'][last_idx:]
                last_idx = len(_scrape_progress['log'])
                active = _scrape_progress['active']
            for ev in new_events:
                yield f"data: {_json.dumps(ev)}\n\n"
                idle_loops = 0
            if not active:
                yield f"data: {_json.dumps({'stage': '__done__'})}\n\n"
                return
            idle_loops += 1
            if idle_loops > 180:  # ~6 min max
                yield f"data: {_json.dumps({'stage': '__timeout__'})}\n\n"
                return
    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'}
    )


@bp.route("/api/scrape-progress/state")
@core.require_auth
def api_scrape_progress_state():
    """One-shot snapshot of current scrape progress (for clients that don't use SSE)."""
    with _scrape_lock:
        return jsonify({
            'active':       _scrape_progress['active'],
            'started_at':   _scrape_progress['started_at'],
            'completed_at': _scrape_progress['completed_at'],
            'log':          list(_scrape_progress['log'][-50:]),
        })


@bp.route("/api/scrape-all-now")
@core.require_scrape_auth
def api_scrape_all_now():
    """Scrape ALL tabs: domestic + abroad + global in one call."""
    ok, used, limit = core._check_refresh_quota()
    if not ok:
        return jsonify({"error": f"מכסת הרענון החודשית הגיעה לסיום ({used}/{limit}). מחכים לחודש הבא.", "quota_used": used, "quota_limit": limit}), 429
    if not _scrape_start():
        return jsonify({"error": "סריקה כבר רצה כרגע. נסו שוב בעוד כמה דקות.", "scrape_active": True}), 409
    try:
        import scraper as sc
        from db import save_plans, save_changes, save_abroad_plans, save_abroad_changes, \
                       save_global_plans, save_global_changes, filter_already_notified
        from change_detector import detect_changes
        results = {}

        # ── Domestic ──────────────────────────────────────────────────────
        _scrape_emit('domestic', 'starting', message='סורק חבילות סלולר ביתיות')
        old_domestic = core.get_plans(db_path=core._db_path())
        new_domestic = sc.scrape_all()
        ch_domestic  = detect_changes(old_domestic, new_domestic)
        save_plans(new_domestic, db_path=core._db_path())
        # Drop changes already announced in the last 24h so the dashboard
        # changes log isn't polluted with repeats from consecutive scrapes.
        ch_domestic = filter_already_notified(ch_domestic, 'changes', db_path=core._db_path())
        if ch_domestic:
            save_changes(ch_domestic, db_path=core._db_path())
        results["domestic"] = {"plans": len(new_domestic), "changes": len(ch_domestic)}
        _scrape_emit('domestic', 'done', count=len(new_domestic), message=f'{len(new_domestic)} חבילות, {len(ch_domestic)} שינויים')
        # Safety net: alert the operator if a newly-added plan arrived with no terms link.
        from notifier import alert_missing_terms
        _terms_cfg = core.load_config()
        alert_missing_terms(ch_domestic, new_domestic, 'plans', _terms_cfg)
        # /mobile-deals consumer price-drop push (event-driven off the fresh list).
        try:
            from notifier import notify_mobile_price_drops
            notify_mobile_price_drops(ch_domestic, _terms_cfg, db_path=core._db_path())
        except Exception as e:
            logger.warning(f"mobile price-drop push failed: {e}")

        # ── Abroad ────────────────────────────────────────────────────────
        _scrape_emit('abroad', 'starting', message='סורק חבילות חו"ל')
        old_abroad = core.get_abroad_plans(db_path=core._db_path())
        new_abroad = sc.scrape_all_abroad()
        existing_abroad_ch = core.get_abroad_changes(limit=1, db_path=core._db_path())
        if not existing_abroad_ch:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_abroad]
            save_abroad_changes(seed, db_path=core._db_path())
            ch_abroad = seed
        else:
            ch_abroad = detect_changes(old_abroad, new_abroad)
            ch_abroad = filter_already_notified(ch_abroad, 'abroad_changes', db_path=core._db_path())
            if ch_abroad:
                save_abroad_changes(ch_abroad, db_path=core._db_path())
        save_abroad_plans(new_abroad, db_path=core._db_path())
        results["abroad"] = {"plans": len(new_abroad), "changes": len(ch_abroad)}
        _scrape_emit('abroad', 'done', count=len(new_abroad), message=f'{len(new_abroad)} חבילות, {len(ch_abroad)} שינויים')
        alert_missing_terms(ch_abroad, new_abroad, 'abroad_plans', _terms_cfg)

        # ── Global ────────────────────────────────────────────────────────
        _scrape_emit('global', 'starting', message='סורק חבילות גלובל / eSIM')
        old_global = core.get_global_plans(db_path=core._db_path())
        new_global = sc.scrape_all_global()
        existing_global_ch = core.get_global_changes(limit=1, db_path=core._db_path())
        if not existing_global_ch:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_global]
            save_global_changes(seed, db_path=core._db_path())
            ch_global = seed
        else:
            ch_global = detect_changes(old_global, new_global, per_group_extras=True)
            # Drop global new/removed churn (per-country scrape flapping); keep price/extras/details.
            ch_global = [c for c in ch_global if c["change_type"] not in ("new_plan", "removed_plan")]
            ch_global = filter_already_notified(ch_global, 'global_changes', db_path=core._db_path())
            if ch_global:
                save_global_changes(ch_global, db_path=core._db_path())
        save_global_plans(new_global, db_path=core._db_path())
        purge_global = core._purge_stale_global(new_global, core.load_config(), db_path=core._db_path())
        try:
            from notifier import notify_esim_price_drops
            notify_esim_price_drops(core.load_config(), db_path=core._db_path())
        except Exception as e:
            logger.warning(f"esim price-drop push failed: {e}")
        results["global"] = {"plans": len(new_global), "changes": len(ch_global),
                             "purged": purge_global["purged"]}
        _scrape_emit('global', 'done', count=len(new_global), message=f'{len(new_global)} חבילות, {len(ch_global)} שינויים')

        # ── Content services ──────────────────────────────────────────────
        _scrape_emit('content', 'starting', message='סורק שירותי תוכן')
        from db import save_content_plans, save_content_changes
        from change_detector import detect_content_changes
        old_content = core.get_content_plans(db_path=core._db_path())
        new_content = sc.scrape_all_content()
        ch_content = detect_content_changes(old_content, new_content)
        save_content_plans(new_content, db_path=core._db_path())
        ch_content = filter_already_notified(ch_content, 'content_changes', key_field='service', db_path=core._db_path())
        if ch_content:
            save_content_changes(ch_content, db_path=core._db_path())
        results["content"] = {"plans": len(new_content), "changes": len(ch_content)}
        _scrape_emit('content', 'done', count=len(new_content), message=f'{len(new_content)} שירותים, {len(ch_content)} שינויים')

        # ── Archive plan snapshots ─────────────────────────────────────────
        _scrape_emit('archive', 'starting', message='שומר תמונת מצב לארכיון')
        core.arc.archive_domestic_plans(new_domestic)
        core.arc.archive_abroad_plans(new_abroad)
        core.arc.archive_global_plans(new_global)
        core.arc.archive_content_plans(new_content)
        _scrape_emit('archive', 'done')

        # ── Banners (homepage + e-store screenshots) ───────────────────────
        _scrape_emit('banners', 'starting', message='מצלם באנרים')
        banners_dir = os.path.join(os.path.dirname(os.path.abspath(core.__file__)), "data", "banners")
        from scraper import (scrape_carrier_banners, scrape_carrier_store_banners,
                             scrape_global_provider_banners)
        banner_results = scrape_carrier_banners(banners_dir)
        store_results  = scrape_carrier_store_banners(banners_dir)
        global_results = scrape_global_provider_banners(banners_dir)
        from scraper import GLOBAL_BANNER_URLS as _GBU
        core.arc.archive_all_banners(banners_dir, list(core.CARRIER_DISPLAY.keys()), list(core.CARRIER_STORE_DISPLAY.keys()))
        core.arc.archive_all_global_banners(banners_dir, list(_GBU.keys()))
        results["banners"] = {
            "homepage": sum(1 for r in banner_results if r["success"]),
            "store":    sum(1 for r in store_results  if r["success"]),
            "global":   sum(1 for r in global_results if r["success"]),
        }
        _scrape_emit('banners', 'done', count=results['banners']['homepage'] + results['banners']['store'] + results['banners']['global'])

        core._invalidate_plan_cache()
        results["status"] = "ok"
        results["total_plans"] = len(new_domestic) + len(new_abroad) + len(new_global) + len(new_content)
        results["total_changes"] = len(ch_domestic) + len(ch_abroad) + len(ch_global) + len(ch_content)
        results["quota_used"]  = used + 1
        results["quota_limit"] = limit
        core._log_refresh('scrape_all')
        _scrape_emit('all', 'completed', count=results['total_plans'],
                     message=f"סה\"כ {results['total_plans']} חבילות, {results['total_changes']} שינויים")
        _scrape_finish()
        logger.info(f"scrape-all-now: {results}")
        return jsonify(results)
    except Exception as e:
        import traceback as _tb
        tb_short = _tb.format_exc(limit=4)
        _scrape_emit('all', 'error', message=str(e))
        _scrape_finish(error=e)
        logger.error(f"scrape-all-now failed: {e}", exc_info=True)
        # Surface the actual error to the dashboard. This is a single-tenant
        # admin tool; the operator (Alon) needs to see what blew up rather
        # than the generic "Internal server error" toast that masks the cause.
        return jsonify({
            "error": f"שגיאה בסקרייפר: {type(e).__name__}: {e}",
            "exception": type(e).__name__,
            "message": str(e),
            "traceback": tb_short,
        }), 500


@bp.route("/api/content-plans")
@core.limiter.limit("60 per minute")
def api_content_plans():
    carrier = request.args.get("carrier")
    service = request.args.get("service")
    plans = core.get_content_plans(service=service, carrier=carrier, db_path=core._db_path())
    return core._public_cache(jsonify(core._filter_hidden_carrier(plans)), 600)


@bp.route("/api/content-changes")
@core.limiter.limit("60 per minute")
def api_content_changes():
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except (ValueError, TypeError):
        limit = 50
    changes = core.get_content_changes(limit=limit, db_path=core._db_path())
    return core._public_cache(jsonify(core._filter_hidden_carrier(changes)), 600)


@bp.route("/api/scrape-resellers-now")
@core.require_api_key_or_query
def api_scrape_resellers_now():
    """Manual trigger: scrape all below-the-line reseller sources, diff + save.

    Same logic as the daily 08:15 job — changes land in reseller_changes and
    surface in the next morning digest's "מתחת לקו" section.
    """
    try:
        return jsonify({"status": "ok", "modules": core.scrape_resellers_job()})
    except Exception as e:
        logger.error(f"scrape-resellers-now failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/scrape-content-now")
@core.require_api_key_or_query
def api_scrape_content_now():
    """Manual trigger: scrape content services, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_content_plans, save_content_changes, filter_already_notified
        from change_detector import detect_content_changes
        old_plans = core.get_content_plans(db_path=core._db_path())
        new_plans = sc.scrape_all_content()
        changes = detect_content_changes(old_plans, new_plans)
        save_content_plans(new_plans, db_path=core._db_path())
        changes = filter_already_notified(changes, 'content_changes', key_field='service', db_path=core._db_path())
        if changes:
            save_content_changes(changes, db_path=core._db_path())
        core.arc.archive_content_plans(new_plans)
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-content-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/scrape-now")
@core.require_api_key_or_query
def api_scrape_now():
    """Manual trigger for testing. Debug endpoint."""
    try:
        import scraper as sc
        from db import save_plans, save_changes, filter_already_notified
        from change_detector import detect_changes
        from notifier import format_message

        new_plans = sc.scrape_all()
        old_plans = core.get_plans(db_path=core._db_path())
        changes = detect_changes(old_plans, new_plans)
        save_plans(new_plans, db_path=core._db_path())
        changes = filter_already_notified(changes, 'changes', db_path=core._db_path())
        if changes:
            save_changes(changes, db_path=core._db_path())
        core.arc.archive_domestic_plans(new_plans)
        from notifier import alert_missing_terms
        alert_missing_terms(changes, new_plans, 'plans', core.load_config())
        try:
            from notifier import notify_mobile_price_drops
            notify_mobile_price_drops(changes, core.load_config(), db_path=core._db_path())
        except Exception as e:
            logger.warning(f"mobile price-drop push failed: {e}")
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500
