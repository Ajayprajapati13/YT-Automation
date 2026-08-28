from pathlib import Path
import subprocess


BASE_DIR = Path(r"C:\YT-Automation")
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "test_video.mp4"


def find_ffmpeg() -> Path:
    """Locate the FFmpeg executable installed by WinGet."""

    winget_packages = (
        Path.home()
        / "AppData"
        / "Local"
        / "Microsoft"
        / "WinGet"
        / "Packages"
    )

    if not winget_packages.exists():
        raise FileNotFoundError(
            f"WinGet package directory not found: {winget_packages}"
        )

    matches = list(
        winget_packages.rglob("ffmpeg.exe")
    )

    # Prefer the Gyan FFmpeg installation.
    matches = [
        path for path in matches
        if "Gyan.FFmpeg.Shared" in str(path)
    ]

    if not matches:
        raise FileNotFoundError(
            "FFmpeg executable was not found in the WinGet package directory."
        )

    return matches[0]


def create_test_video(ffmpeg: Path) -> None:

    command = [
        str(ffmpeg),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1280x720:r=30",
        "-t",
        "10",
        "-vf",
"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
"text='YT Automation Test':"
"fontcolor=white:"
"fontsize=64:"
"x=(w-text_w)/2:"
"y=(h-text_h)/2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(OUTPUT_FILE),
    ]

    print(f"Using FFmpeg: {ffmpeg}")
    print("Generating video...")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("FFmpeg failed.")
        print(result.stderr)
        raise RuntimeError("Video generation failed.")

    print(f"Video created successfully:")
    print(OUTPUT_FILE)


def main() -> None:
    ffmpeg = find_ffmpeg()

    print(f"FFmpeg found: {ffmpeg}")

    create_test_video(ffmpeg)


if __name__ == "__main__":
    main()