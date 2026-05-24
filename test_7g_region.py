import sys, urllib.request as ur, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import scraper

# Test parsing the Africa region page
slug = 'africa'
url = f'https://7g.app/he/esim/region/{slug}'
req = ur.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
r = ur.urlopen(req, timeout=15)
html = r.read().decode('utf-8')
print(f'STATUS: {r.status}')
print(f'LEN: {len(html)}')

m = re.search(r'<title>([^<]+)</title>', html)
print(f'TITLE: {m.group(1) if m else "NONE"}')

# Try parsing
plans = scraper._parse_seven_g_page(html, 3.7, 'Africa')
print(f'\nPLANS PARSED: {len(plans)}')
for p in plans[:3]:
    print(f'  {p}')

# Check raw text content for GB markers
from html.parser import HTMLParser
class TE(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
    def handle_data(self, d):
        if d.strip():
            self.texts.append(d.strip())
p = TE(); p.feed(html)
print(f'\nText fragments: {len(p.texts)}')
gb_lines = [(i, t) for i,t in enumerate(p.texts) if re.match(r'^\d+(?:\.\d+)?\s*GB$', t, re.I)]
print(f'GB-matching lines: {len(gb_lines)}')
for i, t in gb_lines[:5]:
    print(f'  [{i}] {t}  next: {p.texts[i+1] if i+1<len(p.texts) else "?"}  next2: {p.texts[i+2] if i+2<len(p.texts) else "?"}')
