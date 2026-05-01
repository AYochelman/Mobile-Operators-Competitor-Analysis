"""
archive.py — snapshot-based archival of plans and banners.

Called after each scrape run.  Only writes a new row when the content
actually changed (content-hash comparison), so storage stays small.
"""

import hashlib
import json
import os
import shutil
from datetime import date

import db

ARCHIVE_BANNER_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "archive", "banners"
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Plans ──────────────────────────────────────────────────────────────────────

def save_plan_snapshot(carrier: str, plan_type: str, plans: list):
    """
    Persist a daily snapshot of *plans* for (carrier, plan_type).
    Always saves once per day — skips only if a snapshot for today already exists.

    plan_type: 'domestic' | 'abroad' | 'global' | 'content'
    """
    if not plans:
        return

    today = date.today().isoformat()

    if db.has_archive_snapshot_today(carrier, plan_type, today):
        return  # already saved today

    # Apply destination-name normalization to extras[0] so archive snapshots
    # match the canonical names shown in the dashboard (db.save_*_plans does
    # this on write — archive must mirror, otherwise the History tab shows
    # "שוודיה" while the live tab shows "שבדיה").
    normalized = []
    for p in plans:
        np = dict(p)
        if isinstance(np.get("extras"), list):
            np["extras"] = db._norm_extras(np["extras"])
        normalized.append(np)

    plans_json = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    new_hash = _sha256(plans_json)
    db.insert_archive_snapshot(carrier, plan_type, today, plans_json, new_hash)


def archive_domestic_plans(all_plans: list):
    """Group a flat list of domestic plans by carrier and snapshot each."""
    by_carrier: dict[str, list] = {}
    for p in all_plans:
        by_carrier.setdefault(p["carrier"], []).append(p)
    for carrier, plans in by_carrier.items():
        save_plan_snapshot(carrier, "domestic", plans)


def archive_abroad_plans(all_plans: list):
    by_carrier: dict[str, list] = {}
    for p in all_plans:
        by_carrier.setdefault(p["carrier"], []).append(p)
    for carrier, plans in by_carrier.items():
        save_plan_snapshot(carrier, "abroad", plans)


def archive_global_plans(all_plans: list):
    by_carrier: dict[str, list] = {}
    for p in all_plans:
        by_carrier.setdefault(p["carrier"], []).append(p)
    for carrier, plans in by_carrier.items():
        save_plan_snapshot(carrier, "global", plans)


def archive_content_plans(all_plans: list):
    """Content plans are stored as a single group per carrier."""
    by_carrier: dict[str, list] = {}
    for p in all_plans:
        by_carrier.setdefault(p["carrier"], []).append(p)
    for carrier, plans in by_carrier.items():
        save_plan_snapshot(carrier, "content", plans)


# ── Banners ────────────────────────────────────────────────────────────────────

def save_banner_snapshot(carrier: str, src_path: str, is_store: bool = False):
    """
    Copy *src_path* to the archive folder only if the image has changed.
    The destination path encodes today's date so each unique image is kept.
    """
    if not os.path.isfile(src_path):
        return

    # Skip suspiciously small files — WAF-blocked or blank screenshot
    if os.path.getsize(src_path) < 10_000:
        return

    new_hash = _sha256_file(src_path)
    last_hash = db.get_last_banner_hash(carrier, is_store=is_store)

    if new_hash == last_hash:
        return  # banner unchanged

    today = date.today().isoformat()
    subfolder = f"{carrier}_store" if is_store else carrier
    dest_dir = os.path.join(ARCHIVE_BANNER_DIR, subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, f"{today}.png")

    shutil.copy2(src_path, dest_path)
    # Store a relative path so the archive is portable
    rel_path = os.path.relpath(dest_path, start=os.path.dirname(os.path.abspath(__file__)))
    db.insert_archive_banner(carrier, is_store, today, rel_path, new_hash)


def archive_all_banners(banner_dir: str, carriers: list[str], store_carriers: list[str]):
    """
    Snapshot all current homepage and e-store PNGs.

    banner_dir   : path to data/banners/
    carriers     : list of all homepage carrier ids
    store_carriers: list of carrier ids that have e-store banners ({carrier}_store.png)
    """
    for carrier in carriers:
        src = os.path.join(banner_dir, f"{carrier}.png")
        save_banner_snapshot(carrier, src, is_store=False)

    for carrier in store_carriers:
        src = os.path.join(banner_dir, f"{carrier}_store.png")
        save_banner_snapshot(carrier, src, is_store=True)
