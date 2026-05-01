# -*- coding: utf-8 -*-
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p_:
    browser = p_.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    pg = ctx.new_page()
    
    pg.goto("https://www.hotmobile.co.il/roaming", timeout=60000, wait_until="domcontentloaded")
    pg.wait_for_timeout(7000)
    
    print(f"Title: {pg.title()}")
    print(f"URL: {pg.url}")
    
    # Print body text
    print("\nBODY TEXT (first 1000):")
    print(pg.inner_text("body")[:1000])
    
    # List all id attributes to find plan containers
    ids = pg.evaluate("""() => {
        const els = document.querySelectorAll('[id]');
        return Array.from(els).map(e => ({id: e.id, tag: e.tagName, cls: e.className.slice(0,50)}));
    }""")
    print(f"\nALL IDs ({len(ids)}):")
    for el in ids:
        print(f"  #{el['id']} <{el['tag']} class='{el['cls']}'>")
    
    # Dump all divs with "deal" in class
    deal_divs = pg.evaluate("""() => {
        const els = document.querySelectorAll('[class*="deal"], [class*="Deal"]');
        return Array.from(els).map(e => ({
            tag: e.tagName, cls: e.className.slice(0,80), 
            id: e.id,
            text: e.innerText.slice(0, 200),
            html: e.outerHTML.slice(0, 500)
        }));
    }""")
    print(f"\nDEAL ELEMENTS ({len(deal_divs)}):")
    for d in deal_divs[:10]:
        print(f"  <{d['tag']} class='{d['cls']}' id='{d['id']}'>")
        print(f"  TEXT: {d['text']!r}")
        print(f"  HTML: {d['html'][:300]}")
        print()
    
    # Also try finding plan containers
    for sel in ["#dealsContainer", "#deals-container", ".deals-container", 
                "#packagesContainer", ".packages-list", ".roaming-packages",
                "ul.deals", ".deals_list", "[class*='package']", "[class*='Package']"]:
        els = pg.query_selector_all(sel)
        if els:
            print(f"\nSELECTOR '{sel}' -> {len(els)} elements")
            print(f"FIRST ELEMENT HTML (3000 chars):\n{els[0].inner_html()[:3000]}")
            break
    
    # Print first 8000 chars of body HTML to find plan structure
    body = pg.inner_html("body")
    # Find where plan content starts
    idx = body.find("Perfect Fly")
    if idx == -1:
        idx = body.find("1GB")
    print(f"\nBODY HTML around plan content (idx={idx}, 3000 chars):")
    print(body[max(0,idx-200):idx+3000])
    
    browser.close()
