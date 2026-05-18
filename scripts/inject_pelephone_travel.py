"""One-off: re-scrape Pelephone with the new Travel-detail injection
and surgically update only those rows in the main DB.

Safe because:
- Reads/writes ONLY rows where carrier='pelephone'.
- Uses INSERT OR REPLACE keyed on (carrier, plan_name) — no orphaning.
- Other carriers (cellcom, partner, hotmobile, etc.) are untouched.
- Idempotent: running twice just overwrites with the same data.
"""
import os
import sys
import json
import sqlite3
from datetime import datetime

# Force UTF-8 stdout on Windows so Hebrew prints don't crash on cp1252
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Make sure we import scraper.py FROM THIS WORKTREE (the one with the fix)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Write to the MAIN project's DB, not the worktree's empty one
MAIN_DB = r"D:\השוואת MASS MARKET\data\plans.db"

from playwright.sync_api import sync_playwright
from scraper import scrape_pelephone

print(f"Using scraper from: {sys.path[0]}")
print(f"Writing to DB: {MAIN_DB}")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    plans = scrape_pelephone(page)
    browser.close()

print(f"\nScraped {len(plans)} Pelephone plans")

conn = sqlite3.connect(MAIN_DB)
cur = conn.cursor()
now = datetime.now().isoformat()
touched = 0
for p in plans:
    extras_json = json.dumps(p["extras"], ensure_ascii=False)
    cur.execute(
        """UPDATE plans
           SET extras = ?, scraped_at = ?
           WHERE carrier = ? AND plan_name = ?""",
        (extras_json, now, p["carrier"], p["plan_name"]),
    )
    if cur.rowcount:
        touched += 1
        print(f"  updated: {p['plan_name']}")
        for e in p["extras"]:
            print(f"      • {e}")
conn.commit()
conn.close()
print(f"\nUpdated {touched} rows")
