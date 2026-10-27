"""Title cards for the demo video (shots 1, 7 and 8), 1920x1080 PNG, in the deck's colours.

    uv run --with pillow python video/make_cards.py     writes video/cards/card1a.png ... card8.png

Every number on a card is the README's; change them here if the README changes.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "cards"
W, H = 1920, 1080
BG, INK, MUTED, ACCENT = "#161B26", "#F6F5F1", "#B8BFCC", "#F59E5B"
FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


REG, BOLD, MONO = "segoeui.ttf", "segoeuib.ttf", "consola.ttf"


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if d.textlength(test, font=f) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + [line]


def block(d, x, y, text, f, fill, width, spacing=1.25) -> int:
    for line in wrap(d, text, f, width):
        d.text((x, y), line, font=f, fill=fill)
        y += int(f.size * spacing)
    return y


def card1() -> None:
    """Three lines that appear one by one: three images, the same layout."""
    lines = ["2013 to 2015",
             "A company registered in Latvia, with the same name as an Asian hardware supplier",
             "Over $120 million wired by two US internet companies"]
    for n in range(1, 4):
        img, d = canvas()
        y = 300
        for i, text in enumerate(lines[:n]):
            f = font(BOLD, 84) if i == 0 else font(REG, 60)
            y = block(d, 160, y, text, f, ACCENT if i == 0 else INK, 1600) + 40
        d.text((160, 960), "Source: US Department of Justice (SDNY), 19 December 2019; reported to be Google and Facebook (WSKG/NPR, 2019)",
               font=font(REG, 28), fill=MUTED)
        img.save(OUT / f"card1{'abc'[n - 1]}.png")


def card7() -> None:
    img, d = canvas()
    d.text((160, 120), "Tested on text we did not write", font=font(BOLD, 72), fill=INK)
    block(d, 160, 230, "NVIDIA Nemotron wrote 44 new requests: impostor e-mails, look-alike domains, new prompt injections. "
          "Sealed with SHA-256 hashes before the first run, evaluated once.", font(REG, 36), MUTED, 1600)
    cols = [160, 900, 1240, 1580]
    head = ["Held-out set", "Payee list only", "PayProof, patterns", "PayProof, model screen"]
    rows = [["Attacks paid without a human", "15 / 24", "6 / 24", "2 / 24"],
            ["Attack money paid", "57.2%", "15.9%", "3.3%"],
            ["Normal payments interrupted", "4 / 20", "0 / 20", "0 / 20"]]
    y = 440
    for x, h in zip(cols, head):
        for i, part in enumerate(wrap(d, h, font(BOLD, 34), 300 if x > 160 else 700)):
            d.text((x, y + i * 42), part, font=font(BOLD, 34), fill=MUTED)
    y += 110
    for r in rows:
        d.line([(160, y - 20), (1840, y - 20)], fill="#2E3646", width=2)
        for j, (x, cell) in enumerate(zip(cols, r)):
            d.text((x, y), cell, font=font(BOLD if j == 3 else REG, 44), fill=ACCENT if j == 3 else INK)
        y += 110
    block(d, 160, 920, "Fictional data; the case mix is a design choice, not field data. Sealed at commit efa9fec; "
          "CI re-checks the seal on every change.", font(REG, 28), MUTED, 1600)
    img.save(OUT / "card7.png")


def card8() -> None:
    img, d = canvas()
    d.text((160, 120), "Sponsor technology, carrying the load", font=font(BOLD, 64), fill=INK)
    items = [("Zetaris", "every check is federated SQL where the data lives; the Verifier re-reads each cited cell there"),
             ("Meterless", "World Model resolves companies by registration number; one injected generator for every model call; Scout-style execution contract"),
             ("NVIDIA Nemotron", "wrote the sealed red-team set the numbers come from")]
    y = 260
    for name, text in items:
        d.text((160, y), name, font=font(BOLD, 44), fill=ACCENT)
        y = block(d, 600, y + 4, text, font(REG, 38), INK, 1160) + 40
    # kept above y 820: the subtitles sit below that
    d.text((160, max(y + 20, 690)), "PayProof", font=font(BOLD, 96), fill=INK)
    d.text((640, max(y + 20, 690) + 42), "github.com/hoongyu/gouji", font=font(REG, 40), fill=MUTED)
    img.save(OUT / "card8.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    card1()
    card7()
    card8()
    print(sorted(p.name for p in OUT.glob("*.png")))
