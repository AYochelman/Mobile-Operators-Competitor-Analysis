"""bcengi scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
logger = core.logger


BCENGI_EN_TO_HEB = {
    "Albania": "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Algeria": "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Andorra": "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Anguilla": "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "Antigua and Barbuda": "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
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
    "Bhutan": "\u05d1\u05d4\u05d5\u05d8\u05df",
    "Bolivia": "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Bosnia and Herzegovina": "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Botswana": "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "Brazil": "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "British Virgin Islands": "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Brunei": "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Bulgaria": "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Burkina Faso": "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Cambodia": "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Cameroon": "\u05e7\u05de\u05e8\u05d5\u05df",
    "Canada": "\u05e7\u05e0\u05d3\u05d4",
    "Cape Verde": "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "Cayman Islands": "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Central African Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Chad": "\u05e6'\u05d0\u05d3",
    "Chile": "\u05e6'\u05d9\u05dc\u05d4",
    "China": "\u05e1\u05d9\u05df",
    "Colombia": "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Comoros": "\u05d0\u05d9\u05d9 \u05e7\u05d5\u05de\u05d5\u05e8\u05d5",
    "Costa Rica": "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Croatia": "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Cuba": "\u05e7\u05d5\u05d1\u05d4",
    "Curacao": "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "Cyprus": "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Czech Republic": "\u05e6'\u05db\u05d9\u05d4",
    "Democratic Republic of the Congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Denmark": "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Dominica": "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "Dominican Republic": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "Ecuador": "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Egypt": "\u05de\u05e6\u05e8\u05d9\u05dd",
    "El Salvador": "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "Estonia": "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Ethiopia": "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Faroe Islands": "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Fiji": "\u05e4\u05d9\u05d2'\u05d9",
    "Finland": "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "France": "\u05e6\u05e8\u05e4\u05ea",
    "French Guiana": "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "French Polynesia": "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Gabon": "\u05d2\u05d0\u05d1\u05d5\u05df",
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
    "Iraq": "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "Ireland": "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Isle of Man": "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Israel": "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "Italy": "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Ivory Coast": "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Jamaica": "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Japan": "\u05d9\u05e4\u05df",
    "Jersey": "\u05d2'\u05e8\u05d6\u05d9",
    "Jordan": "\u05d9\u05e8\u05d3\u05df",
    "Kazakhstan": "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Kenya": "\u05e7\u05e0\u05d9\u05d4",
    "Kiribati": "\u05e7\u05d9\u05e8\u05d9\u05d1\u05d8\u05d9",
    "Kyrgyzstan": "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Laos": "\u05dc\u05d0\u05d5\u05e1",
    "Latvia": "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Lebanon": "\u05dc\u05d1\u05e0\u05d5\u05df",
    "Lesotho": "\u05dc\u05e1\u05d5\u05d8\u05d5",
    "Liberia": "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Liechtenstein": "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Lithuania": "\u05dc\u05d9\u05d8\u05d0",
    "Luxembourg": "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Macau": "\u05de\u05e7\u05d0\u05d5",
    "Macedonia": "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "Madagascar": "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Malawi": "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Malaysia": "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Maldives": "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
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
    "Montserrat": "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "Morocco": "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Mozambique": "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Nepal": "\u05e0\u05e4\u05d0\u05dc",
    "Netherlands": "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "Netherlands Antilles": "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "New Caledonia": "\u05e7\u05dc\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "New Zealand": "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Nicaragua": "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Niger": "\u05e0\u05d9\u05d2'\u05e8",
    "Nigeria": "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "Norway": "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "Oman": "\u05e2\u05d5\u05de\u05df",
    "Pakistan": "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "Palau": "\u05e4\u05dc\u05d0\u05d5",
    # "Palestine" intentionally omitted: db.py _DEST_NORM maps it to "ישראל",
    # which would collide with the Israel entry at a different per-GB rate.
    "Panama": "\u05e4\u05e0\u05de\u05d4",
    "Papua New Guinea": "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Paraguay": "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Peru": "\u05e4\u05e8\u05d5",
    "Philippines": "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Poland": "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Portugal": "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Puerto Rico": "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "Qatar": "\u05e7\u05d8\u05e8",
    "Republic of the Congo": "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Reunion": "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Romania": "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Rwanda": "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Saint Barthelemy": "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "Saint Kitts and Nevis": "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "Saint Lucia": "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Saint Maarten": "\u05e1\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df",
    "Saint Martin": "\u05e1\u05df \u05de\u05e8\u05d8\u05df",
    "Saint Vincent and the Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Samoa": "\u05e1\u05de\u05d5\u05d0\u05d4",
    "San Marino": "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "Saudi Arabia": "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Senegal": "\u05e1\u05e0\u05d2\u05dc",
    "Serbia": "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Seychelles": "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Sierra Leone": "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "Singapore": "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Slovakia": "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Slovenia": "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "South Africa": "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "South Korea": "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "Spain": "\u05e1\u05e4\u05e8\u05d3",
    "Sri Lanka": "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Sudan": "\u05e1\u05d5\u05d3\u05df",
    "Suriname": "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Swaziland": "\u05d0\u05e1\u05d5\u05d5\u05d0\u05d8\u05d9\u05e0\u05d9",
    "Sweden": "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Switzerland": "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Taiwan": "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Tajikistan": "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Tanzania": "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Thailand": "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Timor-Leste": "\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4",
    "Togo": "\u05d8\u05d5\u05d2\u05d5",
    "Tonga": "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Trinidad and Tobago": "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Tunisia": "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Turkey": "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "Turks and Caicos Islands": "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "U.S. Virgin Islands": '\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d0\u05e8\u05d4"\u05d1)',
    "Uganda": "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Ukraine": "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "United Arab Emirates": "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "United Kingdom": "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "United States": "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "Uruguay": "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Uzbekistan": "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu": "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Vatican City": "\u05d5\u05ea\u05d9\u05e7\u05df",
    "Venezuela": "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "Vietnam": "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Zambia": "\u05d6\u05de\u05d1\u05d9\u05d4",
}


BCENGI_BENEFITS = [
    "\u05ea\u05e9\u05dc\u05d5\u05dd \u05dc\u05e4\u05d9 \u05e9\u05d9\u05de\u05d5\u05e9 (GB)",
    "\u05dc\u05dc\u05d0 \u05ea\u05e4\u05d5\u05d2\u05d4 \u05dc\u05d9\u05ea\u05e8\u05d4",
    "\u05ea\u05e2\u05e8\u05d9\u05e4\u05d9 \u05de\u05e4\u05e2\u05d9\u05dc \u05de\u05e7\u05d5\u05de\u05d9",
    "eSIM \u05d0\u05d7\u05d3 \u05dc\u05db\u05dc \u05d4\u05d8\u05d9\u05d5\u05dc\u05d9\u05dd",
]


def _parse_bcengi_body(body, usd_rate):
    lines = [l.strip() for l in body.split('\n')]
    plans = []
    for i, line in enumerate(lines):
        if line == '/GB' and i >= 8:
            price_str  = lines[i - 2]
            dollar     = lines[i - 4]
            country_en = lines[i - 8]
            if dollar != '$':
                continue
            try:
                price_usd = float(price_str)
            except ValueError:
                continue
            country_heb = BCENGI_EN_TO_HEB.get(country_en)
            if not country_heb:
                logger.debug(f"Bcengi: unmapped country '{country_en}'")
                continue
            price_ils = round(price_usd * usd_rate, 2)
            plans.append(core._make_global_plan(
                "bcengi", country_heb, price_ils, "USD", price_usd,
                data_gb=1, days=None, esim=True,
                extras=[country_heb] + BCENGI_BENEFITS,
            ))
    logger.info(f"Bcengi: {len(plans)} plans")
    return plans


def scrape_bcengi_global(_page=None, usd_rate=None):
    """Scrape Bcengi TravelPass per-country pricing (pay-per-GB eSIM).

    Each plan represents the per-GB rate for one country (data_gb=1 = price per 1 GB).
    Balance top-ups are $10/$25/$50/$100 and never expire; GB amount depends on country.
    """
    from playwright.sync_api import sync_playwright as _sp

    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    URL = "https://www.bcengi.com/travelpass/pricing"

    with _sp() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(user_agent=_UA)
        try:
            page.goto(URL, timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            body = page.inner_text("body")
        finally:
            browser.close()

    return _parse_bcengi_body(body, usd_rate)
