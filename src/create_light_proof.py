"""Milestone 3 proof: white-background motion-graphics scene with
synchronized narration.

Reuses the milestone-1/2 engine and timeline unchanged (see
create_poc_scene.py's THEME system) — only the palette, duration, and
an added narration track are new. Output:
    C:\\YT-Automation\\output\\gpu_light_proof.mp4
"""

from pathlib import Path
import subprocess
import re

import sys
sys.path.insert(0, str(Path(__file__).parent))

import motion_graphics as mg
import create_poc_scene as scene

BASE_DIR = Path(r"C:\YT-Automation")
SCRIPT_FILE = BASE_DIR / "content" / "gpu_light_proof_script.txt"
TEMP_DIR = BASE_DIR / "temp" / "light_proof"
VOICE_FILE = BASE_DIR / "output" / "gpu_light_proof_voice.wav"
SILENT_VIDEO = TEMP_DIR / "silent.mp4"
OUTPUT_FILE = BASE_DIR / "output" / "gpu_light_proof.mp4"

MIN_DURATION = 30.0
MAX_DURATION = 45.0
OUTRO_HOLD = 2.5


def ffprobe_path(ffmpeg_path):
    return ffmpeg_path.parent / "ffprobe.exe"


def probe_duration(ffprobe, media_path):
    result = subprocess.run(
        [
            str(ffprobe), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {media_path}:\n{result.stderr}")
    return float(result.stdout.strip())


def mux_video_audio(ffmpeg, silent_video, voice_wav, output_path, duration):
    command = [
        str(ffmpeg), "-y",
        "-i", str(silent_video),
        "-i", str(voice_wav),
        "-filter_complex", "[1:a]apad[a]",
        "-map", "0:v:0",
        "-map", "[a]",
        "-t", str(duration),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg mux failed:\n{result.stderr}")


def volume_check(ffmpeg, media_path):
    """Loudness/peak sanity check via ffmpeg's volumedetect filter."""
    result = subprocess.run(
        [
            str(ffmpeg), "-i", str(media_path),
            "-af", "volumedetect", "-vn", "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    stderr = result.stderr
    mean_match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", stderr)
    max_match = re.search(r"max_volume:\s*(-?[\d.]+) dB", stderr)
    return {
        "mean_volume_db": float(mean_match.group(1)) if mean_match else None,
        "max_volume_db": float(max_match.group(1)) if max_match else None,
    }


def main():
    ffmpeg = mg.find_ffmpeg()
    ffprobe = ffprobe_path(ffmpeg)

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "output").mkdir(parents=True, exist_ok=True)

    script_text = SCRIPT_FILE.read_text(encoding="utf-8").strip()
    print(f"Narration script: {len(script_text.split())} words")

    print("Synthesizing narration (Windows SAPI, existing voice pipeline)...")
    mg.synthesize_narration(script_text, VOICE_FILE)
    audio_duration = probe_duration(ffprobe, VOICE_FILE)
    print(f"Narration duration: {audio_duration:.2f}s")

    video_duration = max(MIN_DURATION, min(MAX_DURATION, round(audio_duration + OUTRO_HOLD, 1)))
    print(f"Video duration: {video_duration}s")

    print("Rendering silent white-background scene...")
    scene.render(scene.LIGHT_THEME, video_duration, SILENT_VIDEO, ffmpeg=ffmpeg, crf=16, preset="medium")

    print("Muxing narration onto video...")
    mux_video_audio(ffmpeg, SILENT_VIDEO, VOICE_FILE, OUTPUT_FILE, video_duration)

    print()
    print("Done.")
    print(f"Output: {OUTPUT_FILE}")

    return {
        "video_duration": video_duration,
        "audio_duration": audio_duration,
    }


if __name__ == "__main__":
    main()
