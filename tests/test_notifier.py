from unittest.mock import patch, MagicMock
from notifier import format_message, send_notification

PRICE_DROP = [
    {"carrier": "partner", "plan_name": "60GB",
     "change_type": "price_change", "old_val": 59, "new_val": 49}
]

PRICE_RISE = [
    {"carrier": "hotmobile", "plan_name": "30GB",
     "change_type": "price_change", "old_val": 35, "new_val": 39}
]

NEW_PLAN = [
    {"carrier": "cellcom", "plan_name": "ללא הגבלה",
     "change_type": "new_plan", "old_val": None, "new_val": 89}
]

REMOVED = [
    {"carrier": "pelephone", "plan_name": "OLD",
     "change_type": "removed_plan", "old_val": 55, "new_val": None}
]

def test_format_price_drop_contains_arrow_down():
    msg = format_message(PRICE_DROP)
    assert "↘" in msg
    assert "59" in msg
    assert "49" in msg
    assert "פרטנר" in msg

def test_format_price_rise_contains_arrow_up():
    msg = format_message(PRICE_RISE)
    assert "↗" in msg
    assert "הוט מובייל" in msg

def test_format_new_plan_contains_sparkle():
    msg = format_message(NEW_PLAN)
    assert "✨" in msg
    assert "ללא הגבלה" in msg

def test_format_removed_plan_contains_x():
    msg = format_message(REMOVED)
    assert "❌" in msg
    assert "OLD" in msg

def test_format_contains_localhost_url():
    msg = format_message(PRICE_DROP)
    assert "localhost:5000" in msg

def test_format_multi_carrier_shows_count():
    changes = PRICE_DROP + PRICE_RISE
    msg = format_message(changes)
    assert "2" in msg

def test_send_notification_success():
    config = {"telegram_bot_token": "TOKEN123", "telegram_chat_id": "CHAT456"}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("notifier.requests.post", return_value=mock_resp) as mock_post:
        result = send_notification("test message", config)
    assert result is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "TOKEN123" in call_kwargs.args[0]
    assert call_kwargs.kwargs["json"]["chat_id"] == "CHAT456"
    assert call_kwargs.kwargs["json"]["text"] == "test message"

def test_send_notification_failure():
    config = {"telegram_bot_token": "BAD", "telegram_chat_id": "BAD"}
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("notifier.requests.post", return_value=mock_resp):
        result = send_notification("msg", config)
    assert result is False
