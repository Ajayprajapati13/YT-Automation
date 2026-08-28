from pathlib import Path
import json


BASE_DIR = Path(r"C:\YT-Automation")

SCENE_FILE = (
    BASE_DIR
    / "content"
    / "gpu_story_scenes.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "content"
    / "gpu_story_assets.json"
)


def main():

    if not SCENE_FILE.exists():
        raise FileNotFoundError(
            f"Scene file not found: {SCENE_FILE}"
        )

    data = json.loads(
        SCENE_FILE.read_text(
            encoding="utf-8"
        )
    )

    assets = []

    for scene in data["scenes"]:

        asset = {
            "scene_id": scene["id"],
            "start": scene["start"],
            "end": scene["end"],
            "duration": (
                scene["end"] - scene["start"]
            ),
            "asset_type": scene["asset_type"],
            "visual_prompt": scene["visual"],
            "narration_topic": scene["narration_topic"],
            "status": "pending",
            "source": None,
            "source_url": None,
            "author": None,
            "license": None,
            "local_file": None
        }

        assets.append(asset)

    output = {
        "video_title": data["video"]["title"],
        "assets": assets
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        f"Created asset plan: {OUTPUT_FILE}"
    )

    print(
        f"Assets required: {len(assets)}"
    )


if __name__ == "__main__":
    main()