"""terminalesim scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


# Pure-HTTP WooCommerce Store API scrape (same platform as SimTLV). ~2,900
# products across ~190 countries + regional/global bundles, priced in USD
# (minor units -> /100). Replaced GlobaleSIM 2026-07 when the operator asked
# us to track terminalesim.com instead (message from 054-4322104).
#
# The product slug encodes the package: "<code>_<gb>_<period>" where period
# is a day count ("et_20_30" = 20GB/30d) or "daily" ("et_10_daily" = 10GB/
# day, no fixed validity). Country codes are ISO-3166 alpha-2 -> Hebrew via
# TERMINAL_CODE_TO_HEBREW; regional codes carry a trailing area count
# ("eu-33", "gl-120") and map to a canonical Hebrew region (all KNOWN_REGIONS
# on the dashboard) via TERMINAL_REGION_BASE. Data/validity are read from the
# product NAME (explicit GB/MB + "NDays" / "/Day"), which is authoritative.
TERMINAL_CODE_TO_HEBREW = {
    "ad": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "ae": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "af": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "ag": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "ai": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "al": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "am": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "ao": "\u05d0\u05e0\u05d2\u05d5\u05dc\u05d4",
    "ar": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "at": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "au": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "ax": "\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3",
    "az": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "ba": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "bb": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "bd": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "be": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "bf": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "bg": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "bh": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bj": "\u05d1\u05e0\u05d9\u05df",
    "bl": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "bm": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bn": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bo": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "br": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "bs": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bt": "\u05d1\u05d4\u05d5\u05d8\u05df",
    "bw": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4",
    "by": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "bz": "\u05d1\u05dc\u05d9\u05d6",
    "ca": "\u05e7\u05e0\u05d3\u05d4",
    "cd": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "cf": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "cg": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "ch": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "ci": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "cl": "\u05e6'\u05d9\u05dc\u05d4",
    "cm": "\u05e7\u05de\u05e8\u05d5\u05df",
    "cn": "\u05e1\u05d9\u05df",
    "co": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "cr": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "cv": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "cw": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cy": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "cz": "\u05e6'\u05db\u05d9\u05d4",
    "de": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "dk": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dm": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "do": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "dz": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "ec": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "ee": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "eg": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "es": "\u05e1\u05e4\u05e8\u05d3",
    "et": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "fi": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "fj": "\u05e4\u05d9\u05d2'\u05d9",
    "fo": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fr": "\u05e6\u05e8\u05e4\u05ea",
    "ga": "\u05d2\u05d1\u05d5\u05df",
    "gb": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "gd": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "ge": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "gf": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gg": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "gh": "\u05d2\u05d0\u05e0\u05d4",
    "gi": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "gl": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "gm": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "gn": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "gp": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "gr": "\u05d9\u05d5\u05d5\u05df",
    "gt": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "gu": "\u05d2\u05d5\u05d0\u05dd",
    "gw": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "gy": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "hk": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hn": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hr": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "ht": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "hu": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "id": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "ie": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "il": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "im": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "in": "\u05d4\u05d5\u05d3\u05d5",
    "iq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "is": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "it": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "je": "\u05d2'\u05e8\u05d6\u05d9",
    "jm": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "jo": "\u05d9\u05e8\u05d3\u05df",
    "jp": "\u05d9\u05e4\u05df",
    "ke": "\u05e7\u05e0\u05d9\u05d4",
    "kg": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "kh": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "kn": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "kr": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "kw": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "ky": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "kz": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "la": "\u05dc\u05d0\u05d5\u05e1",
    "lc": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "li": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lk": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "lr": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "lt": "\u05dc\u05d9\u05d8\u05d0",
    "lu": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "lv": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "ly": "\u05dc\u05d5\u05d1",
    "ma": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mc": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "md": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "me": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "mf": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "mg": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "mk": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "ml": "\u05de\u05d0\u05dc\u05d9",
    "mn": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "mo": "\u05de\u05e7\u05d0\u05d5",
    "mq": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "ms": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "mt": "\u05de\u05dc\u05d8\u05d4",
    "mu": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mv": "\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mw": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "mx": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "my": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "mz": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "ne": "\u05e0\u05d9\u05d2'\u05e8",
    "ng": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "ni": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "nl": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "no": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "np": "\u05e0\u05e4\u05d0\u05dc",
    "nz": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "om": "\u05e2\u05d5\u05de\u05d0\u05df",
    "pa": "\u05e4\u05e0\u05de\u05d4",
    "pe": "\u05e4\u05e8\u05d5",
    "pf": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "ph": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "pk": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "pl": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "pr": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "pt": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "py": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "qa": "\u05e7\u05d8\u05e8",
    "re": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "ro": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "rs": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "ru": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rw": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "sa": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "sc": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sd": "\u05e1\u05d5\u05d3\u05df",
    "se": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "sg": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "si": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "sk": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "sl": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "sm": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "sn": "\u05e1\u05e0\u05d2\u05dc",
    "sr": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "sv": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "sz": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9",
    "tc": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "td": "\u05e6'\u05d0\u05d3",
    "th": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "tj": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tn": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "tr": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "tt": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tz": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "ua": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "ug": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "us": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "uy": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "uz": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "va": "\u05d4\u05d5\u05d5\u05ea\u05d9\u05e7\u05df",
    "vc": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd",
    "vg": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d1\u05e8\u05d9\u05d8\u05d9\u05d9\u05dd",
    "vn": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "ws": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "xk": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "yt": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "za": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "zm": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


TERMINAL_REGION_BASE = {
    "eu": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "as": "\u05d0\u05e1\u05d9\u05d4",
    "na": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "sa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "af": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "oc": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "o-oc": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "me": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "cb": "\u05d0\u05d9\u05d9 \u05d4\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "ca": "\u05de\u05e8\u05db\u05d6 \u05d0\u05e1\u05d9\u05d4",
    "gl": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "cn": "\u05e1\u05d9\u05df + \u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2 + \u05de\u05e7\u05d0\u05d5",
    "cnhk": "\u05e1\u05d9\u05df + \u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2 + \u05de\u05e7\u05d0\u05d5",
    "cnjpkr": "\u05d0\u05e1\u05d9\u05d4",
    "jpkr": "\u05d9\u05e4\u05df \u05d5\u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "aunz": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "usca": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "bi": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "iesi": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "aukus": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "saaeqakwombh": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "sgmy": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "sgmyth": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
    "sgmyvnthid": "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
}


TERMINAL_REGION_FULL = {
    "eu-7": "\u05d1\u05dc\u05e7\u05df",
    "as-5": "\u05de\u05e8\u05db\u05d6 \u05d0\u05e1\u05d9\u05d4",
}


def _terminal_resolve_dest(slug):
    """slug -> (dest_hebrew, is_region, area_count) or (None, None, None)."""
    code = slug.split("_")[0]
    if code in TERMINAL_CODE_TO_HEBREW:
        return TERMINAL_CODE_TO_HEBREW[code], False, None
    low = slug.lower()
    if low.startswith("england") or low.startswith("united-kingdom"):
        return TERMINAL_CODE_TO_HEBREW["gb"], False, None
    if code in TERMINAL_REGION_FULL:
        m = re.search(r"-(\d+)$", code)
        return TERMINAL_REGION_FULL[code], True, (int(m.group(1)) if m else None)
    m = re.match(r"^(.*)-(\d+)$", code)
    if m and m.group(1) in TERMINAL_REGION_BASE:
        return TERMINAL_REGION_BASE[m.group(1)], True, int(m.group(2))
    return None, None, None


def _terminal_parse_pkg(name):
    """Terminal product name -> (data_gb, days, is_daily, fup_note).

    data_gb: None if no size token; MB stored as GB fraction (<1).
    days: None for "/Day" plans (validity chosen at checkout).
    """
    n = name
    is_daily = bool(re.search(r"/\s*Day", n, re.I) or re.search(r"\bDaily\b", n, re.I))
    gb = None
    dm = re.search(r"(\d+(?:\.\d+)?)\s*GB", n, re.I)
    mbm = re.search(r"(\d+(?:\.\d+)?)\s*MB", n, re.I)
    if dm:
        gb = float(dm.group(1))
        gb = int(gb) if gb == int(gb) else gb
    elif mbm:
        gb = round(float(mbm.group(1)) / 1024, 4)
    dd = re.search(r"(\d+)\s*Days?\b", n, re.I)
    days = int(dd.group(1)) if dd else None
    fup = re.search(r"FUP\s*([0-9]+\s*[MKmk]bps)", n)
    return gb, days, is_daily, (fup.group(1) if fup else None)


def scrape_terminalesim(_page=None, usd_rate=None):
    """Terminal eSIM full per-country/regional catalog via the WooCommerce
    Store API. Pure HTTP, no Playwright. USD prices -> ILS via usd_rate.
    Mirrors scrape_simtlv_esim: dedup by (title, gb, days, daily) keeping the
    newest product id; destinations canonicalized via db._DEST_NORM before the
    plan name is built so plan_name and extras[0] agree (idempotent on save).
    """
    import html as _html
    from db import _DEST_NORM
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    products = core._woo_store_fetch(
        "https://terminalesim.com/wp-json/wc/store/v1/products", "Terminal eSIM")
    best = {}  # (title, gb, days, is_daily) -> (product_id, usd, dest, fup)
    for prod in products:
        try:
            slug = prod.get("slug") or ""
            if not slug or slug == "topup" or slug.startswith("topup"):
                continue
            name = re.sub(r"\s+", " ", _html.unescape(prod.get("name") or "")).strip()
            dest, is_region, area = _terminal_resolve_dest(slug)
            if dest is None:
                continue
            gb, days, is_daily, fup = _terminal_parse_pkg(name)
            if gb is None and not is_daily:
                continue
            if not is_daily and days is None:
                continue
            prices = prod.get("prices") or {}
            minor = int(prices.get("currency_minor_unit") or 2)
            usd = int(prices.get("price")) / (10 ** minor)
            pid = int(prod.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if usd <= 0:
            continue
        dest = _DEST_NORM.get(dest, dest)
        title = f"{dest} ({area} " + "\u05de\u05d3\u05d9\u05e0\u05d5\u05ea" + ")" if (is_region and area) else dest
        key = (title, gb, days, is_daily)
        if key not in best or pid > best[key][0]:
            best[key] = (pid, usd, dest, fup)
    plans = []
    for (title, gb, days, is_daily), (pid, usd, dest, fup) in best.items():
        if gb is None:
            size = "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4"
        elif gb >= 1:
            size = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
        else:
            size = f"{round(gb * 1024)}MB"
        if is_daily:
            plan_name = f"{title} \u2013 {size} " + "\u05dc\u05d9\u05d5\u05dd"
        else:
            plan_name = f"{title} \u2013 {size} \u2013 {days} " + "\u05d9\u05de\u05d9\u05dd"
        extras = [dest]
        if is_daily:
            extras.append("\u05d2\u05dc\u05d9\u05e9\u05d4 \u05d9\u05d5\u05de\u05d9\u05ea")
        if fup:
            extras.append(f"FUP {fup}")
        plans.append(core._make_global_plan(
            "terminalesim", plan_name, round(usd * usd_rate, 2), "USD", round(usd, 2),
            gb, days, esim=True, extras=extras))
    logger.info(f"Terminal eSIM: {len(plans)} plans from {len(products)} products")
    return plans
