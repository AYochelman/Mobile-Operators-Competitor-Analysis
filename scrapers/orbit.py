"""orbit scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


ORBIT_NAME_TO_HEBREW = {
    "Afghanistan": "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "Albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Anguilla": "\u05d0\u05e0\u05d2\u05d9\u05dc\u05d4",
    "Antigua And Barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "Argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "Armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "Aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "Australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "Austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "Azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "Bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "Bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "Bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "Barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "Belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "Belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "Belize": "\u05d1\u05dc\u05d9\u05d6",
    "Benin": "\u05d1\u05e0\u05d9\u05df",
    "Bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "Bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Bosnia And Herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Botswana": "\u05d1\u05d5\u05e6\u05d5\u05d5\u05d0\u05e0\u05d4",
    "Brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "British Virgin Islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Burkina Faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "Canada": "\u05e7\u05e0\u05d3\u05d4",
    "Cape Verde": "\u05db\u05e3 \u05d5\u05e8\u05d3\u05d4",
    "Cayman Islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Central African Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Chad": "\u05e6'\u05d0\u05d3",
    "Chile": "\u05e6'\u05d9\u05dc\u05d4",
    "China": "\u05e1\u05d9\u05df",
    "Colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Congo": "\u05e7\u05d5\u05e0\u05d2\u05d5",
    "Costa Rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Cuba": "\u05e7\u05d5\u05d1\u05d4",
    "Curacao": "\u05e7\u05d5\u05e8\u05e1\u05d0\u05d5",
    "Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Czech Republic": "\u05e6'\u05db\u05d9\u05d4",
    "Democratic Republic Of The Congo": "\u05e7\u05d5\u05e0\u05d2\u05d5 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea",
    "Denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "Dominican Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "East Timor": "\u05de\u05d6\u05e8\u05d7 \u05d8\u05d9\u05de\u05d5\u05e8",
    "Ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "El Salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "Estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Eswatini": "\u05d0\u05e1\u05d5\u05d5\u05d8\u05d9\u05e0\u05d9",
    "Ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Faroe Islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "Finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "France": "\u05e6\u05e8\u05e4\u05ea",
    "French Guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Gabon": "\u05d2\u05d1\u05d5\u05df",
    "Gambia": "\u05d2\u05de\u05d1\u05d9\u05d4",
    "Georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "Germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "Ghana": "\u05d2\u05d0\u05e0\u05d4",
    "Gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "Greece": "\u05d9\u05d5\u05d5\u05df",
    "Greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "Guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "Guam": "\u05d2\u05d5\u05d0\u05dd",
    "Guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "Guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "Guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "Guinea-Bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "Guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "Haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "Honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "Hong Kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "Hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "Iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "India": "\u05d4\u05d5\u05d3\u05d5",
    "Indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "Iran": "\u05d0\u05d9\u05e8\u05df",
    "Iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "Ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Isle of Man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Ivory Coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Japan": "\u05d9\u05e4\u05df",
    "Jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "Jordan": "\u05d9\u05e8\u05d3\u05df",
    "Kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Kenya": "\u05e7\u05e0\u05d9\u05d4",
    "Kosovo": "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "Kuwait": "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "Kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Laos": "\u05dc\u05d0\u05d5\u05e1",
    "Latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "Liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "Luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4",
    "Madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Mali": "\u05de\u05d0\u05dc\u05d9",
    "Malta": "\u05de\u05dc\u05d8\u05d4",
    "Martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "Mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "Mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "Mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "Moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "Monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "Mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "Montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "Montserrat": "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "Morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "Nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "Nepal": "\u05e0\u05e4\u05d0\u05dc",
    "Netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "Netherlands Antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "New Zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Niger": "\u05e0\u05d9\u05d2'\u05e8",
    "Nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "Norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "Oman": "\u05e2\u05d5\u05de\u05d0\u05df",
    "Pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "Palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "Panama": "\u05e4\u05e0\u05de\u05d4",
    "Papua New Guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Peru": "\u05e4\u05e8\u05d5",
    "Philippines": "\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Puerto Rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "Qatar": "\u05e7\u05d8\u05e8",
    "Reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Russia": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "Rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Saint Kitts And Nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d1\u05d9\u05e1",
    "Saint Lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Saint Vincent And The Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "San Marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "Saudi Arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Senegal": "\u05e1\u05e0\u05d2\u05dc",
    "Serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Sierra Leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "Singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Sint Maarten": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "Slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "South Africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "South Korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "South Sudan": "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "Spain": "\u05e1\u05e4\u05e8\u05d3",
    "Sri Lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Sudan": "\u05e1\u05d5\u05d3\u05df",
    "Suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Togo": "\u05d8\u05d5\u05d2\u05d5",
    "Tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Trinidad And Tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "Turks And Caicos Islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",  # איי טורקס וקאיקוס
    "Uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "United Arab Emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "United Kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "United States": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "United States Virgin Islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",  # איי הבתולה (ארה"ב)
    "Uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


ORBIT_ZONE_TO_HEBREW = {
    1: "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",                           # אירופה
    2: "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",                           # גלובלי
    3: "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",                           # אפריקה
    4: "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",  # המזרח התיכון וצפון אפריקה
    5: "\u05d0\u05e1\u05d9\u05d4",                                        # אסיה
    7: "\u05e6\u05e4\u05d5\u05df \u05d5\u05d3\u05e8\u05d5\u05dd \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",  # צפון ודרום אמריקה
    17: "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9 \u05e4\u05dc\u05d5\u05e1",  # גלובלי פלוס
    18: "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",  # צפון אמריקה
    19: "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",  # אמריקה הלטינית
}


# Product title of a regional pass -> (Hebrew plan-name prefix, extras[0] region).
# Prefixes are the ones the old be.orbitmobile.com zones produced, so the stored
# plan_name keys (and their price history) carry over unchanged.
ORBIT_PASS_TO_HEBREW = {
    "Europe Pass":                     ("אירופה", "אירופה"),
    "Global Pass":                     ("גלובלי", "גלובלי"),
    "Global Pass Plus":                ("גלובלי פלוס", "גלובלי"),
    "Africa Pass":                     ("אפריקה", "אפריקה"),
    "Middle East & North Africa Pass": ("המזרח התיכון וצפון אפריקה", "המזרח התיכון וצפון אפריקה"),
    "Asia Pass":                       ("אסיה", "אסיה"),
    "North & South America Pass":      ("צפון ודרום אמריקה", "צפון ודרום אמריקה"),
    "North America Pass":              ("צפון אמריקה", "צפון אמריקה"),
    "Latin America Pass":              ("אמריקה הלטינית", "אמריקה הלטינית"),
}

# Country product titles the new storefront spells differently from the old API
_ORBIT_TITLE_ALIASES = {
    "Curaçao": "Curacao",
    "Viet Nam": "Vietnam",
}

_ORBIT_STORE = "https://storefront.orbitmobile.com/store/plans"


def _orbit_fetch_catalog():
    """Return every plan of the Orbit storefront (paged, ~4,300 rows, auth-free)."""
    import requests as _req
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
        "accept": "application/json",
    }
    plans, offset = [], 0
    while True:
        try:
            resp = _req.get(_ORBIT_STORE, params={"limit": 1000, "offset": offset},
                            headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            if not plans:
                raise
            # A later page failed: keep the pages we have (the stale-row purge
            # refuses to act on a partial catalog) rather than dropping the run.
            logger.warning(f"Orbit: catalog page at offset {offset} failed ({e}) - partial catalog of {len(plans)} rows")
            return plans
        batch = data.get("plans") or []
        plans.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(data.get("count") or 0):
            return plans


def scrape_orbit_global(_page=None, usd_rate=None):
    """Scrape Orbit Mobile eSIM plans from the storefront REST API (no browser).

    Orbit moved platforms in 2026-10/11: the old be.orbitmobile.com API now answers
    every call with HTTP 505 "Upgrade required" (the scraper returned [] silently
    from 2026-11-08). The site is now a storefront on
    storefront.orbitmobile.com/store/plans - one public, paged JSON feed holding:
      * fixed packages per country (1/3/5/10/20GB x 30 days) - same catalog as before
      * regional passes (Europe / Global / Asia ...), with their country lists
      * "Build your own" daily plans (1GB/day, 2GB/day, unlimited x 1-15 days)
      * "Boost" top-ups (need an active plan) and a once-per-customer 1-day trial
        of the Global Pass - both skipped, they are not standalone offers.
    Prices are USD minor units (amount / 100).
    """
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    all_plans = []
    try:
        catalog = _orbit_fetch_catalog()
    except Exception as e:
        logger.error(f"Orbit global failed: {e}", exc_info=True)
        return all_plans

    def _title(item):
        return (((item.get("variant") or {}).get("product") or {}).get("title") or "").strip()

    # The storefront is inconsistent about capitalisation ("Viet Nam" / "Viet nam")
    name_ci = {k.lower(): v for k, v in ORBIT_NAME_TO_HEBREW.items()}
    name_ci.update({k.lower(): ORBIT_NAME_TO_HEBREW[v] for k, v in _ORBIT_TITLE_ALIASES.items()})

    def _country_heb(title):
        title = _ORBIT_TITLE_ALIASES.get(title, title)
        return ORBIT_NAME_TO_HEBREW.get(title) or name_ci.get(title.lower(), "")

    # ISO code -> Hebrew, preferring Orbit's own spellings (from single-country products)
    code_heb = {}
    for item in catalog:
        codes = item.get("countries") or []
        if len(codes) == 1:
            heb = _country_heb(_title(item).split(" · ")[0])
            if heb:
                code_heb.setdefault(codes[0], heb)

    seen, skipped_titles = set(), set()
    counts = {"country": 0, "pass": 0, "daily": 0}
    for item in catalog:
        try:
            if item.get("status") != "published":
                continue
            full_title = _title(item)
            if "Boost" in full_title:
                continue                                   # top-up, not a standalone plan
            base_title = full_title.split(" · ")[0]
            meta = item.get("metadata") or {}
            daily = meta.get("allowance_period") == "day"
            days = int(item.get("duration") or 0)
            if days <= 0 or (item.get("duration_unit") or "days") != "days":
                continue
            usd = next((p.get("amount") for p in (item.get("variant") or {}).get("prices") or []
                        if p.get("currency_code") == "usd"), None)
            if not usd or usd <= 0:
                continue
            usd = usd / 100.0

            amount = float(item.get("data_allowance") or 0)
            unlimited = amount < 0
            per_gb = None
            if not unlimited:
                if amount == 0:
                    continue
                per_gb = amount / 1024 if (item.get("data_allowance_unit") or "").upper() == "MB" else amount
            codes = item.get("countries") or []

            if base_title in ORBIT_PASS_TO_HEBREW:
                if days == 1 and not daily:
                    continue                               # once-per-customer trial pass
                prefix, region = ORBIT_PASS_TO_HEBREW[base_title]
                covered = [code_heb.get(c) or core.ESIMO_CODE_TO_HEBREW.get(c) for c in codes]
                extras = [region] + [c for c in covered if c]
                kind = "pass"
            else:
                prefix = _country_heb(base_title)
                if not prefix:
                    skipped_titles.add(base_title)
                    continue
                extras = [prefix]
                kind = "country"

            day_unit = "יום" if days == 1 else "ימים"
            if unlimited:
                gb, gb_str = None, "ללא הגבלה"
                extras.append("גלישה ללא הגבלה")
                desc = ((item.get("variant") or {}).get("product") or {}).get("description") or ""
                m = re.search(r"Unlimited includes (\d+) GB/day at high speed, then ([\d.]+) Mbps", desc)
                if m:
                    extras.append(f"{m.group(1)}GB ליום במהירות גבוהה, לאחר מכן {m.group(2)}Mbps")
            else:
                if per_gb < 1:
                    size = f"{round(per_gb * 1024)}MB"
                else:
                    size = f"{per_gb:g}GB"
                if daily:
                    gb, gb_str = round(per_gb * days, 4), f"{size} ליום"
                    extras.append(f"{size} ליום")
                else:
                    gb, gb_str = per_gb, size
            if daily:
                kind = "daily"

            plan_name = f"{prefix} - {gb_str} - {days} {day_unit}"
            if plan_name in seen:                          # guard UNIQUE(carrier, plan_name)
                continue
            seen.add(plan_name)
            all_plans.append(core._make_global_plan(
                "orbit", plan_name, round(usd * usd_rate, 2), "USD", usd,
                data_gb=gb, days=days, esim=True, extras=extras,
            ))
            counts[kind] += 1
        except (ValueError, TypeError, AttributeError):
            continue

    if skipped_titles:
        logger.warning(
            f"Orbit: skipped unmapped products {sorted(skipped_titles)} "
            f"- add them to ORBIT_NAME_TO_HEBREW / ORBIT_PASS_TO_HEBREW"
        )
    logger.info(
        f"Orbit total: {len(all_plans)} plans ({counts['country']} country, "
        f"{counts['pass']} regional, {counts['daily']} daily) from {len(catalog)} catalog rows"
    )
    return all_plans
