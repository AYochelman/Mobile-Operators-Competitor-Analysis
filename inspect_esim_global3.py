import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import re

def inspect_simtlv(page):
    url = "https://simtlv.co.il/global-61-30days/?refg=159162"
    print(f"\n{'='*70}")
    print(f"SIMTLV DEEP DIVE")
    print('='*70)
    page.goto(url, timeout=45000, wait_until="networkidle")
    page.wait_for_timeout(5000)

    # Get all elementor-col-25 columns (plan cards)
    cards = page.query_selector_all(".elementor-col-25.elementor-top-column")
    print(f"  .elementor-col-25.elementor-top-column: {len(cards)} cards")
    for i, card in enumerate(cards):
        txt = card.inner_text()
        cls = card.get_attribute('class') or ''
        print(f"\n  CARD [{i}] class='{cls}'")
        print(f"  FULL TEXT:\n{txt}")
        print(f"  ---")

    # Also try elementor-price-table
    tables = page.query_selector_all(".elementor-price-table")
    print(f"\n  .elementor-price-table: {len(tables)} found")
    for i, t in enumerate(tables):
        print(f"\n  TABLE [{i}]:")
        print(t.inner_text())
        # Get inner HTML
        print(f"  HTML:\n{t.inner_html()[:2000]}")

    # Get the full HTML region around price tables
    body = page.content()
    # Find price-table sections
    idx = body.find('elementor-price-table')
    if idx >= 0:
        print(f"\n  elementor-price-table HTML (up to 6000 chars from first occurrence):")
        print(body[max(0,idx-200):idx+6000])

    # Also check WooCommerce product structure
    products = page.query_selector_all(".product, .wc-product, li.product, .type-product")
    print(f"\n  WooCommerce products found: {len(products)}")
    for i, p in enumerate(products[:10]):
        print(f"  [{i}] {p.get_attribute('class')}: {p.inner_text()[:200]}")

def inspect_world8(page):
    url = "https://world8.co.il/"
    print(f"\n{'='*70}")
    print(f"WORLD8 DEEP DIVE")
    print('='*70)
    page.goto(url, timeout=45000, wait_until="networkidle")
    page.wait_for_timeout(5000)

    # Get price cards
    cards = page.query_selector_all(".price-card.popup_btn.pricing_content")
    print(f"  .price-card.popup_btn.pricing_content: {len(cards)} cards")
    for i, card in enumerate(cards):
        txt = card.inner_text()
        cls = card.get_attribute('class') or ''
        print(f"\n  CARD [{i}] class='{cls}'")
        print(f"  FULL TEXT:\n{txt}")
        # Get inner HTML
        print(f"  HTML:\n{card.inner_html()[:2000]}")
        print(f"  ---")

    # Also check vc_col-sm-3 cards
    cols = page.query_selector_all(".vc_col-sm-3")
    print(f"\n  .vc_col-sm-3: {len(cols)} elements")
    for i, col in enumerate(cols):
        if col.is_visible():
            txt = col.inner_text()
            print(f"  [{i}] visible text: {txt[:300]}")

    # Get full HTML around price-card
    body = page.content()
    idx = body.find('price-card')
    if idx >= 0:
        print(f"\n  price-card HTML context (5000 chars):")
        print(body[max(0,idx-200):idx+5000])

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )

    inspect_simtlv(page)
    inspect_world8(page)

    browser.close()
