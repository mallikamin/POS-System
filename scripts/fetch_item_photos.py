"""Real photos for Danny's ingredients and photo-less dishes (D-38 round 2).

Step 1, candidates:  python scripts/fetch_item_photos.py candidates
    Searches Openverse (Creative Commons, commercial use allowed) for each item,
    downloads up to 4 candidates to _files/2026-09-25/photo-candidates/, and
    draws labelled contact sheets there so a person can pick by eye.
Step 2, publish:     python scripts/fetch_item_photos.py publish
    Reads picks.json ({name: candidate index}) from the candidates folder,
    writes frontend/public/photos/<slug>.jpg (400x300, cropped) and
    frontend/public/photos/CREDITS.md (title, author, licence, source).

Hosted by us, not hot-linked, so a photo cannot vanish or change under a demo.
"""
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "_files" / "2026-09-25" / "photo-candidates"
OUT = ROOT / "frontend" / "public" / "photos"
UA = "SitaraPOS/1.0 (amin@sitaratech.info)"

# name -> search query. Queries name the raw product as a kitchen buys it.
QUERIES = {
    "Chicken (Karahi Cut)": "raw chicken", "Boneless Chicken": "raw chicken breast",
    "Chicken Wings": "chicken wing", "Mutton": "raw mutton meat", "Beef Mince": "raw minced beef",
    "Beef Undercut (Local)": "raw beef steak", "Beef Ribeye (Local)": "raw ribeye steak",
    "Beef Tenderloin (Imported)": "beef tenderloin raw", "Prawns": "raw shrimp",
    "Fish Fillet": "raw fish fillet", "Tomato": "tomatoes", "Onion": "onions", "Ginger": "ginger root",
    "Garlic": "garlic bulbs", "Green Chilli": "green chili", "Capsicum": "green bell pepper",
    "Lettuce": "iceberg lettuce", "Lemon": "lemons", "Yogurt": "yogurt bowl", "Fresh Cream": "heavy cream",
    "Milk": "glass of milk", "Butter": "butter stick", "Mozzarella Cheese": "mozzarella cheese",
    "Cheddar Slices": "cheddar cheese slices", "Parmesan": "parmesan cheese", "Blue Cheese": "blue cheese",
    "Cooking Oil": "olive oil bottle", "Salt": "salt", "Black Pepper": "black peppercorns",
    "Karahi Spice Mix": "indian spice mix", "Tikka Spice Mix": "tandoori masala spice",
    "Maida (Flour)": "white flour", "Yeast": "dry yeast", "Sugar": "white sugar",
    "Basmati Rice": "basmati rice", "Cornflour": "cornstarch", "Soy Sauce": "soy sauce",
    "Chilli Sauce": "hot sauce bottle", "Mayonnaise": "mayonnaise", "Fettuccine Pasta": "fettuccine pasta",
    "Eggs": "brown eggs", "Breadcrumbs": "bread crumbs", "Egg Noodles": "egg noodles", "Peanuts": "peanuts",
    "Honey": "honey jar", "Burger Buns": "burger buns", "Molten Lava Cake": "chocolate lava cake",
    "Tiramisu Slice": "tiramisu", "Cheesecake Slice": "cheesecake slice",
    "Walnut Brownie Piece": "walnut brownie", "Kunafa Portion": "kunafa",
    "Frozen Fries": "french fries", "Vanilla Ice Cream": "ice cream tub",
    "Espresso Beans": "coffee beans", "Tea Leaves": "black tea leaves", "Oreo Biscuits": "oreo cookies",
    "Lotus Biscuits": "biscoff", "Soft Drink Can": "cola can", "Mineral Water (Small)": "water bottle",
    "Caramel Syrup": "dulce de leche", "Blue Curacao Syrup": "blue curacao",
    "Pineapple Juice": "pineapple juice", "Coconut Cream": "coconut milk",
    "Karahi Masala Base": "tomato masala", "Naan Dough": "dough ball", "Tikka Marinade": "tandoori marinade",
    "Malai Marinade": "yogurt marinade", "Garlic Mayo": "aioli", "White Sauce": "bechamel sauce",
    "Black Pepper Sauce": "pepper sauce steak",
    "Roti": "tandoori roti", "Roghni Naan": "naan bread", "Garlic Naan": "garlic naan",
    "Cheese Naan": "cheese naan", "Kunafa": "kunafa", "Prawn Masala": "prawn masala curry",
}


def slug(name: str) -> str:
    s = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s


def get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fit(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    return ImageOps.fit(img, (400, 300), Image.LANCZOS)


def candidates(only: list[str]) -> None:
    CAND.mkdir(parents=True, exist_ok=True)
    meta_path = CAND / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    names = only or list(QUERIES)
    for name in names:
        if name in meta and not only:
            continue
        q = urllib.parse.quote(QUERIES[name])
        try:
            res = json.loads(get(
                f"https://api.openverse.org/v1/images/?q={q}&page_size=8&license_type=commercial"
                "&mature=false&extension=jpg"
            ))["results"]
        except Exception as e:  # noqa: BLE001
            print(f"search failed {name}: {e}")
            time.sleep(10)
            continue
        kept = []
        for r in res:
            if len(kept) == 4:
                break
            try:
                fit(get(r["url"])).save(CAND / f"{slug(name)}-{len(kept)}.jpg", quality=85)
            except Exception:  # noqa: BLE001
                continue
            kept.append({k: r.get(k) for k in ("title", "creator", "license", "license_version",
                                                 "foreign_landing_url", "url")})
        meta[name] = kept
        meta_path.write_text(json.dumps(meta, indent=1))
        print(f"{name}: {len(kept)}")
        time.sleep(4)  # anonymous Openverse rate limit
    sheets({n: meta[n] for n in names if n in meta}, "retry" if only else "sheet")


def sheets(meta: dict, prefix: str = "sheet") -> None:
    font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)
    names = list(meta)
    per = 6
    for s in range(0, len(names), per):
        chunk = names[s:s + per]
        sheet = Image.new("RGB", (4 * 210 + 260, len(chunk) * 170), "white")
        d = ImageDraw.Draw(sheet)
        for row, name in enumerate(chunk):
            d.text((8, row * 170 + 60), name[:22], fill="black", font=font)
            for i in range(len(meta[name])):
                p = CAND / f"{slug(name)}-{i}.jpg"
                if p.exists():
                    thumb = Image.open(p).resize((200, 150))
                    x, y = 260 + i * 210, row * 170 + 5
                    sheet.paste(thumb, (x, y))
                    d.rectangle((x, y, x + 28, y + 28), fill="yellow")
                    d.text((x + 7, y + 1), str(i), fill="black", font=font)
        sheet.save(CAND / f"{prefix}-{s // per:02d}.jpg", quality=80)
    print(f"sheets written to {CAND}")


def publish() -> None:
    meta = json.loads((CAND / "meta.json").read_text())
    picks = json.loads((CAND / "picks.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# Photo credits", "", "Creative Commons photos via Openverse, cropped to 400x300.", ""]
    for name, idx in picks.items():
        src = CAND / f"{slug(name)}-{idx}.jpg"
        Image.open(src).save(OUT / f"{slug(name)}.jpg", quality=82, optimize=True, progressive=True)
        m = meta[name][idx]
        lic = f"CC {m['license'].upper()} {m.get('license_version') or ''}".strip()
        lines.append(f"* {name}: \"{m['title']}\" by {m['creator']}, {lic}, {m['foreign_landing_url']}")
    (OUT / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"published {len(picks)} photos to {OUT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "candidates":
        candidates(sys.argv[2:])
    elif cmd == "sheets":
        sheets(json.loads((CAND / "meta.json").read_text()))
    elif cmd == "publish":
        publish()
    else:
        sys.exit(__doc__)
