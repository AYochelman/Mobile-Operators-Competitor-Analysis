"""Offline guards for two parsers rewritten in the 2026-11-26 scraper audit,
built from the live markup / text of that day."""
import scraper  # noqa: F401  (loads the scrapers package the way the app does)
import btl_scrapers
from scrapers.seven_g import _parse_seven_g_page

# ── 7G: one <label class="plan-opt"> per card; Unlimited durations in a <select> ──

SEVEN_G_HTML = (
    '<title>eSIM לצרפת – תוכניות נתונים מ-US$1.99 | 7G eSIM</title>'
    '<fieldset class="plans">'
    '<label class="plan-opt" data-days="7"><input type="radio" name="plan" value="NX-30730"/>'
    '<span class="plan-opt__gb"><bdi>1 GB</bdi></span><span class="plan-opt__days">7 ימים</span>'
    '<span class="plan-opt__price"><s><span class="sr">מחיר קודם<!-- --> </span>$2.39</s>$1.99</span>'
    '<span class="plan-opt__chips"><span class="plan-chip">5% בקרדיטים של 7G</span></span></label>'
    '<label class="plan-opt plan-opt--fold" data-days="7"><input type="radio" name="plan" value="NX-35090"/>'
    '<span class="plan-opt__gb"><bdi>Unlimited</bdi><svg class="plan-opt__inf"><path d="M1"></path></svg></span>'
    '<span class="plan-opt__days plan-opt__pick">7 ימים<select aria-label="בחרו משך">'
    '<option value="NX-35090" selected="">7 ימים<!-- --> · <!-- -->$19.99</option>'
    '<option value="NX-35091">15 ימים<!-- --> · <!-- -->$29.99</option></select></span>'
    '<span class="plan-opt__price">$19.99</span></label>'
    '<label class="plan-opt" data-days="30"><input type="radio" name="plan" value="NX-30733"/>'
    '<span class="plan-opt__gb"><bdi>10 GB</bdi></span><span class="plan-opt__days">30 ימים</span>'
    '<span class="plan-opt__price"><s><span class="sr">מחיר קודם<!-- --> </span>$13.19</s>$10.99</span>'
    '<span class="plan-opt__chips"><span class="plan-chip">5% בקרדיטים של 7G</span></span></label>'
    '</fieldset>'
)


def test_seven_g_reads_the_plan_cards():
    plans = _parse_seven_g_page(SEVEN_G_HTML, 3.0, "France")
    got = {(p["data_gb"], p["days"]): p["original_price"] for p in plans}
    # the struck-through list price is ignored; the chip's "5%" never glues onto the price
    assert got == {(1.0, 7): 1.99, (10.0, 30): 10.99, (None, 7): 19.99, (None, 15): 29.99}
    names = {p["plan_name"].replace("‏", "") for p in plans}
    assert "צרפת – 1GB – 7 ימים" in names            # unchanged key format for fixed plans
    assert "צרפת – ללא הגבלה – 15 ימים" in names
    assert all(p["extras"] == ["צרפת"] for p in plans)


# ── zol-li: "ג׳יגה" in the details, "בהצטרפות שני מנויים ומעלה" pricing ──

ZOL_TEXT = (
    "<< << << דור 5 Total 5G Plus 400GB 3,500 דק' שיחה 3,500 הודעות 400GB דור 5G "
    "הנחה בצירוף 2 מנויים ומעלה 37.5 ₪ לחודש 072-3952945 מידע נוסף info_outline "
    "פרטי המסלול: דקות שיחה והודעות בשימוש סביר והוגן: עד 3500 דקות ו-3500 הודעות בארץ "
    "גלישה: עד 400 ג׳יגה גלישה, דור 5 בארץ credit_card מחיר: 37.5 ₪ לחודש local_mall "
    "פירוט המחיר: מנוי יחיד 39.90 ₪ לחודש בהצטרפות שני מנויים ומעלה 37.5 ₪ בחודש לכל מנוי "
    "get_app התקנה: ללא עלות "
    "סלולר Classic Family Plus 300GB 3,000 דק' שיחה 3,000 הודעות 300GB דור 4G "
    "בהצטרפות שני מנויים ומעלה 27.5 ₪ לחודש מידע נוסף info_outline "
    "פרטי המסלול: דקות שיחה והודעות בשימוש סביר והוגן: עד 3000 דקות ו-3000 הודעות בארץ "
    "גלישה: עד 300 ג׳יגה גלישה בארץ credit_card מחיר: 27.5 ₪ לחודש local_mall "
    "פירוט המחיר: מנוי יחיד 29.90 ₪ לחודש בהצטרפות שני מנויים ומעלה: 27.5 ₪ בחודש "
    "get_app התקנה: דמי חיבור 10.90 ₪"
)


def test_zol_li_reads_the_current_cards(monkeypatch):
    monkeypatch.setattr(btl_scrapers, "_fetch_text", lambda url: ZOL_TEXT)
    rows = {r["plan_name"]: r for r in btl_scrapers.scrape_zol_li()}
    assert set(rows) == {"הוט מובייל 5G 400GB — Total 5G Plus",
                         "הוט מובייל 4G 300GB — Classic Family Plus"}
    top = rows["הוט מובייל 5G 400GB — Total 5G Plus"]
    assert (top["price"], top["data_gb"], top["minutes"]) == (37.5, 400.0, 3500)   # per line
    assert "37.5 ₪ לקו בצירוף 2 מנויים ומעלה" in top["extras"]
    assert "מנוי בודד: 39.90 ₪ לחודש" in top["extras"]
    assert rows["הוט מובייל 4G 300GB — Classic Family Plus"]["price"] == 27.5
