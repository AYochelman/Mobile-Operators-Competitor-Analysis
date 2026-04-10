import json
import os
import logging
import secrets
import hmac
import hashlib
import base64
import time as _time
from functools import wraps
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from db import init_db, get_plans, get_changes, get_abroad_plans, get_abroad_changes, get_global_plans, get_global_changes, \
               get_content_plans, get_content_changes, \
               save_price_alert, get_price_alerts, delete_price_alert, update_alert_triggered

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
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

@app.after_request
def add_security_headers(response):
    """Attach security headers to every response."""
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
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

        # Check expiry
        exp = payload.get('exp')
        if exp is not None and _time.time() > exp:
            logger.warning("JWT has expired")
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


@app.route("/api/plans")
def api_plans():
    carrier = request.args.get("carrier")
    plans = get_plans(carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/changes")
def api_changes():
    try:
        limit = min(int(request.args.get("limit", 20)), 500)
    except (ValueError, TypeError):
        limit = 20
    changes = get_changes(limit=limit, db_path=_db_path())
    return jsonify(changes)


@app.route("/api/abroad-plans")
def api_abroad_plans():
    carrier = request.args.get("carrier")
    plans = get_abroad_plans(carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/global-plans")
def api_global_plans():
    carrier = request.args.get("carrier")
    plans = get_global_plans(carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/exchange-rates")
def api_exchange_rates():
    from scraper import _get_usd_to_ils, _get_eur_to_ils
    return jsonify({"usd": _get_usd_to_ils(), "eur": _get_eur_to_ils()})


@app.route("/api/global-changes")
def api_global_changes():
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
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
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-global-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@app.route("/api/abroad-changes")
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

        results["status"] = "ok"
        results["total_plans"] = len(new_domestic) + len(new_abroad) + len(new_global) + len(new_content)
        results["total_changes"] = len(ch_domestic) + len(ch_abroad) + len(ch_global) + len(ch_content)
        logger.info(f"scrape-all-now: {results}")
        return jsonify(results)
    except Exception as e:
        logger.error(f"scrape-all-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


@app.route("/api/content-plans")
def api_content_plans():
    carrier = request.args.get("carrier")
    service = request.args.get("service")
    plans = get_content_plans(service=service, carrier=carrier, db_path=_db_path())
    return jsonify(plans)


@app.route("/api/content-changes")
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
        return jsonify({"plans": len(new_plans), "changes": len(changes), "status": "ok"})
    except Exception as e:
        logger.error(f"scrape-now failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500


# ── Price Alerts Routes ────────────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
@require_api_key
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
@require_api_key
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
@require_api_key
def api_delete_alert(alert_id):
    delete_price_alert(alert_id, db_path=_db_path())
    return jsonify({"status": "deleted"})


# ── Push Notification Routes ───────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
@require_api_key
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
            return f"₪{p}" if p is not None else "—"

        def fmt_gb(g):
            if g is None: return "ללא הגבלה"
            return f"{round(g*1024)}MB" if g < 1 else f"{g}GB"

        lines = [
            "אתה עוזר נתונים עבור מערכת השוואת חבילות סלולר ישראלית.",
            "להלן הנתונים הנוכחיים מהמסד נתונים. ענה בעברית, בצורה תמציתית וברורה.",
            f"תאריך עדכון: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "",
        ]

        # Domestic plans
        domestic = get_plans(db_path=_db_path())
        if domestic:
            lines.append("## חבילות ביתיות (ישראל)")
            for p in domestic:
                lines.append(
                    f"  {p['carrier']} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
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
                    f"  {p['carrier']} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{p.get('days','')} ימים | {fmt_gb(p.get('data_gb'))}"
                    + (f" | extras: {';'.join(p['extras'])}" if p.get('extras') else "")
                )

        # Global plans (limit to avoid token overflow)
        global_plans = get_global_plans(db_path=_db_path())[:500]
        if global_plans:
            lines.append("")
            lines.append("## חבילות גלובליות (eSIM)")
            for p in global_plans:
                lines.append(
                    f"  {p['carrier']} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{p.get('days','')} ימים | {fmt_gb(p.get('data_gb'))}"
                    + (f" | extras: {';'.join(p['extras'])}" if p.get('extras') else "")
                )

        # Content services
        content = get_content_plans(db_path=_db_path())
        if content:
            lines.append("")
            lines.append("## שירותי תוכן")
            for p in content:
                lines.append(
                    f"  {p['service']} | {p['carrier']} | {p.get('price','')} | "
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


@app.route("/api/push/subscribe", methods=["POST"])
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
@limiter.limit("30 per minute")
def api_my_role():
    """Return the role of the currently authenticated Supabase user.
    Verifies JWT signature (HS256) + expiry, then queries DB directly (bypasses RLS)."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({"role": "viewer"})
    token = auth[7:]
    payload = _verify_supabase_jwt(token)
    if not payload:
        return jsonify({"role": "viewer"}), 401
    user_id = payload.get('sub')
    if not user_id:
        return jsonify({"role": "viewer"}), 401
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("SELECT role FROM public.user_roles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        conn.close()
        return jsonify({"role": row[0] if row else "viewer"})
    except Exception as e:
        logger.error(f"my-role failed: {e}")
        return jsonify({"role": "viewer"})


@app.route("/api/users")
@require_api_key
@limiter.limit("20 per minute")
def api_get_users():
    """List all users from Supabase via direct DB connection."""
    try:
        conn = _supabase_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.created_at, COALESCE(r.role, 'viewer') as role
            FROM auth.users u
            LEFT JOIN public.user_roles r ON u.id = r.user_id
            ORDER BY u.created_at DESC
        """)
        users = [{'id': str(row[0]), 'email': row[1], 'created_at': str(row[2]), 'role': row[3]} for row in cur.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        logger.error(f"get users failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/users", methods=["POST"])
@require_api_key
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
@require_api_key
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
@require_api_key
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
        except Exception as e:
            logger.error(f"Scrape job failed: {e}", exc_info=True)

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
    scheduler.start()
    logger.info("Flask starting → http://0.0.0.0:5000")
    try:
        host = os.environ.get("FLASK_HOST", "127.0.0.1")  # Use 0.0.0.0 only for ngrok/LAN
        app.run(host=host, port=5000, debug=False, use_reloader=False)
    finally:
        scheduler.shutdown()
