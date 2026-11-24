"""Read a content service's benefit ("free trial") text from the carrier's page.

Until 2026-11-24 the benefit of every content service was a fixed string in
CONTENT_SERVICES (scrapers/content.py) and only the PRICE was read from the page,
so a changed benefit (Pelephone eSIM watch: two months -> half a year) never
reached the database. `extract_free_trial` finds the benefit phrase in the page
text; `resolve_free_trial` decides what is stored.

Pure text logic, no browser and no project imports, so it is unit-testable
(tests/test_content_trial.py).
"""
import re

# "half a year", "a year", "two months", "first month", "3 months", "first 3 months"...
_NUM_WORDS = (r"(?:שלושה|שלושת|"      # שלושה / שלושת
              r"ארבעה|ארבעת|"          # ארבעה / ארבעת
              r"חמישה|חמשת|"                # חמישה / חמשת
              r"שישה|ששת)")                           # שישה / ששת
_PERIOD = (
    r"(?:"
    r"חצי\s+שנה(?:\s+ה?ראשונה)?"      # חצי שנה [ראשונה]
    r"|שנה(?:\s+(?:שלמה|ה?ראשונה))?"  # שנה [שלמה|ראשונה]
    r"|חודשיים(?:\s+ה?ראשונים)?"  # חודשיים [ראשונים]
    r"|(?:\d{1,2}|" + _NUM_WORDS + r")\s+ה?חודשים"                  # N חודשים
    r"(?:\s+ה?ראשונים)?"                                       #   [ראשונים]
    r"|חודש(?:\s+ה?ראשון)?"                          # חודש [ראשון]
    r")"
)
# חינם / בחינם / מתנה / במתנה / ללא עלות / ללא תשלום / ללא חיוב
_FREE = (r"(?:ב?חינם|ב?מתנה|"
         r"ללא\s+(?:עלות|תשלום|חיוב))")
_HE = "א-ת"
_SEP = r"[\s\-–:!]{1,4}"
# ל / ל- / למשך / למשך ה-
_FOR = r"(?:למשך\s+ה?-?\s*|ל-?\s*)"

_PATTERNS = [
    # "50% הנחה ל-4 חודשים"
    re.compile(r"\d{1,3}\s*%\s*הנחה\s+" + _FOR + _PERIOD),
    # "חודש ראשון חינם", "3 חודשים ללא עלות", "חצי שנה מתנה"
    # (a leading "ו" - "וחודש ראשון מתנה" - is allowed and left out of the phrase)
    re.compile(r"(?<![" + _HE + r"\d])\u05d5?(" + _PERIOD + _SEP + _FREE + r")(?![" + _HE + r"])"),
    # "חינם לחצי שנה", "מתנה ל-6 חודשים", "ללא עלות למשך 3 חודשים"
    re.compile(r"(?<![" + _HE + r"])" + _FREE + r"\s+" + _FOR + _PERIOD + r"(?![" + _HE + r"])"),
]

WINDOW_BEFORE = 400
WINDOW_AFTER = 700


def _clean(phrase):
    return re.sub(r"\s+", " ", phrase).strip(" -–:!")


def extract_free_trial(text, keyword=None):
    """The benefit phrase in `text`, or None when the page states none.

    With a `keyword` (the entry's price keyword) only the text around it is read
    and the phrase NEAREST to it wins - several services can share one page
    (Pelephone cyber + Norton). A keyword that is not on the page -> None.
    """
    if not text:
        return None
    anchor = None
    if keyword:
        idx = text.find(keyword)
        if idx == -1:
            return None
        start = max(0, idx - WINDOW_BEFORE)
        text = text[start:idx + WINDOW_AFTER]
        anchor = idx - start
    best = None
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            dist = 0 if anchor is None else min(abs(m.start() - anchor), abs(m.end() - anchor))
            key = (dist, m.start()) if anchor is not None else (m.start(), 0)
            if best is None or key < best[0]:
                best = (key, m.group(m.lastindex or 0))
    return _clean(best[1]) if best else None


def resolve_free_trial(entry, detected):
    """What to store for a CONTENT_SERVICES entry: (free_trial, source).

    The page wins only for entries flagged `trial_scan` - each page words its
    benefit differently, so an entry is switched on after its detection was
    checked (scripts/content_trial_preview.py). Otherwise, and whenever nothing
    was detected, the entry's fixed text is used. A " | ..." tail of the fixed
    text (the song services' download price) is kept.
    """
    default = entry.get("free_trial", "—")
    if not (entry.get("trial_scan") and detected):
        return default, "default"
    head, sep, tail = default.partition(" | ")
    return (detected + sep + tail if sep else detected), "page"
