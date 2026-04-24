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
        "content": [{"type": "text/plain", "value": body}],
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
        hidden = sub.get("hidden_carrier")
        visible = [c for c in changes if not hidden or c.get("carrier") != hidden]
        if not visible:
            continue
        n_c = len({c["carrier"] for c in visible})
        body = f"זוהו {len(visible)} שינויים ב-{n_c} חברות"
        pld = json.dumps({"title": "השוואת סלולר", "body": body}, ensure_ascii=False)
        sub_info = {"endpoint": sub["endpoint"], "keys": sub["keys"]}
        try:
            webpush(
                subscription_info=sub_info,
                data=pld,
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
        "content": [{"type": "text/plain", "value": body}],
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


def send_contact_email(from_email: str, workspace_name: str, message: str, config: dict) -> bool:
    """Send an in-app contact request from a suspended/active user to the MOCA operator.

    Delivers to config['email_recipient'] (the MOCA admin mailbox). The
    requester's email is placed in Reply-To so a simple 'Reply' in the admin's
    client goes back to them directly.
    """
    api_key   = config.get("sendgrid_api_key", "")
    sender    = config.get("email_sender", "")
    recipient = config.get("email_recipient", "")
    if not all([api_key, sender, recipient, from_email, message]):
        return False

    ws_label = workspace_name or "(\u05dc\u05dc\u05d0 workspace)"
    body = (
        f"\u05e4\u05e0\u05d9\u05d9\u05d4 \u05d7\u05d3\u05e9\u05d4 \u05de\u05ea\u05d5\u05da MOCA\n\n"
        f"\u05de: {from_email}\n"
        f"Workspace: {ws_label}\n"
        f"\u05ea\u05d0\u05e8\u05d9\u05da: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"---\n\n{message}\n"
    )
    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": sender},
        "reply_to": {"email": from_email},
        "subject": f"MOCA — \u05e4\u05e0\u05d9\u05d9\u05ea \u05e7\u05e9\u05e8 \u05de {ws_label}",
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        if resp.status_code != 202:
            import logging as _log
            _log.getLogger(__name__).error(
                f"send_contact_email SendGrid {resp.status_code}: {resp.text[:400]}"
            )
        return resp.status_code == 202
    except requests.RequestException as e:
        import logging as _log
        _log.getLogger(__name__).error(f"send_contact_email network error: {e}")
        return False


def send_weekly_digest(to_emails: list, workspace_name: str, changes: list, config: dict) -> bool:
    """Send a weekly changes digest to all users of a workspace.
    Changes is a flat list of change dicts (carrier, plan_name, change_type, old_val, new_val, changed_at).
    Returns True if all emails were dispatched successfully."""
    api_key = config.get("sendgrid_api_key", "")
    sender  = config.get("email_sender", "")
    if not all([api_key, sender]) or not to_emails:
        return False
    if not changes:
        return True  # nothing to report — skip silently

    app_url = "https://lucent-kulfi-f037ad.netlify.app"
    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch.get('carrier', '')].append(ch)

    lines = [
        f"\u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2\u05d9 \u05e9\u05dc MOCA \u2014 {workspace_name}\n",
        f"\u05ea\u05d0\u05e8\u05d9\u05da: {datetime.now().strftime('%d/%m/%Y')}\n",
        f"\u05e1\u05d4\"\u05db {len(changes)} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05d1-7 \u05d9\u05de\u05d9\u05dd \u05d4\u05d0\u05d7\u05e8\u05d5\u05e0\u05d9\u05dd\n\n",
    ]
    CHANGE_HE = {
        'price_change':  '\u05e9\u05d9\u05e0\u05d5\u05d9 \u05de\u05d7\u05d9\u05e8',
        'new_plan':      '\u05d7\u05d1\u05d9\u05dc\u05d4 \u05d7\u05d3\u05e9\u05d4',
        'removed_plan':  '\u05d4\u05d5\u05e1\u05e8\u05d4',
        'extras_change': '\u05e9\u05d9\u05e0\u05d5\u05d9 \u05d4\u05d8\u05d1\u05d5\u05ea',
    }
    for carrier, chs in sorted(by_carrier.items()):
        lines.append(f"\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n{carrier} ({len(chs)} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd)\n")
        for ch in chs[:6]:
            kind   = CHANGE_HE.get(ch.get('change_type', ''), ch.get('change_type', ''))
            old_v  = ch.get('old_val', '')
            new_v  = ch.get('new_val', '')
            suffix = f" \u2014 {old_v} \u2192 {new_v}" if old_v or new_v else ''
            lines.append(f"  \u2022 {ch.get('plan_name','')} [{kind}]{suffix}\n")
        if len(chs) > 6:
            lines.append(f"  ... \u05d5\u05e2\u05d5\u05d3 {len(chs)-6} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd\n")
    lines.append(f"\n\u05dc\u05e6\u05e4\u05d9\u05d9\u05d4 \u05de\u05dc\u05d0\u05d4: {app_url}\n\n\u05e6\u05d5\u05d5\u05ea MOCA")

    body = ''.join(lines)
    ok = True
    for email in to_emails:
        payload = {
            "personalizations": [{"to": [{"email": email}]}],
            "from": {"email": sender},
            "subject": f"MOCA \u2014 \u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2\u05d9 \u05e2\u05d1\u05d5\u05e8 {workspace_name}",
            "content": [{"type": "text/plain", "value": body}],
        }
        try:
            resp = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=20,
            )
            if resp.status_code != 202:
                import logging as _log
                _log.getLogger(__name__).error(f"weekly_digest SendGrid {resp.status_code} for {email}: {resp.text[:200]}")
                ok = False
        except requests.RequestException as e:
            import logging as _log
            _log.getLogger(__name__).error(f"weekly_digest network error for {email}: {e}")
            ok = False
    return ok


def send_welcome_email(to_email: str, workspace_name: str, role: str, config: dict) -> bool:
    """Send a welcome email to a newly assigned workspace user."""
    api_key = config.get("sendgrid_api_key", "")
    sender  = config.get("email_sender", "")
    if not all([api_key, sender, to_email]):
        return False

    app_url = "https://lucent-kulfi-f037ad.netlify.app"
    role_he = "\u05de\u05e0\u05d4\u05dc" if role == "admin" else "\u05e6\u05d5\u05e4\u05d4"
    body = (
        f"\u05e9\u05dc\u05d5\u05dd,\n\n"
        f"\u05e0\u05d5\u05e1\u05e4\u05ea \u05dc-workspace \u05e9\u05dc {workspace_name} \u05d1-MOCA "
        f"\u05d1\u05ea\u05e4\u05e7\u05d9\u05d3 {role_he}.\n\n"
        f"\u05db\u05e0\u05d9\u05e1\u05d4 \u05dc\u05d0\u05e4\u05dc\u05d9\u05e7\u05e6\u05d9\u05d4:\n{app_url}\n\n"
        f"\u05d0\u05dd \u05d0\u05d9\u05df \u05dc\u05da \u05d7\u05e9\u05d1\u05d5\u05df \u05e2\u05d3\u05d9\u05d9\u05df, "
        f"\u05d4\u05d9\u05e8\u05e9\u05dd \u05d1\u05d0\u05d5\u05ea\u05d5 \u05d0\u05d9\u05de\u05d9\u05d9\u05dc "
        f"\u05d1\u05d3\u05e3 \u05d4\u05db\u05e0\u05d9\u05e1\u05d4.\n\n"
        f"\u05d1\u05d1\u05e8\u05db\u05d4,\n\u05e6\u05d5\u05d5\u05ea MOCA"
    )
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": sender},
        "subject": f"MOCA \u2014 \u05d4\u05ea\u05d5\u05d5\u05e1\u05e4\u05ea \u05dc-{workspace_name}",
        "content": [{"type": "text/plain", "value": body}],
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
