"""Generic, scene-agnostic beat segmentation and visual-strategy selection.

This is what makes the shot-driven architecture reusable across scenes
instead of N hand-coded one-offs: segment_narration_into_beats() and
select_visual_strategy() operate on any narration text with the same
deterministic rules regardless of which scene it came from. Only the
per-scene DATA (content/gpu_scene_concepts.json - entity labels the
generic visual-strategy builders draw) is scene-specific; the logic that
turns narration into beats, and beats into strategies, is not.

Deterministic throughout - no randomness anywhere in this module.
"""
from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_COMMA_SPLIT = re.compile(r",\s+")

NUMBER_WORDS = {
    "million", "millions", "billion", "billions", "thousand", "thousands",
    "hundred", "hundreds", "dozens", "dozen",
}
COMPARISON_MARKERS = ("unlike", " vs ", "vs.", "compared to", "instead of", "rather than", " versus ")
FLOW_MARKERS = ("flow", "send", "sends", "stream", "travel", "move", "moves", "transfer",
                "request", "requests", "connect", "connects", "deliver")

MAX_WORDS_PER_BEAT = 22


def segment_narration_into_beats(narration: str, max_words: int = MAX_WORDS_PER_BEAT) -> list:
    """Splits on sentence boundaries; a sentence longer than max_words is
    split once more, at whichever comma falls nearest its midpoint.
    Deterministic - same input always produces the same beats, no
    per-scene special-casing."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(narration.strip()) if s.strip()]
    beats = []
    for sent in sentences:
        if len(sent.split()) <= max_words:
            beats.append(sent)
            continue
        commas = [m.start() for m in _COMMA_SPLIT.finditer(sent)]
        if not commas:
            beats.append(sent)
            continue
        mid = len(sent) / 2
        split_at = min(commas, key=lambda i: abs(i - mid))
        first, second = sent[: split_at + 1].strip(), sent[split_at + 1 :].strip()
        if first:
            beats.append(first)
        if second:
            beats.append(second)
    return beats


def _has_number(text: str) -> bool:
    if any(ch.isdigit() for ch in text):
        return True
    lower_words = text.lower().split()
    return any(w.strip(".,") in NUMBER_WORDS for w in lower_words)


def select_visual_strategy(beat_text: str, position: str, prior_strategy: str = None) -> str:
    """position: 'first' | 'middle' | 'last'.

    Deterministic priority order - content signals before position,
    position before the generic default - so a strongly-signalled beat (a
    real number, an explicit comparison) is never overridden just because
    it happens to open or close a scene. If the top candidate equals
    prior_strategy and another candidate is also available, that one is
    used instead - avoids an immediate repeat without any randomness.
    """
    lower = beat_text.lower()
    candidates = []
    if _has_number(beat_text):
        candidates.append("stat_callout")
    if any(m in lower for m in COMPARISON_MARKERS):
        candidates.append("comparison")
    if any(m in lower for m in FLOW_MARKERS):
        candidates.append("data_flow")
    if position == "first":
        candidates.append("establishing_visual")
    if position == "last":
        candidates.append("character_interaction")
    if lower.count(",") >= 2:
        candidates.append("diagram_build")
    candidates.append("diagram_build")  # always-available fallback

    for c in candidates:
        if c != prior_strategy:
            return c
    return candidates[0]


CAMERA_DEFAULTS = {
    "establishing_visual": {"kind": "pull_out", "scale_from": 1.05, "scale_to": 1.0},
    "diagram_build": {"kind": "push_in", "scale_from": 1.0, "scale_to": 1.08},
    "comparison": {"kind": "pull_out", "scale_from": 1.1, "scale_to": 1.0},
    "stat_callout": {"kind": "static", "scale_from": 1.0, "scale_to": 1.0},
    "data_flow": {"kind": "push_in", "scale_from": 1.0, "scale_to": 1.15},
    "character_interaction": {"kind": "static", "scale_from": 1.0, "scale_to": 1.0},
    "kinetic_text": {"kind": "static", "scale_from": 1.0, "scale_to": 1.0},
    "close_up_detail": {"kind": "push_in", "scale_from": 1.0, "scale_to": 1.2},
    "transition_visual": {"kind": "static", "scale_from": 1.0, "scale_to": 1.0},
}

# Anchors cycle deterministically by beat index (not randomly) so two
# shots sharing a strategy elsewhere in a video don't push/pull on the
# exact same point.
ANCHOR_CYCLE = ((760, 540), (1160, 540), (960, 460), (960, 640))


def select_camera_strategy(strategy: str, beat_index: int) -> dict:
    base = dict(CAMERA_DEFAULTS.get(strategy, CAMERA_DEFAULTS["diagram_build"]))
    base["anchor"] = list(ANCHOR_CYCLE[beat_index % len(ANCHOR_CYCLE)])
    return base
