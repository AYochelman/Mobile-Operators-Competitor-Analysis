"""
Offline regression tests for the pure-HTTP scrapers.

Each fixture under tests/fixtures/http/<provider>.json.gz is a capped capture
of the provider's real HTTP responses (see scraper_fixtures.py). Replaying it
must reproduce exactly the plan count recorded at capture time and every plan
must pass the schema check. No network, no Playwright, pinned FX rates.

Re-record a provider after an intentional scraper change:
    python scripts/record_scraper_fixture.py <provider>
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper_fixtures as sf  # noqa: E402

RECORDED = sf.list_recorded()


@pytest.mark.parametrize("provider", RECORDED or ["__none__"])
def test_fixture_replay_reproduces_recorded_plans(provider):
    if provider == "__none__":
        pytest.skip("no HTTP fixtures recorded yet (scripts/record_scraper_fixture.py all)")
    plans, fx = sf.replay(provider)
    expected = fx["expected_plans"]
    assert len(plans) == expected, (
        f"{provider}: replay produced {len(plans)} plans, fixture expects {expected} "
        f"(scraper changed? re-record with scripts/record_scraper_fixture.py {provider})"
    )
    assert expected > 0, f"{provider}: fixture reproduces 0 plans - re-record"
    errs = sf.validate_plans(plans, fx.get("type", "global"))
    assert not errs, f"{provider}: {errs[:5]}"
    assert all(p.get("carrier") for p in plans)


def test_registry_functions_exist():
    import scraper
    missing = [n for n, spec in sf.PROVIDERS.items() if not hasattr(scraper, spec["fn"])]
    assert not missing, f"PROVIDERS references scrape fns that no longer exist: {missing}"


def test_replay_blocks_unrecorded_urls(monkeypatch):
    """A URL outside the capture must fail like a dead network, never go live."""
    import urllib.request
    import requests
    with sf._Interceptor("replay", responses={}):
        with pytest.raises(Exception):
            urllib.request.urlopen("https://example.com/not-recorded")
        with pytest.raises(requests.ConnectionError):
            requests.get("https://example.com/not-recorded")


def test_replay_serves_recorded_body():
    import base64
    import urllib.request
    import requests
    body = b'{"ok": true}'
    responses = {
        "GET https://example.com/a": {"status": 200, "headers": {"Content-Type": "application/json"},
                                      "body_b64": base64.b64encode(body).decode()},
    }
    with sf._Interceptor("replay", responses=responses):
        with urllib.request.urlopen("https://example.com/a", timeout=5) as r:
            assert r.status == 200 and r.read() == body
        resp = requests.get("https://example.com/a", timeout=5)
        assert resp.ok and resp.json() == {"ok": True}
        assert resp.headers.get("content-type") == "application/json"


def test_validate_plans_flags_bad_rows():
    good = {"carrier": "x", "plan_name": "p", "price": 10, "data_gb": 1, "days": 7, "extras": ["יפן"]}
    assert sf.validate_plans([good], "global") == []
    bad = dict(good, price="10")
    assert sf.validate_plans([bad], "global")
    assert sf.validate_plans([dict(good, days="7")], "global")
    assert sf.validate_plans([dict(good, plan_name="")], "global")
    # a global plan without a destination is legal (multi-country bundles: travelsim, world8)
    assert sf.validate_plans([dict(good, extras=[])], "global") == []
