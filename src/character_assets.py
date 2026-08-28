"""Extracts the individual presenter poses from the user-provided
character reference sheet.

Canonical asset (per TASK-008): assets/character/character_reference_sheet.png
(as placed by the user, it had a duplicated .png.png extension; renamed to
the canonical single-extension name -- content untouched, per "do not
replace it" in the task, this only fixes the filename).

The sheet is a moodboard image, but its alpha channel already contains
clean, pre-matted per-character transparency for the five top-row
portraits (verified: compositing onto white produces clean edges, no
visible halo). Each portrait sits in its own labeled column with a
debug label badge burned in near the bottom -- we crop above the badge
and trim to the alpha bounding box, so no Pillow redrawing/approximation
of the character is involved, only cropping the existing artwork.
"""

from pathlib import Path
from PIL import Image

BASE_DIR = Path(r"C:\YT-Automation")
REFERENCE_SHEET = BASE_DIR / "assets" / "character" / "character_reference_sheet.png"

# Column order matches the sheet's own labels (left to right).
POSE_NAMES = ["reference", "introg", "explaining", "thinking", "closing"]

_BADGE_CUTOFF_Y = 384  # everything below this row is the debug label badge
_LEFT_TRIM = 10        # small trim to drop the neighbouring pose's arm sliver

_cache = None


def load_poses():
    """Returns {pose_name: PIL.Image RGBA}, computed once and cached."""
    global _cache
    if _cache is not None:
        return _cache

    if not REFERENCE_SHEET.exists():
        raise FileNotFoundError(f"Character reference sheet not found: {REFERENCE_SHEET}")

    sheet = Image.open(REFERENCE_SHEET).convert("RGBA")
    width, _ = sheet.size

    col_start = 200
    col_width = (width - col_start) // len(POSE_NAMES)

    poses = {}
    for i, name in enumerate(POSE_NAMES):
        x0 = col_start + i * col_width + _LEFT_TRIM
        x1 = col_start + (i + 1) * col_width
        region = sheet.crop((x0, 0, x1, _BADGE_CUTOFF_Y))
        bbox = region.getbbox()
        poses[name] = region.crop(bbox) if bbox else region

    _cache = poses
    return poses


def character_sprite(pose, target_height, flip=False):
    """Scaled (and optionally mirrored) copy of a pose, aspect preserved."""
    poses = load_poses()
    if pose not in poses:
        raise KeyError(f"Unknown pose '{pose}'. Available: {sorted(poses)}")

    sprite = poses[pose]
    scale = target_height / sprite.height
    sprite = sprite.resize((max(1, int(sprite.width * scale)), target_height), Image.LANCZOS)

    if flip:
        sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)

    return sprite


def paste_character(base_rgba, pose, cx, bottom_y, target_height, alpha=1.0, flip=False):
    """Composite a character pose onto base_rgba, anchored bottom-center."""
    if alpha <= 0.001:
        return base_rgba

    sprite = character_sprite(pose, target_height, flip=flip)

    if alpha < 0.999:
        r, g, b, a = sprite.split()
        a = a.point(lambda v: int(v * alpha))
        sprite = Image.merge("RGBA", (r, g, b, a))

    x = int(cx - sprite.width / 2)
    y = int(bottom_y - sprite.height)

    base_rgba.alpha_composite(sprite, (x, y))
    return base_rgba
