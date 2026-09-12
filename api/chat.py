"""/api/chat - Claude-powered assistant over the live plan data (rate-limited per user).

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
logger = core.logger
from flask import Blueprint
bp = Blueprint("chat", __name__)


@bp.route("/api/chat", methods=["POST"])
@core.require_auth
@core.limiter.limit("10 per minute")
@core.limiter.limit(core._chat_daily_limit, key_func=core._chat_user_key)
def api_chat():
    """AI chat over the plans data using Claude API."""
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "no question"}), 400

    # Workspace self-carrier scoping: strip the user's own MVNO from the
    # grounding data AND instruct the model to not mention it. The user is
    # here to learn about competitors, not about themselves.
    hidden_carrier = core._hidden_carrier_for_request()

    config = core.load_config()
    api_key = config.get("anthropic_api_key", "")
    if not api_key:
        return jsonify({"error": "anthropic_api_key missing in config.json"}), 500

    try:
        import requests as _req
        from datetime import datetime

        # ── Build context from DB ──────────────────────────────────────────
        def fmt_price(p):
            if p is None: return "—"
            try: return f"₪{float(p):.2f}".rstrip('0').rstrip('.')
            except (TypeError, ValueError): return f"₪{p}"

        def fmt_gb(g):
            if g is None: return "ללא הגבלה"
            try: g = float(g)
            except (TypeError, ValueError): return str(g)
            return f"{round(g*1024)}MB" if g < 1 else f"{g}GB"

        # Carrier ID → display name (used in context so AI resolves aliases correctly)
        # MUST stay in sync with mass-market-app/src/data/carrierLabels.js
        _CARRIER_NAMES = {
            # Domestic
            'partner': 'פרטנר', 'pelephone': 'פלאפון', 'hotmobile': 'הוט מובייל',
            'cellcom': 'סלקום', 'mobile019': '019', 'xphone': 'XPhone',
            'wecom': 'We-Com', 'neptucom': 'Neptucom', 'golan': 'גולן טלקום',
            'rami_levy': 'רמי לוי תקשורת',
            # Global eSIM
            'tuki': 'Tuki', 'terminalesim': 'Terminal eSIM', 'gigsky': 'GigSky',
            'esimgenius': 'eSIM Genius', 'nisim': 'Nisim eSIM', 'esimax': 'eSIM Max',
            'venterrasim': 'VenterraSIM', 'simzol': 'Simzol',
            'airalo': 'Airalo', 'airalo_local': 'Airalo', 'airalo_regional': 'Airalo',
            'pelephone_global': 'GlobalSIM', 'esimo': 'eSIMo', 'simtlv': 'SimTLV',
            'world8': '8 World', 'xphone_global': 'XPhone Global', 'saily': 'Saily',
            'holafly': 'Holafly', 'esimio': 'eSIM.io', 'sparks': 'Sparks',
            'voye': 'VOYE', 'orbit': 'Orbit', 'travelsim': 'Travel Sim',
            'gomoworld': 'GoMoWorld', 'tasim': 'Tasim', 'maya': 'Maya Mobile',
            'bcengi': 'Bcengi', 'esim70': 'eSIM70', 'jetpack': 'Jetpack', 'breez': 'Breeze',
            'bytesim': 'ByteSim', 'besim': 'Besim', 'seven_g': '7G',
            'bestconnect': 'Best Connect', 'esimplus': 'eSIM Plus', 'bnesim': 'BNESIM',
            'yesim': 'Yesim', 'nomad': 'Nomad', 'ubigi': 'Ubigi', 'alosim': 'aloSIM',
            # USA tourist-plan operators (נוחתים בארה"ב) — mirror of USA_LABELS
            # in carrierLabels.js
            'tmobile_prepaid': 'T-Mobile Prepaid', 'att_prepaid': 'AT&T Prepaid',
            'verizon_prepaid': 'Verizon Prepaid', 'mint': 'Mint Mobile',
            'ultra': 'Ultra Mobile', 'lyca_usa': 'Lycamobile USA', 'tello': 'Tello',
            'metro': 'Metro by T-Mobile', 'simple_mobile': 'Simple Mobile',
            'cricket': 'Cricket Wireless', 'h2o': 'H2O Wireless',
            'visible': 'Visible', 'us_mobile': 'US Mobile',
            'red_pocket': 'Red Pocket', 'straight_talk': 'Straight Talk',
            'total_wireless': 'Total Wireless', 'boost': 'Boost Mobile',
        }
        def _cn(carrier):
            return _CARRIER_NAMES.get(carrier, carrier)

        lines = [
            "אתה עוזר נתונים עבור מערכת השוואת חבילות סלולר ישראלית.",
            "להלן הנתונים הנוכחיים מהמסד נתונים. ענה בעברית, בצורה תמציתית וברורה.",
            f"תאריך עדכון: {datetime.now().strftime('%d/%m/%Y')}",
            "שמות ספקים (מזהה=שם מוצג): airalo/airalo_local/airalo_regional=Airalo, "
            "pelephone_global=GlobalSIM, xphone_global=XPhone Global, mobile019=019, "
            "rami_levy=רמי לוי תקשורת, gomoworld=GoMoWorld=Gomo, world8=8 World, simtlv=SimTLV, "
            "esimio=eSIM.io, maya=Maya Mobile, travelsim=Travel Sim, neptucom=Neptucom.",
        ]
        if hidden_carrier:
            lines.append(
                f"חשוב: המשתמש הוא נציג של {_CARRIER_NAMES.get(hidden_carrier, hidden_carrier)}. "
                f"אל תתייחס לחבילות או לנתונים של {_CARRIER_NAMES.get(hidden_carrier, hidden_carrier)} "
                f"בתשובותיך — התמקד רק במתחרים שלהם."
            )
        lines.append("")

        # Domestic plans — reuse the shared 5-min plan cache (same key the list
        # endpoints use) instead of a full uncached DB read on every chat message.
        domestic = core._filter_hidden_carrier(core._cached_plans('plans', lambda: core.get_plans(db_path=core._db_path())))
        if domestic:
            lines.append("## חבילות ביתיות (ישראל)")
            for p in domestic:
                lines.append(
                    f"  {_cn(p['carrier'])} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{fmt_gb(p.get('data_gb'))} | {p.get('minutes','')} דקות"
                    + (f" | extras: {';'.join(p['extras'])}" if p.get('extras') else "")
                )

        # Abroad plans
        abroad = core._filter_hidden_carrier(core._cached_plans('abroad_plans', lambda: core.get_abroad_plans(db_path=core._db_path())))
        if abroad:
            lines.append("")
            lines.append("## חבילות חו\"ל")
            for p in abroad:
                lines.append(
                    f"  {_cn(p['carrier'])} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{p.get('days','')} ימים | {fmt_gb(p.get('data_gb'))}"
                    + (f" | extras: {';'.join(p['extras'])}" if p.get('extras') else "")
                )

        # Global plans — 1 cheapest plan per carrier+destination, up to 40 dest per carrier
        from collections import defaultdict as _dd
        _all_global = core._filter_hidden_carrier(core._cached_plans('global_plans', lambda: core.get_global_plans(db_path=core._db_path())))
        _by_carrier_dest = _dd(lambda: _dd(list))
        for _p in _all_global:
            _dest = (_p.get('extras') or [''])[0] or 'global'
            _by_carrier_dest[_p['carrier']][_dest].append(_p)
        global_plans = []
        for _carrier in sorted(_by_carrier_dest):
            _dest_cheapest = []
            for _dest, _dplans in _by_carrier_dest[_carrier].items():
                _cheapest = min(_dplans, key=lambda x: float(x.get('price') or 9999))
                _dest_cheapest.append(_cheapest)
            _dest_cheapest.sort(key=lambda x: float(x.get('price') or 9999))
            global_plans.extend(_dest_cheapest[:40])
        if global_plans:
            lines.append("")
            lines.append("## חבילות גלובליות (eSIM)")
            for p in global_plans:
                lines.append(
                    f"  {_cn(p['carrier'])} | {p['plan_name']} | {fmt_price(p.get('price'))} | "
                    f"{p.get('days','')} ימים | {fmt_gb(p.get('data_gb'))}"
                    + (f" | יעד: {p['extras'][0]}" if p.get('extras') else "")
                )

        # Content services
        content = core._filter_hidden_carrier(core.get_content_plans(db_path=core._db_path()))
        if content:
            lines.append("")
            lines.append("## שירותי תוכן")
            for p in content:
                lines.append(
                    f"  {p['service']} | {_cn(p['carrier'])} | {p.get('price','')} | "
                    f"ניסיון: {p.get('free_trial','')}"
                )

        # Recent changes (last 90 days)
        all_changes = []
        for ch in core._filter_hidden_carrier(core.get_changes(limit=200, db_path=core._db_path())):
            all_changes.append(("ביתי", ch))
        for ch in core._filter_hidden_carrier(core.get_abroad_changes(limit=200, db_path=core._db_path())):
            all_changes.append(("חו\"ל", ch))
        for ch in core._filter_hidden_carrier(core.get_global_changes(limit=200, db_path=core._db_path())):
            all_changes.append(("גלובלי", ch))
        for ch in core._filter_hidden_carrier(core.get_content_changes(limit=200, db_path=core._db_path())):
            all_changes.append(("תוכן", ch))

        if all_changes:
            lines.append("")
            lines.append("## היסטוריית שינויים (עד 200 אחרונים לכל קטגוריה)")
            for tab, ch in all_changes:
                carrier = ch.get("carrier", ch.get("service", ""))
                lines.append(
                    f"  [{tab}] {ch.get('changed_at','')[:10]} | {carrier} | "
                    f"{ch.get('plan_name', ch.get('service',''))} | "
                    f"{ch.get('change_type','')} | {ch.get('old_val','')} → {ch.get('new_val','')}"
                )

        context = "\n".join(lines)

        # ── Call Anthropic API ─────────────────────────────────────────────
        # Sonnet has dramatically better Hebrew than Haiku; the latency/cost
        # premium is justified for business-facing reports. Caller can request
        # 'haiku' explicitly for fast/cheap quick-fire chat.
        ALLOWED_MODELS = {
            'sonnet': 'claude-sonnet-4-6',
            'haiku':  'claude-haiku-4-5-20251001',
        }
        requested = (data.get('model') or '').strip().lower()
        model = ALLOWED_MODELS.get(requested, 'claude-sonnet-4-6')

        # Hebrew-quality system prompt: prepend strict language rules to the context
        hebrew_rules = (
            "כללי כתיבה (חובה לעקוב אחריהם):\n"
            "1. כתוב אך ורק בעברית תקנית. אל תמציא מילים שאינן קיימות במילון העברי.\n"
            "2. אל תתרגם ישירות מאנגלית — נסח מחדש בעברית טבעית. במקרה של ספק, השאר את המונח באנגלית במקום לתרגם בצורה שגויה.\n"
            "3. השתמש במילים מלאות, ללא קיצורים שגויים או הברות חסרות (למשל: 'שיחות' ולא 'שיח'; 'צרכנים' ולא 'צרים'; 'בכורה' ולא 'בחור').\n"
            "4. פעמיים בדוק כל משפט שכתבת — אם משפט נשמע מוזר, נסח אותו מחדש.\n"
            "5. השתמש במונחי הענף הסלולרי הנכונים: 'חבילת גלישה', 'דקות שיחה', 'הודעות SMS', 'גלישה בחו\"ל', 'תנאי הצטרפות'.\n"
            "6. אם אין לך מידע ודאי על משהו — אל תמציא, ציין במפורש שהמידע לא זמין.\n\n"
        )
        full_system = hebrew_rules + context

        resp = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "system": [
                    {
                        "type": "text",
                        "text": full_system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [{"role": "user", "content": question}],
            },
            timeout=45,
        )
        resp.raise_for_status()
        body = resp.json()
        usage = body.get("usage", {}) or {}
        logger.info(
            "chat ok: model=%s in=%s cache_read=%s cache_write=%s out=%s",
            model,
            usage.get("input_tokens"),
            usage.get("cache_read_input_tokens"),
            usage.get("cache_creation_input_tokens"),
            usage.get("output_tokens"),
        )
        core._record_claude_call("chat", model, body, user_email=core._caller_email())
        answer = body["content"][0]["text"]
        core._track_user_action(core._current_user_email(), 'chat_used', {"model": model})
        return jsonify({"answer": answer, "model": model})

    except Exception as e:
        logger.error(f"chat failed: {e}", exc_info=True)
        logger.error(f"API error: {e}", exc_info=True); return jsonify({"error": "Internal server error"}), 500
