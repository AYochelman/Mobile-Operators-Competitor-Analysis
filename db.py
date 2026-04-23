import sqlite3
import json
import os
from datetime import datetime, timezone, timedelta

# Canonical Hebrew country/destination names — applied before every global plan save
_DEST_NORM = {
    '\u05e0\u05d5\u05e8\u05d5\u05d5\u05d2\u05d9\u05d4': '\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4',                   # נורווגיה → נורבגיה
    '\u05e9\u05d5\u05d5\u05d3\u05d9\u05d4': '\u05e9\u05d1\u05d3\u05d9\u05d4',                                             # שוודיה → שבדיה
    '\u05e4\u05e8\u05d2\u05d5\u05d5\u05d0\u05d9': '\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9',                   # פרגוואי → פראגוואי
    '\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d0\u05d5\u05df': '\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4',  # סיירה לאון → סיירה ליאונה
    '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',    # איי טורק וקייקוס
    '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',  # איי טורקס וקייקוס
    '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',  # איי טוקס וקייקוס
    '\u05d0\u05d9\u05d9 \u05d8\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',  # איי טרקס וקייקוס
    # ── 10 canonical renames ────────────────────────────────────────────────
    '\u05d0\u05e8\u05d4"\u05d1': '\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea',                            # ארה"ב → ארצות הברית
    '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd': '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd',  # אנטילים ההולנדיים → אנטילים ההולנדים
    '\u05d1\u05d5\u05e6\u05d5\u05d0\u05e0\u05d4': '\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4',                       # בוצוואנה → בוטסואנה
    '\u05d2\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4': '\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4',                       # גואדלופ → גוואדלופ
    '\u05d2\u05d9\u05e0\u05d0\u05d4-\u05d1\u05d9\u05e1\u05d0\u05d5': '\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5',  # גינאה-ביסאו → גינאה ביסאו
    '\u05db\u05d5\u05d5\u05d9\u05ea': '\u05db\u05d5\u05d5\u05d9\u05d9\u05ea',                                                # כווית → כוויית
    '\u05dc\u05d8\u05d5\u05d5\u05d9\u05d4': '\u05dc\u05d8\u05d1\u05d9\u05d4',                                                # לטוויה → לטביה
    '\u05e0\u05d9\u05d6\'\u05e8': '\u05e0\u05d9\u05d2\'\u05e8',                                                              # ניז'ר → ניג'ר
    '\u05e0\u05d9\u05e7\u05e8\u05d2\u05d5\u05d0\u05d4': '\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4',          # ניקרגואה → ניקראגואה
    '\u05e1\u05d9\u05d9\u05e9\u05dc': '\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc',                                   # סיישל → איי סיישל
    '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd': '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd',  # סנט וינסנט והגרנדינים → סנט וינסנט והגרדינים
    '\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d1\u05d9\u05e1': '\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1',  # סנט קיטס ונביס → סנט קיטס ונוויס
    # ── TravelSim / Orbit / misc normalizations ─────────────────────────────────
    '\u05d0\u05d9\u05d9 \u05d1\u05d4\u05d0\u05de\u05d4': '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4',                                            # איי בהאמה → איי הבהאמה
    '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d0\u05de\u05e8\u05d9\u05e7\u05d0\u05d9\u05d9\u05dd': '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4"\u05d1)',   # איי הבתולה האמריקאיים → איי הבתולה (ארה"ב)
    '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d1\u05e8\u05d9\u05d8\u05d9\u05d9\u05dd': '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)',  # איי הבתולה הבריטיים → איי הבתולה (בריטניה)
    '\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea \u05d4\u05e2\u05e8\u05d1\u05d9\u05d5\u05ea': '\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea',  # איחוד האמירויות הערביות → איחוד האמירויות
    '\u05d0\u05d9\u05e8\u05df': '\u05d0\u05d9\u05e8\u05d0\u05df',                                                              # אירן → איראן
    '\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2\'\u05d0\u05df': '\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2\'\u05df',                                        # אזרבייג'אן → אזרבייג'ן
    '\u05d5\u05d9\u05d0\u05d8\u05e0\u05d0\u05dd': '\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd',                                                              # ויאטנאם → וייטנאם
    '\u05d5\u05d9\u05d0\u05d8\u05e0\u05dd': '\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd',                                                                    # ויאטנם → וייטנאם
    '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd \u05d4\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05d9\u05dd': '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd',  # האיים ההולנדיים האנטיליים → אנטילים הולנדיים
    '\u05d4\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd': '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd',  # האנטילים ההולנדיים → אנטילים הולנדיים
    '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd': '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd',  # אנטילים ההולנדים → אנטילים הולנדיים
    '\u05de\u05d5\u05e0\u05d0\u05e7\u05d5': '\u05de\u05d5\u05e0\u05e7\u05d5',                                                              # מונאקו → מונקו
    '\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4': '\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea',                  # מקדוניה → מקדוניה הצפונית
    '\u05e4\u05d5\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5': '\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5',                              # פורטו ריקו → פוארטו ריקו
    '\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd': '\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd',                               # פיליפינים → הפיליפינים
    '\u05e7\u05d5\u05e8\u05e1\u05d0\u05d5': '\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5',                                                    # קורסאו → קוראסאו
    '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05e1': '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd',  # סנט וינסנט וגרנדינס → סנט וינסנט והגרדינים
    '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd': '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd',  # סנט וינסנט והגרנדינים → סנט וינסנט והגרדינים
    '\u05e1\u05d5\u05e8\u05d9\u05e0\u05dd': '\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd',                                                    # סורינם → סורינאם
    '\u05e2\u05d5\u05de\u05d0\u05df': '\u05e2\u05d5\u05de\u05df',                                                              # עומאן → עומן
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d8\u05d5\u05e8\u05e7\u05d9\u05ea': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea',  # קפריסין הטורקית → קפריסין הצפונית
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d9\u05d5\u05d5\u05e0\u05d9\u05ea': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df',                     # קפריסין היוונית → קפריסין
    '\u05de\u05d6\u05e8\u05d7 \u05d8\u05d9\u05de\u05d5\u05e8': '\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4',                                    # מזרח טימור → טימור לסטה
    '\u05de\u05d9\u05d5\u05d8': '\u05de\u05d0\u05d9\u05d5\u05d8',                                                              # מיוט → מאיוט
    '\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd': '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd',           # מלדיביים → האיים המלדיביים
    '\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4': '\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4',                              # כף ורדה → קייפ ורדה
    '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6-\u05d0\u05e4\u05e8\u05d9\u05e7\u05e0\u05d9\u05ea': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea',  # הרפובליקה המרכז-אפריקנית → הרפובליקה המרכז אפריקאית
    '\u05e1\u05d5\u05d0\u05d6\u05d9\u05dc\u05e0\u05d3': '\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9',                                           # סואזילנד → אסוואטיני
    '\u05d0\u05d5\u05dc\u05e0\u05d3': '\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3',                                     # אולנד → איי אולנד
    '\u05e7\u05d5\u05e0\u05d2\u05d5': '\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5',      # קונגו → רפובליקת קונגו
    '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5',  # הרפובליקה של קונגו → הרפובליקה הדמוקרטית של קונגו
    '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05de\u05e8\u05d9\u05e7\u05d4)': '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4"\u05d1)',  # איי הבתולה (אמריקה) → איי הבתולה (ארה"ב)
    '\u05d0\u05e0\u05d2\u05dc\u05d9\u05d4': '\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4',                                       # אנגליה → בריטניה
    'Korea': '\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4',                                                   # Korea → דרום קוריאה
    'North America': '\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4',                                           # North America → צפון אמריקה
    '\u05e7\u05d8\u05d0\u05e8': '\u05e7\u05d8\u05e8',                                                                           # קטאר → קטר
    '\u05d0\u05e0\u05d2\u05d9\u05dc\u05d4': '\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4',                                   # אנגילה → אנגווילה
    '\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9': '\u05d0\u05e1\u05d5\u05d0\u05d5\u05d8\u05d9\u05e0\u05d9',                # אסווטיני → אסוואטיני
    '\u05d1\u05d5\u05e6\u05d5\u05d0\u05e0\u05d4': '\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4',                            # בוצואנה → בוטסואנה
    '\u05d2\u05d1\u05d5\u05df': '\u05d2\u05d0\u05d1\u05d5\u05df',                                                                 # גבון → גאבון
    '\u05d2\u05d5\u05d5\u05d3\u05dc\u05d5\u05e4': '\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4',                            # גוודלופ → גוואדלופ
    '\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4': '\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4',                                # כף ורדה → קייפ ורדה
    '\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4 \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea': '\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4',  # קוריאה הדרומית → דרום קוריאה
    '\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5',  # קונגו הדמוקרטית → הרפובליקה הדמוקרטית של קונגו
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df',  # קפריסין הדרומית → קפריסין
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df+': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df',                                 # קפריסין+ → קפריסין
    '\u05e4\u05dc\u05e1\u05d8\u05d9\u05df': '\u05d9\u05e9\u05e8\u05d0\u05dc',                                                   # פלסטין → ישראל
    '\u05d8\u05d9\u05de\u05d5\u05e8-\u05dc\u05e1\u05d8\u05d4': '\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4',      # טימור-לסטה → טימור לסטה
    '\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd': '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd',  # מלדיביים → האיים המלדיביים
    # ── additional dedup fixes ──────────────────────────────────────────────
    '\u05d0\u05e1\u05d5\u05d0\u05d5\u05d8\u05d9\u05e0\u05d9': '\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9',          # אסואוטיני → אסוואטיני
    '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6-\u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea',  # הרפובליקה המרכז-אפריקאית → הרפובליקה המרכז אפריקאית
    '\u05d0\u05d9\u05d9 \u05e7\u05e0\u05e8\u05d9': '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05e7\u05e0\u05e8\u05d9\u05d9\u05dd',   # איי קנרי → האיים הקנריים
    '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d0\u05de\u05e8\u05d9\u05e7\u05e0\u05d9\u05d9\u05dd': '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4"\u05d1)',  # איי הבתולה האמריקניים → איי הבתולה (ארה"ב)
    '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd': '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd',  # האיים ההאיים המלדיביים → האיים המלדיביים
    '\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4': '\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4',                            # בוצוואנה → בוטסואנה
    '\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8': '\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8',                                  # מונטסראט → מונסראט
    '\u05e1\u05e0\u05d8 \u05de\u05e8\u05d8\u05df': '\u05e1\u05df \u05de\u05e8\u05d8\u05df',                                            # סנט מרטן → סן מרטן
    '\u05e1\u05d9\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df': '\u05e1\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df',                   # סינט מארטן → סנט מארטן
}

def _norm_extras(extras):
    """Normalize extras[0] (destination) to canonical name before DB save."""
    if not extras:
        return extras
    dest = extras[0]
    if dest and dest in _DEST_NORM:
        return [_DEST_NORM[dest]] + list(extras[1:])
    return extras

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "plans.db")


def _connect(db_path=None):
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return sqlite3.connect(path)


def init_db(db_path=None):
    conn = _connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                id         INTEGER PRIMARY KEY,
                carrier    TEXT NOT NULL,
                plan_name  TEXT NOT NULL,
                price      REAL,
                data_gb    INTEGER,
                minutes    TEXT,
                extras     TEXT,
                scraped_at TEXT,
                url        TEXT,
                UNIQUE(carrier, plan_name)
            );
            CREATE TABLE IF NOT EXISTS changes (
                id          INTEGER PRIMARY KEY,
                carrier     TEXT NOT NULL,
                plan_name   TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id         INTEGER PRIMARY KEY,
                endpoint   TEXT NOT NULL UNIQUE,
                p256dh     TEXT NOT NULL,
                auth       TEXT NOT NULL,
                user_email TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS abroad_changes (
                id          INTEGER PRIMARY KEY,
                carrier     TEXT NOT NULL,
                plan_name   TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS global_plans (
                id             INTEGER PRIMARY KEY,
                carrier        TEXT NOT NULL,
                plan_name      TEXT NOT NULL,
                price          REAL,
                currency       TEXT,
                original_price REAL,
                days           INTEGER,
                data_gb        REAL,
                minutes        INTEGER,
                sms            INTEGER,
                esim           INTEGER DEFAULT 1,
                extras         TEXT,
                scraped_at     TEXT,
                UNIQUE(carrier, plan_name)
            );
            CREATE TABLE IF NOT EXISTS global_changes (
                id          INTEGER PRIMARY KEY,
                carrier     TEXT NOT NULL,
                plan_name   TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS abroad_plans (
                id         INTEGER PRIMARY KEY,
                carrier    TEXT NOT NULL,
                plan_name  TEXT NOT NULL,
                price      REAL,
                days       INTEGER,
                data_gb    REAL,
                minutes    INTEGER,
                sms        INTEGER,
                extras     TEXT,
                scraped_at TEXT,
                UNIQUE(carrier, plan_name)
            );
            CREATE TABLE IF NOT EXISTS content_plans (
                id         INTEGER PRIMARY KEY,
                service    TEXT NOT NULL,
                carrier    TEXT NOT NULL,
                price      TEXT,
                free_trial TEXT,
                note       TEXT,
                status     TEXT,
                scraped_at TEXT,
                UNIQUE(service, carrier)
            );
            CREATE TABLE IF NOT EXISTS content_changes (
                id          INTEGER PRIMARY KEY,
                service     TEXT NOT NULL,
                carrier     TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS price_alerts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email     TEXT NOT NULL,
                tab            TEXT NOT NULL DEFAULT 'domestic',
                carrier        TEXT,
                plan_pattern   TEXT,
                threshold      REAL NOT NULL,
                active         INTEGER NOT NULL DEFAULT 1,
                last_triggered TEXT,
                created_at     TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS executive_summary (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category     TEXT NOT NULL UNIQUE,
                metrics_json TEXT NOT NULL,
                narrative    TEXT NOT NULL,
                generated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS social_sentiment (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                carrier             TEXT NOT NULL UNIQUE,
                platform_data_json  TEXT NOT NULL,
                narrative           TEXT NOT NULL,
                sentiment           TEXT NOT NULL DEFAULT 'neutral',
                generated_at        TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS archive_snapshots (
                id            INTEGER PRIMARY KEY,
                carrier       TEXT NOT NULL,
                plan_type     TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                plans_json    TEXT NOT NULL,
                content_hash  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_archive_snapshots
                ON archive_snapshots(carrier, plan_type, snapshot_date);
            CREATE TABLE IF NOT EXISTS archive_banners (
                id           INTEGER PRIMARY KEY,
                carrier      TEXT NOT NULL,
                is_store     INTEGER DEFAULT 0,
                archive_date TEXT NOT NULL,
                file_path    TEXT NOT NULL,
                content_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_archive_banners
                ON archive_banners(carrier, is_store, archive_date);
            CREATE TABLE IF NOT EXISTS news_articles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                carrier      TEXT NOT NULL,
                headline     TEXT NOT NULL,
                url          TEXT NOT NULL UNIQUE,
                source       TEXT,
                published_at TEXT,
                fetched_at   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS affiliate_clicks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                provider   TEXT NOT NULL,
                plan_id    TEXT,
                country    TEXT,
                clicked_at TEXT NOT NULL,
                ip_hash    TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_at
                ON affiliate_clicks(clicked_at);
        """)
        conn.commit()
        # Migration: add url column if DB was created before this column existed
        try:
            conn.execute("ALTER TABLE plans ADD COLUMN url TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists
        # Migration: add user_email to push_subscriptions (added for multi-user scoping)
        try:
            conn.execute("ALTER TABLE push_subscriptions ADD COLUMN user_email TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists
    finally:
        conn.close()


def upsert_news_articles(articles, db_path=None):
    """Insert news articles, ignoring duplicates by URL."""
    conn = _connect(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            """INSERT OR IGNORE INTO news_articles
               (carrier, headline, url, source, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(a['carrier'], a['headline'], a['url'],
              a.get('source', ''), a.get('published_at', ''), now)
             for a in articles]
        )
        conn.commit()
    finally:
        conn.close()


def get_news_articles(carrier=None, limit=200, db_path=None):
    """Return news articles ordered by published_at DESC."""
    conn = _connect(db_path)
    try:
        if carrier and carrier != 'all':
            rows = conn.execute(
                "SELECT carrier, headline, url, source, published_at, fetched_at "
                "FROM news_articles WHERE carrier = ? ORDER BY published_at DESC LIMIT ?",
                (carrier, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, headline, url, source, published_at, fetched_at "
                "FROM news_articles ORDER BY published_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        cols = ['carrier', 'headline', 'url', 'source', 'published_at', 'fetched_at']
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def log_affiliate_click(provider, plan_id=None, country=None, ip_hash=None, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO affiliate_clicks (provider, plan_id, country, clicked_at, ip_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (provider, plan_id, country, datetime.now(timezone.utc).isoformat(), ip_hash)
        )
        conn.commit()
    finally:
        conn.close()


def get_affiliate_stats(days=30, db_path=None):
    conn = _connect(db_path)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT provider, date(clicked_at) AS date, COUNT(*) AS clicks
               FROM affiliate_clicks
               WHERE clicked_at >= ?
               GROUP BY provider, date(clicked_at)
               ORDER BY date DESC, clicks DESC""",
            (cutoff,)
        ).fetchall()
        return [{"provider": r[0], "date": r[1], "clicks": r[2]} for r in rows]
    finally:
        conn.close()


def save_executive_summary(category, metrics, narrative, db_path=None):
    """Upsert one category's executive summary row."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO executive_summary (category, metrics_json, narrative, generated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(category) DO UPDATE SET
                   metrics_json = excluded.metrics_json,
                   narrative    = excluded.narrative,
                   generated_at = excluded.generated_at""",
            (category, json.dumps(metrics, ensure_ascii=False),
             narrative, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_executive_summary(db_path=None):
    """Return list of all category summaries, or [] if table is empty."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT category, metrics_json, narrative, generated_at "
            "FROM executive_summary ORDER BY category"
        ).fetchall()
        return [
            {
                "category":     r[0],
                "metrics":      json.loads(r[1]),
                "narrative":    r[2],
                "generated_at": r[3],
            }
            for r in rows
        ]
    finally:
        conn.close()


def save_social_sentiment(carrier, platform_data, narrative, sentiment, db_path=None):
    """Upsert social sentiment row for one carrier."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO social_sentiment (carrier, platform_data_json, narrative, sentiment, generated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(carrier) DO UPDATE SET
                 platform_data_json = excluded.platform_data_json,
                 narrative          = excluded.narrative,
                 sentiment          = excluded.sentiment,
                 generated_at       = excluded.generated_at""",
            (carrier, json.dumps(platform_data, ensure_ascii=False), narrative, sentiment,
             datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        )
        conn.commit()
    finally:
        conn.close()


def get_social_sentiment(carrier=None, db_path=None):
    """Return list of carrier sentiment rows, or single row if carrier specified."""
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, platform_data_json, narrative, sentiment, generated_at "
                "FROM social_sentiment WHERE carrier = ?", (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, platform_data_json, narrative, sentiment, generated_at "
                "FROM social_sentiment ORDER BY carrier"
            ).fetchall()
        return [
            {
                'carrier':      r[0],
                'platform_data': json.loads(r[1]),
                'narrative':    r[2],
                'sentiment':    r[3],
                'generated_at': r[4],
            }
            for r in rows
        ]
    finally:
        conn.close()


def compute_executive_metrics(category, usd_rate=3.7, eur_rate=4.0, db_path=None):
    """Compute algorithmic market metrics for one category.

    Returns dict: { cheapest, most_aggressive, weekly_changes, chart_data, top_plans }
    """
    _VALID_CATEGORIES = {'domestic', 'abroad', 'global', 'content'}
    if category not in _VALID_CATEGORIES:
        raise ValueError(f"Unknown category: {category!r}")

    conn = _connect(db_path)
    try:
        if category == 'domestic':
            rows = conn.execute("""
                SELECT carrier, AVG(price * 1.0 / data_gb) AS v
                FROM plans
                WHERE data_gb > 0 AND price IS NOT NULL
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa/GB'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, data_gb FROM plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]} | " + (f"{r[3]}GB" if r[3] else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                for r in top_rows
            ]
            changes_table = 'changes'
            changes_carrier_col = 'carrier'

        elif category == 'abroad':
            rows = conn.execute("""
                SELECT carrier, AVG(price * 1.0 / NULLIF(days, 0)) AS v
                FROM abroad_plans
                WHERE days > 0 AND price IS NOT NULL
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa/\u05d9\u05d5\u05dd'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, days, data_gb FROM abroad_plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]} | {r[3]} \u05d9\u05de\u05d9\u05dd | " + (f"{r[4]}GB" if r[4] else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                for r in top_rows
            ]
            changes_table = 'abroad_changes'
            changes_carrier_col = 'carrier'

        elif category == 'global':
            all_global = conn.execute(
                "SELECT carrier, plan_name, price, currency, data_gb FROM global_plans "
                "WHERE price IS NOT NULL ORDER BY carrier"
            ).fetchall()
            by_carrier = {}
            for r in all_global:
                carrier, name, price, currency, data_gb = r
                if currency == 'USD':
                    ils = price * usd_rate
                elif currency == 'EUR':
                    ils = price * eur_rate
                else:
                    ils = price if price else 0
                if data_gb and data_gb > 0:
                    ppgb = ils / data_gb
                    by_carrier.setdefault(carrier, []).append(ppgb)
            rows_raw = [(c, sum(v) / len(v)) for c, v in by_carrier.items()]
            rows_raw.sort(key=lambda x: x[1])
            rows = rows_raw
            unit = '\u20aa/GB (\u05d1\u05e9\u05e7\u05dc\u05d9\u05dd)'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, currency, data_gb FROM global_plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | {r[2]}{r[3]} | " + (f"{r[4]}GB" if r[4] else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                for r in top_rows
            ]
            changes_table = 'global_changes'
            changes_carrier_col = 'carrier'

        elif category == 'content':
            rows = conn.execute("""
                SELECT carrier, AVG(CAST(price AS REAL)) AS v
                FROM content_plans
                WHERE price GLOB '[0-9]*'
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa (\u05de\u05d7\u05d9\u05e8 \u05e2\u05e8\u05d5\u05e5 \u05de\u05d5\u05e6\u05dc\u05d1)'
            top_rows = conn.execute("""
                SELECT carrier, service, price, free_trial FROM content_plans
                WHERE price GLOB '[0-9]*' ORDER BY CAST(price AS REAL) ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]}"
                + (f" | \u05e0\u05d9\u05e1\u05d9\u05d5\u05df: {r[3]}" if r[3] else "")
                for r in top_rows
            ]
            changes_table = 'content_changes'
            changes_carrier_col = 'carrier'

        chart_data = [
            {'carrier': r[0], 'value': round(float(r[1]), 2)}
            for r in rows if r[1] is not None
        ]
        cheapest = chart_data[0] if chart_data else {'carrier': '-', 'value': 0}

        if category == 'content':
            drop_rows = conn.execute(f"""
                SELECT {changes_carrier_col}, COUNT(*) AS cnt
                FROM {changes_table}
                WHERE change_type = 'price_change'
                  AND changed_at >= datetime('now', '-7 days')
                GROUP BY {changes_carrier_col} ORDER BY cnt DESC
            """).fetchall()
        else:
            drop_rows = conn.execute(f"""
                SELECT {changes_carrier_col}, COUNT(*) AS cnt
                FROM {changes_table}
                WHERE change_type = 'price_change'
                  AND changed_at >= datetime('now', '-7 days')
                  AND CAST(new_val AS REAL) < CAST(old_val AS REAL)
                GROUP BY {changes_carrier_col} ORDER BY cnt DESC
            """).fetchall()

        rise_rows = conn.execute(f"""
            SELECT {changes_carrier_col}, COUNT(*) AS cnt
            FROM {changes_table}
            WHERE change_type = 'price_change'
              AND changed_at >= datetime('now', '-7 days')
              AND CAST(new_val AS REAL) > CAST(old_val AS REAL)
            GROUP BY {changes_carrier_col} ORDER BY cnt DESC
        """).fetchall()

        total_drops = sum(r[1] for r in drop_rows)
        total_rises = sum(r[1] for r in rise_rows)
        most_aggressive_carrier = drop_rows[0][0] if drop_rows else (
            chart_data[-1]['carrier'] if chart_data else '-'
        )
        most_aggressive_count = drop_rows[0][1] if drop_rows else 0

        return {
            'cheapest':        {'carrier': cheapest['carrier'], 'value': cheapest['value'], 'unit': unit},
            'most_aggressive': {'carrier': most_aggressive_carrier, 'changes': most_aggressive_count},
            'weekly_changes':  {'total': total_drops + total_rises, 'drops': total_drops, 'rises': total_rises},
            'chart_data':      chart_data,
            'top_plans':       top_plans,
        }
    finally:
        conn.close()


def save_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO plans (carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price      = excluded.price,
                    data_gb    = excluded.data_gb,
                    minutes    = excluded.minutes,
                    extras     = excluded.extras,
                    scraped_at = excluded.scraped_at,
                    url        = excluded.url
            """, (
                plan["carrier"], plan["plan_name"], plan.get("price"),
                plan.get("data_gb"), plan.get("minutes"),
                json.dumps(plan.get("extras", []), ensure_ascii=False),
                now, plan.get("url")
            ))
        conn.commit()
    finally:
        conn.close()


def get_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url "
                "FROM plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url "
                "FROM plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "data_gb": r[3], "minutes": r[4],
                "extras": json.loads(r[5]) if r[5] else [],
                "scraped_at": r[6], "url": r[7]
            }
            for r in rows
        ]
    finally:
        conn.close()


def save_global_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO global_plans
                  (carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price          = excluded.price,
                    currency       = excluded.currency,
                    original_price = excluded.original_price,
                    days           = excluded.days,
                    data_gb        = excluded.data_gb,
                    minutes        = excluded.minutes,
                    sms            = excluded.sms,
                    esim           = excluded.esim,
                    extras         = excluded.extras,
                    scraped_at     = excluded.scraped_at
            """, (
                plan["carrier"], plan["plan_name"], plan.get("price"),
                plan.get("currency"), plan.get("original_price"),
                plan.get("days"), plan.get("data_gb"), plan.get("minutes"),
                plan.get("sms"), 1 if plan.get("esim", True) else 0,
                json.dumps(_norm_extras(plan.get("extras", [])), ensure_ascii=False), now
            ))
        conn.commit()
    finally:
        conn.close()


def get_global_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at "
                "FROM global_plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at "
                "FROM global_plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "price": r[2], "currency": r[3],
             "original_price": r[4], "days": r[5], "data_gb": r[6], "minutes": r[7],
             "sms": r[8], "esim": bool(r[9]),
             "extras": json.loads(r[10]) if r[10] else [], "scraped_at": r[11]}
            for r in rows
        ]
    finally:
        conn.close()


def save_global_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO global_changes (carrier, plan_name, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["carrier"], ch["plan_name"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def get_global_changes(limit=50, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
            "FROM global_changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def save_abroad_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO abroad_plans (carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price      = excluded.price,
                    days       = excluded.days,
                    data_gb    = excluded.data_gb,
                    minutes    = excluded.minutes,
                    sms        = excluded.sms,
                    extras     = excluded.extras,
                    scraped_at = excluded.scraped_at
            """, (
                plan["carrier"], plan["plan_name"], plan.get("price"),
                plan.get("days"), plan.get("data_gb"), plan.get("minutes"),
                plan.get("sms"),
                json.dumps(plan.get("extras", []), ensure_ascii=False),
                now
            ))
        conn.commit()
    finally:
        conn.close()


def get_abroad_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at "
                "FROM abroad_plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at "
                "FROM abroad_plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "days": r[3], "data_gb": r[4], "minutes": r[5], "sms": r[6],
                "extras": json.loads(r[7]) if r[7] else [],
                "scraped_at": r[8]
            }
            for r in rows
        ]
    finally:
        conn.close()


def save_abroad_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO abroad_changes (carrier, plan_name, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["carrier"], ch["plan_name"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def get_abroad_changes(limit=50, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
            "FROM abroad_changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def save_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO changes (carrier, plan_name, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["carrier"], ch["plan_name"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def save_push_subscription(endpoint, p256dh, auth, user_email=None, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO push_subscriptions "
            "(endpoint, p256dh, auth, user_email, created_at) VALUES (?, ?, ?, ?, ?)",
            (endpoint, p256dh, auth, user_email, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def delete_push_subscription(endpoint, user_email=None, db_path=None):
    """Delete a subscription by endpoint. If user_email is given, restrict to
    rows owned by that user (returns number of rows deleted)."""
    conn = _connect(db_path)
    try:
        if user_email:
            cur = conn.execute(
                "DELETE FROM push_subscriptions WHERE endpoint=? AND user_email=?",
                (endpoint, user_email)
            )
        else:
            cur = conn.execute(
                "DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,)
            )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_push_subscriptions(user_email=None, db_path=None):
    """Return subscriptions; optionally filter to a single user."""
    conn = _connect(db_path)
    try:
        if user_email:
            rows = conn.execute(
                "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_email=?",
                (user_email,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT endpoint, p256dh, auth FROM push_subscriptions"
            ).fetchall()
        return [
            {"endpoint": r[0], "keys": {"p256dh": r[1], "auth": r[2]}}
            for r in rows
        ]
    finally:
        conn.close()


def save_content_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO content_plans (service, carrier, price, free_trial, note, status, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(service, carrier) DO UPDATE SET
                    price      = excluded.price,
                    free_trial = excluded.free_trial,
                    note       = excluded.note,
                    status     = excluded.status,
                    scraped_at = excluded.scraped_at
            """, (
                plan["service"], plan["carrier"], plan.get("price"),
                plan.get("free_trial"), plan.get("note", ""),
                plan.get("status"), now
            ))
        conn.commit()
    finally:
        conn.close()


def get_content_plans(service=None, carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if service and carrier:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans WHERE service=? AND carrier=? ORDER BY service, carrier",
                (service, carrier)
            ).fetchall()
        elif service:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans WHERE service=? ORDER BY carrier",
                (service,)
            ).fetchall()
        elif carrier:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans WHERE carrier=? ORDER BY service",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans ORDER BY service, carrier"
            ).fetchall()
        return [
            {"service": r[0], "carrier": r[1], "price": r[2], "free_trial": r[3],
             "note": r[4], "status": r[5], "scraped_at": r[6]}
            for r in rows
        ]
    finally:
        conn.close()


def save_content_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO content_changes (service, carrier, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["service"], ch["carrier"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def get_content_changes(limit=50, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT service, carrier, change_type, old_val, new_val, changed_at "
            "FROM content_changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"service": r[0], "carrier": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def get_changes(limit=20, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
            "FROM changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


# ── Price Alerts CRUD ─────────────────────────────────────────────────────

def save_price_alert(user_email, tab, carrier, plan_pattern, threshold, db_path=None):
    """Create a new price alert."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO price_alerts (user_email, tab, carrier, plan_pattern, threshold, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_email, tab, carrier or None, plan_pattern or None,
             threshold, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_price_alerts(user_email=None, active_only=True, db_path=None):
    """Get alerts, optionally filtered by user."""
    conn = _connect(db_path)
    try:
        conditions = []
        params = []
        if user_email:
            conditions.append("user_email = ?")
            params.append(user_email)
        if active_only:
            conditions.append("active = 1")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"SELECT id, user_email, tab, carrier, plan_pattern, threshold, active, last_triggered, created_at "
            f"FROM price_alerts {where} ORDER BY created_at DESC",
            params
        ).fetchall()
        return [
            {"id": r[0], "user_email": r[1], "tab": r[2], "carrier": r[3],
             "plan_pattern": r[4], "threshold": r[5], "active": bool(r[6]),
             "last_triggered": r[7], "created_at": r[8]}
            for r in rows
        ]
    finally:
        conn.close()


def delete_price_alert(alert_id, user_email=None, db_path=None):
    """Delete an alert by ID. If user_email is given, the delete only happens
    when the alert belongs to that user (used to prevent IDOR from the API).
    Returns the number of rows deleted (0 means not found / not owned)."""
    conn = _connect(db_path)
    try:
        if user_email:
            cur = conn.execute(
                "DELETE FROM price_alerts WHERE id = ? AND user_email = ?",
                (alert_id, user_email)
            )
        else:
            cur = conn.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def update_alert_triggered(alert_id, db_path=None):
    """Mark alert as triggered (set last_triggered to now)."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE price_alerts SET last_triggered = ? WHERE id = ?",
            (datetime.now().isoformat(), alert_id)
        )
        conn.commit()
    finally:
        conn.close()


# ── Archive helpers ────────────────────────────────────────────────────────────

def get_last_archive_hash(carrier, plan_type, db_path=None):
    """Return the content_hash of the most recent snapshot for (carrier, plan_type), or None."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """SELECT content_hash FROM archive_snapshots
               WHERE carrier = ? AND plan_type = ?
               ORDER BY snapshot_date DESC LIMIT 1""",
            (carrier, plan_type)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def has_archive_snapshot_today(carrier, plan_type, today, db_path=None):
    """Return True if a snapshot already exists for (carrier, plan_type) on today's date."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """SELECT 1 FROM archive_snapshots
               WHERE carrier = ? AND plan_type = ? AND snapshot_date = ? LIMIT 1""",
            (carrier, plan_type, today)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def insert_archive_snapshot(carrier, plan_type, snapshot_date, plans_json, content_hash, db_path=None):
    """Insert a new plan snapshot row."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO archive_snapshots (carrier, plan_type, snapshot_date, plans_json, content_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (carrier, plan_type, snapshot_date, plans_json, content_hash)
        )
        conn.commit()
    finally:
        conn.close()


def get_last_banner_hash(carrier, is_store=0, db_path=None):
    """Return content_hash of the most recent banner snapshot, or None."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """SELECT content_hash FROM archive_banners
               WHERE carrier = ? AND is_store = ?
               ORDER BY archive_date DESC LIMIT 1""",
            (carrier, int(is_store))
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def insert_archive_banner(carrier, is_store, archive_date, file_path, content_hash, db_path=None):
    """Insert a new banner archive row."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO archive_banners (carrier, is_store, archive_date, file_path, content_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (carrier, int(is_store), archive_date, file_path, content_hash)
        )
        conn.commit()
    finally:
        conn.close()


def get_archive_plans(carrier, date_str, db_path=None):
    """Return latest plan snapshot per plan_type for carrier on or before date_str."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT plan_type, plans_json, snapshot_date
               FROM archive_snapshots
               WHERE carrier = ? AND snapshot_date <= ?
               GROUP BY plan_type
               HAVING snapshot_date = MAX(snapshot_date)""",
            (carrier, date_str)
        ).fetchall()
        return [{"plan_type": r[0], "plans": json.loads(r[1]), "snapshot_date": r[2]} for r in rows]
    finally:
        conn.close()


def get_archive_banners(carrier, date_str, db_path=None):
    """Return latest banner per is_store for carrier on or before date_str."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT is_store, file_path, archive_date
               FROM archive_banners
               WHERE carrier = ? AND archive_date <= ?
               GROUP BY is_store
               HAVING archive_date = MAX(archive_date)""",
            (carrier, date_str)
        ).fetchall()
        return [{"is_store": bool(r[0]), "file_path": r[1], "archive_date": r[2]} for r in rows]
    finally:
        conn.close()


def get_archive_date_range(db_path=None):
    """Return the earliest and latest snapshot dates across all archive tables."""
    conn = _connect(db_path)
    try:
        snap = conn.execute(
            "SELECT MIN(snapshot_date), MAX(snapshot_date) FROM archive_snapshots"
        ).fetchone()
        ban = conn.execute(
            "SELECT MIN(archive_date), MAX(archive_date) FROM archive_banners"
        ).fetchone()
        dates = [d for d in [snap[0], snap[1], ban[0], ban[1]] if d]
        return {"min": min(dates) if dates else None, "max": max(dates) if dates else None}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

_HISTORY_TABLE_MAP = {
    'domestic': ('changes',        'plan_name'),
    'abroad':   ('abroad_changes', 'plan_name'),
    'global':   ('global_changes', 'plan_name'),
    'content':  ('content_changes','service'),
}


def get_history_changes(carrier, plan_type='domestic', from_date='', to_date='', db_path=None):
    """Return all change events for a carrier+plan_type, newest first.

    Args:
        carrier:   carrier id string (e.g. 'pelephone')
        plan_type: one of domestic/abroad/global/content
        from_date: ISO date string 'YYYY-MM-DD' (inclusive lower bound, optional)
        to_date:   ISO date string 'YYYY-MM-DD' (inclusive upper bound, optional)
        db_path:   override DB path (used by tests)

    Returns:
        list of dicts with keys: plan_name, change_type, old_val, new_val, changed_at
        Empty list if plan_type is unknown.
    """
    if plan_type not in _HISTORY_TABLE_MAP:
        return []
    table, name_col = _HISTORY_TABLE_MAP[plan_type]
    db_path = db_path or DB_PATH
    conn = _connect(db_path)
    try:
        sql = (f'SELECT {name_col} AS plan_name, change_type, old_val, new_val, changed_at '
               f'FROM {table} WHERE carrier = ?')
        params = [carrier]
        if from_date:
            sql += ' AND changed_at >= ?'
            params.append(from_date)
        if to_date:
            sql += ' AND changed_at <= ?'
            params.append(to_date + 'T23:59:59')
        sql += ' ORDER BY changed_at DESC'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {'plan_name': r[0], 'change_type': r[1], 'old_val': r[2],
         'new_val': r[3], 'changed_at': r[4]}
        for r in rows
    ]


def get_history_price_series(carrier, plan_type='domestic', plan_name='', from_date='', db_path=None):
    """Build price time-series from price_change events.

    Args:
        carrier:   carrier id string
        plan_type: one of domestic/abroad/global/content
        plan_name: specific plan to narrow to (empty = all plans)
        from_date: ISO date string lower bound (optional)
        db_path:   override DB path

    Returns:
        list of dicts: [{plan_name: str, points: [{date: str, price: float}]}]
        Capped at 10 plans (those with the most change events).
        First point uses old_val of first event (price before the change).
    """
    if plan_type not in _HISTORY_TABLE_MAP:
        return []
    table, name_col = _HISTORY_TABLE_MAP[plan_type]
    db_path = db_path or DB_PATH
    conn = _connect(db_path)
    try:
        sql = (f"SELECT {name_col} AS plan_name, old_val, new_val, changed_at "
               f"FROM {table} WHERE carrier = ? AND change_type = 'price_change'")
        params = [carrier]
        if plan_name:
            sql += f' AND {name_col} = ?'
            params.append(plan_name)
        if from_date:
            sql += ' AND changed_at >= ?'
            params.append(from_date)
        sql += ' ORDER BY changed_at ASC'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    plan_events = {}
    for pname, old_val, new_val, ts in rows:
        plan_events.setdefault(pname, []).append(
            {'old': old_val, 'new': new_val, 'date': ts[:10]}
        )

    # Keep the 10 plans with the most change events
    top = sorted(plan_events.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    series = []
    for pname, events in top:
        try:
            pts = [{'date': events[0]['date'], 'price': float(events[0]['old'])}]
            for e in events:
                pts.append({'date': e['date'], 'price': float(e['new'])})
            series.append({'plan_name': pname, 'points': pts})
        except (ValueError, TypeError):
            continue
    return series
