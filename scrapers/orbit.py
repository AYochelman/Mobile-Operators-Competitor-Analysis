"""orbit scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
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


def scrape_orbit_global(_page=None, usd_rate=None):
    """Scrape Orbit Mobile eSIM plans via their REST API (no browser needed)."""
    import requests as _req
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    all_plans = []
    headers = {
        "companycode": "Web",
        "accept-language": "en",
        "app-version": "1.2",
        "accept": "application/json",
        "apikey": "HzN1buVkKZQfjRhkUy3hFFMif3nTTPE7JEp8ddDv0BQunnJFAq",
        "operatingsystem": "web",
    }
    base = "https://be.orbitmobile.com"

    try:
        # ── Per-country plans ─────────────────────────────────────
        countries_resp = _req.get(f"{base}/plans/countries", headers=headers, timeout=20)
        countries = countries_resp.json().get("countries", [])

        for country in countries:
            cc = country.get("countryCode", "")
            en_name = country.get("countryName", "")
            heb_name = ORBIT_NAME_TO_HEBREW.get(en_name, "")
            if not heb_name or not cc:
                continue
            try:
                plans_resp = _req.get(f"{base}/plans", params={"countryCode": cc}, headers=headers, timeout=15)
                esim_plans = plans_resp.json().get("esimPlans", [])
            except Exception:
                continue

            for plan in esim_plans:
                try:
                    gb = float(plan.get("dataAllowance", 0))
                    days = int(plan.get("validity", 30))
                    prices = plan.get("prices", [])
                    if not prices:
                        continue
                    p = prices[0]
                    price_usd = p.get("discountedCost") or p.get("cost", 0)
                    original_usd = p.get("cost", price_usd)
                    if not price_usd or price_usd <= 0 or gb <= 0:
                        continue
                except (ValueError, TypeError):
                    continue

                price_ils = round(float(price_usd) * usd_rate, 2)
                gb_str = f"{int(gb)}GB" if gb >= 1 else f"{round(gb * 1024)}MB"
                plan_name = f"{heb_name} - {gb_str} - {days} \u05d9\u05de\u05d9\u05dd"
                all_plans.append(core._make_global_plan(
                    "orbit", plan_name, price_ils, "USD", float(original_usd),
                    data_gb=gb, days=days, esim=True, extras=[heb_name]
                ))

        logger.info(f"Orbit countries: {len(all_plans)} plans from {len(countries)} countries")

        # ── Regional / Zone plans ─────────────────────────────────
        zone_count = 0
        try:
            zones_resp = _req.get(f"{base}/plans/zones/custom", headers=headers, timeout=20)
            zones = zones_resp.json().get("zones", [])
        except Exception:
            zones = []

        for zone in zones:
            zone_id = zone.get("zoneId")
            zone_name_en = zone.get("zoneName", "")
            zone_heb = ORBIT_ZONE_TO_HEBREW.get(zone_id, zone_name_en)
            zone_countries = zone.get("countries", [])
            zone_countries_heb = [ORBIT_NAME_TO_HEBREW.get(c.get("countryName", ""), c.get("countryName", "")) for c in zone_countries]

            try:
                zp_resp = _req.get(f"{base}/plans", params={"customZoneId": zone_id}, headers=headers, timeout=15)
                esim_plans = zp_resp.json().get("esimPlans", [])
            except Exception:
                continue

            for plan in esim_plans:
                try:
                    gb = float(plan.get("dataAllowance", 0))
                    days = int(plan.get("validity", 30))
                    prices = plan.get("prices", [])
                    if not prices:
                        continue
                    p = prices[0]
                    price_usd = p.get("discountedCost") or p.get("cost", 0)
                    original_usd = p.get("cost", price_usd)
                    if not price_usd or price_usd <= 0 or gb <= 0:
                        continue
                except (ValueError, TypeError):
                    continue

                price_ils = round(float(price_usd) * usd_rate, 2)
                gb_str = f"{int(gb)}GB" if gb >= 1 else f"{round(gb * 1024)}MB"
                plan_name = f"{zone_heb} - {gb_str} - {days} \u05d9\u05de\u05d9\u05dd"
                # Unify "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9 \u05e4\u05dc\u05d5\u05e1" under canonical "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9" region (qualifier remains in plan_name)
                region_for_extras = "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9" if zone_id == 17 else zone_heb
                all_plans.append(core._make_global_plan(
                    "orbit", plan_name, price_ils, "USD", float(original_usd),
                    data_gb=gb, days=days, esim=True, extras=[region_for_extras] + zone_countries_heb
                ))
                zone_count += 1

        logger.info(f"Orbit zones: {zone_count} plans from {len(zones)} zones")
        logger.info(f"Orbit total: {len(all_plans)} plans")
    except Exception as e:
        logger.error(f"Orbit global failed: {e}", exc_info=True)

    return all_plans
