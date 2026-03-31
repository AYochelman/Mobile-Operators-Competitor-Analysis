import json
import pytest
import os

from app import app as flask_app
from db import init_db, save_plans

PLANS = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,
     "data_gb": 60, "minutes": "unlimited", "extras": ["TV"]},
    {"carrier": "pelephone", "plan_name": "50GB", "price": 55,
     "data_gb": 50, "minutes": "unlimited", "extras": []},
]

@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "test.db")
    flask_app.config["TEST_DB_PATH"] = db
    flask_app.config["TESTING"] = True
    init_db(db_path=db)
    save_plans(PLANS, db_path=db)
    with flask_app.test_client() as c:
        yield c

def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"html" in resp.data.lower()

def test_api_plans_returns_all(client):
    resp = client.get("/api/plans")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert len(data) == 2

def test_api_plans_filter_by_carrier(client):
    resp = client.get("/api/plans?carrier=partner")
    data = json.loads(resp.data)
    assert len(data) == 1
    assert data[0]["carrier"] == "partner"

def test_api_changes_returns_list(client):
    resp = client.get("/api/changes")
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert isinstance(data, list)
