from pathlib import Path
import re
import subprocess


BASE_DIR = Path(r"C:\YT-Automation")

SCRIPT_FILE = BASE_DIR / "content" / "gpu_story.txt"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "gpu_story_voice.wav"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_script() -> str:
    if not SCRIPT_FILE.exists():
        raise FileNotFoundError(
            f"Script not found: {SCRIPT_FILE}"
        )

    text = SCRIPT_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if not text:
        raise ValueError("Script is empty.")

    return text


def generate_voice(text: str) -> None:

    # Escape PowerShell-sensitive characters.
    escaped = text.replace("'", "''")

    powershell_script = f"""
Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$synth.SelectVoice("Microsoft David Desktop")

$synth.Rate = 0
$synth.Volume = 100

$text = @'
{escaped}
'@

$synth.SetOutputToWaveFile(
    "{OUTPUT_FILE}"
)

$synth.Speak($text)

$synth.Dispose()
"""

    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        powershell_script,
    ]

    print("Generating narration...")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(
            "Voice generation failed."
        )

    if not OUTPUT_FILE.exists():
        raise RuntimeError(
            "Voice file was not created."
        )

    if OUTPUT_FILE.stat().st_size == 0:
        raise RuntimeError(
            "Voice file is empty."
        )

    print("Narration generated:")
    print(OUTPUT_FILE)


def main():

    text = read_script()

    word_count = len(
        re.findall(r"\b[\w'-]+\b", text)
    )

    print(f"Script words: {word_count}")

    generate_voice(text)


if __name__ == "__main__":
    main()