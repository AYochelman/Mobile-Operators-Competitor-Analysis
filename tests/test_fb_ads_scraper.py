"""Offline tests for fb_ads_scraper's ad-copy parser.

The ad texts below are copied from the live Meta Ad Library (2026-11-10), so a
regression in the regexes shows up here without a browser or the internet.
"""
import fb_ads_scraper as f

ADV = {a["reseller_id"]: a for a in f.ADVERTISERS}

SIMPEL_1000 = """ממומן
משפחה שרוצה לעבור לדור 5? עכשיו זה הזמן 🚀
4 מנויים במסלול דור 5 של פלאפון ב-100 ₪ לחודש בסך הכול, כלומר 25 ₪ לכל מנוי, עם 1000GB גלישה בדור 5 לכל מנוי.
המחיר קבוע ל-12 חודשים. אחר כך 69.90 ₪ לחודש לכל מנוי.
למצטרפים חדשים, במכשיר תומך ובאזור עם כיסוי דור 5. המבצע בתוקף עד 15.11 בלבד.
FB.ME
4 מנויים בדור 5 ב-100 ₪ לחודש
הרשמה"""

SIMPEL_400 = """ממומן
משפחה עם כמה קווים? זה המבצע שחיכיתם לו
5 מנויים בפלאפון ב-100 ₪ לחודש בסך הכול, כלומר 20 ₪ לכל מנוי, עם 400GB גלישה לכל מנוי.
המחיר קבוע ל-12 חודשים. אחר כך 69.90 ₪ לחודש לכל מנוי.
FB.ME
5 מנויים ב-100 ₪ לחודש
הרשמה"""

SIMPEL_JOB = """ממומן
📞 דרושים/ות אנשי מכירות טלפוניים למוקד בבאר שבע
Apply Now"""

PELEPHONE_PROMOS = """ממומן
מבצע מיוחד בפלאפון!
5 קווים ב־100 ₪ לחודש בלבד.
✅ 400 גיגה גלישה לכל קו
✅ 3,500 דקות שיחה
✅ 3,500 הודעות SMS
**למצטרפים חדשים בלבד.**
FB.ME
5 קווים ב־100 ₪ בלבד
לפרטים"""

RAMI_PAIR = """ממומן
רמי לוי תקשורת יצאו במבצע מטורף לזמן מוגבל!
שני קווי סלולר ב־55 ₪ לחודש!
לכל קו מגיע בחבילה:
✅ 5,000 דקות שיחה ו-5,000 הודעות SMS.
✅ 400 גי'גה גלישה
וכל זה למשך 3 שנים!
מי שמגיע לסניף עם המודעה מקבל חודש מתנה לכל קו!
הרשמה"""

RAMI_TRIPLE = """ממומן
ברמי לוי תקשורת חוסכים לכם יותר -
☑️ 5G
☑️ 600GB גלישה
☑️ 5,000 דקות שיחה
3 קווים  רק ב-80₪ לחודש! 🤯
Sign Up"""

RAMI_FOUR = """ממומן
ארבעה קווים. מחיר אחד!
4 קווי סלולר ב־100 ₪ לחודש, ל־24 החודשים הראשונים.
בצירוף 4 קווים למסלול זה בלבד.
בכל קו: עד 300GB גלישה, 4,000 דקות שיחה ו־4,000 SMS.
מחיר החבילה לקו הינו 32.90 ₪ לחודש | ההטבה מקנה 24 חודשים ראשונים במחיר 27.90 ₪ לקו לחודש | מחיר ההטבה ל 4 מנויים יעמוד על 100 ₪ לחודש | דמי חיבור חד פעמי 49.90 לכל קו
מידע נוסף"""

# The pre-existing copy formats must keep parsing the same way.
TIER_DISCLOSURE = """מבצע 5G
400GB גלישה בדור 5
1-4 מנויים: 29.90 ₪
5 מנויים ומעלה: 20 ₪
לאחר שנה: 69.90 ₪"""


def _one(text):
    offers = f.parse_offers(text)
    assert len(offers) == 1, offers
    return offers[0]


def test_bundle_with_words_between_count_and_price():
    o = _one(SIMPEL_1000)
    assert (o["data_gb"], o["min_lines"], o["price"], o["total"]) == (1000, 4, 25.0, 100.0)
    assert o["after_price"] == 69.9 and o["months"] == 12 and o["gen5"]


def test_lines_word_and_hebrew_gb_unit():
    o = _one(PELEPHONE_PROMOS)
    assert (o["data_gb"], o["min_lines"], o["price"], o["minutes"]) == (400, 5, 20.0, 3500)


def test_number_word_lines_and_apostrophe_gb():
    o = _one(RAMI_PAIR)
    assert (o["data_gb"], o["min_lines"], o["price"], o["total"]) == (400, 2, 27.5, 55.0)
    assert o["months"] == 36 and o["minutes"] == 5000
    assert o["perks"] == ["חודש מתנה לכל קו למגיעים לסניף עם המודעה"]


def test_rak_between_lines_and_price_and_rounded_total():
    o = _one(RAMI_TRIPLE)
    assert (o["data_gb"], o["min_lines"], o["price"], o["total"]) == (600, 3, 26.67, 80.0)
    p = f._to_plan(ADV["fb_rami_levy_branches"], dict(o, carrier="rami_levy"), "u")
    assert 'סה"כ 80 ₪' in p["extras"][0]          # not 80.01 from 26.67 * 3


def test_construct_form_lines_list_price_and_connection_fee():
    o = _one(RAMI_FOUR)
    assert (o["data_gb"], o["min_lines"], o["price"]) == (300, 4, 25.0)
    assert o["months"] == 24 and o["after_price"] == 32.9
    p = f._to_plan(ADV["fb_rami_levy_branches"], dict(o, carrier="rami_levy"), "u")
    assert "לאחר 2 שנים: 32.9 ₪ לחודש למנוי" in p["extras"]
    assert "דמי חיבור חד-פעמיים 49.9 ₪ לקו" in p["extras"]


def test_tier_disclosure_unchanged():
    offers = {o["min_lines"]: o for o in f.parse_offers(TIER_DISCLOSURE)}
    assert offers[1]["price"] == 29.9 and offers[1]["max_lines"] == 4
    assert offers[5]["price"] == 20.0
    p = f._to_plan(ADV["fb_pelephone_deals"], dict(offers[5], carrier="pelephone"), "u")
    assert p["plan_name"] == "400GB – 5 מנויים ומעלה – קמפיין פייסבוק"
    assert "לאחר שנה: 69.9 ₪ לחודש למנוי" in p["extras"]


def test_per_line_price_is_not_divided():
    o = _one("700GB גלישה\n5 מנויים ב-20 ₪ למנוי")
    assert (o["min_lines"], o["price"], o["total"]) == (5, 20.0, None)


def test_detect_carrier():
    assert f.detect_carrier(SIMPEL_1000) == "pelephone"
    assert f.detect_carrier(RAMI_PAIR) == "rami_levy"
    assert f.detect_carrier("עוברים מסלקום לפלאפון 400GB") is None   # ambiguous
    assert f.detect_carrier("5 מנויים ב-100 ₪ 400GB") is None


def _body(page_name, *ads):
    return "".join(f"\nפעילה\n{page_name}\n{ad}" for ad in ads)


def test_simpel_end_to_end_skips_non_offer_ads():
    adv = ADV["fb_simpel"]
    plans = f.plans_from_body(adv, _body(adv["page_name"], SIMPEL_1000, SIMPEL_JOB, SIMPEL_400), "u")
    got = sorted((p["carrier"], p["plan_name"], p["price"]) for p in plans)
    assert got == [
        ("pelephone", "1000GB – 4 מנויים ומעלה – קמפיין פייסבוק", 25.0),
        ("pelephone", "400GB – 5 מנויים ומעלה – קמפיין פייסבוק", 20.0),
    ]
    assert all(p["reseller_id"] == "fb_simpel" for p in plans)


def test_rami_levy_branches_end_to_end():
    adv = ADV["fb_rami_levy_branches"]
    plans = f.plans_from_body(adv, _body(adv["page_name"], RAMI_PAIR, RAMI_TRIPLE, RAMI_PAIR, RAMI_FOUR), "u")
    assert sorted((p["data_gb"], p["price"]) for p in plans) == [(300.0, 25.0), (400.0, 27.5), (600.0, 26.67)]
    assert {p["carrier"] for p in plans} == {"rami_levy"}


def test_new_ids_are_registered_everywhere():
    import db
    import notifier
    for rid in ("fb_pelephone_promos", "fb_simpel", "fb_rami_levy_branches"):
        assert rid in ADV
        assert rid in db.AUTO_SCRAPED_RESELLER_IDS
        assert rid in notifier.RESELLER_NAMES
    assert "fb_rami_levy_branches" in db.ALWAYS_SHOW_RESELLER_IDS
    assert "fb_simpel" not in db.ALWAYS_SHOW_RESELLER_IDS
