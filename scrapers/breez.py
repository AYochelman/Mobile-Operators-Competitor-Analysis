"""breez scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


BREEZ_EN_TO_HEBREW = {
    # Countries
    "Canada": "\u05e7\u05e0\u05d3\u05d4",
    "United States of America": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "Morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "United Kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Spain": "\u05e1\u05e4\u05e8\u05d3",
    "United Arab Emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "Italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Netherlands Antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "France": "\u05e6\u05e8\u05e4\u05ea",
    "Japan": "\u05d9\u05e4\u05df",
    "Switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Mexico": "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "Greece": "\u05d9\u05d5\u05d5\u05df",
    "Peru": "\u05e4\u05e8\u05d5",
    "Saudi Arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Indonesia": "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "Thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Australia": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "Tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Germany": "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "Portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "Northern Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "China": "\u05e1\u05d9\u05df",
    "Brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "Colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Costa Rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Korea Republic of": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "Iceland": "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "Albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Hungary": "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "Netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "Bahamas": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "Hong Kong": "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "Singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Hawaii": "\u05d4\u05d5\u05d5\u05d0\u05d9",
    "Barbados": "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "Pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "VietNam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Argentina": "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "India": "\u05d4\u05d5\u05d3\u05d5",
    "Canary Islands": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05e7\u05e0\u05e8\u05d9\u05d9\u05dd",
    "Dominican Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "South Africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "Poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Austria": "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "Sri Lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "New Zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Chile": "\u05e6'\u05d9\u05dc\u05d4",
    "Croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Taiwan-Province of China": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Belgium": "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "Czech Republic": "\u05e6'\u05db\u05d9\u05d4",
    "Montenegro": "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "Ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "Antigua And Barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "Denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Tanzania, United Republic of": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Cape Verde": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "Suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Malta": "\u05de\u05dc\u05d8\u05d4",
    "Romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Virgin Islands - British": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Panama": "\u05e4\u05e0\u05de\u05d4",
    "Qatar": "\u05e7\u05d8\u05e8",
    "Saint Lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Grenada": "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "Finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Mauritius": "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "El Salvador": "\u05d0\u05dc \u05e1\u05dc\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Kenya": "\u05e7\u05e0\u05d9\u05d4",
    "Turks And Caicos Islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "Trinidad And Tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Russian Federation": "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "Guatemala": "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "Guernsey": "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "Serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Bosnia And Herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Cayman Islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Namibia": "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "Algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Oman": "\u05e2\u05d5\u05de\u05df",
    "Nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "Dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "North Macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "Bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Ghana": "\u05d2\u05d0\u05e0\u05d4",
    "Jordan": "\u05d9\u05e8\u05d3\u05df",
    "Bahrain": "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "Saint Martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "Honduras": "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "Saint Vincent And The Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Georgia": "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "Lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "Isle of Man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "Latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Macao": "\u05de\u05e7\u05d0\u05d5",
    "Moldova": "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "Ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "Curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "Bangladesh": "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "Nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "Middle East and North Africa": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05d5\u05e6\u05e4\u05d5\u05df \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "Azerbaijan": "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "Senegal": "\u05e1\u05e0\u05d2\u05dc",
    "Kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Bonaire, saint Eustatius and Saba": "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "Estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Armenia": "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "Monaco": "\u05de\u05d5\u05e0\u05e7\u05d5",
    "Anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "Ivory Coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Mauritania": "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Martinique": "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "Zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
    "Botswana": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "Saint Kitts And Nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "Andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Guam": "\u05d2\u05d5\u05d0\u05dd",
    "Rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Mongolia": "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "Lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "Virgin Islands - United States": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4\"\u05d1)",
    "Bermuda": "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "Fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "Reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Togo": "\u05d8\u05d5\u05d2\u05d5",
    "Ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Guyana": "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "Papua New Guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Greenland": "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Saint Barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "Benin": "\u05d1\u05e0\u05d9\u05df",
    "Brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Laos": "\u05dc\u05d0\u05d5\u05e1",
    "Palestine": "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df",
    "Kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Guadeloupe": "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "Seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Montserrat": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "Swaziland": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "Congo-the Democratic Republic of the": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Faroe Islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Gibraltar": "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "Mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Sudan": "\u05e1\u05d5\u05d3\u05df",
    "Aruba": "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "Cuba": "\u05e7\u05d5\u05d1\u05d4",
    "Belarus": "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "Central African Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Congo": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "Cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "Burkina Faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Guinea-Bissau": "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "Niger": "\u05e0\u05d9\u05d2'\u05e8",
    "Liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Mali": "\u05de\u05d0\u05dc\u05d9",
    "Iran-Islamic Republic of": "\u05d0\u05d9\u05e8\u05d0\u05df",
    "Chad": "\u05e6'\u05d0\u05d3",
    "Vatican City": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "French Guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Guinea": "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "Gabon": "\u05d2\u05d0\u05d1\u05d5\u05df",
    "Nauru": "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "Mayotte": "\u05de\u05d0\u05d9\u05d5\u05d8",
    "Tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Haiti": "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "Puerto Rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    # Regions (country-bundles collection)
    "Caribbean": "\u05e7\u05e8\u05d9\u05d1\u05d9\u05d9\u05dd",
    "South America": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "EU & USA": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4 \u05d5\u05d0\u05e8\u05d4\"\u05d1",
    "Portugal and Spain": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc \u05d5\u05e1\u05e4\u05e8\u05d3",
    "CENAM": "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6\u05d9\u05ea",
    "Balkans": "\u05d4\u05d1\u05dc\u05e7\u05df",
    "CIS": "\u05d7\u05d1\u05e8 \u05d4\u05de\u05d3\u05d9\u05e0\u05d5\u05ea",
    "Middle East Lite": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df \u05dc\u05d9\u05d9\u05d8",
    "Europe Lite": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4 \u05dc\u05d9\u05d9\u05d8",
    # Regions (regional-bundles collection)
    "EU+": "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4+",
    "North America": "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "Middle East": "\u05d4\u05de\u05d6\u05e8\u05d7 \u05d4\u05ea\u05d9\u05db\u05d5\u05df",
    "Asia": "\u05d0\u05e1\u05d9\u05d4",
    "Global": "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "Africa": "\u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
}


# English product title -> Shopify product handle (breezesim.com/products/<handle>),
# from the same country-bundles + regional-bundles collections the scraper reads. Used
# by app.py to build per-destination affiliate deep-links (/go/breez?dest=...) with the
# UpPromote sca_ref param. Format verified via the dashboard "Get product link" tool
# 2026-07-06 (it emits exactly /products/<handle>?sca_ref=<tag>). Regenerate when Breeze
# changes its catalog (scratchpad breez_en_handles.py: fetch collections, map title->handle).
BREEZ_EN_TO_HANDLE = {
    "Africa": "esimg_raf_v2",
    "Albania": "esimg_al_v2",
    "Algeria": "esimg_dz_v2",
    "Andorra": "esimg_ad_v2",
    "Anguilla": "esimg_ai_v2",
    "Antigua And Barbuda": "esimg_ag_v2",
    "Argentina": "esim-argentina",
    "Armenia": "esimg_am_v2",
    "Aruba": "esim-aruba",
    "Asia": "esim-asia",
    "Australia": "esim-australia",
    "Austria": "esimg_at_v2",
    "Azerbaijan": "esimg_az_v2",
    "Bahamas": "esim-bahamas",
    "Bahrain": "esimg_bh_v2",
    "Balkans": "esim-balkans",
    "Bangladesh": "esimg_bd_v2",
    "Barbados": "esimg_bb_v2",
    "Belarus": "esimg_by_v2",
    "Belgium": "esimg_be_v2",
    "Benin": "esimg_bj_v2",
    "Bermuda": "esim-bermuda",
    "Bolivia": "esimg_bo_v2",
    "Bonaire, saint Eustatius and Saba": "esim-bonaire-saint-eustatius-and-saba",
    "Bosnia And Herzegovina": "esimg_ba_v2",
    "Botswana": "esimg_bw_v2",
    "Brazil": "esim-brazil",
    "Brunei": "esimg_bn_v2",
    "Bulgaria": "esimg_bg_v2",
    "Burkina Faso": "esimg_bf_v2",
    "CENAM": "esim-cenam",
    "CIS": "esim-cis-region",
    "Cambodia": "esimg_kh_v2",
    "Cameroon": "esimg_cm_v2",
    "Canada": "esim-canada",
    "Canary Islands": "esimg_ic_v2",
    "Cape Verde": "esim-cape-verde",
    "Caribbean": "esim-caribbean",
    "Cayman Islands": "esimg_ky_v2",
    "Central African Republic": "esimg_cf_v2",
    "Chad": "esimg_td_v2",
    "Chile": "esimg_cl_v2",
    "China": "esim-china",
    "Colombia": "esim-colombia",
    "Congo": "esimg_cg_v2",
    "Congo-the Democratic Republic of the": "esimg_cd_v2",
    "Costa Rica": "esim-costa-rica",
    "Croatia": "esimg_hr_v2",
    "Cuba": "esim-cuba",
    "Curacao": "esim-curacao",
    "Cyprus": "esimg_cy_v2",
    "Czech Republic": "esimg_cz_v2",
    "Denmark": "esimg_dk_v2",
    "Dominica": "esimg_dm_v2",
    "Dominican Republic": "esim-dominican-republic",
    "EU+": "esim-europe",
    "Ecuador": "esimg_ec_v2",
    "Egypt": "esim-egypt",
    "El Salvador": "esimg_sv_v2",
    "Estonia": "esimg_ee_v2",
    "Ethiopia": "esim-ethiopia",
    "Europe Lite": "esim-europe-lite",
    "Faroe Islands": "esimg_fo_v2",
    "Fiji": "esimg_fj_v2",
    "Finland": "esimg_fi_v2",
    "France": "esim-france",
    "French Guiana": "esimg_gf_v2",
    "Gabon": "esimg_ga_v2",
    "Georgia": "esimg_ge_v2",
    "Germany": "esim-germany",
    "Ghana": "esimg_gh_v2",
    "Gibraltar": "esimg_gi_v2",
    "Global": "esim-global",
    "Greece": "esim-greece",
    "Greenland": "esimg_gl_v2",
    "Grenada": "esimg_gd_v2",
    "Guadeloupe": "esimg_gp_v2",
    "Guam": "esimg_gu_v2",
    "Guatemala": "esimg_gt_v2",
    "Guernsey": "esimg_gg_v2",
    "Guinea": "esimg_gn_v2",
    "Guinea-Bissau": "esimg_gw_v2",
    "Guyana": "esimg_gy_v2",
    "Haiti": "esim-haiti",
    "Hawaii": "esim-hawaii",
    "Honduras": "esimg_hn_v2",
    "Hong Kong": "esim-hong-kong",
    "Hungary": "esim-hungary",
    "Iceland": "esimg_is_v2",
    "India": "esim-india",
    "Indonesia": "esimg_id_v2",
    "Iran-Islamic Republic of": "esimg_ir_v2",
    "Ireland": "esim-ireland",
    "Isle of Man": "esimg_im_v2",
    "Israel": "esimg_il_v2",
    "Italy": "esim-italy",
    "Ivory Coast": "esimg_ci_v2",
    "Jamaica": "esimg_jm_v2",
    "Japan": "esim-japan",
    "Jersey": "esimg_je_v2",
    "Jordan": "esimg_jo_v2",
    "Kazakhstan": "esimg_kz_v2",
    "Kenya": "esimg_ke_v2",
    "Korea Republic of": "esim-south-korea",
    "Kyrgyzstan": "esimg_kg_v2",
    "Laos": "esimg_la_v2",
    "Latvia": "esimg_lv_v2",
    "Lesotho": "esimg_ls_v2",
    "Liberia": "esimg_lr_v2",
    "Liechtenstein": "esimg_li_v2",
    "Lithuania": "esimg_lt_v2",
    "Luxembourg": "esimg_lu_v2",
    "Macao": "esimg_mo_v2",
    "Madagascar": "esimg_mg_v2",
    "Malawi": "esimg_mw_v2",
    "Malaysia": "esimg_my_v2",
    "Mali": "esimg_ml_v2",
    "Malta": "esimg_mt_v2",
    "Martinique": "esimg_mq_v2",
    "Mauritania": "esimg_mr_v2",
    "Mauritius": "esimg_mu_v2",
    "Mayotte": "esimg_yt_v2",
    "Mexico": "esim-mexico",
    "Middle East": "esimg_rme_v2",
    "Middle East and North Africa": "esim-middle-east-and-north-africa",
    "Moldova": "esimg_md_v2",
    "Monaco": "esimg_mc_v2",
    "Mongolia": "esimg_mn_v2",
    "Montenegro": "esimg_me_v2",
    "Montserrat": "esimg_ms_v2",
    "Morocco": "esim-morocco",
    "Mozambique": "esimg_mz_v2",
    "Namibia": "esimg_na_v2",
    "Nauru": "esimg_nr_v2",
    "Netherlands": "esim-netherlands",
    "Netherlands Antilles": "esim-netherlands-antilles",
    "New Zealand": "esimg_nz_v2",
    "Nicaragua": "esimg_ni_v2",
    "Niger": "esimg_ne_v2",
    "Nigeria": "esimg_ng_v2",
    "North America": "esim-north-america",
    "North Macedonia": "esimg_mk_v2",
    "Northern Cyprus": "esim-northern-cyprus",
    "Norway": "esimg_no_v2",
    "Oman": "esimg_om_v2",
    "Pakistan": "esimg_pk_v2",
    "Palestine": "esimg_ps_v2",
    "Panama": "esim-panama",
    "Papua New Guinea": "esimg_pg_v2",
    "Paraguay": "esimg_py_v2",
    "Peru": "esim-peru",
    "Philippines": "esim-philippines",
    "Poland": "esimg_pl_v2",
    "Portugal": "esim-portugal",
    "Puerto Rico": "esim-puerto-rico",
    "Qatar": "esimg_qa_v2",
    "Reunion": "esimg_re_v2",
    "Romania": "esimg_ro_v2",
    "Russian Federation": "esimg_ru_v2",
    "Rwanda": "esimg_rw_v2",
    "Saint Barthelemy": "esimg_bl_v2",
    "Saint Kitts And Nevis": "esimg_kn_v2",
    "Saint Lucia": "esim-saint-lucia",
    "Saint Martin": "esimg_mf_v2",
    "Saint Vincent And The Grenadines": "esimg_vc_v2",
    "Samoa": "esimg_eh_v2",
    "Saudi Arabia": "esim-saudi-arabia",
    "Senegal": "esimg_sn_v2",
    "Serbia": "esimg_rs_v2",
    "Seychelles": "esim-seychelles",
    "Singapore": "esimg_sg_v2",
    "Slovakia": "esimg_sk_v2",
    "Slovenia": "esimg_si_v2",
    "South Africa": "esim-south-africa",
    "South America": "esim-south-america",
    "Spain": "esim-spain",
    "Sri Lanka": "esimg_lk_v2",
    "Sudan": "esimg_sd_v2",
    "Suriname": "esimg_sr_v2",
    "Swaziland": "esimg_sz_v2",
    "Sweden": "esimg_se_v2",
    "Switzerland": "esim-switzerland",
    "Taiwan-Province of China": "esim-taiwan",
    "Tajikistan": "esimg_tj_v2",
    "Tanzania, United Republic of": "esim-tanzania",
    "Thailand": "esim-thailand",
    "Togo": "esim-togo",
    "Tonga": "esimg_to_v2",
    "Trinidad And Tobago": "esimg_tt_v2",
    "Tunisia": "esim-tunisia",
    "Turkey": "esim-turkey",
    "Turks And Caicos Islands": "esimg_tc_v2",
    "Uganda": "esimg_ug_v2",
    "Ukraine": "esimg_ua_v2",
    "United Arab Emirates": "esim-united-arab-emirates",
    "United Kingdom": "esim-united-kingdom",
    "United States of America": "esim-usa",
    "Uruguay": "esimg_uy_v2",
    "Uzbekistan": "esimg_uz_v2",
    "Vanuatu": "esim-vanuatu",
    "Vatican City": "esimg_va_v2",
    "VietNam": "esim-vietnam",
    "Virgin Islands - British": "esimg_vg_v2",
    "Virgin Islands - United States": "esim-virgin-islands-us",
    "Zambia": "esimg_zm_v2",
}


# Hebrew destination -> Shopify handle, composed from the two maps above so the
# /go/breez deep-link layer can key on the canonical Hebrew ?dest= value.
BREEZ_HEB_TO_HANDLE = {
    BREEZ_EN_TO_HEBREW[_en]: _h
    for _en, _h in BREEZ_EN_TO_HANDLE.items()
    if _en in BREEZ_EN_TO_HEBREW
}


def scrape_breez_global(_page=None, usd_rate=None):
    """Scrape Breeze eSIM global plans via Shopify JSON API (USD base pricing, no browser).

    Prices are fetched in the shop's BASE currency (USD) and converted to ILS
    with usd_rate. Do NOT request `currency=ILS` from Shopify — its converted
    prices are re-rounded against a daily FX rate, so the whole catalog
    "changed price" by ±1 ₪ every day (~700 phantom price_change events/day,
    fixed 2026-07-26). currency='USD' + original_price=USD lets
    change_detector compare the stable USD value.
    """
    import requests as _req
    import re as _re

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()
    base = "https://breezesim.com"
    all_plans = []
    seen_names = set()

    def _parse_sku(sku):
        m = _re.match(r'^(?:esimd|2025h2)_(\w+)_(\d+)D_', sku)
        if not m:
            return None, None
        data_part, days = m.group(1), int(m.group(2))
        if data_part == 'ULE':
            return None, days
        gb_m = _re.match(r'^(\d+)GB$', data_part)
        if gb_m:
            return int(gb_m.group(1)), days
        return None, None

    def _fetch_products(collection_handle):
        products, page = [], 1
        while True:
            try:
                r = _req.get(
                    f"{base}/collections/{collection_handle}/products.json",
                    params={"limit": 250, "page": page},
                    timeout=25,
                )
                r.raise_for_status()
                batch = r.json().get("products", [])
                if not batch:
                    break
                products.extend(batch)
                if len(batch) < 250:
                    break
                page += 1
            except Exception:
                break
        return products

    try:
        country_products = _fetch_products("country-bundles")
        regional_products = _fetch_products("regional-bundles")
        logger.info(
            f"Breez: {len(country_products)} country products, "
            f"{len(regional_products)} regional products"
        )

        for product in country_products + regional_products:
            title = product.get("title", "")
            heb_name = BREEZ_EN_TO_HEBREW.get(title)
            if not heb_name:
                continue

            for variant in product.get("variants", []):
                if not variant.get("available", True):
                    continue
                sku = variant.get("sku", "")
                data_gb, days = _parse_sku(sku)
                if days is None:
                    continue
                try:
                    usd = float(variant.get("price", 0))
                except (ValueError, TypeError):
                    continue
                if usd <= 0:
                    continue

                gb_str = (f"{int(data_gb)}GB" if data_gb is not None
                          else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                day_word = "\u05d9\u05d5\u05dd" if days == 1 else "\u05d9\u05de\u05d9\u05dd"
                plan_name = f"{heb_name} \u2013 {gb_str} \u2013 {days} {day_word}"

                if plan_name in seen_names:
                    continue
                seen_names.add(plan_name)

                all_plans.append(core._make_global_plan(
                    "breez", plan_name, usd * usd_rate, "USD", usd,
                    data_gb=data_gb, days=days, esim=True, extras=[heb_name],
                ))

        logger.info(f"Breez total: {len(all_plans)} plans")
    except Exception as e:
        logger.error(f"Breez global failed: {e}", exc_info=True)

    return all_plans
