# -*- coding: utf-8 -*-
"""Generate the MOCA reminder-email hero banners via Gemini image gen.

One 21:9 hero per email kind, saved as JPEG in mass-market-app/public/email/
(the emails embed them as PUBLIC Netlify URLs via notifier._rem_hero_url, so a
frontend deploy is needed after regenerating). Idempotent - delete a jpg to
regenerate. Same API pattern as scripts/gen_dest_backgrounds.py
(gemini-2.5-flash-image, config.json gemini_api_key).
Run: python scripts/gen_email_banners.py
"""
import base64
import io
import json
import os
import sys
import time

import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "mass-market-app", "public", "email")

MODEL = "gemini-2.5-flash-image"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

STYLE = (
    "Flat vector-style editorial illustration, warm mocha-latte brand palette: espresso "
    "brown #5c3317, terracotta orange #c9622f, cream #f5ede0 background, soft rounded "
    "shapes, generous negative space, minimal and premium, absolutely no text, no letters, "
    "no numbers, no watermark"
)

# Keyed by the notifier email kind (see notifier._rem_hero_url).
BANNERS = {
    "better_deal": (
        "Wide banner illustration: a smartphone standing at the center with a large downward "
        "arrow beside it and a few coins stacked at its base, subtle sparkles, conveying "
        "'the price just dropped'. " + STYLE
    ),
    "plan_end": (
        "Wide banner illustration: an hourglass next to a smartphone with a small bell above "
        "them, conveying 'your plan term is about to end, time to act'. " + STYLE
    ),
    "heartbeat": (
        "Wide banner illustration: a calm smooth pulse line (like a gentle heartbeat or "
        "market graph) flowing horizontally across the frame over a cream background, a "
        "small shield icon at its end, conveying 'we are watching the market for you, all "
        "is calm'. " + STYLE
    ),
    "renewal": (
        "Wide banner illustration: a calendar page with a circular arrow wrapping around "
        "it (renewal loop motif), a small checkmark, conveying 'time to renew and keep "
        "your good terms'. " + STYLE
    ),
}


def generate(key, slug, prompt, retries=4):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "21:9"}},
    }
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    delay = 5
    for attempt in range(retries):
        try:
            r = requests.post(API_URL, headers=headers, json=body, timeout=180)
            if r.status_code == 200:
                parts = r.json()["candidates"][0]["content"]["parts"]
                for p in parts:
                    inline = p.get("inlineData") or p.get("inline_data")
                    if inline:
                        img = Image.open(io.BytesIO(base64.b64decode(inline["data"]))).convert("RGB")
                        if img.width > 1120:
                            img = img.resize((1120, round(img.height * 1120 / img.width)), Image.LANCZOS)
                        img.save(os.path.join(OUT_DIR, f"{slug}.jpg"), "JPEG", quality=82, optimize=True)
                        return True
                print(f"  {slug}: no image part (attempt {attempt + 1})")
            elif r.status_code in (429, 500, 502, 503):
                print(f"  {slug}: HTTP {r.status_code}, retrying in {delay}s")
            else:
                print(f"  {slug}: HTTP {r.status_code}: {r.text[:200]}")
                return False
        except requests.RequestException as e:
            print(f"  {slug}: {type(e).__name__}, retrying in {delay}s")
        time.sleep(delay)
        delay = min(delay * 2, 60)
    return False


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        key = json.load(f)["gemini_api_key"]
    os.makedirs(OUT_DIR, exist_ok=True)
    for slug, prompt in BANNERS.items():
        path = os.path.join(OUT_DIR, f"{slug}.jpg")
        if os.path.exists(path):
            print(f"  {slug}: exists, skipping")
            continue
        ok = generate(key, slug, prompt)
        print(f"  {slug}: {'OK' if ok else 'FAILED'}")


if __name__ == "__main__":
    main()
