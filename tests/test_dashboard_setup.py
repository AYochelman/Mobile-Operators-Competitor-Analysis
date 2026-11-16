"""Dashboard setup wizard: validation, filtering, scheduling and the dispatcher.
Offline - a temp SQLite file, a fake context resolver and fake senders."""
from datetime import datetime, timedelta

import pytest

import db
import dashboard_setup as ds


@pytest.fixture
def path(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    return p


def _log(path, table, carrier, plan, ctype, old, new, when, reseller=None):
    conn = db._connect(path)
    if table == "content_changes":
        conn.execute("INSERT INTO content_changes (service, carrier, change_type, old_val, new_val, changed_at) "
                     "VALUES (?,?,?,?,?,?)", (plan, carrier, ctype, old, new, when))
    elif table == "reseller_changes":
        conn.execute("INSERT INTO reseller_changes (reseller_id, carrier, plan_name, change_type, old_val, "
                     "new_val, changed_at) VALUES (?,?,?,?,?,?,?)", (reseller, carrier, plan, ctype, old, new, when))
    else:
        conn.execute(f"INSERT INTO {table} (carrier, plan_name, change_type, old_val, new_val, changed_at) "
                     "VALUES (?,?,?,?,?,?)", (carrier, plan, ctype, old, new, when))
    conn.commit()
    conn.close()


def _user(**over):
    cfg = ds.clean_user_config({
        "channels": {"email": {"enabled": True, "address": "a@b.co", "frequency": "immediate"},
                     "whatsapp": {"enabled": False}},
        "categories": ["domestic", "abroad", "global", "content", "resellers"],
        "events": list(ds.EVENTS), "min_price_delta": 1,
        "quiet": {"days": list(range(7)), "from": "00:00", "to": "23:59"},
    })
    cfg.update(over)
    return cfg


# ── validation ───────────────────────────────────────────────────────────────

def test_phone_normalization():
    assert ds.normalize_phone("054-123 4567") == "972541234567"
    assert ds.normalize_phone("+972 54 1234567") == "972541234567"
    assert ds.normalize_phone("") == ""
    with pytest.raises(ds.SetupError):
        ds.normalize_phone("12345")


def test_user_config_rejects_enabled_channel_without_target():
    with pytest.raises(ds.SetupError):
        ds.clean_user_config({"channels": {"whatsapp": {"enabled": True, "phone": ""}}})
    with pytest.raises(ds.SetupError):
        ds.clean_user_config({"channels": {"email": {"enabled": True, "address": "nope"}}})
    # the login e-mail is the default address
    cfg = ds.clean_user_config({"channels": {"email": {"enabled": True}}}, default_email="U@X.io")
    assert cfg["channels"]["email"]["address"] == "u@x.io"


def test_user_config_drops_unknown_values():
    cfg = ds.clean_user_config({"categories": ["domestic", "bogus"], "events": ["price_drop", "x"],
                                "min_price_delta": "9999", "quiet": {"days": [9, 1], "from": "25:00"},
                                "lang": "fr", "role": "hacker"})
    assert cfg["categories"] == ["domestic"] and cfg["events"] == ["price_drop"]
    assert cfg["min_price_delta"] == 500 and cfg["quiet"] == {"days": [1], "from": "08:00", "to": "20:00"}
    assert cfg["lang"] == "he" and cfg["role"] == "other"


def test_workspace_config_respects_operator_locks():
    cfg = ds.clean_workspace_config(
        {"sections": {"/plans": "focus", "/esim": "focus", "/news": "hidden", "/x": "hidden"},
         "landing": "/esim", "focus_carriers": ["partner", "Bad Id!", "partner"]},
        locked_flags={"hide_global": True})
    assert cfg["sections"] == {"/plans": "focus", "/news": "hidden"}   # /esim is locked, /x unknown
    assert cfg["landing"] == ""                                        # locked section cannot be the landing
    assert cfg["focus_carriers"] == ["partner"]
    assert ds.hidden_section_flags(cfg) == {"hide_news": True}


def test_workspace_config_must_keep_something_visible():
    with pytest.raises(ds.SetupError):
        ds.clean_workspace_config({"sections": {p: "hidden" for p in ds.SECTION_FLAGS}})


# ── scheduling ───────────────────────────────────────────────────────────────

def test_quiet_hours_and_days():
    quiet = {"days": [0, 1, 2, 3, 4], "from": "08:00", "to": "20:00"}
    assert ds.is_allowed_now(quiet, datetime(2026, 11, 15, 9, 0))        # Sunday morning
    assert not ds.is_allowed_now(quiet, datetime(2026, 11, 15, 21, 0))   # Sunday night
    assert not ds.is_allowed_now(quiet, datetime(2026, 11, 14, 12, 0))   # Saturday


def test_due_rules():
    sun = datetime(2026, 11, 15, 9, 0)
    assert ds.is_due("immediate", sun, sun)
    assert ds.is_due("daily", sun - timedelta(days=1), sun)
    assert not ds.is_due("daily", sun.replace(hour=7), sun)              # already handled today
    assert not ds.is_due("daily", sun - timedelta(days=1), sun.replace(hour=8, minute=0))
    assert ds.is_due("weekly", datetime(2026, 11, 13, 9, 0), sun)        # last week (Friday)
    assert not ds.is_due("weekly", sun, datetime(2026, 11, 18, 9, 0))    # same week (Wednesday)


# ── filtering ────────────────────────────────────────────────────────────────

def _ch(cat, carrier, plan, ctype, old, new, at="2026-11-15T07:40:00"):
    return {"category": cat, "carrier": carrier, "plan_name": plan, "change_type": ctype,
            "old_val": old, "new_val": new, "changed_at": at}


def test_filter_scopes_by_workspace_and_user_choices():
    changes = [
        _ch("domestic", "partner", "A", "price_change", "59.9", "49.9"),
        _ch("domestic", "cellcom", "B", "price_change", "50", "50.5"),      # below the 1-shekel floor
        _ch("domestic", "pelephone", "C", "new_plan", None, "39.9"),        # the workspace's own carrier
        _ch("domestic", "golan", "D", "removed_plan", "30", None),          # outside the allowlist
        _ch("abroad", "partner", "E", "extras_change", "[1]", "[2]"),       # /roaming hidden by the admin
        _ch("global", "airalo", "F", "price_change", "10", "7"),            # /esim locked by the operator
    ]
    ws = {"mvno_carrier": "pelephone", "hide_self_carrier": True,
          "visible_carriers": ["partner", "cellcom", "pelephone"],
          "feature_flags": {"hide_global": True},
          "dashboard_config": {"sections": {"/roaming": "hidden"}, "focus_carriers": ["partner"]}}
    out = ds.filter_changes(changes, _user(), ws)
    assert [(c["carrier"], c["event"]) for c in out] == [("partner", "price_drop")]
    assert out[0]["focus"] is True and out[0]["delta"] == pytest.approx(-10.0)


def test_filter_focus_scope_and_event_choice():
    changes = [_ch("domestic", "partner", "A", "price_change", "50", "60"),
               _ch("domestic", "cellcom", "B", "price_change", "50", "40")]
    ws = {"dashboard_config": {"focus_carriers": ["cellcom"]}}
    assert [c["carrier"] for c in ds.filter_changes(changes, _user(carrier_scope="focus"), ws)] == ["cellcom"]
    only_rises = ds.filter_changes(changes, _user(events=["price_rise"]), ws)
    assert [c["carrier"] for c in only_rises] == ["partner"]
    # focus carriers lead the list even when their move is smaller
    both = ds.filter_changes(changes + [_ch("domestic", "golan", "C", "price_change", "100", "10")], _user(), ws)
    assert both[0]["carrier"] == "cellcom"


def test_net_changes_collapse_round_trips_and_flaps():
    changes = [
        _ch("domestic", "partner", "A", "price_change", "50", "40", "2026-11-10T07:40:00"),
        _ch("domestic", "partner", "A", "price_change", "40", "50", "2026-11-11T07:40:00"),   # back to start
        _ch("domestic", "cellcom", "B", "price_change", "50", "45", "2026-11-10T07:40:00"),
        _ch("domestic", "cellcom", "B", "price_change", "45", "30", "2026-11-12T07:40:00"),
        _ch("domestic", "golan", "X", "new_plan", None, "20", "2026-11-10T07:40:00"),
        _ch("domestic", "golan", "X", "removed_plan", "20", None, "2026-11-11T07:40:00"),     # flap
    ]
    out = ds.filter_changes(changes, _user(), None)
    assert len(out) == 1 and (out[0]["old_val"], out[0]["new_val"]) == ("50", "30")


def test_messages_render_in_both_languages():
    cfg = {"public_site_url": "https://example.test"}
    changes = ds.filter_changes([
        _ch("domestic", "partner", "100GB", "price_change", "59.9", "49.9"),
        _ch("global", "airalo", "USA 5GB", "price_change", "10", "7"),
        _ch("content", "cellcom", "סייבר", "price_change", "לא קיים", "₪19.90"),
    ], _user(), None)
    he = ds.build_text_message(changes, "daily", "he", cfg)
    assert "סיכום יומי" in he and "₪59.9 → ₪49.9 (-17%)" in he and "10 → 7 (-30%)" in he
    assert "https://example.test/setup" in he
    subject, text, html = ds.build_email(changes, "weekly", "en", cfg)
    assert subject == "MOCA · 3 competitor changes" and 'dir="ltr"' in html and "Weekly summary" in html
    assert "*" not in text


# ── dispatcher ───────────────────────────────────────────────────────────────

class _Senders(dict):
    def __init__(self, ok=True):
        self.sent = []
        super().__init__(
            email=lambda to, subject, text, html, config: (self.sent.append(("email", to, subject)), ok)[1],
            whatsapp=lambda phone, text, config: (self.sent.append(("whatsapp", phone, text)), ok)[1])


def _ctx(email):
    return {"role": "admin", "workspace": {"active": True, "feature_flags": {}, "dashboard_config": {}}}


def test_dispatch_initializes_then_sends_only_new_changes(path):
    ds._FAIL_UNTIL.clear()
    db.save_dashboard_setup("user", "u@x.io", _user(), db_path=path)
    t0 = datetime(2026, 11, 15, 9, 0)
    _log(path, "changes", "partner", "old", "price_change", "50", "40", "2026-11-15T07:40:00")
    s = _Senders()
    r = ds.run_dispatch({}, _ctx, now=t0, db_path=path, senders=s)
    assert r[0]["status"] == "initialized" and not s.sent        # nothing from before the signup

    _log(path, "changes", "partner", "new", "price_change", "50", "40", "2026-11-15T17:05:00")
    r = ds.run_dispatch({}, _ctx, now=datetime(2026, 11, 15, 17, 15), db_path=path, senders=s)
    assert r[0]["status"] == "sent" and r[0]["changes"] == 1
    assert s.sent == [("email", "a@b.co", "MOCA · שינוי אחד אצל המתחרים")]

    r = ds.run_dispatch({}, _ctx, now=datetime(2026, 11, 15, 17, 30), db_path=path, senders=s)
    assert r[0]["status"] == "nothing_new" and len(s.sent) == 1  # never twice


def test_dispatch_holds_through_quiet_hours_without_losing_changes(path):
    ds._FAIL_UNTIL.clear()
    cfg = _user(quiet={"days": [0, 1, 2, 3, 4], "from": "08:00", "to": "18:00"})
    db.save_dashboard_setup("user", "u@x.io", cfg, db_path=path)
    db.set_alert_cursor("u@x.io", "email", "2026-11-12T12:00:00", db_path=path)   # Thursday noon
    _log(path, "changes", "partner", "P", "new_plan", None, "30", "2026-11-13T17:05:00")  # Friday
    s = _Senders()
    r = ds.run_dispatch({}, _ctx, now=datetime(2026, 11, 13, 17, 15), db_path=path, senders=s)
    assert r[0]["status"] == "quiet_hours" and not s.sent
    r = ds.run_dispatch({}, _ctx, now=datetime(2026, 11, 15, 8, 5), db_path=path, senders=s)  # Sunday
    assert r[0]["status"] == "sent" and len(s.sent) == 1


def test_dispatch_never_sends_without_a_resolved_workspace(path):
    ds._FAIL_UNTIL.clear()
    db.save_dashboard_setup("user", "u@x.io", _user(), db_path=path)
    db.set_alert_cursor("u@x.io", "email", "2026-11-15T07:00:00", db_path=path)
    _log(path, "changes", "partner", "P", "new_plan", None, "30", "2026-11-15T07:40:00")
    s = _Senders()
    now = datetime(2026, 11, 15, 9, 0)
    for ctx in ({"role": "viewer", "workspace": None, "reason": "db_error"},
                {"role": "viewer", "workspace": None},
                {"role": "admin", "workspace": {"active": False}}):
        r = ds.run_dispatch({}, lambda e, c=ctx: c, now=now, db_path=path, senders=s)
        assert r[0]["status"] in ("no_context", "workspace_inactive")
    assert not s.sent
    # the cursor did not move, so the change is still delivered once the context is back
    assert ds.run_dispatch({}, _ctx, now=now, db_path=path, senders=s)[0]["status"] == "sent"


def test_dispatch_failure_backs_off_and_dry_run_moves_nothing(path):
    ds._FAIL_UNTIL.clear()
    db.save_dashboard_setup("user", "u@x.io", _user(), db_path=path)
    db.set_alert_cursor("u@x.io", "email", "2026-11-15T07:00:00", db_path=path)
    _log(path, "changes", "partner", "P", "new_plan", None, "30", "2026-11-15T07:40:00")
    now = datetime(2026, 11, 15, 9, 0)
    dry = ds.run_dispatch({}, _ctx, now=now, db_path=path, dry_run=True)
    assert dry[0]["status"] == "would_send" and "preview" in dry[0]
    bad = _Senders(ok=False)
    assert ds.run_dispatch({}, _ctx, now=now, db_path=path, senders=bad)[0]["status"] == "failed"
    assert ds.run_dispatch({}, _ctx, now=now + timedelta(minutes=15), db_path=path,
                           senders=bad)[0]["status"] == "backoff"
    good = _Senders()
    later = now + ds.FAIL_BACKOFF + timedelta(minutes=1)
    assert ds.run_dispatch({}, _ctx, now=later, db_path=path, senders=good)[0]["status"] == "sent"
    ds._FAIL_UNTIL.clear()


# ── API ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(path, monkeypatch):
    import app as core
    core.app.config["TEST_DB_PATH"] = path
    state = {"email": "admin@x.io", "role": "admin"}
    monkeypatch.setattr(core, "_current_user_email", lambda: state["email"])
    monkeypatch.setattr(core, "_get_user_context", lambda email: {
        "role": state["role"], "workspace_id": "ws-1",
        "workspace": {"id": "ws-1", "name": "X", "mvno_carrier": "pelephone", "hide_self_carrier": True,
                      "visible_carriers": [], "feature_flags": {"hide_usa": True}, "active": True}})
    monkeypatch.setattr(core, "log_audit", lambda *a, **k: None)
    headers = {"X-API-Key": core._get_api_key()}
    c = core.app.test_client()
    yield c, state, headers
    core.app.config.pop("TEST_DB_PATH", None)


def test_api_roundtrip_and_permissions(client, path):
    c, state, h = client
    first = c.get("/api/dashboard-setup", headers=h).get_json()
    assert first["can_edit_workspace"] and first["user"]["completed_at"] is None
    assert first["workspace"]["locked_flags"] == {"hide_usa": True}

    r = c.put("/api/dashboard-setup/workspace", headers=h,
              json={"sections": {"/plans": "focus", "/usa": "focus", "/news": "hidden"}, "landing": "/plans"})
    assert r.status_code == 200 and r.get_json()["config"]["sections"] == {"/plans": "focus", "/news": "hidden"}

    r = c.put("/api/dashboard-setup/user", headers=h,
              json={"channels": {"whatsapp": {"enabled": True, "phone": "0541234567", "frequency": "weekly"}},
                    "categories": ["domestic"], "events": ["price_drop"]})
    assert r.status_code == 200
    assert r.get_json()["config"]["channels"]["whatsapp"]["phone"] == "972541234567"
    assert "whatsapp" in db.get_alert_cursors("admin@x.io", db_path=path)     # starts counting from now

    again = c.get("/api/dashboard-setup", headers=h).get_json()
    assert again["user"]["completed_at"] and again["workspace"]["config"]["landing"] == "/plans"

    assert c.put("/api/dashboard-setup/user", headers=h,
                 json={"channels": {"email": {"enabled": True, "address": "bad"}}}).status_code == 400

    state["role"], state["email"] = "viewer", "viewer@x.io"
    assert c.put("/api/dashboard-setup/workspace", headers=h, json={"sections": {}}).status_code == 403
    assert c.post("/api/dashboard-setup/dismiss", headers=h).status_code == 200
    assert c.get("/api/dashboard-setup", headers=h).get_json()["user"]["dismissed_at"]


def test_api_test_message_validates_target(client, monkeypatch):
    c, _state, h = client
    sent = []
    monkeypatch.setattr(ds, "send_test", lambda ch, target, lang, cfg: (sent.append((ch, target)), True)[1])
    assert c.post("/api/dashboard-setup/test", headers=h, json={"channel": "whatsapp", "phone": "12"}).status_code == 400
    assert c.post("/api/dashboard-setup/test", headers=h, json={"channel": "sms"}).status_code == 400
    assert c.post("/api/dashboard-setup/test", headers=h,
                  json={"channel": "whatsapp", "phone": "054-1234567"}).status_code == 200
    assert sent == [("whatsapp", "972541234567")]
