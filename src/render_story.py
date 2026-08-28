from pathlib import Path
import json
import subprocess
import shutil


BASE_DIR = Path(r"C:\YT-Automation")

SCENE_FILE = BASE_DIR / "content" / "gpu_story_scenes.json"
VOICE_FILE = BASE_DIR / "output" / "gpu_story_voice.wav"

VISUAL_DIR = BASE_DIR / "assets" / "v2"

OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp" / "render_v2"

OUTPUT_FILE = OUTPUT_DIR / "gpu_story_final_v2.mp4"

WIDTH = 1920
HEIGHT = 1080
FPS = 30


def find_ffmpeg():

    packages = (
        Path.home()
        / "AppData"
        / "Local"
        / "Microsoft"
        / "WinGet"
        / "Packages"
    )

    matches = [
        p
        for p in packages.rglob("ffmpeg.exe")
        if "Gyan.FFmpeg.Shared" in str(p)
    ]

    if not matches:
        raise FileNotFoundError(
            "FFmpeg executable was not found."
        )

    return matches[0]


def run(command):

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(
            "FFmpeg command failed."
        )

    return result


def load_scenes():

    if not SCENE_FILE.exists():
        raise FileNotFoundError(
            f"Scene file not found: {SCENE_FILE}"
        )

    data = json.loads(
        SCENE_FILE.read_text(
            encoding="utf-8"
        )
    )

    scenes = data["scenes"]

    if len(scenes) != 9:
        raise RuntimeError(
            f"Expected 9 scenes, found {len(scenes)}."
        )

    return scenes


def create_scene_clip(
    ffmpeg,
    image,
    duration,
    output
):

    command = [
        str(ffmpeg),
        "-y",

        "-loop",
        "1",

        "-i",
        str(image),

        "-t",
        str(duration),

        "-vf",
        (
            f"scale={WIDTH}:{HEIGHT}:"
            "force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},"
            f"fps={FPS}"
        ),

        "-c:v",
        "libx264",

        "-preset",
        "ultrafast",

        "-crf",
        "26",

        "-pix_fmt",
        "yuv420p",

        "-an",

        str(output)
    ]

    run(command)


def concatenate(
    ffmpeg,
    clips,
    output
):

    concat_file = TEMP_DIR / "concat.txt"

    with concat_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        for clip in clips:

            path = (
                str(clip.resolve())
                .replace("\\", "/")
            )

            file.write(
                f"file '{path}'\n"
            )

    command = [
        str(ffmpeg),
        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(concat_file),

        "-c",
        "copy",

        str(output)
    ]

    run(command)


def add_audio(
    ffmpeg,
    silent_video,
    output
):

    command = [
        str(ffmpeg),
        "-y",

        "-i",
        str(silent_video),

        "-i",
        str(VOICE_FILE),

        "-map",
        "0:v:0",

        "-map",
        "1:a:0",

        "-c:v",
        "copy",

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-shortest",

        "-movflags",
        "+faststart",

        str(output)
    ]

    run(command)


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if not VOICE_FILE.exists():
        raise FileNotFoundError(
            f"Voice file not found: {VOICE_FILE}"
        )

    if not VISUAL_DIR.exists():
        raise FileNotFoundError(
            f"Visual directory not found: {VISUAL_DIR}"
        )

    ffmpeg = find_ffmpeg()

    scenes = load_scenes()

    print(f"FFmpeg: {ffmpeg}")
    print(f"Scenes: {len(scenes)}")

    total_duration = sum(
        scene["end"] - scene["start"]
        for scene in scenes
    )

    print(
        f"Planned duration: "
        f"{total_duration} seconds"
    )

    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    clips = []

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        scene_id = scene["id"]

        image = (
            VISUAL_DIR
            / f"scene_{scene_id:02d}.png"
        )

        if not image.exists():
            raise FileNotFoundError(
                f"Visual missing: {image}"
            )

        duration = (
            scene["end"]
            - scene["start"]
        )

        clip = (
            TEMP_DIR
            / f"scene_{scene_id:02d}.mp4"
        )

        print()
        print(
            f"[{index}/9] "
            f"Scene {scene_id}"
        )

        print(
            f"Duration: {duration}s"
        )

        create_scene_clip(
            ffmpeg,
            image,
            duration,
            clip
        )

        clips.append(clip)

    silent_video = (
        TEMP_DIR
        / "silent_video.mp4"
    )

    print()
    print("Concatenating scenes...")

    concatenate(
        ffmpeg,
        clips,
        silent_video
    )

    print("Adding narration...")

    add_audio(
        ffmpeg,
        silent_video,
        OUTPUT_FILE
    )

    print()
    print("=" * 60)
    print("V2 VIDEO COMPLETE")
    print("=" * 60)

    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()