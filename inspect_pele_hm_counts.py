# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p_:
    browser = p_.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    pg = ctx.new_page()
    
    # PELEPHONE
    print("="*60)
    print("PELEPHONE - All cards with details")
    print("="*60)
    pg.goto("https://www.pelephone.co.il/digitalsite/heb/abroad/packages/", timeout=60000, wait_until="domcontentloaded")
    pg.wait_for_timeout(6000)
    
    # Click more button
    more = pg.query_selector(".btn_more_packs.more_show")
    if more and more.is_visible():
        print("Clicking 'לחבילות נוספות'...")
        more.click()
        pg.wait_for_timeout(2000)
    
    cards = pg.query_selector_all(".package")
    print(f"Total .package cards: {len(cards)}")
    for i, card in enumerate(cards):
        name_el = card.query_selector(".ttl")
        period_el = card.query_selector(".period")
        price_el = card.query_selector(".price")
        g_el = card.query_selector(".g")
        d_el = card.query_selector(".d")
        s_el = card.query_selector(".s")
        # check visibility
        vis = card.is_visible()
        name_txt = ""
        if name_el:
            raw = name_el.inner_text()
            name_txt = raw.split("\n")[0].strip()
        print(f"  [{i+1}] visible={vis} name='{name_txt}' period='{period_el.inner_text().strip() if period_el else '?'}' price='{price_el.inner_text().strip() if price_el else '?'}' data='{g_el.inner_text().strip() if g_el else '?'}' min='{d_el.inner_text().strip() if d_el else '-'}' sms='{s_el.inner_text().strip() if s_el else '-'}'")
    
    # HOTMOBILE
    print("\n" + "="*60)
    print("HOTMOBILE - All cards")
    print("="*60)
    pg.goto("https://www.hotmobile.co.il/roaming", timeout=60000, wait_until="domcontentloaded")
    pg.wait_for_timeout(7000)
    
    cards = pg.query_selector_all(".lobby2022_dealsItem")
    print(f"Total .lobby2022_dealsItem cards: {len(cards)}")
    
    # check for more button
    more_btn = pg.query_selector("a[onclick*='ShowMore'], button[onclick*='ShowMore'], .showMore, #showMorePackages, [class*='more']")
    if more_btn:
        print(f"More button found: {more_btn.inner_text()}")
        more_btn.click()
        pg.wait_for_timeout(2000)
        cards = pg.query_selector_all(".lobby2022_dealsItem")
        print(f"After click: {len(cards)} cards")
    
    for i, card in enumerate(cards):
        card_id = card.get_attribute("id")
        title_el = card.query_selector(".dealsItem_title h3")
        price_el = card.query_selector(".dealsItem_priceAmount strong")
        dur_el = card.query_selector(".dealsItem_priceDetails")
        details = card.query_selector_all(".dealsItem_details li")
        details_txt = [d.inner_text().strip() for d in details]
        vis = card.is_visible()
        print(f"  [{i+1}] id={card_id} vis={vis} title='{title_el.inner_text().strip() if title_el else '?'}' price='{price_el.inner_text().strip() if price_el else '?'}' dur='{dur_el.inner_text().strip() if dur_el else '?'}' details={details_txt}")
    
    browser.close()
