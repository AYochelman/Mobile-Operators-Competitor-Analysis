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
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from db import init_db, get_plans, get_changes, get_abroad_plans, get_abroad_changes, get_global_plans, get_global_changes, \
               get_content_plans, get_content_changes, \
               save_price_alert, get_price_alerts, delete_price_alert, update_alert_triggered, \
               save_executive_summary, get_executive_summary, compute_executive_metrics, \
               save_social_sentiment, get_social_sentiment, \
               get_archive_plans, get_archive_banners, get_archive_date_range, \
               get_history_changes, get_history_price_series, \
               upsert_news_articles, get_news_articles, \
               log_affiliate_click, get_affiliate_stats
import archive as arc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per minute"], storage_uri="memory://")

# CORS: restrict to known origins
ALLOWED_ORIGINS = [
    "http://localhost:5000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175",
    "http://127.0.0.1:5000", "http://127.0.0.1:5173",
    "https://lucent-kulfi-f037ad.netlify.app",
    # ngrok URLs added dynamically via ALLOWED_ORIGINS env var
]
# Add ngrok/netlify URLs from environment if set
_extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _extra_origins:
    ALLOWED_ORIGINS.extend(_extra_origins.split(","))
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS, "supports_credentials": True}})

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
        "connect-src 'self' https: wss:; "
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
        if not provided or provided != expected:
            return jsonify({"error": "Unauthorized — API key required"}), 401
        return f(*args, **kwargs)
    return decorated


def require_auth(f):
    """Accept a valid Supabase JWT (Authorization header or auth_token cookie) OR API key.
    Sets g.jwt_payload to the decoded payload (or None for API-key auth).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. API key (server-to-server)
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header and hmac.compare_digest(api_key_header, _get_api_key()):
            g.jwt_payload = None
            return f(*args, **kwargs)
        # 2. JWT from Authorization header
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        # 3. JWT from httpOnly cookie (fallback)
        if not token:
            token = request.cookies.get("auth_token")
        if token:
            payload = _verify_supabase_jwt(token)
            if payload:
                g.jwt_payload = payload
                return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


def require_admin(f):
    """Accept API key OR a verified Supabase JWT whose owner has admin role in user_roles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. API key
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header and hmac.compare_digest(api_key_header, _get_api_key()):
            g.jwt_payload = None
            return f(*args, **kwargs)
        # 2. JWT
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
                    if row and row[0] == 'admin':
                        g.jwt_payload = payload
                        return f(*args, **kwargs)
                except Exception as e:
                    logger.error(f"require_admin DB check failed: {e}")
        return jsonify({"error": "Unauthorized — admin required"}), 401
    return decorated


def require_api_key_or_query(f):
    """Accepts API key via header OR ?api_key= query param.
    Use ONLY on /api/scrape-*-now for manual browser convenience."""
    @wraps(f)
    def decorated(*args, **kwargs):
        provided = request.headers.get("X-API-Key") or request.args.get("api_key")
        expected = _get_api_key()
        if not provided or provided != expected:
            return jsonify({"error": "Unauthorized — API key required"}), 401
        return f(*args, **kwargs)
    return decorated


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
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
            cfg = load_config()
            secret = cfg.get('supabase_jwt_secret') or os.environ.get('SUPABASE_JWT_SECRET', '')
            if secret:
                computed = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
                if not hmac.compare_digest(computed, sig_bytes):
                    logger.warning("HS256 JWT signature verification failed — possible token forgery")
                    return None
            else:
                logger.warning("supabase_jwt_secret not configured — HS256 token accepted without verification")

        else:
            logger.warning(f"Unsupported JWT algorithm: {alg}")
            return None

        # Check expiry — allow 15-minute grace period (clock skew + refresh lag)
        exp = payload.get('exp')
        if exp is not None and _time.time() > exp + 900:
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
    """Serve carrier homepage screenshot PNGs."""
    if not filename.endswith(".png"):
        abort(404)
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    return send_from_directory(banners_dir, filename)


@app.route("/api/plans")
@limiter.limit("60 per minute")
def api_plans():
    carrier = request.args.get("carrier")
    plans = get_plans(carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/changes")
@limiter.limit("60 per minute")
def api_changes():
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 500))
    except (ValueError, TypeError):
        limit = 20
    changes = get_changes(limit=limit, db_path=_db_path())
    return jsonify(changes)


@app.route("/api/abroad-plans")
@limiter.limit("60 per minute")
def api_abroad_plans():
    carrier = request.args.get("carrier")
    plans = get_abroad_plans(carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/global-plans")
@limiter.limit("60 per minute")
def api_global_plans():
    carrier = request.args.get("carrier")
    plans = get_global_plans(carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/news")
@limiter.limit("60 per minute")
def api_news():
    """Return cached news articles. Optional ?carrier=<id> filter."""
    carrier = request.args.get('carrier', None)
    articles = get_news_articles(carrier=carrier, db_path=_db_path())
    return jsonify(articles)


_AFFILIATE_FALLBACK_URLS = {
    "airalo":     "https://www.airalo.com",
    "holafly":    "https://esim.holafly.com",
    "saily":      "https://saily.com",
    "globalesim": "https://globalesim.com",
}

@app.route("/go/<provider>")
@app.route("/go/<provider>/<plan_id>")
@limiter.limit("60 per minute")
def affiliate_redirect(provider, plan_id=None):
    ip      = request.remote_addr or ""
    cfg     = load_config()
    api_key = cfg.get("api_key", "")
    ip_hash = hmac.new(api_key.encode(), ip.encode(), hashlib.sha256).hexdigest()
    country = request.args.get("country")

    try:
        log_affiliate_click(provider, plan_id=plan_id, country=country,
                            ip_hash=ip_hash, db_path=_db_path())
    except Exception:
        app.logger.warning("affiliate click log failed", exc_info=True)

    affiliate = cfg.get("affiliate", {}).get(provider)
    if affiliate:
        return redirect(affiliate["base_url"], 302)

    fallback = _AFFILIATE_FALLBACK_URLS.get(provider, "https://lucent-kulfi-f037ad.netlify.app")
    return redirect(fallback, 302)


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


@app.route("/api/exchange-rates")
@limiter.limit("30 per minute")
def api_exchange_rates():
    from scraper import _get_usd_to_ils, _get_eur_to_ils, _get_gbp_to_ils
    return jsonify({"usd": _get_usd_to_ils(), "eur": _get_eur_to_ils(), "gbp": _get_gbp_to_ils()})


@app.route("/api/global-changes")
@limiter.limit("60 per minute")
def api_global_changes():
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 500))
    except (ValueError, TypeError):
        limit = 50
    changes = get_global_changes(limit=limit, db_path=_db_path())
    return jsonify(changes)


@app.route("/api/scrape-global-now")
@require_api_key_or_query
def api_scrape_global_now():
    """Manual trigger: scrape global eSIM packages, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_global_plans, save_global_changes
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
            changes = detect_changes(old_plans, new_plans)
            if changes:
                save_global_changes(changes, db_path=_db_path())
        save_global_plans(new_plans, db_path=_db_path())
        arc.archive_global_plans(new_plans)
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
    return jsonify(changes)


@app.route("/api/scrape-abroad-now")
@require_api_key_or_query
def api_scrape_abroad_now():
    """Manual trigger: scrape abroad packages, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_abroad_plans, save_abroad_changes
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
            if changes:
                save_abroad_changes(changes, db_path=_db_path())
        save_abroad_plans(new_plans, db_path=_db_path())
        arc.archive_abroad_plans(new_plans)
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-abroad-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@app.route("/api/scrape-all-now")
@require_api_key_or_query
def api_scrape_all_now():
    """Scrape ALL tabs: domestic + abroad + global in one call."""
    try:
        import scraper as sc
        from db import save_plans, save_changes, save_abroad_plans, save_abroad_changes, \
                       save_global_plans, save_global_changes
        from change_detector import detect_changes
        results = {}

        # ── Domestic ──────────────────────────────────────────────────────
        old_domestic = get_plans(db_path=_db_path())
        new_domestic = sc.scrape_all()
        ch_domestic  = detect_changes(old_domestic, new_domestic)
        save_plans(new_domestic, db_path=_db_path())
        if ch_domestic:
            save_changes(ch_domestic, db_path=_db_path())
        results["domestic"] = {"plans": len(new_domestic), "changes": len(ch_domestic)}

        # ── Abroad ────────────────────────────────────────────────────────
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
            if ch_abroad:
                save_abroad_changes(ch_abroad, db_path=_db_path())
        save_abroad_plans(new_abroad, db_path=_db_path())
        results["abroad"] = {"plans": len(new_abroad), "changes": len(ch_abroad)}

        # ── Global ────────────────────────────────────────────────────────
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
            ch_global = detect_changes(old_global, new_global)
            if ch_global:
                save_global_changes(ch_global, db_path=_db_path())
        save_global_plans(new_global, db_path=_db_path())
        results["global"] = {"plans": len(new_global), "changes": len(ch_global)}

        # ── Content services ──────────────────────────────────────────────
        from db import save_content_plans, save_content_changes
        from change_detector import detect_content_changes
        old_content = get_content_plans(db_path=_db_path())
        new_content = sc.scrape_all_content()
        ch_content = detect_content_changes(old_content, new_content)
        save_content_plans(new_content, db_path=_db_path())
        if ch_content:
            save_content_changes(ch_content, db_path=_db_path())
        results["content"] = {"plans": len(new_content), "changes": len(ch_content)}

        # ── Archive plan snapshots ─────────────────────────────────────────
        arc.archive_domestic_plans(new_domestic)
        arc.archive_abroad_plans(new_abroad)
        arc.archive_global_plans(new_global)
        arc.archive_content_plans(new_content)

        # ── Banners (homepage + e-store screenshots) ───────────────────────
        banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
        from scraper import scrape_carrier_banners, scrape_carrier_store_banners
        banner_results = scrape_carrier_banners(banners_dir)
        store_results  = scrape_carrier_store_banners(banners_dir)
        arc.archive_all_banners(banners_dir, list(CARRIER_DISPLAY.keys()), list(CARRIER_STORE_DISPLAY.keys()))
        results["banners"] = {
            "homepage": sum(1 for r in banner_results if r["success"]),
            "store":    sum(1 for r in store_results  if r["success"]),
        }

        results["status"] = "ok"
        results["total_plans"] = len(new_domestic) + len(new_abroad) + len(new_global) + len(new_content)
        results["total_changes"] = len(ch_domestic) + len(ch_abroad) + len(ch_global) + len(ch_content)
        logger.info(f"scrape-all-now: {results}")
        return jsonify(results)
    except Exception as e:
        logger.error(f"scrape-all-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@app.route("/api/content-plans")
@limiter.limit("60 per minute")
def api_content_plans():
    carrier = request.args.get("carrier")
    service = request.args.get("service")
    plans = get_content_plans(service=service, carrier=carrier, db_path=_db_path())
    return jsonify(plans)


def _price_direction(change):
    """Return 'up', 'down', or None for a price_change record."""
    try:
        old, new = float(change['old_val']), float(change['new_val'])
        if new > old: return 'up'
        if new < old: return 'down'
        return None
    except (ValueError, TypeError):
        return None


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
    'globalesim': 'GlobaleSIM',
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
}
_HISTORY_TYPE_NAMES = {
    'domestic': '\u05de\u05e7\u05d5\u05de\u05d9',
    'abroad': '\u05d7\u05d5"\u05dc',
    'global': '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9',
    'content': '\u05ea\u05d5\u05db\u05df',
}


CARRIER_DISPLAY = {
    "partner":   {"name": "פרטנר",      "url": "https://www.partner.net.il",       "color": "#e8003d"},
    "pelephone": {"name": "פלאפון",     "url": "https://www.pelephone.co.il",      "color": "#ff6600"},
    "hotmobile": {"name": "הוט מובייל", "url": "https://www.hotmobile.co.il",      "color": "#e3001e"},
    "cellcom":   {"name": "סלקום",      "url": "https://www.cellcom.co.il",        "color": "#003b7a"},
    "mobile019": {"name": "019 מובייל", "url": "https://www.019mobile.co.il",      "color": "#555555"},
    "xphone":    {"name": "XPhone",     "url": "https://www.xphone.co.il",         "color": "#6a0dad"},
    "wecom":     {"name": "וי-קום",     "url": "https://we-com.co.il",             "color": "#006633"},
    "neptucom":  {"name": "נפטוקום",    "url": "https://www.neptucom.com",         "color": "#004488"},
    "golan":     {"name": "גולן טלקום", "url": "https://www.golantelecom.co.il",   "color": "#009688"},
    "rami_levy": {"name": "רמי לוי",    "url": "https://mobile.rami-levy.co.il",  "color": "#e32032"},
}

CARRIER_STORE_DISPLAY = {
    "pelephone": {"name": "פלאפון",     "url": "https://www.pelephone.co.il/ds/heb/eshop/lobby/", "color": "#ff6600"},
    "cellcom":   {"name": "סלקום",      "url": "https://shop.cellcom.co.il/",                      "color": "#003b7a"},
    "partner":   {"name": "פרטנר",      "url": "https://store.partner.co.il/home",                 "color": "#e8003d"},
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
    since_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')

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
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 400,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()["content"][0]["text"].strip()

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
                    "model": "claude-sonnet-4-5",
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
            raw_narrative = resp.json()["content"][0]["text"].strip()
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


@app.route("/api/executive-summary")
@limiter.limit("60 per minute")
def api_executive_summary():
    """Return cached executive summary for all 4 categories."""
    rows = get_executive_summary(db_path=_db_path())
    if not rows:
        return jsonify({"error": "not_generated_yet"}), 404
    return jsonify(rows)


@app.route("/api/executive-summary/refresh", methods=["POST"])
@require_api_key_or_query
def api_executive_summary_refresh():
    """Trigger manual regeneration of all 4 executive summaries."""
    try:
        generate_executive_summary()
        rows = get_executive_summary(db_path=_db_path())
        generated_at = rows[0]["generated_at"] if rows else None
        return jsonify({"status": "ok", "generated_at": generated_at})
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
@require_api_key_or_query
def api_social_sentiment_refresh():
    """Trigger manual regeneration of social sentiment for all carriers."""
    try:
        generate_social_sentiment()
        rows = get_social_sentiment(db_path=_db_path())
        generated_at = rows[0]["generated_at"] if rows else None
        return jsonify({"status": "ok", "generated_at": generated_at})
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
        exists = os.path.exists(png_path)
        if exists:
            mtime = os.path.getmtime(png_path)
            scraped_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        result.append({
            "carrier":    carrier,
            "name":       meta["name"],
            "url":        meta["url"],
            "color":      meta["color"],
            "image_url":  f"/banners/{carrier}.png" if exists else None,
            "scraped_at": scraped_at,
        })
    return jsonify(result)


@app.route("/api/store-banners")
@limiter.limit("60 per minute")
def api_store_banners():
    """Return metadata for carrier e-store banner screenshots."""
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    result = []
    for carrier, meta in CARRIER_STORE_DISPLAY.items():
        png_path = os.path.join(banners_dir, f"{carrier}_store.png")
        scraped_at = None
        exists = os.path.exists(png_path)
        if exists:
            mtime = os.path.getmtime(png_path)
            scraped_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        result.append({
            "carrier":    carrier,
            "name":       meta["name"],
            "url":        meta["url"],
            "color":      meta["color"],
            "image_url":  f"/banners/{carrier}_store.png" if exists else None,
            "scraped_at": scraped_at,
        })
    return jsonify(result)


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


@app.route("/archive-banners/<path:filepath>")
def serve_archive_banner(filepath):
    """Serve archived banner PNG files."""
    base = os.path.dirname(os.path.abspath(__file__))
    full = os.path.join(base, filepath)
    if not os.path.isfile(full):
        abort(404)
    directory = os.path.dirname(full)
    filename = os.path.basename(full)
    return send_from_directory(directory, filename)


@app.route("/api/content-changes")
@limiter.limit("60 per minute")
def api_content_changes():
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except (ValueError, TypeError):
        limit = 50
    changes = get_content_changes(limit=limit, db_path=_db_path())
    return jsonify(changes)


@app.route("/api/scrape-content-now")
@require_api_key_or_query
def api_scrape_content_now():
    """Manual trigger: scrape content services, detect changes, save to DB."""
    try:
        import scraper as sc
        from db import save_content_plans, save_content_changes
        from change_detector import detect_content_changes
        old_plans = get_content_plans(db_path=_db_path())
        new_plans = sc.scrape_all_content()
        changes = detect_content_changes(old_plans, new_plans)
        save_content_plans(new_plans, db_path=_db_path())
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
        from db import save_plans, save_changes
        from change_detector import detect_changes
        from notifier import format_message

        new_plans = sc.scrape_all()
        old_plans = get_plans(db_path=_db_path())
        changes = detect_changes(old_plans, new_plans)
        save_plans(new_plans, db_path=_db_path())
        if changes:
            save_changes(changes, db_path=_db_path())
        arc.archive_domestic_plans(new_plans)
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


# ── Price Alerts Routes ────────────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
@require_auth
@limiter.limit("60 per minute")
def api_get_alerts():
    """Get alerts for the authenticated user.
    Email is derived from the verified JWT (Authorization: Bearer <token>).
    Falls back to ?user_email= query param for backwards compatibility."""
    user_email = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        payload = _verify_supabase_jwt(auth_header[7:])
        if payload:
            user_email = payload.get('email')
    if not user_email:
        user_email = request.args.get("user_email", "")
    alerts = get_price_alerts(user_email=user_email or None, db_path=_db_path())
    return jsonify(alerts)


@app.route("/api/alerts", methods=["POST"])
@require_auth
@limiter.limit("20 per minute")
def api_create_alert():
    data = request.get_json(force=True)
    try:
        save_price_alert(
            user_email=data.get("user_email", ""),
            tab=data.get("tab", "domestic"),
            carrier=data.get("carrier", ""),
            plan_pattern=data.get("plan_pattern", ""),
            threshold=float(data.get("threshold", 0)),
            db_path=_db_path()
        )
        return jsonify({"status": "created"}), 201
    except Exception as e:
        logger.error(f"create alert failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
@require_auth
def api_delete_alert(alert_id):
    delete_price_alert(alert_id, db_path=_db_path())
    return jsonify({"status": "deleted"})


# ── Push Notification Routes ───────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
@require_auth
@limiter.limit("10 per minute")
def api_chat():
    """AI chat over the plans data using Claude API."""
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "no question"}), 400

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
        _CARRIER_NAMES = {
            'partner': 'פרטנר', 'pelephone': 'פלאפון', 'hotmobile': 'הוט מובייל',
            'cellcom': 'סלקום', 'mobile019': '019', 'xphone': 'XPhone',
            'wecom': 'We-Com', 'neptucom': 'Neptucom', 'golan': 'גולן טלקום',
            'tuki': 'Tuki', 'globalesim': 'GlobaleSIM',
            'airalo': 'Airalo', 'airalo_local': 'Airalo', 'airalo_regional': 'Airalo',
            'pelephone_global': 'GlobalSIM', 'esimo': 'eSIMo', 'simtlv': 'SimTLV',
            'world8': '8 World', 'xphone_global': 'XPhone Global', 'saily': 'Saily',
            'holafly': 'Holafly', 'esimio': 'eSIM.io', 'sparks': 'Sparks',
            'voye': 'VOYE', 'orbit': 'Orbit', 'travelsim': 'Travel Sim',
            'gomoworld': 'GoMoWorld', 'tasim': 'Tasim', 'maya': 'Maya Mobile',
            'esim70': 'eSIM70',
        }
        def _cn(carrier):
            return _CARRIER_NAMES.get(carrier, carrier)

        lines = [
            "אתה עוזר נתונים עבור מערכת השוואת חבילות סלולר ישראלית.",
            "להלן הנתונים הנוכחיים מהמסד נתונים. ענה בעברית, בצורה תמציתית וברורה.",
            f"תאריך עדכון: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "שמות ספקים: gomoworld=GoMoWorld=Gomo, airalo/airalo_local/airalo_regional=Airalo, pelephone_global=GlobalSIM, xphone_global=XPhone Global, mobile019=019.",
            "",
        ]

        # Domestic plans
        domestic = get_plans(db_path=_db_path())
        if domestic:
            lines.append("## חבילות ביתיות (ישראל)")
            for p in domestic:
                lines.append(
                    f"  {_cn(p['carrier'])} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{fmt_gb(p.get('data_gb'))} | {p.get('minutes','')} דקות"
                    + (f" | extras: {';'.join(p['extras'])}" if p.get('extras') else "")
                )

        # Abroad plans
        abroad = get_abroad_plans(db_path=_db_path())
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
        _all_global = get_global_plans(db_path=_db_path())
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
        content = get_content_plans(db_path=_db_path())
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
        for ch in get_changes(limit=200, db_path=_db_path()):
            all_changes.append(("ביתי", ch))
        for ch in get_abroad_changes(limit=200, db_path=_db_path()):
            all_changes.append(("חו\"ל", ch))
        for ch in get_global_changes(limit=200, db_path=_db_path()):
            all_changes.append(("גלובלי", ch))
        for ch in get_content_changes(limit=200, db_path=_db_path()):
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
        resp = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1024,
                "system": context,
                "messages": [{"role": "user", "content": question}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        answer = resp.json()["content"][0]["text"]
        return jsonify({"answer": answer})

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
    data = request.get_json(force=True)
    endpoint = data.get("endpoint")
    p256dh   = data.get("keys", {}).get("p256dh")
    auth     = data.get("keys", {}).get("auth")
    if not all([endpoint, p256dh, auth]):
        return jsonify({"error": "missing fields"}), 400
    save_push_subscription(endpoint, p256dh, auth, db_path=_db_path())
    return jsonify({"status": "subscribed"}), 201


@app.route("/api/push/unsubscribe", methods=["DELETE"])
@require_auth
@limiter.limit("10 per minute")
def api_push_unsubscribe():
    from db import delete_push_subscription
    data = request.get_json(force=True)
    endpoint = data.get("endpoint")
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400
    delete_push_subscription(endpoint, db_path=_db_path())
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
    """Return the role of the given user email.
    Email is extracted from the verified JWT payload (g.jwt_payload),
    or falls back to X-User-Email header for API-key auth."""
    payload = getattr(g, 'jwt_payload', None)
    if payload:
        email = (payload.get('email') or '').strip().lower()
    else:
        email = request.headers.get('X-User-Email', '').strip().lower()
    if not email:
        return jsonify({"role": "viewer"})
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(r.role, 'viewer')
            FROM auth.users u
            LEFT JOIN public.user_roles r ON u.id = r.user_id
            WHERE LOWER(u.email) = %s
        """, (email,))
        row = cur.fetchone()
        conn.close()
        return jsonify({"role": row[0] if row else "viewer"})
    except Exception as e:
        logger.error(f"my-role failed: {e}")
        return jsonify({"role": "viewer"})


@app.route("/api/users")
@require_admin
@limiter.limit("20 per minute")
def api_get_users():
    """List all users from Supabase via direct DB connection."""
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.created_at, COALESCE(r.role, 'viewer') as role, u.last_sign_in_at
            FROM auth.users u
            LEFT JOIN public.user_roles r ON u.id = r.user_id
            ORDER BY u.created_at DESC
        """)
        users = [{'id': str(row[0]), 'email': row[1], 'created_at': str(row[2]), 'role': row[3], 'last_sign_in_at': str(row[4]) if row[4] else None} for row in cur.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        logger.error(f"get users failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/users", methods=["POST"])
@require_admin
@limiter.limit("10 per minute")
def api_create_user():
    """Create a new user in Supabase."""
    import urllib.request
    data = request.get_json(force=True)
    email = data.get('email', '')
    password = data.get('password', '')
    role = data.get('role', 'viewer')
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    try:
        cfg = load_config()
        anon_key = cfg.get('supabase_anon_key') or os.environ.get('SUPABASE_ANON_KEY', '')
        supabase_url = cfg.get('supabase_url') or os.environ.get('SUPABASE_URL', 'https://gmfefvjdmgzluwffzrzj.supabase.co')
        if not anon_key:
            logger.error("api_create_user: supabase_anon_key not configured")
            return jsonify({"error": "Server misconfiguration"}), 500

        # Create user via Supabase Auth API
        url = f'{supabase_url}/auth/v1/signup'
        payload = json.dumps({'email': email, 'password': password}).encode()
        req = urllib.request.Request(url, payload, method='POST')
        req.add_header('apikey', anon_key)
        req.add_header('Content-Type', 'application/json')
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        user_id = result.get('id') or result.get('user', {}).get('id')

        # Confirm email + set role
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute('UPDATE auth.users SET email_confirmed_at = now() WHERE id = %s', (user_id,))
        cur.execute("INSERT INTO public.user_roles (user_id, role) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET role = %s", (user_id, role, role))
        conn.close()

        logger.info(f"AUDIT create_user: email={email!r} role={role!r} new_user_id={user_id!r} by_ip={request.remote_addr}")
        return jsonify({"status": "created", "user_id": user_id}), 201
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logger.error(f"create user failed: {body}")
        return jsonify({"error": "Failed to create user"}), 500
    except Exception as e:
        logger.error(f"create user failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/users/<user_id>", methods=["DELETE"])
@require_admin
@limiter.limit("10 per minute")
def api_delete_user(user_id):
    """Delete a user from Supabase."""
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
@require_admin
@limiter.limit("20 per minute")
def api_update_user_role(user_id):
    """Update a user's role."""
    data = request.get_json(force=True)
    role = data.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        return jsonify({"error": "role must be admin or viewer"}), 400
    try:
        conn = _supabase_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("INSERT INTO public.user_roles (user_id, role) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET role = %s", (user_id, role, role))
        conn.close()
        logger.info(f"AUDIT update_role: user_id={user_id!r} new_role={role!r} by_ip={request.remote_addr}")
        return jsonify({"status": "updated", "role": role})
    except Exception as e:
        logger.error(f"update role failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/history/changes')
@limiter.limit('60 per minute')
def api_history_changes():
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400

    changes = get_history_changes(carrier, plan_type, from_date, to_date, db_path=_db_path())
    summary = {
        'total':         len(changes),
        'price_up':      sum(1 for c in changes if c['change_type'] == 'price_change' and _price_direction(c) == 'up'),
        'price_down':    sum(1 for c in changes if c['change_type'] == 'price_change' and _price_direction(c) == 'down'),
        'new_plans':     sum(1 for c in changes if c['change_type'] == 'new_plan'),
        'removed_plans': sum(1 for c in changes if c['change_type'] == 'removed_plan'),
    }
    return jsonify({'changes': changes, 'summary': summary})


@app.route('/api/history/price-series')
@limiter.limit('60 per minute')
def api_history_price_series():
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    plan_name = request.args.get('plan_name', '')
    from_date = request.args.get('from', '')
    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400
    series = get_history_price_series(
        carrier, plan_type, plan_name, from_date, db_path=_db_path()
    )
    return jsonify({'series': series})


@app.route('/api/history/analyze')
@limiter.limit('10 per minute')
def api_history_analyze():
    """AI analysis of historical price changes for a carrier using Claude Haiku.
    Rate-limited to 10/min (vs 60/min for other history routes) due to Anthropic API cost.
    Note: to_date is not forwarded to get_history_price_series (unsupported by that function).
    """
    carrier   = request.args.get('carrier', '')
    plan_type = request.args.get('plan_type', 'domestic')
    from_date = request.args.get('from', '')
    to_date   = request.args.get('to', '')

    if plan_type not in ('domestic', 'abroad', 'global', 'content'):
        return jsonify({'error': 'plan_type must be domestic/abroad/global/content'}), 400

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
        answer = resp.json()['content'][0]['text']
        return jsonify({'analysis': answer})
    except Exception as e:
        logger.error(f'history analyze failed: {e}', exc_info=True)
        return jsonify({'error': 'analysis failed'}), 500


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from apscheduler.schedulers.background import BackgroundScheduler
    from change_detector import detect_changes
    from notifier import (format_message, format_abroad_message, format_global_message,
                          format_content_message, send_notification, send_whatsapp,
                          send_email_report, send_push_notifications)
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

    def run_scrape_job():
        logger.info("Starting scheduled scrape...")
        config = load_config()
        try:
            from db import save_plans, save_changes, save_abroad_plans, save_abroad_changes, get_abroad_plans

            # ── Domestic plans ─────────────────────────────────────────────
            new_plans = scraper.scrape_all()
            old_plans = get_plans()
            changes = detect_changes(old_plans, new_plans)
            save_plans(new_plans)
            if changes:
                save_changes(changes)
                msg = format_message(changes)
                ok_tg = send_notification(msg, config)
                logger.info(f"Telegram (domestic) sent: {ok_tg}")
                ok_wa = send_whatsapp(msg, config)
                logger.info(f"WhatsApp sent: {ok_wa}")
                n_push = send_push_notifications(changes, config)
                logger.info(f"Web Push sent: {n_push}")
            else:
                logger.info("No domestic changes.")

            # ── Abroad plans ───────────────────────────────────────────────
            new_abroad = scraper.scrape_all_abroad()
            old_abroad = get_abroad_plans()
            abroad_changes = detect_changes(old_abroad, new_abroad)
            save_abroad_plans(new_abroad)
            if abroad_changes:
                save_abroad_changes(abroad_changes)
                abroad_msg = format_abroad_message(abroad_changes)
                ok_tg_abroad = send_notification(abroad_msg, config)
                ok_wa_abroad = send_whatsapp(abroad_msg, config)
                logger.info(f"Telegram (abroad) sent: {ok_tg_abroad}, WhatsApp: {ok_wa_abroad}, changes: {len(abroad_changes)}")
            else:
                logger.info("No abroad changes.")

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
                global_changes = detect_changes(old_global, new_global)
                if global_changes:
                    save_global_changes(global_changes)
            save_global_plans(new_global)
            if global_changes:
                global_msg = format_global_message(global_changes)
                ok_tg_global = send_notification(global_msg, config)
                ok_wa_global = send_whatsapp(global_msg, config)
                logger.info(f"Telegram (global) sent: {ok_tg_global}, WhatsApp: {ok_wa_global}, changes: {len(global_changes)}")
            else:
                logger.info("No global changes.")

            # ── Content services ───────────────────────────────────────────
            from db import save_content_plans, save_content_changes
            from change_detector import detect_content_changes
            old_content = get_content_plans()
            new_content = scraper.scrape_all_content()
            content_changes = detect_content_changes(old_content, new_content)
            save_content_plans(new_content)
            if content_changes:
                save_content_changes(content_changes)
                content_msg = format_content_message(content_changes)
                ok_tg_content = send_notification(content_msg, config)
                ok_wa_content = send_whatsapp(content_msg, config)
                logger.info(f"Telegram (content) sent: {ok_tg_content}, WhatsApp: {ok_wa_content}, changes: {len(content_changes)}")
            else:
                logger.info("No content changes.")

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
        except Exception as e:
            logger.error(f"Scrape job failed: {e}", exc_info=True)

    def scrape_banners_job():
        """Daily 08:00 job — screenshot each carrier homepage."""
        from scraper import scrape_carrier_banners
        banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
        logger.info("Starting daily banner screenshot job")
        try:
            results = scrape_carrier_banners(banners_dir)
            ok = sum(1 for r in results if r["success"])
            logger.info("Banner screenshots: %d/%d succeeded", ok, len(results))
            arc.archive_all_banners(banners_dir, list(CARRIER_DISPLAY.keys()), [])
        except Exception as e:
            logger.error("Banner screenshot job failed: %s", e, exc_info=True)

    def scrape_store_banners_job():
        """Daily 08:00 job — screenshot each carrier e-store page."""
        from scraper import scrape_carrier_store_banners
        banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
        logger.info("Starting daily store banner screenshot job")
        try:
            results = scrape_carrier_store_banners(banners_dir)
            ok = sum(1 for r in results if r["success"])
            logger.info("Store banner screenshots: %d/%d succeeded", ok, len(results))
            arc.archive_all_banners(banners_dir, [], list(CARRIER_STORE_DISPLAY.keys()))
        except Exception as e:
            logger.error("Store banner screenshot job failed: %s", e, exc_info=True)

    _ensure_vapid_keys(CONFIG_PATH)
    init_db()
    config = load_config()
    scheduler = BackgroundScheduler()
    for time_str in config.get("schedule_times", ["10:00", "16:00"]):
        hour, minute = map(int, time_str.split(":"))
        scheduler.add_job(run_scrape_job, "cron", hour=hour, minute=minute)
    report_time = config.get("email_report_time", "09:00")
    rh, rm = map(int, report_time.split(":"))
    scheduler.add_job(run_email_report_job, "cron", hour=rh, minute=rm)
    scheduler.add_job(scrape_banners_job, "cron", hour=8, minute=0)
    scheduler.add_job(scrape_store_banners_job, "cron", hour=8, minute=0)
    scheduler.add_job(generate_executive_summary, "cron", hour=8, minute=5, id="executive_summary")
    scheduler.add_job(scrape_news_job, "cron", hour=8, minute=10, id="news_scrape")
    # Social sentiment: every 3 days at 08:00 — use interval trigger with next 08:00 as start
    from datetime import datetime as _dt, timedelta as _td
    _now = _dt.now()
    _next_8 = _now.replace(hour=8, minute=0, second=0, microsecond=0)
    if _next_8 <= _now:
        _next_8 += _td(days=1)
    scheduler.add_job(generate_social_sentiment, "interval", days=3,
                      start_date=_next_8, id="social_sentiment")
    scheduler.start()
    logger.info("Flask starting → http://0.0.0.0:5000")
    try:
        host = os.environ.get("FLASK_HOST", "127.0.0.1")  # Use 0.0.0.0 only for ngrok/LAN
        app.run(host=host, port=5000, debug=False, use_reloader=False)
    finally:
        scheduler.shutdown()
