"""Shot-level render/resume driver.

Renders each shot in a beat shot plan as its own independent file (bounded
ffmpeg process per shot, not one process for the whole scene/video), then
concatenates them. Skips any shot file that already validates and only
re-renders invalid/missing ones - safe to re-run after a partial failure,
same pattern as render_hf_incident_chunks.py (feat/ai-supervisor-control-loop).

Each shot is rendered by wrapping its beat diagram function in a single-item
scene_engine.Scene and calling the existing scene_engine.render_scenes() -
this reuses the real engine (cross-fade/glow/character-safety plumbing) per
shot rather than reimplementing any of it; motion_graphics.py and
scene_engine.py are unmodified.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import motion_graphics as mg
import scene_engine as se
from gpu_explainer_beats import BEAT_DIAGRAM_BUILDERS, build_diagram_for_strategy
from visual_identity import VisualIdentity, default_identity

STAGE_BOX = (110, 140, 1830, 1010)


def _resolve_draw_diagram(shot: dict, identity: VisualIdentity):
    """Two dispatch paths: shots carrying 'entities' (shot_planner.build_auto_shots -
    any scene, via the generic strategy library) resolve through
    build_diagram_for_strategy(); shots without it (shot_planner.build_beat_shots -
    today only cpu_vs_gpu's hand-authored beats) resolve through the
    fixed, exact-visual_id-keyed BEAT_DIAGRAM_BUILDERS, unchanged."""
    duration = shot["duration"]
    if shot.get("entities") is not None:
        return build_diagram_for_strategy(
            shot["visual_strategy"], duration, shot["camera_strategy"], identity,
            shot["entities"], shot.get("character_pose"),
        )
    builder = BEAT_DIAGRAM_BUILDERS.get(shot["visual_id"])
    if builder is None:
        raise KeyError(f"no diagram builder registered for visual_id={shot['visual_id']!r}")
    return builder(duration, shot["camera_strategy"], identity)


def probe_ok(ffprobe: Path, path: Path) -> tuple[bool, float | None]:
    if not path.exists() or path.stat().st_size == 0:
        return False, None
    dur = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if dur.returncode != 0 or not dur.stdout.strip():
        return False, None
    vstream = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if vstream.returncode != 0 or "video" not in vstream.stdout:
        return False, None
    try:
        return True, float(dur.stdout.strip())
    except ValueError:
        return False, None


def shot_path(shot: dict, shot_dir: Path) -> Path:
    return shot_dir / f"{shot['shot_id']}.mp4"


def render_shot(shot: dict, background, theme: dict, path: Path, ffmpeg: Path,
                 identity: VisualIdentity = None, crf: int = 16, preset: str = "medium") -> Path:
    identity = identity or default_identity(theme)
    duration = shot["duration"]
    draw_diagram = _resolve_draw_diagram(shot, identity)

    scene = se.Scene(
        id=shot["shot_id"], title=shot["beat_id"], narration=shot["narration_text"],
        start=0.0, end=duration, draw_diagram=draw_diagram,
        stage_box=STAGE_BOX, overlap=0.0,
        validation={"visual_strategy": shot["visual_strategy"], "visual_type": shot["visual_type"]},
    )
    draw_frame = se.render_scenes([scene], theme, background)
    mg.render_video(draw_frame, duration, path, ffmpeg=ffmpeg, crf=crf, preset=preset)
    return path


def render_shots(shots: list, background, theme: dict, shot_dir: Path, ffmpeg: Path,
                  ffprobe: Path, identity: VisualIdentity = None,
                  log: Callable[[str], None] = print) -> list:
    """Renders every shot, reusing any already-valid file. Returns the
    ordered list of shot file paths (all validated) ready for concat."""
    identity = identity or default_identity(theme)
    paths = []
    for shot in shots:
        path = shot_path(shot, shot_dir)
        ok, dur = probe_ok(ffprobe, path)
        if ok and abs(dur - shot["duration"]) < 0.5:
            log(f"{shot['shot_id']}: reusing valid existing file ({dur:.2f}s)")
            paths.append(path)
            continue
        if path.exists():
            log(f"{shot['shot_id']}: existing file invalid/incomplete, re-rendering")
            path.unlink()
        log(f"{shot['shot_id']}: rendering [{shot['visual_strategy']}] ({shot['duration']:.2f}s)...")
        render_shot(shot, background, theme, path, ffmpeg, identity=identity)
        ok, dur = probe_ok(ffprobe, path)
        if not ok:
            raise RuntimeError(f"shot {shot['shot_id']} failed validation immediately after rendering")
        log(f"{shot['shot_id']}: done ({dur:.2f}s)")
        paths.append(path)
    return paths


def concat_shots(shot_paths: list, ffmpeg: Path, ffprobe: Path, concat_list_path: Path,
                  output_path: Path) -> float:
    lines = [f"file '{p.resolve().as_posix()}'" for p in shot_paths]
    concat_list_path.parent.mkdir(parents=True, exist_ok=True)
    concat_list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    command = [
        str(ffmpeg), "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path), "-c", "copy", str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"concat failed:\n{result.stderr}")

    ok, duration = probe_ok(ffprobe, output_path)
    if not ok:
        raise RuntimeError("concatenated silent video failed validation")
    return duration
