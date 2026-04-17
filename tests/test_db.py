import pytest
from db import (init_db, save_plans, get_plans, save_changes, get_changes,
                upsert_news_articles, get_news_articles,
                log_affiliate_click, get_affiliate_stats)

@pytest.fixture
def tmp_db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(db_path=path)
    return path

SAMPLE_PLANS = [
    {"carrier": "partner", "plan_name": "60GB", "price": 49,
     "data_gb": 60, "minutes": "unlimited", "extras": ["TV Basic"]},
    {"carrier": "partner", "plan_name": "100GB", "price": 69,
     "data_gb": 100, "minutes": "unlimited", "extras": []},
    {"carrier": "pelephone", "plan_name": "50GB", "price": 55,
     "data_gb": 50, "minutes": "unlimited", "extras": []},
]

def test_init_creates_tables(tmp_db):
    plans = get_plans(db_path=tmp_db)
    assert plans == []

def test_save_and_get_all_plans(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    plans = get_plans(db_path=tmp_db)
    assert len(plans) == 3

def test_get_plans_filter_by_carrier(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    plans = get_plans(carrier="partner", db_path=tmp_db)
    assert len(plans) == 2
    assert all(p["carrier"] == "partner" for p in plans)

def test_save_plans_upsert(tmp_db):
    save_plans(SAMPLE_PLANS, db_path=tmp_db)
    updated = [{"carrier": "partner", "plan_name": "60GB", "price": 45,
                "data_gb": 60, "minutes": "unlimited", "extras": []}]
    save_plans(updated, db_path=tmp_db)
    plans = get_plans(carrier="partner", db_path=tmp_db)
    sixty = next(p for p in plans if p["plan_name"] == "60GB")
    assert sixty["price"] == 45  # updated

def test_save_and_get_changes(tmp_db):
    changes = [
        {"carrier": "partner", "plan_name": "60GB",
         "change_type": "price_change", "old_val": "59", "new_val": "49"}
    ]
    save_changes(changes, db_path=tmp_db)
    result = get_changes(db_path=tmp_db)
    assert len(result) == 1
    assert result[0]["change_type"] == "price_change"

def test_get_changes_limit(tmp_db):
    changes = [
        {"carrier": "partner", "plan_name": f"plan{i}",
         "change_type": "new_plan", "old_val": None, "new_val": "49"}
        for i in range(5)
    ]
    save_changes(changes, db_path=tmp_db)
    result = get_changes(limit=3, db_path=tmp_db)
    assert len(result) == 3


SAMPLE_ARTICLES = [
    {'carrier': 'partner',   'headline': 'פרטנר מוזילה מחירים', 'url': 'https://example.com/1',
     'source': 'גלובס', 'published_at': '2026-04-17T08:00:00Z'},
    {'carrier': 'pelephone', 'headline': 'פלאפון מרחיבה 5G',    'url': 'https://example.com/2',
     'source': 'ynet',   'published_at': '2026-04-17T07:00:00Z'},
    {'carrier': 'partner',   'headline': 'פרטנר רוכשת חברה',     'url': 'https://example.com/3',
     'source': 'TheMarker', 'published_at': '2026-04-16T12:00:00Z'},
]

def test_upsert_and_get_all_news(tmp_db):
    upsert_news_articles(SAMPLE_ARTICLES, db_path=tmp_db)
    articles = get_news_articles(db_path=tmp_db)
    assert len(articles) == 3

def test_get_news_filter_by_carrier(tmp_db):
    upsert_news_articles(SAMPLE_ARTICLES, db_path=tmp_db)
    articles = get_news_articles(carrier='partner', db_path=tmp_db)
    assert len(articles) == 2
    assert all(a['carrier'] == 'partner' for a in articles)

def test_upsert_news_deduplication(tmp_db):
    upsert_news_articles(SAMPLE_ARTICLES, db_path=tmp_db)
    upsert_news_articles(SAMPLE_ARTICLES, db_path=tmp_db)   # insert again
    articles = get_news_articles(db_path=tmp_db)
    assert len(articles) == 3   # still 3, not 6


def test_log_affiliate_click_basic(tmp_db):
    log_affiliate_click("airalo", plan_id="israel-1gb", country="ישראל",
                        ip_hash="abc123", db_path=tmp_db)
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    assert len(stats) == 1
    assert stats[0]["provider"] == "airalo"
    assert stats[0]["clicks"] == 1

def test_log_affiliate_click_optional_fields(tmp_db):
    log_affiliate_click("holafly", db_path=tmp_db)
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    assert stats[0]["clicks"] == 1

def test_get_affiliate_stats_groups_by_provider(tmp_db):
    log_affiliate_click("airalo", db_path=tmp_db)
    log_affiliate_click("airalo", db_path=tmp_db)
    log_affiliate_click("holafly", db_path=tmp_db)
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    providers = {s["provider"]: s["clicks"] for s in stats}
    assert providers["airalo"] == 2
    assert providers["holafly"] == 1

def test_get_affiliate_stats_respects_days_window(tmp_db):
    import sqlite3, datetime
    old_ts = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=40)).isoformat()
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO affiliate_clicks (provider, clicked_at) VALUES (?,?)",
        ("airalo", old_ts)
    )
    conn.commit()
    conn.close()
    stats = get_affiliate_stats(days=30, db_path=tmp_db)
    assert stats == []
