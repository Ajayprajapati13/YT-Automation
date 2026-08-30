"""20-30s test of the GENERALIZED (auto beat/strategy-selection) path,
on a scene cpu_vs_gpu's hand-authored work never touched: inference_scale.

Unlike test_shot_driven_render.py (which uses hand-authored beats.json
entries for cpu_vs_gpu), this drives shot_planner.build_auto_shots() -
narration segmentation and visual-strategy selection are both fully
automatic (src/beat_authoring.py); only lightweight per-scene entity data
(content/gpu_scene_concepts.json) is scene-specific. Demonstrates the
architecture generalizes beyond the one hand-tuned scene.

Output:
  output/test_shot_driven_15_30s.mp4  (overwritten by this run)
  output/test_shot_plan.json          (overwritten by this run)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import create_gpu_explainer as gpu
import motion_graphics as mg
import render_shots
import shot_planner
from visual_identity import default_identity

CONCEPTS_FILE = gpu.BASE_DIR / "content" / "gpu_scene_concepts.json"
TEST_TEMP_DIR = gpu.BASE_DIR / "temp" / "shot_driven_generalized_test"
SHOT_DIR = TEST_TEMP_DIR / "shots"
CONCAT_LIST = TEST_TEMP_DIR / "concat_list.txt"
SILENT_VIDEO = TEST_TEMP_DIR / "silent.mp4"
NARRATION_WAV = TEST_TEMP_DIR / "narration.wav"
SHOT_PLAN_OUT = gpu.BASE_DIR / "output" / "test_shot_plan.json"
OUTPUT_FILE = gpu.BASE_DIR / "output" / "test_shot_driven_15_30s.mp4"

TEST_SCENE_ID = "inference_scale"


def main() -> dict:
    report = {"attempts": [], "failures": []}
    t_wall_start = time.time()

    ffmpeg = mg.find_ffmpeg()
    ffprobe = gpu.ffprobe_path(ffmpeg)
    gpu.ca.load_poses()
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    (gpu.BASE_DIR / "output").mkdir(parents=True, exist_ok=True)

    all_scenes = json.loads(gpu.SCRIPT_JSON.read_text(encoding="utf-8"))["scenes"]
    scene_data = next(s for s in all_scenes if s["id"] == TEST_SCENE_ID)

    print(f"Synthesizing narration for scene '{TEST_SCENE_ID}' (existing TTS path)...")
    t0 = time.time()
    scenes_with_audio = gpu.synthesize_scene_narration(ffprobe, [scene_data])
    scenes_with_timeline = gpu.compute_timeline(scenes_with_audio)
    scene = scenes_with_timeline[0]
    t_tts = time.time() - t0
    print(f"  narration duration: {scene['narration_duration']:.2f}s, "
          f"scene window: [{scene['start']:.2f}, {scene['end']:.2f}]")

    concepts = json.loads(CONCEPTS_FILE.read_text(encoding="utf-8"))["scenes"]
    entities = concepts[TEST_SCENE_ID]

    plan = shot_planner.build_auto_shots(scene, entities)
    shot_planner.write_beat_shot_plan(plan, SHOT_PLAN_OUT)
    print(f"Shot plan written: {SHOT_PLAN_OUT} ({len(plan['shots'])} shots)")
    for s in plan["shots"]:
        print(f"  {s['shot_id']:<32} {s['visual_strategy']:<24} {s['duration']:5.2f}s  | {s['narration_text'][:60]}")

    print("Validating visual diversity...")
    diversity_warnings = shot_planner.validate_visual_diversity(plan["shots"])
    for w in diversity_warnings:
        print(f"  WARNING [{w['rule']}]: {w['detail']}")
    if not diversity_warnings:
        print("  no diversity warnings")

    strategies_used = sorted({s["visual_strategy"] for s in plan["shots"]})
    print(f"Distinct visual strategies in this test: {len(strategies_used)} -> {strategies_used}")

    background = gpu.build_background()
    identity = default_identity(gpu.THEME)

    print("Rendering shots independently...")
    t0 = time.time()
    shot_paths = []
    for shot in plan["shots"]:
        path = render_shots.shot_path(shot, SHOT_DIR)
        pre_ok, _ = render_shots.probe_ok(ffprobe, path)
        t_shot0 = time.time()
        try:
            paths_this = render_shots.render_shots([shot], background, gpu.THEME, SHOT_DIR, ffmpeg, ffprobe,
                                                     identity=identity, log=print)
        except Exception as exc:  # noqa: BLE001
            report["failures"].append({"shot": shot["shot_id"], "error": f"{type(exc).__name__}: {exc}"})
            print(f"  RETRY after failure on {shot['shot_id']}: {exc}")
            paths_this = render_shots.render_shots([shot], background, gpu.THEME, SHOT_DIR, ffmpeg, ffprobe,
                                                     identity=identity, log=print)
        shot_paths.extend(paths_this)
        report["attempts"].append({
            "shot": shot["shot_id"], "visual_strategy": shot["visual_strategy"],
            "reused_existing": pre_ok, "render_seconds": round(time.time() - t_shot0, 2),
        })
    t_shots = time.time() - t0

    print("Concatenating shots...")
    t0 = time.time()
    silent_duration = render_shots.concat_shots(shot_paths, ffmpeg, ffprobe, CONCAT_LIST, SILENT_VIDEO)
    t_concat = time.time() - t0
    print(f"  concatenated silent video: {silent_duration:.2f}s")

    print("Building narration track (existing audio-mix path)...")
    t0 = time.time()
    gpu.build_combined_audio(ffmpeg, scenes_with_timeline, NARRATION_WAV, scene["end"])
    t_audio = time.time() - t0

    print("Muxing narration onto video...")
    t0 = time.time()
    gpu.mux_video_audio(ffmpeg, SILENT_VIDEO, NARRATION_WAV, OUTPUT_FILE, scene["end"])
    t_mux = time.time() - t0

    total_wall = time.time() - t_wall_start
    report.update({
        "scene": TEST_SCENE_ID,
        "output": str(OUTPUT_FILE),
        "shot_plan": str(SHOT_PLAN_OUT),
        "num_shots": len(plan["shots"]),
        "distinct_visual_strategies": strategies_used,
        "diversity_warnings": diversity_warnings,
        "tts_seconds": round(t_tts, 2),
        "shots_render_seconds": round(t_shots, 2),
        "concat_seconds": round(t_concat, 2),
        "audio_build_seconds": round(t_audio, 2),
        "mux_seconds": round(t_mux, 2),
        "total_wall_seconds": round(total_wall, 2),
        "final_duration_seconds": silent_duration,
    })
    print()
    print("Done.")
    print(f"Output: {OUTPUT_FILE}")
    return report


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
