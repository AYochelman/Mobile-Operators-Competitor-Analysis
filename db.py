import sqlite3
import json
import os
import re
import zlib
from datetime import datetime, timezone, timedelta

# Bot / crawler User-Agent signature. Non-compliant crawlers ignore robots.txt
# (Disallow: /go/) and rel="sponsored nofollow", hammering the affiliate redirect
# and polluting the click log (a single crawler fired 1,295 junk /go hits across
# the new /esim/<dest>/ SEO pages on 2026-07-10). `is_bot_ua` flags those so the
# /go route can block them AND the attribution reports can exclude them. The bare
# "bot" token catches the vast majority (Googlebot/Bingbot/AhrefsBot/…); the rest
# cover UA strings that omit it (scrapers, HTTP libraries, headless browsers,
# link-preview + uptime fetchers).
_BOT_UA_RE = re.compile(
    r"bot\b|bot/|crawl|spider|slurp|mediapartners|adsbot|bingpreview|"
    r"facebookexternalhit|facebot|embedly|quora|whatsapp|telegram|discord|"
    r"slackbot|twitterbot|linkedinbot|pinterest|redditbot|applebot|yandex|"
    r"baidu|sogou|exabot|ahrefs|semrush|mj12|dotbot|petalbot|bytespider|"
    r"dataforseo|gptbot|oai-searchbot|chatgpt|claudebot|claude-user|ccbot|"
    r"perplexity|amazonbot|google-extended|python-requests|python-urllib|"
    r"curl/|wget|scrapy|headlesschrome|phantomjs|go-http-client|axios|"
    r"node-fetch|okhttp|java/|libwww|apache-httpclient|guzzle|lighthouse|"
    r"uptimerobot|pingdom|statuscake|monitoring|site24x7",
    re.I,
)


def is_bot_ua(ua):
    """True if the User-Agent looks like a bot/crawler/HTTP-library, not a human
    browser. Empty/absent UA is NOT treated as a bot (real browsers always send
    one, but so do some privacy tools — we don't want to over-block)."""
    if not ua:
        return False
    return bool(_BOT_UA_RE.search(ua))

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
    '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd': '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd',  # אנטילים ההולנדיים → אנטילים ההולנדים
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
    '\u05e2\u05d5\u05de\u05df': '\u05e2\u05d5\u05de\u05d0\u05df',                                                              # עומאן → עומן
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d8\u05d5\u05e8\u05e7\u05d9\u05ea': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea',  # קפריסין הטורקית → קפריסין הצפונית
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d9\u05d5\u05d5\u05e0\u05d9\u05ea': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df',                     # קפריסין היוונית → קפריסין
    '\u05de\u05d6\u05e8\u05d7 \u05d8\u05d9\u05de\u05d5\u05e8': '\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4',                                    # מזרח טימור → טימור לסטה
    '\u05de\u05d9\u05d5\u05d8': '\u05de\u05d0\u05d9\u05d5\u05d8',                                                              # מיוט → מאיוט
    '\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd': '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd',           # מלדיביים → האיים המלדיביים
    '\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4': '\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4',                              # כף ורדה → קייפ ורדה
    '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6-\u05d0\u05e4\u05e8\u05d9\u05e7\u05e0\u05d9\u05ea': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea',  # הרפובליקה המרכז-אפריקנית → הרפובליקה המרכז אפריקאית
    '\u05e1\u05d5\u05d0\u05d6\u05d9\u05dc\u05e0\u05d3': '\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9',                                           # סואזילנד → אסוואטיני
    '\u05d0\u05d5\u05dc\u05e0\u05d3': '\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3',                                     # אולנד → איי אולנד
    '\u05e7\u05d5\u05e0\u05d2\u05d5': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5',   # קונגו → הרפובליקה הדמוקרטית של קונגו (per audit 2026-05-16; רפובליקת קונגו kept distinct)      # קונגו → רפובליקת קונגו
    '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5',  # הרפובליקה של קונגו → הרפובליקה הדמוקרטית של קונגו
    '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05de\u05e8\u05d9\u05e7\u05d4)': '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4"\u05d1)',  # איי הבתולה (אמריקה) → איי הבתולה (ארה"ב)
    '\u05d0\u05e0\u05d2\u05dc\u05d9\u05d4': '\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4',                                       # אנגליה → בריטניה
    'Korea': '\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4',                                                   # Korea → דרום קוריאה
    'North America': '\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4',                                           # North America → צפון אמריקה
    '\u05e7\u05d8\u05d0\u05e8': '\u05e7\u05d8\u05e8',                                                                           # קטאר → קטר
    '\u05d0\u05e0\u05d2\u05d9\u05dc\u05d4': '\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4',                                   # אנגילה → אנגווילה
    '\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9': '\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9',                # אסווטיני → אסוואטיני
    '\u05d1\u05d5\u05e6\u05d5\u05d0\u05e0\u05d4': '\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4',                            # בוצואנה → בוטסואנה
    '\u05d2\u05d1\u05d5\u05df': '\u05d2\u05d0\u05d1\u05d5\u05df',                                                                 # גבון → גאבון
    '\u05d2\u05d5\u05d5\u05d3\u05dc\u05d5\u05e4': '\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4',                            # גוודלופ → גוואדלופ
    '\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4': '\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4',                                # כף ורדה → קייפ ורדה
    '\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4 \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea': '\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4',  # קוריאה הדרומית → דרום קוריאה
    '\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea': '\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5',  # קונגו הדמוקרטית → הרפובליקה הדמוקרטית של קונגו
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05d3\u05e8\u05d5\u05de\u05d9\u05ea': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df',  # קפריסין הדרומית → קפריסין
    '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df+': '\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df',                                 # קפריסין+ → קפריסין
    '\u05e4\u05dc\u05e1\u05d8\u05d9\u05df': '\u05d9\u05e9\u05e8\u05d0\u05dc',
    '\u05d4\u05e9\u05d8\u05d7\u05d9\u05dd \u05d4\u05e4\u05dc\u05e1\u05d8\u05d9\u05e0\u05d9\u05d9\u05dd': '\u05d9\u05e9\u05e8\u05d0\u05dc',  # השטחים הפלסטיניים → ישראל
    '\u05d4\u05e9\u05d8\u05d7\u05d9\u05dd \u05d4\u05e4\u05dc\u05e1\u05d8\u05d9\u05e0\u05d9\u05dd': '\u05d9\u05e9\u05e8\u05d0\u05dc',  # השטחים הפלסטינים → ישראל                                                   # פלסטין → ישראל
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
    '\u05e1\u05d9\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df': '\u05e1\u05df \u05de\u05e8\u05d8\u05df',   # סינט מארטן → סן מרטן (per audit 2026-05-16)
    '\u05e1\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df': '\u05e1\u05df \u05de\u05e8\u05d8\u05df',          # סנט מארטן → סן מרטן (per audit 2026-05-16)
    '\u05d0\u05d9\u05d9 \u05d0\u05d6\u05d5\u05e8\u05d9': '\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05d0\u05d6\u05d5\u05e8\u05d9\u05d9\u05dd',  # איי אזורי → האיים האזוריים (per audit 2026-05-16)
    '\u05d0\u05d9\u05d9 \u05d0\u05dc\u05d0\u05e0\u05d3': '\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3',            # איי אלאנד → איי אולנד (per audit 2026-05-16),                   # סינט מארטן → סנט מארטן
    # ── definite-article-doubling dedup (collapse ה+ה / spurious ה prefix on regions) ──
    'ההפיליפינים': 'הפיליפינים',  # ההפיליפינים → הפיליפינים
    'הבלקן': 'בלקן',                                                                              # הבלקן → בלקן
    'הקריביים': 'קריביים',                                    # הקריביים → קריביים
    # ASCII-only-safe: 'aii sishl' -> 'aii siishl' (Seychelles)
    '\u05d0\u05d9\u05d9 \u05e1\u05d9\u05e9\u05dc': '\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc',
    # Kiribati / El Salvador / eSIM70 'Global Package' label
    '\u05e7\u05d9\u05e8\u05d9\u05d1\u05d8\u05d9': '\u05e7\u05d9\u05e8\u05d9\u05d1\u05d0\u05d8\u05d9',
    '\u05d0\u05dc \u05e1\u05dc\u05d5\u05d5\u05d3\u05d5\u05e8': '\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8',
    '\u05d7\u05d1\u05d9\u05dc\u05d4 \u05d2\u05dc\u05d5\u05d1\u05dc\u05d9\u05ea': '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9',
    # Saba (canonical 'sabah' with he-final, drop alef-final)
    '\u05e1\u05d0\u05d1\u05d0': '\u05e1\u05d0\u05d1\u05d4',
    # \u2500\u2500 seven_g / bestconnect / esimplus dedup (2026-05-15) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    # Hebrew geresh (U+05F3) variants \u2014 collapse to ASCII apostrophe canonical
    "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2\u05f3\u05df": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "\u05d0\u05dc\u05d2\u05f3\u05d9\u05e8\u05d9\u05d4": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "\u05d2\u05f3\u05de\u05d9\u05d9\u05e7\u05d4": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "\u05d2\u05f3\u05e8\u05e1\u05d9": "\u05d2'\u05e8\u05d6\u05d9",
    "\u05d8\u05d2\u05f3\u05d9\u05e7\u05d9\u05e1\u05d8\u05df": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "\u05e0\u05d9\u05d6\u05f3\u05e8": "\u05e0\u05d9\u05d2'\u05e8",
    "\u05e4\u05d9\u05d2\u05f3\u05d9": "\u05e4\u05d9\u05d2'\u05d9",
    "\u05e6\u05f3\u05d0\u05d3": "\u05e6'\u05d0\u05d3",
    "\u05e6\u05f3\u05d9\u05dc\u05d4": "\u05e6'\u05d9\u05dc\u05d4",
    "\u05e6\u05f3\u05db\u05d9\u05d4": "\u05e6'\u05db\u05d9\u05d4",
    # Hebrew-name variants
    "\u05e9\u05d5\u05d5\u05d9\u05d9\u05e5": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "\u05e1\u05d5\u05d5\u05d6\u05d9\u05dc\u05e0\u05d3": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d0\u05d5\u05e0\u05d4": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "\u05d4\u05d5\u05d5\u05ea\u05d9\u05e7\u05df": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "\u05e4\u05dc\u05d0\u05d5": "\u05e4\u05d0\u05dc\u05d0\u05d5",
    "\u05e7\u05d5\u05de\u05d5\u05e8\u05d5": "\u05d0\u05d9\u05d9 \u05e7\u05d5\u05de\u05d5\u05e8\u05d5",
    "\u05e7\u05d5\u05e0\u05d2\u05d5 - \u05d1\u05e8\u05d6\u05d0\u05d5\u05d9\u05dc": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "\u05e7\u05d5\u05e0\u05d2\u05d5 - \u05e7\u05d9\u05e0\u05e9\u05d0\u05e1\u05d4": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "\u05de\u05d0\u05e8\u05d9-\u05d2\u05d0\u05dc\u05d0\u05e0\u05d8": "\u05de\u05e8\u05d9-\u05d2\u05dc\u05e0\u05d8",
    "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05e9\u05dc \u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea": '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4"\u05d1)',
    "\u05d4\u05de\u05de\u05dc\u05db\u05d4 \u05d4\u05de\u05d0\u05d5\u05d7\u05d3\u05ea": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2 (\u05de\u05d7\u05d5\u05d6 \u05de\u05e0\u05d4\u05dc\u05d9 \u05de\u05d9\u05d5\u05d7\u05d3 \u05e9\u05dc \u05e1\u05d9\u05df)": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "\u05de\u05e7\u05d0\u05d5 (\u05de\u05d7\u05d5\u05d6 \u05de\u05e0\u05d4\u05dc\u05d9 \u05de\u05d9\u05d5\u05d7\u05d3 \u05e9\u05dc \u05e1\u05d9\u05df)": "\u05de\u05e7\u05d0\u05d5",
    "\u05e1\u05e0\u05d8 \u05d1\u05e8\u05ea\u05d5\u05dc\u05d5\u05de\u05d9\u05d0\u05d5": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05e9\u05dc \u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "\u05d8\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    # ── English country labels from bestconnect / esimplus / seven_g (2026-05-18) ──
    "Angola": "\u05d0\u05e0\u05d2\u05d5\u05dc\u05d4",  # Angola → אנגולה
    "Antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",  # Antilles → אנטילים הולנדיים
    "Azores": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05d0\u05d6\u05d5\u05e8\u05d9\u05d9\u05dd",  # Azores → האיים האזוריים
    "Bailiwick of Guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",  # Bailiwick of Guernsey → גרנזי
    "Bailiwick of Jersey": "\u05d2'\u05e8\u05d6\u05d9",  # Bailiwick of Jersey → ג'רזי
    "Belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",  # Belarus → בלארוס
    "Canary Islands": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05e7\u05e0\u05e8\u05d9\u05d9\u05dd",  # Canary Islands → האיים הקנריים
    "Congo - Brazzaville": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",  # Congo - Brazzaville → רפובליקת קונגו
    "Cuba": "\u05e7\u05d5\u05d1\u05d4",  # Cuba → קובה
    "Democratic Republic of the Congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",  # Democratic Republic of the Congo → הרפובליקה הדמוקרטית של קונגו
    "Equatorial Guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05de\u05e9\u05d5\u05d5\u05e0\u05d9\u05ea",  # Equatorial Guinea → גינאה המשוונית
    "Ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",  # Ethiopia → אתיופיה
    "Iran": "\u05d0\u05d9\u05e8\u05d0\u05df",  # Iran → איראן
    "Ivory Coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",  # Ivory Coast → חוף השנהב
    "Lebanon": "\u05dc\u05d1\u05e0\u05d5\u05df",  # Lebanon → לבנון
    "Libya": "\u05dc\u05d5\u05d1",  # Libya → לוב
    "Macau": "\u05de\u05e7\u05d0\u05d5",  # Macau → מקאו
    "Madeira": "\u05de\u05d3\u05d9\u05d9\u05e8\u05d4",  # Madeira → מדיירה
    "Marie-Galante": "\u05de\u05e8\u05d9-\u05d2\u05dc\u05e0\u05d8",  # Marie-Galante → מרי-גלנט
    "Myanmar": "\u05de\u05d9\u05d0\u05e0\u05de\u05e8",  # Myanmar → מיאנמר
    "Myanmar (Burma)": "\u05de\u05d9\u05d0\u05e0\u05de\u05e8",  # Myanmar (Burma) → מיאנמר
    "North Macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",  # North Macedonia → מקדוניה הצפונית
    "Northern Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",  # Northern Cyprus → קפריסין הצפונית
    "Reunion Islands": "\u05e8\u05d9\u05d5\u05e0\u05d9\u05d5\u05df",  # Reunion Islands → ריוניון
    "Russia": "\u05e8\u05d5\u05e1\u05d9\u05d4",  # Russia → רוסיה
    "Saba": "\u05e1\u05d0\u05d1\u05d4",  # Saba → סאבה
    "Saint Vincent and the Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",  # Saint Vincent and the Grenadines → סנט וינסנט והגרדינים
    "Scotland": "\u05e1\u05e7\u05d5\u05d8\u05dc\u05e0\u05d3",  # Scotland → סקוטלנד
    "Sint Eustatius": "\u05e1\u05d9\u05e0\u05d8 \u05d0\u05d5\u05e1\u05d8\u05d8\u05d9\u05d5\u05e1",  # Sint Eustatius → סינט אוסטטיוס
    "St. Martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",  # St. Martin → סן מרטן
    "St. Vincent & Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",  # St. Vincent & Grenadines → סנט וינסנט והגרדינים
    # ── SimTLV catalog spellings (2026-06-11) ──
    'אלגריה': "אלג'יריה",                                       # אלגריה → אלג'יריה
    'וותיקן': 'ותיקן',                                           # וותיקן → ותיקן
    'טיוואן': 'טייוואן',                                         # טיוואן → טייוואן
    'מלדיבים': 'האיים המלדיביים',                                # מלדיבים → האיים המלדיביים
    'קירגיסטן': 'קירגיזסטן',                                     # קירגיסטן → קירגיזסטן
    'צאד': "צ'אד",                                               # צאד → צ'אד
    'אנגליה (בריטניה)': 'בריטניה',                               # אנגליה (בריטניה) → בריטניה
    'דובאי (איחוד האמירויות הערביות)': 'דובאי',                  # דובאי (איחוד האמירויות הערביות) → דובאי
    'הונג קונג,סין ומקאו': 'הונג קונג, סין ומקאו',               # missing space after comma
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
    conn = sqlite3.connect(path)
    # WAL allows concurrent reads during writes — critical during scrape windows
    # when bulk inserts hold the writer lock for many seconds. Persists in the DB file.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # WAL still allows only ONE writer at a time. Without a busy_timeout, a second
    # writer (e.g. an API POST while the 07:30 scrape is bulk-inserting) fails
    # immediately with "database is locked" instead of waiting. 5s lets it retry.
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path=None):
    conn = _connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                id           INTEGER PRIMARY KEY,
                carrier      TEXT NOT NULL,
                plan_name    TEXT NOT NULL,
                price        REAL,
                data_gb      INTEGER,
                minutes      TEXT,
                extras       TEXT,
                scraped_at   TEXT,
                url          TEXT,
                promo_price  REAL,
                promo_months INTEGER,
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
            CREATE TABLE IF NOT EXISTS esim_push_subscriptions (
                id               INTEGER PRIMARY KEY,
                endpoint         TEXT NOT NULL UNIQUE,
                p256dh           TEXT NOT NULL,
                auth             TEXT NOT NULL,
                destination      TEXT NOT NULL,
                lang             TEXT DEFAULT 'he',
                baseline_price   REAL,
                created_at       TEXT NOT NULL,
                last_notified_at TEXT
            );
            -- Price-drop alerts for the public /mobile-deals page (domestic plans).
            -- Keyed on a carrier id or 'all' — EVENT-driven off the domestic
            -- change log (no baseline column; domestic change detection is
            -- reliable per (carrier, plan_name), unlike global).
            CREATE TABLE IF NOT EXISTS mobile_push_subscriptions (
                id               INTEGER PRIMARY KEY,
                endpoint         TEXT NOT NULL UNIQUE,
                p256dh           TEXT NOT NULL,
                auth             TEXT NOT NULL,
                carrier          TEXT DEFAULT 'all',
                lang             TEXT DEFAULT 'he',
                created_at       TEXT NOT NULL,
                last_notified_at TEXT
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
                terms_url  TEXT,
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
            CREATE TABLE IF NOT EXISTS watchlist (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                carrier    TEXT NOT NULL,
                plan_name  TEXT NOT NULL,
                plan_type  TEXT NOT NULL,
                added_at   TEXT NOT NULL,
                UNIQUE(user_email, carrier, plan_name, plan_type)
            );
            CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_email);
            CREATE TABLE IF NOT EXISTS saved_views (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email   TEXT NOT NULL,
                name         TEXT NOT NULL,
                filters_json TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                UNIQUE(user_email, name)
            );
            CREATE INDEX IF NOT EXISTS idx_saved_views_user ON saved_views(user_email);
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
                ip_hash    TEXT,
                src        TEXT,
                campaign   TEXT,
                user_agent TEXT,
                is_bot     INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_at
                ON affiliate_clicks(clicked_at);
            -- NB: idx_affiliate_clicks_bot is deliberately NOT created here — on a
            -- DB whose affiliate_clicks predates the is_bot column this whole
            -- executescript would die with "no such column: is_bot" before the
            -- ALTER migration below ever runs (bit seed_coupons.py 2026-07-11).
            -- The migration block adds the column and then creates that index.
            -- Anonymous traffic events for the public B2C eSIM compare page
            -- (page views + destination picks). NO PII — ip is hashed, sid is a
            -- random per-browser-session token (not an identity). Powers the B2C
            -- traffic dashboard; deal clicks live in affiliate_clicks (src='esim').
            CREATE TABLE IF NOT EXISTS esim_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sid         TEXT,
                event_type  TEXT NOT NULL,   -- page_view | destination_pick
                destination TEXT,            -- canonical Hebrew dest (on pick / deep-link)
                src         TEXT,            -- acquisition source (utm_source / referrer host)
                campaign    TEXT,            -- specific post/video (utm_campaign / campaign)
                lang        TEXT,
                referrer    TEXT,            -- referrer host only
                ip_hash     TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_esim_events_at
                ON esim_events(created_at);
            -- Anonymous traffic events for the public B2C /mobile-deals page
            -- (domestic plan comparison). Same privacy model as esim_events:
            -- ip hashed, sid is a random per-browser-session token.
            CREATE TABLE IF NOT EXISTS mobile_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sid         TEXT,
                event_type  TEXT NOT NULL,   -- page_view | tab_pick | carrier_click | push_subscribe
                tab         TEXT,            -- domestic | roaming | content
                carrier     TEXT,            -- clicked / subscribed carrier id
                src         TEXT,            -- acquisition source (utm_source / referrer host)
                campaign    TEXT,            -- specific post/video (utm_campaign / campaign)
                lang        TEXT,
                referrer    TEXT,            -- referrer host only
                ip_hash     TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mobile_events_at
                ON mobile_events(created_at);
            -- /mobile-deals email/WhatsApp reminders (public opt-in, no auth).
            -- One row per (submission, kind); rows from one submission share a
            -- token so the unsubscribe link removes the whole signup at once.
            -- kind='better_deal': recurring — alert when another carrier offers
            --   >= the snapshot data for less; best_price_alerted ratchets down
            --   so the same offer never re-alerts.
            -- kind='plan_end': one-shot — fires at end_date - remind_days_before
            --   (done=1 after sending), optionally attaching similar offers.
            -- plan_type: 'domestic' (default) | 'roaming' (abroad_plans row) |
            --   'content' (content_plans row — plan_name holds the service name).
            CREATE TABLE IF NOT EXISTS mobile_reminders (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                token              TEXT NOT NULL,
                email              TEXT,
                phone              TEXT,             -- digits, intl format (972…)
                channel            TEXT NOT NULL DEFAULT 'email',  -- email | whatsapp | both
                kind               TEXT NOT NULL,    -- better_deal | plan_end
                plan_type          TEXT NOT NULL DEFAULT 'domestic',
                carrier            TEXT NOT NULL,
                plan_name          TEXT NOT NULL,
                price              REAL,             -- snapshot at signup
                data_gb            REAL,             -- snapshot (NULL + unlimited=1 → unlimited)
                unlimited          INTEGER DEFAULT 0,
                days               INTEGER,          -- roaming: package duration snapshot
                end_date           TEXT,             -- plan_end: ISO date the plan term ends
                remind_days_before INTEGER,          -- plan_end
                include_offers     INTEGER DEFAULT 1,-- plan_end: attach similar offers
                lang               TEXT DEFAULT 'he',
                best_price_alerted REAL,             -- better_deal dedup ratchet
                last_notified_at   TEXT,
                done               INTEGER DEFAULT 0,
                last_heartbeat_at  TEXT,             -- better_deal: monthly market-pulse email
                followup_sent      INTEGER DEFAULT 0,-- plan_end: renewal follow-up went out
                paid_price         REAL,             -- user-declared ACTUAL monthly price (optional)
                created_at         TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mobile_reminders_token
                ON mobile_reminders(token);
            CREATE TABLE IF NOT EXISTS workspace_invites (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                token        TEXT NOT NULL UNIQUE,
                workspace_id TEXT NOT NULL,
                role         TEXT NOT NULL DEFAULT 'viewer',
                created_by   TEXT,
                created_at   TEXT NOT NULL,
                expires_at   TEXT NOT NULL,
                used_at      TEXT,
                used_by      TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                action       TEXT NOT NULL,
                actor_email  TEXT,
                target_email TEXT,
                workspace_id TEXT,
                details      TEXT,
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_log_at
                ON audit_log(created_at);
            -- Per-user activity tracking (logins, page views, key actions)
            -- powering the super-admin "user activity" dashboard. Super-admins
            -- are deliberately NOT recorded (gated at the API layer in app.py).
            CREATE TABLE IF NOT EXISTS user_activity (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email   TEXT NOT NULL,
                workspace_id TEXT,
                event_type   TEXT NOT NULL,
                path         TEXT,
                details      TEXT,
                user_agent   TEXT,
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_user_activity_email_at
                ON user_activity(user_email, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_user_activity_at
                ON user_activity(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_user_activity_event
                ON user_activity(event_type);
            CREATE TABLE IF NOT EXISTS plan_annotations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT,
                user_email   TEXT NOT NULL,
                carrier      TEXT NOT NULL,
                plan_name    TEXT NOT NULL,
                plan_type    TEXT NOT NULL,
                note         TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_annotations_plan
                ON plan_annotations(workspace_id, carrier, plan_name, plan_type);
            CREATE TABLE IF NOT EXISTS reseller_plans (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                reseller_id  TEXT NOT NULL,
                carrier      TEXT NOT NULL,
                plan_name    TEXT NOT NULL,
                price        REAL,
                data_gb      REAL,
                minutes      INTEGER,
                sms          INTEGER,
                extras       TEXT,
                source_url   TEXT,
                seen_at      TEXT,
                scraped_at   TEXT,
                UNIQUE(reseller_id, carrier, plan_name)
            );
            CREATE INDEX IF NOT EXISTS idx_reseller_plans_carrier
                ON reseller_plans(carrier);
            -- Change log for below-the-line (משווקים) offers — written by
            -- sync_reseller_plans() during the daily 08:15 reseller scrape,
            -- read by the 08:20 morning digest.
            CREATE TABLE IF NOT EXISTS reseller_changes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                reseller_id  TEXT NOT NULL,
                carrier      TEXT NOT NULL,
                plan_name    TEXT NOT NULL,
                change_type  TEXT NOT NULL,
                old_val      TEXT,
                new_val      TEXT,
                changed_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reseller_changes_time
                ON reseller_changes(changed_at);
            -- US operators' prepaid plans for inbound tourists (נוחתים בארה"ב tab).
            -- carrier = US operator id (tmobile_prepaid, mint, visible, ...).
            -- price is ILS-converted at seed time (matches global_plans convention);
            -- original_price keeps the native USD amount.
            CREATE TABLE IF NOT EXISTS usa_tourist_plans (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                carrier        TEXT NOT NULL,
                plan_name      TEXT NOT NULL,
                price          REAL,
                currency       TEXT DEFAULT 'USD',
                original_price REAL,
                data_gb        REAL,
                minutes        INTEGER,
                sms            INTEGER,
                days           INTEGER,
                esim           INTEGER DEFAULT 0,
                network        TEXT,
                extras         TEXT,
                source_url     TEXT,
                scraped_at     TEXT,
                UNIQUE(carrier, plan_name)
            );
            CREATE INDEX IF NOT EXISTS idx_usa_tourist_plans_carrier
                ON usa_tourist_plans(carrier);
            -- Tracks every outbound Anthropic API call so the user can monitor
            -- token usage + computed USD cost locally (Anthropic has no balance API).
            CREATE TABLE IF NOT EXISTS claude_api_usage (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint              TEXT NOT NULL,
                model                 TEXT NOT NULL,
                input_tokens          INTEGER NOT NULL DEFAULT 0,
                output_tokens         INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
                cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd              REAL NOT NULL DEFAULT 0,
                user_email            TEXT,
                workspace_id          TEXT,
                called_at             TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_claude_usage_called_at
                ON claude_api_usage(called_at DESC);
            CREATE INDEX IF NOT EXISTS idx_claude_usage_endpoint
                ON claude_api_usage(endpoint);
            -- Manually-curated discount codes for global eSIM providers (Saily / Holafly / Airalo / etc).
            -- Surfaced as a small pill on PlanCard so users can copy the code straight from the plan.
            -- carrier matches the scraper id used in plans tables (e.g. 'saily', 'holafly').
            CREATE TABLE IF NOT EXISTS provider_coupons (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                carrier         TEXT NOT NULL,
                code            TEXT NOT NULL,
                discount_label  TEXT,        -- short human text e.g. "15% הנחה" / "$5 OFF"
                expires_at      TEXT,        -- ISO date (YYYY-MM-DD) or NULL = no expiry
                source_url      TEXT,        -- where the code was verified
                is_active       INTEGER NOT NULL DEFAULT 1,
                notes           TEXT,        -- admin notes (eligibility, restrictions)
                created_at      TEXT NOT NULL,
                updated_at      TEXT,
                UNIQUE(carrier, code)
            );
            CREATE INDEX IF NOT EXISTS idx_provider_coupons_carrier
                ON provider_coupons(carrier, is_active);
            -- Provider deal/relationship CRM — one row per tracked provider,
            -- powering the super-admin "סטטוס ספקים" dashboard (outreach state,
            -- signed agreement + our commission %, required actions). Coupon
            -- liveness is NOT stored here — it's joined live from provider_coupons
            -- at read time so "is there a coupon in the air" is always accurate.
            -- Manually curated via seed_provider_deals.py (UPSERT by provider_id).
            CREATE TABLE IF NOT EXISTS provider_deals (
                provider_id       TEXT PRIMARY KEY,   -- carrier/provider id
                display_name      TEXT NOT NULL,
                category          TEXT,               -- global | domestic | roaming
                is_israeli        INTEGER DEFAULT 0,
                outreach_status   TEXT,               -- not_contacted|contacted|in_discussion|approved|declined|live
                outreach_last_at  TEXT,               -- ISO date of last contact
                contact           TEXT,               -- email / WhatsApp of the partner contact
                program_network   TEXT,               -- Impact | Everflow | Own | AWIN | CJ | PAP | WhatsApp …
                agreement_status  TEXT,               -- none | pending | signed | live
                commission_pct    REAL,               -- our commission %, NULL if flat-fee/unknown
                commission_note   TEXT,               -- free text e.g. "$5/sale" / "10-20% by volume"
                coupon_note       TEXT,               -- why there is / isn't a live coupon (nuance)
                has_tracking_link INTEGER DEFAULT 0,  -- 1 = an affiliate tracking link is wired
                next_actions      TEXT,               -- what WE need to do next
                priority          TEXT,               -- high | med | low
                is_leak           INTEGER DEFAULT 0,  -- looks monetized but earns us $0
                notes             TEXT,
                updated_at        TEXT
            );
            -- Provider-side plan/checkout tokens keyed by (carrier, plan_name), kept
            -- out of global_plans so they never leak into the UI extras. Currently the
            -- Saily checkout `identifier` used to build the /go deep-link.
            CREATE TABLE IF NOT EXISTS plan_refs (
                carrier     TEXT NOT NULL,
                plan_name   TEXT NOT NULL,
                plan_ref    TEXT,
                updated_at  TEXT,
                PRIMARY KEY (carrier, plan_name)
            );
            -- Speed up the per-carrier filters on the dashboard. UNIQUE(carrier, plan_name)
            -- already covers (carrier) lookups via prefix, but an explicit single-column
            -- index makes the planner's choice predictable across SQLite versions.
            CREATE INDEX IF NOT EXISTS idx_plans_carrier ON plans(carrier);
            CREATE INDEX IF NOT EXISTS idx_global_plans_carrier ON global_plans(carrier);
            CREATE INDEX IF NOT EXISTS idx_abroad_plans_carrier ON abroad_plans(carrier);
            -- The public B2C eSIM feed + hotel guest portals filter/group global_plans
            -- by destination = json_extract(extras,'$[0]'). Without this expression
            -- index every /api/esim/compare, /api/esim/destinations and /api/guest/<slug>
            -- cache-miss full-scans + JSON-parses the whole table. SQLite uses an
            -- expression index for both the `=` filter and the GROUP BY.
            CREATE INDEX IF NOT EXISTS idx_global_plans_dest
                ON global_plans(json_extract(extras, '$[0]'));
            -- changes tables are queried ORDER BY changed_at DESC LIMIT N — needs an index.
            CREATE INDEX IF NOT EXISTS idx_changes_changed_at ON changes(changed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_abroad_changes_changed_at ON abroad_changes(changed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_global_changes_changed_at ON global_changes(changed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_content_changes_changed_at ON content_changes(changed_at DESC);
            -- ===== MOCA Guest Connect (hotels vertical) =====================
            -- A hotel/host that exposes a branded guest portal at /guest/<slug>.
            -- brand_* drive the runtime theme (mirrors workspace brand_config but
            -- needs no Supabase row — public page reads these over the open API).
            CREATE TABLE IF NOT EXISTS hotels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                tagline         TEXT,
                brand_primary   TEXT,        -- c1 — deep brand color (text/hero)
                brand_secondary TEXT,        -- c2 — accent color
                brand_bg        TEXT,        -- page background tint
                logo_url        TEXT,        -- data: URI or hosted URL (optional)
                mono            TEXT,        -- 1-3 char monogram fallback for the avatar
                languages       TEXT,        -- JSON array e.g. ["en","he"]
                default_lang    TEXT DEFAULT 'en',
                commission_note TEXT,        -- free text shown to the operator (e.g. "50/50")
                contact_email   TEXT,
                active          INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL,
                updated_at      TEXT
            );
            -- Anonymous guest-portal events powering the per-hotel analytics
            -- dashboard + affiliate attribution. NO PII — ip is hashed, identity
            -- is never stored (GDPR-safe per Hotel Plan §8).
            CREATE TABLE IF NOT EXISTS guest_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_slug  TEXT NOT NULL,
                event_type  TEXT NOT NULL,   -- view | scan | engage | click | lead
                provider    TEXT,            -- on click: the eSIM/SIM provider id
                plan_name   TEXT,            -- on click: which package
                lang        TEXT,
                country     TEXT,            -- guest origin (from Accept-Language), anonymous
                ip_hash     TEXT,
                user_agent  TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_guest_events_hotel_at
                ON guest_events(hotel_slug, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_guest_events_type
                ON guest_events(event_type);
            -- Inbound sales leads from the public /hotels marketing landing form.
            CREATE TABLE IF NOT EXISTS hotel_leads (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_name   TEXT,
                contact_name TEXT,
                email        TEXT,
                phone        TEXT,
                rooms        INTEGER,
                message      TEXT,
                source       TEXT,
                created_at   TEXT NOT NULL
            );
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
        # Migration: multi-tenant workspace scoping (PR #1)
        # workspace_id is a Supabase UUID stored as TEXT. NULL = legacy rows that
        # belong to the default 'moca-internal' workspace until reassigned.
        for table in ("price_alerts", "push_subscriptions"):
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN workspace_id TEXT")
                conn.commit()
            except Exception:
                pass  # column already exists
        # Migration: store the carrier hidden per subscription for workspace-scoped push
        try:
            conn.execute("ALTER TABLE push_subscriptions ADD COLUMN hidden_carrier TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists
        # Migration: /mobile-deals reminder engagement fields (monthly heartbeat +
        # plan-end renewal follow-up) + roaming/content reminder support
        for col, sql in (("last_heartbeat_at", "TEXT"), ("followup_sent", "INTEGER DEFAULT 0"),
                         ("paid_price", "REAL"),
                         ("plan_type", "TEXT NOT NULL DEFAULT 'domestic'"),
                         ("days", "INTEGER")):
            try:
                conn.execute(f"ALTER TABLE mobile_reminders ADD COLUMN {col} {sql}")
                conn.commit()
            except Exception:
                pass  # column already exists
        # Migration: promo pricing on domestic plans (e.g. "3 חודשים ראשונים ב-39 ₪")
        for col, sql in (("promo_price", "REAL"), ("promo_months", "INTEGER")):
            try:
                conn.execute(f"ALTER TABLE plans ADD COLUMN {col} {sql}")
                conn.commit()
            except Exception:
                pass  # column already exists
        # Migration: external offer fields on coupons. When external_offer_url is set
        # the card renders a link-out button instead of a copyable code (e.g. for
        # third-party benefit aggregators like gooday.co.il that issue per-user codes).
        for col, sql in (("external_offer_url", "TEXT"), ("partner_name", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE provider_coupons ADD COLUMN {col} {sql}")
                conn.commit()
            except Exception:
                pass  # column already exists
        # Migration: attribution on affiliate clicks. `src` = the traffic source
        # channel (e.g. 'esim' for the B2C compare page vs hotel guest portals);
        # `campaign` = the specific content/post (utm_source/utm_campaign) so we can
        # tell WHICH video/post drove the click. Both NULL for legacy rows.
        for col in ("src", "campaign"):
            try:
                conn.execute(f"ALTER TABLE affiliate_clicks ADD COLUMN {col} TEXT")
                conn.commit()
            except Exception:
                pass  # column already exists
        # Migration: bot detection on affiliate clicks. `user_agent` = the raw UA
        # (capped) so a click can be attributed to a human vs a crawler after the
        # fact; `is_bot` = 1 when the /go route flagged the UA as a bot (see
        # is_bot_ua). Attribution reports exclude is_bot=1 so a crawler storm can't
        # masquerade as real traffic. Legacy rows default to 0 (ADD COLUMN default).
        for col, sql in (("user_agent", "TEXT"), ("is_bot", "INTEGER DEFAULT 0")):
            try:
                conn.execute(f"ALTER TABLE affiliate_clicks ADD COLUMN {col} {sql}")
                conn.commit()
            except Exception:
                pass  # column already exists
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_bot "
                         "ON affiliate_clicks(is_bot)")
            conn.commit()
        except Exception:
            pass
        # Migration: terms_url on abroad_plans — the roaming card's "עיקרי התוכנית"
        # PDF. Populated per scrape (e.g. Cellcom's policiesEpi from its abroad API),
        # surfaced by PlanCard's details link with the hardcoded map as a fallback.
        try:
            conn.execute("ALTER TABLE abroad_plans ADD COLUMN terms_url TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists
        # Migration: hotel guest-portal destination localization. `country` is the
        # canonical Hebrew destination (matches global_plans.extras[0]) the portal
        # filters its eSIM feed to. NULL = legacy rows → treated as 'ישראל'.
        try:
            conn.execute("ALTER TABLE hotels ADD COLUMN country TEXT")
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


def log_affiliate_click(provider, plan_id=None, country=None, ip_hash=None,
                        src=None, campaign=None, user_agent=None, is_bot=None,
                        db_path=None):
    if is_bot is None:                       # infer from UA when caller didn't decide
        is_bot = is_bot_ua(user_agent)
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO affiliate_clicks
                   (provider, plan_id, country, clicked_at, ip_hash, src, campaign,
                    user_agent, is_bot)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (provider, plan_id, country, datetime.now(timezone.utc).isoformat(),
             ip_hash, src, campaign, (user_agent or "")[:300] or None,
             1 if is_bot else 0)
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
               WHERE clicked_at >= ? AND COALESCE(is_bot, 0) = 0
               GROUP BY provider, date(clicked_at)
               ORDER BY date DESC, clicks DESC""",
            (cutoff,)
        ).fetchall()
        return [{"provider": r[0], "date": r[1], "clicks": r[2]} for r in rows]
    finally:
        conn.close()


def get_affiliate_attribution(days=30, db_path=None):
    """Click attribution breakdown by traffic source (`src`) and by campaign
    (the specific post/video, from utm). Lets us see WHICH channel/content drove
    the clicks — separate from get_affiliate_stats so its provider/date shape
    (consumed by SettingsPage) stays unchanged. Legacy rows have NULL src/campaign,
    surfaced as 'ללא תיוג' / 'untagged' so they're still counted. Bot/crawler
    clicks (is_bot=1) are excluded so a crawler storm can't masquerade as real
    traffic; the count that WAS filtered is returned as `bot_clicks`."""
    conn = _connect(db_path)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        by_source = conn.execute(
            """SELECT COALESCE(NULLIF(src, ''), '—') AS src, COUNT(*) AS clicks
               FROM affiliate_clicks WHERE clicked_at >= ? AND COALESCE(is_bot,0) = 0
               GROUP BY src ORDER BY clicks DESC""",
            (cutoff,)
        ).fetchall()
        by_campaign = conn.execute(
            """SELECT COALESCE(NULLIF(campaign, ''), '—') AS campaign,
                      COALESCE(NULLIF(src, ''), '—') AS src, COUNT(*) AS clicks
               FROM affiliate_clicks
               WHERE clicked_at >= ? AND COALESCE(is_bot,0) = 0
                 AND campaign IS NOT NULL AND campaign != ''
               GROUP BY campaign, src ORDER BY clicks DESC""",
            (cutoff,)
        ).fetchall()
        bot_clicks = conn.execute(
            "SELECT COUNT(*) FROM affiliate_clicks "
            "WHERE clicked_at >= ? AND is_bot = 1", (cutoff,)
        ).fetchone()[0]
        return {
            "by_source":   [{"src": r[0], "clicks": r[1]} for r in by_source],
            "by_campaign": [{"campaign": r[0], "src": r[1], "clicks": r[2]} for r in by_campaign],
            "bot_clicks":  bot_clicks,
        }
    finally:
        conn.close()


def log_esim_event(event_type, sid=None, destination=None, src=None, campaign=None,
                   lang=None, referrer=None, ip_hash=None, db_path=None):
    """Best-effort anonymous B2C eSIM page event. NEVER raises into the caller."""
    if not event_type:
        return
    try:
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO esim_events "
                "(sid, event_type, destination, src, campaign, lang, referrer, ip_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ((sid or "")[:40] or None, str(event_type)[:30], destination,
                 (src or "")[:60] or None, (campaign or "")[:80] or None,
                 (lang or "")[:8] or None, (referrer or "")[:120] or None, ip_hash,
                 datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def log_mobile_event(event_type, sid=None, tab=None, carrier=None, src=None,
                     campaign=None, lang=None, referrer=None, ip_hash=None, db_path=None):
    """Best-effort anonymous B2C /mobile-deals page event. NEVER raises into the caller."""
    if not event_type:
        return
    try:
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO mobile_events "
                "(sid, event_type, tab, carrier, src, campaign, lang, referrer, ip_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ((sid or "")[:40] or None, str(event_type)[:30],
                 (tab or "")[:20] or None, (carrier or "")[:30] or None,
                 (src or "")[:60] or None, (campaign or "")[:80] or None,
                 (lang or "")[:8] or None, (referrer or "")[:120] or None, ip_hash,
                 datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def get_esim_analytics(days=30, db_path=None):
    """Traffic dashboard for the public B2C eSIM page: views / sessions / destination
    picks from esim_events + deal clicks from affiliate_clicks (src='esim'), merged
    into a funnel by day / destination / source / campaign. days=0 = lifetime."""
    conn = _connect(db_path)
    try:
        ev_time, cl_time, pev, pcl = "", "", [], []
        if days and days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            ev_time, cl_time, pev, pcl = " AND created_at >= ?", " AND clicked_at >= ?", [cutoff], [cutoff]

        # Human deal clicks only — bot/crawler /go hits (is_bot=1) are excluded from
        # every clicks aggregate so the funnel reflects real traffic. The filtered
        # count is surfaced separately as totals.bot_clicks for transparency.
        nobot = " AND COALESCE(is_bot,0) = 0"

        one  = lambda sql, p=(): (conn.execute(sql, p).fetchone() or [0])[0]
        rows = lambda sql, p=(): conn.execute(sql, p).fetchall()

        views    = one(f"SELECT COUNT(*) FROM esim_events WHERE event_type='page_view'{ev_time}", pev)
        sessions = one(f"SELECT COUNT(DISTINCT sid) FROM esim_events WHERE event_type='page_view' AND sid IS NOT NULL{ev_time}", pev)
        picks    = one(f"SELECT COUNT(*) FROM esim_events WHERE event_type='destination_pick'{ev_time}", pev)
        clicks   = one(f"SELECT COUNT(*) FROM affiliate_clicks WHERE src='esim'{nobot}{cl_time}", pcl)
        bot_clicks = one(f"SELECT COUNT(*) FROM affiliate_clicks WHERE src='esim' AND is_bot=1{cl_time}", pcl)

        v_day = dict(rows(f"SELECT date(created_at), COUNT(*) FROM esim_events WHERE event_type='page_view'{ev_time} GROUP BY 1", pev))
        c_day = dict(rows(f"SELECT date(clicked_at), COUNT(*) FROM affiliate_clicks WHERE src='esim'{nobot}{cl_time} GROUP BY 1", pcl))
        by_day = [{"date": d, "views": v_day.get(d, 0), "clicks": c_day.get(d, 0)} for d in sorted(set(v_day) | set(c_day))]

        d_pick  = dict(rows(f"SELECT destination, COUNT(*) FROM esim_events WHERE event_type='destination_pick' AND destination IS NOT NULL{ev_time} GROUP BY destination", pev))
        d_click = dict(rows(f"SELECT country, COUNT(*) FROM affiliate_clicks WHERE src='esim' AND country IS NOT NULL{nobot}{cl_time} GROUP BY country", pcl))
        top_destinations = sorted(
            [{"destination": k, "picks": d_pick.get(k, 0), "clicks": d_click.get(k, 0)} for k in (set(d_pick) | set(d_click))],
            key=lambda r: r["picks"] + r["clicks"], reverse=True)[:12]

        by_source = [{"src": r[0], "views": r[1]} for r in rows(
            f"SELECT COALESCE(NULLIF(src,''),'—'), COUNT(*) FROM esim_events WHERE event_type='page_view'{ev_time} GROUP BY 1 ORDER BY 2 DESC", pev)][:12]

        c_views  = dict(rows(f"SELECT campaign, COUNT(*) FROM esim_events WHERE event_type='page_view' AND campaign IS NOT NULL AND campaign!=''{ev_time} GROUP BY campaign", pev))
        c_clicks = dict(rows(f"SELECT campaign, COUNT(*) FROM affiliate_clicks WHERE src='esim' AND campaign IS NOT NULL AND campaign!=''{nobot}{cl_time} GROUP BY campaign", pcl))
        by_campaign = sorted(
            [{"campaign": k, "views": c_views.get(k, 0), "clicks": c_clicks.get(k, 0)} for k in (set(c_views) | set(c_clicks))],
            key=lambda r: r["views"] + r["clicks"], reverse=True)[:15]

        conv = round(clicks / views * 100, 1) if views else 0.0
        return {
            "totals": {"views": views, "sessions": sessions, "picks": picks, "clicks": clicks, "conversion": conv, "bot_clicks": bot_clicks},
            "by_day": by_day,
            "top_destinations": top_destinations,
            "by_source": by_source,
            "by_campaign": by_campaign,
        }
    finally:
        conn.close()


# ── MOCA Guest Connect (hotels vertical) ───────────────────────────────────
_ISRAEL_HE = "ישראל"  # ישראל — canonical destination value (matches _DEST_NORM)

# Cruise (ship) eSIM packages. A few providers sell dedicated at-sea/cruise data,
# each under its own destination label (Maya's "global + cruise", VOYE's "cruise at
# sea"). The public B2C compare page surfaces them all under one synthetic
# destination — "קרוז" (cruise) — so it can be pinned like a country: get_esim_destinations
# collapses the sources into it, and get_esim_deals_for_destination("קרוז") unions
# them back. Add a provider's cruise label here as it appears (verified against
# global_plans.extras[0]).
_CRUISE_DEST_HE = "קרוז"  # קרוז — synthetic B2C cruise destination
_CRUISE_SOURCE_DESTS = (
    "גלובלי ושייט",   # Maya — unlimited global + cruise tiers
    "קרוז בספינה",     # VOYE — cruise at sea
    "קרוז - אמריקה וקריביים",  # GigSky cruise buckets ↓
    "קרוז - אסיה פסיפיק",
    "קרוז - אירופה",
    "קרוז - עולמי",
    "קרוז - המזרח התיכון",
    "קרוז - בים בלבד",
)

_HOTEL_COLS = ("slug", "name", "tagline", "brand_primary", "brand_secondary",
               "brand_bg", "logo_url", "mono", "languages", "default_lang",
               "commission_note", "contact_email", "active", "country",
               "created_at", "updated_at")


def _hotel_row_to_dict(r):
    d = dict(zip(_HOTEL_COLS, r))
    try:
        d["languages"] = json.loads(d["languages"]) if d["languages"] else ["en", "he"]
    except Exception:
        d["languages"] = ["en", "he"]
    d["active"] = bool(d["active"])
    d["country"] = d.get("country") or "ישראל"  # default: ישראל
    return d


def upsert_hotel(data, db_path=None):
    """Create or update a hotel by slug. `data` is a dict; unknown keys ignored.
    Returns the stored hotel dict."""
    slug = str(data.get("slug") or "").strip().lower()
    if not slug or not str(data.get("name") or "").strip():
        raise ValueError("slug and name are required")
    now = datetime.now(timezone.utc).isoformat()
    langs = data.get("languages") or ["en", "he"]
    conn = _connect(db_path)
    try:
        conn.execute("""
            INSERT INTO hotels (slug, name, tagline, brand_primary, brand_secondary,
                                brand_bg, logo_url, mono, languages, default_lang,
                                commission_note, contact_email, active, country,
                                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name            = excluded.name,
                tagline         = excluded.tagline,
                brand_primary   = excluded.brand_primary,
                brand_secondary = excluded.brand_secondary,
                brand_bg        = excluded.brand_bg,
                logo_url        = excluded.logo_url,
                mono            = excluded.mono,
                languages       = excluded.languages,
                default_lang    = excluded.default_lang,
                commission_note = excluded.commission_note,
                contact_email   = excluded.contact_email,
                active          = excluded.active,
                country         = excluded.country,
                updated_at      = excluded.updated_at
        """, (
            slug, str(data["name"]).strip(), data.get("tagline"),
            data.get("brand_primary"), data.get("brand_secondary"), data.get("brand_bg"),
            data.get("logo_url"), data.get("mono"),
            json.dumps(langs, ensure_ascii=False), data.get("default_lang", "en"),
            data.get("commission_note"), data.get("contact_email"),
            1 if data.get("active", True) else 0,
            str(data.get("country") or "ישראל").strip(), now, now,
        ))
        conn.commit()
    finally:
        conn.close()
    return get_hotel(slug, db_path=db_path)


def get_hotel(slug, db_path=None):
    conn = _connect(db_path)
    try:
        r = conn.execute(
            f"SELECT {', '.join(_HOTEL_COLS)} FROM hotels WHERE slug=?",
            ((slug or "").strip().lower(),)
        ).fetchone()
        return _hotel_row_to_dict(r) if r else None
    finally:
        conn.close()


def list_hotels(db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {', '.join(_HOTEL_COLS)} FROM hotels ORDER BY active DESC, name"
        ).fetchall()
        return [_hotel_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def delete_hotel(slug, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM hotels WHERE slug=?", ((slug or "").strip().lower(),))
        conn.commit()
    finally:
        conn.close()


def log_guest_event(hotel_slug, event_type, provider=None, plan_name=None,
                    lang=None, country=None, ip_hash=None, user_agent=None, db_path=None):
    """Best-effort anonymous guest-portal event. NEVER raises into the caller."""
    if not hotel_slug or not event_type:
        return
    try:
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO guest_events "
                "(hotel_slug, event_type, provider, plan_name, lang, country, ip_hash, user_agent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ((hotel_slug or "").strip().lower(), event_type, provider, plan_name,
                 lang, country, ip_hash, (user_agent or "")[:400] or None,
                 datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def get_guest_analytics(slug, days=30, db_path=None):
    """Per-hotel anonymous analytics for the operator dashboard. days=0 = lifetime."""
    slug = (slug or "").strip().lower()
    conn = _connect(db_path)
    try:
        where = "WHERE hotel_slug=?"
        params = [slug]
        if days and days > 0:
            where += " AND created_at >= ?"
            params.append((datetime.now(timezone.utc) - timedelta(days=days)).isoformat())

        totals = {"view": 0, "scan": 0, "engage": 0, "click": 0, "lead": 0}
        for et, n in conn.execute(
            f"SELECT event_type, COUNT(*) FROM guest_events {where} GROUP BY event_type", params
        ).fetchall():
            totals[et] = n

        daily = {}
        for d, et, n in conn.execute(
            f"SELECT date(created_at) AS d, event_type, COUNT(*) FROM guest_events {where} "
            f"GROUP BY d, event_type ORDER BY d", params
        ).fetchall():
            row = daily.setdefault(d, {"date": d, "open": 0, "click": 0})
            if et in ("view", "scan"):
                row["open"] += n
            elif et == "click":
                row["click"] += n

        by_provider = [
            {"provider": p, "clicks": n}
            for p, n in conn.execute(
                f"SELECT provider, COUNT(*) AS c FROM guest_events {where} AND event_type='click' "
                f"AND provider IS NOT NULL GROUP BY provider ORDER BY c DESC", params
            ).fetchall()
        ]
        by_lang = [
            {"lang": (lg or "?"), "count": n}
            for lg, n in conn.execute(
                f"SELECT lang, COUNT(*) AS c FROM guest_events {where} AND event_type IN ('view','scan') "
                f"GROUP BY lang ORDER BY c DESC", params
            ).fetchall()
        ]
        by_country = [
            {"country": (co or "?"), "count": n}
            for co, n in conn.execute(
                f"SELECT country, COUNT(*) AS c FROM guest_events {where} AND event_type IN ('view','scan') "
                f"AND country IS NOT NULL GROUP BY country ORDER BY c DESC LIMIT 8", params
            ).fetchall()
        ]
        opens = totals["view"] + totals["scan"]
        return {
            "slug": slug, "days": days,
            "totals": totals,
            "opens": opens,
            "funnel": {"opens": opens, "engaged": totals["engage"], "clicks": totals["click"]},
            "daily": list(daily.values()),
            "by_provider": by_provider,
            "by_lang": by_lang,
            "by_country": by_country,
        }
    finally:
        conn.close()


def get_esim_deals_for_destination(destination=None, db_path=None):
    """Live global eSIM plans whose destination (extras[0]) is `destination` — the
    guest portal's core feed. `destination` is the canonical Hebrew country string
    (e.g. 'ישראל', 'קפריסין'); defaults to Israel. Returns rows sorted by price
    (cheapest first)."""
    dest = (destination or _ISRAEL_HE)
    conn = _connect(db_path)
    try:
        if dest == _CRUISE_DEST_HE:
            # Synthetic cruise destination: union every provider's cruise bucket.
            placeholders = ",".join("?" * len(_CRUISE_SOURCE_DESTS))
            rows = conn.execute(
                "SELECT carrier, plan_name, price, currency, original_price, days, data_gb, esim, extras, scraped_at "
                f"FROM global_plans WHERE json_extract(extras, '$[0]') IN ({placeholders}) AND price IS NOT NULL "
                "ORDER BY price",
                _CRUISE_SOURCE_DESTS
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, currency, original_price, days, data_gb, esim, extras, scraped_at "
                "FROM global_plans WHERE json_extract(extras, '$[0]') = ? AND price IS NOT NULL "
                "ORDER BY price",
                (dest,)
            ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "price": r[2], "currency": r[3],
             "original_price": r[4], "days": r[5], "data_gb": r[6], "esim": bool(r[7]),
             "extras": json.loads(r[8]) if r[8] else [], "scraped_at": r[9]}
            for r in rows
        ]
    finally:
        conn.close()


def get_israel_esim_deals(db_path=None):
    """Back-compat wrapper — Israel-only eSIM feed."""
    return get_esim_deals_for_destination(_ISRAEL_HE, db_path=db_path)


def get_esim_alert_floor(destination, db_path=None):
    """The ₪ price the B2C price-drop alerts track: cheapest TRIP-SIZED deal for
    the destination (≥5GB or unlimited, ≥7 days or no day info). The absolute
    catalog min is a ~₪1 daily/100MB package whose moves are meaningless to a
    traveler — and sits below the alert threshold anyway. Falls back to the
    overall min when no deal matches the filter (tiny destinations)."""
    deals = get_esim_deals_for_destination(destination, db_path=db_path)
    prices = [d["price"] for d in deals if d.get("price")
              and (d.get("data_gb") is None or d["data_gb"] >= 5)
              and (d.get("days") is None or d["days"] >= 7)]
    if not prices:
        prices = [d["price"] for d in deals if d.get("price")]
    return min(prices) if prices else None


def get_esim_destinations(db_path=None):
    """Distinct destinations (extras[0]) that currently carry live global-eSIM
    deals, each with a deal count + cheapest price. Powers the public consumer
    compare page's destination picker. Sorted by deal count (most-covered first),
    so the picker can surface the best-served destinations as quick picks."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT json_extract(extras, '$[0]') AS dest, COUNT(*) AS n, MIN(price) AS minp "
            "FROM global_plans WHERE price IS NOT NULL "
            "AND dest IS NOT NULL AND dest != '' "
            "GROUP BY dest ORDER BY n DESC"
        ).fetchall()
        out = []
        cruise_n, cruise_min = 0, None
        for dest, n, minp in rows:
            # Fold every provider's cruise bucket into one synthetic "קרוז" entry so
            # the picker shows a single, pinnable cruise destination (see _assemble).
            if dest in _CRUISE_SOURCE_DESTS:
                cruise_n += n
                if minp is not None and (cruise_min is None or minp < cruise_min):
                    cruise_min = minp
                continue
            out.append({"destination": dest, "count": n, "min_price": minp})
        if cruise_n:
            out.append({"destination": _CRUISE_DEST_HE, "count": cruise_n, "min_price": cruise_min})
            out.sort(key=lambda d: d["count"], reverse=True)  # keep most-covered first
        return out
    finally:
        conn.close()


def save_hotel_lead(data, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO hotel_leads (hotel_name, contact_name, email, phone, rooms, message, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data.get("hotel_name"), data.get("contact_name"), data.get("email"),
             data.get("phone"), data.get("rooms"), data.get("message"),
             data.get("source", "/hotels"), datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_hotel_leads(limit=200, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT hotel_name, contact_name, email, phone, rooms, message, source, created_at "
            "FROM hotel_leads ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        cols = ("hotel_name", "contact_name", "email", "phone", "rooms", "message", "source", "created_at")
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def log_claude_usage(endpoint, model, usage, cost_usd,
                     user_email=None, workspace_id=None, db_path=None):
    """Record a single Anthropic API call's token usage + computed USD cost.

    `usage` is the raw `usage` dict from the Anthropic API response.
    Cost is computed by the caller (app.py owns the pricing table).
    """
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO claude_api_usage
                 (endpoint, model, input_tokens, output_tokens,
                  cache_read_tokens, cache_creation_tokens,
                  cost_usd, user_email, workspace_id, called_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                endpoint, model,
                int(usage.get("input_tokens") or 0),
                int(usage.get("output_tokens") or 0),
                int(usage.get("cache_read_input_tokens") or 0),
                int(usage.get("cache_creation_input_tokens") or 0),
                float(cost_usd or 0),
                user_email, workspace_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_claude_usage_recent(limit=100, db_path=None):
    """Return the N most recent Anthropic API calls."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT endpoint, model, input_tokens, output_tokens,
                      cache_read_tokens, cache_creation_tokens,
                      cost_usd, user_email, workspace_id, called_at
               FROM claude_api_usage
               ORDER BY called_at DESC
               LIMIT ?""",
            (int(limit),),
        ).fetchall()
        cols = ['endpoint', 'model', 'input_tokens', 'output_tokens',
                'cache_read_tokens', 'cache_creation_tokens',
                'cost_usd', 'user_email', 'workspace_id', 'called_at']
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def get_claude_usage_summary(days=30, db_path=None):
    """Return per-day / per-model / per-endpoint aggregates for the last N days,
    plus a grand total. `days=0` returns lifetime totals."""
    conn = _connect(db_path)
    try:
        if days and days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            where = "WHERE called_at >= ?"
            params = (cutoff,)
        else:
            where = ""
            params = ()

        total_row = conn.execute(
            f"""SELECT COUNT(*),
                       COALESCE(SUM(input_tokens), 0),
                       COALESCE(SUM(output_tokens), 0),
                       COALESCE(SUM(cache_read_tokens), 0),
                       COALESCE(SUM(cache_creation_tokens), 0),
                       COALESCE(SUM(cost_usd), 0)
                  FROM claude_api_usage {where}""",
            params,
        ).fetchone()

        by_day = conn.execute(
            f"""SELECT substr(called_at, 1, 10) AS day,
                       COUNT(*)             AS calls,
                       SUM(cost_usd)        AS cost_usd,
                       SUM(input_tokens + cache_read_tokens + cache_creation_tokens) AS in_tok,
                       SUM(output_tokens)   AS out_tok
                  FROM claude_api_usage {where}
              GROUP BY day
              ORDER BY day DESC""",
            params,
        ).fetchall()

        by_model = conn.execute(
            f"""SELECT model,
                       COUNT(*)      AS calls,
                       SUM(cost_usd) AS cost_usd
                  FROM claude_api_usage {where}
              GROUP BY model
              ORDER BY cost_usd DESC""",
            params,
        ).fetchall()

        by_endpoint = conn.execute(
            f"""SELECT endpoint,
                       COUNT(*)      AS calls,
                       SUM(cost_usd) AS cost_usd
                  FROM claude_api_usage {where}
              GROUP BY endpoint
              ORDER BY cost_usd DESC""",
            params,
        ).fetchall()

        return {
            "window_days": days,
            "total": {
                "calls":                 total_row[0],
                "input_tokens":          total_row[1],
                "output_tokens":         total_row[2],
                "cache_read_tokens":     total_row[3],
                "cache_creation_tokens": total_row[4],
                "cost_usd":              round(total_row[5], 6),
            },
            "by_day":      [{"day": r[0], "calls": r[1], "cost_usd": round(r[2] or 0, 6),
                             "input_tokens": r[3], "output_tokens": r[4]} for r in by_day],
            "by_model":    [{"model": r[0], "calls": r[1], "cost_usd": round(r[2] or 0, 6)} for r in by_model],
            "by_endpoint": [{"endpoint": r[0], "calls": r[1], "cost_usd": round(r[2] or 0, 6)} for r in by_endpoint],
        }
    finally:
        conn.close()


def get_claude_spend(since_iso=None, db_path=None):
    """Total logged USD spend + call count since `since_iso` (or lifetime when
    None), plus the earliest call timestamp.

    Used by the budget / remaining-balance estimate. Deliberately independent
    of the display window so the remaining balance stays stable as the user
    toggles the 7/30/90-day views — the balance depends on *all* spend since the
    budget baseline, not on what the chart happens to show."""
    conn = _connect(db_path)
    try:
        if since_iso:
            row = conn.execute(
                """SELECT COALESCE(SUM(cost_usd), 0), COUNT(*), MIN(called_at)
                     FROM claude_api_usage WHERE called_at >= ?""",
                (since_iso,),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT COALESCE(SUM(cost_usd), 0), COUNT(*), MIN(called_at)
                     FROM claude_api_usage"""
            ).fetchone()
        return {"cost_usd": round(row[0] or 0, 6), "calls": row[1] or 0,
                "first_call_at": row[2]}
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
        best_deal = None  # (carrier, value) of the single best per-unit deal; overrides `cheapest`
        if category == 'domestic':
            # Weighted blended price-per-GB (SUM(price)/SUM(GB)) per carrier. A naive
            # AVG(price/data_gb) is an average-of-ratios: a tiny-data plan (e.g. 019's
            # 100MB plan at ~102 ILS/GB) dominates the mean and falsely ranks a budget
            # carrier as the most expensive. Weighting by GB lets large plans count
            # proportionally, which is the intuitively correct blended rate.
            rows = conn.execute("""
                SELECT carrier, SUM(price) * 1.0 / SUM(data_gb) AS v
                FROM plans
                WHERE data_gb > 0 AND price IS NOT NULL
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa/GB'
            # "Most worthwhile" card = the single best price-per-GB deal on the market.
            # With exactly one MIN() aggregate, SQLite draws the bare `carrier` column
            # from the row that holds the minimum value.
            best_deal = conn.execute("""
                SELECT carrier, MIN(price * 1.0 / data_gb) AS v
                FROM plans
                WHERE data_gb > 0 AND price IS NOT NULL
            """).fetchone()
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

        # 3 decimals (not 2): carriers selling "unlimited" plans at huge fair-use caps
        # (e.g. We-Com's 10,000GB) land at ~0.003-0.005 ₪/GB, which rounds to a misleading
        # 0.0 at 2 decimals. 3 decimals keeps those values visible; larger values are
        # unaffected.
        chart_data = [
            {'carrier': r[0], 'value': round(float(r[1]), 3)}
            for r in rows if r[1] is not None
        ]
        # For ₪/GB categories the "most worthwhile" card shows the single best deal
        # (best_deal); other categories fall back to the cheapest carrier by chart metric.
        if best_deal is not None and best_deal[1] is not None:
            cheapest = {'carrier': best_deal[0], 'value': round(float(best_deal[1]), 3)}
        else:
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
        # "Most aggressive" = the carrier with the most price DROPS in the last 7 days.
        # When nobody cut prices there is no aggressor — return '-' / 0 rather than
        # falling back to the most-expensive carrier (chart_data[-1]), which would
        # mislabel a passive, pricey carrier as "aggressive" with 0 drops.
        if drop_rows:
            most_aggressive_carrier = drop_rows[0][0]
            most_aggressive_count = drop_rows[0][1]
        else:
            most_aggressive_carrier = '-'
            most_aggressive_count = 0

        return {
            'cheapest':        {'carrier': cheapest['carrier'], 'value': cheapest['value'], 'unit': unit},
            'most_aggressive': {'carrier': most_aggressive_carrier, 'changes': most_aggressive_count},
            'weekly_changes':  {'total': total_drops + total_rises, 'drops': total_drops, 'rises': total_rises},
            'chart_data':      chart_data,
            'top_plans':       top_plans,
        }
    finally:
        conn.close()


def filter_already_notified(changes, table_name, key_field='carrier', within_hours=24, db_path=None):
    """Drop changes that were already recorded in `table_name` within the last N hours.

    Why: if a plan disappears from a carrier's site for several scrapes in a row,
    detect_changes will report the same `removed_plan` event on every scrape. The
    user only wants to be notified ONCE per change. This helper reads the change
    log and filters out anything already seen.

    The key tuple is (key_field, plan_name, change_type) — typically that's
    (carrier, plan_name, change_type), or for content (service, carrier, change_type).

    Returns the subset of `changes` that has NOT been seen recently.
    """
    if not changes:
        return []
    cutoff = (datetime.now() - timedelta(hours=within_hours)).isoformat()
    conn = _connect(db_path)
    try:
        # content_changes uses (service, carrier) as its identity rather than
        # (carrier, plan_name); pick the column accordingly.
        if table_name == 'content_changes':
            rows = conn.execute(
                "SELECT service, carrier, change_type FROM content_changes WHERE changed_at >= ?",
                (cutoff,)
            ).fetchall()
            already = {(r[0], r[1], r[2]) for r in rows}
            return [c for c in changes
                    if (c.get('service'), c.get('carrier'), c.get('change_type')) not in already]
        rows = conn.execute(
            f"SELECT {key_field}, plan_name, change_type FROM {table_name} WHERE changed_at >= ?",
            (cutoff,)
        ).fetchall()
        already = {(r[0], r[1], r[2]) for r in rows}
    finally:
        conn.close()
    return [c for c in changes
            if (c.get(key_field), c.get('plan_name'), c.get('change_type')) not in already]


def _delete_stale_carrier_rows(conn, table, plans):
    """Delete rows for carriers that returned plans, when those rows aren't in the new scrape.

    Guard: only acts on carriers that returned ≥1 plan in `plans`. A carrier
    that returned 0 plans (e.g. blocked by Incapsula) leaves its existing rows
    untouched — same logic as detect_changes' removal guard.
    """
    by_carrier = {}
    for p in plans:
        by_carrier.setdefault(p["carrier"], set()).add(p["plan_name"])
    for carrier, names in by_carrier.items():
        placeholders = ",".join("?" * len(names))
        conn.execute(
            f"DELETE FROM {table} WHERE carrier=? AND plan_name NOT IN ({placeholders})",
            (carrier, *names)
        )


def save_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        _delete_stale_carrier_rows(conn, "plans", plans)
        now = datetime.now().isoformat()
        # One executemany instead of N execute() round-trips — same single
        # transaction/commit, but a much shorter writer-lock window.
        rows = [(
            plan["carrier"], plan["plan_name"], plan.get("price"),
            plan.get("data_gb"), plan.get("minutes"),
            json.dumps(plan.get("extras", []), ensure_ascii=False),
            now, plan.get("url"),
            plan.get("promo_price"), plan.get("promo_months")
        ) for plan in plans]
        conn.executemany("""
                INSERT INTO plans (carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url, promo_price, promo_months)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price        = excluded.price,
                    data_gb      = excluded.data_gb,
                    minutes      = excluded.minutes,
                    extras       = excluded.extras,
                    scraped_at   = excluded.scraped_at,
                    url          = excluded.url,
                    promo_price  = excluded.promo_price,
                    promo_months = excluded.promo_months
            """, rows)
        conn.commit()
    finally:
        conn.close()


def get_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url, promo_price, promo_months "
                "FROM plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url, promo_price, promo_months "
                "FROM plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "data_gb": r[3], "minutes": r[4],
                "extras": json.loads(r[5]) if r[5] else [],
                "scraped_at": r[6], "url": r[7],
                "promo_price": r[8], "promo_months": r[9]
            }
            for r in rows
        ]
    finally:
        conn.close()


def save_global_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        # Batched: this is the heaviest writer (Terminal eSIM alone ≈2,500 rows),
        # so collapsing per-row execute() into two executemany() calls cuts the
        # writer-lock window that other writers (API POSTs, other scrapers) contend on.
        rows = [(
            plan["carrier"], plan["plan_name"], plan.get("price"),
            plan.get("currency"), plan.get("original_price"),
            plan.get("days"), plan.get("data_gb"), plan.get("minutes"),
            plan.get("sms"), 1 if plan.get("esim", True) else 0,
            json.dumps(_norm_extras(plan.get("extras", [])), ensure_ascii=False), now
        ) for plan in plans]
        conn.executemany("""
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
            """, rows)
        ref_rows = [
            (plan["carrier"], plan["plan_name"], plan["plan_ref"], now)
            for plan in plans if plan.get("plan_ref")
        ]
        if ref_rows:
            conn.executemany("""
                    INSERT INTO plan_refs (carrier, plan_name, plan_ref, updated_at)
                    VALUES (?,?,?,?)
                    ON CONFLICT(carrier, plan_name) DO UPDATE SET
                        plan_ref   = excluded.plan_ref,
                        updated_at = excluded.updated_at
                """, ref_rows)
        conn.commit()
    finally:
        conn.close()



# ── Guarded purge of stale global rows ────────────────────────────────────────
# save_global_plans deliberately never deletes (per-country scrapers fail
# partially all the time), so rows for tiers/destinations a provider dropped
# months ago kept being served by /api/global-plans, the /esim-deals deals +
# alert floor, etc. (2026-09-03: gomoworld had 894 rows vs a 716-plan live
# catalog, 178 of them with prices from an old currency bug; 17% of all global
# rows were stale). This purge deletes them, but only when the scrape that just
# ran LOOKS COMPLETE for that carrier. "Complete" is judged against what the DB
# saw for the carrier within a rolling window (rows + destinations with
# scraped_at in the last `window_days`), NOT against the total row count:
# a months-old backlog ages out of the baseline and gets purged (sparks/tuki/
# orbit sat at ~51% stale for months), while a per-country scraper that missed
# destinations RECENTLY still counts them and blocks the purge.
GLOBAL_PURGE_DEFAULTS = {
    "min_ratio":    0.90,  # fresh rows / rows seen in window AND fresh dests / dests seen in window
    "min_rows":     2,     # never act on a stub result (tasim/world8 are 2-row catalogs)
    "grace_hours":  72,    # a row must be unseen for this long before it's eligible
    "window_days":  30,    # baseline = rows/destinations seen in the last N days
}
# Per-country scrapers whose coverage fluctuates run-to-run (archive_snapshots
# 2026-08-20..09-03 daily row counts: esimplus 33..582, holafly 509..1645,
# alosim 1439..1705, besim 438..640, gomoworld 284..716). A row of theirs must be
# unseen for a full week before it's eligible; the window guards do the rest.
# Keys are the same knob names as GLOBAL_PURGE_DEFAULTS; {"enabled": False}
# disables the purge for a carrier entirely (the report is still produced).
GLOBAL_PURGE_OVERRIDES = {
    "esimplus":  {"grace_hours": 168},
    "holafly":   {"grace_hours": 168},
    "alosim":    {"grace_hours": 168},
    "besim":     {"grace_hours": 168},
    "gomoworld": {"grace_hours": 168},
}


def _global_dest(plan):
    ex = _norm_extras(plan.get("extras") or [])
    return ex[0] if ex and ex[0] else None


def purge_stale_global_rows(plans, db_path=None, dry_run=False, overrides=None, **knobs):
    """Delete global_plans rows that a COMPLETE-looking scrape no longer returns.

    `plans` is the fresh list just passed to save_global_plans (call this right
    after it, so the fresh rows carry the newest scraped_at). For every carrier
    present in `plans`:
      1. baseline = the carrier's rows with scraped_at within `window_days`
         (fresh rows included): their count and their distinct destinations;
      2. the scrape is "complete" when fresh rows >= min_rows AND
         fresh_rows / baseline_rows >= min_ratio AND
         fresh_dests / baseline_dests >= min_ratio;
      3. if complete (and not dry_run / disabled): delete the carrier's rows whose
         plan_name is not in the fresh set AND whose scraped_at is older than
         `grace_hours` (a flapping per-country tier seen recently is spared).
    Carriers absent from `plans` (scraper returned []) are never touched.
    Deletes only global_plans (+ the matching plan_refs); it never writes to
    global_changes, so no new_plan/removed_plan noise, and never touches
    esim_push_subscriptions - removing rows can only raise a destination's
    alert floor, which notify_esim_price_drops absorbs silently as a baseline rise.
    dry_run performs no writes at all. Returns {carrier: report-dict};
    report["purged"] is the deleted row count, report["decision"] says why not.
    """
    knobs = {**GLOBAL_PURGE_DEFAULTS, **{k: v for k, v in knobs.items() if v is not None}}
    overrides = GLOBAL_PURGE_OVERRIDES if overrides is None else overrides
    by_carrier = {}
    for p in plans:
        by_carrier.setdefault(p["carrier"], []).append(p)
    if not by_carrier:
        return {}
    now = datetime.now()
    report = {}
    conn = _connect(db_path)
    try:
        for carrier, fresh in sorted(by_carrier.items()):
            k = {**knobs, **(overrides.get(carrier) or {})}
            fresh_names = {p["plan_name"] for p in fresh}
            fresh_dests = {d for d in (_global_dest(p) for p in fresh) if d}
            window_start = (now - timedelta(days=k["window_days"])).isoformat()
            cutoff = (now - timedelta(hours=k["grace_hours"])).isoformat()
            rows = conn.execute(
                "SELECT id, plan_name, scraped_at, json_extract(extras, '$[0]') "
                "FROM global_plans WHERE carrier=?", (carrier,)).fetchall()
            in_window = [r for r in rows if (r[2] or "") >= window_start]
            base_names = {r[1] for r in in_window} | fresh_names
            base_dests = {r[3] for r in in_window if r[3]} | fresh_dests
            ratio_rows = len(fresh_names) / len(base_names) if base_names else 0.0
            ratio_dests = len(fresh_dests) / len(base_dests) if base_dests else 1.0
            stale = [(rid, name) for rid, name, at, _ in rows if name not in fresh_names]
            eligible = [(rid, name) for rid, name, at, _ in rows
                        if name not in fresh_names and (at or "") < cutoff]
            if k.get("enabled") is False:
                decision = "disabled"
            elif len(fresh_names) < k["min_rows"]:
                decision = f"too-few-rows (<{k['min_rows']})"
            elif ratio_rows < k["min_ratio"]:
                decision = f"partial-rows ({ratio_rows:.2f}<{k['min_ratio']})"
            elif ratio_dests < k["min_ratio"]:
                decision = f"partial-dests ({ratio_dests:.2f}<{k['min_ratio']})"
            elif not eligible:
                decision = "complete, nothing eligible"
            elif dry_run:
                decision = "complete, dry-run"
            else:
                decision = "purged"
            purged = 0
            if decision == "purged":
                ids = [rid for rid, _ in eligible]
                names = [name for _, name in eligible]
                for i in range(0, len(ids), 500):
                    chunk = ids[i:i + 500]
                    ph = ",".join("?" * len(chunk))
                    purged += conn.execute(
                        f"DELETE FROM global_plans WHERE id IN ({ph})", chunk).rowcount
                for i in range(0, len(names), 500):
                    chunk = names[i:i + 500]
                    ph = ",".join("?" * len(chunk))
                    conn.execute(
                        f"DELETE FROM plan_refs WHERE carrier=? AND plan_name IN ({ph})",
                        (carrier, *chunk))
            report[carrier] = {
                "fresh": len(fresh_names), "fresh_dests": len(fresh_dests),
                "baseline_rows": len(base_names), "baseline_dests": len(base_dests),
                "ratio_rows": round(ratio_rows, 3), "ratio_dests": round(ratio_dests, 3),
                "db_rows": len(rows), "stale": len(stale), "eligible": len(eligible),
                "purged": purged, "decision": decision,
            }
        if not dry_run:
            conn.commit()
    finally:
        conn.close()
    return report

def get_plan_ref(carrier, plan_name, db_path=None):
    """Provider-side checkout/plan token for one plan, or None. Used by the /go
    redirect to build a per-plan affiliate deep link (e.g. Saily checkout)."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT plan_ref FROM plan_refs WHERE carrier=? AND plan_name=?",
            (carrier, plan_name)).fetchone()
        return row[0] if row and row[0] else None
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
                 ch.get("changed_at") or now)
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
        _delete_stale_carrier_rows(conn, "abroad_plans", plans)
        now = datetime.now().isoformat()
        rows = [(
            plan["carrier"], plan["plan_name"], plan.get("price"),
            plan.get("days"), plan.get("data_gb"), plan.get("minutes"),
            plan.get("sms"),
            json.dumps(plan.get("extras", []), ensure_ascii=False),
            now,
            plan.get("terms_url")
        ) for plan in plans]
        conn.executemany("""
                INSERT INTO abroad_plans (carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at, terms_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price      = excluded.price,
                    days       = excluded.days,
                    data_gb    = excluded.data_gb,
                    minutes    = excluded.minutes,
                    sms        = excluded.sms,
                    extras     = excluded.extras,
                    scraped_at = excluded.scraped_at,
                    terms_url  = excluded.terms_url
            """, rows)
        conn.commit()
    finally:
        conn.close()


def get_abroad_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at, terms_url "
                "FROM abroad_plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at, terms_url "
                "FROM abroad_plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "days": r[3], "data_gb": r[4], "minutes": r[5], "sms": r[6],
                "extras": json.loads(r[7]) if r[7] else [],
                "scraped_at": r[8],
                "terms_url": r[9],
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
                 ch.get("changed_at") or now)
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
                 ch.get("changed_at") or now)
            )
        conn.commit()
    finally:
        conn.close()


def save_push_subscription(endpoint, p256dh, auth, user_email=None, hidden_carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO push_subscriptions "
            "(endpoint, p256dh, auth, user_email, hidden_carrier, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (endpoint, p256dh, auth, user_email, hidden_carrier, datetime.now().isoformat())
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
                "SELECT endpoint, p256dh, auth, hidden_carrier FROM push_subscriptions WHERE user_email=?",
                (user_email,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT endpoint, p256dh, auth, hidden_carrier FROM push_subscriptions"
            ).fetchall()
        return [
            {"endpoint": r[0], "keys": {"p256dh": r[1], "auth": r[2]}, "hidden_carrier": r[3]}
            for r in rows
        ]
    finally:
        conn.close()


# ── Public B2C eSIM price-drop push subscriptions (/esim-deals) ─────────────

def save_esim_push_subscription(endpoint, p256dh, auth, destination, lang="he",
                                baseline_price=None, db_path=None):
    """UPSERT by endpoint — re-subscribing from the same browser with a new
    destination MOVES the alert (one destination alert per device)."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO esim_push_subscriptions "
            "(endpoint, p256dh, auth, destination, lang, baseline_price, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "p256dh=excluded.p256dh, auth=excluded.auth, destination=excluded.destination, "
            "lang=excluded.lang, baseline_price=excluded.baseline_price, last_notified_at=NULL",
            (endpoint, p256dh, auth, destination, lang, baseline_price,
             datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def delete_esim_push_subscription(endpoint, db_path=None):
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM esim_push_subscriptions WHERE endpoint=?", (endpoint,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_esim_push_subscriptions(db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT endpoint, p256dh, auth, destination, lang, baseline_price "
            "FROM esim_push_subscriptions"
        ).fetchall()
        return [
            {"endpoint": r[0], "keys": {"p256dh": r[1], "auth": r[2]},
             "destination": r[3], "lang": r[4] or "he", "baseline_price": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def update_esim_push_baseline(endpoint, price, notified=False, db_path=None):
    """Move a subscription's price baseline. notified=True also stamps
    last_notified_at (a push was actually sent for this move)."""
    conn = _connect(db_path)
    try:
        if notified:
            conn.execute(
                "UPDATE esim_push_subscriptions SET baseline_price=?, last_notified_at=? "
                "WHERE endpoint=?",
                (price, datetime.now().isoformat(), endpoint))
        else:
            conn.execute(
                "UPDATE esim_push_subscriptions SET baseline_price=? WHERE endpoint=?",
                (price, endpoint))
        conn.commit()
    finally:
        conn.close()


def save_mobile_push_subscription(endpoint, p256dh, auth, carrier="all", lang="he",
                                  db_path=None):
    """UPSERT by endpoint — re-subscribing from the same browser with a new
    carrier MOVES the alert (one domestic price-drop alert per device)."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO mobile_push_subscriptions "
            "(endpoint, p256dh, auth, carrier, lang, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "p256dh=excluded.p256dh, auth=excluded.auth, carrier=excluded.carrier, "
            "lang=excluded.lang, last_notified_at=NULL",
            (endpoint, p256dh, auth, carrier or "all", lang,
             datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def delete_mobile_push_subscription(endpoint, db_path=None):
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM mobile_push_subscriptions WHERE endpoint=?", (endpoint,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_mobile_push_subscriptions(db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT endpoint, p256dh, auth, carrier, lang, last_notified_at "
            "FROM mobile_push_subscriptions"
        ).fetchall()
        return [
            {"endpoint": r[0], "keys": {"p256dh": r[1], "auth": r[2]},
             "carrier": r[3] or "all", "lang": r[4] or "he", "last_notified_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def touch_mobile_push_notified(endpoint, db_path=None):
    """Stamp last_notified_at — a push was actually delivered to this endpoint."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE mobile_push_subscriptions SET last_notified_at=? WHERE endpoint=?",
            (datetime.now().isoformat(), endpoint))
        conn.commit()
    finally:
        conn.close()


def save_mobile_reminders(token, rows, db_path=None):
    """Insert the reminder rows of one /mobile-deals signup (all sharing `token`).
    Re-signing up for the same (kind, plan_type, carrier, plan_name) with the
    same contact replaces the old row — a user tweaking the reminder date
    shouldn't stack duplicate reminders."""
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for r in rows:
            conn.execute(
                "DELETE FROM mobile_reminders WHERE kind=? AND plan_type=? AND carrier=? "
                "AND plan_name=? "
                "AND IFNULL(email,'')=IFNULL(?,'') AND IFNULL(phone,'')=IFNULL(?,'')",
                (r["kind"], r.get("plan_type") or "domestic", r["carrier"], r["plan_name"],
                 r.get("email"), r.get("phone")))
            conn.execute(
                "INSERT INTO mobile_reminders "
                "(token, email, phone, channel, kind, plan_type, carrier, plan_name, price, "
                " data_gb, unlimited, days, end_date, remind_days_before, include_offers, "
                " lang, paid_price, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (token, r.get("email"), r.get("phone"), r.get("channel") or "email",
                 r["kind"], r.get("plan_type") or "domestic", r["carrier"], r["plan_name"],
                 r.get("price"), r.get("data_gb"),
                 1 if r.get("unlimited") else 0, r.get("days"), r.get("end_date"),
                 r.get("remind_days_before"), 0 if r.get("include_offers") is False else 1,
                 r.get("lang") or "he", r.get("paid_price"), now))
        conn.commit()
    finally:
        conn.close()


def get_mobile_reminders(kind=None, db_path=None):
    """Active reminder rows (plan_end rows already sent are excluded)."""
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        q = "SELECT * FROM mobile_reminders WHERE done=0"
        args = []
        if kind:
            q += " AND kind=?"
            args.append(kind)
        return [dict(r) for r in conn.execute(q, args).fetchall()]
    finally:
        conn.close()


def get_all_mobile_reminders(db_path=None):
    """EVERY reminder row (active + done) for the super-admin subscribers view.
    Contains raw contact details — serve only behind super-admin auth."""
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM mobile_reminders ORDER BY created_at DESC, id DESC").fetchall()]
    finally:
        conn.close()


def delete_mobile_reminders_by_token(token, db_path=None):
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM mobile_reminders WHERE token=?", (token,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def mark_mobile_reminder_notified(reminder_id, best_price=None, done=False, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE mobile_reminders SET last_notified_at=?, "
            "best_price_alerted=COALESCE(?, best_price_alerted), "
            "done=CASE WHEN ? THEN 1 ELSE done END WHERE id=?",
            (datetime.now().isoformat(), best_price, 1 if done else 0, reminder_id))
        conn.commit()
    finally:
        conn.close()


def touch_mobile_reminder_heartbeat(reminder_id, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE mobile_reminders SET last_heartbeat_at=? WHERE id=?",
                     (datetime.now().isoformat(), reminder_id))
        conn.commit()
    finally:
        conn.close()


def get_mobile_plan_end_followups(db_path=None):
    """plan_end reminders whose end-of-term reminder already went out (done=1)
    and whose renewal follow-up hasn't - candidates for the 'did you renew?'
    email a week after end_date."""
    conn = _connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM mobile_reminders "
            "WHERE kind='plan_end' AND done=1 AND IFNULL(followup_sent,0)=0").fetchall()]
    finally:
        conn.close()


def mark_mobile_reminder_followup(reminder_id, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE mobile_reminders SET followup_sent=1 WHERE id=?", (reminder_id,))
        conn.commit()
    finally:
        conn.close()


def count_domestic_price_drops(days=30, db_path=None):
    """(drops, rises) counted from the domestic change log over the last N days -
    fuel for the monthly heartbeat email's market-pulse stats."""
    conn = _connect(db_path)
    try:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        drops = rises = 0
        for old_val, new_val in conn.execute(
                "SELECT old_val, new_val FROM changes "
                "WHERE change_type='price_change' AND changed_at>=?", (since,)).fetchall():
            try:
                if float(new_val) < float(old_val):
                    drops += 1
                elif float(new_val) > float(old_val):
                    rises += 1
            except (TypeError, ValueError):
                continue
        return drops, rises
    finally:
        conn.close()


def save_content_plans(plans, db_path=None):
    # Failure sentinels a flaky scrape can return. Never let one overwrite a
    # previously-good price: that flap wrote "לא נמצא" over a valid ₪ price and fired
    # false "service not found" alerts (e.g. cellcom eSIM שעון, 2026-05-28 + 2026-07-01).
    # NB "לא זמין" is intentional (the not_available strategy) and is NOT a failure.
    _BAD_CONTENT_PRICES = ("לא נמצא", "שגיאה")
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            if plan.get("price") in _BAD_CONTENT_PRICES:
                existing = conn.execute(
                    "SELECT price FROM content_plans WHERE service=? AND carrier=?",
                    (plan["service"], plan["carrier"])
                ).fetchone()
                if existing and existing[0] and existing[0] not in _BAD_CONTENT_PRICES:
                    # keep last-known-good value; skip this failed scrape entirely
                    continue
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
                 ch.get("changed_at") or now)
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


# ── Watchlist CRUD ────────────────────────────────────────────────────────

def add_to_watchlist(user_email, carrier, plan_name, plan_type, db_path=None):
    """Add a plan to user's watchlist. Idempotent via UNIQUE constraint."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (user_email, carrier, plan_name, plan_type, added_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_email, carrier, plan_name, plan_type, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def remove_from_watchlist(user_email, carrier, plan_name, plan_type, db_path=None):
    """Remove a plan from user's watchlist. Scoped by user_email."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_email = ? AND carrier = ? AND plan_name = ? AND plan_type = ?",
            (user_email, carrier, plan_name, plan_type)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_watchlist(user_email, db_path=None):
    """Return all watched plans for a user (newest first)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, carrier, plan_name, plan_type, added_at FROM watchlist "
            "WHERE user_email = ? ORDER BY added_at DESC",
            (user_email,)
        ).fetchall()
        return [
            {"id": r[0], "carrier": r[1], "plan_name": r[2], "plan_type": r[3], "added_at": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


# ── Saved Views CRUD ──────────────────────────────────────────────────────

def save_view(user_email, name, filters_json, db_path=None):
    """Upsert a saved view for a user. filters_json is a JSON string."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO saved_views (user_email, name, filters_json, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_email, name) DO UPDATE SET filters_json = excluded.filters_json",
            (user_email, name, filters_json, datetime.now().isoformat())
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM saved_views WHERE user_email = ? AND name = ?",
            (user_email, name)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_saved_views(user_email, db_path=None):
    """Return all saved views for a user."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, name, filters_json, created_at FROM saved_views "
            "WHERE user_email = ? ORDER BY created_at DESC",
            (user_email,)
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "filters_json": r[2], "created_at": r[3]}
            for r in rows
        ]
    finally:
        conn.close()


def delete_saved_view(view_id, user_email, db_path=None):
    """Delete a saved view. Scoped by user_email to prevent IDOR. Returns rows deleted."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM saved_views WHERE id = ? AND user_email = ?",
            (view_id, user_email)
        )
        conn.commit()
        return cur.rowcount
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


def _archive_encode(plans_json):
    """Compress a plans_json snapshot for storage. Archive snapshots are large,
    highly-repetitive JSON (full plan lists) — zlib shrinks them ~8-12x. Returns
    bytes, stored as a BLOB in the (TEXT-affinity) plans_json column."""
    return zlib.compress(plans_json.encode("utf-8"), 6)


def _archive_decode(blob):
    """Inverse of _archive_encode, tolerant of legacy uncompressed rows.
    Compressed rows come back from SQLite as bytes; legacy rows as a str
    (raw JSON) and are returned unchanged."""
    if isinstance(blob, (bytes, bytearray)):
        try:
            return zlib.decompress(blob).decode("utf-8")
        except zlib.error:
            return bytes(blob).decode("utf-8", "replace")
    return blob


def insert_archive_snapshot(carrier, plan_type, snapshot_date, plans_json, content_hash, db_path=None):
    """Insert a new plan snapshot row."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO archive_snapshots (carrier, plan_type, snapshot_date, plans_json, content_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (carrier, plan_type, snapshot_date, _archive_encode(plans_json), content_hash)
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
        return [{"plan_type": r[0], "plans": json.loads(_archive_decode(r[1])), "snapshot_date": r[2]} for r in rows]
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
        sql += ' ORDER BY changed_at DESC, id DESC'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {'plan_name': r[0], 'change_type': r[1], 'old_val': r[2],
         'new_val': r[3], 'changed_at': r[4]}
        for r in rows
    ]


def get_market_movers(days=7, limit=5, plan_types=None, db_path=None):
    """Return the top price moves (absolute % change) over the last `days` days.
    Content plans are excluded — they're binary status changes, not price points.

    Args:
        plan_types: iterable subset of ('domestic','abroad','global'). None = all.

    Result item: {carrier, plan_name, plan_type, old_price, new_price,
                   pct_change, abs_pct, changed_at}
    Capped at `limit` entries, sorted by |pct_change| descending.
    """
    since = (datetime.now() - timedelta(days=days)).isoformat()
    db_path = db_path or DB_PATH
    results = []
    valid_types = ('domestic', 'abroad', 'global')
    if plan_types:
        types_iter = tuple(t for t in plan_types if t in valid_types) or valid_types
    else:
        types_iter = valid_types
    # One connection reused across all three change tables (was opened/closed per type).
    conn = _connect(db_path)
    try:
        for plan_type in types_iter:
            table, name_col = _HISTORY_TABLE_MAP[plan_type]
            rows = conn.execute(
                f"SELECT carrier, {name_col}, old_val, new_val, changed_at "
                f"FROM {table} WHERE change_type = 'price_change' AND changed_at >= ? "
                f"ORDER BY changed_at DESC",
                (since,)
            ).fetchall()
            for carrier, pname, old_v, new_v, ts in rows:
                try:
                    old_p = float(old_v)
                    new_p = float(new_v)
                except (ValueError, TypeError):
                    continue
                if old_p <= 0:
                    continue  # can't compute % against 0
                pct = (new_p - old_p) / old_p * 100.0
                if abs(pct) < 5.0:
                    continue  # filter out small/noise price changes
                results.append({
                    'carrier':    carrier,
                    'plan_name':  pname,
                    'plan_type':  plan_type,
                    'old_price':  old_p,
                    'new_price':  new_p,
                    'pct_change': round(pct, 1),
                    'abs_pct':    abs(pct),
                    'changed_at': ts,
                })
    finally:
        conn.close()
    # Dedup by (carrier, plan_name) — keep the most recent event per plan
    seen = set()
    deduped = []
    for r in sorted(results, key=lambda x: x['changed_at'], reverse=True):
        key = (r['carrier'], r['plan_name'], r['plan_type'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    deduped.sort(key=lambda x: x['abs_pct'], reverse=True)
    return deduped[:limit]


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
        sql += ' ORDER BY changed_at ASC, id ASC'
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
            pts = []
            prev_new = None
            for e in events:
                old = float(e['old'])
                new = float(e['new'])
                # First event: seed with its old price.
                # Subsequent events: if old != previous new, the chain is
                # broken (likely a transient scraper artifact or a missed
                # intermediate scrape). Add the discontinuous "old" so the
                # chart faithfully reflects what was recorded — otherwise
                # we'd silently drop a price point that's visible in the
                # changes log.
                if prev_new is None or old != prev_new:
                    pts.append({'date': e['date'], 'price': old})
                pts.append({'date': e['date'], 'price': new})
                prev_new = new
            series.append({'plan_name': pname, 'points': pts})
        except (ValueError, TypeError):
            continue
    return series


def get_all_price_series(plan_type='domestic', from_date=None, db_path=None):
    """Batch variant of get_history_price_series: the price-change point series
    for EVERY plan of a type in ONE query, keyed by 'carrier|plan_name'. Powers
    the dashboard sparklines with a single request instead of one fetch per card.

    Returns { 'carrier|plan_name': [{date, price}, ...] } — only plans with >=2
    points (i.e. that actually had a recorded price change) are included.
    """
    if plan_type not in _HISTORY_TABLE_MAP:
        return {}
    table, name_col = _HISTORY_TABLE_MAP[plan_type]
    db_path = db_path or DB_PATH
    conn = _connect(db_path)
    try:
        sql = (f"SELECT carrier, {name_col} AS plan_name, old_val, new_val, changed_at "
               f"FROM {table} WHERE change_type = 'price_change'")
        params = []
        if from_date:
            sql += ' AND changed_at >= ?'
            params.append(from_date)
        sql += ' ORDER BY changed_at ASC, id ASC'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    events_by_key = {}
    for carrier, pname, old_val, new_val, ts in rows:
        events_by_key.setdefault(f"{carrier}|{pname}", []).append(
            {'old': old_val, 'new': new_val, 'date': ts[:10]})

    out = {}
    for key, events in events_by_key.items():
        try:
            pts = []
            prev_new = None
            for e in events:
                old = float(e['old'])
                new = float(e['new'])
                # Same discontinuity handling as get_history_price_series.
                if prev_new is None or old != prev_new:
                    pts.append({'date': e['date'], 'price': old})
                pts.append({'date': e['date'], 'price': new})
                prev_new = new
            if len(pts) >= 2:
                out[key] = pts
        except (ValueError, TypeError):
            continue
    return out


def create_workspace_invite(workspace_id, role='viewer', created_by=None, db_path=None):
    """Create a single-use invite token (valid 7 days). Returns the token string."""
    import uuid as _uuid
    token = str(_uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=7)).isoformat()
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO workspace_invites (token, workspace_id, role, created_by, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (token, str(workspace_id), role, created_by, now.isoformat(), expires)
        )
        conn.commit()
    finally:
        conn.close()
    return token


def get_workspace_invite(token, db_path=None):
    """Return invite row dict or None if not found / expired / already used."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT token, workspace_id, role, created_by, created_at, expires_at, used_at, used_by "
            "FROM workspace_invites WHERE token = ?",
            (token,)
        ).fetchone()
        if not row:
            return None
        invite = {
            'token': row[0], 'workspace_id': row[1], 'role': row[2],
            'created_by': row[3], 'created_at': row[4], 'expires_at': row[5],
            'used_at': row[6], 'used_by': row[7],
        }
        return invite
    finally:
        conn.close()


def use_workspace_invite(token, used_by, db_path=None):
    """Mark invite as used. Returns True on success, False if already used."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE workspace_invites SET used_at = ?, used_by = ? "
            "WHERE token = ? AND used_at IS NULL",
            (now, used_by, token)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def log_audit(action, actor_email=None, target_email=None, workspace_id=None, details=None, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO audit_log (action, actor_email, target_email, workspace_id, details, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (action, actor_email, target_email, str(workspace_id) if workspace_id else None,
             details, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_audit_log(limit=200, workspace_id=None, db_path=None):
    conn = _connect(db_path)
    try:
        if workspace_id:
            rows = conn.execute(
                "SELECT id, action, actor_email, target_email, workspace_id, details, created_at "
                "FROM audit_log WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?",
                (str(workspace_id), limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, action, actor_email, target_email, workspace_id, details, created_at "
                "FROM audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [
            {"id": r[0], "action": r[1], "actor_email": r[2], "target_email": r[3],
             "workspace_id": r[4], "details": r[5], "created_at": r[6]}
            for r in rows
        ]
    finally:
        conn.close()


def count_refreshes(workspace_id, month_prefix, db_path=None):
    """COUNT of 'refresh_triggered' audit rows for a workspace in a given month
    (created_at LIKE 'YYYY-MM%'). Backs the monthly manual-refresh quota — this
    replaces pulling a capped 500-row audit slice into Python to count a handful,
    which also could undercount once a workspace exceeded 500 audit rows in a month."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action = 'refresh_triggered' "
            "AND workspace_id = ? AND created_at LIKE ?",
            (str(workspace_id), month_prefix + '%')
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


# ── User activity tracking (super-admin dashboard) ─────────────────────────
def log_user_activity(user_email, event_type, workspace_id=None, path=None,
                      details=None, user_agent=None, db_path=None):
    """Best-effort per-user activity log (logins, page views, key actions).

    NEVER raises into the caller — a logging failure must not break the user
    action it is attached to. Super-admins are excluded by the API layer
    (app.py), not here. Powers the super-admin user-activity dashboard.
    """
    if not user_email or not event_type:
        return
    try:
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO user_activity "
                "(user_email, workspace_id, event_type, path, details, user_agent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_email.strip().lower(),
                 str(workspace_id) if workspace_id else None,
                 event_type, path, details,
                 (user_agent or "")[:400] or None,
                 datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def get_user_activity_overview(days=30, db_path=None):
    """Per-user activity aggregation over the last N days (0 = lifetime).

    Returns a list of dicts (one per user_email with any activity) with
    per-event-type counts, distinct active days, and first/last seen. The
    event_type strings here MUST match those written by the action hooks in
    app.py and the client beacon (login / page_view / alert_created /
    watchlist_added / watchlist_removed / comparison_saved).
    """
    from datetime import datetime, timezone, timedelta
    conn = _connect(db_path)
    try:
        if days and days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            where, params = "WHERE created_at >= ?", (cutoff,)
        else:
            where, params = "", ()
        rows = conn.execute(
            f"""SELECT user_email,
                       SUM(CASE WHEN event_type='login'             THEN 1 ELSE 0 END) AS logins,
                       SUM(CASE WHEN event_type='page_view'         THEN 1 ELSE 0 END) AS page_views,
                       SUM(CASE WHEN event_type='alert_created'     THEN 1 ELSE 0 END) AS alerts_created,
                       SUM(CASE WHEN event_type='watchlist_added'   THEN 1 ELSE 0 END) AS watchlist_added,
                       SUM(CASE WHEN event_type='watchlist_removed' THEN 1 ELSE 0 END) AS watchlist_removed,
                       SUM(CASE WHEN event_type='comparison_saved'  THEN 1 ELSE 0 END) AS comparisons_saved,
                       SUM(CASE WHEN event_type='chat_used'         THEN 1 ELSE 0 END) AS chat_used,
                       COUNT(DISTINCT substr(created_at,1,10)) AS active_days,
                       MIN(created_at) AS first_seen,
                       MAX(created_at) AS last_seen
                  FROM user_activity {where}
              GROUP BY user_email""",
            params,
        ).fetchall()
        cols = ['user_email', 'logins', 'page_views', 'alerts_created',
                'watchlist_added', 'watchlist_removed', 'comparisons_saved',
                'chat_used', 'active_days', 'first_seen', 'last_seen']
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def get_user_activity_summary(days=30, db_path=None):
    """Aggregate activity for charts: totals, per-day series, and top pages.

    Mirrors the shape of get_claude_usage_summary so the dashboard can reuse
    the same chart code.
    """
    from datetime import datetime, timezone, timedelta
    conn = _connect(db_path)
    try:
        if days and days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            where, params = "WHERE created_at >= ?", (cutoff,)
        else:
            where, params = "", ()

        total = conn.execute(
            f"""SELECT COUNT(*),
                       COUNT(DISTINCT user_email),
                       SUM(CASE WHEN event_type='login'     THEN 1 ELSE 0 END),
                       SUM(CASE WHEN event_type='page_view' THEN 1 ELSE 0 END)
                  FROM user_activity {where}""",
            params,
        ).fetchone()

        by_day = conn.execute(
            f"""SELECT substr(created_at,1,10) AS day,
                       COUNT(*) AS events,
                       COUNT(DISTINCT user_email) AS users
                  FROM user_activity {where}
              GROUP BY day ORDER BY day""",
            params,
        ).fetchall()

        if days and days > 0:
            pages_where = "WHERE created_at >= ? AND event_type='page_view' AND path IS NOT NULL"
            pages_params = (cutoff,)
        else:
            pages_where = "WHERE event_type='page_view' AND path IS NOT NULL"
            pages_params = ()
        top_pages = conn.execute(
            f"""SELECT path, COUNT(*) AS views
                  FROM user_activity {pages_where}
              GROUP BY path ORDER BY views DESC LIMIT 15""",
            pages_params,
        ).fetchall()

        by_event = conn.execute(
            f"""SELECT event_type, COUNT(*) AS count
                  FROM user_activity {where}
              GROUP BY event_type ORDER BY count DESC""",
            params,
        ).fetchall()

        return {
            "window_days": days,
            "total": {"events": total[0] or 0, "active_users": total[1] or 0,
                      "logins": total[2] or 0, "page_views": total[3] or 0},
            "by_day": [{"day": r[0], "events": r[1], "users": r[2]} for r in by_day],
            "top_pages": [{"path": r[0], "views": r[1]} for r in top_pages],
            "by_event_type": [{"event_type": r[0], "count": r[1]} for r in by_event],
        }
    finally:
        conn.close()


def get_user_activity_events(email=None, event_type=None, days=30, limit=100, db_path=None):
    """Raw activity feed (newest first) for the dashboard drill-down — for a
    single user (email) or all. limit is clamped to 1..500."""
    from datetime import datetime, timezone, timedelta
    conn = _connect(db_path)
    try:
        clauses, params = [], []
        if email:
            clauses.append("user_email = ?")
            params.append(email.strip().lower())
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if days and days > 0:
            clauses.append("created_at >= ?")
            params.append((datetime.now(timezone.utc) - timedelta(days=days)).isoformat())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            limit = max(1, min(500, int(limit)))
        except (TypeError, ValueError):
            limit = 100
        params.append(limit)
        rows = conn.execute(
            f"""SELECT id, user_email, workspace_id, event_type, path, details, user_agent, created_at
                  FROM user_activity {where}
              ORDER BY created_at DESC LIMIT ?""",
            params,
        ).fetchall()
        cols = ['id', 'user_email', 'workspace_id', 'event_type', 'path',
                'details', 'user_agent', 'created_at']
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def prune_user_activity(keep_days=180, db_path=None):
    """Delete activity rows older than keep_days. DELETE only (no VACUUM) — the
    shared plans.db is served per-request by the elevated Flask. Returns rows deleted."""
    from datetime import datetime, timezone, timedelta
    conn = _connect(db_path)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
        cur = conn.execute("DELETE FROM user_activity WHERE created_at < ?", (cutoff,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ── Plan annotations (team notes) ──────────────────────────────────────────
def add_annotation(workspace_id, user_email, carrier, plan_name, plan_type, note, db_path=None):
    """Insert a new annotation. Returns inserted id."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO plan_annotations
               (workspace_id, user_email, carrier, plan_name, plan_type, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (workspace_id, user_email, carrier, plan_name, plan_type, note, now)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_annotations(workspace_id, carrier=None, plan_name=None, plan_type=None, db_path=None):
    """Return annotations for the workspace, optionally filtered to a specific plan."""
    conn = _connect(db_path)
    try:
        sql = ("SELECT id, user_email, carrier, plan_name, plan_type, note, created_at, updated_at "
               "FROM plan_annotations WHERE workspace_id IS ?")
        params = [workspace_id]
        if carrier:
            sql += " AND carrier = ?"
            params.append(carrier)
        if plan_name:
            sql += " AND plan_name = ?"
            params.append(plan_name)
        if plan_type:
            sql += " AND plan_type = ?"
            params.append(plan_type)
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [
            {"id": r[0], "user_email": r[1], "carrier": r[2], "plan_name": r[3],
             "plan_type": r[4], "note": r[5], "created_at": r[6], "updated_at": r[7]}
            for r in rows
        ]
    finally:
        conn.close()


def get_annotation_counts(workspace_id, db_path=None):
    """Return dict {carrier|plan_type|plan_name: count} for all annotations in workspace."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT carrier, plan_type, plan_name, COUNT(*) FROM plan_annotations
               WHERE workspace_id IS ?
               GROUP BY carrier, plan_type, plan_name""",
            (workspace_id,)
        ).fetchall()
        return {f"{r[0]}|{r[1]}|{r[2]}": r[3] for r in rows}
    finally:
        conn.close()


def delete_annotation(annotation_id, workspace_id, user_email, db_path=None):
    """Delete an annotation. Author OR same-workspace admin can delete (caller enforces admin)."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """DELETE FROM plan_annotations
               WHERE id = ? AND workspace_id IS ? AND user_email = ?""",
            (annotation_id, workspace_id, user_email)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def update_annotation(annotation_id, workspace_id, user_email, note, db_path=None):
    """Update an annotation. Only author can edit. Returns rows updated."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """UPDATE plan_annotations SET note = ?, updated_at = ?
               WHERE id = ? AND workspace_id IS ? AND user_email = ?""",
            (note, now, annotation_id, workspace_id, user_email)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ── Provider coupons (manually curated discount codes) ───────────────────────

def get_active_coupons(db_path=None):
    """Public read — returns active coupons whose expiry has not passed.

    Shape matches what PlanCard renders directly. If external_offer_url is set
    the card renders as a link-out tile (third-party offer); otherwise as a
    copy-the-code pill.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT carrier, code, discount_label, expires_at, source_url,
                      external_offer_url, partner_name
               FROM provider_coupons
               WHERE is_active = 1
                 AND (expires_at IS NULL OR expires_at = '' OR expires_at >= ?)
               ORDER BY carrier, code""",
            (today,)
        ).fetchall()
        return [
            {"carrier": r[0], "code": r[1], "discount_label": r[2],
             "expires_at": r[3], "source_url": r[4],
             "external_offer_url": r[5], "partner_name": r[6]}
            for r in rows
        ]
    finally:
        conn.close()


def get_all_coupons(db_path=None):
    """Admin read — every row, active or not, expired or not."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT id, carrier, code, discount_label, expires_at, source_url,
                      is_active, notes, external_offer_url, partner_name,
                      created_at, updated_at
               FROM provider_coupons
               ORDER BY carrier, code"""
        ).fetchall()
        return [
            {"id": r[0], "carrier": r[1], "code": r[2], "discount_label": r[3],
             "expires_at": r[4], "source_url": r[5], "is_active": bool(r[6]),
             "notes": r[7], "external_offer_url": r[8], "partner_name": r[9],
             "created_at": r[10], "updated_at": r[11]}
            for r in rows
        ]
    finally:
        conn.close()


# ── Provider deal CRM (manually curated relationship / commission tracker) ───

_PROVIDER_DEAL_FIELDS = (
    "display_name", "category", "is_israeli", "outreach_status",
    "outreach_last_at", "contact", "program_network", "agreement_status",
    "commission_pct", "commission_note", "coupon_note", "has_tracking_link",
    "next_actions", "priority", "is_leak", "notes",
)


def get_provider_deals(db_path=None):
    """Return every provider deal row, highest-priority first. Coupon liveness is
    joined separately (see app._enrich_provider_deals) so it stays live."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            f"""SELECT provider_id, {', '.join(_PROVIDER_DEAL_FIELDS)}, updated_at
                FROM provider_deals
                ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'med' THEN 1
                                       WHEN 'low' THEN 2 ELSE 3 END,
                         display_name COLLATE NOCASE"""
        ).fetchall()
        out = []
        for r in rows:
            d = {"provider_id": r[0]}
            for i, f in enumerate(_PROVIDER_DEAL_FIELDS, start=1):
                d[f] = r[i]
            d["is_israeli"]        = bool(d.get("is_israeli"))
            d["has_tracking_link"] = bool(d.get("has_tracking_link"))
            d["is_leak"]           = bool(d.get("is_leak"))
            d["updated_at"] = r[len(_PROVIDER_DEAL_FIELDS) + 1]
            out.append(d)
        return out
    finally:
        conn.close()


def upsert_provider_deal(provider_id, db_path=None, **fields):
    """Insert or update a provider deal by provider_id. Only known columns in
    `fields` are written; booleans accepted as bool/int. Returns provider_id."""
    now = datetime.now(timezone.utc).isoformat()
    vals = {f: fields.get(f) for f in _PROVIDER_DEAL_FIELDS}
    for b in ("is_israeli", "has_tracking_link", "is_leak"):
        vals[b] = 1 if vals.get(b) else 0
    cols = list(_PROVIDER_DEAL_FIELDS)
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols)
    conn = _connect(db_path)
    try:
        conn.execute(
            f"""INSERT INTO provider_deals (provider_id, {', '.join(cols)}, updated_at)
                VALUES (?, {placeholders}, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                  {updates}, updated_at = excluded.updated_at""",
            (provider_id, *[vals[c] for c in cols], now)
        )
        conn.commit()
        return provider_id
    finally:
        conn.close()


def upsert_coupon(carrier, code, discount_label=None, expires_at=None,
                  source_url=None, is_active=True, notes=None,
                  external_offer_url=None, partner_name=None, db_path=None):
    """Insert or update a coupon by (carrier, code). Returns rowid of the row."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO provider_coupons
                 (carrier, code, discount_label, expires_at, source_url,
                  is_active, notes, external_offer_url, partner_name,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(carrier, code) DO UPDATE SET
                 discount_label     = excluded.discount_label,
                 expires_at         = excluded.expires_at,
                 source_url         = excluded.source_url,
                 is_active          = excluded.is_active,
                 notes              = excluded.notes,
                 external_offer_url = excluded.external_offer_url,
                 partner_name       = excluded.partner_name,
                 updated_at         = excluded.updated_at""",
            (carrier, code, discount_label, expires_at, source_url,
             1 if is_active else 0, notes, external_offer_url, partner_name,
             now, now)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM provider_coupons WHERE carrier = ? AND code = ?",
            (carrier, code)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def update_coupon(coupon_id, fields, db_path=None):
    """Partial update by id. `fields` may contain any of the editable columns.
    Returns number of rows updated (0 = not found)."""
    allowed = {"carrier", "code", "discount_label", "expires_at",
               "source_url", "is_active", "notes",
               "external_offer_url", "partner_name"}
    set_clauses = []
    params = []
    for k, v in (fields or {}).items():
        if k not in allowed:
            continue
        if k == "is_active":
            v = 1 if v else 0
        set_clauses.append(f"{k} = ?")
        params.append(v)
    if not set_clauses:
        return 0
    set_clauses.append("updated_at = ?")
    params.append(datetime.now(timezone.utc).isoformat())
    params.append(coupon_id)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            f"UPDATE provider_coupons SET {', '.join(set_clauses)} WHERE id = ?",
            params
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_coupon(coupon_id, db_path=None):
    """Delete by id. Returns number of rows deleted."""
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM provider_coupons WHERE id = ?", (coupon_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def save_reseller_plans(plans, db_path=None):
    """Upsert reseller plans. Each plan dict needs reseller_id, carrier, plan_name, price."""
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO reseller_plans
                  (reseller_id, carrier, plan_name, price, data_gb, minutes, sms, extras, source_url, seen_at, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reseller_id, carrier, plan_name) DO UPDATE SET
                    price      = excluded.price,
                    data_gb    = excluded.data_gb,
                    minutes    = excluded.minutes,
                    sms        = excluded.sms,
                    extras     = excluded.extras,
                    source_url = excluded.source_url,
                    seen_at    = excluded.seen_at,
                    scraped_at = excluded.scraped_at
            """, (
                plan["reseller_id"], plan["carrier"], plan["plan_name"],
                plan.get("price"), plan.get("data_gb"),
                plan.get("minutes"), plan.get("sms"),
                json.dumps(plan.get("extras", []), ensure_ascii=False),
                plan.get("source_url"),
                plan.get("seen_at"),
                now,
            ))
        conn.commit()
    finally:
        conn.close()


# Auto-scraped reseller sources (btl_scrapers.py + the per-site modules, daily
# 08:15). Used by get_scrape_freshness to flag a source whose scraper silently
# broke — seed-only sources (Facebook ads, login-gated clubs) are excluded so
# they don't raise false staleness alarms.
AUTO_SCRAPED_RESELLER_IDS = {
    # "pelephon4u" removed 2026-07-26 — site 403 (Cloudways domain unmapped)
    # since ~2026-07-12; module also dropped from RESELLER_SCRAPER_MODULES.
    # Re-add both if pelephon4u.co.il returns.
    "pelephone_join",                          # legacy per-site modules
    "tiber", "zol_li", "kamaze",               # btl_scrapers — third-party sites
    "wecom_site", "rami_levy_landing",         # btl_scrapers — carrier pages
    "tikshoretishit", "clubdeal",
    "rami_levy_hever", "partner_site",         # btl_scrapers — JS (Playwright)
}


def sync_reseller_plans(plans, db_path=None):
    """Diff freshly-scraped reseller plans against the DB, log to reseller_changes,
    delete stale rows, then UPSERT. Returns the list of change dicts.

    Stale-row deletion is scoped per (reseller_id, carrier) pair and only for
    pairs that returned ≥1 plan in this scrape — so a partially-failed source
    (e.g. tiber's golan page down while its pelephone page works) can't mass-
    remove another pair's rows. Mirrors _delete_stale_carrier_rows semantics.
    """
    if not plans:
        return []
    pairs = {(p["reseller_id"], p["carrier"]) for p in plans}
    changes = []
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for rid, carrier in sorted(pairs):
            old_rows = {
                r[0]: r[1]
                for r in conn.execute(
                    "SELECT plan_name, price FROM reseller_plans "
                    "WHERE reseller_id = ? AND carrier = ?", (rid, carrier))
            }
            new_rows = {p["plan_name"]: p for p in plans
                        if p["reseller_id"] == rid and p["carrier"] == carrier}
            for name, p in new_rows.items():
                if name not in old_rows:
                    changes.append({"reseller_id": rid, "carrier": carrier,
                                    "plan_name": name, "change_type": "new_plan",
                                    "old_val": None, "new_val": str(p.get("price"))})
                else:
                    old_price, new_price = old_rows[name], p.get("price")
                    try:
                        if old_price is not None and new_price is not None \
                                and float(old_price) != float(new_price):
                            changes.append({"reseller_id": rid, "carrier": carrier,
                                            "plan_name": name, "change_type": "price_change",
                                            "old_val": str(old_price), "new_val": str(new_price)})
                    except (TypeError, ValueError):
                        pass
            for name, old_price in old_rows.items():
                if name not in new_rows:
                    conn.execute(
                        "DELETE FROM reseller_plans "
                        "WHERE reseller_id = ? AND carrier = ? AND plan_name = ?",
                        (rid, carrier, name))
                    changes.append({"reseller_id": rid, "carrier": carrier,
                                    "plan_name": name, "change_type": "removed_plan",
                                    "old_val": str(old_price), "new_val": None})
        for ch in changes:
            conn.execute(
                "INSERT INTO reseller_changes "
                "(reseller_id, carrier, plan_name, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ch["reseller_id"], ch["carrier"], ch["plan_name"],
                 ch["change_type"], ch["old_val"], ch["new_val"], now))
        conn.commit()
    finally:
        conn.close()
    save_reseller_plans(plans, db_path=db_path)
    return changes


# Reseller sources always shown regardless of carrier dominance — tracked by
# explicit user request even when the underlying carrier publishes an equal-or-
# better plan (e.g. a carrier's OWN lead-gen landing page, a benefit-club price
# that needs membership, a multi-line bundle whose TOTAL exceeds a single-line
# plan, or a Facebook-ad disclosure). rami_levy also needs this because its
# kosher ₪14.9 plan stores data_gb=None (≡ ∞ here), which would otherwise
# dominate every priced rami_levy reseller plan.
ALWAYS_SHOW_RESELLER_IDS = {
    "rami_levy_landing",
    "rami_levy_hever",    # club-exclusive prices (membership required)
    "rami_levy_cc",       # credit-card benefit on a rate-card plan
    "partner_site",       # Partner's own lobby — BTL terms of rate-card plans
    "wecom_site",         # WeCom's own data-only page
    "clubdeal",           # Pelephone-owned members club
    "pelephone_fb",       # official FB-ad campaign
    "analizer",           # FB-ad broker disclosure (continuation pricing)
    "kamaze",             # only BTL-marked rows are scraped (multi-line/ladder)
    "kamazeole",          # 3-line family bundle — total-price dominance is unfair
}


def filter_undominated_reseller_plans(reseller_plans, db_path=None):
    """Remove reseller plans that are dominated by the official carrier's own plans.

    Dominance: a carrier plan dominates a reseller plan if it offers >=data_gb at <=price.
    Reseller plans with no comparable carrier offering (e.g. smaller GB tier the carrier
    doesn't publish) are always kept. data_gb=None is treated as unlimited (∞).

    This is the rule "show only resellers whose plans are cheaper than the carrier OR
    not on the carrier's site." Applied lazily at API time so the DB keeps full history.
    """
    if not reseller_plans:
        return []
    carriers_needed = {p["carrier"] for p in reseller_plans}
    # One query for all needed carriers instead of a get_plans() per carrier
    # (each of which opened its own connection and json.loads'd every extras blob).
    # Dominance only needs price + data_gb, so fetch just those two columns.
    carrier_plans_by_id = {}
    if carriers_needed:
        conn = _connect(db_path)
        try:
            placeholders = ",".join("?" * len(carriers_needed))
            rows = conn.execute(
                f"SELECT carrier, price, data_gb FROM plans WHERE carrier IN ({placeholders})",
                tuple(carriers_needed)
            ).fetchall()
        finally:
            conn.close()
        for c, price, gb in rows:
            carrier_plans_by_id.setdefault(c, []).append({"price": price, "data_gb": gb})

    def _gb(v):
        return float("inf") if v is None else v

    kept = []
    for rp in reseller_plans:
        if rp.get("reseller_id") in ALWAYS_SHOW_RESELLER_IDS:
            kept.append(rp)
            continue
        r_price = rp.get("price")
        if r_price is None:
            kept.append(rp)
            continue
        r_gb = _gb(rp.get("data_gb"))
        cps = carrier_plans_by_id.get(rp["carrier"], [])
        dominated = False
        for cp in cps:
            c_price = cp.get("price")
            if c_price is None:
                continue
            if _gb(cp.get("data_gb")) >= r_gb and c_price <= r_price:
                dominated = True
                break
        if not dominated:
            kept.append(rp)
    return kept


def get_reseller_plans(reseller_id=None, carrier=None, db_path=None):
    """Return reseller plans. Filter by reseller_id and/or underlying carrier."""
    conn = _connect(db_path)
    try:
        sql = ("SELECT reseller_id, carrier, plan_name, price, data_gb, minutes, "
               "sms, extras, source_url, seen_at, scraped_at FROM reseller_plans")
        clauses, params = [], []
        if reseller_id:
            clauses.append("reseller_id = ?")
            params.append(reseller_id)
        if carrier:
            clauses.append("carrier = ?")
            params.append(carrier)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY price"
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "reseller_id": r[0], "carrier": r[1], "plan_name": r[2],
                "price": r[3], "data_gb": r[4], "minutes": r[5], "sms": r[6],
                "extras": json.loads(r[7]) if r[7] else [],
                "source_url": r[8], "seen_at": r[9], "scraped_at": r[10],
            }
            for r in rows
        ]
    finally:
        conn.close()


def save_usa_tourist_plans(plans, db_path=None):
    """Upsert US tourist-plan rows. Each dict needs carrier (US operator id) and
    plan_name; price is ILS-converted, original_price is the native USD amount."""
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO usa_tourist_plans
                  (carrier, plan_name, price, currency, original_price, data_gb,
                   minutes, sms, days, esim, network, extras, source_url, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price          = excluded.price,
                    currency       = excluded.currency,
                    original_price = excluded.original_price,
                    data_gb        = excluded.data_gb,
                    minutes        = excluded.minutes,
                    sms            = excluded.sms,
                    days           = excluded.days,
                    esim           = excluded.esim,
                    network        = excluded.network,
                    extras         = excluded.extras,
                    source_url     = excluded.source_url,
                    scraped_at     = excluded.scraped_at
            """, (
                plan["carrier"], plan["plan_name"],
                plan.get("price"), plan.get("currency", "USD"),
                plan.get("original_price"), plan.get("data_gb"),
                plan.get("minutes"), plan.get("sms"), plan.get("days"),
                1 if plan.get("esim") else 0, plan.get("network"),
                json.dumps(plan.get("extras", []), ensure_ascii=False),
                plan.get("source_url"),
                now,
            ))
        conn.commit()
    finally:
        conn.close()


def get_usa_tourist_plans(carrier=None, db_path=None):
    """Return US tourist plans, optionally filtered by operator id."""
    conn = _connect(db_path)
    try:
        sql = ("SELECT carrier, plan_name, price, currency, original_price, data_gb, "
               "minutes, sms, days, esim, network, extras, source_url, scraped_at "
               "FROM usa_tourist_plans")
        params = []
        if carrier:
            sql += " WHERE carrier = ?"
            params.append(carrier)
        sql += " ORDER BY price"
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "currency": r[3], "original_price": r[4], "data_gb": r[5],
                "minutes": r[6], "sms": r[7], "days": r[8],
                "esim": bool(r[9]), "network": r[10],
                "extras": json.loads(r[11]) if r[11] else [],
                "source_url": r[12], "scraped_at": r[13],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_recent_changes_summary(within_hours=26, db_path=None):
    """Return all change events from the last N hours, grouped by plan category.

    Powers the morning-check digest: unlike the per-scrape notifications (which
    only fire on freshly-detected changes), this reads the change LOG so the
    daily summary includes every event recorded in the window — even ones whose
    real-time notification was missed.

    Returns {'domestic': [...], 'abroad': [...], 'global': [...], 'content': [...]}.
    Content rows carry both 'service' and 'carrier'.
    """
    cutoff = (datetime.now() - timedelta(hours=within_hours)).isoformat()
    conn = _connect(db_path)
    try:
        summary = {}
        for key, table in (("domestic", "changes"), ("abroad", "abroad_changes"),
                           ("global", "global_changes")):
            rows = conn.execute(
                f"SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
                f"FROM {table} WHERE changed_at >= ? ORDER BY changed_at DESC, id DESC",
                (cutoff,)
            ).fetchall()
            summary[key] = [
                {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
                 "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
                for r in rows
            ]
        rows = conn.execute(
            "SELECT service, carrier, change_type, old_val, new_val, changed_at "
            "FROM content_changes WHERE changed_at >= ? ORDER BY changed_at DESC, id DESC",
            (cutoff,)
        ).fetchall()
        summary["content"] = [
            {"service": r[0], "carrier": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
        # Below-the-line (משווקים) — reseller rows carry both the reseller_id
        # and the underlying carrier so the digest can show "טיבר · פלאפון".
        rows = conn.execute(
            "SELECT reseller_id, carrier, plan_name, change_type, old_val, new_val, changed_at "
            "FROM reseller_changes WHERE changed_at >= ? ORDER BY changed_at DESC, id DESC",
            (cutoff,)
        ).fetchall()
        summary["resellers"] = [
            {"reseller_id": r[0], "carrier": r[1], "plan_name": r[2], "change_type": r[3],
             "old_val": r[4], "new_val": r[5], "changed_at": r[6]}
            for r in rows
        ]
        return summary
    finally:
        conn.close()


def get_scrape_freshness(db_path=None):
    """Per-carrier plan count + most recent scraped_at for each plan table.

    A carrier whose last_scraped is old (or whose count is 0) means its scraper
    silently broke — change detection can't flag a new plan it never saw, so
    the morning check surfaces these as freshness warnings.
    """
    conn = _connect(db_path)
    try:
        out = {}
        for key, table in (("domestic", "plans"), ("abroad", "abroad_plans"),
                           ("global", "global_plans"), ("content", "content_plans")):
            rows = conn.execute(
                f"SELECT carrier, COUNT(*), MAX(scraped_at) FROM {table} GROUP BY carrier"
            ).fetchall()
            out[key] = [
                {"carrier": r[0], "count": r[1], "last_scraped": r[2]}
                for r in rows
            ]
        # Auto-scraped reseller sources only — seed-only sources (FB ads,
        # login-gated clubs) refresh manually and must not alarm as stale.
        seen = {}
        for rid, count, last in conn.execute(
                "SELECT reseller_id, COUNT(*), MAX(scraped_at) "
                "FROM reseller_plans GROUP BY reseller_id"):
            seen[rid] = (count, last)
        out["resellers"] = [
            {"carrier": rid, "count": seen.get(rid, (0, None))[0],
             "last_scraped": seen.get(rid, (0, None))[1]}
            for rid in sorted(AUTO_SCRAPED_RESELLER_IDS)
        ]
        return out
    finally:
        conn.close()
