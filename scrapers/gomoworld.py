"""gomoworld scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import re
logger = core.logger


GOMOWORLD_SLUG_TO_HEBREW = {
    # ─── Countries ───────────────────────────────────────────────────────────
    "Afghanistan":                      "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "Albania":                          "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "Algeria":                          "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "Andorra":                          "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "Angola":                           "\u05d0\u05e0\u05d2\u05d5\u05dc\u05d4",
    "Anguilla":                         "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "Antigua_and_Barbuda":              "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "Argentina":                        "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "Armenia":                          "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "Australia":                        "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "Austria":                          "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "Azerbaijan":                       "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "Bahamas":                          "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "Bahrain":                          "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "Bangladesh":                       "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "Barbados":                         "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "Belarus":                          "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "Belgium":                          "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "Belize":                           "\u05d1\u05dc\u05d9\u05d6",
    "Benin":                            "\u05d1\u05e0\u05d9\u05df",
    "Bermuda":                          "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "Bhutan":                           "\u05d1\u05d4\u05d5\u05d8\u05df",
    "Bolivia":                          "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "Bosnia_and_Herzegovina":           "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "Botswana":                         "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "Brazil":                           "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "British_Virgin_Islands":           "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "Brunei":                           "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "Bulgaria":                         "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "Burkina_Faso":                     "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "Cambodia":                         "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "Cameroon":                         "\u05e7\u05de\u05e8\u05d5\u05df",
    "Canada":                           "\u05e7\u05e0\u05d3\u05d4",
    "Cape_Verde":                       "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "Cayman_Islands":                   "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "Central_African_Republic":         "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05de\u05e8\u05db\u05d6 \u05d0\u05e4\u05e8\u05d9\u05e7\u05d0\u05d9\u05ea",
    "Chad":                             "\u05e6'\u05d0\u05d3",
    "Chile":                            "\u05e6'\u05d9\u05dc\u05d4",
    "China":                            "\u05e1\u05d9\u05df",
    "Colombia":                         "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "Comoros":                          "\u05e7\u05d5\u05de\u05d5\u05e8\u05d5",
    "Costa_Rica":                       "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "Croatia":                          "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "Cyprus":                           "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "Czech_Republic":                   "\u05e6'\u05db\u05d9\u05d4",
    "Democratic_Republic_of_the_Congo": "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Denmark":                          "\u05d3\u05e0\u05de\u05e8\u05e7",
    "Dominica":                         "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "Dominican_Republic":               "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "Ecuador":                          "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "Egypt":                            "\u05de\u05e6\u05e8\u05d9\u05dd",
    "El_Salvador":                      "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "Estonia":                          "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "Ethiopia":                         "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "Faroe_Islands":                    "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "Fiji":                             "\u05e4\u05d9\u05d2'\u05d9",
    "Finland":                          "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "France":                           "\u05e6\u05e8\u05e4\u05ea",
    "French_Polynesia":                 "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "Gabon":                            "\u05d2\u05d0\u05d1\u05d5\u05df",
    "Gambia":                           "\u05d2\u05de\u05d1\u05d9\u05d4",
    "Georgia":                          "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "Germany":                          "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "Ghana":                            "\u05d2\u05d0\u05e0\u05d4",
    "Gibraltar":                        "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "Greece":                           "\u05d9\u05d5\u05d5\u05df",
    "Greenland":                        "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "Grenada":                          "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "Guam":                             "\u05d2\u05d5\u05d0\u05dd",
    "Guatemala":                        "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "Guernsey":                         "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "Guinea":                           "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "Guinea-Bissau":                    "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "Haiti":                            "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "Honduras":                         "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "Hong_Kong":                        "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "Hungary":                          "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "Iceland":                          "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "India":                            "\u05d4\u05d5\u05d3\u05d5",
    "Indonesia":                        "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "Iraq":                             "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "Ireland":                          "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "Isle_of_Man":                      "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "Israel":                           "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "Italy":                            "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "Ivory_Coast":                      "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "Jamaica":                          "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "Japan":                            "\u05d9\u05e4\u05df",
    "Jersey":                           "\u05d2'\u05e8\u05d6\u05d9",
    "Jordan":                           "\u05d9\u05e8\u05d3\u05df",
    "Kazakhstan":                       "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "Kenya":                            "\u05e7\u05e0\u05d9\u05d4",
    "Kiribati":                         "\u05e7\u05d9\u05e8\u05d9\u05d1\u05d0\u05d8\u05d9",
    "Korea":                            "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "Kosovo":                           "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "Kuwait":                           "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "Kyrgyzstan":                       "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "Laos":                             "\u05dc\u05d0\u05d5\u05e1",
    "Latvia":                           "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "Liberia":                          "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "Libya":                            "\u05dc\u05d5\u05d1",
    "Liechtenstein":                    "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "Lithuania":                        "\u05dc\u05d9\u05d8\u05d0",
    "Luxembourg":                       "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "Macao":                            "\u05de\u05e7\u05d0\u05d5",
    "Madagascar":                       "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "Malawi":                           "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "Malaysia":                         "\u05de\u05dc\u05d6\u05d9\u05d4",
    "Maldives":                         "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "Mali":                             "\u05de\u05d0\u05dc\u05d9",
    "Malta":                            "\u05de\u05dc\u05d8\u05d4",
    "Mauritania":                       "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "Mauritius":                        "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "Mayotte":                          "\u05de\u05d0\u05d9\u05d5\u05d8",
    "Mexico":                           "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "Moldova":                          "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "Monaco":                           "\u05de\u05d5\u05e0\u05e7\u05d5",
    "Mongolia":                         "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "Montenegro":                       "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "Montserrat":                       "\u05de\u05d5\u05e0\u05d8\u05e1\u05e8\u05d0\u05d8",
    "Morocco":                          "\u05de\u05e8\u05d5\u05e7\u05d5",
    "Mozambique":                       "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "Nepal":                            "\u05e0\u05e4\u05d0\u05dc",
    "Netherlands":                      "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "New_Zealand":                      "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "Nicaragua":                        "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "Niger":                            "\u05e0\u05d9\u05d2'\u05e8",
    "Nigeria":                          "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "North_Macedonia":                  "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "Norway":                           "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "Oman":                             "\u05e2\u05d5\u05de\u05df",
    "Pakistan":                         "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "Palau":                            "\u05e4\u05d0\u05dc\u05d0\u05d5",
    "Panama":                           "\u05e4\u05e0\u05de\u05d4",
    "Papua_New_Guinea":                 "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "Paraguay":                         "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Peru":                             "\u05e4\u05e8\u05d5",
    "Philippines":                      "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "Poland":                           "\u05e4\u05d5\u05dc\u05d9\u05df",
    "Portugal":                         "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "Puerto_Rico":                      "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "Qatar":                            "\u05e7\u05d8\u05e8",
    "Republic_of_the_Congo":            "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "Reunion":                          "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "Romania":                          "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "Russia":                           "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "Rwanda":                           "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "Saint_Kitts_and_Nevis":            "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "Saint_Lucia":                      "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "Saint_Vincent_and_the_Grenadines": "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "Samoa":                            "\u05e1\u05de\u05d5\u05d0\u05d4",
    "San_Marino":                       "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "Saudi_Arabia":                     "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "Senegal":                          "\u05e1\u05e0\u05d2\u05dc",
    "Serbia":                           "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "Seychelles":                       "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "Sierra_Leone":                     "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "Singapore":                        "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "Slovakia":                         "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "Slovenia":                         "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "Solomon_Island":                   "\u05d0\u05d9\u05d9 \u05e9\u05dc\u05de\u05d4",
    "South_Africa":                     "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "South_Sudan":                      "\u05d3\u05e8\u05d5\u05dd \u05e1\u05d5\u05d3\u05df",
    "Spain":                            "\u05e1\u05e4\u05e8\u05d3",
    "Sri_Lanka":                        "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "Suriname":                         "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "Swaziland":                        "\u05d0\u05e1\u05d5\u05d0\u05d5\u05d8\u05d9\u05e0\u05d9",
    "Sweden":                           "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "Switzerland":                      "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "Taiwan":                           "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "Tajikistan":                       "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "Tanzania":                         "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "Thailand":                         "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "Timor-Leste":                      "\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4",
    "Togo":                             "\u05d8\u05d5\u05d2\u05d5",
    "Tonga":                            "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "Trinidad_and_Tobago":              "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "Tunisia":                          "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "Turkey":                           "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "Turks_and_Caicos_Islands":         "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "Uganda":                           "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "Ukraine":                          "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "United_Arab_Emirates":             "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "United_Kingdom":                   "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "United_States":                    "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "Uruguay":                          "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "Uzbekistan":                       "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "Vanuatu":                          "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "Venezuela":                        "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "Viet_Nam":                         "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "Yemen":                            "\u05ea\u05d9\u05de\u05df",
    "Zambia":                           "\u05d6\u05de\u05d1\u05d9\u05d4",
    # ─── Zones / Regions ─────────────────────────────────────────────────────
    "Channel_Islands":                  "\u05d0\u05d9\u05d9 \u05d4\u05ea\u05e2\u05dc\u05d4",
    "Europe":                           "\u05d0\u05d9\u05e8\u05d5\u05e4\u05d4",
    "French_Antilles":                  "\u05d4\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05d9\u05dd",
    "Latin_America":                    "\u05d0\u05de\u05e8\u05d9\u05e7\u05d4 \u05d4\u05dc\u05d8\u05d9\u05e0\u05d9\u05ea",
    "Netherlands_Antilles":             "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "North_America":                    "\u05e6\u05e4\u05d5\u05df \u05d0\u05de\u05e8\u05d9\u05e7\u05d4",
    "South_East_Asia":                  "\u05d3\u05e8\u05d5\u05dd \u05de\u05d6\u05e8\u05d7 \u05d0\u05e1\u05d9\u05d4",
}


_GOMO_SYMBOL_CCY = {"\u20aa": "ILS", "\u00a3": "GBP", "$": "USD", "\u20ac": "EUR"}


def _parse_gomoworld_plans(body, country_heb, gbp_rate, usd_rate=None, eur_rate=None):
    """Parse plan blocks from a GoMoWorld destination page body text.

    Currency-aware (2026-09-03): the site geo-prices per visitor and flips the
    quoted currency between GBP / USD / ILS from run to run (cookie
    `gmw_currency`), while this parser used to treat every number as GBP -
    8,600 phantom price_change rows (x1.26 / x3.7 swings) since 2026-07-10.
    `scrape_gomoworld_global` now pins the cookie to ILS, and the symbol in the
    price line decides the conversion here as a safety net: ILS is stored as-is
    (they are fixed x.99 price points, not FX-converted), other symbols are
    converted with the matching rate and logged.
    """
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    # Find start after "Compatible smartphones"
    start = -1
    for i, l in enumerate(lines):
        if l == 'Compatible smartphones':
            start = i + 1
            break
    if start == -1:
        return []
    # Find end
    end = len(lines)
    for i, l in enumerate(lines[start:], start):
        if 'face issues' in l or 'unable to activate' in l or 'encounter issues' in l or 'Confirm,' in l:
            end = i
            break
    plan_lines = lines[start:end]
    plans = []
    warned = set()
    i = 0
    while i < len(plan_lines):
        line = plan_lines[i]
        # GB line: e.g. "35GB" or "90GB75GB" (PROMO = concatenated)
        m_gb = re.match(r'^(\d+(?:\.\d+)?)GB', line)
        if m_gb and i + 2 < len(plan_lines):
            gb = float(m_gb.group(1))
            # Next line: "X-day plan"
            m_day = re.match(r'^(\d+)-day plan$', plan_lines[i + 1])
            if m_day:
                days = int(m_day.group(1))
                # Next line: price with currency symbol + number, e.g. "₪109.99" / "£29.99"
                price_line = plan_lines[i + 2]
                m_price = re.search(r'([\u20aa\u00a3$\u20ac])\s*(\d+(?:\.\d+)?)', price_line)
                if m_price:
                    sym, price_orig = m_price.group(1), float(m_price.group(2))
                    ccy = _GOMO_SYMBOL_CCY[sym]
                    if ccy == "ILS":
                        price_ils = round(price_orig, 2)
                    else:
                        if ccy not in warned:
                            warned.add(ccy)
                            logger.warning(f"GoMoWorld {country_heb}: page quoted {ccy}, not ILS - converting")
                        if ccy == "GBP":
                            rate = gbp_rate
                        elif ccy == "USD":
                            rate = usd_rate or core._get_usd_to_ils()
                        else:
                            rate = eur_rate or core._get_eur_to_ils()
                        price_ils = round(price_orig * rate, 2)
                    gb_str = f"{int(gb)}GB" if gb == int(gb) else f"{gb}GB"
                    plan_name = f"{country_heb} \u2013 {gb_str} \u2013 {days} \u05d9\u05de\u05d9\u05dd"
                    plans.append(core._make_global_plan(
                        "gomoworld", plan_name, price_ils, ccy, price_orig,
                        data_gb=gb, days=days, esim=True, extras=[country_heb]
                    ))
                    i += 3
                    continue
        i += 1
    return plans


def scrape_gomoworld_global(_page=None, gbp_rate=None):
    """Scrape GoMoWorld eSIM per-country and regional plans.

    Prices are read in ILS: the `gmw_currency` cookie is pinned to ILS on the
    browser context so the quoted currency no longer depends on geo-detection
    (see `_parse_gomoworld_plans`). `gbp_rate` is only used as the fallback
    conversion if a page still comes back in GBP.
    """
    if gbp_rate is None:
        gbp_rate = core._get_gbp_to_ils()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    all_plans = []
    success_count = 0
    with core.sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(user_agent=ua)
        context.add_cookies([{
            "name": "gmw_currency", "value": "ILS",
            "domain": ".gomoworld.com", "path": "/",
        }])
        page = context.new_page()
        for slug, country_heb in GOMOWORLD_SLUG_TO_HEBREW.items():
            try:
                page.goto(
                    f"https://www.gomoworld.com/en/destinations/{slug}",
                    timeout=25000, wait_until="domcontentloaded"
                )
                page.wait_for_timeout(1500)
                body = page.inner_text("body")
                plans = _parse_gomoworld_plans(body, country_heb, gbp_rate)
                if plans:
                    all_plans.extend(plans)
                    success_count += 1
                else:
                    logger.warning(f"GoMoWorld {slug}: no plans parsed")
            except Exception as exc:
                logger.warning(f"GoMoWorld {slug}: {exc}")
                continue
        browser.close()
    logger.info(f"GoMoWorld: {len(all_plans)} plans from {success_count}/{len(GOMOWORLD_SLUG_TO_HEBREW)} destinations")
    return all_plans
