import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import json

def inspect_partner():
    """Partner uses Angular, need to find the right selectors"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.partner.co.il/n/cellularsale/lobby", timeout=30000, wait_until="networkidle")

        # Get all classes, looking for Angular component patterns
        result = page.evaluate("""() => {
            // Find all elements with non-empty class that appear 3-10 times
            const allEls = Array.from(document.querySelectorAll('*'));
            const classCounts = {};
            allEls.forEach(el => {
                el.classList.forEach(cls => {
                    if (cls && !cls.startsWith('ng-') && !cls.startsWith('mat-') && !cls.startsWith('cdk-')) {
                        classCounts[cls] = (classCounts[cls] || 0) + 1;
                    }
                });
            });

            const filtered = Object.entries(classCounts)
                .filter(([cls, count]) => count >= 3 && count <= 10)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 60);
            return filtered.map(([cls, count]) => ({cls, count}));
        }""")

        print("Partner - Classes appearing 3-10 times (excluding ng/mat/cdk):")
        for item in result:
            print(f"  .{item['cls']}: {item['count']}")

        # Try to find the plan cards - look for repeated sibling structures
        cards = page.evaluate("""() => {
            // Look for elements that contain price symbols and GB
            const allDivs = Array.from(document.querySelectorAll('div, section, article, li'));
            const planCards = [];
            allDivs.forEach(el => {
                const text = el.innerText || '';
                const childCount = el.children.length;
                // Plan cards likely have GB + price info + moderate length text
                if (text.includes('GB') && (text.includes('\u20aa') || text.includes('\u05dc\u05d7\u05d5\u05d3\u05e9')) && childCount >= 2 && childCount <= 15) {
                    const classes = Array.from(el.classList).join(' ');
                    const id = el.id || '';
                    const dataAttrs = Array.from(el.attributes)
                        .filter(a => a.name.startsWith('data-'))
                        .map(a => `${a.name}="${a.value}"`)
                        .join(', ');
                    planCards.push({
                        tag: el.tagName,
                        id: id,
                        classes: classes,
                        dataAttrs: dataAttrs,
                        childCount: childCount,
                        textLen: text.length,
                        sampleText: text.slice(0, 300)
                    });
                }
            });
            // Sort by text length ascending (smaller = more specific card)
            planCards.sort((a, b) => a.textLen - b.textLen);
            return planCards.slice(0, 20);
        }""")

        print("\nPartner - Elements containing GB + price:")
        for item in cards:
            print(f"  <{item['tag']} class='{item['classes']}' id='{item['id']}' data=[{item['dataAttrs']}]>")
            print(f"    Children: {item['childCount']}, TextLen: {item['textLen']}")
            print(f"    Sample: {repr(item['sampleText'][:200])}")
            print()

        # Also check data-testid and aria attributes
        testids = page.evaluate("""() => {
            const withTestId = Array.from(document.querySelectorAll('[data-testid]'));
            return withTestId.map(el => ({
                tag: el.tagName,
                testid: el.getAttribute('data-testid'),
                classes: Array.from(el.classList).join(' '),
                text: el.innerText.slice(0, 100)
            }));
        }""")
        print(f"\nPartner - data-testid elements ({len(testids)}):")
        for item in testids[:20]:
            print(f"  [{item['testid']}] <{item['tag']} class='{item['classes']}'>: {repr(item['text'][:80])}")

        browser.close()

def inspect_cellcom():
    """Cellcom - try different approaches"""
    urls_to_try = [
        "https://cellcom.co.il/production/Private/Cellular/",
        "https://www.cellcom.co.il/",
        "https://cellcom.co.il/",
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for url in urls_to_try:
            print(f"\nTrying Cellcom URL: {url}")
            page = browser.new_page()
            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                title = page.title()
                text = page.evaluate("() => document.body.innerText.slice(0, 1000)")
                print(f"  Title: {title}")
                print(f"  Text sample: {text[:500]}")

                # Check if there's a redirect or SPA
                current_url = page.url
                print(f"  Final URL: {current_url}")

                # Try to find any card-like structures
                cards = page.evaluate("""() => {
                    const allEls = document.querySelectorAll('*');
                    const classCounts = {};
                    allEls.forEach(el => {
                        el.classList.forEach(cls => {
                            classCounts[cls] = (classCounts[cls] || 0) + 1;
                        });
                    });
                    return Object.entries(classCounts)
                        .filter(([cls, count]) => count >= 2 && count <= 12)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 20)
                        .map(([cls, count]) => ({cls, count}));
                }""")
                print(f"  Classes: {cards[:10]}")

            except Exception as e:
                print(f"  Error: {e}")
            finally:
                page.close()

        browser.close()

print("=== PARTNER DEEP INSPECTION ===\n")
inspect_partner()

print("\n\n=== CELLCOM INVESTIGATION ===\n")
inspect_cellcom()
