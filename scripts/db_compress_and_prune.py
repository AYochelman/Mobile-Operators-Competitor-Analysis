"""
One-time DB maintenance (2026-06-04).

  1. Safe snapshot of plans.db (online backup API) -> data/plans_premaint.db
  2. Compress legacy archive_snapshots.plans_json rows (zlib) — lossless, ~10x
  3. Delete global_changes flap noise (removed_plan / new_plan)
  4. VACUUM to reclaim the freed space

Run AFTER restarting Flask with the new db.py (so the read path decompresses).
Idempotent: re-running skips already-compressed rows and finds no noise to delete.
"""
import os
import sqlite3
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(ROOT, "data", "plans.db")
BAK  = os.path.join(ROOT, "data", "plans_premaint.db")


def mb(path):
    return os.path.getsize(path) / 1048576 if os.path.exists(path) else 0


print("DB before: %.1f MB" % mb(DB))

# 1) Safe snapshot via the online backup API (consistent even while Flask writes)
print("Snapshotting -> %s" % BAK)
src = sqlite3.connect(DB)
dst = sqlite3.connect(BAK)
with dst:
    src.backup(dst)
dst.close()
src.close()
print("  snapshot saved: %.1f MB" % mb(BAK))

conn = sqlite3.connect(DB, timeout=120)
conn.execute("PRAGMA busy_timeout=120000")

# 2) Compress legacy archive rows (only those still stored as TEXT/str)
ids = [r[0] for r in conn.execute("SELECT id FROM archive_snapshots").fetchall()]
comp = skip = 0
for i, rid in enumerate(ids, 1):
    pj = conn.execute("SELECT plans_json FROM archive_snapshots WHERE id=?", (rid,)).fetchone()[0]
    if isinstance(pj, (bytes, bytearray)):
        skip += 1
        continue
    conn.execute(
        "UPDATE archive_snapshots SET plans_json=? WHERE id=?",
        (zlib.compress(pj.encode("utf-8"), 6), rid),
    )
    comp += 1
    if i % 200 == 0:
        conn.commit()
        print("  ...%d/%d rows" % (i, len(ids)))
conn.commit()
print("Compressed %d archive rows (skipped %d already-compressed)" % (comp, skip))

# 3) Delete global_changes flap noise (keep price_change/extras_change/details_change)
before = conn.execute("SELECT COUNT(*) FROM global_changes").fetchone()[0]
conn.execute("DELETE FROM global_changes WHERE change_type IN ('removed_plan','new_plan')")
conn.commit()
after = conn.execute("SELECT COUNT(*) FROM global_changes").fetchone()[0]
print("global_changes: %d -> %d (%d noise rows deleted)" % (before, after, before - after))
conn.close()

# 4) VACUUM — rewrites the file to reclaim freed pages
print("VACUUM (rewrites the file; ~20-60s, brief exclusive lock)...")
vac = sqlite3.connect(DB, timeout=300)
vac.execute("PRAGMA busy_timeout=300000")
vac.execute("VACUUM")
vac.close()

print("DB after:  %.1f MB" % mb(DB))
print("Done. Snapshot kept at %s — delete it once you've verified the app." % BAK)
