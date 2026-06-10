import base64
import html
import json
import logging
import os
import requests
import smtplib
import ssl
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.header import Header
from email.utils import formataddr

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


# Carriers with no "עיקרי התוכנית" terms link by design — never flag these as missing.
# neptucom = eSIM-only hardcoded list (no terms button); xphone roaming = scraped as
# plain text with no terms source. (See the plan-terms-coverage skill methodology table.)
_TERMS_EXEMPT = {("plans", "neptucom"), ("abroad_plans", "xphone")}


def _plan_has_terms(plan, table):
    """Backend view of 'does this plan expose terms': a scraped link
    (domestic → url, roaming → terms_url) or an in-app __info__ modal in extras."""
    extras = plan.get("extras") or []
    if isinstance(extras, (list, tuple)) and any("__info__" in str(e) for e in extras):
        return True
    if table == "abroad_plans":
        return bool(plan.get("terms_url"))
    return bool(plan.get("url"))


def alert_missing_terms(changes, plans, table, config):
    """Post-scrape safety net: if a NEWLY ADDED plan arrived with no "עיקרי התוכנית" terms
    link, send one operator-facing Telegram alert so the per-provider fetch can be wired in
    (every carrier now auto-captures terms, so a gap means a provider changed their page or a
    transient fetch failure — run the plan-terms-coverage skill). Returns the count flagged.

    changes — the (already dedup-filtered) change list for this scrape.
    plans   — the freshly scraped plan dicts (carry url / terms_url / extras).
    table   — 'plans' (domestic) or 'abroad_plans' (roaming). Global is affiliate-only and
              content always has its own modal, so callers don't pass those.
    Never raises — a failure here must not break a scrape.
    """
    try:
        if table not in ("plans", "abroad_plans"):
            return 0
        new_keys = {(c.get("carrier"), c.get("plan_name"))
                    for c in (changes or []) if c.get("change_type") == "new_plan"}
        if not new_keys:
            return 0
        by_key = {(p.get("carrier"), p.get("plan_name")): p for p in (plans or [])}
        missing = []
        for carrier, name in sorted(new_keys):
            if (table, carrier) in _TERMS_EXEMPT:
                continue
            plan = by_key.get((carrier, name))
            if plan is None:            # new_plan with no matching scraped row — skip
                continue
            if not _plan_has_terms(plan, table):
                missing.append((carrier, name))
        if not missing:
            return 0

        kind = "חו\"ל" if table == "abroad_plans" else "ארצית"
        lines = [
            "⚠️ MOCA — חבילה חדשה ללא \"עיקרי התוכנית\"",
            "",
            f"נוספו {len(missing)} חבילות ({kind}) בלי קישור תנאים — צריך לבדוק את שליפת התנאים מהספק:",
            "",
        ]
        for carrier, name in missing[:25]:
            cname = CARRIER_NAMES.get(carrier, carrier)
            lines.append(f"• {cname} — {name}")
        if len(missing) > 25:
            lines.append(f"… ועוד {len(missing) - 25}")
        lines += ["", "להרצה: סקיל plan-terms-coverage"]
        send_notification("\n".join(lines), config)
        return len(missing)
    except Exception as exc:
        logger.warning(f"alert_missing_terms failed: {exc}")
        return 0


import re as _re_slack

# Defence-in-depth: even if a caller forgets to validate, this final guard
# stops SSRF before requests.post is reached.
_SLACK_TEAMS_WEBHOOK_RE = _re_slack.compile(
    r'^https://(hooks\.slack\.com/|.+\.webhook\.office\.com/)'
)


def send_slack(message: str, webhook_url: str) -> bool:
    """Send a message to a Slack/Teams-compatible webhook URL.

    Slack and Microsoft Teams both accept POST {"text": "..."} on incoming-webhook URLs,
    so the same function works for both.

    The URL is validated against an allowlist (Slack hooks domain or any
    *.webhook.office.com host) to prevent the function from being weaponised as
    an SSRF gadget if a caller passes an attacker-controlled URL.
    """
    if not webhook_url:
        return False
    if not _SLACK_TEAMS_WEBHOOK_RE.match(webhook_url.strip()):
        # Refuse to send to unknown hosts. Log + return False so callers see failure.
        try:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "send_slack refused: webhook_url is not on Slack/Teams allowlist"
            )
        except Exception:
            pass
        return False
    try:
        resp = requests.post(webhook_url, json={"text": message}, timeout=10)
        return resp.status_code in (200, 201, 202, 204)
    except requests.RequestException:
        return False


_SENDGRID_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"


def _mime_attachment(att: dict):
    """Build a MIMEBase part from an abstract attachment dict
    {filename, content(bytes), mimetype, cid?}. A 'cid' makes it inline."""
    maintype, _, subtype = (att.get("mimetype") or "application/octet-stream").partition("/")
    part = MIMEBase(maintype, subtype or "octet-stream")
    part.set_payload(att["content"])
    encoders.encode_base64(part)
    filename = att.get("filename", "attachment")
    if att.get("cid"):
        part.add_header("Content-ID", f"<{att['cid']}>")
        part.add_header("Content-Disposition", "inline", filename=filename)
    else:
        part.add_header("Content-Disposition", "attachment", filename=filename)
    return part


def _send_via_smtp(config, sender, recipients, subject, text, html, attachments, reply_to, from_name):
    """Send one message over SMTP (Resend by default). Returns True on success."""
    host = config.get("smtp_host") or "smtp.resend.com"
    port = int(config.get("smtp_port") or 587)
    user = config.get("smtp_user") or "resend"
    password = config.get("smtp_password", "")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((from_name, sender), charset="utf-8") if from_name else sender
    msg["To"] = ", ".join(recipients)
    if reply_to:
        msg["Reply-To"] = reply_to

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text or "", "plain", "utf-8"))
    if html:
        alt.attach(MIMEText(html, "html", "utf-8"))

    inline = [a for a in attachments if a.get("cid")]
    files  = [a for a in attachments if not a.get("cid")]
    if inline:
        related = MIMEMultipart("related")
        related.attach(alt)
        for a in inline:
            related.attach(_mime_attachment(a))
        msg.attach(related)
    else:
        msg.attach(alt)
    for a in files:
        msg.attach(_mime_attachment(a))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.sendmail(sender, recipients, msg.as_string())
        return True
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f"SMTP send to {recipients} via {host}:{port} failed: {e}")
        return False


def _send_via_sendgrid(config, sender, recipients, subject, text, html, attachments, reply_to, from_name):
    """Legacy fallback: send via the SendGrid REST API. Returns True on success."""
    api_key = config.get("sendgrid_api_key", "")
    content = [{"type": "text/plain", "value": text or ""}]
    if html:
        content.append({"type": "text/html", "value": html})
    payload = {
        "personalizations": [{"to": [{"email": r} for r in recipients]}],
        "from": {"email": sender, "name": from_name} if from_name else {"email": sender},
        "subject": subject,
        "content": content,
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}
    sg_atts = []
    for a in attachments:
        item = {
            "content": base64.b64encode(a["content"]).decode("ascii"),
            "filename": a.get("filename", "attachment"),
            "type": a.get("mimetype", "application/octet-stream"),
            "disposition": "inline" if a.get("cid") else "attachment",
        }
        if a.get("cid"):
            item["content_id"] = a["cid"]
        sg_atts.append(item)
    if sg_atts:
        payload["attachments"] = sg_atts
    try:
        resp = requests.post(_SENDGRID_ENDPOINT, json=payload,
                             headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
        if resp.status_code != 202:
            import logging as _log
            _log.getLogger(__name__).error(f"SendGrid {resp.status_code} to {recipients}: {resp.text[:300]}")
        return resp.status_code == 202
    except requests.RequestException as e:
        import logging as _log
        _log.getLogger(__name__).error(f"SendGrid network error to {recipients}: {e}")
        return False


def _send_email(config, to, subject, text=None, html=None, attachments=None,
                reply_to=None, from_name="MOCA"):
    """Provider-agnostic transactional send. Uses Resend SMTP when `smtp_password`
    is set in config; otherwise falls back to the legacy SendGrid API. `to` is a
    str or list. `attachments`: list of {filename, content(bytes), mimetype, cid?}
    — a 'cid' embeds the part inline for HTML <img src="cid:...">."""
    sender = config.get("email_sender", "")
    if not sender or not to:
        return False
    recipients = [to] if isinstance(to, str) else [r for r in to if r]
    if not recipients:
        return False
    attachments = attachments or []
    if config.get("smtp_password"):
        return _send_via_smtp(config, sender, recipients, subject, text, html, attachments, reply_to, from_name)
    if config.get("sendgrid_api_key"):
        return _send_via_sendgrid(config, sender, recipients, subject, text, html, attachments, reply_to, from_name)
    import logging as _log
    _log.getLogger(__name__).error("no email transport configured (set smtp_password or sendgrid_api_key)")
    return False


def send_email_report(excel_bytes: bytes, config: dict) -> bool:
    """Send the daily Excel report as an attachment (Resend SMTP, SendGrid fallback)."""
    sender    = config.get("email_sender", "")
    recipient = config.get("email_recipient", "")
    if not all([sender, recipient]):
        return False

    today    = datetime.now().strftime("%d.%m.%Y")
    filename = f"cellular_report_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    body = (
        f"שלום,\n\n"
        f"מצורף דו\"ח חבילות הסלולר של {today}.\n"
        f"שורות המסומנות בצהוב עברו שינוי ב-24 השעות האחרונות.\n\n"
        f"https://mocaintel.com"
    )
    return _send_email(
        config, recipient, f'דו"ח סריקת מתחרים - {today}',
        text=body,
        attachments=[{
            "filename": filename,
            "content": excel_bytes,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }],
    )


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

APP_URL = "https://mocaintel.com"


def send_price_alert_email(user_email: str, alert: dict, matching_plans: list, config: dict) -> bool:
    """Send a price-alert notification email to the subscriber (Resend SMTP, SendGrid fallback)."""
    sender = config.get("email_sender", "")
    if not all([sender, user_email]):
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

    return _send_email(config, user_email, subject, text=body)


def send_contact_email(from_email: str, workspace_name: str, message: str, config: dict) -> bool:
    """Send an in-app contact request from a suspended/active user to the MOCA operator.

    Delivers to config['email_recipient'] (the MOCA admin mailbox). The
    requester's email is placed in Reply-To so a simple 'Reply' in the admin's
    client goes back to them directly.
    """
    sender    = config.get("email_sender", "")
    recipient = config.get("email_recipient", "")
    if not all([sender, recipient, from_email, message]):
        return False

    ws_label = workspace_name or "(\u05dc\u05dc\u05d0 workspace)"
    body = (
        f"\u05e4\u05e0\u05d9\u05d9\u05d4 \u05d7\u05d3\u05e9\u05d4 \u05de\u05ea\u05d5\u05da MOCA\n\n"
        f"\u05de: {from_email}\n"
        f"Workspace: {ws_label}\n"
        f"\u05ea\u05d0\u05e8\u05d9\u05da: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"---\n\n{message}\n"
    )
    subject = f"MOCA — \u05e4\u05e0\u05d9\u05d9\u05ea \u05e7\u05e9\u05e8 \u05de {ws_label}"
    return _send_email(config, recipient, subject, text=body, reply_to=from_email)


CARRIER_LABEL_HE = {
    "partner":   "\u05e4\u05e8\u05d8\u05e0\u05e8",
    "pelephone": "\u05e4\u05dc\u05d0\u05e4\u05d5\u05df",
    "hotmobile": "\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc",
    "cellcom":   "\u05e1\u05dc\u05e7\u05d5\u05dd",
    "mobile019": "019",
    "xphone":    "XPhone",
    "wecom":     "We-Com",
    "neptucom":  "Neptucom",
    "golan":     "\u05d2\u05d5\u05dc\u05df \u05d8\u05dc\u05e7\u05d5\u05dd",
    "rami_levy": "\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9",
}


def _build_digest_html(workspace_name: str, app_title: str, primary: str, secondary: str, logo_url: str,
                       app_url: str, by_carrier: dict, change_label: dict, total: int) -> str:
    """Render the weekly digest as inline-styled HTML (email-client-safe)."""
    sections = []
    for carrier, chs in sorted(by_carrier.items()):
        label = CARRIER_LABEL_HE.get(carrier, carrier)
        rows = []
        for ch in chs[:8]:
            kind = change_label.get(ch.get('change_type', ''), ch.get('change_type', ''))
            old_v = ch.get('old_val', '') or ''
            new_v = ch.get('new_val', '') or ''
            arrow = (f'<span style="color:#9a8670;">{old_v}</span> '
                     f'<span style="color:{primary};font-weight:600;">&#8594; {new_v}</span>') if (old_v or new_v) else ''
            rows.append(
                f'<tr><td style="padding:8px 0;border-bottom:1px solid #efe7d9;font-size:13px;color:#4a3a24;">'
                f'<span style="display:inline-block;padding:2px 8px;background:{secondary};color:#fff;'
                f'border-radius:10px;font-size:10px;margin-left:8px;">{kind}</span>'
                f'{ch.get("plan_name","")}'
                f'</td><td style="padding:8px 0;border-bottom:1px solid #efe7d9;font-size:12px;text-align:left;" dir="ltr">'
                f'{arrow}</td></tr>'
            )
        more = ''
        if len(chs) > 8:
            more = (f'<p style="margin:8px 0 0;font-size:11px;color:#9a8670;text-align:center;">'
                    f'+ \u05e2\u05d5\u05d3 {len(chs)-8} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd</p>')
        sections.append(
            f'<div style="margin:16px 0;background:#fff;border:1px solid #e5d8c5;border-radius:12px;padding:16px;">'
            f'<h3 style="margin:0 0 10px;color:{primary};font-size:15px;font-weight:700;">'
            f'{label} <span style="color:#9a8670;font-weight:400;font-size:12px;">({len(chs)})</span></h3>'
            f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table>{more}'
            f'</div>'
        )
    logo_block = ''
    if logo_url:
        logo_block = f'<img src="{logo_url}" alt="{app_title}" style="max-height:40px;margin-bottom:12px;" />'
    return f'''<!DOCTYPE html><html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9f4ee;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9f4ee;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="background:{primary};border-radius:12px 12px 0 0;padding:24px;text-align:right;">
{logo_block}
<h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">{app_title}</h1>
<p style="margin:6px 0 0;color:#fce8d0;font-size:13px;">\u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2\u05d9 \u2014 {workspace_name}</p>
</td></tr>
<tr><td style="background:#fff;padding:20px 24px;border-right:1px solid #e5d8c5;border-left:1px solid #e5d8c5;">
<p style="margin:0;color:#4a3a24;font-size:14px;">
\u05d1-7 \u05d9\u05de\u05d9\u05dd \u05d4\u05d0\u05d7\u05e8\u05d5\u05e0\u05d9\u05dd \u05e0\u05e8\u05e9\u05de\u05d5
<strong style="color:{primary};">{total} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd</strong> \u05d1\u05ea\u05d5\u05db\u05e0\u05d9\u05d5\u05ea \u05d4\u05de\u05ea\u05d7\u05e8\u05d9\u05dd.</p>
<p style="margin:6px 0 0;color:#9a8670;font-size:11px;">\u05ea\u05d0\u05e8\u05d9\u05da: {datetime.now().strftime('%d/%m/%Y')}</p>
</td></tr>
<tr><td style="background:#f9f4ee;padding:4px 24px;border-right:1px solid #e5d8c5;border-left:1px solid #e5d8c5;">
{"".join(sections)}
</td></tr>
<tr><td style="background:{primary};border-radius:0 0 12px 12px;padding:20px 24px;text-align:center;">
<a href="{app_url}" style="display:inline-block;padding:10px 24px;background:#fff;color:{primary};border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">
\u05e4\u05ea\u05d9\u05d7\u05ea \u05d4\u05d0\u05e4\u05dc\u05d9\u05e7\u05e6\u05d9\u05d4 \u2190</a>
<p style="margin:14px 0 0;color:#fce8d0;font-size:11px;">\u05e0\u05e9\u05dc\u05d7 \u05d0\u05d5\u05d8\u05d5\u05de\u05d8\u05d9\u05ea \u05de-{app_title}</p>
</td></tr>
</table></td></tr></table></body></html>'''


def send_weekly_digest(to_emails: list, workspace_name: str, changes: list, config: dict,
                       brand_config: dict = None, app_url: str = None) -> bool:
    """Send a weekly changes digest to all users of a workspace.

    Renders an HTML email using the workspace's brand_config (primary_color,
    secondary_color, app_title, logo_url). Falls back to MOCA defaults.
    Returns True if all emails were dispatched successfully.
    """
    sender = config.get("email_sender", "")
    if not sender or not to_emails:
        return False
    if not changes:
        return True  # nothing to report — skip silently

    bc = brand_config or {}
    primary   = bc.get('primary_color')   or '#5c3317'
    secondary = bc.get('secondary_color') or '#a08060'
    app_title = bc.get('app_title')       or 'MOCA'
    logo_url  = bc.get('logo_url')        or ''
    app_url   = app_url or 'https://mocaintel.com'

    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch.get('carrier', '')].append(ch)

    CHANGE_HE = {
        'price_change':  '\u05e9\u05d9\u05e0\u05d5\u05d9 \u05de\u05d7\u05d9\u05e8',
        'new_plan':      '\u05d7\u05d1\u05d9\u05dc\u05d4 \u05d7\u05d3\u05e9\u05d4',
        'removed_plan':  '\u05d4\u05d5\u05e1\u05e8\u05d4',
        'extras_change': '\u05e9\u05d9\u05e0\u05d5\u05d9 \u05d4\u05d8\u05d1\u05d5\u05ea',
    }

    html_body = _build_digest_html(workspace_name, app_title, primary, secondary,
                                   logo_url, app_url, by_carrier, CHANGE_HE, len(changes))

    # Plain-text fallback for clients that can't render HTML
    text_lines = [
        f"{app_title} \u2014 \u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2\u05d9 \u2014 {workspace_name}\n",
        f"\u05ea\u05d0\u05e8\u05d9\u05da: {datetime.now().strftime('%d/%m/%Y')}\n",
        f"\u05e1\u05d4\"\u05db {len(changes)} \u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05d1-7 \u05d9\u05de\u05d9\u05dd \u05d4\u05d0\u05d7\u05e8\u05d5\u05e0\u05d9\u05dd\n\n",
    ]
    for carrier, chs in sorted(by_carrier.items()):
        label = CARRIER_LABEL_HE.get(carrier, carrier)
        text_lines.append(f"\u2014\u2014\u2014\u2014\n{label} ({len(chs)})\n")
        for ch in chs[:6]:
            kind   = CHANGE_HE.get(ch.get('change_type', ''), ch.get('change_type', ''))
            old_v  = ch.get('old_val', '') or ''
            new_v  = ch.get('new_val', '') or ''
            suffix = f" \u2014 {old_v} \u2192 {new_v}" if (old_v or new_v) else ''
            text_lines.append(f"  \u2022 {ch.get('plan_name','')} [{kind}]{suffix}\n")
    text_lines.append(f"\n\u05dc\u05e6\u05e4\u05d9\u05d9\u05d4: {app_url}")
    text_body = ''.join(text_lines)

    subject = f"{app_title} \u2014 \u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2\u05d9 \u05e2\u05d1\u05d5\u05e8 {workspace_name}"

    ok = True
    for email in to_emails:
        if not _send_email(config, email, subject, text=text_body, html=html_body, from_name=app_title):
            ok = False
    return ok


_WELCOME_HERO_URL = "https://mocaintel.com/email/welcome-hero.png"
_WELCOME_HERO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "mass-market-app", "public", "email", "welcome-hero.png")
_WELCOME_HERO_CID = "welcomehero"


def _build_welcome_html(workspace_name: str, role_he: str, hero_img_url: str,
                        app_url: str, primary: str, secondary: str) -> str:
    """Render the welcome email HTML from templates/welcome_email.html.

    Hebrew markup is kept in the template file (like templates/index.html)
    rather than inline here, per the project convention that Python source
    uses \\u escapes. workspace_name is HTML-escaped (user-controlled).
    """
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "templates", "welcome_email.html")
    with open(tpl_path, encoding="utf-8") as fh:
        tpl = fh.read()
    repl = {
        "{{WORKSPACE}}": html.escape(workspace_name or ""),
        "{{ROLE}}":      html.escape(role_he or ""),
        "{{HERO_IMG}}":  hero_img_url,
        "{{APP_URL}}":   app_url,
        "{{PRIMARY}}":   primary,
        "{{SECONDARY}}": secondary,
        "{{YEAR}}":      str(datetime.now().year),
    }
    for key, val in repl.items():
        tpl = tpl.replace(key, val)
    return tpl


def send_welcome_email(to_email: str, workspace_name: str, role: str, config: dict) -> bool:
    """Send the welcome email (HTML + plain-text fallback) to a newly added user.

    Signature is unchanged so the existing callers in app.py (workspace
    assignment + invite acceptance) keep working as-is.
    """
    sender = config.get("email_sender", "")
    if not all([sender, to_email]):
        return False

    app_url = "https://mocaintel.com"
    role_he = "\u05de\u05e0\u05d4\u05dc" if role == "admin" else "\u05e6\u05d5\u05e4\u05d4"

    # plain-text fallback (must precede the HTML part in multipart/alternative)
    text_body = (
        f"\u05e9\u05dc\u05d5\u05dd \u05d5\u05d1\u05e8\u05db\u05d4,\n\n"
        f"\u05e0\u05e4\u05ea\u05d7 \u05e2\u05d1\u05d5\u05e8\u05da \u05d7\u05e9\u05d1\u05d5\u05df \u05d1-MOCA \u2014 "
        f"\u05de\u05e2\u05e8\u05db\u05ea \u05d4\u05de\u05e2\u05e7\u05d1 \u05d5\u05d4\u05e0\u05d9\u05ea\u05d5\u05d7 \u05e9\u05dc "
        f"\u05de\u05d7\u05d9\u05e8\u05d9 \u05d4\u05de\u05ea\u05d7\u05e8\u05d9\u05dd \u05d1\u05e9\u05d5\u05e7 \u05d4\u05e1\u05dc\u05d5\u05dc\u05e8.\n\n"
        f"\u05e9\u05d5\u05d9\u05d9\u05db\u05ea \u05dc\u05d0\u05d6\u05d5\u05e8 \u05d4\u05e2\u05d1\u05d5\u05d3\u05d4 \u00ab{workspace_name}\u00bb "
        f"\u05d1\u05ea\u05e4\u05e7\u05d9\u05d3 {role_he}.\n\n"
        f"\u05db\u05e0\u05d9\u05e1\u05d4 \u05dc\u05de\u05e2\u05e8\u05db\u05ea:\n{app_url}\n\n"
        f"\u05d0\u05dd \u05d0\u05d9\u05df \u05dc\u05da \u05e2\u05d3\u05d9\u05d9\u05df \u05d7\u05e9\u05d1\u05d5\u05df \u2014 \u05db\u05d3\u05d0\u05d9 \u05dc\u05e4\u05e0\u05d5\u05ea "
        f"\u05dc\u05de\u05d7\u05d6\u05d9\u05e7 \u05d7\u05e9\u05d1\u05d5\u05df \u05d4\u05d0\u05d3\u05de\u05d9\u05df \u05d1\u05d0\u05e8\u05d2\u05d5\u05e0\u05da.\n\n"
        f"\u05d1\u05d1\u05e8\u05db\u05d4,\n\u05de\u05e0\u05d4\u05dc \u05d4\u05de\u05e2\u05e8\u05db\u05ea \u00b7 \u05e6\u05d5\u05d5\u05ea MOCA"
    )

    # Embed the 3D hero inline (CID) so it always renders -- including in Gmail
    # with external images off, and without depending on the hosted URL being
    # live. Falls back to the hosted URL only if the local PNG is missing.
    hero_src = _WELCOME_HERO_URL
    hero_attachment = None
    try:
        with open(_WELCOME_HERO_PATH, "rb") as _hf:
            _hero_bytes = _hf.read()
        hero_src = f"cid:{_WELCOME_HERO_CID}"
        hero_attachment = {
            "filename": "welcome-hero.png",
            "content": _hero_bytes,
            "mimetype": "image/png",
            "cid": _WELCOME_HERO_CID,
        }
    except OSError as e:
        import logging as _log
        _log.getLogger(__name__).warning(f"welcome hero inline failed, using hosted URL: {e}")

    try:
        html_body = _build_welcome_html(
            workspace_name=workspace_name, role_he=role_he,
            hero_img_url=hero_src, app_url=app_url,
            primary="#5c3317", secondary="#a08060",
        )
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).warning(f"welcome html build failed, sending text-only: {e}")
        html_body = None

    subject = "\u05d1\u05e8\u05d5\u05db\u05d9\u05dd \u05d4\u05d1\u05d0\u05d9\u05dd \u05dc-MOCA"
    if workspace_name:
        subject += f" \u00b7 {workspace_name}"

    return _send_email(
        config, to_email, subject,
        text=text_body, html=html_body,
        attachments=[hero_attachment] if hero_attachment else None,
    )


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
