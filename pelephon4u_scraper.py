"""Scrape pelephon4u.co.il — authorized Pelephone reseller (איי ג'י דאטה בע"מ).

The site lists 2-3 promotional plans on the homepage with structured pricing data.
This scraper extracts them and upserts into reseller_plans.

Usage:
  python pelephon4u_scraper.py        # scrape + upsert
"""
from __future__ import annotations

import io
import re
import sys
from datetime import datetime

import requests

# Windows console defaults to cp1252 — force UTF-8 so Hebrew prints don't crash.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

from db import init_db, save_reseller_plans

URL = "https://pelephon4u.co.il/"
RESELLER_ID = "pelephon4u"


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    return re.sub(r"\s+", " ", text).strip()


# Matches "1000GB ... 49.90 ₪ ... <variant>". Variant is bounded so the regex
# doesn't gobble adjacent sentences from the next paragraph.
_PLAN_BLOCK = re.compile(
    r"(\d{2,4})\s*GB"
    r"\s+(\d{2,3}(?:\.\d{1,2})?)\s*₪"
    r"\s+לחודש\s+למנוי"
    r"(?:"
    r"\s+(?P<intro>חודשיים ראשונים ב-\s*\d{1,3}(?:\.\d{1,2})?\s*₪\s+למנוי)|"
    r"\s+(?P<fixed>מחיר קבוע לשנה)|"
    r"\s+(?P<family>בצירוף \d+ מנויים)"
    r")?",
    re.UNICODE,
)


def scrape() -> list[dict]:
    """Fetch pelephon4u.co.il, parse the 3 plan cards on the homepage."""
    resp = requests.get(URL, timeout=15, headers={"User-Agent": "Mozilla/5.0 MOCA-reseller-scraper"})
    resp.raise_for_status()
    text = _strip_html(resp.text)

    plans = []
    seen = set()
    for m in _PLAN_BLOCK.finditer(text):
        gb = int(m.group(1))
        price = float(m.group(2))
        if (gb, price) in seen:
            continue
        seen.add((gb, price))

        # Plan name variant — intro / fixed-price / family bundle / standalone
        intro = m.group("intro")
        fixed = m.group("fixed")
        family = m.group("family")
        if intro:
            note = intro.strip()
            plan_name = f"{gb}GB 5G ב-{price} ₪ ({note})"
        elif fixed:
            plan_name = f"{gb}GB 5G ב-{price} ₪ — מחיר קבוע לשנה"
        elif family:
            plan_name = f"{gb}GB 5G ב-{price} ₪ — {family.strip()}"
        else:
            plan_name = f"{gb}GB 5G ב-{price} ₪"

        extras = [
            "5000 דקות ו-SMS",
            "מועדון הטבות 5G",
            "חיבור מיידי עם eSIM",
        ]
        if intro: extras.append(intro.strip())
        if fixed: extras.append("מחיר קבוע לשנה")
        if family: extras.append(family.strip())

        plans.append({
            "reseller_id": RESELLER_ID,
            "carrier": "pelephone",
            "plan_name": plan_name,
            "price": price,
            "data_gb": float(gb),
            "minutes": 5000,
            "sms": 5000,
            "extras": extras,
            "source_url": URL,
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
        print(f"  {p['plan_name']}  ({p['data_gb']:.0f}GB, {p['price']}₪)")
    print(f"\nUpserted {len(plans)} reseller_plans rows.")


if __name__ == "__main__":
    main()
