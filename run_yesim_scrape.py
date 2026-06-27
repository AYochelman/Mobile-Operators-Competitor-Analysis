"""Run only the Yesim scraper and save to DB. Bypasses scrape_all_global's
12-min orchestration (mirrors run_7g_scrape.py). save_global_plans upserts by
(carrier, plan_name), so this is idempotent."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import scraper
from db import save_global_plans
from collections import Counter

t0 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] Yesim global (countries)...')
g = scraper.scrape_yesim_global()
print(f'  {len(g)} country plans in {time.time()-t0:.1f}s')

t1 = time.time()
r = scraper.scrape_yesim_regions()
print(f'  {len(r)} region plans in {time.time()-t1:.1f}s')

plans = g + r
dests = Counter(p['extras'][0] for p in plans if p.get('extras'))
prices = [p['original_price'] for p in plans if p.get('original_price')]
print(f'unique destinations: {len(dests)} | total plans: {len(plans)}')
if prices:
    print(f'USD price min/max: {min(prices)} / {max(prices)}')

print(f'[{time.strftime("%H:%M:%S")}] Saving to DB...')
save_global_plans(plans)
print(f'[{time.strftime("%H:%M:%S")}] Done.')
