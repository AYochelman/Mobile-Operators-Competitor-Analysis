"""
Record (or re-record) HTTP fixtures for the pure-HTTP scrapers.

    python scripts/record_scraper_fixture.py saily_global          # one provider
    python scripts/record_scraper_fixture.py all                   # every registered provider
    python scripts/record_scraper_fixture.py all --missing         # only providers with no fixture yet
    python scripts/record_scraper_fixture.py esim70_global --cap 20

Each run hits the provider LIVE once, stores the first --cap distinct URLs
(default 12) under tests/fixtures/http/<provider>.json.gz, immediately replays
the capture offline and records the reproduced plan count as `expected_plans`.
A scraper that launches Playwright is marked `playwright: true` (no fixture).

Re-record when a scraper is intentionally changed (new parsing, new endpoint)
or when the weekly drift check reports a provider whose site changed and the
scraper has been fixed.
"""
import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Hebrew/emoji in the report vs a cp1255 Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import scraper_fixtures as sf  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("providers", nargs="+", help="provider ids (see scraper_fixtures.PROVIDERS) or 'all'")
    ap.add_argument("--cap", type=int, default=sf.DEFAULT_CAP, help="distinct URLs to capture")
    ap.add_argument("--missing", action="store_true", help="skip providers that already have a fixture")
    ap.add_argument("--no-verify", action="store_true", help="skip the replay verification pass")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    names = list(sf.PROVIDERS) if args.providers == ["all"] else args.providers
    unknown = [n for n in names if n not in sf.PROVIDERS]
    if unknown:
        sys.exit(f"unknown provider(s): {unknown}. Known: {', '.join(sf.PROVIDERS)}")

    rows = []
    for name in names:
        if args.missing and os.path.exists(sf.fixture_path(name)):
            continue
        t0 = time.time()
        try:
            meta = sf.record(name, cap=args.cap, verify=not args.no_verify)
        except Exception as exc:  # a scraper that raises is itself a finding
            rows.append((name, "ERROR", 0, 0, 0, f"{type(exc).__name__}: {exc}"[:90]))
            print(f"  {name:<22} ERROR {exc}", flush=True)
            continue
        size_kb = os.path.getsize(sf.fixture_path(name)) // 1024
        if meta.get("playwright"):
            rows.append((name, "playwright", 0, 0, size_kb, "launches a browser - no HTTP fixture"))
        else:
            note = ""
            if meta.get("validation_errors"):
                note = "VALIDATION: " + meta["validation_errors"][0][:60]
            elif meta.get("expected_plans") != meta.get("recorded_plans"):
                note = f"replay {meta['expected_plans']} != live {meta['recorded_plans']}"
            elif meta.get("truncated"):
                note = f"{len(meta['truncated'])} body(ies) truncated at {sf.MAX_BODY // 1048576}MB"
            rows.append((name, "ok" if not note else "check", meta.get("recorded_plans", 0),
                         len(meta.get("responses", {})), size_kb, note))
        print(f"  {name:<22} {rows[-1][1]:<10} plans={rows[-1][2]:<5} urls={rows[-1][3]:<3} "
              f"{size_kb:>6} KB  {time.time() - t0:5.1f}s  {rows[-1][5]}", flush=True)

    print("\nSummary:")
    print(f"  {'provider':<22} {'status':<10} {'plans':>6} {'urls':>5} {'KB':>7}  note")
    for r in rows:
        print(f"  {r[0]:<22} {r[1]:<10} {r[2]:>6} {r[3]:>5} {r[4]:>7}  {r[5]}")
    total_kb = sum(r[4] for r in rows)
    print(f"\n  fixtures on disk: {total_kb} KB total")


if __name__ == "__main__":
    main()
