"""Narration takes with word timings, from the ElevenLabs REST API (no SDK); reads ELEVENLABS_API_KEY.

    python video/explainer/voice.py S01 S02 ...   write audio/S01.mp3 and audio/S01.json from narration.txt
    python video/explainer/voice.py all           every take

The JSON holds the take's words with start and end times, so the animation can land on a spoken word.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
VOICE = "cjVigY5qzO86Huf0OWal"  # Eric, the voice of the first cut
MODEL = "eleven_multilingual_v2"


def narration() -> dict[str, str]:
    lines = (HERE / "narration.txt").read_text(encoding="utf-8").splitlines()
    return {k.strip(): v.strip() for k, v in (line.split(":", 1) for line in lines if ":" in line)}


def words(alignment: dict) -> list[dict]:
    out, cur = [], None
    for ch, t0, t1 in zip(alignment["characters"], alignment["character_start_times_seconds"],
                          alignment["character_end_times_seconds"]):
        if ch.isspace():
            cur = None
            continue
        if cur is None:
            cur = {"w": "", "t0": round(t0, 3), "t1": round(t1, 3)}
            out.append(cur)
        cur["w"] += ch
        cur["t1"] = round(t1, 3)
    return out


def speak(take: str, text: str) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15,
                                          "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_128",
        data=body, method="POST", headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    out = HERE / "audio"
    out.mkdir(exist_ok=True)
    (out / f"{take}.mp3").write_bytes(base64.b64decode(data["audio_base64"]))
    ws = words(data["alignment"])
    (out / f"{take}.json").write_text(json.dumps({"text": text, "words": ws}, indent=1), encoding="utf-8")
    print(f"{take}: {len(ws)} words, speech ends at {ws[-1]['t1']:.2f} s")


def main() -> None:
    texts = narration()
    takes = list(texts) if sys.argv[1:] == ["all"] else sys.argv[1:]
    for take in takes:
        speak(take, texts[take])


if __name__ == "__main__":
    main()
