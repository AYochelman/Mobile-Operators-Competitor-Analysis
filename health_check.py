import json, requests
from pathlib import Path

cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))

def check(name, fn):
    try:
        ok, msg = fn()
        print(("PASS  " if ok else "FAIL  ") + name + ": " + msg)
    except Exception as e:
        print("FAIL  " + name + ": " + str(e))

def telegram_bot():
    r = requests.get("https://api.telegram.org/bot" + cfg["telegram_bot_token"] + "/getMe", timeout=8)
    j = r.json()
    return j.get("ok"), ("bot @" + j["result"]["username"]) if j.get("ok") else j.get("description","?")

def green_api():
    url = cfg["greenapi_url"] + "/waInstance" + str(cfg["greenapi_instance"]) + "/getStateInstance/" + cfg["greenapi_token"]
    r = requests.get(url, timeout=8).json()
    return r.get("stateInstance") == "authorized", str(r.get("stateInstance","?"))

def anthropic_api():
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": cfg["anthropic_api_key"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model":"claude-haiku-4-5-20251001","max_tokens":5,"messages":[{"role":"user","content":"hi"}]},
        timeout=15,
    )
    return r.status_code == 200, "HTTP " + str(r.status_code)

def supabase_ping():
    r = requests.get(cfg["supabase_url"] + "/rest/v1/", timeout=8)
    return r.status_code in (200, 401, 404), "HTTP " + str(r.status_code)

def telethon_session():
    import asyncio
    from telethon import TelegramClient
    async def go():
        c = TelegramClient("data/telegram_session", cfg["telegram_api_id"], cfg["telegram_api_hash"])
        await c.connect()
        ok = await c.is_user_authorized()
        await c.disconnect()
        return ok
    ok = asyncio.run(go())
    return ok, "authorized" if ok else "NOT authorized - re-login needed"

check("Telegram Bot", telegram_bot)
check("WhatsApp Green API", green_api)
check("Anthropic Claude API", anthropic_api)
check("Supabase", supabase_ping)
check("Telethon session", telethon_session)
