# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

def run(carrier, url, extra_wait, fn):
    print(f"\n{'='*60}\nCARRIER: {carrier}\n{'='*60}")
    with sync_playwright() as p_:
        browser = p_.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
        pg = ctx.new_page()
        try:
            pg.goto(url, timeout=60000, wait_until="domcontentloaded")
            pg.wait_for_timeout(extra_wait)
            fn(pg)
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback; traceback.print_exc()
        browser.close()

# ---- PELEPHONE ----
def pele(pg):
    # Click the "more packages" button
    more = pg.query_selector(".btn_more_packs.more_show")
    if more:
        print("Clicking 'more packages' button...")
        more.click()
        pg.wait_for_timeout(2000)
    
    cards = pg.query_selector_all(".package")
    print(f"Found {len(cards)} .package cards")
    for i, card in enumerate(cards[:3]):
        print(f"\n--- CARD {i+1} ---")
        print(card.inner_html()[:2000])

run("pelephone", "https://www.pelephone.co.il/digitalsite/heb/abroad/packages/", 6000, pele)

# ---- CELLCOM ----
def cellcom(pg):
    cards = pg.query_selector_all(".abroad-package-client")
    print(f"Found {len(cards)} .abroad-package-client cards")
    
    # Check for more button
    more_btns = pg.query_selector_all("button, [role='button']")
    for btn in more_btns:
        try:
            txt = btn.inner_text().strip()
            if txt and len(txt) < 50:
                print(f"  Button: '{txt}'")
        except: pass
    
    for i, card in enumerate(cards[:2]):
        print(f"\n--- CARD {i+1} ---")
        print(card.inner_html()[:3000])

run("cellcom", "https://cellcom.co.il/AbroadMain/lobby/", 8000, cellcom)

# ---- PARTNER ----
def partner(pg):
    cards = pg.query_selector_all(".package-wrapper")
    print(f"Found {len(cards)} .package-wrapper cards")
    
    # check for more button
    more_btns = pg.query_selector_all("button")
    for btn in more_btns:
        try:
            txt = btn.inner_text().strip()
            if txt and len(txt) < 50:
                print(f"  Button: '{txt}'")
        except: pass
    
    for i, card in enumerate(cards[:2]):
        print(f"\n--- CARD {i+1} ---")
        print(card.inner_html()[:3000])

run("partner", "https://www.partner.co.il/n/roamingcellular/lobby", 6000, partner)

# ---- HOTMOBILE ----
def hotmobile(pg):
    # No card class found — dump containers with "plan" type content
    body_html = pg.inner_html("body")
    # Find deal/plan containers by searching HTML
    import re
    # Look for sections/divs with plan data
    matches = re.findall(r'<(?:div|section|article|li)[^>]*(?:deal|plan|package|roam)[^>]*>.*?</(?:div|section|article|li)>', body_html[:50000], re.IGNORECASE | re.DOTALL)
    print(f"Regex matches: {len(matches)}")
    for m in matches[:3]:
        print(f"\n--- MATCH ---\n{m[:1500]}")
    
    # also try specific IDs/classes that appeared in body text
    for sel in ["#deals_pack", ".deal", ".deals", ".plan-item", ".roaming-plan",
                "[id^='deal']", "[class*='deal']", "[class*='roam']", ".card", ".item"]:
        els = pg.query_selector_all(sel)
        if els:
            print(f"\n  Selector '{sel}' -> {len(els)} elements")
            print(f"  FIRST HTML:\n{els[0].inner_html()[:1500]}")
            break
    
    # Print all top-level children of main/article
    main = pg.query_selector("main, #main, [role='main'], .main-content, .content")
    if main:
        print(f"\nMAIN content HTML (first 3000):\n{main.inner_html()[:3000]}")

run("hotmobile", "https://www.hotmobile.co.il/roaming", 7000, hotmobile)

# ---- 019 ----
def mobile019(pg):
    # deals_pack section found, item_pack is the card
    cards = pg.query_selector_all(".item_pack")
    print(f"Found {len(cards)} .item_pack cards")
    
    # also check for more
    more_btns = pg.query_selector_all("button, a.show-more, .load-more")
    for btn in more_btns:
        try:
            txt = btn.inner_text().strip()
            if txt and len(txt) < 60 and any(w in txt for w in ["עוד", "more", "כל"]):
                print(f"  More button: '{txt}'")
        except: pass
    
    # Print full section HTML
    section = pg.query_selector("#deals_pack, .deals_pack_flying, .deals_pack")
    if section:
        print(f"\nSection HTML (first 5000):\n{section.inner_html()[:5000]}")
    
    for i, card in enumerate(cards[:3]):
        print(f"\n--- CARD {i+1} ---")
        print(card.inner_html()[:2000])

run("019", "https://019mobile.co.il/גלישה-בחול-חבילה-לחול-חבילות-אינטרנט/", 6000, mobile019)
