"""Diagnose why pelephone.co.il scrapes return nothing (run ON THE BOX, read-only).

Every pelephone.co.il scraper (domestic, roaming, GlobalSIM, content) stopped
on 2026-09-21 at the same time, so the cause is the domain or the box's route
to it, not one page's selectors. This walks the layers in order and prints a
verdict for each:

  1. DNS       - A / AAAA records (the box had IPv6 disabled on 2026-09-18)
  2. TLS       - handshake + certificate expiry, verified like a browser would
  3. HTTP      - plain GET: status, server / WAF headers, body size
  4. Browser   - the 3 pages in Playwright: the OLD bare session (HeadlessChrome UA)
                 vs the NEW run_pelephone_session (stealth + real UA + he-IL),
                 reporting title, size and whether the plan cards render

Usage:
    python scripts/diagnose_pelephone.py            # all checks
    python scripts/diagnose_pelephone.py --no-browser
"""
import argparse
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOST = "www.pelephone.co.il"
PAGES = [
    ("domestic", "https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/",
     ".border_5 .item"),
    ("abroad", "https://www.pelephone.co.il/digitalsite/heb/abroad/packages/", ".package"),
    ("globalsim", "https://www.pelephone.co.il/digitalsite/heb/abroad/global-sim/",
     ".packs > div[id^='p'] .pack_top .price"),
]
WAF_HEADERS = ("server", "x-iinfo", "x-cdn", "cf-ray", "x-akamai-transformed",
               "akamai-grn", "x-sucuri-id", "set-cookie")


def check_dns():
    print("== 1. DNS")
    for fam, label in ((socket.AF_INET, "A"), (socket.AF_INET6, "AAAA")):
        try:
            addrs = sorted({ai[4][0] for ai in socket.getaddrinfo(HOST, 443, fam)})
            print(f"   {label:4} {', '.join(addrs)}")
        except socket.gaierror as exc:
            print(f"   {label:4} none ({exc})")


def check_tls():
    print("== 2. TLS")
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((HOST, 443), timeout=15) as sock:
            with ctx.wrap_socket(sock, server_hostname=HOST) as tls:
                cert = tls.getpeercert()
                not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                days = (not_after - datetime.now(timezone.utc)).days
                issuer = dict(x[0] for x in cert.get("issuer", ()))
                print(f"   OK  {tls.version()}  issuer={issuer.get('organizationName')}  "
                      f"expires {not_after:%Y-%m-%d} ({days} days)")
    except ssl.SSLCertVerificationError as exc:
        print(f"   FAIL certificate does not verify: {exc}")
        print("        -> browsers on the box reject it too; the banner job survives only "
              "because it sets ignore_https_errors")
    except Exception as exc:
        print(f"   FAIL {type(exc).__name__}: {exc}")


def check_http():
    print("== 3. HTTP (plain GET, real Chrome UA)")
    from scrapers.pelephone import PELEPHONE_UA
    for label, url, _ in PAGES:
        req = urllib.request.Request(url, headers={
            "User-Agent": PELEPHONE_UA, "Accept-Language": "he-IL,he;q=0.9",
            "Accept": "text/html,application/xhtml+xml"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body, status, headers = r.read(), r.status, r.headers
        except urllib.error.HTTPError as exc:
            body, status, headers = exc.read(), exc.code, exc.headers
        except Exception as exc:
            print(f"   {label:9} FAIL {type(exc).__name__}: {exc}")
            continue
        waf = {h: (headers.get(h) or "")[:60] for h in WAF_HEADERS if headers.get(h)}
        print(f"   {label:9} HTTP {status}  {len(body):>7} bytes  {time.time() - t0:.1f}s  {waf}")


def check_browser():
    print("== 4. Browser")
    import scraper as core

    def probe(page, url, selector):
        page.goto(url, timeout=40000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector(selector, timeout=20000)
            cards = len(page.query_selector_all(selector))
        except Exception:
            cards = 0
        body = page.evaluate("() => (document.body && document.body.innerText) || ''")
        return cards, page.title(), len(page.content()), " ".join(body.split())[:120]

    core._ensure_event_loop()
    print("   -- OLD: bare browser.new_page() (what the scrapers used until now)")
    with core.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page()
        for label, url, sel in PAGES:
            try:
                cards, title, size, snip = probe(page, url, sel)
                print(f"   {label:9} cards={cards:<3} html={size:>7}  title={title!r}  body={snip!r}")
            except Exception as exc:
                print(f"   {label:9} FAIL {type(exc).__name__}: {str(exc)[:160]}")
        browser.close()

    print("   -- NEW: run_pelephone_session (stealth + real UA + he-IL)")
    for label, url, sel in PAGES:
        try:
            cards, title, size, snip = core.run_pelephone_session(lambda pg: probe(pg, url, sel))
            print(f"   {label:9} cards={cards:<3} html={size:>7}  title={title!r}  body={snip!r}")
        except Exception as exc:
            print(f"   {label:9} FAIL {type(exc).__name__}: {str(exc)[:160]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-browser", action="store_true", help="skip the Playwright checks")
    args = ap.parse_args()
    check_dns()
    check_tls()
    check_http()
    if not args.no_browser:
        check_browser()
    print("\nReading it: cards>0 under NEW = fixed by this change (restart Flask). "
          "cards=0 under both with a challenge/blocked title = WAF on the box's IP. "
          "TLS FAIL = certificate problem on Pelephone's side or the box's trust store.")


if __name__ == "__main__":
    main()
