"""Milestone 4 (TASK-008): character-led GPU explainer proof.

Integrates the user-provided character reference sheet
(assets/character/, see character_assets.py) into a 6-beat, ~48-60s
narrated explainer, reusing the light-theme engine from
create_poc_scene.py (THEME system, glow/parallax/caption primitives)
and the narration pipeline from create_light_proof.py. No new drawing
engine, no Pillow-drawn "fake" character -- only the real reference
art, cropped.

Storyboard (per TASK-007), ~8s/beat:
  1. INTRO            0-8s
  2. WHAT IS A GPU     8-16s
  3. CPU VS GPU       16-24s
  4. INSIDE THE GPU   24-32s
  5. AI CONNECTION    32-40s
  6. TAKEAWAY         40-48s (+ outro hold if narration runs long)

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

BASE_DIR = Path(r"C:\YT-Automation")
SCRIPT_FILE = BASE_DIR / "content" / "gpu_character_proof_script.txt"
TEMP_DIR = BASE_DIR / "temp" / "character_proof"
VOICE_FILE = BASE_DIR / "output" / "gpu_character_proof_voice.wav"
SILENT_VIDEO = TEMP_DIR / "silent.mp4"
OUTPUT_FILE = BASE_DIR / "output" / "gpu_character_proof.mp4"

THEME = scene.LIGHT_THEME
CPU_COLOR = (95, 105, 125)

BEATS = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0, 48.0]
MIN_DURATION = 45.0
MAX_DURATION = 60.0
OUTRO_HOLD = 1.5

PARALLAX_MARGIN = 220


def beat_alpha(t, start, end, fade=0.6):
    return mg.fade_window(t, start, start + fade, end - fade, end)


def beat_progress(t, start, dur=0.8):
    return mg.ease_out_back(mg.window(t, start, start + dur))


def core_grid(draw, cx, cy, w, h, rows, cols, label, alpha, t, processing_since, glow, color=None):
    color = color or THEME["blue"]
    hw, hh = w / 2, h / 2
    box = (cx - hw, cy - hh, cx + hw, cy + hh)

    mg.draw_rounded_rect(draw, box, 16, outline=color, width=4, alpha=alpha)
    mg.draw_text_centered(draw, label, cx, cy - hh + 24, 22, THEME["text"], alpha=alpha, bold=True)

    if processing_since is not None and t >= processing_since and rows * cols > 1:
        pad = 16
        top = cy - hh + 44
        cell_w = (w - pad * 2) / cols
        cell_h = (hh * 2 - 44 - pad) / rows
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                lit = mg.pulse((t - processing_since) * 1.3 + idx * 0.08, 1.6)
                x0 = cx - hw + pad + c * cell_w
                y0 = top + r * cell_h
                x1 = x0 + cell_w - 4
                y1 = y0 + cell_h - 4
                mg.draw_rounded_rect(draw, (x0, y0, x1, y1), 3, outline=color, width=1,
                                      fill=color, alpha=alpha * (0.12 + 0.5 * lit))

    glow.append(("rect", box, 16, color, alpha * 0.22))
    return box


def beat_intro(draw, t, glow):
    alpha = beat_alpha(t, *BEATS[0:2])
    if alpha <= 0.001:
        return None
    scene.caption(draw, "WHY DOES AI NEED SO MANY GPUS?", alpha, THEME)
    prog = beat_progress(t, BEATS[0])
    return ("introg", 1350, mg.lerp(1120, 1030, prog), int(mg.lerp(640, 690, prog)), alpha, False)


def beat_what_is_gpu(draw, t, glow):
    alpha = beat_alpha(t, *BEATS[1:3])
    if alpha <= 0.001:
        return None
    prog = beat_progress(t, BEATS[1])
    core_grid(draw, 640, 560, mg.lerp(360, 420, prog), 340, 4, 5, "GPU",
              alpha, t, BEATS[1] + 0.8, glow)
    scene.caption(draw, "A GPU RUNS THOUSANDS OF TASKS AT ONCE", alpha, THEME)
    return ("explaining", 1480, 1000, 560, alpha, True)


def beat_cpu_vs_gpu(draw, t, glow):
    alpha = beat_alpha(t, *BEATS[2:4])
    if alpha <= 0.001:
        return None
    core_grid(draw, 430, 560, 300, 300, 2, 2, "CPU", alpha, t, BEATS[2] + 0.8, glow, color=CPU_COLOR)
    core_grid(draw, 1010, 560, 400, 300, 4, 8, "GPU", alpha, t, BEATS[2] + 1.0, glow, color=THEME["blue"])
    mg.draw_text_centered(draw, "VS", 720, 560, 34, THEME["dim_text"], alpha=alpha, bold=True)
    scene.caption(draw, "CPU: FEW CORES  -  GPU: THOUSANDS OF CORES", alpha, THEME)
    return ("thinking", 1560, 990, 470, alpha, False)


def beat_inside_gpu(draw, t, glow):
    alpha = beat_alpha(t, *BEATS[3:5])
    if alpha <= 0.001:
        return None
    core_grid(draw, 560, 560, 560, 380, 4, 8, "COMPUTE CORES", alpha, t, BEATS[3] + 0.8, glow)
    core_grid(draw, 1130, 560, 240, 380, 1, 1, "MEMORY", alpha, t, None, glow, color=THEME["green"])
    top = (840, 460)
    bot = (1010, 460)
    top2 = (1010, 660)
    bot2 = (840, 660)
    scene.pipeline_arrow(draw, top, bot, t, BEATS[3] + 1.0, BEATS[3] + 1.6, THEME, alpha=alpha, width=4)
    scene.pipeline_arrow(draw, top2, bot2, t, BEATS[3] + 1.3, BEATS[3] + 1.9, THEME, alpha=alpha, width=4)
    scene.caption(draw, "CORES + MEMORY WORK TOGETHER", alpha, THEME)
    return ("introg", 1620, 980, 460, alpha, False)


def beat_ai_connection(draw, t, glow):
    alpha = beat_alpha(t, *BEATS[4:6])
    if alpha <= 0.001:
        return None
    start = BEATS[4]

    data_box = (150, 500, 340, 620)
    mg.draw_rounded_rect(draw, data_box, 14, outline=THEME["blue"], width=4, alpha=alpha)
    mg.draw_text_centered(draw, "DATA", 245, 560, 26, THEME["text"], alpha=alpha, bold=True)
    glow.append(("rect", data_box, 14, THEME["blue"], alpha * 0.22))

    gpu_centers = [(560, 460), (560, 660), (760, 560)]
    for i, (gcx, gcy) in enumerate(gpu_centers):
        gbox = (gcx - 80, gcy - 65, gcx + 80, gcy + 65)
        mg.draw_rounded_rect(draw, gbox, 12, outline=THEME["blue"], width=3, alpha=alpha)
        mg.draw_text_centered(draw, f"GPU {i + 1}", gcx, gcy, 18, THEME["text"], alpha=alpha, bold=True)
        glow.append(("rect", gbox, 12, THEME["blue"], alpha * 0.18))
        scene.pipeline_arrow(draw, (340, 560), (gcx - 80, gcy), t, start + 0.6 + i * 0.15,
                              start + 1.1 + i * 0.15, THEME, alpha=alpha, width=3)
        scene.pipeline_arrow(draw, (gcx + 80, gcy), (1080, 560), t, start + 1.4 + i * 0.15,
                              start + 1.9 + i * 0.15, THEME, alpha=alpha, width=3)

    model_box = (1080, 470, 1320, 650)
    mg.draw_rounded_rect(draw, model_box, 18, outline=THEME["blue_bright"], width=5, alpha=alpha)
    mg.draw_text_centered(draw, "AI MODEL", 1200, 560, 26, THEME["text"], alpha=alpha, bold=True)
    glow.append(("rect", model_box, 18, THEME["blue_bright"], alpha * 0.3))

    scene.caption(draw, "GPUS WORK TOGETHER TO POWER AI", alpha, THEME)
    return ("explaining", 1650, 970, 430, alpha, False)


BEAT_FUNCS = [beat_intro, beat_what_is_gpu, beat_cpu_vs_gpu, beat_inside_gpu, beat_ai_connection]


def draw_takeaway(rgb_image, t):
    start, end = BEATS[5], BEATS[6]
    text_window = (start + 0.6, start + 1.6)
    bar_window = (start + 1.6, start + 2.2)

    progress = mg.ease_out_back(mg.window(t, *text_window))
    alpha = mg.fade_window(t, *text_window)

    if alpha > 0.001:
        def glow_fn(d, s):
            cx, cy = 780 * s, mg.HEIGHT / 2 * s
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
        scale = mg.lerp(0.85, 1.0, progress)
        cx, cy = 780, mg.HEIGHT / 2
        mg.draw_text_centered(draw, "AI NEEDS MASSIVE", cx, cy - 60 * scale, int(64 * scale),
                               THEME["text"], alpha=alpha, bold=True)
        mg.draw_text_centered(draw, "PARALLEL COMPUTING", cx, cy + 60 * scale, int(64 * scale),
                               THEME["blue_bright"], alpha=alpha, bold=True)

    bar_progress = mg.ease_in_out_cubic(mg.window(t, *bar_window))
    if bar_progress > 0.001:
        bar_w = 440 * bar_progress
        cx, cy = 780, mg.HEIGHT / 2 + 130
        draw.rectangle((cx - bar_w / 2, cy, cx + bar_w / 2, cy + 5), fill=mg.rgba(THEME["amber"], alpha))

    composed = Image.alpha_composite(rgba_image, layer)
    return composed.convert("RGB"), alpha


def compute_zoom(t, total_duration):
    return mg.lerp(1.0, 1.05, min(1.0, t / max(1.0, BEATS[6])))


def make_draw_frame(background_wide):
    def draw_frame(t, frame_index, total_frames):
        base = mg.parallax_crop(background_wide, t, mg.WIDTH, mg.HEIGHT).convert("RGBA")
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")

        glow_sources = []
        char_call = None
        for fn in BEAT_FUNCS:
            result = fn(draw, t, glow_sources)
            if result is not None:
                char_call = result

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
                                         outline=mg.blend_toward(color, THEME["glow_neutral"], min(1.0, a)),
                                         width=width)
            rgb = mg.glow_composite(rgb, glow_fn, blur_radius=12, downsample=3, blend=THEME["glow_blend"])

        rgba = rgb.convert("RGBA")
        if char_call is not None:
            pose, cx, bottom_y, height, alpha, flip = char_call
            ca.paste_character(rgba, pose, cx, bottom_y, height, alpha=alpha, flip=flip)

        # Takeaway character (independent of the diagram beats above).
        takeaway_alpha = mg.fade_window(t, BEATS[5], BEATS[5] + 0.7)
        if takeaway_alpha > 0.001:
            prog = beat_progress(t, BEATS[5])
            ca.paste_character(rgba, "closing", 1500, mg.lerp(1150, 1040, prog),
                                int(mg.lerp(680, 720, prog)), alpha=takeaway_alpha)

        rgb = rgba.convert("RGB")

        zoom = compute_zoom(t, BEATS[6])
        rgb = mg.apply_zoom(rgb, zoom, focus=(0.5, 0.46))

        if t >= BEATS[5]:
            rgb, _ = draw_takeaway(rgb, t)

        return rgb

    return draw_frame


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

    background_wide = mg.build_background(
        width=mg.WIDTH + PARALLAX_MARGIN, height=mg.HEIGHT,
        top=THEME["bg_top"], bottom=THEME["bg_bottom"], grid_color=THEME["bg_grid"],
        vignette_color=THEME["bg_vignette_color"], vignette_strength=THEME["bg_vignette_strength"],
    )
    draw_frame = make_draw_frame(background_wide)

    print("Rendering character-led scene...")
    mg.render_video(draw_frame, video_duration, SILENT_VIDEO, ffmpeg=ffmpeg, crf=16, preset="medium")

    print("Muxing narration onto video...")
    mux_video_audio(ffmpeg, SILENT_VIDEO, VOICE_FILE, OUTPUT_FILE, video_duration)

    print()
    print("Done.")
    print(f"Output: {OUTPUT_FILE}")

    return {"video_duration": video_duration, "audio_duration": audio_duration}


if __name__ == "__main__":
    main()
