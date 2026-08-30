"""Shot-driven production entry point.

Builds and persists the shot/timeline plan BEFORE rendering, then uses that
plan to enforce frequent visual motion. This is a wrapper around the existing
GPU explainer scene engine; it does not replace the proven diagram renderer.
"""

from pathlib import Path

from PIL import Image

import create_gpu_explainer as gpu
import motion_graphics as mg
import shot_planner


SHOT_PLAN = gpu.BASE_DIR / "output" / "gpu_explainer_shot_plan.json"


def _find_shot(shots, t):
    for shot in shots:
        if shot["start"] <= t < shot["end"]:
            return shot
    return shots[-1]


def apply_shot_motion(rgb_image, t, shots):
    """Apply a restrained camera move for every planned shot.

    The source frame is rendered at 1920x1080. A small animated crop keeps
    diagrams/text readable while preventing long static holds.
    """
    shot = _find_shot(shots, t)
    duration = max(0.1, shot["duration"])
    p = max(0.0, min(1.0, (t - shot["start"]) / duration))

    # Smoothstep for cinematic rather than linear movement.
    p = p * p * (3.0 - 2.0 * p)
    motion = shot["motion"]

    # Keep the maximum scale deliberately conservative so text and diagrams
    # remain inside frame and do not become distorted.
    zoom = 1.0 + 0.035 * p if motion in {"push_in", "drift_up", "drift_down"} else 1.035 - 0.035 * p
    if motion == "hold_pulse":
        zoom = 1.0 + 0.012 * (1.0 - abs(2.0 * p - 1.0))

    w, h = rgb_image.size
    crop_w = int(w / zoom)
    crop_h = int(h / zoom)

    if motion == "pan_right":
        x = int((w - crop_w) * p)
        y = int((h - crop_h) * 0.5)
    elif motion == "pan_left":
        x = int((w - crop_w) * (1.0 - p))
        y = int((h - crop_h) * 0.5)
    elif motion == "drift_up":
        x = int((w - crop_w) * 0.5)
        y = int((h - crop_h) * (1.0 - p))
    elif motion == "drift_down":
        x = int((w - crop_w) * 0.5)
        y = int((h - crop_h) * p)
    else:
        x = int((w - crop_w) * 0.5)
        y = int((h - crop_h) * 0.5)

    cropped = rgb_image.crop((x, y, x + crop_w, y + crop_h))
    return cropped.resize((w, h), Image.Resampling.LANCZOS)


def main():
    ffmpeg = mg.find_ffmpeg()
    ffprobe = gpu.ffprobe_path(ffmpeg)

    gpu.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (gpu.BASE_DIR / "output").mkdir(parents=True, exist_ok=True)

    gpu.ca.load_poses()
    scenes_data = __import__("json").loads(
        gpu.SCRIPT_JSON.read_text(encoding="utf-8")
    )["scenes"]

    print(f"Loaded {len(scenes_data)} scenes from {gpu.SCRIPT_JSON.name}")
    print("Synthesizing per-scene narration...")
    scenes_with_audio = gpu.synthesize_scene_narration(ffprobe, scenes_data)
    scenes_with_timeline = gpu.compute_timeline(scenes_with_audio)

    # CRITICAL: produce the shot list before any video frame is rendered.
    plan = shot_planner.build_shot_plan(scenes_with_timeline)
    shot_planner.write_shot_plan(plan, SHOT_PLAN)
    print(f"Shot plan written: {SHOT_PLAN}")
    print(
        f"Planned {len(plan['shots'])} shots; "
        f"max visual hold={plan['max_visual_hold_seconds']}s"
    )

    total_duration = round(scenes_with_timeline[-1]["end"] + gpu.OUTRO_HOLD, 1)
    scenes = gpu.build_scene_objects(scenes_with_timeline)

    takeaway_sc = scenes_with_timeline[-1]
    takeaway_overlay = gpu.make_takeaway_overlay(
        takeaway_sc["start"], takeaway_sc["end"], takeaway_sc["title_lines"]
    )
    shots = plan["shots"]

    def post_frame(rgb_image, t):
        # Existing cinematic outro overlay remains part of the proven engine.
        rgb_image = takeaway_overlay(rgb_image, t)
        return apply_shot_motion(rgb_image, t, shots)

    draw_frame = gpu.se.render_scenes(
        scenes,
        gpu.THEME,
        gpu.build_background(),
        post_fn=post_frame,
    )

    print("Rendering shot-driven production video...")
    mg.render_video(
        draw_frame,
        total_duration,
        gpu.SILENT_VIDEO,
        ffmpeg=ffmpeg,
        crf=16,
        preset="medium",
    )

    print("Building combined narration track...")
    gpu.build_combined_audio(
        ffmpeg,
        scenes_with_timeline,
        gpu.COMBINED_VOICE,
        total_duration,
    )

    print("Muxing narration onto video...")
    gpu.mux_video_audio(
        ffmpeg,
        gpu.SILENT_VIDEO,
        gpu.COMBINED_VOICE,
        gpu.OUTPUT_FILE,
        total_duration,
    )

    print("Done.")
    print(f"Video: {gpu.OUTPUT_FILE}")
    print(f"Shot plan: {SHOT_PLAN}")


if __name__ == "__main__":
    main()
