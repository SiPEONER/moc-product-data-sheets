"""Product photos: swap in better cutouts and make every photo consistent.

    python3 tools/photos.py swap picks.json   # {"<item>": "<path to source PNG>", ...}
    python3 tools/photos.py normalize          # trim and size every img/*.png

Every photo is trimmed to the product (no transparent margin), so each bottle
fills the same photo box on the sheet, and capped at 1,800 px tall (300 dpi at
the ad sheet's 5.75 in box) to keep the PDFs light. A swap records where the
photo came from in the product file ("photo") and drops an ad-only photo
override once the main photo is sharp enough.
"""
import json, pathlib, sys
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = pathlib.Path(__file__).resolve().parent.parent
MAX_H = 1800
SHARP = 900  # px tall: below this a photo reads soft on the sheet


def clean(src, dest):
    im = Image.open(src)
    im = im.convert("RGBA")
    box = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        im = im.crop(box)
    if im.height > MAX_H:
        im = im.resize((round(im.width * MAX_H / im.height), MAX_H), Image.LANCZOS)
    im.save(dest, optimize=True)
    return im.size


def swap(picks):
    for item, src in sorted(picks.items()):
        f = ROOT / "products" / f"{item}.json"
        p = json.loads(f.read_text())
        dest = ROOT / "img" / f"{item}.png"
        w, h = clean(src, dest)
        p["image"] = f"img/{dest.name}"
        p["photo"] = {"source": src.split("Graphics/")[-1].split("uploads/")[-1], "px": h}
        if p.get("ad", {}).get("image") and h >= SHARP:
            (ROOT / p["ad"].pop("image")).unlink(missing_ok=True)
        f.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n")
        print(f"{item:>7}  {h:>5}px  {p['photo']['source']}")


def normalize():
    soft = []
    for f in sorted((ROOT / "img").glob("*.png")):
        w, h = clean(f, f)
        if h < SHARP:
            soft.append(f.stem)
    print(f"normalized {len(list((ROOT / 'img').glob('*.png')))} photos; under {SHARP}px: {len(soft)}")
    print(" ".join(soft))


if __name__ == "__main__":
    if sys.argv[1] == "swap":
        swap(json.loads(pathlib.Path(sys.argv[2]).read_text()))
    else:
        normalize()
