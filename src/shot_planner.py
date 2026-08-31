"""Shot-driven timeline planner for production video rendering.

Creates a deterministic shot list before video rendering. The planner is
independent of the rendering engine so the timeline can be reviewed/debugged
as JSON before expensive frame rendering begins.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import beat_authoring


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


# ------------------------------------------------------------------
# Beat-based shot planning (docs/pipeline_architecture_audit_2026-08-31.md,
# section E). Unlike build_shot_plan() above (equal time division, no
# content awareness), this derives shots from hand-authored narration
# beats: each shot's duration is the scene's REAL measured narration
# duration weighted by that beat's own word count, not a fixed window.
# Every shot carries the full metadata a shot-driven renderer needs to
# actually change visual content per shot, not just camera framing.
# ------------------------------------------------------------------

REQUIRED_BEAT_FIELDS = (
    "beat_id", "text", "visual_strategy", "visual_type",
    "visual_id", "animation_strategy", "camera_strategy",
)

# The initial visual-strategy library (docs/pipeline_architecture_audit_2026-08-31.md
# section E / follow-up task). A beat's visual_strategy must be one of these -
# it names WHAT KIND of shot this is, independent of which specific
# visual_id/diagram builder implements it.
VISUAL_STRATEGY_LIBRARY = (
    "establishing_visual",
    "diagram_build",
    "data_flow",
    "comparison",
    "stat_callout",
    "kinetic_text",
    "close_up_detail",
    "character_interaction",
    "transition_visual",
)


def build_beat_shots(scene: dict, beats: list) -> dict:
    """scene: a timeline-computed scene dict with 'id', 'start', 'end'
    (from create_gpu_explainer.compute_timeline - real measured narration
    duration, not a guess). beats: this scene's ordered beat definitions
    (content/gpu_explainer_beats.json), each with the REQUIRED_BEAT_FIELDS
    above plus:
      - 'text': the beat's narration/beat reference. May be "" for a beat
        that adds no new spoken words (e.g. a reaction beat covering
        trailing silence) - such beats MUST set 'weight_words' explicitly
        instead, so duration is still derived from something real (an
        authored editorial weight), never an arbitrary equal split.
      - 'weight_words' (optional): overrides the word-count weight used to
        proportion this beat's share of the scene's real measured
        duration. Required when 'text' is empty.
      - 'character_pose' (optional): the pose this beat's character shot
        uses, if any - carried through for validate_visual_diversity().

    Beat duration is proportional to weight vs. the scene's real measured
    narration duration - never scene_duration / len(beats).
    """
    if not beats:
        raise ValueError(f"no beats defined for scene {scene['id']}")
    for b in beats:
        missing = [f for f in REQUIRED_BEAT_FIELDS if f not in b]
        if missing:
            raise ValueError(f"beat {b.get('beat_id', '?')} missing fields: {missing}")
        if b["visual_strategy"] not in VISUAL_STRATEGY_LIBRARY:
            raise ValueError(
                f"beat {b['beat_id']}: visual_strategy {b['visual_strategy']!r} "
                f"is not in VISUAL_STRATEGY_LIBRARY"
            )
        if not b["text"].strip() and "weight_words" not in b:
            raise ValueError(
                f"beat {b['beat_id']}: empty 'text' requires an explicit 'weight_words' "
                "(duration must come from an authored weight, not an arbitrary split)"
            )

    start, end = float(scene["start"]), float(scene["end"])
    duration = end - start
    if duration <= 0:
        raise ValueError(f"invalid scene duration for {scene['id']}: {duration}")

    weights = [max(1, int(b.get("weight_words") or len(b["text"].split()))) for b in beats]
    total_weight = sum(weights)

    shots = []
    cursor = start
    for i, (beat, weight) in enumerate(zip(beats, weights)):
        is_last = i == len(beats) - 1
        shot_end = end if is_last else cursor + duration * (weight / total_weight)
        shots.append({
            "shot_id": f"{scene['id']}.{beat['beat_id']}",
            "scene_id": scene["id"],
            "beat_id": beat["beat_id"],
            "narration_text": beat["text"],
            "visual_strategy": beat["visual_strategy"],
            "visual_type": beat["visual_type"],
            "visual_id": beat["visual_id"],
            "animation_strategy": beat["animation_strategy"],
            "camera_strategy": beat["camera_strategy"],
            "character_pose": beat.get("character_pose"),
            "start": round(cursor, 3),
            "end": round(shot_end, 3),
            "duration": round(shot_end - cursor, 3),
        })
        cursor = shot_end

    return {"version": 1, "scene_id": scene["id"], "shots": shots}


def write_beat_shot_plan(plan: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


# ------------------------------------------------------------------
# Visual diversity validation (requirement 11). Reject/warn rather than
# silently accept a shot plan that would read as repetitive on screen.
# Deliberately rule-based on the plan's own declared metadata, not random
# perturbation - diversity here means "matches what the narration actually
# needs," not "changes for its own sake."
# ------------------------------------------------------------------

MAX_CONSECUTIVE_SAME_VISUAL_TYPE = 2
MAX_STRATEGY_SHARE = 0.6  # a single visual_strategy dominating >60% of a scene's shots
MAX_CONSECUTIVE_SAME_POSE = 3


class VisualDiversityError(Exception):
    """Raised for the most flagrant repetition: the exact same visual_id
    used twice in one scene - i.e. literally the same composition shown
    again with nothing new, which is exactly the failure mode this whole
    architecture exists to prevent."""


def validate_visual_diversity(shots: list) -> list[dict]:
    """Returns a list of {rule, detail} warnings for softer repetition.
    Raises VisualDiversityError for the hard case (duplicate visual_id).
    Does not mutate or reorder shots - the plan is always reported as-is;
    the caller decides whether to treat warnings as fatal."""
    warnings = []

    seen_visual_ids = {}
    for s in shots:
        seen_visual_ids.setdefault(s["visual_id"], []).append(s["shot_id"])
    dupes = {vid: ids for vid, ids in seen_visual_ids.items() if len(ids) > 1}
    if dupes:
        detail = "; ".join(f"{vid} used by {ids}" for vid, ids in dupes.items())
        raise VisualDiversityError(f"same visual_id repeated without a new composition: {detail}")

    run_type, run_len = None, 0
    for s in shots:
        vt = s["visual_type"]
        run_len = run_len + 1 if vt == run_type else 1
        run_type = vt
        if run_len > MAX_CONSECUTIVE_SAME_VISUAL_TYPE:
            warnings.append({
                "rule": "consecutive_visual_type",
                "detail": f"visual_type {vt!r} repeats {run_len} shots in a row at {s['shot_id']}",
            })

    strategy_counts = {}
    for s in shots:
        strategy_counts[s["visual_strategy"]] = strategy_counts.get(s["visual_strategy"], 0) + 1
    for strategy, count in strategy_counts.items():
        share = count / len(shots)
        if share > MAX_STRATEGY_SHARE and len(shots) > 2:
            warnings.append({
                "rule": "strategy_dominance",
                "detail": f"visual_strategy {strategy!r} is {share:.0%} of shots ({count}/{len(shots)})",
            })

    run_pose, run_pose_len = None, 0
    for s in shots:
        pose = s.get("character_pose")
        if pose is None:
            run_pose, run_pose_len = None, 0
            continue
        run_pose_len = run_pose_len + 1 if pose == run_pose else 1
        run_pose = pose
        if run_pose_len > MAX_CONSECUTIVE_SAME_POSE:
            warnings.append({
                "rule": "consecutive_character_pose",
                "detail": f"character_pose {pose!r} repeats {run_pose_len} shots in a row at {s['shot_id']}",
            })

    return warnings


# ------------------------------------------------------------------
# Generalized (auto) shot planning: this is the reusable path. Instead of
# a hand-authored beats.json entry per scene (content/gpu_explainer_beats.json,
# cpu_vs_gpu only), this takes ANY scene's real narration text plus a small
# per-scene entity-data dict (content/gpu_scene_concepts.json) and derives
# beats, strategies, and camera work automatically via beat_authoring - the
# same segmentation/selection logic for every scene, no per-scene code.
# ------------------------------------------------------------------

CLOSING_REACTION_WEIGHT = 5


def build_auto_shots(scene: dict, entities: dict, include_closing_reaction: bool = True) -> dict:
    """scene: a timeline-computed scene dict with 'id', 'start', 'end',
    'narration' (the real scene narration text, as loaded from
    content/gpu_explainer_script.json - NOT re-synthesized; only used here
    to derive beat text/strategy, same as build_beat_shots does for
    hand-authored beats). entities: this scene's data dict from
    content/gpu_scene_concepts.json.

    Duration is proportioned by word count against the scene's real
    measured narration duration - identical math to build_beat_shots,
    just with the beat list and strategy assignment derived automatically
    instead of hand-authored.
    """
    start, end = float(scene["start"]), float(scene["end"])
    duration = end - start
    if duration <= 0:
        raise ValueError(f"invalid scene duration for {scene['id']}: {duration}")

    beat_texts = beat_authoring.segment_narration_into_beats(scene["narration"])
    if not beat_texts:
        raise ValueError(f"no beats could be segmented from scene {scene['id']}'s narration")

    n = len(beat_texts) + (1 if include_closing_reaction else 0)
    weights = []
    prior_strategy = None
    beats = []
    for i, text in enumerate(beat_texts):
        position = "first" if i == 0 else ("last" if (i == len(beat_texts) - 1 and not include_closing_reaction) else "middle")
        strategy = beat_authoring.select_visual_strategy(text, position, prior_strategy)
        prior_strategy = strategy
        camera = beat_authoring.select_camera_strategy(strategy, i)
        beats.append({
            "beat_id": f"beat_{i:02d}",
            "text": text,
            "visual_strategy": strategy,
            "visual_id": f"{scene['id']}.auto.{i:02d}.{strategy}",
            "animation_strategy": f"auto:{strategy}",
            "camera_strategy": camera,
            "character_pose": "explaining" if strategy in
                ("diagram_build", "comparison", "character_interaction", "establishing_visual") else None,
        })
        weights.append(max(1, len(text.split())))

    if include_closing_reaction:
        strategy = "character_interaction" if prior_strategy != "character_interaction" else "transition_visual"
        camera = beat_authoring.select_camera_strategy(strategy, len(beat_texts))
        beats.append({
            "beat_id": f"beat_{len(beat_texts):02d}_reaction",
            "text": "",
            "visual_strategy": strategy,
            "visual_id": f"{scene['id']}.auto.{len(beat_texts):02d}.{strategy}",
            "animation_strategy": f"auto:{strategy}",
            "camera_strategy": camera,
            "character_pose": "explaining",
        })
        weights.append(CLOSING_REACTION_WEIGHT)

    total_weight = sum(weights)
    shots = []
    cursor = start
    for i, (beat, weight) in enumerate(zip(beats, weights)):
        is_last = i == len(beats) - 1
        shot_end = end if is_last else cursor + duration * (weight / total_weight)
        shots.append({
            "shot_id": f"{scene['id']}.{beat['beat_id']}",
            "scene_id": scene["id"],
            "beat_id": beat["beat_id"],
            "narration_text": beat["text"],
            "visual_strategy": beat["visual_strategy"],
            "visual_type": beat["visual_strategy"],
            "visual_id": beat["visual_id"],
            "animation_strategy": beat["animation_strategy"],
            "camera_strategy": beat["camera_strategy"],
            "character_pose": beat["character_pose"],
            "entities": entities,
            "start": round(cursor, 3),
            "end": round(shot_end, 3),
            "duration": round(shot_end - cursor, 3),
        })
        cursor = shot_end

    return {"version": 1, "scene_id": scene["id"], "shots": shots}
