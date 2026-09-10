"""maya scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import json as _json
import urllib.request
logger = core.logger


MAYA_SLUG_TO_HEBREW = {
    # Global & regions
    "global":                       "\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9",
    "oceania":                      "\u05d0\u05d5\u05e7\u05d9\u05d0\u05e0\u05d9\u05d4",
    # Countries (A-Z)
    "afghanistan":                  "\u05d0\u05e4\u05d2\u05e0\u05d9\u05e1\u05d8\u05df",
    "albania":                      "\u05d0\u05dc\u05d1\u05e0\u05d9\u05d4",
    "algeria":                      "\u05d0\u05dc\u05d2'\u05d9\u05e8\u05d9\u05d4",
    "andorra":                      "\u05d0\u05e0\u05d3\u05d5\u05e8\u05d4",
    "anguilla":                     "\u05d0\u05e0\u05d2\u05d5\u05d5\u05d9\u05dc\u05d4",
    "antigua-barbuda":              "\u05d0\u05e0\u05d8\u05d9\u05d2\u05d5\u05d0\u05d4 \u05d5\u05d1\u05e8\u05d1\u05d5\u05d3\u05d4",
    "argentina":                    "\u05d0\u05e8\u05d2\u05e0\u05d8\u05d9\u05e0\u05d4",
    "armenia":                      "\u05d0\u05e8\u05de\u05e0\u05d9\u05d4",
    "aruba":                        "\u05d0\u05e8\u05d5\u05d1\u05d4",
    "australia":                    "\u05d0\u05d5\u05e1\u05d8\u05e8\u05dc\u05d9\u05d4",
    "austria":                      "\u05d0\u05d5\u05e1\u05d8\u05e8\u05d9\u05d4",
    "azerbaijan":                   "\u05d0\u05d6\u05e8\u05d1\u05d9\u05d9\u05d2'\u05df",
    "bahamas":                      "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05d4\u05d0\u05de\u05d4",
    "bahrain":                      "\u05d1\u05d7\u05e8\u05d9\u05d9\u05df",
    "bangladesh":                   "\u05d1\u05e0\u05d2\u05dc\u05d3\u05e9",
    "barbados":                     "\u05d1\u05e8\u05d1\u05d3\u05d5\u05e1",
    "belarus":                      "\u05d1\u05dc\u05d0\u05e8\u05d5\u05e1",
    "belgium":                      "\u05d1\u05dc\u05d2\u05d9\u05d4",
    "belize":                       "\u05d1\u05dc\u05d9\u05d6",
    "benin":                        "\u05d1\u05e0\u05d9\u05df",
    "bermuda":                      "\u05d1\u05e8\u05de\u05d5\u05d3\u05d4",
    "bhutan":                       "\u05d1\u05d4\u05d5\u05d8\u05df",
    "bolivia":                      "\u05d1\u05d5\u05dc\u05d9\u05d1\u05d9\u05d4",
    "bonaire-saba-eustatius":       "\u05d1\u05d5\u05e0\u05d9\u05d9\u05e8",
    "bosnia-herzegovina":           "\u05d1\u05d5\u05e1\u05e0\u05d9\u05d4 \u05d5\u05d4\u05e8\u05e6\u05d2\u05d5\u05d1\u05d9\u05e0\u05d4",
    "botswana":                     "\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4",
    "brazil":                       "\u05d1\u05e8\u05d6\u05d9\u05dc",
    "british-virgin-islands":       "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 (\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4)",
    "brunei":                       "\u05d1\u05e8\u05d5\u05e0\u05d9\u05d9",
    "bulgaria":                     "\u05d1\u05d5\u05dc\u05d2\u05e8\u05d9\u05d4",
    "burkina-faso":                 "\u05d1\u05d5\u05e8\u05e7\u05d9\u05e0\u05d4 \u05e4\u05d0\u05e1\u05d5",
    "burundi":                      "\u05d1\u05d5\u05e8\u05d5\u05e0\u05d3\u05d9",
    "cambodia":                     "\u05e7\u05de\u05d1\u05d5\u05d3\u05d9\u05d4",
    "cameroon":                     "\u05e7\u05de\u05e8\u05d5\u05df",
    "canada":                       "\u05e7\u05e0\u05d3\u05d4",
    "cape-verde":                   "\u05e7\u05d9\u05d9\u05e4 \u05d5\u05e8\u05d3\u05d4",
    "cayman-islands":               "\u05d0\u05d9\u05d9 \u05e7\u05d9\u05d9\u05de\u05df",
    "chad":                         "\u05e6'\u05d0\u05d3",
    "chile":                        "\u05e6'\u05d9\u05dc\u05d4",
    "china":                        "\u05e1\u05d9\u05df",
    "colombia":                     "\u05e7\u05d5\u05dc\u05d5\u05de\u05d1\u05d9\u05d4",
    "congo-drc":                    "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05de\u05d5\u05e7\u05e8\u05d8\u05d9\u05ea \u05e9\u05dc \u05e7\u05d5\u05e0\u05d2\u05d5",
    "costa-rica":                   "\u05e7\u05d5\u05e1\u05d8\u05d4 \u05e8\u05d9\u05e7\u05d4",
    "croatia":                      "\u05e7\u05e8\u05d5\u05d0\u05d8\u05d9\u05d4",
    "curacao":                      "\u05e7\u05d5\u05e8\u05d0\u05e1\u05d0\u05d5",
    "cyprus":                       "\u05e7\u05e4\u05e8\u05d9\u05e1\u05d9\u05df",
    "czech-republic":               "\u05e6'\u05db\u05d9\u05d4",
    "denmark":                      "\u05d3\u05e0\u05de\u05e8\u05e7",
    "dominica":                     "\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05d4",
    "dominican-republic":           "\u05d4\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05d4 \u05d4\u05d3\u05d5\u05de\u05d9\u05e0\u05d9\u05e7\u05e0\u05d9\u05ea",
    "ecuador":                      "\u05d0\u05e7\u05d5\u05d5\u05d3\u05d5\u05e8",
    "egypt":                        "\u05de\u05e6\u05e8\u05d9\u05dd",
    "el-salvador":                  "\u05d0\u05dc \u05e1\u05dc\u05d1\u05d3\u05d5\u05e8",
    "estonia":                      "\u05d0\u05e1\u05d8\u05d5\u05e0\u05d9\u05d4",
    "ethiopia":                     "\u05d0\u05ea\u05d9\u05d5\u05e4\u05d9\u05d4",
    "falkland-islands":             "\u05d0\u05d9\u05d9 \u05e4\u05d5\u05e7\u05dc\u05e0\u05d3",
    "faroe-islands":                "\u05d0\u05d9\u05d9 \u05e4\u05d0\u05e8\u05d5",
    "fiji":                         "\u05e4\u05d9\u05d2'\u05d9",
    "finland":                      "\u05e4\u05d9\u05e0\u05dc\u05e0\u05d3",
    "france":                       "\u05e6\u05e8\u05e4\u05ea",
    "french-guiana":                "\u05d2\u05d9\u05d0\u05e0\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "french-polynesia":             "\u05e4\u05d5\u05dc\u05d9\u05e0\u05d6\u05d9\u05d4 \u05d4\u05e6\u05e8\u05e4\u05ea\u05d9\u05ea",
    "gabon":                        "\u05d2\u05d0\u05d1\u05d5\u05df",
    "gambia":                       "\u05d2\u05de\u05d1\u05d9\u05d4",
    "georgia":                      "\u05d2\u05d0\u05d5\u05e8\u05d2\u05d9\u05d4",
    "germany":                      "\u05d2\u05e8\u05de\u05e0\u05d9\u05d4",
    "ghana":                        "\u05d2\u05d0\u05e0\u05d4",
    "gibraltar":                    "\u05d2\u05d9\u05d1\u05e8\u05dc\u05d8\u05e8",
    "greece":                       "\u05d9\u05d5\u05d5\u05df",
    "greenland":                    "\u05d2\u05e8\u05d9\u05e0\u05dc\u05e0\u05d3",
    "grenada":                      "\u05d2\u05e8\u05e0\u05d3\u05d4",
    "guadeloupe":                   "\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4",
    "guam":                         "\u05d2\u05d5\u05d0\u05dd",
    "guatemala":                    "\u05d2\u05d5\u05d0\u05d8\u05de\u05dc\u05d4",
    "guernsey":                     "\u05d2\u05e8\u05e0\u05d6\u05d9",
    "guinea":                       "\u05d2\u05d9\u05e0\u05d0\u05d4",
    "guinea-bissau":                "\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5",
    "guyana":                       "\u05d2\u05d9\u05d0\u05e0\u05d4",
    "haiti":                        "\u05d4\u05d0\u05d9\u05d8\u05d9",
    "honduras":                     "\u05d4\u05d5\u05e0\u05d3\u05d5\u05e8\u05e1",
    "hong-kong":                    "\u05d4\u05d5\u05e0\u05d2 \u05e7\u05d5\u05e0\u05d2",
    "hungary":                      "\u05d4\u05d5\u05e0\u05d2\u05e8\u05d9\u05d4",
    "iceland":                      "\u05d0\u05d9\u05e1\u05dc\u05e0\u05d3",
    "india":                        "\u05d4\u05d5\u05d3\u05d5",
    "indonesia":                    "\u05d0\u05d9\u05e0\u05d3\u05d5\u05e0\u05d6\u05d9\u05d4",
    "iraq":                         "\u05e2\u05d9\u05e8\u05d0\u05e7",
    "ireland":                      "\u05d0\u05d9\u05e8\u05dc\u05e0\u05d3",
    "isle-of-man":                  "\u05d4\u05d0\u05d9 \u05de\u05d0\u05df",
    "israel":                       "\u05d9\u05e9\u05e8\u05d0\u05dc",
    "italy":                        "\u05d0\u05d9\u05d8\u05dc\u05d9\u05d4",
    "ivory-coast":                  "\u05d7\u05d5\u05e3 \u05d4\u05e9\u05e0\u05d4\u05d1",
    "jamaica":                      "\u05d2'\u05de\u05d9\u05d9\u05e7\u05d4",
    "japan":                        "\u05d9\u05e4\u05df",
    "jersey":                       "\u05d2'\u05e8\u05d6\u05d9",
    "jordan":                       "\u05d9\u05e8\u05d3\u05df",
    "kazakhstan":                   "\u05e7\u05d6\u05d7\u05e1\u05d8\u05df",
    "kenya":                        "\u05e7\u05e0\u05d9\u05d4",
    "kosovo":                       "\u05e7\u05d5\u05e1\u05d5\u05d1\u05d5",
    "kuwait":                       "\u05db\u05d5\u05d5\u05d9\u05d9\u05ea",
    "kyrgyzstan":                   "\u05e7\u05d9\u05e8\u05d2\u05d9\u05d6\u05e1\u05d8\u05df",
    "laos":                         "\u05dc\u05d0\u05d5\u05e1",
    "latvia":                       "\u05dc\u05d8\u05d1\u05d9\u05d4",
    "liberia":                      "\u05dc\u05d9\u05d1\u05e8\u05d9\u05d4",
    "liechtenstein":                "\u05dc\u05d9\u05db\u05d8\u05e0\u05e9\u05d8\u05d9\u05d9\u05df",
    "lithuania":                    "\u05dc\u05d9\u05d8\u05d0",
    "luxembourg":                   "\u05dc\u05d5\u05e7\u05e1\u05de\u05d1\u05d5\u05e8\u05d2",
    "macau":                        "\u05de\u05e7\u05d0\u05d5",
    "macedonia":                    "\u05de\u05e7\u05d3\u05d5\u05e0\u05d9\u05d4 \u05d4\u05e6\u05e4\u05d5\u05e0\u05d9\u05ea",
    "madagascar":                   "\u05de\u05d3\u05d2\u05e1\u05e7\u05e8",
    "malawi":                       "\u05de\u05dc\u05d0\u05d5\u05d5\u05d9",
    "malaysia":                     "\u05de\u05dc\u05d6\u05d9\u05d4",
    "maldives":                     "\u05d4\u05d0\u05d9\u05d9\u05dd \u05d4\u05de\u05dc\u05d3\u05d9\u05d1\u05d9\u05d9\u05dd",
    "mali":                         "\u05de\u05d0\u05dc\u05d9",
    "malta":                        "\u05de\u05dc\u05d8\u05d4",
    "martinique":                   "\u05de\u05e8\u05d8\u05d9\u05e0\u05d9\u05e7",
    "mauritania":                   "\u05de\u05d0\u05d5\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "mauritius":                    "\u05de\u05d0\u05d5\u05e8\u05d9\u05e6\u05d9\u05d5\u05e1",
    "mayotte":                      "\u05de\u05d0\u05d9\u05d5\u05d8",
    "mexico":                       "\u05de\u05e7\u05e1\u05d9\u05e7\u05d5",
    "moldova":                      "\u05de\u05d5\u05dc\u05d3\u05d5\u05d1\u05d4",
    "monaco":                       "\u05de\u05d5\u05e0\u05e7\u05d5",
    "mongolia":                     "\u05de\u05d5\u05e0\u05d2\u05d5\u05dc\u05d9\u05d4",
    "montenegro":                   "\u05de\u05d5\u05e0\u05d8\u05e0\u05d2\u05e8\u05d5",
    "montserrat":                   "\u05de\u05d5\u05e0\u05e1\u05e8\u05d0\u05d8",
    "morocco":                      "\u05de\u05e8\u05d5\u05e7\u05d5",
    "mozambique":                   "\u05de\u05d5\u05d6\u05de\u05d1\u05d9\u05e7",
    "namibia":                      "\u05e0\u05de\u05d9\u05d1\u05d9\u05d4",
    "nauru":                        "\u05e0\u05d0\u05d5\u05e8\u05d5",
    "nepal":                        "\u05e0\u05e4\u05d0\u05dc",
    "netherlands":                  "\u05d4\u05d5\u05dc\u05e0\u05d3",
    "netherlands-antilles":         "\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd",
    "new-zealand":                  "\u05e0\u05d9\u05d5 \u05d6\u05d9\u05dc\u05e0\u05d3",
    "nicaragua":                    "\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4",
    "niger":                        "\u05e0\u05d9\u05d2'\u05e8",
    "nigeria":                      "\u05e0\u05d9\u05d2\u05e8\u05d9\u05d4",
    "norway":                       "\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4",
    "oman":                         "\u05e2\u05d5\u05de\u05df",
    "pakistan":                     "\u05e4\u05e7\u05d9\u05e1\u05d8\u05df",
    "palau":                        "\u05e4\u05d0\u05dc\u05d0\u05d5",
    "panama":                       "\u05e4\u05e0\u05de\u05d4",
    "papua-new-guinea":             "\u05e4\u05e4\u05d5\u05d0\u05d4 \u05d2\u05d9\u05e0\u05d0\u05d4 \u05d4\u05d7\u05d3\u05e9\u05d4",
    "paraguay":                     "\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9",
    "peru":                         "\u05e4\u05e8\u05d5",
    "philippines":                  "\u05d4\u05e4\u05d9\u05dc\u05d9\u05e4\u05d9\u05e0\u05d9\u05dd",
    "poland":                       "\u05e4\u05d5\u05dc\u05d9\u05df",
    "portugal":                     "\u05e4\u05d5\u05e8\u05d8\u05d5\u05d2\u05dc",
    "puerto-rico":                  "\u05e4\u05d5\u05d0\u05e8\u05d8\u05d5 \u05e8\u05d9\u05e7\u05d5",
    "qatar":                        "\u05e7\u05d8\u05e8",
    "republic-congo":               "\u05e8\u05e4\u05d5\u05d1\u05dc\u05d9\u05e7\u05ea \u05e7\u05d5\u05e0\u05d2\u05d5",
    "reunion":                      "\u05e8\u05d0\u05d5\u05e0\u05d9\u05d5\u05df",
    "romania":                      "\u05e8\u05d5\u05de\u05e0\u05d9\u05d4",
    "russia":                       "\u05e8\u05d5\u05e1\u05d9\u05d4",
    "rwanda":                       "\u05e8\u05d5\u05d0\u05e0\u05d3\u05d4",
    "saint-barthelemy":             "\u05e1\u05df \u05d1\u05e8\u05ea\u05dc\u05de\u05d9",
    "saint-kitts-nevis":            "\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1",
    "saint-lucia":                  "\u05e1\u05e0\u05d8 \u05dc\u05d5\u05e1\u05d9\u05d4",
    "saint-martin":                 "\u05e1\u05e0\u05d8 \u05de\u05e8\u05d8\u05df",
    "saint-pierre-miquelon":        "\u05e1\u05df \u05e4\u05d9\u05d9\u05e8 \u05d5\u05de\u05d9\u05e7\u05dc\u05d5\u05df",
    "saint-vincent-grenadines":     "\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd",
    "saipan":                       "\u05e1\u05d9\u05d9\u05e4\u05df",
    "samoa":                        "\u05e1\u05de\u05d5\u05d0\u05d4",
    "san-marino":                   "\u05e1\u05df \u05de\u05e8\u05d9\u05e0\u05d5",
    "saudi-arabia":                 "\u05e2\u05e8\u05d1 \u05d4\u05e1\u05e2\u05d5\u05d3\u05d9\u05ea",
    "senegal":                      "\u05e1\u05e0\u05d2\u05dc",
    "serbia":                       "\u05e1\u05e8\u05d1\u05d9\u05d4",
    "seychelles":                   "\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc",
    "sierra-leone":                 "\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4",
    "singapore":                    "\u05e1\u05d9\u05e0\u05d2\u05e4\u05d5\u05e8",
    "sint-maarten":                 "\u05e1\u05d9\u05e0\u05d8 \u05de\u05d0\u05e8\u05d8\u05df",
    "slovakia":                     "\u05e1\u05dc\u05d5\u05d1\u05e7\u05d9\u05d4",
    "slovenia":                     "\u05e1\u05dc\u05d5\u05d1\u05e0\u05d9\u05d4",
    "south-africa":                 "\u05d3\u05e8\u05d5\u05dd \u05d0\u05e4\u05e8\u05d9\u05e7\u05d4",
    "south-korea":                  "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4",
    "spain":                        "\u05e1\u05e4\u05e8\u05d3",
    "sri-lanka":                    "\u05e1\u05e8\u05d9 \u05dc\u05e0\u05e7\u05d4",
    "sudan":                        "\u05e1\u05d5\u05d3\u05df",
    "suriname":                     "\u05e1\u05d5\u05e8\u05d9\u05e0\u05d0\u05dd",
    "swaziland":                    "\u05d0\u05e1\u05d5\u05d0\u05d5\u05d8\u05d9\u05e0\u05d9",
    "sweden":                       "\u05e9\u05d1\u05d3\u05d9\u05d4",
    "switzerland":                  "\u05e9\u05d5\u05d5\u05d9\u05e5",
    "taiwan":                       "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df",
    "tajikstan":                    "\u05d8\u05d2'\u05d9\u05e7\u05d9\u05e1\u05d8\u05df",
    "tanzania":                     "\u05d8\u05e0\u05d6\u05e0\u05d9\u05d4",
    "thailand":                     "\u05ea\u05d0\u05d9\u05dc\u05e0\u05d3",
    "timor-leste":                  "\u05d8\u05d9\u05de\u05d5\u05e8 \u05dc\u05e1\u05d8\u05d4",
    "togo":                         "\u05d8\u05d5\u05d2\u05d5",
    "tonga":                        "\u05d8\u05d5\u05e0\u05d2\u05d4",
    "trinidad-tobago":              "\u05d8\u05e8\u05d9\u05e0\u05d9\u05d3\u05d3 \u05d5\u05d8\u05d5\u05d1\u05d2\u05d5",
    "tunisia":                      "\u05ea\u05d5\u05e0\u05d9\u05e1\u05d9\u05d4",
    "turkey":                       "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4",
    "turks-caicos":                 "\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1",
    "uae":                          "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea",
    "uganda":                       "\u05d0\u05d5\u05d2\u05e0\u05d3\u05d4",
    "uk":                           "\u05d1\u05e8\u05d9\u05d8\u05e0\u05d9\u05d4",
    "ukraine":                      "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4",
    "uruguay":                      "\u05d0\u05d5\u05e8\u05d5\u05d2\u05d5\u05d5\u05d0\u05d9",
    "usa":                          "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea",
    "us-virgin-islands":            "\u05d0\u05d9\u05d9 \u05d4\u05d1\u05ea\u05d5\u05dc\u05d4 \u05d4\u05d0\u05de\u05e8\u05d9\u05e7\u05e0\u05d9\u05d9\u05dd",
    "uzbekistan":                   "\u05d0\u05d5\u05d6\u05d1\u05e7\u05d9\u05e1\u05d8\u05df",
    "vanuatu":                      "\u05d5\u05e0\u05d5\u05d0\u05d8\u05d5",
    "venezuela":                    "\u05d5\u05e0\u05e6\u05d5\u05d0\u05dc\u05d4",
    "vietnam":                      "\u05d5\u05d9\u05d9\u05d8\u05e0\u05d0\u05dd",
    "zambia":                       "\u05d6\u05de\u05d1\u05d9\u05d4",
}


def scrape_maya_global(_page=None, usd_rate=None):
    """Fetch Maya Mobile's current eSIM catalog from the official affiliate feed.

    SOURCE CHANGE (2026-06): switched from scraping the Angular-SSR `maya-mobile-state`
    blob to Maya's official partner feed at
        https://assets.maya.net/affiliates/plans.json
    (shared by their partnerships team; auth-free, stable JSON). The old scrape parsed
    `CACHE_CONTENT_STATE_KEY.cache.globalRegions/cruiseRegions` out of the page HTML --
    that markup died twice in the 2026 redesigns, so the official feed is far more robust.

    The feed lists the same 8 unlimited tiers: 4 "global" (regionType=global) + 4
    "global + cruise" (regionType=cruise / supportedCruises set), at 3/7/14/30 days. We
    shape it into the globalRegions / cruiseRegions buckets the rest of this function
    already expects, so plan naming + dedup (and the stored plan_name keys) are unchanged.

    Plans are unlimited (daily FUP) -> data_gb=None. extras[0] = global / global+cruise
    (Hebrew); the plain "global" name maps to MAYA_GLOBAL in getPlanCoverage. Price uses
    priceDiscounted.USD (falls back to priceOriginal). The current catalog is exactly the
    8 rows already stored, so no stale-row purge is needed.
    """
    if usd_rate is None:
        usd_rate = core._get_usd_to_ils()

    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Official affiliate data feed (shared by Maya's partnerships team 2026-06). Replaces
    # the brittle Angular-SSR `maya-mobile-state` scrape that died twice in the 2026 site
    # redesigns. Auth-free JSON of the same 8 unlimited tiers (4 global + 4 global+cruise).
    API_URL = "https://assets.maya.net/affiliates/plans.json"
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            payload = _json.loads(r.read().decode("utf-8", errors="replace"))
        api_plans = payload.get("plans") or []
    except Exception as exc:
        logger.warning(f"Maya Mobile API: {exc} -- skipping")
        return []
    if not api_plans:
        logger.warning("Maya Mobile API: no plans returned -- skipping")
        return []

    def _adapt(p):
        # Map the affiliate-feed shape onto the legacy region-plan shape _ingest expects,
        # so the naming / dedup logic below (and the stored plan_name keys) stay unchanged.
        return {
            "validity": p.get("validityInDays"),
            "priceBundle": p.get("priceDiscounted") or p.get("priceOriginal") or {},
            "dataUsageAllowanceType": p.get("dataUsageAllowanceType"),
            "dataUsageAllowanceInGb": p.get("dataUsageAllowanceInGb"),
            "fupDescription": p.get("fupDescription"),
            "isActive": True,
        }

    def _is_cruise(p):
        return (p.get("regionType") == "cruise") or bool(p.get("supportedCruises"))

    # Shape into the buckets _ingest already consumes.
    cache = {
        "globalRegions": [{"plans": [_adapt(p) for p in api_plans if not _is_cruise(p)]}],
        "cruiseRegions": [{"plans": [_adapt(p) for p in api_plans if _is_cruise(p)]}],
    }

    GLOBAL_HEB = "גלובלי"
    CRUISE_HEB = "גלובלי ושייט"

    by_name = {}

    def _ingest(regions, dest_heb):
        for region in regions or []:
            for p in region.get("plans") or []:
                try:
                    days = int(p.get("validity"))
                    price_usd = float((p.get("priceBundle") or {}).get("USD") or 0)
                except (TypeError, ValueError):
                    continue
                if days <= 0 or price_usd <= 0 or not p.get("isActive", True):
                    continue
                # All current Maya plans are unlimited (daily FUP) -> data_gb=None.
                unlimited = (p.get("dataUsageAllowanceType") or "").upper() == "UNLIMITED"
                data_gb = None if unlimited else (p.get("dataUsageAllowanceInGb") or None)
                if data_gb is None:
                    label = "ללא הגבלה"
                else:
                    label = f"{int(data_gb)}GB" if data_gb == int(data_gb) else f"{data_gb}GB"
                plan_name = (
                    f"{dest_heb} – {label} – {days} ימים"
                )
                extras = [dest_heb]
                fup = (p.get("fupDescription") or "").strip()
                if fup:
                    extras.append(fup)
                # Dedup: Maya lists each tier twice (two slugs); keep the cheapest.
                prev = by_name.get(plan_name)
                if prev and prev.get("original_price", 1e9) <= price_usd:
                    continue
                by_name[plan_name] = core._make_global_plan(
                    "maya", plan_name, round(price_usd * usd_rate, 2), "USD",
                    price_usd, data_gb=data_gb, days=days, esim=True, extras=extras,
                )

    _ingest(cache.get("globalRegions"), GLOBAL_HEB)
    _ingest(cache.get("cruiseRegions"), CRUISE_HEB)

    all_plans = list(by_name.values())
    logger.info(
        f"Maya Mobile: {len(all_plans)} plans "
        f"(global + cruise unlimited; per-country catalog retired)"
    )
    return all_plans
