"""Character-led GPU explainer proof, on the reusable scene engine.

TASK-009 built this as 6 bespoke beat functions with hand-wired cross-
fade/transition/character logic duplicated in each one. TASK-010 (this
revision) converts that into `scene_engine.Scene` data objects run by
a single shared `scene_engine.render_scenes()` — the diagram content
per scene is unchanged (same visuals, same timings), but the plumbing
around it (fade timing, transition sweep, glow pass, "only the active
scene's character is drawn") is now centralized, so the remaining
full-video scenes can be added as new Scene entries instead of new
copies of that plumbing.

Regression fix found while converting: TASK-009's takeaway character
was composited as a special case *in addition to* whichever beat
function's character was still fading out, so for ~0.5s two character
poses rendered superimposed during the SCALE->TAKEAWAY cross-fade. On
the scene engine, TAKEAWAY is just the last Scene in the list, so its
character naturally wins once its alpha is non-zero -- verified fixed,
see TASK-010 status validation.

Output: C:\\YT-Automation\\output\\gpu_character_proof.mp4
"""

from pathlib import Path
from PIL import Image, ImageDraw
import subprocess
import re

import sys
sys.path.insert(0, str(Path(__file__).parent))

import motion_graphics as mg
import create_poc_scene as scene
import character_assets as ca
import scene_engine as se

BASE_DIR = Path(r"C:\YT-Automation")
SCRIPT_FILE = BASE_DIR / "content" / "gpu_character_proof_script.txt"
TEMP_DIR = BASE_DIR / "temp" / "character_proof"
VOICE_FILE = BASE_DIR / "output" / "gpu_character_proof_voice.wav"
SILENT_VIDEO = TEMP_DIR / "silent.mp4"
OUTPUT_FILE = BASE_DIR / "output" / "gpu_character_proof.mp4"

THEME = scene.LIGHT_THEME
CPU_COLOR = (95, 105, 125)

# HOOK, CPU_VS_GPU, PARALLEL, GPU_AI, SCALE, TAKEAWAY
BEATS = [0.0, 9.0, 20.0, 31.0, 42.0, 51.0, 60.0]
MIN_DURATION = 55.0
MAX_DURATION = 65.0
OUTRO_HOLD = 1.5

PARALLAX_MARGIN = 220
STAGE_BOX = (110, 140, 1830, 1010)

beat_progress = se.beat_progress
safe_character = se.safe_character


def hand_connector(draw, pose, cx, bottom_y, height, flip, target, t, grow_start, grow_end, alpha):
    se.hand_connector(draw, THEME, pose, cx, bottom_y, height, flip, target, t, grow_start, grow_end, alpha)


def core_grid(draw, cx, cy, w, h, rows, cols, label, alpha, t, build_start, glow,
              stagger=0.05, color=None, label_size=22):
    color = color or THEME["blue"]
    hw, hh = w / 2, h / 2
    box = (cx - hw, cy - hh, cx + hw, cy + hh)

    box_alpha = alpha * mg.fade_window(t, build_start, build_start + 0.3)
    mg.draw_rounded_rect(draw, box, 16, outline=color, width=4, alpha=box_alpha)
    mg.draw_text_centered(draw, label, cx, cy - hh + label_size + 2, label_size,
                           THEME["text"], alpha=box_alpha, bold=True)

    if rows * cols > 1:
        pad = 16
        top = cy - hh + label_size * 2
        cell_w = (w - pad * 2) / cols
        cell_h = (hh * 2 - label_size * 2 - pad) / rows

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                cstart = build_start + 0.3 + idx * stagger
                born_alpha = mg.fade_window(t, cstart, cstart + 0.3)
                if born_alpha <= 0.001:
                    continue
                cprog = mg.ease_out_back(mg.window(t, cstart, cstart + 0.3))
                lit = mg.pulse(max(0.0, t - cstart - 0.3) * 1.3 + idx * 0.05, 1.6) if t > cstart + 0.3 else 0.0
                cell_scale = mg.lerp(0.3, 1.0, cprog)
                base_w, base_h = cell_w - 5, cell_h - 5
                cw, ch = base_w * cell_scale, base_h * cell_scale
                x0 = cx - hw + pad + c * cell_w + (base_w - cw) / 2
                y0 = top + r * cell_h + (base_h - ch) / 2
                mg.draw_rounded_rect(draw, (x0, y0, x0 + cw, y0 + ch), 3, outline=color, width=1,
                                      fill=color, alpha=alpha * born_alpha * (0.15 + 0.5 * lit))

    glow.append(("rect", box, 16, color, box_alpha * 0.2))
    return box


# ------------------------------------------------------------------
# Scene 1: HOOK
# ------------------------------------------------------------------

def hook_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[0], BEATS[1]

    title_alpha = mg.fade_window(t, start + 0.2, start + 0.5, end - 0.6, end)
    p1 = mg.ease_out_cubic(mg.window(t, start + 0.3, start + 1.3))
    p2 = mg.ease_out_cubic(mg.window(t, start + 0.8, start + 1.9))
    mg.text_reveal(layer, "WHY DOES AI NEED", 640, 430, 58, THEME["text"], p1, alpha=title_alpha, bold=True)
    mg.text_reveal(layer, "SO MANY GPUS?", 640, 510, 58, THEME["blue_bright"], p2, alpha=title_alpha, bold=True)

    prog = beat_progress(t, start, 1.0)
    char_y = mg.lerp(1150, 1000, prog)
    return safe_character("introg", 1300, char_y, int(mg.lerp(600, 660, prog)), alpha)


# ------------------------------------------------------------------
# Scene 2: CPU VS GPU
# ------------------------------------------------------------------

def cpu_vs_gpu_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[1], BEATS[2]

    cam_p = mg.ease_in_out_cubic(mg.window(t, start + 5.5, start + 8.0))
    cam = mg.Camera(anchor=(1080, 560), scale=mg.lerp(1.0, 1.07, cam_p))

    core_grid(draw, *cam.xy(430, 560), cam.wh(300), cam.wh(300), 2, 2,
              "CPU", alpha, t, start + 0.3, glow, stagger=0.35, color=CPU_COLOR)
    gpu_box = core_grid(draw, *cam.xy(1080, 560), cam.wh(420), cam.wh(300), 4, 8,
                         "GPU", alpha, t, start + 1.6, glow, stagger=0.045)

    vs_alpha = alpha * mg.fade_window(t, start + 1.0, start + 1.5)
    mg.draw_text_centered(draw, "VS", *cam.xy(755, 560), 34, THEME["dim_text"], alpha=vs_alpha, bold=True)

    scene.caption(draw, "CPU: FEW CORES  -  GPU: THOUSANDS OF CORES", alpha, THEME)

    prog = beat_progress(t, start, 0.9)
    char = safe_character("explaining", mg.lerp(2000, 1660, prog), 1010, 520, alpha, flip=True)
    _, ccx, cby, ch, calpha, cflip = char
    hand_connector(draw, "explaining", ccx, cby, ch, True, (gpu_box[2] - 20, (gpu_box[1] + gpu_box[3]) / 2),
                    t, start + 2.4, start + 3.0, alpha)
    return char


# ------------------------------------------------------------------
# Scene 3: PARALLEL PROCESSING
# ------------------------------------------------------------------

def parallel_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[2], BEATS[3]

    data_box = (250, 500, 430, 620)
    data_alpha = alpha * mg.fade_window(t, start + 0.2, start + 0.6)
    mg.draw_rounded_rect(draw, data_box, 14, outline=THEME["blue"], width=4, alpha=data_alpha)
    mg.draw_text_centered(draw, "DATA", 340, 560, 24, THEME["text"], alpha=data_alpha, bold=True)
    glow.append(("rect", data_box, 14, THEME["blue"], data_alpha * 0.2))

    core_grid(draw, 1180, 560, 520, 380, 4, 8, "GPU CORES", alpha, t, start + 0.9, glow, stagger=0.04)

    targets_y = [430, 490, 560, 630, 690]
    for i, ty in enumerate(targets_y):
        stream_start = start + 1.8 + i * 0.1
        if t >= stream_start:
            mg.traveling_dots(draw, (430, 560), (960, ty), t - stream_start, 0.55, 3,
                               THEME["blue_bright"], radius=4, alpha=alpha * 0.7, phase_offset=i * 0.17)

    scene.caption(draw, "THOUSANDS OF OPERATIONS AT ONCE", alpha, THEME)

    prog = beat_progress(t, start, 0.9)
    return safe_character("thinking", mg.lerp(-100, 300, prog), 995, 300, alpha)


# ------------------------------------------------------------------
# Scene 4: GPU + AI
# ------------------------------------------------------------------

def gpu_ai_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[3], BEATS[4]

    pan_p = mg.ease_in_out_cubic(mg.window(t, start + 1.0, start + 7.0))
    cam = mg.Camera(anchor=(mg.lerp(500, 1350, pan_p), 560), scale=1.03)

    data_c = cam.xy(280, 560)
    gpu_c = cam.xy(760, 560)
    model_c = cam.xy(1300, 560)

    pipe_alpha = alpha * mg.fade_window(t, start + 0.3, start + 0.9)
    pipe_box = (data_c[0], gpu_c[1] - cam.wh(18), model_c[0], gpu_c[1] + cam.wh(18))
    mg.draw_rounded_rect(draw, pipe_box, cam.wh(18), fill=THEME["blue"], alpha=pipe_alpha * 0.12)

    d_alpha = alpha * mg.fade_window(t, start + 0.3, start + 0.7)
    d_box = (data_c[0] - cam.wh(90), data_c[1] - cam.wh(60), data_c[0] + cam.wh(90), data_c[1] + cam.wh(60))
    mg.draw_rounded_rect(draw, d_box, cam.wh(14), outline=THEME["blue"], width=3, alpha=d_alpha)
    mg.draw_text_centered(draw, "DATA", *data_c, 22, THEME["text"], alpha=d_alpha, bold=True)
    glow.append(("rect", d_box, 14, THEME["blue"], d_alpha * 0.2))

    gpu_box = core_grid(draw, gpu_c[0], gpu_c[1], cam.wh(260), cam.wh(220), 3, 4, "GPU",
                         alpha, t, start + 1.2, glow, stagger=0.06, label_size=18)

    m_alpha = alpha * mg.fade_window(t, start + 3.4, start + 3.9)
    m_box = (model_c[0] - cam.wh(120), model_c[1] - cam.wh(90), model_c[0] + cam.wh(120), model_c[1] + cam.wh(90))
    mg.draw_rounded_rect(draw, m_box, cam.wh(18), outline=THEME["blue_bright"], width=5, alpha=m_alpha)
    mg.draw_text_centered(draw, "AI MODEL", *model_c, 22, THEME["text"], alpha=m_alpha, bold=True)
    glow.append(("rect", m_box, 18, THEME["blue_bright"], m_alpha * 0.3))

    if t >= start + 1.0:
        mg.traveling_dots(draw, (d_box[2], data_c[1]), (gpu_box[0], gpu_c[1]),
                           t - start - 1.0, 0.6, 3, THEME["blue"], radius=4, alpha=alpha * 0.7)
    if t >= start + 3.9:
        mg.traveling_dots(draw, (gpu_box[2], gpu_c[1]), (m_box[0], model_c[1]),
                           t - start - 3.9, 0.6, 3, THEME["blue_bright"], radius=4, alpha=alpha * 0.7)

    scene.caption(draw, "ONE CONNECTED PIPELINE POWERS THE MODEL", alpha, THEME)

    prog = beat_progress(t, start, 0.9)
    char = safe_character("explaining", 1650, mg.lerp(1150, 1010, prog), 440, alpha, flip=True)
    _, ccx, cby, ch, calpha, cflip = char
    active_target = (gpu_c[0], gpu_c[1] - cam.wh(130)) if t < start + 6.0 else (model_c[0], model_c[1] - cam.wh(110))
    hand_connector(draw, "explaining", ccx, cby, ch, True, active_target, t, start + 2.0, start + 2.6, alpha)
    return char


# ------------------------------------------------------------------
# Scene 5: SCALE
# ------------------------------------------------------------------

_SCALE_ANCHOR = (860, 590)
_SCALE_GRID = [
    (c * 260 - 1.5 * 260, r * 180 - 1.5 * 180)
    for r in range(4) for c in range(4)
]
_SCALE_POSITIONS = sorted(_SCALE_GRID, key=lambda p: p[0] ** 2 + p[1] ** 2)
_SCALE_REVEAL_TIMES = [0.4 + i * 0.19 for i in range(len(_SCALE_POSITIONS))]


def scale_diagram(draw, layer, t, alpha, glow):
    start, end = BEATS[4], BEATS[5]

    zoom_p = mg.ease_in_out_cubic(mg.window(t, start + 1.0, start + 6.0))
    cam = mg.Camera(anchor=_SCALE_ANCHOR, scale=mg.lerp(1.0, 0.88, zoom_p))

    ax, ay = _SCALE_ANCHOR
    for i, (ox, oy) in enumerate(_SCALE_POSITIONS):
        reveal_t = start + _SCALE_REVEAL_TIMES[i]
        born = mg.fade_window(t, reveal_t, reveal_t + 0.3)
        if born <= 0.001:
            continue
        prog = mg.ease_out_back(mg.window(t, reveal_t, reveal_t + 0.35))
        gx, gy = cam.xy(ax + ox, ay + oy)
        size = cam.wh(150 * mg.lerp(0.4, 1.0, prog))
        box = (gx - size / 2, gy - size / 2.4, gx + size / 2, gy + size / 2.4)
        a = alpha * born
        mg.draw_rounded_rect(draw, box, 10, outline=THEME["blue"], width=3, alpha=a)
        if size > 60:
            mg.draw_text_centered(draw, "GPU", gx, gy, max(10, int(size * 0.14)), THEME["text"], alpha=a, bold=True)
        glow.append(("rect", box, 10, THEME["blue"], a * 0.16))

    scene.caption(draw, "GPU POWER MULTIPLIES ACROSS THE CLUSTER", alpha, THEME)

    prog = beat_progress(t, start, 0.9)
    return safe_character("introg", mg.lerp(2000, 1690, prog), 990, 380, alpha, flip=True)


# ------------------------------------------------------------------
# Scene 6: TAKEAWAY
# ------------------------------------------------------------------

def takeaway_diagram(draw, layer, t, alpha, glow):
    """No diagram content -- the closing statement is a whole-frame
    post_fn effect (dim + text + bar), applied after character
    compositing. This scene only supplies the closing character, so it
    participates in the same cross-fade/"last wins" character logic as
    every other scene (this is what fixes the TASK-009 double-character
    bug at the SCALE->TAKEAWAY boundary)."""
    start = BEATS[5]
    prog = beat_progress(t, start)
    return safe_character("closing", 1460, mg.lerp(1160, 1030, prog), int(mg.lerp(680, 720, prog)), alpha)


def draw_takeaway_overlay(rgb_image, t):
    start, end = BEATS[5], BEATS[6]
    if t < start:
        return rgb_image

    text_window = (start + 0.6, start + 1.6)
    bar_window = (start + 1.6, start + 2.2)

    progress = mg.ease_out_back(mg.window(t, *text_window))
    alpha = mg.fade_window(t, *text_window)

    if alpha > 0.001:
        def glow_fn(d, s):
            cx, cy = 740 * s, mg.HEIGHT / 2 * s
            d.ellipse((cx - 400 * s, cy - 130 * s, cx + 400 * s, cy + 130 * s),
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
        mg.draw_text_centered(draw, "AI NEEDS MASSIVE", cx, cy - 60 * scale_, int(62 * scale_),
                               THEME["text"], alpha=alpha, bold=True)
        mg.draw_text_centered(draw, "PARALLEL COMPUTING", cx, cy + 60 * scale_, int(62 * scale_),
                               THEME["blue_bright"], alpha=alpha, bold=True)

    bar_progress = mg.ease_in_out_cubic(mg.window(t, *bar_window))
    if bar_progress > 0.001:
        bar_w = 420 * bar_progress
        cx, cy = 740, mg.HEIGHT / 2 + 128
        draw.rectangle((cx - bar_w / 2, cy, cx + bar_w / 2, cy + 5), fill=mg.rgba(THEME["amber"], alpha))

    composed = Image.alpha_composite(rgba_image, layer)
    return composed.convert("RGB")


# ------------------------------------------------------------------
# Scene list (the production-scene representation) and render entrypoint
# ------------------------------------------------------------------

SCENES = [
    se.Scene(
        id="hook", title="HOOK", narration="Every modern AI system runs on a huge amount of hardware "
        "behind the scenes. So why does AI need so many GPUs?",
        start=BEATS[0], end=BEATS[1], draw_diagram=hook_diagram, stage_box=STAGE_BOX, overlap=0.0,
        validation={"min_duration": 6.0},
    ),
    se.Scene(
        id="cpu_vs_gpu", title="CPU VS GPU", narration="A CPU handles a handful of tasks with a few "
        "powerful cores. A GPU takes the opposite approach: thousands of simpler cores, built to run "
        "in parallel.",
        start=BEATS[1], end=BEATS[2], draw_diagram=cpu_vs_gpu_diagram, stage_box=STAGE_BOX,
        validation={"min_duration": 8.0},
    ),
    se.Scene(
        id="parallel", title="PARALLEL PROCESSING", narration="Instead of one task at a time, a GPU "
        "splits the work into thousands of pieces and processes them all at once, across every core.",
        start=BEATS[2], end=BEATS[3], draw_diagram=parallel_diagram, stage_box=STAGE_BOX,
        validation={"min_duration": 8.0},
    ),
    se.Scene(
        id="gpu_ai", title="GPU + AI", narration="That parallel power flows straight into AI. Data "
        "moves through GPU memory and compute cores, feeding the model with results in real time.",
        start=BEATS[3], end=BEATS[4], draw_diagram=gpu_ai_diagram, stage_box=STAGE_BOX,
        validation={"min_duration": 8.0},
    ),
    se.Scene(
        id="scale", title="SCALE", narration="One GPU isn't enough. Real AI systems multiply that "
        "power across dozens, then thousands of GPUs working together.",
        start=BEATS[4], end=BEATS[5], draw_diagram=scale_diagram, stage_box=STAGE_BOX,
        validation={"min_duration": 6.0},
    ),
    se.Scene(
        id="takeaway", title="TAKEAWAY", narration="That is the real reason AI needs massive parallel "
        "computing power.",
        start=BEATS[5], end=BEATS[6], draw_diagram=takeaway_diagram, stage_box=None,
        validation={"min_duration": 6.0},
    ),
]


def make_draw_frame(background_wide, scenes=SCENES):
    return se.render_scenes(scenes, THEME, background_wide, post_fn=draw_takeaway_overlay)


def probe_duration(ffprobe, media_path):
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {media_path}:\n{result.stderr}")
    return float(result.stdout.strip())


def mux_video_audio(ffmpeg, silent_video, voice_wav, output_path, duration):
    command = [
        str(ffmpeg), "-y",
        "-i", str(silent_video),
        "-i", str(voice_wav),
        "-filter_complex", "[1:a]apad[a]",
        "-map", "0:v:0", "-map", "[a]",
        "-t", str(duration),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg mux failed:\n{result.stderr}")


def volume_check(ffmpeg, media_path):
    result = subprocess.run(
        [str(ffmpeg), "-i", str(media_path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    stderr = result.stderr
    mean_match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", stderr)
    max_match = re.search(r"max_volume:\s*(-?[\d.]+) dB", stderr)
    return {
        "mean_volume_db": float(mean_match.group(1)) if mean_match else None,
        "max_volume_db": float(max_match.group(1)) if max_match else None,
    }


def build_background():
    return mg.build_background(
        width=mg.WIDTH + PARALLAX_MARGIN, height=mg.HEIGHT,
        top=THEME["bg_top"], bottom=THEME["bg_bottom"], grid_color=THEME["bg_grid"],
        vignette_color=THEME["bg_vignette_color"], vignette_strength=THEME["bg_vignette_strength"],
    )


def main():
    ffmpeg = mg.find_ffmpeg()
    ffprobe = ffmpeg.parent / "ffprobe.exe"

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "output").mkdir(parents=True, exist_ok=True)

    ca.load_poses()  # fail fast if the reference sheet is missing

    script_text = SCRIPT_FILE.read_text(encoding="utf-8").strip()
    print(f"Narration script: {len(script_text.split())} words")

    print("Synthesizing narration...")
    mg.synthesize_narration(script_text, VOICE_FILE)
    audio_duration = probe_duration(ffprobe, VOICE_FILE)
    print(f"Narration duration: {audio_duration:.2f}s")

    video_duration = max(MIN_DURATION, min(MAX_DURATION, max(BEATS[6], round(audio_duration + OUTRO_HOLD, 1))))
    print(f"Video duration: {video_duration}s")

    draw_frame = make_draw_frame(build_background())

    print("Rendering cinematic character-led scene...")
    mg.render_video(draw_frame, video_duration, SILENT_VIDEO, ffmpeg=ffmpeg, crf=16, preset="medium")

    print("Muxing narration onto video...")
    mux_video_audio(ffmpeg, SILENT_VIDEO, VOICE_FILE, OUTPUT_FILE, video_duration)

    print()
    print("Done.")
    print(f"Output: {OUTPUT_FILE}")

    return {"video_duration": video_duration, "audio_duration": audio_duration}


if __name__ == "__main__":
    main()
