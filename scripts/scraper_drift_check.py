"""
Live drift probe for the pure-HTTP scrapers (the same check the weekly
APScheduler job runs on Sundays, see run_scraper_drift_job in app.py).

    python scripts/scraper_drift_check.py               # every provider with a fixture
    python scripts/scraper_drift_check.py saily_global  # one provider
    python scripts/scraper_drift_check.py --notify      # also send the Telegram summary

For each provider it re-fetches ONLY the URLs stored in its fixture (fresh
bodies, live network), runs the parser, and compares the plan count with the
fixture's expected count. < 50% (or 0, or schema errors) = drift.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Hebrew/emoji in the report vs a cp1255 Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import scraper_fixtures as sf  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("providers", nargs="*")
    ap.add_argument("--min-ratio", type=float, default=0.5)
    ap.add_argument("--notify", action="store_true", help="send the summary to Telegram (config.json)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    providers = args.providers or sf.list_recorded()
    results = []
    for p in providers:
        r = sf.drift_check(p, min_ratio=args.min_ratio)
        results.append(r)
        if not args.json:
            flag = {"ok": "  ", "drift": "!!", "error": "XX", "skipped": "--"}[r["status"]]
            print(f"{flag} {p:<22} {r['status']:<8} live={r.get('live', '-'):<5} "
                  f"expected={r.get('expected', '-'):<5} {r.get('secs', '')}s {r.get('error', '')}", flush=True)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        print()
        print(sf.format_drift_report(results))
    if args.notify:
        import notifier
        from app import load_config
        notifier.send_notification(sf.format_drift_report(results), load_config())


if __name__ == "__main__":
    main()
