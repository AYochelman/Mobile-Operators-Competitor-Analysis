# -*- coding: utf-8 -*-
"""
Generate TikTok awareness clips for esim.mocaintel.com with Gemini Veo 3.1.

5 videos x 2 portrait (9:16) clips each = 10 clips. Each pair is then
concatenated with ffmpeg into a final ~16-20s video.

Resume-safe: progress is tracked in tiktok-veo/state.json, so re-running the
script only generates what is still missing (e.g. after a daily-quota stop).

Exit codes: 0 = everything done, 1 = partial (errors remain), 2 = quota
exhausted (re-run tomorrow), 3 = fatal (auth/billing).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "marketing" / "b2c-launch" / "tiktok-veo"
STATE_FILE = OUT_DIR / "state.json"
BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "veo-3.1-fast-generate-preview"
POLL_EVERY = 15          # seconds
POLL_TIMEOUT = 15 * 60   # per clip
URL_CARD = "esim.mocaintel.com"

# ---------------------------------------------------------------- prompts ---
END_CARD = (
    "a clean full-screen end card: warm cream background, bold dark "
    f"espresso-brown sans-serif text reading exactly '{URL_CARD}' centered "
    "and perfectly legible"
)

CLIPS = {
    # ---- Video 1: "The roaming bill" (shock -> relief) ----
    "v1_p1": (
        "Vertical 9:16 cinematic UGC-style shot. A young woman in her 20s "
        "sits at a bright home kitchen table, an unpacked suitcase with "
        "luggage tags beside her, just back from vacation. She opens her "
        "phone, freezes, eyes widen in disbelief at a phone bill with a huge "
        "total highlighted in red, she brings the phone closer, jaw drops, "
        "slumps back dramatically. Fast push-in camera move toward her "
        "shocked face, then a quick whip pan to the glowing phone screen. "
        "Natural morning light, realistic skin texture, handheld feel. "
        "Audio: tense rising sting, a sharp gasp. No dialogue, no subtitles."
    ),
    "v1_p2": (
        "Vertical 9:16 cinematic shot in two beats. First beat: a young "
        "woman in her 20s relaxes on a sunny Greek island balcony "
        "overlooking white houses and blue sea, holds up her phone showing "
        "full signal bars and a green connected checkmark, smiles, sips "
        "iced coffee, gentle breeze, camera slowly orbits her. Second beat: "
        f"smash cut to {END_CARD}, subtle confetti falling. Audio: light "
        "upbeat ukulele music, a cheerful ding when the end card appears. "
        "No dialogue, no subtitles."
    ),
    # ---- Video 2: "Same eSIM, 4x the price" (price-gap reveal) ----
    "v2_p1": (
        "Vertical 9:16 stylized 3D motion-graphics scene. Dozens of "
        "identical glowing eSIM chip cards float in neat rows above a dark "
        "world map, each card has a paper price tag hanging from it, some "
        "tags huge and red, some small and green, wildly different sizes "
        "for identical cards. A giant hand swipes through them like a "
        "carousel, tags flipping and swinging. Dramatic spotlight, shallow "
        "depth of field. Audio: fast whoosh on each swipe, ticking clock "
        "tension building. No dialogue, no subtitles, no readable words."
    ),
    "v2_p2": (
        "Vertical 9:16 stylized 3D motion-graphics scene in two beats. "
        "First beat: floating eSIM chip cards with price tags suddenly sort "
        "themselves into a vertical leaderboard, the cheapest card rises to "
        "the top and glows gold, a big green checkmark stamps onto it, the "
        "expensive cards tumble away into darkness, camera pushes in on the "
        f"winner. Second beat: smash cut to {END_CARD}. Audio: satisfying "
        "rapid sorting clicks, a triumphant chime on the stamp, soft music "
        "outro. No dialogue, no subtitles."
    ),
    # ---- Video 3: "POV: you land already connected" ----
    "v3_p1": (
        "Vertical 9:16 first-person POV, smartphone-camera realism. Walking "
        "out of an airplane door onto a jet bridge with other passengers "
        "ahead, the traveler's hand raises a phone: the screen lights up "
        "with full signal bars and a rapid flood of incoming message "
        "notification bubbles. Energetic pace, slight handheld bounce, "
        "bright light at the end of the jet bridge. Audio: airplane cabin "
        "ambience fading out, rapid message notification pops, upbeat music "
        "kicking in. No dialogue, no subtitles."
    ),
    "v3_p2": (
        "Vertical 9:16 POV in two beats. First beat: quick warm flashback "
        "at home the night before, hands scan a QR code shown on a laptop "
        "screen using a phone, the phone instantly glows with a green "
        "connected checkmark. Second beat: back at the airport, POV sliding "
        "into a taxi back seat, the phone opens a navigation map instantly, "
        "city lights ahead through the windshield, then a smash cut to "
        f"{END_CARD}. Audio: one soft scan beep, seamless upbeat music, "
        "calm confident arrival vibe. No dialogue, no subtitles."
    ),
    # ---- Video 4: "The airport kiosk rip-off" (comedy) ----
    "v4_p1": (
        "Vertical 9:16 comedic cinematic shot, exaggerated sitcom energy. "
        "A sweaty tourist with a big backpack stands at a garish airport "
        "SIM-card kiosk abroad, the grinning vendor dramatically flips a "
        "price sign covered in currency symbols to reveal an absurdly high "
        "price, coins and bills decorate the stall. Slow dramatic zoom into "
        "the tourist's despairing face, colors desaturate, a comedic "
        "deadpan pause. Audio: record scratch, cash register cha-ching "
        "repeating menacingly. No dialogue, no subtitles."
    ),
    "v4_p2": (
        "Vertical 9:16 comedic cinematic shot in two beats. First beat: the "
        "tourist's friend appears, taps her phone twice and turns the "
        "screen to camera, a tidy list on the screen cascades down and "
        "lands on one tiny green price at the top, both travelers' faces "
        "light up and they strut away from the kiosk in slow motion putting "
        "on sunglasses while the kiosk vendor deflates like a balloon. "
        f"Second beat: smash cut to {END_CARD}. Audio: swaggering funk beat "
        "drop, one playful boing as the vendor deflates. No dialogue, no "
        "subtitles."
    ),
    # ---- Video 5: "One phone, whole world" (aspirational montage) ----
    "v5_p1": (
        "Vertical 9:16 fast-paced aspirational travel montage, rich "
        "cinematic color grade. Four quick scenes, in each one a hand holds "
        "up the same smartphone showing full signal bars and a glowing "
        "connected checkmark: neon Tokyo crossing at night, the Eiffel "
        "Tower at golden hour, white-and-blue Santorini rooftops at noon, "
        "a snowy Alps peak. Whip-pan transitions landing on the beat. "
        "Audio: driving percussion building energy, whoosh on every "
        "transition. No dialogue, no subtitles."
    ),
    "v5_p2": (
        "Vertical 9:16 stylized finale in two beats. First beat: a glowing "
        "globe assembled from hundreds of tiny eSIM chip cards spins slowly "
        "in dark space, then gracefully collapses and funnels into a single "
        "smartphone floating upright, the phone screen fills with a bright "
        "checkmark and a warm light burst. Second beat: the light fades "
        f"into {END_CARD}. Audio: cinematic riser resolving into a warm "
        "satisfying chord, soft sparkle. No dialogue, no subtitles."
    ),
}

VIDEOS = {f"v{i}": (f"v{i}_p1", f"v{i}_p2") for i in range(1, 6)}

# ----------------------------------------------------------------- helpers --

def log(msg):
    print(time.strftime("[%H:%M:%S]"), msg, flush=True)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"clips": {}, "params": {"durationSeconds": 10, "resolution": "1080p"}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def api_key():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    return cfg["gemini_api_key"]


def find_uris(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            find_uris(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_uris(v, out)
    elif isinstance(obj, str) and obj.startswith("http"):
        out.append(obj)


class Quota(Exception):
    pass


class Fatal(Exception):
    pass


def start_clip(key, prompt, params):
    """POST predictLongRunning; adapts params on 400. Returns op name."""
    body = {"instances": [{"prompt": prompt}], "parameters": dict(params)}
    body["parameters"]["aspectRatio"] = "9:16"
    body["parameters"]["personGeneration"] = "allow_adult"
    for attempt in range(6):
        r = requests.post(
            f"{BASE}/models/{MODEL}:predictLongRunning",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=body, timeout=60,
        )
        if r.status_code == 200:
            return r.json()["name"], body["parameters"]
        if r.status_code == 429:
            raise Quota(r.text[:500])
        if r.status_code in (401, 403):
            raise Fatal(f"{r.status_code}: {r.text[:500]}")
        if r.status_code == 400:
            msg = r.text.lower()
            p = body["parameters"]
            if "duration" in msg and p.get("durationSeconds", 8) != 8:
                log(f"  400 on duration -> falling back to 8s")
                p["durationSeconds"] = 8
                continue
            if "resolution" in msg and p.get("resolution") == "1080p":
                log(f"  400 on resolution -> falling back to 720p")
                p["resolution"] = "720p"
                continue
            for k in ("resolution", "durationSeconds", "personGeneration"):
                if k.lower() in msg and k in p:
                    log(f"  400 on {k} -> dropping param")
                    del p[k]
                    break
            else:
                raise RuntimeError(f"400: {msg[:500]}")
            continue
        if r.status_code >= 500:
            log(f"  {r.status_code}, retrying in 20s")
            time.sleep(20)
            continue
        raise RuntimeError(f"{r.status_code}: {r.text[:500]}")
    raise RuntimeError("start_clip: retries exhausted")


def poll(op_name):
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        r = requests.get(f"{BASE}/{op_name}", headers={"x-goog-api-key": key},
                         timeout=60)
        if r.status_code == 429:
            time.sleep(30)
            continue
        r.raise_for_status()
        op = r.json()
        if op.get("done"):
            if "error" in op:
                raise RuntimeError(f"operation error: {json.dumps(op['error'])[:400]}")
            resp = op.get("response", {})
            uris = []
            find_uris(resp, uris)
            if not uris:
                raise RuntimeError(f"no video uri (filtered?): {json.dumps(resp)[:400]}")
            for u in uris:
                if "download" in u or u.endswith(".mp4"):
                    return u
            return uris[0]
        time.sleep(POLL_EVERY)
    raise RuntimeError("poll timeout")


def download(uri, dest):
    with requests.get(uri, headers={"x-goog-api-key": key}, stream=True,
                      timeout=300, allow_redirects=True) as r:
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "json" in ct or "text" in ct:
            raise RuntimeError(f"download returned {ct}: {r.text[:300]}")
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    size = dest.stat().st_size
    if size < 100_000:
        raise RuntimeError(f"file too small ({size} bytes)")
    return size


def concat(p1, p2, final):
    lst = final.with_suffix(".txt")
    lst.write_text(
        f"file '{p1.as_posix()}'\nfile '{p2.as_posix()}'\n", encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-c", "copy", str(final)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not final.exists() or final.stat().st_size < 100_000:
        cmd = ["ffmpeg", "-y", "-i", str(p1), "-i", str(p2),
               "-filter_complex",
               "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
               "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
               "-c:a", "aac", "-b:a", "192k", str(final)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {r.stderr[-400:]}")
    lst.unlink(missing_ok=True)


# -------------------------------------------------------------------- main --
if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key = api_key()
    state = load_state()
    clips = state["clips"]
    quota_hit = False

    for cid, prompt in CLIPS.items():
        rec = clips.get(cid, {})
        dest = OUT_DIR / f"{cid}.mp4"
        if rec.get("status") == "done" and dest.exists():
            continue
        log(f"=== {cid}: starting generation ({MODEL})")
        try:
            op_name, used = start_clip(key, prompt, state["params"])
            state["params"] = {k: v for k, v in used.items()
                               if k in ("durationSeconds", "resolution")}
            log(f"  op={op_name} params={state['params']}")
            uri = poll(op_name)
            size = download(uri, dest)
            clips[cid] = {"status": "done", "file": dest.name, "bytes": size}
            log(f"  DONE {dest.name} ({size/1e6:.1f} MB)")
        except Quota as e:
            clips[cid] = {"status": "quota", "error": str(e)[:300]}
            log(f"  QUOTA EXHAUSTED - stopping. Re-run to resume. {e}")
            quota_hit = True
            save_state(state)
            break
        except Fatal as e:
            clips[cid] = {"status": "fatal", "error": str(e)[:300]}
            log(f"  FATAL (auth/billing): {e}")
            save_state(state)
            sys.exit(3)
        except Exception as e:
            clips[cid] = {"status": "error", "error": str(e)[:300]}
            log(f"  ERROR: {e}")
        save_state(state)
        time.sleep(5)

    # concat finished pairs
    for vid, (a, b) in VIDEOS.items():
        fa, fb = OUT_DIR / f"{a}.mp4", OUT_DIR / f"{b}.mp4"
        final = OUT_DIR / f"{vid}_final.mp4"
        if fa.exists() and fb.exists() and not final.exists():
            try:
                concat(fa, fb, final)
                log(f"=== {vid}_final.mp4 created")
            except Exception as e:
                log(f"  CONCAT ERROR {vid}: {e}")

    done = sum(1 for c in clips.values() if c.get("status") == "done")
    log(f"SUMMARY: {done}/{len(CLIPS)} clips done. quota_hit={quota_hit}")
    if quota_hit:
        sys.exit(2)
    sys.exit(0 if done == len(CLIPS) else 1)
