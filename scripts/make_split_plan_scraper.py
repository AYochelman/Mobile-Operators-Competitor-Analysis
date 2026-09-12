"""
Build scripts/split_plan_scraper.json for split_monolith.py: assign every
top-level def/constant of scraper.py to a provider module by name keyword.
Shared helpers (parsers, FX, _make_global_plan, the scrape_all_* aggregators,
_woo_store_fetch) stay in scraper.py, which becomes the package core.

    python scripts/make_split_plan_scraper.py        # writes the plan, prints conflicts
"""
import ast
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# module -> keywords (checked in this order; first hit wins)
BUCKETS = [
    ("pelephone_globalsim", ["pelephone_globalsim", "globalsim"]),
    ("mobile019",   ["019"]),
    ("partner",     ["partner"]),
    ("pelephone",   ["pelephone", "_pele_"]),
    ("hotmobile",   ["hotmobile"]),
    ("cellcom",     ["cellcom"]),
    ("xphone",      ["xphone"]),
    ("wecom",       ["wecom"]),
    ("neptucom",    ["neptucom"]),
    ("golan",       ["golan"]),
    ("rami_levy",   ["rami_levy", "ramilevy"]),
    ("tuki",        ["tuki"]),
    ("airalo",      ["airalo"]),
    ("esimio",      ["esimio"]),
    ("esimo",       ["esimo"]),
    ("simtlv",      ["simtlv"]),
    ("terminalesim", ["terminal"]),
    ("world8",      ["world8"]),
    ("saily",       ["saily"]),
    ("holafly",     ["holafly"]),
    ("yesim",       ["yesim"]),
    ("nomad",       ["nomad"]),
    ("ubigi",       ["ubigi"]),
    ("alosim",      ["alosim"]),
    ("sparks",      ["sparks"]),
    ("voye",        ["voye"]),
    ("orbit",       ["orbit"]),
    ("travelsim",   ["travelsim"]),
    ("gomoworld",   ["gomoworld", "_gomo_"]),
    ("tasim",       ["tasim"]),
    ("gigsky",      ["gigsky"]),
    ("esimgenius",  ["esimgenius"]),
    ("nisim",       ["nisim"]),
    ("esimax",      ["esimax"]),
    ("venterrasim", ["venterra"]),
    ("simzol",      ["simzol"]),
    ("maya",        ["maya"]),
    ("bcengi",      ["bcengi"]),
    ("esim70",      ["esim70"]),
    ("jetpack",     ["jetpack"]),
    ("breez",       ["breez"]),
    ("bytesim",     ["bytesim"]),
    ("seven_g",     ["seven_g", "sevengo", "7g"]),
    ("bestconnect", ["bestconnect", "_bc_"]),
    ("esimplus",    ["esimplus"]),
    ("bnesim",      ["bnesim"]),
    ("besim",       ["besim"]),
    ("content",     ["content"]),
    ("banners",     ["banner", "popup", "news", "_is_error_page", "carrier_homepage_urls", "carrier_store_urls",
                     "_stealth_ua", "_ahash_distance", "consent_hider", "_global_popup"]),
]
DOCS = {
    "banners": "Homepage / e-store / global-provider banner screenshots, popup dismissal, Google News RSS.",
    "content": "Content services (eSIM שעון, סייבר, נורטון, שיר בהמתנה, תא קולי) across the 4 big carriers.",
}
KEEP = {"scrape_all", "scrape_all_global", "scrape_all_abroad", "_woo_store_fetch", "_make_global_plan",
        "_get_usd_to_ils", "_get_eur_to_ils", "_get_gbp_to_ils", "_ensure_event_loop", "_run_parallel_scraper",
        "_parse_price", "_parse_minutes", "_parse_gb", "_parse_days", "_parse_sms", "logger"}
# names whose keyword match is ambiguous - pin them explicitly
OVERRIDES = {
    "_ESIMPLUS_TO_SAILY": "esimplus",        # eSIM Plus's slug map onto Saily's Hebrew dict
    "_banner_019_stealth": "banners",
    "_banner_xphone_stealth": "banners",
}


def main():
    src = open(os.path.join(ROOT, "scraper.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    modules = {}
    conflicts, unassigned = [], []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [n.name]
        elif isinstance(n, ast.Assign):
            names = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if not names:
                unassigned.append(f"line {n.lineno}: non-name assignment target {ast.dump(n.targets[0])[:60]}")
                continue
        else:
            continue
        name = names[0]
        if name in KEEP:
            continue
        low = name.lower()
        hits = [OVERRIDES[name]] if name in OVERRIDES else [mod for mod, kws in BUCKETS if any(k in low for k in kws)]
        if not hits:
            unassigned.append(f"line {n.lineno}: {name}")
            continue
        if len(hits) > 1:
            conflicts.append((name, hits))
        mod = hits[0]
        modules.setdefault(mod, {"names": [], "doc": DOCS.get(mod, f"{mod} scraper (extracted from scraper.py).")})
        modules[mod]["names"].extend(names)
    plan = {"monolith": "scraper.py", "core": "scraper", "package": "scrapers", "kind": "plain",
            "local_aliases": ["logger"], "latebind_imports": ["sync_playwright"], "modules": modules}
    out = os.path.join(ROOT, "scripts", "split_plan_scraper.json")
    json.dump(plan, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"plan: {len(modules)} modules, {sum(len(m['names']) for m in modules.values())} names -> {out}")
    print("conflicts (first bucket wins):")
    for c in conflicts:
        print("  ", c)
    print("unassigned (stay in scraper.py):")
    for u in unassigned:
        print("  ", u)


if __name__ == "__main__":
    main()
