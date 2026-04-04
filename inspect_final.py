import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

def inspect_cellcom_package():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://cellcom.co.il/production/Private/Cellular/", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        result = page.evaluate("""() => {
            const packages = document.querySelectorAll('.package');
            const findings = [];
            packages.forEach((pkg, i) => {
                const allLeaves = Array.from(pkg.querySelectorAll('*'));
                const structure = {};
                allLeaves.forEach(el => {
                    const classes = Array.from(el.classList).join(' ');
                    const text = (el.innerText || '').trim();
                    if (text && el.children.length === 0) {
                        structure[`${el.tagName}.${classes || 'no-class'}`] = text.slice(0, 100);
                    }
                });
                // Also get direct children
                const children = Array.from(pkg.children).map(c => ({
                    tag: c.tagName,
                    classes: Array.from(c.classList).join(' '),
                    text: c.innerText.slice(0, 150)
                }));

                findings.push({
                    index: i,
                    id: pkg.id,
                    classes: Array.from(pkg.classList).join(' '),
                    dataAttrs: Array.from(pkg.attributes)
                        .filter(a => a.name.startsWith('data-'))
                        .map(a => `${a.name}="${a.value}"`)
                        .join(', '),
                    childCount: pkg.children.length,
                    fullText: pkg.innerText.slice(0, 400),
                    leafStructure: structure,
                    directChildren: children
                });
            });
            return findings;
        }""")

        print(f"Cellcom - .package elements ({len(result)}):")
        for pkg in result:
            print(f"\n--- Package[{pkg['index']}] id='{pkg['id']}' class='{pkg['classes']}'")
            print(f"    data: {pkg['dataAttrs']}")
            print(f"    full text: {repr(pkg['fullText'][:300])}")
            print(f"    Direct children:")
            for child in pkg['directChildren']:
                print(f"      <{child['tag']} class='{child['classes']}'>: {repr(child['text'][:100])}")
            print(f"    Leaf structure:")
            for sel, text in pkg['leafStructure'].items():
                print(f"      {sel}: {repr(text[:80])}")

        browser.close()

def inspect_partner_subsels():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.partner.co.il/n/cellularsale/lobby", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            const cards = document.querySelectorAll('.plan-wrapper');
            const findings = [];
            cards.forEach((card, i) => {
                if (i >= 3) return;
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
                const directChildren = Array.from(card.children).map(c => ({
                    tag: c.tagName,
                    classes: Array.from(c.classList).join(' '),
                    childCount: c.children.length,
                    text: c.innerText.slice(0, 200)
                }));
                findings.push({
                    index: i,
                    fullText: card.innerText.slice(0, 500),
                    directChildren: directChildren,
                    leafStructure: structure
                });
            });
            return findings;
        }""")

        print(f"\nPartner - .plan-wrapper elements ({len(result)}):")
        for card in result:
            print(f"\n--- Card[{card['index']}] ---")
            print(f"  Full text: {repr(card['fullText'][:300])}")
            print(f"  Direct children:")
            for child in card['directChildren']:
                print(f"    <{child['tag']} class='{child['classes']}'> ({child['childCount']} children): {repr(child['text'][:100])}")
            print(f"  Leaf structure:")
            for sel, text in card['leafStructure'].items():
                print(f"    {sel}: {repr(text[:80])}")

        browser.close()

def inspect_019_subsels():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://019mobile.co.il/\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea-\u05e1\u05dc\u05d5\u05dc\u05e8/", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            // Get the first regular item (not item_hor)
            const items = Array.from(document.querySelectorAll('.item')).filter(el =>
                !el.classList.contains('item_hor') && el.innerText.includes('GB')
            );

            const findings = [];
            items.slice(0, 3).forEach((item, i) => {
                const allLeaves = Array.from(item.querySelectorAll('*'));
                const structure = {};
                allLeaves.forEach(el => {
                    const classes = Array.from(el.classList).join(' ');
                    const text = (el.innerText || '').trim();
                    if (text && el.children.length <= 1) {
                        const key = `${el.tagName}.${classes || 'no-class'}`;
                        if (!structure[key]) structure[key] = text.slice(0, 100);
                    }
                });
                const directChildren = Array.from(item.children).map(c => ({
                    tag: c.tagName,
                    classes: Array.from(c.classList).join(' '),
                    childCount: c.children.length,
                    text: c.innerText.slice(0, 200)
                }));
                findings.push({
                    index: i,
                    fullText: item.innerText.slice(0, 400),
                    directChildren: directChildren,
                    leafStructure: structure
                });
            });
            return findings;
        }""")

        print(f"\n019mobile - .item (regular plans) elements ({len(result)}):")
        for item in result:
            print(f"\n--- Item[{item['index']}] ---")
            print(f"  Full text: {repr(item['fullText'][:300])}")
            print(f"  Direct children:")
            for child in item['directChildren']:
                print(f"    <{child['tag']} class='{child['classes']}'> ({child['childCount']} children): {repr(child['text'][:100])}")
            print(f"  Leaf/near-leaf structure:")
            for sel, text in item['leafStructure'].items():
                print(f"    {sel}: {repr(text[:80])}")

        browser.close()

def inspect_pelephone_plan_items():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            // Items are .item.item1, .item.item2 etc inside .border_5
            const items = document.querySelectorAll('.border_5 .item');
            const findings = [];
            items.forEach((item, i) => {
                if (i >= 5) return;
                const allLeaves = Array.from(item.querySelectorAll('*'));
                const structure = {};
                allLeaves.forEach(el => {
                    const classes = Array.from(el.classList).join(' ');
                    const text = (el.innerText || '').trim();
                    if (text && el.children.length === 0) {
                        const key = `${el.tagName}.${classes || 'no-class'}`;
                        if (!structure[key]) structure[key] = text.slice(0, 100);
                    }
                });
                findings.push({
                    index: i,
                    classes: Array.from(item.classList).join(' '),
                    fullText: item.innerText.slice(0, 400),
                    leafStructure: structure
                });
            });
            return findings;
        }""")

        print(f"\nPelephone - .border_5 .item elements ({len(result)}):")
        for item in result:
            print(f"\n--- item[{item['index']}] class='{item['classes']}' ---")
            print(f"  Full text: {repr(item['fullText'][:300])}")
            print(f"  Leaf structure:")
            for sel, text in item['leafStructure'].items():
                print(f"    {sel}: {repr(text[:80])}")

        browser.close()

print("=== CELLCOM .package STRUCTURE ===")
inspect_cellcom_package()

print("\n\n=== PARTNER .plan-wrapper STRUCTURE ===")
inspect_partner_subsels()

print("\n\n=== 019MOBILE .item STRUCTURE ===")
inspect_019_subsels()

print("\n\n=== PELEPHONE .border_5 .item STRUCTURE ===")
inspect_pelephone_plan_items()
