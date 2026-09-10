"""Price history: change log, market movers, per-plan series + batch sparklines, daily aggregates (price_history_daily), maintenance trigger, AI analysis.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
logger = core.logger
from flask import Blueprint
bp = Blueprint("history", __name__)


@bp.route('/api/history/changes')
@core.limiter.limit('60 per minute')
def api_history_changes():
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400

    hidden = core._hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({'error': 'carrier not available for this workspace'}), 403

    changes = core.get_history_changes(carrier, plan_type, from_date, to_date, db_path=core._db_path())
    summary = {
        'total':         len(changes),
        'price_up':      sum(1 for c in changes if c['change_type'] == 'price_change' and core._price_direction(c) == 'up'),
        'price_down':    sum(1 for c in changes if c['change_type'] == 'price_change' and core._price_direction(c) == 'down'),
        'new_plans':     sum(1 for c in changes if c['change_type'] == 'new_plan'),
        'removed_plans': sum(1 for c in changes if c['change_type'] == 'removed_plan'),
    }
    return jsonify({'changes': changes, 'summary': summary})


@bp.route('/api/market-movers')
@core.limiter.limit('60 per minute')
def api_market_movers():
    """Top biggest price moves (by absolute %) in the last `days` days.
    Query params:
        days       (default 7)
        limit      (default 5)
        plan_types (default 'domestic,abroad,global'; comma-separated subset)
    """
    from db import get_market_movers as _gmm
    try:
        days  = max(1, min(int(request.args.get('days', 7)), 90))
    except (ValueError, TypeError):
        days = 7
    try:
        limit = max(1, min(int(request.args.get('limit', 5)), 20))
    except (ValueError, TypeError):
        limit = 5
    raw_types = request.args.get('plan_types', '').strip()
    plan_types = tuple(t.strip() for t in raw_types.split(',') if t.strip()) if raw_types else None
    movers = _gmm(days=days, limit=limit * 3, plan_types=plan_types, db_path=core._db_path())  # fetch extra, filter, then cap
    hidden = core._hidden_carrier_for_request()
    if hidden:
        movers = [m for m in movers if m.get('carrier') != hidden]
    return jsonify({'movers': movers[:limit], 'days': days})


@bp.route('/api/history/price-series')
@core.limiter.limit('60 per minute')
def api_history_price_series():
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    plan_name = request.args.get('plan_name', '')
    from_date = request.args.get('from', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
    hidden = core._hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({'error': 'carrier not available for this workspace'}), 403
    series = core.get_history_price_series(
        carrier, plan_type, plan_name, from_date, db_path=core._db_path()
    )
    return jsonify({'series': series})


@bp.route('/api/history/price-series/batch')
@core.limiter.limit('60 per minute')
def api_history_price_series_batch():
    """All plans' sparkline series for one tab in a single request — replaces the
    per-card N+1 that hit /price-series once per PlanCard. Keyed carrier|plan_name."""
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
    data = core.get_all_price_series(plan_type, from_date or None, db_path=core._db_path())
    hidden = core._hidden_carrier_for_request()
    if hidden:
        data = {k: v for k, v in data.items() if not k.startswith(hidden + '|')}
    resp = jsonify({'series': data})
    return core._public_cache(resp, 300)


@bp.route('/api/history/daily')
def api_history_daily():
    """Daily price aggregates from price_history_daily (maintenance.py) - the
    change-log-independent history source: min/avg/max price + cheapest ₪/GB
    per (plan_type, carrier, destination) per day.

    ?plan_type=domestic|abroad|global|content (required)
    &carrier=<id> &destination=<hebrew> (global/abroad; omit = all destinations)
    &from=YYYY-MM-DD &to=YYYY-MM-DD
    """
    import maintenance as _mt
    plan_type = request.args.get('plan_type', 'domestic')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
    carrier = request.args.get('carrier') or None
    hidden = core._hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({'error': 'carrier not available for this workspace'}), 403
    dest = request.args.get('destination')
    rows = _mt.get_price_history_daily(
        plan_type, carrier=carrier, destination=dest if dest is not None else None,
        from_day=request.args.get('from') or None, to_day=request.args.get('to') or None,
        db_path=core._db_path())
    if hidden:
        rows = [r for r in rows if r['carrier'] != hidden]
    resp = jsonify({'plan_type': plan_type, 'rows': rows})
    return core._public_cache(resp, 300)


@bp.route('/api/maintenance/run-now', methods=['GET', 'POST'])
@core.require_api_key_or_query
def api_maintenance_run_now():
    """Run a maintenance job on demand. ?job=weekly|daily|backfill  &dry_run=true
    weekly  = prune *_changes (+ optional archive thinning, VACUUM if &vacuum=true)
    daily   = build today's price_history_daily aggregates
    backfill = rebuild price_history_daily from archive_snapshots (&from=YYYY-MM-DD)"""
    import maintenance as _mt
    job = request.args.get('job', 'weekly')
    dry = request.args.get('dry_run', 'false').lower() == 'true'
    try:
        if job == 'weekly':
            out = _mt.run_weekly(core.load_config(), dry_run=dry,
                                 force_vacuum=request.args.get('vacuum', 'false').lower() == 'true')
        elif job == 'daily':
            out = _mt.run_daily(core.load_config())
        elif job == 'backfill':
            out = _mt.backfill_price_history_from_archive(from_date=request.args.get('from') or None,
                                                          overwrite=request.args.get('overwrite', 'false').lower() == 'true')
        else:
            return jsonify({'error': 'job must be weekly/daily/backfill'}), 400
        return jsonify(out)
    except Exception as e:
        logger.error(f"Maintenance job {job} failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/history/analyze')
@core.require_auth
@core.limiter.limit('10 per minute')
@core.limiter.limit(core._chat_daily_limit, key_func=core._chat_user_key)
def api_history_analyze():
    """AI analysis of historical price changes for a carrier using Claude Haiku.

    Auth: @require_auth (logged-in user or server API key) — this endpoint spends
    real Anthropic USD, so it must not be anonymously reachable. It's only called
    from the login-gated History tab, so gating it does not affect public pages.
    Rate limits: 10/min (per user/IP) PLUS the same per-user daily cap as /api/chat
    (_chat_daily_limit), so a single authenticated user can't drive unbounded spend.
    Note: to_date is not forwarded to get_history_price_series (unsupported by that function).
    """
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')

    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400

    hidden = core._hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({'error': 'carrier not available for this workspace'}), 403

    changes = core.get_history_changes(carrier, plan_type, from_date, to_date, db_path=core._db_path())
    if not changes:
        return jsonify({'analysis': None})

    series = core.get_history_price_series(carrier, plan_type, from_date=from_date, db_path=core._db_path())

    config = core.load_config()
    api_key = config.get('anthropic_api_key', '')
    if not api_key:
        return jsonify({'error': 'anthropic_api_key missing in config.json'}), 500

    carrier_display = core._HISTORY_CARRIER_NAMES.get(carrier, carrier)
    type_display    = core._HISTORY_TYPE_NAMES.get(plan_type, plan_type)

    if from_date and to_date:
        period_display = f'{from_date} \u05e2\u05d3 {to_date}'
    elif from_date:
        period_display = f'\u05de-{from_date} \u05e2\u05d3 \u05d4\u05d9\u05d5\u05dd'
    else:
        period_display = '\u05db\u05dc \u05d4\u05d6\u05de\u05e0\u05d9\u05dd'

    price_up      = sum(1 for c in changes if c['change_type'] == 'price_change' and core._price_direction(c) == 'up')
    price_down    = sum(1 for c in changes if c['change_type'] == 'price_change' and core._price_direction(c) == 'down')
    new_plans     = sum(1 for c in changes if c['change_type'] == 'new_plan')
    removed_plans = sum(1 for c in changes if c['change_type'] == 'removed_plan')
    extras_changes = sum(1 for c in changes if c['change_type'] in ('extras_change', 'details_change'))

    price_changes = [c for c in changes if c['change_type'] == 'price_change'][:20]
    price_lines = '\n'.join(
        f"  {c['plan_name']}: \u20aa{c['old_val']} \u2192 \u20aa{c['new_val']} ({c['changed_at'][:10]})"
        for c in price_changes
    ) or '  \u05d0\u05d9\u05df \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9 \u05de\u05d7\u05d9\u05e8'

    series_lines = '\n'.join(
        f"  {s['plan_name']}: \u20aa{s['points'][0]['price']} \u2192 \u20aa{s['points'][-1]['price']} ({len(s['points']) - 1} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd)"
        for s in series[:10]
    ) if series else '  \u05d0\u05d9\u05df \u05e0\u05ea\u05d5\u05e0\u05d9 \u05de\u05d2\u05de\u05d4'

    question = (
        f"\u05e0\u05ea\u05d7 \u05d0\u05ea \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9 \u05d4\u05de\u05d7\u05d9\u05e8 \u05e9\u05dc {carrier_display}"
        f" \u05d1\u05ea\u05d7\u05d5\u05dd {type_display} \u05d1\u05ea\u05e7\u05d5\u05e4\u05d4 {period_display}.\n\n"
        f"\u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd:\n"
        f'- \u05e1\u05d4"\u05db \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd: {len(changes)}\n'
        f"- \u05e2\u05dc\u05d9\u05d9\u05d5\u05ea \u05de\u05d7\u05d9\u05e8: {price_up}\n"
        f"- \u05d9\u05e8\u05d9\u05d3\u05d5\u05ea \u05de\u05d7\u05d9\u05e8: {price_down}\n"
        f"- \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05d7\u05d3\u05e9\u05d5\u05ea: {new_plans}\n"
        f"- \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05e9\u05d4\u05d5\u05e1\u05e8\u05d5: {removed_plans}\n"
        f"- \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9 \u05e4\u05e8\u05d8\u05d9\u05dd: {extras_changes}\n\n"
        f"\u05e4\u05d9\u05e8\u05d5\u05d8 \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9 \u05de\u05d7\u05d9\u05e8:\n{price_lines}\n\n"
        f"\u05de\u05d2\u05de\u05d5\u05ea \u05de\u05d7\u05d9\u05e8:\n{series_lines}"
    )

    system_prompt = (
        "\u05d0\u05ea\u05d4 \u05de\u05e0\u05ea\u05d7 \u05e0\u05ea\u05d5\u05e0\u05d9 \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05e9\u05dc \u05e1\u05e4\u05e7\u05d9 \u05e1\u05dc\u05d5\u05dc\u05e8 \u05d9\u05e9\u05e8\u05d0\u05dc\u05d9\u05d9\u05dd.\n"
        "\u05e2\u05e0\u05d4 \u05d1\u05e2\u05d1\u05e8\u05d9\u05ea \u05d1\u05dc\u05d1\u05d3, \u05d1\u05e6\u05d5\u05e8\u05d4 \u05ea\u05de\u05e6\u05d9\u05ea\u05d9\u05ea \u05d5\u05d1\u05e8\u05d5\u05e8\u05d4 \u2014 3 \u05e2\u05d3 5 \u05de\u05e9\u05e4\u05d8\u05d9\u05dd.\n"
        "\u05d4\u05ea\u05de\u05e7\u05d3 \u05d1\u05de\u05d2\u05de\u05d5\u05ea, \u05d1\u05d4\u05d9\u05e7\u05e3 \u05d4\u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05d5\u05d1\u05db\u05d9\u05d5\u05d5\u05df \u05d4\u05de\u05d7\u05d9\u05e8\u05d9\u05dd \u05d4\u05db\u05dc\u05dc\u05d9.\n"
        "\u05d0\u05dc \u05ea\u05e6\u05d9\u05d9\u05df \u05ea\u05d0\u05e8\u05d9\u05db\u05d9\u05dd \u05e1\u05e4\u05e6\u05d9\u05e4\u05d9\u05d9\u05dd \u05dc\u05db\u05dc \u05e9\u05d9\u05e0\u05d5\u05d9 \u2014 \u05ea\u05df \u05ea\u05de\u05d5\u05e0\u05d4 \u05db\u05d5\u05dc\u05dc\u05ea."
    )

    try:
        import requests as _req
        resp = _req.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 512,
                'system': system_prompt,
                'messages': [{'role': 'user', 'content': question}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        core._record_claude_call('history_analyze', 'claude-haiku-4-5-20251001', body,
                            user_email=core._caller_email())
        answer = body['content'][0]['text']
        return jsonify({'analysis': answer})
    except Exception as e:
        logger.error(f'history analyze failed: {e}', exc_info=True)
        return jsonify({'error': 'analysis failed'}), 500
