"""Public /mobile-deals consumer API: normalized domestic feed, event beacons, carrier push alerts, email/WhatsApp reminders + the daily reminders job.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
import secrets
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
import re as _re_mobile
logger = core.logger
from flask import Blueprint
bp = Blueprint("mobile", __name__)


_RE_M_KOSHER = _re_mobile.compile(r'כשר|נטפרי|ועד הרבנים|KOSHER')


_RE_M_DATA_ONLY = _re_mobile.compile(r'DATA\s*ONLY|SIM\s*DATA|גלישה בלבד')


_RE_M_CONDITIONAL = _re_mobile.compile(r'קווים|בהצטרפות|כ\.אשראי|\bלקו\b')


_RE_M_CHIP_PRIO = _re_mobile.compile(
    r'חו"ל|חו״ל|לחו|אפליקציות|eSIM|תיעדוף|מתועדף|מחיר קבוע|ללא עליית', _re_mobile.IGNORECASE)


def _mobile_has_roaming(extras):
    """Included-roaming detector: a quantified data note ("1GB גלישה בחו\"ל") OR a
    qualitative "חו\"ל כלול" tag. Pay-per-use routes deliberately don't match."""
    for e in extras or []:
        if not core._RE_M_INTL.search(e):
            continue
        if (any(ch.isdigit() for ch in e) and core._RE_M_DATA_WORD.search(e)) or core._RE_M_INCLUDED.search(e):
            return True
    return False


def _mobile_minutes_abroad(extras):
    for e in extras or []:
        if ('דק' in e or 'שיחות' in e) and ('לחו"ל' in e or 'לחו״ל' in e):
            return True
    return False


def _assemble_mobile_plans(db_path):
    """Normalized consumer feed for /mobile-deals (see section comment)."""
    rows = core.get_plans(db_path=db_path)
    plans, updated = [], None
    for r in rows:
        extras = r.get('extras') or []
        info, vis = None, []
        for e in extras:
            if isinstance(e, str) and e.startswith('__info__|'):
                info = e.split('|', 1)[1]
            else:
                vis.append(e)
        hay = ((r.get('plan_name') or '') + ' ' + ' '.join(vis)).upper()
        five_g = bool(core._RE_M_5G.search(hay))
        priority = five_g and bool(core._RE_M_PRIORITY_HE.search(hay) or core._RE_M_PRIORITY_KW.search(hay))
        kosher = bool(_RE_M_KOSHER.search(hay))
        gb = r.get('data_gb')
        unlimited = voice_only = False
        if gb is not None and gb >= 9999:
            # wecom encodes "גלישה חופשית" as 10000GB — normalize to unlimited.
            unlimited, gb = True, None
        elif gb is None:
            # NULL is "unlimited" in the dashboard convention, but the only live
            # NULL rows are voice-only kosher plans — don't sell them as unlimited.
            if kosher or 'ללא גלישה' in hay:
                voice_only = True
            else:
                unlimited = True
        price = r.get('price')
        ppgb = None
        if not unlimited and not voice_only and gb and gb >= 1 and price:
            ppgb = round(price / gb, 2)
        cond_hay = (r.get('plan_name') or '') + ' ' + ' '.join(vis) + ' ' + (info or '')
        conditional = bool(_RE_M_CONDITIONAL.search(cond_hay))
        # Chip guard: a bare pay-per-use route mention (e.g. Pelephone's
        # 'מסלול חו"ל Travel' — intl wording with no quantity and no
        # included-tag) reads as an included-roaming benefit on a consumer
        # card. Keep it in the full extras/details, drop it from chips.
        def _chip_ok(e):
            if core._RE_M_INTL.search(e) and not any(ch.isdigit() for ch in e) \
                    and not core._RE_M_INCLUDED.search(e):
                return False
            return True
        short = [e for e in vis if len(e) <= 60 and _chip_ok(e)]
        chips = ([e for e in short if _RE_M_CHIP_PRIO.search(e)]
                 + [e for e in short if not _RE_M_CHIP_PRIO.search(e)])[:4]
        sa = r.get('scraped_at')
        if sa and (updated is None or sa > updated):
            updated = sa
        plans.append({
            'id': f"{r['carrier']}|{r['plan_name']}",
            'carrier': r['carrier'], 'plan_name': r['plan_name'],
            'price': price, 'promo_price': r.get('promo_price'),
            'promo_months': r.get('promo_months'),
            'data_gb': gb, 'unlimited': unlimited, 'voice_only': voice_only,
            'minutes': r.get('minutes'),
            'chips': chips, 'extras': vis, 'info': info,
            'terms_url': r.get('url'),
            'price_conditional': conditional,
            'price_per_gb': ppgb,
            'facets': {
                'five_g': five_g, 'five_g_priority': priority,
                'roaming': _mobile_has_roaming(vis),
                'minutes_abroad': _mobile_minutes_abroad(vis),
                'esim': 'ESIM' in hay,
                'kosher': kosher,
                'data_only': bool(_RE_M_DATA_ONLY.search(hay)),
                'free_apps': any('אפליקציות' in e for e in vis),
            },
            'scraped_at': sa,
        })
    carriers = []
    for cid, name in core._MOBILE_CARRIERS.items():
        mine = [p for p in plans if p['carrier'] == cid]
        if not mine:
            continue
        prices = [p['price'] for p in mine if p['price']]
        carriers.append({'id': cid, 'name': name, 'count': len(mine),
                         'min_price': min(prices) if prices else None})
    return {'plans': plans, 'carriers': carriers,
            'updated_at': updated or datetime.now(timezone.utc).isoformat()}


@bp.route("/api/mobile/compare")
@core.limiter.limit("60 per minute")
def api_mobile_compare():
    """Public consumer feed for /mobile-deals — normalized domestic plans +
    per-carrier summary. Roaming / content tabs reuse the existing public
    /api/abroad-plans and /api/content-plans as-is."""
    payload = core._cached_plans('mobile_compare', lambda: _assemble_mobile_plans(core._db_path()))
    return core._public_cache(jsonify(payload), 600)


@bp.route("/api/mobile/event", methods=["POST"])
@core.limiter.limit("240 per minute")
def api_mobile_event():
    """Anonymous traffic beacon from the public /mobile-deals page. No auth, no
    PII — ip hashed, sid is a random session token. Kept separate from
    /api/esim/event so the eSIM analytics funnel stays vertical-clean."""
    body = request.get_json(silent=True) or {}
    etype = (body.get("type") or "").strip()
    if etype not in ("page_view", "tab_pick", "carrier_click"):
        return jsonify({"ok": False}), 400
    from db import log_mobile_event
    log_mobile_event(
        etype,
        sid=body.get("sid"),
        tab=(body.get("tab") or None),
        carrier=(body.get("carrier") or None),
        src=(body.get("src") or None),
        campaign=(body.get("campaign") or None),
        lang=(body.get("lang") or None),
        referrer=(body.get("referrer") or None),
        ip_hash=core._guest_ip_hash(),
        db_path=core._db_path(),
    )
    return jsonify({"ok": True})


@bp.route("/api/mobile/push/subscribe", methods=["POST"])
@core.limiter.limit("10 per minute")
def api_mobile_push_subscribe():
    """Public (no auth): domestic price-drop alert from /mobile-deals.
    Body: { subscription: {endpoint, keys:{p256dh,auth}}, carrier, lang }.
    carrier is a domestic id or 'all'. One alert per device — re-subscribing
    moves it. Event-driven off the domestic change log (notify_mobile_price_drops),
    so unlike the eSIM flow there is no price baseline."""
    from db import save_mobile_push_subscription, log_mobile_event
    body = request.get_json(silent=True) or {}
    sub = body.get("subscription") or {}
    endpoint = (sub.get("endpoint") or "").strip()
    keys = sub.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    carrier = (body.get("carrier") or "all").strip() or "all"
    lang = body.get("lang") if body.get("lang") in ("he", "en") else "he"
    if not all([endpoint, p256dh, auth]):
        return jsonify({"error": "missing fields"}), 400
    if not endpoint.startswith("https://"):
        return jsonify({"error": "bad endpoint"}), 400
    if carrier != "all" and carrier not in core._MOBILE_CARRIERS:
        return jsonify({"error": "unknown carrier"}), 400
    save_mobile_push_subscription(endpoint, p256dh, auth, carrier=carrier, lang=lang,
                                  db_path=core._db_path())
    log_mobile_event("push_subscribe", sid=body.get("sid"), carrier=carrier,
                     src=(body.get("src") or None), campaign=(body.get("campaign") or None),
                     lang=lang, ip_hash=core._guest_ip_hash(), db_path=core._db_path())
    return jsonify({"status": "subscribed"}), 201


@bp.route("/api/mobile/push/unsubscribe", methods=["DELETE", "POST"])
@core.limiter.limit("10 per minute")
def api_mobile_push_unsubscribe():
    """Public: remove a /mobile-deals price-drop subscription by its endpoint."""
    from db import delete_mobile_push_subscription
    body = request.get_json(silent=True) or {}
    endpoint = (body.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"error": "missing endpoint"}), 400
    deleted = delete_mobile_push_subscription(endpoint, db_path=core._db_path())
    return jsonify({"status": "unsubscribed", "deleted": deleted}), 200


_REM_KINDS = ("better_deal", "plan_end")


_REM_PLAN_TYPES = ("domestic", "roaming", "content")


_REM_DAYS_CHOICES = (3, 7, 14, 30)


def _rem_parse_price(val):
    """First ₪ amount inside a free-text price (content_plans prices are strings
    like '19.90 ₪ לחודש'). None when there is no usable number."""
    m = _re_mobile.search(r"\d+(?:\.\d+)?", str(val or ""))
    try:
        p = float(m.group()) if m else None
        return p if p is not None and 0 < p <= 1000 else None
    except (TypeError, ValueError):
        return None


def _rem_lookup_plan(plan_type, carrier, plan_name):
    """Snapshot dict for the signed-up plan, validated against the live data of
    its type — or None when no such plan exists. For 'content', plan_name is the
    service name (content rows have no plan_name of their own)."""
    if plan_type == "roaming":
        from db import get_abroad_plans
        row = next((p for p in get_abroad_plans(carrier=carrier, db_path=core._db_path())
                    if p["plan_name"] == plan_name), None)
        if row is None:
            return None
        # Abroad NULL data_gb = a voice-minutes package (no data), NOT
        # unlimited — the matchers skip such rows on both sides.
        return {"price": row.get("price"), "data_gb": row.get("data_gb"),
                "unlimited": False, "days": row.get("days")}
    if plan_type == "content":
        from db import get_content_plans
        row = next((p for p in get_content_plans(service=plan_name, carrier=carrier,
                                                 db_path=core._db_path())), None)
        if row is None:
            return None
        return {"price": _rem_parse_price(row.get("price")), "data_gb": None,
                "unlimited": False, "days": None}
    feed = core._cached_plans('mobile_compare', lambda: _assemble_mobile_plans(core._db_path()))
    plan = next((p for p in feed.get("plans", [])
                 if p["carrier"] == carrier and p["plan_name"] == plan_name), None)
    if plan is None:
        return None
    return {"price": plan.get("price"), "data_gb": plan.get("data_gb"),
            "unlimited": plan.get("unlimited"), "days": None}


@bp.route("/api/mobile/reminders", methods=["POST"])
@core.limiter.limit("6 per minute")
def api_mobile_reminders_subscribe():
    """Public (no auth): /mobile-deals email/WhatsApp reminder signup.
    Body: { email?, phone?, kinds: ['better_deal'|'plan_end'...], plan_type?
    ('domestic'|'roaming'|'content', default domestic), carrier, plan_name,
    end_date?, remind_days_before?, include_offers?, lang, sid? }. For
    plan_type='content', plan_name carries the service name. At least one
    contact field is required; the plan must exist on the live data of its type
    (price/data are snapshotted server-side, never trusted from the client).
    Returns the shared unsubscribe token."""
    from db import save_mobile_reminders, log_mobile_event
    body = request.get_json(silent=True) or {}
    lang = body.get("lang") if body.get("lang") in ("he", "en") else "he"
    email = (body.get("email") or "").strip().lower()[:120]
    if email and not _re_mobile.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "bad email"}), 400
    phone = _re_mobile.sub(r"\D", "", (body.get("phone") or "").strip()[:25])
    if phone:
        if phone.startswith("0"):
            phone = "972" + phone[1:]
        if not _re_mobile.match(r"^\d{10,15}$", phone):
            return jsonify({"error": "bad phone"}), 400
    if not email and not phone:
        return jsonify({"error": "missing contact"}), 400
    carrier = (body.get("carrier") or "").strip()
    plan_name = (body.get("plan_name") or "").strip()[:200]
    plan_type = body.get("plan_type") if body.get("plan_type") in _REM_PLAN_TYPES else "domestic"
    kinds = [k for k in (body.get("kinds") or []) if k in _REM_KINDS]
    if not kinds:
        return jsonify({"error": "missing kinds"}), 400
    if carrier not in core._MOBILE_CARRIERS or not plan_name:
        return jsonify({"error": "unknown plan"}), 400
    plan = _rem_lookup_plan(plan_type, carrier, plan_name)
    if plan is None:
        return jsonify({"error": "unknown plan"}), 404
    channel = "both" if (email and phone) else ("email" if email else "whatsapp")
    # Optional self-declared actual monthly price ("כמה אתם משלמים בפועל?") —
    # when present, alerts compare against it instead of the rate-card price.
    paid_price = None
    try:
        pp = float(body.get("paid_price"))
        if 5 <= pp <= 500:
            paid_price = round(pp, 2)
    except (TypeError, ValueError):
        pass
    rows = []
    for k in kinds:
        row = {"kind": k, "plan_type": plan_type, "carrier": carrier,
               "plan_name": plan_name,
               "price": plan.get("price"), "data_gb": plan.get("data_gb"),
               "unlimited": plan.get("unlimited"), "days": plan.get("days"),
               "email": email or None,
               "phone": phone or None, "channel": channel, "lang": lang,
               "paid_price": paid_price}
        if k == "plan_end":
            today = datetime.now().date()
            try:
                end = datetime.strptime((body.get("end_date") or "").strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "bad end_date"}), 400
            if not (today <= end <= today + timedelta(days=3 * 365)):
                return jsonify({"error": "bad end_date"}), 400
            try:
                days_before = int(body.get("remind_days_before"))
            except (TypeError, ValueError):
                days_before = 7
            if days_before not in _REM_DAYS_CHOICES:
                days_before = 7
            row.update({"end_date": end.isoformat(), "remind_days_before": days_before,
                        "include_offers": bool(body.get("include_offers", True))})
        rows.append(row)
    token = secrets.token_urlsafe(24)
    save_mobile_reminders(token, rows, db_path=core._db_path())
    log_mobile_event("reminder_subscribe", sid=body.get("sid"), carrier=carrier,
                     src=(body.get("src") or None), campaign=(body.get("campaign") or None),
                     lang=lang, ip_hash=core._guest_ip_hash(), db_path=core._db_path())
    return jsonify({"status": "subscribed", "token": token, "kinds": kinds}), 201


@bp.route("/api/mobile/reminders/unsubscribe", methods=["GET", "POST"])
@core.limiter.limit("30 per minute")
def api_mobile_reminders_unsubscribe():
    """Public: remove ALL reminder rows of one signup by its shared token.
    GET renders a tiny bilingual confirmation page (the email/WhatsApp links
    are plain <a> clicks); POST returns JSON for in-app use."""
    from db import delete_mobile_reminders_by_token
    token = (request.args.get("token")
             or (request.get_json(silent=True) or {}).get("token") or "").strip()
    if not token or len(token) > 80:
        return jsonify({"error": "missing token"}), 400
    deleted = delete_mobile_reminders_by_token(token, db_path=core._db_path())
    if request.method == "POST":
        return jsonify({"status": "unsubscribed", "deleted": deleted})
    msg_he = ("הוסרת מרשימת העדכונים. לא יישלחו יותר תזכורות." if deleted
              else "הקישור כבר אינו פעיל - ההרשמה הוסרה בעבר.")
    msg_en = ("You have been unsubscribed - no more reminders will be sent." if deleted
              else "This link is no longer active - the signup was already removed.")
    site = (core.load_config().get("public_site_url") or "https://mocaintel.com").rstrip("/")
    page = (
        "<!doctype html><html dir='rtl' lang='he'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>MOCA</title></head>"
        "<body style='font-family:Arial,sans-serif;background:#f9f4ee;color:#3b1f0d;"
        "display:flex;align-items:center;justify-content:center;min-height:90vh;margin:0'>"
        "<div style='background:#fff;border-radius:20px;padding:32px 28px;max-width:420px;"
        "text-align:center;box-shadow:0 6px 24px rgba(70,45,20,.08)'>"
        "<div style='font-size:34px;margin-bottom:10px'>&#9889;</div>"
        f"<h1 style='font-size:19px;margin:0 0 8px'>MOCA</h1>"
        f"<p style='font-size:15px;margin:0 0 6px'>{msg_he}</p>"
        f"<p dir='ltr' style='font-size:13px;color:#8a6a4a;margin:0 0 16px'>{msg_en}</p>"
        f"<a href='{site}/mobile-deals' "
        f"style='color:#5c3317;font-weight:bold'>{site.split('//', 1)[-1]}/mobile-deals</a>"
        "</div></body></html>")
    return Response(page, mimetype="text/html")


def run_mobile_reminders_job():
    """Daily 09:15 — deliver /mobile-deals email/WhatsApp reminders off the
    normalized domestic feed: better-deal alerts (recurring, price-ratcheted)
    and plan-term-end reminders (one-shot, optional retention offers)."""
    try:
        from notifier import (notify_mobile_better_deals, notify_mobile_plan_end_reminders,
                              notify_mobile_heartbeat, notify_mobile_renewal_followups)
        config = core.load_config()
        plans = _assemble_mobile_plans(core._db_path()).get("plans", [])
        n_deal = notify_mobile_better_deals(plans, config, db_path=core._db_path())
        n_end = notify_mobile_plan_end_reminders(plans, config, db_path=core._db_path())
        n_renew = notify_mobile_renewal_followups(plans, config, db_path=core._db_path())
        n_pulse = notify_mobile_heartbeat(plans, config, db_path=core._db_path())
        logger.info(f"mobile reminders job: {n_deal} better-deal + {n_end} plan-end "
                    f"+ {n_renew} renewal + {n_pulse} heartbeat sent")
        return {"better_deal_sent": n_deal, "plan_end_sent": n_end,
                "renewal_sent": n_renew, "heartbeat_sent": n_pulse}
    except Exception as e:
        logger.error(f"mobile reminders job failed: {e}")
        return {"error": str(e)}


@bp.route("/api/mobile/reminders/run-now", methods=["GET", "POST"])
@core.require_api_key
def api_mobile_reminders_run_now():
    """Manual trigger / smoke-test for the daily reminders job."""
    return jsonify(run_mobile_reminders_job())


@bp.route("/api/mobile/reminders/subscribers")
@core.require_api_key_or_super_admin
def api_mobile_reminders_subscribers():
    """Super-admin: every reminder signup (contact details included) for the
    /admin/mobile-subscribers dashboard. Returns ALL rows — active and done —
    newest first, plus summary counts."""
    from db import get_all_mobile_reminders
    rows = get_all_mobile_reminders(db_path=core._db_path())
    emails = {r["email"] for r in rows if r.get("email")}
    phones = {r["phone"] for r in rows if r.get("phone")}
    return jsonify({
        "rows": rows,
        "stats": {
            "total_rows": len(rows),
            "active_rows": sum(1 for r in rows if not r.get("done")),
            "unique_emails": len(emails),
            "unique_phones": len(phones),
        },
    })
