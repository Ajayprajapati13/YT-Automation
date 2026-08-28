# Visual System (locked, TASK-010)

This is the channel's default production style, locked after the
TASK-009 proof. It applies to all future scenes/videos built on this
pipeline unless a task explicitly says otherwise.

## Locked visual direction

- White / near-white background (`create_poc_scene.LIGHT_THEME`).
- The existing fictional presenter (`assets/character/character_reference_sheet.png`)
  is the canonical character. Do not redesign it, and never approximate
  a human character by drawing one with Pillow primitives — only crop
  real reference art (see `character_assets.py`).
- Blue/teal technical palette, restrained accents.
- Character-led storytelling, not slide-like presentation: every scene
  groups its diagram with the presenter inside a shared "stage" panel
  (`scene_engine.stage_panel`) rather than floating each in empty
  canvas.
- Cinematic composition: purposeful camera movement, object-level
  animation (cells/particles/grid cells animate individually, not just
  a whole-frame pan), connected transitions between scenes, restrained
  glow.
- Narration drives scene timing — video duration is derived from the
  actual synthesized narration length (`mg.synthesize_narration()` +
  `ffprobe`), not hand-picked.

## Cinematic character direction

Currently usable poses, extracted from the reference sheet by
`character_assets.load_poses()` (adaptive alpha-valley boundaries, not
a fixed equal-width split — see that module's docstring):

| pose | reads as | current use |
|---|---|---|
| `introg` | confident hook / welcoming | HOOK intro, SCALE |
| `explaining` | open-hand explaining / pointing | CPU_VS_GPU, GPU_AI |
| `thinking` | thoughtful / reaction | PARALLEL |
| `closing` | clean closing / emphasis | TAKEAWAY |
| `reference` | — | **not used** — its own hand has no true zero-alpha gap to its neighbour in the source sheet (confirmed: increasing the crop trim cuts into opaque arm content rather than removing bleed). If a "reference" or "emphasis" pose is needed later, treat it as a new asset requirement rather than forcing this one. |

Rules for staging a pose:

- Placement always goes through `scene_engine.safe_character()`, which
  clamps position so the sprite can never clip a frame edge — this is
  a hard requirement, not a style choice.
- Camera work (`motion_graphics.Camera`) is applied to diagram
  coordinates only, never to the character's own placement, so a
  camera push/pan can never move the character off-frame or resize it
  unexpectedly.
- Scale/placement/flip are used to make a pose feel intentional (e.g.
  `explaining` is mirrored to face whichever side the diagram is on).
  Do not invent a new pose by drawing on top of the character.
- When a scene needs the presenter to reference a specific diagram
  element, use `scene_engine.hand_connector()` to draw a line from the
  character's approximate hand position (`character_assets.hand_point()`)
  to that element, instead of relying on proximity alone.

## Scene contract

Every scene in the video is a `scene_engine.Scene` (see that module's
docstring for the full field list). This is the 9-field contract
TASK-010 asked for, and what `create_character_proof.SCENES` is an
instance of:

1. **metadata/story beat** — `Scene.id`, `Scene.title`
2. **narration segment** — `Scene.narration` (the text this scene
   covers; today the video's narration is still one script file read
   as a whole — see "Known gap" below)
3. **character pose/placement** — decided inside `draw_diagram`,
   returned as `(pose, cx, bottom_y, height, alpha, flip)` via
   `safe_character()`
4. **background/stage** — `Scene.stage_box` (a stage panel rect, or
   `None` to skip it, as TAKEAWAY does)
5. **diagram/technical visual layers** — the body of `draw_diagram`
6. **object animations/data flows** — drawn inside `draw_diagram`
   using shared primitives (`core_grid`'s staggered cell build-in,
   `mg.traveling_dots`, etc.)
7. **camera actions** — a `motion_graphics.Camera` built inside
   `draw_diagram`, applied to diagram coordinates only
8. **transition** — `Scene.fade` / `Scene.overlap` (cross-fade timing)
   plus the automatic light-sweep `scene_engine` draws at every scene
   boundary
9. **timing/validation** — `Scene.start` / `Scene.end` / `Scene.validation`

### Adding a new scene

Append a `Scene(...)` to the list passed to `scene_engine.render_scenes()`
with a new `draw_diagram(draw, layer, t, alpha, glow) -> character_tuple | None`
function. You do **not** need to re-implement cross-fade timing, the
transition sweep, the glow blur pass, or "only one character renders
during a cross-fade" — `scene_engine.render_scenes()` already handles
all of that for every scene in the list.

### Known gap (not fixed by TASK-010)

The `narration` field currently documents each scene's intended text,
but `create_character_proof.main()` still synthesizes narration from
one flat script file (`content/gpu_character_proof_script.txt`) rather
than stitching together `Scene.narration` segments with per-scene
timing. Wiring narration synthesis to the scene list directly (so
`Scene.narration` is the single source of truth, and scene timing can
be derived from each segment's own synthesized length) is the natural
next architectural step before the full multi-minute video, where
hand-tuning one global script against ~15+ scenes would get unwieldy.
