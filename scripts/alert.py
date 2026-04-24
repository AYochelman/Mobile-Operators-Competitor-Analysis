"""Send an alert via multiple channels (SendGrid email + Telegram).

Usage:
    python alert.py "Subject" "Body text"

Exit codes:
    0 = at least one channel delivered
    1 = missing config or all channels failed
"""
import json
import sys
from pathlib import Path


def load_config() -> dict:
    project_root = Path(__file__).resolve().parent.parent
    config_path  = project_root / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"config.json not found at {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def send_email(subject: str, body: str, config: dict) -> bool:
    import requests
    api_key   = config.get("sendgrid_api_key", "")
    sender    = config.get("email_sender", "")
    recipient = config.get("email_recipient", "")
    if not all([api_key, sender, recipient]):
        sys.stderr.write("email: missing sendgrid_api_key / email_sender / email_recipient\n")
        return False

    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from":    {"email": sender, "name": "MOCA Backup Alert"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
    except requests.RequestException as e:
        sys.stderr.write(f"email: network error {e}\n")
        return False

    if resp.status_code == 202:
        return True
    sys.stderr.write(f"email: SendGrid {resp.status_code}: {resp.text[:300]}\n")
    return False


def send_telegram(subject: str, body: str, config: dict) -> bool:
    import requests
    token   = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if not all([token, chat_id]):
        sys.stderr.write("telegram: missing telegram_bot_token / telegram_chat_id\n")
        return False

    # Combine subject + body into a single Telegram message.
    message = f"\U0001F6A8 {subject}\n\n{body}"
    # Telegram caps at 4096 chars; truncate safely
    if len(message) > 4000:
        message = message[:3990] + "\n\n[truncated]"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
    except requests.RequestException as e:
        sys.stderr.write(f"telegram: network error {e}\n")
        return False

    if resp.status_code == 200:
        return True
    sys.stderr.write(f"telegram: {resp.status_code}: {resp.text[:300]}\n")
    return False


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: alert.py <subject> <body>\n")
        return 1

    subject = sys.argv[1]
    body    = sys.argv[2]

    try:
        config = load_config()
    except Exception as e:
        sys.stderr.write(f"config load failed: {e}\n")
        return 1

    email_ok    = send_email(subject, body, config)
    telegram_ok = send_telegram(subject, body, config)

    results = []
    results.append(f"email={'ok' if email_ok else 'FAIL'}")
    results.append(f"telegram={'ok' if telegram_ok else 'FAIL'}")
    sys.stdout.write(" ".join(results) + "\n")

    return 0 if (email_ok or telegram_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
