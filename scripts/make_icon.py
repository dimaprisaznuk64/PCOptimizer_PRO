"""Generate assets/app.ico for the PyInstaller build (no external design tools)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZES = (16, 24, 32, 48, 64, 128, 256)
BG = (15, 17, 21, 255)
ACCENT = (79, 140, 255, 255)
INNER = (15, 17, 21, 255)


def make_icon(path: Path) -> Path:
    images = []
    for size in SIZES:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        radius = max(size // 5, 1)
        draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=BG)
        margin = max(size // 6, 1)
        draw.ellipse((margin, margin, size - 1 - margin, size - 1 - margin), fill=ACCENT)
        inner = size // 4
        draw.ellipse((inner, inner, size - 1 - inner, size - 1 - inner), fill=INNER)
        images.append(img)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(path, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    return path


if __name__ == "__main__":
    out = make_icon(Path(__file__).resolve().parent.parent / "assets" / "app.ico")
    print(f"icon written: {out}")
