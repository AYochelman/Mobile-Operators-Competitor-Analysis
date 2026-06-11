"""Seed/upsert MOCA Guest Connect hotel portals.

Idempotent — re-run anytime to refresh the demo + prospect portals. Each row
drives a public branded guest portal at /guest/<slug>.

  python seed_hotels.py
"""
import db

HOTELS = [
    # ── Live prospect (colors sampled from brownhotels.co.il) ──────────────
    {
        "slug": "brown", "name": "Brown Hotels",
        "brand_primary": "#26170f", "brand_secondary": "#d16938", "brand_bg": "#f4f1ee",
        "mono": "B", "languages": ["en", "he", "fr", "ru"], "default_lang": "en",
        "commission_note": "50/50", "active": True,
    },
    # ── White-label demo brands (used by the /hotels landing switcher) ─────
    {
        "slug": "demo", "name": "Coastline Hotels",
        "brand_primary": "#26170f", "brand_secondary": "#d16938", "brand_bg": "#f4f1ee",
        "mono": "CH", "languages": ["en", "he", "fr", "ru"], "default_lang": "en",
        "commission_note": "50/50", "active": True,
    },
    {
        "slug": "demo-navy", "name": "Harbor & Pearl",
        "brand_primary": "#0e2a47", "brand_secondary": "#c8a24b", "brand_bg": "#f4f7fb",
        "mono": "HP", "languages": ["en", "he", "fr", "ru"], "default_lang": "en",
        "commission_note": "50/50", "active": True,
    },
    {
        "slug": "demo-verde", "name": "Galil Verde Collection",
        "brand_primary": "#1d4d3b", "brand_secondary": "#9ec27a", "brand_bg": "#f3f8f4",
        "mono": "GV", "languages": ["en", "he", "fr", "ru"], "default_lang": "en",
        "commission_note": "50/50", "active": True,
    },
    {
        "slug": "demo-urban", "name": "TLV Urban Hotels",
        "brand_primary": "#17171c", "brand_secondary": "#d9c8ae", "brand_bg": "#f7f7f8",
        "mono": "TLV", "languages": ["en", "he", "fr", "ru"], "default_lang": "en",
        "commission_note": "50/50", "active": True,
    },
]


def main():
    db.init_db()
    for h in HOTELS:
        row = db.upsert_hotel(h)
        print(f"  [ok] {row['slug']:<12} {row['name']}")
    print(f"Seeded {len(HOTELS)} guest portals.")


if __name__ == "__main__":
    main()
