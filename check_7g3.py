import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect('data/plans.db')
cur = c.cursor()
# Look at ALL distinct destinations for 7G
cur.execute("SELECT DISTINCT extras FROM global_plans WHERE carrier='seven_g'")
names = []
for r in cur.fetchall():
    if not r[0]:
        continue
    try:
        x = json.loads(r[0])
    except Exception:
        continue
    if x:
        names.append(x[0])

# Filter to ones that look like regions (keywords from SEVEN_G_REGION_SLUG_MAP)
region_keys = ['Africa', 'Asia', 'Europe', 'Global', 'Caribbean', 'Middle', 'GCC', 'Gulf', 'Oceania',
                'North America', 'South America', 'Australia & New Zealand', 'Singapore', 'Balkans',
                'Central Asia', 'China', 'אפריק', 'אסי', 'אירופ', 'גלובל', 'מזרח', 'מפרץ',
                'אוקיאני', 'אוסטר', 'בלקן', 'מרכז', 'דרום אמ', 'צפון אמ', 'קריב']
print(f"Total: {len(names)} destinations\n")
print("ALL destinations (sorted):")
for n in sorted(names):
    print(f"  {n}")
