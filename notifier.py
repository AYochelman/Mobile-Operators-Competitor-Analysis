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
    """Send daily Excel report as email attachment via Outlook SMTP."""
    sender    = config.get("email_sender", "")
    password  = config.get("email_password", "")
    recipient = config.get("email_recipient", "")
    if not all([sender, password, recipient]):
        return False

    today = datetime.now().strftime("%d.%m.%Y")
    filename = f"cellular_report_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    msg = MIMEMultipart()
    msg["From"]    = sender
    msg["To"]      = recipient
    msg["Subject"] = f'דו"ח סריקת מתחרים – {today}'

    body = (
        f"שלום,\n\n"
        f"מצורף דו\"ח חבילות הסלולר של {today}.\n"
        f"שורות המסומנות בצהוב עברו שינוי ב-24 השעות האחרונות.\n\n"
        f"📊 http://localhost:5000"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(excel_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.office365.com", 587, timeout=20) as server:
            server.starttls(context=context)
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        return True
    except Exception:
        return False


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
