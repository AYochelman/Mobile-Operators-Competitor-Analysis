# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

results = {}

def inspect_carrier(page, url, carrier, wait_sel=None, extra_wait=5000):
    print(f"\n{'='*60}\nCARRIER: {carrier}\nURL: {url}\n{'='*60}")
    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(extra_wait)
        
        # Try to dismiss cookie/privacy popups
        for sel in ["button[id*='accept']", "button[id*='cookie']", "button[class*='accept']",
                    "button[class*='cookie']", ".modal button", "#onetrust-accept-btn-handler"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    page.wait_for_timeout(500)
            except:
                pass

        print(f"Title: {page.title()}")
        print(f"Final URL: {page.url}")
        
        # Print body text (first 500 chars) to confirm we're on right page
        body_text = page.inner_text("body")[:500]
        print(f"\nBODY TEXT PREVIEW:\n{body_text}")
        
        # Print unique classes/ids on likely plan card containers
        card_candidates = page.evaluate("""() => {
            const allEls = document.querySelectorAll('[class*="card"], [class*="plan"], [class*="package"], [class*="pack"], [class*="product"], [class*="tariff"]');
            const seen = new Set();
            const results = [];
            allEls.forEach(el => {
                const key = el.tagName + '.' + el.className.split(' ').slice(0,3).join('.');
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push({
                        tag: el.tagName,
                        classes: el.className,
                        id: el.id,
                        childCount: el.children.length,
                        textSnippet: el.innerText.slice(0, 200)
                    });
                }
            });
            return results.slice(0, 20);
        }""")
        
        print(f"\nCARD CANDIDATES ({len(card_candidates)}):")
        for c in card_candidates:
            print(f"  <{c['tag']} class='{c['classes'][:80]}' id='{c['id']}' children={c['childCount']}>")
            print(f"    TEXT: {c['textSnippet'][:150]!r}")
        
        # Also look for price patterns (₪ or ש"ח)
        price_els = page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            const res = [];
            for (const el of all) {
                if (el.children.length === 0 && el.innerText && 
                    (el.innerText.includes('₪') || el.innerText.includes('\u05e9\\"\u05d7'))) {
                    res.push({
                        tag: el.tagName,
                        classes: el.className,
                        text: el.innerText.slice(0, 100),
                        parent: el.parentElement ? el.parentElement.className.slice(0,60) : ''
                    });
                }
            }
            return res.slice(0, 15);
        }""")
        
        print(f"\nPRICE ELEMENTS ({len(price_els)}):")
        for p_ in price_els:
            print(f"  <{p_['tag']} class='{p_['classes'][:60]}'> text={p_['text']!r} parent='{p_['parent']}'")
        
        # Print HTML of first few plan cards if we can identify them
        # Try common plan selectors
        for sel in [".plan-card", ".package-card", ".PackageCard", ".roaming-card",
                    "[class*='package-item']", "[class*='planCard']", "[class*='plan-item']",
                    "[class*='package_card']", "[class*='packageCard']", "[class*='tariff-card']",
                    "article", ".product-card", "[class*='prodCard']"]:
            els = page.query_selector_all(sel)
            if els:
                print(f"\n  SELECTOR '{sel}' matched {len(els)} elements")
                if els:
                    print(f"  FIRST MATCH HTML:\n{els[0].inner_html()[:1000]}")
                break
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

with sync_playwright() as p_:
    browser = p_.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
                               user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    pg = ctx.new_page()
    
    sites = [
        ("https://www.pelephone.co.il/digitalsite/heb/abroad/packages/", "pelephone", 6000),
        ("https://cellcom.co.il/AbroadMain/lobby/", "cellcom", 8000),
        ("https://www.partner.co.il/n/roamingcellular/lobby", "partner", 6000),
        ("https://www.hotmobile.co.il/roaming", "hotmobile", 6000),
        ("https://019mobile.co.il/גלישה-בחול-חבילה-לחול-חבילות-אינטרנט/", "019", 6000),
    ]
    
    for url, carrier, ew in sites:
        inspect_carrier(pg, url, carrier, extra_wait=ew)
    
    browser.close()
