"""ByteSim lists several unlimited tiers per product; each needs its own plan_name
or the stored price flips with the order the store returns its variants in."""
import scraper  # noqa: F401  (loads the scrapers package the way the app does)
from scrapers.bytesim import _bytesim_build_plans, _dedupe_cheapest


def _names(plans):
    # _make_global_plan adds RLM marks before digits for BiDi; compare without them
    return {p["plan_name"].replace("\u200f", ""): p["original_price"] for p in plans}


def _v(o1, days, cents):
    return {"o1": o1, "o2": str(days), "price": cents}


def test_unlimited_tiers_get_distinct_names():
    variants = [
        _v("Unlimited Lite - 10Mbps Throughout", 3, 590),
        _v("Unlimited Plus - 1GB/day Full Speed, then 10Mbps", 3, 790),
        _v("Unlimited Max - No Throttle + Thai Number", 3, 1290),
        _v("Total 5GB", 3, 450),
    ]
    plans = _bytesim_build_plans(variants, "תאילנד", "תאילנד", 3.0)
    names = _names(plans)
    assert len(names) == 4
    assert names["תאילנד – ללא הגבלה לייט – 3 ימים"] == 5.9
    assert names["תאילנד – ללא הגבלה פלוס – 3 ימים"] == 7.9
    assert names["תאילנד – ללא הגבלה מקס + מספר מקומי – 3 ימים"] == 12.9
    assert names["תאילנד – 5GB – 3 ימים"] == 4.5


def test_throttle_and_calls_variants():
    variants = [
        _v("Unlimited Data (2GB/Day then 5Mbps)", 5, 3300),
        _v("Unlimited Data (3GB/Day then 1Mbps)", 5, 2290),
        _v("Unlimited Data (3GB/Day then 1Mbps) + Local Calls & SMS", 5, 2690),
        _v("IT&E Unlimited Data (No Throttle) + Local Calls & SMS", 5, 3800),
    ]
    names = set(_names(_bytesim_build_plans(variants, "גואם", "גואם", 3.0)))
    assert names == {
        "גואם – ללא הגבלה 2GB/יום ואז 5Mbps – 5 ימים",
        "גואם – ללא הגבלה 3GB/יום ואז 1Mbps – 5 ימים",
        "גואם – ללא הגבלה 3GB/יום ואז 1Mbps + שיחות ו-SMS – 5 ימים",
        "גואם – ללא הגבלה ללא האטה + שיחות ו-SMS – 5 ימים",
    }


def test_same_daily_cap_different_throttle_speeds():
    variants = [
        _v("Unlimited Data (10Mbps after 1GB/Day usage)", 7, 1990),
        _v("Unlimited Data (512kbps after 1GB/Day usage)", 7, 1290),
    ]
    names = set(_names(_bytesim_build_plans(variants, "סינגפור", "סינגפור", 3.0)))
    assert names == {
        "סינגפור – ללא הגבלה 1GB/יום ואז 10Mbps – 7 ימים",
        "סינגפור – ללא הגבלה 1GB/יום ואז 512kbps – 7 ימים",
    }


def test_5g_tier():
    variants = [_v("Unlimited Data (*5G Network)", 7, 2500), _v("Unlimited Lite", 7, 1500)]
    names = set(_names(_bytesim_build_plans(variants, "קוריאה", "קוריאה", 3.0)))
    assert "קוריאה – ללא הגבלה 5G – 7 ימים" in names


def test_single_unlimited_keeps_its_plain_name_and_order_does_not_matter():
    a = [_v("Unlimited Data", 7, 1500), _v("1GB/Day", 7, 900)]
    names = set(_names(_bytesim_build_plans(a, "יפן", "יפן", 3.0)))
    assert "יפן – ללא הגבלה – 7 ימים" in names
    dup = [_v("Unlimited Data", 7, 1500), _v("Unlimited Data", 7, 1200)]
    for order in (dup, dup[::-1]):
        (p,) = _bytesim_build_plans(order, "יפן", "יפן", 3.0)
        assert p["original_price"] == 12.0


def test_dedupe_cheapest_across_pages():
    p1 = {"plan_name": "סן מרטן – 1GB – 7 ימים", "original_price": 9.0}
    p2 = {"plan_name": "סן מרטן – 1GB – 7 ימים", "original_price": 7.0}
    assert _dedupe_cheapest([p1, p2]) == [p2]
