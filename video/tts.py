"""Narration takes from ElevenLabs, through its REST API (no SDK), reading ELEVENLABS_API_KEY from the environment.

    python video/tts.py --voice <voice_id> V1 V2 ...    write video/input/V1.mp3 ... from video/narration.txt
    python video/tts.py --voice <voice_id> --sample V1  write video/samples/V1-<voice_id>.mp3 instead
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
MODEL = "eleven_multilingual_v2"


def narration() -> dict[str, str]:
    lines = (HERE / "narration.txt").read_text(encoding="utf-8").splitlines()
    return {k.strip(): v.strip() for k, v in (line.split(":", 1) for line in lines if ":" in line)}


def speak(text: str, voice: str, out: Path) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15,
                                          "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                                 data=body, method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.read())
    print(f"{out.relative_to(HERE.parent)}: {out.stat().st_size // 1024} KB, {len(text)} characters")


def main() -> None:
    args = sys.argv[1:]
    voice = args[args.index("--voice") + 1]
    takes = [a for a in args if a.upper().startswith("V") and a[1:].isdigit()]
    texts = narration()
    for take in takes:
        out = (HERE / "samples" / f"{take}-{voice}.mp3") if "--sample" in args else (HERE / "input" / f"{take}.mp3")
        speak(texts[take], voice, out)


if __name__ == "__main__":
    main()
