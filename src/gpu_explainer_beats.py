"""Beat-level diagram builders implementing the visual-strategy library
(docs/pipeline_architecture_audit_2026-08-31.md follow-up, requirement 4).

Each builder returns a draw_diagram(draw, layer, t, alpha, glow) ->
character_tuple|None function with the exact scene_engine.Scene contract -
a beat IS a Scene, just scoped to one shot's local time (0..duration)
instead of the whole video.

Every builder takes an optional `entities` dict (labels/grid sizes/lines
pulled from content/gpu_scene_concepts.json) as its last argument. This is
what makes a single set of 9 builders reusable across every scene instead
of one hand-written diagram function per scene: the SAME make_comparison,
for example, draws "CPU vs GPU" for cpu_vs_gpu and "TASK vs GPU CORES" for
parallelism purely from data, not new code. When entities is None/omitted,
each builder falls back to its original cpu_vs_gpu-specific defaults, so
the existing, validated cpu_vs_gpu path (BEAT_DIAGRAM_BUILDERS, called
with exactly 3 positional args) is unaffected.

Character presence is optional per beat (entities["include_character"],
default varies by strategy - see each builder) rather than forced into
every shot.

Reuses existing primitives only (core_grid/hand_connector from
create_character_proof, safe_character/beat_progress from scene_engine,
Camera/traveling_dots/text_reveal/draw_arrow from motion_graphics) - no
changes to motion_graphics.py or scene_engine.py. motion_graphics.py on
this branch does not define stat_reveal (it exists only on a different
branch's HF-incident script), so it's composed here from existing
primitives (draw_text_centered/fade_window/ease_out_back).

motion_graphics.Camera is applied inside each beat's own diagram function -
apply_shot_motion (whole-frame post-crop, create_shot_driven_video.py) is
not used anywhere in this path.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

import motion_graphics as mg
import scene_engine as se
from create_character_proof import core_grid, hand_connector, CPU_COLOR, THEME
from visual_identity import VisualIdentity, default_identity

safe_character = se.safe_character
beat_progress = se.beat_progress


def stat_reveal(draw, cx, cy, number_text, label_text, alpha, t, start, color, dur=0.8,
                 number_size=110, label_size=24):
    """Composed from existing motion_graphics primitives (ease_out_back,
    fade_window, lerp, draw_text_centered) - not a rewrite of anything,
    since motion_graphics.py does not itself define this on this branch."""
    a = alpha * mg.fade_window(t, start, start + 0.4)
    if a <= 0.001:
        return
    prog = mg.ease_out_back(mg.window(t, start, start + dur))
    size = max(1, int(number_size * mg.lerp(0.6, 1.0, prog)))
    mg.draw_text_centered(draw, number_text, cx, cy - number_size * 0.32, size, color, alpha=a, bold=True)
    mg.draw_text_centered(draw, label_text, cx, cy + number_size * 0.4, label_size, THEME["dim_text"],
                           alpha=a, bold=True)


def _camera(strategy: dict, duration: float, t: float, identity: VisualIdentity) -> mg.Camera:
    kind = strategy["kind"]
    anchor = tuple(strategy["anchor"])
    s0, s1 = strategy["scale_from"], strategy["scale_to"]
    s1 = mg.lerp(s0, s1, identity.camera_intensity) if identity.camera_intensity != 1.0 else s1
    if kind in ("push_in", "pull_out"):
        p = mg.ease_in_out_cubic(mg.window(t, duration * 0.1, duration * 0.9))
        return mg.Camera(anchor=anchor, scale=mg.lerp(s0, s1, p))
    return mg.Camera(anchor=anchor, scale=1.0)


# ------------------------------------------------------------------
# Visual strategy library - 9 entries (shot_planner.VISUAL_STRATEGY_LIBRARY).
# ------------------------------------------------------------------

def make_establishing_visual(duration: float, camera_strategy: dict,
                              identity: VisualIdentity = None, entities: dict = None):
    """establishing_visual: title-only beat, no diagram yet. Distinct
    composition: pure kinetic type on an otherwise empty stage."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    title = entities.get("title", "CPU  vs  GPU")
    include_character = entities.get("include_character", True)

    def diagram(draw, layer, t, alpha, glow):
        cam = _camera(camera_strategy, duration, t, identity)
        title_alpha = mg.fade_window(t, 0.15, 0.5, duration - 0.4, duration)
        p = mg.ease_out_cubic(mg.window(t, 0.2, duration - 0.3))
        mg.text_reveal(layer, title, *cam.xy(960, 480), 56, THEME["blue_bright"], p, alpha=title_alpha, bold=True)
        if not include_character:
            return None
        prog = beat_progress(t, 0.1, 0.7)
        return safe_character("thinking", mg.lerp(-100, 300, prog), 1000, 380, alpha)
    return diagram


def make_diagram_build(duration: float, camera_strategy: dict,
                        identity: VisualIdentity = None, entities: dict = None):
    """diagram_build: a single entity's grid assembles - genuinely
    different composition from a title-only establishing beat."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    label = entities.get("entity_a", "CPU")
    rows, cols = entities.get("entity_a_grid", [2, 2])
    sublabel = entities.get("entity_a_sublabel", "FEW CORES, HIGH PER-CORE SPEED")
    color = CPU_COLOR if label == "CPU" else None
    include_character = entities.get("include_character", True)

    def diagram(draw, layer, t, alpha, glow):
        cam = _camera(camera_strategy, duration, t, identity)
        box = core_grid(draw, *cam.xy(*camera_strategy["anchor"]), cam.wh(320), cam.wh(320), rows, cols,
                         label, alpha, t, 0.2, glow, stagger=0.35 * identity.grid_density_bias, color=color)
        if sublabel:
            sub_alpha = alpha * mg.fade_window(t, 1.0, 1.4)
            mg.draw_text_centered(draw, sublabel, (box[0] + box[2]) / 2, box[3] + 40, 20,
                                   THEME["dim_text"], alpha=sub_alpha, bold=True)
        if not include_character:
            return None
        prog = beat_progress(t, 0.1, 0.7)
        return safe_character("explaining", mg.lerp(2000, 1660, prog), 1010, 470, alpha, flip=True)
    return diagram


def make_comparison(duration: float, camera_strategy: dict,
                     identity: VisualIdentity = None, entities: dict = None):
    """comparison: a second entity's grid builds alongside the first,
    settled, with a marker between them - two full diagrams side by
    side, not one diagram continued."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    left_label = entities.get("entity_a", "CPU")
    left_rows, left_cols = entities.get("entity_a_grid", [2, 2])
    right_label = entities.get("entity_b", "GPU")
    right_rows, right_cols = entities.get("entity_b_grid", [4, 8])
    marker = entities.get("comparison_marker", "VS")
    left_color = CPU_COLOR if left_label == "CPU" else None
    include_character = entities.get("include_character", True)

    def diagram(draw, layer, t, alpha, glow):
        cam = _camera(camera_strategy, duration, t, identity)
        core_grid(draw, *cam.xy(430, 560), cam.wh(280), cam.wh(280), left_rows, left_cols, left_label,
                  alpha, t, -0.6, glow, stagger=0.0, color=left_color)
        gpu_box = core_grid(draw, *cam.xy(1080, 560), cam.wh(420), cam.wh(300), right_rows, right_cols,
                             right_label, alpha, t, 0.2, glow, stagger=0.045 * identity.grid_density_bias)
        vs_alpha = alpha * mg.fade_window(t, 0.9, 1.3)
        mg.draw_text_centered(draw, marker, *cam.xy(755, 560), 30, THEME["dim_text"], alpha=vs_alpha, bold=True)
        if not include_character:
            return None
        prog = beat_progress(t, 0.1, 0.7)
        char = safe_character("explaining", mg.lerp(2000, 1660, prog), 1010, 470, alpha, flip=True)
        _, ccx, cby, ch, calpha, cflip = char
        hand_connector(draw, "explaining", ccx, cby, ch, True,
                        (gpu_box[2] - 20, (gpu_box[1] + gpu_box[3]) / 2), t, 1.4, 2.0, alpha)
        return char
    return diagram


def make_stat_callout(duration: float, camera_strategy: dict,
                       identity: VisualIdentity = None, entities: dict = None):
    """stat_callout: diagrams disappear entirely - a full-frame numeric
    emphasis card. Character optional and off by default: this beat's
    whole point is a pure typography moment with nothing competing."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    number = entities.get("stat_number", "1000s")
    label = entities.get("stat_label", "MORE CORES THAN A CPU")
    color = THEME[identity.stat_emphasis_color_key]
    include_character = entities.get("include_character", False)

    def diagram(draw, layer, t, alpha, glow):
        stat_reveal(draw, 960, 480, number, label, alpha, t, 0.15, color, dur=0.7)
        if not include_character:
            return None
        return safe_character("thinking", 1650, 1010, 300, alpha)
    return diagram


def make_data_flow(duration: float, camera_strategy: dict,
                    identity: VisualIdentity = None, entities: dict = None):
    """data_flow: camera pushes into an entity's grid detail and
    traveling-dot streams animate through it - close-up, content-focused;
    character optional and off by default."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    label = entities.get("entity_b") or entities.get("entity_a", "GPU")
    rows, cols = entities.get("entity_b_grid") or entities.get("entity_a_grid", [4, 8])
    caption = entities.get("flow_caption", "EVERY CORE WORKING AT ONCE")
    include_character = entities.get("include_character", False)

    def diagram(draw, layer, t, alpha, glow):
        cam = _camera(camera_strategy, duration, t, identity)
        gpu_box = core_grid(draw, *cam.xy(1080, 560), cam.wh(420), cam.wh(300), rows, cols, label,
                             alpha, t, -0.6, glow, stagger=0.0)
        targets = [(gpu_box[0] + 40 + i * 45, gpu_box[1] + 30) for i in range(min(6, rows * cols))]
        source = (gpu_box[0] - 140, gpu_box[1] + (gpu_box[3] - gpu_box[1]) / 2)
        for i, tgt in enumerate(targets):
            stream_start = 0.2 + i * 0.12
            if t >= stream_start:
                mg.traveling_dots(draw, source, tgt, t - stream_start, 0.5, 3,
                                   THEME["blue_bright"], radius=4, alpha=alpha * 0.75, phase_offset=i * 0.13)
        cap_alpha = alpha * mg.fade_window(t, 0.4, 0.8)
        mg.draw_text_centered(draw, caption, 960, 940, 26,
                               THEME[identity.stat_emphasis_color_key], alpha=cap_alpha, bold=True)
        if not include_character:
            return None
        return safe_character("thinking", 1700, 1000, 340, alpha)
    return diagram


def make_character_interaction(duration: float, camera_strategy: dict,
                                identity: VisualIdentity = None, entities: dict = None,
                                pose: str = "explaining"):
    """character_interaction: the diagram settles into the background and
    the frame closes on the presenter reacting/confirming, with an
    animated hand-connector arrow. Beyond static placement: the character
    steps in, THEN keeps a small continuous confirming bob for the rest
    of the hold (mg.pulse on vertical position) rather than freezing once
    placed - a first, modest step toward real movement/reaction rather
    than a static pose, per the requirement that the character
    progressively move beyond static placement."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    statement = entities.get("closing_statement", "THAT'S THE ADVANTAGE.")
    bg_label = entities.get("entity_b") or entities.get("entity_a", "GPU")

    def diagram(draw, layer, t, alpha, glow):
        dim_alpha = alpha * 0.5
        core_grid(draw, 700, 700, 300, 220, 2, 4, bg_label, dim_alpha, t, -1.0, glow, stagger=0.0)
        prog = beat_progress(t, 0.05, 0.5)
        step_x = mg.lerp(1650, 1500, prog)
        bob = 0.0
        if t > 0.55:
            bob = 6.0 * mg.pulse((t - 0.55) * 0.6, 1.7)
        char = safe_character(pose, step_x, 1000 - bob, 620, alpha, flip=False)
        _, ccx, cby, ch, calpha, cflip = char
        hand_connector(draw, pose, ccx, cby, ch, False, (900, 700), t, 0.2, 0.6, alpha)
        conf_alpha = alpha * mg.fade_window(t, 0.5, 0.9)
        mg.draw_text_centered(draw, statement, 1500, 300, 28, THEME["blue_bright"], alpha=conf_alpha, bold=True)
        return char
    return diagram


def make_kinetic_text(duration: float, camera_strategy: dict,
                       identity: VisualIdentity = None, entities: dict = None):
    """kinetic_text: pure animated typography, no diagram or character -
    a full-strategy-library entry, not exercised by the current tests
    (their scenes always have a diagram-worthy concept in play), included
    so the library is complete for scenes that need a pure statement beat."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    lines = entities.get("lines") or (entities.get("title", "KEY IDEA"),)

    def diagram(draw, layer, t, alpha, glow):
        cam = _camera(camera_strategy, duration, t, identity)
        for i, line in enumerate(lines):
            p = mg.ease_out_cubic(mg.window(t, 0.15 + i * 0.3, duration - 0.3))
            a = mg.fade_window(t, 0.1 + i * 0.3, 0.5 + i * 0.3)
            mg.text_reveal(layer, line, *cam.xy(960, 480 + i * 90), 54, THEME["blue_bright"],
                            p, alpha=alpha * a, bold=True)
        return None
    return diagram


def make_close_up_detail(duration: float, camera_strategy: dict,
                          identity: VisualIdentity = None, entities: dict = None):
    """close_up_detail: a tight camera push on a single element with no
    wider context - character off by default (this is a pure-detail
    beat)."""
    identity = identity or default_identity(THEME)
    entities = entities or {}
    label = entities.get("entity_a", "CORE")
    include_character = entities.get("include_character", False)

    def diagram(draw, layer, t, alpha, glow):
        cam = _camera(camera_strategy, duration, t, identity)
        core_grid(draw, *cam.xy(960, 560), cam.wh(220), cam.wh(220), 1, 1, label, alpha, t, 0.1, glow)
        if not include_character:
            return None
        return safe_character("thinking", 1700, 1000, 300, alpha)
    return diagram


def make_transition_visual(duration: float, camera_strategy: dict,
                            identity: VisualIdentity = None, entities: dict = None):
    """transition_visual: a brief connective beat (light sweep + hold) -
    no character, no diagram; purely a pacing/connective beat between
    concepts."""
    identity = identity or default_identity(THEME)

    def diagram(draw, layer, t, alpha, glow):
        sweep_p = mg.window(t, 0.0, duration)
        sweep_alpha = alpha * (1.0 - abs(2 * sweep_p - 1.0)) * 0.4
        x = mg.lerp(-200, mg.WIDTH + 200, sweep_p)
        draw.polygon([(x, 0), (x + 130, 0), (x - 130, mg.HEIGHT), (x - 260, mg.HEIGHT)],
                     fill=mg.rgba(THEME["blue_bright"], sweep_alpha))
        return None
    return diagram


BEAT_DIAGRAM_BUILDERS = {
    "cpu_vs_gpu.establishing": make_establishing_visual,
    "cpu_vs_gpu.cpu_build": make_diagram_build,
    "cpu_vs_gpu.gpu_build_compare": make_comparison,
    "cpu_vs_gpu.core_count_stat": make_stat_callout,
    "cpu_vs_gpu.core_data_flow": make_data_flow,
    "cpu_vs_gpu.explaining_reaction": make_character_interaction,
}

# Strategy-name -> builder map, independent of any one scene's visual_id
# namespacing. This is the actual reusable "library": build_diagram_for_strategy()
# below dispatches on visual_strategy + per-scene entities, so a new scene
# needs a content/gpu_scene_concepts.json entry, not a new function here.
VISUAL_STRATEGY_BUILDERS = {
    "establishing_visual": make_establishing_visual,
    "diagram_build": make_diagram_build,
    "comparison": make_comparison,
    "stat_callout": make_stat_callout,
    "data_flow": make_data_flow,
    "character_interaction": make_character_interaction,
    "kinetic_text": make_kinetic_text,
    "close_up_detail": make_close_up_detail,
    "transition_visual": make_transition_visual,
}


def build_diagram_for_strategy(strategy: str, duration: float, camera_strategy: dict,
                                identity: VisualIdentity, entities: dict, character_pose: str = None):
    """The generic dispatcher: any scene's auto-selected shot (strategy +
    entities, from shot_planner.build_auto_shots) resolves to a draw_diagram
    through here, reusing the same 9 builders cpu_vs_gpu's hand-authored
    beats use directly via BEAT_DIAGRAM_BUILDERS."""
    builder = VISUAL_STRATEGY_BUILDERS.get(strategy)
    if builder is None:
        raise KeyError(f"no builder registered for visual_strategy={strategy!r}")
    if strategy == "character_interaction" and character_pose:
        return builder(duration, camera_strategy, identity, entities, pose=character_pose)
    return builder(duration, camera_strategy, identity, entities)
