from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(r"C:\YT-Automation")
SCENE_DIR = BASE_DIR / "assets" / "scenes"
SCENE_DIR.mkdir(parents=True, exist_ok=True)

WIDTH = 1920
HEIGHT = 1080

FONT_PATH = Path(r"C:\Windows\Fonts\arial.ttf")


SCENES = [
    "Artificial Intelligence",
    "Massive Data Centers",
    "Thousands of GPUs",
    "AI Model Training",
    "Billions in Investment",
    "The AI Computing Race",
]


def get_font(size: int):
    return ImageFont.truetype(str(FONT_PATH), size)


def create_scene(index: int, title: str):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (15, 23, 42),
    )

    draw = ImageDraw.Draw(image)

    # Large title
    title_font = get_font(82)

    bbox = draw.textbbox((0, 0), title, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (WIDTH - text_width) // 2
    y = (HEIGHT - text_height) // 2

    draw.text(
        (x, y),
        title,
        font=title_font,
        fill=(255, 255, 255),
    )

    # Scene number
    number_font = get_font(36)

    draw.text(
        (60, 60),
        f"SCENE {index:02d}",
        font=number_font,
        fill=(180, 190, 210),
    )

    output = SCENE_DIR / f"scene_{index:02d}.png"

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    print(f"Created: {output}")


def main():

    for index, title in enumerate(SCENES, start=1):
        create_scene(index, title)

    print()
    print(f"Created {len(SCENES)} scenes.")
    print(f"Location: {SCENE_DIR}")


if __name__ == "__main__":
    main()