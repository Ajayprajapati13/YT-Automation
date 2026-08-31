# Video pipeline architecture audit (2026-08-31)

Scope note: the repository currently has three diverged branches from the
same base commit (`8e5c946`, end of TASK-011): `main`, `fix/shot-driven-video-pipeline`
(this audit; current branch at the time of writing), and
`feat/ai-supervisor-control-loop` (where Task 0003's actual documentary was
produced). The shot-planning work described below (`shot_planner.py`,
`create_shot_driven_video.py`) exists only on this branch and was **not**
used to produce the Task 0003 video - that used the plain scene-engine path.
Cross-branch facts here came from read-only `git show`/`git ls-tree`, no
branch switch.

## 1. How does the current pipeline create the final video?

Every production script (`create_gpu_explainer.py`, and - on the other
branch - `create_hf_incident_documentary.py`) follows the same sequence:

1. Load a script JSON (`content/*_script.json`) - a list of scene objects
   (`id`, `title_lines`, `narration`).
2. `synthesize_scene_narration()` - one TTS call per scene via
   `motion_graphics.synthesize_narration()` (Windows SAPI,
   `System.Speech.Synthesis`), writing one `.wav` per scene and measuring
   its real duration with `ffprobe`.
3. `compute_timeline()` - assigns each scene a `start`/`end` from its
   *measured* narration length + fixed lead-in/tail constants
   (`LEAD_IN=0.4`, `TAIL=1.1`).
4. `build_scene_objects()` - wraps each scene in a `scene_engine.Scene`,
   pairing it with a hand-written `draw_diagram` function from a
   per-script `SCENE_BUILDERS` dict.
5. `scene_engine.render_scenes(scenes, theme, background)` - returns one
   `draw_frame(t, frame_index, total_frames)` closure covering the whole
   video.
6. `motion_graphics.render_video(draw_frame, duration, path, ...)` - calls
   `draw_frame` for every frame at 30fps, pipes raw RGB bytes into one
   `ffmpeg` process (`-f rawvideo`), producing a silent MP4.
7. `build_combined_audio()` / `build_narration_track()` - ffmpeg
   `adelay`+`amix` (or `concat`, in the HF-incident variant) stitches
   per-scene WAVs into one narration track at the correct offsets.
8. `mux_video_audio()` - one ffmpeg call muxes silent video + narration
   into the final MP4.

## 2. Does it generate a scene/shot/timeline before rendering?

Scene-level timeline: yes, everywhere. `compute_timeline()`/`build_timeline()`
run before any frame is drawn.

Shot-level timeline: only on this branch, only in `shot_planner.py`.
`create_shot_driven_video.py` explicitly comments
`# CRITICAL: produce the shot list before any video frame is rendered`,
calls `shot_planner.build_shot_plan(scenes_with_timeline)`, and persists it
to `output/gpu_explainer_shot_plan.json` before rendering starts. This
matches the target pattern structurally - but see Q5/Q8: it carries only
timing and camera-motion, not visual content.

## 3. Is narration divided into scene/beat/shot segments, or one long narration per scene?

One narration string per scene, synthesized as one WAV. No beat- or
shot-level narration segmentation exists anywhere. `shot_planner.build_shot_plan()`
splits *scene duration* into shot-length windows (`MIN_SHOT=2.8s`-`MAX_SHOT=5.0s`)
purely arithmetically - it does not touch or re-segment the narration text
or audio.

## 4. How long can one visual remain on screen?

Without the shot planner (the branch that actually shipped Task 0003):
unbounded - as long as the scene lasts. `create_hf_incident_documentary.py`'s
`node_box()` has a "breathe" pulse specifically because *"Long documentary
scenes hold a box on screen for 30-50s; without this, a box that finishes
its entrance in ~0.5s reads as a dead static slide for the rest of the
scene."*

With the shot planner (this branch, unmerged): `build_shot_plan()` enforces
`MAX_SHOT=5.0s` per shot and asserts it - but this caps how long the
*camera framing* holds, not the underlying diagram (see Q5).

## 5. Does each shot have its own visual asset, or is the same diagram reused with only camera motion?

Same diagram reused; only camera motion changes. `create_shot_driven_video.py::apply_shot_motion()`
is a post-processing crop applied via `post_fn` to frames already fully
drawn by the ordinary `scene_engine.render_scenes(scenes, ...)` call, which
has no concept of shots at all. Its own docstring: *"A small animated crop
keeps diagrams/text readable while preventing long static holds."* Diagram
content, layout, and element set are identical across every shot within a
scene; only the crop/zoom/pan window differs.

## 6. What actual animation exists today?

| Type | Exists? | Where |
|---|---|---|
| Camera movement | Yes, two mechanisms | `motion_graphics.Camera` (object-level, applied to diagram coordinates only); `apply_shot_motion()` (whole-frame crop/zoom/pan, this branch only) |
| Object movement | Yes | `mg.draw_arrow` (animated growth), `agent_grid`'s per-dot staggered build-in |
| Particles / data flows | Yes | `mg.traveling_dots()` - dots looping along a path |
| Diagrams building | Yes | `node_box`/`core_grid` staggered `ease_out_back` per-element entrance; `checklist()` staggered item reveal |
| Kinetic text | Yes | `mg.text_reveal()` (left-to-right wipe), `stat_reveal()` (scale-in numbers) |
| Transitions | Yes | `scene_engine.Scene.alpha()` cross-fade + `transition_sweep()` light-sweep band at every scene boundary |
| B-roll / video clips | No | No `VideoFileClip`/stock/`moviepy` reference anywhere in `src/`. Only procedurally-drawn Pillow diagrams and one static character reference sheet cropped into poses |

## 7. Does the architecture support changing visuals every ~3-5 seconds?

Camera framing: yes, but only on this unmerged branch. Visual content: no,
on either branch. Even where the shot planner runs, it changes the crop
window, not the diagram.

## 8. Does it support different visual types within one narration segment?

No. One `draw_diagram` function is bound to one `Scene` = one narration
segment, for that segment's entire duration, in both branches. The shot
planner introduces sub-scene time windows but not sub-scene visual-type
switching.

## 9. Cinematic documentary pipeline, or fundamentally still slide architecture?

Structurally still slide architecture, with cinematic surface polish. The
unit of visual change is the scene (often 15-50+ seconds), not the shot.
Within that unit the frame is genuinely animated (camera drift, particle
flow, staggered builds, glow) - real motion-graphics work, not static
slides - but composition/content doesn't change until the next scene. The
codebase's own comments confirm this is a recognized problem: the
`node_box` "breathe" animation exists specifically to disguise a 30-50s
static hold, and `shot_planner.py`/`create_shot_driven_video.py` were
written specifically to address it - they just haven't been connected to a
real production script or merged into the branch that ships videos.

## 10. Files/functions per part

| Part | File | Function/class |
|---|---|---|
| Script -> timeline | `create_gpu_explainer.py`, `create_hf_incident_documentary.py` | `synthesize_scene_narration`, `compute_timeline`/`build_timeline` |
| Shot list (timing only) | `shot_planner.py` | `build_shot_plan`, `write_shot_plan` |
| Shot-driven entry point | `create_shot_driven_video.py` | `main`, `apply_shot_motion` |
| Scene/render engine | `scene_engine.py` | `Scene`, `render_scenes`, `safe_character`, `transition_sweep` |
| Animation primitives | `motion_graphics.py` | `Camera`, `text_reveal`, `traveling_dots`, `draw_rounded_rect`/`draw_arrow`/`draw_dot`, easing fns |
| Raw-frame -> ffmpeg render | `motion_graphics.py` | `render_video`, `find_ffmpeg` |
| TTS | `motion_graphics.py` | `synthesize_narration` (Windows SAPI) |
| Audio mux/mix | `create_gpu_explainer.py` | `build_combined_audio`, `mux_video_audio` |
| Character system | `character_assets.py` | `load_poses`, `hand_point`, `paste_character` |
| Per-diagram content | `create_gpu_explainer.py`, `create_hf_incident_documentary.py` | `SCENE_BUILDERS` dict + one `make_*`/`*_diagram` function per scene |
| Design-intent doc | `docs/visual_system.md` | TASK-010 "locked visual system", scene 9-field contract |

## Target pipeline comparison

`Script -> narration/beat segmentation -> shot list/timeline -> visual
strategy per shot -> asset generation/selection -> animation/compositing ->
audio synchronization -> chunk/shot rendering -> final assembly`

| Stage | Status | Evidence |
|---|---|---|
| Script | Have | `content/*_script.json` |
| Narration/beat segmentation | Partial - scene-level only | `synthesize_scene_narration` |
| Shot list/timeline | Partial - timing-only, unmerged | `shot_planner.build_shot_plan` |
| Visual strategy per shot | Missing | n/a |
| Asset generation/selection | Have, but scene-granular | `SCENE_BUILDERS` |
| Animation/compositing | Have | `motion_graphics.py`, `scene_engine.py` |
| Audio synchronization | Have, scene-granular | `compute_timeline`, `build_combined_audio` |
| Chunk/shot rendering | Have (chunk), not shot | `render_hf_incident_chunks.py` (other branch; render-robustness chunking, not shot-aligned) |
| Final assembly | Have | `mux_video_audio` |

## A. What we already have
- A working, narration-duration-driven, scene-level render pipeline
  shipping real output (both branches).
- A reusable, well-factored animation/compositing engine
  (`motion_graphics.py` + `scene_engine.py`).
- A locked design-intent document (`docs/visual_system.md`) with a 9-field
  scene contract.
- A first-pass shot-timing planner with duration caps and motion cycling
  (`shot_planner.py`, this branch, unmerged, unused in production).
- A robust, resumable chunked-rendering driver for long videos
  (`render_hf_incident_chunks.py`, other branch).

## B. What was just added
Nothing on this branch as part of this audit - the shot planner predates
it. On `feat/ai-supervisor-control-loop`, earlier the same session,
`render_hf_incident_chunks.py` was added: an idempotent, bounded-per-chunk
render/resume driver, purely for rendering robustness (surviving
interruption mid-render); unrelated to shot-level visual variety.

## C. What is still missing
- Beat/shot-level narration segmentation.
- A visual-strategy decision layer that varies visual type per shot, not
  just camera crop.
- Per-shot asset generation/selection distinct from one hand-authored
  diagram function per scene.
- Integration of the shot planner into any script that actually ships a
  video.
- Shot-level camera motion consistent with the codebase's own established
  pattern (`apply_shot_motion` uses whole-frame crop, which `Camera`'s own
  docstring calls out as the inferior, edge-clipping-risk approach).

## D. What should NOT be rewritten
- `motion_graphics.py`'s primitive library end-to-end - granularity-agnostic.
- `scene_engine.py`'s compositing/cross-fade/character-safety plumbing -
  also granularity-agnostic.
- `character_assets.py` - stable, orthogonal.
- `render_hf_incident_chunks.py` - orthogonal concern, composes with any
  shot solution.
- TTS/mux plumbing (`synthesize_narration`, ffmpeg mux commands) - correct
  pattern already, just needs finer granularity.

## E. Minimum architectural changes needed
1. Extend `shot_planner.build_shot_plan()` to attach a visual descriptor
   per shot (e.g. a `diagram_id`), so consuming code can pick a different
   `draw_diagram` per shot instead of one per scene.
2. Change the render entry point so each shot becomes its own
   `scene_engine.Scene`-like unit with its own `draw_diagram`, instead of
   wrapping one scene-level `render_scenes()` output in a post-hoc crop.
   This is the one real rewrite, localized to `create_shot_driven_video.py`.
3. Replace `apply_shot_motion`'s whole-frame crop with `motion_graphics.Camera`
   applied inside each shot's own `draw_diagram`, consistent with the
   codebase's documented preference.
4. Merge this branch's shot-planning work into the line of development
   that actually ships videos (`feat/ai-supervisor-control-loop`) - right
   now they are disconnected, and Task 0003 shipped with zero shot-level
   variety despite this work existing.
5. Define, as a small lookup/rule (not a rewrite), what "visual strategy
   per shot" means concretely for this channel - e.g. cycling through
   {diagram continuation, stat callout, character reaction, kinetic-text-only
   beat} - since nothing upstream currently decides visual kind, only
   visual timing.
