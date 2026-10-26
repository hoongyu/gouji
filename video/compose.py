"""Assemble the demo video from the narration takes, the screen recordings and the title cards.

    python video/compose.py            needs video/input/V1..V8.<audio> and video/input/shot2..shot6.<video>
    python video/compose.py --check    also writes contact sheets of the final video to video/out/check/

Each segment lasts as long as its narration (plus a short breath). A recording longer than its narration is
sped up (at most 3x); a shorter one holds its last frame. Subtitles come from video/narration.txt, split by
sentence and timed by length; they are burned in and also written as video/out/payproof-demo.srt.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
IN, OUT, CARDS = HERE / "input", HERE / "out", HERE / "cards"
W, H, FPS = 1920, 1080, 30
LEAD, TAIL = 0.3, 0.5                     # silence before and after each take, seconds
MAX_SPEEDUP = 3.0
SEGMENTS = [("V1", ["card1a", "card1b", "card1c"]), ("V2", "shot2"), ("V3", "shot3"), ("V4", "shot4"),
            ("V5", "shot5"), ("V6", "shot6"), ("V7", ["card7"]), ("V8", ["card8"])]
AUDIO_EXT = (".wav", ".m4a", ".mp3", ".aac", ".ogg", ".opus", ".webm", ".flac", ".mp4")
VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm", ".avi")


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True, cwd=cwd)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def find(stem: str, exts: tuple[str, ...]) -> Path:
    for ext in exts:
        for p in (IN / f"{stem}{ext}", IN / f"{stem}{ext.upper()}"):
            if p.exists():
                return p
    sys.exit(f"missing video/input/{stem} with one of {', '.join(exts)}")


def narration() -> dict[str, str]:
    lines = (HERE / "narration.txt").read_text(encoding="utf-8").splitlines()
    return {k.strip(): v.strip() for k, v in (line.split(":", 1) for line in lines if ":" in line)}


def audio_filter(seg_dur: float) -> str:
    return (f"highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11,adelay={int(LEAD * 1000)}:all=1,"
            f"apad=whole_dur={seg_dur:.3f},atrim=0:{seg_dur:.3f},aformat=sample_rates=48000:channel_layouts=stereo")


SCALE = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=#161B26,"
         f"setsar=1,fps={FPS},format=yuv420p")


def segment(i: int, take: str, visual, text: str) -> tuple[Path, float, float]:
    """Render one segment; returns (file, its length, the narration's length)."""
    audio = find(take, AUDIO_EXT)
    speech = duration(audio)
    seg_dur = LEAD + speech + TAIL
    out = OUT / f"seg{i}.mp4"
    common = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
              "-t", f"{seg_dur:.3f}", str(out)]
    if isinstance(visual, list):  # title cards, shown in turn, evenly over the take
        each = seg_dur / len(visual)
        inputs, chains = [], []
        for n, card in enumerate(visual):
            inputs += ["-loop", "1", "-t", f"{each:.3f}", "-i", str(CARDS / f"{card}.png")]
            chains.append(f"[{n}:v]{SCALE}[c{n}]")
        concat = "".join(f"[c{n}]" for n in range(len(visual))) + f"concat=n={len(visual)}:v=1:a=0[v]"
        a = len(visual)
        run(*inputs, "-i", str(audio), "-filter_complex",
            ";".join(chains) + f";{concat};[{a}:a]{audio_filter(seg_dur)}[a]", "-map", "[v]", "-map", "[a]", *common)
    else:
        rec = find(visual, VIDEO_EXT)
        speed = min(max(duration(rec) / seg_dur, 1.0), MAX_SPEEDUP)
        run("-i", str(rec), "-i", str(audio), "-filter_complex",
            f"[0:v]setpts=PTS/{speed:.4f},{SCALE},tpad=stop_mode=clone:stop_duration={seg_dur:.3f}[v];"
            f"[1:a]{audio_filter(seg_dur)}[a]", "-map", "[v]", "-map", "[a]", *common)
        if speed > 1.0:
            print(f"  {visual}: recording sped up {speed:.2f}x to fit {take}")
    return out, seg_dur, speech


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def subtitles(timeline: list[tuple[float, float, str]]) -> str:
    """One cue per sentence (long ones split at a comma), timed by character count."""
    cues = []
    for start, speech, text in timeline:
        parts = []
        for s in re.split(r"(?<=[.!?])\s+", text):
            while len(s) > 90 and ", " in s[30:]:
                cut = s.index(", ", 30) + 1
                parts.append(s[:cut].strip())
                s = s[cut:].strip()
            parts.append(s)
        total = sum(len(p) for p in parts)
        t = start + LEAD
        for p in parts:
            d = speech * len(p) / total
            cues.append((t, t + d, p))
            t += d
    return "\n".join(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n" for n, (a, b, txt) in enumerate(cues, 1))


def contact_sheets(video: Path) -> None:
    check = OUT / "check"
    check.mkdir(exist_ok=True)
    for old in check.glob("*.png"):
        old.unlink()
    run("-i", str(video), "-vf", "fps=1/2,scale=960:540,tile=2x2", str(check / "sheet_%03d.png"))
    print(f"contact sheets (one frame every 2 s, 4 per sheet): {len(list(check.glob('*.png')))} in {check}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    texts = narration()
    files, timeline, t = [], [], 0.0
    for i, (take, visual) in enumerate(SEGMENTS, 1):
        f, seg_dur, speech = segment(i, take, visual, texts[take])
        files.append(f)
        timeline.append((t, speech, texts[take]))
        print(f"  segment {i} ({take}): {seg_dur:.1f} s")
        t += seg_dur
    (OUT / "list.txt").write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
    run("-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4", cwd=OUT)
    (OUT / "payproof-demo.srt").write_text(subtitles(timeline), encoding="utf-8")
    style = ("FontName=Segoe UI,FontSize=20,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,"
             "Outline=0,Shadow=0,MarginV=36")
    run("-i", "joined.mp4", "-vf", f"subtitles=payproof-demo.srt:force_style='{style}'", "-c:v", "libx264",
        "-preset", "medium", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", "payproof-demo.mp4", cwd=OUT)
    final = OUT / "payproof-demo.mp4"
    total = duration(final)
    print(f"video/out/payproof-demo.mp4: {total:.1f} s ({'OK, under 4 minutes' if total <= 240 else 'OVER 4 MINUTES'})")
    if "--check" in sys.argv:
        contact_sheets(final)


if __name__ == "__main__":
    main()
