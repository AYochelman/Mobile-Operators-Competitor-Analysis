"""
booking_notifier.py — WhatsApp alert on a new Google Calendar appointment booking.

Polls the calendar's PRIVATE iCal feed (a secret URL, no OAuth) so it is
unaffected by Google Advanced Protection — which blocks custom Apps Scripts.
Finds new bookings whose title contains the keyword ("Moca"), and sends a
WhatsApp via the existing Green API helper (notifier.send_whatsapp).

Scheduled every few minutes by app.py's APScheduler. Dedup state is kept in
data/booking_seen.json (a JSON list of event UIDs already announced). On the
very first run the current bookings are SEEDED (recorded, not announced) so we
never blast pre-existing events.
"""
import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta

import requests

from notifier import send_whatsapp

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.abspath(__file__))
SEEN_PATH = os.path.join(_BASE, "data", "booking_seen.json")

try:
    from zoneinfo import ZoneInfo
    _IL = ZoneInfo("Asia/Jerusalem")
except Exception:  # pragma: no cover - fallback for Python < 3.9
    _IL = timezone(timedelta(hours=3))


def _load_config():
    try:
        with open(os.path.join(_BASE, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_seen():
    """Return a set of seen UIDs, or None on the first run (file absent)."""
    try:
        with open(SEEN_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return None
    except Exception:
        return set()


def _save_seen(seen):
    try:
        os.makedirs(os.path.dirname(SEEN_PATH), exist_ok=True)
        with open(SEEN_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(seen), f)
    except Exception as e:
        logger.warning(f"booking_notifier: could not save seen file: {e}")


def _field(block, name):
    """Extract an iCal property value (ignoring ;params) from a VEVENT block."""
    m = re.search(r"^" + name + r"(?:;[^:\r\n]*)?:(.*)$", block, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _fmt_time(raw):
    """Format an iCal DTSTART (UTC 'Z', local, or date-only) as Israel time."""
    try:
        if raw.endswith("Z"):
            dt = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        elif "T" in raw:
            dt = datetime.strptime(raw[:15], "%Y%m%dT%H%M%S").replace(tzinfo=_IL)
        else:
            return datetime.strptime(raw[:8], "%Y%m%d").strftime("%d/%m/%Y")
        return dt.astimezone(_IL).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return raw


def _booker(description, summary):
    """Pull the booker's name/email from the 'Booked by' DESCRIPTION block,
    falling back to the parenthetical in the SUMMARY."""
    if description:
        d = (description.replace("\\n", "\n")
                        .replace("\\,", ",")
                        .replace("\\\\", "\\"))
        d = re.sub(r"<[^>]+>", "", d)  # strip HTML tags
        lines = [ln.strip() for ln in d.split("\n") if ln.strip()]
        for i, ln in enumerate(lines):
            if "booked by" in ln.lower():
                parts = lines[i + 1:i + 3]
                if len(parts) >= 2:
                    return f"{parts[0]} ({parts[1]})"
                if parts:
                    return parts[0]
    m = re.search(r"\(([^)]+)\)\s*$", summary)
    return m.group(1).strip() if m else ""


def check_new_bookings(config=None):
    """Poll the iCal feed and WhatsApp any new keyword-matching bookings."""
    cfg = config if config is not None else _load_config()
    url = (cfg.get("booking_ical_url") or "").strip()
    if not url:
        return
    keyword = (cfg.get("booking_keyword") or "Moca").strip()

    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        raw = resp.text
    except Exception as e:
        logger.warning(f"booking_notifier: iCal fetch failed: {e}")
        return

    content = re.sub(r"\r?\n[ \t]", "", raw)  # unfold folded iCal lines
    blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", content, re.DOTALL)

    matches = []
    for b in blocks:
        summary = _field(b, "SUMMARY")
        if keyword.lower() not in summary.lower():
            continue
        uid = _field(b, "UID")
        if uid:
            matches.append((uid, summary, _field(b, "DTSTART"), _field(b, "DESCRIPTION")))

    seen = _load_seen()
    if seen is None:  # first run → learn the current state, announce nothing
        _save_seen({uid for uid, _s, _dt, _de in matches})
        logger.info(f"booking_notifier: seeded {len(matches)} existing booking(s)")
        return

    # Send to the dedicated booking number, falling back to the general one.
    wa_cfg = dict(cfg)
    wa_cfg["whatsapp_group_id"] = ""
    wa_cfg["whatsapp_phone"] = (cfg.get("booking_whatsapp_phone")
                                or cfg.get("whatsapp_phone") or "")

    sent_any = False
    for uid, summary, dtstart, description in matches:
        if uid in seen:
            continue
        title = re.sub(r"\s*\([^)]*\)\s*$", "", summary)
        title = re.sub(r"\s{2,}", " ", title).strip()
        when = _fmt_time(dtstart)
        who = _booker(description, summary)
        msg = "📅 פגישה חדשה נקבעה דרך דף הנחיתה!\n\n"
        msg += f"🗓️ {title}\n🕒 {when}"
        if who:
            msg += f"\n👤 {who}"
        ok = send_whatsapp(msg, wa_cfg)
        logger.info(f"booking_notifier: notified uid={uid} sent={ok}")
        seen.add(uid)
        sent_any = True

    if sent_any:
        _save_seen(seen)


if __name__ == "__main__":  # manual test: python booking_notifier.py
    logging.basicConfig(level=logging.INFO)
    check_new_bookings()
