import json
import os
import logging
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory
from db import init_db, get_plans, get_changes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _db_path():
    """Return test DB path when running under pytest, else default (None = use DB_PATH in db.py)."""
    return app.config.get("TEST_DB_PATH") or None


def _ensure_vapid_keys(config_path):
    """Generate VAPID keys on first run and save to config.json."""
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg.get("vapid_public_key") and cfg.get("vapid_private_key"):
        return
    try:
        from py_vapid import Vapid
        v = Vapid()
        v.generate_keys()
        cfg["vapid_private_key"] = v.private_pem().decode()
        cfg["vapid_public_key"] = v.public_key
        cfg["vapid_email"] = f"mailto:{cfg.get('email_sender', 'alon.yoch@gmail.com')}"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        logger.info("VAPID keys generated and saved to config.json")
    except Exception as e:
        logger.error(f"VAPID key generation failed: {e}")


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
    limit = int(request.args.get("limit", 20))
    changes = get_changes(limit=limit, db_path=_db_path())
    return jsonify(changes)


@app.route("/api/scrape-now")
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
        return jsonify({"error": str(e)}), 500


# ── Push Notification Routes ───────────────────────────────────────────────

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
def api_push_test():
    """Debug: send a test push notification to all subscribed devices."""
    config = load_config()
    from notifier import send_push_notifications
    fake = [{"carrier": "partner", "plan_name": "טסט", "change_type": "price_change",
             "old_val": 100, "new_val": 90}]
    n = send_push_notifications(fake, config, _db_path())
    return jsonify({"sent": n})


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from apscheduler.schedulers.background import BackgroundScheduler
    from change_detector import detect_changes
    from notifier import format_message, send_notification, send_whatsapp, send_email_report, send_push_notifications
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
            new_plans = scraper.scrape_all()
            from db import save_plans, save_changes
            old_plans = get_plans()
            changes = detect_changes(old_plans, new_plans)
            save_plans(new_plans)
            if changes:
                save_changes(changes)
                msg = format_message(changes)
                ok_tg = send_notification(msg, config)
                logger.info(f"Telegram sent: {ok_tg}")
                ok_wa = send_whatsapp(msg, config)
                logger.info(f"WhatsApp sent: {ok_wa}")
                n_push = send_push_notifications(changes, config)
                logger.info(f"Web Push sent: {n_push}")
            else:
                logger.info("No changes.")
            logger.info(f"Done. {len(new_plans)} plans, {len(changes)} changes.")
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
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    finally:
        scheduler.shutdown()
