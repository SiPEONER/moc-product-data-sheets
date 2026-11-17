"""Product image library: images/manifest.csv + the library's own photos -> web/images/ (page, files, zip).

    python3 tools/images.py

The page lives at /images/ (cleanUrls). Built from the same files the data sheets use, so it follows every swap:
  default package   img/<item>.png
  5 gal pail        img/sizes/<item>_5gal.png
images/manifest.csv is the label chat's list (2026-11-17): one row per label part number (item number plus a size
digit: 1 bottle or aerosol, 3 one gallon, 4 quart, 5 five gallon), with name, variant, package and net contents.
Rows whose product shows no image on its data sheet (photo.none) are left out, so the library never offers an
image the sheets have withdrawn.

Output
  web/images/index.html        the page (search, package filter, per-image downloads)
  web/images/full/<pn>.png     the library photo, byte for byte (git stores it once), about 1,800 px tall
  web/images/web_800/<pn>.png  800 px tall
  web/images/thumbs/<pn>.webp  360 px tall, for the page grid only
  web/images/manifest.csv      as published (actual pixel sizes)
  web/images/MOC_product_images_800px.zip   web_800 + manifest + README, built reproducibly (no churn on rebuild)
"""
import csv, io, json, pathlib, shutil, sys, zipfile
from jinja2 import Environment, select_autoescape
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

OUT = ROOT / "web" / "images"
PKGS = ["Additive bottle", "Aerosol can", "32 oz bottle", "1 gal jug", "5 gal pail"]
ZIP = "MOC_product_images_800px.zip"
WEB_H, THUMB_H = 800, 360
README = """MOC Products // product image library

{n} product images on a transparent background (PNG with alpha), front view, trimmed to the product.
These are renders of the new MOC label on each package, the same images used on the MOC product data sheets.
Online: https://datasheets.mocproducts.app/images/

This zip
  {n} images, 800 px tall, for web, CRM and POS screens
  manifest.csv   one row per image: part number, item number, product name, variant, package, net contents, file, pixel sizes
  The 1,800 px version of each image is a separate download on the page above.

File names
  Each file is named by the part number printed on the label (for example 41263.png).
  The part number is the item number plus a size digit: 1 = bottle or aerosol, 3 = 1 gal, 4 = 32 oz, 5 = 5 gal.
  So item 4126 has two images: 41263.png (1 gal jug) and 41265.png (5 gal pail). Use manifest.csv to map them.

What is included
  {counts}.
  Products not listed in manifest.csv do not have a new image yet (Pro Series, drums, kits and other low-volume packages).

Notes
  Fluid colors in the jugs and pails are matched to product photos and are approximate.
  The descriptive lines on the labels are draft copy pending MOC's product review; part numbers, names and sizes are final.
"""


def source(row):
    it = row["item_number"]
    return ROOT / ("img/sizes/" + f"{it}_5gal.png" if row["package"] == "5 gal pail" else f"img/{it}.png")


def resize(src, h, dest, **kw):
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:  # unchanged photo: keep the file (fast rebuild)
        return Image.open(dest).size
    im = Image.open(src).convert("RGBA")
    im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, **kw)
    if not dest.exists() or dest.read_bytes() != buf.getvalue():
        dest.write_bytes(buf.getvalue())
    return im.size


def main():
    products = {json.loads(p.read_text())["item"]: json.loads(p.read_text()) for p in (ROOT / "products").glob("*.json")}
    rows, skipped = [], []
    for r in csv.DictReader(open(ROOT / "images/manifest.csv", newline="")):
        p = products.get(r["item_number"])
        if not p or p.get("photo", {}).get("none"):
            skipped.append(f"{r['part_number']} ({r['item_number']} {r['package']}: no image on its data sheet)")
            continue
        if not source(r).exists():
            sys.exit(f"Missing {source(r)} for part {r['part_number']}")
        rows.append(r)
    for sub in ("full", "web_800", "thumbs"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    keep = {r["part_number"] for r in rows}
    for sub in ("full", "web_800", "thumbs"):
        for f in (OUT / sub).iterdir():
            if f.stem not in keep:
                f.unlink()

    out = []
    for r in rows:
        pn, src = r["part_number"], source(r)
        full = OUT / "full" / f"{pn}.png"
        if not full.exists() or full.read_bytes() != src.read_bytes():
            shutil.copyfile(src, full)
        fw, fh = Image.open(src).size
        ww, wh = resize(src, WEB_H, OUT / "web_800" / f"{pn}.png", format="PNG", optimize=True)
        resize(src, THUMB_H, OUT / "thumbs" / f"{pn}.webp", format="WEBP", quality=82, method=6)
        ds = build.file_base("pds", products[r["item_number"]]) if build.has("pds", products[r["item_number"]]) else ""
        out.append(dict(pn=pn, item=r["item_number"], name=r["product_name"], variant=r["variant"], pkg=r["package"],
                        net=r["net_contents"], fw=fw, fh=fh, ww=ww, wh=wh, ds=ds,
                        full_kb=round((OUT / "full" / f"{pn}.png").stat().st_size / 1024),
                        web_kb=round((OUT / "web_800" / f"{pn}.png").stat().st_size / 1024)))

    # manifest as published
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["part_number", "item_number", "product_name", "variant", "package", "net_contents",
                "full_file", "full_width_px", "full_height_px", "web_file", "web_width_px", "web_height_px"])
    for o in out:
        w.writerow([o["pn"], o["item"], o["name"], o["variant"], o["pkg"], o["net"],
                    f"full/{o['pn']}.png", o["fw"], o["fh"], f"web_800/{o['pn']}.png", o["ww"], o["wh"]])
    manifest = buf.getvalue()
    (OUT / "manifest.csv").write_text(manifest)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["part_number", "item_number", "product_name", "variant", "package", "net_contents",
                "file", "width_px", "height_px", "full_size_url"])
    for o in out:
        w.writerow([o["pn"], o["item"], o["name"], o["variant"], o["pkg"], o["net"], f"{o['pn']}.png", o["ww"], o["wh"],
                    f"https://datasheets.mocproducts.app/images/full/{o['pn']}.png"])
    zip_manifest = buf.getvalue()

    counts = {k: sum(o["pkg"] == k for o in out) for k in PKGS}
    readme = README.format(n=len(out),
                           counts=", ".join(f"{k}s: {v}" for k, v in counts.items()))
    (OUT / "README.txt").write_text(readme)

    # reproducible zip: fixed timestamps, stored (PNGs are already compressed); rewrite only when contents change
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_STORED) as z:
        def add(name, data):
            zi = zipfile.ZipInfo(f"MOC_product_images_800px/{name}", date_time=(2026, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)
        add("README.txt", readme)
        add("manifest.csv", zip_manifest)
        for o in out:
            add(f"{o['pn']}.png", (OUT / "web_800" / f"{o['pn']}.png").read_bytes())
    zp = OUT / ZIP
    if not zp.exists() or zp.read_bytes() != zbuf.getvalue():
        zp.write_bytes(zbuf.getvalue())

    env = Environment(autoescape=select_autoescape(default=True))
    html = env.from_string((ROOT / "images_template.html").read_text()).render(
        items=out, pkgs=[(k, counts[k]) for k in PKGS], total=len(out), zip=ZIP,
        zip_mb=f"{zp.stat().st_size / 1e6:.0f}", noindex=build.NOINDEX, base="https://datasheets.mocproducts.app")
    (OUT / "index.html").write_text(html)
    print(f"images: {len(out)} published ({', '.join(f'{v} {k}' for k, v in counts.items())}); zip {zp.stat().st_size / 1e6:.1f} MB")
    for s in skipped:
        print("  left out:", s)


if __name__ == "__main__":
    main()
