"""Turn an old MOC Product Performance & Data Sheet PDF into a products/<item>.json draft.

    python3 tools/extract_ppd.py <pdf> [<pdf> ...] --out drafts/

What it reads from the old sheet:
  header line   "AUTOMOTIVE BRAKE FLUID - #0602"  -> category, item
  product name  set as artwork in the header       -> OCR (tesseract), checked against the description
  sections      Performance Ratings, Outstanding Features, Description, Application,
                Specifications, Packaging          -> by heading position
  bottle photo  the largest embedded RGB image with a transparency mask -> img/<item>.png
  revision      "Rev002" in the footer             -> new sheet is the next revision (3.0)

Every draft carries a "review" list of anything the extractor was unsure about.
Nothing here edits product copy; typos are flagged, not fixed.
"""
import argparse, io, json, pathlib, re, subprocess, sys, tempfile
import pdfplumber
from PIL import Image, ImageChops

HEADS = ["PERFORMANCE RATINGS", "OUTSTANDING FEATURES", "DESCRIPTION", "APPLICATION", "SPECIFICATIONS", "PACKAGING"]
# Spellings and synonyms seen on the old sheets.
ALIASES = {"KEY FEATURES": "OUTSTANDING FEATURES", "PAKAGING": "PACKAGING", "PACKAGE": "PACKAGING", "PERFORMANCE RATING": "PERFORMANCE RATINGS"}
DASHES = re.compile(r"\s+[–—-]\s+")  # " – " between a feature's lead-in and its text


def lines_of(page):
    """Group words into lines (by top), keeping x positions."""
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False, extra_attrs=["size"])
    rows = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if rows and abs(rows[-1]["top"] - w["top"]) < 3:
            rows[-1]["words"].append(w)
        else:
            rows.append({"top": w["top"], "words": [w]})
    out = []
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
        # A heading in the left column can share a line with feature text in the right column:
        # split such lines at the wide gap so the heading stands alone.
        segs, cur = [], [r["words"][0]]
        for w in r["words"][1:]:
            if w["x0"] - cur[-1]["x1"] > 40:
                segs.append(cur); cur = []
            cur.append(w)
        segs.append(cur)
        if len(segs) > 1 and any(norm_head(" ".join(w["text"] for w in sg)) for sg in segs):
            # Keep the right-hand (earlier) column's text ahead of the new heading.
            parts = sorted(segs, key=lambda sg: 0 if not norm_head(" ".join(w["text"] for w in sg)) else 1)
        else:
            parts = [r["words"]]
        for ws in parts:
            text = " ".join(w["text"] for w in ws)
            if "Montague" in text or "All rights reserved" in text:
                continue
            out.append({"top": r["top"], "words": ws, "text": text, "x0": ws[0]["x0"]})
    return out


def norm_head(t):
    t = re.sub(r"[^A-Z ]", "", t.upper()).strip()
    t = t.rstrip(":")
    if t in ALIASES:
        return ALIASES[t]
    for h in HEADS:
        if t == h or t == h.rstrip("S") or t.startswith(h):
            return h
    return None


def split_sections(rows):
    out, cur = {}, None
    for r in rows:
        h = norm_head(r["text"])
        letters = re.sub(r"[^A-Za-z]", "", r["text"])
        if h and len(r["text"]) < 30 and letters.isupper():  # headings are set in capitals
            cur = h
            out.setdefault(cur, [])
            continue
        if cur:
            out[cur].append(r)
    return out


def cell_split(row, gap=18):
    """Split a line into cells wherever words are far apart."""
    cells, cur, last = [], [], None
    for w in row["words"]:
        if last is not None and w["x0"] - last > gap:
            cells.append(" ".join(x["text"] for x in cur)); cur = []
        cur.append(w); last = w["x1"]
    if cur:
        cells.append(" ".join(x["text"] for x in cur))
    return cells


def paragraphs(rows):
    return re.sub(r"\s+", " ", " ".join(r["text"] for r in rows)).strip()


def bullets(rows):
    """A line opens a new item when its first word is a lone symbol (•, or a Wingdings glyph)."""
    items, cur = [], []
    for r in rows:
        t = r["text"].strip()
        first = r["words"][0]["text"] if r.get("words") else ""
        if len(first) == 1 and not first.isalnum() and first not in "(\"'$#%&":
            if cur: items.append(" ".join(cur))
            cur = [t[1:].strip()]
        elif cur:
            cur.append(t)
    if cur: items.append(" ".join(cur))
    return [re.sub(r"\s+", " ", i).strip() for i in items if i.strip()]


def to_feature(t):
    m = DASHES.split(t, maxsplit=1)
    if len(m) == 2 and len(m[0]) <= 40 and not m[0].endswith("."):
        lead, text = m[0].strip(), m[1].strip()
        return {"lead": lead, "text": text[:1].lower() + text[1:] if text[:2].isupper() is False else text}
    return {"text": t}


def specs_of(rows, review):
    specs, extra = [], []
    for r in rows:
        cells = [c.strip() for c in cell_split(r) if c.strip()]
        if not cells:
            continue
        if cells[0].lower() == "test":
            continue
        # Flags such as "Body Shop Safe - YES" sit in a third column before the table header.
        flags = [c for c in cells if re.search(r"-\s*(YES|NO)\b", c, re.I)]
        cells = [c for c in cells if c not in flags]
        for f in flags:
            k, v = re.split(r"\s*-\s*", f, maxsplit=1)
            extra.append([k.strip(), "", v.strip().capitalize()])
        if len(cells) == 3:
            name, method, result = cells
        elif len(cells) == 2:
            name, method, result = cells[0], "", cells[1]
        elif len(cells) == 1:
            if specs:  # wrapped test name
                specs[-1][0] += " " + cells[0]
            continue
        else:
            review.append(f"Spec row not understood: {' | '.join(cells)}")
            continue
        method = "" if method in ("-", "–", "–") else method.replace("ASTM ", "")
        if result in ("-", "–"):
            result = ""
        specs.append([name, method, result])
    return specs + extra


def packaging_of(rows, review):
    """Rows of "Fill: x   Case Quantity: y   Case Weight: z" (labels vary: Drum Weight, KIT: #...)."""
    out = []
    for r in rows:
        t = r["text"].strip()
        if not t:
            continue
        LABELS = r"(Fill|Case Quantity|Case Qty|Quantity|Case Weight|Drum Weight|Pail Weight|Weight|Kit)"
        parts = re.findall(LABELS + r":\s*(.*?)(?=\s+" + LABELS + r":|$)", t, re.I)
        parts = [(m[0], m[1]) for m in parts]
        kv = {k.strip().lower(): v.strip() for k, v in parts}
        fill = kv.get("fill")
        if fill is None:
            review.append(f"Packaging line not understood: {t}")
            continue
        qty = next((v for k, v in kv.items() if "quantity" in k or k == "qty"), "")
        wt = next((v for k, v in kv.items() if "weight" in k), "")
        other = {k: v for k, v in kv.items() if k != "fill" and "quantity" not in k and "weight" not in k}
        if other:
            review.append("Packaging also says: " + "; ".join(f"{k.title()}: {v}" for k, v in other.items()))
        out.append([fill, qty, wt])
    return out


def ocr_name(pdf_path, cat_top, review, desc=""):
    """OCR the product name: dark letters on the coloured band above the category line."""
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-png", "-r", "300", "-f", "1", "-l", "1", str(pdf_path), f"{d}/p"], check=True)
        img = Image.open(next(pathlib.Path(d).glob("p*.png"))).convert("RGB")
    k = img.height / 792.0
    bottom = int((cat_top or 150) * k) - 6
    x0 = int(img.width * 0.47)
    crop = img.crop((x0, int(40 * k), img.width - int(4 * k), bottom))
    W, H = crop.size
    px = crop.load()
    # Band top: first row where the right edge is coloured (not white).
    top = 0
    for y in range(H):
        r, g, b = px[W - 8, y]
        if min(r, g, b) < 235:
            top = y; break
    crop = crop.crop((int(W * 0.04), top, W, H))
    r_, g_, b_ = crop.split()
    mx = ImageChops.lighter(ImageChops.lighter(r_, g_), b_)
    mn = ImageChops.darker(ImageChops.darker(r_, g_), b_)
    reads = [_ocr_mask(mx.point(lambda v: 0 if v < 95 else 255)),   # dark letters on a light band
             _ocr_mask(mn.point(lambda v: 0 if v > 220 else 255))]  # white letters on a dark band
    def score(t):
        words = re.findall(r"[A-Za-z]{3,}", t)
        hits = sum(1 for w in words if w.lower() in (desc or "").lower())
        junk = len(re.findall(r"\b[A-Za-z]{1,2}\b", t))
        return hits * 3 + len(words) - junk * 2
    return max(reads, key=score)


def _ocr_mask(mask):
    # Drop the dark bar under the band: rows that are mostly dark.
    mw, mh = mask.size
    mp = mask.load()
    keep_h = mh
    for y in range(mh - 1, int(mh * 0.5), -1):
        dark = sum(1 for x in range(0, mw, 4) if mp[x, y] == 0) / (mw / 4)
        if dark > 0.5:
            keep_h = y
        elif keep_h != mh:
            break
    mask = mask.crop((0, 0, mw, max(10, keep_h - 4)))
    txt = subprocess.run(["tesseract", "-", "-", "--psm", "6"], input=_png(mask), capture_output=True).stdout.decode()
    lines = [re.sub(r"[^A-Za-z0-9&.'/+ -]", "", l).strip() for l in txt.splitlines()]
    lines = [l for l in lines if len(re.sub(r"[^A-Za-z0-9]", "", l)) >= 2]
    return " ".join(" ".join(lines).split())


ACRONYMS = {"DOT", "ATF", "AC", "EV", "HEV", "DEF", "DPF", "GDI", "CVT", "HP", "MP", "ULV", "EGR", "PS", "UV", "LV", "MV", "OE", "OEM", "API", "SAE", "VOC", "II", "III", "MOC", "PTFE", "MAX", "XL", "FX", "4X4", "AWD", "R1234YF", "R134A", "PAG", "POE", "XP", "MTF", "APC", "VLR", "TPMS", "PH", "UTV", "ATV"}


def fix_case(name):
    """Title case, keeping acronyms and numbers as they are."""
    out = []
    for w in name.split():
        core = re.sub(r"[^A-Za-z0-9]", "", w).upper()
        if re.fullmatch(r"(?:[A-Za-z]\.){2,}[A-Za-z]?\.?", w):  # A.P.C, V.L.R.
            out.append(w.upper()); continue
        out.append(w.upper() if core in ACRONYMS or re.search(r"\d", w) else w.capitalize() if w.isupper() or w.islower() else w)
    return " ".join(out)


def _png(im):
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def bottle_of(pdf_path, out_png):
    """The bottle: the largest tall (portrait) colour image on page 1.

    The old MP logo is also a masked RGB image but is landscape, so tall-only keeps it out.
    Images without a transparency mask get their white background knocked out.
    """
    with tempfile.TemporaryDirectory() as d:
        lst = subprocess.run(["pdfimages", "-list", "-f", "1", "-l", "1", str(pdf_path)], capture_output=True, text=True).stdout.splitlines()[2:]
        recs = [l.split() for l in lst if l.split()]
        # Where each image is drawn on the page, keyed by its pixel size.
        with pdfplumber.open(pdf_path) as pdf:
            pg = pdf.pages[0]
            placed = {}
            for im in pg.images:
                sw, sh = im.get("srcsize", (0, 0))
                area = (im["x1"] - im["x0"]) * (im["bottom"] - im["top"])
                in_logo_corner = im["top"] < 90 and im["x0"] > pg.width * 0.6
                full_bleed = (im["x1"] - im["x0"]) > pg.width * 0.6
                if not in_logo_corner and not full_bleed:
                    placed[(int(sw), int(sh))] = max(area, placed.get((int(sw), int(sh)), 0))
        best = None
        for i, r in enumerate(recs):
            if r[2] != "image" or r[5] not in ("rgb", "cmyk", "icc"):
                continue
            w, h = int(r[3]), int(r[4])
            area = placed.get((w, h), 0)
            if area < 40 * 72:  # smaller than about 0.55 x 0.75 in on the page: a badge, not the product
                continue
            masked = i + 1 < len(recs) and recs[i + 1][2] == "smask"
            if not best or area > best[1]:
                best = (int(r[1]), area, masked)
        if not best:
            return None
        subprocess.run(["pdfimages", "-png", "-f", "1", "-l", "1", str(pdf_path), f"{d}/i"], check=True)
        n, _, masked = best
        rgb = Image.open(f"{d}/i-{n:03d}.png").convert("RGB")
        if masked:
            mask = Image.open(f"{d}/i-{n + 1:03d}.png").convert("L").resize(rgb.size)
        else:
            mask = _knock_out_white(rgb)
        rgb.putalpha(mask)
        bbox = rgb.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bbox:
            rgb = rgb.crop(bbox)
        rgb.save(out_png)
        return rgb.size


def _knock_out_white(rgb):
    """Alpha mask that removes a near-white background connected to the image edges."""
    from PIL import ImageDraw
    g = rgb.convert("L").point(lambda v: 255 if v > 238 else 0)
    flood = g.copy()
    W, H = flood.size
    for xy in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        if flood.getpixel(xy) == 255:
            ImageDraw.floodfill(flood, xy, 128)
    return flood.point(lambda v: 0 if v == 128 else 255)


def extract(pdf_path, out_dir, img_dir):
    review = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        rows = lines_of(page)
        full = page.extract_text() or ""
    head = next((r["text"] for r in rows[:12] if re.search(r"[-\u2013]\s*#?\s*\d{4}", r["text"])), "")
    m = re.match(r"(.*?)\s*[-\u2013]\s*#?\s*(\d[0-9A-Za-z-]+)", head)
    category = (m.group(1).strip().title() if m else "").replace("&", "&")
    item = m.group(2) if m else pathlib.Path(pdf_path).stem
    if not m:
        review.append("Header line with category and # not found")
    sec = split_sections(rows)
    feats = [to_feature(b) for b in bullets(sec.get("OUTSTANDING FEATURES", []))]
    ratings = bullets(sec.get("PERFORMANCE RATINGS", []))
    desc = paragraphs(sec.get("DESCRIPTION", []))
    appl = paragraphs(sec.get("APPLICATION", []))
    specs = specs_of(sec.get("SPECIFICATIONS", []), review)
    pack = packaging_of(sec.get("PACKAGING", []), review)
    rev_m = re.search(r"Rev\s*0*(\d+)", full)
    old_rev = int(rev_m.group(1)) if rev_m else 0
    cat_word = next((w for r in rows[:8] for w in r["words"] if w["text"].startswith("#")), None)
    name = ocr_name(pdf_path, cat_word["top"] if cat_word else None, review, desc)
    dm = re.search(r"MOC®\s+([A-Z][\w.'™® -]{2,60}?)\s+(?:is|contains|helps|enhances|removes|cleans|was|will|can|provides|keeps|restores|protects|prevents|reduces|works|has|offers|eliminates)\b", desc)
    desc_name = dm.group(1).replace("™", "").replace("®", "").strip() if dm else ""
    if not name:
        name = desc_name
        review.append("Product name not read from the header; taken from the description" if desc_name else "Product name missing")
    elif desc_name and desc_name.lower() != name.lower():
        review.append(f"Name check: header reads \"{name}\", description says \"{desc_name}\"")
    for f in feats:
        t = (f.get("lead", "") + " " + f["text"])
        if re.search(r"\b[a-z]{2,}\b", t) is None:
            pass
    if not feats:
        review.append("No features found")
    if not specs:
        review.append("No specifications found")
    if not pack:
        review.append("No packaging found")
    if ratings:
        review.append("Has a Performance Ratings section: " + "; ".join(ratings))
    img = img_dir / f"{item}.png"
    size = bottle_of(pdf_path, img)
    if not size:
        review.append("No bottle photo found in the PDF")
    elif size[1] < 900:
        review.append(f"Bottle photo is only {size[1]} px tall")
    data = {
        "item": item,
        "name": fix_case(name),
        "category": category or "Automotive Additives & Lubricants",
        "library_section": category or "Products",
        "rev": f"{old_rev + 1}.0" if old_rev else "1.0",
        "issued": "2026",
        "image": f"img/{item}.png" if size else "",
        "features": feats,
        "ratings": ratings,
        "description": desc,
        "specs": specs,
        "application": appl,
        "packaging": pack,
        "source": {"pdf": str(pathlib.Path(pdf_path).name), "old_rev": old_rev},
        "review": review,
    }
    (out_dir / f"{item}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--out", default="drafts")
    ap.add_argument("--img", default="img")
    a = ap.parse_args()
    out, img = pathlib.Path(a.out), pathlib.Path(a.img)
    out.mkdir(parents=True, exist_ok=True); img.mkdir(parents=True, exist_ok=True)
    for p in a.pdfs:
        try:
            d = extract(p, out, img)
            print(f"{d['item']:>8}  {d['name'][:34]:34}  feat {len(d['features'])}  spec {len(d['specs'])}  pack {len(d['packaging'])}  review {len(d['review'])}")
        except Exception as e:
            print(f"FAILED {p}: {e}", file=sys.stderr)
