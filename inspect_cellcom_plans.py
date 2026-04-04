import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

def inspect_cellcom():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://cellcom.co.il/production/Private/Cellular/", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # The UpgradeItemBlock are add-on services. Find actual plan cards
        result = page.evaluate("""() => {
            // Find elements containing GB amounts and prices that are plan-like
            const allEls = Array.from(document.querySelectorAll('*'));
            const findings = [];

            allEls.forEach(el => {
                const text = el.innerText || '';
                const childCount = el.children.length;
                // Plan cards: contain GB + price + moderate text
                if (text.includes('GB') && text.includes('\u20aa') && childCount >= 2 && childCount <= 15 && text.length < 800) {
                    const classes = Array.from(el.classList).join(' ');
                    const id = el.id;
                    const dataAttrs = Array.from(el.attributes)
                        .filter(a => a.name.startsWith('data-'))
                        .map(a => `${a.name}="${a.value}"`)
                        .join(', ');
                    findings.push({
                        tag: el.tagName,
                        classes: classes,
                        id: id,
                        dataAttrs: dataAttrs,
                        childCount: childCount,
                        textLen: text.length,
                        text: text.slice(0, 400)
                    });
                }
            });

            findings.sort((a, b) => a.textLen - b.textLen);
            return findings.slice(0, 30);
        }""")

        print(f"Cellcom - Elements with GB + price (sorted by text length):")
        for item in result:
            print(f"\n  <{item['tag']} class='{item['classes']}' id='{item['id']}' data=[{item['dataAttrs']}]>")
            print(f"    children={item['childCount']}, textLen={item['textLen']}")
            print(f"    text: {repr(item['text'][:300])}")

        # Also dump all distinct class names used in the document
        all_classes = page.evaluate("""() => {
            const allEls = document.querySelectorAll('*');
            const classCounts = {};
            allEls.forEach(el => {
                el.classList.forEach(cls => {
                    classCounts[cls] = (classCounts[cls] || 0) + 1;
                });
            });
            return Object.entries(classCounts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 80)
                .map(([cls, count]) => `${cls}:${count}`);
        }""")

        print("\n\nAll top classes:")
        for c in all_classes:
            print(f"  {c}")

        # Check the full page text to understand the structure
        full_text = page.evaluate("() => document.body.innerText")
        print(f"\n\nFull page text length: {len(full_text)}")
        print(full_text[:3000])

        browser.close()

inspect_cellcom()
