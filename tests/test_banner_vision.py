"""banner_vision.py: the guards that decide when a paid reading happens, and the
campaign-timeline bookkeeping. No API call is made in these tests."""
from datetime import datetime, timedelta

import pytest

import banner_vision as bv

PIL = pytest.importorskip("PIL")


def _png(path, color):
    from PIL import Image
    im = Image.new("RGB", (64, 36), color)
    # A hard edge, so the average-hash is not uniform.
    for x in range(32):
        for y in range(36):
            im.putpixel((x, y), (0, 0, 0))
    im.save(path)


def _png_other(path):
    from PIL import Image
    im = Image.new("RGB", (64, 36), (255, 255, 255))
    for x in range(64):
        for y in range(18):
            im.putpixel((x, y), (0, 0, 0))
    im.save(path)


def _reading(**kw):
    base = {"has_offer": True, "headline": "חבילת 5G במבצע", "offer": "500GB", "price_text": "₪39.90 לחודש",
            "campaign_type": "price_plan", "products": [], "fine_print": "", "cta": "", "confidence": "high",
            "obstruction": ""}
    base.update(kw)
    return base


SRC = {"key": "cellcom", "carrier": "cellcom", "kind": "home", "name": "Cellcom", "file": "cellcom.png"}


def test_parse_price():
    assert bv.parse_price("₪39.90 לחודש") == 39.9
    assert bv.parse_price("29,90") == 29.9
    assert bv.parse_price("") is None and bv.parse_price(None) is None


def test_same_campaign_tolerates_rewording_but_not_a_price_move():
    a = _reading()
    assert bv.is_same_campaign(a, _reading(headline="חבילת 5G במבצע!"))
    assert not bv.is_same_campaign(a, _reading(price_text="₪34.90 לחודש"))
    assert not bv.is_same_campaign(a, _reading(headline="אייפון 17 חדש בחנות"))
    assert not bv.is_same_campaign(a, _reading(has_offer=False))
    assert not bv.is_same_campaign(None, a)


def test_should_analyze_guards(tmp_path):
    p = tmp_path / "cellcom.png"
    assert bv.should_analyze(str(p), None)[0] is False          # no file
    _png(str(p), (255, 255, 255))
    go, reason, h = bv.should_analyze(str(p), None)
    assert go and reason == "first reading" and len(h) == 256
    now = datetime(2026, 11, 24, 8, 0)
    recent = {"analyzed_at": (now - timedelta(hours=3)).isoformat(), "image_hash": "0" * 256}
    assert bv.should_analyze(str(p), recent, now=now)[0] is False     # read 3h ago
    old_same = {"analyzed_at": (now - timedelta(hours=30)).isoformat(), "image_hash": h}
    assert bv.should_analyze(str(p), old_same, now=now)[1] == "image unchanged"
    _png_other(str(p))
    assert bv.should_analyze(str(p), old_same, now=now) [0] is True   # image changed


def test_timeline_first_same_changed_and_unreadable(tmp_path):
    dbp = str(tmp_path / "t.db")
    bv.ensure_table(dbp)
    t0 = datetime(2026, 11, 1, 8, 0)
    assert bv.store_reading(SRC, _reading(), "h1", "m", None, now=t0, db_path=dbp) == "first"
    prev = bv.latest_rows(dbp)["cellcom"]
    assert prev["price"] == 39.9 and prev["prev_headline"] is None

    t1 = t0 + timedelta(days=1)
    assert bv.store_reading(SRC, _reading(headline="חבילת 5G במבצע!"), "h2", "m", prev, now=t1, db_path=dbp) == "same"
    row = bv.latest_rows(dbp)["cellcom"]
    assert row["id"] == prev["id"] and row["last_seen_at"] == t1.isoformat()

    t2 = t0 + timedelta(days=2)
    low = _reading(headline="", offer="", price_text="", confidence="low", obstruction="cookie banner")
    assert bv.store_reading(SRC, low, "h3", "m", row, now=t2, db_path=dbp) == "unreadable"
    assert bv.latest_rows(dbp)["cellcom"]["last_seen_at"] == t1.isoformat()   # timeline untouched

    t3 = t0 + timedelta(days=3)
    new = _reading(headline="אייפון 17 חדש בחנות", price_text="₪3,999", campaign_type="device")
    assert bv.store_reading(SRC, new, "h4", "m", bv.latest_rows(dbp)["cellcom"], now=t3, db_path=dbp) == "changed"
    cur = bv.latest_rows(dbp)["cellcom"]
    assert cur["campaign_type"] == "device" and cur["prev_price_text"] == "₪39.90 לחודש"

    # The carousel comes back to the first slide: stored, but not a switch.
    t4 = t0 + timedelta(days=4)
    assert bv.store_reading(SRC, _reading(), "h5", "m", cur, now=t4, db_path=dbp) == "rotation"
    assert bv.latest_rows(dbp)["cellcom"]["prev_headline"] is None
    assert len(bv.recent_changes(3650, dbp)) == 1
    # ...while the same slide a month later is a campaign that returned.
    t5 = t0 + timedelta(days=40)
    back = _reading(headline="אייפון 17 חדש בחנות", price_text="₪3,999")
    assert bv.store_reading(SRC, back, "h6", "m", bv.latest_rows(dbp)["cellcom"], now=t5, db_path=dbp) == "changed"


def test_run_dry_run_makes_no_call_and_respects_the_cap(tmp_path, monkeypatch):
    dbp = str(tmp_path / "t.db")
    srcs = []
    for i in range(3):
        f = "c%d.png" % i
        _png(str(tmp_path / f), (255, 255, 255))
        srcs.append({"key": "c%d" % i, "carrier": "c%d" % i, "kind": "home", "name": "C%d" % i, "file": f})
    monkeypatch.setattr(bv, "read_banner", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    out = bv.run({}, str(tmp_path), srcs, db_path=dbp, dry_run=True, limit=2)
    assert out["analyzed"] == 2 and out["skipped"] == 1 and not bv.latest_rows(dbp)
    assert bv.run({"banner_vision_enabled": False}, str(tmp_path), srcs, db_path=dbp, dry_run=True).get("disabled")


def test_run_stores_readings_and_reports_only_real_switches(tmp_path, monkeypatch):
    dbp = str(tmp_path / "t.db")
    _png(str(tmp_path / "cellcom.png"), (255, 255, 255))
    answers = iter([_reading(), _reading(headline="אייפון 17 חדש בחנות", price_text="₪3,999")])
    calls = []
    monkeypatch.setattr(bv, "read_banner", lambda *a, **k: (calls.append(1), next(answers))[1])
    cfg = {"anthropic_api_key": "k"}
    first = bv.run(cfg, str(tmp_path), [SRC], db_path=dbp)
    assert first["analyzed"] == 1 and first["changed"] == []         # a first reading is not a switch
    assert bv.run(cfg, str(tmp_path), [SRC], db_path=dbp)["analyzed"] == 0   # read minutes ago
    second = bv.run(cfg, str(tmp_path), [SRC], db_path=dbp, force=True)
    assert len(calls) == 2 and second["changed"][0]["prev_price_text"] == "₪39.90 לחודש"
    assert "Cellcom" in bv.changes_message(second["changed"])
    assert len(bv.recent_changes(30, dbp)) == 1
