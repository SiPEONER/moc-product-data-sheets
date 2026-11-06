"""Read an old MOC product ad sheet PDF into an ad draft (JSON).

    python3 tools/extract_ad.py <pdf> [<pdf> ...] --out drafts_ad/ --img img_ad/

Old ad layout (2023-2026): a big headline over a photo (Bebas, 40pt+), a name line
"Boost Fuel Stabilizer - #04421" (about 30pt), a description, a "<X> Benefits:" heading
(about 24pt) and bulleted benefits (Wingdings glyph), then the footer.
Copy is taken as written; anything else on the page is listed for review, not placed.
"""
import argparse, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pdfplumber
from extract_ppd import bottle_of, fix_case  # same bottle picker and name casing as the data sheets


def rows_of(page):
    words = page.extract_words(extra_attrs=["size", "fontname"])
    rows = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if rows and abs(rows[-1]["top"] - w["top"]) < 4 and abs(rows[-1]["size"] - w["size"]) < 8:
            rows[-1]["words"].append(w)
        else:
            rows.append({"top": w["top"], "size": w["size"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
        r["text"] = " ".join(w["text"] for w in r["words"]).strip()
        r["size"] = max(w["size"] for w in r["words"])
        r["x0"] = r["words"][0]["x0"]
    return sorted(rows, key=lambda r: r["top"])


def spaced_text(chars):
    """Text of one line from its characters, reading word breaks from the gaps.
    Letter-spaced headlines ("R E D U C E") defeat a fixed tolerance, so the
    break is a gap well past this line's own letter spacing."""
    lines = []
    for c in sorted((c for c in chars if c["text"].strip() and c.get("upright", True)), key=lambda c: (round(c["top"]), c["x0"])):
        if lines and abs(lines[-1][-1]["top"] - c["top"]) < 6:
            lines[-1].append(c)
        else:
            lines.append([c])
    out = []
    for ln in lines:
        ln.sort(key=lambda c: c["x0"])
        gaps = sorted(b["x0"] - a["x1"] for a, b in zip(ln, ln[1:]))
        med = gaps[len(gaps) // 2] if gaps else 0
        size = max(c["size"] for c in ln)
        word = ln[0]["text"]
        for a, b in zip(ln, ln[1:]):
            word += (" " if b["x0"] - a["x1"] > med + 0.1 * size else "") + b["text"]
        if len(word) > 2:  # stray vertical or shadow letters, one or two per line
            out.append(word)
    return " ".join(out)


def is_footer(t):
    return "MOC PRODUCTS COMPANY" in t.upper() or "mocproducts.com" in t or re.fullmatch(r"©?\d{4}", t)


def extract(pdf_path, img_dir):
    review = []
    with pdfplumber.open(pdf_path) as pdf:
        rows = rows_of(pdf.pages[0])
        chars = pdf.pages[0].chars
    anchor = next((r for r in rows if r["size"] >= 18 and re.search(r"#\s*[-–]?\s*\d{4}|\s[-–]\s*$", r["text"])), None)
    if not anchor:
        # A few ads print no item number: take the 30pt name line under the claim.
        anchor = next((r for r in rows if 26 <= r["size"] <= 34 and r["top"] > 150 and not is_footer(r["text"])), None)
        if anchor:
            review.append("The old ad prints no item number: item matched by name")
    if not anchor:
        return None
    # The name line can be set in several sizes ("PRECISE" 30pt, "#28042" 27pt): gather its whole baseline.
    line = [r for r in rows if abs(r["top"] - anchor["top"]) < 9 and r["size"] >= 14]
    lwords = sorted((w for r in line for w in r["words"]), key=lambda w: w["x0"])
    text = " ".join(w["text"] for w in lwords)
    name_row = dict(anchor, top=max(r["top"] for r in line))
    m = re.match(r"(.*?)\s*[-–]?\s*#?\s*[-–]?\s*(\d{4,5}[A-Za-z]?)\s*x?\s*$", text)
    raw_name, item = (m.group(1), m.group(2)) if m else (text, "")
    item = re.sub(r"[xX]$", "", item)
    line_ids = {id(r) for r in line}
    raw_name = re.sub(r"[™®]", "", raw_name).strip(" -")
    head = [r for r in rows if r["size"] >= 36 and r["top"] < name_row["top"]]
    head_top = max((r["top"] for r in head), default=0)
    headline = spaced_text([c for c in chars if c["size"] >= 36 and c["top"] < name_row["top"] and c["top"] <= head_top + 6])
    headline = re.sub(r"\s*&\s*", " & ", headline)
    headline = re.sub(r"\s+", " ", headline).strip()
    ben_row = next((r for r in rows if r["top"] > name_row["top"] and re.search(r"benefits?\s*:?$", r["text"], re.I) and r["size"] >= 16), None)
    end_desc = ben_row["top"] if ben_row else 9e9
    body = [r for r in rows if name_row["top"] < r["top"] < end_desc and 7.5 <= r["size"] <= 14
            and not is_footer(r["text"]) and id(r) not in line_ids and len(r["text"]) > 1]
    # Paragraphs: a gap over 1.7 lines starts a new one.
    paras, cur, last = [], [], None
    for r in body:
        if last is not None and r["top"] - last > r["size"] * 1.7:
            paras.append(" ".join(cur)); cur = []
        cur.append(r["text"]); last = r["top"]
    if cur:
        paras.append(" ".join(cur))
    paras = [re.sub(r"\s+", " ", p).strip() for p in paras if p.strip()]
    benefits, label, used = [], "Product Benefits", set(id(r) for r in head + body) | line_ids
    if ben_row:
        used.add(id(ben_row))
        label = " ".join(w.capitalize() for w in ben_row["text"].rstrip(":").split())
        cur = None
        for r in [r for r in rows if r["top"] > ben_row["top"]]:
            if is_footer(r["text"]) or r["size"] > 14 or r["size"] < 7.5:
                continue
            first = r["words"][0]["text"]
            if len(first) == 1 and not first.isalnum():
                if cur: benefits.append(cur)
                cur = r["text"][1:].strip(); used.add(id(r))
            elif cur is not None and r["x0"] > r["words"][0]["x0"] - 1 and abs(r["top"] - last_top) < r["size"] * 1.8:
                cur += " " + r["text"]; used.add(id(r))
            else:
                continue
            last_top = r["top"]
        if cur: benefits.append(cur)
    else:
        review.append("No benefits heading found on the old ad")
    benefits = [re.sub(r"\s+", " ", b).strip() for b in benefits]
    # Fine print that qualifies a claim ("*Depending on ...") travels with the ad.
    notes = [r for r in rows if id(r) not in used and r["text"].startswith("*") and r["top"] > name_row["top"]]
    used |= {id(r) for r in notes}
    footnotes = [re.sub(r"\s+", " ", r["text"]).strip() for r in notes]
    other = [r["text"] for r in rows if id(r) not in used and not is_footer(r["text"]) and len(r["text"]) > 2 and r["top"] > 60]
    if other:
        review.append("Other text on the old ad (call-out or part numbers?): " + " | ".join(other[:6]))
    img = img_dir / f"ad-{item or pathlib.Path(pdf_path).stem}.png"
    size = bottle_of(pdf_path, img)
    if not headline:
        review.append("No headline found")
    return {
        "item": item, "name": fix_case(raw_name.upper()) if raw_name.isupper() or raw_name.islower() else raw_name,
        "ad": {"rev": "1.0", "headline": fix_case(headline.upper()) if headline else "", "description": "\n\n".join(paras),
               "benefits_label": label, "benefits": benefits, "callout": "", "footnotes": footnotes},
        "image": str(img) if size else "", "image_px": size[1] if size else 0,
        "source": {"ad_pdf": str(pdf_path)}, "review": review,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--out", default="drafts_ad")
    ap.add_argument("--img", default="img_ad")
    a = ap.parse_args()
    out, img = pathlib.Path(a.out), pathlib.Path(a.img)
    out.mkdir(parents=True, exist_ok=True); img.mkdir(parents=True, exist_ok=True)
    for p in a.pdfs:
        try:
            d = extract(p, img)
            if not d:
                print(f"SKIP (no name line) {p}"); continue
            # One draft per old file: a product can have several old ads (the promote step picks the newest).
            key = f"{d['item']}_{pathlib.Path(p).stem}" if d["item"] else pathlib.Path(p).stem
            (out / f"{key}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
            print(f"{key:>8}  {d['name'][:30]:30} | {d['ad']['headline'][:24]:24} | ben {len(d['ad']['benefits'])} | img {d['image_px']} | rev {len(d['review'])}")
        except Exception as e:
            print(f"FAILED {p}: {e}", file=sys.stderr)
