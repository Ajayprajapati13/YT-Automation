"""Reusable frame-by-frame motion graphics engine.

Renders animated scenes by generating raw RGB frames with Pillow and
streaming them directly into FFmpeg (stdin, rawvideo) to produce an H.264
MP4 — no intermediate PNG sequence, no static-slide zoompan tricks.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import subprocess
import math

WIDTH = 1920
HEIGHT = 1080
FPS = 30

FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")

_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        path = FONT_BOLD if bold and FONT_BOLD.exists() else FONT_REGULAR
        _font_cache[key] = ImageFont.truetype(str(path), size)
    return _font_cache[key]


def find_ffmpeg():
    packages = (
        Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    )

    matches = [
        p for p in packages.rglob("ffmpeg.exe") if "Gyan.FFmpeg.Shared" in str(p)
    ]

    if not matches:
        raise FileNotFoundError("FFmpeg executable was not found.")

    return matches[0]


# ------------------------------------------------------------------
# Easing / interpolation helpers
# ------------------------------------------------------------------

def clamp01(t):
    return max(0.0, min(1.0, t))


def lerp(a, b, t):
    return a + (b - a) * t


def window(t, start, end):
    """Progress 0..1 within [start, end], clamped."""
    if end <= start:
        return 1.0 if t >= end else 0.0
    return clamp01((t - start) / (end - start))


def ease_out_cubic(t):
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    t = clamp01(t)
    if t < 0.5:
        return 4 * t ** 3
    return 1 - ((-2 * t + 2) ** 3) / 2


def ease_out_back(t):
    t = clamp01(t)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def fade_window(t, in_start, in_end, out_start=None, out_end=None):
    """Alpha envelope: eases in over [in_start,in_end], holds at 1,
    optionally eases out over [out_start,out_end]."""
    if t < in_start:
        return 0.0
    if t < in_end:
        return ease_out_cubic(window(t, in_start, in_end))
    if out_start is None:
        return 1.0
    if t < out_start:
        return 1.0
    if t < out_end:
        return 1.0 - ease_in_out_cubic(window(t, out_start, out_end))
    return 0.0


def pulse(t, period):
    """0..1..0 triangular pulse, looping every `period` seconds."""
    phase = (t % period) / period
    return 1.0 - abs(2 * phase - 1.0)


# ------------------------------------------------------------------
# Color helpers
# ------------------------------------------------------------------

def rgba(color, alpha=1.0):
    r, g, b = color[:3]
    return (r, g, b, max(0, min(255, int(round(alpha * 255)))))


# ------------------------------------------------------------------
# Drawing primitives (operate on an RGBA layer draw context)
# ------------------------------------------------------------------

def draw_rounded_rect(draw, box, radius, outline=None, width=3, fill=None, alpha=1.0):
    if alpha <= 0.001:
        return
    kwargs = {}
    if fill is not None:
        kwargs["fill"] = rgba(fill, alpha)
    if outline is not None:
        kwargs["outline"] = rgba(outline, alpha)
        kwargs["width"] = width
    draw.rounded_rectangle(box, radius=radius, **kwargs)


def text_size(draw, text, size, bold=False):
    f = font(size, bold)
    box = draw.textbbox((0, 0), text, font=f)
    return box[2] - box[0], box[3] - box[1]


def draw_text(draw, pos, text, size, color, alpha=1.0, bold=False, anchor="la"):
    if alpha <= 0.001:
        return
    draw.text(pos, text, font=font(size, bold), fill=rgba(color, alpha), anchor=anchor)


def draw_text_centered(draw, text, cx, cy, size, color, alpha=1.0, bold=False):
    draw_text(draw, (cx, cy), text, size, color, alpha=alpha, bold=bold, anchor="mm")


def draw_arrow(draw, start, end, progress=1.0, color=(120, 180, 255), width=6, alpha=1.0):
    progress = clamp01(progress)
    if progress <= 0.001 or alpha <= 0.001:
        return

    tip = (
        lerp(start[0], end[0], progress),
        lerp(start[1], end[1], progress),
    )

    draw.line([start, tip], fill=rgba(color, alpha), width=width)

    if progress > 0.97:
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        size = 8 + width * 1.6

        p1 = (
            tip[0] - size * math.cos(angle - 0.5),
            tip[1] - size * math.sin(angle - 0.5),
        )
        p2 = (
            tip[0] - size * math.cos(angle + 0.5),
            tip[1] - size * math.sin(angle + 0.5),
        )

        draw.polygon([tip, p1, p2], fill=rgba(color, alpha))


def draw_dot(draw, pos, radius, color, alpha=1.0):
    if alpha <= 0.001:
        return
    x, y = pos
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=rgba(color, alpha),
    )


def point_on_segment(p0, p1, t):
    return (lerp(p0[0], p1[0], t), lerp(p0[1], p1[1], t))


def traveling_dots(draw, start, end, t, period, count, color, radius=6, alpha=1.0, phase_offset=0.0):
    """Draw `count` dots evenly spaced, looping along start->end forever."""
    if alpha <= 0.001:
        return
    for i in range(count):
        offset = i / count
        phase = ((t / period) + offset + phase_offset) % 1.0
        pos = point_on_segment(start, end, phase)
        fade = min(1.0, 4 * phase, 4 * (1.0 - phase))
        draw_dot(draw, pos, radius, color, alpha=alpha * max(0.0, fade))


# ------------------------------------------------------------------
# Scene background
# ------------------------------------------------------------------

def build_background(width=WIDTH, height=HEIGHT):
    """Dark technology gradient with a faint grid — precomputed once."""
    image = Image.new("RGB", (width, height), (8, 12, 20))
    top = (10, 15, 26)
    bottom = (5, 8, 14)

    pixels = image.load()
    for y in range(height):
        t = y / height
        r = int(lerp(top[0], bottom[0], t))
        g = int(lerp(top[1], bottom[1], t))
        b = int(lerp(top[2], bottom[2], t))
        for x in range(0, width, 4):
            for dx in range(4):
                if x + dx < width:
                    pixels[x + dx, y] = (r, g, b)

    draw = ImageDraw.Draw(image, "RGBA")

    grid_color = (60, 90, 130, 22)
    step = 80
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Vignette
    vignette = Image.new("L", (width, height), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse((-width * 0.3, -height * 0.3, width * 1.3, height * 1.3), fill=90)
    vdraw.ellipse((width * 0.15, height * 0.1, width * 0.85, height * 0.95), fill=0)
    dark = Image.new("RGB", (width, height), (0, 0, 0))
    image = Image.composite(dark, image, vignette)

    return image


# ------------------------------------------------------------------
# Renderer
# ------------------------------------------------------------------

def render_video(draw_frame, duration, output_path, ffmpeg=None, fps=FPS,
                  width=WIDTH, height=HEIGHT, crf=18, preset="medium"):
    """draw_frame(t, frame_index, total_frames) -> PIL.Image (RGB or RGBA)."""

    ffmpeg = ffmpeg or find_ffmpeg()
    total_frames = int(round(duration * fps))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        str(ffmpeg), "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        for frame_index in range(total_frames):
            t = frame_index / fps
            image = draw_frame(t, frame_index, total_frames)
            if image.mode != "RGB":
                image = image.convert("RGB")
            if image.size != (width, height):
                image = image.resize((width, height))
            proc.stdin.write(image.tobytes())
    finally:
        proc.stdin.close()

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{stderr.decode(errors='ignore')}")

    return output_path


def parallax_crop(wide_image, t, width=WIDTH, height=HEIGHT, amplitude=70.0, period=22.0):
    """Slow side-to-side drift across a wider background for a depth cue
    that's independent of any foreground camera zoom/pan."""
    iw, ih = wide_image.size
    max_offset = max(0, iw - width)
    amp = min(amplitude, max_offset / 2)
    center = max_offset / 2
    offset = center + amp * math.sin(2 * math.pi * t / period)
    offset = max(0, min(max_offset, offset))
    left = int(round(offset))
    top = max(0, (ih - height) // 2)
    return wide_image.crop((left, top, left + width, top + height))


def glow_composite(base_rgb, draw_glow_fn, blur_radius=18, downsample=3):
    """Cheap cinematic bloom: draw bright glow-source shapes at reduced
    resolution, blur them, then screen-blend onto the full-res frame.

    draw_glow_fn(draw, scale) draws onto a `scale`-sized (1/downsample)
    transparent layer — multiply coordinates by `scale` when drawing.
    """
    width, height = base_rgb.size
    sw = max(1, width // downsample)
    sh = max(1, height // downsample)

    small = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(small, "RGBA")
    draw_glow_fn(draw, 1.0 / downsample)

    small = small.filter(ImageFilter.GaussianBlur(max(1.0, blur_radius / downsample)))
    big = small.resize((width, height), Image.BILINEAR).convert("RGB")

    return ImageChops.screen(base_rgb, big)


def apply_zoom(image, zoom, focus=(0.5, 0.5)):
    """Subtle zoom/pan: scale the frame up and crop back to original size."""
    if zoom <= 1.0001:
        return image

    width, height = image.size
    zw, zh = int(round(width * zoom)), int(round(height * zoom))
    resized = image.resize((zw, zh), Image.BILINEAR)

    fx, fy = focus
    left = int((zw - width) * fx)
    top = int((zh - height) * fy)
    left = max(0, min(zw - width, left))
    top = max(0, min(zh - height, top))

    return resized.crop((left, top, left + width, top + height))
