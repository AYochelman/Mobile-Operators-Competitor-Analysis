import sys as _sys
if __name__ == "__main__":
    # `python app.py` makes this module __main__; the api/ sub-modules do
    # `import app as core`, which would otherwise execute this file a second time.
    _sys.modules.setdefault("app", _sys.modules[__name__])
import json
import os
import logging
import secrets
import hmac
import hashlib
import base64
import time as _time
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
from flask_compress import Compress
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from db import init_db, get_plans, get_changes, get_abroad_plans, get_abroad_changes, get_global_plans, get_global_changes, \
               get_content_plans, get_content_changes, \
               save_price_alert, get_price_alerts, delete_price_alert, update_alert_triggered, \
               save_executive_summary, get_executive_summary, compute_executive_metrics, \
               save_social_sentiment, get_social_sentiment, \
               get_archive_plans, get_archive_banners, get_archive_date_range, \
               get_history_changes, get_history_price_series, get_all_price_series, \
               upsert_news_articles, get_news_articles, \
               log_affiliate_click, get_affiliate_stats, get_affiliate_attribution, is_bot_ua, \
               upsert_hotel, get_hotel, list_hotels, delete_hotel, \
               log_guest_event, get_guest_analytics, get_esim_deals_for_destination, \
               log_esim_event, get_esim_analytics, \
               get_esim_destinations, \
               save_hotel_lead, get_hotel_leads, \
               log_audit, get_audit_log, count_refreshes, \
               log_user_activity, get_user_activity_overview, get_user_activity_summary, \
               get_user_activity_events, prune_user_activity, \
               create_workspace_invite, get_workspace_invite, use_workspace_invite, \
               get_reseller_plans, save_reseller_plans, filter_undominated_reseller_plans, \
               get_usa_tourist_plans, save_usa_tourist_plans, \
               log_claude_usage, get_claude_usage_recent, get_claude_usage_summary, get_claude_spend, \
               get_active_coupons, get_all_coupons, upsert_coupon, update_coupon, delete_coupon, \
               get_provider_deals, \
               get_plan_ref
import archive as arc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# In-memory TTL caches (avoids repeated Supabase/SQLite roundtrips)
_USER_CONTEXT_CACHE: dict = {}   # email → (timestamp, context_dict)
_USER_CONTEXT_TTL = 60           # seconds — workspace config rarely changes
_PLAN_CACHE: dict = {}           # 'plans'|'abroad_plans'|'global_plans' → (timestamp, rows)
_PLAN_CACHE_TTL = 300            # 5 minutes — invalidated after every scrape

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Anthropic list pricing in USD per 1M tokens. Used to estimate the local cost
# of each /api/chat etc. call — Anthropic does not expose a balance endpoint.
# Update when Anthropic publishes new rates or you swap models. Override via
# config.json -> "claude_pricing": { "<model-id>": { "input": ..., "output": ..., "cache_read": ..., "cache_write": ... } }.
CLAUDE_PRICING_DEFAULT = {
    "claude-sonnet-4-6":          {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5-20251001":  {"input": 1.00, "output":  5.00, "cache_read": 0.10, "cache_write": 1.25},
    "claude-opus-4-7":            {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
}


def _claude_pricing_for(model):
    """Return per-MTok pricing for a model, honoring config.json overrides."""
    try:
        overrides = (load_config().get("claude_pricing") or {})
    except Exception:
        overrides = {}
    return overrides.get(model) or CLAUDE_PRICING_DEFAULT.get(model) or \
           CLAUDE_PRICING_DEFAULT["claude-sonnet-4-6"]


def _claude_cost_usd(model, usage):
    """Compute the USD cost of a single API call from its `usage` dict."""
    if not usage:
        return 0.0
    p = _claude_pricing_for(model)
    inp   = int(usage.get("input_tokens") or 0)
    out   = int(usage.get("output_tokens") or 0)
    cread = int(usage.get("cache_read_input_tokens") or 0)
    cwrite = int(usage.get("cache_creation_input_tokens") or 0)
    return (
        inp    * p["input"]      / 1_000_000 +
        out    * p["output"]     / 1_000_000 +
        cread  * p["cache_read"] / 1_000_000 +
        cwrite * p["cache_write"]/ 1_000_000
    )


def _record_claude_call(endpoint, model, response_json, user_email=None, workspace_id=None):
    """Log token usage + computed USD cost for a single Anthropic call.

    Pass the parsed response JSON (already `resp.json()`). Safe to call inside
    a try/except — never raises out, just logs and moves on.
    """
    try:
        usage = (response_json or {}).get("usage") or {}
        cost = _claude_cost_usd(model, usage)
        log_claude_usage(
            endpoint=endpoint,
            model=model,
            usage=usage,
            cost_usd=cost,
            user_email=user_email,
            workspace_id=workspace_id,
            db_path=_db_path(),
        )
    except Exception as e:
        logger.warning("claude usage log failed for %s: %s", endpoint, e)

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# gzip/brotli compression on JSON + text responses.
# Auto-applied to >500-byte responses with Accept-Encoding: gzip/br.
# Skips already-compressed mimetypes (image/*, video/*) automatically.
Compress(app)


def _client_ip():
    """Real client IP behind the Cloudflare Tunnel. cloudflared terminates the
    public TLS connection and forwards the origin IP in CF-Connecting-IP (and
    X-Forwarded-For); Flask's request.remote_addr is just the tunnel's local peer
    (127.0.0.1), so WITHOUT this every public visitor collapses to one address —
    breaking per-client rate limiting and any bot/human IP analysis. Falls back to
    remote_addr for direct localhost/LAN access. Trusting the header is safe because
    the only public ingress is the tunnel from localhost (Flask binds 127.0.0.1)."""
    hdr = request.headers
    return (hdr.get("CF-Connecting-IP")
            or hdr.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr
            or "")


# Rate limiting — keyed on the real client IP (see _client_ip) so limits are
# per-visitor, not one global bucket for all tunnel traffic.
limiter = Limiter(_client_ip, app=app, default_limits=["200 per minute"], storage_uri="memory://")


def _public_cache(resp, max_age):
    """Stamp a public Cache-Control on a response; PWA + browser cache it for max_age seconds."""
    resp.headers["Cache-Control"] = f"public, max-age={max_age}"
    return resp

# CORS: restrict to known origins
ALLOWED_ORIGINS = [
    "http://localhost:5000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
    "http://127.0.0.1:5000", "http://127.0.0.1:5173",
    "https://www.mocaintel.com", "https://mocaintel.com",
    "https://esim.mocaintel.com",  # public B2C eSIM compare microsite (its own origin)
    "https://mobile.mocaintel.com",  # public B2C domestic-plans microsite (/mobile-deals)
    "https://lucent-kulfi-f037ad.netlify.app",  # legacy Netlify subdomain — kept as fallback
    # extra origins added dynamically via ALLOWED_ORIGINS env var
]
# Add ngrok/netlify URLs from environment if set
_extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _extra_origins:
    ALLOWED_ORIGINS.extend(_extra_origins.split(","))
# /banners/* included: the frontend blob-fetches banner screenshots (useApiImage,
# to carry the ngrok-skip-browser-warning header past the interstitial) and a
# cross-origin fetch() - unlike a plain <img> - is blocked without CORS headers.
CORS(app, resources={
    r"/api/*": {"origins": ALLOWED_ORIGINS, "supports_credentials": True},
    r"/banners/*": {"origins": ALLOWED_ORIGINS},
    # Time Machine banner snapshots are blob-fetched too (useApiImage) - same
    # cross-origin story as /banners/*; without this the archive images are
    # CORS-blocked on the live site (empty tiles in TimeMachineModal/ArchivePage).
    r"/archive-banners/*": {"origins": ALLOWED_ORIGINS},
})

@app.after_request
def add_security_headers(response):
    """Attach security headers to every response."""
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        # connect-src tightened from blanket https:/wss: to same-origin only —
        # the Flask-served legacy dashboard fetches exclusively from /api/... on
        # its own origin, so this blocks data exfiltration to arbitrary hosts if
        # an XSS ever slipped past escHtml. (img-src keeps https: for the
        # wikimedia/icons8 carrier logos; the React SPA on Netlify has its own CSP.)
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "frame-ancestors 'none'"
    )
    return response

# ── API Key auth for sensitive endpoints ───────────────────────────────
def _get_api_key():
    """Get or generate API key from config."""
    try:
        cfg = load_config()
        key = cfg.get("api_key")
        if key:
            return key
    except Exception as e:
        logger.warning(f"Could not read API key from config: {e}")
    # Generate and save a new key
    key = secrets.token_urlsafe(32)
    try:
        cfg = load_config()
        cfg["api_key"] = key
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        logger.info("New API key generated and saved")
    except Exception as e:
        logger.warning(f"Could not save API key: {e}")
    return key

def require_api_key(f):
    """Decorator to require X-API-Key header only (no URL query param)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        provided = request.headers.get("X-API-Key")
        expected = _get_api_key()
        if not provided or not hmac.compare_digest(provided, expected):
            return jsonify({"error": "Unauthorized — API key required"}), 401
        return f(*args, **kwargs)
    return decorated


def require_auth(f):
    """Accept a valid Supabase JWT (Authorization header or auth_token cookie) OR API key.
    Sets g.jwt_payload to the decoded payload (or None for API-key-only auth).

    JWT is checked FIRST so that requests carrying both headers (e.g. dev-mode
    frontend that sends both Authorization Bearer + X-API-Key) are identified
    by the real user — otherwise role-aware helpers that read g.jwt_payload
    would treat the request as anonymous server-to-server and deny per-user
    actions like managing workspace users.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. JWT from Authorization header
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        # 2. JWT from httpOnly cookie (fallback)
        if not token:
            token = request.cookies.get("auth_token")
        if token:
            payload = _verify_supabase_jwt(token)
            if payload:
                g.jwt_payload = payload
                return f(*args, **kwargs)
        # 3. API key (server-to-server) — only if no valid JWT was provided
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header and hmac.compare_digest(api_key_header, _get_api_key()):
            g.jwt_payload = None
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


def _get_server_admin_key():
    """Get or generate the SEPARATE server-admin key. This key is what
    legitimate server-to-server jobs use to bypass role checks. It is
    intentionally distinct from the regular api_key (which is scoped to
    scrape-trigger / data-read endpoints) so that a leak of one does not
    automatically grant admin powers."""
    try:
        cfg = load_config()
        key = cfg.get("server_admin_key")
        if key:
            return key
    except Exception as e:
        logger.warning(f"Could not read server_admin_key from config: {e}")
    key = secrets.token_urlsafe(32)
    try:
        cfg = load_config()
        cfg["server_admin_key"] = key
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        logger.info("New server_admin_key generated and saved")
    except Exception as e:
        logger.warning(f"Could not save server_admin_key: {e}")
    return key


def _require_role(allowed_roles, error_msg):
    """Factory for role-based decorators. JWT auth must resolve to a role
    in allowed_roles. The regular api_key does NOT bypass this check —
    only a request bearing the dedicated X-Server-Admin-Key header can,
    and that key is never sent from the frontend."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Dedicated server-admin key (separate from api_key) — never
            # exposed to the browser. Used only by trusted server-to-server
            # callers (e.g. cron scripts) that legitimately need admin access.
            if _is_server_admin_request():
                g.jwt_payload = None
                return f(*args, **kwargs)
            # JWT — extract email, verify role via Supabase
            token = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            if not token:
                token = request.cookies.get("auth_token")
            if token:
                payload = _verify_supabase_jwt(token)
                if payload:
                    email = (payload.get('email') or '').strip().lower()
                    try:
                        conn = _supabase_conn()
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT COALESCE(r.role,'viewer') FROM auth.users u "
                            "LEFT JOIN public.user_roles r ON u.id=r.user_id "
                            "WHERE LOWER(u.email)=%s", (email,)
                        )
                        row = cur.fetchone()
                        conn.close()
                        if row and row[0] in allowed_roles:
                            g.jwt_payload = payload
                            return f(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"role check failed: {e}")
            return jsonify({"error": error_msg}), 401
        return decorated
    return decorator


# Admin includes super_admin (super_admin has all admin privileges)
require_admin = _require_role({'admin', 'super_admin'}, 'Unauthorized — admin required')
# Super-admin is cross-workspace (MOCA operator only)
require_super_admin = _require_role({'super_admin'}, 'Unauthorized — super_admin required')


def require_api_key_or_super_admin(f):
    """Accept the regular API key (server-to-server / dev frontend), the
    dedicated server-admin key, OR a verified super_admin JWT — nothing else.

    Used for the Claude usage / billing endpoints: the MOCA operator
    (super_admin) can view spend from the PRODUCTION web app via their JWT,
    while workspace admins and viewers are refused — they never hold
    super_admin, and the api_key is not shipped in the production bundle. Sets
    g.jwt_payload when a JWT authenticated the request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Regular API key (dev frontend via VITE_DEV_API_KEY, server jobs)
        provided = request.headers.get("X-API-Key")
        if provided and hmac.compare_digest(provided, _get_api_key()):
            g.jwt_payload = None
            return f(*args, **kwargs)
        # 2. Dedicated server-admin key
        if _is_server_admin_request():
            g.jwt_payload = None
            return f(*args, **kwargs)
        # 3. super_admin JWT (Authorization header or auth_token cookie)
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.cookies.get("auth_token")
        if token:
            payload = _verify_supabase_jwt(token)
            if payload:
                email = (payload.get('email') or '').strip().lower()
                if _get_user_context(email).get('role') == 'super_admin':
                    g.jwt_payload = payload
                    return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized — super_admin required"}), 401
    return decorated


# Slack / Teams incoming-webhook allowlist — used everywhere a webhook URL is
# accepted from a request body. Prevents SSRF to internal services / cloud
# metadata endpoints.
import re as _re_webhook
_SLACK_TEAMS_WEBHOOK_RE = _re_webhook.compile(
    r'^https://(hooks\.slack\.com/|.+\.webhook\.office\.com/)'
)


def _is_valid_slack_webhook(url: str) -> bool:
    """True iff *url* is an HTTPS Slack or MS Teams incoming-webhook URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(_SLACK_TEAMS_WEBHOOK_RE.match(url.strip()))


def _current_user_email():
    """Return the authenticated user's email (lowercased) from the JWT payload
    set by @require_auth. If the request was authenticated via API key
    (trusted server-to-server), fall back to decoding any JWT that was also
    attached — this lets dev-mode callers that send both headers still be
    identified as a real user for per-user resources (saved views, alerts)."""
    payload = getattr(g, 'jwt_payload', None)
    if payload is None:
        # API-key auth path — try to pull identity from a JWT if one is present
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.cookies.get("auth_token")
        if token:
            p = _verify_supabase_jwt(token)
            if p:
                email = (p.get('email') or '').strip().lower()
                return email or None
        return None
    email = (payload.get('email') or '').strip().lower()
    return email or None


def _is_server_admin_request():
    """True iff the current request bears the dedicated X-Server-Admin-Key
    header with the correct value. The regular api_key does NOT count —
    that key is for scrape triggers and JWT-anonymous reads, not for
    administrative bypass."""
    sa_key_header = request.headers.get("X-Server-Admin-Key")
    if not sa_key_header:
        return False
    try:
        return hmac.compare_digest(sa_key_header, _get_server_admin_key())
    except Exception:
        return False


def _can_manage_workspace_users(workspace_id):
    """True if the current request may manage users for the given workspace.
    Server-admin key (dedicated, server-to-server only): always allowed.
    super_admin: always allowed.
    admin: only when their own workspace_id matches the target workspace.

    Note: a request authenticated only by the regular api_key (i.e. the key
    used by dev mode and scrape triggers) is NOT trusted here. Admin bypass
    requires the dedicated X-Server-Admin-Key header.
    """
    if _is_server_admin_request():
        return True
    payload = getattr(g, 'jwt_payload', None)
    if payload is None:
        return False  # api_key alone is not enough for user-management bypass
    email = (payload.get('email') or '').strip().lower()
    ctx = _get_user_context(email)
    role = ctx.get('role', 'viewer')
    if role == 'super_admin':
        return True
    if role == 'admin' and str(ctx.get('workspace_id') or '') == str(workspace_id):
        return True
    return False


def _user_is_super_admin(cur, user_id):
    """True iff the given user currently holds the global super_admin role.
    Uses the caller's existing open cursor (same connection/txn).

    Guards against the user_roles UNIQUE(user_id) footgun: any write that
    upserts a workspace-scoped role for a user would OVERWRITE their global
    super_admin — and since the UI can only grant admin/viewer, that demotion
    cannot be undone without a direct DB edit. Callers use this to refuse such
    writes for a super_admin target."""
    cur.execute("SELECT role FROM public.user_roles WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    return bool(row and row[0] == 'super_admin')


def _caller_email():
    """Best-effort: return the authenticated user's email, or None."""
    payload = getattr(g, 'jwt_payload', None)
    if payload:
        e = (payload.get('email') or '').strip().lower()
        if e:
            return e
    return None


def _hidden_carrier_for_request():
    """Resolve the self-carrier that should be omitted from responses for the
    current request, based on the authenticated user's workspace.

    Returns the carrier id string (e.g. 'partner') to hide, or None when no
    filtering applies. Endpoints can use this to scope data away from a
    workspace's own MVNO (so a Partner tester never sees Partner plans).

    Filtering is SKIPPED when:
      - No JWT / unauthenticated public caller
      - Token invalid / not verifiable
      - User's role is super_admin (cross-workspace view)
      - Workspace has hide_self_carrier=False
      - Workspace has no mvno_carrier configured

    Result is cached on `flask.g` so multiple calls within a single request
    do not re-hit Supabase.
    """
    cached = getattr(g, '_hidden_carrier', '__UNSET__')
    if cached != '__UNSET__':
        return cached

    result = None
    try:
        # Prefer JWT payload already set by @require_auth, fall back to header/cookie
        payload = getattr(g, 'jwt_payload', None)
        if payload is None:
            token = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            if not token:
                token = request.cookies.get("auth_token")
            if token:
                payload = _verify_supabase_jwt(token)

        if payload:
            email = (payload.get('email') or '').strip().lower()
            if email:
                ctx = _get_user_context(email)
                if ctx.get('role') != 'super_admin':
                    ws = ctx.get('workspace') or {}
                    if ws.get('hide_self_carrier') and ws.get('mvno_carrier'):
                        result = ws['mvno_carrier']
    except Exception as e:
        logger.warning(f"_hidden_carrier_for_request: {e}")

    g._hidden_carrier = result
    return result


def _filter_hidden_carrier(items, key='carrier'):
    """Strip items whose `carrier` field matches the request's hidden carrier.
    No-op when no filter applies. Accepts a list of dicts and returns a new list."""
    hide = _hidden_carrier_for_request()
    if not hide:
        return items
    return [it for it in items if (it or {}).get(key) != hide]


def _get_user_context(email):
    """Resolve a user's role + workspace config from Supabase in one query.

    Returns a dict with keys:
      role          — 'super_admin' | 'admin' | 'viewer'  (default 'viewer')
      workspace_id  — UUID string or None (None only for super_admin)
      workspace     — dict {slug, name, mvno_carrier, brand_config, feature_flags,
                            hide_self_carrier, active} or None

    On DB failure, returns a safe default: viewer role, no workspace. Callers
    MUST handle workspace=None gracefully (e.g. return 503 or fall back to
    default behavior).
    """
    if not email:
        return {"role": "viewer", "workspace_id": None, "workspace": None}
    _now = _time.time()
    _cached = _USER_CONTEXT_CACHE.get(email)
    if _cached and _now - _cached[0] < _USER_CONTEXT_TTL:
        return _cached[1]
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(r.role, 'viewer'),
                   r.workspace_id,
                   w.slug, w.name, w.mvno_carrier,
                   w.brand_config, w.feature_flags,
                   w.hide_self_carrier, w.active, w.trial_ends_at,
                   COALESCE(w.visible_carriers, '[]'::jsonb),
                   COALESCE(r.digest_opt_out, FALSE)
            FROM auth.users u
            LEFT JOIN public.user_roles r ON r.user_id = u.id
            LEFT JOIN public.workspaces w ON w.id = r.workspace_id
            WHERE LOWER(u.email) = %s
        """, (email,))
        row = cur.fetchone()
        conn.close()
        if not row:
            _result = {"role": "viewer", "workspace_id": None, "workspace": None, "digest_opt_out": False}
            _USER_CONTEXT_CACHE[email] = (_time.time(), _result)
            return _result
        role, ws_id = row[0], row[1]
        digest_opt_out = bool(row[11])
        workspace = None
        if row[2]:  # slug present = workspace joined successfully
            import time as _time2
            trial_ends_at = row[9]
            trial_expired = False
            if trial_ends_at:
                import datetime as _dt2
                now_utc = _dt2.datetime.now(_dt2.timezone.utc)
                if hasattr(trial_ends_at, 'tzinfo'):
                    trial_expired = now_utc > trial_ends_at
                else:
                    trial_expired = now_utc > trial_ends_at.replace(tzinfo=_dt2.timezone.utc)
            active = bool(row[8]) and not trial_expired
            vc_raw = row[10]
            visible_carriers = json.loads(vc_raw) if isinstance(vc_raw, str) else (list(vc_raw) if vc_raw else [])
            workspace = {
                "id":                str(ws_id) if ws_id else None,
                "slug":              row[2],
                "name":              row[3],
                "mvno_carrier":      row[4],
                "brand_config":      row[5] or {},
                "feature_flags":     row[6] or {},
                "hide_self_carrier": bool(row[7]),
                "active":            active,
                "trial_ends_at":     trial_ends_at.isoformat() if trial_ends_at else None,
                "trial_expired":     trial_expired,
                "visible_carriers":  visible_carriers,
            }
        _result = {"role": role, "workspace_id": str(ws_id) if ws_id else None,
                   "workspace": workspace, "digest_opt_out": digest_opt_out}
        _USER_CONTEXT_CACHE[email] = (_time.time(), _result)
        return _result
    except Exception as e:
        # Supabase unreachable, bad credentials, IPv6-only direct host, etc. This
        # is NOT "the user is a viewer" - it is "we could not find out". Tag it
        # so /api/my-context callers can tell the two apart; without the tag a
        # dead DB link silently demoted every admin (seen live 2026-09-20: the
        # user_roles row said super_admin, the app showed viewer, and nothing
        # in the UI said why). Deliberately NOT cached, so the first request
        # after the link recovers gets the real role.
        logger.error(f"_get_user_context({email!r}) failed: {e}")
        return {"role": "viewer", "workspace_id": None, "workspace": None,
                "digest_opt_out": False, "reason": "db_error"}


def require_api_key_or_query(f):
    """Accepts API key via header OR ?api_key= query param.
    Use ONLY on /api/scrape-*-now for manual browser convenience."""
    @wraps(f)
    def decorated(*args, **kwargs):
        provided = request.headers.get("X-API-Key") or request.args.get("api_key")
        expected = _get_api_key()
        if not provided or not hmac.compare_digest(provided, expected):
            return jsonify({"error": "Unauthorized — API key required"}), 401
        return f(*args, **kwargs)
    return decorated


MONTHLY_REFRESH_LIMIT = 5


def require_scrape_auth(f):
    """Accepts API key (unlimited) OR admin/super_admin JWT (quota-limited).
    Sets g.jwt_payload when JWT is used; g.jwt_payload=None for API key callers."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # API key path — trusted caller, no quota
        provided = request.headers.get("X-API-Key") or request.args.get("api_key")
        if provided and provided == _get_api_key():
            g.jwt_payload = None
            return f(*args, **kwargs)
        # JWT path — workspace admin or super_admin
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            payload = _verify_supabase_jwt(auth_header[7:])
            if payload:
                email = (payload.get("email") or "").strip().lower()
                ctx = _get_user_context(email)
                role = ctx.get("role", "viewer")
                if role in ("admin", "super_admin"):
                    g.jwt_payload = payload
                    g._refresh_ctx = ctx
                    return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


def _check_refresh_quota():
    """Call inside a @require_scrape_auth endpoint.
    Returns (ok, used, limit) — ok=True means quota not exceeded.
    Super_admin and API-key callers always return (True, 0, limit)."""
    ctx = getattr(g, '_refresh_ctx', None)
    if ctx is None:
        return True, 0, MONTHLY_REFRESH_LIMIT  # API key caller
    role = ctx.get('role', 'viewer')
    if role == 'super_admin':
        return True, 0, MONTHLY_REFRESH_LIMIT
    ws_id = ctx.get('workspace_id')
    if not ws_id:
        return True, 0, MONTHLY_REFRESH_LIMIT
    from datetime import datetime as _dt, timezone as _tz
    month_prefix = _dt.now(_tz.utc).strftime('%Y-%m')
    used = count_refreshes(ws_id, month_prefix, db_path=_db_path())
    return used < MONTHLY_REFRESH_LIMIT, used, MONTHLY_REFRESH_LIMIT


def _workspace_refresh_quota_for_email(email):
    """Returns (used, limit, remaining, unlimited) for the given email."""
    ctx = _get_user_context(email)
    role = ctx.get('role', 'viewer')
    if role == 'super_admin':
        return 0, MONTHLY_REFRESH_LIMIT, MONTHLY_REFRESH_LIMIT, True
    ws_id = ctx.get('workspace_id')
    if not ws_id:
        return 0, MONTHLY_REFRESH_LIMIT, MONTHLY_REFRESH_LIMIT, False
    from datetime import datetime as _dt, timezone as _tz
    month_prefix = _dt.now(_tz.utc).strftime('%Y-%m')
    used = count_refreshes(ws_id, month_prefix, db_path=_db_path())
    remaining = max(0, MONTHLY_REFRESH_LIMIT - used)
    return used, MONTHLY_REFRESH_LIMIT, remaining, False


def _log_refresh(action_detail=''):
    """Log a manual refresh to audit_log for quota tracking. No-op for API-key callers."""
    ctx = getattr(g, '_refresh_ctx', None)
    if ctx is None:
        return
    actor = _current_user_email() or ''
    ws_id = ctx.get('workspace_id')
    log_audit('refresh_triggered', actor_email=actor, workspace_id=ws_id,
              details=action_detail, db_path=_db_path())


@app.route('/api/refresh-quota', methods=['GET'])
@require_auth
@limiter.limit('60 per minute')
def api_refresh_quota():
    """Return current month's manual-refresh usage for the caller's workspace."""
    email = _current_user_email() or ''
    if not email:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            _p = _verify_supabase_jwt(auth_header[7:])
            if _p:
                email = (_p.get('email') or '').strip().lower()
    if not email:
        return jsonify({'used': 0, 'limit': MONTHLY_REFRESH_LIMIT,
                        'remaining': MONTHLY_REFRESH_LIMIT, 'unlimited': True})
    used, limit, remaining, unlimited = _workspace_refresh_quota_for_email(email)
    return jsonify({'used': used, 'limit': limit, 'remaining': remaining, 'unlimited': unlimited})


_config_cache = {"mtime": None, "data": None}

def load_config():
    # Hot path: called on every @require_api_key request, the /go affiliate redirect
    # (up to 3× per hit), guest/esim beacons, etc. Re-reading + JSON-parsing the
    # credentials file each time is wasted disk I/O. Cache by mtime so the settings
    # endpoints that write config.json directly are still picked up immediately.
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if _config_cache["mtime"] != mtime or _config_cache["data"] is None:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                _config_cache["data"] = json.load(f)
            _config_cache["mtime"] = mtime
        # Shallow copy so a caller that mutates a top-level key (e.g. _get_api_key
        # setting cfg["api_key"]) can't poison the shared cache between file writes.
        return dict(_config_cache["data"])
    except FileNotFoundError:
        # Fallback to environment variables (for cloud deployment)
        return {
            "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
            "schedule_times": json.loads(os.environ.get("SCHEDULE_TIMES", '["10:00","16:00"]')),
            "notify_on_changes_only": True,
            "sendgrid_api_key": os.environ.get("SENDGRID_API_KEY", ""),
            "email_sender": os.environ.get("EMAIL_SENDER", ""),
            "email_recipient": os.environ.get("EMAIL_RECIPIENT", ""),
            "email_report_time": "09:00",
            "api_key": os.environ.get("API_KEY", ""),
            "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "vapid_private_key": os.environ.get("VAPID_PRIVATE_KEY", ""),
            "vapid_public_key": os.environ.get("VAPID_PUBLIC_KEY", ""),
            "vapid_email": os.environ.get("VAPID_EMAIL", ""),
            "supabase_jwt_secret": os.environ.get("SUPABASE_JWT_SECRET", ""),
            "supabase_anon_key": os.environ.get("SUPABASE_ANON_KEY", ""),
            "supabase_url": os.environ.get("SUPABASE_URL", ""),
        }


_jwks_cache = {"keys": [], "fetched_at": 0}

def _get_jwks():
    """Fetch and cache Supabase JWKS (TTL: 1 hour)."""
    import urllib.request as _ur
    now = _time.time()
    if now - _jwks_cache["fetched_at"] < 3600 and _jwks_cache["keys"]:
        return _jwks_cache["keys"]
    try:
        cfg = load_config()
        supabase_url = cfg.get('supabase_url') or os.environ.get('SUPABASE_URL', 'https://gmfefvjdmgzluwffzrzj.supabase.co')
        req = _ur.Request(f"{supabase_url}/auth/v1/.well-known/jwks.json")
        resp = _ur.urlopen(req, timeout=5)
        jwks = json.loads(resp.read())
        _jwks_cache["keys"] = jwks.get("keys", [])
        _jwks_cache["fetched_at"] = now
        return _jwks_cache["keys"]
    except Exception as e:
        logger.warning(f"Failed to fetch JWKS: {e}")
        return _jwks_cache["keys"]


def _verify_supabase_jwt(token: str):
    """Verify a Supabase JWT (HS256 or ES256) and return the payload dict, or None on failure.

    - ES256 (current): verifies with EC public key from Supabase JWKS endpoint (cached 1h)
    - HS256 (legacy):  verifies with supabase_jwt_secret from config.json
    - Unknown alg:     rejects the token
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        header  = json.loads(base64.urlsafe_b64decode(header_b64  + '=='))
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + '=='))
        alg = header.get('alg', 'HS256')
        kid = header.get('kid')
        signing_input = f"{header_b64}.{payload_b64}".encode('ascii')
        sig_bytes     = base64.urlsafe_b64decode(sig_b64 + '==')

        if alg == 'ES256':
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

            keys = _get_jwks()
            jwk = next((k for k in keys if kid is None or k.get('kid') == kid), None)
            if not jwk:
                logger.warning(f"No JWKS key found for kid={kid}")
                return None

            x = int.from_bytes(base64.urlsafe_b64decode(jwk['x'] + '=='), 'big')
            y = int.from_bytes(base64.urlsafe_b64decode(jwk['y'] + '=='), 'big')
            pub_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()

            # JWT ES256 signature is raw r||s (32 bytes each) — convert to DER for cryptography
            r = int.from_bytes(sig_bytes[:32], 'big')
            s = int.from_bytes(sig_bytes[32:], 'big')
            try:
                pub_key.verify(encode_dss_signature(r, s), signing_input, ec.ECDSA(hashes.SHA256()))
            except Exception:
                logger.warning("ES256 JWT signature verification failed — possible token forgery")
                return None

        elif alg == 'HS256':
            # HS256 is the legacy signing algorithm. Once Supabase has been
            # migrated to JWT Signing Keys (ES256, the default since late 2025),
            # the project's HS256 secret is revoked and no legitimate new token
            # will ever come in with alg=HS256. Reject unconditionally if the
            # secret is missing — silently accepting unsigned tokens here would
            # be a complete authentication bypass.
            cfg = load_config()
            secret = cfg.get('supabase_jwt_secret') or os.environ.get('SUPABASE_JWT_SECRET', '')
            if not secret:
                logger.warning("HS256 JWT rejected: supabase_jwt_secret not configured (Supabase has migrated to ES256 — this token is either expired or forged)")
                return None
            computed = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
            if not hmac.compare_digest(computed, sig_bytes):
                logger.warning("HS256 JWT signature verification failed — possible token forgery")
                return None

        else:
            logger.warning(f"Unsupported JWT algorithm: {alg}")
            return None

        # Check expiry with a bounded grace period for clock skew. The backend
        # runs on a Windows box whose clock can drift (seen: +2h) and whose
        # w32time NTP sync is not always running, so a fresh JWT can look expired
        # without some leeway. But a large grace also extends the replay window
        # for a stolen/logged-out token, so keep it as small as the drift allows
        # and make it tunable: enable Windows time sync, then drop this to ~300s.
        # config.json:jwt_exp_grace_seconds overrides the default (2h, down from 4h).
        try:
            _grace = int(load_config().get('jwt_exp_grace_seconds', 7200))
        except (TypeError, ValueError):
            _grace = 7200
        exp = payload.get('exp')
        if exp is not None and _time.time() > exp + max(0, _grace):
            logger.warning("JWT has expired (beyond grace period)")
            return None

        return payload

    except Exception as e:
        logger.error(f"_verify_supabase_jwt error: {e}")
        return None


def _supabase_conn():
    """Get a psycopg2 connection to Supabase DB using credentials from config.

    config.json keys (env-var fallback in parentheses; all but host/password
    optional):
      supabase_db_host      (SUPABASE_DB_HOST)      required
      supabase_db_password  (SUPABASE_DB_PASSWORD)  required
      supabase_db_user      (SUPABASE_DB_USER)      default 'postgres'
      supabase_db_port      (SUPABASE_DB_PORT)      default 5432
      supabase_db_name      (SUPABASE_DB_NAME)      default 'postgres'

    IPv6 GOTCHA (bit us 2026-09-20): Supabase's DIRECT host
    `db.<ref>.supabase.co` publishes an AAAA record only - no IPv4 on the free
    tier. From a box without an IPv6 route (the Windows host, after its router
    lost IPv6) libpq's getaddrinfo fails with "could not translate host name
    ... Name or service not known", _get_user_context swallows it, and EVERY
    signed-in user silently becomes a viewer. The fix is Supabase's Session
    Pooler (Dashboard -> Connect -> Session pooler), which is dual-stack:
        supabase_db_host = aws-0-<region>.pooler.supabase.com
        supabase_db_user = postgres.<project-ref>     <- tenant suffix REQUIRED
        supabase_db_port = 5432                       (session mode; 6543 is
                                                       transaction mode, which
                                                       breaks prepared stmts)
    That is why `user` and `port` are configurable here instead of hardcoded.
    """
    import psycopg2
    cfg = load_config()
    env = os.environ.get
    def _int(v, default):
        try:
            return int(v) if v not in (None, "") else default
        except (TypeError, ValueError):
            return default
    port    = _int(cfg.get("supabase_db_port") or env("SUPABASE_DB_PORT"), 5432)
    timeout = _int(cfg.get("supabase_db_connect_timeout") or env("SUPABASE_DB_CONNECT_TIMEOUT"), 10)
    return psycopg2.connect(
        host=cfg.get("supabase_db_host", env("SUPABASE_DB_HOST", "")),
        port=port,
        dbname=cfg.get("supabase_db_name") or env("SUPABASE_DB_NAME") or "postgres",
        user=cfg.get("supabase_db_user") or env("SUPABASE_DB_USER") or "postgres",
        password=cfg.get("supabase_db_password", env("SUPABASE_DB_PASSWORD", "")),
        sslmode='require',
        connect_timeout=timeout,
    )


def _db_path():
    """Return test DB path when running under pytest, else default (None = use DB_PATH in db.py)."""
    return app.config.get("TEST_DB_PATH") or None


_GLOBAL_PURGE_KNOBS = ("min_ratio", "min_rows", "grace_hours", "window_days")


def _purge_stale_global(new_global, config, db_path=None):
    """Guarded purge of stale global_plans rows - run right AFTER save_global_plans
    and BEFORE notify_esim_price_drops on every global scrape path (so the alert
    floor is computed on clean data). See db.purge_stale_global_rows for the
    completeness guards. config.json knobs (all optional): `global_purge_enabled`
    (default true; false = dry-run: the per-carrier report is still logged),
    `global_purge_min_ratio` (0.90), `global_purge_min_rows` (2),
    `global_purge_grace_hours` (72), `global_purge_window_days` (30).
    Never raises. Returns {"purged": n, "carriers": {...}}."""
    summary = {"purged": 0, "carriers": {}}
    try:
        from db import purge_stale_global_rows
        knobs = {k: config.get(f"global_purge_{k}") for k in _GLOBAL_PURGE_KNOBS
                 if config.get(f"global_purge_{k}") is not None}
        dry_run = not config.get("global_purge_enabled", True)
        report = purge_stale_global_rows(new_global, db_path=db_path, dry_run=dry_run, **knobs)
        for carrier, r in report.items():
            line = (f"global purge {carrier}: fresh={r['fresh']} ({r['fresh_dests']} dests) "
                    f"baseline={r['baseline_rows']} rows/{r['baseline_dests']} dests in window "
                    f"ratio={r['ratio_rows']:.2f}/{r['ratio_dests']:.2f} db={r['db_rows']} "
                    f"stale={r['stale']} eligible={r['eligible']} purged={r['purged']} [{r['decision']}]")
            if r["purged"] or r["decision"].startswith(("partial", "too-few", "complete, dry-run")):
                logger.info(line)
            else:
                logger.debug(line)
            summary["carriers"][carrier] = {"purged": r["purged"], "stale": r["stale"], "decision": r["decision"]}
        summary["purged"] = sum(r["purged"] for r in report.values())
        n_stale = sum(r["stale"] for r in report.values())
        logger.info(f"global purge summary: carriers={len(report)} purged={summary['purged']} "
                    f"stale_remaining={n_stale - summary['purged']}"
                    + (" (dry-run: global_purge_enabled=false)" if dry_run else ""))
    except Exception as e:
        logger.warning(f"global stale purge failed: {e}", exc_info=True)
    return summary


def _ensure_vapid_keys(config_path):
    """Generate VAPID keys on first run and save to config.json."""
    if not os.path.exists(config_path):
        logger.info("No config.json found — skipping VAPID key generation (cloud mode)")
        return
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg.get("vapid_public_key") and cfg.get("vapid_private_key"):
        return
    try:
        import base64
        from py_vapid import Vapid
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        v = Vapid()
        v.generate_keys()
        # Serialize private key as PEM string
        cfg["vapid_private_key"] = v.private_pem().decode()
        # Serialize public key as uncompressed point → urlsafe base64 (no padding)
        pub_bytes = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        cfg["vapid_public_key"] = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()
        cfg["vapid_email"] = f"mailto:{cfg.get('email_sender', 'alon.yoch@gmail.com')}"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        logger.info("VAPID keys generated and saved to config.json")
    except Exception as e:
        logger.error(f"VAPID key generation failed: {e}")


# Initialize DB on import (needed for gunicorn which skips __main__)
init_db()

# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/sw.js")
def service_worker():
    resp = make_response(send_from_directory("static", "sw.js"))
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/banners/<string:filename>")
def serve_banner(filename):
    """Serve carrier homepage screenshot PNGs. Banners refresh daily at 08:00 — cache for 1 day."""
    if not filename.endswith(".png"):
        abort(404)
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    resp = make_response(send_from_directory(banners_dir, filename))
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


def _cached_plans(key, fetch_fn):
    """Return plan list from TTL cache or fetch fresh from DB."""
    now = _time.time()
    entry = _PLAN_CACHE.get(key)
    if entry and now - entry[0] < _PLAN_CACHE_TTL:
        return entry[1]
    data = fetch_fn()
    _PLAN_CACHE[key] = (_time.time(), data)
    return data


def _invalidate_plan_cache():
    _PLAN_CACHE.clear()


@app.route("/api/plans")
@limiter.limit("60 per minute")
def api_plans():
    carrier = request.args.get("carrier")
    if carrier:
        plans = get_plans(carrier=carrier, db_path=_db_path())
    else:
        plans = _cached_plans('plans', lambda: get_plans(db_path=_db_path()))
    return _public_cache(jsonify(_filter_hidden_carrier(plans)), 600)


@app.route("/api/changes")
@limiter.limit("60 per minute")
def api_changes():
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 500))
    except (ValueError, TypeError):
        limit = 20
    changes = get_changes(limit=limit, db_path=_db_path())
    return _public_cache(jsonify(_filter_hidden_carrier(changes)), 600)


@app.route("/api/abroad-plans")
@limiter.limit("60 per minute")
def api_abroad_plans():
    carrier = request.args.get("carrier")
    if carrier:
        plans = get_abroad_plans(carrier=carrier, db_path=_db_path())
    else:
        plans = _cached_plans('abroad_plans', lambda: get_abroad_plans(db_path=_db_path()))
    return _public_cache(jsonify(_filter_hidden_carrier(plans)), 600)


@app.route("/api/global-plans")
@limiter.limit("60 per minute")
def api_global_plans():
    carrier = request.args.get("carrier")
    if carrier:
        plans = get_global_plans(carrier=carrier, db_path=_db_path())
    else:
        plans = _cached_plans('global_plans', lambda: get_global_plans(db_path=_db_path()))
    return _public_cache(jsonify(_filter_hidden_carrier(plans)), 600)


@app.route("/api/reseller-plans")
@limiter.limit("60 per minute")
def api_reseller_plans():
    """Plans offered by Israeli authorized resellers (משווקים).

    By rule, only plans that are CHEAPER than the carrier's own offering (or have
    no comparable carrier plan) are returned. Pass ?all=1 to bypass the filter
    (useful for debugging / admin).
    """
    reseller = request.args.get("reseller")
    carrier = request.args.get("carrier")
    show_all = request.args.get("all") == "1"
    plans = get_reseller_plans(reseller_id=reseller, carrier=carrier, db_path=_db_path())
    if not show_all:
        plans = filter_undominated_reseller_plans(plans, db_path=_db_path())
    return jsonify(_filter_hidden_carrier(plans))


@app.route("/api/usa-plans")
@limiter.limit("60 per minute")
def api_usa_plans():
    """US operators' prepaid plans for inbound tourists (the נוחתים בארה"ב tab).

    carrier = US operator id (tmobile_prepaid, mint, visible, ...). price is
    ILS-converted at seed time; original_price keeps the native USD amount.
    Data is seeded via seed_usa_tourist.py (manually-researched, not scraped).
    """
    carrier = request.args.get("carrier")
    plans = get_usa_tourist_plans(carrier=carrier, db_path=_db_path())
    return _public_cache(jsonify(plans), 600)


@app.route("/api/news")
@limiter.limit("60 per minute")
def api_news():
    """Return cached news articles. Optional ?carrier=<id> filter."""
    carrier = request.args.get('carrier', None)
    articles = get_news_articles(carrier=carrier, db_path=_db_path())
    return _public_cache(jsonify(_filter_hidden_carrier(articles)), 600)


_AFFILIATE_FALLBACK_URLS = {
    "airalo":     "https://www.airalo.com",
    "holafly":    "https://esim.holafly.com",
    "saily":      "https://saily.com",
    "terminalesim": "https://terminalesim.com",
}

# ── MOCA Guest Connect — provider display + destination resolution ──────────
# label/color drive the guest-portal chips; url is the public Israel page used
# as the redirect destination when no affiliate deep link is configured. In
# production each provider's "url" is replaced by a referral-tagged base_url in
# config.json -> affiliate. Local Israeli carriers have no affiliate program yet
# but still flow through /go so per-hotel attribution + analytics are captured.
# `domain` drives the guest-portal logo (DuckDuckGo favicon CDN). None = no clean
# domain → the portal falls back to the colored monogram chip.
_GUEST_PROVIDER_META = {
    # global eSIM (ids match the scraper carrier ids that carry Israel packages)
    "saily":       {"label": "Saily",        "color": "#0fb39a", "domain": "saily.com",        "url": "https://saily.com/esim-israel/"},
    "airalo_local":{"label": "Airalo",       "color": "#ff5963", "domain": "airalo.com",       "url": "https://www.airalo.com/israel-esim"},
    "airalo":      {"label": "Airalo",       "color": "#ff5963", "domain": "airalo.com",       "url": "https://www.airalo.com/israel-esim"},
    "holafly":     {"label": "Holafly",      "color": "#fa3c54", "domain": "holafly.com",      "url": "https://esim.holafly.com/esim-israel/"},
    "esimo":       {"label": "eSIMo",        "color": "#6c5ce7", "domain": "esimo.io",         "url": "https://esimo.io"},
    "esimio":      {"label": "eSIM.io",      "color": "#5b6cf0", "domain": "esim.io",          "url": "https://esim.io"},
    "orbit":       {"label": "Orbit",        "color": "#2980ff", "domain": "orbitmobile.com",  "url": "https://orbitmobile.com"},
    "simtlv":      {"label": "SimTLV",       "color": "#2bb3c0", "domain": "simtlv.co.il",     "url": "https://simtlv.co.il"},
    "voye":        {"label": "Voye",         "color": "#e8553e", "domain": "voyeglobal.com",   "url": "https://voyeglobal.com"},
    "yesim":       {"label": "Yesim",        "color": "#f97316", "domain": "yesim.app",        "url": "https://yesim.app"},
    "nomad":       {"label": "Nomad",        "color": "#16a34a", "domain": "nomadesim.com",   "url": "https://www.nomadesim.com"},
    "ubigi":       {"label": "Ubigi",        "color": "#2563eb", "domain": "ubigi.com",        "url": "https://www.ubigi.com"},
    "alosim":      {"label": "aloSIM",       "color": "#dc2626", "domain": "alosim.com",       "url": "https://alosim.com"},
    "sparks":      {"label": "Sparks",       "color": "#f2a900", "domain": "sparks.travel",    "url": "https://www.sparks.travel"},
    "gomoworld":   {"label": "GoMoWorld",    "color": "#00a86b", "domain": "gomoworld.com",    "url": "https://www.gomoworld.com"},
    "bcengi":      {"label": "BCengi",       "color": "#555c66", "domain": "bcengi.com",        "url": "https://www.bcengi.com"},
    "esim70":      {"label": "eSIM70",       "color": "#1f6feb", "domain": "esim70.com",       "url": "https://esim70.com"},
    "esimgenius":  {"label": "eSIM Genius",  "color": "#7c3aed", "domain": "esimgenius.ai",    "url": "https://esimgenius.ai"},
    "nisim":       {"label": "Nisim eSIM",   "color": "#252551", "domain": "nisim-esim.co.il", "url": "https://www.nisim-esim.co.il"},
    "esimax":      {"label": "eSIM Max",     "color": "#b70a4d", "domain": "esimax.io",        "url": "https://esimax.io"},
    "venterrasim": {"label": "VenterraSIM",  "color": "#2463eb", "domain": "venterrasim.com",  "url": "https://venterrasim.com"},
    "simzol":      {"label": "Simzol",       "color": "#58b64b", "domain": "simzol.co.il",     "url": "https://www.simzol.co.il"},
    "jetpack":     {"label": "Jetpac",       "color": "#7b2ff7", "domain": "jetpacglobal.com", "url": "https://www.jetpacglobal.com"},
    "breez":       {"label": "Breeze",       "color": "#19b3c7", "domain": "breezesim.com",    "url": "https://breezesim.com"},
    "bytesim":     {"label": "ByteSIM",      "color": "#34495e", "domain": "bytesim.com",      "url": "https://bytesim.com"},
    "besim":       {"label": "BeSIM",        "color": "#e84393", "domain": "besim.co.il",      "url": "https://besim.co.il"},
    "bnesim":      {"label": "BNESIM",       "color": "#1e3a8a", "domain": "bnesim.com",       "url": "https://www.bnesim.com/plans/il/"},
    "seven_g":     {"label": "7G",           "color": "#e67e22", "domain": "7g.app",            "url": "https://7g.app"},
    "bestconnect": {"label": "Best Connect", "color": "#2d9cdb", "domain": "bestconnect.online", "url": "https://bestconnect.online"},
    "esimplus":    {"label": "eSIM Plus",    "color": "#00b894", "domain": "esimplus.me",      "url": "https://esimplus.me/esim/israel"},
    # global eSIM carriers that also surface for ABROAD destinations (the Israel
    # feed didn't reach them, so they were missing — abroad needs every id the
    # feed can emit to have a label + domain, else the chip is bare + /go dead-ends).
    "tuki":             {"label": "Tuki",          "color": "#6c2bd9", "domain": "tuki-esim.co.il"},
    "terminalesim":     {"label": "Terminal eSIM", "color": "#1a73e8", "domain": "terminalesim.com"},
    "gigsky":           {"label": "GigSky",        "color": "#2b4c9b", "domain": "gigsky.com",       "url": "https://www.gigsky.com"},
    "airalo_regional":  {"label": "Airalo",        "color": "#ff5963", "domain": "airalo.com"},
    "pelephone_global": {"label": "GlobalSIM",     "color": "#e3001b", "domain": "pelephone.co.il", "url": "https://www.pelephone.co.il/digitalsite/heb/abroad/global-sim/"},
    "world8":           {"label": "8 World",       "color": "#00a3a3", "domain": "world8.co.il"},
    "xphone_global":    {"label": "XPhone Global", "color": "#00857a", "domain": "xphone.co.il"},
    "travelsim":        {"label": "Travel Sim",    "color": "#f59e0b", "domain": "travelsimobile.co.il"},
    "tasim":            {"label": "Tasim",         "color": "#2563eb", "domain": "tasim.us"},
    "maya":             {"label": "Maya Mobile",   "color": "#ec4899", "domain": "maya.net",       "url": "https://maya.net/esim/israel"},  # Israel dest lands on Maya's IL eSIM page (per Bart, Maya 2026-06-30). Impact tracking base_url is wired in config.json["affiliate"]["maya"] (mayamobile.pxf.io/oNV1xn) → /go/maya attributes; this `url` is only the Israel-dest fallback.
    # local Israeli carriers — inbound-tourist SIM/eSIM (curated, see below)
    "mobile019":   {"label": "019 Mobile",     "color": "#d81b60", "domain": "019mobile.co.il", "url": "https://www.019mobile.co.il"},
    "partner":     {"label": "Partner Tourist","color": "#0072ce", "domain": "partner.co.il",   "url": "https://www.partner.co.il"},
    "cellcom":     {"label": "Cellcom Tourist","color": "#5f259f", "domain": "cellcom.co.il",   "url": "https://www.cellcom.co.il"},
    "hot":         {"label": "HOT Mobile",     "color": "#e4002b", "domain": "hotmobile.co.il", "url": "https://www.hotmobile.co.il"},
}

# Inbound-tourist local SIM/eSIM offers. These are NOT scraped (the system
# scrapes domestic plans for Israelis + roaming + global eSIM), so they are
# curated here. Prices in ILS, illustrative of current tourist packages — verify
# periodically. perks keys map to the guest portal i18n dictionary.
ISRAEL_TOURIST_LOCAL_SIMS = [
    {"provider": "mobile019", "form": "sim",  "gb": None, "days": 30, "price": 99,
     "perks": ["ilNumber", "calls", "airport"]},
    {"provider": "partner",   "form": "esim", "gb": 100,  "days": 30, "price": 89,
     "perks": ["ilNumber", "calls", "instant"]},
    {"provider": "cellcom",   "form": "sim",  "gb": 110,  "days": 30, "price": 99,
     "perks": ["ilNumber", "intlMin", "airport"]},
]


# AUTO-GENERATED aloSIM Hebrew-destination -> (slug, uid) map.
# Source: Everflow offer-9 URL table + alosim.com location sitemap.
# Regenerate via _build_alosim_map.py + _gen_alosim_code.py.
_ALOSIM_DEST_MAP = {
    "אוגנדה": ("uganda-esim", 1195),
    "אוזבקיסטן": ("uzbekistan-esim", 1197),
    "אוסטריה": ("austria-esim", 1177),
    "אוסטרליה": ("australia-esim", 573),
    "אוסטרליה וניו זילנד": ("australia-and-nz-esim", None),
    "אוקראינה": ("ukraine-esim", 1039),
    "אורוגוואי": ("uruguay-esim", 1038),
    "אזרבייג'ן": ("azerbaijan-esim", 1244),
    "איחוד האמירויות": ("united-arab-emirates-esim", 1196),
    "איטליה": ("italy-esim", 597),
    "איי הבהאמה": ("bahamas-esim", 574),
    "איי הבתולה (ארה\"ב)": ("us-virgin-islands-esim", 1194),
    "איי הבתולה (בריטניה)": ("british-virgin-islands-esim", 1045),
    "איי הקריביים": ("caribbean-esim", 682),
    "איי טורקס וקאיקוס": ("turks-and-caicos-esim", 1040),
    "איי סיישל": ("seychelles-esim", None),
    "איי פארו": ("faroe-islands-esim", 917),
    "איי קיימן": ("cayman-islands-esim", 1064),
    "אינדונזיה": ("indonesia-esim", 1067),
    "איסלנד": ("iceland-esim", 593),
    "אירופה": ("europe-esim", 564),
    "אירלנד": ("ireland-esim", 680),
    "אל סלבדור": ("el-salvador-esim", 919),
    "אלבניה": ("albania-esim", 571),
    "אלג'יריה": ("algeria-esim", 1199),
    "אנגווילה": ("anguilla-esim", 1049),
    "אנדורה": ("andorra-esim", None),
    "אנטיגואה וברבודה": ("antigua-and-barbuda-esim", 918),
    "אנטילים הולנדיים": ("netherlands-antilles-esim", None),
    "אסוואטיני": ("eswatini-esim", None),
    "אסטוניה": ("estonia-esim", 913),
    "אסיה": ("asia-esim", 562),
    "אפגניסטן": ("afghanistan-esim", 1243),
    "אקוודור": ("ecuador-esim", 586),
    "ארגנטינה": ("argentina-esim", 572),
    "ארובה": ("aruba-esim", 1065),
    "ארמניה": ("armenia-esim", 1088),
    "ארצות הברית": ("united-states-esim", 615),
    "אתיופיה": ("ethiopia-esim", None),
    "באלי": ("indonesia-esim", 1067),
    "בהוטן": ("bhutan-esim", 1245),
    "בוטסואנה": ("botswana-esim", 1246),
    "בולגריה": ("bulgaria-esim", 577),
    "בוליביה": ("bolivia-esim", 1041),
    "בוסניה והרצגובינה": ("bosnia-and-herzegovina-esim", None),
    "בורקינה פאסו": ("burkina-faso-esim", None),
    "בחריין": ("bahrain-esim", 914),
    "בלארוס": ("belarus-esim", 1178),
    "בלגיה": ("belgium-esim", 575),
    "בליז": ("belize-esim", None),
    "בנגלדש": ("bangladesh-esim", 911),
    "בנין": ("benin-esim", None),
    "ברבדוס": ("barbados-esim", 1042),
    "ברוניי": ("brunei-esim", 1247),
    "ברזיל": ("brazil-esim", 576),
    "בריטניה": ("uk-esim", 614),
    "בריטניה ואירלנד": ("uk-ireland-esim", 569),
    "ברמודה": ("bermuda-esim", 1037),
    "ג'מייקה": ("jamaica-esim", 1066),
    "ג'רזי": ("jersey-esim", 1046),
    "גאבון": ("gabon-esim", None),
    "גאורגיה": ("georgia-esim", 908),
    "גאנה": ("ghana-esim", 590),
    "גואטמלה": ("guatemala-esim", 1261),
    "גואם": ("guam-esim", 1262),
    "גוואדלופ": ("guadeloupe-esim", None),
    "גיאנה": ("guyana-esim", None),
    "גיאנה הצרפתית": ("french-guiana-esim", None),
    "גיאנה הצרפתית ומרטיניק": ("french-guiana-and-martinique-esim", None),
    "גיברלטר": ("gibraltar-esim", None),
    "גינאה": ("guinea-esim", None),
    "גינאה ביסאו": ("guinea-bissau-esim", None),
    "גלובלי": ("global-esim", None),
    "גמביה": ("gambia-esim", None),
    "גרינלנד": ("greenland-esim", 1050),
    "גרמניה": ("germany-esim", 589),
    "גרנדה": ("grenada-esim", 1096),
    "גרנזי": ("guernsey-esim", None),
    "דומיניקה": ("dominica-esim", 1095),
    "דנמרק": ("denmark-esim", 585),
    "דרום אמריקה": ("south-america-esim", 568),
    "דרום אפריקה": ("south-africa-esim", 1193),
    "דרום קוריאה": ("south-korea-esim", 608),
    "האי מאן": ("isle-of-man-esim", None),
    "האיטי": ("haiti-esim", None),
    "האיים המלדיביים": ("maldives-esim", None),
    "הודו": ("india-esim", 594),
    "הוואי": ("united-states-esim", 615),
    "הולנד": ("netherlands-esim", 600),
    "הונג קונג": ("hong-kong-esim", 916),
    "הונגריה": ("hungary-esim", 592),
    "הונדורס": ("honduras-esim", 1094),
    "הליפקס": ("halifax-esim", None),
    "הפיליפינים": ("philippines-esim", 1187),
    "הרפובליקה הדומיניקנית": ("dominican-republic-esim", 1063),
    "הרפובליקה הדמוקרטית של קונגו": ("democratic-republic-of-the-congo-esim", None),
    "הרפובליקה המרכז אפריקאית": ("central-african-republic-esim", None),
    "וייטנאם": ("vietnam-esim", 906),
    "ונצואלה": ("venezuela-esim", 1198),
    "ותיקן": ("vatican-city-esim", None),
    "זמביה": ("zambia-esim", 1249),
    "חוף השנהב": ("ivory-coast-cote-divoire-esim", None),
    "טג'יקיסטן": ("tajikistan-esim", 1260),
    "טוגו": ("togo-esim", None),
    "טונגה": ("tonga-esim", 1253),
    "טורונטו": ("canada-esim", 578),
    "טורקיה": ("turkey-esim", 613),
    "טייוואן": ("taiwan-esim", 912),
    "טימור לסטה": ("timor-leste-esim", None),
    "טנזניה": ("tanzania-esim", None),
    "טקסס": ("united-states-esim", 615),
    "טרינידד וטובגו": ("trinidad-and-tobago-esim", None),
    "יוון": ("greece-esim", 591),
    "יפן": ("japan-esim", 598),
    "ירדן": ("jordan-esim", 1091),
    "ישראל": ("israel-esim", 596),
    "כוויית": ("kuwait-esim", None),
    "לאוס": ("laos-esim", 1258),
    "לבנון": ("lebanon-esim", None),
    "לוקסמבורג": ("luxembourg-esim", 920),
    "לטביה": ("latvia-esim", 683),
    "ליבריה": ("liberia-esim", 1090),
    "ליטא": ("lithuania-esim", 905),
    "ליכטנשטיין": ("liechtenstein-esim", 1044),
    "לסוטו": ("lesotho-esim", 1092),
    "מאוריציוס": ("mauritius-esim", None),
    "מאיוט": ("mayotte-esim", 1252),
    "מאלי": ("mali-esim", None),
    "מדגסקר": ("madagascar-esim", None),
    "מוזמביק": ("mozambique-esim", None),
    "מולדובה": ("moldova-esim", 1043),
    "מונגוליה": ("mongolia-esim", None),
    "מונטנגרו": ("montenegro-esim", 1181),
    "מונסראט": ("montserrat-esim", None),
    "מונקו": ("monaco-esim", None),
    "מזרח אירופה": ("eastern-europe-esim", 563),
    "מלאווי": ("malawi-esim", None),
    "מלזיה": ("malaysia-esim", 910),
    "מלטה": ("malta-esim", 681),
    "מערב אירופה": ("western-europe-esim", 570),
    "מצרים": ("egypt-esim", 907),
    "מקאו": ("macau-esim", 1051),
    "מקדוניה הצפונית": ("macedonia-esim", None),
    "מקסיקו": ("mexico-esim", 599),
    "מרוקו": ("morocco-esim", 1182),
    "מרטיניק": ("martinique-esim", 922),
    "מרכז אמריקה": ("central-america-esim", None),
    "נאורו": ("nauru-esim", None),
    "נורבגיה": ("norway-esim", 1184),
    "ניג'ר": ("niger-esim", None),
    "ניגריה": ("nigeria-esim", 1183),
    "ניו זילנד": ("new-zealand-esim", 601),
    "ניו יורק": ("united-states-esim", 615),
    "ניקראגואה": ("nicaragua-esim", 1256),
    "נמיביה": ("namibia-esim", None),
    "נפאל": ("nepal-esim", 1257),
    "סודן": ("the-sudan-esim", None),
    "סורינאם": ("suriname-esim", None),
    "סיירה ליאונה": ("sierra-leone-esim", None),
    "סין": ("china-esim", 1180),
    "סינגפור": ("singapore-esim", 606),
    "סלובניה": ("slovenia-esim", 909),
    "סלובקיה": ("slovakia-esim", 607),
    "סן ברתלמי": ("saint-barthelemy-esim", None),
    "סן מרינו": ("san-marino-esim", 1048),
    "סנגל": ("senegal-esim", None),
    "סנט וינסנט והגרדינים": ("saint-vincent-esim", 1251),
    "סנט לוסיה": ("saint-lucia-esim", 1191),
    "סנט קיטס ונוויס": ("saint-kitts-and-nevis-esim", None),
    "ספרד": ("spain-esim", 609),
    "סקנדינביה": ("scandinavia-esim", 567),
    "סרביה": ("serbia-esim", 1036),
    "סרי לנקה": ("sri-lanka-esim", 1254),
    "עומאן": ("oman-esim", 1259),
    "עיראק": ("iraq-esim", 595),
    "ערב הסעודית": ("saudi-arabia-esim", 1192),
    "פוארטו ריקו": ("puerto-rico-esim", 1188),
    "פולין": ("poland-esim", 602),
    "פולינזיה הצרפתית": ("french-polynesia-esim", None),
    "פורטוגל": ("portugal-esim", 603),
    "פיג'י": ("fiji-esim", 679),
    "פינלנד": ("finland-esim", 587),
    "פלורידה": ("united-states-esim", 615),
    "פנמה": ("panama-esim", 1186),
    "פפואה גינאה החדשה": ("papua-new-guinea-esim", None),
    "פקיסטן": ("pakistan-esim", 1185),
    "פראגוואי": ("paraguay-esim", None),
    "פרו": ("peru-esim", 1047),
    "צ'אד": ("chad-esim", None),
    "צ'ילה": ("chile-esim", 579),
    "צ'כיה": ("czech-republic-esim", 584),
    "צפון אמריקה": ("north-america-esim", 566),
    "צרפת": ("france-esim", 588),
    "קולומביה": ("colombia-esim", 580),
    "קוסובו": ("kosovo-esim", None),
    "קוסטה ריקה": ("costa-rica-esim", 581),
    "קוראסאו": ("curacao-esim", None),
    "קזחסטן": ("kazakhstan-esim", 915),
    "קטר": ("qatar-esim", 604),
    "קייפ ורדה": ("cabo-verde-esim", None),
    "קירגיזסטן": ("kyrgyzstan-esim", None),
    "קיריבאטי": ("kiribati-esim", None),
    "קליפורניה": ("california-esim", None),
    "קמבודיה": ("cambodia-esim", 1179),
    "קמרון": ("cameroon-esim", 1248),
    "קנדה": ("canada-esim", 578),
    "קניה": ("kenya-esim", 1089),
    "קפריסין": ("cyprus-esim", 583),
    "קרואטיה": ("croatia-esim", 582),
    "ראוניון": ("reunion-esim", 1052),
    "רואנדה": ("rwanda-esim", 1190),
    "רומניה": ("romania-esim", 605),
    "רפובליקת קונגו": ("republic-of-the-congo-esim", None),
    "שבדיה": ("sweden-esim", 610),
    "שוויץ": ("switzerland-esim", 611),
    "תאילנד": ("thailand-esim", 612),
    "תוניסיה": ("tunisia-esim", 1250),
}

def _alosim_dest_url(destination):
    """Build a per-destination aloSIM affiliate URL with Everflow uid when known."""
    entry = _ALOSIM_DEST_MAP.get(destination or "")
    if not entry:
        return None
    slug, uid = entry
    params = "uid={}&oid=9&affid=1652".format(uid) if uid else "oid=9&affid=1652"
    return "https://alosim.com/{}/?{}".format(slug, params)


def _guest_provider_dest(provider, destination=None):
    """Resolve the redirect destination for a guest-portal provider:
    affiliate deep link (config) → provider country page → legacy fallback.
    For non-Israel destinations the per-provider `url` (an Israel landing page) is
    the wrong target, so fall back to the provider's generic homepage."""
    # aloSIM: per-destination deep links with Everflow uid tracking
    if provider == "alosim":
        dest_url = _alosim_dest_url(destination)
        if dest_url:
            return dest_url
        return "https://alosim.com/?oid=9&affid=1652"
    cfg = load_config()
    affiliate = cfg.get("affiliate", {}).get(provider)
    if affiliate and affiliate.get("base_url"):
        return affiliate["base_url"]
    meta = _GUEST_PROVIDER_META.get(provider)
    if meta and destination and destination != "ישראל" and meta.get("domain"):
        return f"https://{meta['domain']}"
    if meta and meta.get("url"):
        return meta["url"]
    if meta and meta.get("domain"):  # provider with a homepage but no curated url
        return f"https://{meta['domain']}"
    return _AFFILIATE_FALLBACK_URLS.get(provider, "https://mocaintel.com")


ISRAEL_HE = "ישראל"  # ישראל — canonical destination
_CRUISE_DEST_HE = "קרוז"  # קרוז — synthetic B2C cruise destination (mirrors db._CRUISE_DEST_HE)


def _assemble_guest_deals(db_path=None, destination=None, include_local=True):
    """Build the guest-portal deal list for a destination country = live eSIM
    plans covering it (curated to a clean per-provider ladder). For Israel it also
    appends the curated local Israeli tourist SIMs; abroad destinations get the
    global-eSIM feed only (we carry no foreign local carriers).

    Pass include_local=False for the public B2C consumer feed, which compares
    global-eSIM providers only (no local Israeli tourist SIMs)."""
    from collections import defaultdict
    dest = (destination or ISRAEL_HE).strip()
    raw = get_esim_deals_for_destination(dest, db_path=db_path)
    updated_at = max((d.get("scraped_at") for d in raw if d.get("scraped_at")), default=None)
    # cheapest per (provider, gb, days) — collapse exact-size duplicates
    best = {}
    for d in raw:
        key = (d["carrier"], d["data_gb"], d["days"])
        if key not in best or (d["price"] or 1e9) < (best[key]["price"] or 1e9):
            best[key] = d
    # Cap per provider to a 6-deal ladder SPREAD across data sizes — NOT the 6
    # smallest. Providers with many tiny/daily plans (e.g. Terminal eSIM, whose
    # catalog is dominated by sub-2GB and per-day packages) would otherwise show
    # only their smallest deals, which all fail the consumer trip filter
    # (default 10GB) and vanish from the page entirely. Instead: keep the
    # cheapest deal per data size, then sample up to 6 sizes evenly across the
    # range so the ladder spans small … large/unlimited.
    by_prov = defaultdict(list)
    for d in best.values():
        by_prov[d["carrier"]].append(d)
    # For the cruise view, size alone is a poor ladder key: a provider's whole cruise
    # offering can be unlimited (data_gb=None) at several durations (Maya: 3/7/14/30
    # days), which would otherwise collapse to a single rung. Key on (size, days) for
    # cruise so each duration tier survives; countries keep the size-only ladder.
    cruise_view = (dest == _CRUISE_DEST_HE)
    curated = []
    for prov, lst in by_prov.items():
        # cheapest deal per distinct data size (None = unlimited → sorted last)
        per_size = {}
        for d in lst:
            k = (d["data_gb"], d["days"]) if cruise_view else d["data_gb"]
            if k not in per_size or (d["price"] or 1e9) < (per_size[k]["price"] or 1e9):
                per_size[k] = d
        sizes = sorted(
            per_size.values(),
            key=lambda d: (d["data_gb"] if d["data_gb"] is not None else 1e9),
        )
        if len(sizes) <= 6:
            curated.extend(sizes)
        else:
            # evenly-spaced 6 including the smallest and largest tiers
            idxs = sorted({round(i * (len(sizes) - 1) / 5) for i in range(6)})
            curated.extend(sizes[i] for i in idxs)

    deals = []
    for d in curated:
        unl = d["data_gb"] is None
        deals.append({
            "provider": d["carrier"],
            "kind": "global",
            "form": "esim" if d["esim"] else "sim",
            "gb": d["data_gb"],
            "days": d["days"],
            "price": round(d["price"], 2) if d["price"] is not None else None,
            "original_price": d["original_price"],
            "currency": d["currency"] or "USD",
            "plan_name": d["plan_name"],
            "perks": ["instant", "unlimited"] if unl else ["instant"],
        })
    for s in (ISRAEL_TOURIST_LOCAL_SIMS if (include_local and dest == ISRAEL_HE) else []):
        deals.append({
            "provider": s["provider"],
            "kind": "local",
            "form": s["form"],
            "gb": s["gb"],
            "days": s["days"],
            "price": s["price"],
            "original_price": s["price"],
            "currency": "ILS",
            "plan_name": _GUEST_PROVIDER_META.get(s["provider"], {}).get("label", s["provider"]),
            "perks": s["perks"],
        })
    deals.sort(key=lambda x: (x["price"] if x["price"] is not None else 1e9))
    providers = {d["provider"]: {
        "label": _GUEST_PROVIDER_META.get(d["provider"], {}).get(
            "label", _HISTORY_CARRIER_NAMES.get(d["provider"], d["provider"])),
        "color": _GUEST_PROVIDER_META.get(d["provider"], {}).get("color", "#5c3317"),
        "domain": _GUEST_PROVIDER_META.get(d["provider"], {}).get("domain"),
    } for d in deals}
    return deals, providers, updated_at


def _saily_sub_fragment(sub_id):
    """URL-encoded `aff_sub=<Sub-ID>` fragment for a Saily placement (e.g. a hotel
    property code), or '' when there's no Sub-ID. Per the Saily Affiliate Team
    (2026-07-03), aff_sub is added to the go.saily.site tracking URL (before the
    url= parameter); Tune records it with the click/conversion, giving per-hotel
    attribution on Saily's side."""
    if not sub_id:
        return ""
    from urllib.parse import quote
    return "aff_sub=" + quote(str(sub_id)[:60], safe="")


def _saily_attach_sub(url, sub_id):
    """Attach an aff_sub Sub-ID to a bare go.saily.site tracking link (the generic
    Saily fallback, which carries no url= deep-link). No-op for non-Saily URLs, an
    empty Sub-ID, or a link that already has one."""
    sub = _saily_sub_fragment(sub_id)
    if not sub or "go.saily.site" not in url or "aff_sub=" in url:
        return url
    return url + ("&" if "?" in url else "?") + sub


def _saily_checkout_url(plan_name, db_path=None, sub_id=None):
    """Per-plan Saily checkout deep-link: route the click through the affiliate
    tracker (go.saily.site) to saily.com/checkout for the exact plan, keeping
    attribution. aff_id / aff_offer_id / aff_transaction_id stay as literal Saily
    macros (the redirector fills them in). When sub_id is set (a hotel code) an
    aff_sub Sub-ID is added to the go.saily.site URL for per-placement tracking.
    Returns None when we have no checkout token for the plan, so /go falls back to
    the generic tracking link."""
    ref = get_plan_ref("saily", plan_name, db_path=db_path)
    if not ref:
        return None
    from urllib.parse import quote
    checkout = ("https://saily.com/checkout/?planId=" + ref +
                "&aff_transaction_id={transaction_id}&aff_offer_id={offer_id}&aff_id={aff_id}")
    base = (load_config().get("affiliate", {}).get("saily", {}).get("base_url")
            or "https://go.saily.site/aff_c?offer_id=101&aff_id=14705")
    sub = _saily_sub_fragment(sub_id)
    if sub:
        base += ("&" if "?" in base else "?") + sub
    sep = "&" if "?" in base else "?"
    return base + sep + "url=" + quote(checkout, safe="")


# Per-plan Maya Impact deep-links — generated 2026-07-03 in the Impact partner
# dashboard (one TrackingLink per plan URL from assets.maya.net/affiliates/plans.json).
# A /go/maya?plan=… click deep-links to the exact plan page WITH attribution instead
# of the generic plans-page link (config.json affiliate.maya.base_url = oNV1xn), which
# still serves as the fallback. Keyed by (region, days) parsed from the plan_name the
# maya scraper builds: "גלובלי – … – 3 ימים" (global)
# / "גלובלי ושייט – … – 14 ימים" (cruise).
_MAYA_PLAN_DEEPLINKS = {
    ("global", 3):  "https://mayamobile.pxf.io/VOgJBM",
    ("global", 7):  "https://mayamobile.pxf.io/vDW5Qy",
    ("global", 14): "https://mayamobile.pxf.io/4a2zyr",
    ("global", 30): "https://mayamobile.pxf.io/NGX5Rb",
    ("cruise", 3):  "https://mayamobile.pxf.io/yZWajb",
    ("cruise", 7):  "https://mayamobile.pxf.io/MKgP22",
    ("cruise", 14): "https://mayamobile.pxf.io/KBgrOy",
    ("cruise", 30): "https://mayamobile.pxf.io/7XdEnd",
}


def _maya_deeplink_url(plan_name):
    """Map a stored Maya plan_name to its plan-specific Impact TrackingLink, or None
    if it can't be matched (so /go/maya falls back to the generic base_url)."""
    if not plan_name:
        return None
    name = plan_name.strip()
    if name.startswith("גלובלי ושייט"):  # "גלובלי ושייט" (global + cruise)
        region = "cruise"
    elif name.startswith("גלובלי"):  # "גלובלי" (global)
        region = "global"
    else:
        return None
    days = next((d for d in (3, 7, 14, 30)
                 if f"{d} ימים" in name), None)  # "N ימים"
    if days is None:
        return None
    return _MAYA_PLAN_DEEPLINKS.get((region, days))


# Per-destination deep-links for Voye + Ubigi (top travel destinations only).
# Unlike Maya's 8-plan catalog, these have 1,000+ plans across 180+ countries with
# no per-plan URL, so we deep-link the busiest destinations and let the long tail
# fall back to the generic base_url. Generated 2026-07-03 in the Impact dashboard
# (Voye → voyeglobal.com/he/esim/<country>/, Ubigi → cellulardata.ubigi.com/…
# ?destination=<iso3>). Keyed by the canonical Hebrew destination the consumer/guest
# surfaces pass as ?dest=. All verified: 302 → country page carrying irpid=7205658.
_VOYE_DEST_DEEPLINKS = {
    "ישראל":            "https://voyeglobalconnectivity.pxf.io/aNPbPb",
    "ארצות הברית":      "https://voyeglobalconnectivity.pxf.io/1G2X2a",
    "בריטניה":          "https://voyeglobalconnectivity.pxf.io/JkB9jr",
    "תאילנד":           "https://voyeglobalconnectivity.pxf.io/gRJmrO",
    "יפן":              "https://voyeglobalconnectivity.pxf.io/PzBeBX",
    "איטליה":           "https://voyeglobalconnectivity.pxf.io/oNVxGn",
    "יוון":             "https://voyeglobalconnectivity.pxf.io/B5BNGx",
    "ספרד":             "https://voyeglobalconnectivity.pxf.io/0G2gnP",
    "צרפת":             "https://voyeglobalconnectivity.pxf.io/E02Lxe",
    "גרמניה":           "https://voyeglobalconnectivity.pxf.io/n4gqAo",
    "איחוד האמירויות":  "https://voyeglobalconnectivity.pxf.io/bk56qP",
    "טורקיה":           "https://voyeglobalconnectivity.pxf.io/6k70xV",
    "הולנד":            "https://voyeglobalconnectivity.pxf.io/OYzkaz",
    "גאורגיה":          "https://voyeglobalconnectivity.pxf.io/2R2ogg",
    "אירופה":           "https://voyeglobalconnectivity.pxf.io/R0KALa",
    "גלובלי":           "https://voyeglobalconnectivity.pxf.io/vDW50O",
}
_UBIGI_DEST_DEEPLINKS = {
    "ישראל":            "https://go.ubigi.com/MKgPk3",
    "ארצות הברית":      "https://go.ubigi.com/KBgrPA",
    "בריטניה":          "https://go.ubigi.com/m4NLaq",
    "תאילנד":           "https://go.ubigi.com/L0gj5L",
    "יפן":              "https://go.ubigi.com/4a2zLM",
    "איטליה":           "https://go.ubigi.com/qWVQ0j",
    "יוון":             "https://go.ubigi.com/DWBYqo",
    "ספרד":             "https://go.ubigi.com/QY0aGM",
    "צרפת":             "https://go.ubigi.com/9V2m90",
    "גרמניה":           "https://go.ubigi.com/rER905",
    "איחוד האמירויות":  "https://go.ubigi.com/PzBeAX",
    "טורקיה":           "https://go.ubigi.com/5kKWq9",
    "הולנד":            "https://go.ubigi.com/k4Vykn",
    "גאורגיה":          "https://go.ubigi.com/ena3QD",
    "אירופה":           "https://go.ubigi.com/MKkqe2",
    "קנדה":             "https://go.ubigi.com/DWq6xa",
    "גלובלי":           "https://go.ubigi.com/L05LkL",
}


def _voye_deeplink_url(dest):
    """Voye per-destination Impact deep-link for a top destination, else None."""
    return _VOYE_DEST_DEEPLINKS.get((dest or "").strip())


def _ubigi_deeplink_url(dest):
    """Ubigi per-destination Impact deep-link for a top destination, else None."""
    return _UBIGI_DEST_DEEPLINKS.get((dest or "").strip())


# Breeze (UpPromote/Shopify) — unlike Voye/Ubigi (Impact TrackingLinks generated one
# per URL), Breeze attributes via a single `sca_ref` query param that works on ANY store
# page, so a per-destination deep link is just the country's product page + ?sca_ref=.
# The Hebrew dest -> Shopify handle map lives in scraper.BREEZ_HEB_TO_HANDLE (co-located
# with the scraper that reads those same product collections). Format confirmed via the
# dashboard "Get product link" tool 2026-07-06: it emits /products/<handle>?sca_ref=<tag>.
# UpPromote also supports an optional `sca_source` sub-tag (the "Get link with source"
# feature) — we ride the traffic channel (hotel > src) on it for per-placement reporting.
_BREEZ_HEB_TO_HANDLE = None  # lazily imported from scraper


def _breez_deeplink_url(dest=None, src=None, hotel=None):
    """Breeze per-destination Shopify product deep-link with UpPromote sca_ref
    attribution (+ optional sca_source = hotel/src for per-placement tracking). Falls
    back to the configured homepage tracking link when the destination has no known
    product handle, so every breez click stays attributed. Returns None only when breez
    isn't configured at all (so /go drops to the generic path)."""
    global _BREEZ_HEB_TO_HANDLE
    aff = load_config().get("affiliate", {}).get("breez", {}) or {}
    ref, base = aff.get("tag"), aff.get("base_url")
    if not ref and not base:
        return None
    if _BREEZ_HEB_TO_HANDLE is None:
        try:
            from scraper import BREEZ_HEB_TO_HANDLE
            _BREEZ_HEB_TO_HANDLE = BREEZ_HEB_TO_HANDLE
        except Exception:
            _BREEZ_HEB_TO_HANDLE = {}
    handle = _BREEZ_HEB_TO_HANDLE.get((dest or "").strip())
    if handle and ref:
        url = "https://breezesim.com/products/{}?sca_ref={}".format(handle, ref)
    else:
        url = base or "https://breezesim.com?sca_ref={}".format(ref)
    source = (hotel or src or "").strip()
    if source:
        from urllib.parse import quote
        url += ("&" if "?" in url else "?") + "sca_source=" + quote(source[:60], safe="")
    return url


# Bcengi has NO per-destination pages (verified via sitemap 2026-07-04: a single
# /travelpass/pricing page covers all 200+ countries), so per-destination Impact
# TrackingLinks à la Voye/Ubigi would all land on the same page. Instead, the
# destination rides on Impact's standard SubId click parameters appended to the
# one tracking link (config.json affiliate.bcengi.base_url): subId1 = destination
# (English slug), subId2 = traffic source (src), subId3 = hotel code. Impact
# records SubIds per click/conversion, so reporting can be segmented per
# destination without separate links.
_BCENGI_HEB_TO_EN = None  # lazily inverted from scraper.BCENGI_EN_TO_HEB


def _bcengi_subid_url(dest=None, src=None, hotel=None):
    """The Bcengi Impact tracking link with per-click SubIds attached, or None
    when no tracking link is configured (so /go falls back to the generic path)."""
    global _BCENGI_HEB_TO_EN
    base = (load_config().get("affiliate", {}).get("bcengi", {}) or {}).get("base_url")
    if not base:
        return None
    if _BCENGI_HEB_TO_EN is None:
        try:
            from scraper import BCENGI_EN_TO_HEB
            _BCENGI_HEB_TO_EN = {heb: en for en, heb in BCENGI_EN_TO_HEB.items()}
        except Exception:
            _BCENGI_HEB_TO_EN = {}
    from urllib.parse import quote
    params = []
    d = (dest or "").strip()
    if d:
        en = _BCENGI_HEB_TO_EN.get(d, d)
        params.append("subId1=" + quote(en.lower().replace(" ", "-")[:60], safe="-"))
    if src:
        params.append("subId2=" + quote(str(src)[:40], safe=""))
    if hotel:
        params.append("subId3=" + quote(str(hotel)[:60], safe=""))
    if not params:
        return base
    return base + ("&" if "?" in base else "?") + "&".join(params)


# Orbit Mobile has NO per-destination pages either (verified live 2026-07-08: the
# orbitmobile.com store is a SPA where picking a country expands an inline accordion —
# the URL stays /en/plans/top-destinations, so per-destination Impact TrackingLinks à
# la Voye/Ubigi would all land on the same page). So the destination rides on Impact's
# standard SubId click parameters appended to the one tracking link (config.json
# affiliate.orbit.base_url): subId1 = destination (English slug), subId2 = traffic
# source (src), subId3 = hotel code. Impact records SubIds per click/conversion, so
# reporting segments per destination without separate links.
_ORBIT_HEB_TO_EN = None  # lazily inverted from scraper.ORBIT_NAME_TO_HEBREW


def _orbit_subid_url(dest=None, src=None, hotel=None):
    """The Orbit Impact tracking link with per-click SubIds attached, or None when no
    tracking link is configured (so /go falls back to the generic path)."""
    global _ORBIT_HEB_TO_EN
    base = (load_config().get("affiliate", {}).get("orbit", {}) or {}).get("base_url")
    if not base:
        return None
    if _ORBIT_HEB_TO_EN is None:
        try:
            from scraper import ORBIT_NAME_TO_HEBREW
            inv = {}
            for en, heb in ORBIT_NAME_TO_HEBREW.items():
                if heb:
                    inv.setdefault(heb, en)
            _ORBIT_HEB_TO_EN = inv
        except Exception:
            _ORBIT_HEB_TO_EN = {}
    from urllib.parse import quote
    params = []
    d = (dest or "").strip()
    if d:
        en = _ORBIT_HEB_TO_EN.get(d, d)
        params.append("subId1=" + quote(en.lower().replace(" ", "-")[:60], safe="-"))
    if src:
        params.append("subId2=" + quote(str(src)[:40], safe=""))
    if hotel:
        params.append("subId3=" + quote(str(hotel)[:60], safe=""))
    if not params:
        return base
    return base + ("&" if "?" in base else "?") + "&".join(params)


# GigSky (Everflow network, per Alex Dufort / GigSky 2026-07-06). Per-destination
# deep links to specific country/plan pages were "just launched" on GigSky's side
# but the URL format is pending documentation, so until then a /go/gigsky click
# lands on the configured Everflow tracking link (config.json affiliate.gigsky.
# base_url) with the viewed destination + traffic source + hotel carried as
# Everflow Sub-IDs: sub1 = destination (ISO code), sub2 = src, sub5 = hotel.
# Everflow records Sub-IDs per click/conversion, so reporting is segmented per
# destination/placement without separate links. Returns None when no tracking
# link is configured yet (so /go falls back to the generic gigsky.com dest).
_GIGSKY_HEB_TO_CODE = None  # lazily inverted from scraper code→Hebrew maps


def _gigsky_deeplink_url(dest=None, src=None, hotel=None):
    """The GigSky Everflow tracking link with per-click Sub-IDs attached, or None
    when no tracking link is configured (so /go falls back to the generic path)."""
    global _GIGSKY_HEB_TO_CODE
    base = (load_config().get("affiliate", {}).get("gigsky", {}) or {}).get("base_url")
    if not base:
        return None
    if _GIGSKY_HEB_TO_CODE is None:
        try:
            from scraper import ESIMO_CODE_TO_HEBREW, GIGSKY_CODE_EXTRA
            inv = {}
            for code, heb in {**ESIMO_CODE_TO_HEBREW, **GIGSKY_CODE_EXTRA}.items():
                if heb:
                    inv.setdefault(heb, code)
            _GIGSKY_HEB_TO_CODE = inv
        except Exception:
            _GIGSKY_HEB_TO_CODE = {}
    from urllib.parse import quote
    params = []
    d = (dest or "").strip()
    if d:
        code = _GIGSKY_HEB_TO_CODE.get(d, d)
        params.append("sub1=" + quote(str(code)[:60], safe=""))
    if src:
        params.append("sub2=" + quote(str(src)[:40], safe=""))
    if hotel:
        params.append("sub5=" + quote(str(hotel)[:60], safe=""))
    if not params:
        return base
    return base + ("&" if "?" in base else "?") + "&".join(params)


# GoMoWorld (Puremium/HasOffers, offer 23, Affiliate ID 1968). The default tracking
# link (config.json affiliate.gomoworld.base_url) lands on gomoworld.com's homepage.
# For a per-destination deep link we ride Puremium's `url=` redirect override: the
# aff_c tracker URL-decodes the url= value and fills the {transaction_id}/
# {affiliate_id} macros inside it (verified 2026-07-06), so the click stays fully
# attributed (this is a Server-Postback-with-Transaction-ID offer) while landing
# straight on the country page. We rebuild the exact querystring Puremium appends to
# its own default landing — utm_source=puremium, affiliate={affiliate_id},
# transaction_id={transaction_id}, promocode=MOCA — so the MOCA 10% code is
# auto-applied on the destination page too. Hebrew dest -> English destination slug
# comes from scraper.GOMOWORLD_SLUG_TO_HEBREW (the same map the scraper reads
# gomoworld.com/en/destinations/<slug> from). Unmapped dests return None so /go
# falls back to the generic config link.
_GOMOWORLD_HEB_TO_SLUG = None  # lazily inverted from scraper.GOMOWORLD_SLUG_TO_HEBREW


def _gomoworld_deeplink_url(dest=None, src=None, hotel=None):
    """GoMoWorld per-destination deep link via Puremium's url= override — fully
    attributed (transaction_id macro) with the MOCA promo code auto-applied. Returns
    None when the destination is unknown or no tracking link is configured, so /go
    falls back to the generic config link."""
    global _GOMOWORLD_HEB_TO_SLUG
    aff = load_config().get("affiliate", {}).get("gomoworld", {}) or {}
    aff_id = aff.get("tag")
    if not aff_id:
        return None
    if _GOMOWORLD_HEB_TO_SLUG is None:
        try:
            from scraper import GOMOWORLD_SLUG_TO_HEBREW
            inv = {}
            for slug, heb in GOMOWORLD_SLUG_TO_HEBREW.items():
                if heb:
                    inv.setdefault(heb, slug)
            _GOMOWORLD_HEB_TO_SLUG = inv
        except Exception:
            _GOMOWORLD_HEB_TO_SLUG = {}
    slug = _GOMOWORLD_HEB_TO_SLUG.get((dest or "").strip())
    if not slug:
        return None
    from urllib.parse import quote
    landing = (
        "https://www.gomoworld.com/en/destinations/{}"
        "?utm_source=puremium&affiliate={{affiliate_id}}"
        "&transaction_id={{transaction_id}}&promocode=MOCA"
    ).format(slug)
    link = "https://www.puremium1.com/aff_c?offer_id=23&aff_id={}&url={}".format(
        aff_id, quote(landing, safe=""))
    source = (hotel or src or "").strip()
    if source:  # per-placement reporting on Puremium's Sub-ID
        link += "&aff_sub=" + quote(source[:60], safe="")
    return link


@app.route("/go/<provider>")
@app.route("/go/<provider>/<plan_id>")
@limiter.limit("120 per minute")
def affiliate_redirect(provider, plan_id=None):
    ip      = _client_ip()
    ua      = request.headers.get("User-Agent", "")
    cfg     = load_config()
    api_key = cfg.get("api_key", "")
    ip_hash = hmac.new(api_key.encode(), ip.encode(), hashlib.sha256).hexdigest()
    country = request.args.get("country")
    hotel   = request.args.get("hotel")
    # Cap the stored plan label (mirrors the src/campaign caps below) so a crafted
    # ?plan=<huge string> can't bloat affiliate_clicks / guest_events.
    plan    = (request.args.get("plan") or plan_id or "")[:120] or None
    dest    = request.args.get("dest")  # hotel destination (canonical Hebrew)
    # Attribution: `src` = traffic-source channel (e.g. 'esim' = the B2C compare
    # page); `campaign` = the specific post/video, forwarded from utm so we can see
    # which content drove the click. Accept any of campaign/utm_campaign/utm_source.
    src      = (request.args.get("src") or "").strip()[:40] or None
    campaign = (request.args.get("campaign") or request.args.get("utm_campaign")
                or request.args.get("utm_source") or "").strip()[:80] or None

    # Bot/crawler gate. robots.txt Disallows /go/ and the buttons are rel="sponsored
    # nofollow", but non-compliant crawlers ignore both and hammer the redirect (a
    # single crawler fired 1,295 junk /go hits across the /esim/<dest>/ SEO pages on
    # 2026-07-10). Following the redirect would register those junk clicks in the
    # affiliate networks (Impact/Everflow), inflating clicks + tanking conversion
    # ratios and risking an invalid-traffic flag. So: log the hit (is_bot=1, for
    # visibility) but STOP here — no affiliate redirect, no hotel attribution.
    bot = is_bot_ua(ua)
    try:
        log_affiliate_click(provider, plan_id=plan, country=country, ip_hash=ip_hash,
                            src=src, campaign=campaign, user_agent=ua, is_bot=bot,
                            db_path=_db_path())
    except Exception:
        app.logger.warning("affiliate click log failed", exc_info=True)

    if bot:
        return ("bot traffic not permitted on affiliate links", 403,
                {"X-Robots-Tag": "noindex, nofollow"})

    # Per-hotel attribution: a click from a hotel's guest portal earns the hotel.
    if hotel:
        log_guest_event(hotel, "click", provider=provider, plan_name=plan,
                        lang=request.args.get("lang"),
                        country=request.headers.get("Accept-Language", "")[:8] or None,
                        ip_hash=ip_hash, user_agent=request.headers.get("User-Agent"),
                        db_path=_db_path())

    # Saily: deep-link straight to the plan's checkout (with attribution) when we
    # have its token; otherwise fall through to the generic per-provider destination.
    # A hotel guest-portal click carries its property code as a Sub-ID (aff_sub) so
    # Saily/Tune attributes the conversion to that hotel (per Saily 2026-07-03).
    if provider == "saily":
        if plan:
            deep = _saily_checkout_url(plan, db_path=_db_path(), sub_id=hotel)
            if deep:
                return redirect(deep, 302)
        return redirect(_saily_attach_sub(
            _guest_provider_dest(provider, destination=dest), hotel), 302)
    # Maya: deep-link straight to the clicked plan's page (with attribution) when we
    # have a per-plan Impact TrackingLink for it; otherwise fall through to the generic
    # per-provider destination (config.json affiliate.maya.base_url).
    if provider == "maya" and plan:
        deep = _maya_deeplink_url(plan)
        if deep:
            return redirect(deep, 302)
    # Voye / Ubigi: deep-link to the viewed destination's country page (top
    # destinations only) with attribution; else fall through to the generic link.
    if provider == "voye" and dest:
        deep = _voye_deeplink_url(dest)
        if deep:
            return redirect(deep, 302)
    if provider == "ubigi" and dest:
        deep = _ubigi_deeplink_url(dest)
        if deep:
            return redirect(deep, 302)
    # Breeze: deep-link to the viewed destination's Shopify product page carrying the
    # UpPromote sca_ref (+ optional sca_source = hotel/src); unknown destinations fall
    # back to the configured homepage tracking link (both attributed).
    if provider == "breez":
        deep = _breez_deeplink_url(dest=dest, src=src, hotel=hotel)
        if deep:
            return redirect(deep, 302)
    # Bcengi: no per-destination pages exist on bcengi.com, so the destination is
    # attached to the single Impact tracking link as subId1 (+ subId2=src,
    # subId3=hotel) for per-destination attribution in Impact reporting.
    if provider == "bcengi":
        deep = _bcengi_subid_url(dest=dest, src=src, hotel=hotel)
        if deep:
            return redirect(deep, 302)
    # Orbit: no per-destination pages (orbitmobile.com is a SPA accordion), so the
    # destination rides on Impact SubIds (subId1=dest, subId2=src, subId3=hotel)
    # appended to the single tracking link for per-destination reporting. Falls
    # through to the generic config link when Orbit isn't configured.
    if provider == "orbit":
        deep = _orbit_subid_url(dest=dest, src=src, hotel=hotel)
        if deep:
            return redirect(deep, 302)
    # GigSky: Everflow network. Per-destination deep-link format is pending from
    # GigSky; until then the click lands on the configured Everflow tracking link
    # with destination/src/hotel as Sub-IDs (sub1/sub2/sub5). Falls through to the
    # generic gigsky.com destination while no tracking link is configured yet.
    if provider == "gigsky":
        deep = _gigsky_deeplink_url(dest=dest, src=src, hotel=hotel)
        if deep:
            return redirect(deep, 302)
    # GoMoWorld: per-destination deep-link via Puremium's url= override (the
    # macro-filled transaction_id keeps attribution intact) with the MOCA code
    # auto-applied; unknown destinations fall through to the generic homepage link.
    if provider == "gomoworld":
        deep = _gomoworld_deeplink_url(dest=dest, src=src, hotel=hotel)
        if deep:
            return redirect(deep, 302)
    return redirect(_guest_provider_dest(provider, destination=dest), 302)


@app.route("/api/affiliate/stats")
@require_api_key
@limiter.limit("60 per minute")
def api_affiliate_stats():
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
    except (ValueError, TypeError):
        days = 30
    stats = get_affiliate_stats(days=days, db_path=_db_path())
    return jsonify(stats)


@app.route("/api/affiliate/attribution")
@require_api_key
@limiter.limit("60 per minute")
def api_affiliate_attribution():
    """Click breakdown by traffic source + campaign — so we can see which channel
    (B2C eSIM vs hotels) and which post/video actually drove the clicks."""
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
    except (ValueError, TypeError):
        days = 30
    return jsonify(get_affiliate_attribution(days=days, db_path=_db_path()))


@app.route("/api/exchange-rates")
@limiter.limit("30 per minute")
def api_exchange_rates():
    from scraper import _get_usd_to_ils, _get_eur_to_ils, _get_gbp_to_ils
    return jsonify({"usd": _get_usd_to_ils(), "eur": _get_eur_to_ils(), "gbp": _get_gbp_to_ils()})


# ── Public B2C eSIM price comparison (consumer site, no auth) ────────────────
# A free, no-login alternative to the B2B dashboard: travelers pick a destination
# and see the cheapest live global-eSIM deals. Monetized through the same /go
# affiliate redirect (no hotel attribution). Global eSIM providers only — the
# include_local=False feed drops local Israeli tourist SIMs.


# ── Public B2C domestic mobile comparison (/mobile-deals, no auth) ───────────
# The domestic twin of the eSIM consumer feed: all rate-card plans of the 10
# Israeli carriers, server-normalized so the public page (and future static
# prerenders) never re-implement the data quirks: unlimited encodings
# (data_gb>=9999 / NULL), voice-only kosher rows, conditional multi-line
# prices, the sub-GB ₪/GB distortion, __info__ extraction and chip curation.
import re as _re_mobile

_MOBILE_CARRIERS = {
    'partner': 'פרטנר', 'pelephone': 'פלאפון', 'hotmobile': 'הוט מובייל',
    'cellcom': 'סלקום', 'mobile019': '019', 'xphone': 'XPhone',
    'wecom': 'We-Com', 'neptucom': 'Neptucom', 'golan': 'גולן טלקום',
    'rami_levy': 'רמי לוי תקשורת',
}

# Facet classifiers — Python ports of the dashboard's regexes. Keep in sync with
# mass-market-app/src/data/networkPriority.js (5G / priority) and the
# roaming-included matcher in DashboardPage.jsx baseFilteredPlans.
# All run on an UPPERCASED haystack (Hebrew is unaffected by upper()).
_RE_M_5G = _re_mobile.compile(r'\b5G\b|דור\s?5')
_RE_M_PRIORITY_HE = _re_mobile.compile(r'תיעדוף|מתועדף')
_RE_M_PRIORITY_KW = _re_mobile.compile(r'\b(?:MAX|ULTRA|PREMIUM|VIP|PRO|BOOST)\b')
_RE_M_INTL = _re_mobile.compile(r'חו"ל|חו״ל')
_RE_M_DATA_WORD = _re_mobile.compile(r'GB|גלישה', _re_mobile.IGNORECASE)
_RE_M_INCLUDED = _re_mobile.compile(r'כלול(?:ה|ים)?|כולל')


# ════════════════════════════════════════════════════════════════════════════
#  MOCA Guest Connect — hotels vertical (public guest portal + operator console)
#  Plan: Hotel/Hotel Plan.txt §2.3 / §5. Public routes are unauthenticated;
#  /api/hotels* admin routes require the API key or a super_admin JWT.
# ════════════════════════════════════════════════════════════════════════════


# ── Operator console (super_admin / API key) ───────────────────────────────


# ── Real-time scrape progress (SSE) ──────────────────────────────────────────
import threading as _threading_progress


# ── Social listening search terms per carrier ──────────────────────────────
# Social listening: search for public MENTIONS of carriers (not their own pages).
# he = Hebrew name to search, en = English name, tags = hashtags for TikTok/Instagram.


# ── Executive Summary generation ───────────────────────────────────────────


# ── Price Alerts Routes ────────────────────────────────────────────────────


# ── Watchlist (per-user starred plans) ────────────────────────────────────


# ── Saved Views (per-user filter presets) ─────────────────────────────────


# ── User activity tracking (super-admin dashboard) ─────────────────────────


# ── Plan annotations (team notes) ──────────────────────────────────────────


# ── Provider coupons (manually curated discount codes) ────────────────────


# ── Provider deal CRM (super-admin "סטטוס ספקים" dashboard) ─────────────────


# ── Push Notification Routes ───────────────────────────────────────────────

def _chat_user_key():
    """Rate-limit key for /api/chat — per authenticated user (falls back to IP)."""
    return _current_user_email() or get_remote_address()


def _chat_daily_limit():
    """Per-user daily cap on AI chat, to bound Anthropic spend by any single
    user (e.g. a client-workspace viewer). Tunable via
    config.json:chat_daily_limit_per_user (default 100, min 1). Counter is
    in-memory (storage_uri='memory://'), so it resets on a Flask restart."""
    try:
        n = int(load_config().get("chat_daily_limit_per_user", 100))
    except (TypeError, ValueError):
        n = 100
    return f"{max(1, n)} per day"


# ── Auth session (httpOnly cookie) ─────────────────────────────────────────


# ── User management (Supabase) ────────────────────────────────────────────


# ── Workspace management (super_admin only) ──────────────────────────────


# ── Workspace invite links ────────────────────────────────────────────────────


# ── Workspace branding (admin of own workspace) ──────────────────────────────


# ── Audit log (super_admin only) ─────────────────────────────────────────────


@app.route('/robots.txt')
@limiter.exempt
def robots_txt():
    """robots.txt for the API host (api.mocaintel.com). The frontend's robots.txt
    (Netlify) Disallows /go/, but the prerendered /esim/<dest>/ SEO pages link the
    deal buttons ABSOLUTELY to api.mocaintel.com/go/... — a different host, where
    (until 2026-07-11) the only robots.txt was Cloudflare's auto-generated one
    (User-agent: * → Allow: /). Result: a perfectly compliant crawler
    (Claude-SearchBot) followed ~1,295 /go links off the SEO pages on launch day.
    Cloudflare's managed robots.txt prepends its content-signal block to whatever
    the origin serves, so these directives ride along with it."""
    body = (
        "User-agent: *\n"
        "Disallow: /go/\n"          # affiliate redirects — clicks pollute attribution
        "Disallow: /api/\n"         # JSON endpoints — nothing indexable
        "Disallow: /banners/\n"     # screenshot PNGs for the internal dashboard
    )
    return body, 200, {"Content-Type": "text/plain; charset=utf-8",
                       "Cache-Control": "public, max-age=3600"}


@app.route('/api/ping')
@limiter.exempt
def api_ping():
    """Public, unauthenticated liveness probe for EXTERNAL uptime monitors
    (UptimeRobot / Better Stack / healthchecks.io). Returns 200 + minimal JSON
    with no DB hit and no auth, so it stays green exactly as long as Flask itself
    is serving requests through the tunnel. Rate-limit exempt so frequent polling
    never trips the global 200/min cap.

    NOTE for the monitor config: send header 'ngrok-skip-browser-warning: true'
    so ngrok's free-tier interstitial page doesn't mask the real response."""
    return jsonify({'ok': True, 'service': 'moca-api'}), 200


@app.route('/api/health')
@require_super_admin
@limiter.limit('30 per minute')
def api_health():
    """System health snapshot for super-admin. Returns operational vitals:
    last scrape / digest timestamps, DB size, workspace counts, scheduler jobs."""
    import os as _os
    from db import DB_PATH as _DB_PATH_CONST
    from datetime import datetime as _dt, timezone as _tz
    info = {'ok': True, 'generated_at': _dt.now(_tz.utc).isoformat()}

    db_path = _db_path() or _DB_PATH_CONST
    try:
        info['db_size_mb'] = round(_os.path.getsize(db_path) / (1024 * 1024), 2)
    except OSError:
        info['db_size_mb'] = None

    try:
        import sqlite3 as _sq3
        conn = _sq3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT MAX(scraped_at) FROM plans")
        info['last_scrape'] = (cur.fetchone() or [None])[0]
        counts = {}
        for pt, tbl in [('domestic', 'plans'), ('abroad', 'abroad_plans'),
                        ('global', 'global_plans'), ('content', 'content_plans')]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                counts[pt] = cur.fetchone()[0]
            except Exception:
                counts[pt] = None
        info['plans_count'] = counts
        cur.execute("SELECT MAX(created_at) FROM audit_log WHERE action = 'digest_sent'")
        info['last_digest_sent'] = (cur.fetchone() or [None])[0]
        cur.execute("SELECT MAX(created_at) FROM audit_log WHERE action = 'scrape_triggered'")
        info['last_manual_scrape'] = (cur.fetchone() or [None])[0]
        conn.close()
    except Exception as e:
        logger.warning(f"health: local db snapshot failed: {e}")

    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE active) FROM public.workspaces")
        total, active = cur.fetchone()
        info['workspaces_total']  = total
        info['workspaces_active'] = active
        conn.close()
    except Exception as e:
        logger.warning(f"health: supabase snapshot failed: {e}")

    try:
        info['scheduled_jobs'] = len(scheduler.get_jobs()) if 'scheduler' in globals() else None
    except Exception:
        info['scheduled_jobs'] = None

    return jsonify(info)


# ── Claude API usage tracking ──────────────────────────────────────────────


# ── Main ───────────────────────────────────────────────────────────────────



# ── sub-modules (api/) - extracted 2026-09, see scripts/split_monolith.py ──
# Imported here (after every helper above is defined) so they can late-bind
# `core.<name>` back to this module; their public + private names are re-exported
# so `app.<name>` keeps working for tests, scripts and the scheduler.
from api.esim import (  # noqa: E402,F401
    api_esim_destinations,
    api_esim_compare,
    api_esim_event,
    api_esim_push_subscribe,
    api_esim_push_unsubscribe,
    api_esim_analytics,
)
import api.esim as _esim_bp_mod  # noqa: E402
app.register_blueprint(_esim_bp_mod.bp)
from api.mobile import (  # noqa: E402,F401
    _RE_M_KOSHER,
    _RE_M_DATA_ONLY,
    _RE_M_CONDITIONAL,
    _RE_M_CHIP_PRIO,
    _mobile_has_roaming,
    _mobile_minutes_abroad,
    _assemble_mobile_plans,
    api_mobile_compare,
    api_mobile_event,
    api_mobile_push_subscribe,
    api_mobile_push_unsubscribe,
    _REM_KINDS,
    _REM_PLAN_TYPES,
    _REM_DAYS_CHOICES,
    _rem_parse_price,
    _rem_lookup_plan,
    api_mobile_reminders_subscribe,
    api_mobile_reminders_unsubscribe,
    run_mobile_reminders_job,
    api_mobile_reminders_run_now,
    api_mobile_reminders_subscribers,
)
import api.mobile as _mobile_bp_mod  # noqa: E402
app.register_blueprint(_mobile_bp_mod.bp)
from api.hotels import (  # noqa: E402,F401
    _guest_ip_hash,
    _qr_svg,
    api_guest_portal,
    _GUEST_CLIENT_EVENTS,
    api_guest_event,
    api_guest_qr,
    api_hotels_list,
    api_hotels_create,
    api_hotels_update,
    api_hotels_delete,
    api_hotels_analytics,
    api_hotels_leads,
    _notify_hotel_lead,
    api_hotels_lead,
)
import api.hotels as _hotels_bp_mod  # noqa: E402
app.register_blueprint(_hotels_bp_mod.bp)
from api.scrape import (  # noqa: E402,F401
    api_global_changes,
    api_scrape_global_now,
    api_abroad_changes,
    api_scrape_abroad_now,
    _scrape_progress,
    _scrape_lock,
    _scrape_signal,
    _scrape_emit,
    _scrape_start,
    _scrape_finish,
    api_scrape_progress_stream,
    api_scrape_progress_state,
    api_scrape_all_now,
    api_content_plans,
    api_content_changes,
    api_scrape_resellers_now,
    api_scrape_content_now,
    api_scrape_now,
)
import api.scrape as _scrape_bp_mod  # noqa: E402
app.register_blueprint(_scrape_bp_mod.bp)
from api.jobs import (  # noqa: E402,F401
    _price_direction,
    _HISTORY_CARRIER_NAMES,
    _HISTORY_TYPE_NAMES,
    CARRIER_DISPLAY,
    CARRIER_STORE_DISPLAY,
    CARRIER_SEARCH_TERMS,
    _normalize_post,
    generate_social_sentiment,
    _CATEGORY_LABELS,
    generate_executive_summary,
    scrape_news_job,
    RESELLER_SCRAPER_MODULES,
    scrape_resellers_job,
    run_morning_check_job,
    run_scraper_drift_job,
    api_scraper_drift_now,
    api_morning_check_now,
    api_executive_summary,
    api_executive_summary_refresh,
    api_social_sentiment,
    api_social_sentiment_refresh,
)
import api.jobs as _jobs_bp_mod  # noqa: E402
app.register_blueprint(_jobs_bp_mod.bp)
from api.banners import (  # noqa: E402,F401
    api_banners,
    api_store_banners,
    api_global_banners,
    api_archive,
    api_archive_date_range,
    _ARCHIVE_BANNER_ROOT,
    serve_archive_banner,
)
import api.banners as _banners_bp_mod  # noqa: E402
app.register_blueprint(_banners_bp_mod.bp)
from api.engagement import (  # noqa: E402,F401
    api_get_alerts,
    api_create_alert,
    api_delete_alert,
    api_get_watchlist,
    api_add_to_watchlist,
    api_remove_from_watchlist,
    api_get_saved_views,
    api_create_saved_view,
    api_delete_saved_view,
    _ACTIVITY_CLIENT_EVENTS,
    _track_user_action,
    api_track_activity,
    api_get_annotations,
    api_annotation_counts,
    api_add_annotation,
    api_update_annotation,
    api_delete_annotation,
    _COUPON_CARRIER_RE,
    _COUPON_CODE_RE,
    _validate_coupon_payload,
    api_get_coupons,
    api_get_all_coupons,
    api_create_coupon,
    api_update_coupon,
    api_delete_coupon,
    api_provider_deals,
)
import api.engagement as _engagement_bp_mod  # noqa: E402
app.register_blueprint(_engagement_bp_mod.bp)
from api.chat import (  # noqa: E402,F401
    api_chat,
)
import api.chat as _chat_bp_mod  # noqa: E402
app.register_blueprint(_chat_bp_mod.bp)
from api.account import (  # noqa: E402,F401
    api_vapid_public_key,
    api_auth_session,
    api_auth_logout,
    api_push_subscribe,
    api_push_unsubscribe,
    api_push_test,
    api_my_role,
    api_update_my_preferences,
    api_my_context,
    api_contact,
)
import api.account as _account_bp_mod  # noqa: E402
app.register_blueprint(_account_bp_mod.bp)
from api.workspaces import (  # noqa: E402,F401
    api_get_users,
    api_create_user,
    api_delete_user,
    api_update_user_role,
    api_set_user_password,
    api_list_workspaces,
    api_create_workspace,
    api_update_workspace,
    api_workspace_users,
    api_assign_workspace_user,
    api_unassign_workspace_user,
    api_create_invite,
    api_create_invite_bulk,
    api_get_invite,
    api_accept_invite,
    api_trigger_digest,
    api_workspace_branding,
    api_workspace_slack_test,
    api_audit_log,
)
import api.workspaces as _workspaces_bp_mod  # noqa: E402
app.register_blueprint(_workspaces_bp_mod.bp)
from api.history import (  # noqa: E402,F401
    api_history_changes,
    api_market_movers,
    api_history_price_series,
    api_history_price_series_batch,
    api_history_daily,
    api_maintenance_run_now,
    api_history_analyze,
)
import api.history as _history_bp_mod  # noqa: E402
app.register_blueprint(_history_bp_mod.bp)
from api.usage import (  # noqa: E402,F401
    _claude_budget_block,
    _ANTHROPIC_COST_CACHE,
    _ANTHROPIC_COST_TTL,
    _fetch_anthropic_cost_usd,
    api_usage_summary,
    api_usage_recent,
    api_activity_overview,
    api_activity_events,
    api_usage_set_budget,
    api_get_notification_settings,
    api_set_notification_settings,
    api_usage_official_cost,
)
import api.usage as _usage_bp_mod  # noqa: E402
app.register_blueprint(_usage_bp_mod.bp)


if __name__ == "__main__":
    from apscheduler.schedulers.background import BackgroundScheduler
    from change_detector import detect_changes
    from notifier import (format_message, format_abroad_message, format_global_message,
                          format_content_message, send_notification, send_whatsapp,
                          send_email_report, send_push_notifications, alert_missing_terms,
                          notify_esim_price_drops)
    from excel_report import build_excel_report
    import scraper

    def run_email_report_job():
        logger.info("Sending daily email report...")
        config = load_config()
        try:
            excel_bytes = build_excel_report()
            ok = send_email_report(excel_bytes, config)
            logger.info(f"Email report sent: {ok}")
        except Exception as e:
            logger.error(f"Email report job failed: {e}", exc_info=True)

    def check_price_alerts(new_plans, new_abroad, new_global, config, db_path=None):
        """After each scrape, evaluate all active price alerts and email users whose threshold is met.

        Cooldown: 24 hours — an alert that fired in the last 24 h is skipped to avoid spam.
        """
        from notifier import send_price_alert_email
        from datetime import datetime, timedelta

        all_alerts = get_price_alerts(active_only=True, db_path=db_path)
        if not all_alerts:
            return 0

        plan_buckets = {"domestic": new_plans, "abroad": new_abroad, "global": new_global}
        sent = 0
        now = datetime.now()

        for alert in all_alerts:
            # Cooldown: skip if triggered within last 24 h
            if alert.get("last_triggered"):
                try:
                    last = datetime.fromisoformat(alert["last_triggered"])
                    if now - last < timedelta(hours=24):
                        continue
                except ValueError:
                    pass

            tab = alert.get("tab", "domestic")
            plans_pool = plan_buckets.get(tab, [])

            # Filter by carrier
            carrier = alert.get("carrier")
            if carrier:
                plans_pool = [p for p in plans_pool if p.get("carrier") == carrier]

            # Filter by plan name (exact match first, then substring fallback for legacy alerts)
            pattern = (alert.get("plan_pattern") or "").strip()
            if pattern:
                exact = [p for p in plans_pool if p.get("plan_name") == pattern]
                plans_pool = exact if exact else [p for p in plans_pool if pattern in (p.get("plan_name") or "")]

            # Find plans below threshold
            threshold = float(alert.get("threshold", 0))
            matching = [p for p in plans_pool if p.get("price") is not None and float(p["price"]) < threshold]

            if not matching:
                continue

            ok = send_price_alert_email(alert["user_email"], alert, matching, config)
            if ok:
                update_alert_triggered(alert["id"], db_path=db_path)
                sent += 1
                logger.info(f"Price alert {alert['id']} fired → {alert['user_email']} ({len(matching)} plans)")
            else:
                logger.warning(f"Price alert email failed for alert {alert['id']}")

        return sent

    def run_scrape_job():
        logger.info("Starting scheduled scrape...")
        config = load_config()
        # Notification language (he/en) — a global operator setting that applies
        # to every push channel alike: Telegram / WhatsApp / Web Push / Slack.
        notify_lang = config.get("notify_lang", "he")

        # Helper: broadcast a notification to every workspace that has a Slack/Teams webhook
        # configured. The mvno_carrier of each workspace is treated as their "self" carrier
        # and changes for that carrier are filtered out (they don't want to see themselves).
        def _broadcast_workspace_slack(changes_list, plan_type_label, lang="he"):
            if not changes_list:
                return 0
            conn = None
            try:
                from notifier import send_slack, _carrier_name
                conn = _supabase_conn()
                cur = conn.cursor()
                cur.execute("SELECT name, mvno_carrier, brand_config FROM public.workspaces WHERE active IS NOT FALSE")
                rows = cur.fetchall()
            except Exception as exc:
                logger.warning(f"slack broadcast: workspace fetch failed: {exc}")
                return 0
            finally:
                # Always release the Supabase connection — the happy-path close()
                # used to be skipped on any execute/fetch error, slowly exhausting
                # the Postgres pool (this runs on every scheduled + manual scrape).
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
            sent = 0
            import json as _json
            for ws_name, mvno, bc in rows:
                bc_dict = bc if isinstance(bc, dict) else (_json.loads(bc) if isinstance(bc, str) else {})
                webhook = (bc_dict or {}).get('slack_webhook_url')
                if not webhook:
                    continue
                relevant = [c for c in changes_list if not mvno or c.get('carrier') != mvno]
                if not relevant:
                    continue
                header = (f"📡 MOCA — {plan_type_label} changes ({len(relevant)})" if lang == "en"
                          else f"📡 MOCA — שינויים ב{plan_type_label} ({len(relevant)})")
                lines = [header]
                for c in relevant[:15]:
                    ctype = c.get('change_type', '')
                    label = {'price_change': '💰', 'new_plan': '🆕', 'removed_plan': '❌'}.get(ctype, '•')
                    name = c.get('plan_name') or ''
                    carrier = _carrier_name(c.get('carrier') or '', lang)
                    if ctype == 'price_change':
                        lines.append(f"{label} {carrier} · {name}: ₪{c.get('old_val')} → ₪{c.get('new_val')}")
                    else:
                        lines.append(f"{label} {carrier} · {name}")
                if len(relevant) > 15:
                    extra = len(relevant) - 15
                    lines.append(f"_+{extra} more changes_" if lang == "en" else f"_+{extra} שינויים נוספים_")
                if send_slack("\n".join(lines), webhook):
                    sent += 1
            return sent

        try:
            from db import (save_plans, save_changes, save_abroad_plans, save_abroad_changes,
                            get_abroad_plans, filter_already_notified)

            # ── Domestic plans ─────────────────────────────────────────────
            new_plans = scraper.scrape_all()
            old_plans = get_plans()
            changes = detect_changes(old_plans, new_plans)
            save_plans(new_plans)
            # Drop changes already announced in the last 24h so users don't
            # receive repeat notifications (e.g. when the same removal sticks
            # around across consecutive scrapes).
            fresh = filter_already_notified(changes, 'changes')
            if fresh:
                save_changes(fresh)
                msg = format_message(fresh, notify_lang)
                ok_tg = send_notification(msg, config)
                logger.info(f"Telegram (domestic) sent: {ok_tg}")
                ok_wa = send_whatsapp(msg, config)
                logger.info(f"WhatsApp sent: {ok_wa}")
                n_push = send_push_notifications(fresh, config, lang=notify_lang)
                logger.info(f"Web Push sent: {n_push}")
                n_slack = _broadcast_workspace_slack(
                    fresh, 'cellular plans' if notify_lang == 'en' else 'חבילות סלולר', notify_lang)
                logger.info(f"Slack workspaces notified (domestic): {n_slack}")
            else:
                if changes:
                    logger.info(f"Domestic: {len(changes)} change(s) detected but already notified within 24h — skipping.")
                else:
                    logger.info("No domestic changes.")

            # Safety net: alert the operator if a newly-added domestic plan has no terms link.
            _n_miss = alert_missing_terms(fresh, new_plans, 'plans', config)
            if _n_miss:
                logger.warning(f"Terms coverage: {_n_miss} new domestic plan(s) without 'עיקרי התוכנית' — alerted.")

            # /mobile-deals consumer price-drop push (event-driven off the fresh list).
            try:
                from notifier import notify_mobile_price_drops
                n_mob = notify_mobile_price_drops(fresh, config)
                if n_mob:
                    logger.info(f"Mobile-deals price-drop push sent: {n_mob}")
            except Exception as e:
                logger.warning(f"mobile price-drop push failed: {e}")

            # ── Abroad plans ───────────────────────────────────────────────
            new_abroad = scraper.scrape_all_abroad()
            old_abroad = get_abroad_plans()
            abroad_changes = detect_changes(old_abroad, new_abroad)
            save_abroad_plans(new_abroad)
            fresh_abroad = filter_already_notified(abroad_changes, 'abroad_changes')
            if fresh_abroad:
                save_abroad_changes(fresh_abroad)
                abroad_msg = format_abroad_message(fresh_abroad, notify_lang)
                ok_tg_abroad = send_notification(abroad_msg, config)
                ok_wa_abroad = send_whatsapp(abroad_msg, config)
                _broadcast_workspace_slack(
                    fresh_abroad, 'roaming plans' if notify_lang == 'en' else 'חבילות חו"ל', notify_lang)
                logger.info(f"Telegram (abroad) sent: {ok_tg_abroad}, WhatsApp: {ok_wa_abroad}, changes: {len(fresh_abroad)}")
            else:
                if abroad_changes:
                    logger.info(f"Abroad: {len(abroad_changes)} change(s) detected but already notified within 24h — skipping.")
                else:
                    logger.info("No abroad changes.")

            # Safety net: alert the operator if a newly-added roaming plan has no terms link.
            _n_miss_ab = alert_missing_terms(fresh_abroad, new_abroad, 'abroad_plans', config)
            if _n_miss_ab:
                logger.warning(f"Terms coverage: {_n_miss_ab} new roaming plan(s) without 'עיקרי התוכנית' — alerted.")

            # ── Global eSIM ────────────────────────────────────────────────
            from db import save_global_plans, save_global_changes
            old_global = get_global_plans()
            new_global = scraper.scrape_all_global()
            existing_global_ch = get_global_changes(limit=1)
            if not existing_global_ch:
                seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                         "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                        for p in new_global]
                save_global_changes(seed)
                global_changes = seed
            else:
                global_changes = detect_changes(old_global, new_global, per_group_extras=True)
                # Drop global new/removed churn (per-country scrape flapping); keep price/extras/details.
                global_changes = [c for c in global_changes if c["change_type"] not in ("new_plan", "removed_plan")]
            save_global_plans(new_global)
            _purge_stale_global(new_global, config)
            try:
                notify_esim_price_drops(config)
            except Exception as e:
                logger.warning(f"esim price-drop push failed: {e}")
            fresh_global = filter_already_notified(global_changes, 'global_changes')
            if fresh_global:
                if existing_global_ch:
                    # Seed already saved above; only persist non-seed fresh changes
                    save_global_changes(fresh_global)
                global_msg = format_global_message(fresh_global, notify_lang)
                ok_tg_global = send_notification(global_msg, config)
                ok_wa_global = send_whatsapp(global_msg, config)
                _broadcast_workspace_slack(
                    fresh_global, 'global eSIM plans' if notify_lang == 'en' else 'חבילות גלובל (eSIM)', notify_lang)
                logger.info(f"Telegram (global) sent: {ok_tg_global}, WhatsApp: {ok_wa_global}, changes: {len(fresh_global)}")
            else:
                if global_changes:
                    logger.info(f"Global: {len(global_changes)} change(s) detected but already notified within 24h — skipping.")
                else:
                    logger.info("No global changes.")

            # ── Content services ───────────────────────────────────────────
            from db import save_content_plans, save_content_changes
            from change_detector import detect_content_changes
            old_content = get_content_plans()
            new_content = scraper.scrape_all_content()
            content_changes = detect_content_changes(old_content, new_content)
            save_content_plans(new_content)
            fresh_content = filter_already_notified(content_changes, 'content_changes', key_field='service')
            if fresh_content:
                save_content_changes(fresh_content)
                content_msg = format_content_message(fresh_content, notify_lang)
                ok_tg_content = send_notification(content_msg, config)
                ok_wa_content = send_whatsapp(content_msg, config)
                logger.info(f"Telegram (content) sent: {ok_tg_content}, WhatsApp: {ok_wa_content}, changes: {len(fresh_content)}")
            else:
                if content_changes:
                    logger.info(f"Content: {len(content_changes)} change(s) detected but already notified within 24h — skipping.")
                else:
                    logger.info("No content changes.")

            _invalidate_plan_cache()
            logger.info(f"Done. {len(new_plans)} domestic, {len(new_abroad)} abroad, "
                        f"{len(new_global)} global, {len(new_content)} content plans.")

            # ── Archive snapshots (only saved when content changed) ────────────
            try:
                arc.archive_domestic_plans(new_plans)
                arc.archive_abroad_plans(new_abroad)
                arc.archive_global_plans(new_global)
                arc.archive_content_plans(new_content)
                logger.info("Archive snapshots updated.")
            except Exception as ae:
                logger.error(f"Archive snapshot failed: {ae}", exc_info=True)

            # ── Banners (homepage + e-store screenshots) ──────────────────────
            # Banners ride along with every scheduled scrape so they refresh at
            # each schedule_times slot (07:30 / 17:00). The previous standalone
            # 08:00 job was removed; /api/scrape-all-now still captures banners.
            try:
                from scraper import (scrape_carrier_banners, scrape_carrier_store_banners,
                                      scrape_global_provider_banners, GLOBAL_BANNER_URLS)
                banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
                home_results   = scrape_carrier_banners(banners_dir)
                store_results  = scrape_carrier_store_banners(banners_dir)
                global_results = scrape_global_provider_banners(banners_dir)
                ok_home   = sum(1 for r in home_results   if r["success"])
                ok_store  = sum(1 for r in store_results  if r["success"])
                ok_global = sum(1 for r in global_results if r["success"])
                logger.info("Banner screenshots: %d/%d homepage, %d/%d e-store, %d/%d global",
                            ok_home, len(home_results), ok_store, len(store_results),
                            ok_global, len(global_results))
                arc.archive_all_banners(banners_dir,
                                        list(CARRIER_DISPLAY.keys()),
                                        list(CARRIER_STORE_DISPLAY.keys()))
                arc.archive_all_global_banners(banners_dir, list(GLOBAL_BANNER_URLS.keys()))
            except Exception as be:
                logger.error(f"Banner capture failed in scheduled scrape: {be}", exc_info=True)

            # ── Price alerts ───────────────────────────────────────────────────
            try:
                n_sent = check_price_alerts(new_plans, new_abroad, new_global, config, _db_path())
                logger.info(f"Price alert emails sent: {n_sent}")
            except Exception as ae:
                logger.error(f"Price alert check failed: {ae}", exc_info=True)

        except Exception as e:
            logger.error(f"Scrape job failed: {e}", exc_info=True)

    def check_trial_expiry_job():
        """Daily 00:05 — auto-suspend workspaces past their trial end date."""
        try:
            conn = _supabase_conn()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                UPDATE public.workspaces
                SET active = FALSE
                WHERE trial_ends_at IS NOT NULL
                  AND trial_ends_at < NOW()
                  AND active = TRUE
                RETURNING name
            """)
            expired = [r[0] for r in cur.fetchall()]
            conn.close()
            if expired:
                logger.info(f"Auto-suspended {len(expired)} expired trial workspace(s): {expired}")
                for ws_name in expired:
                    log_audit('trial_expired', workspace_id=None, details=ws_name, db_path=_db_path())
        except Exception as e:
            logger.error(f"Trial expiry check failed: {e}", exc_info=True)

    def weekly_digest_job():
        """Every Sunday 08:30 — send 7-day plan-changes digest to all workspace users."""
        from notifier import send_weekly_digest as _send_digest
        from db import get_history_changes as _ghc
        from datetime import datetime as _dt, timedelta as _td
        _cfg = load_config()
        _from = (_dt.now() - _td(days=7)).strftime('%Y-%m-%d')
        try:
            conn = _supabase_conn()
            cur = conn.cursor()
            # Fetch all workspaces
            cur.execute("""
                SELECT id, name, mvno_carrier,
                       hide_self_carrier,
                       COALESCE(visible_carriers, '[]'::jsonb),
                       COALESCE(brand_config, '{}'::jsonb),
                       COALESCE(digest_frequency, 'weekly')
                FROM public.workspaces WHERE active = TRUE
            """)
            workspaces = cur.fetchall()
            today_day = _dt.now().day
            is_first_sunday = today_day <= 7  # monthly digests run only on the 1st Sunday
            for ws_id, ws_name, mvno_carrier, hide_self, vc_raw, bc_raw, digest_freq in workspaces:
                try:
                    if digest_freq == 'off':
                        continue
                    if digest_freq == 'monthly' and not is_first_sunday:
                        continue
                    visible_carriers = json.loads(vc_raw) if isinstance(vc_raw, str) else (list(vc_raw) if vc_raw else [])
                    brand_config = json.loads(bc_raw) if isinstance(bc_raw, str) else (dict(bc_raw) if bc_raw else {})
                    # Get all user emails for this workspace
                    cur.execute("""
                        SELECT u.email FROM auth.users u
                        JOIN public.user_roles r ON r.user_id = u.id
                        WHERE r.workspace_id = %s AND COALESCE(r.digest_opt_out, FALSE) = FALSE
                    """, (ws_id,))
                    emails = [r[0] for r in cur.fetchall() if r[0]]
                    if not emails:
                        continue
                    # Collect changes from last 7 days across plan types
                    all_changes = []
                    for ptype in ('domestic', 'abroad', 'global'):
                        ch = _ghc('', ptype, _from, '', db_path=_db_path())
                        # Apply same carrier scoping as the dashboard
                        if visible_carriers:
                            ch = [c for c in ch if c.get('carrier') in visible_carriers]
                        elif hide_self and mvno_carrier:
                            ch = [c for c in ch if c.get('carrier') != mvno_carrier]
                        all_changes.extend(ch)
                    if not all_changes:
                        continue
                    _send_digest(emails, ws_name, all_changes, _cfg, brand_config=brand_config)
                    logger.info(f"Weekly digest sent to {len(emails)} users in workspace {ws_name!r}")
                except Exception as _we:
                    logger.error(f"Weekly digest failed for workspace {ws_name!r}: {_we}", exc_info=True)
            conn.close()
        except Exception as e:
            logger.error(f"Weekly digest job failed: {e}", exc_info=True)

    # ── Supabase schema migrations ────────────────────────────────────────────
    try:
        _mc = _supabase_conn(); _mc.autocommit = True; _mcu = _mc.cursor()
        _mcu.execute("ALTER TABLE public.workspaces ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ")
        _mcu.execute("ALTER TABLE public.workspaces ADD COLUMN IF NOT EXISTS visible_carriers JSONB DEFAULT '[]'")
        _mcu.execute("ALTER TABLE public.workspaces ADD COLUMN IF NOT EXISTS digest_frequency TEXT DEFAULT 'weekly'")
        _mcu.execute("ALTER TABLE public.user_roles ADD COLUMN IF NOT EXISTS digest_opt_out BOOLEAN DEFAULT FALSE")
        _mc.close()
        logger.info("Supabase migration: trial_ends_at + visible_carriers + digest prefs columns ensured")
    except Exception as _me:
        logger.warning(f"Supabase migration skipped: {_me}")

    _ensure_vapid_keys(CONFIG_PATH)
    init_db()
    config = load_config()
    # Generous misfire window so APScheduler doesn't silently drop a cron when
    # the host is briefly throttled (Win11 modern standby, IO storms, etc).
    # coalesce=True collapses any backlog into a single late run.
    _job_defaults = {"misfire_grace_time": 3600, "coalesce": True}

    def _run_scrape_job_guarded():
        # Claim the shared single-scrape slot so a scheduled run never overlaps a
        # manual /api/scrape-all-now (or vice versa) — two Playwright passes on the
        # one box double the load and can interleave DB writes into spurious change
        # events. APScheduler's max_instances already blocks scheduled-vs-scheduled.
        if not _scrape_start():
            logger.warning("scheduled scrape skipped — a scrape is already running")
            return
        try:
            run_scrape_job()
        finally:
            _scrape_finish()

    scheduler = BackgroundScheduler()
    for time_str in config.get("schedule_times", ["10:00", "16:00"]):
        hour, minute = map(int, time_str.split(":"))
        scheduler.add_job(_run_scrape_job_guarded, "cron", hour=hour, minute=minute, **_job_defaults)
    report_time = config.get("email_report_time", "09:00")
    rh, rm = map(int, report_time.split(":"))
    scheduler.add_job(run_email_report_job, "cron", hour=rh, minute=rm, **_job_defaults)
    scheduler.add_job(generate_executive_summary, "cron", hour=8, minute=5, id="executive_summary", **_job_defaults)
    scheduler.add_job(scrape_news_job, "cron", hour=8, minute=10, id="news_scrape", **_job_defaults)
    scheduler.add_job(scrape_resellers_job, "cron", hour=8, minute=15, id="resellers_scrape", **_job_defaults)
    # Morning changes digest — daily heartbeat summarizing the last day's
    # new/removed/changed plans + scraper-freshness warnings (see run_morning_check_job)
    mc_time = config.get("morning_check_time", "08:20")
    mch, mcm = map(int, mc_time.split(":"))
    scheduler.add_job(run_morning_check_job, "cron", hour=mch, minute=mcm, id="morning_check", **_job_defaults)
    # Social sentiment: every 3 days at 08:00 — use interval trigger with next 08:00 as start
    from datetime import datetime as _dt, timedelta as _td
    _now = _dt.now()
    _next_8 = _now.replace(hour=8, minute=0, second=0, microsecond=0)
    if _next_8 <= _now:
        _next_8 += _td(days=1)
    scheduler.add_job(generate_social_sentiment, "interval", days=3,
                      start_date=_next_8, id="social_sentiment", **_job_defaults)
    scheduler.add_job(weekly_digest_job, "cron", day_of_week="sun", hour=8, minute=30,
                      id="weekly_digest", **_job_defaults)
    scheduler.add_job(check_trial_expiry_job, "cron", hour=0, minute=5, id="trial_expiry", **_job_defaults)
    # DB maintenance (maintenance.py): daily price aggregates after each scrape window,
    # weekly change-log retention (Sun 03:00; VACUUM on the first Sunday of the month)
    import maintenance as _maint
    for _h, _m in ((8, 50), (18, 30)):
        scheduler.add_job(lambda: _maint.run_daily(load_config()), "cron", hour=_h, minute=_m,
                          id=f"price_history_daily_{_h}", **_job_defaults)
    scheduler.add_job(lambda: _maint.run_weekly(load_config()), "cron", day_of_week="sun", hour=3, minute=0,
                      id="db_maintenance_weekly", **_job_defaults)
    # Weekly scraper drift probe (fixture URL sets re-fetched live) - see run_scraper_drift_job
    scheduler.add_job(run_scraper_drift_job, "cron", day_of_week="sun", hour=6, minute=30,
                      id="scraper_drift", **_job_defaults)
    # /mobile-deals consumer reminders (email/WhatsApp) — after the 07:30 scrape
    # so better-deal checks run against fresh prices
    scheduler.add_job(run_mobile_reminders_job, "cron", hour=9, minute=15,
                      id="mobile_reminders", **_job_defaults)
    if config.get("booking_ical_url"):
        try:
            from booking_notifier import check_new_bookings
            _bk_min = int(config.get("booking_check_minutes", 5))
            scheduler.add_job(check_new_bookings, "interval", minutes=_bk_min,
                              id="booking_whatsapp", **_job_defaults)
            logger.info(f"Booking notifier: polling calendar iCal every {_bk_min} min")
        except Exception as _be:
            logger.warning(f"Booking notifier not started: {_be}")
    scheduler.start()
    logger.info("Flask starting → http://0.0.0.0:5000")
    try:
        host = os.environ.get("FLASK_HOST", "127.0.0.1")  # Use 0.0.0.0 only for ngrok/LAN
        app.run(host=host, port=5000, debug=False, use_reloader=False)
    finally:
        scheduler.shutdown()
