# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p_:
    browser = p_.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    pg = ctx.new_page()
    
    # CELLCOM: click "לחבילות חו"ל נוספות" button and count cards
    print("="*60)
    print("CELLCOM - Clicking more button")
    print("="*60)
    pg.goto("https://cellcom.co.il/AbroadMain/lobby/", timeout=60000, wait_until="domcontentloaded")
    pg.wait_for_timeout(8000)
    
    cards_before = pg.query_selector_all(".abroad-package-client")
    print(f"Cards BEFORE clicking more: {len(cards_before)}")
    
    # Click more
    more_btns = pg.query_selector_all("button")
    for btn in more_btns:
        try:
            txt = btn.inner_text().strip()
            if "נוספות" in txt or "more" in txt.lower():
                print(f"Clicking: '{txt}'")
                btn.click()
                pg.wait_for_timeout(3000)
                break
        except: pass
    
    cards_after = pg.query_selector_all(".abroad-package-client")
    print(f"Cards AFTER clicking more: {len(cards_after)}")
    
    for i, card in enumerate(cards_after):
        title_el = card.query_selector(".abroad-package-client__title")
        dur_el = card.query_selector(".abroad-package-client__duration")
        price_el = card.query_selector("[class*='price-real']")
        data_el = card.query_selector("[class*='data--bank']")
        print(f"  Card {i+1}: name='{title_el.inner_text() if title_el else '?'}' dur='{dur_el.inner_text() if dur_el else '?'}' data='{data_el.inner_text() if data_el else '?'}'")
    
    # PARTNER: click more and count
    print("\n"+"="*60)
    print("PARTNER - Clicking more button")
    print("="*60)
    pg.goto("https://www.partner.co.il/n/roamingcellular/lobby", timeout=60000, wait_until="domcontentloaded")
    pg.wait_for_timeout(6000)
    
    cards_before = pg.query_selector_all(".package-wrapper")
    print(f"Cards BEFORE: {len(cards_before)}")
    
    more_btns = pg.query_selector_all("button")
    for btn in more_btns:
        try:
            txt = btn.inner_text().strip()
            if "נוספות" in txt or "נוספים" in txt or "more" in txt.lower():
                print(f"Clicking: '{txt}'")
                btn.click()
                pg.wait_for_timeout(3000)
                break
        except: pass
    
    cards_after = pg.query_selector_all(".package-wrapper")
    print(f"Cards AFTER: {len(cards_after)}")
    
    for i, card in enumerate(cards_after):
        name_el = card.query_selector(".package-name")
        size_el = card.query_selector(".package-size")
        price_el = card.query_selector(".price-text")
        dur_els = card.query_selector_all(".description-item .description-text")
        dur = [e.inner_text() for e in dur_els] if dur_els else []
        print(f"  Card {i+1}: name='{name_el.inner_text() if name_el else '?'}' size='{size_el.inner_text() if size_el else '?'}' price='{price_el.inner_text() if price_el else '?'}' details={dur}")
    
    browser.close()
