# -*- coding: utf-8 -*-
"""Generate the 3D "interface" hero image used in the MOCA welcome email.

Renders a polished, on-brand MOCA mock dashboard (the same visual language as
mass-market-app/public/demo-3d.html, variant 1 "browser tilt") into a crisp,
transparent PNG with the 3D perspective + shadow baked in -- because email
clients (Gmail/Outlook/Apple Mail) strip CSS 3D transforms, the only reliable
cross-client way to show a 3D visual is a pre-rendered raster <img>.

Output:
  mass-market-app/public/email/welcome-hero.png   (deployed to Netlify ->
                                                    https://mocaintel.com/email/welcome-hero.png)

Also (best-effort, once templates/welcome_email.html + notifier._build_welcome_html
exist) renders a full-email preview to docs/email/welcome-preview.{html,png}.

Re-runnable: `python scripts/build_welcome_hero.py`
Deps already in requirements.txt: playwright==1.58.0, Pillow==12.1.1
"""
import base64
import io
import os
import sys

from PIL import Image, ImageOps
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_DIR = os.path.join(ROOT, "mass-market-app", "public", "logos")
OUT_DIR = os.path.join(ROOT, "mass-market-app", "public", "email")
PREVIEW_DIR = os.path.join(ROOT, "docs", "email")
HERO_PNG = os.path.join(OUT_DIR, "welcome-hero.png")

# carrier id -> (Hebrew label, logo filename)
CARRIERS = {
    "cellcom":   ("סלקום",  "cellcom.png"),
    "partner":   ("פרטנר",  "partner.png"),
    "pelephone": ("פלאפון", "pelephone.png"),
    "hotmobile": ("הוט",      "hotmobile.png"),
    "golan":     ("גולן",      "golan.png"),
    "rami_levy": ("רמי לוי", "rami_levy.png"),
}


def _data_uri(path):
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return "data:image/png;base64," + b64


def _build_html():
    logos = {cid: _data_uri(os.path.join(LOGO_DIR, fn)) for cid, (_, fn) in CARRIERS.items()}

    def chip(cid):
        label, _ = CARRIERS[cid]
        return (f'<div class="chip"><span class="av"><img src="{logos[cid]}" alt=""></span>'
                f'<span class="cl">{label}</span></div>')

    def card(cid, name, price, meta, delta, direction):
        return (f'<div class="pcard"><div class="pt">'
                f'<img src="{logos[cid]}" alt="">'
                f'<div><div class="pname">{name}</div><div class="pmeta">{meta}</div></div></div>'
                f'<div class="pb"><div class="price">₪{price}<small>/חודש</small></div>'
                f'<span class="delta {direction}">{delta}</span></div></div>')

    def bar(height, label, win=False):
        cls = "b win" if win else "b"
        return f'<div class="{cls}" style="height:{height}%"><span>{label}</span></div>'

    chips = "".join(chip(c) for c in ["cellcom", "partner", "pelephone", "hotmobile", "golan", "rami_levy"])
    cards = (
        card("partner", "פרטנר · 200GB", "35",
             "200GB · ללא הגבלה · SMS חופשי", "▲ 10", "up")
        + card("cellcom", "סלקום · ללא הגבלה", "49",
               "ללא הגבלה · 5G · SMS חופשי", "▼ 15", "down")
    )
    bars = (
        bar(40, "רמי לוי", True) + bar(58, "גולן")
        + bar(72, "פרטנר") + bar(66, "הוט")
        + bar(88, "סלקום") + bar(80, "פלאפון")
    )

    # nav items for the slim sidebar (label, active)
    nav = [
        ("דשבורד", True),
        ("השוואה", False),
        ("מיצוב", False),
        ("התראות", False),
        ("סיכום מנהלים", False),
        ("ארכיון", False),
    ]
    nav_html = "".join(
        f'<div class="nav {"on" if act else ""}"><span class="ni"></span>{lbl}</div>'
        for lbl, act in nav
    )

    css = """
    *{box-sizing:border-box;margin:0;padding:0}
    html,body{background:transparent}
    body{font-family:'Assistant',system-ui,Arial,sans-serif;-webkit-font-smoothing:antialiased}

    /* capture frame: transparent padding so the box-shadow is not clipped */
    #capture{display:inline-block;padding:160px 210px 240px 210px;background:transparent}
    .stage{perspective:1700px}
    .frame{transform-style:preserve-3d;transform:rotateY(-14deg) rotateX(6deg)}

    .deck{width:760px;background:#fff;border:1px solid #e6d4bd;border-radius:18px;overflow:hidden;
      box-shadow:0 2px 6px rgba(60,40,20,.10),
                 30px 36px 56px -26px rgba(60,40,20,.50),
                 56px 74px 96px -48px rgba(60,40,20,.34)}

    /* browser chrome */
    .chrome{display:flex;align-items:center;gap:7px;padding:11px 14px;
      background:linear-gradient(#fbf4ea,#f3e7d4);border-bottom:1px solid #e6d4bd}
    .chrome .dot{width:11px;height:11px;border-radius:50%}
    .chrome .r{background:#e0654f}.chrome .y{background:#e3aa3c}.chrome .g{background:#5aa451}
    .chrome .url{flex:1;margin-inline-start:10px;background:#fff;border:1px solid #e6d4bd;border-radius:9px;
      font-size:12px;color:#a08468;padding:5px 12px;text-align:center;direction:ltr}

    .app{display:flex;background:#faf5ee}

    /* slim sidebar (RTL -> physical right because it is the first flex child) */
    .side{width:140px;background:#fffdfa;border-inline-start:1px solid #efe2cf;padding:14px 12px}
    .brand{display:flex;align-items:center;gap:7px;font-family:'Frank Ruhl Libre',serif;
      font-weight:900;font-size:18px;color:#5c3317;margin-bottom:18px}
    .brand .bolt{display:grid;place-items:center;width:26px;height:26px;border-radius:8px;
      background:#c9622f;color:#fff;font-size:14px}
    .nav{display:flex;align-items:center;gap:8px;font-size:12.5px;color:#8a6a4a;
      padding:7px 9px;border-radius:9px;margin-bottom:3px}
    .nav .ni{width:8px;height:8px;border-radius:3px;background:#d9c4a8}
    .nav.on{background:#f3e7d4;color:#4a2a13;font-weight:700}
    .nav.on .ni{background:#c9622f}

    .main{flex:1;padding:16px 18px 20px}
    .topbar{display:flex;align-items:center;gap:10px;margin-bottom:16px}
    .srch{flex:1;background:#f9f4ee;border:1px solid #e0cdb5;border-radius:10px;
      padding:8px 12px;color:#a08468;font-size:12.5px}
    .live{display:flex;align-items:center;gap:6px;font-weight:800;font-size:11px;
      color:#4a7c3f;letter-spacing:.6px}
    .live i{width:9px;height:9px;border-radius:50%;background:#4a7c3f;
      box-shadow:0 0 0 4px rgba(74,124,63,.18)}

    .head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:14px}
    .head .kick{font-family:'Frank Ruhl Libre',serif;font-weight:700;font-size:19px;color:#4a2a13}
    .head .date{font-size:11px;color:#a08468}

    .chips{display:flex;gap:13px;margin-bottom:18px}
    .chip{display:flex;flex-direction:column;align-items:center;gap:5px;width:48px}
    .chip .av{width:44px;height:44px;border-radius:50%;background:#fff;border:1.5px solid #ead9c2;
      display:grid;place-items:center;overflow:hidden;box-shadow:0 1px 4px rgba(60,40,20,.10)}
    .chip .av img{width:74%;height:74%;object-fit:contain}
    .chip .cl{font-size:10.5px;color:#8a6a4a;white-space:nowrap}

    .cards{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
    .pcard{background:#fff;border:1px solid #efe2cf;border-radius:13px;padding:12px 13px}
    .pcard .pt{display:flex;align-items:center;gap:9px;margin-bottom:11px}
    .pcard .pt img{width:30px;height:30px;border-radius:8px;object-fit:contain;background:#fff;
      border:1px solid #ead9c2;padding:3px}
    .pcard .pname{font-weight:700;font-size:13.5px;color:#4a2a13;line-height:1.2}
    .pcard .pmeta{font-size:10.5px;color:#a08468;margin-top:2px}
    .pcard .pb{display:flex;align-items:center;justify-content:space-between}
    .pcard .price{font-family:'Frank Ruhl Libre',serif;font-weight:900;font-size:23px;color:#3b1f0d}
    .pcard .price small{font-weight:600;font-size:11px;color:#a08468}
    .delta{font-size:11px;font-weight:800;padding:3px 9px;border-radius:999px;color:#fff}
    .delta.up{background:#b4472d}
    .delta.down{background:#4a7c3f}

    .chart{background:#fff;border:1px solid #efe2cf;border-radius:13px;padding:13px 14px}
    .chart .ct{display:flex;justify-content:space-between;font-weight:700;font-size:12px;
      color:#8a6a4a;margin-bottom:12px}
    .chart .ct b{color:#4a7c3f}
    .bars{display:flex;align-items:flex-end;gap:11px;height:74px}
    .bars .b{flex:1;border-radius:6px 6px 3px 3px;position:relative;background:#e8d5bc}
    .bars .b.win{background:linear-gradient(#c9622f,#a84f24)}
    .bars .b span{position:absolute;top:-15px;left:50%;transform:translateX(-50%);
      font-size:9.5px;color:#a08468;white-space:nowrap}
    """

    body = f"""
    <div id="capture"><div class="stage"><div class="frame">
      <div class="deck">
        <div class="chrome">
          <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
          <span class="url">app.mocaintel.com/dashboard</span>
        </div>
        <div class="app">
          <div class="side">
            <div class="brand"><span class="bolt">⚡</span>MOCA</div>
            {nav_html}
          </div>
          <div class="main">
            <div class="topbar">
              <div class="srch">חיפוש חבילה, מתחרה או מדינה…</div>
              <div class="live"><i></i>LIVE</div>
            </div>
            <div class="head">
              <div class="kick">מעקב מחירים · Mass Market</div>
              <div class="date">סריקה אחרונה · היום 07:30</div>
            </div>
            <div class="chips">{chips}</div>
            <div class="cards">{cards}</div>
            <div class="chart">
              <div class="ct"><span>₪ לכל GB — מי הכי משתלם</span><b>רמי לוי מוביל</b></div>
              <div class="bars">{bars}</div>
            </div>
          </div>
        </div>
      </div>
    </div></div></div>
    """

    return f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700;800&family=Frank+Ruhl+Libre:wght@700;900&display=swap" rel="stylesheet">
<style>{css}</style></head><body>{body}</body></html>"""


def render_hero():
    os.makedirs(OUT_DIR, exist_ok=True)
    html = _build_html()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1100}, device_scale_factor=2)
        page.set_content(html, wait_until="networkidle")
        try:
            page.evaluate("document.fonts.ready")
        except Exception:
            pass
        page.wait_for_timeout(500)
        raw = page.locator("#capture").screenshot(omit_background=True)
        browser.close()

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    img = ImageOps.expand(img, border=36, fill=(0, 0, 0, 0))  # small breathing margin
    img.save(HERO_PNG, format="PNG", optimize=True)
    kb = os.path.getsize(HERO_PNG) / 1024
    print(f"[hero] {HERO_PNG}  {img.width}x{img.height}px  {kb:.0f} KB")
    return HERO_PNG


def render_preview():
    """Best-effort: render the full welcome email (needs notifier + template)."""
    sys.path.insert(0, ROOT)
    try:
        from notifier import _build_welcome_html
    except Exception as e:  # template/function not ready yet -> skip
        print(f"[preview] skipped ({e})")
        return None

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    hero_url = "file:///" + HERO_PNG.replace("\\", "/")
    html = _build_welcome_html(
        workspace_name="סלקום",  # sample workspace
        role_he="מנהל",
        hero_img_url=hero_url,
        app_url="https://mocaintel.com",
        primary="#5c3317",
        secondary="#a08060",
    )
    preview_html = os.path.join(PREVIEW_DIR, "welcome-preview.html")
    with open(preview_html, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"[preview] {preview_html}")
    file_url = "file:///" + preview_html.replace("\\", "/")
    outputs = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # desktop (680px) + mobile (390px ~ iPhone logical width)
        for name, width in (("welcome-preview.png", 680), ("welcome-preview-mobile.png", 390)):
            page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=2)
            page.goto(file_url, wait_until="networkidle")
            try:
                page.evaluate("document.fonts.ready")
            except Exception:
                pass
            page.wait_for_timeout(400)
            out = os.path.join(PREVIEW_DIR, name)
            page.screenshot(path=out, full_page=True)
            page.close()
            outputs[name] = out
            print(f"[preview] {out}")
        browser.close()
    return outputs.get("welcome-preview.png")


if __name__ == "__main__":
    render_hero()
    render_preview()
