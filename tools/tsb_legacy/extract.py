"""Draft tsb/<id>.json + figures from the 2011-2021 bulletin PDFs (Word template era).

Raw pass: header, title, body paragraphs, captions, part numbers, figure crops.
The light brand edit is applied in edit.py so this stays a faithful extraction.
"""
import json, re, sys, glob, pathlib, subprocess, datetime
import pdfplumber
from PIL import Image, ImageChops

SRC = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
(OUT / "img").mkdir(parents=True, exist_ok=True)
(OUT / "raw").mkdir(parents=True, exist_ok=True)
DPI = 300
S = DPI / 72
MONTHS = "January February March April May June July August September October November December".split()

FILE_IDS = {"2014/TSB Vol 14 No 09 - New Technical Service Line Hours.pdf": "14-09", "2014/TSB Vol 14 No 11 - Volvo 3.0L Fuel Adapter.pdf": "14-11",
            "2014/TSB Vol 14 No 08 - 74746 Drain Hose modified.pdf": "14-08", "2014/TSB Vol 14 No 10 - Flat Brake Bleeder Adapter (New) - 98010 Discontinued.pdf": "14-10"}  # two headers misprinted
# Pages from this index on are attachments in the original (Do-It-Right sheets, flyers, adapter tables):
# kept as page images, not re-typeset.
ATTACH = {"2012/TSB  Vol 12 No 09 Important Optimizer Service Procedure Revision.pdf": 1,
          "2013/TSB Vol 13 No 28 - New Transmission Adapter Kits.pdf": 1,
          "2014/TSB Vol 14 No 02 - New Optimizer Tool Caps with Chart.pdf": 1,
          "2018/TSB Vol 18 No 02 - Air Coolant Bulletin FA111317.pdf": 0,
          "2018/TSB Vol 18 No 10 - EDR-3 Machine.pdf": 1,
          "2018/TSB Vol 18 No 11 - EDR-3 Module.pdf": 1,
          "2020/TSB Vol 20. No 01 - GDI Chemicals.pdf": 1,
          "2016/TSB Vol 16 No 01 - Engine Flush Adapter - BMW 2.0L-3.0L (New).pdf": 1}
SKIP = {"2015/TSB Vol 15 No 17 - Smart Tech Engine Flush bulletin.pdf"}  # duplicate of 15-18 (same text, renumbered)
NOTICES = {"2019/MOC_Bulletin_30APR2019.pdf": ("19-EN1", "2019-04-30"), "2019/MOC_Bulletin_01_13MAY2019.pdf": ("19-EN2", "2019-05-13")}


def clean(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("", "•").replace("", "•").replace("•", "•").replace("", "•").replace("", "•")
    return re.sub(r"[ \t]+", " ", s).strip()


def parse_date(text):
    m = re.search(r"(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})", text, re.I)
    if not m:
        return None
    return datetime.date(int(m.group(3)), MONTHS.index(m.group(1).title()) + 1, int(m.group(2))).isoformat()


CACHE = {}


def crop(pdf_path, page_no, bbox, name, cache=CACHE):
    key = (str(pdf_path), page_no)
    if key not in cache:
        out = OUT / "raw" / f"_{page_no}"
        subprocess.run(["pdftoppm", "-r", str(DPI), "-f", str(page_no + 1), "-l", str(page_no + 1), "-png", "-singlefile", str(pdf_path), str(out)], check=True)
        cache[key] = Image.open(str(out) + ".png").convert("RGB")
    im = cache[key]
    x0, y0, x1, y1 = [v * S for v in bbox]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(im.width, x1), min(im.height, y1)
    c = im.crop((int(x0), int(y0), int(x1 + 1), int(y1 + 1)))
    diff = ImageChops.difference(c, Image.new("RGB", c.size, "white")).convert("L").point(lambda v: 255 if v > 14 else 0)
    box = diff.getbbox()
    if box:
        c = c.crop(box)
    if max(c.size) > 1600:
        c.thumbnail((1600, 1600), Image.LANCZOS)
    c.save(OUT / "img" / name, quality=88, optimize=True)
    return c.size


def merge_boxes(boxes, pad=6):
    """Images that touch or overlap become one figure (composites, photo + arrow overlays)."""
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] - pad < b[2] and b[0] - pad < a[2] and a[1] - pad < b[3] and b[1] - pad < a[3]:
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    boxes.pop(j)
                    changed = True
                    break
            if changed:
                break
    return boxes


def extract(rel):
    path = SRC / rel
    pdf = pdfplumber.open(path)
    first = pdf.pages[0]
    all_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    head = first.extract_text() or ""
    if rel in FILE_IDS:
        tid, date = FILE_IDS[rel], parse_date(head)
    elif rel in NOTICES:
        tid, date = NOTICES[rel]
    else:
        m = re.search(r"Vo\.?l?\.?\s*(\d{2})\.?\s*[-–]?\s*No[.\-]?\s*(\d{1,2})", head) or re.search(r"Vo\.?l?\.?\s*(\d{2})\.?\s*[-–]?\s*No[.\-]?\s*(\d{1,2})", rel)
        tid = f"{m.group(1)}-{int(m.group(2)):02d}"
        date = parse_date(head) or parse_date(all_text)
    title_lines, body, captions, figs = [], [], [], []
    fig_n = 0
    attach_from = ATTACH.get(rel, len(pdf.pages))
    attachments = []
    for pno in range(attach_from, len(pdf.pages)):
        name = f"{tid}-a{pno + 1}.jpg"
        out = OUT / "raw" / "_att"
        subprocess.run(["pdftoppm", "-r", "160", "-f", str(pno + 1), "-l", str(pno + 1), "-png", "-singlefile", str(path), str(out)], check=True)
        im = Image.open(str(out) + ".png").convert("RGB")
        box = ImageChops.difference(im, Image.new("RGB", im.size, "white")).convert("L").point(lambda v: 255 if v > 14 else 0).getbbox()
        if box:
            im = im.crop((max(0, box[0] - 16), max(0, box[1] - 16), min(im.width, box[2] + 16), min(im.height, box[3] + 16)))
        im.save(OUT / "img" / name, quality=85, optimize=True)
        attachments.append(dict(img=name, page=pno + 1, w=im.width, h=im.height))
    for pno, pg in enumerate(pdf.pages):
        if pno >= attach_from:
            break
        lines = pg.extract_text_lines(return_chars=True)
        imgs = []
        for im in pg.images:
            b = (im["x0"], im["top"], im["x1"], im["bottom"])
            if b[2] - b[0] < 30 or b[3] - b[1] < 30:
                continue
            if b[1] < 170 and b[0] < 170 and b[2] < 175 and pno == 0:  # logo top left
                continue
            if b[1] < 120 and (b[2] - b[0]) > 400:  # header banner (2019 notices)
                continue
            imgs.append(b)
        boxes = merge_boxes(imgs)
        page_body = []
        for ln in lines:
            t = clean(ln["text"])
            if not t:
                continue
            c = ln["chars"][0]
            size, font, top, x0 = c["size"], c["fontname"], ln["top"], ln["x0"]
            if top > pg.height - 45 or re.search(r"All Rights Reserved|Confidential and Proprietary", t):
                continue  # footer
            if pno == 0 and top < 175 and ("Black" in font or "TECHNICAL SERVICE" in t.upper() or "MOC PRODUCTS" in t.upper() or re.match(r"(TSB )?Vol", t) or parse_date(t) or t.upper() in ("BULLETIN", "TECHNICAL SERVICE", "APRIL 2019", "MAY 2019") or "Machine and Equipment Department" == t):
                continue
            if size >= 19 and not page_body and pno == 0:
                title_lines.append(t)
                continue
            if rel in NOTICES and pno == 0 and not title_lines and size >= 13:
                title_lines.append(t)
                continue
            # caption: a line near a figure and not at the left text margin
            near = None
            for b in boxes:
                if b[1] - 4 <= top <= b[3] + 48 and (x0 > 58 or b[0] > 300) and not (x0 < 58 and b[0] < 60):
                    if x0 >= b[0] - 60 and x0 <= b[2] + 10 or (b[3] <= top <= b[3] + 48):
                        near = b
                        break
            if near is not None and not re.match(r"Please contact", t):
                captions.append(dict(page=pno, box=near, top=top, x0=x0, text=t, bold="Bold" in font))
                continue
            page_body.append(dict(top=top, x0=x0, text=t, size=size, bold="Bold" in font))
        body.extend([dict(l, page=pno) for l in page_body])
        for b in boxes:
            fig_n += 1
            name = f"{tid}-{fig_n}.jpg"
            w, h = crop(path, pno, b, name)
            figs.append(dict(img=name, page=pno, box=b, w=w, h=h))
    # paragraphs from body lines
    paras, cur, last = [], [], None
    for l in body:
        t = l["text"]
        new_para = last is None or l["page"] != last["page"] or l["top"] - last["top"] > 24 or t.startswith("•") or re.match(r"^(\d{1,2}[.)]\s|Step \d|[A-Z][a-z]+:$)", t)
        if new_para and cur:
            paras.append(" ".join(cur))
            cur = []
        cur.append(t)
        last = l
    if cur:
        paras.append(" ".join(cur))
    paras = [re.sub(r"\s+", " ", p.replace("- ", "-") if False else p).strip() for p in paras]
    # attach captions to figures
    for f in figs:
        cs = [c for c in captions if c["page"] == f["page"] and c["box"] == f["box"]]
        cs.sort(key=lambda c: (c["top"], c["x0"]))
        f["caption_raw"] = " ".join(c["text"] for c in cs)
    CACHE.clear()
    pdf.close()
    for f in (OUT / "raw").glob("_*.png"):
        f.unlink()
    title = " ".join(title_lines)
    return dict(id=tid, date=date, title_raw=title, paras=paras, figures=figs, attachments=attachments, source=rel, pages=len(pdf.pages), text=all_text)


def main():
    files = sorted(str(p.relative_to(SRC)) for p in SRC.glob("20*/*.pdf"))
    if len(sys.argv) > 3:
        files = [f for f in files if f in FILE_IDS]
    res = []
    for rel in files:
        if rel in SKIP:
            continue
        try:
            r = extract(rel)
        except Exception as e:  # noqa
            print("FAIL", rel, e)
            continue
        res.append(r)
        print(r["id"], r["date"], len(r["paras"]), "paras", len(r["figures"]), "figs |", r["title_raw"][:60])
    for f in (OUT / "raw").glob("_*.png"):
        f.unlink()
    if len(sys.argv) > 3:
        old = [x for x in json.loads((OUT / "raw.json").read_text()) if x["source"] not in {r["source"] for r in res}]
        res = sorted(old + res, key=lambda x: x["id"])
    (OUT / "raw.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


main()
