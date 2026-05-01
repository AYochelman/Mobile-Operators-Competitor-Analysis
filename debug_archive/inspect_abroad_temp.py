# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

OUT = []

def p(s=""):
    OUT.append(str(s))

def inspect_page(page, url, carrier):
    p()
    p("="*60)
    p(f"CARRIER: {carrier}")
    p(f"URL: {url}")
    p("="*60)
    
    try:
        page.goto(url, timeout=60000, wait_until="networkidle")
        page.wait_for_timeout(4000)
        
        # Check for "more packages" / show more buttons
        more_btns = page.query_selector_all("button, a, [role='button']")
        for btn in more_btns:
            try:
                txt = btn.inner_text().strip() if btn.is_visible() else ""
                if any(w in txt for w in ["\u05e2\u05d5\u05d3 \u05d7\u05d1\u05d9\u05dc\u05d5\u05ea", "\u05d4\u05e6\u05d2 \u05e2\u05d5\u05d3", "load more", "show more", "\u05e2\u05d5\u05d3", "\u05db\u05dc \u05d4\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea"]):
                    p(f"  FOUND MORE BUTTON: '{txt}' - clicking")
                    btn.click()
                    page.wait_for_timeout(2000)
            except:
                pass
        
        p(f"Page title: {page.title()}")
        
        body = page.content()
        p(f"\nHTML (first 10000 chars):\n{body[:10000]}")
        
    except Exception as e:
        p(f"ERROR: {e}")

with sync_playwright() as p_:
    browser = p_.chromium.launch(headless=True)
    pg = browser.new_page()
    
    sites = [
        ("https://www.pelephone.co.il/digitalsite/heb/abroad/packages/", "pelephone"),
        ("https://cellcom.co.il/AbroadMain/lobby/", "cellcom"),
        ("https://www.partner.co.il/n/roamingcellular/lobby", "partner"),
        ("https://www.hotmobile.co.il/roaming", "hotmobile"),
        ("https://019mobile.co.il/%d7%92%d7%9c%d7%99%d7%a9%d7%94-%d7%91%d7%97%d7%95%d7%9c-%d7%97%d7%91%d7%99%d7%9c%d7%94-%d7%9c%d7%97%d7%95%d7%9c-%d7%97%d7%91%d7%99%d7%9c%d7%95%d7%aa-%d7%90%d7%99%d7%a0%d7%98%d7%a8%d7%a0%d7%98/", "019"),
    ]
    
    for url, carrier in sites:
        inspect_page(pg, url, carrier)
    
    browser.close()

with open("D:/\u05d4\u05e9\u05d5\u05d5\u05d0\u05ea MASS MARKET/abroad_inspect_out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(OUT))

print("Done - output written to abroad_inspect_out.txt")
