# -*- coding: utf-8 -*-
"""Offline regression tests for Cellcom roaming terms capture (the "עיקרי התוכנית" link).

Background: `scrape_cellcom_abroad` fetches each package's terms PDF (`policiesEpi`) from
GetPackagePopular, which echoes back ONLY the SOC codes the caller asks for. Those lists
used to be hardcoded while the Silent-Roamers DOM source is open-ended, so a package
Cellcom published outside them (the holiday promo "מושלמת לחגים", 2026-09) was scraped
with terms_url=None. These tests pin the discovery path that closes that gap.

No network: GetPackagePopular is stubbed from the recorded response in
cellcom_abroad_api_result.json, and the Playwright Page is faked.
"""
import json
import os
import io
import pytest

import scraper

FIXTURE = os.path.join(os.path.dirname(__file__), os.pardir, "cellcom_abroad_api_result.json")


def _recorded_packages():
    with io.open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)["Body"]


# ── The extra package Cellcom published outside every hardcoded SOC list ──────
HOLIDAY_SOC = "FMWH1234"
HOLIDAY = {
    "titleEpi": 'מושלמת לחגים',
    "socCode": HOLIDAY_SOC,
    "policiesEpi": "/globalassets/pdf/abraod/30199.pdf",
    "price": 199.0,
    "packageDuration": 21,
    "packageDetailsList": [{"data": {"value": 30}, "voice": {"value": 100}, "sms": {"value": 100}}],
}


@pytest.fixture
def stub_api(monkeypatch):
    """Stub GetPackagePopular with the recorded catalogue + the holiday package, echoing
    back only the SOCs asked for — the real API's behaviour, and the whole reason a SOC we
    never discover can never yield a terms PDF."""
    catalogue = {p["socCode"]: p for p in _recorded_packages()}
    catalogue[HOLIDAY_SOC] = HOLIDAY
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload
        def read(self):
            return json.dumps(self._payload).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        asked = json.loads(req.data.decode())["SocIdList"]
        calls.append(asked)
        return _Resp({"Body": [catalogue[s] for s in asked if s in catalogue]})

    monkeypatch.setattr(scraper.urllib.request, "urlopen", fake_urlopen)
    return calls


# ── _cellcom_norm_title ──────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ('גולשים ומדברים ', 'גולשים ומדברים'),
    ('כל מה שצריך לחודש', 'כל מה שצריך לחודש'),
    ('המושלמת לחו&quot;ל', 'המושלמת לחו"ל'),
    ('המושלמת לחו״ל', 'המושלמת לחו"ל'),
    ('  גולשים   בגדול  ', 'גולשים בגדול'),
    (None, ''),
])
def test_norm_title(raw, expected):
    assert scraper._cellcom_norm_title(raw) == expected


def test_soc_regex_matches_real_codes():
    text = 'href="/AbroadMain/purchase/?soc=FMWH0047" data-soc="HUL4209" x="FMWH998"'
    assert {m.group(0) for m in scraper._CELLCOM_SOC_RE.finditer(text)} == \
        {"FMWH0047", "HUL4209", "FMWH998"}


# ── _cellcom_fetch_abroad_policies ───────────────────────────────────────────
def test_policies_keyed_by_title_and_soc(stub_api):
    socs = [p["socCode"] for p in _recorded_packages()]
    by_title, by_soc = scraper._cellcom_fetch_abroad_policies(socs, 20557)
    assert by_soc["HUL4209"] == \
        "https://contentepi.cellcom.co.il/globalassets/pdf/abraod/05.22/17463-0923-10-hul4209--hul4210.pdf"
    # trailing space in the recorded titleEpi must not create a second key
    assert 'גולשים ומדברים' in by_title
    assert len(by_soc) == len(socs)


def test_policies_survive_api_failure(monkeypatch):
    def boom(*a, **kw):
        raise OSError("connection reset")
    monkeypatch.setattr(scraper.urllib.request, "urlopen", boom)
    assert scraper._cellcom_fetch_abroad_policies(["FMWH998"], 20557) == ({}, {})


# ── Fake Playwright page ─────────────────────────────────────────────────────
class _El:
    def __init__(self, text="", attrs=None, outer="", pdfs=()):
        self._text, self._attrs, self._outer, self._pdfs = text, attrs or {}, outer, pdfs
    def inner_text(self):
        return self._text
    def get_attribute(self, name):
        return self._attrs.get(name)
    def evaluate(self, _js):
        return self._outer
    def query_selector(self, sel):
        found = self.query_selector_all(sel)
        return found[0] if found else None
    def query_selector_all(self, sel):
        if '.pdf' in sel:
            return list(self._pdfs)
        return []


class _Card(_El):
    def __init__(self, name, days, gb, price, outer="", pdfs=()):
        super().__init__(outer=outer, pdfs=pdfs)
        self._parts = {
            ".abroad-package-client__title": _El(name),
            ".abroad-package-client__duration": _El(f"חבילה ל-{days} ימים"),
            ".abroad-package-client__data--bank": _El(f"{gb}\nGB"),
            ".abroad-package-client__price-real--bank--container": _El(f"{price}₪"),
        }
        self._price = price
    def query_selector(self, sel):
        if sel in self._parts:
            return self._parts[sel]
        return super().query_selector(sel)
    def query_selector_all(self, sel):
        if sel == ".abroad-package-voice-sms__value":
            return []
        if sel == "span":
            return [_El(f"{self._price}")]
        if '.pdf' in sel:
            return list(self._pdfs)
        return []


class _Page:
    def __init__(self, cards, html):
        self._cards, self._html = cards, html
    def goto(self, *a, **kw):
        return None
    def wait_for_timeout(self, *a):
        return None
    def content(self):
        return self._html
    def query_selector_all(self, sel):
        return list(self._cards) if sel == ".abroad-package-client" else []


def _plans_by_name(plans):
    return {p["plan_name"]: p for p in plans}


# ── The regression: a new card whose SOC only appears in the page HTML ───────
def test_new_dom_package_gets_terms_from_discovered_soc(stub_api):
    card = _Card('מושלמת לחגים', 21, 30, 199)
    page = _Page([card], f'<a href="/AbroadMain/purchase/?soc={HOLIDAY_SOC}">לרכישה</a>')

    plans = scraper.scrape_cellcom_abroad(page)
    holiday = _plans_by_name(plans)['מושלמת לחגים']

    assert holiday["terms_url"] == \
        "https://contentepi.cellcom.co.il/globalassets/pdf/abraod/30199.pdf"
    # the unknown SOC was actually asked for, not guessed
    assert any(HOLIDAY_SOC in asked for asked in stub_api)
    # private discovery keys never reach the DB layer
    assert "_soc" not in holiday and "_dom_terms" not in holiday


def test_lobby_packages_keep_their_terms(stub_api):
    page = _Page([], "")
    plans = scraper.scrape_cellcom_abroad(page)
    assert len(plans) == 8
    assert all(p["terms_url"] for p in plans), \
        [p["plan_name"] for p in plans if not p["terms_url"]]
    assert _plans_by_name(plans)['גלישה בקטנה']["terms_url"].endswith(
        "/globalassets/pdf/30027-0623-01-hul4539--hul4540.pdf")


def test_card_pdf_anchor_is_the_last_resort(stub_api):
    """No SOC anywhere — the card's own /globalassets/ terms anchor still wins the day."""
    pdf = _El('לתנאי החבילה המלאים', {"href": "/globalassets/pdf/abraod/30200.pdf"})
    card = _Card('חבילת סתיו', 14, 10, 129, pdfs=[pdf])
    plans = scraper.scrape_cellcom_abroad(_Page([card], "<html>no soc here</html>"))
    assert _plans_by_name(plans)['חבילת סתיו']["terms_url"] == \
        "https://contentepi.cellcom.co.il/globalassets/pdf/abraod/30200.pdf"


def test_unrelated_pdf_is_not_linked_as_terms(stub_api):
    """Linking a factually-wrong document is worse than an empty state, so only Cellcom's
    /globalassets/ terms PDFs qualify."""
    pdf = _El('מדריך נסיעות', {"href": "https://cdn.example.com/brochure.pdf"})
    card = _Card('חבילת סתיו', 14, 10, 129, pdfs=[pdf])
    plans = scraper.scrape_cellcom_abroad(_Page([card], "<html>no soc here</html>"))
    assert _plans_by_name(plans)['חבילת סתיו']["terms_url"] is None


def test_dom_title_variant_still_matches_by_title(stub_api):
    """DOM text carrying an NBSP / typographic quote must still resolve to the API title."""
    card = _Card('המושלמת לחו״ל', 30, 20, 249)
    plans = scraper.scrape_cellcom_abroad(_Page([card], "<html></html>"))
    # the lobby source already returns this plan, so the DOM card dedups against it
    assert all(p["terms_url"] for p in plans)


def test_discovered_soc_never_overwrites_a_known_title(monkeypatch):
    """A page-wide SOC regex can also catch codes that aren't consumer roaming packages.
    One of those sharing a title with a real plan must not hijack its terms PDF."""
    catalogue = {p["socCode"]: p for p in _recorded_packages()}
    impostor = "HUL9999"
    catalogue[impostor] = {"titleEpi": 'גולשים בגדול', "socCode": impostor,
                           "policiesEpi": "/globalassets/pdf/business/wrong.pdf"}

    class _Resp:
        def __init__(self, payload):
            self._payload = payload
        def read(self):
            return json.dumps(self._payload).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        asked = json.loads(req.data.decode())["SocIdList"]
        return _Resp({"Body": [catalogue[s] for s in asked if s in catalogue]})

    monkeypatch.setattr(scraper.urllib.request, "urlopen", fake_urlopen)
    plans = scraper.scrape_cellcom_abroad(_Page([], f'<div data-soc="{impostor}"></div>'))
    assert _plans_by_name(plans)['גולשים בגדול']["terms_url"].endswith(
        "/globalassets/pdf/abraod/31.10.24/30086.pdf")
