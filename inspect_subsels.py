import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

def inspect_cellcom_cards():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://cellcom.co.il/production/Private/Cellular/", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        result = page.evaluate("""() => {
            const cards = document.querySelectorAll('.UpgradeItemBlock');
            const findings = [];
            cards.forEach((card, i) => {
                if (i >= 5) return;
                const allEls = Array.from(card.querySelectorAll('*'));
                const structure = {};
                allEls.forEach(el => {
                    const classes = Array.from(el.classList).join(' ');
                    if (classes) {
                        structure[classes] = (el.innerText || '').trim().slice(0, 100);
                    }
                });
                findings.push({
                    cardIndex: i,
                    fullText: card.innerText.slice(0, 400),
                    structure: structure
                });
            });
            return findings;
        }""")

        print(f"Cellcom - Found {len(result)} UpgradeItemBlock cards")
        for card in result:
            print(f"\n--- Card {card['cardIndex']} ---")
            print(f"Full text: {repr(card['fullText'][:300])}")
            print("Structure:")
            for cls, text in card['structure'].items():
                if text:
                    print(f"  .{cls}: {repr(text[:80])}")

        browser.close()

def inspect_pelephone_cards():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            // Find the package containers - we know there are 3 with class 'package'
            // Let's look at the broader context
            const packages = document.querySelectorAll('[class*="package"]');
            const findings = [];
            packages.forEach((pkg, i) => {
                if (i >= 10) return;
                const allEls = Array.from(pkg.querySelectorAll('*'));
                const classes = Array.from(pkg.classList).join(' ');
                const structure = {};
                allEls.forEach(el => {
                    const elClasses = Array.from(el.classList).join(' ');
                    if (elClasses && el.children.length === 0) {
                        const text = (el.innerText || '').trim();
                        if (text) {
                            structure[elClasses] = text.slice(0, 100);
                        }
                    }
                });
                findings.push({
                    index: i,
                    classes: classes,
                    childCount: pkg.children.length,
                    fullText: pkg.innerText.slice(0, 500),
                    structure: structure
                });
            });
            return findings;
        }""")

        print(f"\nPelephone - [class*='package'] elements: {len(result)}")
        for item in result:
            print(f"\n--- package[{item['index']}] class='{item['classes']}' children={item['childCount']} ---")
            print(f"Text: {repr(item['fullText'][:300])}")
            print("Leaf structure:")
            for cls, text in item['structure'].items():
                print(f"  .{cls}: {repr(text[:80])}")

        # Also check whiteHeaderBf / pratiBF / iskiBF structure
        result2 = page.evaluate("""() => {
            const containers = ['pratiBF', 'iskiBF', 'whiteHeaderBf'];
            const findings = {};
            containers.forEach(cls => {
                const el = document.querySelector('.' + cls);
                if (el) {
                    findings[cls] = {
                        html_snippet: el.outerHTML.slice(0, 500),
                        text: el.innerText.slice(0, 300),
                        childCount: el.children.length
                    };
                }
            });
            return findings;
        }""")

        print("\nPelephone - whiteHeaderBf/pratiBF/iskiBF:")
        for cls, info in result2.items():
            print(f"  .{cls}: children={info['childCount']}")
            print(f"    text: {repr(info['text'][:200])}")

        # Find the actual individual plan items
        result3 = page.evaluate("""() => {
            // Look at the top_blue class which had GB info
            const topBlues = document.querySelectorAll('.top_blue');
            const findings = [];
            topBlues.forEach((el, i) => {
                const parent = el.parentElement;
                const grandParent = parent ? parent.parentElement : null;
                findings.push({
                    index: i,
                    top_blue_text: el.innerText.slice(0, 100),
                    parent_classes: parent ? Array.from(parent.classList).join(' ') : '',
                    parent_text: parent ? parent.innerText.slice(0, 200) : '',
                    gp_classes: grandParent ? Array.from(grandParent.classList).join(' ') : '',
                    gp_child_count: grandParent ? grandParent.children.length : 0
                });
            });
            return findings;
        }""")

        print(f"\nPelephone - top_blue elements ({len(result3)}):")
        for item in result3:
            print(f"  [{item['index']}] text={repr(item['top_blue_text'][:80])}")
            print(f"    parent: .{item['parent_classes']} | grandparent: .{item['gp_classes']} (children: {item['gp_child_count']})")
            print(f"    parent text: {repr(item['parent_text'][:150])}")

        browser.close()

def inspect_019mobile_cards():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://019mobile.co.il/\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea-\u05e1\u05dc\u05d5\u05dc\u05e8/", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            const items = document.querySelectorAll('.item');
            const findings = [];
            items.forEach((item, i) => {
                if (i >= 10) return;
                const allEls = Array.from(item.querySelectorAll('*'));
                const structure = {};
                allEls.forEach(el => {
                    const classes = Array.from(el.classList).join(' ');
                    if (classes && el.children.length === 0) {
                        const text = (el.innerText || '').trim();
                        if (text) {
                            structure[classes] = text.slice(0, 100);
                        }
                    }
                });
                findings.push({
                    index: i,
                    classes: Array.from(item.classList).join(' '),
                    childCount: item.children.length,
                    fullText: item.innerText.slice(0, 400),
                    structure: structure
                });
            });
            return findings;
        }""")

        print(f"\n019mobile - .item elements: {len(result)}")
        for item in result:
            print(f"\n--- item[{item['index']}] class='{item['classes']}' children={item['childCount']} ---")
            print(f"Text: {repr(item['fullText'][:200])}")
            print("Leaf structure:")
            for cls, text in item['structure'].items():
                if text.strip():
                    print(f"  .{cls}: {repr(text[:80])}")

        browser.close()

def inspect_hotmobile_cards():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.hotmobile.co.il/saleslobby", timeout=30000, wait_until="networkidle")

        result = page.evaluate("""() => {
            const plans = document.querySelectorAll('[class*="plan"]');
            const findings = [];
            let seen = new Set();
            plans.forEach((plan, i) => {
                const classes = Array.from(plan.classList).join(' ');
                // Find plan cards (not the outer wrapper)
                if (!seen.has(classes) && plan.innerText.includes('GB') && plan.children.length <= 10) {
                    seen.add(classes);
                    const allEls = Array.from(plan.querySelectorAll('*'));
                    const structure = {};
                    allEls.forEach(el => {
                        const elClasses = Array.from(el.classList).join(' ');
                        if (elClasses && el.children.length === 0) {
                            const text = (el.innerText || '').trim();
                            if (text) {
                                structure[elClasses] = text.slice(0, 100);
                            }
                        }
                    });
                    if (findings.length < 5) {
                        findings.push({
                            classes: classes,
                            childCount: plan.children.length,
                            fullText: plan.innerText.slice(0, 500),
                            structure: structure
                        });
                    }
                }
            });
            return findings;
        }""")

        print(f"\nHOT mobile - plan elements:")
        for item in result:
            print(f"\n--- class='{item['classes']}' children={item['childCount']} ---")
            print(f"Text: {repr(item['fullText'][:300])}")
            print("Leaf structure:")
            for cls, text in item['structure'].items():
                if text.strip():
                    print(f"  .{cls}: {repr(text[:80])}")

        browser.close()

print("=== CELLCOM CARD STRUCTURE ===")
inspect_cellcom_cards()

print("\n\n=== PELEPHONE CARD STRUCTURE ===")
inspect_pelephone_cards()

print("\n\n=== 019MOBILE CARD STRUCTURE ===")
inspect_019mobile_cards()

print("\n\n=== HOT MOBILE CARD STRUCTURE ===")
inspect_hotmobile_cards()
