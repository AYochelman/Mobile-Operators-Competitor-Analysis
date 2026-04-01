import json
import requests
import smtplib
import ssl
from datetime import datetime
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

CARRIER_NAMES = {
    "partner":   "פרטנר",
    "pelephone": "פלאפון",
    "hotmobile": "הוט מובייל",
    "cellcom":   "סלקום",
    "mobile019": "019",
}


def format_message(changes):
    now = datetime.now().strftime("%H:%M")
    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch["carrier"]].append(ch)

    n = len(by_carrier)
    suffix = "חברה" if n == 1 else "חברות"
    lines = [
        f"📱 השוואת סלולר | עדכון {now}",
        "",
        f"🔔 זוהו שינויים ב-{n} {suffix}",
    ]

    for carrier, carrier_changes in by_carrier.items():
        name = CARRIER_NAMES.get(carrier, carrier)
        lines.append(f"\n● {name}")
        for ch in carrier_changes:
            ct = ch["change_type"]
            if ct == "price_change":
                old, new = ch["old_val"], ch["new_val"]
                arrow = "↘" if new < old else "↗"
                lines.append(f"{arrow} {ch['plan_name']}: ₪{old} ← ₪{new}")
            elif ct == "new_plan":
                lines.append(f"✨ חבילה חדשה: {ch['plan_name']} ב-₪{ch['new_val']}")
            elif ct == "removed_plan":
                lines.append(f"❌ הוסרה: {ch['plan_name']}")
            elif ct == "extras_change":
                lines.append(f"🔄 שינוי הטבות: {ch['plan_name']}")

    lines += ["", "📊 http://localhost:5000"]
    return "\n".join(lines)


def send_notification(message, config):
    token = config["telegram_bot_token"]
    chat_id = config["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def send_email_report(excel_bytes: bytes, config: dict) -> bool:
    """Send daily Excel report as email attachment via SendGrid API."""
    import base64
    api_key   = config.get("sendgrid_api_key", "")
    sender    = config.get("email_sender", "")
    recipient = config.get("email_recipient", "")
    if not all([api_key, sender, recipient]):
        return False

    today    = datetime.now().strftime("%d.%m.%Y")
    filename = f"cellular_report_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    body = (
        f"שלום,\n\n"
        f"מצורף דו\"ח חבילות הסלולר של {today}.\n"
        f"שורות המסומנות בצהוב עברו שינוי ב-24 השעות האחרונות.\n\n"
        f"http://localhost:5000"
    )
    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": sender},
        "subject": f'דו"ח סריקת מתחרים - {today}',
        "content": [{"type": "text/plain; charset=utf-8", "value": body}],
        "attachments": [{
            "content":     base64.b64encode(excel_bytes).decode(),
            "filename":    filename,
            "type":        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "disposition": "attachment",
        }],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        return resp.status_code == 202
    except requests.RequestException:
        return False


def send_push_notifications(changes, config, db_path=None):
    """Send Web Push notifications to all subscribed devices."""
    from db import get_push_subscriptions, delete_push_subscription
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return 0
    vapid_private_key = config.get("vapid_private_key")
    if not vapid_private_key:
        return 0
    subscriptions = get_push_subscriptions(db_path)
    if not subscriptions:
        return 0
    n_carriers = len({c["carrier"] for c in changes})
    body = f"זוהו {len(changes)} שינויים ב-{n_carriers} חברות"
    payload = json.dumps({"title": "השוואת סלולר", "body": body}, ensure_ascii=False)
    vapid_email = config.get("vapid_email", "mailto:alon.yoch@gmail.com")
    sent, stale = 0, []
    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_email},
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None) if hasattr(e, "response") and e.response else None
            if status in (404, 410):
                stale.append(sub["endpoint"])
        except Exception:
            pass
    for ep in stale:
        delete_push_subscription(ep, db_path)
    return sent


def send_whatsapp(message, config):
    base_url = config.get("greenapi_url", "")
    instance = config.get("greenapi_instance", "")
    token = config.get("greenapi_token", "")
    phone = config.get("whatsapp_phone", "")
    if not all([base_url, instance, token, phone]):
        return False
    url = f"{base_url}/waInstance{instance}/sendMessage/{token}"
    chat_id = f"{phone}@c.us"
    try:
        resp = requests.post(
            url,
            json={"chatId": chat_id, "message": message},
            timeout=10
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False
