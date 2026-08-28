from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math


BASE_DIR = Path(r"C:\YT-Automation")

OUTPUT_DIR = (
    BASE_DIR
    / "assets"
    / "v2"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

WIDTH = 1920
HEIGHT = 1080

FONT = Path(r"C:\Windows\Fonts\arial.ttf")


def font(size):
    return ImageFont.truetype(
        str(FONT),
        size
    )


def background():
    return Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (10, 17, 30)
    )


def title(draw, text, subtitle):

    draw.text(
        (80, 60),
        text,
        font=font(64),
        fill=(255, 255, 255)
    )

    draw.text(
        (82, 140),
        subtitle,
        font=font(30),
        fill=(170, 185, 205)
    )


def center_text(draw, text, y, size=50):

    f = font(size)

    box = draw.textbbox(
        (0, 0),
        text,
        font=f
    )

    x = (
        WIDTH
        - (box[2] - box[0])
    ) // 2

    draw.text(
        (x, y),
        text,
        font=f,
        fill=(255, 255, 255)
    )


def arrow(draw, start, end, width=6):

    draw.line(
        [start, end],
        fill=(120, 180, 255),
        width=width
    )

    angle = math.atan2(
        end[1] - start[1],
        end[0] - start[0]
    )

    size = 22

    p1 = (
        end[0] - size * math.cos(angle - 0.5),
        end[1] - size * math.sin(angle - 0.5)
    )

    p2 = (
        end[0] - size * math.cos(angle + 0.5),
        end[1] - size * math.sin(angle + 0.5)
    )

    draw.polygon(
        [end, p1, p2],
        fill=(120, 180, 255)
    )


def save(image, number):
    path = (
        OUTPUT_DIR
        / f"scene_{number:02d}.png"
    )

    image.save(
        path,
        format="PNG",
        optimize=True
    )

    print(f"Created: {path}")


# ============================================================
# Scene 1
# ============================================================

def scene_01():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "AI LOOKS SIMPLE",
        "But enormous computing happens behind the interface"
    )

    # Laptop
    draw.rounded_rectangle(
        (250, 350, 800, 700),
        radius=25,
        outline=(100, 140, 190),
        width=6
    )

    draw.rectangle(
        (290, 390, 760, 650),
        outline=(70, 110, 160),
        width=4
    )

    center_text(
        draw,
        "AI",
        490,
        80
    )

    # Arrow
    arrow(
        draw,
        (820, 525),
        (1080, 525)
    )

    # Data center
    for row in range(3):
        for col in range(4):

            x = 1120 + col * 150
            y = 350 + row * 150

            draw.rounded_rectangle(
                (x, y, x + 110, y + 100),
                radius=10,
                outline=(90, 150, 210),
                width=5
            )

            draw.ellipse(
                (x + 20, y + 25,
                 x + 35, y + 40),
                fill=(100, 220, 150)
            )

            draw.ellipse(
                (x + 20, y + 55,
                 x + 35, y + 70),
                fill=(100, 180, 240)
            )

    save(image, 1)


# ============================================================
# Scene 2
# ============================================================

def scene_02():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "AI DATA CENTERS",
        "Large-scale computing infrastructure"
    )

    # Floor
    draw.rectangle(
        (150, 850, 1770, 900),
        fill=(25, 35, 52)
    )

    # Server racks
    for col in range(7):

        x = 190 + col * 225

        draw.rounded_rectangle(
            (x, 270, x + 170, 850),
            radius=12,
            outline=(90, 130, 175),
            width=5
        )

        for row in range(8):

            y = 300 + row * 65

            draw.rectangle(
                (x + 20, y,
                 x + 150, y + 40),
                outline=(70, 105, 145),
                width=3
            )

            for light in range(3):

                lx = x + 35 + light * 30

                draw.ellipse(
                    (lx, y + 12,
                     lx + 10, y + 22),
                    fill=(100, 210, 160)
                )

    center_text(
        draw,
        "COMPUTE",
        150,
        44
    )

    save(image, 2)


# ============================================================
# Scene 3
# ============================================================

def scene_03():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "GPUs",
        "Designed for massive parallel computation"
    )

    # Large GPU board
    draw.rounded_rectangle(
        (380, 300, 1540, 780),
        radius=30,
        outline=(90, 150, 210),
        width=8
    )

    # GPU chips
    for row in range(3):
        for col in range(6):

            x = 480 + col * 165
            y = 370 + row * 125

            draw.rounded_rectangle(
                (x, y, x + 120, y + 80),
                radius=10,
                outline=(120, 180, 230),
                width=4
            )

            center = (
                x + 60,
                y + 40
            )

            draw.ellipse(
                (
                    center[0] - 18,
                    center[1] - 18,
                    center[0] + 18,
                    center[1] + 18
                ),
                outline=(160, 210, 255),
                width=4
            )

    center_text(
        draw,
        "MANY PROCESSING UNITS",
        840,
        42
    )

    save(image, 3)


# ============================================================
# Scene 4
# ============================================================

def scene_04():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "PARALLEL PROCESSING",
        "Why GPUs are useful for AI workloads"
    )

    # CPU
    draw.rounded_rectangle(
        (180, 330, 700, 760),
        radius=25,
        outline=(130, 150, 180),
        width=6
    )

    center_text(
        draw,
        "CPU",
        370,
        60
    )

    draw.rectangle(
        (300, 500, 580, 560),
        outline=(130, 150, 180),
        width=4
    )

    center_text(
        draw,
        "FEWER",
        600,
        34
    )

    # GPU
    draw.rounded_rectangle(
        (1100, 250, 1740, 820),
        radius=25,
        outline=(90, 170, 230),
        width=6
    )

    draw.text(
        (1350, 300),
        "GPU",
        font=font(60),
        fill=(255, 255, 255),
        anchor="mm"
    )

    for row in range(5):
        for col in range(5):

            x = 1170 + col * 105
            y = 410 + row * 75

            draw.rectangle(
                (x, y,
                 x + 70,
                 y + 45),
                outline=(100, 180, 240),
                width=3
            )

    draw.text(
        (1420, 730),
        "MANY",
        font=font(34),
        fill=(190, 205, 220),
        anchor="mm"
    )

    arrow(
        draw,
        (730, 545),
        (1080, 545)
    )

    save(image, 4)


# ============================================================
# Scene 5
# ============================================================

def scene_05():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "MEMORY + BANDWIDTH",
        "AI constantly moves data between processors and memory"
    )

    # GPU
    draw.rounded_rectangle(
        (300, 380, 750, 700),
        radius=20,
        outline=(100, 170, 230),
        width=6
    )

    center_text(
        draw,
        "GPU",
        490,
        58
    )

    # Memory
    draw.rounded_rectangle(
        (1170, 350, 1650, 730),
        radius=20,
        outline=(120, 190, 160),
        width=6
    )

    draw.text(
        (1410, 470),
        "MEMORY",
        font=font(48),
        fill=(255, 255, 255),
        anchor="mm"
    )

    draw.text(
        (1410, 570),
        "HIGH SPEED",
        font=font(34),
        fill=(180, 200, 215),
        anchor="mm"
    )

    # Data streams
    for y in range(430, 680, 55):

        arrow(
            draw,
            (780, y),
            (1140, y),
            width=4
        )

    center_text(
        draw,
        "DATA FLOW",
        820,
        38
    )

    save(image, 5)


# ============================================================
# Scene 6
# ============================================================

def scene_06():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "GPU CLUSTERS",
        "Large AI workloads can be distributed across many accelerators"
    )

    centers = []

    for row in range(2):
        for col in range(4):

            cx = 430 + col * 360
            cy = 390 + row * 300

            centers.append(
                (cx, cy)
            )

            draw.rounded_rectangle(
                (
                    cx - 110,
                    cy - 80,
                    cx + 110,
                    cy + 80
                ),
                radius=18,
                outline=(100, 170, 230),
                width=5
            )

            draw.text(
                (cx, cy),
                "GPU",
                font=font(42),
                fill=(255, 255, 255),
                anchor="mm"
            )

    # Connections
    for i in range(len(centers)):

        for j in range(i + 1, len(centers)):

            x1, y1 = centers[i]
            x2, y2 = centers[j]

            if abs(x1 - x2) <= 360:
                draw.line(
                    (x1, y1, x2, y2),
                    fill=(70, 100, 140),
                    width=3
                )

    center_text(
        draw,
        "DISTRIBUTED COMPUTATION",
        900,
        38
    )

    save(image, 6)


# ============================================================
# Scene 7
# ============================================================

def scene_07():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "AI INFERENCE",
        "Every user request requires computing capacity"
    )

    # Users
    for i in range(5):

        y = 280 + i * 125

        draw.ellipse(
            (180, y, 260, y + 80),
            outline=(130, 170, 210),
            width=4
        )

        draw.text(
            (220, y + 40),
            str(i + 1),
            font=font(30),
            fill=(255, 255, 255),
            anchor="mm"
        )

        arrow(
            draw,
            (280, y + 40),
            (700, y + 40),
            width=4
        )

    # AI model
    draw.rounded_rectangle(
        (760, 350, 1160, 730),
        radius=25,
        outline=(150, 190, 240),
        width=6
    )

    draw.text(
        (960, 540),
        "AI\nMODEL",
        font=font(55),
        fill=(255, 255, 255),
        anchor="mm",
        align="center"
    )

    # GPU cluster
    for i in range(3):

        y = 350 + i * 145

        draw.rounded_rectangle(
            (1300, y, 1690, y + 100),
            radius=15,
            outline=(100, 190, 160),
            width=5
        )

        draw.text(
            (1495, y + 50),
            f"GPU {i + 1}",
            font=font(32),
            fill=(255, 255, 255),
            anchor="mm"
        )

        arrow(
            draw,
            (1170, y + 50),
            (1270, y + 50),
            width=4
        )

    save(image, 7)


# ============================================================
# Scene 8
# ============================================================

def scene_08():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "THE REAL COST",
        "AI infrastructure requires more than GPUs"
    )

    items = [
        ("HARDWARE", 250),
        ("ELECTRICITY", 600),
        ("COOLING", 950),
        ("NETWORKING", 1300)
    ]

    for label, x in items:

        draw.rounded_rectangle(
            (x, 390, x + 280, 690),
            radius=20,
            outline=(110, 160, 210),
            width=5
        )

        draw.text(
            (x + 140, 500),
            label,
            font=font(32),
            fill=(255, 255, 255),
            anchor="mm"
        )

        draw.rectangle(
            (x + 70, 570,
             x + 210, 620),
            outline=(100, 140, 180),
            width=3
        )

    center_text(
        draw,
        "PERFORMANCE  +  COST  +  CAPACITY",
        820,
        42
    )

    save(image, 8)


# ============================================================
# Scene 9
# ============================================================

def scene_09():

    image = background()
    draw = ImageDraw.Draw(image)

    title(
        draw,
        "THE AI COMPUTING RACE",
        "The infrastructure behind the AI economy"
    )

    # Central AI
    draw.ellipse(
        (760, 360, 1160, 760),
        outline=(120, 190, 240),
        width=8
    )

    draw.text(
        (960, 560),
        "AI",
        font=font(90),
        fill=(255, 255, 255),
        anchor="mm"
    )

    # Nodes
    nodes = [
        (350, 250),
        (1550, 250),
        (300, 800),
        (1600, 800)
    ]

    for i, (x, y) in enumerate(nodes):

        draw.rounded_rectangle(
            (x - 110, y - 70,
             x + 110, y + 70),
            radius=15,
            outline=(100, 170, 220),
            width=5
        )

        draw.text(
            (x, y),
            f"COMPUTE {i + 1}",
            font=font(28),
            fill=(255, 255, 255),
            anchor="mm"
        )

        arrow(
            draw,
            (x, y),
            (960, 560),
            width=4
        )

    center_text(
        draw,
        "COMPUTING POWER IS INFRASTRUCTURE",
        900,
        40
    )

    save(image, 9)


# ============================================================
# Main
# ============================================================

def main():

    print("Creating V2 visuals...")

    scene_01()
    scene_02()
    scene_03()
    scene_04()
    scene_05()
    scene_06()
    scene_07()
    scene_08()
    scene_09()

    print()
    print("V2 visual generation complete.")


if __name__ == "__main__":
    main()