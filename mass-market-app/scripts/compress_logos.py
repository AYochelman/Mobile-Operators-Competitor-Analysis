"""Compress oversized logo PNGs in mass-market-app/public/logos/.

Targets only files >100 KB. Resizes to max 256 px on longest edge,
preserves transparency, saves as optimized PNG. Originals backed up
to logos_originals_backup/ before overwrite.
"""
from pathlib import Path
import shutil
from PIL import Image

LOGOS_DIR = Path(__file__).resolve().parents[1] / 'public' / 'logos'
BACKUP_DIR = LOGOS_DIR.parent / 'logos_originals_backup'
THRESHOLD_BYTES = 100 * 1024   # only touch files larger than this
MAX_EDGE = 256                  # plenty for retina at logical 32-72 px

def compress(path: Path) -> tuple[int, int]:
    """Returns (before_bytes, after_bytes)."""
    before = path.stat().st_size
    img = Image.open(path)
    # Preserve transparency
    if img.mode not in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
    img.save(path, format='PNG', optimize=True)
    return before, path.stat().st_size

def main() -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    total_before = 0
    total_after = 0
    touched = 0
    for png in sorted(LOGOS_DIR.glob('*.png')):
        if png.stat().st_size <= THRESHOLD_BYTES:
            continue
        backup = BACKUP_DIR / png.name
        if not backup.exists():
            shutil.copy2(png, backup)
        before, after = compress(png)
        total_before += before
        total_after += after
        touched += 1
        pct = 100 * (1 - after / before)
        print(f"{png.name:30s} {before/1024:>8.0f} KB -> {after/1024:>6.0f} KB  ({pct:5.1f}% saved)")
    if touched:
        saved_mb = (total_before - total_after) / (1024 * 1024)
        print(f"\nTotal: {touched} files, saved {saved_mb:.1f} MB")
    else:
        print("Nothing to compress.")

if __name__ == '__main__':
    main()
