"""TASK-011: full production video build.

The first complete GPU/AI explainer, built entirely on the TASK-010
scene engine (src/scene_engine.py) and reusing the diagram helpers
already proven in the TASK-009 proof (src/create_character_proof.py)
rather than reimplementing them. No new rendering engine.

Story source of truth: content/gpu_story.txt and
content/gpu_story_scenes.json (the project's existing 9-scene
narrative, target ~165s) were adapted into per-scene narration
segments in content/gpu_explainer_script.json -- this closes the
TASK-010 architectural gap ("narration must be associated with
scene/beat segments rather than one undifferentiated blob"): each
scene synthesizes its own narration clip, and the video's timing is
derived from those 9 measured clip durations, not a single global
script.

Output: C:\\YT-Automation\\output\\gpu_explainer_final.mp4
"""

from pathlib import Path
from PIL import Image, ImageDraw
import json
import subprocess
import re

import sys
sys.path.insert(0, str(Path(__file__).parent))

import motion_graphics as mg
import create_poc_scene as scene
import character_assets as ca
import scene_engine as se
from create_character_proof import core_grid, hand_connector, CPU_COLOR, THEME, PARALLAX_MARGIN, build_background

BASE_DIR = Path(r"C:\YT-Automation")
SCRIPT_JSON = BASE_DIR / "content" / "gpu_explainer_script.json"
TEMP_DIR = BASE_DIR / "temp" / "gpu_explainer"
VOICE_DIR = TEMP_DIR / "voices"
COMBINED_VOICE = TEMP_DIR / "combined_voice.wav"
SILENT_VIDEO = TEMP_DIR / "silent.mp4"
OUTPUT_FILE = BASE_DIR / "output" / "gpu_explainer_final.mp4"

STAGE_BOX = (110, 140, 1830, 1010)
LEAD_IN = 0.4     # seconds of visual entrance before narration starts
TAIL = 1.1        # seconds held after narration ends before the next scene
OUTRO_HOLD = 1.6

beat_progress = se.beat_progress
safe_character = se.safe_character


# ------------------------------------------------------------------
# Per-scene diagram content (reuses core_grid / hand_connector / Camera
# / text_reveal / caption -- all existing engine primitives)
# ------------------------------------------------------------------

def title_reveal_2line(layer, lines, cx, cy, size, colors, t, start, alpha):
    p1 = mg.ease_out_cubic(mg.window(t, start + 0.3, start + 1.3))
    mg.text_reveal(layer, lines[0], cx, cy - (size + 12) / 2 if len(lines) > 1 else cy,
                    size, colors[0], p1, alpha=alpha, bold=True)
    if len(lines) > 1:
        p2 = mg.ease_out_cubic(mg.window(t, start + 0.8, start + 1.9))
        mg.text_reveal(layer, lines[1], cx, cy + (size + 12) / 2, size,
                        colors[1] if len(colors) > 1 else colors[0], p2, alpha=alpha, bold=True)


def make_hook(sc_start, sc_end, title_lines):
    def diagram(draw, layer, t, alpha, glow):
        title_alpha = mg.fade_window(t, sc_start + 0.2, sc_start + 0.5, sc_end - 0.6, sc_end)
        title_reveal_2line(layer, title_lines, 640, 470, 58, [THEME["text"], THEME["blue_bright"]],
                            t, sc_start, title_alpha)
        prog = beat_progress(t, sc_start, 1.0)
        char_y = mg.lerp(1150, 1000, prog)
        return safe_character("introg", 1300, char_y, int(mg.lerp(600, 660, prog)), alpha)
    return diagram


def make_why_gpus(sc_start, sc_end, caption_text):
    def diagram(draw, layer, t, alpha, glow):
        box = core_grid(draw, 620, 560, 480, 400, 5, 7, "AI MODEL", alpha, t, sc_start + 0.4, glow,
                         stagger=0.03)
        scene.caption(draw, caption_text, alpha, THEME)
        prog = beat_progress(t, sc_start, 0.9)
        char = safe_character("explaining", mg.lerp(2000, 1640, prog), 1010, 500, alpha, flip=True)
        _, ccx, cby, ch, calpha, cflip = char
        hand_connector(draw, "explaining", ccx, cby, ch, True, (box[2] - 20, (box[1] + box[3]) / 2),
                        t, sc_start + 2.0, sc_start + 2.6, alpha)
        return char
    return diagram


def make_cpu_vs_gpu(sc_start, sc_end, caption_text):
    def diagram(draw, layer, t, alpha, glow):
        cam_p = mg.ease_in_out_cubic(mg.window(t, sc_start + 5.0, sc_start + 7.5))
        cam = mg.Camera(anchor=(1080, 560), scale=mg.lerp(1.0, 1.07, cam_p))
        core_grid(draw, *cam.xy(430, 560), cam.wh(300), cam.wh(300), 2, 2, "CPU", alpha, t,
                  sc_start + 0.3, glow, stagger=0.35, color=CPU_COLOR)
        gpu_box = core_grid(draw, *cam.xy(1080, 560), cam.wh(420), cam.wh(300), 4, 8, "GPU", alpha, t,
                             sc_start + 1.6, glow, stagger=0.045)
        vs_alpha = alpha * mg.fade_window(t, sc_start + 1.0, sc_start + 1.5)
        mg.draw_text_centered(draw, "VS", *cam.xy(755, 560), 34, THEME["dim_text"], alpha=vs_alpha, bold=True)
        scene.caption(draw, caption_text, alpha, THEME)
        prog = beat_progress(t, sc_start, 0.9)
        char = safe_character("explaining", mg.lerp(2000, 1660, prog), 1010, 520, alpha, flip=True)
        _, ccx, cby, ch, calpha, cflip = char
        hand_connector(draw, "explaining", ccx, cby, ch, True,
                        (gpu_box[2] - 20, (gpu_box[1] + gpu_box[3]) / 2),
                        t, sc_start + 2.4, sc_start + 3.0, alpha)
        return char
    return diagram


def make_parallelism(sc_start, sc_end, caption_text):
    def diagram(draw, layer, t, alpha, glow):
        data_box = (250, 500, 430, 620)
        data_alpha = alpha * mg.fade_window(t, sc_start + 0.2, sc_start + 0.6)
        mg.draw_rounded_rect(draw, data_box, 14, outline=THEME["blue"], width=4, alpha=data_alpha)
        mg.draw_text_centered(draw, "TASK", 340, 560, 24, THEME["text"], alpha=data_alpha, bold=True)
        glow.append(("rect", data_box, 14, THEME["blue"], data_alpha * 0.2))
        core_grid(draw, 1180, 560, 520, 380, 4, 8, "GPU CORES", alpha, t, sc_start + 0.9, glow, stagger=0.04)
        targets_y = [430, 490, 560, 630, 690]
        for i, ty in enumerate(targets_y):
            stream_start = sc_start + 1.8 + i * 0.1
            if t >= stream_start:
                mg.traveling_dots(draw, (430, 560), (960, ty), t - stream_start, 0.55, 3,
                                   THEME["blue_bright"], radius=4, alpha=alpha * 0.7, phase_offset=i * 0.17)
        scene.caption(draw, caption_text, alpha, THEME)
        prog = beat_progress(t, sc_start, 0.9)
        return safe_character("thinking", mg.lerp(-100, 300, prog), 995, 300, alpha)
    return diagram


def make_memory_bandwidth(sc_start, sc_end, caption_text):
    def diagram(draw, layer, t, alpha, glow):
        gpu_box = core_grid(draw, 560, 560, 560, 380, 4, 8, "COMPUTE CORES", alpha, t, sc_start + 0.4, glow)
        mem_box = core_grid(draw, 1130, 560, 240, 380, 1, 1, "MEMORY", alpha, t, sc_start + 0.4, glow, color=THEME["green"])
        top1, bot1 = (840, 460), (1010, 460)
        top2, bot2 = (1010, 660), (840, 660)
        scene.pipeline_arrow(draw, top1, bot1, t, sc_start + 1.0, sc_start + 1.6, THEME, alpha=alpha, width=4)
        scene.pipeline_arrow(draw, top2, bot2, t, sc_start + 1.3, sc_start + 1.9, THEME, alpha=alpha, width=4)
        scene.caption(draw, caption_text, alpha, THEME)
        prog = beat_progress(t, sc_start, 0.9)
        return safe_character("introg", 1620, 980, 460, alpha)
    return diagram


def make_clusters(sc_start, sc_end, caption_text):
    anchor = (860, 590)
    grid = sorted(
        [(c * 260 - 1.5 * 260, r * 180 - 1.5 * 180) for r in range(4) for c in range(4)],
        key=lambda p: p[0] ** 2 + p[1] ** 2,
    )
    reveal_times = [0.4 + i * 0.19 for i in range(len(grid))]

    def diagram(draw, layer, t, alpha, glow):
        zoom_p = mg.ease_in_out_cubic(mg.window(t, sc_start + 1.0, sc_start + 6.0))
        cam = mg.Camera(anchor=anchor, scale=mg.lerp(1.0, 0.88, zoom_p))
        ax, ay = anchor
        for i, (ox, oy) in enumerate(grid):
            reveal_t = sc_start + reveal_times[i]
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
        scene.caption(draw, caption_text, alpha, THEME)
        prog = beat_progress(t, sc_start, 0.9)
        return safe_character("introg", mg.lerp(2000, 1690, prog), 990, 380, alpha, flip=True)
    return diagram


def make_inference_scale(sc_start, sc_end, caption_text):
    user_ys = [370, 460, 560, 660, 750]

    def diagram(draw, layer, t, alpha, glow):
        cluster_c = (900, 560)
        model_c = (1330, 560)

        for i, uy in enumerate(user_ys):
            u_alpha = alpha * mg.fade_window(t, sc_start + 0.2 + i * 0.08, sc_start + 0.5 + i * 0.08)
            if u_alpha <= 0.001:
                continue
            mg.draw_dot(draw, (270, uy), 10, THEME["blue"], alpha=u_alpha)
            mg.draw_arrow(draw, (285, uy), (cluster_c[0] - 110, cluster_c[1] + (uy - 560) * 0.4),
                           progress=1.0, color=THEME["blue"], width=2, alpha=u_alpha * 0.6)
            stream_start = sc_start + 1.0 + i * 0.08
            if t >= stream_start:
                mg.traveling_dots(draw, (285, uy), (cluster_c[0] - 110, cluster_c[1] + (uy - 560) * 0.4),
                                   t - stream_start, 0.5, 2, THEME["blue_bright"], radius=3, alpha=alpha * 0.5)

        cluster_box = core_grid(draw, cluster_c[0], cluster_c[1], 260, 260, 3, 3, "GPUS", alpha, t,
                                 sc_start + 1.4, glow, stagger=0.05)
        model_alpha = alpha * mg.fade_window(t, sc_start + 2.6, sc_start + 3.1)
        model_box = (model_c[0] - 110, model_c[1] - 90, model_c[0] + 110, model_c[1] + 90)
        mg.draw_rounded_rect(draw, model_box, 18, outline=THEME["blue_bright"], width=5, alpha=model_alpha)
        mg.draw_text_centered(draw, "AI MODEL", *model_c, 20, THEME["text"], alpha=model_alpha, bold=True)
        glow.append(("rect", model_box, 18, THEME["blue_bright"], model_alpha * 0.3))
        if t >= sc_start + 3.1:
            mg.traveling_dots(draw, (cluster_box[2], cluster_c[1]), (model_box[0], model_c[1]),
                               t - sc_start - 3.1, 0.5, 3, THEME["blue_bright"], radius=4, alpha=alpha * 0.7)

        scene.caption(draw, caption_text, alpha, THEME)
        prog = beat_progress(t, sc_start, 0.9)
        char = safe_character("explaining", 1650, 1010, 440, alpha, flip=True)
        _, ccx, cby, ch, calpha, cflip = char
        hand_connector(draw, "explaining", ccx, cby, ch, True, (cluster_box[2] + 30, cluster_c[1] - 100),
                        t, sc_start + 2.0, sc_start + 2.6, alpha)
        return char
    return diagram


def make_real_cost(sc_start, sc_end, caption_text):
    items = ["HARDWARE", "ELECTRICITY", "COOLING", "NETWORKING"]
    xs = [330, 630, 930, 1230]

    def diagram(draw, layer, t, alpha, glow):
        for i, (label, x) in enumerate(zip(items, xs)):
            build_start = sc_start + 0.4 + i * 0.35
            core_grid(draw, x, 560, 220, 260, 1, 1, label, alpha, t, build_start, glow, label_size=18)
        scene.caption(draw, caption_text, alpha, THEME)
        prog = beat_progress(t, sc_start, 0.9)
        return safe_character("thinking", 1700, 1000, 320, alpha)
    return diagram


def make_takeaway(sc_start, sc_end):
    def diagram(draw, layer, t, alpha, glow):
        prog = beat_progress(t, sc_start)
        return safe_character("closing", 1460, mg.lerp(1160, 1030, prog), int(mg.lerp(680, 720, prog)), alpha)
    return diagram


def make_takeaway_overlay(sc_start, sc_end, title_lines):
    text_window = (sc_start + 0.6, sc_start + 1.6)
    bar_window = (sc_start + 1.6, sc_start + 2.2)

    def overlay(rgb_image, t):
        if t < sc_start:
            return rgb_image
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

        dim_alpha = mg.fade_window(t, sc_start, sc_start + 0.8) * THEME["dim_overlay_alpha"]
        if dim_alpha > 0.001:
            draw.rectangle((0, 0, mg.WIDTH, mg.HEIGHT), fill=mg.rgba(THEME["dim_overlay_color"], dim_alpha))

        if alpha > 0.001:
            scale_ = mg.lerp(0.85, 1.0, progress)
            cx, cy = 740, mg.HEIGHT / 2
            mg.draw_text_centered(draw, title_lines[0], cx, cy - 60 * scale_, int(62 * scale_),
                                   THEME["text"], alpha=alpha, bold=True)
            mg.draw_text_centered(draw, title_lines[1], cx, cy + 60 * scale_, int(62 * scale_),
                                   THEME["blue_bright"], alpha=alpha, bold=True)

        bar_progress = mg.ease_in_out_cubic(mg.window(t, *bar_window))
        if bar_progress > 0.001:
            bar_w = 420 * bar_progress
            cx, cy = 740, mg.HEIGHT / 2 + 128
            draw.rectangle((cx - bar_w / 2, cy, cx + bar_w / 2, cy + 5), fill=mg.rgba(THEME["amber"], alpha))

        composed = Image.alpha_composite(rgba_image, layer)
        return composed.convert("RGB")
    return overlay


SCENE_BUILDERS = {
    "hook": lambda s, e, sc: make_hook(s, e, sc["title_lines"]),
    "why_gpus": lambda s, e, sc: make_why_gpus(s, e, " ".join(sc["title_lines"])),
    "cpu_vs_gpu": lambda s, e, sc: make_cpu_vs_gpu(s, e, " ".join(sc["title_lines"])),
    "parallelism": lambda s, e, sc: make_parallelism(s, e, " ".join(sc["title_lines"])),
    "memory_bandwidth": lambda s, e, sc: make_memory_bandwidth(s, e, " ".join(sc["title_lines"])),
    "clusters": lambda s, e, sc: make_clusters(s, e, " ".join(sc["title_lines"])),
    "inference_scale": lambda s, e, sc: make_inference_scale(s, e, " ".join(sc["title_lines"])),
    "real_cost": lambda s, e, sc: make_real_cost(s, e, " ".join(sc["title_lines"])),
    "takeaway": lambda s, e, sc: make_takeaway(s, e),
}

CHARACTER_POSES = {
    "hook": "introg", "why_gpus": "explaining", "cpu_vs_gpu": "explaining",
    "parallelism": "thinking", "memory_bandwidth": "introg", "clusters": "introg",
    "inference_scale": "explaining", "real_cost": "thinking", "takeaway": "closing",
}


# ------------------------------------------------------------------
# Narration-driven timeline
# ------------------------------------------------------------------

def ffprobe_path(ffmpeg_path):
    return ffmpeg_path.parent / "ffprobe.exe"


def probe_duration(ffprobe, media_path):
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {media_path}:\n{result.stderr}")
    return float(result.stdout.strip())


def synthesize_scene_narration(ffprobe, scenes_data):
    """Synthesizes one narration clip per scene, returns
    [{id, narration_duration, ...}] with durations measured, not guessed."""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for sc in scenes_data:
        wav_path = VOICE_DIR / f"{sc['id']}.wav"
        mg.synthesize_narration(sc["narration"], wav_path)
        duration = probe_duration(ffprobe, wav_path)
        results.append({**sc, "wav_path": wav_path, "narration_duration": duration})
        print(f"  [{sc['id']}] {len(sc['narration'].split())} words -> {duration:.2f}s")
    return results


def compute_timeline(scenes_with_audio):
    """Assigns start/end to each scene from its measured narration
    length plus a lead-in/tail, rather than a fixed guess."""
    t = 0.0
    for sc in scenes_with_audio:
        sc["start"] = t
        sc["narration_at"] = t + LEAD_IN
        sc["end"] = t + LEAD_IN + sc["narration_duration"] + TAIL
        t = sc["end"]
    return scenes_with_audio


def build_scene_objects(scenes_with_timeline):
    scenes = []
    for i, sc in enumerate(scenes_with_timeline):
        builder = SCENE_BUILDERS[sc["id"]]
        draw_diagram = builder(sc["start"], sc["end"], sc)
        stage_box = None if sc["id"] == "takeaway" else STAGE_BOX
        scenes.append(se.Scene(
            id=sc["id"], title=" / ".join(sc["title_lines"]), narration=sc["narration"],
            start=sc["start"], end=sc["end"], draw_diagram=draw_diagram, stage_box=stage_box,
            overlap=0.0 if i == 0 else 0.5,
            validation={"narration_duration": sc["narration_duration"], "pose": CHARACTER_POSES[sc["id"]]},
        ))
    return scenes


def build_combined_audio(ffmpeg, scenes_with_timeline, output_path, total_duration):
    inputs = []
    filters = []
    for i, sc in enumerate(scenes_with_timeline):
        inputs += ["-i", str(sc["wav_path"])]
        delay_ms = max(0, round(sc["narration_at"] * 1000))
        filters.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
    mix_inputs = "".join(f"[a{i}]" for i in range(len(scenes_with_timeline)))
    filters.append(f"{mix_inputs}amix=inputs={len(scenes_with_timeline)}:duration=longest:normalize=0[mixed]")
    filters.append(f"[mixed]apad,atrim=0:{total_duration}[aout]")

    command = [
        str(ffmpeg), "-y", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "[aout]",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio mix failed:\n{result.stderr}")


def mux_video_audio(ffmpeg, silent_video, audio_path, output_path, duration):
    command = [
        str(ffmpeg), "-y",
        "-i", str(silent_video),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(duration),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg mux failed:\n{result.stderr}")


def main():
    ffmpeg = mg.find_ffmpeg()
    ffprobe = ffprobe_path(ffmpeg)

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "output").mkdir(parents=True, exist_ok=True)

    ca.load_poses()  # fail fast if the reference sheet is missing

    scenes_data = json.loads(SCRIPT_JSON.read_text(encoding="utf-8"))["scenes"]
    print(f"Loaded {len(scenes_data)} scenes from {SCRIPT_JSON.name}")

    print("Synthesizing per-scene narration...")
    scenes_with_audio = synthesize_scene_narration(ffprobe, scenes_data)

    scenes_with_timeline = compute_timeline(scenes_with_audio)
    total_duration = round(scenes_with_timeline[-1]["end"] + OUTRO_HOLD, 1)
    print(f"Total narration-driven duration: {total_duration}s")

    scenes = build_scene_objects(scenes_with_timeline)

    takeaway_sc = scenes_with_timeline[-1]
    post_fn = make_takeaway_overlay(takeaway_sc["start"], takeaway_sc["end"], takeaway_sc["title_lines"])

    draw_frame = se.render_scenes(scenes, THEME, build_background(), post_fn=post_fn)

    print("Rendering full production video...")
    mg.render_video(draw_frame, total_duration, SILENT_VIDEO, ffmpeg=ffmpeg, crf=16, preset="medium")

    print("Building combined narration track...")
    build_combined_audio(ffmpeg, scenes_with_timeline, COMBINED_VOICE, total_duration)

    print("Muxing narration onto video...")
    mux_video_audio(ffmpeg, SILENT_VIDEO, COMBINED_VOICE, OUTPUT_FILE, total_duration)

    print()
    print("Done.")
    print(f"Output: {OUTPUT_FILE}")

    return {"total_duration": total_duration, "scenes": [(s.id, s.start, s.end) for s in scenes]}


if __name__ == "__main__":
    main()
