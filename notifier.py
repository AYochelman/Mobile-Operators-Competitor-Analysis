import base64
import html
import json
import logging
import os
import requests
import smtplib
import ssl
from datetime import datetime, timedelta
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
    "xphone":    "XPhone",
    "wecom":     "וי-קום",
    "neptucom":  "נפטוקום",
    "golan":     "גולן טלקום",
    "rami_levy": "רמי לוי תקשורת",
}

GLOBAL_PROVIDER_NAMES = {
    "tuki":             "Tuki",
    "terminalesim":     "Terminal eSIM",
    "airalo":           "Airalo",
    "pelephone_global": "GlobalSIM - Pelephone",
    "esimo":            "eSIMo",
    "simtlv":           "SimTLV",
    "world8":           "8 World",
}

# English brand names for domestic carriers (CARRIER_NAMES is Hebrew). The
# notification language is a global operator setting (config.json:notify_lang,
# "he"|"en"); these localize only the *framing* — scraped plan names and detail
# texts are the carriers' real product strings and stay in their original
# language regardless of the chosen notification language.
CARRIER_NAMES_EN = {
    "partner":   "Partner",
    "pelephone": "Pelephone",
    "hotmobile": "HOT Mobile",
    "cellcom":   "Cellcom",
    "mobile019": "019 Mobile",
    "xphone":    "XPhone",
    "wecom":     "We-Com",
    "neptucom":  "Neptune Mobile",
    "golan":     "Golan Telecom",
    "rami_levy": "Rami Levy",
}


def _carrier_name(carrier, lang="he"):
    """Carrier/provider display name in the requested language, with graceful
    fallbacks (global providers are already Latin; unknown ids pass through)."""
    table = CARRIER_NAMES_EN if lang == "en" else CARRIER_NAMES
    return table.get(carrier) or GLOBAL_PROVIDER_NAMES.get(carrier) or carrier


# Static phrases for the change-notification messages, per language. Hebrew is
# the default and reproduces the original wording verbatim (pinned by tests).
_NOTIFY_STRINGS = {
    "he": {
        "title_domestic": "📱 השוואת סלולר | עדכון {now}",
        "title_abroad":   "✈️ חבילות חו\"ל | עדכון {now}",
        "title_global":   "🌍 חבילות גלובליות | עדכון {now}",
        "title_content":  "📺 שירותי תוכן | עדכון {now}",
        "detected":       "🔔 זוהו שינויים ב-{n} {suffix}",
        "company_1": "חברה", "company_n": "חברות",
        "provider_1": "ספק",  "provider_n": "ספקים",
        "service_1": "שירות", "service_n": "שירותים",
        "new_plan":        "✨ חבילה חדשה: {name} ב-₪{price}",
        "removed":         "❌ הוסרה: {name}",
        "extras_benefits": "🔄 שינוי הטבות: {name}",
        "extras_details":  "🔄 שינוי פרטים: {name}",
        "details":         "📋 {name}: {new} (היה: {old})",
        "c_new":   "✨ {carrier}: חדש — {val}",
        "c_price": "💰 {carrier}: {old} ← {new}",
        "c_trial": "🎁 {carrier}: ניסיון {old} ← {new}",
        # Alon's own channel; Flask serves :5000 on his box, so the link is live for him.
        "footer": "📊 http://localhost:5000",
    },
    "en": {
        "title_domestic": "📱 Cellular plans | update {now}",
        "title_abroad":   "✈️ Roaming plans | update {now}",
        "title_global":   "🌍 Global eSIM | update {now}",
        "title_content":  "📺 Content services | update {now}",
        "detected":       "🔔 Changes detected at {n} {suffix}",
        "company_1": "operator", "company_n": "operators",
        "provider_1": "provider", "provider_n": "providers",
        "service_1": "service",  "service_n": "services",
        "new_plan":        "✨ New plan: {name} for ₪{price}",
        "removed":         "❌ Removed: {name}",
        "extras_benefits": "🔄 Benefits changed: {name}",
        "extras_details":  "🔄 Details changed: {name}",
        "details":         "📋 {name}: {new} (was: {old})",
        "c_new":   "✨ {carrier}: new — {val}",
        "c_price": "💰 {carrier}: {old} ← {new}",
        "c_trial": "🎁 {carrier}: trial {old} ← {new}",
        # External recipients can't reach localhost — use the public dashboard URL.
        "footer": "📊 https://mocaintel.com",
    },
}


def _nstr(lang):
    """Notification strings for a language, falling back to Hebrew."""
    return _NOTIFY_STRINGS.get(lang) or _NOTIFY_STRINGS["he"]


def format_message(changes, lang="he"):
    S = _nstr(lang)
    now = datetime.now().strftime("%H:%M")
    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch["carrier"]].append(ch)

    n = len(by_carrier)
    suffix = S["company_1"] if n == 1 else S["company_n"]
    lines = [
        S["title_domestic"].format(now=now),
        "",
        S["detected"].format(n=n, suffix=suffix),
    ]

    for carrier, carrier_changes in by_carrier.items():
        name = _carrier_name(carrier, lang)
        lines.append(f"\n● {name}")
        for ch in carrier_changes:
            ct = ch["change_type"]
            if ct == "price_change":
                old, new = ch["old_val"], ch["new_val"]
                arrow = "↘" if new < old else "↗"
                lines.append(f"{arrow} {ch['plan_name']}: ₪{old} ← ₪{new}")
            elif ct == "new_plan":
                lines.append(S["new_plan"].format(name=ch["plan_name"], price=ch["new_val"]))
            elif ct == "removed_plan":
                lines.append(S["removed"].format(name=ch["plan_name"]))
            elif ct == "extras_change":
                lines.append(S["extras_benefits"].format(name=ch["plan_name"]))
            elif ct == "details_change":
                lines.append(S["details"].format(name=ch["plan_name"], new=ch["new_val"], old=ch["old_val"]))

    lines += ["", S["footer"]]
    return "\n".join(lines)


def format_abroad_message(changes, lang="he"):
    S = _nstr(lang)
    now = datetime.now().strftime("%H:%M")
    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch["carrier"]].append(ch)

    n = len(by_carrier)
    suffix = S["company_1"] if n == 1 else S["company_n"]
    lines = [
        S["title_abroad"].format(now=now),
        "",
        S["detected"].format(n=n, suffix=suffix),
    ]

    for carrier, carrier_changes in by_carrier.items():
        name = _carrier_name(carrier, lang)
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
                lines.append(S["new_plan"].format(name=ch["plan_name"], price=ch["new_val"]))
            elif ct == "removed_plan":
                lines.append(S["removed"].format(name=ch["plan_name"]))
            elif ct == "extras_change":
                lines.append(S["extras_details"].format(name=ch["plan_name"]))
            elif ct == "details_change":
                lines.append(S["details"].format(name=ch["plan_name"], new=ch["new_val"], old=ch["old_val"]))

    lines += ["", S["footer"]]
    return "\n".join(lines)


def format_global_message(changes, lang="he"):
    S = _nstr(lang)
    now = datetime.now().strftime("%H:%M")
    by_provider = defaultdict(list)
    for ch in changes:
        by_provider[ch["carrier"]].append(ch)

    n = len(by_provider)
    suffix = S["provider_1"] if n == 1 else S["provider_n"]
    lines = [
        S["title_global"].format(now=now),
        "",
        S["detected"].format(n=n, suffix=suffix),
    ]

    for carrier, carrier_changes in by_provider.items():
        name = _carrier_name(carrier, lang)
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
                lines.append(S["new_plan"].format(name=ch["plan_name"], price=ch["new_val"]))
            elif ct == "removed_plan":
                lines.append(S["removed"].format(name=ch["plan_name"]))
            elif ct == "extras_change":
                lines.append(S["extras_details"].format(name=ch["plan_name"]))
            elif ct == "details_change":
                lines.append(S["details"].format(name=ch["plan_name"], new=ch["new_val"], old=ch["old_val"]))

    lines += ["", S["footer"]]
    return "\n".join(lines)


def format_content_message(changes, lang="he"):
    S = _nstr(lang)
    now = datetime.now().strftime("%H:%M")
    by_service = defaultdict(list)
    for ch in changes:
        by_service[ch["service"]].append(ch)

    n = len(by_service)
    suffix = S["service_1"] if n == 1 else S["service_n"]
    lines = [
        S["title_content"].format(now=now),
        "",
        S["detected"].format(n=n, suffix=suffix),
    ]

    for service, service_changes in by_service.items():
        lines.append(f"\n● {service}")
        for ch in service_changes:
            ct = ch["change_type"]
            carrier_name = _carrier_name(ch.get("carrier", ""), lang)
            if ct == "price_change":
                lines.append(S["c_price"].format(carrier=carrier_name, old=ch["old_val"], new=ch["new_val"]))
            elif ct == "new_service":
                lines.append(S["c_new"].format(carrier=carrier_name, val=ch["new_val"]))
            elif ct == "trial_change":
                lines.append(S["c_trial"].format(carrier=carrier_name, old=ch["old_val"], new=ch["new_val"]))

    lines += ["", S["footer"]]
    return "\n".join(lines)


_DIGEST_CATEGORY_LABELS = {
    "domestic":  "📱 חבילות בארץ",
    "abroad":    "✈️ חבילות חו\"ל",
    "global":    "🌍 eSIM גלובלי",
    "content":   "🎬 שירותי תוכן",
    "resellers": "🏷️ מתחת לקו (משווקים)",
}

_DIGEST_CATEGORY_LABELS_EN = {
    "domestic":  "📱 Domestic plans",
    "abroad":    "✈️ Roaming plans",
    "global":    "🌍 Global eSIM",
    "content":   "🎬 Content services",
    "resellers": "🏷️ Below-the-line (resellers)",
}


def _digest_category_label(cat, lang="he"):
    table = _DIGEST_CATEGORY_LABELS_EN if lang == "en" else _DIGEST_CATEGORY_LABELS
    return table.get(cat, cat)


# Static phrases for the morning digest. Hebrew reproduces the original wording
# verbatim (pinned by tests/test_morning_check.py).
_DIGEST_STRINGS = {
    "he": {
        "title": "☀️ MOCA — בדיקת בוקר {today}",
        "none":  "✅ לא זוהו שינויים בחבילות ב-{h} השעות האחרונות.",
        "count": "🔔 {total} שינויים ב-{h} השעות האחרונות:",
        "more":  "…ועוד {n} שינויים",
        "fresh_hdr":     "⚠️ אזהרת רעננות — ייתכן שהסקרייפר נשבר ({n}):",
        "fresh_zero":    "• {carrier} ({cat}): 0 חבילות במסד",
        "fresh_stale":   "• {carrier} ({cat}): לא נסרק כבר {h} שעות",
        "fresh_unknown": "• {carrier} ({cat}): מועד סריקה אחרון לא ידוע",
        "more_warn":     "…ועוד {n} אזהרות",
        "cl_new":     "✨ {carrier} · חבילה חדשה: {name}{suffix}",
        "cl_removed": "❌ {carrier} · הוסרה: {name}",
        "cl_extras":  "🔄 {carrier} · שינוי הטבות: {name}",
        "cl_details": "📋 {carrier} · {name}: {new} (היה: {old})",
        "cl_other":   "• {carrier} · {name}: {ct}",
    },
    "en": {
        "title": "☀️ MOCA — morning check {today}",
        "none":  "✅ No plan changes in the last {h} hours.",
        "count": "🔔 {total} changes in the last {h} hours:",
        "more":  "…and {n} more changes",
        "fresh_hdr":     "⚠️ Freshness warning — a scraper may be broken ({n}):",
        "fresh_zero":    "• {carrier} ({cat}): 0 plans in DB",
        "fresh_stale":   "• {carrier} ({cat}): not scraped for {h} hours",
        "fresh_unknown": "• {carrier} ({cat}): last scrape time unknown",
        "more_warn":     "…and {n} more warnings",
        "cl_new":     "✨ {carrier} · New plan: {name}{suffix}",
        "cl_removed": "❌ {carrier} · Removed: {name}",
        "cl_extras":  "🔄 {carrier} · Benefits changed: {name}",
        "cl_details": "📋 {carrier} · {name}: {new} (was: {old})",
        "cl_other":   "• {carrier} · {name}: {ct}",
    },
}


def _digest_str(lang):
    return _DIGEST_STRINGS.get(lang) or _DIGEST_STRINGS["he"]

# Display names for below-the-line sources (reseller_id → Hebrew label).
# Keep in sync with RESELLERS in DashboardPage.jsx.
RESELLER_NAMES = {
    "tiber":                "טיבר",
    "zol_li":               "זול-לי",
    "kamaze":               "כמה זה",
    "kamazeole":            "כמה זה עולה",
    "sell_zoll":            "sell-zoll",
    "tikshoretishit":       "תקשורת אישית",
    "clubdeal":             "ClubDeal (פלאפון)",
    "partner_site":         "פרטנר — דף הצטרפות",
    "wecom_site":           "וי-קום — סים דאטה",
    "rami_levy_landing":    "רמי לוי — דף נחיתה",
    "rami_levy_hever":      "רמי לוי — מועדון חבר",
    "rami_levy_cc":         "רמי לוי — הטבת אשראי",
    "pelephon4u":           "פלאפון 4U",
    "pelephone_join":       "פלאפון Join",
    "pelephone_cellphone":  "פלאפון Deal",
    "pelephone_fb":         "פלאפון — קמפיין פייסבוק",
    "analizer":             "אנלייזר (מתווך)",
    "cellcomshefamr":       "סלקום שפרעם",
    "zorro":                "זורו",
}

_DIGEST_MAX_LINES_PER_CATEGORY = 15
_DIGEST_MAX_FRESHNESS_LINES = 12


def _digest_carrier_name(carrier_id, lang="he"):
    base = CARRIER_NAMES_EN if lang == "en" else CARRIER_NAMES
    return (base.get(carrier_id) or GLOBAL_PROVIDER_NAMES.get(carrier_id)
            or RESELLER_NAMES.get(carrier_id) or carrier_id)


def _digest_change_line(ch, lang="he"):
    S = _digest_str(lang)
    carrier = _digest_carrier_name(ch.get("carrier", ""), lang)
    # Below-the-line rows: show the source too — "טיבר · פלאפון" (reseller
    # brand names have no English form, so they stay as-is).
    if ch.get("reseller_id"):
        source = RESELLER_NAMES.get(ch["reseller_id"], ch["reseller_id"])
        carrier = f"{source} · {carrier}"
    # Content rows: the "plan" is the service name
    name = ch.get("plan_name") or ch.get("service") or ""
    ct = ch.get("change_type", "")
    if ct == "price_change":
        old, new = ch.get("old_val"), ch.get("new_val")
        # Domestic/abroad/global store raw numbers → prefix ₪. Content stores
        # already-formatted strings ("₪19.90") or text sentinels ("לא נמצא") →
        # leave as-is (avoids the "₪₪19.90" / "₪לא נמצא" mangling in the digest).
        def _num(v):
            return float(str(v).replace("₪", "").replace(",", "").strip())
        def _price(v):
            s = str(v).strip()
            if s.startswith("₪"):
                return s
            try:
                _num(s)
                return f"₪{s}"
            except ValueError:
                return s
        try:
            arrow = "↘" if _num(new) < _num(old) else "↗"
        except (TypeError, ValueError):
            arrow = "🔄"
        return f"{arrow} {carrier} · {name}: {_price(old)} ← {_price(new)}"
    if ct == "new_plan":
        price = ch.get("new_val")
        suffix = f" (₪{price})" if price not in (None, "") else ""
        return S["cl_new"].format(carrier=carrier, name=name, suffix=suffix)
    if ct == "removed_plan":
        return S["cl_removed"].format(carrier=carrier, name=name)
    if ct == "extras_change":
        return S["cl_extras"].format(carrier=carrier, name=name)
    if ct == "details_change":
        return S["cl_details"].format(carrier=carrier, name=name,
                                      new=ch.get("new_val"), old=ch.get("old_val"))
    return S["cl_other"].format(carrier=carrier, name=name, ct=ct)


def format_morning_digest(summary, freshness_warnings=None, within_hours=26, lang="he"):
    """Morning digest of every change recorded in the last N hours (he/en).

    Always returns a message — an explicit "no changes" included — so the
    morning check doubles as a daily heartbeat: if the message doesn't arrive,
    the job (or Flask itself) is down.

    Args:
        summary: dict from db.get_recent_changes_summary —
                 {'domestic': [...], 'abroad': [...], 'global': [...], 'content': [...]}
        freshness_warnings: list of dicts {carrier, category, count, last_scraped,
                            hours_ago} for carriers whose data is stale/empty
        within_hours: the lookback window, echoed in the message
    """
    S = _digest_str(lang)
    today = datetime.now().strftime("%d/%m/%Y")
    total = sum(len(v) for v in (summary or {}).values())
    lines = [S["title"].format(today=today), ""]

    if total == 0:
        lines.append(S["none"].format(h=within_hours))
    else:
        lines.append(S["count"].format(total=total, h=within_hours))
        for cat in ("domestic", "abroad", "global", "content", "resellers"):
            changes = (summary or {}).get(cat) or []
            if not changes:
                continue
            lines += ["", f"{_digest_category_label(cat, lang)} ({len(changes)})"]
            for ch in changes[:_DIGEST_MAX_LINES_PER_CATEGORY]:
                lines.append(_digest_change_line(ch, lang))
            hidden = len(changes) - _DIGEST_MAX_LINES_PER_CATEGORY
            if hidden > 0:
                lines.append(S["more"].format(n=hidden))

    if freshness_warnings:
        lines += ["", S["fresh_hdr"].format(n=len(freshness_warnings))]
        for w in freshness_warnings[:_DIGEST_MAX_FRESHNESS_LINES]:
            carrier = _digest_carrier_name(w.get("carrier", ""), lang)
            cat_label = _digest_category_label(w.get("category", ""), lang)
            if not w.get("count"):
                lines.append(S["fresh_zero"].format(carrier=carrier, cat=cat_label))
            elif w.get("hours_ago") is not None:
                lines.append(S["fresh_stale"].format(carrier=carrier, cat=cat_label, h=int(w["hours_ago"])))
            else:
                lines.append(S["fresh_unknown"].format(carrier=carrier, cat=cat_label))
        hidden = len(freshness_warnings) - _DIGEST_MAX_FRESHNESS_LINES
        if hidden > 0:
            lines.append(S["more_warn"].format(n=hidden))

    lines += ["", "📊 https://mocaintel.com"]
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


def _push_payload(n_changes, n_carriers, lang="he"):
    if lang == "en":
        title, body = "MOCA Cellular", f"{n_changes} changes across {n_carriers} operators"
    else:
        title, body = "השוואת סלולר", f"זוהו {n_changes} שינויים ב-{n_carriers} חברות"
    return json.dumps({"title": title, "body": body}, ensure_ascii=False)


def send_push_notifications(changes, config, db_path=None, lang="he"):
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
    vapid_email = config.get("vapid_email", "mailto:alon.yoch@gmail.com")
    sent, stale = 0, []
    for sub in subscriptions:
        hidden = sub.get("hidden_carrier")
        visible = [c for c in changes if not hidden or c.get("carrier") != hidden]
        if not visible:
            continue
        n_c = len({c["carrier"] for c in visible})
        pld = _push_payload(len(visible), n_c, lang)
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


def notify_esim_price_drops(config, db_path=None):
    """State-based price-drop alerts for the public /esim-deals page: after every
    global scrape, compare each subscribed destination's CURRENT cheapest deal
    against the subscription's baseline (set at subscribe time / last alert).
    Deliberately independent of the change log — the global scrape paths drop
    new_plan/removed_plan events, but a brand-new cheaper plan should still alert.
    Notify only on a real drop (≥5% AND ≥₪2 — stored ₪ prices carry scrape-time
    FX noise); on a rise, silently raise the baseline so a later fall re-alerts."""
    from urllib.parse import quote
    from db import (get_esim_push_subscriptions, get_esim_alert_floor,
                    update_esim_push_baseline, delete_esim_push_subscription)
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return 0
    vapid_private_key = config.get("vapid_private_key")
    if not vapid_private_key:
        return 0
    subs = get_esim_push_subscriptions(db_path=db_path)
    if not subs:
        return 0
    vapid_email = config.get("vapid_email", "mailto:alon.yoch@gmail.com")
    min_by_dest = {}
    sent, stale = 0, []
    for sub in subs:
        dest = sub["destination"]
        if dest not in min_by_dest:
            min_by_dest[dest] = get_esim_alert_floor(dest, db_path=db_path)
        cur = min_by_dest[dest]
        if cur is None:
            continue
        base = sub.get("baseline_price")
        if base is None or cur > base:
            update_esim_push_baseline(sub["endpoint"], cur, db_path=db_path)
            continue
        drop = base - cur
        if drop < 2 or drop < base * 0.05:
            continue
        if (sub.get("lang") or "he") == "en":
            body = f"Price drop! eSIM deals for your destination now from ₪{round(cur)}"
        else:
            body = f"ירידת מחיר! חבילות eSIM ל{dest} עכשיו החל מ-₪{round(cur)}"
        url = (f"https://mocaintel.com/esim-deals?dest={quote(dest)}"
               f"&lang={sub.get('lang') or 'he'}&utm_source=push&utm_campaign=price_drop")
        payload = json.dumps(
            {"title": "MOCA eSIM", "body": body, "url": url, "tag": "esim-price-drop"},
            ensure_ascii=False)
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_email},
            )
            update_esim_push_baseline(sub["endpoint"], cur, notified=True, db_path=db_path)
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None) if hasattr(e, "response") and e.response else None
            if status in (404, 410):
                stale.append(sub["endpoint"])
        except Exception:
            pass
    for ep in stale:
        delete_esim_push_subscription(ep, db_path=db_path)
    return sent


def notify_mobile_price_drops(fresh_changes, config, db_path=None):
    """Event-driven price-drop alerts for the public /mobile-deals page: called
    with the POST-dedup ("fresh") domestic change list after every domestic
    scrape, so the 24h filter_already_notified dedup is inherited. Unlike the
    eSIM floor model (state-based, because global scrapes drop new/removed
    events), domestic change detection is reliable per (carrier, plan_name) —
    alerting straight off price_change events is simpler and can name the
    actual plan. One push per endpoint per run; endpoints notified in the last
    20h are skipped (scrapes run 2×/day)."""
    from db import (get_mobile_push_subscriptions, delete_mobile_push_subscription,
                    touch_mobile_push_notified)
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return 0
    vapid_private_key = config.get("vapid_private_key")
    if not vapid_private_key:
        return 0

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    drops = []
    for c in fresh_changes or []:
        if c.get("change_type") != "price_change":
            continue
        old, new = _num(c.get("old_val")), _num(c.get("new_val"))
        if old is None or new is None or new >= old:
            continue
        drops.append({"carrier": c.get("carrier") or "", "plan_name": c.get("plan_name") or "",
                      "old": old, "new": new})
    if not drops:
        return 0
    subs = get_mobile_push_subscriptions(db_path=db_path)
    if not subs:
        return 0
    vapid_email = config.get("vapid_email", "mailto:alon.yoch@gmail.com")

    def _fmt(p):
        return str(int(p)) if float(p).is_integer() else f"{p:g}"

    now = datetime.now()
    sent, stale = 0, []
    for sub in subs:
        mine = drops if sub["carrier"] == "all" else [d for d in drops if d["carrier"] == sub["carrier"]]
        if not mine:
            continue
        last = sub.get("last_notified_at")
        if last:
            try:
                if (now - datetime.fromisoformat(last)).total_seconds() < 20 * 3600:
                    continue
            except (ValueError, TypeError):
                pass
        lang = sub.get("lang") or "he"
        if len(mine) == 1:
            d = mine[0]
            name = CARRIER_DISPLAY_NAMES.get(d["carrier"], d["carrier"])
            if lang == "en":
                body = f"Price drop! {name} - {d['plan_name']}: now ₪{_fmt(d['new'])} instead of ₪{_fmt(d['old'])}"
            else:
                body = f"ירידת מחיר! {name} - {d['plan_name']}: עכשיו ₪{_fmt(d['new'])} במקום ₪{_fmt(d['old'])}"
        else:
            if lang == "en":
                body = f"{len(mine)} mobile plans just got cheaper - worth comparing"
            else:
                body = f"{len(mine)} חבילות סלולר הוזלו - שווה להשוות"
        url = ("https://mocaintel.com/mobile-deals?utm_source=push&utm_campaign=price_drop"
               + ("&lang=en" if lang == "en" else ""))
        payload = json.dumps(
            {"title": "MOCA", "body": body, "url": url, "tag": "mobile-price-drop"},
            ensure_ascii=False)
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_email},
            )
            touch_mobile_push_notified(sub["endpoint"], db_path=db_path)
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None) if hasattr(e, "response") and e.response else None
            if status in (404, 410):
                stale.append(sub["endpoint"])
        except Exception:
            pass
    for ep in stale:
        delete_mobile_push_subscription(ep, db_path=db_path)
    return sent


CARRIER_DISPLAY_NAMES = {
    "partner": "פרטנר", "pelephone": "פלאפון", "hotmobile": "הוט מובייל",
    "cellcom": "סלקום", "mobile019": "019", "xphone": "XPhone",
    "wecom": "We-Com", "neptucom": "Neptucom",
    "golan": "גולן טלקום", "rami_levy": "רמי לוי תקשורת",
    "tuki": "Tuki", "terminalesim": "Terminal eSIM", "airalo": "Airalo",
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


_WA_CHATID_CACHE = {}


def _resolve_whatsapp_chatid(phone, base_url, instance, token):
    """Resolve a phone number to its real Green API chatId. WhatsApp accounts
    behind the @lid privacy layer (e.g. 972502002003 → 28862348046428@lid)
    silently DROP messages addressed to <phone>@c.us — the API returns 200 and
    the message sticks at 'sent' forever (verified 2026-08-06). checkWhatsapp
    returns the routable chatId; fall back to <phone>@c.us on any failure."""
    if phone in _WA_CHATID_CACHE:
        return _WA_CHATID_CACHE[phone]
    chat_id = f"{phone}@c.us"
    try:
        resp = requests.post(
            f"{base_url}/waInstance{instance}/checkWhatsapp/{token}",
            json={"phoneNumber": int(phone)}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("existsWhatsapp") and data.get("chatId"):
                chat_id = data["chatId"]
    except (requests.RequestException, ValueError):
        pass
    _WA_CHATID_CACHE[phone] = chat_id
    return chat_id


def _send_whatsapp_direct(phone, message, config):
    """Green API send to a specific user phone (intl digits, e.g. 9725…) —
    unlike send_whatsapp, which targets the operator's configured group.
    The chatId is resolved via checkWhatsapp first (see _resolve_whatsapp_chatid)."""
    base_url = config.get("greenapi_url", "")
    instance = config.get("greenapi_instance", "")
    token = config.get("greenapi_token", "")
    if not all([base_url, instance, token, phone]):
        return False
    chat_id = _resolve_whatsapp_chatid(phone, base_url, instance, token)
    try:
        resp = requests.post(
            f"{base_url}/waInstance{instance}/sendMessage/{token}",
            json={"chatId": chat_id, "message": message},
            timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _rem_fmt_price(p):
    try:
        p = float(p)
    except (TypeError, ValueError):
        return str(p)
    return str(int(p)) if p.is_integer() else f"{p:g}"


def _rem_gb_label(plan, lang):
    if plan.get("unlimited") or plan.get("data_gb") is None:
        return "Unlimited data" if lang == "en" else "גלישה ללא הגבלה"
    g = plan["data_gb"]
    return f"{g:g}GB"


def find_better_mobile_deals(base, plans, min_saving=2.0, limit=3):
    """Competing domestic plans that beat `base` (a mobile_reminders row / feed
    plan): at least the same data for less money, or more data for the same
    money. `plans` is the normalized /api/mobile/compare feed (voice-only and
    conditional-price rows are excluded — their headline ₪ is not comparable)."""
    INF = float("inf")

    def _data(p):
        return INF if (p.get("unlimited") or p.get("data_gb") is None) else (p.get("data_gb") or 0)

    base_price, base_data = base.get("price"), _data(base)
    if base_price is None:
        return []
    out = []
    for p in plans:
        if p.get("carrier") == base.get("carrier") or p.get("price") is None:
            continue
        if p.get("voice_only") or p.get("price_conditional"):
            continue
        d, pr = _data(p), p["price"]
        if (d >= base_data and pr <= base_price - min_saving) or (d > base_data and pr <= base_price):
            out.append(p)
    out.sort(key=lambda p: (p["price"], -_data(p) if _data(p) != INF else -10 ** 9))
    return out[:limit]


def find_similar_mobile_offers(base, plans, limit=3):
    """Retention alternatives for a plan-end reminder: same-or-more data from any
    carrier (including the user's own), cheapest first. Unlike
    find_better_mobile_deals, price may equal/exceed the old plan — the point is
    preserving terms, not only undercutting them."""
    INF = float("inf")

    def _data(p):
        return INF if (p.get("unlimited") or p.get("data_gb") is None) else (p.get("data_gb") or 0)

    base_data = _data(base)
    out = [p for p in plans
           if p.get("price") is not None and not p.get("voice_only")
           and not p.get("price_conditional") and _data(p) >= base_data
           and not (p.get("carrier") == base.get("carrier") and p.get("plan_name") == base.get("plan_name"))]
    out.sort(key=lambda p: (p["price"], -_data(p) if _data(p) != INF else -10 ** 9))
    return out[:limit]


def _rem_urls(config):
    """Public URLs for reminder messages. Config-driven because the canonical
    hosts flip during the mocaintel.com takedown (public_site_url = the Netlify
    subdomain, public_api_url = the reserved ngrok domain); defaults are the
    canonical domains."""
    site = (config.get("public_site_url") or "https://mocaintel.com").rstrip("/")
    api = (config.get("public_api_url") or "https://api.mocaintel.com").rstrip("/")
    return (site + "/mobile-deals",
            api + "/api/mobile/reminders/unsubscribe?token=")


def _rem_deal_lines(deals, lang):
    lines = []
    for p in deals:
        name = CARRIER_DISPLAY_NAMES.get(p["carrier"], p["carrier"])
        lines.append(f"• {name} - {p['plan_name']}: ₪{_rem_fmt_price(p['price'])} ({_rem_gb_label(p, lang)})")
    return lines


def _rem_links(rem, config):
    """(page-with-utm, unsubscribe) URLs for one reminder row."""
    lang = rem.get("lang") or "he"
    page_url, unsub_base = _rem_urls(config)
    utm = f"{page_url}?utm_source=reminder&utm_campaign={rem['kind']}" + ("&lang=en" if lang == "en" else "")
    return utm, unsub_base + rem["token"]


# ---- Branded reminder emails --------------------------------------------
# Palette mirrors the #mobile-app tokens in MobileComparePage.jsx so the mail
# reads as the same product: c1 #5c3317, c2 #c9622f, bg #f9f4ee, cream #f5ede0,
# ink #3b1f0d, sub #8a6a4a, muted #a08468, line #e0cdb5, green #246b43/#e3f3e9.
# Email-client-safe: tables + inline styles only, no flex/grid/webfont deps.

def _rem_hero_url(kind, config):
    """Public URL of the per-kind hero illustration (hosted in the app's
    public/email/ on Netlify — email clients need an absolute, external URL)."""
    site = (config.get("public_site_url") or "https://mocaintel.com").rstrip("/")
    return f"{site}/email/{kind}.jpg"


def _rem_email_shell(lang, unsub, inner_rows, hero_url=None, share_url=None):
    """Shared shell (cream canvas, MOCA header, footer) around content <tr> rows.
    `share_url` adds a refer-a-friend line above the footer."""
    rtl = lang != "en"
    dir_attr = "rtl" if rtl else "ltr"
    tagline = "השוואת מסלולי סלולר בישראל" if rtl else "Israel mobile plan comparison"
    footer_note = ("קיבלת מייל זה כי נרשמת להתראות בעמוד השוואת המסלולים של MOCA."
                   if rtl else
                   "You are receiving this because you signed up for alerts on MOCA's plan comparison page.")
    unsub_label = "להסרה מהעדכונים" if rtl else "Unsubscribe"
    share_row = ""
    if share_url:
        share_txt = ("מכירים מישהו שמשלם יותר מדי על סלולר?" if rtl
                     else "Know someone paying too much for mobile?")
        share_link = "שלחו לו את ההשוואה" if rtl else "Send them the comparison"
        share_row = (
            f'<tr><td style="padding:14px 16px 0;text-align:center;">'
            f'<p style="margin:0;color:#8a6a4a;font-size:12.5px;line-height:1.7;">{share_txt} '
            f'<a href="{share_url}" style="color:#c9622f;font-weight:700;">{share_link}</a></p>'
            f'</td></tr>')
    return f'''<!DOCTYPE html><html dir="{dir_attr}" lang="{"he" if rtl else "en"}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9f4ee;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f9f4ee;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" dir="{dir_attr}" style="max-width:600px;width:100%;font-family:'Assistant','Segoe UI',Arial,sans-serif;">
<tr><td style="background:#5c3317;border-radius:18px 18px 0 0;padding:24px 30px;">
<span style="color:#ffffff;font-size:26px;font-weight:800;letter-spacing:2px;">MOCA</span>
<span style="display:inline-block;width:9px;height:9px;background:#c9622f;border-radius:9px;margin:0 5px;"></span>
<div style="color:#e8cdb4;font-size:12.5px;margin-top:4px;">{tagline}</div>
</td></tr>
{f'<tr><td style="background:#ffffff;padding:0;line-height:0;"><img src="{hero_url}" width="600" alt="" style="width:100%;height:auto;display:block;border:0;"></td></tr>' if hero_url else ''}
{inner_rows}
{share_row}
<tr><td style="padding:18px 16px 4px;text-align:center;">
<p style="margin:0;color:#a08468;font-size:11.5px;line-height:1.8;">{footer_note}<br>
<a href="{unsub}" style="color:#8a6a4a;">{unsub_label}</a> &middot; MOCA</p>
</td></tr>
</table></td></tr></table></body></html>'''


# Domestic carrier homepages for the deal-card click-outs. Mirrors the `url`
# field of CARRIER_DISPLAY in app.py (importing app here would be circular) —
# keep the two in sync.
CARRIER_HOME_URLS = {
    "partner":   "https://www.partner.net.il",
    "pelephone": "https://www.pelephone.co.il",
    "hotmobile": "https://www.hotmobile.co.il",
    "cellcom":   "https://www.cellcom.co.il",
    "mobile019": "https://www.019mobile.co.il",
    "xphone":    "https://www.xphone.co.il",
    "wecom":     "https://we-com.co.il",
    "neptucom":  "https://www.neptucom.com",
    "golan":     "https://www.golantelecom.co.il",
    "rami_levy": "https://mobile.rami-levy.co.il",
}


def _rem_deal_cards_html(deals, lang, mark_best=False):
    """Deal rows as white cards: carrier + plan on the start side, price + data
    on the end side. The first card optionally gets a green 'best value' tag.
    When the carrier's homepage is known, the card content links out to it."""
    rtl = lang != "en"
    end_align = "left" if rtl else "right"
    best_label = "הכי משתלמת" if rtl else "Best value"
    per_month = "לחודש" if rtl else "per month"
    visit_label = "לאתר המפעיל ›" if rtl else "Visit carrier site ›"
    cards = []
    for i, p in enumerate(deals):
        name = CARRIER_DISPLAY_NAMES.get(p["carrier"], p["carrier"])
        home = CARRIER_HOME_URLS.get(p["carrier"])
        badge = ""
        if mark_best and i == 0 and len(deals) > 1:
            badge = (f'<span style="display:inline-block;background:#e3f3e9;color:#246b43;font-size:10.5px;'
                     f'font-weight:700;border-radius:999px;padding:2px 10px;margin-bottom:4px;">{best_label}</span><br>')
        info = (f'<span style="color:#3b1f0d;font-size:15px;font-weight:700;">{name}</span><br>'
                f'<span style="color:#8a6a4a;font-size:12.5px;">{p["plan_name"]}</span>')
        price = (f'<span dir="ltr" style="color:#c9622f;font-size:21px;font-weight:800;">&#8362;{_rem_fmt_price(p["price"])}</span><br>'
                 f'<span style="color:#8a6a4a;font-size:12px;">{_rem_gb_label(p, lang)} &middot; {per_month}</span>')
        if home:
            info = (f'<a href="{home}" style="text-decoration:none;color:inherit;">{info}</a><br>'
                    f'<a href="{home}" style="color:#c9622f;font-size:11.5px;font-weight:700;'
                    f'text-decoration:none;">{visit_label}</a>')
            price = f'<a href="{home}" style="text-decoration:none;color:inherit;">{price}</a>'
        cards.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:#ffffff;border:1px solid #e0cdb5;border-radius:14px;margin:0 0 10px;"><tr>'
            f'<td style="padding:14px 18px;">{badge}{info}</td>'
            f'<td align="{end_align}" style="padding:14px 18px;white-space:nowrap;vertical-align:top;">{price}'
            f'</td></tr></table>')
    return "".join(cards)


def _rem_email_body(lang, badge, title, blocks_html, cta_url):
    """Content rows: alert pill + title, free-form blocks, CTA button."""
    rtl = lang != "en"
    cta_label = "להשוואה המלאה באתר" if rtl else "See the full comparison"
    return (
        f'<tr><td style="background:#ffffff;padding:26px 30px 4px;">'
        f'<span style="display:inline-block;background:#fdeee3;color:#c9622f;font-size:11.5px;font-weight:700;'
        f'border-radius:999px;padding:4px 14px;letter-spacing:.3px;">{badge}</span>'
        f'<h1 style="margin:12px 0 4px;color:#3b1f0d;font-size:20px;font-weight:700;line-height:1.4;'
        f"font-family:'Assistant','Segoe UI',Arial,sans-serif;\">{title}</h1>"
        f'</td></tr>'
        f'<tr><td style="background:#ffffff;padding:8px 30px 4px;">{blocks_html}</td></tr>'
        f'<tr><td style="background:#ffffff;border-radius:0 0 18px 18px;padding:12px 30px 28px;" align="center">'
        f'<a href="{cta_url}" style="display:inline-block;background:#c9622f;color:#ffffff;text-decoration:none;'
        f'font-size:14.5px;font-weight:700;border-radius:999px;padding:12px 34px;">{cta_label}</a>'
        f'</td></tr>')


def _build_better_deal_html(rem, base, deals, config, btl=None):
    """Branded email for the better_deal reminder: current-plan strip, savings
    tag, competing deal cards, optional below-the-line reseller cards, CTA."""
    lang = rem.get("lang") or "he"
    rtl = lang != "en"
    utm, unsub = _rem_links(rem, config)
    cname = CARRIER_DISPLAY_NAMES.get(rem["carrier"], rem["carrier"])
    cur_label = "המסלול שלך היום" if rtl else "Your current plan"
    base_strip = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#f5ede0;border-radius:12px;margin:6px 0 12px;"><tr>'
        f'<td style="padding:12px 18px;">'
        f'<span style="color:#a08468;font-size:11px;font-weight:700;">{cur_label}</span><br>'
        f'<span style="color:#3b1f0d;font-size:13.5px;font-weight:700;">{rem["plan_name"]}</span> '
        f'<span style="color:#8a6a4a;font-size:12.5px;">({cname})</span></td>'
        f'<td align="{"left" if rtl else "right"}" style="padding:12px 18px;white-space:nowrap;">'
        f'<span dir="ltr" style="color:#8a6a4a;font-size:16px;font-weight:700;">&#8362;{_rem_fmt_price(base["price"])}</span><br>'
        f'<span style="color:#a08468;font-size:11.5px;">{_rem_gb_label(base, lang)}</span>'
        f'</td></tr></table>')
    saving_html = ""
    try:
        saving = float(base["price"]) - float(deals[0]["price"])
        if saving >= 1:
            annual = round(saving * 12)
            saving_txt = (f"חיסכון של עד &#8362;{_rem_fmt_price(saving)} בחודש = כ-&#8362;{annual} בשנה" if rtl
                          else f"Save up to &#8362;{_rem_fmt_price(saving)} a month = about &#8362;{annual} a year")
            saving_html = (f'<div style="margin:0 0 14px;"><span style="display:inline-block;background:#e3f3e9;'
                           f'color:#246b43;font-size:12.5px;font-weight:800;border-radius:999px;padding:5px 16px;">'
                           f'&#8595; {saving_txt}</span></div>')
    except (TypeError, ValueError):
        pass
    badge = "התראת חיסכון" if rtl else "Savings alert"
    title = ("מצאנו חבילות שמשתלמות יותר מהמסלול שלך" if rtl
             else "We found plans that beat your current one")
    blocks = base_strip + saving_html + _rem_deal_cards_html(deals, lang, mark_best=True)
    if btl:
        btl_title = ("מתחת לקו: הצעות משווקים שרוב ההשוואתונים לא מציגים" if rtl
                     else "Below the line: reseller offers most comparison sites never show")
        blocks += (f'<p style="margin:14px 0 8px;color:#3b1f0d;font-size:13.5px;font-weight:700;">{btl_title}</p>'
                   + _rem_btl_cards_html(btl, lang))
    return _rem_email_shell(lang, unsub, _rem_email_body(lang, badge, title, blocks, utm),
                            hero_url=_rem_hero_url("better_deal", config),
                            share_url=_rem_share_url(rem, config))


def _build_plan_end_html(rem, intro_lines, offers, config):
    """Branded email for the plan_end reminder: intro paragraphs + optional
    retention-alternative cards."""
    lang = rem.get("lang") or "he"
    rtl = lang != "en"
    utm, unsub = _rem_links(rem, config)
    paras = "".join(f'<p style="margin:0 0 10px;color:#4a3a24;font-size:14px;line-height:1.7;">{ln}</p>'
                    for ln in intro_lines if ln)
    blocks = paras
    if offers:
        offers_title = "הצעות דומות שזמינות היום" if rtl else "Similar offers available today"
        blocks += (f'<p style="margin:14px 0 8px;color:#3b1f0d;font-size:13.5px;font-weight:700;">{offers_title}</p>'
                   + _rem_deal_cards_html(offers, lang))
    badge = "תזכורת סיום מסלול" if rtl else "Plan-end reminder"
    cname = CARRIER_DISPLAY_NAMES.get(rem["carrier"], rem["carrier"])
    title = (f"המסלול שלך ב{cname} עומד להסתיים" if rtl
             else f"Your plan at {cname} is about to end")
    return _rem_email_shell(lang, unsub, _rem_email_body(lang, badge, title, blocks, utm),
                            hero_url=_rem_hero_url("plan_end", config),
                            share_url=_rem_share_url(rem, config))


# ---- Engagement extensions (2026-08-06): annual savings, market percentile,
# ---- monthly heartbeat, plan-end renewal follow-up. Email-channel only —
# ---- consumer WhatsApp is quota-blocked until the Green API plan upgrade.

def _rem_share_url(rem, config):
    """Refer-a-friend link (separate utm_source so referral traffic is
    distinguishable from the subscriber's own clicks)."""
    lang = rem.get("lang") or "he"
    page_url, _ = _rem_urls(config)
    return f"{page_url}?utm_source=referral&utm_campaign=email_share" + ("&lang=en" if lang == "en" else "")


def _rem_base_price(rem, cur=None):
    """The price this subscriber actually pays: the self-declared paid_price
    (the 'כמה אתם משלמים?' question) wins; else the plan's current rate-card
    price; else the signup snapshot."""
    if rem.get("paid_price"):
        return rem["paid_price"]
    return (cur or rem).get("price")


def _find_reseller_deals(base, db_path=None, min_saving=2.0, limit=2):
    """Below-the-line (משווקים) offers that beat the user's plan — reseller
    sites, carrier landing pages and FB-ad campaigns tracked in reseller_plans.
    Info no other Israeli comparison surfaces; clearly labeled in the email."""
    from db import get_reseller_plans
    INF = float("inf")

    def _data(p):
        return INF if p.get("data_gb") is None else (p.get("data_gb") or 0)

    base_price = base.get("price")
    if base_price is None:
        return []
    base_data = INF if (base.get("unlimited") or base.get("data_gb") is None) else (base.get("data_gb") or 0)
    try:
        rows = get_reseller_plans(db_path=db_path)
    except Exception:
        return []
    out = [r for r in rows
           if r.get("price") is not None and r["price"] >= 5
           and _data(r) >= base_data and r["price"] <= base_price - min_saving]
    out.sort(key=lambda r: r["price"])
    return out[:limit]


def _rem_btl_cards_html(btl, lang):
    """Reseller-deal cards: reseller name + underlying carrier, clearly tagged
    as a below-the-line offer, price side links to the source page."""
    rtl = lang != "en"
    end_align = "left" if rtl else "right"
    tag = "הצעת משווק" if rtl else "Reseller offer"
    per_month = "לחודש" if rtl else "per month"
    cards = []
    for r in btl:
        rname = RESELLER_NAMES.get(r["reseller_id"], r["reseller_id"])
        cname = CARRIER_DISPLAY_NAMES.get(r["carrier"], r["carrier"])
        gb = ("ללא הגבלה" if rtl else "Unlimited data") if r.get("data_gb") is None \
            else f"{r['data_gb']:g}GB"
        src = r.get("source_url") or ""
        price_html = f'&#8362;{_rem_fmt_price(r["price"])}'
        if src:
            price_html = f'<a href="{src}" style="color:#c9622f;text-decoration:none;">{price_html}</a>'
        cards.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:#fdf6ec;border:1px dashed #d9b98c;border-radius:14px;margin:0 0 10px;"><tr>'
            f'<td style="padding:14px 18px;">'
            f'<span style="display:inline-block;background:#f5e3c8;color:#7a5a2e;font-size:10.5px;'
            f'font-weight:700;border-radius:999px;padding:2px 10px;margin-bottom:4px;">{tag}</span><br>'
            f'<span style="color:#3b1f0d;font-size:15px;font-weight:700;">{rname}</span> '
            f'<span style="color:#8a6a4a;font-size:12.5px;">({cname})</span><br>'
            f'<span style="color:#8a6a4a;font-size:12.5px;">{r["plan_name"]}</span></td>'
            f'<td align="{end_align}" style="padding:14px 18px;white-space:nowrap;">'
            f'<span dir="ltr" style="font-size:21px;font-weight:800;">{price_html}</span><br>'
            f'<span style="color:#8a6a4a;font-size:12px;">{gb} &middot; {per_month}</span>'
            f'</td></tr></table>')
    return "".join(cards)


def _market_ppgb(plans):
    """GB-weighted market ₪/GB (SUM(price)/SUM(GB), like the exec summary —
    a naive AVG lets tiny-data plans dominate). The consumer 'מדד MOCA' number."""
    tp = tg = 0.0
    for p in plans:
        gb, pr = p.get("data_gb"), p.get("price")
        if (pr and gb and gb >= 1 and not p.get("unlimited")
                and not p.get("voice_only") and not p.get("price_conditional")):
            tp += pr
            tg += gb
    return round(tp / tg, 3) if tg else None


def _market_percentile(base, plans):
    """Share (0-100) of comparable plans (>= the user's data, honest pricing)
    that cost MORE than the user's plan — 'cheaper than N% of the market'.
    None when the comparable set is too small to be meaningful."""
    INF = float("inf")

    def _data(p):
        return INF if (p.get("unlimited") or p.get("data_gb") is None) else (p.get("data_gb") or 0)

    base_price = base.get("price")
    if base_price is None:
        return None
    base_data = _data(base)
    comp = [p for p in plans
            if p.get("price") is not None and not p.get("voice_only")
            and not p.get("price_conditional") and _data(p) >= base_data
            and not (p.get("carrier") == base.get("carrier") and p.get("plan_name") == base.get("plan_name"))]
    if len(comp) < 3:
        return None
    return round(100 * sum(1 for p in comp if p["price"] > base_price) / len(comp))


def _rem_percentile_html(pct, lang):
    rtl = lang != "en"
    label = (f"החבילה שלכם זולה מ-{pct}% מהחבילות המקבילות בשוק" if rtl
             else f"Your plan is cheaper than {pct}% of comparable plans on the market")
    return (
        f'<div style="margin:14px 0 6px;">'
        f'<div style="font-size:13px;color:#3b1f0d;font-weight:700;margin-bottom:6px;">{label}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="background:#f0e6d8;border-radius:8px;padding:0;line-height:0;">'
        f'<div style="width:{max(4, min(100, pct))}%;background:#c9622f;height:10px;'
        f'border-radius:8px;font-size:0;">&nbsp;</div></td></tr></table></div>')


def _rem_stats_html(stats):
    """Row of metric chips [(value, label), ...] in the wizard-card style."""
    width = round(100 / max(1, len(stats)))
    cells = "".join(
        f'<td style="background:#f5ede0;border-radius:12px;padding:12px 6px;'
        f'text-align:center;width:{width}%;">'
        f'<div dir="ltr" style="font-size:17px;font-weight:700;color:#5c3317;">{v}</div>'
        f'<div style="font-size:11px;color:#8a6a4a;line-height:1.4;">{l}</div></td>'
        for v, l in stats)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="6" '
            f'style="margin:10px 0 4px;">{"<tr>" + cells + "</tr>"}</table>')


def _build_heartbeat_html(rem, base, pct, stats, config):
    """Monthly market-pulse email: reassurance + percentile bar + market chips."""
    lang = rem.get("lang") or "he"
    rtl = lang != "en"
    page_url, unsub_base = _rem_urls(config)
    utm = f"{page_url}?utm_source=reminder&utm_campaign=heartbeat" + ("&lang=en" if lang == "en" else "")
    unsub = unsub_base + rem["token"]
    cname = CARRIER_DISPLAY_NAMES.get(rem["carrier"], rem["carrier"])
    intro = (f'אנחנו ממשיכים לעקוב אחרי "{rem["plan_name"]}" ({cname}, ₪{_rem_fmt_price(base["price"])} לחודש) מול כל השוק. הנה תמונת המצב החודשית:'
             if rtl else
             f'We keep tracking "{rem["plan_name"]}" ({cname}, ₪{_rem_fmt_price(base["price"])}/month) against the whole market. Here is this month\'s picture:')
    reassure = ("ברגע שתופיע חבילה שמנצחת את שלכם - נעדכן מיד, בלי שתצטרכו לבדוק."
                if rtl else
                "The moment a plan beats yours - we alert you right away, no checking needed.")
    blocks = (
        f'<p style="margin:0 0 10px;color:#4a3a24;font-size:14px;line-height:1.7;">{intro}</p>'
        + (_rem_percentile_html(pct, lang) if pct is not None else "")
        + _rem_stats_html(stats)
        + f'<p style="margin:10px 0 0;color:#8a6a4a;font-size:12.5px;line-height:1.7;">{reassure}</p>')
    badge = "דופק השוק החודשי" if rtl else "Monthly market pulse"
    title = ("החבילה שלכם מול השוק - הכול תחת שליטה" if rtl
             else "Your plan vs the market - all under control")
    return _rem_email_shell(lang, unsub, _rem_email_body(lang, badge, title, blocks, utm),
                            hero_url=_rem_hero_url("heartbeat", config),
                            share_url=_rem_share_url(rem, config))


def _build_renewal_html(rem, offers, config):
    """Renewal follow-up email, ~a week after the plan term ended."""
    lang = rem.get("lang") or "he"
    rtl = lang != "en"
    page_url, unsub_base = _rem_urls(config)
    utm = f"{page_url}?utm_source=reminder&utm_campaign=renewal" + ("&lang=en" if lang == "en" else "")
    unsub = unsub_base + rem["token"]
    cname = CARRIER_DISPLAY_NAMES.get(rem["carrier"], rem["carrier"])
    p1 = (f'לפני כשבוע הסתיימה תקופת המסלול "{rem["plan_name"]}" ב{cname}.'
          if rtl else
          f'About a week ago the term of "{rem["plan_name"]}" at {cname} ended.')
    p2 = ("התחדשתם או עברתם מסלול? היכנסו לדף ההשוואה, לחצו על הפעמון בחבילה החדשה - ונמשיך לשמור על התנאים שלכם גם בתקופה הבאה."
          if rtl else
          "Renewed or switched? Open the comparison page, tap the bell on your new plan - and we will keep guarding your terms through the next term too.")
    blocks = (f'<p style="margin:0 0 10px;color:#4a3a24;font-size:14px;line-height:1.7;">{p1}</p>'
              f'<p style="margin:0 0 10px;color:#4a3a24;font-size:14px;line-height:1.7;">{p2}</p>')
    if offers:
        offers_title = "ההצעות המובילות היום לחבילה כמו שלכם" if rtl else "Today's top offers for a plan like yours"
        blocks += (f'<p style="margin:14px 0 8px;color:#3b1f0d;font-size:13.5px;font-weight:700;">{offers_title}</p>'
                   + _rem_deal_cards_html(offers, lang, mark_best=True))
    badge = "ממשיכים לשמור עליכם" if rtl else "Still watching over you"
    title = "התחדשתם? נמשיך לעקוב" if rtl else "Renewed? Let's keep tracking"
    return _rem_email_shell(lang, unsub, _rem_email_body(lang, badge, title, blocks, utm),
                            hero_url=_rem_hero_url("renewal", config),
                            share_url=_rem_share_url(rem, config))


def _rem_send(rem, subject, text_lines, config, html=None):
    """Deliver one reminder over its chosen channel(s). Returns True if at least
    one channel accepted the message. `html` overrides the plain generated email
    body (the WhatsApp text always comes from text_lines)."""
    lang = rem.get("lang") or "he"
    utm, unsub = _rem_links(rem, config)
    share_line = (("Know someone paying too much? Send them: " if lang == "en"
                   else "מכירים מישהו שמשלם יותר מדי? שלחו לו: ") + _rem_share_url(rem, config))
    body_lines = text_lines + ["", utm, share_line]
    ok = False
    channel = rem.get("channel") or "email"
    if channel in ("email", "both") and rem.get("email"):
        footer = ("Unsubscribe: " if lang == "en" else "להסרה מהעדכונים: ") + unsub
        text = "\n".join(body_lines + ["", footer, "", "MOCA"])
        if html is None:
            dir_attr = "ltr" if lang == "en" else "rtl"
            html_body = "".join(f"<p style='margin:6px 0'>{ln}</p>" for ln in body_lines if ln)
            html = (f"<div dir='{dir_attr}' style='font-family:Arial,sans-serif;font-size:15px;color:#3b1f0d'>"
                    f"{html_body}"
                    f"<p style='margin:14px 0 0;font-size:12px;color:#8a6a4a'>"
                    f"<a href='{unsub}'>{'Unsubscribe' if lang == 'en' else 'להסרה מהעדכונים'}</a> · MOCA</p></div>")
        if _send_email(config, rem["email"], subject, text=text, html=html):
            ok = True
    if channel in ("whatsapp", "both") and rem.get("phone"):
        footer = ("Unsubscribe: " if lang == "en" else "להסרה: ") + unsub
        if _send_whatsapp_direct(rem["phone"], "\n".join(body_lines + [footer]), config):
            ok = True
    return ok


def notify_mobile_better_deals(plans, config, db_path=None):
    """Recurring /mobile-deals reminder #1: 'a similar plan now costs less at
    another carrier'. Runs daily off the normalized feed. Per subscription, the
    best_price_alerted ratchet means a given offer alerts once — a re-alert
    needs a strictly better (>= ₪1 cheaper) competing offer. 72h cooldown."""
    from db import get_mobile_reminders, mark_mobile_reminder_notified
    sent = 0
    by_id = {f"{p['carrier']}|{p['plan_name']}": p for p in plans}
    for rem in get_mobile_reminders(kind="better_deal", db_path=db_path):
        last = rem.get("last_notified_at")
        if last:
            try:
                if (datetime.now() - datetime.fromisoformat(last)).total_seconds() < 72 * 3600:
                    continue
            except (ValueError, TypeError):
                pass
        # Compare against what the user actually PAYS: their self-declared
        # paid_price wins, else the plan's current rate-card price (prices move
        # after signup), else the signup snapshot.
        cur = by_id.get(f"{rem['carrier']}|{rem['plan_name']}")
        base = {"carrier": rem["carrier"], "price": _rem_base_price(rem, cur),
                "data_gb": rem.get("data_gb"), "unlimited": rem.get("unlimited")}
        deals = find_better_mobile_deals(base, plans)
        if not deals:
            continue
        best = deals[0]["price"]
        prev = rem.get("best_price_alerted")
        if prev is not None and best > prev - 1:
            continue
        lang = rem.get("lang") or "he"
        cname = CARRIER_DISPLAY_NAMES.get(rem["carrier"], rem["carrier"])
        if lang == "en":
            subject = f"MOCA: a better deal than {rem['plan_name']} ({cname})"
            head = [f"Good news - we found plans that beat \"{rem['plan_name']}\" ({cname}, ₪{_rem_fmt_price(base['price'])}):"]
        else:
            subject = f"MOCA: נמצאה חבילה משתלמת יותר מ{cname}"
            head = [f"חדשות טובות - מצאנו חבילות שמנצחות את \"{rem['plan_name']}\" ({cname}, ₪{_rem_fmt_price(base['price'])}):"]
        tail = []
        try:
            saving = float(base["price"]) - float(best)
            if saving >= 1:
                annual = round(saving * 12)
                tail = [(f"Switching saves up to ₪{_rem_fmt_price(saving)}/month - about ₪{annual} a year"
                         if lang == "en" else
                         f"מעבר חוסך עד ₪{_rem_fmt_price(saving)} בחודש - כ-₪{annual} בשנה")]
        except (TypeError, ValueError):
            pass
        btl = _find_reseller_deals(base, db_path=db_path)
        if btl:
            tail.append("Below the line (reseller offers):" if lang == "en"
                        else "מתחת לקו (הצעות משווקים):")
            for r in btl:
                rname = RESELLER_NAMES.get(r["reseller_id"], r["reseller_id"])
                cname = CARRIER_DISPLAY_NAMES.get(r["carrier"], r["carrier"])
                tail.append(f"• {rname} ({cname}) - {r['plan_name']}: ₪{_rem_fmt_price(r['price'])}")
        html = _build_better_deal_html(rem, base, deals, config, btl=btl)
        if _rem_send(rem, subject, head + _rem_deal_lines(deals, lang) + tail, config, html=html):
            mark_mobile_reminder_notified(rem["id"], best_price=best, db_path=db_path)
            sent += 1
    return sent


def notify_mobile_plan_end_reminders(plans, config, db_path=None):
    """One-shot /mobile-deals reminder #2: the user's plan term is about to end.
    Fires once when today >= end_date - remind_days_before; optionally attaches
    similar offers (retention alternatives). Reminders whose end_date passed
    more than 7 days ago are retired silently."""
    from db import get_mobile_reminders, mark_mobile_reminder_notified
    sent = 0
    today = datetime.now().date()
    for rem in get_mobile_reminders(kind="plan_end", db_path=db_path):
        try:
            end = datetime.fromisoformat((rem.get("end_date") or "")[:10]).date()
        except (ValueError, TypeError):
            mark_mobile_reminder_notified(rem["id"], done=True, db_path=db_path)
            continue
        days_before = rem.get("remind_days_before") or 7
        if today < end - timedelta(days=days_before):
            continue
        if today > end + timedelta(days=7):
            mark_mobile_reminder_notified(rem["id"], done=True, db_path=db_path)
            continue
        days_left = (end - today).days
        lang = rem.get("lang") or "he"
        cname = CARRIER_DISPLAY_NAMES.get(rem["carrier"], rem["carrier"])
        date_str = end.strftime("%d/%m/%Y")
        if lang == "en":
            subject = f"MOCA reminder: your plan at {cname} ends on {date_str}"
            when = "today" if days_left <= 0 else f"in {days_left} days" if days_left > 1 else "tomorrow"
            head = [f"Reminder: the term of \"{rem['plan_name']}\" at {cname} ends on {date_str} ({when}).",
                    "A good moment to renegotiate your terms or compare alternatives."]
            offers_title = "Similar offers available today:"
        else:
            subject = f"MOCA תזכורת: המסלול ב{cname} מסתיים ב-{date_str}"
            when = ("היום" if days_left <= 0
                    else "מחר" if days_left == 1
                    else f"בעוד {days_left} ימים")
            head = [f"תזכורת: תקופת המסלול \"{rem['plan_name']}\" ב{cname} מסתיימת ב-{date_str} ({when}).",
                    "זה הזמן לבדוק את התנאים מול המפעיל או להשוות חלופות."]
            offers_title = "הצעות דומות שזמינות היום:"
        lines = list(head)
        offers = []
        if rem.get("include_offers"):
            base = {"carrier": rem["carrier"], "plan_name": rem["plan_name"],
                    "price": rem.get("price"), "data_gb": rem.get("data_gb"),
                    "unlimited": rem.get("unlimited")}
            offers = find_similar_mobile_offers(base, plans)
            if offers:
                lines += ["", offers_title] + _rem_deal_lines(offers, lang)
        html = _build_plan_end_html(rem, head, offers, config)
        if _rem_send(rem, subject, lines, config, html=html):
            mark_mobile_reminder_notified(rem["id"], done=True, db_path=db_path)
            sent += 1
        else:
            # Delivery failed on every channel — keep the row so tomorrow's run
            # retries (still inside the pre-end window).
            pass
    return sent


def notify_mobile_heartbeat(plans, config, db_path=None):
    """Monthly 'market pulse' email for better_deal subscribers: keeps the
    channel warm between real alerts so the eventual alert doesn't land as a
    cold surprise. Email-only. Gated per row: >=28 days since the last touch
    (signup / alert / previous heartbeat), so a fresh signup or a recent
    better-deal alert pushes the pulse forward a month."""
    from db import get_mobile_reminders, touch_mobile_reminder_heartbeat, count_domestic_price_drops
    sent = 0
    now = datetime.now()
    drops = rises = None
    by_id = {f"{p['carrier']}|{p['plan_name']}": p for p in plans}
    honest = [p for p in plans if p.get("price") is not None
              and not p.get("voice_only") and not p.get("price_conditional")]
    for rem in get_mobile_reminders(kind="better_deal", db_path=db_path):
        if not rem.get("email") or (rem.get("channel") or "email") == "whatsapp":
            continue
        marks = [m for m in (rem.get("last_heartbeat_at"), rem.get("last_notified_at"),
                             rem.get("created_at")) if m]
        try:
            last = max(datetime.fromisoformat(m) for m in marks)
        except (ValueError, TypeError):
            continue
        if (now - last).days < 28:
            continue
        if drops is None:
            drops, rises = count_domestic_price_drops(30, db_path=db_path)
        cur = by_id.get(f"{rem['carrier']}|{rem['plan_name']}")
        base = {"carrier": rem["carrier"], "plan_name": rem["plan_name"],
                "price": _rem_base_price(rem, cur),
                "data_gb": rem.get("data_gb"), "unlimited": rem.get("unlimited")}
        if base["price"] is None:
            continue
        pct = _market_percentile(base, plans)
        lang = rem.get("lang") or "he"
        ppgb = _market_ppgb(plans)
        unl = min((p["price"] for p in honest if p.get("unlimited")), default=None)
        if lang == "en":
            stats = [(f"{drops}", "price drops, 30 days"), (f"{rises}", "price rises, 30 days")]
            if ppgb is not None:
                stats.append((f"₪{ppgb:g}", "MOCA index: ₪ per GB"))
            if unl is not None:
                stats.append((f"₪{_rem_fmt_price(unl)}", "cheapest unlimited"))
            subject = "MOCA: your monthly market pulse"
            lines = [f"Your plan \"{rem['plan_name']}\" is still being tracked against the whole market.",
                     f"Last 30 days: {drops} price drops and {rises} rises across the carriers."]
            if ppgb is not None:
                lines.append(f"MOCA index: the market's weighted average is ₪{ppgb:g} per GB.")
            if pct is not None:
                lines.append(f"Your plan is cheaper than {pct}% of comparable plans.")
            lines.append("The moment a plan beats yours - we alert you right away.")
        else:
            stats = [(f"{drops}", "ירידות מחיר ב-30 יום"), (f"{rises}", "עליות מחיר ב-30 יום")]
            if ppgb is not None:
                stats.append((f"₪{ppgb:g}", "מדד MOCA: ₪ לכל GB"))
            if unl is not None:
                stats.append((f"₪{_rem_fmt_price(unl)}", "ללא הגבלה - הזולה ביותר"))
            subject = "MOCA: דופק השוק החודשי שלך"
            lines = [f"אנחנו ממשיכים לעקוב אחרי \"{rem['plan_name']}\" מול כל השוק.",
                     f"ב-30 הימים האחרונים: {drops} ירידות מחיר ו-{rises} עליות אצל המפעילים."]
            if ppgb is not None:
                lines.append(f"מדד MOCA: הממוצע המשוקלל בשוק הוא ₪{ppgb:g} לכל GB.")
            if pct is not None:
                lines.append(f"החבילה שלכם זולה מ-{pct}% מהחבילות המקבילות.")
            lines.append("ברגע שתופיע חבילה שמנצחת את שלכם - נעדכן מיד.")
        html = _build_heartbeat_html(rem, base, pct, stats[:4], config)
        # Email-only nudge — never spend WhatsApp quota on a heartbeat.
        if _rem_send(dict(rem, channel="email"), subject, lines, config, html=html):
            touch_mobile_reminder_heartbeat(rem["id"], db_path=db_path)
            sent += 1
    return sent


def notify_mobile_renewal_followups(plans, config, db_path=None):
    """One-shot renewal follow-up ~a week after a plan_end reminder's end_date
    passed: 'did you renew? re-signup and we keep tracking'. Turns the one-shot
    plan-end reminder into a yearly loop. Email-only — rows without an email
    address are closed out silently."""
    from db import get_mobile_plan_end_followups, mark_mobile_reminder_followup
    sent = 0
    today = datetime.now().date()
    for rem in get_mobile_plan_end_followups(db_path=db_path):
        try:
            end = datetime.fromisoformat((rem.get("end_date") or "")[:10]).date()
        except (ValueError, TypeError):
            mark_mobile_reminder_followup(rem["id"], db_path=db_path)
            continue
        if today < end + timedelta(days=7):
            continue
        if not rem.get("email"):
            mark_mobile_reminder_followup(rem["id"], db_path=db_path)
            continue
        base = {"carrier": rem["carrier"], "plan_name": rem["plan_name"],
                "price": rem.get("price"), "data_gb": rem.get("data_gb"),
                "unlimited": rem.get("unlimited")}
        offers = find_similar_mobile_offers(base, plans)
        lang = rem.get("lang") or "he"
        cname = CARRIER_DISPLAY_NAMES.get(rem["carrier"], rem["carrier"])
        if lang == "en":
            subject = "MOCA: renewed your plan? Let's keep tracking"
            lines = [f"About a week ago the term of \"{rem['plan_name']}\" at {cname} ended.",
                     "Renewed or switched? Tap the bell on your new plan on the comparison page and we keep guarding your terms."]
            if offers:
                lines += ["", "Today's top offers for a plan like yours:"] + _rem_deal_lines(offers, lang)
        else:
            subject = "MOCA: התחדשתם? נמשיך לעקוב"
            lines = [f"לפני כשבוע הסתיימה תקופת המסלול \"{rem['plan_name']}\" ב{cname}.",
                     "התחדשתם או עברתם? לחצו על הפעמון בחבילה החדשה בדף ההשוואה ונמשיך לשמור על התנאים שלכם."]
            if offers:
                lines += ["", "ההצעות המובילות היום לחבילה כמו שלכם:"] + _rem_deal_lines(offers, lang)
        # Force the email channel: the row may be channel='both', but this
        # nudge is an email product (and consumer WhatsApp is quota-blocked).
        email_rem = dict(rem, channel="email")
        html = _build_renewal_html(rem, offers, config)
        if _rem_send(email_rem, subject, lines, config, html=html):
            mark_mobile_reminder_followup(rem["id"], db_path=db_path)
            sent += 1
    return sent


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
