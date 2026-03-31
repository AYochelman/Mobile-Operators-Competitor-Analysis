import requests
from datetime import datetime
from collections import defaultdict

CARRIER_NAMES = {
    "partner":   "פרטנר",
    "pelephone": "פלאפון",
    "hotmobile": "הוט מובייל",
    "cellcom":   "סלקום",
    "mobile019": "019",
}


def format_message(changes):
    now = datetime.now().strftime("%H:%M")
    by_carrier = defaultdict(list)
    for ch in changes:
        by_carrier[ch["carrier"]].append(ch)

    n = len(by_carrier)
    suffix = "חברה" if n == 1 else "חברות"
    lines = [
        f"📱 השוואת סלולר | עדכון {now}",
        "",
        f"🔔 זוהו שינויים ב-{n} {suffix}",
    ]

    for carrier, carrier_changes in by_carrier.items():
        name = CARRIER_NAMES.get(carrier, carrier)
        lines.append(f"\n● {name}")
        for ch in carrier_changes:
            ct = ch["change_type"]
            if ct == "price_change":
                old, new = ch["old_val"], ch["new_val"]
                arrow = "↘" if new < old else "↗"
                lines.append(f"{arrow} {ch['plan_name']}: ₪{old} ← ₪{new}")
            elif ct == "new_plan":
                lines.append(f"✨ חבילה חדשה: {ch['plan_name']} ב-₪{ch['new_val']}")
            elif ct == "removed_plan":
                lines.append(f"❌ הוסרה: {ch['plan_name']}")
            elif ct == "extras_change":
                lines.append(f"🔄 שינוי הטבות: {ch['plan_name']}")

    lines += ["", "📊 http://localhost:5000"]
    return "\n".join(lines)


def send_notification(message, config):
    token = config["telegram_bot_token"]
    chat_id = config["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def send_whatsapp(message, config):
    base_url = config.get("greenapi_url", "")
    instance = config.get("greenapi_instance", "")
    token = config.get("greenapi_token", "")
    phone = config.get("whatsapp_phone", "")
    if not all([base_url, instance, token, phone]):
        return False
    url = f"{base_url}/waInstance{instance}/sendMessage/{token}"
    chat_id = f"{phone}@c.us"
    try:
        resp = requests.post(
            url,
            json={"chatId": chat_id, "message": message},
            timeout=10
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False
