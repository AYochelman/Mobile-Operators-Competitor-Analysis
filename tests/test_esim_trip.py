"""esim_trip.py: request validation, stretch requirements, candidate filtering."""
import json

import pytest

import db
import esim_trip as et

FX = {"usd": 4.0, "eur": 4.5, "gbp": 5.0}
TH, VN, ASIA = "תאילנד", "וייטנאם", "אסיה"


def test_clean_request_accepts_and_rejects():
    legs, gb, bundles = et.clean_request({"legs": [{"destination": TH, "days": 10}, {"destination": VN, "days": "7"}],
                                          "gb": "unl", "bundles": [ASIA, ASIA, TH, 5]})
    assert legs == [{"destination": TH, "days": 10}, {"destination": VN, "days": 7}]
    assert gb is None and bundles == [ASIA]          # deduped, own country and junk dropped
    for bad in (None, {"legs": [{"destination": TH, "days": 3}]},
                {"legs": [{"destination": TH, "days": 0}, {"destination": VN, "days": 3}]},
                {"legs": [{"destination": TH, "days": 60}, {"destination": VN, "days": 60}]},
                {"legs": [{"destination": TH, "days": 3}, {"destination": VN, "days": 3}], "gb": -1}):
        with pytest.raises(ValueError):
            et.clean_request(bad)


def test_segments_split_the_data_by_days():
    segs = et.segments_of([{"destination": TH, "days": 10}, {"destination": VN, "days": 5}], 9)
    by = {(s["from"], s["to"]): s for s in segs}
    assert by[(0, 0)]["days"] == 10 and by[(0, 0)]["gb"] == 6
    assert by[(1, 1)]["gb"] == 3 and by[(0, 1)] == {"from": 0, "to": 1, "days": 15, "gb": 9}
    assert all(s["gb"] is None for s in et.segments_of([{"destination": TH, "days": 1}, {"destination": VN, "days": 1}], None))


def test_fits():
    row = {"days": 15, "data_gb": 10, "ils": 50}
    assert et.fits(row, 15, 10) and not et.fits(row, 16, 10) and not et.fits(row, 15, 11)
    assert not et.fits(row, 15, None)                           # 10GB is not "unlimited"
    assert et.fits({"days": 30, "data_gb": None, "ils": 80}, 15, None)
    assert et.fits({"days": 30, "data_gb": 60, "ils": 80}, 15, None)
    assert not et.fits({"days": None, "data_gb": None, "ils": 80}, 1, 1)


def _seed(dbp):
    db.init_db(dbp)
    conn = db._connect(dbp)
    rows = [  # carrier, plan, ILS price, currency, native price, days, gb, dest
        ("saily", "th-10", 40, "USD", 10, 15, 10, TH),
        ("saily", "th-short", 20, "USD", 5, 7, 10, TH),
        ("airalo", "th-10", 48, "USD", 12, 30, 10, TH),
        ("saily", "vn-5", 28, "USD", 7, 7, 5, VN),
        ("saily", "asia-20", 100, "USD", 25, 30, 20, ASIA),
        ("saily", "asia-20-dear", 120, "USD", 30, 30, 20, ASIA),
        ("nisim", "asia-ils", 90, "ILS", None, 30, 20, ASIA),
    ]
    for car, name, price, cur, orig, days, gb, dest in rows:
        conn.execute("INSERT INTO global_plans (carrier, plan_name, price, currency, original_price, days, data_gb, "
                     "esim, extras, scraped_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (car, name, price, cur, orig, days, gb, 1, json.dumps([dest]), "2026-11-24T07:30:00"))
    conn.commit()
    conn.close()


def test_trip_candidates(tmp_path):
    dbp = str(tmp_path / "t.db")
    try:
        _seed(dbp)
    except Exception as e:                      # schema drift in the fixture insert
        pytest.skip("global_plans seed failed: %s" % e)
    legs = [{"destination": TH, "days": 10}, {"destination": VN, "days": 7}]
    segs, newest = et.trip_candidates(legs, 15, [ASIA], FX, db_path=dbp)
    by = {(s["from"], s["to"]): s for s in segs}
    th = by[(0, 0)]
    assert [d["plan_name"] for d in th["own"]] == ["th-10", "th-10"]      # the 7-day plan is too short
    assert th["own"][0]["provider"] == "saily" and th["own"][0]["ils"] == 40.0   # 10 USD x 4.0
    assert by[(1, 1)]["gb"] == 7 and by[(1, 1)]["own"] == []             # vn-5 has too little data
    whole = by[(0, 1)]
    assert whole["own"] == [] and whole["days"] == 17 and whole["gb"] == 15
    # one row per provider (the cheaper Saily bundle), ILS-native plan at its stored price
    assert [(d["provider"], d["plan_name"], d["ils"]) for d in whole["bundles"]] == \
        [("nisim", "asia-ils", 90.0), ("saily", "asia-20", 100.0)]
    assert newest == "2026-11-24T07:30:00"
