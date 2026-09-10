"""travelsim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


def scrape_travelsim(page=None):
    """Travel Sim \u2014 static global eSIM plans (travelsimobile.co.il).
    10 plans across 3 zones (no Playwright needed).
    """
    plans = [
        # \u2500\u2500 Zone 123: Global (144 countries) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        core._make_global_plan(
            "travelsim", "Travel Mini", 19, "ILS", 19,
            data_gb=1, days=4, minutes=None, sms=None, esim=True,
            extras=[]
        ),
        core._make_global_plan(
            "travelsim", "Travel Lite", 59, "ILS", 59,
            data_gb=6, days=7, minutes=15, sms=None, esim=True,
            extras=[]
        ),
        core._make_global_plan(
            "travelsim", "Travel Plus", 69, "ILS", 69,
            data_gb=7, days=14, minutes=30, sms=None, esim=True,
            extras=[]
        ),
        core._make_global_plan(
            "travelsim", "Travel Max", 99, "ILS", 99,
            data_gb=20, days=30, minutes=100, sms=None, esim=True,
            extras=[]
        ),
        core._make_global_plan(
            "travelsim", "Travel Ultra", 139, "ILS", 139,
            data_gb=30, days=45, minutes=30, sms=None, esim=True,
            extras=[]
        ),
        core._make_global_plan(
            "travelsim", "Travel Long", 49, "ILS", 49,
            data_gb=1, days=1095, minutes=None, sms=None, esim=True,
            extras=["", "\u05d9\u05ea\u05e8\u05d4 \u05e0\u05e9\u05de\u05e8\u05ea \u05dc\u05e0\u05e1\u05d9\u05e2\u05d5\u05ea \u05d4\u05d1\u05d0\u05d5\u05ea"]  # extras[0]="" = no destination, extras[1] = feature
        ),
        # \u2500\u2500 Zone 1: \u05d0\u05e8\u05d4"\u05d1 / \u05e7\u05e0\u05d3\u05d4 / \u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea (3 countries) \u2500\u2500\u2500\u2500\u2500
        core._make_global_plan(
            "travelsim", "Travel USA 30GB", 89, "ILS", 89,
            data_gb=30, days=14, minutes=30, sms=None, esim=True,
            extras=["\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea"]
        ),
        core._make_global_plan(
            "travelsim", "Travel USA 70GB", 99, "ILS", 99,
            data_gb=70, days=30, minutes=100, sms=None, esim=True,
            extras=["\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea"]
        ),
        # \u2500\u2500 Zone 6: \u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df (5 countries) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        core._make_global_plan(
            "travelsim", "Middle East 1GB", 89, "ILS", 89,
            data_gb=1, days=30, minutes=None, sms=None, esim=True,
            extras=["\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df"]
        ),
        core._make_global_plan(
            "travelsim", "Middle East 5GB", 189, "ILS", 189,
            data_gb=5, days=30, minutes=None, sms=None, esim=True,
            extras=["\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df"]
        ),
    ]
    logger.info(f"Travel Sim: {len(plans)} plans")
    return plans
