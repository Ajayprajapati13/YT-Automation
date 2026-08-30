"""Per-video visual identity (requirement 12, architecture audit follow-up).

A small, explicit config object so a future video can diverge in camera
language, typography treatment, transition style, and animation emphasis
without touching builder code - beat builders read identity knobs instead
of hardcoding them. The character (character_assets.py) stays a recurring
brand element regardless of identity; this only affects how it and the
diagrams around it are staged/moved/typeset.

Deliberately minimal: this does not yet cover asset treatment (no B-roll/
generated-asset hookup - requirement 13 explicitly defers that) or new
character behaviors beyond the existing static poses (see the "known
limitations" note in the architecture audit follow-up) - environments,
composition, and camera language are the parts wired in today.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VisualIdentity:
    name: str
    theme: dict                          # color palette (create_poc_scene.LIGHT_THEME today)
    camera_intensity: float = 1.0        # multiplies every beat's camera_strategy scale delta
    transition_style: str = "hard_cut"   # between-shot treatment: "hard_cut" | "cross_fade"
    stat_emphasis_color_key: str = "amber"  # which theme color stat_callout/kinetic text uses
    grid_density_bias: float = 1.0       # multiplies core_grid stagger timing (denser/sparser builds)


def default_identity(theme: dict) -> VisualIdentity:
    """Matches today's locked visual system (docs/visual_system.md) exactly -
    the baseline every existing video already uses, expressed as data so a
    future identity is a new instance of this, not a code change."""
    return VisualIdentity(name="locked_default_v1", theme=theme)
