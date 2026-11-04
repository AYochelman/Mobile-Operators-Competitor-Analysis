"""Yesim prices = vanillaPrice x a per-visitor geo rate (1.2 from Israel). Some
responses come back at rate 1.0, which flapped the whole catalog by x0.833 / x1.2
(Sep-Oct 2026). One run must price every page at the same, highest, rate."""
import scraper  # noqa: F401  (loads the scrapers package the way the app does)
from scrapers.yesim import _yesim_dedup, _yesim_plans_from_pp, _yesim_run_rate


def _page(rate, cents=350, days=1):
    return {
        "currency": {"code": "USD", "rate": rate},
        "standardPlans": [],
        "unlimitedPlans": [{"validityPeriod": days, "vanillaPrice": cents, "unlimited": True,
                            "dataAmount": {"inGb": "NaN"}}],
    }


def test_run_rate_ignores_fallback_pages():
    assert _yesim_run_rate([_page(1.2), _page(1.0), None, _page(1.2)], "t") == 1.2
    assert _yesim_run_rate([_page(1.0)], "t") == 1.0
    assert _yesim_run_rate([None], "t") == 1.0


def test_fallback_page_priced_at_run_rate():
    plans = _yesim_plans_from_pp(_page(1.0), 3.0, heb_override="אירופה", rate=1.2)
    assert plans[0]["original_price"] == 4.2
    assert plans[0]["price"] == 12.6


def test_dedup_keeps_cheapest_regardless_of_order():
    a = _yesim_plans_from_pp(_page(1.2, cents=400), 3.0, heb_override="צרפת")
    b = _yesim_plans_from_pp(_page(1.2, cents=350), 3.0, heb_override="צרפת")
    for order in (a + b, b + a):
        out = _yesim_dedup(order)
        assert len(out) == 1 and out[0]["original_price"] == 4.2
