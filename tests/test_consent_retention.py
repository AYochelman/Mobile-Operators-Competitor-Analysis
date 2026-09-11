"""Privacy / anti-spam compliance guards (2026-09-11):
- public signups store documented consent and refuse without it
- marketing labelling helpers
- personal-data retention pruning
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app import app as flask_app
from db import init_db, _connect
import maintenance as m
import notifier


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    flask_app.config["TEST_DB_PATH"] = db
    flask_app.config["TESTING"] = True
    init_db(db_path=db)
    # never hit Telegram/email from the lead handler
    import api.hotels as hotels_mod
    monkeypatch.setattr(hotels_mod, "_notify_hotel_lead", lambda lead: None)
    with flask_app.test_client() as c:
        yield c, db


def test_hotel_lead_requires_consent(client):
    c, db = client
    body = {"hotel_name": "H", "contact_name": "A", "email": "a@b.co", "rooms": 10}
    r = c.post("/api/hotels/lead", json=body)
    assert r.status_code == 400 and "consent" in r.get_json()["error"]
    r = c.post("/api/hotels/lead", json={**body, "consent": True, "consent_version": "2026-09-11"})
    assert r.status_code == 200
    conn = _connect(db)
    row = conn.execute("SELECT email, consent_at, consent_version FROM hotel_leads").fetchone()
    conn.close()
    assert row[0] == "a@b.co" and row[1] and row[2] == "2026-09-11"


def test_mobile_reminder_requires_consent(client):
    c, _ = client
    body = {"email": "a@b.co", "kinds": ["better_deal"], "carrier": "partner", "plan_name": "X"}
    r = c.post("/api/mobile/reminders", json=body)
    assert r.status_code == 400 and r.get_json()["error"] == "consent required"


def test_promo_subject_and_sender_identity():
    assert notifier._promo_subject("MOCA: x", "he").startswith("פרסומת: ")
    assert notifier._promo_subject("MOCA: x", "en").startswith("Advertisement (פרסומת): ")
    # idempotent
    s = notifier._promo_subject("MOCA: x", "he")
    assert notifier._promo_subject(s, "he") == s
    ident = notifier._sender_identity("he", {"business_name": "Foo Ltd", "business_id": "515", "business_address": "Tel Aviv"})
    assert ident.startswith("Foo Ltd") and "515" in ident and "Tel Aviv" in ident and "Helpdesk@mocaintel.com" in ident
    assert notifier._sender_identity("en", {}).startswith("MOCA")


def test_prune_personal_data(tmp_path):
    db = str(tmp_path / "p.db")
    init_db(db_path=db)
    conn = _connect(db)
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    new = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    conn.execute("INSERT INTO esim_events (sid, event_type, created_at) VALUES ('s','page_view',?)", (old,))
    conn.execute("INSERT INTO esim_events (sid, event_type, created_at) VALUES ('s','page_view',?)", (new,))
    conn.execute("INSERT INTO hotel_leads (hotel_name, email, source, created_at) VALUES ('h','a@b','/hotels',?)", (old,))
    conn.execute("INSERT INTO mobile_reminders (token, kind, carrier, plan_name, created_at, done) VALUES ('t','plan_end','partner','P',?,1)", (old,))
    conn.execute("INSERT INTO mobile_reminders (token, kind, carrier, plan_name, created_at, done) VALUES ('t2','better_deal','partner','P',?,0)", (old,))
    conn.commit(); conn.close()
    rep = m.prune_personal_data({}, db_path=db, dry_run=True)
    assert rep["esim_events"] == 1 and rep["hotel_leads"] == 0 and rep["mobile_reminders"] == 1
    m.prune_personal_data({"leads_retention_days": 30}, db_path=db)
    conn = _connect(db)
    assert conn.execute("SELECT COUNT(*) FROM esim_events").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM hotel_leads").fetchone()[0] == 0
    # active (done=0) reminders are never touched by retention
    assert conn.execute("SELECT COUNT(*) FROM mobile_reminders").fetchone()[0] == 1
    conn.close()
