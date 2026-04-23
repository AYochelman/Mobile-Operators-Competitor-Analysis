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

GLOBAL_PROVIDER_NAMES = {
    "tuki":             "Tuki",
    "globalesim":       "GlobaleSIM",
    "airalo":           "Airalo",
    "pelephone_global": "GlobalSIM - Pelephone",
    "esimo":            "eSIMo",
    "simtlv":           "SimTLV",
    "world8":           "8 World",
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
            elif ct == "details_change":
                lines.append(f"📋 {ch['plan_name']}: {ch['new_val']} (היה: {ch['old_val']})")

    lines += ["", "📊 http://localhost:5000"]
    return "\n".join(lines)


def format_abroad_message(changes):
    now = datetime.now().strftime("%H:%M")
    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch["carrier"]].append(ch)

    n = len(by_carrier)
    suffix = "חברה" if n == 1 else "חברות"
    lines = [
        f"✈️ חבילות חו\"ל | עדכון {now}",
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
                try:
                    arrow = "↘" if float(new) < float(old) else "↗"
                except (TypeError, ValueError):
                    arrow = "↕"
                lines.append(f"{arrow} {ch['plan_name']}: ₪{old} ← ₪{new}")
            elif ct == "new_plan":
                lines.append(f"✨ חבילה חדשה: {ch['plan_name']} ב-₪{ch['new_val']}")
            elif ct == "removed_plan":
                lines.append(f"❌ הוסרה: {ch['plan_name']}")
            elif ct == "extras_change":
                lines.append(f"🔄 שינוי פרטים: {ch['plan_name']}")
            elif ct == "details_change":
                lines.append(f"📋 {ch['plan_name']}: {ch['new_val']} (היה: {ch['old_val']})")

    lines += ["", "📊 http://localhost:5000"]
    return "\n".join(lines)


def format_global_message(changes):
    now = datetime.now().strftime("%H:%M")
    by_provider = defaultdict(list)
    for ch in changes:
        by_provider[ch["carrier"]].append(ch)

    n = len(by_provider)
    suffix = "ספק" if n == 1 else "ספקים"
    lines = [
        f"🌍 חבילות גלובליות | עדכון {now}",
        "",
        f"🔔 זוהו שינויים ב-{n} {suffix}",
    ]

    for carrier, carrier_changes in by_provider.items():
        name = GLOBAL_PROVIDER_NAMES.get(carrier, carrier)
        lines.append(f"\n● {name}")
        for ch in carrier_changes:
            ct = ch["change_type"]
            if ct == "price_change":
                old, new = ch["old_val"], ch["new_val"]
                try:
                    arrow = "↘" if float(new) < float(old) else "↗"
                except (TypeError, ValueError):
                    arrow = "↕"
                lines.append(f"{arrow} {ch['plan_name']}: ₪{old} ← ₪{new}")
            elif ct == "new_plan":
                lines.append(f"✨ חבילה חדשה: {ch['plan_name']} ב-₪{ch['new_val']}")
            elif ct == "removed_plan":
                lines.append(f"❌ הוסרה: {ch['plan_name']}")
            elif ct == "extras_change":
                lines.append(f"🔄 שינוי פרטים: {ch['plan_name']}")
            elif ct == "details_change":
                lines.append(f"📋 {ch['plan_name']}: {ch['new_val']} (היה: {ch['old_val']})")

    lines += ["", "📊 http://localhost:5000"]
    return "\n".join(lines)


def format_content_message(changes):
    now = datetime.now().strftime("%H:%M")
    by_service = defaultdict(list)
    for ch in changes:
        by_service[ch["service"]].append(ch)

    n = len(by_service)
    suffix = "שירות" if n == 1 else "שירותים"
    lines = [
        f"📺 שירותי תוכן | עדכון {now}",
        "",
        f"🔔 זוהו שינויים ב-{n} {suffix}",
    ]

    for service, service_changes in by_service.items():
        lines.append(f"\n● {service}")
        for ch in service_changes:
            ct = ch["change_type"]
            carrier_name = CARRIER_NAMES.get(ch.get("carrier", ""), ch.get("carrier", ""))
            if ct == "price_change":
                lines.append(f"💰 {carrier_name}: {ch['old_val']} ← {ch['new_val']}")
            elif ct == "new_service":
                lines.append(f"✨ {carrier_name}: חדש — {ch['new_val']}")
            elif ct == "trial_change":
                lines.append(f"🎁 {carrier_name}: ניסיון {ch['old_val']} ← {ch['new_val']}")

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
    subscriptions = get_push_subscriptions(db_path=db_path)
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
        delete_push_subscription(ep, db_path=db_path)
    return sent


CARRIER_DISPLAY_NAMES = {
    "partner": "פרטנר", "pelephone": "פלאפון", "hotmobile": "הוט מובייל",
    "cellcom": "סלקום", "mobile019": "019", "xphone": "XPhone",
    "wecom": "We-Com", "neptucom": "Neptucom",
    "tuki": "Tuki", "globalesim": "GlobaleSIM", "airalo": "Airalo",
    "pelephone_global": "GlobalSIM", "esimo": "eSIMo", "simtlv": "SimTLV",
    "world8": "8 World", "saily": "Saily", "holafly": "Holafly",
    "esimio": "eSIM.io", "xphone_global": "XPhone Global", "sparks": "Sparks",
    "voye": "VOYE", "orbit": "Orbit", "travelsim": "Travel Sim",
}

APP_URL = "https://lucent-kulfi-f037ad.netlify.app"


def send_price_alert_email(user_email: str, alert: dict, matching_plans: list, config: dict) -> bool:
    """Send a price-alert notification email via SendGrid to the subscriber."""
    api_key = config.get("sendgrid_api_key", "")
    sender  = config.get("email_sender", "")
    if not all([api_key, sender, user_email]):
        return False

    carrier_name = CARRIER_DISPLAY_NAMES.get(alert.get("carrier", ""), alert.get("carrier") or "כל הספקים")
    tab_label    = {"domestic": "חבילות סלולר", "abroad": "חו\"ל", "global": "גלובלי"}.get(alert.get("tab", ""), alert.get("tab", ""))

    lines = []
    for p in matching_plans:
        name = p.get("plan_name", "")
        price = p.get("price", "")
        c = CARRIER_DISPLAY_NAMES.get(p.get("carrier", ""), p.get("carrier", ""))
        lines.append(f"  • {name} ({c}) — \u20aa{price}")

    plans_text = "\n".join(lines)
    body = (
        f"\u05e9\u05dc\u05d5\u05dd,\n\n"
        f"\u05d4\u05ea\u05e8\u05d0\u05d4 \u05e9\u05d4\u05d2\u05d3\u05e8\u05ea \u05d1-MOCA \u05d4\u05d5\u05e4\u05e2\u05dc\u05d4.\n"
        f"\u05e1\u05d5\u05d2: {tab_label}\n"
        f"\u05e1\u05e3: \u20aa{alert['threshold']}\n\n"
        f"\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05e9\u05e2\u05d5\u05e0\u05d3\u05ea\u05d5 \u05dc\u05e1\u05d3 \u05d4\u05d2\u05d3\u05e8\u05ea \u05d4\u05ea\u05e8\u05d0\u05d4:\n{plans_text}\n\n"
        f"\u05e6\u05e4\u05d4 \u05d1\u05d0\u05e4\u05dc\u05d9\u05e7\u05e6\u05d9\u05d4: {APP_URL}\n\n"
        f"MOCA \u2014 \u05de\u05e2\u05e8\u05db\u05ea \u05d4\u05e9\u05d5\u05d5\u05d0\u05ea \u05e1\u05dc\u05d5\u05dc\u05e8"
    )

    subject = f"MOCA \u05d4\u05ea\u05e8\u05d0\u05ea \u05de\u05d7\u05d9\u05e8: {carrier_name} \u05d9\u05e8\u05d3 \u05de\u05ea\u05d7\u05ea \u05dc-\u20aa{alert['threshold']}"

    payload = {
        "personalizations": [{"to": [{"email": user_email}]}],
        "from": {"email": sender},
        "subject": subject,
        "content": [{"type": "text/plain; charset=utf-8", "value": body}],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        return resp.status_code == 202
    except requests.RequestException:
        return False


def send_whatsapp(message, config):
    base_url = config.get("greenapi_url", "")
    instance = config.get("greenapi_instance", "")
    token = config.get("greenapi_token", "")
    group_id = config.get("whatsapp_group_id", "")
    phone = config.get("whatsapp_phone", "")
    if not all([base_url, instance, token]) or not (group_id or phone):
        return False
    url = f"{base_url}/waInstance{instance}/sendMessage/{token}"
    chat_id = group_id if group_id else f"{phone}@c.us"
    try:
        resp = requests.post(
            url,
            json={"chatId": chat_id, "message": message},
            timeout=10
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False
