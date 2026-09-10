"""
One-time cleanup of the two documented flap backlogs in global_changes (2026-09-10).

  1. extras_change rows before 2026-07-15  - the phantom destination-normalization
     flap (~1,300 rows/day across 20 providers) killed centrally in
     _make_global_plan on 2026-07-14. 73,568 rows vs 37 genuine ones after the fix.
  2. breez price_change rows before 2026-07-27 - the Shopify FX leak (catalog-wide
     +-1/2 ILS moves every scrape) fixed on 2026-07-26 with the USD price basis.
     87,400 rows, 91% of them +-1..2 ILS. Real Breeze price moves in that window
     are indistinguishable from the noise, so the whole window goes.

Safety: online-backup snapshot to data/plans_pre_prune_2026_09.db first, then
DELETE + VACUUM. Idempotent. Flask may stay up (busy_timeout handles the lock).
After this, maintenance.py's weekly job keeps the change logs at 180 days.

    python scripts/db_prune_2026_09.py            # do it
    python scripts/db_prune_2026_09.py --dry-run  # counts only
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "plans.db")
BAK = os.path.join(ROOT, "data", "plans_pre_prune_2026_09.db")
DRY = "--dry-run" in sys.argv


def mb(p):
    return os.path.getsize(p) / 1048576 if os.path.exists(p) else 0


RULES = [
    ("phantom extras_change (pre 2026-07-15)",
     "FROM global_changes WHERE change_type='extras_change' AND changed_at < '2026-07-15'"),
    ("breez FX-flap price_change (pre 2026-07-27)",
     "FROM global_changes WHERE carrier='breez' AND change_type='price_change' AND changed_at < '2026-07-27'"),
]

print("DB before: %.1f MB" % mb(DB))
conn = sqlite3.connect(DB, timeout=120)
conn.execute("PRAGMA busy_timeout=120000")
for label, where in RULES:
    n = conn.execute("SELECT COUNT(*) " + where).fetchone()[0]
    print(f"  {label}: {n} rows")

if DRY:
    conn.close()
    sys.exit(0)

print("Snapshot ->", BAK)
dst = sqlite3.connect(BAK)
with dst:
    conn.backup(dst)
dst.close()

total = 0
for label, where in RULES:
    cur = conn.execute("DELETE " + where)
    total += cur.rowcount
    conn.commit()
    print(f"  deleted {cur.rowcount}: {label}")
left = conn.execute("SELECT COUNT(*) FROM global_changes").fetchone()[0]
print(f"global_changes now: {left} rows (deleted {total})")
conn.close()

print("VACUUM ...")
v = sqlite3.connect(DB, timeout=300)
v.execute("PRAGMA busy_timeout=300000")
v.execute("VACUUM")
v.close()
print("DB after: %.1f MB" % mb(DB))
print("Snapshot kept at", BAK, "- delete once verified.")
