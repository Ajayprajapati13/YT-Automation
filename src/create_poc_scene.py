"""Explainer scene: 'Why AI Companies Need So Many GPUs'.

Builds a single continuous 28s animated explainer scene using the
motion_graphics engine (no static-slide slideshow). Output:
    C:\\YT-Automation\\output\\gpu_motion_v2.mp4

Milestone 2 adds cinematic depth on top of the milestone-1 architecture
(reused as-is): a parallax background layer, a soft node/glow bloom
pass, and lower-third caption cards for typographic hierarchy.
"""

from pathlib import Path
from PIL import Image, ImageDraw

import sys
sys.path.insert(0, str(Path(__file__).parent))

import motion_graphics as mg

BASE_DIR = Path(r"C:\YT-Automation")
OUTPUT_FILE = BASE_DIR / "output" / "gpu_motion_v2.mp4"

DURATION = 28.0

BLUE = (110, 175, 235)
BLUE_BRIGHT = (150, 205, 255)
GREEN = (100, 220, 160)
AMBER = (255, 200, 120)
WHITE = (255, 255, 255)
DIM_TEXT = (170, 190, 215)

PARALLAX_MARGIN = 220
BACKGROUND_WIDE = mg.build_background(width=mg.WIDTH + PARALLAX_MARGIN, height=mg.HEIGHT)

# ------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------

REQUEST_CENTER = (260, 540)
REQUEST_SIZE = (240, 140)

MODEL_CENTER = (760, 540)
MODEL_SIZE = (300, 360)

GPU_SIZE = (180, 150)
GPU_GRID_CENTER = (1520, 540)
GPU_POS = [
    (1300, 430),  # 0 top-left  (single GPU in S3)
    (1520, 430),  # 1 top-mid
    (1740, 430),  # 2 top-right
    (1300, 650),  # 3 bottom-left
    (1520, 650),  # 4 bottom-mid
    (1740, 650),  # 5 bottom-right
]

# GPU appear windows: index 0 appears in S3, 1-5 stagger through S4.
GPU_APPEAR = [
    (7.0, 7.8),
    (12.00, 12.60),
    (12.35, 12.95),
    (12.70, 13.30),
    (13.05, 13.65),
    (13.40, 14.00),
]

CONNECTOR_PAIRS = [(0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (1, 4), (2, 5)]

# Dispatch chain: only GPU 0 and GPU 3 (row leaders) receive arrows
# directly from the model; the rest relay along their row so lines
# never cross through an unrelated GPU box.
CHAIN_SOURCE = {0: "model", 1: 0, 2: 1, 3: "model", 4: 3, 5: 4}

# ------------------------------------------------------------------
# Timeline constants
# ------------------------------------------------------------------

REQUEST_IN = (0.0, 0.9)
CAPTION_1 = (0.3, 1.2, 2.6, 3.3)
CAPTION_1_TEXT = "EVERY AI REQUEST STARTS WITH COMPUTE"

ARROW_REQ_MODEL = (3.0, 3.6)
MODEL_IN = (3.0, 3.9)
CAPTION_2 = (3.0, 3.8, 6.3, 7.0)
CAPTION_2_TEXT = "YOUR REQUEST REACHES THE AI MODEL"

ARROW_MODEL_GPU0 = (7.0, 7.6)
CAPTION_3 = (7.0, 7.8, 11.3, 12.0)
CAPTION_3_TEXT = "ONE GPU PROCESSES THE WORKLOAD"

CAPTION_4 = (12.0, 12.6, 17.3, 18.0)
CAPTION_4_TEXT = "THE WORKLOAD SPLITS INTO PARALLEL TASKS"

CLUSTER_EXPAND = (18.0, 19.5)
CONNECTORS_IN = (18.0, 19.0)
CAPTION_5 = (18.0, 18.7, 23.3, 24.0)
CAPTION_5_TEXT = "GPUS WORK TOGETHER AS A CLUSTER"

DIM_WINDOW = (24.0, 24.8)
FINAL_TEXT_WINDOW = (24.6, 25.6)
FINAL_BAR_WINDOW = (25.6, 26.2)
FINAL_LINE_1 = "AI NEEDS MASSIVE"
FINAL_LINE_2 = "PARALLEL COMPUTING"


# ------------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------------

def arrow_progress(t, start, end):
    return mg.ease_out_cubic(mg.window(t, start, end))


def gpu_box(draw, cx, cy, w, h, label, alpha, t, processing_since=None, color=BLUE):
    if alpha <= 0.001:
        return

    hw, hh = w / 2, h / 2
    box = (cx - hw, cy - hh, cx + hw, cy + hh)

    mg.draw_rounded_rect(draw, box, 16, outline=color, width=4, alpha=alpha)
    mg.draw_text_centered(draw, label, cx, cy - hh + 26, 24, WHITE, alpha=alpha, bold=True)

    if processing_since is not None and t >= processing_since:
        cols, rows = 3, 2
        pad = 18
        top = cy - hh + 48
        cell_w = (w - pad * 2) / cols
        cell_h = (hh * 2 - 48 - pad) / rows

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                lit = mg.pulse((t - processing_since) * 1.3 + idx * 0.18, 1.6)
                x0 = cx - hw + pad + c * cell_w
                y0 = top + r * cell_h
                x1 = x0 + cell_w - 6
                y1 = y0 + cell_h - 6
                mg.draw_rounded_rect(
                    draw, (x0, y0, x1, y1), 4,
                    outline=color, width=2,
                    fill=color, alpha=alpha * (0.10 + 0.55 * lit),
                )


def pipeline_arrow(draw, start, end, t, grow_start, grow_end, alpha=1.0,
                    color=BLUE_BRIGHT, dot_color=BLUE_BRIGHT, width=6,
                    dot_period=0.8, dot_count=3):
    progress = arrow_progress(t, grow_start, grow_end)
    mg.draw_arrow(draw, start, end, progress=progress, color=color, width=width, alpha=alpha)
    if t >= grow_end:
        mg.traveling_dots(draw, start, end, t - grow_end, dot_period, dot_count,
                           dot_color, radius=5, alpha=alpha * 0.9)


def caption(draw, text, alpha):
    """Lower-third style caption: soft card behind bold centered text."""
    if alpha <= 0.001:
        return

    size = 44
    cx, cy = mg.WIDTH / 2, 130
    tw, th = mg.text_size(draw, text, size, bold=True)
    pad_x, pad_y = 34, 20

    box = (cx - tw / 2 - pad_x, cy - th / 2 - pad_y,
           cx + tw / 2 + pad_x, cy + th / 2 + pad_y)

    mg.draw_rounded_rect(draw, box, 14, fill=(8, 14, 24), alpha=alpha * 0.55)
    mg.draw_rounded_rect(draw, box, 14, outline=BLUE, width=2, alpha=alpha * 0.5)
    mg.draw_text_centered(draw, text, cx, cy, size, WHITE, alpha=alpha, bold=True)


def task_token(draw, start, end, t, spawn_time, duration=0.5, color=AMBER, alpha=1.0):
    if t < spawn_time or t > spawn_time + duration:
        return
    p = mg.ease_in_out_cubic((t - spawn_time) / duration)
    pos = mg.point_on_segment(start, end, p)
    fade = min(1.0, 6 * p, 6 * (1 - p))
    size = 9
    draw.rectangle(
        (pos[0] - size, pos[1] - size, pos[0] + size, pos[1] + size),
        fill=mg.rgba(color, alpha * max(0.0, fade)),
    )


def scene_dim(t):
    return mg.lerp(1.0, 0.20, mg.ease_out_cubic(mg.window(t, *DIM_WINDOW)))


def cluster_expand_factor(t):
    return mg.lerp(1.0, 1.10, mg.ease_in_out_cubic(mg.window(t, *CLUSTER_EXPAND)))


def gpu_center(i, t):
    bx, by = GPU_POS[i]
    factor = cluster_expand_factor(t)
    cx = GPU_GRID_CENTER[0] + (bx - GPU_GRID_CENTER[0]) * factor
    cy = GPU_GRID_CENTER[1] + (by - GPU_GRID_CENTER[1]) * factor
    return cx, cy


def compute_zoom(t):
    if t <= 24.0:
        return mg.lerp(1.0, 1.05, t / 24.0)
    return mg.lerp(1.05, 1.09, mg.ease_out_cubic(mg.window(t, 24.0, 26.0)))


# ------------------------------------------------------------------
# Frame drawing
# ------------------------------------------------------------------

def draw_pipeline(draw, t, glow):
    dim = scene_dim(t)

    # --- Request node ---
    req_progress = mg.ease_out_back(mg.window(t, *REQUEST_IN))
    req_alpha = mg.fade_window(t, REQUEST_IN[0], REQUEST_IN[1]) * dim
    if req_alpha > 0.001:
        rx = mg.lerp(-260, REQUEST_CENTER[0], req_progress)
        ry = REQUEST_CENTER[1]
        rw, rh = REQUEST_SIZE
        box = (rx - rw / 2, ry - rh / 2, rx + rw / 2, ry + rh / 2)
        mg.draw_rounded_rect(draw, box, 16, outline=BLUE, width=4, alpha=req_alpha)
        mg.draw_text_centered(draw, "REQUEST", rx, ry - 20, 30, WHITE, alpha=req_alpha, bold=True)
        mg.draw_dot(draw, (rx, ry + 28), 10, AMBER, alpha=req_alpha)
        glow.append(("rect", box, 16, BLUE, req_alpha * 0.5))

    caption(draw, CAPTION_1_TEXT, mg.fade_window(t, *CAPTION_1) * dim)

    # --- Request -> Model arrow ---
    req_edge = (REQUEST_CENTER[0] + REQUEST_SIZE[0] / 2 + 10, REQUEST_CENTER[1])
    model_left_edge = (MODEL_CENTER[0] - MODEL_SIZE[0] / 2 - 10, MODEL_CENTER[1])
    pipeline_arrow(draw, req_edge, model_left_edge, t, *ARROW_REQ_MODEL, alpha=dim)

    # --- AI Model node ---
    model_progress = mg.ease_out_back(mg.window(t, *MODEL_IN))
    model_alpha = mg.fade_window(t, MODEL_IN[0], MODEL_IN[1]) * dim
    if model_alpha > 0.001:
        scale = mg.lerp(0.6, 1.0, model_progress)
        mw, mh = MODEL_SIZE[0] * scale, MODEL_SIZE[1] * scale
        cx, cy = MODEL_CENTER
        box = (cx - mw / 2, cy - mh / 2, cx + mw / 2, cy + mh / 2)
        mg.draw_rounded_rect(draw, box, 22, outline=BLUE_BRIGHT, width=6, alpha=model_alpha)
        mg.draw_text_centered(draw, "AI", cx, cy - 30, 60, WHITE, alpha=model_alpha, bold=True)
        mg.draw_text_centered(draw, "MODEL", cx, cy + 30, 34, DIM_TEXT, alpha=model_alpha, bold=True)
        glow.append(("rect", box, 22, BLUE_BRIGHT, model_alpha * 0.55))

    caption(draw, CAPTION_2_TEXT, mg.fade_window(t, *CAPTION_2) * dim)
    caption(draw, CAPTION_3_TEXT, mg.fade_window(t, *CAPTION_3) * dim)
    caption(draw, CAPTION_4_TEXT, mg.fade_window(t, *CAPTION_4) * dim)
    caption(draw, CAPTION_5_TEXT, mg.fade_window(t, *CAPTION_5) * dim)

    # --- Model -> GPUs (chained per row so lines never cross a box) ---
    model_right_edge = (MODEL_CENTER[0] + MODEL_SIZE[0] / 2 + 10, MODEL_CENTER[1])
    gw, gh = GPU_SIZE

    for i in range(6):
        grow_start, grow_end = GPU_APPEAR[i] if i > 0 else ARROW_MODEL_GPU0
        cx, cy = gpu_center(i, t)

        source = CHAIN_SOURCE[i]
        if source == "model":
            start = model_right_edge
        else:
            scx, scy = gpu_center(source, t)
            start = (scx + gw / 2 + 10, scy)

        left_edge = (cx - gw / 2 - 10, cy)
        pipeline_arrow(
            draw, start, left_edge, t, grow_start, grow_end,
            alpha=dim, dot_color=BLUE_BRIGHT,
        )

        task_token(draw, start, left_edge, t, grow_end, alpha=dim)

        appear_start, appear_end = GPU_APPEAR[i]
        box_progress = mg.ease_out_back(mg.window(t, appear_start, appear_end))
        box_alpha = mg.fade_window(t, appear_start, appear_end) * dim

        if box_alpha > 0.001:
            box_scale = mg.lerp(0.5, 1.0, box_progress)
            sw, sh = gw * box_scale, gh * box_scale
            gpu_box(
                draw, cx, cy, sw, sh,
                f"GPU {i + 1}", box_alpha, t,
                processing_since=appear_end, color=BLUE,
            )
            pulse_avg = mg.pulse((t - appear_end) * 1.3, 1.6) if t >= appear_end else 0.0
            gbox = (cx - sw / 2, cy - sh / 2, cx + sw / 2, cy + sh / 2)
            glow.append(("rect", gbox, 16, BLUE, box_alpha * (0.18 + 0.20 * pulse_avg)))

    # --- Cluster interconnects ---
    connector_alpha = mg.fade_window(t, *CONNECTORS_IN) * dim * 0.5
    if connector_alpha > 0.001:
        for a, b in CONNECTOR_PAIRS:
            if t < GPU_APPEAR[a][1] or t < GPU_APPEAR[b][1]:
                continue
            ca = gpu_center(a, t)
            cb = gpu_center(b, t)
            gw, gh = GPU_SIZE
            dx, dy = cb[0] - ca[0], cb[1] - ca[1]
            length = max(1.0, (dx ** 2 + dy ** 2) ** 0.5)
            ux, uy = dx / length, dy / length
            start = (ca[0] + ux * gw / 2, ca[1] + uy * gh / 2)
            end = (cb[0] - ux * gw / 2, cb[1] - uy * gh / 2)
            mg.draw_arrow(draw, start, end, progress=1.0, color=GREEN, width=2, alpha=connector_alpha)
            if t >= CONNECTORS_IN[1]:
                mg.traveling_dots(draw, start, end, t - CONNECTORS_IN[1], 1.1, 2,
                                   GREEN, radius=4, alpha=dim * 0.8, phase_offset=(a + b) * 0.13)


def draw_final_statement(rgb_image, t):
    progress = mg.ease_out_back(mg.window(t, *FINAL_TEXT_WINDOW))
    alpha = mg.fade_window(t, *FINAL_TEXT_WINDOW)

    if alpha > 0.001:
        def glow_fn(d, s):
            cx, cy = mg.WIDTH / 2, mg.HEIGHT / 2
            d.ellipse(
                ((cx - 380) * s, (cy - 120) * s, (cx + 380) * s, (cy + 120) * s),
                fill=mg.rgba(BLUE_BRIGHT, alpha * 0.16),
            )
        rgb_image = mg.glow_composite(rgb_image, glow_fn, blur_radius=40, downsample=4)

    rgba_image = rgb_image.convert("RGBA")
    layer = Image.new("RGBA", rgba_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")

    dim_alpha = mg.fade_window(t, *DIM_WINDOW) * 0.55
    if dim_alpha > 0.001:
        draw.rectangle((0, 0, mg.WIDTH, mg.HEIGHT), fill=mg.rgba((0, 0, 0), dim_alpha))

    if alpha > 0.001:
        scale = mg.lerp(0.85, 1.0, progress)
        cy = mg.HEIGHT / 2

        size1 = int(78 * scale)
        size2 = int(78 * scale)

        mg.draw_text_centered(draw, FINAL_LINE_1, mg.WIDTH / 2, cy - 60 * scale, size1,
                               WHITE, alpha=alpha, bold=True)
        mg.draw_text_centered(draw, FINAL_LINE_2, mg.WIDTH / 2, cy + 60 * scale, size2,
                               BLUE_BRIGHT, alpha=alpha, bold=True)

    bar_progress = mg.ease_in_out_cubic(mg.window(t, *FINAL_BAR_WINDOW))
    if bar_progress > 0.001:
        bar_w = 480 * bar_progress
        cy = mg.HEIGHT / 2 + 130
        cx = mg.WIDTH / 2
        draw.rectangle(
            (cx - bar_w / 2, cy, cx + bar_w / 2, cy + 5),
            fill=mg.rgba(AMBER, alpha),
        )

    composed = Image.alpha_composite(rgba_image, layer)
    return composed.convert("RGB")


def draw_frame(t, frame_index, total_frames):
    base = mg.parallax_crop(BACKGROUND_WIDE, t, mg.WIDTH, mg.HEIGHT).convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")

    glow_sources = []
    draw_pipeline(draw, t, glow_sources)

    composed = Image.alpha_composite(base, layer)
    rgb = composed.convert("RGB")

    if t < 23.6 and glow_sources:
        def glow_fn(d, s):
            for kind, box, radius, color, a in glow_sources:
                if a <= 0.001:
                    continue
                x0, y0, x1, y1 = box
                width = max(1, round(14 * s))
                d.rounded_rectangle(
                    (x0 * s, y0 * s, x1 * s, y1 * s), radius=radius * s,
                    outline=mg.rgba(color, min(1.0, a)), width=width,
                )
        rgb = mg.glow_composite(rgb, glow_fn, blur_radius=14, downsample=3)

    zoom = compute_zoom(t)
    rgb = mg.apply_zoom(rgb, zoom, focus=(0.56, 0.46))

    if t >= 23.6:
        rgb = draw_final_statement(rgb, t)

    return rgb


def main():
    ffmpeg = mg.find_ffmpeg()
    print(f"FFmpeg: {ffmpeg}")
    print(f"Rendering {DURATION}s @ {mg.FPS}fps -> {OUTPUT_FILE}")

    mg.render_video(
        draw_frame,
        DURATION,
        OUTPUT_FILE,
        ffmpeg=ffmpeg,
        crf=18,
        preset="medium",
    )

    print("Done.")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
