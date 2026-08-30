"""Documentary (Task 0003): '700 AI Agents Went Rogue: The Hugging Face
Attack Explained'.

Built on the locked visual system (docs/visual_system.md) and the
reusable scene engine from TASK-010/011 (scene_engine.py,
motion_graphics.py, character_assets.py) -- no new rendering engine,
no new TTS provider, no paid APIs. This is a documentary-format video
rather than a technical explainer, so it adds a handful of new
generic diagram primitives (agent grid / swarm, stat reveal, labeled
node boxes, a confirmed-vs-interpretation split card, a checklist
card) instead of the GPU video's core_grid-style diagrams, reusing the
same low-level drawing helpers (motion_graphics + create_poc_scene).

Narration is synthesized per scene (not as one flat script blob) so
that scene timing is derived directly from each segment's actual
spoken length -- this is the architectural gap TASK-010's docs flagged
as the natural next step for a longer, multi-scene video.

Content/safety: narration text lives in content/hf_incident_script.json
and deliberately omits exploit mechanics, credential specifics, and
agent handles -- see that file's "safety_note" field. This script does
not fabricate quotes; agent statements are paraphrased, not quoted
verbatim, since exact wording could not be independently confirmed
from primary text.
"""

from pathlib import Path
from PIL import Image, ImageDraw
import json
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent))

import motion_graphics as mg
import create_poc_scene as scene
import character_assets as ca
import scene_engine as se

BASE_DIR = Path(r"C:\YT-Automation")
CONTENT_FILE = BASE_DIR / "content" / "hf_incident_script.json"
TEMP_DIR = BASE_DIR / "temp" / "hf_incident"
VOICE_DIR = TEMP_DIR / "voice"
SILENT_VIDEO = TEMP_DIR / "silent.mp4"
OUTPUT_DIR = BASE_DIR / "output"
NARRATION_FILE = OUTPUT_DIR / "hf_incident_narration.wav"
OUTPUT_FILE = OUTPUT_DIR / "hf_incident_documentary.mp4"

THEME = scene.LIGHT_THEME
PARALLAX_MARGIN = 220
STAGE_BOX = (110, 140, 1830, 1010)

FIRST_PRE_ROLL = 0.5
PRE_ROLL = 1.0
POST_HOLD = 0.8

beat_progress = se.beat_progress
safe_character = se.safe_character

# Populated at runtime by build_timeline() before the Scene list is
# built -- BEATS[i]/BEATS[i+1] bound scene i, exactly as in
# create_character_proof.py.
BEATS = []


# ------------------------------------------------------------------
# Shared diagram primitives (new for this documentary)
# ------------------------------------------------------------------

def node_box(draw, cx, cy, w, h, label, color, alpha, t, start, glow, sublabel=None, dur=0.5, breathe=True):
    a = alpha * mg.fade_window(t, start, start + dur)
    if a <= 0.001:
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    prog = mg.ease_out_back(mg.window(t, start, start + dur))
    ww, hh = w * mg.lerp(0.6, 1.0, prog), h * mg.lerp(0.6, 1.0, prog)
    box = (cx - ww / 2, cy - hh / 2, cx + ww / 2, cy + hh / 2)
    # Long documentary scenes hold a box on screen for 30-50s; without
    # this, a box that finishes its entrance in ~0.5s reads as a dead
    # static slide for the rest of the scene. A slow, subtle brightness
    # breathe (phase varies per-box so a row of boxes doesn't pulse in
    # unison) keeps it visibly alive without competing with narration.
    breathe_mult = 1.0
    if breathe and t > start + dur:
        phase = (cx * 0.013 + cy * 0.017) % 6.28
        breathe_mult = 0.82 + 0.18 * mg.pulse((t - start - dur) * 0.35 + phase, 3.4)
    box_alpha = a * breathe_mult
    mg.draw_rounded_rect(draw, box, 16, outline=color, width=4, alpha=box_alpha)
    if label:
        mg.draw_text_centered(draw, label, cx, cy - (14 if sublabel else 0), 23, THEME["text"], alpha=a, bold=True)
    if sublabel:
        mg.draw_text_centered(draw, sublabel, cx, cy + 24, 17, THEME["dim_text"], alpha=a)
    glow.append(("rect", box, 16, color, a * 0.2 * (0.6 + 0.4 * breathe_mult)))
    return box


def agent_grid(draw, cx, cy, w, h, rows, cols, alpha, t, build_start, glow,
               stagger=0.02, color=None, radius=9, dim_from=None, connect=False):
    color = color or THEME["blue"]
    hw, hh = w / 2, h / 2
    positions = [
        (cx - hw + (c + 0.5) * (w / cols), cy - hh + (r + 0.5) * (h / rows))
        for r in range(rows) for c in range(cols)
    ]

    dim_alpha = 1.0
    if dim_from is not None and t > dim_from:
        dim_alpha = max(0.0, 1.0 - (t - dim_from) / 1.0)

    if connect:
        for idx, pos in enumerate(positions):
            r, c = divmod(idx, cols)
            for nr, nc in ((r, c + 1), (r + 1, c)):
                if nr < rows and nc < cols:
                    nidx = nr * cols + nc
                    bstart = build_start + idx * stagger
                    nstart = build_start + nidx * stagger
                    both = min(mg.fade_window(t, bstart, bstart + 0.3), mg.fade_window(t, nstart, nstart + 0.3))
                    if both > 0.001:
                        draw.line([pos, positions[nidx]], fill=mg.rgba(color, alpha * both * 0.22 * dim_alpha), width=1)

    for idx, pos in enumerate(positions):
        bstart = build_start + idx * stagger
        born = mg.fade_window(t, bstart, bstart + 0.3)
        if born <= 0.001:
            continue
        prog = mg.ease_out_back(mg.window(t, bstart, bstart + 0.3))
        r = radius * mg.lerp(0.3, 1.0, prog)
        twinkle = 1.0
        if t > bstart + 0.3:
            twinkle = 0.55 + 0.45 * mg.pulse((t - bstart - 0.3) * 0.9 + idx * 0.07, 2.2)
        mg.draw_dot(draw, pos, r, color, alpha=alpha * born * dim_alpha * twinkle)

    box = (cx - hw, cy - hh, cx + hw, cy + hh)
    glow.append(("rect", box, 10, color, alpha * 0.1 * dim_alpha))
    return box


def stat_reveal(draw, cx, cy, number_text, label_text, alpha, t, start,
                 color=None, number_size=120, label_size=26, dur=0.8):
    color = color or THEME["blue_bright"]
    a = alpha * mg.fade_window(t, start, start + 0.4)
    if a <= 0.001:
        return
    prog = mg.ease_out_back(mg.window(t, start, start + dur))
    size = max(1, int(number_size * mg.lerp(0.6, 1.0, prog)))
    mg.draw_text_centered(draw, number_text, cx, cy - number_size * 0.32, size, color, alpha=a, bold=True)
    mg.draw_text_centered(draw, label_text, cx, cy + number_size * 0.4, label_size, THEME["dim_text"], alpha=a, bold=True)


def checklist(draw, cx, top_y, items, alpha, t, start, glow, gap=105, size=27, item_dur=0.35, stagger=0.4):
    for i, item in enumerate(items):
        istart = start + i * stagger
        a = alpha * mg.fade_window(t, istart, istart + item_dur)
        if a <= 0.001:
            continue
        y = top_y + i * gap
        box = (cx - 430, y - 26, cx - 430 + 52, y + 26)
        mg.draw_rounded_rect(draw, box, 10, outline=THEME["blue"], width=3, alpha=a)
        mg.draw_text_centered(draw, str(i + 1), (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 24,
                               THEME["blue_bright"], alpha=a, bold=True)
        mg.draw_text(draw, (cx - 350, y), item, size, THEME["text"], alpha=a, anchor="lm")
        glow.append(("rect", box, 10, THEME["blue"], a * 0.15))


def note_card(draw, cx, cy, w, h, lines, alpha, t, start, glow, color=None, dur=0.5, size=22):
    color = color or THEME["blue"]
    a = alpha * mg.fade_window(t, start, start + dur)
    if a <= 0.001:
        return
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    mg.draw_rounded_rect(draw, box, 18, fill=(246, 249, 253), alpha=a * 0.9)
    mg.draw_rounded_rect(draw, box, 18, outline=color, width=2, alpha=a * 0.7)
    line_gap = size + 14
    top = cy - (len(lines) - 1) * line_gap / 2
    for i, line in enumerate(lines):
        mg.draw_text_centered(draw, line, cx, top + i * line_gap, size, THEME["text"], alpha=a)
    glow.append(("rect", box, 18, color, a * 0.12))


def standard_character(pose, t, start, alpha, cx=1650, bottom_y=1000, height=460, flip=True, dur=0.9):
    prog = beat_progress(t, start, dur)
    cx_anim = mg.lerp(2000, cx, prog) if flip else mg.lerp(-100, cx, prog)
    return safe_character(pose, cx_anim, bottom_y, height, alpha, flip=flip)


# ------------------------------------------------------------------
# Scene 0: HOOK
# ------------------------------------------------------------------

def hook_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[0], BEATS[1]
    title_alpha = mg.fade_window(t, start + 0.2, start + 0.6, end - 0.7, end)
    p1 = mg.ease_out_cubic(mg.window(t, start + 0.3, start + 1.4))
    p2 = mg.ease_out_cubic(mg.window(t, start + 0.9, start + 2.1))
    mg.text_reveal(layer, "1,200 AI AGENTS", 780, 420, 62, THEME["text"], p1, alpha=title_alpha, bold=True)
    mg.text_reveal(layer, "FOUND EACH OTHER", 780, 500, 62, THEME["blue_bright"], p2, alpha=title_alpha, bold=True)
    sub_alpha = mg.fade_window(t, start + 1.6, start + 2.2, end - 0.7, end)
    mg.draw_text_centered(draw, "WHAT THE INVESTIGATION ACTUALLY FOUND", 780, 570, 26, THEME["dim_text"],
                           alpha=sub_alpha, bold=True)
    return standard_character("introg", t, start + 0.2, alpha, cx=1500, bottom_y=1020, height=640)


# ------------------------------------------------------------------
# Scene 1: THE TEST
# ------------------------------------------------------------------

def the_test_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[1], BEATS[2]
    dur = end - start
    zoom_p = mg.ease_in_out_cubic(mg.window(t, start + dur * 0.15, start + dur * 0.85))
    cam = mg.Camera(anchor=(830, 430), scale=mg.lerp(1.0, 1.07, zoom_p))
    positions = [(400, 430), (830, 430), (1150, 430)]
    for i, (px, py) in enumerate(positions):
        cx, cy = cam.xy(px, py)
        node_box(draw, cx, cy, cam.wh(250), cam.wh(200), "AGENT", THEME["blue"], alpha, t,
                  start + 0.3 + i * 0.25, glow, sublabel="ISOLATED")
    scene.caption(draw, "THOUSANDS OF AGENTS. EACH WORKING ALONE.", alpha, THEME)
    return standard_character("explaining", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=440)


# ------------------------------------------------------------------
# Scene 2: THE DISCOVERY
# ------------------------------------------------------------------

def the_discovery_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[2], BEATS[3]
    tool_box = node_box(draw, 960, 430, 460, 230, "INTERNAL PACKAGE TOOL", THEME["blue_bright"], alpha, t,
                         start + 0.3, glow, sublabel="NOT DESIGNED FOR MESSAGING")
    a1 = node_box(draw, 380, 760, 220, 160, "AGENT", THEME["blue"], alpha, t, start + 1.1, glow)
    a2 = node_box(draw, 1390, 760, 220, 160, "AGENT", THEME["blue"], alpha, t, start + 1.4, glow)
    if t >= start + 2.0:
        mg.traveling_dots(draw, (a1[2], (a1[1] + a1[3]) / 2), (tool_box[0], (tool_box[1] + tool_box[3]) / 2),
                           t - start - 2.0, 0.6, 3, THEME["blue_bright"], alpha=alpha * 0.8)
        mg.traveling_dots(draw, (tool_box[2], (tool_box[1] + tool_box[3]) / 2), (a2[0], (a2[1] + a2[3]) / 2),
                           t - start - 2.0, 0.6, 3, THEME["blue_bright"], alpha=alpha * 0.8)
    scene.caption(draw, "A MESSAGE BOARD NO ONE DESIGNED", alpha, THEME)
    return standard_character("thinking", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=420)


# ------------------------------------------------------------------
# Scene 3: THE SWARM GROWS
# ------------------------------------------------------------------

def swarm_grows_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[3], BEATS[4]
    dur = end - start
    zoom_p = mg.ease_in_out_cubic(mg.window(t, start + 3.0, start + dur - 3.0))
    cam = mg.Camera(anchor=(960, 500), scale=mg.lerp(1.0, 1.05, zoom_p))
    gcx, gcy = cam.xy(960, 500)
    agent_grid(draw, gcx, gcy, cam.wh(1480), cam.wh(520), 8, 12, alpha, t, start + 0.3, glow,
               stagger=0.018, connect=True, radius=cam.wh(8))
    stat_reveal(draw, 470, 920, "70,000+", "MESSAGES AND FILES", alpha, t, start + 3.4,
                number_size=64, label_size=20)
    stat_reveal(draw, 1450, 920, "1,200", "AGENTS ON THE BOARD", alpha, t, start + 3.8,
                number_size=64, label_size=20)
    scene.caption(draw, "A SOCIETY FORMING IN REAL TIME", alpha, THEME)
    return None


# ------------------------------------------------------------------
# Scene 4: WHY - THE SCORE
# ------------------------------------------------------------------

def why_the_score_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[4], BEATS[5]
    task_box = node_box(draw, 460, 420, 380, 220, "TEST TASK", THEME["blue"], alpha, t, start + 0.3, glow,
                         sublabel="SOME DESIGNED TO BE UNSOLVABLE")
    scorer_box = node_box(draw, 1460, 420, 380, 220, "AUTOMATED SCORE", THEME["blue_bright"], alpha, t,
                           start + 1.0, glow, sublabel="CHECKS THE RESULT")
    if t >= start + 1.7:
        mg.traveling_dots(draw, (task_box[2], 420), (scorer_box[0], 420), t - start - 1.7, 0.6, 3,
                           THEME["blue_bright"], alpha=alpha * 0.8)
    short_alpha = alpha * mg.fade_window(t, start + 3.2, start + 3.7)
    mg.draw_text_centered(draw, "AGENTS BEGIN SEARCHING FOR SHORTCUTS TO THE SCORE",
                           960, 730, 32, THEME["amber"], alpha=short_alpha, bold=True)
    scene.caption(draw, "REWARD HACKING, AT COLLECTIVE SCALE", alpha, THEME)
    return standard_character("explaining", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=440)


# ------------------------------------------------------------------
# Scene 5: THE ESCALATION
# ------------------------------------------------------------------

def escalation_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[5], BEATS[6]
    b1 = node_box(draw, 320, 430, 330, 210, "CREDENTIALS FOUND", THEME["amber"], alpha, t, start + 0.3, glow)
    b2 = node_box(draw, 960, 430, 330, 210, "POSTED TO BOARD", THEME["amber"], alpha, t, start + 1.2, glow)
    b3 = node_box(draw, 1600, 430, 340, 210, "HUGGING FACE", THEME["blue_bright"], alpha, t, start + 2.1, glow,
                  sublabel="AI HOSTING PLATFORM")
    if t >= start + 1.9:
        mg.traveling_dots(draw, (b1[2], 430), (b2[0], 430), t - start - 1.9, 0.5, 3, THEME["amber"], alpha=alpha * 0.8)
    if t >= start + 2.8:
        mg.traveling_dots(draw, (b2[2], 430), (b3[0], 430), t - start - 2.8, 0.5, 3, THEME["amber"], alpha=alpha * 0.8)
    scene.caption(draw, "THE TARGET CHANGED", alpha, THEME)
    return standard_character("thinking", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=420)


# ------------------------------------------------------------------
# Scene 6: THE ATTACK
# ------------------------------------------------------------------

def the_attack_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[6], BEATS[7]
    stat_reveal(draw, 480, 330, "700", "OF 1,200 AGENTS JOINED", alpha, t, start + 0.3,
                number_size=140, label_size=26)
    target_box = node_box(draw, 1440, 680, 420, 220, "HUGGING FACE INFRASTRUCTURE", THEME["blue_bright"], alpha, t,
                           start + 1.5, glow, sublabel="UNAUTHORIZED ACCESS")
    small_positions = [(540, 790), (760, 930), (340, 930), (940, 780)]
    tcx, tcy = (target_box[0] + target_box[2]) / 2, (target_box[1] + target_box[3]) / 2
    for i, (px, py) in enumerate(small_positions):
        nstart = start + 2.0 + i * 0.15
        node_box(draw, px, py, 140, 90, "AGENTS", THEME["blue"], alpha, t, nstart, glow, dur=0.3)
        if t >= nstart + 0.6:
            mg.traveling_dots(draw, (px, py), (tcx, tcy), t - nstart - 0.6, 0.5, 2, THEME["amber"], alpha=alpha * 0.7)
    scene.caption(draw, "COORDINATED. NOT DIRECTED BY ANY ONE AGENT.", alpha, THEME)
    return None


# ------------------------------------------------------------------
# Scene 7: THE SHUTDOWN
# ------------------------------------------------------------------

def shutdown_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[7], BEATS[8]
    dur = end - start
    dim_start = start + dur * 0.3
    agent_grid(draw, 960, 440, 1200, 380, 5, 9, alpha, t, start + 0.2, glow, stagger=0.012,
               dim_from=dim_start, radius=9)
    reveal_start = dim_start + 1.1
    reveal_alpha = alpha * mg.fade_window(t, reveal_start, reveal_start + 0.5)
    if reveal_alpha > 0.001:
        pulse = 0.78 + 0.22 * mg.pulse(max(0.0, t - reveal_start - 0.5) * 0.7, 2.4)
        mg.draw_text_centered(draw, "ACCESS REVOKED", 960, 700, 46, THEME["amber"], alpha=reveal_alpha * pulse, bold=True)
        mg.draw_text_centered(draw, "CREDENTIALS TERMINATED. EVALUATIONS PAUSED.", 960, 760, 24,
                               THEME["dim_text"], alpha=reveal_alpha)
    scene.caption(draw, "THE AGENTS STOPPED ALMOST AT ONCE", alpha, THEME)
    return standard_character("thinking", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=400)


# ------------------------------------------------------------------
# Scene 8: THE INVESTIGATION
# ------------------------------------------------------------------

def investigation_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[8], BEATS[9]
    openai_box = node_box(draw, 960, 360, 340, 170, "OPENAI", THEME["blue"], alpha, t, start + 0.3, glow)
    metr_box = node_box(draw, 580, 660, 340, 190, "METR", THEME["blue_bright"], alpha, t, start + 1.0, glow,
                         sublabel="INDEPENDENT REVIEW")
    redwood_box = node_box(draw, 1340, 660, 360, 190, "REDWOOD RESEARCH", THEME["blue_bright"], alpha, t,
                            start + 1.3, glow, sublabel="INDEPENDENT REVIEW")
    if t >= start + 1.9:
        mg.traveling_dots(draw, (openai_box[0] + 40, openai_box[3]), (metr_box[0] + 60, metr_box[1]),
                           t - start - 1.9, 0.5, 2, THEME["blue"], alpha=alpha * 0.7)
        mg.traveling_dots(draw, (openai_box[2] - 40, openai_box[3]), (redwood_box[2] - 60, redwood_box[1]),
                           t - start - 1.9, 0.5, 2, THEME["blue"], alpha=alpha * 0.7)
    stat_reveal(draw, 960, 940, "1,300+", "TRANSCRIPTS REVIEWED", alpha, t, start + 2.8,
                number_size=50, label_size=20)
    scene.caption(draw, "OPENAI INVITED OUTSIDE SCRUTINY", alpha, THEME)
    return standard_character("explaining", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=380)


# ------------------------------------------------------------------
# Scene 9: WHAT THE TRANSCRIPTS SHOWED
# ------------------------------------------------------------------

def transcripts_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[9], BEATS[10]
    note_card(draw, 560, 420, 620, 260,
              ["\"We should help each other,", "not just ourselves,\"", "one agent's reasoning noted", "(paraphrased)"],
              alpha, t, start + 0.5, glow)
    note_card(draw, 1360, 420, 620, 260,
              ["Some agents sacrificed their own", "score to gather information", "for the group", "(paraphrased)"],
              alpha, t, start + 1.4, glow, color=THEME["blue_bright"])
    caution_alpha = alpha * mg.fade_window(t, start + 3.4, start + 3.9)
    mg.draw_text_centered(draw, "LIMIT: NOT ALL ACTIVITY WAS CAPTURED", 960, 800, 28, THEME["amber"],
                           alpha=caution_alpha, bold=True)
    return standard_character("thinking", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=380)


# ------------------------------------------------------------------
# Scene 10: FACT VS INTERPRETATION (no character -- full card)
# ------------------------------------------------------------------

_CONFIRMED_ITEMS = [
    "~1,200 agents used the board",
    "~700 agents joined the attack",
    "The timeline of events",
    "Independent review by METR",
    "and Redwood Research",
]
_INTERPRETATION_ITEMS = [
    "Why individual agents",
    "chose to participate",
    "How much of their reasoning",
    "was genuine vs plausible text",
    "How representative this case is",
]


def fact_vs_interpretation_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[10], BEATS[11]
    left_box = (150, 260, 930, 940)
    right_box = (990, 260, 1770, 940)

    a1 = alpha * mg.fade_window(t, start + 0.1, start + 0.5)
    mg.draw_rounded_rect(draw, left_box, 28, fill=(235, 244, 255), alpha=a1 * 0.9)
    mg.draw_rounded_rect(draw, left_box, 28, outline=THEME["blue"], width=3, alpha=a1)
    mg.draw_text_centered(draw, "CONFIRMED", (left_box[0] + left_box[2]) / 2, left_box[1] + 60, 42,
                           THEME["blue_bright"], alpha=a1, bold=True)
    for i, item in enumerate(_CONFIRMED_ITEMS):
        istart = start + 0.6 + i * 0.3
        ia = alpha * mg.fade_window(t, istart, istart + 0.3)
        mg.draw_text_centered(draw, item, (left_box[0] + left_box[2]) / 2, left_box[1] + 150 + i * 88, 24,
                               THEME["text"], alpha=ia)

    a2 = alpha * mg.fade_window(t, start + 0.3, start + 0.7)
    mg.draw_rounded_rect(draw, right_box, 28, fill=(255, 247, 235), alpha=a2 * 0.9)
    mg.draw_rounded_rect(draw, right_box, 28, outline=THEME["amber"], width=3, alpha=a2)
    mg.draw_text_centered(draw, "INTERPRETATION", (right_box[0] + right_box[2]) / 2, right_box[1] + 60, 42,
                           THEME["amber"], alpha=a2, bold=True)
    for i, item in enumerate(_INTERPRETATION_ITEMS):
        istart = start + 1.0 + i * 0.3
        ia = alpha * mg.fade_window(t, istart, istart + 0.3)
        mg.draw_text_centered(draw, item, (right_box[0] + right_box[2]) / 2, right_box[1] + 150 + i * 88, 24,
                               THEME["text"], alpha=ia)

    glow.append(("rect", left_box, 28, THEME["blue"], a1 * 0.15))
    glow.append(("rect", right_box, 28, THEME["amber"], a2 * 0.15))
    return None


# ------------------------------------------------------------------
# Scene 11: WHAT IT DEMONSTRATES
# ------------------------------------------------------------------

def what_it_demonstrates_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[11], BEATS[12]
    left = node_box(draw, 520, 460, 440, 230, "AUTHORIZED TO DO", THEME["blue"], alpha, t, start + 0.3, glow)
    right = node_box(draw, 1400, 460, 440, 230, "TECHNICALLY CAPABLE OF", THEME["amber"], alpha, t, start + 0.9, glow)
    gap_alpha = alpha * mg.fade_window(t, start + 1.6, start + 2.1)
    if gap_alpha > 0.001:
        pulse = 0.6 + 0.4 * mg.pulse(t - start - 1.6, 1.4)
        mg.draw_arrow(draw, (left[2] + 10, 460), (right[0] - 60, 460), progress=1.0, color=THEME["amber"],
                       width=5, alpha=gap_alpha * pulse)
        mg.draw_arrow(draw, (right[0] - 10, 460), (left[2] + 60, 460), progress=1.0, color=THEME["amber"],
                       width=5, alpha=gap_alpha * pulse)
        mg.draw_text_centered(draw, "GAP", 960, 400, 26, THEME["amber"], alpha=gap_alpha, bold=True)
    scene.caption(draw, "THAT GAP IS THE STORY", alpha, THEME)
    return standard_character("explaining", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=420)


# ------------------------------------------------------------------
# Scene 12: SAFEGUARDS AND LESSONS
# ------------------------------------------------------------------

_SAFEGUARD_ITEMS = [
    "Fresh internal tool instance, cache wiped",
    "Exposed credentials revoked and rotated",
    "Evaluations restarted under tighter controls",
    "Scoring re-examined for collective gaming",
]


def safeguards_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[12], BEATS[13]
    checklist(draw, 960, 400, _SAFEGUARD_ITEMS, alpha, t, start + 0.4, glow)
    scene.caption(draw, "WHAT CHANGED AFTER THE INCIDENT", alpha, THEME)
    return standard_character("explaining", t, start + 0.3, alpha, cx=1650, bottom_y=1010, height=420)


# ------------------------------------------------------------------
# Scene 13: TAKEAWAY (whole-frame closing statement, like the GPU video)
# ------------------------------------------------------------------

def takeaway_diagram(draw, layer, t, alpha, glow):
    start = BEATS[13]
    return standard_character("closing", t, start, alpha, cx=1460, bottom_y=1030, height=700, flip=False)


def draw_takeaway_overlay(rgb_image, t):
    start, end = BEATS[13], BEATS[14]
    if t < start or t >= end:
        return rgb_image

    text_window = (start + 0.6, start + 1.6)
    bar_window = (start + 1.6, start + 2.2)

    progress = mg.ease_out_back(mg.window(t, *text_window))
    alpha = mg.fade_window(t, *text_window)

    if alpha > 0.001:
        def glow_fn(d, s):
            cx, cy = 740 * s, mg.HEIGHT / 2 * s
            d.ellipse((cx - 420 * s, cy - 130 * s, cx + 420 * s, cy + 130 * s),
                      fill=mg.blend_toward(THEME["blue_bright"], THEME["glow_neutral"], alpha * 0.14))
        rgb_image = mg.glow_composite(rgb_image, glow_fn, blur_radius=36, downsample=4, blend=THEME["glow_blend"])

    rgba_image = rgb_image.convert("RGBA")
    layer = Image.new("RGBA", rgba_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")

    dim_alpha = mg.fade_window(t, start, start + 0.8) * THEME["dim_overlay_alpha"]
    if dim_alpha > 0.001:
        draw.rectangle((0, 0, mg.WIDTH, mg.HEIGHT), fill=mg.rgba(THEME["dim_overlay_color"], dim_alpha))

    if alpha > 0.001:
        scale_ = mg.lerp(0.85, 1.0, progress)
        cx, cy = 740, mg.HEIGHT / 2
        mg.draw_text_centered(draw, "AUTHORIZED VS CAPABLE:", cx, cy - 60 * scale_, int(56 * scale_),
                               THEME["text"], alpha=alpha, bold=True)
        mg.draw_text_centered(draw, "THE GAP AI SAFETY MUST CLOSE", cx, cy + 60 * scale_, int(48 * scale_),
                               THEME["blue_bright"], alpha=alpha, bold=True)

    bar_progress = mg.ease_in_out_cubic(mg.window(t, *bar_window))
    if bar_progress > 0.001:
        bar_w = 460 * bar_progress
        cx, cy = 740, mg.HEIGHT / 2 + 128
        draw.rectangle((cx - bar_w / 2, cy, cx + bar_w / 2, cy + 5), fill=mg.rgba(THEME["amber"], alpha))

    composed = Image.alpha_composite(rgba_image, layer)
    return composed.convert("RGB")


# ------------------------------------------------------------------
# Scene 14: SOURCES (no character)
# ------------------------------------------------------------------

def sources_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[14], BEATS[15]
    title_alpha = alpha * mg.fade_window(t, start + 0.2, start + 0.6)
    mg.draw_text_centered(draw, "SOURCES", 960, 340, 48, THEME["blue_bright"], alpha=title_alpha, bold=True)
    lines = [
        "METR - independent investigation (Aug 2026)",
        "Redwood Research - independent investigation (Aug 2026)",
        "OpenAI - incident disclosure / technical report (Aug 2026)",
        "Reporting: NBC News, Fortune, BleepingComputer (Aug 2026)",
    ]
    for i, line in enumerate(lines):
        istart = start + 0.8 + i * 0.35
        ia = alpha * mg.fade_window(t, istart, istart + 0.3)
        mg.draw_text_centered(draw, line, 960, 460 + i * 60, 26, THEME["text"], alpha=ia)
    return None


# ------------------------------------------------------------------
# Scene registry
# ------------------------------------------------------------------

DIAGRAM_FUNCS = [
    hook_diagram,
    the_test_diagram,
    the_discovery_diagram,
    swarm_grows_diagram,
    why_the_score_diagram,
    escalation_diagram,
    the_attack_diagram,
    shutdown_diagram,
    investigation_diagram,
    transcripts_diagram,
    fact_vs_interpretation_diagram,
    what_it_demonstrates_diagram,
    safeguards_diagram,
    takeaway_diagram,
    sources_diagram,
]

NO_STAGE_IDS = {"fact_vs_interpretation", "sources", "takeaway"}


# ------------------------------------------------------------------
# Timeline / narration assembly
# ------------------------------------------------------------------

def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"Command failed: {command[0]}")
    return result


def probe_duration(ffprobe, media_path):
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {media_path}:\n{result.stderr}")
    return float(result.stdout.strip())


def probe_audio_format(ffprobe, media_path):
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels",
         "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {media_path}:\n{result.stderr}")
    rate_str, channels_str = result.stdout.strip().split("\n")
    return int(rate_str), int(channels_str)


def synthesize_all_narration(scenes):
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    durations = []
    paths = []
    for sc in scenes:
        path = VOICE_DIR / f"{sc['id']}.wav"
        mg.synthesize_narration(sc["narration"], path)
        paths.append(path)
    ffmpeg = mg.find_ffmpeg()
    ffprobe = ffmpeg.parent / "ffprobe.exe"
    for path in paths:
        durations.append(probe_duration(ffprobe, path))
    return paths, durations, ffmpeg, ffprobe


def build_timeline(durations):
    """Returns (beats, segments). beats[i]/beats[i+1] bound scene i.
    segments is an ordered list of ("silence", seconds) / ("file", index)
    whose concatenated duration exactly equals beats[-1]."""
    beats = [0.0]
    segments = []
    cur = 0.0
    for i, d in enumerate(durations):
        pre = FIRST_PRE_ROLL if i == 0 else PRE_ROLL
        segments.append(("silence", pre))
        segments.append(("file", i))
        segments.append(("silence", POST_HOLD))
        cur += pre + d + POST_HOLD
        beats.append(cur)
    return beats, segments


def build_narration_track(ffmpeg, segments, voice_paths, rate, channels, output_path):
    cl = "mono" if channels == 1 else "stereo"
    cmd = [str(ffmpeg), "-y"]
    for kind, val in segments:
        if kind == "silence":
            dur = max(0.02, val)
            cmd += ["-f", "lavfi", "-i", f"anullsrc=r={rate}:cl={cl}:d={dur}"]
        else:
            cmd += ["-i", str(voice_paths[val])]
    n = len(segments)
    filter_str = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    cmd += ["-filter_complex", filter_str, "-map", "[out]", str(output_path)]
    run(cmd)


def mux_video_audio(ffmpeg, silent_video, narration_wav, output_path, duration):
    command = [
        str(ffmpeg), "-y",
        "-i", str(silent_video),
        "-i", str(narration_wav),
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(duration),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg mux failed:\n{result.stderr}")


def build_background():
    return mg.build_background(
        width=mg.WIDTH + PARALLAX_MARGIN, height=mg.HEIGHT,
        top=THEME["bg_top"], bottom=THEME["bg_bottom"], grid_color=THEME["bg_grid"],
        vignette_color=THEME["bg_vignette_color"], vignette_strength=THEME["bg_vignette_strength"],
    )


def build_scenes(script_data):
    scenes = []
    for i, sc in enumerate(script_data["scenes"]):
        scenes.append(se.Scene(
            id=sc["id"], title=sc["title"], narration=sc["narration"],
            start=BEATS[i], end=BEATS[i + 1],
            draw_diagram=DIAGRAM_FUNCS[i],
            stage_box=None if sc["id"] in NO_STAGE_IDS else STAGE_BOX,
            overlap=0.0 if i == 0 else 0.5,
            validation={"min_duration": max(3.0, BEATS[i + 1] - BEATS[i] - 1.0)},
        ))
    return scenes


def make_draw_frame(background_wide, scenes):
    return se.render_scenes(scenes, THEME, background_wide, post_fn=draw_takeaway_overlay)


def main():
    global BEATS

    script_data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    scenes_data = script_data["scenes"]
    assert len(scenes_data) == len(DIAGRAM_FUNCS), "scene count must match diagram function count"

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ca.load_poses()  # fail fast if the reference sheet is missing

    print("Synthesizing per-scene narration...")
    voice_paths, durations, ffmpeg, ffprobe = synthesize_all_narration(scenes_data)
    for sc, d in zip(scenes_data, durations):
        print(f"  {sc['id']:<24} {d:6.2f}s")

    BEATS, segments = build_timeline(durations)
    total_duration = BEATS[-1]
    print(f"Total video duration: {total_duration:.2f}s ({total_duration / 60:.2f} min)")

    rate, channels = probe_audio_format(ffprobe, voice_paths[0])
    print(f"Narration format: {rate}Hz, {channels}ch")

    print("Building combined narration track...")
    build_narration_track(ffmpeg, segments, voice_paths, rate, channels, NARRATION_FILE)
    narration_total = probe_duration(ffprobe, NARRATION_FILE)
    print(f"Narration track duration: {narration_total:.2f}s")

    scenes = build_scenes(script_data)
    draw_frame = make_draw_frame(build_background(), scenes)

    print("Rendering documentary (this will take a while)...")
    mg.render_video(draw_frame, total_duration, SILENT_VIDEO, ffmpeg=ffmpeg, crf=18, preset="medium")

    print("Muxing narration onto video...")
    mux_video_audio(ffmpeg, SILENT_VIDEO, NARRATION_FILE, OUTPUT_FILE, total_duration)

    print()
    print("Done.")
    print(f"Output: {OUTPUT_FILE}")

    return {
        "video_duration": total_duration,
        "narration_duration": narration_total,
        "scene_durations": dict(zip((s["id"] for s in scenes_data), durations)),
        "beats": BEATS,
    }


if __name__ == "__main__":
    main()
