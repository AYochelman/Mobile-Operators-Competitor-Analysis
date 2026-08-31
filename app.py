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
        logger.error(f"_get_user_context({email!r}) failed: {e}")
        return {"role": "viewer", "workspace_id": None, "workspace": None, "digest_opt_out": False}


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
    """Get a psycopg2 connection to Supabase DB using credentials from config."""
    import psycopg2
    cfg = load_config()
    return psycopg2.connect(
        host=cfg.get("supabase_db_host", os.environ.get("SUPABASE_DB_HOST", "")),
        port=5432, dbname='postgres', user='postgres',
        password=cfg.get("supabase_db_password", os.environ.get("SUPABASE_DB_PASSWORD", "")),
        sslmode='require'
    )


def _db_path():
    """Return test DB path when running under pytest, else default (None = use DB_PATH in db.py)."""
    return app.config.get("TEST_DB_PATH") or None


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

@app.route("/api/esim/destinations")
@limiter.limit("60 per minute")
def api_esim_destinations():
    """Destinations that currently have live global-eSIM deals, for the consumer
    destination picker: canonical Hebrew name + deal count + cheapest price."""
    dests = get_esim_destinations(db_path=_db_path())
    return _public_cache(jsonify(dests), 600)


@app.route("/api/esim/compare")
@limiter.limit("60 per minute")
def api_esim_compare():
    """Public consumer feed: cheapest live global-eSIM deals for a destination.
    Same shape as the guest portal minus hotel branding, global providers only."""
    destination = (request.args.get("destination") or ISRAEL_HE).strip()
    deals, providers, updated_at = _assemble_guest_deals(
        db_path=_db_path(), destination=destination, include_local=False)
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
    for c in get_active_coupons(db_path=_db_path()):
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
    return _public_cache(jsonify(payload), 300)


@app.route("/api/esim/event", methods=["POST"])
@limiter.limit("240 per minute")
def api_esim_event():
    """Anonymous traffic beacon from the public B2C eSIM page (page_view /
    destination_pick). No auth, no PII — ip hashed, sid is a random session token.
    Deal clicks are logged separately by the /go redirect (src='esim')."""
    body = request.get_json(silent=True) or {}
    etype = (body.get("type") or "").strip()
    if etype not in ("page_view", "destination_pick", "pwa_install"):
        return jsonify({"ok": False}), 400
    log_esim_event(
        etype,
        sid=body.get("sid"),
        destination=(body.get("destination") or None),
        src=(body.get("src") or None),
        campaign=(body.get("campaign") or None),
        lang=(body.get("lang") or None),
        referrer=(body.get("referrer") or None),
        ip_hash=_guest_ip_hash(),
        db_path=_db_path(),
    )
    return jsonify({"ok": True})


@app.route("/api/esim/push/subscribe", methods=["POST"])
@limiter.limit("10 per minute")
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
    live = {d["destination"] for d in get_esim_destinations(db_path=_db_path())}
    if destination not in live:
        return jsonify({"error": "unknown destination"}), 400
    from db import get_esim_alert_floor
    baseline = get_esim_alert_floor(destination, db_path=_db_path())
    save_esim_push_subscription(endpoint, p256dh, auth, destination, lang=lang,
                                baseline_price=baseline, db_path=_db_path())
    log_esim_event("push_subscribe", sid=body.get("sid"), destination=destination,
                   src=(body.get("src") or None), campaign=(body.get("campaign") or None),
                   lang=lang, ip_hash=_guest_ip_hash(), db_path=_db_path())
    return jsonify({"status": "subscribed", "baseline": baseline}), 201


@app.route("/api/esim/push/unsubscribe", methods=["DELETE", "POST"])
@limiter.limit("10 per minute")
def api_esim_push_unsubscribe():
    """Public: remove a B2C price-drop subscription by its push endpoint."""
    from db import delete_esim_push_subscription
    body = request.get_json(silent=True) or {}
    endpoint = (body.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400
    deleted = delete_esim_push_subscription(endpoint, db_path=_db_path())
    return jsonify({"status": "unsubscribed", "deleted": deleted}), 200


@app.route("/api/esim/analytics")
@require_api_key_or_super_admin
@limiter.limit("60 per minute")
def api_esim_analytics():
    """B2C eSIM traffic dashboard: views / sessions / picks / clicks funnel by day,
    destination, source and campaign. Admin-only (dev key or super_admin JWT)."""
    try:
        days = max(0, min(int(request.args.get("days", 30)), 365))
    except (ValueError, TypeError):
        days = 30
    return jsonify(get_esim_analytics(days=days, db_path=_db_path()))


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
_RE_M_KOSHER = _re_mobile.compile(r'כשר|נטפרי|ועד הרבנים|KOSHER')
_RE_M_DATA_ONLY = _re_mobile.compile(r'DATA\s*ONLY|SIM\s*DATA|גלישה בלבד')
_RE_M_CONDITIONAL = _re_mobile.compile(r'קווים|בהצטרפות|כ\.אשראי|\bלקו\b')
_RE_M_CHIP_PRIO = _re_mobile.compile(
    r'חו"ל|חו״ל|לחו|אפליקציות|eSIM|תיעדוף|מתועדף|מחיר קבוע|ללא עליית', _re_mobile.IGNORECASE)


def _mobile_has_roaming(extras):
    """Included-roaming detector: a quantified data note ("1GB גלישה בחו\"ל") OR a
    qualitative "חו\"ל כלול" tag. Pay-per-use routes deliberately don't match."""
    for e in extras or []:
        if not _RE_M_INTL.search(e):
            continue
        if (any(ch.isdigit() for ch in e) and _RE_M_DATA_WORD.search(e)) or _RE_M_INCLUDED.search(e):
            return True
    return False


def _mobile_minutes_abroad(extras):
    for e in extras or []:
        if ('דק' in e or 'שיחות' in e) and ('לחו"ל' in e or 'לחו״ל' in e):
            return True
    return False


def _assemble_mobile_plans(db_path):
    """Normalized consumer feed for /mobile-deals (see section comment)."""
    rows = get_plans(db_path=db_path)
    plans, updated = [], None
    for r in rows:
        extras = r.get('extras') or []
        info, vis = None, []
        for e in extras:
            if isinstance(e, str) and e.startswith('__info__|'):
                info = e.split('|', 1)[1]
            else:
                vis.append(e)
        hay = ((r.get('plan_name') or '') + ' ' + ' '.join(vis)).upper()
        five_g = bool(_RE_M_5G.search(hay))
        priority = five_g and bool(_RE_M_PRIORITY_HE.search(hay) or _RE_M_PRIORITY_KW.search(hay))
        kosher = bool(_RE_M_KOSHER.search(hay))
        gb = r.get('data_gb')
        unlimited = voice_only = False
        if gb is not None and gb >= 9999:
            # wecom encodes "גלישה חופשית" as 10000GB — normalize to unlimited.
            unlimited, gb = True, None
        elif gb is None:
            # NULL is "unlimited" in the dashboard convention, but the only live
            # NULL rows are voice-only kosher plans — don't sell them as unlimited.
            if kosher or 'ללא גלישה' in hay:
                voice_only = True
            else:
                unlimited = True
        price = r.get('price')
        ppgb = None
        if not unlimited and not voice_only and gb and gb >= 1 and price:
            ppgb = round(price / gb, 2)
        cond_hay = (r.get('plan_name') or '') + ' ' + ' '.join(vis) + ' ' + (info or '')
        conditional = bool(_RE_M_CONDITIONAL.search(cond_hay))
        # Chip guard: a bare pay-per-use route mention (e.g. Pelephone's
        # 'מסלול חו"ל Travel' — intl wording with no quantity and no
        # included-tag) reads as an included-roaming benefit on a consumer
        # card. Keep it in the full extras/details, drop it from chips.
        def _chip_ok(e):
            if _RE_M_INTL.search(e) and not any(ch.isdigit() for ch in e) \
                    and not _RE_M_INCLUDED.search(e):
                return False
            return True
        short = [e for e in vis if len(e) <= 60 and _chip_ok(e)]
        chips = ([e for e in short if _RE_M_CHIP_PRIO.search(e)]
                 + [e for e in short if not _RE_M_CHIP_PRIO.search(e)])[:4]
        sa = r.get('scraped_at')
        if sa and (updated is None or sa > updated):
            updated = sa
        plans.append({
            'id': f"{r['carrier']}|{r['plan_name']}",
            'carrier': r['carrier'], 'plan_name': r['plan_name'],
            'price': price, 'promo_price': r.get('promo_price'),
            'promo_months': r.get('promo_months'),
            'data_gb': gb, 'unlimited': unlimited, 'voice_only': voice_only,
            'minutes': r.get('minutes'),
            'chips': chips, 'extras': vis, 'info': info,
            'terms_url': r.get('url'),
            'price_conditional': conditional,
            'price_per_gb': ppgb,
            'facets': {
                'five_g': five_g, 'five_g_priority': priority,
                'roaming': _mobile_has_roaming(vis),
                'minutes_abroad': _mobile_minutes_abroad(vis),
                'esim': 'ESIM' in hay,
                'kosher': kosher,
                'data_only': bool(_RE_M_DATA_ONLY.search(hay)),
                'free_apps': any('אפליקציות' in e for e in vis),
            },
            'scraped_at': sa,
        })
    carriers = []
    for cid, name in _MOBILE_CARRIERS.items():
        mine = [p for p in plans if p['carrier'] == cid]
        if not mine:
            continue
        prices = [p['price'] for p in mine if p['price']]
        carriers.append({'id': cid, 'name': name, 'count': len(mine),
                         'min_price': min(prices) if prices else None})
    return {'plans': plans, 'carriers': carriers,
            'updated_at': updated or datetime.now(timezone.utc).isoformat()}


@app.route("/api/mobile/compare")
@limiter.limit("60 per minute")
def api_mobile_compare():
    """Public consumer feed for /mobile-deals — normalized domestic plans +
    per-carrier summary. Roaming / content tabs reuse the existing public
    /api/abroad-plans and /api/content-plans as-is."""
    payload = _cached_plans('mobile_compare', lambda: _assemble_mobile_plans(_db_path()))
    return _public_cache(jsonify(payload), 600)


@app.route("/api/mobile/event", methods=["POST"])
@limiter.limit("240 per minute")
def api_mobile_event():
    """Anonymous traffic beacon from the public /mobile-deals page. No auth, no
    PII — ip hashed, sid is a random session token. Kept separate from
    /api/esim/event so the eSIM analytics funnel stays vertical-clean."""
    body = request.get_json(silent=True) or {}
    etype = (body.get("type") or "").strip()
    if etype not in ("page_view", "tab_pick", "carrier_click"):
        return jsonify({"ok": False}), 400
    from db import log_mobile_event
    log_mobile_event(
        etype,
        sid=body.get("sid"),
        tab=(body.get("tab") or None),
        carrier=(body.get("carrier") or None),
        src=(body.get("src") or None),
        campaign=(body.get("campaign") or None),
        lang=(body.get("lang") or None),
        referrer=(body.get("referrer") or None),
        ip_hash=_guest_ip_hash(),
        db_path=_db_path(),
    )
    return jsonify({"ok": True})


@app.route("/api/mobile/push/subscribe", methods=["POST"])
@limiter.limit("10 per minute")
def api_mobile_push_subscribe():
    """Public (no auth): domestic price-drop alert from /mobile-deals.
    Body: { subscription: {endpoint, keys:{p256dh,auth}}, carrier, lang }.
    carrier is a domestic id or 'all'. One alert per device — re-subscribing
    moves it. Event-driven off the domestic change log (notify_mobile_price_drops),
    so unlike the eSIM flow there is no price baseline."""
    from db import save_mobile_push_subscription, log_mobile_event
    body = request.get_json(silent=True) or {}
    sub = body.get("subscription") or {}
    endpoint = (sub.get("endpoint") or "").strip()
    keys = sub.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    carrier = (body.get("carrier") or "all").strip() or "all"
    lang = body.get("lang") if body.get("lang") in ("he", "en") else "he"
    if not all([endpoint, p256dh, auth]):
        return jsonify({"error": "missing fields"}), 400
    if not endpoint.startswith("https://"):
        return jsonify({"error": "bad endpoint"}), 400
    if carrier != "all" and carrier not in _MOBILE_CARRIERS:
        return jsonify({"error": "unknown carrier"}), 400
    save_mobile_push_subscription(endpoint, p256dh, auth, carrier=carrier, lang=lang,
                                  db_path=_db_path())
    log_mobile_event("push_subscribe", sid=body.get("sid"), carrier=carrier,
                     src=(body.get("src") or None), campaign=(body.get("campaign") or None),
                     lang=lang, ip_hash=_guest_ip_hash(), db_path=_db_path())
    return jsonify({"status": "subscribed"}), 201


@app.route("/api/mobile/push/unsubscribe", methods=["DELETE", "POST"])
@limiter.limit("10 per minute")
def api_mobile_push_unsubscribe():
    """Public: remove a /mobile-deals price-drop subscription by its endpoint."""
    from db import delete_mobile_push_subscription
    body = request.get_json(silent=True) or {}
    endpoint = (body.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400
    deleted = delete_mobile_push_subscription(endpoint, db_path=_db_path())
    return jsonify({"status": "unsubscribed", "deleted": deleted}), 200


_REM_KINDS = ("better_deal", "plan_end")
_REM_PLAN_TYPES = ("domestic", "roaming", "content")
_REM_DAYS_CHOICES = (3, 7, 14, 30)


def _rem_parse_price(val):
    """First ₪ amount inside a free-text price (content_plans prices are strings
    like '19.90 ₪ לחודש'). None when there is no usable number."""
    m = _re_mobile.search(r"\d+(?:\.\d+)?", str(val or ""))
    try:
        p = float(m.group()) if m else None
        return p if p is not None and 0 < p <= 1000 else None
    except (TypeError, ValueError):
        return None


def _rem_lookup_plan(plan_type, carrier, plan_name):
    """Snapshot dict for the signed-up plan, validated against the live data of
    its type — or None when no such plan exists. For 'content', plan_name is the
    service name (content rows have no plan_name of their own)."""
    if plan_type == "roaming":
        from db import get_abroad_plans
        row = next((p for p in get_abroad_plans(carrier=carrier, db_path=_db_path())
                    if p["plan_name"] == plan_name), None)
        if row is None:
            return None
        # Abroad NULL data_gb = a voice-minutes package (no data), NOT
        # unlimited — the matchers skip such rows on both sides.
        return {"price": row.get("price"), "data_gb": row.get("data_gb"),
                "unlimited": False, "days": row.get("days")}
    if plan_type == "content":
        from db import get_content_plans
        row = next((p for p in get_content_plans(service=plan_name, carrier=carrier,
                                                 db_path=_db_path())), None)
        if row is None:
            return None
        return {"price": _rem_parse_price(row.get("price")), "data_gb": None,
                "unlimited": False, "days": None}
    feed = _cached_plans('mobile_compare', lambda: _assemble_mobile_plans(_db_path()))
    plan = next((p for p in feed.get("plans", [])
                 if p["carrier"] == carrier and p["plan_name"] == plan_name), None)
    if plan is None:
        return None
    return {"price": plan.get("price"), "data_gb": plan.get("data_gb"),
            "unlimited": plan.get("unlimited"), "days": None}


@app.route("/api/mobile/reminders", methods=["POST"])
@limiter.limit("6 per minute")
def api_mobile_reminders_subscribe():
    """Public (no auth): /mobile-deals email/WhatsApp reminder signup.
    Body: { email?, phone?, kinds: ['better_deal'|'plan_end'...], plan_type?
    ('domestic'|'roaming'|'content', default domestic), carrier, plan_name,
    end_date?, remind_days_before?, include_offers?, lang, sid? }. For
    plan_type='content', plan_name carries the service name. At least one
    contact field is required; the plan must exist on the live data of its type
    (price/data are snapshotted server-side, never trusted from the client).
    Returns the shared unsubscribe token."""
    from db import save_mobile_reminders, log_mobile_event
    body = request.get_json(silent=True) or {}
    lang = body.get("lang") if body.get("lang") in ("he", "en") else "he"
    email = (body.get("email") or "").strip().lower()[:120]
    if email and not _re_mobile.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "bad email"}), 400
    phone = _re_mobile.sub(r"\D", "", (body.get("phone") or "").strip()[:25])
    if phone:
        if phone.startswith("0"):
            phone = "972" + phone[1:]
        if not _re_mobile.match(r"^\d{10,15}$", phone):
            return jsonify({"error": "bad phone"}), 400
    if not email and not phone:
        return jsonify({"error": "missing contact"}), 400
    carrier = (body.get("carrier") or "").strip()
    plan_name = (body.get("plan_name") or "").strip()[:200]
    plan_type = body.get("plan_type") if body.get("plan_type") in _REM_PLAN_TYPES else "domestic"
    kinds = [k for k in (body.get("kinds") or []) if k in _REM_KINDS]
    if not kinds:
        return jsonify({"error": "missing kinds"}), 400
    if carrier not in _MOBILE_CARRIERS or not plan_name:
        return jsonify({"error": "unknown plan"}), 400
    plan = _rem_lookup_plan(plan_type, carrier, plan_name)
    if plan is None:
        return jsonify({"error": "unknown plan"}), 404
    channel = "both" if (email and phone) else ("email" if email else "whatsapp")
    # Optional self-declared actual monthly price ("כמה אתם משלמים בפועל?") —
    # when present, alerts compare against it instead of the rate-card price.
    paid_price = None
    try:
        pp = float(body.get("paid_price"))
        if 5 <= pp <= 500:
            paid_price = round(pp, 2)
    except (TypeError, ValueError):
        pass
    rows = []
    for k in kinds:
        row = {"kind": k, "plan_type": plan_type, "carrier": carrier,
               "plan_name": plan_name,
               "price": plan.get("price"), "data_gb": plan.get("data_gb"),
               "unlimited": plan.get("unlimited"), "days": plan.get("days"),
               "email": email or None,
               "phone": phone or None, "channel": channel, "lang": lang,
               "paid_price": paid_price}
        if k == "plan_end":
            today = datetime.now().date()
            try:
                end = datetime.strptime((body.get("end_date") or "").strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "bad end_date"}), 400
            if not (today <= end <= today + timedelta(days=3 * 365)):
                return jsonify({"error": "bad end_date"}), 400
            try:
                days_before = int(body.get("remind_days_before"))
            except (TypeError, ValueError):
                days_before = 7
            if days_before not in _REM_DAYS_CHOICES:
                days_before = 7
            row.update({"end_date": end.isoformat(), "remind_days_before": days_before,
                        "include_offers": bool(body.get("include_offers", True))})
        rows.append(row)
    token = secrets.token_urlsafe(24)
    save_mobile_reminders(token, rows, db_path=_db_path())
    log_mobile_event("reminder_subscribe", sid=body.get("sid"), carrier=carrier,
                     src=(body.get("src") or None), campaign=(body.get("campaign") or None),
                     lang=lang, ip_hash=_guest_ip_hash(), db_path=_db_path())
    return jsonify({"status": "subscribed", "token": token, "kinds": kinds}), 201


@app.route("/api/mobile/reminders/unsubscribe", methods=["GET", "POST"])
@limiter.limit("30 per minute")
def api_mobile_reminders_unsubscribe():
    """Public: remove ALL reminder rows of one signup by its shared token.
    GET renders a tiny bilingual confirmation page (the email/WhatsApp links
    are plain <a> clicks); POST returns JSON for in-app use."""
    from db import delete_mobile_reminders_by_token
    token = (request.args.get("token")
             or (request.get_json(silent=True) or {}).get("token") or "").strip()
    if not token or len(token) > 80:
        return jsonify({"error": "missing token"}), 400
    deleted = delete_mobile_reminders_by_token(token, db_path=_db_path())
    if request.method == "POST":
        return jsonify({"status": "unsubscribed", "deleted": deleted})
    msg_he = ("הוסרת מרשימת העדכונים. לא יישלחו יותר תזכורות." if deleted
              else "הקישור כבר אינו פעיל - ההרשמה הוסרה בעבר.")
    msg_en = ("You have been unsubscribed - no more reminders will be sent." if deleted
              else "This link is no longer active - the signup was already removed.")
    site = (load_config().get("public_site_url") or "https://mocaintel.com").rstrip("/")
    page = (
        "<!doctype html><html dir='rtl' lang='he'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>MOCA</title></head>"
        "<body style='font-family:Arial,sans-serif;background:#f9f4ee;color:#3b1f0d;"
        "display:flex;align-items:center;justify-content:center;min-height:90vh;margin:0'>"
        "<div style='background:#fff;border-radius:20px;padding:32px 28px;max-width:420px;"
        "text-align:center;box-shadow:0 6px 24px rgba(70,45,20,.08)'>"
        "<div style='font-size:34px;margin-bottom:10px'>&#9889;</div>"
        f"<h1 style='font-size:19px;margin:0 0 8px'>MOCA</h1>"
        f"<p style='font-size:15px;margin:0 0 6px'>{msg_he}</p>"
        f"<p dir='ltr' style='font-size:13px;color:#8a6a4a;margin:0 0 16px'>{msg_en}</p>"
        f"<a href='{site}/mobile-deals' "
        f"style='color:#5c3317;font-weight:bold'>{site.split('//', 1)[-1]}/mobile-deals</a>"
        "</div></body></html>")
    return Response(page, mimetype="text/html")


def run_mobile_reminders_job():
    """Daily 09:15 — deliver /mobile-deals email/WhatsApp reminders off the
    normalized domestic feed: better-deal alerts (recurring, price-ratcheted)
    and plan-term-end reminders (one-shot, optional retention offers)."""
    try:
        from notifier import (notify_mobile_better_deals, notify_mobile_plan_end_reminders,
                              notify_mobile_heartbeat, notify_mobile_renewal_followups)
        config = load_config()
        plans = _assemble_mobile_plans(_db_path()).get("plans", [])
        n_deal = notify_mobile_better_deals(plans, config, db_path=_db_path())
        n_end = notify_mobile_plan_end_reminders(plans, config, db_path=_db_path())
        n_renew = notify_mobile_renewal_followups(plans, config, db_path=_db_path())
        n_pulse = notify_mobile_heartbeat(plans, config, db_path=_db_path())
        logger.info(f"mobile reminders job: {n_deal} better-deal + {n_end} plan-end "
                    f"+ {n_renew} renewal + {n_pulse} heartbeat sent")
        return {"better_deal_sent": n_deal, "plan_end_sent": n_end,
                "renewal_sent": n_renew, "heartbeat_sent": n_pulse}
    except Exception as e:
        logger.error(f"mobile reminders job failed: {e}")
        return {"error": str(e)}


@app.route("/api/mobile/reminders/run-now", methods=["GET", "POST"])
@require_api_key
def api_mobile_reminders_run_now():
    """Manual trigger / smoke-test for the daily reminders job."""
    return jsonify(run_mobile_reminders_job())


@app.route("/api/mobile/reminders/subscribers")
@require_api_key_or_super_admin
def api_mobile_reminders_subscribers():
    """Super-admin: every reminder signup (contact details included) for the
    /admin/mobile-subscribers dashboard. Returns ALL rows — active and done —
    newest first, plus summary counts."""
    from db import get_all_mobile_reminders
    rows = get_all_mobile_reminders(db_path=_db_path())
    emails = {r["email"] for r in rows if r.get("email")}
    phones = {r["phone"] for r in rows if r.get("phone")}
    return jsonify({
        "rows": rows,
        "stats": {
            "total_rows": len(rows),
            "active_rows": sum(1 for r in rows if not r.get("done")),
            "unique_emails": len(emails),
            "unique_phones": len(phones),
        },
    })


# ════════════════════════════════════════════════════════════════════════════
#  MOCA Guest Connect — hotels vertical (public guest portal + operator console)
#  Plan: Hotel/Hotel Plan.txt §2.3 / §5. Public routes are unauthenticated;
#  /api/hotels* admin routes require the API key or a super_admin JWT.
# ════════════════════════════════════════════════════════════════════════════

def _guest_ip_hash():
    ip = _client_ip() or ""
    api_key = load_config().get("api_key", "")
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


@app.route("/api/guest/<slug>")
@limiter.limit("120 per minute")
def api_guest_portal(slug):
    """Public guest portal payload: hotel branding + live Israel deal feed."""
    hotel = get_hotel(slug, db_path=_db_path())
    if not hotel or not hotel.get("active"):
        return jsonify({"error": "Guest portal not found"}), 404
    destination = hotel.get("country") or "ישראל"
    deals, providers, updated_at = _assemble_guest_deals(db_path=_db_path(), destination=destination)
    try:
        from scraper import _get_usd_to_ils
        fx = _get_usd_to_ils()
    except Exception:
        fx = 3.7
    # Discount codes for the providers in this feed (e.g. Saily MOCA 10%), first
    # active code per carrier (matches the main app's PlanCard behaviour).
    provs_in_feed = {d["provider"] for d in deals}
    guest_coupons = {}
    for c in get_active_coupons(db_path=_db_path()):
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
    return _public_cache(jsonify(payload), 300)


_GUEST_CLIENT_EVENTS = {"view", "scan", "engage"}


@app.route("/api/guest/<slug>/event", methods=["POST"])
@limiter.limit("240 per minute")
def api_guest_event(slug):
    """Anonymous guest-portal beacon (view / scan / engage). 204, never errors."""
    if not get_hotel(slug, db_path=_db_path()):
        return ("", 204)
    data = request.get_json(silent=True) or {}
    et = (data.get("event_type") or "").strip()
    if et not in _GUEST_CLIENT_EVENTS:
        return ("", 204)
    log_guest_event(
        slug, et, lang=(data.get("lang") or None),
        country=(request.headers.get("Accept-Language", "")[:8] or None),
        ip_hash=_guest_ip_hash(), user_agent=request.headers.get("User-Agent"),
        db_path=_db_path(),
    )
    return ("", 204)


@app.route("/api/guest/<slug>/qr.svg")
@limiter.limit("60 per minute")
def api_guest_qr(slug):
    """Branded QR (SVG) that deep-links to the hotel's guest portal."""
    hotel = get_hotel(slug, db_path=_db_path())
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
        app.logger.warning("QR generation failed (is 'qrcode' installed?)", exc_info=True)
        return jsonify({"error": "QR generation unavailable"}), 503
    resp = Response(svg, mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ── Operator console (super_admin / API key) ───────────────────────────────
@app.route("/api/hotels", methods=["GET"])
@require_api_key_or_super_admin
@limiter.limit("60 per minute")
def api_hotels_list():
    return jsonify(list_hotels(db_path=_db_path()))


@app.route("/api/hotels", methods=["POST"])
@require_api_key_or_super_admin
@limiter.limit("30 per minute")
def api_hotels_create():
    data = request.get_json(silent=True) or {}
    try:
        hotel = upsert_hotel(data, db_path=_db_path())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(hotel), 201


@app.route("/api/hotels/<slug>", methods=["PATCH"])
@require_api_key_or_super_admin
@limiter.limit("30 per minute")
def api_hotels_update(slug):
    existing = get_hotel(slug, db_path=_db_path())
    if not existing:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    merged = {**existing, **data, "slug": slug}
    try:
        hotel = upsert_hotel(merged, db_path=_db_path())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(hotel)


@app.route("/api/hotels/<slug>", methods=["DELETE"])
@require_api_key_or_super_admin
@limiter.limit("30 per minute")
def api_hotels_delete(slug):
    delete_hotel(slug, db_path=_db_path())
    return ("", 204)


@app.route("/api/hotels/<slug>/analytics")
@require_api_key_or_super_admin
@limiter.limit("60 per minute")
def api_hotels_analytics(slug):
    try:
        days = max(0, min(int(request.args.get("days", 30)), 365))
    except (ValueError, TypeError):
        days = 30
    return jsonify(get_guest_analytics(slug, days=days, db_path=_db_path()))


@app.route("/api/hotels/leads")
@require_api_key_or_super_admin
@limiter.limit("60 per minute")
def api_hotels_leads():
    return jsonify(get_hotel_leads(db_path=_db_path()))


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
        notifier.send_notification(msg, load_config())
    except Exception:
        app.logger.warning("hotel lead telegram failed", exc_info=True)


@app.route("/api/hotels/lead", methods=["POST"])
@limiter.limit("10 per minute")
def api_hotels_lead():
    """Public lead capture from the /hotels marketing landing form."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not email and not phone:
        return jsonify({"error": "email or phone required"}), 400
    try:
        rooms = int(data["rooms"]) if str(data.get("rooms", "")).strip() else None
    except (ValueError, TypeError):
        rooms = None
    lead = {
        "hotel_name": (data.get("hotel_name") or "")[:200],
        "contact_name": (data.get("contact_name") or "")[:200],
        "email": email[:200], "phone": phone[:60], "rooms": rooms,
        "message": (data.get("message") or "")[:2000], "source": "/hotels",
    }
    save_hotel_lead(lead, db_path=_db_path())
    _notify_hotel_lead(lead)
    return jsonify({"ok": True})


@app.route("/api/global-changes")
@limiter.limit("60 per minute")
def api_global_changes():
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 500))
    except (ValueError, TypeError):
        limit = 50
    changes = get_global_changes(limit=limit, db_path=_db_path())
    return _public_cache(jsonify(_filter_hidden_carrier(changes)), 600)


@app.route("/api/scrape-global-now")
@require_api_key_or_query
def api_scrape_global_now():
    """Manual trigger: scrape global eSIM packages, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_global_plans, save_global_changes, filter_already_notified
        from change_detector import detect_changes
        old_plans = get_global_plans(db_path=_db_path())
        new_plans = sc.scrape_all_global()
        existing_changes = get_global_changes(limit=1, db_path=_db_path())
        if not existing_changes:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_plans]
            save_global_changes(seed, db_path=_db_path())
            changes = seed
        else:
            changes = detect_changes(old_plans, new_plans, per_group_extras=True)
            # Global providers scrape hundreds of per-country pages; partial failures make
            # plans flap new/removed every run (~6,700 phantom rows/day). Keep only the
            # meaningful signal (price/extras/details) for global — price_change still
            # powers the history charts. Domestic/abroad are unaffected.
            changes = [c for c in changes if c["change_type"] not in ("new_plan", "removed_plan")]
            changes = filter_already_notified(changes, 'global_changes', db_path=_db_path())
            if changes:
                save_global_changes(changes, db_path=_db_path())
        save_global_plans(new_plans, db_path=_db_path())
        arc.archive_global_plans(new_plans)
        # B2C destination price-drop pushes — state-based (baseline vs current min),
        # so it must run after save_global_plans on EVERY global scrape path.
        try:
            from notifier import notify_esim_price_drops
            notify_esim_price_drops(load_config(), db_path=_db_path())
        except Exception as e:
            logger.warning(f"esim price-drop push failed: {e}")
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-global-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@app.route("/api/abroad-changes")
@limiter.limit("60 per minute")
def api_abroad_changes():
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except (ValueError, TypeError):
        limit = 50
    changes = get_abroad_changes(limit=limit, db_path=_db_path())
    return _public_cache(jsonify(_filter_hidden_carrier(changes)), 600)


@app.route("/api/scrape-abroad-now")
@require_api_key_or_query
def api_scrape_abroad_now():
    """Manual trigger: scrape abroad packages, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_abroad_plans, save_abroad_changes, filter_already_notified
        from change_detector import detect_changes
        old_plans = get_abroad_plans(db_path=_db_path())
        new_plans = sc.scrape_all_abroad()
        # If abroad_changes is empty (first run), seed all plans as new_plan
        existing_changes = get_abroad_changes(limit=1, db_path=_db_path())
        if not existing_changes:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_plans]
            save_abroad_changes(seed, db_path=_db_path())
            changes = seed
        else:
            changes = detect_changes(old_plans, new_plans)
            changes = filter_already_notified(changes, 'abroad_changes', db_path=_db_path())
            if changes:
                save_abroad_changes(changes, db_path=_db_path())
        save_abroad_plans(new_plans, db_path=_db_path())
        arc.archive_abroad_plans(new_plans)
        from notifier import alert_missing_terms
        alert_missing_terms(changes, new_plans, 'abroad_plans', load_config())
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-abroad-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


# ── Real-time scrape progress (SSE) ──────────────────────────────────────────
import threading as _threading_progress

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


@app.route("/api/scrape-progress/stream")
@require_auth
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


@app.route("/api/scrape-progress/state")
@require_auth
def api_scrape_progress_state():
    """One-shot snapshot of current scrape progress (for clients that don't use SSE)."""
    with _scrape_lock:
        return jsonify({
            'active':       _scrape_progress['active'],
            'started_at':   _scrape_progress['started_at'],
            'completed_at': _scrape_progress['completed_at'],
            'log':          list(_scrape_progress['log'][-50:]),
        })


@app.route("/api/scrape-all-now")
@require_scrape_auth
def api_scrape_all_now():
    """Scrape ALL tabs: domestic + abroad + global in one call."""
    ok, used, limit = _check_refresh_quota()
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
        old_domestic = get_plans(db_path=_db_path())
        new_domestic = sc.scrape_all()
        ch_domestic  = detect_changes(old_domestic, new_domestic)
        save_plans(new_domestic, db_path=_db_path())
        # Drop changes already announced in the last 24h so the dashboard
        # changes log isn't polluted with repeats from consecutive scrapes.
        ch_domestic = filter_already_notified(ch_domestic, 'changes', db_path=_db_path())
        if ch_domestic:
            save_changes(ch_domestic, db_path=_db_path())
        results["domestic"] = {"plans": len(new_domestic), "changes": len(ch_domestic)}
        _scrape_emit('domestic', 'done', count=len(new_domestic), message=f'{len(new_domestic)} חבילות, {len(ch_domestic)} שינויים')
        # Safety net: alert the operator if a newly-added plan arrived with no terms link.
        from notifier import alert_missing_terms
        _terms_cfg = load_config()
        alert_missing_terms(ch_domestic, new_domestic, 'plans', _terms_cfg)
        # /mobile-deals consumer price-drop push (event-driven off the fresh list).
        try:
            from notifier import notify_mobile_price_drops
            notify_mobile_price_drops(ch_domestic, _terms_cfg, db_path=_db_path())
        except Exception as e:
            logger.warning(f"mobile price-drop push failed: {e}")

        # ── Abroad ────────────────────────────────────────────────────────
        _scrape_emit('abroad', 'starting', message='סורק חבילות חו"ל')
        old_abroad = get_abroad_plans(db_path=_db_path())
        new_abroad = sc.scrape_all_abroad()
        existing_abroad_ch = get_abroad_changes(limit=1, db_path=_db_path())
        if not existing_abroad_ch:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_abroad]
            save_abroad_changes(seed, db_path=_db_path())
            ch_abroad = seed
        else:
            ch_abroad = detect_changes(old_abroad, new_abroad)
            ch_abroad = filter_already_notified(ch_abroad, 'abroad_changes', db_path=_db_path())
            if ch_abroad:
                save_abroad_changes(ch_abroad, db_path=_db_path())
        save_abroad_plans(new_abroad, db_path=_db_path())
        results["abroad"] = {"plans": len(new_abroad), "changes": len(ch_abroad)}
        _scrape_emit('abroad', 'done', count=len(new_abroad), message=f'{len(new_abroad)} חבילות, {len(ch_abroad)} שינויים')
        alert_missing_terms(ch_abroad, new_abroad, 'abroad_plans', _terms_cfg)

        # ── Global ────────────────────────────────────────────────────────
        _scrape_emit('global', 'starting', message='סורק חבילות גלובל / eSIM')
        old_global = get_global_plans(db_path=_db_path())
        new_global = sc.scrape_all_global()
        existing_global_ch = get_global_changes(limit=1, db_path=_db_path())
        if not existing_global_ch:
            seed = [{"carrier": p["carrier"], "plan_name": p["plan_name"],
                     "change_type": "new_plan", "old_val": None, "new_val": p.get("price")}
                    for p in new_global]
            save_global_changes(seed, db_path=_db_path())
            ch_global = seed
        else:
            ch_global = detect_changes(old_global, new_global, per_group_extras=True)
            # Drop global new/removed churn (per-country scrape flapping); keep price/extras/details.
            ch_global = [c for c in ch_global if c["change_type"] not in ("new_plan", "removed_plan")]
            ch_global = filter_already_notified(ch_global, 'global_changes', db_path=_db_path())
            if ch_global:
                save_global_changes(ch_global, db_path=_db_path())
        save_global_plans(new_global, db_path=_db_path())
        try:
            from notifier import notify_esim_price_drops
            notify_esim_price_drops(load_config(), db_path=_db_path())
        except Exception as e:
            logger.warning(f"esim price-drop push failed: {e}")
        results["global"] = {"plans": len(new_global), "changes": len(ch_global)}
        _scrape_emit('global', 'done', count=len(new_global), message=f'{len(new_global)} חבילות, {len(ch_global)} שינויים')

        # ── Content services ──────────────────────────────────────────────
        _scrape_emit('content', 'starting', message='סורק שירותי תוכן')
        from db import save_content_plans, save_content_changes
        from change_detector import detect_content_changes
        old_content = get_content_plans(db_path=_db_path())
        new_content = sc.scrape_all_content()
        ch_content = detect_content_changes(old_content, new_content)
        save_content_plans(new_content, db_path=_db_path())
        ch_content = filter_already_notified(ch_content, 'content_changes', key_field='service', db_path=_db_path())
        if ch_content:
            save_content_changes(ch_content, db_path=_db_path())
        results["content"] = {"plans": len(new_content), "changes": len(ch_content)}
        _scrape_emit('content', 'done', count=len(new_content), message=f'{len(new_content)} שירותים, {len(ch_content)} שינויים')

        # ── Archive plan snapshots ─────────────────────────────────────────
        _scrape_emit('archive', 'starting', message='שומר תמונת מצב לארכיון')
        arc.archive_domestic_plans(new_domestic)
        arc.archive_abroad_plans(new_abroad)
        arc.archive_global_plans(new_global)
        arc.archive_content_plans(new_content)
        _scrape_emit('archive', 'done')

        # ── Banners (homepage + e-store screenshots) ───────────────────────
        _scrape_emit('banners', 'starting', message='מצלם באנרים')
        banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
        from scraper import (scrape_carrier_banners, scrape_carrier_store_banners,
                             scrape_global_provider_banners)
        banner_results = scrape_carrier_banners(banners_dir)
        store_results  = scrape_carrier_store_banners(banners_dir)
        global_results = scrape_global_provider_banners(banners_dir)
        from scraper import GLOBAL_BANNER_URLS as _GBU
        arc.archive_all_banners(banners_dir, list(CARRIER_DISPLAY.keys()), list(CARRIER_STORE_DISPLAY.keys()))
        arc.archive_all_global_banners(banners_dir, list(_GBU.keys()))
        results["banners"] = {
            "homepage": sum(1 for r in banner_results if r["success"]),
            "store":    sum(1 for r in store_results  if r["success"]),
            "global":   sum(1 for r in global_results if r["success"]),
        }
        _scrape_emit('banners', 'done', count=results['banners']['homepage'] + results['banners']['store'] + results['banners']['global'])

        _invalidate_plan_cache()
        results["status"] = "ok"
        results["total_plans"] = len(new_domestic) + len(new_abroad) + len(new_global) + len(new_content)
        results["total_changes"] = len(ch_domestic) + len(ch_abroad) + len(ch_global) + len(ch_content)
        results["quota_used"]  = used + 1
        results["quota_limit"] = limit
        _log_refresh('scrape_all')
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


@app.route("/api/content-plans")
@limiter.limit("60 per minute")
def api_content_plans():
    carrier = request.args.get("carrier")
    service = request.args.get("service")
    plans = get_content_plans(service=service, carrier=carrier, db_path=_db_path())
    return _public_cache(jsonify(_filter_hidden_carrier(plans)), 600)


def _price_direction(change):
    """Return 'up', 'down', or None for a price_change record."""
    try:
        old, new = float(change['old_val']), float(change['new_val'])
        if new > old: return 'up'
        if new < old: return 'down'
        return None
    except (ValueError, TypeError):
        return None


# Carrier ID \u2192 display name for price-history endpoints.
# MUST stay in sync with mass-market-app/src/data/carrierLabels.js
# (mirrors _CARRIER_NAMES below; both track the JS GLOBAL_LABELS/DOMESTIC_LABELS).
_HISTORY_CARRIER_NAMES = {
    'partner': '\u05e4\u05e8\u05d8\u05e0\u05e8',
    'pelephone': '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df',
    'hotmobile': '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
    'cellcom': '\u05e1\u05dc\u05e7\u05d5\u05dd',
    'mobile019': '019',
    'xphone': 'XPhone',
    'wecom': 'We-Com',
    'neptucom': 'Neptucom',
    'tuki': 'Tuki',
    'terminalesim': 'Terminal eSIM',
    'gigsky': 'GigSky',
    'esimgenius': 'eSIM Genius',
    'nisim': 'Nisim eSIM',
    'esimax': 'eSIM Max',
    'venterrasim': 'VenterraSIM',
    'simzol': 'Simzol',
    'airalo': 'Airalo',
    'pelephone_global': 'GlobalSIM',
    'esimo': 'eSIMo',
    'simtlv': 'SimTLV',
    'world8': '8 World',
    'xphone_global': 'XPhone Global',
    'saily': 'Saily',
    'holafly': 'Holafly',
    'esimio': 'eSIM.io',
    'sparks': 'Sparks',
    'voye': 'VOYE',
    'orbit': 'Orbit',
    'travelsim': 'Travel Sim',
    'gomoworld': 'GoMoWorld',
    'tasim': 'Tasim',
    'maya': 'Maya Mobile',
    'esim70': 'eSIM70',
    'jetpack': 'Jetpack',
    'breez': 'Breeze',
    'bytesim': 'ByteSim',
    'besim': 'Besim',
    'seven_g': '7G',
    'bestconnect': 'Best Connect',
    'bnesim': 'BNESIM',
    'esimplus': 'eSIM Plus',
    'bcengi': 'Bcengi',
    'yesim': 'Yesim', 'nomad': 'Nomad', 'ubigi': 'Ubigi', 'alosim': 'aloSIM',
}
_HISTORY_TYPE_NAMES = {
    'domestic': '\u05de\u05e7\u05d5\u05de\u05d9',
    'abroad': '\u05d7\u05d5"\u05dc',
    'global': '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9',
    'content': '\u05ea\u05d5\u05db\u05df',
}


CARRIER_DISPLAY = {
    "partner":   {"name": "פרטנר",      "url": "https://www.partner.net.il",       "color": "#2ed5c4"},
    "pelephone": {"name": "פלאפון",     "url": "https://www.pelephone.co.il",      "color": "#001fff"},
    "hotmobile": {"name": "הוט מובייל", "url": "https://www.hotmobile.co.il",      "color": "#e3001e"},
    "cellcom":   {"name": "סלקום",      "url": "https://www.cellcom.co.il",        "color": "#9530ff"},
    "mobile019": {"name": "019 מובייל", "url": "https://www.019mobile.co.il",      "color": "#e8202a"},
    "xphone":    {"name": "XPhone",     "url": "https://www.xphone.co.il",         "color": "#2b9fd5"},
    "wecom":     {"name": "וי-קום",     "url": "https://we-com.co.il",             "color": "#ff4500"},
    "neptucom":  {"name": "נפטוקום",    "url": "https://www.neptucom.com",         "color": "#29b6d6"},
    "golan":     {"name": "גולן טלקום", "url": "https://www.golantelecom.co.il",   "color": "#cc1717"},
    "rami_levy": {"name": "רמי לוי תקשורת", "url": "https://mobile.rami-levy.co.il",  "color": "#e8178a"},
}

CARRIER_STORE_DISPLAY = {
    "pelephone": {"name": "פלאפון",     "url": "https://www.pelephone.co.il/ds/heb/eshop/lobby/", "color": "#001fff"},
    "cellcom":   {"name": "סלקום",      "url": "https://shop.cellcom.co.il/",                      "color": "#9530ff"},
    "partner":   {"name": "פרטנר",      "url": "https://store.partner.co.il/home",                 "color": "#2ed5c4"},
    "hotmobile": {"name": "הוט מובייל", "url": "https://hotstore.hotmobile.co.il/smartphones.html","color": "#e3001e"},
}


# ── Social listening search terms per carrier ──────────────────────────────
# Social listening: search for public MENTIONS of carriers (not their own pages).
# he = Hebrew name to search, en = English name, tags = hashtags for TikTok/Instagram.

CARRIER_SEARCH_TERMS = {
    'partner': {
        'he':   '\u05e4\u05e8\u05d8\u05e0\u05e8',
        'en':   'Partner Communications',
        'tags': ['\u05e4\u05e8\u05d8\u05e0\u05e8', 'partner_il', 'partnertv'],
    },
    'pelephone': {
        'he':   '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df',
        'en':   'Pelephone',
        'tags': ['\u05e4\u05dc\u05d0\u05e4\u05d5\u05df', 'pelephone'],
    },
    'cellcom': {
        'he':   '\u05e1\u05dc\u05e7\u05d5\u05dd',
        'en':   'Cellcom Israel',
        'tags': ['\u05e1\u05dc\u05e7\u05d5\u05dd', 'cellcom'],
    },
    'hotmobile': {
        'he':   '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
        'en':   'Hot Mobile Israel',
        'tags': ['\u05d4\u05d5\u05d8\u05de\u05d5\u05d1\u05d9\u05d9\u05dc', 'hotmobile'],
    },
    'mobile019': {
        'he':   '019 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
        'en':   '019 Mobile',
        'tags': ['019mobile', '019\u05de\u05d5\u05d1\u05d9\u05d9\u05dc'],
    },
    'xphone': {
        'he':   '\u05d0\u05e7\u05e1 \u05e4\u05d5\u05df',
        'en':   'XPhone Israel',
        'tags': ['xphone'],
    },
    'wecom': {
        'he':   '\u05d5\u05d9 \u05e7\u05d5\u05dd',
        'en':   'WeCom Israel',
        'tags': ['wecom', '\u05d5\u05d9\u05e7\u05d5\u05dd'],
    },
    'neptucom': {
        'he':   'Neptucom',
        'en':   'Neptucom Israel',
        'tags': ['neptucom'],
    },
    'golan': {
        'he':   '\u05d2\u05d5\u05dc\u05df \u05d8\u05dc\u05e7\u05d5\u05dd',
        'en':   'Golan Telecom',
        'tags': ['golantelecom', '\u05d2\u05d5\u05dc\u05df\u05d8\u05dc\u05e7\u05d5\u05dd'],
    },
    'rami_levy': {
        'he':   '\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9 \u05ea\u05e7\u05e9\u05d5\u05e8\u05ea',
        'en':   'Rami Levy Communications',
        'tags': ['ramilevy', '\u05e8\u05de\u05d9\u05dc\u05d5\u05d9\u05ea\u05e7\u05e9\u05d5\u05e8\u05ea'],
    },
}


def _normalize_post(platform, raw):
    """Normalize a raw Apify post dict to a consistent schema.

    Handles field-name differences across actors:
      Facebook  (scrapeforge~facebook-search-posts):   message, post_text, content
      Instagram (apify~instagram-hashtag-scraper):     caption, alt
      Twitter   (api-ninja~x-twitter-advanced-search): text, full_text, tweet_text
      TikTok    (clockworks~tiktok-scraper):           text, description
    """
    text = (
        raw.get('message') or raw.get('post_text') or raw.get('content') or
        raw.get('caption') or raw.get('alt') or
        raw.get('text') or raw.get('full_text') or raw.get('tweet_text') or
        raw.get('description') or raw.get('title') or ''
    )
    likes = (
        raw.get('likesCount') or raw.get('diggCount') or raw.get('likes') or
        raw.get('likeCount') or raw.get('favoriteCount') or
        raw.get('like_count') or raw.get('retweet_count') or 0
    )
    date = (
        raw.get('time') or raw.get('timestamp') or raw.get('date') or
        raw.get('createdAt') or raw.get('created_at') or raw.get('publishedAt') or
        raw.get('post_date') or ''
    )
    url = (
        raw.get('url') or raw.get('postUrl') or raw.get('post_url') or
        raw.get('webVideoUrl') or raw.get('link') or raw.get('tweet_url') or ''
    )
    likes_val = likes
    if not isinstance(likes_val, int):
        try:
            likes_val = int(likes_val)
        except (TypeError, ValueError):
            likes_val = 0
    return {
        'platform': platform,
        'text':     str(text)[:400],
        'likes':    likes_val,
        'date':     str(date),
        'url':      str(url),
    }


def generate_social_sentiment():
    """Scrape social media for each carrier and generate Hebrew sentiment analysis.

    Runs every 3 days at 08:00 via APScheduler and on-demand via POST /api/social-sentiment/refresh.
    Requires 'apify_api_key' and 'anthropic_api_key' in config.json.
    """
    logger.info("Generating social sentiment...")
    config = load_config()
    anthropic_key = config.get("anthropic_api_key", "")
    apify_key     = config.get("apify_api_key", "")
    if not anthropic_key:
        logger.warning("social sentiment: anthropic_api_key missing, skipping")
        return
    if not apify_key:
        logger.warning("social sentiment: apify_api_key missing — add 'apify_api_key' to config.json")
        return

    import requests as _req
    import re as _re

    def _scrape_apify(platform, actor_slug, actor_input):
        """Call Apify run-sync and return normalized post list (max 10).

        actor_slug must use ~ separator (e.g. 'apify~facebook-posts-scraper').
        Apify run-sync returns 200 or 201; both indicate dataset items.
        """
        try:
            url = (
                f"https://api.apify.com/v2/acts/{actor_slug}/run-sync-get-dataset-items"
                f"?token={apify_key}&timeout=60&memory=256"
            )
            resp = _req.post(url, json=actor_input, timeout=75)
            if resp.status_code not in (200, 201):
                logger.warning(f"social sentiment: Apify {platform} HTTP {resp.status_code} — {resp.text[:150]}")
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            # Filter out error/empty sentinel items
            valid = [
                item for item in data
                if isinstance(item, dict)
                and not item.get('error')
                and not item.get('noResults')
                and (item.get('message') or item.get('caption') or item.get('text')
                     or item.get('full_text') or item.get('description') or item.get('title'))
            ]
            return [_normalize_post(platform, item) for item in valid[:10]]
        except Exception as exc:
            logger.warning(f"social sentiment: {platform} failed: {exc}")
            return []

    # Social LISTENING: search public mentions of carriers, not their own pages.
    system_prompt = (
        "אתה אנליסט מדיה חברתית במחלקת השיווק של Pelephone. "
        "תפקידך לנטר את שיח הציבור על ספקי הסלולר ולהסיק משמעויות עבור מנהל השיווק של Pelephone. "
        "אתה מקבל פוסטים של לקוחות ומשתמשים רגילים ברשתות החברתיות שמאזכרים ספק סלולר מסוים. "
        "כאשר הספק הוא Pelephone — נתח מה אומר הציבור עלינו ומה משמעות הדבר לפעילות השיווקית. "
        "כאשר הספק הוא מתחרה — נתח מה חולשותיו וחוזקותיו בעיני הציבור ומה Pelephone יכולה ללמוד מכך. "
        "כתוב אך ורק בעברית תקנית, נכונה ורהוטה. "
        "השתמש במילים עבריות קיימות ונפוצות בלבד — אל תמציא מילים. "
        "שמות ספקים וחברות תמיד באנגלית (Partner, Pelephone, Cellcom, Hot Mobile, 019, XPhone, WeCom). "
        "אסור לתרגם שמות ספקים לעברית. "
        "אסור להשתמש ב-Markdown, כותרות, כוכביות, או תבליטים. "
        "כתוב פרוזה רגילה בלבד. "
        "בסוף התגובה, הוסף שורה חדשה: SENTIMENT: ולאחריה אחת מ: positive / negative / neutral / mixed"
    )

    platform_labels = {
        'facebook':  '\u05e4\u05d9\u05d9\u05e1\u05d1\u05d5\u05e7',
        'instagram': '\u05d0\u05d9\u05e0\u05e1\u05d8\u05d2\u05e8\u05dd',
        'twitter':   'Twitter / X',
        'tiktok':    'TikTok',
    }
    since_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')

    from urllib.parse import quote as _url_quote

    for carrier, terms in CARRIER_SEARCH_TERMS.items():
        try:
            platform_data = {}
            he_term = terms['he']
            en_term = terms['en']
            tags     = terms.get('tags', [he_term])

            # ── Facebook: search public posts mentioning the carrier ──────────
            # scrapeforge~facebook-search-posts: keyword search across public posts
            fb_query = f"{he_term} OR {en_term}"
            posts = _scrape_apify('facebook', 'scrapeforge~facebook-search-posts', {
                'query':        fb_query,
                'search_type':  'posts',
                'max_results':  15,
                'recent_posts': True,
            })
            if posts:
                platform_data['facebook'] = posts

            # ── Instagram: search by Hebrew hashtag ───────────────────────────
            # apify~instagram-hashtag-scraper: official hashtag search actor
            posts = _scrape_apify('instagram', 'apify~instagram-hashtag-scraper', {
                'hashtags':     [t.lstrip('#') for t in tags[:2]],
                'resultsType':  'posts',
                'resultsLimit': 10,
            })
            if posts:
                platform_data['instagram'] = posts

            # ── Twitter/X: search for public mentions in Hebrew ───────────────
            # api-ninja~x-twitter-advanced-search: keyword + language filter
            twitter_query = f'{he_term} OR {en_term}'
            posts = _scrape_apify('twitter', 'api-ninja~x-twitter-advanced-search', {
                'query':           twitter_query,
                'search_type':     'Latest',
                'numberOfTweets':  15,
                'contentLanguage': 'he',
                'timeWithinTime':  '7d',
                'tweetTypes':      ['original', 'quotes', 'replies'],
            })
            if posts:
                platform_data['twitter'] = posts

            # ── TikTok: search by hashtags ────────────────────────────────────
            posts = _scrape_apify('tiktok', 'clockworks~tiktok-scraper', {
                'hashtags':              [t.lstrip('#') for t in tags[:2]],
                'resultsPerPage':        10,
                'oldestPostDateUnified': since_date,
            })
            if posts:
                platform_data['tiktok'] = posts

            if not platform_data:
                logger.info(f"social sentiment: no mentions found for {carrier}, skipping")
                continue

            carrier_english = en_term
            total_posts = sum(len(v) for v in platform_data.values())
            posts_text = ''
            for platform, posts in platform_data.items():
                label = platform_labels.get(platform, platform)
                posts_text += f"\n{label} ({len(posts)} \u05e4\u05d5\u05e1\u05d8\u05d9\u05dd):\n"
                for p in posts:
                    if p['text']:
                        posts_text += f"  - {p['text'][:250]}\n"

            is_pelephone = (carrier == 'pelephone')
            perspective_line = (
                "סכם מה הציבור אומר עלינו (Pelephone), מה הנושאים החוזרים, ומה המשמעות לפעילות השיווקית שלנו."
                if is_pelephone else
                f"סכם מה הציבור אומר על {carrier_english}, והסק מה Pelephone יכולה ללמוד מכך — חולשות שניתן לנצל, או חוזקות שכדאי לקחת בחשבון."
            )
            prompt = (
                f"להלן {total_posts} פוסטים של משתמשים ברשתות החברתיות שמאזכרים את {carrier_english} ב-7 הימים האחרונים:\n"
                f"{posts_text}\n"
                f"כתוב פסקה אחת קצרה ורהוטה בעברית תקינה (3-4 משפטים, עד 80 מילה).\n"
                f"{perspective_line}\n"
                f"לאחר הפסקה, הוסף שתי שורות:\n"
                f"SENTIMENT: ואחריה אחת מ: positive / negative / neutral / mixed\n"
                f"COUNTS: positive:N negative:N neutral:N (כאשר N הוא מספר הפוסטים בכל קטגוריה)"
            )

            resp = _req.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 400,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            _ss_body = resp.json()
            _record_claude_call('social_sentiment', 'claude-sonnet-4-6', _ss_body)
            raw = _ss_body["content"][0]["text"].strip()

            sentiment = 'neutral'
            counts = {'positive': 0, 'negative': 0, 'neutral': 0}

            if 'SENTIMENT:' in raw:
                parts = raw.split('SENTIMENT:', 1)
                raw_narrative = parts[0].strip()
                after_sentiment = parts[1]
                for s in ['positive', 'negative', 'mixed', 'neutral']:
                    if s in after_sentiment.lower():
                        sentiment = s
                        break
                if 'COUNTS:' in after_sentiment:
                    counts_str = after_sentiment.split('COUNTS:', 1)[1]
                    for key in ['positive', 'negative', 'neutral']:
                        m = _re.search(rf'{key}:(\d+)', counts_str, _re.IGNORECASE)
                        if m:
                            counts[key] = int(m.group(1))
            else:
                raw_narrative = raw

            narrative = _re.sub(r'^#+\s*', '', raw_narrative, flags=_re.MULTILINE)
            narrative = _re.sub(r'\*+', '', narrative)
            narrative = _re.sub(r'\n{2,}', ' ', narrative).strip()

            platform_data['_counts'] = counts
            save_social_sentiment(carrier, platform_data, narrative, sentiment, db_path=_db_path())
            logger.info(f"social sentiment: saved {carrier} ({sentiment})")

        except Exception as exc:
            logger.error(f"social sentiment: failed for {carrier}: {exc}", exc_info=True)

    logger.info("Social sentiment generation complete.")


# ── Executive Summary generation ───────────────────────────────────────────

_CATEGORY_LABELS = {
    'domestic': '\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05e1\u05dc\u05d5\u05dc\u05e8',
    'abroad':   '\u05d7\u05d5"\u05dc',
    'global':   '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9 (eSIM)',
    'content':  '\u05ea\u05d5\u05db\u05df',
}


def generate_executive_summary():
    """Generate AI-powered executive summary for all 4 categories and store in DB.

    Runs at 08:05 via APScheduler and on-demand via POST /api/executive-summary/refresh.
    """
    logger.info("Generating executive summary...")
    config = load_config()
    api_key = config.get("anthropic_api_key", "")
    if not api_key:
        logger.warning("executive summary: anthropic_api_key missing, skipping")
        return

    import requests as _req
    try:
        from scraper import _get_usd_to_ils, _get_eur_to_ils
        usd_rate = _get_usd_to_ils()
        eur_rate = _get_eur_to_ils()
    except Exception as e:
        logger.warning(f"executive summary: could not get exchange rates: {e}, using defaults")
        usd_rate, eur_rate = 3.7, 4.0

    for category in ['domestic', 'abroad', 'global', 'content']:
        try:
            metrics = compute_executive_metrics(
                category, usd_rate=usd_rate, eur_rate=eur_rate, db_path=_db_path()
            )
            if not metrics['chart_data']:
                logger.info(f"executive summary: no data for {category}, skipping")
                continue

            cat_label = _CATEGORY_LABELS.get(category, category)
            cheapest = metrics['cheapest']
            aggressive = metrics['most_aggressive']
            wc = metrics['weekly_changes']
            top_plans_str = '\n'.join(f"  - {p}" for p in metrics['top_plans'])

            cheapest_name = CARRIER_DISPLAY.get(cheapest['carrier'], {}).get('name', cheapest['carrier'])
            aggressive_name = CARRIER_DISPLAY.get(aggressive['carrier'], {}).get('name', aggressive['carrier'])

            prompt = (
                f"נתוני שוק עדכניים לקטגוריית {cat_label}:\n\n"
                f"הספק הזול ביותר: {cheapest_name} — {cheapest['value']} {cheapest['unit']}\n"
                f"הספק האגרסיבי ביותר (הכי הרבה הורדות מחיר ב-7 ימים): {aggressive_name} — {aggressive['changes']} שינויים\n"
                f"שינויים השבוע: סך הכל {wc['total']} ({wc['drops']} ירידות מחיר, {wc['rises']} עליות מחיר)\n\n"
                f"חבילות מובילות בשוק:\n{top_plans_str}\n\n"
                f"כתוב פסקה אחת קצרה ורהוטה בעברית תקינה ונכונה (3 עד 4 משפטים, עד 80 מילה).\n"
                f"הפסקה תנותח מנקודת מבטו של מנהל השיווק של Pelephone: מה מצב Pelephone ביחס למתחרים, אילו איומים או הזדמנויות עולים מהנתונים, ומה המשמעות השיווקית המיידית עבור Pelephone.\n"
                f"כתוב פרוזה רגילה בלבד — ללא כותרות, ללא מספרים, ללא תבליטים, ללא סימני Markdown."
            )

            resp = _req.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 400,
                    "system": (
                        "אתה אנליסט שוק בכיר במחלקת השיווק של Pelephone. "
                        "תפקידך לנתח את תמונת השוק ולהסיק משמעויות אסטרטגיות עבור מנהל השיווק של Pelephone. "
                        "כתוב אך ורק בעברית תקנית, נכונה ורהוטה. "
                        "השתמש במילים עבריות קיימות ונפוצות בלבד — אל תמציא מילים. "
                        "שמות ספקים וחברות יש לכתוב תמיד באנגלית בלבד (לדוגמה: Orbit, SimTLV, eSIMio, Airalo, Holafly, Voye, Partner, Pelephone, Cellcom, Hot Mobile, 019). "
                        "אסור לתעתק שמות ספקים לעברית. "
                        "השתמש במונחים מדויקים ובמשפטים קצרים וברורים. "
                        "אסור להשתמש ב-Markdown, כותרות, כוכביות, מספרים ממוספרים, או תבליטים. "
                        "כתוב פרוזה רגילה בלבד."
                    ),
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            _exec_body = resp.json()
            _record_claude_call('executive_summary', 'claude-sonnet-4-6', _exec_body)
            raw_narrative = _exec_body["content"][0]["text"].strip()
            # Strip any markdown artifacts Claude might still produce
            import re as _re
            narrative = _re.sub(r'^#+\s*', '', raw_narrative, flags=_re.MULTILINE)
            narrative = _re.sub(r'\*+', '', narrative)
            narrative = _re.sub(r'\n{2,}', ' ', narrative).strip()

            save_executive_summary(category, metrics, narrative, db_path=_db_path())
            logger.info(f"executive summary: saved {category}")

        except Exception as e:
            logger.error(f"executive summary: failed for {category}: {e}", exc_info=True)

    logger.info("Executive summary generation complete.")


def scrape_news_job():
    """Fetch Google News RSS for all domestic carriers and store in DB.

    Runs daily at 08:10 via APScheduler.
    """
    from scraper import scrape_carrier_news
    logger.info("Scraping carrier news from Google News RSS...")
    try:
        articles = scrape_carrier_news()
        upsert_news_articles(articles, db_path=_db_path())
        logger.info(f"News scrape complete: {len(articles)} articles saved")
    except Exception as e:
        logger.error(f"News scrape job failed: {e}", exc_info=True)


# pelephon4u_scraper SILENCED 2026-07-26: pelephon4u.co.il returns 403 since
# ~2026-07-12 (Cloudways domain unmapped). Re-add if the site comes back.
RESELLER_SCRAPER_MODULES = ("pelephone_join_scraper", "btl_scrapers")


def scrape_resellers_job():
    """Scrape known reseller / below-the-line sources for promotional plans not
    on the carrier rate cards.

    Runs daily at 08:15 via APScheduler — 5 minutes before the morning digest,
    whose "מתחת לקו" section reads the reseller_changes this job writes. Each
    module is called in isolation so a failure in one doesn't block the others;
    btl_scrapers additionally isolates each SOURCE internally.

    Returns {module: {plans, changes}} for the manual-trigger endpoint.
    """
    logger.info("Scraping reseller websites...")
    from db import sync_reseller_plans
    result = {}
    for module_name in RESELLER_SCRAPER_MODULES:
        try:
            mod = __import__(module_name)
            plans = mod.scrape()
            if plans:
                changes = sync_reseller_plans(plans, db_path=_db_path())
                logger.info(f"{module_name}: {len(plans)} plans synced, {len(changes)} changes")
                result[module_name] = {"plans": len(plans), "changes": len(changes)}
            else:
                logger.warning(f"{module_name}: 0 plans matched — site layout may have changed")
                result[module_name] = {"plans": 0, "changes": 0}
        except Exception as e:
            logger.error(f"{module_name} scrape failed: {e}", exc_info=True)
            result[module_name] = {"error": str(e)}
    return result


def run_morning_check_job(send=True):
    """Morning changes check — runs daily (default 08:20) via APScheduler.

    Why it exists: the 07:30/17:00 scrape jobs notify only on changes that are
    freshly detected at scrape time — if a notification is missed, or a scraper
    silently breaks and stops seeing a carrier's page, nothing tells the
    operator. This job is the daily heartbeat: it summarizes everything in the
    change log over the last N hours (new plans / removed plans / price &
    extras changes across domestic+abroad+global+content), flags carriers whose
    data went stale or empty (a broken scraper can never report a new plan it
    didn't see), and ALWAYS sends — an explicit "אין שינויים" included.

    config.json knobs (all optional):
      morning_check_time          "HH:MM"  — cron time, default "08:20"
      morning_check_window_hours  int      — lookback window, default 26
      morning_check_stale_hours   int      — freshness threshold, default 36
      morning_check_global_stale_hours int — global freshness threshold, default 72
      morning_check_whatsapp      bool     — also send via WhatsApp, default false
    """
    from db import get_recent_changes_summary, get_scrape_freshness
    from notifier import format_morning_digest, send_notification, send_whatsapp

    config = load_config()
    within = int(config.get("morning_check_window_hours", 26))
    stale_after = int(config.get("morning_check_stale_hours", 36))
    # Global eSIM providers scrape hundreds of per-country pages; coverage is partial
    # per run by design, so MAX(scraped_at) legitimately lags a domestic carrier's.
    # A blanket 36h threshold here false-positives on normal flakiness and trains the
    # operator to ignore the global section — which is how esimio (frozen since Apr 29)
    # and maya (May 11) rotted unnoticed. A days-scale threshold flags real breakage
    # (weeks of zero rows) while tolerating a missed run or two. Note: a broken global
    # scraper returns [] but save_global_plans never deletes, so its rows AGE rather
    # than vanish — the per-row staleness check below is what catches the breakage.
    global_stale_after = int(config.get("morning_check_global_stale_hours", 72))

    summary = get_recent_changes_summary(within_hours=within, db_path=_db_path())
    freshness = get_scrape_freshness(db_path=_db_path())

    warnings = []
    now = datetime.now()
    for category, rows in freshness.items():
        threshold = global_stale_after if category == "global" else stale_after
        for row in rows:
            hours_ago = None
            if row.get("last_scraped"):
                try:
                    hours_ago = (now - datetime.fromisoformat(row["last_scraped"])).total_seconds() / 3600
                except (ValueError, TypeError):
                    pass
            if not row.get("count") or hours_ago is None or hours_ago > threshold:
                warnings.append({"carrier": row["carrier"], "category": category,
                                 "count": row.get("count", 0),
                                 "last_scraped": row.get("last_scraped"),
                                 "hours_ago": round(hours_ago, 1) if hours_ago is not None else None})
    # A carrier whose rows vanished entirely has no GROUP BY row at all —
    # check the known domestic carriers explicitly (skip when the DB is empty,
    # e.g. a fresh install, to avoid 10 false alarms).
    domestic_seen = {r["carrier"] for r in freshness.get("domestic", [])}
    if domestic_seen:
        for cid in CARRIER_DISPLAY:
            if cid not in domestic_seen:
                warnings.append({"carrier": cid, "category": "domestic", "count": 0,
                                 "last_scraped": None, "hours_ago": None})

    message = format_morning_digest(summary, warnings, within_hours=within,
                                    lang=config.get("notify_lang", "he"))
    sent = {"telegram": False, "whatsapp": False}
    if send:
        sent["telegram"] = send_notification(message, config)
        if config.get("morning_check_whatsapp"):
            sent["whatsapp"] = bool(send_whatsapp(message, config))

    total = sum(len(v) for v in summary.values())
    logger.info(f"Morning check: {total} change(s) in last {within}h, "
                f"{len(warnings)} freshness warning(s); telegram={sent['telegram']}")
    return {
        "total_changes": total,
        "by_category": {k: len(v) for k, v in summary.items()},
        "changes": summary,
        "freshness_warnings": warnings,
        "message": message,
        "sent": sent,
    }


@app.route("/api/morning-check/now", methods=["GET", "POST"])
@require_api_key_or_query
def api_morning_check_now():
    """Manually trigger the morning changes digest (same logic as the daily cron).

    ?send=false returns the digest JSON without sending Telegram/WhatsApp —
    useful for previewing what the morning message will look like.
    """
    send = request.args.get("send", "true").lower() != "false"
    try:
        return jsonify(run_morning_check_job(send=send))
    except Exception as e:
        logger.error(f"Morning check failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/executive-summary")
@limiter.limit("60 per minute")
def api_executive_summary():
    """Return cached executive summary for all 4 categories."""
    rows = get_executive_summary(db_path=_db_path())
    if not rows:
        return jsonify({"error": "not_generated_yet"}), 404
    return jsonify(rows)


@app.route("/api/executive-summary/refresh", methods=["POST"])
@require_scrape_auth
def api_executive_summary_refresh():
    """Trigger manual regeneration of all 4 executive summaries."""
    ok, used, limit = _check_refresh_quota()
    if not ok:
        return jsonify({"error": f"מכסת הרענון החודשית הגיעה לסיום ({used}/{limit}). מחכים לחודש הבא.", "quota_used": used, "quota_limit": limit}), 429
    try:
        generate_executive_summary()
        rows = get_executive_summary(db_path=_db_path())
        generated_at = rows[0]["generated_at"] if rows else None
        _log_refresh('executive_summary')
        return jsonify({"status": "ok", "generated_at": generated_at, "quota_used": used + 1, "quota_limit": limit})
    except Exception as e:
        logger.error(f"executive summary refresh failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/social-sentiment")
@limiter.limit("60 per minute")
def api_social_sentiment():
    """Return cached social-media sentiment for all carriers."""
    rows = get_social_sentiment(db_path=_db_path())
    if not rows:
        return jsonify({"error": "not_generated_yet"}), 404
    return jsonify(rows)


@app.route("/api/social-sentiment/refresh", methods=["POST"])
@require_scrape_auth
def api_social_sentiment_refresh():
    """Trigger manual regeneration of social sentiment for all carriers."""
    ok, used, limit = _check_refresh_quota()
    if not ok:
        return jsonify({"error": f"מכסת הרענון החודשית הגיעה לסיום ({used}/{limit}). מחכים לחודש הבא.", "quota_used": used, "quota_limit": limit}), 429
    try:
        generate_social_sentiment()
        rows = get_social_sentiment(db_path=_db_path())
        generated_at = rows[0]["generated_at"] if rows else None
        _log_refresh('social_sentiment')
        return jsonify({"status": "ok", "generated_at": generated_at, "quota_used": used + 1, "quota_limit": limit})
    except Exception as exc:
        logger.error(f"social sentiment refresh failed: {exc}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/banners")
@limiter.limit("60 per minute")
def api_banners():
    """Return metadata for all carrier homepage banner screenshots."""
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    result = []
    for carrier, meta in CARRIER_DISPLAY.items():
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
    return _public_cache(jsonify(_filter_hidden_carrier(result)), 600)


@app.route("/api/store-banners")
@limiter.limit("60 per minute")
def api_store_banners():
    """Return metadata for carrier e-store banner screenshots."""
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    result = []
    for carrier, meta in CARRIER_STORE_DISPLAY.items():
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
    return _public_cache(jsonify(_filter_hidden_carrier(result)), 600)


@app.route("/api/global-banners")
@limiter.limit("60 per minute")
def api_global_banners():
    """Return metadata for global eSIM provider homepage banner screenshots.

    Providers + homepage URLs come from scraper.GLOBAL_BANNER_URLS; display
    name/color come from _GUEST_PROVIDER_META (same source that drives the
    provider chips). Files are {provider}_global.png in data/banners/.
    """
    from scraper import GLOBAL_BANNER_URLS
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
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
        meta = _GUEST_PROVIDER_META.get(provider, {})
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
    return _public_cache(jsonify(_filter_hidden_carrier(result)), 600)


@app.route("/api/archive")
@limiter.limit("60 per minute")
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
    hidden = _hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({"error": "carrier not available for this workspace"}), 403

    plan_rows = get_archive_plans(carrier, date_str, db_path=_db_path())
    banner_rows = get_archive_banners(carrier, date_str, db_path=_db_path())

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


@app.route("/api/archive/date-range")
@limiter.limit("60 per minute")
def api_archive_date_range():
    """Returns the earliest and latest dates available in the archive."""
    return jsonify(get_archive_date_range(db_path=_db_path()))


_ARCHIVE_BANNER_ROOT = os.path.realpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "archive", "banners"
))


@app.route("/archive-banners/<path:filepath>")
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


@app.route("/api/content-changes")
@limiter.limit("60 per minute")
def api_content_changes():
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except (ValueError, TypeError):
        limit = 50
    changes = get_content_changes(limit=limit, db_path=_db_path())
    return _public_cache(jsonify(_filter_hidden_carrier(changes)), 600)


@app.route("/api/scrape-resellers-now")
@require_api_key_or_query
def api_scrape_resellers_now():
    """Manual trigger: scrape all below-the-line reseller sources, diff + save.

    Same logic as the daily 08:15 job — changes land in reseller_changes and
    surface in the next morning digest's "מתחת לקו" section.
    """
    try:
        return jsonify({"status": "ok", "modules": scrape_resellers_job()})
    except Exception as e:
        logger.error(f"scrape-resellers-now failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/scrape-content-now")
@require_api_key_or_query
def api_scrape_content_now():
    """Manual trigger: scrape content services, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_content_plans, save_content_changes, filter_already_notified
        from change_detector import detect_content_changes
        old_plans = get_content_plans(db_path=_db_path())
        new_plans = sc.scrape_all_content()
        changes = detect_content_changes(old_plans, new_plans)
        save_content_plans(new_plans, db_path=_db_path())
        changes = filter_already_notified(changes, 'content_changes', key_field='service', db_path=_db_path())
        if changes:
            save_content_changes(changes, db_path=_db_path())
        arc.archive_content_plans(new_plans)
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-content-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@app.route("/api/scrape-now")
@require_api_key_or_query
def api_scrape_now():
    """Manual trigger for testing. Debug endpoint."""
    try:
        import scraper as sc
        from db import save_plans, save_changes, filter_already_notified
        from change_detector import detect_changes
        from notifier import format_message

        new_plans = sc.scrape_all()
        old_plans = get_plans(db_path=_db_path())
        changes = detect_changes(old_plans, new_plans)
        save_plans(new_plans, db_path=_db_path())
        changes = filter_already_notified(changes, 'changes', db_path=_db_path())
        if changes:
            save_changes(changes, db_path=_db_path())
        arc.archive_domestic_plans(new_plans)
        from notifier import alert_missing_terms
        alert_missing_terms(changes, new_plans, 'plans', load_config())
        try:
            from notifier import notify_mobile_price_drops
            notify_mobile_price_drops(changes, load_config(), db_path=_db_path())
        except Exception as e:
            logger.warning(f"mobile price-drop push failed: {e}")
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


# ── Price Alerts Routes ────────────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def api_get_alerts():
    """Return alerts owned by the authenticated user.
    Identity is taken from the verified JWT; API-key callers MUST pass
    ?user_email= explicitly. Unscoped queries (which would expose every
    user's alerts) are rejected."""
    user_email = _current_user_email()
    if user_email is None:
        # Server-to-server (API key) — explicit user_email is required.
        user_email = (request.args.get("user_email") or "").strip().lower() or None
        if not user_email:
            return jsonify({"error": "user_email required for API-key callers"}), 400
    alerts = get_price_alerts(user_email=user_email, db_path=_db_path())
    return jsonify(alerts)


@app.route("/api/alerts", methods=["POST"])
@require_auth
@limiter.limit("20 per minute")
def api_create_alert():
    data = request.get_json(force=True) or {}
    user_email = _current_user_email()
    if user_email is None:
        # Server-to-server must provide the target user explicitly
        user_email = (data.get("user_email") or "").strip().lower()
        if not user_email:
            return jsonify({"error": "user_email required for API-key callers"}), 400
    try:
        save_price_alert(
            user_email=user_email,
            tab=data.get("tab", "domestic"),
            carrier=data.get("carrier", ""),
            plan_pattern=data.get("plan_pattern", ""),
            threshold=float(data.get("threshold", 0)),
            db_path=_db_path()
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


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
@require_auth
def api_delete_alert(alert_id):
    """Delete an alert. JWT callers can only delete their own alerts;
    API-key callers MUST pass ?user_email= so the delete remains scoped
    (otherwise an unscoped delete bypasses the per-user IDOR check)."""
    user_email = _current_user_email()
    if user_email is None:
        user_email = (request.args.get("user_email") or "").strip().lower() or None
        if not user_email:
            return jsonify({"error": "user_email required for API-key callers"}), 400
    deleted = delete_price_alert(alert_id, user_email=user_email, db_path=_db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


# ── Watchlist (per-user starred plans) ────────────────────────────────────

@app.route("/api/watchlist", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def api_get_watchlist():
    from db import get_watchlist as _gwl
    user_email = _current_user_email()
    if not user_email:
        return jsonify([])
    return jsonify(_gwl(user_email, db_path=_db_path()))


@app.route("/api/watchlist", methods=["POST"])
@require_auth
@limiter.limit("30 per minute")
def api_add_to_watchlist():
    from db import add_to_watchlist as _awl
    user_email = _current_user_email()
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
        _awl(user_email, carrier, plan_name, plan_type, db_path=_db_path())
        _track_user_action(user_email, 'watchlist_added', {
            "carrier": carrier, "plan_name": plan_name, "plan_type": plan_type,
        })
        return jsonify({"status": "added"}), 201
    except Exception as e:
        logger.error(f"add watchlist failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/watchlist", methods=["DELETE"])
@require_auth
def api_remove_from_watchlist():
    from db import remove_from_watchlist as _rwl
    user_email = _current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True) or {}
    deleted = _rwl(user_email, data.get('carrier', ''), data.get('plan_name', ''),
                   data.get('plan_type', ''), db_path=_db_path())
    if deleted:
        _track_user_action(user_email, 'watchlist_removed', {
            "carrier": data.get('carrier', ''), "plan_name": data.get('plan_name', ''),
        })
    return jsonify({"status": "deleted", "rows": deleted})


# ── Saved Views (per-user filter presets) ─────────────────────────────────

@app.route("/api/saved-views", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def api_get_saved_views():
    from db import get_saved_views as _gsv
    user_email = _current_user_email()
    if not user_email:
        return jsonify([])
    return jsonify(_gsv(user_email, db_path=_db_path()))


@app.route("/api/saved-views", methods=["POST"])
@require_auth
@limiter.limit("20 per minute")
def api_create_saved_view():
    from db import save_view as _sv
    user_email = _current_user_email()
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
        view_id = _sv(user_email, name, json.dumps(filters, ensure_ascii=False), db_path=_db_path())
        if filters.get('kind') == 'compare':
            _track_user_action(user_email, 'comparison_saved', {
                "name": name, "count": len(filters.get('plans') or []),
            })
        return jsonify({"status": "saved", "id": view_id}), 201
    except Exception as e:
        logger.error(f"save view failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/saved-views/<int:view_id>", methods=["DELETE"])
@require_auth
def api_delete_saved_view(view_id):
    from db import delete_saved_view as _dsv
    user_email = _current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    deleted = _dsv(view_id, user_email, db_path=_db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


# ── User activity tracking (super-admin dashboard) ─────────────────────────

_ACTIVITY_CLIENT_EVENTS = {'login', 'page_view', 'search', 'export'}


def _track_user_action(user_email, event_type, details=None):
    """Best-effort server-side activity log for a user action (alert / watchlist
    / comparison). Skips super-admins (operator's own activity is never
    recorded) and never raises into the calling request handler."""
    if not user_email:
        return
    try:
        ctx = _get_user_context(user_email)
        if ctx.get('role') == 'super_admin':
            return
        log_user_activity(
            user_email=user_email,
            event_type=event_type,
            workspace_id=ctx.get('workspace_id'),
            details=json.dumps(details, ensure_ascii=False) if details else None,
            user_agent=request.headers.get('User-Agent'),
            db_path=_db_path(),
        )
    except Exception:
        pass


@app.route("/api/activity", methods=["POST"])
@require_auth
@limiter.limit("240 per minute")
def api_track_activity():
    """Best-effort client activity beacon (login / page_view). Identity is
    ALWAYS derived server-side from the JWT — any client-supplied identity is
    ignored. Super-admins are intentionally NOT recorded. Action events
    (alerts/watchlist/comparisons) are logged server-side in their own
    handlers, not here. Returns 204 and never hard-errors."""
    user_email = _current_user_email()
    if not user_email:
        return ("", 204)  # API-key-only caller without a JWT — nothing to attribute
    ctx = _get_user_context(user_email)
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
    log_user_activity(
        user_email=user_email,
        event_type=event_type,
        workspace_id=ctx.get('workspace_id'),
        path=path,
        details=details,
        user_agent=request.headers.get('User-Agent'),
        db_path=_db_path(),
    )
    return ("", 204)


# ── Plan annotations (team notes) ──────────────────────────────────────────

@app.route("/api/annotations", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def api_get_annotations():
    """Return annotations for current workspace, optionally filtered to a plan."""
    from db import get_annotations as _ga
    user_email_for_ctx = _current_user_email() or ''
    ctx = _get_user_context(user_email_for_ctx) if user_email_for_ctx else {}
    ws_id = ctx.get('workspace_id')
    carrier   = request.args.get('carrier')
    plan_name = request.args.get('plan_name')
    plan_type = request.args.get('plan_type')
    return jsonify(_ga(ws_id, carrier=carrier, plan_name=plan_name, plan_type=plan_type, db_path=_db_path()))


@app.route("/api/annotations/counts", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def api_annotation_counts():
    """Return annotation counts grouped by plan key for the workspace."""
    from db import get_annotation_counts as _gac
    user_email_for_ctx = _current_user_email() or ''
    ctx = _get_user_context(user_email_for_ctx) if user_email_for_ctx else {}
    ws_id = ctx.get('workspace_id')
    return jsonify(_gac(ws_id, db_path=_db_path()))


@app.route("/api/annotations", methods=["POST"])
@require_auth
@limiter.limit("30 per minute")
def api_add_annotation():
    from db import add_annotation as _aa
    user_email = _current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    ctx = _get_user_context(user_email)
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
        new_id = _aa(ws_id, user_email, carrier, plan_name, plan_type, note, db_path=_db_path())
        _track_user_action(user_email, 'annotation_added', {"carrier": carrier, "plan_name": plan_name})
        return jsonify({"status": "added", "id": new_id}), 201
    except Exception as exc:
        logger.error(f"add annotation failed: {exc}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/annotations/<int:ann_id>", methods=["PATCH"])
@require_auth
def api_update_annotation(ann_id):
    from db import update_annotation as _ua
    user_email = _current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    ctx = _get_user_context(user_email)
    ws_id = ctx.get('workspace_id')
    data = request.get_json(force=True) or {}
    note = (data.get('note') or '').strip()
    if not note or len(note) > 1000:
        return jsonify({"error": "note required (max 1000 chars)"}), 400
    updated = _ua(ann_id, ws_id, user_email, note, db_path=_db_path())
    if updated == 0:
        return jsonify({"error": "not found or not author"}), 404
    return jsonify({"status": "updated"})


@app.route("/api/annotations/<int:ann_id>", methods=["DELETE"])
@require_auth
def api_delete_annotation(ann_id):
    from db import delete_annotation as _da
    user_email = _current_user_email()
    if not user_email:
        return jsonify({"error": "auth required"}), 401
    ctx = _get_user_context(user_email)
    ws_id = ctx.get('workspace_id')
    deleted = _da(ann_id, ws_id, user_email, db_path=_db_path())
    if deleted == 0:
        return jsonify({"error": "not found or not author"}), 404
    return jsonify({"status": "deleted"})


# ── Provider coupons (manually curated discount codes) ────────────────────

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


@app.route("/api/coupons", methods=["GET"])
@limiter.limit("120 per minute")
def api_get_coupons():
    """Public: active, non-expired coupons. Cached for 5 min on the client."""
    coupons = get_active_coupons(db_path=_db_path())
    resp = jsonify(coupons)
    return _public_cache(resp, 300)


@app.route("/api/coupons/all", methods=["GET"])
@require_api_key_or_super_admin
def api_get_all_coupons():
    """Admin: every coupon row including inactive / expired."""
    return jsonify(get_all_coupons(db_path=_db_path()))


@app.route("/api/coupons", methods=["POST"])
@require_api_key_or_super_admin
def api_create_coupon():
    data = request.get_json(force=True) or {}
    cleaned, err = _validate_coupon_payload(data, partial=False)
    if err:
        return jsonify({"error": err}), 400
    try:
        new_id = upsert_coupon(
            cleaned["carrier"], cleaned["code"],
            discount_label=cleaned.get("discount_label"),
            expires_at=cleaned.get("expires_at"),
            source_url=cleaned.get("source_url"),
            is_active=cleaned.get("is_active", True),
            notes=cleaned.get("notes"),
            external_offer_url=cleaned.get("external_offer_url"),
            partner_name=cleaned.get("partner_name"),
            db_path=_db_path(),
        )
        return jsonify({"status": "saved", "id": new_id}), 201
    except Exception as exc:
        logger.error(f"create coupon failed: {exc}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/coupons/<int:coupon_id>", methods=["PATCH"])
@require_api_key_or_super_admin
def api_update_coupon(coupon_id):
    data = request.get_json(force=True) or {}
    cleaned, err = _validate_coupon_payload(data, partial=True)
    if err:
        return jsonify({"error": err}), 400
    if not cleaned:
        return jsonify({"error": "no editable fields supplied"}), 400
    updated = update_coupon(coupon_id, cleaned, db_path=_db_path())
    if updated == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "updated"})


@app.route("/api/coupons/<int:coupon_id>", methods=["DELETE"])
@require_api_key_or_super_admin
def api_delete_coupon(coupon_id):
    deleted = delete_coupon(coupon_id, db_path=_db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


# ── Provider deal CRM (super-admin "סטטוס ספקים" dashboard) ─────────────────

@app.route("/api/provider-deals", methods=["GET"])
@require_api_key_or_super_admin
def api_provider_deals():
    """Provider relationship/commission status, one row per tracked provider.

    Merges the manually curated CRM rows (seed_provider_deals.py) with two LIVE
    signals so the dashboard is always accurate without editing the seed:
      - coupon liveness from provider_coupons (is there a coupon in the air?)
      - affiliate clicks in the last 30d (is a live deal getting traffic?)
    """
    dbp = _db_path()
    deals = get_provider_deals(db_path=dbp)

    # First live (active, non-expired) coupon per carrier.
    coupon_by_carrier = {}
    for c in get_active_coupons(db_path=dbp):
        car = c.get("carrier")
        if car and car not in coupon_by_carrier:
            coupon_by_carrier[car] = c

    # Clicks per provider over the last 30 days (attribution health).
    clicks_by_provider = {}
    try:
        for row in get_affiliate_stats(days=30, db_path=dbp):
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


@app.route("/api/chat", methods=["POST"])
@require_auth
@limiter.limit("10 per minute")
@limiter.limit(_chat_daily_limit, key_func=_chat_user_key)
def api_chat():
    """AI chat over the plans data using Claude API."""
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "no question"}), 400

    # Workspace self-carrier scoping: strip the user's own MVNO from the
    # grounding data AND instruct the model to not mention it. The user is
    # here to learn about competitors, not about themselves.
    hidden_carrier = _hidden_carrier_for_request()

    config = load_config()
    api_key = config.get("anthropic_api_key", "")
    if not api_key:
        return jsonify({"error": "anthropic_api_key missing in config.json"}), 500

    try:
        import requests as _req
        from datetime import datetime

        # ── Build context from DB ──────────────────────────────────────────
        def fmt_price(p):
            if p is None: return "—"
            try: return f"₪{float(p):.2f}".rstrip('0').rstrip('.')
            except (TypeError, ValueError): return f"₪{p}"

        def fmt_gb(g):
            if g is None: return "ללא הגבלה"
            try: g = float(g)
            except (TypeError, ValueError): return str(g)
            return f"{round(g*1024)}MB" if g < 1 else f"{g}GB"

        # Carrier ID → display name (used in context so AI resolves aliases correctly)
        # MUST stay in sync with mass-market-app/src/data/carrierLabels.js
        _CARRIER_NAMES = {
            # Domestic
            'partner': 'פרטנר', 'pelephone': 'פלאפון', 'hotmobile': 'הוט מובייל',
            'cellcom': 'סלקום', 'mobile019': '019', 'xphone': 'XPhone',
            'wecom': 'We-Com', 'neptucom': 'Neptucom', 'golan': 'גולן טלקום',
            'rami_levy': 'רמי לוי תקשורת',
            # Global eSIM
            'tuki': 'Tuki', 'terminalesim': 'Terminal eSIM', 'gigsky': 'GigSky',
            'esimgenius': 'eSIM Genius', 'nisim': 'Nisim eSIM', 'esimax': 'eSIM Max',
            'venterrasim': 'VenterraSIM', 'simzol': 'Simzol',
            'airalo': 'Airalo', 'airalo_local': 'Airalo', 'airalo_regional': 'Airalo',
            'pelephone_global': 'GlobalSIM', 'esimo': 'eSIMo', 'simtlv': 'SimTLV',
            'world8': '8 World', 'xphone_global': 'XPhone Global', 'saily': 'Saily',
            'holafly': 'Holafly', 'esimio': 'eSIM.io', 'sparks': 'Sparks',
            'voye': 'VOYE', 'orbit': 'Orbit', 'travelsim': 'Travel Sim',
            'gomoworld': 'GoMoWorld', 'tasim': 'Tasim', 'maya': 'Maya Mobile',
            'bcengi': 'Bcengi', 'esim70': 'eSIM70', 'jetpack': 'Jetpack', 'breez': 'Breeze',
            'bytesim': 'ByteSim', 'besim': 'Besim', 'seven_g': '7G',
            'bestconnect': 'Best Connect', 'esimplus': 'eSIM Plus', 'bnesim': 'BNESIM',
            'yesim': 'Yesim', 'nomad': 'Nomad', 'ubigi': 'Ubigi', 'alosim': 'aloSIM',
            # USA tourist-plan operators (נוחתים בארה"ב) — mirror of USA_LABELS
            # in carrierLabels.js
            'tmobile_prepaid': 'T-Mobile Prepaid', 'att_prepaid': 'AT&T Prepaid',
            'verizon_prepaid': 'Verizon Prepaid', 'mint': 'Mint Mobile',
            'ultra': 'Ultra Mobile', 'lyca_usa': 'Lycamobile USA', 'tello': 'Tello',
            'metro': 'Metro by T-Mobile', 'simple_mobile': 'Simple Mobile',
            'cricket': 'Cricket Wireless', 'h2o': 'H2O Wireless',
            'visible': 'Visible', 'us_mobile': 'US Mobile',
            'red_pocket': 'Red Pocket', 'straight_talk': 'Straight Talk',
            'total_wireless': 'Total Wireless', 'boost': 'Boost Mobile',
        }
        def _cn(carrier):
            return _CARRIER_NAMES.get(carrier, carrier)

        lines = [
            "אתה עוזר נתונים עבור מערכת השוואת חבילות סלולר ישראלית.",
            "להלן הנתונים הנוכחיים מהמסד נתונים. ענה בעברית, בצורה תמציתית וברורה.",
            f"תאריך עדכון: {datetime.now().strftime('%d/%m/%Y')}",
            "שמות ספקים (מזהה=שם מוצג): airalo/airalo_local/airalo_regional=Airalo, "
            "pelephone_global=GlobalSIM, xphone_global=XPhone Global, mobile019=019, "
            "rami_levy=רמי לוי תקשורת, gomoworld=GoMoWorld=Gomo, world8=8 World, simtlv=SimTLV, "
            "esimio=eSIM.io, maya=Maya Mobile, travelsim=Travel Sim, neptucom=Neptucom.",
        ]
        if hidden_carrier:
            lines.append(
                f"חשוב: המשתמש הוא נציג של {_CARRIER_NAMES.get(hidden_carrier, hidden_carrier)}. "
                f"אל תתייחס לחבילות או לנתונים של {_CARRIER_NAMES.get(hidden_carrier, hidden_carrier)} "
                f"בתשובותיך — התמקד רק במתחרים שלהם."
            )
        lines.append("")

        # Domestic plans — reuse the shared 5-min plan cache (same key the list
        # endpoints use) instead of a full uncached DB read on every chat message.
        domestic = _filter_hidden_carrier(_cached_plans('plans', lambda: get_plans(db_path=_db_path())))
        if domestic:
            lines.append("## חבילות ביתיות (ישראל)")
            for p in domestic:
                lines.append(
                    f"  {_cn(p['carrier'])} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{fmt_gb(p.get('data_gb'))} | {p.get('minutes','')} דקות"
                    + (f" | extras: {';'.join(p['extras'])}" if p.get('extras') else "")
                )

        # Abroad plans
        abroad = _filter_hidden_carrier(_cached_plans('abroad_plans', lambda: get_abroad_plans(db_path=_db_path())))
        if abroad:
            lines.append("")
            lines.append("## חבילות חו\"ל")
            for p in abroad:
                lines.append(
                    f"  {_cn(p['carrier'])} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{p.get('days','')} ימים | {fmt_gb(p.get('data_gb'))}"
                    + (f" | extras: {';'.join(p['extras'])}" if p.get('extras') else "")
                )

        # Global plans — 1 cheapest plan per carrier+destination, up to 40 dest per carrier
        from collections import defaultdict as _dd
        _all_global = _filter_hidden_carrier(_cached_plans('global_plans', lambda: get_global_plans(db_path=_db_path())))
        _by_carrier_dest = _dd(lambda: _dd(list))
        for _p in _all_global:
            _dest = (_p.get('extras') or [''])[0] or 'global'
            _by_carrier_dest[_p['carrier']][_dest].append(_p)
        global_plans = []
        for _carrier in sorted(_by_carrier_dest):
            _dest_cheapest = []
            for _dest, _dplans in _by_carrier_dest[_carrier].items():
                _cheapest = min(_dplans, key=lambda x: float(x.get('price') or 9999))
                _dest_cheapest.append(_cheapest)
            _dest_cheapest.sort(key=lambda x: float(x.get('price') or 9999))
            global_plans.extend(_dest_cheapest[:40])
        if global_plans:
            lines.append("")
            lines.append("## חבילות גלובליות (eSIM)")
            for p in global_plans:
                lines.append(
                    f"  {_cn(p['carrier'])} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{p.get('days','')} ימים | {fmt_gb(p.get('data_gb'))}"
                    + (f" | יעד: {p['extras'][0]}" if p.get('extras') else "")
                )

        # Content services
        content = _filter_hidden_carrier(get_content_plans(db_path=_db_path()))
        if content:
            lines.append("")
            lines.append("## שירותי תוכן")
            for p in content:
                lines.append(
                    f"  {p['service']} | {_cn(p['carrier'])} | {p.get('price','')} | "
                    f"ניסיון: {p.get('free_trial','')}"
                )

        # Recent changes (last 90 days)
        all_changes = []
        for ch in _filter_hidden_carrier(get_changes(limit=200, db_path=_db_path())):
            all_changes.append(("ביתי", ch))
        for ch in _filter_hidden_carrier(get_abroad_changes(limit=200, db_path=_db_path())):
            all_changes.append(("חו\"ל", ch))
        for ch in _filter_hidden_carrier(get_global_changes(limit=200, db_path=_db_path())):
            all_changes.append(("גלובלי", ch))
        for ch in _filter_hidden_carrier(get_content_changes(limit=200, db_path=_db_path())):
            all_changes.append(("תוכן", ch))

        if all_changes:
            lines.append("")
            lines.append("## היסטוריית שינויים (עד 200 אחרונים לכל קטגוריה)")
            for tab, ch in all_changes:
                carrier = ch.get("carrier", ch.get("service", ""))
                lines.append(
                    f"  [{tab}] {ch.get('changed_at','')[:10]} | {carrier} | "
                    f"{ch.get('plan_name', ch.get('service',''))} | "
                    f"{ch.get('change_type','')} | {ch.get('old_val','')} → {ch.get('new_val','')}"
                )

        context = "\n".join(lines)

        # ── Call Anthropic API ─────────────────────────────────────────────
        # Sonnet has dramatically better Hebrew than Haiku; the latency/cost
        # premium is justified for business-facing reports. Caller can request
        # 'haiku' explicitly for fast/cheap quick-fire chat.
        ALLOWED_MODELS = {
            'sonnet': 'claude-sonnet-4-6',
            'haiku':  'claude-haiku-4-5-20251001',
        }
        requested = (data.get('model') or '').strip().lower()
        model = ALLOWED_MODELS.get(requested, 'claude-sonnet-4-6')

        # Hebrew-quality system prompt: prepend strict language rules to the context
        hebrew_rules = (
            "כללי כתיבה (חובה לעקוב אחריהם):\n"
            "1. כתוב אך ורק בעברית תקנית. אל תמציא מילים שאינן קיימות במילון העברי.\n"
            "2. אל תתרגם ישירות מאנגלית — נסח מחדש בעברית טבעית. במקרה של ספק, השאר את המונח באנגלית במקום לתרגם בצורה שגויה.\n"
            "3. השתמש במילים מלאות, ללא קיצורים שגויים או הברות חסרות (למשל: 'שיחות' ולא 'שיח'; 'צרכנים' ולא 'צרים'; 'בכורה' ולא 'בחור').\n"
            "4. פעמיים בדוק כל משפט שכתבת — אם משפט נשמע מוזר, נסח אותו מחדש.\n"
            "5. השתמש במונחי הענף הסלולרי הנכונים: 'חבילת גלישה', 'דקות שיחה', 'הודעות SMS', 'גלישה בחו\"ל', 'תנאי הצטרפות'.\n"
            "6. אם אין לך מידע ודאי על משהו — אל תמציא, ציין במפורש שהמידע לא זמין.\n\n"
        )
        full_system = hebrew_rules + context

        resp = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "system": [
                    {
                        "type": "text",
                        "text": full_system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [{"role": "user", "content": question}],
            },
            timeout=45,
        )
        resp.raise_for_status()
        body = resp.json()
        usage = body.get("usage", {}) or {}
        logger.info(
            "chat ok: model=%s in=%s cache_read=%s cache_write=%s out=%s",
            model,
            usage.get("input_tokens"),
            usage.get("cache_read_input_tokens"),
            usage.get("cache_creation_input_tokens"),
            usage.get("output_tokens"),
        )
        _record_claude_call("chat", model, body, user_email=_caller_email())
        answer = body["content"][0]["text"]
        _track_user_action(_current_user_email(), 'chat_used', {"model": model})
        return jsonify({"answer": answer, "model": model})

    except Exception as e:
        logger.error(f"chat failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@app.route("/api/push/vapid-public-key")
def api_vapid_public_key():
    return jsonify({"publicKey": load_config().get("vapid_public_key", "")})


# ── Auth session (httpOnly cookie) ─────────────────────────────────────────

@app.route("/api/auth/session", methods=["POST"])
@limiter.limit("20 per minute")
def api_auth_session():
    """Receive a valid Supabase JWT from the frontend and persist it as an httpOnly cookie.
    The cookie is used by Flask to authenticate API requests without exposing
    the token to JavaScript (mitigates XSS-based token theft)."""
    data = request.get_json(force=True) or {}
    token = data.get("access_token", "").strip()
    if not token:
        return jsonify({"error": "access_token required"}), 400
    payload = _verify_supabase_jwt(token)
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


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Clear the httpOnly auth cookie on logout."""
    resp = make_response(jsonify({"status": "ok"}))
    resp.set_cookie("auth_token", "", httponly=True, secure=True,
                    samesite="None", max_age=0, path="/api/")
    return resp


@app.route("/api/push/subscribe", methods=["POST"])
@require_auth
@limiter.limit("10 per minute")
def api_push_subscribe():
    from db import save_push_subscription
    data = request.get_json(force=True) or {}
    endpoint = data.get("endpoint")
    p256dh   = data.get("keys", {}).get("p256dh")
    auth     = data.get("keys", {}).get("auth")
    if not all([endpoint, p256dh, auth]):
        return jsonify({"error": "missing fields"}), 400
    user_email = _current_user_email()
    if user_email is None:
        # Server-to-server subscriptions must name their owner
        user_email = (data.get("user_email") or "").strip().lower() or None
    # Resolve the carrier this subscription should not receive push for
    hidden_carrier = None
    if user_email:
        ctx = _get_user_context(user_email)
        ws = ctx.get('workspace') or {}
        if ws.get('hide_self_carrier') and ws.get('mvno_carrier'):
            hidden_carrier = ws['mvno_carrier']
    save_push_subscription(endpoint, p256dh, auth, user_email=user_email,
                           hidden_carrier=hidden_carrier, db_path=_db_path())
    return jsonify({"status": "subscribed"}), 201


@app.route("/api/push/unsubscribe", methods=["DELETE"])
@require_auth
@limiter.limit("10 per minute")
def api_push_unsubscribe():
    from db import delete_push_subscription
    data = request.get_json(force=True) or {}
    endpoint = data.get("endpoint")
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400
    # JWT callers can only unsubscribe endpoints they own; API-key can unsubscribe any
    user_email = _current_user_email()
    deleted = delete_push_subscription(endpoint, user_email=user_email, db_path=_db_path())
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "unsubscribed"}), 200


@app.route("/api/push/test")
@require_api_key
def api_push_test():
    """Debug: send a test push notification to all subscribed devices."""
    config = load_config()
    from notifier import send_push_notifications
    fake = [{"carrier": "partner", "plan_name": "טסט", "change_type": "price_change",
             "old_val": 100, "new_val": 90}]
    n = send_push_notifications(fake, config, _db_path())
    return jsonify({"sent": n})


# ── User management (Supabase) ────────────────────────────────────────────

@app.route("/api/my-role")
@require_auth
@limiter.limit("60 per minute")
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
    return jsonify({"role": _get_user_context(email)["role"]})


@app.route("/api/my-preferences", methods=["PATCH"])
@require_auth
@limiter.limit("20 per minute")
def api_update_my_preferences():
    """Update per-user preferences. Currently supports: {digest_opt_out: bool}."""
    email = _current_user_email()
    if not email:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True) or {}
    if 'digest_opt_out' not in data:
        return jsonify({"error": "no updatable fields provided"}), 400
    opt_out = bool(data['digest_opt_out'])
    try:
        conn = _supabase_conn()
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


@app.route("/api/my-context")
@require_auth
@limiter.limit("60 per minute")
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
    payload = getattr(g, 'jwt_payload', None)
    if not payload:
        return jsonify({"role": "viewer", "workspace_id": None, "workspace": None})
    email = (payload.get('email') or '').strip().lower()
    if not email:
        return jsonify({"role": "viewer", "workspace_id": None, "workspace": None})
    return jsonify(_get_user_context(email))


@app.route("/api/contact", methods=["POST"])
@require_auth
@limiter.limit("3 per minute")
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

    from_email = _current_user_email() or ''
    if not from_email:
        # API-key auth short-circuited require_auth; still try the Bearer JWT for the email.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            _p = _verify_supabase_jwt(auth_header[7:])
            if _p:
                from_email = (_p.get('email') or '').strip().lower()
    if not from_email:
        return jsonify({"error": "authenticated email required"}), 401

    # Best-effort workspace label for the admin's inbox preview
    ctx = _get_user_context(from_email)
    ws_name = (ctx.get('workspace') or {}).get('name') or ''

    try:
        from notifier import send_contact_email
        ok = send_contact_email(from_email, ws_name, message, load_config())
        if not ok:
            return jsonify({"error": "failed to send — check email configuration"}), 500
        logger.info(f"AUDIT contact_sent: from={from_email} ws={ws_name!r}")
        return jsonify({"status": "sent"})
    except Exception as e:
        logger.error(f"api_contact failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/users")
@require_admin
@limiter.limit("20 per minute")
def api_get_users():
    """List users from Supabase via direct DB connection.

    Cross-tenant scoping: a workspace `admin` sees only users assigned to their
    OWN workspace; super_admin (and the trusted server-admin key) get the full
    cross-workspace list. Without this scope, any workspace admin could read
    every user's email + role across all carrier workspaces — a cross-tenant
    info leak. Mirrors the ownership pattern in _can_manage_workspace_users.
    """
    try:
        # Decide scope from the caller's role. The dedicated server-admin key
        # (_is_server_admin_request) is the trusted MOCA operator → full list,
        # same as super_admin. scope_ws_id is None when the full list is allowed.
        scope_ws_id = None
        if not _is_server_admin_request():
            ctx = _get_user_context(_current_user_email())
            if ctx.get('role') != 'super_admin':
                scope_ws_id = ctx.get('workspace_id')
                if not scope_ws_id:
                    # Workspace admin with no workspace assigned: show nothing
                    # rather than leaking the global user list.
                    return jsonify([])

        conn = _supabase_conn()
        cur = conn.cursor()
        if scope_ws_id is None:
            cur.execute("""
                SELECT u.id, u.email, u.created_at, COALESCE(r.role, 'viewer') as role, u.last_sign_in_at
                FROM auth.users u
                LEFT JOIN public.user_roles r ON u.id = r.user_id
                ORDER BY u.created_at DESC
            """)
        else:
            cur.execute("""
                SELECT u.id, u.email, u.created_at, COALESCE(r.role, 'viewer') as role, u.last_sign_in_at
                FROM public.user_roles r
                JOIN auth.users u ON u.id = r.user_id
                WHERE r.workspace_id = %s
                ORDER BY u.created_at DESC
            """, (scope_ws_id,))
        users = [{'id': str(row[0]), 'email': row[1], 'created_at': str(row[2]), 'role': row[3], 'last_sign_in_at': str(row[4]) if row[4] else None} for row in cur.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        logger.error(f"get users failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/users", methods=["POST"])
@require_super_admin
@limiter.limit("10 per minute")
def api_create_user():
    """Create a new user directly in Supabase Postgres. super_admin / server-admin-key ONLY.

    Provisions the auth identity by writing auth.users + auth.identities + a
    (workspace-less) public.user_roles row in one transaction — the same thing
    GoTrue's admin API does internally, with the email pre-confirmed.

    We deliberately do NOT use the public /auth/v1/signup flow anymore: it sends
    a confirmation email on every create (which we then redundantly force-
    confirmed anyway), and Supabase's shared email sender rate-limits those to a
    few per hour — so onboarding more than ~2 users in a row failed with
    "email rate limit exceeded" (HTTP 429 -> generic "Failed to create user").
    Direct provisioning sends NO email; onboarding mail is our own Welcome email,
    fired by the workspace-assign step (send_welcome_email).

    Restricted to the MOCA operator — a workspace `admin` must never mint
    accounts (the role row here has no workspace_id, i.e. a global/workspace-less
    role, and there's no cross-tenant ownership check). Workspace admins add
    people to their OWN workspace via POST /api/workspaces/<id>/users (assign an
    existing user) or an invite link — both gated by _can_manage_workspace_users.
    """
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role', 'viewer')
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if role not in ('admin', 'viewer'):
        # Never allow minting a super_admin via the API — that role is DB-only.
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    conn = None
    try:
        import uuid as _uuid
        user_id = str(_uuid.uuid4())
        conn = _supabase_conn()
        cur = conn.cursor()
        # Reject duplicates up front (mirrors GoTrue's 422 with a clear message).
        cur.execute("SELECT 1 FROM auth.users WHERE LOWER(email) = %s", (email,))
        if cur.fetchone():
            conn.close()
            return jsonify({"error": f"user {email} already exists"}), 409
        # 1) auth.users — email pre-confirmed; confirmed_at is a GENERATED column
        #    (omit it); password hashed with bcrypt (cost 10) via pgcrypto.
        cur.execute("""
            INSERT INTO auth.users (
                instance_id, id, aud, role, email, encrypted_password,
                email_confirmed_at, confirmation_token, recovery_token,
                email_change_token_new, email_change, email_change_token_current,
                phone_change, phone_change_token, reauthentication_token,
                raw_app_meta_data, raw_user_meta_data,
                created_at, updated_at, email_change_confirm_status,
                is_sso_user, is_anonymous
            ) VALUES (
                '00000000-0000-0000-0000-000000000000', %s,
                'authenticated', 'authenticated', %s, crypt(%s, gen_salt('bf', 10)),
                now(), '', '', '', '', '', '', '', '',
                '{"provider":"email","providers":["email"]}'::jsonb,
                jsonb_build_object('sub', %s, 'email', %s, 'email_verified', true, 'phone_verified', false),
                now(), now(), 0, false, false
            )
        """, (user_id, email, password, user_id, email))
        # 2) auth.identities — the `email` column is GENERATED (omit it).
        cur.execute("""
            INSERT INTO auth.identities (
                id, provider_id, user_id, identity_data, provider,
                last_sign_in_at, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), %s, %s,
                jsonb_build_object('sub', %s, 'email', %s, 'email_verified', true, 'phone_verified', false),
                'email', now(), now(), now()
            )
        """, (user_id, user_id, user_id, email))
        # 3) global (workspace-less) role row — workspace assignment happens later.
        cur.execute("INSERT INTO public.user_roles (user_id, role) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role", (user_id, role))
        conn.commit()
        conn.close()
        logger.info(f"AUDIT create_user: email={email!r} role={role!r} new_user_id={user_id!r} by_ip={request.remote_addr}")
        return jsonify({"status": "created", "user_id": user_id}), 201
    except Exception as e:
        try:
            if conn:
                conn.rollback()
                conn.close()
        except Exception:
            pass
        logger.error(f"create user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/users/<user_id>", methods=["DELETE"])
@require_super_admin
@limiter.limit("10 per minute")
def api_delete_user(user_id):
    """Delete a user from Supabase. super_admin / server-admin-key ONLY.

    Operates on an arbitrary user id with no workspace-ownership check, so a
    workspace `admin` must not reach it — otherwise a Partner admin could delete
    a Cellcom user (cross-tenant). Workspace admins remove members from their own
    workspace via DELETE /api/workspaces/<id>/users/<uid> (gated by
    _can_manage_workspace_users), which only un-assigns within that workspace.
    """
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute('DELETE FROM public.user_roles WHERE user_id = %s', (user_id,))
        cur.execute('DELETE FROM auth.users WHERE id = %s', (user_id,))
        conn.close()
        logger.info(f"AUDIT delete_user: user_id={user_id!r} by_ip={request.remote_addr}")
        return jsonify({"status": "deleted"})
    except Exception as e:
        logger.error(f"delete user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/users/<user_id>/role", methods=["POST"])
@require_super_admin
@limiter.limit("20 per minute")
def api_update_user_role(user_id):
    """Update a user's role. super_admin / server-admin-key ONLY.

    Re-roles an arbitrary user id with no workspace-ownership check, so a
    workspace `admin` must not reach it (cross-tenant: a Partner admin could
    promote/demote a Cellcom user). Workspace admins set a member's role within
    their own workspace via POST /api/workspaces/<id>/users (gated by
    _can_manage_workspace_users). The last-super_admin guard below still applies.
    """
    data = request.get_json(force=True)
    role = data.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be admin or viewer"}), 400
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        # Guard: don't remove the last super_admin. This endpoint can only set
        # admin/viewer, so demoting the final super_admin would lock everyone out
        # of super-admin-only management with no UI path to restore it.
        if _user_is_super_admin(cur, user_id):
            cur.execute("SELECT COUNT(*) FROM public.user_roles WHERE role = 'super_admin'")
            if cur.fetchone()[0] <= 1:
                conn.close()
                return jsonify({"error": "לא ניתן להוריד את ה-super_admin האחרון במערכת — חייב להישאר לפחות אחד."}), 409
        cur.execute("INSERT INTO public.user_roles (user_id, role) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET role = %s", (user_id, role, role))
        conn.close()
        logger.info(f"AUDIT update_role: user_id={user_id!r} new_role={role!r} by_ip={request.remote_addr}")
        return jsonify({"status": "updated", "role": role})
    except Exception as e:
        logger.error(f"update role failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/users/<user_id>/password", methods=["POST"])
@require_super_admin
@limiter.limit("20 per minute")
def api_set_user_password(user_id):
    """Set a user's password directly. super_admin / server-admin-key ONLY.

    Admin-driven reset for a user who's locked out — writes the bcrypt hash
    straight to auth.users (same mechanism as api_create_user), so it sends NO
    email and isn't subject to Supabase's email rate limit. The user can sign in
    with the new password immediately. No workspace-ownership check (mirrors the
    other bare /api/users* writes), so it's operator-only; workspace admins
    manage their own team via the workspace endpoints.
    """
    data = request.get_json(force=True) or {}
    password = data.get('password') or ''
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    conn = None
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("UPDATE auth.users SET encrypted_password = crypt(%s, gen_salt('bf', 10)), updated_at = now() WHERE id = %s", (password, user_id))
        updated = cur.rowcount
        conn.close()
        if not updated:
            return jsonify({"error": "user not found"}), 404
        logger.info(f"AUDIT set_user_password: user_id={user_id!r} by_ip={request.remote_addr}")
        return jsonify({"status": "updated"})
    except Exception as e:
        try:
            if conn:
                conn.close()
        except Exception:
            pass
        logger.error(f"set user password failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ── Workspace management (super_admin only) ──────────────────────────────

@app.route("/api/workspaces", methods=["GET"])
@require_super_admin
@limiter.limit("30 per minute")
def api_list_workspaces():
    """List all workspaces with user count, last login, trial info, and monthly refresh count."""
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT w.id, w.slug, w.name, w.mvno_carrier,
                   w.brand_config, w.feature_flags,
                   w.hide_self_carrier, w.active, w.created_at,
                   COUNT(r.user_id) AS user_count,
                   MAX(u.last_sign_in_at) AS last_login,
                   w.trial_ends_at,
                   COALESCE(w.visible_carriers, '[]'::jsonb),
                   COALESCE(w.digest_frequency, 'weekly')
            FROM public.workspaces w
            LEFT JOIN public.user_roles r ON r.workspace_id = w.id
            LEFT JOIN auth.users u ON u.id = r.user_id
            GROUP BY w.id
            ORDER BY w.created_at ASC
        """)
        rows = cur.fetchall()
        conn.close()

        # Fetch monthly refresh counts from SQLite for all workspaces
        from datetime import datetime as _dt, timezone as _tz
        month_prefix = _dt.now(_tz.utc).strftime('%Y-%m')
        all_entries = get_audit_log(limit=2000, db_path=_db_path())
        refresh_by_ws = {}
        for e in all_entries:
            if e['action'] == 'refresh_triggered' and (e['created_at'] or '').startswith(month_prefix):
                ws = e['workspace_id'] or ''
                refresh_by_ws[ws] = refresh_by_ws.get(ws, 0) + 1

        workspaces = []
        for row in rows:
            ws_id = str(row[0])
            trial_ends_at = row[11]
            trial_expired = False
            if trial_ends_at:
                now_utc = _dt.now(_tz.utc)
                te = trial_ends_at if hasattr(trial_ends_at, 'tzinfo') else trial_ends_at.replace(tzinfo=_tz.utc)
                trial_expired = now_utc > te
            vc_raw = row[12]
            vc_list = json.loads(vc_raw) if isinstance(vc_raw, str) else (list(vc_raw) if vc_raw else [])
            workspaces.append({
                'id':                ws_id,
                'slug':              row[1],
                'name':              row[2],
                'mvno_carrier':      row[3],
                'brand_config':      row[4] or {},
                'feature_flags':     row[5] or {},
                'hide_self_carrier': bool(row[6]),
                'active':            bool(row[7]),
                'created_at':        str(row[8]),
                'user_count':        row[9],
                'last_login':        row[10].isoformat() if row[10] else None,
                'trial_ends_at':     trial_ends_at.isoformat() if trial_ends_at else None,
                'trial_expired':     trial_expired,
                'visible_carriers':  vc_list,
                'digest_frequency':  row[13] or 'weekly',
                'refresh_count_month': refresh_by_ws.get(ws_id, 0),
                'refresh_limit':       None if row[1] == 'moca-internal' else MONTHLY_REFRESH_LIMIT,
            })
        return jsonify(workspaces)
    except Exception as e:
        logger.error(f"list workspaces failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/workspaces", methods=["POST"])
@require_super_admin
@limiter.limit("10 per minute")
def api_create_workspace():
    """Create a new workspace. Body: {slug, name, mvno_carrier?, brand_config?,
    feature_flags?, hide_self_carrier?}."""
    data = request.get_json(force=True) or {}
    slug = (data.get('slug') or '').strip().lower()
    name = (data.get('name') or '').strip()
    if not slug or not name:
        return jsonify({"error": "slug and name are required"}), 400
    # slug: lowercase alphanumeric + hyphens, 2–40 chars
    import re as _re
    if not _re.fullmatch(r'[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?', slug):
        return jsonify({"error": "slug must be lowercase alphanumeric/hyphens (2-40 chars)"}), 400
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.workspaces (slug, name, mvno_carrier, brand_config,
                                           feature_flags, hide_self_carrier)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
            RETURNING id
        """, (
            slug, name, data.get('mvno_carrier') or None,
            json.dumps(data.get('brand_config') or {}),
            json.dumps(data.get('feature_flags') or {}),
            bool(data.get('hide_self_carrier', True)),
        ))
        new_id = str(cur.fetchone()[0])
        conn.close()
        actor = _current_user_email() or ''
        log_audit('workspace_created', actor_email=actor, workspace_id=new_id,
                  details=f'slug={slug!r} name={name!r}', db_path=_db_path())
        logger.info(f"AUDIT create_workspace: slug={slug!r} id={new_id} by_ip={request.remote_addr}")
        return jsonify({"status": "created", "id": new_id}), 201
    except Exception as e:
        msg = str(e)
        if 'unique' in msg.lower() or 'duplicate' in msg.lower():
            return jsonify({"error": f"slug '{slug}' already exists"}), 409
        logger.error(f"create workspace failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/workspaces/<workspace_id>", methods=["PATCH"])
@require_super_admin
@limiter.limit("20 per minute")
def api_update_workspace(workspace_id):
    """Update a workspace. Body may include any subset of: name, mvno_carrier,
    brand_config, feature_flags, hide_self_carrier, active."""
    data = request.get_json(force=True) or {}
    allowed = {'name', 'mvno_carrier', 'brand_config', 'feature_flags',
               'hide_self_carrier', 'active', 'trial_ends_at', 'visible_carriers',
               'digest_frequency'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "no updatable fields provided"}), 400
    if 'digest_frequency' in updates and updates['digest_frequency'] not in ('weekly', 'monthly', 'off'):
        return jsonify({"error": "digest_frequency must be weekly/monthly/off"}), 400
    sets, params = [], []
    for k, v in updates.items():
        if k in ('brand_config', 'feature_flags'):
            sets.append(f"{k} = %s::jsonb")
            params.append(json.dumps(v or {}))
        elif k == 'visible_carriers':
            sets.append(f"{k} = %s::jsonb")
            params.append(json.dumps(v or []))
        elif k in ('hide_self_carrier', 'active'):
            sets.append(f"{k} = %s")
            params.append(bool(v))
        else:
            sets.append(f"{k} = %s")
            params.append(v or None)
    params.append(workspace_id)
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            f"UPDATE public.workspaces SET {', '.join(sets)} WHERE id = %s",
            params
        )
        updated = cur.rowcount
        conn.close()
        if updated == 0:
            return jsonify({"error": "workspace not found"}), 404
        actor = _current_user_email() or ''
        log_audit('workspace_updated', actor_email=actor, workspace_id=workspace_id,
                  details=str(list(updates.keys())), db_path=_db_path())
        logger.info(f"AUDIT update_workspace: id={workspace_id} fields={list(updates.keys())}")
        return jsonify({"status": "updated"})
    except Exception as e:
        logger.error(f"update workspace failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/workspaces/<workspace_id>/users", methods=["GET"])
@require_auth
@limiter.limit("30 per minute")
def api_workspace_users(workspace_id):
    """List users assigned to a workspace."""
    if not _can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.created_at, r.role, u.last_sign_in_at
            FROM public.user_roles r
            JOIN auth.users u ON u.id = r.user_id
            WHERE r.workspace_id = %s
            ORDER BY u.email
        """, (workspace_id,))
        users = [{
            'id':              str(row[0]),
            'email':           row[1],
            'created_at':      str(row[2]),
            'role':            row[3],
            'last_sign_in_at': str(row[4]) if row[4] else None,
        } for row in cur.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        logger.error(f"list workspace users failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/workspaces/<workspace_id>/users", methods=["POST"])
@require_auth
@limiter.limit("20 per minute")
def api_assign_workspace_user(workspace_id):
    """Assign an existing Supabase user (by email) to this workspace.
    Body: {email, role: 'admin'|'viewer'} (defaults to 'viewer')."""
    if not _can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    role = data.get('role', 'viewer')
    if not email:
        return jsonify({"error": "email required"}), 400
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        # Look up user id
        cur.execute("SELECT id FROM auth.users WHERE LOWER(email) = %s", (email,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": f"no user with email {email!r}"}), 404
        user_id = row[0]
        # Guard: never demote a super_admin via workspace assignment. user_roles
        # has UNIQUE(user_id), so writing a workspace role here would overwrite
        # their global super_admin — a silent self-lockout (this endpoint only
        # grants admin/viewer, so it can't be reversed from the UI).
        if _user_is_super_admin(cur, user_id):
            conn.close()
            return jsonify({"error": "לא ניתן לשייך משתמש בעל הרשאת super_admin לאזור — הפעולה הייתה מוחקת את ההרשאה הגלובלית שלו. לשינוי מכוון, השתמש בניהול התפקידים."}), 409
        # Verify workspace exists
        cur.execute("SELECT 1 FROM public.workspaces WHERE id = %s", (workspace_id,))
        if not cur.fetchone():
            conn.close()
            return jsonify({"error": "workspace not found"}), 404
        # Upsert role + workspace
        cur.execute("""
            INSERT INTO public.user_roles (user_id, role, workspace_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
              SET role = EXCLUDED.role, workspace_id = EXCLUDED.workspace_id
        """, (user_id, role, workspace_id))
        # Fetch workspace name for welcome email
        cur.execute("SELECT name FROM public.workspaces WHERE id = %s", (workspace_id,))
        ws_row = cur.fetchone()
        ws_name = ws_row[0] if ws_row else ''
        conn.close()
        actor = _current_user_email() or ''
        log_audit('user_assigned', actor_email=actor, target_email=email,
                  workspace_id=workspace_id, details=f'role={role}', db_path=_db_path())
        logger.info(f"AUDIT assign_workspace_user: email={email!r} workspace={workspace_id} role={role}")
        # Send welcome email in background (non-blocking)
        try:
            from notifier import send_welcome_email as _send_welcome
            import threading as _threading
            _threading.Thread(
                target=_send_welcome,
                args=(email, ws_name, role, load_config()),
                daemon=True,
            ).start()
        except Exception as _we:
            logger.warning(f"welcome email skipped: {_we}")
        return jsonify({"status": "assigned", "user_id": str(user_id)}), 201
    except Exception as e:
        logger.error(f"assign workspace user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/workspaces/<workspace_id>/users/<user_id>", methods=["DELETE"])
@require_auth
@limiter.limit("20 per minute")
def api_unassign_workspace_user(workspace_id, user_id):
    """Unassign a user from a workspace by moving them to 'moca-internal' as viewer.
    We never orphan users (NULL workspace_id is reserved for super_admin)."""
    if not _can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT id FROM public.workspaces WHERE slug = 'moca-internal'")
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "moca-internal workspace missing"}), 500
        internal_id = row[0]
        cur.execute("""
            UPDATE public.user_roles
            SET workspace_id = %s, role = 'viewer'
            WHERE user_id = %s AND workspace_id = %s
        """, (internal_id, user_id, workspace_id))
        affected = cur.rowcount
        conn.close()
        if affected == 0:
            return jsonify({"error": "user not in this workspace"}), 404
        actor = _current_user_email() or ''
        log_audit('user_removed', actor_email=actor, target_email=user_id,
                  workspace_id=workspace_id, details=f'moved to moca-internal',
                  db_path=_db_path())
        logger.info(f"AUDIT unassign_workspace_user: user={user_id} from={workspace_id}")
        return jsonify({"status": "moved to moca-internal"})
    except Exception as e:
        logger.error(f"unassign workspace user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ── Workspace invite links ────────────────────────────────────────────────────

@app.route("/api/workspaces/<workspace_id>/invite", methods=["POST"])
@require_auth
@limiter.limit("10 per minute")
def api_create_invite(workspace_id):
    """Create a single-use invite link for this workspace.
    Body: {role: 'admin'|'viewer'} — defaults to 'viewer'."""
    if not _can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json(force=True) or {}
    role = data.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    creator = _current_user_email() or ''
    token = create_workspace_invite(workspace_id, role=role, created_by=creator, db_path=_db_path())
    log_audit('invite_created', actor_email=creator, workspace_id=workspace_id,
              details=f'role={role}', db_path=_db_path())
    return jsonify({"token": token, "role": role}), 201


@app.route("/api/workspaces/<workspace_id>/invite-bulk", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")
def api_create_invite_bulk(workspace_id):
    """Bulk-create invite links. Body: {emails: [...], role: 'admin'|'viewer'}.
    Emails are only used as labels (the token itself is not bound to an email) —
    useful for onboarding a whole team at once with one copy-ready table."""
    if not _can_manage_workspace_users(workspace_id):
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json(force=True) or {}
    role = data.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be 'admin' or 'viewer'"}), 400
    raw_emails = data.get('emails') or []
    if not isinstance(raw_emails, list) or not raw_emails:
        return jsonify({"error": "emails array required"}), 400
    if len(raw_emails) > 50:
        return jsonify({"error": "max 50 emails per batch"}), 400
    import re as _re
    email_rx = _re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    creator = _current_user_email() or ''
    results = []
    seen = set()
    for raw in raw_emails:
        email = (raw or '').strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        if not email_rx.match(email):
            results.append({"email": email, "error": "invalid email"})
            continue
        try:
            token = create_workspace_invite(workspace_id, role=role, created_by=creator, db_path=_db_path())
            results.append({"email": email, "token": token})
        except Exception as e:
            logger.error(f"bulk invite create failed for {email}: {e}")
            results.append({"email": email, "error": "could not create"})
    ok_count = sum(1 for r in results if r.get('token'))
    if ok_count > 0:
        log_audit('invite_created', actor_email=creator, workspace_id=workspace_id,
                  details=f'bulk: {ok_count} invites, role={role}', db_path=_db_path())
    return jsonify({"role": role, "results": results, "created": ok_count}), 201


@app.route("/api/invite/<token>", methods=["GET"])
@limiter.limit("30 per minute")
def api_get_invite(token):
    """Public — validate invite token and return workspace name + role."""
    from datetime import datetime as _dt, timezone as _tz
    invite = get_workspace_invite(token, db_path=_db_path())
    if not invite:
        return jsonify({"error": "קישור לא תקין"}), 404
    if invite['used_at']:
        return jsonify({"error": "קישור זה כבר נוצל"}), 410
    if _dt.fromisoformat(invite['expires_at']) < _dt.now(_tz.utc):
        return jsonify({"error": "קישור פג תוקף"}), 410
    # Fetch workspace name
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("SELECT name FROM public.workspaces WHERE id = %s", (invite['workspace_id'],))
        row = cur.fetchone()
        conn.close()
        ws_name = row[0] if row else ''
    except Exception:
        ws_name = ''
    return jsonify({"workspace_name": ws_name, "role": invite['role'],
                    "expires_at": invite['expires_at']})


@app.route("/api/invite/<token>/accept", methods=["POST"])
@require_auth
@limiter.limit("10 per minute")
def api_accept_invite(token):
    """Authenticated user accepts an invite — assigns them to the workspace."""
    from datetime import datetime as _dt, timezone as _tz
    invite = get_workspace_invite(token, db_path=_db_path())
    if not invite:
        return jsonify({"error": "קישור לא תקין"}), 404
    if invite['used_at']:
        return jsonify({"error": "קישור זה כבר נוצל"}), 410
    if _dt.fromisoformat(invite['expires_at']) < _dt.now(_tz.utc):
        return jsonify({"error": "קישור פג תוקף"}), 410

    email = _current_user_email()
    if not email:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT id FROM auth.users WHERE LOWER(email) = %s", (email.lower(),))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "user not found"}), 404
        user_id = row[0]
        # Guard: a super_admin accepting a workspace invite must not be demoted
        # (UNIQUE(user_id) would overwrite their global role). Leave the invite
        # unused so it can still be redeemed by an intended workspace member.
        if _user_is_super_admin(cur, user_id):
            conn.close()
            return jsonify({"error": "אתה super_admin — קישורי הזמנה אינם משנים את ההרשאה הגלובלית שלך."}), 409
        cur.execute("""
            INSERT INTO public.user_roles (user_id, role, workspace_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
              SET role = EXCLUDED.role, workspace_id = EXCLUDED.workspace_id
        """, (user_id, invite['role'], invite['workspace_id']))
        cur.execute("SELECT name FROM public.workspaces WHERE id = %s", (invite['workspace_id'],))
        ws_row = cur.fetchone()
        ws_name = ws_row[0] if ws_row else 'MOCA'
        conn.close()
        use_workspace_invite(token, used_by=email, db_path=_db_path())
        log_audit('invite_accepted', actor_email=email, workspace_id=invite['workspace_id'],
                  details=f'role={invite["role"]}', db_path=_db_path())
        # Send welcome email (same as manual assignment)
        try:
            from notifier import send_welcome_email as _send_welcome
            import threading as _threading
            _threading.Thread(
                target=_send_welcome,
                args=(email, ws_name, invite['role'], load_config()),
                daemon=True,
            ).start()
        except Exception as _we:
            logger.warning(f"invite welcome email skipped: {_we}")
        return jsonify({"status": "accepted", "role": invite['role'],
                        "workspace_id": invite['workspace_id']})
    except Exception as e:
        logger.error(f"accept invite failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/workspaces/<workspace_id>/trigger-digest", methods=["POST"])
@require_super_admin
@limiter.limit("5 per minute")
def api_trigger_digest(workspace_id):
    """Manually trigger the weekly digest for a specific workspace (super_admin only)."""
    from notifier import send_weekly_digest as _send_digest
    from db import get_history_changes as _ghc
    from datetime import datetime as _dt, timedelta as _td
    _cfg = load_config()
    _from = (_dt.now() - _td(days=7)).strftime('%Y-%m-%d')
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT name, mvno_carrier, hide_self_carrier,
                   COALESCE(visible_carriers, '[]'::jsonb),
                   COALESCE(brand_config, '{}'::jsonb)
            FROM public.workspaces WHERE id = %s AND active = TRUE
        """, (workspace_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "workspace not found or inactive"}), 404
        ws_name, mvno_carrier, hide_self, vc_raw, bc_raw = row
        visible_carriers = json.loads(vc_raw) if isinstance(vc_raw, str) else (list(vc_raw) if vc_raw else [])
        brand_config = json.loads(bc_raw) if isinstance(bc_raw, str) else (dict(bc_raw) if bc_raw else {})
        cur.execute("""
            SELECT u.email FROM auth.users u
            JOIN public.user_roles r ON r.user_id = u.id
            WHERE r.workspace_id = %s AND COALESCE(r.digest_opt_out, FALSE) = FALSE
        """, (workspace_id,))
        emails = [r[0] for r in cur.fetchall() if r[0]]
        conn.close()
        if not emails:
            return jsonify({"error": "no users in workspace (or all opted out)"}), 400
        all_changes = []
        for ptype in ('domestic', 'abroad', 'global'):
            ch = _ghc('', ptype, _from, '', db_path=_db_path())
            if visible_carriers:
                ch = [c for c in ch if c.get('carrier') in visible_carriers]
            elif hide_self and mvno_carrier:
                ch = [c for c in ch if c.get('carrier') != mvno_carrier]
            all_changes.extend(ch)
        if not all_changes:
            return jsonify({"status": "skipped", "reason": "no changes in last 7 days"})
        ok = _send_digest(emails, ws_name, all_changes, _cfg, brand_config=brand_config)
        actor = _current_user_email() or ''
        log_audit('digest_sent', actor_email=actor, workspace_id=workspace_id,
                  details=f'{len(all_changes)} changes → {len(emails)} users', db_path=_db_path())
        return jsonify({"status": "sent" if ok else "partial", "emails": len(emails), "changes": len(all_changes)})
    except Exception as e:
        logger.error(f"trigger digest failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ── Workspace branding (admin of own workspace) ──────────────────────────────

@app.route("/api/workspace/branding", methods=["PATCH"])
@require_auth
@limiter.limit("20 per minute")
def api_workspace_branding():
    """Update brand_config for the caller's own workspace.
    Body: {primary_color?, secondary_color?, app_title?, logo_url?}
    Workspace admins (non-super) can update their own workspace only."""
    # g.jwt_payload is None when API key was also present (dev mode sends both).
    # Fall back to parsing Bearer JWT directly so we know who the caller is.
    email = _current_user_email() or ''
    if not email:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            _p = _verify_supabase_jwt(auth_header[7:])
            if _p:
                email = (_p.get('email') or '').strip().lower()
    if not email:
        return jsonify({"error": "Unauthorized"}), 403
    ctx = _get_user_context(email)
    role = ctx.get('role', 'viewer')
    ws_id = ctx.get('workspace_id')
    if role not in ('admin', 'super_admin') or not ws_id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(force=True) or {}
    allowed_keys = {'primary_color', 'secondary_color', 'app_title', 'logo_url', 'slack_webhook_url'}
    updates = {k: v for k, v in data.items() if k in allowed_keys}
    if not updates:
        return jsonify({"error": "no valid fields provided"}), 400

    # Validate colour values (must be hex colour or empty string)
    import re as _re
    for colour_key in ('primary_color', 'secondary_color'):
        if colour_key in updates and updates[colour_key]:
            if not _re.match(r'^#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?$', updates[colour_key]):
                return jsonify({"error": f"invalid hex colour for {colour_key}"}), 400

    # Validate Slack webhook URL — must be HTTPS to a known incoming-webhook host
    if updates.get('slack_webhook_url'):
        if not _is_valid_slack_webhook(updates['slack_webhook_url']):
            return jsonify({"error": "slack_webhook_url must be a Slack or Teams incoming-webhook HTTPS URL"}), 400

    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT brand_config FROM public.workspaces WHERE id = %s", (ws_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "workspace not found"}), 404
        import json as _json
        existing = row[0] or {}
        merged = {**existing, **updates}
        # Remove keys that were explicitly set to empty string (clear the field)
        merged = {k: v for k, v in merged.items() if v not in (None, '')}
        cur.execute(
            "UPDATE public.workspaces SET brand_config = %s::jsonb WHERE id = %s",
            (_json.dumps(merged), ws_id)
        )
        conn.close()
        log_audit('branding_updated', actor_email=email, workspace_id=ws_id,
                  details=str(list(updates.keys())), db_path=_db_path())
        logger.info(f"AUDIT branding_updated: workspace={ws_id} by={email!r} fields={list(updates.keys())}")
        return jsonify({"status": "updated", "brand_config": merged})
    except Exception as e:
        logger.error(f"workspace branding update failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/workspace/slack-test", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")
def api_workspace_slack_test():
    """Send a test message to the workspace's configured Slack/Teams webhook.
    Body: {webhook_url?} — if provided, tests this URL without saving."""
    from notifier import send_slack
    email = _current_user_email() or ''
    if not email:
        return jsonify({"error": "Unauthorized"}), 403
    ctx = _get_user_context(email)
    role = ctx.get('role', 'viewer')
    ws_id = ctx.get('workspace_id')
    if role not in ('admin', 'super_admin') or not ws_id:
        return jsonify({"error": "Unauthorized"}), 403

    # Caller can pass a URL to test before saving, or rely on stored config.
    # NOTE: any URL accepted from the request body MUST be validated against the
    # Slack/Teams allowlist to prevent SSRF (e.g. http://169.254.169.254/...).
    data = request.get_json(silent=True) or {}
    webhook_url = (data.get('webhook_url') or '').strip()
    if webhook_url and not _is_valid_slack_webhook(webhook_url):
        return jsonify({
            "error": "webhook_url must be a Slack or Teams incoming-webhook HTTPS URL"
        }), 400
    if not webhook_url:
        try:
            conn = _supabase_conn()
            cur = conn.cursor()
            cur.execute("SELECT brand_config FROM public.workspaces WHERE id = %s", (ws_id,))
            row = cur.fetchone()
            conn.close()
            bc = row[0] if row else {}
            if isinstance(bc, str):
                import json as _json
                bc = _json.loads(bc)
            webhook_url = (bc or {}).get('slack_webhook_url') or ''
        except Exception:
            webhook_url = ''
    if not webhook_url:
        return jsonify({"error": "no webhook configured"}), 400

    msg = f"✅ MOCA Slack integration test — workspace {ctx.get('workspace', {}).get('name', '')} · sent by {email}"
    ok = send_slack(msg, webhook_url)
    return jsonify({"status": "sent" if ok else "failed", "ok": ok})


# ── Audit log (super_admin only) ─────────────────────────────────────────────

@app.route("/api/audit-log", methods=["GET"])
@require_super_admin
@limiter.limit("30 per minute")
def api_audit_log():
    """Return the audit log. Optional query params: limit (default 200),
    workspace_id (filter to a specific workspace)."""
    limit = min(int(request.args.get('limit', 200)), 1000)
    ws_filter = request.args.get('workspace_id') or None
    entries = get_audit_log(limit=limit, workspace_id=ws_filter, db_path=_db_path())
    return jsonify(entries)


@app.route('/api/history/changes')
@limiter.limit('60 per minute')
def api_history_changes():
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400

    hidden = _hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({'error': 'carrier not available for this workspace'}), 403

    changes = get_history_changes(carrier, plan_type, from_date, to_date, db_path=_db_path())
    summary = {
        'total':         len(changes),
        'price_up':      sum(1 for c in changes if c['change_type'] == 'price_change' and _price_direction(c) == 'up'),
        'price_down':    sum(1 for c in changes if c['change_type'] == 'price_change' and _price_direction(c) == 'down'),
        'new_plans':     sum(1 for c in changes if c['change_type'] == 'new_plan'),
        'removed_plans': sum(1 for c in changes if c['change_type'] == 'removed_plan'),
    }
    return jsonify({'changes': changes, 'summary': summary})


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


@app.route('/api/market-movers')
@limiter.limit('60 per minute')
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
    movers = _gmm(days=days, limit=limit * 3, plan_types=plan_types, db_path=_db_path())  # fetch extra, filter, then cap
    hidden = _hidden_carrier_for_request()
    if hidden:
        movers = [m for m in movers if m.get('carrier') != hidden]
    return jsonify({'movers': movers[:limit], 'days': days})


@app.route('/api/history/price-series')
@limiter.limit('60 per minute')
def api_history_price_series():
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    plan_name = request.args.get('plan_name', '')
    from_date = request.args.get('from', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
    hidden = _hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({'error': 'carrier not available for this workspace'}), 403
    series = get_history_price_series(
        carrier, plan_type, plan_name, from_date, db_path=_db_path()
    )
    return jsonify({'series': series})


@app.route('/api/history/price-series/batch')
@limiter.limit('60 per minute')
def api_history_price_series_batch():
    """All plans' sparkline series for one tab in a single request — replaces the
    per-card N+1 that hit /price-series once per PlanCard. Keyed carrier|plan_name."""
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
    data = get_all_price_series(plan_type, from_date or None, db_path=_db_path())
    hidden = _hidden_carrier_for_request()
    if hidden:
        data = {k: v for k, v in data.items() if not k.startswith(hidden + '|')}
    resp = jsonify({'series': data})
    return _public_cache(resp, 300)


@app.route('/api/history/analyze')
@require_auth
@limiter.limit('10 per minute')
@limiter.limit(_chat_daily_limit, key_func=_chat_user_key)
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

    hidden = _hidden_carrier_for_request()
    if hidden and carrier == hidden:
        return jsonify({'error': 'carrier not available for this workspace'}), 403

    changes = get_history_changes(carrier, plan_type, from_date, to_date, db_path=_db_path())
    if not changes:
        return jsonify({'analysis': None})

    series = get_history_price_series(carrier, plan_type, from_date=from_date, db_path=_db_path())

    config = load_config()
    api_key = config.get('anthropic_api_key', '')
    if not api_key:
        return jsonify({'error': 'anthropic_api_key missing in config.json'}), 500

    carrier_display = _HISTORY_CARRIER_NAMES.get(carrier, carrier)
    type_display    = _HISTORY_TYPE_NAMES.get(plan_type, plan_type)

    if from_date and to_date:
        period_display = f'{from_date} \u05e2\u05d3 {to_date}'
    elif from_date:
        period_display = f'\u05de-{from_date} \u05e2\u05d3 \u05d4\u05d9\u05d5\u05dd'
    else:
        period_display = '\u05db\u05dc \u05d4\u05d6\u05de\u05e0\u05d9\u05dd'

    price_up      = sum(1 for c in changes if c['change_type'] == 'price_change' and _price_direction(c) == 'up')
    price_down    = sum(1 for c in changes if c['change_type'] == 'price_change' and _price_direction(c) == 'down')
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
        _record_claude_call('history_analyze', 'claude-haiku-4-5-20251001', body,
                            user_email=_caller_email())
        answer = body['content'][0]['text']
        return jsonify({'analysis': answer})
    except Exception as e:
        logger.error(f'history analyze failed: {e}', exc_info=True)
        return jsonify({'error': 'analysis failed'}), 500


# ── Claude API usage tracking ──────────────────────────────────────────────

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
    cfg = load_config()
    raw_total = cfg.get("claude_budget_usd")
    as_of = cfg.get("claude_budget_as_of") or None
    try:
        total = float(raw_total) if raw_total not in (None, "") else 0.0
    except (TypeError, ValueError):
        total = 0.0
    if total <= 0:
        return {"configured": False, "total_usd": None, "as_of": as_of}

    since_iso = f"{as_of}T00:00:00+00:00" if as_of else None
    spend = get_claude_spend(since_iso=since_iso, db_path=db_path)
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
        key = (load_config().get("anthropic_admin_key") or "").strip()
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


@app.route('/api/usage/summary')
@require_api_key_or_super_admin
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
    summary = get_claude_usage_summary(days=days, db_path=_db_path())
    summary['pricing'] = {
        m: CLAUDE_PRICING_DEFAULT[m] for m in CLAUDE_PRICING_DEFAULT
    }
    summary['budget'] = _claude_budget_block(summary, _db_path())
    summary['note'] = (
        'Estimated locally — Anthropic has no balance API. '
        'Check console.anthropic.com/settings/billing for the authoritative balance.'
    )
    return jsonify(summary)


@app.route('/api/usage/recent')
@require_api_key_or_super_admin
def api_usage_recent():
    """Return the N most recent Anthropic API calls (default 100, max 500)."""
    try:
        limit = max(1, min(500, int(request.args.get('limit', '100'))))
    except ValueError:
        limit = 100
    rows = get_claude_usage_recent(limit=limit, db_path=_db_path())
    return jsonify({'calls': rows, 'count': len(rows)})


@app.route('/api/activity/overview')
@require_api_key_or_super_admin
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
        conn = _supabase_conn()
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
                    for o in get_user_activity_overview(days=days, db_path=_db_path())}

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

        summary = get_user_activity_summary(days=days, db_path=_db_path())
        summary['total_users'] = len(users)
        summary['active_today'] = len(get_user_activity_overview(days=1, db_path=_db_path()))
        summary['active_this_week'] = len(get_user_activity_overview(days=7, db_path=_db_path()))
        summary['active_this_month'] = len(get_user_activity_overview(days=30, db_path=_db_path()))

        # Opportunistic retention prune (rare; DELETE only — keep the table bounded
        # without a cron). 180-day retention.
        import random as _rnd
        if _rnd.random() < 0.02:
            try:
                prune_user_activity(db_path=_db_path())
            except Exception:
                pass

        return jsonify({"users": users, "summary": summary})
    except Exception as e:
        logger.error(f"activity overview failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/activity/events')
@require_api_key_or_super_admin
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
        rows = get_user_activity_events(email=email, event_type=event_type,
                                        days=days, limit=limit, db_path=_db_path())
        return jsonify({"events": rows, "count": len(rows)})
    except Exception as e:
        logger.error(f"activity events failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/usage/budget', methods=['POST'])
@require_api_key_or_super_admin
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
    if not os.path.exists(CONFIG_PATH):
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
        with open(CONFIG_PATH, encoding="utf-8") as f:
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
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("claude budget save failed: %s", e)
        return jsonify({"error": "could not save budget"}), 500

    summary = get_claude_usage_summary(days=30, db_path=_db_path())
    return jsonify(_claude_budget_block(summary, _db_path()))


@app.route('/api/settings/notifications', methods=['GET'])
@require_api_key_or_super_admin
def api_get_notification_settings():
    """Global notification settings — currently just the message language."""
    cfg = load_config()
    return jsonify({"notify_lang": cfg.get("notify_lang", "he")})


@app.route('/api/settings/notifications', methods=['POST'])
@require_api_key_or_super_admin
def api_set_notification_settings():
    """Set the notification message language (he|en).

    Applies to every push channel — Telegram / WhatsApp / Web Push / Slack —
    and the morning digest. The scrape/digest jobs re-read config.json each run,
    so the change takes effect on the next notification with no restart. Scraped
    plan names and detail texts stay in their original language (real product
    strings); only the framing is localized.
    """
    if not os.path.exists(CONFIG_PATH):
        return jsonify({"error": "config.json is not writable in this deployment"}), 400
    data = request.get_json(silent=True) or {}
    lang = str(data.get("notify_lang") or "").strip().lower()
    if lang not in ("he", "en"):
        return jsonify({"error": "notify_lang must be 'he' or 'en'"}), 400
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["notify_lang"] = lang
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("notify_lang save failed: %s", e)
        return jsonify({"error": "could not save settings"}), 500
    return jsonify({"notify_lang": lang})


@app.route('/api/usage/official-cost')
@require_api_key_or_super_admin
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


# ── Main ───────────────────────────────────────────────────────────────────

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
