# -*- coding: utf-8 -*-
"""Generate a print-ready, branded QR table-stand for a Guest Connect hotel.

Reusable: edit STAND (or add entries) and run `python Hotel/qr-stands/build_stand.py`.
The QR is generated inline (no network needed at print time) and encodes the
hotel's public guest portal with ?via=qr so scans are logged as 'scan' events
for the pilot analytics. Open the HTML in a browser → Print → "Save as PDF"
(A6 portrait) → print / send to a print shop. Designed to sit in a table frame
or be folded as a tent.
"""
import qrcode

PUBLIC = "https://mocaintel.com"

STAND = {
    "slug": "brown",
    "name": "BROWN HOTELS",
    "primary": "#26170f",   # espresso
    "accent": "#d16938",    # terracotta
    "bg": "#f4f1ee",
}


def qr_svg(data, color, scale=12, border=3):
    qr = qrcode.QRCode(border=border, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    m = qr.get_matrix()
    size = len(m) * scale
    seg = []
    for y, row in enumerate(m):
        for x, dark in enumerate(row):
            if dark:
                seg.append(f"M{x*scale} {y*scale}h{scale}v{scale}h{-scale}z")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
            f'shape-rendering="crispEdges" style="width:100%;height:100%"><path d="{"".join(seg)}" '
            f'fill="{color}"/></svg>')


def build(s):
    url = f"{PUBLIC}/guest/{s['slug']}?via=qr"
    qr = qr_svg(url, s["primary"])
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{s['name']} — Guest Connect QR stand</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700;800&family=Frank+Ruhl+Libre:wght@500;700;900&display=swap" rel="stylesheet">
<style>
  :root{{--p:{s['primary']};--a:{s['accent']};--bg:{s['bg']}}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#e9e2d8;font-family:'Assistant',system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;gap:16px;padding:24px}}
  .hint{{font-size:13px;color:#6b5a48;font-weight:600;max-width:105mm;text-align:center}}
  .card{{
    width:105mm;height:148mm;background:var(--bg);border-radius:10mm;overflow:hidden;
    box-shadow:0 10px 40px rgba(40,20,5,.25);display:flex;flex-direction:column;position:relative;
  }}
  .top{{background:var(--p);color:#fff;padding:9mm 8mm 8mm;text-align:center;position:relative;overflow:hidden}}
  .top::after{{content:"";position:absolute;bottom:-30mm;right:-18mm;width:50mm;height:50mm;border-radius:50%;background:color-mix(in srgb,var(--a),transparent 70%)}}
  .brand{{font-family:'Frank Ruhl Libre',serif;font-weight:900;font-size:8mm;letter-spacing:.5mm;position:relative;z-index:1}}
  .kicker{{font-size:2.9mm;letter-spacing:2.4mm;font-weight:700;opacity:.7;margin-top:1.5mm;position:relative;z-index:1}}
  .body{{flex:1;display:flex;flex-direction:column;align-items:center;text-align:center;padding:6mm 8mm 0}}
  h1{{font-family:'Frank Ruhl Libre',serif;font-weight:700;color:var(--p);font-size:6.6mm;line-height:1.15;margin-bottom:1mm}}
  h1 .he{{display:block;font-size:5.4mm;direction:rtl}}
  .sub{{margin-top:2.5mm;max-width:86mm;display:flex;flex-direction:column;align-items:center;gap:2mm}}
  .sub div{{font-size:3.2mm;color:#6b5a48;font-weight:600;line-height:1.4}}
  .sub .en{{direction:ltr}}
  .sub .he{{direction:rtl}}
  .qr{{width:54mm;height:54mm;background:#fff;border:1.2mm solid var(--a);border-radius:6mm;padding:4mm;margin:5mm 0 3mm;box-shadow:0 4px 14px rgba(40,20,5,.12)}}
  .scan{{font-size:3.2mm;font-weight:800;color:var(--p);margin-bottom:5mm}}
  .scan .he{{direction:rtl}}
  .foot{{background:color-mix(in srgb,var(--p),transparent 92%);padding:4mm 8mm;text-align:center;border-top:.4mm solid color-mix(in srgb,var(--a),transparent 60%)}}
  .foot .pw{{font-size:3mm;font-weight:800;color:var(--p)}}
  .foot .pw b{{color:var(--a)}}
  .foot .url{{font-size:2.7mm;color:#8a7560;font-weight:600;margin-top:.8mm}}
  @media print{{
    @page{{size:A6 portrait;margin:0}}
    body{{background:#fff;padding:0;gap:0}}
    .hint{{display:none}}
    .card{{box-shadow:none;border-radius:0;width:105mm;height:148mm}}
  }}
</style>
</head>
<body>
  <div class="hint">תצוגה מקדימה — פתחו בדפדפן, Print → "Save as PDF" (A6). הקלף נכנס למסגרת שולחנית או מתקפל כ-tent. ה-QR מקודד את הפורטל של {s['name']}.</div>
  <div class="card">
    <div class="top">
      <div class="brand">{s['name']}</div>
      <div class="kicker">GUEST CONNECT</div>
    </div>
    <div class="body">
      <h1>Stay connected in Israel<span class="he">מתחברים לאינטרנט בישראל</span></h1>
      <div class="sub">
        <div class="en">Scan for the best SIM &amp; eSIM deals for your stay — compared live, updated daily.</div>
        <div class="he">סרקו להשוואת חבילות הסים וה-eSIM המשתלמות ביותר לשהות — בהשוואה חיה, מתעדכן מדי יום.</div>
      </div>
      <div class="qr">{qr}</div>
      <div class="scan">📷 Scan with your phone camera · <span class="he">סרקו עם מצלמת הטלפון</span></div>
    </div>
    <div class="foot">
      <div class="pw">Powered by <b>MOCA</b> Guest Connect ⚡</div>
      <div class="url">{PUBLIC}/guest/{s['slug']}</div>
    </div>
  </div>
</body>
</html>"""
    out = f"Hotel/qr-stands/{s['slug']}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", out, "| QR ->", url)


if __name__ == "__main__":
    build(STAND)
