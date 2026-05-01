# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p_:
    browser = p_.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    pg = ctx.new_page()
    pg.goto("https://www.hotmobile.co.il/roaming", timeout=60000, wait_until="domcontentloaded")
    pg.wait_for_timeout(7000)
    
    body = pg.inner_html("body")
    idx = body.find("Perfect Fly")
    print(f"'Perfect Fly' found at index {idx}")
    print("\nHTML around plans (5000 chars):")
    print(body[max(0,idx-500):idx+5000])
    
    browser.close()
