# -*- coding: utf-8 -*-
"""
MOCA Facebook posting reminder.
Reads docs/marketing/b2c-launch/fb-content-calendar.json daily; when a pending post
is due today (or overdue and not yet reminded today) it sends the ready-to-publish
post to Telegram, and warns when the pending backlog is low so Claude regenerates
the next 2 weeks. Run daily via Task Scheduler. Use --test to send a sample now.
"""
import json
import os
import sys
import datetime
from datetime import date

ROOT = r"D:\השוואת MASS MARKET"
CONFIG = os.path.join(ROOT, "config.json")
CAL = os.path.join(ROOT, "docs", "marketing", "b2c-launch", "fb-content-calendar.json")
LOG = os.path.join(ROOT, "scripts", "fb_post_reminder.log")


def _log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] {msg}\n")
    except Exception:
        pass
    print(msg)


def _telegram(msg, cfg):
    import requests
    token = cfg.get("telegram_bot_token")
    chat_id = cfg.get("telegram_chat_id")
    if not token or not chat_id:
        print("no telegram creds in config.json")
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat_id, "text": msg,
                                "disable_web_page_preview": True}, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print("telegram error", str(e)[:120])
        return False


def _post_msg(p, image_dir):
    img = os.path.join(image_dir, p["image"])
    return (
        f"🗓️ תזכורת פרסום MOCA — {p['title']}\n"
        f"({p['date']} בשעה {p.get('time', '')})\n\n"
        f"{p['body']}\n\n"
        f"🔗 לינק מתויג (לשים בתגובה הראשונה):\n{p['link']}\n\n"
        f"🖼️ תמונה:\n{img}\n\n"
        f"כשמוכן: פתח פוסט חדש בעמוד, הדבק את הטקסט, צרף את התמונה, פרסם, "
        f"ושים את הלינק בתגובה הראשונה. או תגיד לקלוד \"קדימה\" והוא יכין לך אותו בדפדפן."
    )


def main():
    test = "--test" in sys.argv
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    data = json.load(open(CAL, encoding="utf-8"))
    meta = data.get("meta", {})
    image_dir = meta.get("image_dir", "")
    threshold = meta.get("pipeline_low_threshold", 1)
    posts = data["posts"]
    today = date.today().isoformat()

    if test:
        sample = next((p for p in posts if p["status"] == "pending"), posts[-1])
        ok = _telegram("✅ בדיקת תזכורת MOCA (test)\n\n" + _post_msg(sample, image_dir), cfg)
        _log(f"test sent: {ok}")
        return

    pending = [p for p in posts if p["status"] == "pending"]
    due = [p for p in pending if p["date"] <= today and p.get("last_reminded") != today]

    changed = False
    for p in due:
        if _telegram(_post_msg(p, image_dir), cfg):
            p["last_reminded"] = today
            changed = True
            _log(f"reminded {p['id']} ({p['title']})")

    # low-backlog warning (dedupe per day)
    if len(pending) <= threshold and meta.get("low_warned_date") != today:
        warn = (f"⚠️ נשארו {len(pending)} פוסטים בלוח הפרסום של MOCA.\n"
                f"בקש מקלוד לייצר את השבועיים הבאים: יעדים חדשים + נוסח שיווקי + לינקים מתויגים + תמונות.")
        if _telegram(warn, cfg):
            meta["low_warned_date"] = today
            changed = True
            _log(f"low-backlog warned ({len(pending)} pending)")

    if changed:
        json.dump(data, open(CAL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not due and len(pending) > threshold:
        _log(f"nothing due today {today} ({len(pending)} pending)")


if __name__ == "__main__":
    main()
