"""Run only the 7G scraper and save to DB. Bypasses scrape_all_global's 12-min orchestration."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import scraper
from db import save_global_plans

t0 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] Starting 7G scrape...')
plans = scraper.scrape_seven_g_global()
print(f'[{time.strftime("%H:%M:%S")}] Got {len(plans)} plans in {time.time()-t0:.1f}s')

# Group by destination to verify regions are included
from collections import Counter
dest_counts = Counter(p['extras'][0] for p in plans if p.get('extras'))
print(f'\nUnique destinations: {len(dest_counts)}')
print(f'\nRegional destinations (English-named or with "+"/"areas"/"מדינות"):')
for d in sorted(dest_counts):
    if any(k in d for k in ['+', 'areas', 'Africa', 'Asia', 'Europe', 'Global', 'America', 'Caribbean', 'Middle', 'GCC', 'Gulf', 'Oceania', 'Australia & New Zealand', 'Singapore', 'Balkans', 'Central Asia', 'China mainland']):
        print(f'  {d}: {dest_counts[d]} plans')

# Save to DB
print(f'\n[{time.strftime("%H:%M:%S")}] Saving to DB...')
save_global_plans(plans)
print(f'[{time.strftime("%H:%M:%S")}] Done')
