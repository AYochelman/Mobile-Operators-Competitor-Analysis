"""neptucom scraper (extracted from scraper.py).

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)


def scrape_neptucom(_page=None):
    """Neptucom plans (neptucom.com) — eSIM-only carrier on Partner/Pelephone infrastructure.
    Static data (site uses PDF-based pricing; last verified April 2026).
    Group A: domestic + international included.
    Group B: domestic only.
    """
    H = "\u05d7\u05d5\"\u05dc"   # חו"ל
    G5 = "\u05ea\u05d5\u05de\u05da \u05d3\u05d5\u05e8 5"  # תומך דור 5 — Wave plans run on 5G infra
    _NEPTUCOM_PDF = "https://neptucom.com/wp-content/uploads/pdfn327/{}.pdf"
    plans = [
        # ── Group A: Domestic + International included ──────────────────
        {
            "carrier": "neptucom", "plan_name": "BreezeWave", "price": 39.0,
            "data_gb": 75, "minutes": "3000",
            "extras": [
                "3,000 SMS",
                f'12GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'50 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "SwellWave", "price": 49.0,
            "data_gb": 100, "minutes": "3000",
            "extras": [
                "3,000 SMS",
                f'5GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9 (60GB \u05dc\u05e9\u05e0\u05d4)',
                f'100 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'50 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05e9\u05e0\u05d4',
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "HighWave", "price": 69.0,
            "data_gb": 100, "minutes": "3000",
            "extras": [
                "3,000 SMS",
                f'32GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'150 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'100 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'100 SMS \u05d9\u05d5\u05e6\u05d0 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                "\u05de\u05e1\u05e4\u05e8 \u05d6\u05e8 \u05e0\u05d5\u05e1\u05e3 \u05dc\u05d1\u05d7\u05d9\u05e8\u05d4",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "ReefWave", "price": 99.0,
            "data_gb": 150, "minutes": "5000",
            "extras": [
                "5,000 SMS",
                f'64GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'200 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'500 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'150 SMS \u05d9\u05d5\u05e6\u05d0 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                "\u05de\u05e1\u05e4\u05e8 \u05d6\u05e8 \u05e0\u05d5\u05e1\u05e3 \u05dc\u05d1\u05d7\u05d9\u05e8\u05d4",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "PeakWave", "price": 129.0,
            "data_gb": 200, "minutes": "5000",
            "extras": [
                "5,000 SMS",
                f'120GB \u05d2\u05dc\u05d9\u05e9\u05d4 \u05d1{H} \u05dc\u05e9\u05e0\u05d4',
                f'250 \u05d3\u05e7\u05f3 \u05e9\u05d9\u05d7\u05d4 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'1,000 \u05d3\u05e7\u05f3 \u05dc{H} \u05de\u05d9\u05e9\u05e8\u05d0\u05dc \u05dc\u05d7\u05d5\u05d3\u05e9',
                f'250 SMS \u05d9\u05d5\u05e6\u05d0 \u05d1{H} \u05dc\u05d7\u05d5\u05d3\u05e9',
                "\u05de\u05e1\u05e4\u05e8 \u05d6\u05e8 \u05e0\u05d5\u05e1\u05e3 \u05dc\u05d1\u05d7\u05d9\u05e8\u05d4",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "VoLTE \u05d5-WiFi Calling",
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 29.90 \u20aa",
                f'{H} \u05db\u05dc\u05d5\u05dc',
            ],
        },
        # ── Group B: Domestic only ──────────────────────────────────────
        {
            "carrier": "neptucom", "plan_name": "HoodWave", "price": 27.0,
            "data_gb": 25, "minutes": "1000",
            "extras": [
                G5,
                "1,000 SMS",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 19.90 \u20aa",
            ],
        },
        {
            "carrier": "neptucom", "plan_name": "LocalWave", "price": 33.0,
            "data_gb": 75, "minutes": "3000",
            "extras": [
                G5,
                "3,000 SMS",
                f'SMS \u05e0\u05db\u05e0\u05e1 \u05de{H} \u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4',
                "eSIM \u05d1\u05dc\u05d1\u05d3",
                "\u05d3\u05de\u05d9 \u05d4\u05e6\u05d8\u05e8\u05e4\u05d5\u05ea: 19.90 \u20aa",
            ],
        },
    ]
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    for p in plans:
        p.setdefault("scraped_at", ts)
        p.setdefault("url", _NEPTUCOM_PDF.format(p["plan_name"]))
    return plans
