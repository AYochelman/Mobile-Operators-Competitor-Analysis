# -*- coding: utf-8 -*-
"""Generate destination background images for the /esim-deals trip wizard.

For every destination in the live /api/esim/destinations feed, generates a
representative landmark photo via the Gemini image API (config.json:
gemini_api_key) into mass-market-app/public/dest-bg/<slug>.webp, then rewrites
the React manifest mass-market-app/src/data/destBg.js (Hebrew destination
string -> image path) from what actually exists on disk.

Curation lives in scripts/dest_bg_map.json: region images shared across
variants ("אירופה+" -> europe.webp), aliases for combo plans ("יפן וקוריאה" ->
jp.webp), sub-national places (Hawaii, Dubai...), and the cruise ship image.
Junk destination strings (provider bundle names, "Family Large 5GB"...) simply
get no manifest entry and render with no background.

Idempotent: existing .webp files are kept (delete a file to regenerate it).
Usage:  python scripts/gen_dest_backgrounds.py [--dry-run] [--workers N]
Requires Flask on :5000 (destination list) and node (English display names).
"""
import argparse
import base64
import io
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "mass-market-app")
OUT_DIR = os.path.join(APP, "public", "dest-bg")
MANIFEST = os.path.join(APP, "src", "data", "destBg.js")
MAP_JSON = os.path.join(ROOT, "scripts", "dest_bg_map.json")

MODEL = "gemini-2.5-flash-image"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# The wizard card is a wide strip (~2.2:1 desktop, taller on mobile) rendered with
# background-size:cover + center — so images are 21:9 banners whose subject is
# horizontally centered and fills the frame height (a small tall landmark against
# empty sky gets crop-decapitated, e.g. the first Eiffel Tower batch).
COUNTRY_TMPL = (
    "Ultra-wide panoramic banner photograph of {en}: its most iconic landmark or most "
    "recognizable scenery, the subject large, horizontally centered and filling most of the "
    "frame height, low horizon, minimal empty sky, warm golden hour light, soft warm tones, "
    "editorial travel-magazine style, no people in the foreground, no text, no watermark"
)
REGION_TMPL = (
    "Ultra-wide panoramic banner photograph: {scene}, the subject large, horizontally centered "
    "and filling most of the frame height, low horizon, minimal empty sky, warm golden hour "
    "light, soft warm tones, editorial travel-magazine style, no text, no watermark"
)

_print_lock = threading.Lock()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def node_country_map():
    """he -> {slug, en} for every live destination with an ISO code, via the app's own catalog."""
    js = (
        "import { pathToFileURL } from 'node:url';"
        f"const mod = await import(pathToFileURL({json.dumps(os.path.join(APP, 'src', 'data', 'hotelDestinations.js'))}).href);"
        "const byHe = new Map(mod.HOTEL_DESTINATIONS.map(d => [d.he, d]));"
        "const list = await (await fetch('http://localhost:5000/api/esim/destinations')).json();"
        "const out = {};"
        "for (const { destination: he } of list) {"
        "  const e = byHe.get(he);"
        "  if (e && e.iso) out[he] = { slug: e.iso.toLowerCase(), en: mod.destLabel(he, 'en') };"
        "}"
        "process.stdout.write(JSON.stringify({ out, all: list.map(d => d.destination) }));"
    )
    r = subprocess.run(
        ["node", "--input-type=module", "-e", js],
        capture_output=True, encoding="utf-8", cwd=APP, check=True,
    )
    return json.loads(r.stdout)


def generate_one(key, slug, prompt, retries=4):
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
                        if img.width > 1080:
                            img = img.resize((1080, round(img.height * 1080 / img.width)), Image.LANCZOS)
                        img.save(os.path.join(OUT_DIR, f"{slug}.webp"), "WEBP", quality=72, method=6)
                        return True
                log(f"  {slug}: no image part (attempt {attempt + 1})")
            elif r.status_code in (429, 500, 502, 503):
                log(f"  {slug}: HTTP {r.status_code}, retrying in {delay}s")
            else:
                log(f"  {slug}: HTTP {r.status_code}: {r.text[:200]}")
                return False
        except requests.RequestException as e:
            log(f"  {slug}: {type(e).__name__}, retrying in {delay}s")
        time.sleep(delay)
        delay = min(delay * 2, 60)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the task list, generate nothing")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        key = json.load(f)["gemini_api_key"]
    with open(MAP_JSON, encoding="utf-8") as f:
        cur = json.load(f)
    os.makedirs(OUT_DIR, exist_ok=True)

    data = node_country_map()
    countries, all_dests = data["out"], set(data["all"])

    # slug -> prompt for every image that should exist
    tasks = {}
    # he -> slug for the manifest (filtered later by what exists on disk)
    manifest = {}

    for he, info in countries.items():
        manifest[he] = info["slug"]
        tasks[info["slug"]] = COUNTRY_TMPL.format(en=info["en"])
    for table in ("manual_countries", "subnational"):
        for he, info in cur[table].items():
            if he in all_dests:
                manifest[he] = info["slug"]
                tasks[info["slug"]] = COUNTRY_TMPL.format(en=info["en"])
    for slug, scene in cur["regions"].items():
        tasks[slug] = REGION_TMPL.format(scene=scene)
    tasks["cruise"] = cur["cruise_prompt"]
    for he, slug in cur["region_keys"].items():
        if he in all_dests:
            manifest[he] = slug
    for he, slug in cur["aliases"].items():
        if he in all_dests:
            manifest[he] = slug

    todo = {s: p for s, p in tasks.items() if not os.path.exists(os.path.join(OUT_DIR, f"{s}.webp"))}
    log(f"destinations: {len(all_dests)} | manifest entries: {len(manifest)} | "
        f"images total: {len(tasks)} | to generate: {len(todo)}")
    if args.dry_run:
        for s in sorted(todo):
            log(f"  {s}: {todo[s][:90]}")
        return

    failed = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(generate_one, key, s, p): s for s, p in todo.items()}
        for fut in as_completed(futs):
            slug = futs[fut]
            done += 1
            if fut.result():
                if done % 10 == 0 or done == len(todo):
                    log(f"[{done}/{len(todo)}] ok: {slug}")
            else:
                failed.append(slug)
                log(f"[{done}/{len(todo)}] FAILED: {slug}")

    # Manifest from what actually exists on disk — a failed slug just gets no bg.
    entries = {he: f"/dest-bg/{slug}.webp" for he, slug in sorted(manifest.items())
               if os.path.exists(os.path.join(OUT_DIR, f"{slug}.webp"))}
    lines = [
        "// AUTO-GENERATED by scripts/gen_dest_backgrounds.py — do not edit by hand.",
        "// Hebrew /api/esim/destinations string -> background image for the /esim-deals trip wizard.",
        "export const DEST_BG_BY_HE = {",
    ]
    lines += [f"  {json.dumps(he, ensure_ascii=False)}: {json.dumps(path)}," for he, path in entries.items()]
    lines += ["}", ""]
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    log(f"manifest written: {len(entries)} entries -> {MANIFEST}")
    if failed:
        log("failed slugs (rerun to retry): " + ", ".join(sorted(failed)))
        sys.exit(1)


if __name__ == "__main__":
    main()
