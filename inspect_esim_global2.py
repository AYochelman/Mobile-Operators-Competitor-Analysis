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
        page.wait_for_timeout(5000)

        # Try clicking "more" / "show all" buttons
        for btn in page.query_selector_all("button, a, [role='button'], .load-more, .show-more"):
            try:
                txt = (btn.inner_text() or "").strip()
                if any(w in txt.lower() for w in ["more", "show", "load", "עוד", "הצג", "כולם", "all", "נוספות"]):
                    if btn.is_visible():
                        print(f"  Clicking: '{txt[:60]}'")
                        btn.click()
                        page.wait_for_timeout(2000)
            except:
                pass

        print(f"\n  PAGE TITLE: {page.title()}")
        body = page.content()
        print(f"  HTML length: {len(body)}")

        # Price patterns in full HTML
        prices = re.findall(r'[$€₪£]\s*\d+[\.,]?\d*|\d+[\.,]?\d*\s*[$€₪£]|\d+\s*(?:USD|EUR|ILS|NIS)', body)
        print(f"  Price patterns found: {prices[:30]}")

        # Extended selector list
        selectors = [
            ".package", ".plan", ".plan-card", ".product-card", ".esim-plan",
            "[class*='plan']", "[class*='package']", "[class*='product']",
            ".card", ".item", ".offer", "[class*='esim']", ".price-box",
            ".bundle", "[class*='bundle']", ".tariff", "[class*='tariff']",
            "article", ".wp-block-group",
            ".sim-box", ".sim-card", ".pricing-box", ".pricing-card",
            "[class*='pricing']", "[class*='sim']", "[class*='card']",
            ".product", ".woocommerce-product", ".wc-product",
            "[class*='price']", "[class*='package-item']",
            "li.product", ".products li", ".product-item",
            ".vc_column_container", ".vc_col-sm-3", ".vc_col-sm-4",
            ".elementor-widget-wrap", ".elementor-column",
            "[class*='elementor-column']",
            ".col-md-3", ".col-md-4", ".col-sm-6",
            "table tr", "tbody tr",
        ]

        for sel in selectors:
            els = page.query_selector_all(sel)
            visible = [e for e in els if e.is_visible()]
            if 2 <= len(visible) <= 60:
                print(f"\n  Selector '{sel}': {len(visible)} visible elements")
                for i, el in enumerate(visible[:5]):
                    try:
                        txt = el.inner_text()[:400].replace('\n', ' | ')
                        cls = (el.get_attribute('class') or '')[:100]
                        print(f"    [{i}] class='{cls}'")
                        print(f"         text={repr(txt[:300])}")
                    except:
                        pass

        # Print a large section of the HTML to find plan areas
        # Search for price-related content
        print(f"\n  --- HTML SEGMENT: chars 8000-18000 ---")
        print(body[8000:18000])
        print(f"\n  --- HTML SEGMENT: chars 18000-28000 ---")
        print(body[18000:28000])

        # Search for key Hebrew plan-related keywords
        for kw in ["₪", "GB", "גיגה", "יום", "eSIM", "תוקף", "גלישה", "נפח"]:
            idx = body.find(kw)
            if idx >= 0:
                print(f"\n  Keyword '{kw}' first at {idx}: ...{body[max(0,idx-100):idx+300]}...")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

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
