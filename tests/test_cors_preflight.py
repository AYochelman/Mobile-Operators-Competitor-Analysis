"""CORS preflights must be cacheable (2026-11-27).

The Netlify app reaches Flask through ngrok, whose free plan allows 20,000
requests a month. Every API call carries Authorization and the
ngrok-skip-browser-warning header, so the browser sends an OPTIONS preflight
first; without Access-Control-Max-Age it repeats it for nearly every call and
doubles the request count. These tests pin the header on the three CORS
resources the frontend calls cross-origin.
"""
import pytest

from app import app as flask_app, CORS_PREFLIGHT_MAX_AGE

ORIGIN = "https://lucent-kulfi-f037ad.netlify.app"


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def _preflight(client, path):
    return client.options(path, headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization, ngrok-skip-browser-warning",
    })


@pytest.mark.parametrize("path", ["/api/plans", "/api/my-context", "/banners/partner.png",
                                  "/archive-banners/partner.png"])
def test_preflight_is_cacheable(client, path):
    resp = _preflight(client, path)
    assert resp.headers.get("Access-Control-Allow-Origin") == ORIGIN
    assert resp.headers.get("Access-Control-Max-Age") == str(CORS_PREFLIGHT_MAX_AGE)


def test_max_age_is_at_least_an_hour():
    # Chrome caps the cache at 2 hours; anything far below that gives most of the saving back.
    assert CORS_PREFLIGHT_MAX_AGE >= 3600


def test_unknown_origin_gets_no_cors_grant(client):
    resp = client.options("/api/plans", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET",
    })
    assert "Access-Control-Allow-Origin" not in resp.headers
