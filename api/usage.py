"""Super-admin analytics: Claude API usage + budget, official Anthropic cost, user-activity overview, notification settings.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import json
import os
import time as _time
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
logger = core.logger
from flask import Blueprint
bp = Blueprint("usage", __name__)


def _claude_budget_block(summary, db_path):
    """Remaining-balance + depletion forecast from the user-set budget.

    Anthropic exposes no balance/credit endpoint (see CLAUDE_PRICING_DEFAULT
    note), so ``claude_budget_usd`` in config.json is the authoritative total
    the user entered (the credit they topped up). Remaining = budget − logged
    spend: lifetime by default, or only spend on/after ``claude_budget_as_of``
    when set (reset that baseline after a top-up). The burn rate uses the
    selected window's daily pace, so the forecast adapts to the 7/30/90-day view.
    Returns ``{"configured": False}`` when no budget is set.
    """
    cfg = core.load_config()
    raw_total = cfg.get("claude_budget_usd")
    as_of = cfg.get("claude_budget_as_of") or None
    try:
        total = float(raw_total) if raw_total not in (None, "") else 0.0
    except (TypeError, ValueError):
        total = 0.0
    if total <= 0:
        return {"configured": False, "total_usd": None, "as_of": as_of}

    since_iso = f"{as_of}T00:00:00+00:00" if as_of else None
    spend = core.get_claude_spend(since_iso=since_iso, db_path=db_path)
    spent = float(spend["cost_usd"] or 0)
    remaining = max(0.0, total - spent)

    forecast = {
        "daily_burn_usd": None, "days_left": None, "depletion_date": None,
        "basis_days": 0, "window_days": summary.get("window_days"),
    }
    by_day = summary.get("by_day") or []
    window_spend = float((summary.get("total") or {}).get("cost_usd") or 0)
    if by_day and window_spend > 0:
        try:
            # by_day is ordered DESC, so the last entry is the earliest day that
            # actually has usage in the window — dividing by the *active span*
            # (not the nominal window) avoids understating the burn rate when the
            # data only covers part of a 30-day window.
            earliest = datetime.strptime(by_day[-1]["day"], "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            span = max(1, (today - earliest).days + 1)
            burn = window_spend / span
            forecast["daily_burn_usd"] = round(burn, 6)
            forecast["basis_days"] = span
            if remaining <= 0:
                forecast["days_left"] = 0
                forecast["depletion_date"] = today.isoformat()
            elif burn > 0:
                days_left = remaining / burn
                forecast["days_left"] = round(days_left, 1)
                dep = today + timedelta(days=int(min(days_left, 3650)))
                forecast["depletion_date"] = dep.isoformat()
        except (ValueError, TypeError):
            pass

    return {
        "configured": True,
        "total_usd": round(total, 2),
        "as_of": as_of,
        "spent_usd": round(spent, 6),
        "remaining_usd": round(remaining, 6),
        "pct_used": round(min(100.0, (spent / total) * 100), 1),
        "calls_counted": spend["calls"],
        "forecast": forecast,
    }


# Org-wide spend pulled from Anthropic's Admin Cost API. Cached because the API
# asks for <=1 poll/min and the call is paginated/slow; keyed by the window.
_ANTHROPIC_COST_CACHE = {}   # (starting_at, ending_at) -> (epoch_ts, result_dict)


_ANTHROPIC_COST_TTL = 600    # 10 minutes


def _fetch_anthropic_cost_usd(starting_at, ending_at=None, force=False):
    """Authoritative org-wide spend (USD) from Anthropic's Admin Cost API.

    Requires config.json:anthropic_admin_key (an org Admin key, `sk-ant-admin...`
    — NOT available for individual accounts). Anthropic has no remaining-balance
    endpoint, so this returns SPEND, not balance. The API's `amount` is in the
    lowest currency unit (cents) as a decimal string, so the sum is /100.

    Returns {configured, total_usd, currency, since, status, error}.
    """
    import urllib.request as _ur, urllib.parse as _up, urllib.error as _ue

    result = {"configured": False, "total_usd": None, "currency": "USD",
              "since": starting_at, "status": None, "error": None}
    try:
        key = (core.load_config().get("anthropic_admin_key") or "").strip()
    except Exception:
        key = ""
    if not key:
        return result
    result["configured"] = True

    cache_key = (starting_at, ending_at)
    now = _time.time()
    if not force and cache_key in _ANTHROPIC_COST_CACHE:
        ts, val = _ANTHROPIC_COST_CACHE[cache_key]
        if now - ts < _ANTHROPIC_COST_TTL:
            return val

    total_cents = 0.0
    currency = "USD"
    page = None
    try:
        for _ in range(60):  # hard page cap
            params = {"starting_at": starting_at, "bucket_width": "1d", "limit": 31}
            if ending_at:
                params["ending_at"] = ending_at
            if page:
                params["page"] = page
            url = "https://api.anthropic.com/v1/organizations/cost_report?" + _up.urlencode(params)
            req = _ur.Request(url, headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            })
            with _ur.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
            for bucket in body.get("data", []):
                for item in bucket.get("results", []):
                    try:
                        total_cents += float(item.get("amount") or 0)
                    except (TypeError, ValueError):
                        pass
                    if item.get("currency"):
                        currency = item["currency"]
            if body.get("has_more") and body.get("next_page"):
                page = body["next_page"]
            else:
                break
        result.update({"total_usd": round(total_cents / 100.0, 6),
                       "currency": currency, "status": 200})
    except _ue.HTTPError as e:
        result["status"] = e.code
        result["error"] = f"HTTP {e.code}"
    except Exception as e:
        result["error"] = str(e)[:200]

    _ANTHROPIC_COST_CACHE[cache_key] = (now, result)
    return result


@bp.route('/api/usage/summary')
@core.require_api_key_or_super_admin
def api_usage_summary():
    """Aggregate Anthropic API usage + computed USD cost.

    Query params:
      days=N  — window in days (default 30, 0 = lifetime totals)

    Anthropic does not expose a balance/credit endpoint, so this is a *local*
    estimate based on the per-MTok pricing in CLAUDE_PRICING_DEFAULT
    (overridable via config.json:claude_pricing). Numbers are token-accurate;
    USD figures match the bill only if the pricing table is current.
    """
    try:
        days = int(request.args.get('days', '30'))
    except ValueError:
        days = 30
    summary = core.get_claude_usage_summary(days=days, db_path=core._db_path())
    summary['pricing'] = {
        m: core.CLAUDE_PRICING_DEFAULT[m] for m in core.CLAUDE_PRICING_DEFAULT
    }
    summary['budget'] = _claude_budget_block(summary, core._db_path())
    summary['note'] = (
        'Estimated locally — Anthropic has no balance API. '
        'Check console.anthropic.com/settings/billing for the authoritative balance.'
    )
    return jsonify(summary)


@bp.route('/api/usage/recent')
@core.require_api_key_or_super_admin
def api_usage_recent():
    """Return the N most recent Anthropic API calls (default 100, max 500)."""
    try:
        limit = max(1, min(500, int(request.args.get('limit', '100'))))
    except ValueError:
        limit = 100
    rows = core.get_claude_usage_recent(limit=limit, db_path=core._db_path())
    return jsonify({'calls': rows, 'count': len(rows)})


@bp.route('/api/activity/overview')
@core.require_api_key_or_super_admin
def api_activity_overview():
    """Per-user activity overview for the super-admin user dashboard.

    Merges the cross-workspace user list (auth.users + user_roles) with
    per-user activity aggregates. Super-admins are omitted from the table
    (their activity is never recorded). days=0 = lifetime. super_admin /
    dev-api-key only.
    """
    try:
        try:
            days = int(request.args.get('days', '30'))
        except ValueError:
            days = 30

        # 1. Cross-workspace user list + each user's workspace_id (one query),
        #    plus workspace id->name (one query — avoids N+1).
        conn = core._supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.created_at,
                   COALESCE(r.role, 'viewer') AS role,
                   u.last_sign_in_at, r.workspace_id
            FROM auth.users u
            LEFT JOIN public.user_roles r ON u.id = r.user_id
            ORDER BY u.created_at DESC
        """)
        user_rows = cur.fetchall()
        cur.execute("SELECT id, name FROM public.workspaces")
        ws_names = {str(i): n for i, n in cur.fetchall()}
        conn.close()

        # 2. Activity aggregates keyed by lowercased email.
        overview = {o['user_email']: o
                    for o in core.get_user_activity_overview(days=days, db_path=core._db_path())}

        users = []
        for uid, email, created_at, role, last_sign_in, ws_id in user_rows:
            if role == 'super_admin':
                continue  # exclude super-admins (operator) from the dashboard
            act = overview.get((email or '').strip().lower(), {})
            users.append({
                "id": str(uid), "email": email, "role": role,
                "created_at": str(created_at) if created_at else None,
                "last_sign_in_at": str(last_sign_in) if last_sign_in else None,
                "workspace_id": str(ws_id) if ws_id else None,
                "workspace_name": ws_names.get(str(ws_id)) if ws_id else None,
                "logins": act.get('logins', 0),
                "page_views": act.get('page_views', 0),
                "alerts_created": act.get('alerts_created', 0),
                "watchlist_added": act.get('watchlist_added', 0),
                "watchlist_removed": act.get('watchlist_removed', 0),
                "comparisons_saved": act.get('comparisons_saved', 0),
                "chat_used": act.get('chat_used', 0),
                "active_days": act.get('active_days', 0),
                "first_seen": act.get('first_seen'),
                "last_seen": act.get('last_seen'),
            })

        summary = core.get_user_activity_summary(days=days, db_path=core._db_path())
        summary['total_users'] = len(users)
        summary['active_today'] = len(core.get_user_activity_overview(days=1, db_path=core._db_path()))
        summary['active_this_week'] = len(core.get_user_activity_overview(days=7, db_path=core._db_path()))
        summary['active_this_month'] = len(core.get_user_activity_overview(days=30, db_path=core._db_path()))

        # Opportunistic retention prune (rare; DELETE only — keep the table bounded
        # without a cron). 180-day retention.
        import random as _rnd
        if _rnd.random() < 0.02:
            try:
                core.prune_user_activity(db_path=core._db_path())
            except Exception:
                pass

        return jsonify({"users": users, "summary": summary})
    except Exception as e:
        logger.error(f"activity overview failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route('/api/activity/events')
@core.require_api_key_or_super_admin
def api_activity_events():
    """Raw per-user activity feed for the dashboard drill-down (newest first).
    super_admin / dev-api-key only."""
    try:
        email = (request.args.get('email') or '').strip().lower() or None
        event_type = (request.args.get('event_type') or '').strip() or None
        try:
            days = int(request.args.get('days', '30'))
        except ValueError:
            days = 30
        try:
            limit = int(request.args.get('limit', '100'))
        except ValueError:
            limit = 100
        rows = core.get_user_activity_events(email=email, event_type=event_type,
                                        days=days, limit=limit, db_path=core._db_path())
        return jsonify({"events": rows, "count": len(rows)})
    except Exception as e:
        logger.error(f"activity events failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route('/api/usage/budget', methods=['POST'])
@core.require_api_key_or_super_admin
def api_usage_set_budget():
    """Persist the Claude budget (total prepaid credit) used for the
    remaining-balance + depletion estimate.

    Body: {"total_usd": <number|null>, "as_of": "YYYY-MM-DD"|null}
      - total_usd null / 0 / ""  → clears the budget (panel reverts to "set up".
      - as_of (optional) → count spend only from this date forward; set it after
        a top-up so old usage doesn't eat into the new credit.

    Anthropic exposes no balance API, so this figure is user-supplied and stored
    in config.json. Returns the freshly-computed budget block.
    """
    if not os.path.exists(core.CONFIG_PATH):
        return jsonify({"error": "config.json is not writable in this deployment"}), 400

    data = request.get_json(silent=True) or {}
    raw_total = data.get('total_usd')
    as_of = (str(data.get('as_of') or '')).strip() or None

    if raw_total in (None, '', 0, '0'):
        total = None  # clear
    else:
        try:
            total = round(float(raw_total), 2)
        except (TypeError, ValueError):
            return jsonify({"error": "total_usd must be a number"}), 400
        if total < 0:
            return jsonify({"error": "total_usd must be >= 0"}), 400

    if as_of:
        try:
            datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "as_of must be YYYY-MM-DD"}), 400

    try:
        with open(core.CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        if total is None:
            cfg.pop("claude_budget_usd", None)
            cfg.pop("claude_budget_as_of", None)
        else:
            cfg["claude_budget_usd"] = total
            if as_of:
                cfg["claude_budget_as_of"] = as_of
            else:
                cfg.pop("claude_budget_as_of", None)
        with open(core.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("claude budget save failed: %s", e)
        return jsonify({"error": "could not save budget"}), 500

    summary = core.get_claude_usage_summary(days=30, db_path=core._db_path())
    return jsonify(_claude_budget_block(summary, core._db_path()))


@bp.route('/api/settings/notifications', methods=['GET'])
@core.require_api_key_or_super_admin
def api_get_notification_settings():
    """Global notification settings — currently just the message language."""
    cfg = core.load_config()
    return jsonify({"notify_lang": cfg.get("notify_lang", "he")})


@bp.route('/api/settings/notifications', methods=['POST'])
@core.require_api_key_or_super_admin
def api_set_notification_settings():
    """Set the notification message language (he|en).

    Applies to every push channel — Telegram / WhatsApp / Web Push / Slack —
    and the morning digest. The scrape/digest jobs re-read config.json each run,
    so the change takes effect on the next notification with no restart. Scraped
    plan names and detail texts stay in their original language (real product
    strings); only the framing is localized.
    """
    if not os.path.exists(core.CONFIG_PATH):
        return jsonify({"error": "config.json is not writable in this deployment"}), 400
    data = request.get_json(silent=True) or {}
    lang = str(data.get("notify_lang") or "").strip().lower()
    if lang not in ("he", "en"):
        return jsonify({"error": "notify_lang must be 'he' or 'en'"}), 400
    try:
        with open(core.CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["notify_lang"] = lang
        with open(core.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("notify_lang save failed: %s", e)
        return jsonify({"error": "could not save settings"}), 500
    return jsonify({"notify_lang": lang})


@bp.route('/api/usage/official-cost')
@core.require_api_key_or_super_admin
def api_usage_official_cost():
    """Authoritative org-wide spend (USD) from Anthropic's Admin Cost API for
    the last N days (days=0 → ~13-month lookback as a 'lifetime' proxy).

    Requires config.json:anthropic_admin_key. This is SPEND, not balance —
    Anthropic exposes no remaining-credit endpoint. Returns
    {configured, total_usd, currency, since, status, error}.
    """
    try:
        days = int(request.args.get('days', '30'))
    except ValueError:
        days = 30
    lookback = days if (days and days > 0) else 396  # 0 = ~13 months back
    starting_at = (datetime.now(timezone.utc) - timedelta(days=lookback)).strftime('%Y-%m-%dT00:00:00Z')
    return jsonify(_fetch_anthropic_cost_usd(starting_at))
