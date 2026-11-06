"""Write review/PAS-review.csv: one row per ad sheet, with what needs a product expert's look.

    python3 tools/ad_review.py
"""
import csv, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
rows = []
for f in sorted((ROOT / "products").glob("*.json")):
    p = json.loads(f.read_text())
    a = p.get("ad")
    if not a or p["item"] == "00000":
        continue
    rows.append({
        "Item": p["item"], "Name": p["name"], "Data sheet": "yes" if p.get("pds", True) else "no (ad only)",
        "Section": p.get("library_section", ""), "Claim": a.get("headline", ""),
        "Benefits heading": a.get("benefits_label", ""), "Call-out": a.get("callout", ""),
        "Old ad": a.get("source", "built by hand"),
        "Check": " | ".join(a.get("review", []) + ([r for r in p.get("review", []) if r.startswith("Ad only")] if not p.get("pds", True) else [])),
    })
out = ROOT / "review" / "PAS-review.csv"
out.parent.mkdir(exist_ok=True)
with out.open("w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print(f"{out.relative_to(ROOT)}: {len(rows)} ad sheets, {sum(1 for r in rows if r['Check'])} with notes")
