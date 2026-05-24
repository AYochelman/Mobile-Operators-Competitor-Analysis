import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect('data/plans.db')
cur = c.cursor()
# Look for plans that match the region slugs from SEVEN_G_REGION_SLUG_MAP
region_keywords = ['אפריקה','אסיה','אירופה','גלובלי','קריבי','מזרח התיכון','מזרח תיכון','אוסטרל','גולף','אמריקה','אוקיאני','בלקן','GCC']
cur.execute("SELECT plan_name, extras, price FROM global_plans WHERE carrier='seven_g'")
matches = {}
for r in cur.fetchall():
    if not r[1]:
        continue
    try:
        x = json.loads(r[1])
    except Exception:
        continue
    if not x:
        continue
    name = x[0]
    for kw in region_keywords:
        if kw in name:
            matches.setdefault(name, []).append(r[0])
            break

print(f"Unique region-matching destinations: {len(matches)}")
for k in sorted(matches):
    print(f"\n  {k}: {len(matches[k])} plans")
    for p in matches[k][:2]:
        print(f"    - {p}")
