from pathlib import Path
import subprocess


BASE_DIR = Path(r"C:\YT-Automation")
OUTPUT_DIR = BASE_DIR / "output"

FFMPEG = next(
    (
        p
        for p in (
            Path.home()
            / "AppData"
            / "Local"
            / "Microsoft"
            / "WinGet"
            / "Packages"
        ).rglob("ffmpeg.exe")
        if "Gyan.FFmpeg.Shared" in str(p)
    ),
    None,
)

VOICE = OUTPUT_DIR / "test_voice.wav"
VIDEO = OUTPUT_DIR / "first_faceless_test.mp4"


def run_ffmpeg(args):
    command = [str(FFMPEG), "-y"] + args

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("FFmpeg failed.")

    return result


def main():

    if not FFMPEG:
        raise FileNotFoundError("FFmpeg was not found.")

    if not VOICE.exists():
        raise FileNotFoundError(f"Voice file not found: {VOICE}")

    print("Creating faceless video...")

    # Generate a simple animated background with narration.
    run_ffmpeg([
        "-f", "lavfi",
        "-i",
        "color=c=0x111827:s=1920x1080:r=30",

        "-i",
        str(VOICE),

        "-vf",
        (
            "drawtext="
            "fontfile='C\\:/Windows/Fonts/arial.ttf':"
            "text='WHY AI NEEDS SO MANY GPUs':"
            "fontcolor=white:"
            "fontsize=64:"
            "x=(w-text_w)/2:"
            "y=(h-text_h)/2"
        ),

        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",

        "-c:a", "aac",
        "-b:a", "128k",

        "-shortest",

        str(VIDEO),
    ])

    print()
    print("Video created successfully:")
    print(VIDEO)


if __name__ == "__main__":
    main()