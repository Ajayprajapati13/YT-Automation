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

TASK-009 fix: a fixed equal-width column split left visible fragments
of the neighbouring pose's hand at some crop edges (TASK-008 review).
The real cause was that poses aren't evenly spaced -- the true gap
between two poses is wherever the alpha density actually drops to zero
between them, not at a naive width/5 boundary. load_poses() now scans
the row's alpha-density profile once and cuts at the true valleys, so
adjacent-pose bleed is eliminated at the boundaries where a true gap
exists (introg|explaining, explaining|thinking, thinking|closing).

The 'reference' pose has no true zero-density gap on its left side --
its own outstretched hand blends continuously toward the neighbouring
pose at low alpha (confirmed: increasing the crop trim there just cuts
into increasingly opaque real arm content, never reaching zero). That
pose remains excluded from use rather than shipped with a residual
fragment, per the TASK-008/009 quality gate.
"""

from pathlib import Path
from PIL import Image

BASE_DIR = Path(r"C:\YT-Automation")
REFERENCE_SHEET = BASE_DIR / "assets" / "character" / "character_reference_sheet.png"

# Column order matches the sheet's own labels (left to right).
POSE_NAMES = ["reference", "introg", "explaining", "thinking", "closing"]

_BADGE_CUTOFF_Y = 384  # everything below this row is the debug label badge
_ALPHA_THRESHOLD = 30
_ROW_STEP = 2  # y sampling step for the density scan (speed vs. precision)

_cache = None


def _column_density(alpha_channel, x, height):
    return sum(
        1 for y in range(0, height, _ROW_STEP)
        if alpha_channel.getpixel((x, y)) > _ALPHA_THRESHOLD
    )


def _find_boundaries(alpha_channel, width, n_poses, col_start=200):
    """Locates the true (lowest-density) split point between each pair
    of adjacent poses, searching near each nominal equal-width boundary
    instead of assuming poses are evenly spaced."""
    nominal_width = (width - col_start) / n_poses
    boundaries = [col_start]

    for i in range(1, n_poses):
        nominal = col_start + i * nominal_width
        lo = int(nominal - nominal_width * 0.35)
        hi = int(nominal + nominal_width * 0.35)
        best_x, best_density = nominal, None
        for x in range(max(col_start, lo), min(width, hi)):
            d = _column_density(alpha_channel, x, _BADGE_CUTOFF_Y)
            if best_density is None or d < best_density:
                best_x, best_density = x, d
        boundaries.append(best_x)

    boundaries.append(width)
    return boundaries


def load_poses():
    """Returns {pose_name: PIL.Image RGBA}, computed once and cached."""
    global _cache
    if _cache is not None:
        return _cache

    if not REFERENCE_SHEET.exists():
        raise FileNotFoundError(f"Character reference sheet not found: {REFERENCE_SHEET}")

    sheet = Image.open(REFERENCE_SHEET).convert("RGBA")
    width, _ = sheet.size
    alpha_channel = sheet.split()[-1]

    boundaries = _find_boundaries(alpha_channel, width, len(POSE_NAMES))

    poses = {}
    for i, name in enumerate(POSE_NAMES):
        x0, x1 = boundaries[i], boundaries[i + 1]
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
    target_height = max(1, int(round(target_height)))
    scale = target_height / sprite.height
    sprite = sprite.resize((max(1, int(sprite.width * scale)), target_height), Image.LANCZOS)

    if flip:
        sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)

    return sprite


# Approximate (dx_frac_of_width, dy_frac_of_height) offset from the
# (cx, bottom_y) anchor to each pose's raised/pointing hand, for drawing
# a connector line from "the presenter's hand" toward a diagram. Only
# defined for poses with a clearly extended gesturing hand.
HAND_OFFSET = {
    "introg": (-0.40, -0.42),
    "explaining": (-0.34, -0.80),
}


def hand_point(pose, cx, bottom_y, target_height, flip=False):
    if pose not in HAND_OFFSET:
        return None
    native = load_poses()[pose]
    width = target_height * (native.width / native.height)
    dxf, dyf = HAND_OFFSET[pose]
    if flip:
        dxf = -dxf
    return (cx + dxf * width, bottom_y + dyf * target_height)


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
