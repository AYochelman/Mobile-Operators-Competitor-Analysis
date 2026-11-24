"""Dashboard setup wizard (/setup) - validation + the personal change alerts.

Two kinds of answers, both stored as JSON in the `dashboard_setup` table (db.py):

* WORKSPACE level (written by the customer's admin): which sections the
  dashboard shows, which are emphasized, the landing page and the competitors
  the organization cares about most.
* USER level (written by every user for themself): alert channels (e-mail /
  WhatsApp), the address or number, a frequency per channel, which categories
  and events to report, a minimum price move, days + hours when messages may be
  sent, and the message language.

The dispatcher (`run_dispatch`) is the only sender. It is cursor based: per
(user, channel) it remembers the timestamp up to which changes were handled,
reads the change LOG (never a live scrape) for everything newer, filters it by
the workspace's scoping rules and the user's choices, and sends one message.
Quiet hours never drop anything - the cursor simply does not advance until a
message may go out again.

Nothing here talks to Supabase: callers pass a `resolver(email) -> context`
(app._get_user_context) so the module stays testable offline.
"""
import html as _html
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Catalogs (mirror mass-market-app/src/data/navFlags.js FLAG_FOR_PATH) ─────
SECTION_FLAGS = {
    "/": "hide_dashboard",
    "/plans": "hide_domestic",
    "/roaming": "hide_abroad",
    "/esim": "hide_global",
    "/esim-banners": "hide_global_banners",
    "/usa": "hide_usa",
    "/ski": "hide_ski",
    "/resellers": "hide_resellers",
    "/content": "hide_content",
    "/compare": "hide_compare",
    "/cockpit": "hide_cockpit",
    "/agent-desk": "hide_agent_desk",
    "/simulator": "hide_simulator",
    "/executive-summary": "hide_executive_summary",
    "/positioning": "hide_positioning",
    "/ai-insights": "hide_ai_insights",
    "/news": "hide_news",
    "/social": "hide_social",
    "/banners": "hide_banners",
    "/archive": "hide_archive",
    "/history": "hide_history",
    "/alerts": "hide_alerts",
}
# Alert category -> the section whose hiding also silences that category.
CATEGORY_SECTION = {
    "domestic": "/plans",
    "abroad": "/roaming",
    "global": "/esim",
    "content": "/content",
    "resellers": "/resellers",
}
CATEGORIES = tuple(CATEGORY_SECTION)
EVENTS = ("price_drop", "price_rise", "new_plan", "removed_plan", "terms_change")
ROLES = ("marketing", "pricing", "sales", "management", "other")
FREQUENCIES = ("immediate", "daily", "weekly")
CHANNELS = ("email", "whatsapp")
SECTION_STATES = ("focus", "hidden")          # "normal" is the absence of an entry

DAILY_SEND_TIME = (8, 30)                     # daily / weekly summaries go out from 08:30
MAX_LOOKBACK_DAYS = 8                         # never report anything older than this
WHATSAPP_MAX_LINES = 12
EMAIL_MAX_LINES = 40

_RE_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")
_RE_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_RE_CARRIER = re.compile(r"^[a-z0-9_]{1,40}$")

DEFAULT_USER_CONFIG = {
    "role": "other",
    "channels": {
        "email":    {"enabled": True,  "address": "", "frequency": "daily"},
        "whatsapp": {"enabled": False, "phone": "",   "frequency": "immediate"},
    },
    "categories": ["domestic", "abroad"],
    "events": ["price_drop", "price_rise", "new_plan", "removed_plan"],
    "min_price_delta": 1,
    "carrier_scope": "all",
    "quiet": {"days": [0, 1, 2, 3, 4], "from": "08:00", "to": "20:00"},
    "lang": "he",
}


class SetupError(ValueError):
    """A wizard payload that cannot be saved; the message is safe to show."""


# ── Validation ───────────────────────────────────────────────────────────────

def normalize_phone(raw):
    """Digits in international form (Israeli 05x -> 9725x). '' when empty;
    raises SetupError when it is not a plausible number."""
    digits = re.sub(r"\D", "", str(raw or "")[:25])
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "972" + digits[1:]
    if not re.match(r"^\d{10,15}$", digits):
        raise SetupError("bad phone")
    return digits


def _clean_carriers(values, limit=60):
    out = []
    for v in values if isinstance(values, (list, tuple)) else []:
        v = str(v or "").strip().lower()
        if _RE_CARRIER.match(v) and v not in out:
            out.append(v)
    return out[:limit]


def clean_workspace_config(data, locked_flags=None):
    """Validate the workspace-level answers. `locked_flags` = the workspace's
    own feature_flags (set by the operator): a section hidden there cannot be
    emphasized or chosen as the landing page."""
    data = data if isinstance(data, dict) else {}
    locked = {p for p, f in SECTION_FLAGS.items() if (locked_flags or {}).get(f)}
    sections = {}
    raw_sections = data.get("sections") if isinstance(data.get("sections"), dict) else {}
    for path, state in raw_sections.items():
        if path in SECTION_FLAGS and state in SECTION_STATES and path not in locked:
            sections[path] = state
    visible = [p for p in SECTION_FLAGS if p not in locked and sections.get(p) != "hidden"]
    if not visible:
        raise SetupError("at least one section must stay visible")
    landing = data.get("landing") or ""
    if landing not in visible:
        landing = ""
    return {
        "sections": sections,
        "landing": landing,
        "focus_carriers": _clean_carriers(data.get("focus_carriers")),
    }


def clean_user_config(data, default_email=""):
    """Validate the user-level answers; raises SetupError on a bad address/number."""
    data = data if isinstance(data, dict) else {}
    out = {"role": data.get("role") if data.get("role") in ROLES else "other"}

    channels_in = data.get("channels") if isinstance(data.get("channels"), dict) else {}
    em = channels_in.get("email") if isinstance(channels_in.get("email"), dict) else {}
    wa = channels_in.get("whatsapp") if isinstance(channels_in.get("whatsapp"), dict) else {}

    address = str(em.get("address") or default_email or "").strip().lower()[:254]
    em_on = bool(em.get("enabled"))
    if em_on and not _RE_EMAIL.match(address):
        raise SetupError("bad email")
    if address and not _RE_EMAIL.match(address):
        address = ""
    phone = normalize_phone(wa.get("phone")) if (wa.get("enabled") or wa.get("phone")) else ""
    wa_on = bool(wa.get("enabled"))
    if wa_on and not phone:
        raise SetupError("bad phone")

    def _freq(v, default):
        return v if v in FREQUENCIES else default

    out["channels"] = {
        "email":    {"enabled": em_on, "address": address, "frequency": _freq(em.get("frequency"), "daily")},
        "whatsapp": {"enabled": wa_on, "phone": phone, "frequency": _freq(wa.get("frequency"), "immediate")},
    }
    cats = data.get("categories") if isinstance(data.get("categories"), list) else []
    out["categories"] = [c for c in CATEGORIES if c in cats]
    evs = data.get("events") if isinstance(data.get("events"), list) else []
    out["events"] = [e for e in EVENTS if e in evs]
    try:
        delta = float(data.get("min_price_delta", 1))
    except (TypeError, ValueError):
        delta = 1.0
    out["min_price_delta"] = round(min(max(delta, 0.0), 500.0), 2)
    out["carrier_scope"] = "focus" if data.get("carrier_scope") == "focus" else "all"

    quiet = data.get("quiet") if isinstance(data.get("quiet"), dict) else {}
    days = sorted({int(d) for d in (quiet.get("days") or [])
                   if isinstance(d, (int, float)) and not isinstance(d, bool) and 0 <= int(d) <= 6})
    if not days:
        days = list(range(7))
    t_from = quiet.get("from") if _RE_TIME.match(str(quiet.get("from") or "")) else "08:00"
    t_to = quiet.get("to") if _RE_TIME.match(str(quiet.get("to") or "")) else "20:00"
    out["quiet"] = {"days": days, "from": t_from, "to": t_to}
    out["lang"] = "en" if data.get("lang") == "en" else "he"
    return out


def hidden_section_flags(workspace_config):
    """{flag: True} for every section the customer's admin chose to hide."""
    sections = (workspace_config or {}).get("sections") or {}
    return {SECTION_FLAGS[p]: True for p, s in sections.items()
            if s == "hidden" and p in SECTION_FLAGS}


# ── Scheduling ───────────────────────────────────────────────────────────────

def _parse_iso(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _sunday_weekday(dt):
    """0 = Sunday ... 6 = Saturday (the wizard's day numbering)."""
    return (dt.weekday() + 1) % 7


def is_allowed_now(quiet, now):
    """True when `now` falls inside the days + hours the user allows messages."""
    quiet = quiet or {}
    days = quiet.get("days") or list(range(7))
    if _sunday_weekday(now) not in days:
        return False
    t_from, t_to = str(quiet.get("from") or "00:00"), str(quiet.get("to") or "23:59")
    if t_from >= t_to:                       # degenerate window = whole day
        return True
    return t_from <= now.strftime("%H:%M") < t_to


def is_due(frequency, cursor, now):
    """Whether a channel on `frequency` should produce a message at `now`,
    given the timestamp its cursor last advanced to."""
    if frequency == "immediate":
        return True
    if (now.hour, now.minute) < DAILY_SEND_TIME:
        return False
    if frequency == "daily":
        return cursor.date() < now.date()
    if frequency == "weekly":
        week = lambda d: d.date() - timedelta(days=_sunday_weekday(d))  # noqa: E731
        return week(cursor) < week(now)
    return False


# ── Filtering ────────────────────────────────────────────────────────────────

def _num(value):
    """First number in a change-log value ('₪19.90' / '27.9' / None) or None."""
    m = re.search(r"-?\d+(?:\.\d+)?", str(value if value is not None else "").replace(",", ""))
    return float(m.group()) if m else None


def classify_event(change):
    """Change-log row -> one of EVENTS (or None when it should never be reported)."""
    ctype = change.get("change_type")
    if ctype == "new_plan":
        return "new_plan"
    if ctype == "removed_plan":
        return "removed_plan"
    if ctype == "price_change":
        old, new = _num(change.get("old_val")), _num(change.get("new_val"))
        if old is None or new is None:
            return "price_drop"              # e.g. content 'לא קיים' -> '₪19.90'
        if new == old:
            return None
        return "price_drop" if new < old else "price_rise"
    if ctype in ("extras_change", "details_change"):
        return "terms_change"
    return None


def _net_changes(changes):
    """Collapse repeats inside the window: one row per (category, carrier, plan,
    change_type) - a price that moved twice is reported earliest-old -> latest-new,
    and a price that came back to where it started is dropped."""
    merged, order = {}, []
    for c in changes:                         # oldest first
        key = (c["category"], c.get("reseller_id"), c["carrier"], c["plan_name"], c["change_type"])
        if key not in merged:
            merged[key] = dict(c)
            order.append(key)
        else:
            merged[key]["new_val"] = c["new_val"]
            merged[key]["changed_at"] = c["changed_at"]
    out = []
    for key in order:
        c = merged[key]
        if c["change_type"] == "price_change":
            old, new = _num(c.get("old_val")), _num(c.get("new_val"))
            if old is not None and new is not None and old == new:
                continue
        out.append(c)
    # A plan that was both launched and removed inside the window is a scrape flap.
    launched = {k[:4] for k in order if k[4] == "new_plan"}
    removed = {k[:4] for k in order if k[4] == "removed_plan"}
    flaps = launched & removed
    return [c for c in out
            if not (c["change_type"] in ("new_plan", "removed_plan")
                    and (c["category"], c.get("reseller_id"), c["carrier"], c["plan_name"]) in flaps)]


def filter_changes(changes, user_cfg, workspace=None):
    """Apply the workspace's scoping rules and the user's choices.

    `workspace` is the context's workspace dict (or None for a super_admin):
    feature_flags, dashboard_config, mvno_carrier, hide_self_carrier,
    visible_carriers. Returns the reportable rows, each tagged with `event`,
    most important first."""
    ws = workspace or {}
    ws_cfg = ws.get("dashboard_config") or {}
    flags = dict(ws.get("feature_flags") or {})
    flags.update(hidden_section_flags(ws_cfg))
    cats = {c for c in (user_cfg.get("categories") or [])
            if not flags.get(SECTION_FLAGS[CATEGORY_SECTION[c]])}
    events = set(user_cfg.get("events") or [])
    min_delta = float(user_cfg.get("min_price_delta") or 0)
    self_carrier = ws.get("mvno_carrier") if ws.get("hide_self_carrier") else None
    allowed = set(ws.get("visible_carriers") or [])
    focus = list(ws_cfg.get("focus_carriers") or [])
    focus_only = user_cfg.get("carrier_scope") == "focus" and bool(focus)

    kept = []
    for c in _net_changes([c for c in changes if c.get("category") in cats]):
        carrier = c.get("carrier")
        if self_carrier and carrier == self_carrier:
            continue
        # The allowlist names domestic carriers; global eSIM providers are not in it.
        if allowed and c["category"] != "global" and carrier not in allowed:
            continue
        if focus_only and carrier not in focus:
            continue
        event = classify_event(c)
        if event not in events:
            continue
        delta = None
        if c["change_type"] == "price_change":
            old, new = _num(c.get("old_val")), _num(c.get("new_val"))
            if old is not None and new is not None:
                delta = new - old
                if abs(delta) < min_delta:
                    continue
        kept.append({**c, "event": event, "delta": delta, "focus": carrier in focus})

    rank = {"price_drop": 0, "price_rise": 0, "new_plan": 1, "removed_plan": 2, "terms_change": 3}
    kept.sort(key=lambda c: (not c["focus"], rank[c["event"]], -abs(c["delta"] or 0)))
    return kept


# ── Message building ─────────────────────────────────────────────────────────

_T = {
    "he": {
        "title": "MOCA · עדכון מתחרים",
        "kind": {"immediate": "עדכון שוטף", "daily": "סיכום יומי", "weekly": "סיכום שבועי"},
        "count_1": "שינוי אחד שעונה להגדרות שלך",
        "count_n": "{n} שינויים שעונים להגדרות שלך",
        "cat": {"domestic": "סלולר", "abroad": "חבילות חו\"ל", "global": "eSIM גלובלי",
                "content": "שירותי תוכן", "resellers": "משווקים (מתחת לקו)"},
        "new": "תוכנית חדשה", "removed": "תוכנית הוסרה", "terms": "שינוי בתנאים או בהטבות",
        "more": "ועוד {n} שינויים בדשבורד",
        "open": "לצפייה בדשבורד", "settings": "לשינוי הגדרות ההתראות",
        "subject_1": "MOCA · שינוי אחד אצל המתחרים", "subject_n": "MOCA · {n} שינויים אצל המתחרים",
        "focus": "במוקד",
        "test": "זוהי הודעת בדיקה מ-MOCA. הערוץ מוגדר כראוי, וההתראות יגיעו לכאן לפי ההגדרות שנבחרו.",
        "test_subject": "MOCA · הודעת בדיקה",
        "footer": "ההודעה נשלחה לפי ההגדרות שנבחרו באשף ההתאמה האישית של MOCA.",
    },
    "en": {
        "title": "MOCA · Competitor update",
        "kind": {"immediate": "Live update", "daily": "Daily summary", "weekly": "Weekly summary"},
        "count_1": "1 change matching your settings",
        "count_n": "{n} changes matching your settings",
        "cat": {"domestic": "Mobile plans", "abroad": "Roaming", "global": "Global eSIM",
                "content": "Content services", "resellers": "Resellers (below the line)"},
        "new": "New plan", "removed": "Plan removed", "terms": "Terms or benefits changed",
        "more": "and {n} more changes on the dashboard",
        "open": "Open the dashboard", "settings": "Change alert settings",
        "subject_1": "MOCA · 1 competitor change", "subject_n": "MOCA · {n} competitor changes",
        "focus": "Focus",
        "test": "This is a test message from MOCA. The channel is set up correctly and alerts "
                "will arrive here according to your settings.",
        "test_subject": "MOCA · Test message",
        "footer": "Sent according to the settings chosen in MOCA's personalization wizard.",
    },
}
_ICON = {"price_drop": "🔻", "price_rise": "🔺", "new_plan": "🆕", "removed_plan": "❌", "terms_change": "📝"}


def _site_url(config):
    return (config.get("public_site_url") or "https://mocaintel.com").rstrip("/")


def _carrier_label(change, lang):
    try:
        from notifier import _carrier_name, RESELLER_NAMES
        name = _carrier_name(change.get("carrier") or "", lang)
        rid = change.get("reseller_id")
        if rid:
            return f"{RESELLER_NAMES.get(rid, rid)} ({name})"
        return name
    except Exception:
        return change.get("carrier") or ""


def _fmt_price(value, category):
    n = _num(value)
    if n is None:
        return str(value or "")
    txt = f"{n:.2f}".rstrip("0").rstrip(".")
    # Global rows may be logged in the provider's own currency - no symbol there.
    return txt if category == "global" else f"₪{txt}"


def describe_change(change, lang="he"):
    """(who, what) plain-text pair for one filtered change."""
    S = _T["en" if lang == "en" else "he"]
    who = f"{_carrier_label(change, lang)} · {change.get('plan_name') or ''}"
    event, cat = change["event"], change["category"]
    if event in ("price_drop", "price_rise"):
        old, new = _fmt_price(change.get("old_val"), cat), _fmt_price(change.get("new_val"), cat)
        o, n = _num(change.get("old_val")), _num(change.get("new_val"))
        pct = f" ({(n - o) / o * 100:+.0f}%)" if o and n is not None else ""
        # LRM keeps "old → new" in reading order inside a right-to-left line.
        return who, f"‎{old} → {new}{pct}"
    if event == "new_plan":
        price = _fmt_price(change.get("new_val"), cat) if _num(change.get("new_val")) is not None else ""
        return who, S["new"] + (f" · ‎{price}" if price else "")
    if event == "removed_plan":
        return who, S["removed"]
    return who, S["terms"]


def build_text_message(changes, frequency, lang, config, max_lines=WHATSAPP_MAX_LINES):
    """WhatsApp / plain-text body."""
    S = _T["en" if lang == "en" else "he"]
    n = len(changes)
    lines = [f"*{S['title']}*", f"{S['kind'][frequency]} · " +
             (S["count_1"] if n == 1 else S["count_n"].format(n=n))]
    shown = changes[:max_lines]
    for cat in CATEGORIES:
        rows = [c for c in shown if c["category"] == cat]
        if not rows:
            continue
        lines += ["", f"*{S['cat'][cat]}*"]
        for c in rows:
            who, what = describe_change(c, lang)
            lines.append(f"{_ICON[c['event']]} {who}: {what}")
    if n > len(shown):
        lines += ["", S["more"].format(n=n - len(shown))]
    site = _site_url(config)
    lines += ["", f"{S['open']}: {site}/home", f"{S['settings']}: {site}/setup"]
    return "\n".join(lines)


def build_email(changes, frequency, lang, config, max_lines=EMAIL_MAX_LINES):
    """(subject, text, html) for the e-mail channel."""
    S = _T["en" if lang == "en" else "he"]
    rtl = lang != "en"
    n = len(changes)
    subject = S["subject_1"] if n == 1 else S["subject_n"].format(n=n)
    text = build_text_message(changes, frequency, lang, config, max_lines=max_lines).replace("*", "")
    site = _site_url(config)
    align = "right" if rtl else "left"
    esc = _html.escape
    shown = changes[:max_lines]
    blocks = []
    for cat in CATEGORIES:
        rows = [c for c in shown if c["category"] == cat]
        if not rows:
            continue
        trs = []
        for c in rows:
            who, what = describe_change(c, lang)
            color = {"price_drop": "#4a7c3f", "price_rise": "#b4472d"}.get(c["event"], "#3b1f0d")
            tag = (f' <span style="background:#fdeee3;color:#9a4419;font-size:11px;font-weight:700;'
                   f'border-radius:999px;padding:1px 8px;">{S["focus"]}</span>') if c.get("focus") else ""
            trs.append(
                f'<tr><td style="padding:9px 0;border-bottom:1px solid #f0e4d2;text-align:{align};">'
                f'<div style="color:#3b1f0d;font-size:14px;font-weight:600;">{esc(who)}{tag}</div>'
                f'<div style="color:{color};font-size:13.5px;margin-top:2px;">'
                f'{_ICON[c["event"]]} {esc(what)}</div></td></tr>')
        blocks.append(
            f'<tr><td style="padding:16px 28px 0;text-align:{align};">'
            f'<div style="color:#7d5f40;font-size:12px;font-weight:700;letter-spacing:.4px;">'
            f'{esc(S["cat"][cat])}</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(trs)}</table>'
            f'</td></tr>')
    more = ""
    if n > len(shown):
        more = (f'<tr><td style="padding:12px 28px 0;color:#7d5f40;font-size:13px;text-align:{align};">'
                f'{esc(S["more"].format(n=n - len(shown)))}</td></tr>')
    count = S["count_1"] if n == 1 else S["count_n"].format(n=n)
    html = (
        f'<!doctype html><html lang="{"he" if rtl else "en"}" dir="{"rtl" if rtl else "ltr"}"><body '
        f'style="margin:0;background:#f9f4ee;font-family:\'Assistant\',\'Segoe UI\',Arial,sans-serif;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f9f4ee;">'
        f'<tr><td align="center" style="padding:24px 12px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="{"rtl" if rtl else "ltr"}" '
        f'style="max-width:600px;background:#ffffff;border:1px solid #e0cdb5;border-radius:16px;">'
        f'<tr><td style="padding:22px 28px 0;text-align:{align};">'
        f'<div style="color:#5c3317;font-size:13px;font-weight:700;letter-spacing:.5px;">MOCA</div>'
        f'<h1 style="margin:6px 0 2px;color:#3b1f0d;font-size:20px;font-weight:700;">'
        f'{esc(S["kind"][frequency])}</h1>'
        f'<div style="color:#7d5f40;font-size:13.5px;">{esc(count)}</div></td></tr>'
        f'{"".join(blocks)}{more}'
        f'<tr><td align="center" style="padding:22px 28px 8px;">'
        f'<a href="{site}/home" style="display:inline-block;background:#5c3317;color:#ffffff;'
        f'text-decoration:none;font-size:14px;font-weight:700;border-radius:999px;padding:11px 30px;">'
        f'{esc(S["open"])}</a></td></tr>'
        f'<tr><td align="center" style="padding:6px 28px 22px;color:#6f553b;font-size:12px;">'
        f'{esc(S["footer"])} <a href="{site}/setup" style="color:#5c3317;">{esc(S["settings"])}</a>'
        f'</td></tr></table></td></tr></table></body></html>')
    return subject, text, html


# ── Sending ──────────────────────────────────────────────────────────────────

def _default_senders():
    from notifier import _send_email, _send_whatsapp_direct
    return {
        "email": lambda to, subject, text, html, config: bool(
            _send_email(config, to, subject, text=text, html=html)),
        "whatsapp": lambda phone, text, config: bool(_send_whatsapp_direct(phone, text, config)),
    }


def send_test(channel, target, lang, config, senders=None):
    """Send the fixed test message to one address / number. Returns bool."""
    S = _T["en" if lang == "en" else "he"]
    senders = senders or _default_senders()
    if channel == "email":
        body = (f'<div dir="{"ltr" if lang == "en" else "rtl"}" style="font-family:Arial,sans-serif;'
                f'color:#3b1f0d;font-size:15px;">{_html.escape(S["test"])}</div>')
        return senders["email"](target, S["test_subject"], S["test"], body, config)
    if channel == "whatsapp":
        return senders["whatsapp"](target, S["test"], config)
    return False


_FAIL_UNTIL = {}                              # (email, channel) -> datetime; retry back-off
FAIL_BACKOFF = timedelta(hours=6)


def run_dispatch(config, resolver, now=None, dry_run=False, db_path=None, senders=None,
                 only_email=None):
    """Send every personal alert that is due right now.

    resolver(email) -> the user's context ({role, workspace, reason?}).
    Returns a per-(user, channel) report list; with dry_run nothing is sent and
    no cursor moves. Never raises for a single user's failure."""
    import db
    now = now or datetime.now()
    now_iso = now.isoformat()
    report = []
    senders = senders if senders is not None else (None if dry_run else _default_senders())

    for row in db.list_dashboard_user_setups(db_path=db_path):
        email = row["email"]
        if only_email and email != only_email:
            continue
        cfg = row["config"]
        active = [(ch, c) for ch, c in (cfg.get("channels") or {}).items()
                  if ch in CHANNELS and isinstance(c, dict) and c.get("enabled")]
        if not active:
            continue
        try:
            cursors = db.get_alert_cursors(email, db_path=db_path)
            allowed_now = is_allowed_now(cfg.get("quiet"), now)
            ctx = None
            for channel, ch_cfg in active:
                freq = ch_cfg.get("frequency") if ch_cfg.get("frequency") in FREQUENCIES else "daily"
                entry = {"email": email, "channel": channel, "frequency": freq}
                cursor = _parse_iso((cursors.get(channel) or {}).get("last_sent_at"))
                if cursor is None:
                    # First sight of this channel: start counting from now.
                    if not dry_run:
                        db.set_alert_cursor(email, channel, now_iso, db_path=db_path)
                    report.append({**entry, "status": "initialized"})
                    continue
                if not is_due(freq, cursor, now):
                    report.append({**entry, "status": "not_due"})
                    continue
                if not allowed_now:
                    report.append({**entry, "status": "quiet_hours"})
                    continue
                if _FAIL_UNTIL.get((email, channel), now) > now:
                    report.append({**entry, "status": "backoff"})
                    continue
                if ctx is None:
                    ctx = resolver(email) or {}
                ws = ctx.get("workspace")
                if ctx.get("reason") or (ctx.get("role") != "super_admin" and not ws):
                    # Unknown / orphaned account: never send unscoped data.
                    report.append({**entry, "status": "no_context"})
                    continue
                if ws and ws.get("active") is False:
                    report.append({**entry, "status": "workspace_inactive"})
                    continue
                since = max(cursor, now - timedelta(days=MAX_LOOKBACK_DAYS)).isoformat()
                raw = db.get_changes_since(since, categories=set(cfg.get("categories") or []),
                                           db_path=db_path)
                changes = filter_changes(raw, cfg, ws)
                if not changes:
                    if not dry_run:
                        db.set_alert_cursor(email, channel, now_iso, db_path=db_path)
                    report.append({**entry, "status": "nothing_new"})
                    continue
                lang = cfg.get("lang") or "he"
                entry["changes"] = len(changes)
                if dry_run:
                    entry["preview"] = build_text_message(changes, freq, lang, config)
                    report.append({**entry, "status": "would_send"})
                    continue
                if channel == "email":
                    subject, text, html = build_email(changes, freq, lang, config)
                    ok = senders["email"](ch_cfg.get("address") or email, subject, text, html, config)
                else:
                    ok = senders["whatsapp"](ch_cfg.get("phone"),
                                             build_text_message(changes, freq, lang, config), config)
                if ok:
                    db.set_alert_cursor(email, channel, now_iso, delivered=True, db_path=db_path)
                    _FAIL_UNTIL.pop((email, channel), None)
                    report.append({**entry, "status": "sent"})
                else:
                    _FAIL_UNTIL[(email, channel)] = now + FAIL_BACKOFF
                    logger.warning("dashboard alert not delivered: %s via %s", email, channel)
                    report.append({**entry, "status": "failed"})
        except Exception as exc:              # one user's failure must not stop the rest
            logger.error("dashboard alert dispatch failed for %s: %s", email, exc, exc_info=True)
            report.append({"email": email, "status": "error"})
    return report
