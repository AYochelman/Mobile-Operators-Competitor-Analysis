"""Scrape public Israeli cellular-deal Telegram channels for reseller-priced plans.

First-run flow:
  $ python telegram_resellers.py login          # one-time interactive login
                                                 # (you'll get a code in your Telegram app)

Routine flow:
  $ python telegram_resellers.py scrape         # ingest recent messages, upsert to DB

Channel list lives in config.json -> telegram_reseller_channels.
Each channel entry can be: "channel_username" or {"username": "...", "label": "...", "limit": 100}
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from db import init_db, save_reseller_plans

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
SESSION_PATH = ROOT / "data" / "telegram_session"   # .session is appended automatically


def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _client() -> TelegramClient:
    cfg = _config()
    api_id = cfg.get("telegram_api_id")
    api_hash = cfg.get("telegram_api_hash")
    if not api_id or not api_hash:
        raise RuntimeError("telegram_api_id / telegram_api_hash missing from config.json")
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(str(SESSION_PATH), api_id, api_hash)


# Carrier-name patterns. Order matters — first match wins.
_CARRIER_PATTERNS = [
    ("cellcom",   re.compile(r"\b(?:סלקום|cellcom)\b", re.IGNORECASE)),
    ("partner",   re.compile(r"\b(?:פרטנר|partner)\b", re.IGNORECASE)),
    ("pelephone", re.compile(r"\b(?:פלאפון|pelephone)\b", re.IGNORECASE)),
    ("hotmobile", re.compile(r"\b(?:הוט\s*מובייל|הוט-מובייל|hot\s*mobile|hotmobile)\b", re.IGNORECASE)),
]

_PRICE_RE = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:₪|ש[\"״]ח|שח|nis|ils)\b", re.IGNORECASE)
_GB_RE    = re.compile(r"(\d{1,4})\s*(?:GB|ג[\"״]ב|גיגה)", re.IGNORECASE)
_MIN_RE   = re.compile(r"(\d{1,5})\s*(?:דקות|דק'|min(?:utes)?)\b", re.IGNORECASE)


def _detect_carrier(text: str) -> str | None:
    for cid, pat in _CARRIER_PATTERNS:
        if pat.search(text):
            return cid
    return None


def _extract_plan(text: str, channel: str, msg_url: str, msg_date: datetime) -> dict | None:
    """Return a reseller_plans row dict, or None if message has no price+carrier."""
    carrier = _detect_carrier(text)
    if not carrier:
        return None
    price_m = _PRICE_RE.search(text)
    if not price_m:
        return None
    price = float(price_m.group(1).replace(",", "."))
    if price < 5 or price > 500:   # filter obvious non-plan numbers
        return None

    gb_m = _GB_RE.search(text)
    min_m = _MIN_RE.search(text)
    data_gb = float(gb_m.group(1)) if gb_m else None
    minutes = int(min_m.group(1)) if min_m else None

    # Build a stable plan_name from the price+spec so the same offer upserts on re-scrape
    spec_bits = []
    if data_gb is not None:
        spec_bits.append(f"{int(data_gb) if data_gb.is_integer() else data_gb}GB")
    if minutes is not None:
        spec_bits.append(f"{minutes} דקות")
    spec = " · ".join(spec_bits) or "חבילה"
    plan_name = f"{spec} ב-{int(price) if price.is_integer() else price} ₪"

    snippet = re.sub(r"\s+", " ", text).strip()[:200]
    return {
        "reseller_id": f"tg_{channel}",
        "carrier": carrier,
        "plan_name": plan_name,
        "price": price,
        "data_gb": data_gb,
        "minutes": minutes,
        "sms": None,
        "extras": [
            f"מקור: ערוץ טלגרם @{channel}",
            snippet,
        ],
        "source_url": msg_url,
        "seen_at": msg_date.date().isoformat(),
    }


_PENDING_PATH = ROOT / "data" / "telegram_pending.json"


async def cmd_login_request() -> None:
    """Phase 1: send the verification code to the user's Telegram app, then exit."""
    cfg = _config()
    phone = cfg.get("telegram_user_phone")
    if not phone:
        raise RuntimeError("telegram_user_phone missing from config.json")
    client = _client()
    await client.connect()
    if await client.is_user_authorized():
        print("ALREADY_AUTHORIZED")
        await client.disconnect()
        return
    sent = await client.send_code_request(phone)
    _PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PENDING_PATH.write_text(json.dumps({
        "phone": phone,
        "phone_code_hash": sent.phone_code_hash,
    }), encoding="utf-8")
    await client.disconnect()
    print("CODE_SENT")


async def cmd_login_verify(code: str, password: str | None = None) -> None:
    """Phase 2: complete sign-in with the code received in the Telegram app."""
    if not _PENDING_PATH.exists():
        raise RuntimeError("No pending login. Run login_request first.")
    pending = json.loads(_PENDING_PATH.read_text(encoding="utf-8"))
    client = _client()
    await client.connect()
    try:
        await client.sign_in(
            phone=pending["phone"],
            code=code,
            phone_code_hash=pending["phone_code_hash"],
        )
    except SessionPasswordNeededError:
        if not password:
            await client.disconnect()
            print("NEED_2FA")
            return
        await client.sign_in(password=password)
    _PENDING_PATH.unlink(missing_ok=True)
    me = await client.get_me()
    await client.disconnect()
    print(f"LOGGED_IN as {me.first_name} ({me.phone})")


async def cmd_scrape(default_limit: int = 100) -> None:
    cfg = _config()
    raw_channels = cfg.get("telegram_reseller_channels", [])
    if not raw_channels:
        print("No channels configured. Add some to config.json -> telegram_reseller_channels.")
        return
    channels = []
    for c in raw_channels:
        if isinstance(c, str):
            channels.append({"username": c.lstrip("@"), "limit": default_limit})
        else:
            channels.append({**c, "username": c["username"].lstrip("@"),
                             "limit": c.get("limit", default_limit)})

    init_db()
    client = _client()
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized. Run: python telegram_resellers.py login")
        await client.disconnect()
        return

    all_plans: list[dict] = []
    for ch in channels:
        username = ch["username"]
        limit = ch["limit"]
        print(f"Scanning @{username} (last {limit} messages)...")
        try:
            entity = await client.get_entity(username)
        except Exception as e:
            print(f"  ! cannot access @{username}: {e}")
            continue
        async for msg in client.iter_messages(entity, limit=limit):
            text = (msg.message or "").strip()
            if not text:
                continue
            url = f"https://t.me/{username}/{msg.id}"
            date = msg.date or datetime.now(timezone.utc)
            plan = _extract_plan(text, username, url, date)
            if plan:
                all_plans.append(plan)
        print(f"  -> {sum(1 for p in all_plans if p['reseller_id']==f'tg_{username}')} plans")

    await client.disconnect()
    if all_plans:
        save_reseller_plans(all_plans)
        print(f"\nUpserted {len(all_plans)} reseller_plans rows.")
    else:
        print("\nNo plans matched filters.")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scrape"
    if cmd == "login_request":
        asyncio.run(cmd_login_request())
    elif cmd == "login_verify":
        if len(sys.argv) < 3:
            print("Usage: telegram_resellers.py login_verify <code> [2fa_password]")
            sys.exit(1)
        code = sys.argv[2]
        pw = sys.argv[3] if len(sys.argv) > 3 else None
        asyncio.run(cmd_login_verify(code, pw))
    elif cmd == "scrape":
        asyncio.run(cmd_scrape())
    else:
        print(f"Unknown command: {cmd}\nUsage: telegram_resellers.py [login_request|login_verify <code>|scrape]")
        sys.exit(1)


if __name__ == "__main__":
    main()
