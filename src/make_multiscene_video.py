from pathlib import Path
import subprocess
import shutil


BASE_DIR = Path(r"C:\YT-Automation")
SCENE_DIR = BASE_DIR / "assets" / "scenes"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp" / "scene_clips"

VOICE = OUTPUT_DIR / "test_voice.wav"
OUTPUT = OUTPUT_DIR / "multiscene_test_v2.mp4"


def find_ffmpeg() -> Path:
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
        raise FileNotFoundError("FFmpeg executable not found.")

    return matches[0]


def run(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("FFmpeg command failed.")

    return result


def create_scene_clip(ffmpeg: Path, image: Path, output: Path):
    command = [
        str(ffmpeg),
        "-y",

        "-loop",
        "1",
        "-i",
        str(image),

        "-t",
        "3",

        "-vf",
        (
            "scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,"
            "zoompan="
            "z='min(zoom+0.0008,1.08)':"
            "d=1:"
            "s=1920x1080:"
            "fps=30"
        ),

        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",

        str(output),
    ]

    run(command)


def concatenate_clips(ffmpeg: Path, clips, output: Path):
    concat_file = TEMP_DIR / "concat.txt"

    with concat_file.open("w", encoding="utf-8") as file:
        for clip in clips:
            # FFmpeg concat demuxer requires escaped paths.
            path = str(clip.resolve()).replace("\\", "/")
            file.write(f"file '{path}'\n")

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

        str(output),
    ]

    run(command)


def add_narration(ffmpeg: Path, video: Path, output: Path):
    command = [
        str(ffmpeg),
        "-y",

        "-i",
        str(video),

        "-i",
        str(VOICE),

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

        str(output),
    ]

    run(command)


def main():

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not VOICE.exists():
        raise FileNotFoundError(
            f"Voice file not found: {VOICE}"
        )

    scenes = sorted(
        SCENE_DIR.glob("scene_*.png")
    )

    if len(scenes) != 6:
        raise RuntimeError(
            f"Expected 6 scene images, found {len(scenes)}."
        )

    ffmpeg = find_ffmpeg()

    print(f"FFmpeg: {ffmpeg}")
    print(f"Found {len(scenes)} scenes.")

    # Clean previous temporary clips.
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)

    TEMP_DIR.mkdir(parents=True)

    clips = []

    # Step 1: Convert every PNG into a separate 3-second video.
    for index, scene in enumerate(scenes, start=1):

        clip = TEMP_DIR / f"clip_{index:02d}.mp4"

        print(
            f"[{index}/{len(scenes)}] "
            f"Creating {scene.name}"
        )

        create_scene_clip(
            ffmpeg,
            scene,
            clip,
        )

        clips.append(clip)

    # Step 2: Concatenate the six video clips.
    silent_video = TEMP_DIR / "silent_video.mp4"

    print("Concatenating scenes...")

    concatenate_clips(
        ffmpeg,
        clips,
        silent_video,
    )

    # Step 3: Add narration.
    print("Adding narration...")

    add_narration(
        ffmpeg,
        silent_video,
        OUTPUT,
    )

    print()
    print("SUCCESS")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()