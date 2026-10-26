"""Shots 2 to 6 of the demo video, made from the running app instead of a manual screen recording.

    python video/make_shots.py capture   headless Chrome screenshots of the live pages (server on :8000)
    python video/make_shots.py terminal  the agents' steps of the Zetaris run, rendered from its trace
    python video/make_shots.py build     video/input/shot2.mp4 ... shot6.mp4, each as long as its narration

Pages are captured 1280 CSS px wide at 1.5x, so 1920 px wide and sharp; a shot is a sequence of moves over
those images (hold, scroll), cut to 1920x1080.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SHOTS, IN = HERE / "shots", HERE / "input"
BASE = "http://localhost:8000"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
W, H, FPS = 1920, 1080, 30
PAGES = {
    "index": ("/", 1600),
    "brief5567": ("/brief/INV-5567", 7000),
    "row_inv": ("/row/invoices/INV-5567?col=issuer_reg_no", 1300),
    "row_reg": ("/row/registry/LV-SYN-90501?col=incorporated_on", 1300),
    "brief5559": ("/brief/INV-5559", 6000),
}


def capture() -> None:
    SHOTS.mkdir(exist_ok=True)
    for name, (path, height) in PAGES.items():
        out = SHOTS / f"{name}.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size=1280,{height}",
                        "--force-device-scale-factor=1.5", f"--screenshot={out}", BASE + path],
                       check=True, capture_output=True, timeout=600)
        print(f"{out.name}: {out.stat().st_size // 1024} KB")


def terminal() -> None:
    """Render the trace of the newest Zetaris run as a terminal screenshot (one long image)."""
    from PIL import Image, ImageDraw, ImageFont
    runs = sorted((HERE.parent / "output_examples" / "zetaris-run").glob("INV-5567.json"))
    trace_file = max((HERE.parent / "logs").glob("trace-2026*.jsonl"), key=lambda p: p.stat().st_mtime)
    if runs:
        rid = json.loads(runs[0].read_text(encoding="utf-8")).get("run_id")
        named = HERE.parent / "logs" / f"trace-{rid}.jsonl" if rid else None
        trace_file = named if named and named.exists() else trace_file
    events = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
    events = [e for e in events if e.get("inv_id", "INV-5567") == "INV-5567"]
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 26)
    bold = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 26)
    lines = [("$ uv run python run.py case INV-5567 --backend zetaris", "#9FE2BF")]
    for e in events:
        lines.append((f"{e['agent']:<13}{e['action']:<13}{e['summary']}", "#E6E8EC"))
    img = Image.new("RGB", (W, max(H, 140 + 40 * len(lines) * 2)), "#0F1218")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 56], fill="#1E2430")
    d.text((24, 14), "Terminal: every query goes to Zetaris (REST API, localhost:8888)", font=bold, fill="#B8BFCC")
    y = 90
    for text, colour in lines:
        while text:  # wrap at 120 characters
            d.text((40, y), text[:120], font=font, fill=colour)
            text = (" " * 26 + text[120:]) if len(text) > 120 else ""
            y += 40
    img = img.crop((0, 0, W, max(H, y + 40)))
    img.save(SHOTS / "terminal.png")
    print(f"terminal.png from {trace_file.name}: {len(lines)} lines, {img.height} px tall")


def clip(image: str, moves: list[tuple[str, float, float, float]], out: Path) -> float:
    """moves: (kind, seconds, y_from, y_to) with kind 'hold' or 'scroll'; y is the top of the 1080 window."""
    src = SHOTS / image
    parts, total = [], 0.0
    for n, (kind, secs, y0, y1) in enumerate(moves):
        part = out.with_name(f"{out.stem}_{n}.mp4")
        expr = f"{y0}" if kind == "hold" else f"{y0}+({y1}-{y0})*min(1\\,t/{secs})"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-t", f"{secs}", "-i", str(src),
                        "-vf", f"scale={W}:-2,pad={W}:max(ih\\,{H}):0:0:color=#FFFFFF,crop={W}:{H}:0:'{expr}',fps={FPS},"
                               "format=yuv420p", "-c:v", "libx264", "-crf", "18", "-r", str(FPS), str(part)],
                       check=True)
        parts.append(part)
        total += secs
    return total, parts


def join(parts: list[Path], out: Path) -> None:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst.name,
                    "-c", "copy", out.name], check=True, cwd=out.parent)
    for p in parts:
        p.unlink()
    lst.unlink()


def narration_len(take: str) -> float:
    for ext in (".mp3", ".m4a", ".wav"):
        f = IN / f"{take}{ext}"
        if f.exists():
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                 capture_output=True, text=True, check=True).stdout
            return float(out) + 0.8
    return 20.0


def build(plan: dict[str, list[tuple[str, list]]]) -> None:
    for shot, segments in plan.items():
        parts = []
        for image, moves in segments:
            _, p = clip(image, moves, IN / f"{shot}.mp4")
            parts += p
        join(parts, IN / f"{shot}.mp4")
        print(f"{shot}.mp4 built")


def plan() -> dict[str, list[tuple[str, list]]]:
    """Each shot's moves, scaled to its narration's length. y values are pixels in the 1920-wide images."""
    def fit(take: str, segs: list[tuple[str, list]]) -> list[tuple[str, list]]:
        want = narration_len(take)
        have = sum(m[1] for _, moves in segs for m in moves)
        k = want / have
        return [(img, [(kind, round(s * k, 2), a, b) for kind, s, a, b in moves]) for img, moves in segs]
    return {
        "shot2": fit("V2", [("index.png", [("hold", 6, 0, 0), ("scroll", 6, 0, 500), ("hold", 4, 500, 500)])]),
        "shot3": fit("V3", [("brief5567.png", [("hold", 8, 0, 0), ("scroll", 5, 0, 520), ("hold", 8, 520, 520)])]),
        "shot4": fit("V4", [("terminal.png", [("hold", 8, 0, 0), ("scroll", 6, 0, 400), ("hold", 4, 400, 400)]),
                            ("zetaris_sql.png", [("hold", 12, 0, 0)])]),
        "shot5": fit("V5", [("brief5567.png", [("scroll", 4, 520, 1000), ("hold", 6, 1000, 1000),
                                               ("scroll", 4, 1000, 1700), ("hold", 4, 1700, 1700)]),
                            ("row_reg.png", [("hold", 6, 0, 0)])]),
        "shot6": fit("V6", [("brief5567.png", [("hold", 6, 1500, 1500)]),
                            ("brief5559.png", [("hold", 6, 0, 0), ("scroll", 4, 0, 1450), ("hold", 6, 1450, 1450)])]),
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "capture":
        capture()
    elif cmd == "terminal":
        terminal()
    elif cmd == "build":
        build(plan())
    else:
        sys.exit(__doc__)
