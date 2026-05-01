import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import re

def inspect(page, url, carrier):
    print(f"\n{'='*70}")
    print(f"CARRIER: {carrier} | URL: {url}")
    print('='*70)
    try:
        page.goto(url, timeout=45000, wait_until="networkidle")
        page.wait_for_timeout(4000)

        # Try clicking "more" buttons
        for btn in page.query_selector_all("button, a, [role='button'], .load-more, .show-more"):
            try:
                txt = (btn.inner_text() or "").strip()
                if any(w in txt.lower() for w in ["more", "show", "load", "עוד", "הצג", "כולם", "all", "נוספות"]):
                    if btn.is_visible():
                        print(f"  Clicking: '{txt[:60]}'")
                        btn.click()
                        page.wait_for_timeout(2000)
            except: pass

        # Common plan card selectors
        for sel in [".package", ".plan", ".plan-card", ".product-card", ".esim-plan",
                    "[class*='plan']", "[class*='package']", "[class*='product']",
                    ".card", ".item", ".offer", "[class*='esim']", ".price-box",
                    ".bundle", "[class*='bundle']", ".tariff", "[class*='tariff']",
                    "article", ".wp-block-group"]:
            els = page.query_selector_all(sel)
            visible = [e for e in els if e.is_visible()]
            if 2 <= len(visible) <= 50:
                print(f"\n  Selector '{sel}': {len(visible)} visible elements")
                for i, el in enumerate(visible[:6]):
                    txt = el.inner_text()[:300].replace('\n',' | ')
                    cls = (el.get_attribute('class') or '')[:80]
                    print(f"    [{i}] class='{cls}'")
                    print(f"         text={repr(txt[:200])}")

        # Print page title and HTML
        print(f"\n  PAGE TITLE: {page.title()}")
        body = page.content()
        print(f"  HTML length: {len(body)}")
        prices = re.findall(r'[$€₪£]\s*\d+[\.,]?\d*|\d+[\.,]?\d*\s*[$€₪£]|\d+\s*(?:USD|EUR|ILS|NIS)', body)
        print(f"  Price patterns: {prices[:20]}")
        print(f"\n  FULL HTML (0-8000):\n{body[:8000]}")

    except Exception as e:
        print(f"  ERROR: {e}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )

    sites = [
        ("https://simtlv.co.il/global-61-30days/?refg=159162", "simtlv"),
        ("https://world8.co.il/", "world8"),
    ]

    for url, carrier in sites:
        inspect(page, url, carrier)

    browser.close()
