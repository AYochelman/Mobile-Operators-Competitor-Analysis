"""Dry-run report for the guarded purge of stale global_plans rows.

READ-ONLY. For every global provider prints: rows in the DB vs rows in its
latest scrape (scraped_at == MAX for that carrier), how many are older than the
grace period, destination counts, and - using the exact production logic
(db.purge_stale_global_rows in dry_run mode, with the rows of the latest scrape
standing in for the fresh list) - what the purge WOULD do right now and why.

    python scripts/global_stale_report.py            # live DB (data/plans.db)
    python scripts/global_stale_report.py path.db    # another DB file

Knobs come from db.GLOBAL_PURGE_DEFAULTS / GLOBAL_PURGE_OVERRIDES (config.json
`global_purge_*` keys are applied by app.py at scrape time, not here).
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402


def main(path):
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = ro.execute("""
        SELECT g.carrier, g.plan_name, g.extras, g.scraped_at, (g.scraped_at = m.mx) AS is_fresh
        FROM global_plans g
        JOIN (SELECT carrier, MAX(scraped_at) mx FROM global_plans GROUP BY carrier) m
          ON m.carrier = g.carrier
    """).fetchall()
    ro.close()
    latest = {}
    for carrier, name, extras, at, is_fresh in rows:
        if is_fresh:
            try:
                ex = __import__("json").loads(extras) if extras else []
            except ValueError:
                ex = []
            latest.setdefault(carrier, []).append(
                {"carrier": carrier, "plan_name": name, "extras": ex})
    fresh = [p for plans in latest.values() for p in plans]
    report = db.purge_stale_global_rows(fresh, db_path=path, dry_run=True)

    hdr = (f"{'carrier':<18}{'db':>7}{'fresh':>7}{'stale':>7}{'stale%':>8}{'elig':>7}"
           f"{'dsts':>6}{'base':>6}{'ratioR':>8}{'ratioD':>8}  decision")
    print(hdr)
    print("-" * len(hdr))
    tot = dict(db=0, fresh=0, stale=0, elig=0)
    for carrier, r in sorted(report.items(), key=lambda kv: -kv[1]["stale"]):
        pct = 100 * r["stale"] / r["db_rows"] if r["db_rows"] else 0
        print(f"{carrier:<18}{r['db_rows']:>7}{r['fresh']:>7}{r['stale']:>7}{pct:>7.1f}%{r['eligible']:>7}"
              f"{r['fresh_dests']:>6}{r['baseline_dests']:>6}{r['ratio_rows']:>8.2f}{r['ratio_dests']:>8.2f}"
              f"  {r['decision']}")
        tot["db"] += r["db_rows"]; tot["fresh"] += r["fresh"]
        tot["stale"] += r["stale"]; tot["elig"] += r["eligible"]
    would = sum(r["eligible"] for r in report.values() if r["decision"] == "complete, dry-run")
    print("-" * len(hdr))
    print(f"TOTAL rows={tot['db']} fresh={tot['fresh']} stale={tot['stale']} "
          f"({100 * tot['stale'] / tot['db']:.1f}%) eligible-by-age={tot['elig']} "
          f"-> would purge NOW: {would} rows")
    print("\n'stale' = not in the carrier's latest scrape; 'elig' = stale AND older than the "
          "grace period; 'base' = destinations seen in the window; a carrier purges only "
          "when both ratios >= min_ratio (decision 'complete, dry-run').")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else db.DB_PATH)
