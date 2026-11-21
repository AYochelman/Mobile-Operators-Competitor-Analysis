"""Offline tests for the scrapers repaired on 2026-11-20 (bytesim JSON-LD,
world8 new markup). Markup below is cut from the live pages. Breeze and Holafly
are covered by tests/test_shopify_catalog.py."""
import json

import scraper  # noqa: F401  (loads the scrapers package the way the app does)
from scrapers import bytesim, world8


def _clean(name):
    return name.replace("‏", "")


# ── bytesim ────────────────────────────────────────────────────────────────

def _bytesim_page(group):
    return ('<html><script type="application/ld+json">{"@type":"Organization","name":"ByteSIM"}</script>'
            '<script type="application/ld+json">\n' + json.dumps(group) + "\n</script></html>")


def _variant(name, price, currency="USD", availability="https://schema.org/InStock"):
    return {"@type": "Product", "name": name,
            "offers": {"@type": "Offer", "price": price, "priceCurrency": currency,
                       "availability": availability}}


def test_bytesim_reads_variants_from_json_ld():
    page = _bytesim_page({
        "@context": "https://schema.org/", "@type": "ProductGroup", "name": "Thailand eSIM",
        "hasVariant": [
            _variant("Thailand eSIM - 500MB/Day/1", "2.90"),
            _variant("Thailand eSIM - Total 5GB/10", "5.90"),
            _variant("Thailand eSIM - Unlimited Lite - 10Mbps Throughout/3", "5.90"),
            _variant("Thailand eSIM - Unlimited Plus - 1GB/day Full Speed, then 10Mbps/3", "7.90"),
            _variant("Thailand eSIM - Total 3GB/7", "9.99", currency="ILS"),
            _variant("Thailand eSIM - Total 1GB/7", "1.00",
                     availability="https://schema.org/OutOfStock"),
        ],
    })
    variants = bytesim._bytesim_variants_from_html(page)
    assert variants == [
        {"o1": "500MB/Day", "o2": "1", "price": 290},
        {"o1": "Total 5GB", "o2": "10", "price": 590},
        {"o1": "Unlimited Lite - 10Mbps Throughout", "o2": "3", "price": 590},
        {"o1": "Unlimited Plus - 1GB/day Full Speed, then 10Mbps", "o2": "3", "price": 790},
    ]
    plans = bytesim._bytesim_build_plans(variants, "תאילנד", "תאילנד", 3.0)
    names = {_clean(p["plan_name"]): p["original_price"] for p in plans}
    assert names["תאילנד – 500MB/יום – 1 יום"] == 2.9
    assert names["תאילנד – 5GB – 10 ימים"] == 5.9
    assert len(names) == 4


def test_bytesim_page_without_product_group():
    assert bytesim._bytesim_variants_from_html("<html><body>redirected home</body></html>") is None


# ── world8 ─────────────────────────────────────────────────────────────────

WORLD8_HTML = (
    '<div class="wf-cards">'
    '<article class="wf-card" data-price="79"><input class="wf-radio" type="radio" value="79">'
    '<h2 class="wf-title">גלישה בלבד</h2><div class="wf-top">'
    '<a class="wf-pill" href="#" data-dialog-open="countries-2">70+ יעדים עיקריים</a>'
    '<ul class="wf-icons"><li class="wf-i-data" title="גלישה"><span class="sr">גלישה</span></li></ul></div>'
    '<div class="wf-data"><div class="wf-main"><p class="wf-big en">15GB</p>'
    '<p class="wf-note">ל-30 יום מהנחיתה</p></div><div class="wf-extra is-empty" aria-hidden="true"></div></div>'
    '<p class="wf-price"><b class="en">79</b><span>₪</span></p></article>'
    '<article class="wf-card is-best has-stats" data-price="99">'
    '<span class="wf-ribbon">הנמכרת ביותר!</span><h2 class="wf-title">גלישה ושיחות</h2>'
    '<div class="wf-top"><a class="wf-pill" href="#">70+ יעדים עיקריים</a>'
    '<ul class="wf-icons"><li class="wf-i-sms" title="סמס"><span class="sr">סמס</span></li></ul></div>'
    '<div class="wf-data"><div class="wf-main"><p class="wf-big en">10GB</p>'
    '<p class="wf-note">ל-30 יום מהנחיתה</p></div>'
    '<div class="wf-extra"><ul><li>60 דקות</li><li>60 סמס</li><li>1GB</li></ul></div>'
    '<p class="wf-note wf-extra-note">שימוש מעורב ל-4 שנים</p></div>'
    '<p class="wf-price"><b class="en">99</b><span>₪</span></p></article>'
    '<article class="wf-card has-stats no-plus" data-price="100"><h2 class="wf-title">כיסוי רחב</h2>'
    '<div class="wf-top"><a class="wf-pill" href="#">110+ יעדים</a></div>'
    '<div class="wf-data"><div class="wf-main"><p class="wf-big en">2GB</p></div>'
    '<div class="wf-extra is-swapped"><ul><li>או 120 דקות או 120 סמס</li></ul></div>'
    '<p class="wf-note">שימוש מעורב ל-4 שנים</p></div>'
    '<p class="wf-price"><b class="en">100</b><span>₪</span></p></article></div>'
)


def test_world8_new_markup():
    plans = {p["plan_name"]: p for p in world8._parse_world8_html(WORLD8_HTML)}
    assert set(plans) == {"גלישה בלבד", "גלישה ושיחות", "כיסוי רחב"}
    data = plans["גלישה בלבד"]
    assert (data["price"], data["data_gb"], data["days"], data["minutes"]) == (79, 15.0, 30, None)
    assert data["currency"] == "ILS" and "70+ יעדים עיקריים" in data["extras"]
    calls = plans["גלישה ושיחות"]
    assert (calls["price"], calls["data_gb"], calls["minutes"], calls["sms"]) == (99, 10.0, 60, 60)
    assert "60 דקות + 60 סמס + 1GB" in calls["extras"] and "הנמכרת ביותר!" in calls["extras"]
    wide = plans["כיסוי רחב"]
    assert (wide["price"], wide["data_gb"], wide["days"]) == (100, 2.0, None)
    assert "או 120 דקות או 120 סמס" in wide["extras"]


def test_world8_old_markup_gives_nothing():
    assert world8._parse_world8_html('<div class="price-card popup_btn"><h3>x</h3></div>') == []
