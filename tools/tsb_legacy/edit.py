"""Light brand edit: raw.json -> tsb/<id>.json (same fields as the 2022-2026 bulletins).

Rules mirror the hand edit of the first 16 (Andy, 2026-11-23): same facts, part numbers and
steps; "NEW!!" becomes a tag; stock openers trimmed; contact lines go to the Contact box;
personal names and email addresses are dropped (the department line replaces them).
Per-bulletin fixes live in OVERRIDES (overrides.py).
"""
import json, re, sys, pathlib, shutil
from overrides import PART_DESC, OVERRIDES, DROP_PARAS

sys.path.insert(0, "/home/claude/moc-pds")
import build as _b  # noqa: E402
NAMES = {}
for _f in pathlib.Path("/home/claude/moc-pds/products").glob("*.json"):
    _p = _b.part_numbers(json.loads(_f.read_text()))
    for _n in [_p["item"], _p["pn"]] + [x for x in (_p.get("pack_pn") or []) if x]:
        NAMES.setdefault(_n, _p["name"])
RAW = pathlib.Path(sys.argv[1])
DEST = pathlib.Path(sys.argv[2])
IMG = RAW.parent / "img"

PN = r"(?:Part\s*(?:No\.?|Number|#)|P/N|MOC\s*#|PN|#)\s*:?\s*([0-9]{4,6}[A-Z]{0,2}(?:-[0-9A-Z]+)?)(?![0-9])"

TAGS = [
    (r"^(?:NEW\s+UPDATES?!*|UPDATED?!*)\s*", "Update"),
    (r"^NEW!+\s*|^New!+\s*|^NEW\s+(?=[A-Z])", "New"),
    (r"^(?:IMPROVED!*|Upgrade!*|UPGRADE!*|Modification!*|Modified!*|MODIFIED!*)\s*", "Update"),
    (r"^(?:DISCONTINUED!*)\s*", "Discontinued"),
    (r"^(?:IMPORTANT!*|Important!*|WARNING!*|Warning!*|NOTICE!*|Notice!*|CAUTION!*)\s*", "Notice"),
]

CATS = [
    ("Brake", r"\bbrake|bleeder|power braking"),
    ("Cooling", r"coolant|cooling|radiator|water pump|antifreeze"),
    ("Transmission", r"\batf\b|transmission|trans\b|\bcvt\b|dipstick|6l80|8l90|allison|5r55w|68rfe|\bnag\b"),
    ("Power Steering", r"power.?steering|pwr str"),
    ("HVAC", r"\ba/c\b|arctic blast|hfo1234|r134|evaporator"),
    ("Driveline", r"differential|\bdiff\b|gear oil"),
    ("Engine", r"engine flush|oil adapter|drain plug|oil drain|engine oil"),
    ("Fuel", r"fuel|induction|optimizer|\bgdi\b|\begr\b|throttle|cat tool|cleaner application|\bedr|turbo|catalytic|intake|map sensor|\bs.?tool"),
]

STOCK = [
    r"(?:To (?:meet|accommodate)[^,]*, )?(?:the )?MOC®? (?:Machine and Equipment|Equipment and Machine|Equipment|Machine) (?:Department|department) (?=has |now has )",
    r"To meet the (?:continuing|growing) needs of our customers(?: in servicing [^,]*)?, (?:the )?MOC®? (?:Machine and Equipment|Equipment and Machine|Equipment|Machine) (?:Department|department) has (?:announced the availability of|(?=developed|released|designed|introduced|added|created|made|a new))",
    r"To meet the (?:continuing|growing) needs of our customers(?: in servicing [^,]*)?, MOC has (?=developed|released|designed|introduced|added|created|made|a new)",
    r"In keeping with MOC'?s commitment to finding solutions with you in mind, MOC has (?=developed)",
    r"With MOC'?s commitment to finding solutions with you in mind, MOC has (?=developed)",
    r"(?:The )?MOC®? (?:Machine and Equipment|Equipment and Machine|Equipment|Machine) (?:Department|departmen)t? has (?=developed|released|designed|introduced|added|created|made|modified|updated|changed)",
]


def tidy(s):
    s = s.replace("MOC®", "MOC").replace("MOC ®", "MOC")
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    s = re.sub(r"\(See Figures? [0-9 &and,]+\)\s*", "", s, flags=re.I)
    s = s.replace(" .", ".")
    s = re.sub(r",\s*,", ",", s)
    return s


def stock(s):
    s = re.sub(r"^MOC has (?:announced the availability of|has )\s*", "MOC now offers ", s)
    s = re.sub(r"\s{2,}", " ", s)
    for r in STOCK:
        m = re.match(r, s)
        if m:
            rest = s[m.end():]
            s = "MOC " + rest if rest.startswith(("has ", "now has ")) else "MOC has " + rest
            break
    s = re.sub(r"^MOC has\s+(an?|the)\b(?! new)", r"MOC now offers \1", s) if re.match(r"^MOC has\s+(an?|the)\s+(?!new)[A-Z]", s) else s
    return re.sub(r"\s{2,}", " ", s)


DROP = re.compile(r"^(Please (contact|direct|call|feel free)|For (additional|more) information|for additional information|additional information\.?$|The following (image|images|picture|pictures|figure|figures|illustration)s? |Below (is|are) (the |an )?(illustration|image|picture)|The images? below|See (the )?(image|picture|figure)s? below|This (adapter|tool|kit) is (illustrated|shown) below|The following shows|Figure \d+\s*:?$|Figure \d+ \()", re.I)
PERSONAL = re.compile(r"[A-Za-z0-9._%+-]+@mocproducts\.com|\b(?:Dean Puett|Tiffany Jaciuk|Tiffany)\b")


def caption_parts(cap):
    """Split a raw caption into (part numbers, text)."""
    pns = re.findall(PN, cap, flags=re.I)
    text = re.sub(PN, "", cap, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,;:-")
    text = re.sub(r"\s*\bMOC\s*®?$", "", text).strip(" ,;:-")
    text = re.sub(r"\(\s*\)", "", text).strip()
    return pns, tidy(text)


NOUNS = r"\b(adapter|tool|kit|hose|plug|machine|filter|gauge|valve|assembly|clip|cap|insert|plate|fitting|coupler|manifold|chip|board|bracket|caster|toolbox|lever|spring|o-ring|washer|clamp|regulator|line|chain|depressor|extension|cleaner|fluid|treatment|module|sensor|tank|pump|drive|station|canister|gun|kit|set|strap|screw|tube|nozzle)"


def context_desc(pn, paras):
    for p in paras:
        m = re.search(r"\b(?:the|a|an|new|our|current|existing|original)\s+([A-Za-z0-9/\"'®™.&\- ]{3,45}?)\s*\(\s*(?:MOC\s*)?(?:Part\s*(?:No\.?|#)|P/N)\s*:?\s*" + re.escape(pn) + r"\s*\)", p, re.I)
        if m:
            d = m.group(1).strip()
            d = re.sub(r"^(?:.*\b(?:the|a|an|new|our|current|existing|original)\s+)", "", d, flags=re.I).strip()
            if 2 < len(d) < 60 and re.search(NOUNS + r"s?$", d, re.I):
                return d[0].upper() + d[1:]
        m = re.search(re.escape(pn) + r"\)?\s*(?:is|,)?\s*(?:the|a|an)?\s*([A-Za-z][A-Za-z0-9/\-' ]{3,40})", p)
    return ""


SRCDIR = pathlib.Path(__file__).parent / "src"


def fit_table(rel):
    """Vehicle fit list ("known to fit the following vehicles") from the layout text, read column by column."""
    import subprocess
    txt = subprocess.run(["pdftotext", "-layout", str(SRCDIR / rel), "-"], capture_output=True, text=True).stdout
    lines = [l.replace("\uf0b7", " ").replace("\u2022", " ") for l in txt.splitlines()]
    try:
        i = next(k for k, l in enumerate(lines) if "fit the following" in l)
    except StopIteration:
        return None
    block = []
    for l in lines[i + 1:]:
        if re.search(r"Please contact|All Rights Reserved|shown below|following image|Adapter,|Part No\.", l):
            if block:
                break
            continue
        if l.strip():
            block.append(l)
    if not block:
        return None
    cols = [[], []]
    for l in block:
        parts = [p.strip() for p in re.split(r"\s{3,}", l.strip()) if p.strip()]
        if len(parts) >= 2 and len(l) - len(l.lstrip()) < 20:
            cols[0].append(parts[0]); cols[1].append(" ".join(parts[1:]))
        elif len(l) - len(l.lstrip()) > 30:
            cols[1].append(parts[0])
        else:
            cols[0].append(" ".join(parts))
    rows, has_group = [], False
    for col in cols:
        group = ""
        for item in col:
            item = re.sub(r"^o\s+", "", item)
            if re.search(r"(transmissions?|vehicles)$|^\d{4} thru \d{4}|^[A-Z]{3,}:?$", item):
                group, has_group = item.rstrip(":").title() if item.isupper() else item, True
                continue
            rows.append([group, item])
    if not rows or any("additional information" in r[1] for r in rows):
        return None
    if has_group:
        return {"title": "Known to fit", "head": ["Group", "Vehicle"], "rows": rows}
    return {"title": "Known to fit", "head": ["Vehicle"], "rows": [[r[1]] for r in rows]}


def list_rows(p):
    """A paragraph that is really a parts list: returns [[pn, desc, note]] or None."""
    q = re.sub(r"^(PART\s*#|Part No\.?)\s*(QTY\s*)?DESCRIPTION\s*", "", p.strip(), flags=re.I)
    q = re.sub(r"^.*?PARTS NEEDED[^:]*:\s*Part No\.?\s*QTY\s*Description\s*", "", q, flags=re.I)
    rows = re.findall(r"([0-9]{5}[A-Z]?)\s+(\d{1,2})\s+(.+?)(?=\s[0-9]{5}[A-Z]?\s+\d{1,2}\s|$)", q)
    if len(rows) >= 2:
        return [[a, tidy(c), "Qty " + b] for a, b, c in rows]
    rows = re.findall(r"([A-Za-z][A-Za-z/&\- ]{2,40}?)\s*[-–]\s*Part No\.?\s*([0-9]{5}[A-Z]?)", q)
    if len(rows) >= 3:
        return [[b, tidy(a), ""] for a, b in rows]
    rows = re.findall(r"([0-9]{5}[A-Z]?)\s*[–-]?\s+([A-Z].{3,80}?)(?=\s[0-9]{5}[A-Z]?\s|$)", q)
    if (len(rows) >= 3 or len(rows) == 2 and re.match(r"[0-9]{5}", q)) and sum(len(a) + len(b) for a, b in rows) > 0.7 * len(q):
        return [[a, tidy(b), ""] for a, b in rows]
    return None


def build(x):
    o = OVERRIDES.get(x["id"], {})
    t = dict(id=o.get("id", x["id"]), date=o.get("date", x["date"]), rev="1.0", dept="Machine & Equipment", source=x["source"])
    title = o.get("title_raw", x["title_raw"]).replace("®", "").replace("™", "")
    tag = None
    for r, name in TAGS:
        m = re.match(r, title)
        if m:
            tag, title = name, title[m.end():]
            break
    title = re.sub(r"\s*!+\s*", " ", title).strip()
    title_pns = re.findall(PN, title, flags=re.I)
    title = re.sub(r"\s*" + PN + r"\s*", " ", title, flags=re.I).strip(" -–,")
    title = re.sub(r"^(\d{5})\s+", "", title) if re.match(r"^\d{5}\s+\D", title) else title
    title = re.sub(r"\s+(vs\.?|and|&|#)$", "", title.strip())
    if title.isupper():
        title = title.title()
    t["title"] = o.get("title", re.sub(r"\s{2,}", " ", title).strip())
    t["tag"] = o.get("tag", tag)

    paras = []
    for i, p in enumerate(x["paras"]):
        if i in DROP_PARAS.get(x["id"], []):
            continue
        p = tidy(p)
        if re.fullmatch(r"(TSB )?Vol\.? ?\d+\.? ?No\.? ?\d+|\d{1,2}|[A-Z]|Fig(ure|\.)? ?[A-Z0-9]", p) or re.match(r"^TSB Vol \d+ No \d+ ", p):
            continue
        if not p or DROP.match(p) or PERSONAL.search(p) and len(p) < 220:
            continue
        p = PERSONAL.sub("", p).strip()
        p = re.sub(r"\s*Please (contact|call) the (Machine and Equipment|Equipment|Machine) Department.*$", "", p)
        p = re.sub(r"\s*(The following (image|images|picture|pictures) (show|shows|illustrate)[^.]*\.)", "", p)
        p = re.sub(r"\s*(Below (is|are) (the )?(illustrations?|images?|pictures?)[^.]*\.|[^.]*\b(is|are) (illustrated|shown|pictured) below\.?|\(?(as )?shown (to the right|below|above)\)?)", "", p).strip()
        p = re.sub(r"\s+([.,])", r"\1", p)
        p = re.sub(r"\s*\((?:Shown|shown) (?:Above|above|Below|below)\)", "", p)
        p = re.sub(r"listed on the following pages", "listed in the table below", p)
        p = re.sub(r"\s*See the next page for [^.]*\.", "", p)
        p = re.sub(r"[Tt]he (images|pictures|photos) on the next page", r"The \1", p)
        p = re.sub(r"\s*See pictures below\.?$", "", p)
        p = re.sub(r"^,\s*and (is|are) (now )?available (to|for) purchase\.?$", "", p).strip()
        if re.match(r"^(,|for purchase\.?$|and (is|are) )", p):
            continue
        if p:
            paras.append(stock(p))
    # part-number lines become parts table rows, label fragments are dropped
    listed, keep = [], []
    fit = None if "table" in o else fit_table(x["source"])
    fit_words = set(re.findall(r"[A-Za-z0-9]{3,}", " ".join(" ".join(r) for r in fit["rows"]))) if fit else set()
    for p in paras:
        q = p.lstrip("•- ").strip()
        if fit and re.search(r"fit the following", q) and len(q) < 140:
            continue
        lr = list_rows(q)
        if lr:
            listed += lr; continue
        m3 = re.search(r"(?:Part No\.?\s*)?[0-9]{5}[A-Z]{0,2}\s*[-–]\s*[A-Z]", q)
        if m3 and m3.start() > 20:
            tail = q[m3.start():]
            rows = re.findall(r"(?:Part No\.?\s*)?([0-9]{5}[A-Z]{0,2})\s*[-–]\s*(.+?)(?=\s(?:Part No\.?\s*)?[0-9]{5}[A-Z]{0,2}\s*[-–]\s*[A-Z]|$)", tail)
            if len(rows) >= 2:
                listed += [[a, tidy(b), ""] for a, b in rows]
                q = p = q[:m3.start()].strip()
        if fit_words:
            w = re.findall(r"[A-Za-z0-9]{3,}", q)
            if w and sum(1 for a in w if a in fit_words) >= 0.6 * len(w) and not q.endswith("."):
                continue
        m = re.fullmatch(r"(?:Part\s*No\.?\s*|#)([0-9]{4,6}[A-Z]{0,2})\s*[–-]\s*(.{3,90})", q) or re.fullmatch(r"([0-9]{5,6}[A-Z]{0,2})\s*[–-]\s*(.{3,90})", q) or re.fullmatch(r"(.{3,70}?)\s*[–-]\s*(?:Part\s*No\.?|#)\s*([0-9]{4,6}[A-Z]?)", q)
        if m and re.fullmatch(r"[0-9]{4,6}[A-Z]{0,2}", m.group(1)):
            listed.append([m.group(1), tidy(m.group(2)).rstrip(" ®"), ""]); continue
        if m:
            listed.append([m.group(2), tidy(m.group(1)), ""]); continue
        rows = re.findall(r"(?:^|\s)([0-9]{4,6}[A-Z]?) [–-] (.+?)(?=\s[0-9]{4,6}[A-Z]? [–-] |$)", q)
        if len(rows) >= 2 and q.startswith(rows[0][0]):
            listed += [[a, tidy(b), ""] for a, b in rows]; continue
        m = re.fullmatch(r"(\d{1,2})\s+([0-9]{4,6}[A-Z]?)\s+(.{3,90})", q)
        if m:
            listed.append([m.group(2), tidy(m.group(3)), "Qty " + m.group(1)]); continue
        if re.fullmatch(r"QTY Part No\.? Description", q, re.I) or re.fullmatch(r"[0-9 ]{4,}", q):
            continue
        if p.startswith("•"):
            keep.append(p); continue
        if len(q) < 32 and not re.search(r"[.:!?]$", q) and not re.match(r"(Step|Note|NOTE)", q):
            continue  # labels lifted from diagrams
        INTRO = r"following parts|listed below|Ordering Information|part numbers for|options are|options available|kit includes|kit will include|following (configurations|adapters|items)|features (of|are)|key features|here are|following configurations"
        if q.endswith(":") and re.search(INTRO, q, re.I):
            sents = re.split(r"(?<=[.!?])\s+", q)
            if len(sents) == 1 or len(q) < 60:
                continue  # introduces the list that is now the part numbers table
            q = p = " ".join(sents[:-1])
        m2 = re.match(r"^(.*?(?:now available|available)[.:])\s+([0-9]{5}.*)$", q)
        if m2 and list_rows(m2.group(2)):
            listed += list_rows(m2.group(2)); q = p = m2.group(1)
            if re.search(INTRO, q, re.I) and len(q) < 90:
                continue
        if len(q) < 130 and not re.search(r"[.!?:)]$", q) and (re.search(PN, q, flags=re.I) or len(q) < 80):
            continue  # labels and part numbers lifted from diagrams
        if re.match(r"^- \S", p) and p.count(" - ") + p.count("; -") >= 1:
            keep += ["• " + x.strip(" ;.") for x in re.split(r";?\s*-\s(?=[A-Z0-9])", p) if x.strip(" ;-")]
            continue
        keep.append(p)
    paras = keep
    # lists: bullets become a list, numbered lines become steps
    steps, bullets, body = [], [], []
    for p in paras:
        if p.startswith("•"):
            bullets.append(p.lstrip("• ").strip())
        elif re.match(r"^\d+[.)]\s+", p):
            steps.append(re.sub(r"^\d+[.)]\s+", "", p))
        else:
            body.append(p)
    apps = [b for b in bullets if re.match(r"(19|20)\d\d\s*[-–]", b) or re.search(r"\((19|20)\d\d", b)]
    if len(apps) >= 2 and "table" not in o and not fit:
        fit = {"title": "Applications", "head": ["Vehicle"], "rows": [[a] for a in apps]}
        bullets = [b for b in bullets if b not in apps]
    lead = o.get("lead") or (body.pop(0) if body else (bullets.pop(0) if bullets else ""))
    for r, _ in TAGS:
        lead = re.sub(r, "", lead)
    t["lead"] = tidy(lead)
    t["body"] = [tidy(b) for b in o.get("body", body)]
    steps = o.get("steps", steps)
    bullets = o.get("benefits", bullets)
    if steps:
        t["steps"] = steps
    if bullets:
        t["benefits"] = bullets
    if o.get("note"):
        t["note"] = o["note"]

    figures, parts, seen = [], [], set()
    for row in listed:
        if row[0] not in seen:
            parts.append(row); seen.add(row[0])
    for n, f in enumerate(x["figures"]):
        if n in o.get("drop_figs", []):
            continue
        raw_cap = f.get("caption_raw", "")
        if re.search(r"additional information|244-6621|fit the following", raw_cap):
            raw_cap = ""
        if len(raw_cap) > 140:  # running text that sat beside a picture
            if "body" not in o:
                t["body"].append(stock(tidy(PERSONAL.sub("", raw_cap))))
            raw_cap = ""
        lr = list_rows(raw_cap) if re.match(r"[0-9]{5}", raw_cap) else None
        if lr:
            for row in lr:
                if row[0] not in seen:
                    parts.append(row); seen.add(row[0])
            raw_cap = ""
        pns, cap = caption_parts(raw_cap)
        if len(pns) > 1 and len(cap) < 4:
            cap = ""
        cap = o.get("captions", {}).get(n, cap)
        fig = dict(img=f["img"], caption=cap or "")
        if pns and len(pns) == 1:
            fig["pn"] = pns[0]
        elif pns and n not in o.get("captions", {}):
            fig["caption"] = (cap + " " if cap else "") + "(" + ", ".join(pns) + ")"
        figures.append(fig)
        if len(pns) > 1 and cap:
            pieces = [x.strip(" ,") for x in re.split(r"(?=\b(?:Adapter|Tool|Plug|Kit|Hose|Assembly|Assy|Extension|Valve|Machine|Clip|Coupler|Insert|Cap|Filter)\s*,)", cap, flags=re.I) if x.strip(" ,")]
            if len(pieces) == len(pns):
                for a, b in zip(pns, pieces):
                    if a not in seen:
                        parts.append([a, b, ""]); seen.add(a)
        if len(pns) == 1 and pns[0] not in seen and cap and len(cap) < 90:
            parts.append([pns[0], cap, ""])
            seen.add(pns[0])
    all_text = " ".join([t["lead"]] + t["body"] + t.get("steps", []) + t.get("benefits", []))
    for pn in re.findall(PN, all_text, flags=re.I) + title_pns:
        if pn not in seen:
            parts.append([pn, NAMES.get(pn) or NAMES.get(pn[:4]) or context_desc(pn, [all_text]) or "", ""])
            seen.add(pn)
    t["figures"] = figures
    if x.get("attachments") and not o.get("drop_attachments"):
        t["attachments"] = [dict(img=a["img"], caption=f"Original attachment, page {a['page']}") for a in x["attachments"]]
    if "table" in o:
        t["table"] = o["table"]
    elif fit:
        t["table"] = fit
    for row in parts:
        if not row[1]:
            row[1] = NAMES.get(row[0]) or NAMES.get(row[0][:4]) or ""
    t["parts"] = o.get("parts", parts)
    pn = o.get("pn")
    if pn is None:
        pn = title_pns or re.findall(PN, t["lead"], flags=re.I)[:2] or [f["pn"] for f in figures if f.get("pn")][:1] or [p[0] for p in parts][:1]
    t["pn"] = pn[:3]
    if "category" in o:
        t["category"] = o["category"]
    else:
        hay = (t["title"] + " " + t["lead"]).lower()
        t["category"] = next((c for c, r in CATS if re.search(r, t["title"].lower())), None) or next((c for c, r in CATS if re.search(r, hay)), "Equipment")
    for k in ("volno", "supersedes", "superseded_by", "upgrade"):
        if k in o:
            t[k] = o[k]
    return t


def main():
    raw = json.loads(RAW.read_text())
    (DEST / "img").mkdir(parents=True, exist_ok=True)
    built = [build(x) for x in raw if not (x["id"] in OVERRIDES and OVERRIDES[x["id"]].get("skip"))]
    known = {}
    for t in built:  # part descriptions known from any bulletin (captions first)
        for pn, d, _ in t["parts"]:
            if d and pn not in known and len(d) < 70 and not re.search(r"^(older|old|larger|kit|complete kit|pack of 5|adapter)$", d, re.I):
                known[pn] = d
    for t in built:
        for row in t["parts"]:
            if not row[1] and row[0] in known:
                row[1] = known[row[0]]
            if not row[1]:
                row[1] = PART_DESC.get(t["id"], {}).get(row[0], "")
    for t, x in zip(built, [x for x in raw if not (x["id"] in OVERRIDES and OVERRIDES[x["id"]].get("skip"))]):
        for f in t["figures"] + t.get("attachments", []):
            new = f["img"].replace(x["id"] + "-", t["id"] + "-", 1)
            shutil.copy2(IMG / f["img"], DEST / "img" / new)
            f["img"] = new
        (DEST / f"{t['id']}.json").write_text(json.dumps(t, indent=1, ensure_ascii=False) + "\n")
    print(len(raw))


if __name__ == "__main__":
    main()
