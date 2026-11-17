"""One-time import: old compatibility chart PDFs -> charts/<slug>.source.json (verbatim data + text outside the tables).

    python3 tools/charts_extract.py <folder with mm-pdf/>

The source files stay as they are; the edited, branded data lives in charts/<slug>.json.
"""
import json, pathlib, re, sys
import pdfplumber

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = {
    "atf-0411": "ATF-Compatibility-Chart-0411.pdf",
    "atf-0413": "ATF-Compatibility-Chart-0413.pdf",
    "atf-0611": "ATF-Compatibility-Chart-0611.pdf",
    "cvt": "CVT-Compatibilitychart.pdf",
    "dct-dsg": "DCT-DSG-Compatibility-Chart.pdf",
}

def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()

def main(folder):
    folder = pathlib.Path(folder)
    for slug, name in SRC.items():
        rows, outside = [], []
        with pdfplumber.open(folder / "mm-pdf" / name) as pdf:
            meta = pdf.metadata
            for pg in pdf.pages:
                tables = pg.find_tables()
                for t in tables:
                    for r in t.extract():
                        oem, spec = clean(r[0]), clean(r[-1])
                        if oem.upper() == "OEM" or (not oem and not spec):
                            continue
                        if not oem and rows:  # wrapped continuation row
                            rows[-1]["spec"] += ", " + spec
                            continue
                        rows.append({"oem": oem, "spec": spec})
                boxes = [t.bbox for t in tables]
                keep = lambda o: not any(b[0] - 1 <= o["x0"] and o["x1"] <= b[2] + 1 and b[1] - 1 <= o["top"] and o["bottom"] <= b[3] + 1 for b in boxes)
                text = pg.filter(lambda o: o.get("object_type") != "char" or keep(o)).extract_text() or ""
                outside.append(text)
        out = {"slug": slug, "source_file": name, "source_dates": {k: meta.get(k) for k in ("CreationDate", "ModDate")},
               "rows": rows, "text_outside_tables": outside}
        (ROOT / "charts" / f"{slug}.source.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        print(f"{slug}: {len(rows)} rows")

if __name__ == "__main__":
    main(sys.argv[1])
