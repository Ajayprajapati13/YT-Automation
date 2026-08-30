"""Chunked render/resume driver for Task 0003 (the 700-agent Hugging Face
incident documentary).

Recovery context: the first production attempt (headless worker session)
got through narration synthesis and started an ad hoc 6-chunk full render
(temp/hf_incident/chunk_plan.json) before running out of execution budget
mid-encode on chunk 1 - the interrupted ffmpeg process left an unfinished
MP4 (no moov atom). That chunking approach was never saved as a script, so
there was nothing to resume from directly; this is that driver, written
properly and made idempotent.

Renders one chunk at a time via bounded, separate ffmpeg processes (never
one ffmpeg call spanning the whole ~10-minute video), so an interruption
loses at most one chunk's progress. Skips any chunk file that already
validates (right duration, readable video stream) and only re-renders
invalid/missing ones - safe to re-run after a partial failure.

Reuses create_hf_incident_documentary's existing build_timeline/
build_scenes/make_draw_frame/mux_video_audio/build_narration_track - this
is not a second rendering pipeline, just a chunked driver around the same
one. Never re-synthesizes narration if the existing per-scene .wav files
are present and valid.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import motion_graphics as mg
import create_hf_incident_documentary as doc

CHUNK_PLAN_PATH = doc.TEMP_DIR / "chunk_plan.json"
CONCAT_LIST_PATH = doc.TEMP_DIR / "concat_list.txt"


def chunk_path(i: int) -> Path:
    return doc.TEMP_DIR / f"chunk_{i}.mp4"


def probe_ok(ffprobe: Path, path: Path) -> tuple[bool, float | None]:
    """Validate an existing chunk/output file: readable duration and an
    actual video stream (catches the moov-atom-missing failure mode, and
    any other truncated/corrupt file, without reading frame content)."""
    if not path.exists() or path.stat().st_size == 0:
        return False, None
    dur = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if dur.returncode != 0 or not dur.stdout.strip():
        return False, None
    vstream = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if vstream.returncode != 0 or "video" not in vstream.stdout:
        return False, None
    try:
        return True, float(dur.stdout.strip())
    except ValueError:
        return False, None


def make_chunk_draw_frame(full_draw_frame, chunk_start_t: float):
    def draw_frame(local_t, frame_index, total_frames):
        return full_draw_frame(chunk_start_t + local_t, frame_index, total_frames)
    return draw_frame


def main() -> dict:
    plan = json.loads(CHUNK_PLAN_PATH.read_text(encoding="utf-8"))
    total_duration = plan["total"]
    num_chunks = plan["chunks"]

    ffmpeg = mg.find_ffmpeg()
    ffprobe = ffmpeg.parent / "ffprobe.exe"

    script_data = json.loads(doc.CONTENT_FILE.read_text(encoding="utf-8"))
    scenes_data = script_data["scenes"]
    voice_paths = [doc.VOICE_DIR / f"{sc['id']}.wav" for sc in scenes_data]
    missing = [str(p) for p in voice_paths if not p.exists()]
    if missing:
        raise RuntimeError(f"missing narration file(s), refusing to auto-regenerate: {missing}")

    durations = [doc.probe_duration(ffprobe, p) for p in voice_paths]
    beats, segments = doc.build_timeline(durations)
    doc.BEATS = beats
    computed_total = beats[-1]
    if abs(computed_total - total_duration) > 0.5:
        raise RuntimeError(
            f"recomputed total duration {computed_total:.2f}s does not match "
            f"chunk_plan.json's {total_duration:.2f}s - narration/scenes changed since planning"
        )

    scenes = doc.build_scenes(script_data)
    full_draw_frame = doc.make_draw_frame(doc.build_background(), scenes)

    chunk_bounds = [
        (i * total_duration / num_chunks, (i + 1) * total_duration / num_chunks)
        for i in range(num_chunks)
    ]

    for i, (start, end) in enumerate(chunk_bounds):
        path = chunk_path(i)
        expected_dur = end - start
        ok, dur = probe_ok(ffprobe, path)
        if ok and abs(dur - expected_dur) < 1.0:
            print(f"chunk {i}: reusing valid existing file ({dur:.2f}s)")
            continue
        if path.exists():
            print(f"chunk {i}: existing file invalid/incomplete ({'ok' if ok else 'unreadable'}), re-rendering")
            path.unlink()
        print(f"chunk {i}: rendering [{start:.2f}s, {end:.2f}s) ...")
        chunk_frame = make_chunk_draw_frame(full_draw_frame, start)
        mg.render_video(chunk_frame, expected_dur, path, ffmpeg=ffmpeg, crf=18, preset="medium")
        ok, dur = probe_ok(ffprobe, path)
        if not ok:
            raise RuntimeError(f"chunk {i} failed validation immediately after rendering")
        print(f"chunk {i}: done ({dur:.2f}s)")

    print("Concatenating chunks...")
    lines = [f"file '{chunk_path(i).resolve().as_posix()}'" for i in range(num_chunks)]
    CONCAT_LIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    concat_cmd = [
        str(ffmpeg), "-y", "-f", "concat", "-safe", "0",
        "-i", str(CONCAT_LIST_PATH), "-c", "copy", str(doc.SILENT_VIDEO),
    ]
    result = subprocess.run(concat_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"concat failed:\n{result.stderr}")

    ok, silent_dur = probe_ok(ffprobe, doc.SILENT_VIDEO)
    if not ok:
        raise RuntimeError("concatenated silent video failed validation")
    print(f"Concatenated silent video: {silent_dur:.2f}s")

    print("Building combined narration track...")
    rate, channels = doc.probe_audio_format(ffprobe, voice_paths[0])
    doc.build_narration_track(ffmpeg, segments, voice_paths, rate, channels, doc.NARRATION_FILE)
    narration_total = doc.probe_duration(ffprobe, doc.NARRATION_FILE)
    print(f"Narration track duration: {narration_total:.2f}s")

    print("Muxing narration onto video...")
    doc.mux_video_audio(ffmpeg, doc.SILENT_VIDEO, doc.NARRATION_FILE, doc.OUTPUT_FILE, total_duration)

    print()
    print("Done.")
    print(f"Output: {doc.OUTPUT_FILE}")

    return {
        "video_duration": total_duration,
        "narration_duration": narration_total,
        "silent_duration": silent_dur,
    }


if __name__ == "__main__":
    main()
