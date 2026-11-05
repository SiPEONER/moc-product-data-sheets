"""Promote extracted drafts (drafts/*.json) to product data files (products/*.json).

    python3 tools/promote.py

- Applies hand-checked names (NAMES) where the header artwork could not be read.
- Groups the old sheets' many category labels into library sections (SECTIONS).
- Turns dash separators in running copy into colons; number ranges keep their en dash.
- Keeps an existing product file's "ad" block, and any product listed in KEEP as it is
  (the designer-edited sheets), changing nothing but what is listed.
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DRAFTS, PRODUCTS = ROOT / "drafts", ROOT / "products"

# Read by hand from the header artwork (OCR could not), 2026-11-05.
NAMES = {
    "0136": "A/C Quiet Max",
    "3100": "Magna Buff",
    "5116": "V.L.R Dressing",
    "5118": "V.L.R Concentrate",
    "6272": "W.W Special",
    "3125": "Miracle Clay H.D.",
    "4351": "Formula 3000",
    "4410": "Bug-B-Gone",
    "4108": "Resolv Adhesive Remover",
    "0446": "Shyft Premium ATF Treatment",
    "2430": "Vinyl & Leather Protectant",
    "0650-0651": "Odor-B-Gone",
    "1065": "Odor-B-Gone Fogger",
    "04533P": "Heavy-Duty Antifreeze / Coolant",
    "4736": "Ultra Interior Cleaner",
}

ACRONYMS = {"ATF", "LV", "DCT", "PLP", "RTU", "CVT", "ULV", "DOT", "MTF", "GDI", "EGR", "DPF", "EV", "HEV", "AC", "MAX", "SAE", "HP", "OPM", "VOC", "O2", "APC"}


def name_case(n):
    """Fix OCR casing inside hyphenated words: Atf-lv -> ATF-LV, Multi-vehicle stays."""
    def word(w):
        parts = w.split("-")
        out = []
        for x in parts:
            core = re.sub(r"[^A-Za-z0-9]", "", x).upper()
            out.append(x.upper() if core in ACRONYMS else x)
        return "-".join(out)
    n = " ".join(word(w) for w in n.split())
    return re.sub(r"\s+-\s+-", " -", n)

# Library sections, first match wins (checked against category + name, lower case).
SECTIONS = [
    ("Glass Care", ["glass"]),
    ("Odor Control", ["deodor", "odor", "air freshener", "fogger"]),
    ("Aerosols", ["aerosol"]),
    ("Shampoos & Washes", ["shampoo", "wash", "rinse", "soap"]),
    ("Waxes, Polishes & Compounds", ["wax", "polish", "sealant", "compound", "glaze", "clay", "buff"]),
    ("Dressings & Protectants", ["dressing", "protectant", "protector", "vinyl", "tire"]),
    ("Cleaners & Degreasers", ["clean", "degreas", "solvent", "acid", "remover", "spot"]),
    ("Additives & Fluids", ["additive", "lubricant", "brake fluid", "coolant", "fluid", "treatment", "oil"]),
]

CATEGORY_FIX = {
    "Automotive Additive & Lubricants": "Automotive Additives & Lubricants",
    "Automotive Additives": "Automotive Additives & Lubricants",
    "Aerosol": "Aerosols",
    "Automotive Wax & Sealant": "Automotive Waxes & Sealants",
    "Automotive Cleaners": "Automotive Cleaner",
    "Interior Cleaners": "Interior Cleaner",
    "Dressings": "Automotive Dressing",
}

# Clear misspellings on the old sheets (logged on each product's review list when applied).
# Technical terms, trade names and claims are never changed here.
SPELLING = [
    ("Evaporator Cileaner", "Evaporator Cleaner"), ("Cileaner", "Cleaner"),
    ("Dressiing", "Dressing"), ("drivebility", "drivability"), ("Denisty", "Density"), ("Denisity", "Density"),
    ("componets", "components"), ("compenents", "components"), ("Treatement", "Treatment"),
    ("moise is the", "noise in the"), ("Pertroleum", "Petroleum"), ("dissolveheavy", "dissolve heavy"),
    ("aersol", "aerosol"), ("approximatly", "approximately"), ("facotry", "factory"), ("inplace", "in place"),
    ("matallic", "metallic"), ("Chamios", "Chamois"), ("Biodegradeable", "Biodegradable"),
    ("D`Limonen", "d-Limonene"), ("coolings systems", "cooling systems"), ("SILCONE", "SILICONE"),
    ("ERPB", "ERBP"), ("streakfree", "streak-free"), ("waterbased", "water-based"), ("pressurewash", "pressure wash"),
    ("\u25e6", "\u00b0"),  # ring operator used as a degree sign
]

# Products already rebuilt by hand from the designer's concept: keep their copy and bottle.
KEEP = {"0101", "0121"}


def spell(p):
    """Apply SPELLING to every text field; return the corrections made."""
    made = set()
    def fix(t):
        if not isinstance(t, str):
            return t
        for a, b in SPELLING:
            if a in t:
                t = t.replace(a, b); made.add(f"{a} -> {b}" if a != "\u25e6" else "\u25e6 -> \u00b0")
        return t
    for k in ("name", "description", "application"):
        p[k] = fix(p[k])
    p["features"] = [{k: fix(v) for k, v in f.items()} for f in p["features"]]
    p["specs"] = [[fix(c) for c in r] for r in p["specs"]]
    p["packaging"] = [[fix(c) for c in r] for r in p["packaging"]]
    return sorted(made)


def section_for(item, category, name):
    """Library section from MOC's item-number ranges, which already group the product lines."""
    hay = f"{category} {name}".lower()
    n = item.split("-")[0]
    lead2 = n[:2]
    if "washer" in hay or "windshield" in hay:
        return "Glass Care"
    if n.startswith("0") or n.startswith("16"):
        return "Additives & Fluids"
    if lead2 in ("10", "11"):
        return "Aerosols & Service Chemicals"
    if n[:3] in ("233", "243"):
        return "Dressings & Protectants"
    if lead2 in ("21", "22", "28") or n.startswith("3"):
        return "Waxes, Polishes & Compounds"
    if n.startswith("4"):
        return "Cleaners & Degreasers"
    if n.startswith("5"):
        return "Dressings & Protectants"
    if n.startswith("6"):
        if "glass" in hay or "washer" in hay or "windshield" in hay:
            return "Glass Care"
        if "air freshener" in hay or "odor" in hay:
            return "Odor Control"
        if n.startswith("611"):
            return "Glass Care"
        return "Shampoos & Washes"
    if n.startswith("9"):
        return "Cleaners & Degreasers"
    return "Additives & Fluids"


def ratings_of(raw):
    """["Gloss - 8 Durability - 4"] -> ["Gloss 8", "Durability 4"]."""
    out = []
    for r in raw:
        pairs = re.findall(r"([A-Za-z][A-Za-z /&]*?)\s*[-:\u2013]\s*(\d+(?:\.\d+)?)", r)
        out += [f"{k.strip()} {v}" for k, v in pairs] or [r]
    return out


def tidy(text):
    if not isinstance(text, str):
        return text
    text = text.replace("—", " – ")
    # "Label – text" -> "Label: text"; keep "6 – 8" ranges.
    text = re.sub(r"(?<=[^\d\s])\s+–\s+(?=\D)", ": ", text)
    text = re.sub(r"(?<=\d)\s+–\s+(?=\d)", "–", text)
    text = text.replace(" ,", ",").replace("MOC ®", "MOC®")
    return re.sub(r"\s{2,}", " ", text).strip()


def main():
    n = 0
    for f in sorted(DRAFTS.glob("*.json")):
        d = json.loads(f.read_text())
        item = d["item"]
        out = PRODUCTS / f"{item}.json"
        old = json.loads(out.read_text()) if out.exists() else {}
        if item in KEEP and old:
            continue
        review = list(d.get("review", []))
        d["name"] = name_case(d["name"])
        if item in NAMES:
            d["name"] = NAMES[item]
            review = [r for r in review if not r.startswith("Product name")]
            review.append("Name read by hand from the header artwork")
        cat = CATEGORY_FIX.get(d["category"], d["category"])
        p = {
            "item": item,
            "name": d["name"],
            "category": cat,
            "library_section": section_for(item, cat, d["name"]),
            "rev": d["rev"],
            "issued": "2026",
            "image": d["image"],
            "features": [{k: tidy(v) for k, v in x.items()} for x in d["features"]],
            "ratings": ratings_of(d.get("ratings", [])),
            "description": tidy(d["description"]),
            "specs": [[tidy(c) for c in row] for row in d["specs"]],
            "application": tidy(d["application"]),
            "packaging": d["packaging"],
            "source": d["source"],
            "review": review,
        }
        fixes = spell(p)
        if fixes:
            p["review"].append("Spelling corrected from the old sheet: " + "; ".join(fixes))
        if item == "0602":
            rows = [r for r in p["specs"] if r[0] == "Dry ERBP"]
            if len(rows) == 2 and "186" in rows[1][2]:
                rows[1][0] = "Wet ERBP"
                p["review"].append("Spec label: the old sheet listed Dry ERBP twice; the ~186\u00b0C row is the wet value (matches the features), now Wet ERBP")
        if old.get("ad"):
            p["ad"] = old["ad"]
        out.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n")
        n += 1
    print(f"{n} product files written")


if __name__ == "__main__":
    main()
