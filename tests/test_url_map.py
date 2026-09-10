"""
Guard for the app.py -> api/ blueprint split (2026-09): every route that existed
in the monolith must still be registered, with the same methods, after the
split. tests/fixtures/url_map.json was captured from the monolith right
before the extraction (scripts/split_monolith.py).

When you ADD or REMOVE a route on purpose, regenerate the snapshot:
    python -c "import json; from app import app; json.dump(sorted([{'rule': r.rule, 'methods': sorted(m for m in r.methods if m not in ('HEAD','OPTIONS')), 'endpoint': r.endpoint} for r in app.url_map.iter_rules()], key=lambda d: (d['rule'], d['endpoint'])), open('tests/fixtures/url_map.json','w',encoding='utf-8'), ensure_ascii=False, indent=0)"
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _live_rules():
    from app import app
    return {(r.rule, tuple(sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS"))))
            for r in app.url_map.iter_rules()}


def _snapshot_rules():
    with open(os.path.join(HERE, "fixtures", "url_map.json"), encoding="utf-8") as f:
        return {(d["rule"], tuple(d["methods"])) for d in json.load(f)}


def test_every_snapshot_route_is_still_registered():
    live, snap = _live_rules(), _snapshot_rules()
    missing = sorted(snap - live)
    assert not missing, f"routes lost since the snapshot: {missing}"


def test_no_unexpected_new_routes_without_snapshot_update():
    live, snap = _live_rules(), _snapshot_rules()
    extra = sorted(live - snap)
    assert not extra, f"new routes not in tests/fixtures/url_map.json (regenerate it): {extra}"


def test_extracted_modules_do_not_use_bare_file_paths():
    """api/ and scrapers/ modules live one directory down; a bare __file__ there
    silently points data/ lookups at the wrong folder (caught the sparks JSON
    and the banners dir during the 2026-09 split). They must use core.__file__."""
    import glob
    import re
    root = os.path.dirname(HERE)
    bad = []
    for p in glob.glob(os.path.join(root, "api", "*.py")) + glob.glob(os.path.join(root, "scrapers", "*.py")):
        src = open(p, encoding="utf-8").read()
        for m in re.finditer(r"(?<![\w.])__file__\b", src):
            bad.append(f"{os.path.relpath(p, root)}:{src[:m.start()].count(chr(10)) + 1}")
    assert not bad, f"bare __file__ in extracted modules: {bad}"


def test_scraper_facade_reexports_every_provider():
    import scraper
    import scraper_fixtures as sf
    missing = [spec["fn"] for spec in sf.PROVIDERS.values() if not callable(getattr(scraper, spec["fn"], None))]
    assert not missing, missing
    assert callable(scraper.scrape_all_global) and callable(scraper._make_global_plan)


def test_blueprints_registered():
    from app import app
    names = set(app.blueprints)
    expected = {"esim", "mobile", "hotels", "scrape", "jobs", "banners", "engagement",
                "chat", "account", "workspaces", "history", "usage"}
    assert expected <= names, f"missing blueprints: {expected - names}"
