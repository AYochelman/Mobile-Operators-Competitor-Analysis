import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import json

def inspect_site(url, name):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="networkidle")
        except Exception as e:
            print(f"  [Warning] networkidle timeout for {name}: {e}, trying domcontentloaded...")
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
            except Exception as e2:
                print(f"  [Error] domcontentloaded also failed for {name}: {e2}")
                browser.close()
                return {"name": name, "url": url, "title": "ERROR", "selectors": {}, "text_sample": str(e2)}

        result = page.evaluate("""() => {
            const candidates = [
                '[class*="plan"]', '[class*="package"]', '[class*="offer"]',
                '[class*="tariff"]', '[class*="bundle"]', '[class*="card"]',
                '[data-testid*="plan"]', '[data-testid*="package"]',
                '.plan', '.package', '.offer', '.product-card',
                '[class*="\u05d7\u05d1\u05d9\u05dc\u05d4"]', '[class*="\u05de\u05e1\u05dc\u05d5\u05dc"]',
            ];

            const findings = {};
            candidates.forEach(sel => {
                try {
                    const els = document.querySelectorAll(sel);
                    if (els.length >= 2 && els.length <= 20) {
                        findings[sel] = {
                            count: els.length,
                            sample_text: els[0].innerText.slice(0, 200)
                        };
                    }
                } catch(e) {}
            });
            return findings;
        }""")

        title = page.title()
        text = page.evaluate("() => document.body.innerText.slice(0, 3000)")

        browser.close()
        return {"name": name, "url": url, "title": title, "selectors": result, "text_sample": text}

def deep_inspect(url, name):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="networkidle")
        except Exception:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

        class_result = page.evaluate("""() => {
            const allEls = document.querySelectorAll('*');
            const classCounts = {};
            allEls.forEach(el => {
                el.classList.forEach(cls => {
                    classCounts[cls] = (classCounts[cls] || 0) + 1;
                });
            });
            return Object.entries(classCounts)
                .filter(([cls, count]) => count >= 3 && count <= 15)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 50)
                .map(([cls, count]) => ({cls, count}));
        }""")

        price_result = page.evaluate("""() => {
            const allEls = document.querySelectorAll('*');
            const priceEls = [];
            allEls.forEach(el => {
                if (el.children.length === 0) {
                    const text = el.innerText || '';
                    if (text.includes('\u20aa') || /\\d+\\s*\u05e9"\u05d7/.test(text)) {
                        const classes = Array.from(el.classList).join(' ');
                        const parentClasses = el.parentElement ? Array.from(el.parentElement.classList).join(' ') : '';
                        priceEls.push({
                            tag: el.tagName,
                            classes: classes,
                            parentClasses: parentClasses,
                            text: text.slice(0, 100)
                        });
                    }
                }
            });
            return priceEls.slice(0, 20);
        }""")

        gb_result = page.evaluate("""() => {
            const allEls = document.querySelectorAll('*');
            const gbEls = [];
            allEls.forEach(el => {
                if (el.children.length === 0) {
                    const text = el.innerText || '';
                    if (/\\d+\\s*(GB|\\u05d2"\\u05d1|\\u05d2\\u05d9\\u05d2\\u05d4)/i.test(text) || text.includes('\u05d2\u05d9\u05d2\u05d4')) {
                        const classes = Array.from(el.classList).join(' ');
                        const parentClasses = el.parentElement ? Array.from(el.parentElement.classList).join(' ') : '';
                        gbEls.push({
                            tag: el.tagName,
                            classes: classes,
                            parentClasses: parentClasses,
                            text: text.slice(0, 100)
                        });
                    }
                }
            });
            return gbEls.slice(0, 20);
        }""")

        # Also get the full outer HTML structure of any repeated card-like containers
        structure_result = page.evaluate("""() => {
            // Find containers that have similar children patterns (repeated cards)
            const allEls = Array.from(document.querySelectorAll('*'));
            const containers = [];
            allEls.forEach(el => {
                const children = Array.from(el.children);
                if (children.length >= 3 && children.length <= 12) {
                    // Check if children have similar class patterns (repeating cards)
                    const childClasses = children.map(c => Array.from(c.classList).sort().join(' '));
                    const uniqueClasses = new Set(childClasses);
                    if (uniqueClasses.size <= 3 && children.length >= 3) {
                        const classes = Array.from(el.classList).join(' ');
                        if (classes) {
                            containers.push({
                                tag: el.tagName,
                                classes: classes,
                                childCount: children.length,
                                childClasses: Array.from(uniqueClasses).slice(0, 3),
                                sampleText: el.innerText.slice(0, 300)
                            });
                        }
                    }
                }
            });
            return containers.slice(0, 20);
        }""")

        browser.close()
        return {
            "name": name,
            "url": url,
            "frequent_classes": class_result,
            "price_elements": price_result,
            "gb_elements": gb_result,
            "repeated_containers": structure_result
        }

carriers = [
    ("https://www.partner.co.il/n/cellularsale/lobby", "partner"),
    ("https://www.pelephone.co.il/ds/heb/packages/mobile-packages/join-pelephone-online/", "pelephone"),
    ("https://www.hotmobile.co.il/saleslobby", "hotmobile"),
    ("https://cellcom.co.il/production/Private/Cellular/", "cellcom"),
    ("https://019mobile.co.il/\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea-\u05e1\u05dc\u05d5\u05dc\u05e8/", "mobile019"),
]

print("=== PHASE 1: Initial Selector Discovery ===\n")
initial_results = {}
for url, name in carriers:
    print(f"\n{'='*60}")
    print(f"CARRIER: {name}")
    print(f"URL: {url}")
    try:
        result = inspect_site(url, name)
        initial_results[name] = result
        print(f"Title: {result['title']}")
        print(f"\nSelectors found ({len(result['selectors'])} matches):")
        for sel, info in result['selectors'].items():
            print(f"  {sel}: {info['count']} elements")
            print(f"    Sample: {repr(info['sample_text'][:150])}")
        print(f"\nPage text sample:\n{result['text_sample'][:1500]}")
    except Exception as e:
        import traceback
        print(f"\nERROR for {name}: {e}")
        traceback.print_exc()
        initial_results[name] = {"error": str(e)}

print("\n\n=== PHASE 2: Deep Inspection ===\n")
deep_results = {}
for url, name in carriers:
    print(f"\n{'='*60}")
    print(f"DEEP INSPECT: {name}")
    try:
        result = deep_inspect(url, name)
        deep_results[name] = result
        print(f"\nFrequent classes (3-15 occurrences):")
        for item in result['frequent_classes'][:20]:
            print(f"  .{item['cls']}: {item['count']} times")
        print(f"\nPrice-containing elements:")
        for item in result['price_elements'][:10]:
            print(f"  <{item['tag']} class='{item['classes']}'> parent='{item['parentClasses']}'")
            print(f"    Text: {repr(item['text'])}")
        print(f"\nGB-containing elements:")
        for item in result['gb_elements'][:10]:
            print(f"  <{item['tag']} class='{item['classes']}'> parent='{item['parentClasses']}'")
            print(f"    Text: {repr(item['text'])}")
        print(f"\nRepeated containers (likely card grids):")
        for item in result['repeated_containers'][:10]:
            print(f"  <{item['tag']} class='{item['classes']}'> {item['childCount']} children")
            print(f"    Child classes: {item['childClasses']}")
            print(f"    Sample: {repr(item['sampleText'][:200])}")
    except Exception as e:
        import traceback
        print(f"ERROR deep inspecting {name}: {e}")
        traceback.print_exc()

# Save all raw results for analysis
with open("D:/\u05d4\u05e9\u05d5\u05d5\u05d0\u05ea MASS MARKET/inspect_raw_results.json", "w", encoding="utf-8") as f:
    json.dump({"initial": initial_results, "deep": deep_results}, f, ensure_ascii=False, indent=2)
print("\n\nRaw results saved to inspect_raw_results.json")
