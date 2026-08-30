"""Shot-driven timeline planner for production video rendering.

Creates a deterministic shot list before video rendering. The planner is
intentionally independent of the rendering engine so the timeline can be
reviewed/debugged as JSON before expensive frame rendering begins.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


MIN_SHOT = 2.8
MAX_SHOT = 5.0

# Deliberately small motion vocabulary. The renderer maps these to camera
# transforms; keeping the plan declarative makes it easy to replace the
# renderer later with richer B-roll/AI-video assets.
MOTION_CYCLE = (
    "push_in",
    "pan_right",
    "pull_out",
    "pan_left",
    "drift_up",
    "drift_down",
)


def _shot_length(remaining: float) -> float:
    if remaining <= MAX_SHOT:
        return round(remaining, 3)
    return MAX_SHOT


def build_shot_plan(scenes: Iterable[dict]) -> dict:
    shots = []
    shot_index = 1

    for scene in scenes:
        start = float(scene["start"])
        end = float(scene["end"])
        cursor = start
        local_index = 0

        while cursor < end - 0.01:
            remaining = end - cursor
            duration = _shot_length(remaining)

            # Avoid a tiny final shot by shortening the previous shot when
            # possible. This keeps every shot meaningful.
            if remaining < MIN_SHOT and shots:
                previous = shots[-1]
                previous["end"] = round(end, 3)
                previous["duration"] = round(end - previous["start"], 3)
                break

            motion = MOTION_CYCLE[(shot_index - 1) % len(MOTION_CYCLE)]
            shots.append(
                {
                    "id": f"shot_{shot_index:03d}",
                    "scene_id": scene["id"],
                    "scene_title": " / ".join(scene["title_lines"]),
                    "start": round(cursor, 3),
                    "end": round(min(end, cursor + duration), 3),
                    "duration": round(duration, 3),
                    "motion": motion,
                    "visual_change_required": True,
                }
            )
            shot_index += 1
            local_index += 1
            cursor += duration

    if not shots:
        raise ValueError("Cannot build a shot plan from an empty timeline.")

    # Hard validation: no shot may exceed the engagement ceiling.
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
