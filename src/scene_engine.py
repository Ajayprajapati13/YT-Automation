"""Reusable production scene engine (TASK-010).

Turns a list of `Scene` definitions into a single draw_frame function,
centralizing the compositing plumbing that TASK-009's proof had wired
by hand per beat (cross-fade timing, transition sweep, the glow pass,
character bounds-safety, "only one character renders at a time"). New
scenes for the full video are added by appending a Scene, not by
duplicating this logic.

Each Scene covers the 9-field contract from TASK-010:
  1. metadata/story beat  -> Scene.id / Scene.title
  2. narration segment    -> Scene.narration
  3. character pose       -> decided inside draw_diagram, returned as
                              (pose, cx, bottom_y, height, alpha, flip)
  4. background/stage     -> Scene.stage_box (None to skip the panel)
  5. diagram/technical visual layers -> Scene.draw_diagram
  6. object animations/data flows    -> drawn inside draw_diagram,
                              using the shared motion_graphics primitives
  7. camera actions       -> a motion_graphics.Camera built inside
                              draw_diagram (kept out of character
                              placement so the character can never be
                              clipped by it -- see safe_character)
  8. transition           -> Scene.fade / Scene.overlap (cross-fade) +
                              the automatic sweep at each scene boundary
  9. timing/validation    -> Scene.start / Scene.end / Scene.validation

draw_diagram signature: (draw, layer, t, alpha, glow_sources) ->
    character_tuple | None
Only actually draw content when alpha > 0 (the runner already skips
calling draw_diagram at alpha<=0.001, but content within a scene may
have its own finer-grained timing).
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
from PIL import Image, ImageDraw

import motion_graphics as mg
import character_assets as ca
import create_poc_scene as _scene  # for pipeline_arrow's grow/dot animation

SAFE_MARGIN = 30


@dataclass
class Scene:
    id: str
    title: str
    narration: str
    start: float
    end: float
    draw_diagram: Callable
    stage_box: Optional[tuple] = None
    stage_fill: tuple = (246, 249, 253)
    stage_fill_alpha: float = 0.65
    stage_outline_alpha: float = 0.22
    fade: float = 0.6
    overlap: float = 0.5
    validation: dict = field(default_factory=dict)

    def alpha(self, t, is_first=False):
        ov = 0.0 if is_first else self.overlap
        return mg.fade_window(t, self.start - ov, self.start - ov + self.fade,
                               self.end - self.fade, self.end)


def beat_progress(t, start, dur=0.8):
    """Standard entrance-timing curve reused across scenes."""
    return mg.ease_out_back(mg.window(t, start, start + dur))


def stage_panel(draw, alpha, box, theme, fill=(246, 249, 253), fill_alpha=0.65, outline_alpha=0.22):
    if alpha <= 0.001 or box is None:
        return
    mg.draw_rounded_rect(draw, box, 44, fill=fill, alpha=alpha * fill_alpha)
    mg.draw_rounded_rect(draw, box, 44, outline=theme["blue"], width=2, alpha=alpha * outline_alpha)


def safe_character(pose, cx, bottom_y, target_height, alpha, flip=False):
    """Clamp a character placement so it always stays fully on-screen,
    regardless of any camera work applied to the diagram around it."""
    native = ca.load_poses()[pose]
    width = target_height * (native.width / native.height)

    cx = max(SAFE_MARGIN + width / 2, min(mg.WIDTH - SAFE_MARGIN - width / 2, cx))
    bottom_y = max(SAFE_MARGIN + target_height, min(mg.HEIGHT - SAFE_MARGIN, bottom_y))

    return (pose, cx, bottom_y, target_height, alpha, flip)


def hand_connector(draw, theme, pose, cx, bottom_y, height, flip, target, t, grow_start, grow_end, alpha):
    origin = ca.hand_point(pose, cx, bottom_y, height, flip=flip)
    if origin is None:
        return
    _scene.pipeline_arrow(draw, origin, target, t, grow_start, grow_end, theme, alpha=alpha * 0.75, width=3)


def transition_sweep(draw, t, boundary, theme, half_width=0.35, color_key="blue_bright", strength=0.10):
    start, end = boundary - half_width, boundary + half_width
    p = mg.window(t, start, end)
    if p <= 0.001 or p >= 0.999:
        return
    band_alpha = (1.0 - abs(2 * p - 1.0)) * strength
    x = mg.lerp(-300, mg.WIDTH + 300, p)
    draw.polygon(
        [(x, 0), (x + 220, 0), (x - 220, mg.HEIGHT), (x - 440, mg.HEIGHT)],
        fill=mg.rgba(theme[color_key], band_alpha),
    )


def render_scenes(scenes, theme, background_wide, post_fn=None, glow_blur=12, glow_downsample=3):
    """Builds a draw_frame(t, frame_index, total_frames) function from a
    list of Scene objects. `post_fn(rgb_image, t) -> rgb_image` runs last,
    after character compositing, for whole-frame effects (e.g. a closing
    dim+statement overlay) that aren't tied to a single scene's alpha."""

    def draw_frame(t, frame_index, total_frames):
        base = mg.parallax_crop(background_wide, t, mg.WIDTH, mg.HEIGHT).convert("RGBA")
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")

        glow_sources = []
        char_call = None

        for i, sc in enumerate(scenes):
            alpha = sc.alpha(t, is_first=(i == 0))
            if alpha <= 0.001:
                continue
            stage_panel(draw, alpha, sc.stage_box, theme, sc.stage_fill, sc.stage_fill_alpha, sc.stage_outline_alpha)
            result = sc.draw_diagram(draw, layer, t, alpha, glow_sources)
            if result is not None:
                # Later scenes win: during a cross-fade, only the
                # incoming scene's character is drawn once its alpha is
                # non-zero, instead of both poses rendering superimposed.
                char_call = result

        for sc in scenes[1:]:
            transition_sweep(draw, t, sc.start, theme)

        composed = Image.alpha_composite(base, layer)
        rgb = composed.convert("RGB")

        if glow_sources:
            def glow_fn(d, s):
                for kind, box, radius, color, a in glow_sources:
                    if a <= 0.001:
                        continue
                    x0, y0, x1, y1 = box
                    width = max(1, round(12 * s))
                    d.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s), radius=radius * s,
                                         outline=mg.blend_toward(color, theme["glow_neutral"], min(1.0, a)),
                                         width=width)
            rgb = mg.glow_composite(rgb, glow_fn, blur_radius=glow_blur, downsample=glow_downsample,
                                     blend=theme["glow_blend"])

        rgba = rgb.convert("RGBA")
        if char_call is not None:
            pose, cx, bottom_y, height, alpha, flip = char_call
            ca.paste_character(rgba, pose, cx, bottom_y, height, alpha=alpha, flip=flip)
        rgb = rgba.convert("RGB")

        if post_fn is not None:
            rgb = post_fn(rgb, t)

        return rgb

    return draw_frame
