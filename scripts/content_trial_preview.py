"""Preview the benefit ("free trial") detection of the content services. Writes nothing.

    python scripts/content_trial_preview.py

Runs the live content scrape (Playwright + internet, a few minutes) and prints, per
service and carrier: the fixed text, the phrase found on the page, and what a real
scrape would store. An entry whose page phrase is right can be switched on by adding
"trial_scan": True to it in CONTENT_SERVICES (scrapers/content.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper  # noqa: E402


def main():
    entries = {(e["service"], e["carrier"]): e for e in scraper.CONTENT_SERVICES}
    rows = scraper.scrape_all_content()
    print(f"{'service / carrier':<28} {'scan':<5} {'price':<10} fixed text  |  on the page  |  stored")
    for r in rows:
        e = entries[(r["service"], r["carrier"])]
        if e["strategy"] in ("not_available", "manual_price"):
            continue
        flag = "ON" if e.get("trial_scan") else "off"
        print(f"{r['service'] + ' / ' + r['carrier']:<28} {flag:<5} {str(r['price']):<10} "
              f"{e.get('free_trial')}  |  {r.get('trial_detected')}  |  {r['free_trial']}")


if __name__ == "__main__":
    main()
