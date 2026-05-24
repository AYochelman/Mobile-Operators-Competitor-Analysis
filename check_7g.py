import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect('data/plans.db')
cur = c.cursor()
cur.execute("SELECT extras FROM global_plans WHERE carrier='seven_g'")
buckets = {}
for r in cur.fetchall():
    if not r[0]:
        continue
    try:
        x = json.loads(r[0])
    except Exception:
        continue
    if not x:
        continue
    name = x[0]
    buckets[name] = buckets.get(name, 0) + 1

print(f"Total unique destinations: {len(buckets)}")
print(f"\nDestinations with '+' or 'מדינות' (likely regions):")
for k in sorted(buckets):
    if '+' in k or 'מדינות' in k or 'אזור' in k:
        print(f"  {k}: {buckets[k]} plans")
print(f"\nFirst 10 single-country destinations:")
single = [k for k in sorted(buckets) if not ('+' in k or 'מדינות' in k or 'אזור' in k)]
for k in single[:10]:
    print(f"  {k}: {buckets[k]} plans")
print(f"\nSingle-country count: {len(single)}")
