"""Run only the Nomad scraper and save to DB (mirrors run_7g/run_yesim)."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
import scraper
from db import save_global_plans
from collections import Counter

t0 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] Nomad scrape...')
plans = scraper.scrape_nomad_global()
print(f'  {len(plans)} plans in {time.time()-t0:.1f}s')
dests = Counter(p['extras'][0] for p in plans if p.get('extras'))
prices = [p['original_price'] for p in plans if p.get('original_price')]
print(f'unique destinations: {len(dests)}', '| USD min/max:', (min(prices), max(prices)) if prices else None)
save_global_plans(plans)
print(f'[{time.strftime("%H:%M:%S")}] Saved.')
