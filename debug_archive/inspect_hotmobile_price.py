import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

def inspect_hotmobile():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.hotmobile.co.il/saleslobby", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            // container plan* are the individual plan cards
            const cards = document.querySelectorAll('.package-wrap.js-plan-filter');
            const findings = [];
            cards.forEach((card, i) => {
                if (i >= 4) return;
                // Find the inner container with plan ID
                const innerContainer = card.querySelector('[class*="container plan"]');
                const innerClasses = innerContainer ? Array.from(innerContainer.classList).join(' ') : 'none';

                // Get all leaf nodes
                const allLeaves = Array.from(card.querySelectorAll('*'));
                const structure = {};
                allLeaves.forEach(el => {
                    const classes = Array.from(el.classList).join(' ');
                    const text = (el.innerText || '').trim();
                    if (text && el.children.length === 0) {
                        const key = `${el.tagName}.${classes || 'no-class'}`;
                        if (!structure[key]) structure[key] = text.slice(0, 100);
                    }
                });

                // Specifically get price-box structure
                const priceBox = card.querySelector('.price-box');
                const priceBoxHTML = priceBox ? priceBox.outerHTML.slice(0, 500) : 'not found';
                const currentPrice = card.querySelector('.current-price');
                const currentPriceText = currentPrice ? currentPrice.innerText : 'not found';
                const currentPriceHTML = currentPrice ? currentPrice.outerHTML : 'not found';

                // Feature names (GB)
                const featureNames = Array.from(card.querySelectorAll('.feature-name')).map(el => el.innerText.trim());

                findings.push({
                    index: i,
                    innerClasses: innerClasses,
                    fullText: card.innerText.slice(0, 400),
                    priceBoxHTML: priceBoxHTML,
                    currentPriceText: currentPriceText,
                    currentPriceHTML: currentPriceHTML.slice(0, 300),
                    featureNames: featureNames,
                    leafStructure: structure
                });
            });
            return findings;
        }""")

        print(f"HOT Mobile - .package-wrap.js-plan-filter cards ({len(result)}):")
        for card in result:
            print(f"\n--- Card[{card['index']}] inner: '{card['innerClasses']}' ---")
            print(f"  Full text: {repr(card['fullText'][:250])}")
            print(f"  Feature names: {card['featureNames']}")
            print(f"  current-price text: {repr(card['currentPriceText'])}")
            print(f"  current-price HTML: {card['currentPriceHTML']}")
            print(f"  price-box HTML: {card['priceBoxHTML'][:300]}")
            print(f"  Leaf structure:")
            for sel, text in card['leafStructure'].items():
                print(f"    {sel}: {repr(text[:80])}")

        browser.close()

def inspect_019_price():
    """019mobile price is split: .nis (₪) + a number + .small (cents part)"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://019mobile.co.il/\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea-\u05e1\u05dc\u05d5\u05dc\u05e8/", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            const items = Array.from(document.querySelectorAll('.item')).filter(el =>
                !el.classList.contains('item_hor') && el.innerText.includes('GB')
            );

            const findings = [];
            items.slice(0, 3).forEach((item, i) => {
                const priceEl = item.querySelector('.price');
                const priceHTML = priceEl ? priceEl.outerHTML.slice(0, 300) : 'not found';
                const priceText = priceEl ? priceEl.innerText : 'not found';

                // Get name
                const nameEl = item.querySelector('h3.title') || item.querySelector('.table-cell');
                const name = nameEl ? nameEl.innerText.trim() : 'not found';

                // Get GB - it's in a <strong> inside an <li>
                const gbEls = Array.from(item.querySelectorAll('li strong'));
                const gbTexts = gbEls.map(el => el.innerText.trim());

                // Get blist items
                const blistItems = Array.from(item.querySelectorAll('.blist li')).map(el => el.innerText.trim());

                findings.push({
                    index: i,
                    name: name,
                    priceText: priceText,
                    priceHTML: priceHTML,
                    gbTexts: gbTexts,
                    blistItems: blistItems
                });
            });
            return findings;
        }""")

        print(f"\n019mobile - price structure:")
        for item in result:
            print(f"\n--- item[{item['index']}] ---")
            print(f"  name: {repr(item['name'])}")
            print(f"  priceText: {repr(item['priceText'])}")
            print(f"  priceHTML: {item['priceHTML']}")
            print(f"  gbTexts: {item['gbTexts']}")
            print(f"  blistItems: {item['blistItems']}")

        browser.close()

print("=== HOT MOBILE PRICE/STRUCTURE INSPECTION ===")
inspect_hotmobile()

print("\n\n=== 019MOBILE PRICE STRUCTURE ===")
inspect_019_price()
