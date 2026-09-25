"""Draw the placeholder tiles for Danny's ingredients and photo-less dishes.

usage: backend/.venv/Scripts/python.exe scripts/make_placeholders.py (Windows: needs Segoe UI Emoji)

Reads PLACEHOLDER_ICONS from seed_dannys.py (one source of truth) and writes
frontend/public/placeholders/<slug>.png, the path `placeholder_url()` gives.
"""
import ast
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "backend" / "app" / "scripts" / "seed_dannys.py"
OUT = ROOT / "frontend" / "public" / "placeholders"
FONT = r"C:\Windows\Fonts\seguiemj.ttf"

# Soft backgrounds per group, light enough for the icon to carry the colour.
COLOURS = {
    "meat": (253, 226, 222), "seafood": (219, 236, 250), "veg": (225, 243, 222),
    "dairy": (250, 246, 225), "dry": (243, 235, 222), "bakery": (248, 228, 238),
    "frozen": (224, 240, 248), "bev": (236, 230, 248), "prep": (252, 236, 214),
    "dish": (250, 238, 220),
}


def load_icons() -> dict:
    tree = ast.parse(SEED.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "PLACEHOLDER_ICONS":
            return ast.literal_eval(node.value)
    sys.exit("PLACEHOLDER_ICONS not found")


def slug(name: str) -> str:
    # Must match placeholder_url() in seed_dannys.py.
    s = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s


def tile(icon: str, group: str) -> Image.Image:
    w, h = 400, 300
    img = Image.new("RGB", (w, h), COLOURS[group])
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 150)
    box = draw.textbbox((0, 0), icon, font=font, embedded_color=True)
    x = (w - (box[2] - box[0])) / 2 - box[0]
    y = (h - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), icon, font=font, embedded_color=True)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icons = load_icons()
    for name, (icon, group) in icons.items():
        tile(icon, group).save(OUT / f"{slug(name)}.png", optimize=True)
    print(f"wrote {len(icons)} tiles to {OUT}")


if __name__ == "__main__":
    main()
