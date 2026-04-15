import json
import pytest
import os

from app import app as flask_app
from db import init_db, save_plans, save_changes

PLANS = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,
     "data_gb": 60, "minutes": "unlimited", "extras": ["TV"]},
    {"carrier": "pelephone", "plan_name": "50GB", "price": 55,
     "data_gb": 50, "minutes": "unlimited", "extras": []},
]

HISTORY_CHANGES = [
    {'carrier': 'partner', 'plan_name': 'Test 50GB', 'change_type': 'price_change',
     'old_val': '40', 'new_val': '45', 'changed_at': '2025-06-01T10:00:00'},
    {'carrier': 'partner', 'plan_name': 'Test 50GB', 'change_type': 'price_change',
     'old_val': '45', 'new_val': '50', 'changed_at': '2025-09-01T10:00:00'},
    {'carrier': 'partner', 'plan_name': 'New Plan', 'change_type': 'new_plan',
     'old_val': None, 'new_val': '30', 'changed_at': '2025-07-01T10:00:00'},
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

@pytest.fixture
def client_with_history(tmp_path):
    db = str(tmp_path / "test.db")
    flask_app.config["TEST_DB_PATH"] = db
    flask_app.config["TESTING"] = True
    init_db(db_path=db)
    save_plans(PLANS, db_path=db)
    save_changes(HISTORY_CHANGES, db_path=db)
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

# --- /api/history/changes ---------------------------------------------------

def test_history_changes_empty_for_unknown_carrier(client):
    resp = client.get('/api/history/changes?carrier=nobody&plan_type=domestic')
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['changes'] == []
    assert data['summary']['total'] == 0

def test_history_changes_invalid_plan_type_returns_400(client):
    resp = client.get('/api/history/changes?carrier=partner&plan_type=invalid')
    assert resp.status_code == 400

def test_history_changes_returns_data_and_summary(client_with_history):
    resp = client_with_history.get('/api/history/changes?carrier=partner&plan_type=domestic')
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['summary']['total'] == 3
    assert data['summary']['price_up'] == 2   # both price_change events are up
    assert data['summary']['price_down'] == 0
    assert data['summary']['new_plans'] == 1
    assert len(data['changes']) == 3

# --- /api/history/price-series ----------------------------------------------

def test_history_price_series_invalid_plan_type_returns_400(client):
    resp = client.get('/api/history/price-series?carrier=partner&plan_type=bad')
    assert resp.status_code == 400

def test_history_price_series_empty_for_unknown_carrier(client):
    resp = client.get('/api/history/price-series?carrier=nobody&plan_type=domestic')
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['series'] == []

def test_history_price_series_builds_correct_timeline(client_with_history):
    resp = client_with_history.get(
        '/api/history/price-series?carrier=partner&plan_type=domestic&plan_name=Test+50GB'
    )
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert len(data['series']) == 1
    pts = data['series'][0]['points']
    # first point = old_val of first change, then new_val of each change
    assert pts[0]['price'] == 40.0
    assert pts[1]['price'] == 45.0
    assert pts[2]['price'] == 50.0

# --- /api/history/analyze ---------------------------------------------------
from unittest.mock import patch, MagicMock

def test_history_analyze_invalid_plan_type_returns_400(client):
    resp = client.get('/api/history/analyze?carrier=partner&plan_type=bad')
    assert resp.status_code == 400

def test_history_analyze_no_data_returns_null(client):
    resp = client.get('/api/history/analyze?carrier=nobody&plan_type=domestic')
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['analysis'] is None

def test_history_analyze_returns_analysis(client_with_history):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'content': [{'text': 'ניתוח בדיקה'}]}
    mock_resp.raise_for_status.return_value = None
    with patch('requests.post', return_value=mock_resp), \
         patch('app.load_config', return_value={'anthropic_api_key': 'test-key'}):
        resp = client_with_history.get(
            '/api/history/analyze?carrier=partner&plan_type=domestic'
        )
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert data['analysis'] == 'ניתוח בדיקה'


def test_history_analyze_prompt_contains_carrier_and_type(client_with_history):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'content': [{'text': 'x'}]}
    mock_resp.raise_for_status.return_value = None
    captured = {}
    def capture_post(url, **kwargs):
        captured['payload'] = kwargs.get('json', {})
        return mock_resp
    with patch('requests.post', side_effect=capture_post), \
         patch('app.load_config', return_value={'anthropic_api_key': 'test-key'}):
        client_with_history.get(
            '/api/history/analyze?carrier=partner&plan_type=domestic'
        )
    user_content = captured['payload']['messages'][0]['content']
    assert '\u05e4\u05e8\u05d8\u05e0\u05e8' in user_content   # פרטנר — partner display name
    assert '\u05de\u05e7\u05d5\u05de\u05d9' in user_content   # מקומי — domestic display name
