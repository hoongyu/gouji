"""Shots 2 to 6 of the demo video, made from the running app instead of a manual screen recording.

    python video/make_shots.py capture [name ...]   headless Chrome screenshots of the live pages ($PAYPROOF_URL)
    python video/make_shots.py terminal logs/trace-<run_id>.jsonl   that run's agent steps, as a terminal image
    python video/make_shots.py zetaris   the C1 join run on Zetaris, as an image (stand-in for a SQL Editor shot)
    python video/make_shots.py build [shot ...]   video/input/shot2.mp4 ... shot6.mp4, each as long as its narration

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
BASE = __import__("os").environ.get("PAYPROOF_URL", "http://localhost:8010")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
W, H, FPS = 1920, 1080, 30
PAGES = {
    "index": ("/", 1600),
    "brief5567": ("/brief/INV-5567", 7000),
    "row_inv": ("/row/invoices/INV-5567?col=issuer_reg_no", 1300),
    "row_reg": ("/row/registry/LV-SYN-90501?col=incorporated_on", 1300),
    "brief5559": ("/brief/INV-5559", 6000),
}


def capture(names: list[str]) -> None:
    SHOTS.mkdir(exist_ok=True)
    for name, (path, height) in PAGES.items():
        if names and name not in names:
            continue
        out = SHOTS / f"{name}.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size=1280,{height}",
                        "--force-device-scale-factor=1.5", f"--screenshot={out}", BASE + path],
                       check=True, capture_output=True, timeout=600)
        print(f"{out.name}: {out.stat().st_size // 1024} KB")


def terminal(trace_file: Path) -> None:
    """Render one run's trace (logs/trace-<run_id>.jsonl) as a terminal screenshot."""
    from PIL import Image, ImageDraw, ImageFont
    events = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
    events = [e for e in events if e.get("inv_id", "INV-5567") == "INV-5567"]
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 26)
    bold = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 26)
    lines = [("$ uv run python run.py case INV-5567 --backend zetaris", "#9FE2BF")]
    for e in events:  # traces written before the singular fix said "1 red flags"
        lines.append((f"{e['agent']:<13}{e['action']:<13}{e['summary'].replace('(1 red flags)', '(1 red flag)')}",
                      "#E6E8EC"))
    img = Image.new("RGB", (W, max(H, 140 + 40 * len(lines) * 2)), "#0F1218")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 56], fill="#1E2430")
    d.text((24, 14), "Terminal: every query goes to Zetaris (REST API, localhost:8888)", font=bold, fill="#B8BFCC")
    y = 90
    for text, colour in lines:
        while text:  # wrap at the last space before 120 characters
            cut = len(text) if len(text) <= 120 else text.rindex(" ", 0, 120)
            d.text((40, y), text[:cut], font=font, fill=colour)
            text = (" " * 26 + text[cut:].lstrip()) if cut < len(text) else ""
            y += 40
    img = img.crop((0, 0, W, max(H, y + 40)))
    img.save(SHOTS / "terminal.png")
    print(f"terminal.png from {trace_file.name}: {len(lines)} lines, {img.height} px tall")


QUERY = """SELECT i.inv_id, i.issuer_reg_no, p.po_id, v.vendor_id, v.reg_no AS master_reg_no,
       c.contract_id, c.vendor_reg_no AS contract_reg_no, c.jurisdiction
FROM erp.invoices i
JOIN erp.purchase_orders p ON p.po_id = i.po_ref
JOIN vendor_master.vendors v ON v.vendor_id = p.vendor_id
LEFT JOIN documents.contracts c ON c.vendor_reg_no = v.reg_no AND c.item = p.item AND c.amendment_of IS NULL
WHERE i.inv_id = 'INV-5567'"""


def zetaris_query() -> None:
    """Run the C1 join on Zetaris through its REST API and render the statement and its answer."""
    from PIL import Image, ImageDraw, ImageFont

    sys.path.insert(0, str(HERE.parent))
    from gouji.harness import zetaris_post
    from gouji.llm import load_dotenv
    load_dotenv()
    out = zetaris_post(QUERY)
    cols, rows = out["headers"], out["data"]
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 26)
    bold = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 26)
    img = Image.new("RGB", (W, H), "#0F1218")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 56], fill="#1E2430")
    d.text((24, 14), "Zetaris Lightning SQL, one query across three systems (REST API, localhost:8888)", font=bold,
           fill="#B8BFCC")
    y = 90
    for line in QUERY.splitlines():
        d.text((40, y), line, font=font, fill="#9FE2BF")
        y += 38
    y += 30
    d.text((40, y), f"{len(rows)} row, answered by Zetaris", font=font, fill="#8A93A3")
    y += 56
    widths = [max(len(c), *(len(str(r[i])) for r in rows)) + 2 for i, c in enumerate(cols)]
    x = 40
    for c, w in zip(cols, widths):
        d.text((x, y), c, font=bold, fill="#E6E8EC")
        x += w * 14.3
    y += 44
    for r in rows:
        x = 40
        for i, (v, w) in enumerate(zip(r, widths)):
            colour = "#FF8A80" if cols[i] == "issuer_reg_no" else "#8EC5FF" if "TW" in str(v) else "#E6E8EC"
            d.text((x, y), str(v), font=font, fill=colour)
            x += w * 14.3
        y += 40
    y += 60
    big = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 40)
    d.text((40, y), "The invoice comes from a Latvian company (LV).", font=big, fill="#FF8A80")
    d.text((40, y + 60), "The order, the vendor master and the contract all point to Taiwan (TW).", font=big, fill="#8EC5FF")
    img.save(SHOTS / "zetaris_query.png")
    print(f"zetaris_query.png: {len(rows)} row(s), columns {', '.join(cols)}")


def clip(image: str, moves: list[tuple], out: Path, first: int = 0) -> float:
    """moves: (kind, seconds, a, b). 'hold' and 'scroll' move a 1080-high window over the image scaled to 1920 wide,
    from top y=a to y=b; 'fit' letterboxes a region (a = (x, y, w, h) in source pixels, or None for the whole image)."""
    src = SHOTS / image
    parts, total = [], 0.0
    for n, (kind, secs, y0, y1) in enumerate(moves):
        part = out.with_name(f"{out.stem}_{first + n}.mp4")
        if kind == "fit":
            region = f"crop={y0[2]}:{y0[3]}:{y0[0]}:{y0[1]}," if y0 else ""
            vf = (f"{region}scale={W}:{H}:force_original_aspect_ratio=decrease,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=#0F1218")
        else:
            expr = f"{y0}" if kind == "hold" else f"{y0}+({y1}-{y0})*min(1\\,t/{secs})"
            vf = f"scale={W}:-2,pad={W}:max(ih\\,{H}):0:0:color=#FFFFFF,crop={W}:{H}:0:'{expr}'"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-t", f"{secs}", "-i", str(src),
                        "-vf", f"{vf},setsar=1,fps={FPS},format=yuv420p", "-c:v", "libx264", "-crf", "18", "-r", str(FPS),
                        str(part)], check=True)
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


def build(plan: dict[str, list[tuple[str, list]]], only: list[str]) -> None:
    for shot, segments in plan.items():
        if only and shot not in only:
            continue
        parts = []
        for image, moves in segments:
            _, p = clip(image, moves, IN / f"{shot}.mp4", len(parts))
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
    # the SQL Editor screenshot when there is one, else the same query rendered from the REST answer
    sql_shot = "zetaris_sql.png" if (SHOTS / "zetaris_sql.png").exists() else "zetaris_query.png"
    # brief5567 windows: 0 verdict and Why, 450 Why and the quarantined note, 900 World Model alerts and evidence,
    # 1300 evidence and the refused pay call, 1650 findings with cited cells. brief5559: 0 release, 1050 the contract.
    return {
        "shot2": fit("V2", [("index.png", [("hold", 6, 0, 0), ("scroll", 6, 0, 500), ("hold", 4, 500, 500)])]),
        "shot3": fit("V3", [("brief5567.png", [("hold", 10.5, 0, 0), ("scroll", 2, 0, 450), ("hold", 8.7, 450, 450)])]),
        "shot4": fit("V4", [("terminal.png", [("hold", 18.5, 0, 0)]),
                            (sql_shot, [("fit", 11.2, None, None)])]),
        "shot5": fit("V5", [("brief5567.png", [("scroll", 1.5, 450, 900), ("hold", 7.5, 900, 900),
                                               ("scroll", 1.5, 900, 1650), ("hold", 2, 1650, 1650)]),
                            ("row_reg.png", [("hold", 3.5, 0, 0)]),
                            ("brief5567.png", [("hold", 8, 1300, 1300)])]),
        "shot6": fit("V6", [("brief5567.png", [("hold", 6, 1300, 1300)]),
                            ("brief5559.png", [("hold", 5, 0, 0), ("scroll", 2, 0, 1050), ("hold", 6.5, 1050, 1050)])]),
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "capture":
        capture(sys.argv[2:])
    elif cmd == "terminal":
        terminal(Path(sys.argv[2]))
    elif cmd == "zetaris":
        zetaris_query()
    elif cmd == "build":
        build(plan(), sys.argv[2:])
    else:
        sys.exit(__doc__)
