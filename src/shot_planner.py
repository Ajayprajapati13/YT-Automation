"""Shot-driven timeline planner for production video rendering.

Creates a deterministic shot list before video rendering. The planner is
independent of the rendering engine so the timeline can be reviewed/debugged
as JSON before expensive frame rendering begins.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


MIN_SHOT = 2.8
MAX_SHOT = 5.0

MOTION_CYCLE = (
    "push_in",
    "pan_right",
    "pull_out",
    "pan_left",
    "drift_up",
    "drift_down",
)


def build_shot_plan(scenes: Iterable[dict]) -> dict:
    shots = []
    shot_index = 1

    for scene in scenes:
        start = float(scene["start"])
        end = float(scene["end"])
        duration = end - start
        if duration <= 0:
            raise ValueError(f"Invalid scene duration for {scene['id']}: {duration}")

        # Split each scene into near-even shots. This prevents a short final
        # remainder from being merged into a shot that exceeds MAX_SHOT.
        count = max(1, int((duration + MAX_SHOT - 1e-9) // MAX_SHOT))
        if count > 1:
            average = duration / count
            if average < MIN_SHOT:
                count = max(1, int(duration / MIN_SHOT + 0.5))
                count = max(1, min(count, int(duration / MAX_SHOT + 0.999)))
            average = duration / count
        else:
            average = duration

        cursor = start
        for local_index in range(count):
            shot_end = end if local_index == count - 1 else start + average * (local_index + 1)
            shot_duration = shot_end - cursor
            motion = MOTION_CYCLE[(shot_index - 1) % len(MOTION_CYCLE)]
            shots.append(
                {
                    "id": f"shot_{shot_index:03d}",
                    "scene_id": scene["id"],
                    "scene_title": " / ".join(scene["title_lines"]),
                    "start": round(cursor, 3),
                    "end": round(shot_end, 3),
                    "duration": round(shot_duration, 3),
                    "motion": motion,
                    "visual_change_required": True,
                }
            )
            shot_index += 1
            cursor = shot_end

    if not shots:
        raise ValueError("Cannot build a shot plan from an empty timeline.")

    longest = max(s["duration"] for s in shots)
    if longest > MAX_SHOT + 0.001:
        raise ValueError(f"Shot duration exceeds {MAX_SHOT}s: {longest}s")

    return {
        "version": 1,
        "max_visual_hold_seconds": MAX_SHOT,
        "shots": shots,
    }


def write_shot_plan(plan: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
