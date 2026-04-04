import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://cellcom.co.il/production/Private/Cellular/", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    result = page.evaluate("""() => {
        const packages = document.querySelectorAll('.package');
        const findings = [];
        packages.forEach((pkg, i) => {
            // Try to find price number differently
            // Check body-package children
            const bodyPkg = pkg.querySelector('.body-package');
            const headerEl = pkg.querySelector('.header');

            // Get header children
            const headerChildren = headerEl ? Array.from(headerEl.children).map(c => ({
                tag: c.tagName, classes: Array.from(c.classList).join(' '), text: c.innerText.trim()
            })) : [];

            // Get body-package children
            const bodyChildren = bodyPkg ? Array.from(bodyPkg.children).map(c => ({
                tag: c.tagName, classes: Array.from(c.classList).join(' '), text: c.innerText.trim().slice(0,100)
            })) : [];

            // Price area
            const priceArea = pkg.querySelector('.bottom-header');
            const priceAreaHTML = priceArea ? priceArea.outerHTML.slice(0, 500) : 'no .bottom-header';

            // Try .header-features
            const headerFeatures = pkg.querySelector('.header-features');
            const headerFeaturesHTML = headerFeatures ? headerFeatures.outerHTML.slice(0, 300) : 'no .header-features';

            // Full HTML
            const fullHTML = pkg.outerHTML.slice(0, 1500);

            findings.push({
                index: i,
                id: pkg.id,
                headerChildren,
                bodyChildren,
                priceAreaHTML,
                headerFeaturesHTML,
                fullHTML
            });
        });
        return findings;
    }""")

    for item in result:
        print(f"\n=== Package[{item['index']}] id={item['id']} ===")
        print(f"Header children: {item['headerChildren']}")
        print(f"Body children: {item['bodyChildren']}")
        print(f"Price area HTML: {item['priceAreaHTML']}")
        print(f"Header features HTML: {item['headerFeaturesHTML']}")
        print(f"\nFull HTML:\n{item['fullHTML'][:1000]}")

    browser.close()
