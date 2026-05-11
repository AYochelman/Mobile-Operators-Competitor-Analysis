"""Scrape pelephone-join.co.il — authorized Pelephone reseller (לפי הדף מבצעים).

Filter rule is applied at API time (db.filter_undominated_reseller_plans), so this
scraper saves ALL plans it can find; the API decides which to expose.

Usage:
  python pelephone_join_scraper.py
"""
from __future__ import annotations

import io
import re
import sys
from datetime import datetime

import requests

from db import init_db, save_reseller_plans

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

URL = "https://pelephone-join.co.il/%D7%A4%D7%9C%D7%90%D7%A4%D7%95%D7%9F-%D7%9E%D7%91%D7%A6%D7%A2%D7%99%D7%9D/"
DISPLAY_URL = "https://pelephone-join.co.il/פלאפון-מבצעים/"
RESELLER_ID = "pelephone_join"
CARRIER_UNDERLYING = "pelephone"


def _strip_html(s: str) -> str:
    s = re.sub(r"<script[\s\S]*?</script>", " ", s)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"&#160;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Site layout: each plan block follows the pattern:
#   "<TIER>" "<DATA_GB>GB" ... "רק ב- <PRICE> ₪"
# TIER is one of: 4G / 5G / MAX (5G Max)
_PLAN_BLOCK = re.compile(
    r"(?P<tier>4G|5G|MAX)\s+"
    r"(?P<gb>\d{2,4})\s*GB"
    r"(?P<body>.{0,300}?)"
    r"(?:רק ב-|החל מ-)\s*"
    r"(?P<price>\d{1,3}(?:\.\d{1,2})?)\s*₪",
    re.UNICODE,
)


def _parse_extras(body: str) -> tuple[int | None, int | None, list[str]]:
    """From a plan block body, pull minutes/SMS and a few feature bullets."""
    minutes = None
    sms = None
    m_min = re.search(r"(\d{3,5})\s*דק", body)
    if m_min:
        minutes = int(m_min.group(1))
    m_sms = re.search(r"SMS\s*(\d{3,5})", body) or re.search(r"(\d{3,5})\s*SMS", body)
    if m_sms:
        sms = int(m_sms.group(1))

    feats = []
    if "Disney" in body or "דיסני" in body:
        feats.append("Disney+ ל-4 מסכים במקביל")
    if "תיעדוף" in body:
        feats.append("תיעדוף בגלישה דור 5 במצבי עומס")
    if "אביזרים" in body and "100" in body:
        feats.append("₪100 לרכישת אביזרים בפלאפון (במוצר מעל ₪599)")
    if "eSIM" in body:
        feats.append("חיבור מיידי עם eSIM")
    if "גלישה חופשית" in body:
        feats.append("גלישה חופשית באפליקציות נבחרות")
    if "חו" in body and ("GB" in body and "10GB" in body):
        feats.append("10GB גלישה בחו״ל")
    if "מחיר קבוע" in body:
        feats.append("מחיר קבוע")
    if "מנויים" in body:
        m_lines = re.search(r"(\d+)\s*מנויים", body)
        if m_lines:
            feats.append(f"בצירוף {m_lines.group(1)}+ מנויים")
    return minutes, sms, feats


def scrape() -> list[dict]:
    resp = requests.get(URL, timeout=15, headers={"User-Agent": "Mozilla/5.0 MOCA-reseller-scraper"})
    resp.raise_for_status()
    text = _strip_html(resp.text)

    plans = []
    seen = set()
    for m in _PLAN_BLOCK.finditer(text):
        tier = m.group("tier")
        gb = int(m.group("gb"))
        price = float(m.group("price"))
        if (tier, gb, price) in seen:
            continue
        seen.add((tier, gb, price))
        minutes, sms, feats = _parse_extras(m.group("body"))

        # Friendly plan name
        tier_label = {"4G": "4G", "5G": "5G", "MAX": "5G Max"}.get(tier, tier)
        plan_name = f"{tier_label} {gb}GB ב-{price} ₪"

        plans.append({
            "reseller_id": RESELLER_ID,
            "carrier": CARRIER_UNDERLYING,
            "plan_name": plan_name,
            "price": price,
            "data_gb": float(gb),
            "minutes": minutes,
            "sms": sms,
            "extras": feats,
            "source_url": DISPLAY_URL,
            "seen_at": datetime.now().date().isoformat(),
        })
    return plans


def main():
    init_db()
    try:
        plans = scrape()
    except requests.RequestException as e:
        print(f"FETCH FAILED: {e}")
        sys.exit(1)
    if not plans:
        print("No plans matched the pattern — site layout may have changed.")
        sys.exit(2)
    save_reseller_plans(plans)
    for p in plans:
        gb = int(p["data_gb"]) if p["data_gb"] else "?"
        print(f"  {p['plan_name']:38s} ({gb}GB, {p['price']}₪)")
    print(f"\nUpserted {len(plans)} reseller_plans rows.")


if __name__ == "__main__":
    main()
