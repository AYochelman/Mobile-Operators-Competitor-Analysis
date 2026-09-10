"""esimo scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
import urllib.request
logger = core.logger


ESIMO_CODE_TO_HEBREW = {
    "AD": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "AE": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "AF": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "AG": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "AI": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "AL": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "AM": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "AN": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "AR": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "AT": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "AU": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "AW": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "AX": "\u05d0\u05d9\u05d9 \u05d0\u05d5\u05dc\u05e0\u05d3",
    "AZ": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "BA": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "BB": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "BD": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "BE": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "BF": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "BG": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "BH": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "BJ": "\u05d1\u05e0\u05d9\u05df",
    "BL": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "BM": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "BN": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "BO": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "BQ": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "BR": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "BS": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "BW": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "BY": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "BZ": "\u05d1\u05dc\u05d9\u05d6",
    "CA": "\u05e7\u05e0\u05d3\u05d4",
    "CD": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "CF": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "CG": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d1\u05e8\u05d6\u05d5\u05d5\u05d9\u05dc",  # Congo-Brazzaville \u2014 distinct from CD so plan names don't collide
    "CH": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "CL": "\u05e6'\u05d9\u05dc\u05d4",
    "CM": "\u05e7\u05de\u05e8\u05d5\u05df",
    "CN": "\u05e1\u05d9\u05df",
    "CO": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "CR": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "CU": "\u05e7\u05d5\u05d1\u05d4",
    "CV": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "CW": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "CY": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "CZ": "\u05e6'\u05db\u05d9\u05d4",
    "DE": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "DK": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "DM": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "DO": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "DZ": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "EC": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "EE": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "EG": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "ES": "\u05e1\u05e4\u05e8\u05d3",
    "ET": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "FI": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "FJ": "\u05e4\u05d9\u05d2'\u05d9",
    "FO": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "FR": "\u05e6\u05e8\u05e4\u05ea",
    "GA": "\u05d2\u05d0\u05d1\u05d5\u05df",
    "GB": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "GD": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "GE": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "GF": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "GG": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "GH": "\u05d2\u05d0\u05e0\u05d4",
    "GI": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "GL": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "GM": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "GN": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "GP": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "GR": "\u05d9\u05d5\u05d5\u05df",
    "GT": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "GU": "\u05d2\u05d5\u05d0\u05dd",
    "GW": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "GY": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "HK": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "HN": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "HR": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "HT": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "HU": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "IC": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05e7\u05e0\u05e8\u05d9\u05d9\u05dd",
    "ID": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "IE": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "IL": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "IM": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "IN": "\u05d4\u05d5\u05d3\u05d5",
    "IQ": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "IR": "\u05d0\u05d9\u05e8\u05d0\u05df",
    "IS": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "IT": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "JE": "\u05d2'\u05e8\u05d6\u05d9",
    "JM": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "JO": "\u05d9\u05e8\u05d3\u05df",
    "JP": "\u05d9\u05e4\u05df",
    "KE": "\u05e7\u05e0\u05d9\u05d4",
    "KG": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "KH": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "KN": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "KR": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "KW": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "KY": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "KZ": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "LA": "\u05dc\u05d0\u05d5\u05e1",
    "LB": "\u05dc\u05d1\u05e0\u05d5\u05df",
    "LC": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "LI": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "LK": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "LR": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "LS": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "LT": "\u05dc\u05d9\u05d8\u05d0",
    "LU": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "LV": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "LY": "\u05dc\u05d5\u05d1",
    "MA": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "MC": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "MD": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "ME": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "MF": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "MG": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "MK": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "ML": "\u05de\u05d0\u05dc\u05d9",
    "MN": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "MO": "\u05de\u05e7\u05d0\u05d5",
    "MQ": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "MR": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "MS": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "MT": "\u05de\u05dc\u05d8\u05d4",
    "MU": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "MV": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "MW": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "MX": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "MY": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "MZ": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "NA": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "NE": "\u05e0\u05d9\u05d2'\u05e8",
    "NG": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "NI": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "NL": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "NO": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "NP": "\u05e0\u05e4\u05d0\u05dc",
    "NR": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "NZ": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "OM": "\u05e2\u05d5\u05de\u05d0\u05df",
    "PA": "\u05e4\u05e0\u05de\u05d4",
    "PE": "\u05e4\u05e8\u05d5",
    "PG": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "PH": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "PK": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "PL": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "PR": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "PT": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "PY": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "QA": "\u05e7\u05d8\u05e8",
    "RE": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "RO": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "RS": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "RU": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "RW": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "SA": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "SC": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "SD": "\u05e1\u05d5\u05d3\u05df",
    "SE": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "SG": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "SI": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "SK": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "SL": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "SN": "\u05e1\u05e0\u05d2\u05dc",
    "SR": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "SS": "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "SV": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "SZ": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "TC": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "TD": "\u05e6'\u05d0\u05d3",
    "TG": "\u05d8\u05d5\u05d2\u05d5",
    "TH": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "TJ": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "TN": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "TO": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "TR": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "TT": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "TW": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "TZ": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "UA": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "UG": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "US": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "UY": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "UZ": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "VA": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "VC": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "VE": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "VG": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "VI": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",
    "VN": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "VU": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "WS": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "YT": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "ZA": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "ZM": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


ESIMO_REGION_TO_HEBREW = {
    "Europe": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "Asia": "\u05d0\u05e1\u05d9\u05d4",
    "Africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "North America": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "Latin America": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "Middle East": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "Caribbean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "Balkans": "\u05d1\u05dc\u05e7\u05df",
    "Oceania": "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    "Global": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
}


_ESIMO_REGION_SLUGS = [
    "europe-only-data", "asia-only-data", "africa-only-data",
    "north-america-only-data", "latin-america-only-data", "middle-east-only-data",
    "caribbean-only-data", "balkans-only-data", "oceania-only-data",
    "global-esim-only-data",
]


_ESIMO_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _esimo_fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": _ESIMO_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _esimo_extract_packages(html, array_key="packages"):
    """Reconstruct the Next.js RSC flight stream and pull the embedded packages array.

    esimo.io is a Next.js app: plan data is server-rendered as escaped JSON split across
    multiple self.__next_f.push([1,"..."]) script chunks. The packages array frequently
    straddles a chunk boundary, so the chunks must be decoded and joined BEFORE searching —
    bracket-matching the raw HTML hits the </script><script> junk and corrupts the parse.
    array_key names the prop that holds the array — other Next.js RSC sites embed the
    same shape under a different key (esimgenius.ai uses "plans").
    """
    import json as _json
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    decoded = []
    for c in chunks:
        try:
            decoded.append(_json.loads('"' + c + '"'))
        except Exception:
            continue
    stream = "".join(decoded)
    idx = stream.find(f'"{array_key}":[')
    if idx < 0:
        return []
    start = stream.index('[', idx)
    depth, in_str, esc, end = 0, False, False, None
    for i in range(start, len(stream)):
        ch = stream[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return []
    try:
        return _json.loads(stream[start:end])
    except Exception:
        return []


def scrape_esimo_global(_page=None, usd_rate=None):
    """Scrape ALL eSIMo plans: ~200 country pages (sitemap) + 9 region pages + global.

    Pure HTTP, no Playwright — product pages are SSR'd so the packages JSON is in the
    initial HTML. The sitemap also lists city alias pages (e.g. new-york) that serve
    their country's packages; deduped by package id. Prices are USD (verified against
    /api/firebase-data startingPrice.USD). The destination Hebrew name comes from the
    package `code` field (ISO alpha2 / region name), never from the slug, so alias and
    stale pages cannot mislabel a plan.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    # Region/global products are not in the sitemap — fixed slugs + sitemap countries
    slugs = set(_ESIMO_REGION_SLUGS)
    try:
        sitemap = _esimo_fetch("https://esimo.io/sitemap.xml", timeout=30)
        slugs.update(re.findall(r"<loc>https://esimo\.io/product/([a-z0-9-]+)</loc>", sitemap))
    except Exception as exc:
        logger.warning(f"eSIMo sitemap fetch failed ({exc}) — scraping region/global pages only")

    def fetch_one(slug):
        return _esimo_extract_packages(_esimo_fetch(f"https://esimo.io/product/{slug}"))

    plans, seen_ids = [], set()
    empty, failed = 0, 0
    unknown_codes = set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_one, s): s for s in sorted(slugs)}
        for fut in as_completed(futures):
            slug = futures[fut]
            try:
                pkgs = fut.result()
            except Exception as exc:
                failed += 1
                logger.warning(f"eSIMo {slug}: {exc}")
                continue
            if not pkgs:
                empty += 1  # stale sitemap entry — Next.js soft-404 has no packages
                continue
            for pkg in pkgs:
                pid = pkg.get("id") or f"{pkg.get('code')}|{pkg.get('data')}|{pkg.get('validity')}"
                if pid in seen_ids:
                    continue  # city alias page — country already captured
                code = pkg.get("code") or ""
                dest = ESIMO_CODE_TO_HEBREW.get(code) or ESIMO_REGION_TO_HEBREW.get(code)
                if not dest:
                    unknown_codes.add(code)
                    continue
                try:
                    gb = float(pkg.get("data", 0))
                    days = int(pkg.get("validity", 0))
                    usd = float(pkg.get("price", 0))
                except (TypeError, ValueError):
                    continue
                if gb <= 0 or days <= 0 or usd <= 0:
                    continue
                seen_ids.add(pid)
                price_ils = round(usd * usd_rate, 2)
                if gb >= 1:
                    gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
                else:
                    gb_str = f"{round(gb * 1024)}MB"
                plan_name = f"{dest} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                plans.append(core._make_global_plan(
                    "esimo", plan_name, price_ils, "USD", usd,
                    gb, days, esim=True, extras=[dest]
                ))
    if unknown_codes:
        logger.warning(
            f"eSIMo: skipped unmapped destination codes {sorted(unknown_codes)} "
            f"— add them to ESIMO_CODE_TO_HEBREW"
        )
    logger.info(f"eSIMo global: {len(plans)} plans from {len(slugs)} pages ({empty} empty, {failed} failed)")
    return plans
