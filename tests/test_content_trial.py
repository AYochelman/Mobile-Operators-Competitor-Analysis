"""Benefit ("free trial") detection for the content services - pure text, no browser."""
import pytest

from content_trial import extract_free_trial, resolve_free_trial

# Real page text, we-com.co.il/norton360 (read 2026-11-24).
WECOM_NORTON = (
    "שירות הגנת סייבר 360 "
    "למכשירי סלולר\nמבית\n"
    "₪7.90 לחודש בלבד, "
    "וחודש ראשון מתנה.\n"
    "דף הבית > שירות נורטון"
)


@pytest.mark.parametrize("text,expected", [
    ("חצי שנה מתנה ואחר כך 19.90",
     "חצי שנה מתנה"),
    ("הצטרפו וקבלו חודשיים מתנה!",
     "חודשיים מתנה"),
    ("3 חודשים ללא עלות",
     "3 חודשים ללא עלות"),
    ("3 חודשים ראשונים  חינם",
     "3 חודשים ראשונים חינם"),
    ("חודש ראשון חינם",
     "חודש ראשון חינם"),
    ("חינם לחצי שנה",
     "חינם לחצי שנה"),
    ("מתנה ל-6 חודשים",
     "מתנה ל-6 חודשים"),
    ("ללא עלות למשך 3 חודשים",
     "ללא עלות למשך 3 חודשים"),
    ("50% הנחה ל-4 חודשים",
     "50% הנחה ל-4 חודשים"),
])
def test_phrases(text, expected):
    assert extract_free_trial(text) == expected


@pytest.mark.parametrize("text", [
    "",
    "₪19.90 לחודש בלבד",          # a price per month is not a benefit
    "19.90 ש\"ח לחודש חינם",  # "לחודש חינם": the ל prefix blocks it
    "משלוח חינם לכל הארץ",
])
def test_no_benefit(text):
    assert extract_free_trial(text) is None


def test_discount_period_is_never_cut_mid_word():
    # "50% הנחה לחודשים הראשונים" used to come back as "50% הנחה לחודש"
    assert extract_free_trial("50% הנחה לחודשים הראשונים") is None
    assert extract_free_trial("50% הנחה לחודש הראשון") == "50% הנחה לחודש הראשון"


def test_real_wecom_page():
    assert extract_free_trial(WECOM_NORTON, "7.90") == \
        "חודש ראשון מתנה"


def test_keyword_missing_from_page():
    assert extract_free_trial(WECOM_NORTON, "99.90") is None


def test_nearest_to_keyword_wins_on_a_shared_page():
    cyber = "הגנת סייבר"
    norton = "Norton"
    page = (cyber + " 3 חודשים חינם " + "x" * 200
            + " " + norton + " חודש ראשון חינם")
    assert extract_free_trial(page, cyber) == "3 חודשים חינם"
    assert extract_free_trial(page, norton) == "חודש ראשון חינם"


def test_resolve():
    half = "חצי שנה מתנה"
    two = "חודשיים מתנה"
    # not switched on -> the fixed text, whatever the page says
    assert resolve_free_trial({"free_trial": two}, half) == (two, "default")
    # switched on -> the page wins
    assert resolve_free_trial({"free_trial": two, "trial_scan": True}, half) == (half, "page")
    # switched on, nothing detected -> the fixed text
    assert resolve_free_trial({"free_trial": two, "trial_scan": True}, None) == (two, "default")
    # the " | ..." tail of the fixed text survives
    tail = "חודש ראשון חינם | X"
    assert resolve_free_trial({"free_trial": tail, "trial_scan": True}, half) == (half + " | X", "page")


# --- wiring: scrape_all_content with a fake browser ---------------------------------------

class _FakePage:
    def __init__(self, pages):
        self.pages, self.url = pages, None

    def goto(self, url, timeout=None):
        self.url = url

    def wait_for_load_state(self, *a, **k):
        pass

    def wait_for_timeout(self, *a, **k):
        pass

    def evaluate(self, *a, **k):
        return self.pages.get(self.url, "")

    def inner_text(self, selector):
        return self.pages.get(self.url, "")


class _FakePlaywright:
    def __init__(self, pages):
        self.pages = pages
        self.chromium = self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def launch(self, **k):
        return self

    def new_page(self, **k):
        return _FakePage(self.pages)

    def close(self):
        pass


def _run(monkeypatch, pages, pelephone=None):
    import scraper
    from scrapers import content
    monkeypatch.setattr(scraper, "sync_playwright", lambda: _FakePlaywright(pages))
    monkeypatch.setattr(scraper, "_cellcom_hub_price", lambda *a, **k: None)
    monkeypatch.setattr(scraper, "_cellcom_faq_esim_price", lambda *a, **k: None)
    monkeypatch.setattr(content, "_pelephone_content_prices", lambda: pelephone or {})
    return {(r["service"], r["carrier"]): r for r in scraper.scrape_all_content()}


def test_scrape_stores_the_page_benefit_when_switched_on(monkeypatch):
    month3 = "3 חודשים חינם"
    rows = _run(monkeypatch, {
        "https://we-com.co.il/norton360/": "₪7.90 לחודש, " + month3,
        # partner eSIM is NOT switched on: the page phrase is reported, not stored
        "https://www.partner.co.il/u/esim": "14.90 ₪ " + month3,
    })
    wecom = rows[("נורטון", "wecom")]
    assert wecom["price"] == "₪7.90" and wecom["free_trial"] == month3
    partner = rows[("eSIM שעון", "partner")]
    assert partner["trial_detected"] == month3
    assert partner["free_trial"] == "ללא תקופת חינם"


def test_pelephone_own_session_benefit(monkeypatch):
    import scraper
    year = "שנה מתנה"
    key = ("eSIM שעון", "pelephone")
    entry = next(e for e in scraper.CONTENT_SERVICES if (e["service"], e["carrier"]) == key)
    rows = _run(monkeypatch, {}, pelephone={key[0]: ("₪19.90", year, entry)})
    assert rows[key]["price"] == "₪19.90" and rows[key]["free_trial"] == year
    # nothing detected on the page -> the fixed text
    rows = _run(monkeypatch, {}, pelephone={key[0]: ("₪19.90", None, entry)})
    assert rows[key]["free_trial"] == entry["free_trial"]
