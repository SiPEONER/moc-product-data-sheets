"""Promote ad drafts (drafts_ad/*.json, from extract_ad.py) into products/*.json.

    python3 tools/promote_ad.py            # writes products, prints a report
    python3 tools/promote_ad.py --dry      # report only

Each ad is matched to its product data sheet by item family (first four digits,
then the full SKU) and checked by name; an ad for a product with no data sheet
becomes an ad-only product file ("pds": false). Service menus and programs are
set aside: they are not single-product ads and need their own layout.
When one product has several old ads, the newest (by the date in the file name) wins.
"""
import argparse, collections, json, pathlib, re, shutil, sys
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from promote import SPELLING, section_for, tidy, name_case  # same rules as the data sheets

ROOT = pathlib.Path(__file__).resolve().parent.parent
DRAFTS, PRODUCTS, IMG = ROOT / "drafts_ad", ROOT / "products", ROOT / "img"

# Old AD Sheets folders that hold service menus, kits sold as a service, or programs.
SET_ASIDE = {
    "AC Evacuation and Recharge", "AC Services", "Battery Service Ad Sht", "Brake Service AD Sheet",
    "CVT Service Kit", "Cooling System AD Sht", "Diesel EGR Service", "Diesel Fuel Service",
    "Drive Line AD Sht", "EV Brake Service", "EV Services", "Emission Control Service",
    "Engine Flush Service", "Enhanced Engine Cleaning", "Fuel System Service", "GDI Fuel Service",
    "Internal Engine Cleaning Service", "MP HEV ad sheet", "ODOR-B-GONE ad sheet", "OPTIMIZER Ad Sht",
    "Oil Consumption Service", "Power Steering Service", "Transmission Service", "Turbo Clean",
    "Vent Sys Serv Ad Sht", "Diesel Exhaust Fluid (DEF)", "N2NOW Ad Sheet", "Fuel System Treatment -kit 02421",
    "Wonder Wafers",  # partner product with a scents list and no MOC item number: needs the item and its own layout
}
# Section by hand where the item-number range misleads.
AD_SECTIONS = {"62941": "Glass Care", "1810": "Cleaners & Degreasers"}
# Older layouts superseded by a newer ad for the same product (kept out of the batch).
SUPERSEDED = {"Octane Booster": "Thrust (04491) is the current ad for this product"}

# Ads that print no item number, matched by hand to the data sheet (2026-11-05).
ITEM_BY_FOLDER = {
    "MP 2- Step": None,  # per file below
    "MP Armour": "2116", "MP Cling": "4290", "MP Nzyme": "4151", "MP Reflection": "2190", "MP Surface": "2108",
    "E-shield": "0107", "EV Protect - EV Cooling": "0444", "Enhance": "0432", "Resolv - Adhesive Remover": "4108",
    "CAT Convertor 02 Sensor Cleaner": "0437", "Quiet Brakes": "0140", "Restore-10oz": "0433",
    "Asian Red-Pink Coolant": "04513", "Banana Wax": "2170", "CVT Service Kit": "0418",
    "Wash n Wax": "6276", "Tri-Foam": "63005", "Wonder Wafers": "", "Glass Cleaner": "10071",
    "Floor Powder": "43552", "Raincoat": "62951", "MP Vision": "62941", "Octane Booster": "", "MP NANO Aerosol": "10961",
}
ITEM_BY_FILE = {"Correction-AD-01.21.26": "3180", "Perfection-AD-01.21.26": "2180"}

# Ad-only product names, set by hand (the old ads mix case and add sizes).
AD_NAMES = {
    "70367": "Premium Copper Grease", "43552": "Floor Powder", "10071": "Foaming Glass Cleaner",
    "69773": "Green Stuff Hand Cleaner", "10961": "Nano Spray Wax Aerosol", "51502": "Refresh Trim Restorer",
    "69663": "Touch of Orange Hand Cleaner", "63005": "Tri-Foam Shampoo & Drying Agent", "1810": "Trueco Interior",
    "62941": "Vision Enhancement Kit", "01581": "Brake System Silicone", "10507": "Fresh A/C",
    "WONDER": "Wonder Wafers", "06021": "Ultra DOT 5.1 Brake Fluid", "62951": "Vision Glass Treatment",
}

# Spelling on the old ads, on top of the data sheet list (logged when applied).
AD_SPELLING = [("Corroision", "Corrosion"), ("power power", "power"), ("Treatement", "Treatment"), ("uphlstery", "upholstery"),
               ("All-in- One", "All-in-One"), ("DIRECTIONS :", "Directions:"), ("dirt.EPA", "dirt. EPA")]

# Read by hand from the old ad artwork where the text layer is broken (2026-11-05).
HAND = {
    "0160": {"headline": "Rodent Deterrent"},
    "4108": {"headline": "Low VOCs"},
    "1049": {"description": ("His heavy-duty", "This heavy-duty")},
    # The last two bullets sit under "PLEASE NOTE:" on the old ad: they are fine print, not benefits.
    "0449": {"footnotes": lambda ad: ad["benefits"][5:], "benefits": lambda ad: ad["benefits"][:5]},
}


def sort_paragraphs(ad, review):
    """Sizes, variants and part numbers set as a paragraph become the call-out; directions stay on the data sheet."""
    keep = []
    for para in ad["description"].split("\n\n"):
        short = len(para) < 70 and para.count(".") <= 2
        if short and re.search(r"gal\b|GAL|#\d|TRI-FOAM|Available in|Part #", para) and not ad.get("callout"):
            c = re.sub(r"\s*(?:\||\s/\s|/)\s*", " // ", para.rstrip("."))
            c = re.sub(r"\s+-\s+", " ", c)
            c = re.sub(r"(TRI-FOAM \w+) (?=TRI-FOAM)", r"\1 // ", c)
            ad["callout"] = c
            review.append(f"Moved to the call-out: {para}")
        elif para.lower().startswith("directions"):
            review.append("Directions left off the ad (" + str(len(para)) + " characters): they belong on the data sheet")
        else:
            keep.append(para)
    ad["description"] = "\n\n".join(keep)

DATE = re.compile(r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{2,4})|(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)")


def date_of(name):
    """Sort key from the date in an old file name (07.21.25, 4-26-26, 060721); 0 when none."""
    best = 0
    for m in DATE.finditer(name):
        mo, dd, yy = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), m.group(5), m.group(6))
        mo, dd, yy = int(mo), int(dd), int(yy[-2:])
        if 1 <= mo <= 12 and 1 <= dd <= 31:
            best = max(best, yy * 10000 + mo * 100 + dd)
    return best


def words(s):
    s = s.lower().replace("&", " ").replace("/", " ")
    return {w for w in re.findall(r"[a-z0-9]+", s) if len(w) > 1 and w not in {"moc", "mp", "the", "and", "of", "premium", "ad", "sheet"}}


def similar(a, b):
    A, B = words(a), words(b)
    return len(A & B) / max(1, min(len(A), len(B))) if A and B else 0


def spell_ad(ad):
    made = set()
    def fix(t):
        for x, y in SPELLING + AD_SPELLING:
            if x in t:
                t = t.replace(x, y); made.add(f"{x} -> {y}" if x != "◦" else "◦ -> °")
        return tidy(t)
    for k in ("headline", "description", "benefits_label", "callout"):
        ad[k] = "\n\n".join(fix(p) for p in ad.get(k, "").split("\n\n"))
    # A drop cap reads as its own word: "D esigned" -> "Designed".
    ad["description"] = re.sub(r"(^|\n\n)([B-HJ-Z]) (?=[a-z])", r"\1\2", ad["description"])
    ad["benefits"] = [fix(b) for b in ad["benefits"]]
    # Labels from the old ad's photos ("BEFORE AFTER", "HOSE INCLUDED") caught in a bullet.
    def strip_labels(b):
        c = re.sub(r"\s*\bBEFORE AFTER\b", "", b)
        c = re.sub(r"(?<=[.)])\s+[A-Z]{3,}(?:\s+[A-Z]{3,})+\s*$", "", c)
        if c != b:
            made.add(f"photo label removed from a benefit: {b[len(c.rstrip('.')) - 10:].strip()}")
        return c
    ad["benefits"] = [strip_labels(b) for b in ad["benefits"]]
    ad["footnotes"] = [fix(b) for b in ad.get("footnotes", [])]
    return sorted(made)


def main(dry):
    products = {f.stem: json.loads(f.read_text()) for f in PRODUCTS.glob("*.json") if f.stem != "00000"}
    by_family = collections.defaultdict(list)
    for k, p in products.items():
        by_family[re.sub(r"\D", "", k)[:4]].append(k)
    cats = collections.defaultdict(collections.Counter)
    for p in products.values():
        cats[p.get("library_section")][p.get("category")] += 1

    set_aside, superseded, chosen, unmatched = [], [], {}, []
    for f in sorted(DRAFTS.glob("*.json")):
        d = json.loads(f.read_text())
        src = pathlib.Path(d["source"]["ad_pdf"])
        folder, stem = src.parent.name, src.stem
        if folder in SET_ASIDE:
            set_aside.append((folder, src.name)); continue
        if folder in SUPERSEDED:
            superseded.append((src.name, SUPERSEDED[folder])); continue
        item = ITEM_BY_FILE.get(stem) or ITEM_BY_FOLDER.get(folder) or d["item"]
        if folder == "Wonder Wafers":
            item = "WONDER"
        # The data sheet this ad belongs to: same SKU, else same family with a matching name.
        target = None
        if item in products:
            target = item
        else:
            fam = re.sub(r"\D", "", item)[:4]
            cands = [k for k in by_family.get(fam, []) if similar(products[k]["name"], d["name"]) >= 0.5]
            if len(by_family.get(fam, [])) == 1 and not cands and similar(products[by_family[fam][0]]["name"], d["name"]) >= 0.34:
                cands = by_family[fam]
            target = cands[0] if cands else None
        key = target or item
        if not key:
            unmatched.append(src.name); continue
        d["_key"], d["_target"], d["_date"], d["_item"] = key, target, date_of(src.name), item
        if key in chosen:
            old = chosen[key]
            keep, drop = (d, old) if d["_date"] >= old["_date"] else (old, d)
            superseded.append((pathlib.Path(drop["source"]["ad_pdf"]).name, f"newer ad {pathlib.Path(keep['source']['ad_pdf']).name} used"))
            chosen[key] = keep
        else:
            chosen[key] = d

    attached, ad_only, low_res = [], [], []
    for key, d in sorted(chosen.items()):
        ad = dict(d["ad"])
        review = [r for r in d.get("review", [])]
        fixes = spell_ad(ad)
        sort_paragraphs(ad, review)
        for k, v in HAND.get(key, {}).items():
            ad[k] = ad[k].replace(*v) if isinstance(v, tuple) else v(ad) if callable(v) else v
            review.append(f"Ad {k} set by hand from the old artwork")
        if fixes:
            review.append("Ad spelling corrected: " + "; ".join(fixes))
        ad["source"] = d["source"]["ad_pdf"].split("AD Sheets/")[-1]
        ad["review"] = review
        if d["_target"]:
            p = products[key]
            if p.get("ad") and key in {"0101", "0121"}:
                continue  # approved master ads, rebuilt by hand
            # The ad photo beats a low-res data sheet photo; the data sheet keeps its own.
            src_png = pathlib.Path(d["image"]) if d.get("image") else None
            pds_px = Image.open(ROOT / p["image"]).height if p.get("image") else 0
            if src_png and d["image_px"] >= 900 and d["image_px"] > pds_px * 1.3 and pds_px < 900:
                dest = IMG / f"{key}-ad.png"
                if not dry:
                    shutil.copy2(src_png, dest)
                ad["image"] = f"img/{dest.name}"
            p["ad"] = ad
            attached.append((key, p["name"], d["name"]))
        else:
            item = key if key != "WONDER" else "WONDER"
            name = AD_NAMES.get(item) or name_case(d["name"])
            name = re.sub(r"\s*-\s*#?\d{4,5}.*$|\s*\(\d+\s*LB\.?\)", "", name).strip()
            sec = section_for(item if item[0].isdigit() else "0", "", name)
            sec = AD_SECTIONS.get(item, sec)
            if "hand cleaner" in name.lower():
                sec = "Cleaners & Degreasers"
            img = ""
            if d.get("image"):
                img = f"img/{item}.png"
                if not dry:
                    shutil.copy2(d["image"], IMG / f"{item}.png")
            p = {"item": item if item != "WONDER" else "", "name": name, "pds": False,
                 "category": cats[sec].most_common(1)[0][0] if cats[sec] else "", "library_section": sec,
                 "image": img, "image_px": d.get("image_px", 0), "ad": ad,
                 "source": {"ad_pdf": ad["source"]},
                 "review": ["Ad only: no product data sheet found for this item"] + (["No item number on the old ad: confirm the item"] if item == "WONDER" else [])}
            if item == "WONDER":
                p["item"] = "WONDER"
            products[item] = p
            ad_only.append((item, name, sec))
        if d.get("image_px", 0) < 900:
            low_res.append(key)
        if not dry:
            (PRODUCTS / f"{key}.json").write_text(json.dumps(products[key], indent=2, ensure_ascii=False) + "\n")

    print(f"attached to data sheets: {len(attached)}")
    for k, n, a in attached:
        flag = "" if similar(n, a) >= 0.5 else "   <- check name"
        print(f"  {k:>7}  {n[:36]:36} <= {a[:36]}{flag}")
    print(f"ad only (no data sheet): {len(ad_only)}")
    for k, n, s in ad_only:
        print(f"  {k:>7}  {n:36} [{s}]")
    seen = {fo for fo, _ in set_aside}
    for fo in sorted(SET_ASIDE - seen):
        for pdf in sorted((pathlib.Path("/mnt/user-data/uploads/AD Sheets") / fo).glob("*.pdf")):
            set_aside.append((fo, pdf.name))
    print(f"set aside (service menus, kits, programs): {len(set_aside)}")
    for fo, fn in set_aside:
        print(f"  {fo} // {fn}")
    print(f"superseded: {len(superseded)}")
    for fn, why in superseded:
        print(f"  {fn}: {why}")
    if unmatched:
        print("UNMATCHED:", unmatched)
    print(f"low-res ad photos (<900px): {len(low_res)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    main(ap.parse_args().dry)
