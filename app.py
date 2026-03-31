import json
import os
import logging
from flask import Flask, jsonify, render_template, request
from db import init_db, get_plans, get_changes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

app = Flask(__name__)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _db_path():
    """Return test DB path when running under pytest, else default (None = use DB_PATH in db.py)."""
    return app.config.get("TEST_DB_PATH") or None


@app.route("/")
def index():
    return render_template("index.html")


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


if __name__ == "__main__":
    from apscheduler.schedulers.background import BackgroundScheduler
    from change_detector import detect_changes
    from notifier import format_message, send_notification
    import scraper

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
                ok = send_notification(msg, config)
                logger.info(f"Telegram sent: {ok}")
            else:
                logger.info("No changes.")
            logger.info(f"Done. {len(new_plans)} plans, {len(changes)} changes.")
        except Exception as e:
            logger.error(f"Scrape job failed: {e}", exc_info=True)

    init_db()
    config = load_config()
    scheduler = BackgroundScheduler()
    for time_str in config.get("schedule_times", ["10:00", "16:00"]):
        hour, minute = map(int, time_str.split(":"))
        scheduler.add_job(run_scrape_job, "cron", hour=hour, minute=minute)
    scheduler.start()
    logger.info("Flask starting → http://localhost:5000")
    try:
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
    finally:
        scheduler.shutdown()
