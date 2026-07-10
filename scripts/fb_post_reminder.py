# -*- coding: utf-8 -*-
"""
MOCA Facebook posting reminder.
Reads docs/marketing/b2c-launch/fb-content-calendar.json daily; when a pending post
is due today (or overdue and not yet reminded today) it sends the ready-to-publish
post to Telegram, and warns when the pending backlog is low so Claude regenerates
the next 2 weeks. Also lints pending bodies for BiDi breakage (a line that contains
Hebrew but opens with a Latin word renders scrambled on Facebook) and warns daily.
Run daily via Task Scheduler. Use --test to send a sample now.
"""
import json
import os
import re
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


_HEB_RE = re.compile(r"[֐-׿]")
_STRONG_RE = re.compile(r"[A-Za-z֐-׿]")


def _bidi_problems(body):
    """Facebook sets each line's direction by its first strong character, so a line
    that contains Hebrew but whose first strong char is Latin (MOCA / 5GB / #eSIM)
    renders its Hebrew scrambled. All-English lines (the URL) are fine."""
    problems = []
    for i, line in enumerate(body.split("\n"), 1):
        line = line.strip()
        if not _HEB_RE.search(line):
            continue
        m = _STRONG_RE.search(line)
        if m and ord(m.group()) < 0x0590:
            problems.append(f"שורה {i} נפתחת באנגלית: {line[:35]}…")
    return problems


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
        msg = _post_msg(p, image_dir)
        probs = _bidi_problems(p["body"])
        if probs:
            msg = ("⚠️ אזהרת BiDi - שורות שיעלו משובשות בפייסבוק, לתקן לפני פרסום:\n"
                   + "\n".join("• " + pr for pr in probs) + "\n\n" + msg)
        if _telegram(msg, cfg):
            p["last_reminded"] = today
            changed = True
            _log(f"reminded {p['id']} ({p['title']})" + (" [BIDI WARN]" if probs else ""))

    # low-backlog warning (dedupe per day)
    if len(pending) <= threshold and meta.get("low_warned_date") != today:
        warn = (f"⚠️ נשארו {len(pending)} פוסטים בלוח הפרסום של MOCA.\n"
                f"בקש מקלוד לייצר את השבועיים הבאים: יעדים חדשים + נוסח שיווקי + לינקים מתויגים + תמונות.")
        if _telegram(warn, cfg):
            meta["low_warned_date"] = today
            changed = True
            _log(f"low-backlog warned ({len(pending)} pending)")

    # BiDi lint over the whole pending backlog (dedupe per day) - catches a broken
    # body days before it is due, not only on publish day
    bad = [(p, _bidi_problems(p["body"])) for p in pending]
    bad = [(p, probs) for p, probs in bad if probs]
    if bad and meta.get("bidi_warned_date") != today:
        lines = [f"⚠️ בדיקת BiDi: {len(bad)} פוסטים ממתינים יעלו משובשים בפייסבוק:"]
        for p, probs in bad:
            lines.append(f"\n{p['id']} - {p['title']}:")
            lines += ["• " + pr for pr in probs]
        lines.append("\nהכלל: כל שורה (כולל שורת ההאשטגים) מתחילה במילה בעברית. אפשר לבקש מקלוד לתקן את הקובץ.")
        if _telegram("\n".join(lines), cfg):
            meta["bidi_warned_date"] = today
            changed = True
            _log(f"bidi-warned {len(bad)} posts: {', '.join(p['id'] for p, _ in bad)}")

    if changed:
        json.dump(data, open(CAL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not due and len(pending) > threshold:
        _log(f"nothing due today {today} ({len(pending)} pending)")


if __name__ == "__main__":
    main()
