from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from html import unescape
import json
import re

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(r"C:\YT-Automation")

SCENE_FILE = BASE_DIR / "content" / "gpu_story_scenes.json"

ASSET_DIR = BASE_DIR / "assets" / "final"
MANIFEST_FILE = BASE_DIR / "assets" / "asset_manifest.json"

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"

WIDTH = 1920
HEIGHT = 1080

ALLOWED_LICENSES = {
    "CC0 1.0",
    "CC BY 2.0",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 2.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
    "Public domain",
    "Public Domain",
}


# ============================================================
# Utilities
# ============================================================

def clean_html(value: str) -> str:
    value = unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    return value.strip()


def get_font(size: int):
    font_path = Path(r"C:\Windows\Fonts\arial.ttf")

    if not font_path.exists():
        raise FileNotFoundError(
            f"Arial font not found: {font_path}"
        )

    return ImageFont.truetype(str(font_path), size)


def api_request(params: dict) -> dict:
    query = urlencode(params)

    request = Request(
        f"{WIKIMEDIA_API}?{query}",
        headers={
            "User-Agent": "YT-Automation-MVP/1.0"
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


# ============================================================
# Wikimedia
# ============================================================

def search_wikimedia(search_term: str, limit: int = 10):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": search_term,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1920",
    }

    data = api_request(params)

    return list(
        data.get("query", {})
        .get("pages", {})
        .values()
    )


def extract_metadata(page: dict) -> dict:
    info = page.get("imageinfo", [{}])[0]

    metadata = info.get(
        "extmetadata",
        {}
    )

    def get_value(name):
        item = metadata.get(name, {})
        return clean_html(
            item.get("value", "")
        )

    return {
        "title": page.get("title", ""),
        "description_url": info.get(
            "descriptionurl", ""
        ),
        "file_url": info.get(
            "url", ""
        ),
        "thumb_url": info.get(
            "thumburl", ""
        ),
        "mime": info.get(
            "mime", ""
        ),
        "width": info.get(
            "width", 0
        ),
        "height": info.get(
            "height", 0
        ),
        "author": get_value("Artist"),
        "license": get_value(
            "LicenseShortName"
        ),
        "license_url": get_value(
            "LicenseUrl"
        ),
        "credit": get_value("Credit"),
    }


def score_candidate(metadata: dict) -> int:
    license_name = metadata["license"]

    if license_name not in ALLOWED_LICENSES:
        return -1000

    score = 100

    width = metadata["width"]
    height = metadata["height"]

    if width >= 1920:
        score += 30
    elif width >= 1280:
        score += 20
    elif width >= 800:
        score += 10
    else:
        score -= 30

    if height >= 1080:
        score += 20
    elif height >= 720:
        score += 10

    if metadata["mime"].startswith("image/"):
        score += 10

    return score


def download_file(url: str, output: Path):
    request = Request(
        url,
        headers={
            "User-Agent": "YT-Automation-MVP/1.0"
        },
    )

    with urlopen(request, timeout=60) as response:
        output.write_bytes(response.read())


# ============================================================
# Original graphics
# ============================================================

def create_graphic(
    scene_id: int,
    title: str,
    description: str,
    output: Path,
):
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (18, 24, 38),
    )

    draw = ImageDraw.Draw(image)

    title_font = get_font(70)
    description_font = get_font(32)
    small_font = get_font(28)

    draw.text(
        (70, 60),
        f"AI COMPUTING  |  SCENE {scene_id:02d}",
        font=small_font,
        fill=(180, 190, 205),
    )

    title_bbox = draw.textbbox(
        (0, 0),
        title,
        font=title_font,
    )

    title_width = (
        title_bbox[2] - title_bbox[0]
    )

    draw.text(
        (
            (WIDTH - title_width) // 2,
            280,
        ),
        title,
        font=title_font,
        fill=(255, 255, 255),
    )

    # Wrap the description.
    words = description.split()
    lines = []
    current = ""

    for word in words:
        test = (
            f"{current} {word}"
            .strip()
        )

        bbox = draw.textbbox(
            (0, 0),
            test,
            font=description_font,
        )

        if bbox[2] - bbox[0] <= 1300:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    y = 420

    for line in lines[:4]:
        bbox = draw.textbbox(
            (0, 0),
            line,
            font=description_font,
        )

        line_width = (
            bbox[2] - bbox[0]
        )

        draw.text(
            (
                (WIDTH - line_width) // 2,
                y,
            ),
            line,
            font=description_font,
            fill=(185, 195, 210),
        )

        y += 50

    # Computing grid.
    box_size = 75
    gap = 18

    total_width = (
        8 * box_size
        + 7 * gap
    )

    start_x = (
        WIDTH - total_width
    ) // 2

    start_y = 680

    for row in range(2):
        for col in range(8):

            x = (
                start_x
                + col * (box_size + gap)
            )

            y = (
                start_y
                + row * (box_size + gap)
            )

            draw.rectangle(
                (
                    x,
                    y,
                    x + box_size,
                    y + box_size,
                ),
                outline=(120, 145, 175),
                width=3,
            )

    image.save(
        output,
        format="PNG",
        optimize=True,
    )


# ============================================================
# Image acquisition
# ============================================================

def acquire_image_scene(
    scene: dict,
    output: Path,
):
    search_term = scene["visual"]

    print()
    print(
        f"Scene {scene['id']}: "
        f"Searching Wikimedia"
    )
    print(
        f"Query: {search_term}"
    )

    pages = search_wikimedia(
        search_term,
        limit=10,
    )

    candidates = []

    for page in pages:
        metadata = extract_metadata(page)

        score = score_candidate(
            metadata
        )

        if score > 0:
            candidates.append(
                (
                    score,
                    metadata
                )
            )

    if not candidates:
        raise RuntimeError(
            "No acceptable licensed image found."
        )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    score, selected = candidates[0]

    print(
        f"Selected: {selected['title']}"
    )
    print(
        f"License: {selected['license']}"
    )
    print(
        f"Resolution: "
        f"{selected['width']}x"
        f"{selected['height']}"
    )

    download_url = (
        selected["thumb_url"]
        or selected["file_url"]
    )

    if not download_url:
        raise RuntimeError(
            "Selected image has no download URL."
        )

    download_file(
        download_url,
        output,
    )

    # Verify downloaded file.
    try:
        with Image.open(output) as image:
            image.verify()
    except Exception as exc:
        output.unlink(
            missing_ok=True
        )
        raise RuntimeError(
            f"Downloaded image is invalid: {exc}"
        )

    return {
        "scene_id": scene["id"],
        "local_file": str(output),
        "source": "Wikimedia Commons",
        "source_url": selected[
            "description_url"
        ],
        "title": selected["title"],
        "author": selected["author"],
        "license": selected["license"],
        "license_url": selected[
            "license_url"
        ],
        "credit": selected["credit"],
        "selection_score": score,
    }


# ============================================================
# Main
# ============================================================

def main():

    ASSET_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not SCENE_FILE.exists():
        raise FileNotFoundError(
            f"Scene file not found: {SCENE_FILE}"
        )

    scene_data = json.loads(
        SCENE_FILE.read_text(
            encoding="utf-8"
        )
    )

    scenes = scene_data["scenes"]

    manifest = []

    print(
        f"Processing {len(scenes)} scenes..."
    )

    for scene in scenes:

        scene_id = scene["id"]

        # --------------------------------------------
        # Graphic scene
        # --------------------------------------------

        if scene["asset_type"] == "graphic":

            output = (
                ASSET_DIR
                / f"scene_{scene_id:02d}.png"
            )

            print()
            print(
                f"Scene {scene_id}: "
                f"Generating original graphic"
            )

            create_graphic(
                scene_id,
                scene["narration_topic"],
                scene["visual"],
                output,
            )

            manifest.append(
                {
                    "scene_id": scene_id,
                    "local_file": str(output),
                    "source": "Original graphic",
                    "source_url": None,
                    "title": None,
                    "author": "YT-Automation",
                    "license": "Original",
                    "license_url": None,
                    "credit": None,
                    "selection_score": None,
                }
            )

            continue

        # --------------------------------------------
        # Licensed image
        # --------------------------------------------

        output = (
            ASSET_DIR
            / f"scene_{scene_id:02d}.jpg"
        )

        try:

            result = acquire_image_scene(
                scene,
                output,
            )

            manifest.append(result)

        except Exception as exc:

            print()
            print(
                f"WARNING: Scene {scene_id} "
                f"image acquisition failed."
            )
            print(
                f"Reason: {exc}"
            )

            # Safe fallback:
            # create an original graphic.
            graphic_output = (
                ASSET_DIR
                / f"scene_{scene_id:02d}.png"
            )

            print(
                f"Scene {scene_id}: "
                f"Using original graphic fallback."
            )

            create_graphic(
                scene_id,
                scene["narration_topic"],
                scene["visual"],
                graphic_output,
            )

            manifest.append(
                {
                    "scene_id": scene_id,
                    "local_file": str(
                        graphic_output
                    ),
                    "source": "Original graphic",
                    "source_url": None,
                    "title": None,
                    "author": "YT-Automation",
                    "license": "Original",
                    "license_url": None,
                    "credit": None,
                    "selection_score": None,
                    "fallback_reason": str(exc),
                }
            )

    # --------------------------------------------
    # Save manifest
    # --------------------------------------------

    MANIFEST_FILE.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("ASSET BUILD COMPLETE")
    print("=" * 60)

    print(
        f"Assets: {len(manifest)}"
    )

    print(
        f"Location: {ASSET_DIR}"
    )

    print(
        f"Manifest: {MANIFEST_FILE}"
    )


if __name__ == "__main__":
    main()