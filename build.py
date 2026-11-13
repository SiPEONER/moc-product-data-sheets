"""Build MOC Product Data Sheets and Product Ad Sheets from products/*.json.

Each product data file feeds two documents:
  MOC-PDS  Product Data Sheet  (template.html)     the technical sheet
  MOC-PAS  Product Ad Sheet    (ad_template.html)  the sales sheet, from the "ad" block

For each document: a self-contained HTML (fonts, logo and photo inlined),
a US Letter PDF and a PNG preview, all in out/. Then the public site in
web/ (the subdomain deploys that folder): one library per document type,
listing every product except the master template (item 00000).

    python3 build.py            # every product
    python3 build.py 01011      # one product
"""
import base64, datetime, json, mimetypes, pathlib, re, shutil, sys
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
WEB = ROOT / "web"
TEMPLATE_ITEM = "00000"
# Keep search engines out until the site is approved for launch; set to False then.
NOINDEX = True
SCALES = (1, 0.96, 0.92, 0.89, 0.86)
# Product name on the data sheet: two lines at most. Designer measure first, then a wider
# measure (still clear of the bottle), then smaller sizes. (width in, size pt)
NAME_FIT = {cp: [(w, pt) for pt in sizes for w in (5.1, 5.45, 5.8)]
            for cp, sizes in ((False, (34, 30, 27, 24)), (True, (28, 26, 24)))}
# Lines in the name, and how far its text runs into the bottle (photo drawn at its own width).
NAME_LINES = "(() => { const g = document.createRange(); g.selectNodeContents(document.querySelector('.title')); return new Set([...g.getClientRects()].filter(r => r.width > 0).map(r => Math.round(r.top))).size; })()"
NAME_CLEAR = "(() => { const i = document.querySelector('.photo img'); if (!i) return 0; const b = i.getBoundingClientRect(); const g = document.createRange(); g.selectNodeContents(document.querySelector('.title')); let r = -1e9; for (const x of g.getClientRects()) if (x.width > 0 && x.bottom > b.top) r = Math.max(r, x.right - b.left + 14); return r; })()"
CLAIMS = (1, 0.9, 0.81, 0.7, 0.62, 0.55)  # 74pt down to 41pt, for one long word
# Order of the library sections on the site (any other section follows, A to Z).
SECTION_ORDER = ["Additives & Fluids", "Aerosols & Service Chemicals", "Cleaners & Degreasers", "Shampoos & Washes",
                 "Waxes, Polishes & Compounds", "Dressings & Protectants", "Glass Care", "Odor Control"]

# The picture as drawn inside the photo box (object-fit: contain, bottom-aligned), not the box itself.
DRAWN = """(() => { const i = document.querySelector('.photo img'); if (!i || !i.naturalWidth) return null;
  const B = i.getBoundingClientRect(), k = Math.min(B.width / i.naturalWidth, B.height / i.naturalHeight);
  const w = i.naturalWidth * k, h = i.naturalHeight * k;
  return { left: B.left + (B.width - w) / 2, top: B.bottom - h, bottom: B.bottom }; })"""

# Footer must stay on the page and its text inside the side margins.
FOOT_CHECK = """(() => { let worst = 0;
  for (const pg of document.querySelectorAll('.page')) {
    const P = pg.getBoundingClientRect(), f = pg.querySelector('.foot'), r = f.getBoundingClientRect();
    const pad = parseFloat(getComputedStyle(f).paddingRight); let side = 0;
    for (const c of f.querySelectorAll('p')) { const g = document.createRange(); g.selectNodeContents(c);
      side = Math.max(side, g.getBoundingClientRect().right - (r.right - pad)); }
    worst = Math.max(worst, r.bottom - P.bottom, side); }
  return worst; })()"""

DOCS = {
    "pds": dict(
        code="PDS", label="Data Sheets", page="index.html", template="template.html",
        rev=lambda p: p["rev"],
        checks={
            "the product name runs to the band edge": "(() => { const t = document.querySelector('.title').getBoundingClientRect(), b = document.querySelector('.band').getBoundingClientRect(); return t.bottom - (b.bottom - 20); })()",
            "the description runs under the photo": "(() => { const ph = document.querySelector('.photo'); return ph ? ph.getBoundingClientRect().bottom - document.querySelectorAll('.h')[1].getBoundingClientRect().top : -1; })()",
        },
    ),
    "pas": dict(
        code="PAS", label="Ad Sheets", page="ads.html", template="ad_template.html",
        rev=lambda p: p["ad"]["rev"],
        checks={
            # Widest the claim may run before it meets the bottle neck: 5.95 in.
            # Widest the claim may run: 5.95 in, and never into the drawn bottle.
            "the headline runs into the bottle": "(() => { const g = document.createRange(); g.selectNodeContents(document.querySelector('.claim')); const d = DRAWN(); let r = -1e9; for (const b of g.getClientRects()) { r = Math.max(r, b.right - 571); if (d && b.bottom > d.top) r = Math.max(r, b.right - d.left + 8); } return r; })()",
            "the headline runs into the product name": "(() => document.querySelector('.claim').getBoundingClientRect().bottom - document.querySelector('.ident').getBoundingClientRect().top + 12)()",
            # The drawn picture inside its box (object-fit: contain, bottom-aligned), not the box itself.
            "the copy runs into the bottle": "(() => { const d = DRAWN(); if (!d) return 0; const g = document.createRange(); g.selectNodeContents(document.querySelector('.body')); let r = -1e9; for (const x of g.getClientRects()) if (x.bottom > d.top && x.top < d.bottom && x.width > 0) r = Math.max(r, x.right - d.left + 6); return r; })()",
            "the call-out runs into the footer": "(() => { const c = document.querySelector('.callout'); return c ? c.getBoundingClientRect().bottom - document.querySelector('.foot').getBoundingClientRect().top + 12 : 0; })()",
        },
    ),
}



def keep(name, phrases, breaks=None):
    """Product name as HTML: each name_keep phrase held on one line (never broken at its hyphen),
    and a line break forced before each name_break phrase."""
    from markupsafe import Markup, escape
    out = str(escape(name))
    for k in phrases or []:
        out = out.replace(str(escape(k)), f'<span class="nb">{escape(k)}</span>')
    for k in breaks or []:
        out = out.replace(" " + str(escape(k)), "<br>" + str(escape(k)), 1).replace(' <span class="nb">' + str(escape(k)), '<br><span class="nb">' + str(escape(k)), 1)
    return Markup(out)

def data_uri(path):
    path = ROOT / path
    mime = mimetypes.guess_type(path.name)[0] or ("font/woff2" if path.suffix == ".woff2" else "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")


def file_base(kind, p):
    d = DOCS[kind]
    return f"MOC-{d['code']}-{p['item']}_{slug(p.get('file_label') or p['name'])}_REV-{d['rev'](p)}"


STEP = re.compile(r"(?:(?<=\s)|^)\(?(\d{1,2})\s?[.)]+\)?\s+")


def steps(text):
    """Split "1.) Do this. 2.) Then this." into a numbered list; None if it is plain prose."""
    if not text:
        return None
    if text.count("\u2022") >= 2:
        parts = [x.strip() for x in text.split("\u2022")]
        return dict(intro=parts[0], list=[x for x in parts[1:] if x], outro="", bullets=True)
    marks = list(STEP.finditer(text))
    nums = [int(m.group(1)) for m in marks]
    if len(marks) < 2 or nums[:2] != [1, 2]:
        return None
    # Keep only an ascending 1, 2, 3 ... run; anything else stays in the text.
    run, want = [], 1
    for m in marks:
        if int(m.group(1)) == want:
            run.append(m); want += 1
    intro = text[: run[0].start()].strip()
    items = [text[m.end(): (run[i + 1].start() if i + 1 < len(run) else len(text))].strip() for i, m in enumerate(run)]
    return dict(intro=intro, list=[i for i in items if i], outro="")


def has(kind, p):
    """Every product has a data sheet unless it is ad-only ("pds": false); an ad sheet when it has an "ad" block."""
    return p.get("pds", True) if kind == "pds" else bool(p.get("ad"))


def main(only):
    env = Environment(loader=FileSystemLoader(ROOT), autoescape=select_autoescape())
    env.filters["steps"] = steps
    env.filters["keep"] = keep
    fonts = {w: data_uri(f"assets/fonts/Montserrat-{w.capitalize()}.woff2") for w in ("regular", "bold", "black")}
    logo = data_uri("assets/logos/moc-box-knockout.svg")
    OUT.mkdir(exist_ok=True)
    products = sorted((ROOT / "products").glob("*.json"))
    if only:
        products = [p for p in products if p.stem in only]
    failed = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for path in products:
            p = json.loads(path.read_text())
            if p.get("image"):
                p["image"] = data_uri(p["image"])
            if p.get("ad", {}).get("image"):
                p["ad"]["image"] = data_uri(p["ad"]["image"])
            for kind, d in DOCS.items():
                if not has(kind, p):
                    continue
                tpl = env.get_template(d["template"])
                docno = f"MOC-{d['code']}-{p['item']}"
                base = file_base(kind, p)
                ctx = dict(p=p, a=p.get("ad") or {}, docno=docno, fonts=fonts, logo=logo)
                page = browser.new_page(viewport={"width": 816, "height": 1056}, device_scale_factor=2)
                # Step the running text down until the sheet fits; 0.86 keeps body copy at 8pt.
                # Fit order: one page as designed, then smaller text, then full-width application,
                # then the compact header; two pages only when none of those fit.
                if kind == "pds":
                    tries = [(lay, False, False, sc) for lay in ("standard", "wide") for sc in SCALES]
                    tries += [(lay, True, False, sc) for lay in ("standard", "wide") for sc in SCALES]
                    tries += [("two", False, ts, sc) for ts in (False, True) for sc in (1, 0.96, 0.92)]
                    tries = [(lay, compact, ts, sc, 1) for lay, compact, ts, sc in tries]
                else:
                    # Ads: the claim steps down first (74pt to 41pt), then the running text.
                    # Then a narrower text column, for jugs and kits that are wider than a bottle.
                    tries = [("standard", nw, False, sc, c) for nw in (False, True) for sc in SCALES for c in CLAIMS]
                names = {}
                if kind == "pds":
                    for cp in (False, True):
                        for w, pt in NAME_FIT[cp]:
                            ctx.update(scale=1, layout="standard", compact=cp, two_specs=False, claim=1, narrow=False, name_w=w, name_pt=pt)
                            page.set_content(tpl.render(screen=False, **ctx), wait_until="load")
                            page.evaluate("document.fonts.ready")
                            if page.evaluate(NAME_LINES) <= 2 and page.evaluate(NAME_CLEAR) <= 0:
                                break
                        else:
                            w, pt = NAME_FIT[cp][-3]  # smallest size at the designer measure
                        names[cp] = (w, pt)
                for lay, compact, two_specs, scale, claim in tries:
                    narrow = compact if kind == "pas" else False
                    compact = compact if kind == "pds" else False
                    ctx.update(scale=scale, layout=lay, compact=compact, two_specs=two_specs, claim=claim, narrow=narrow)
                    if kind == "pds":
                        ctx.update(name_w=names[compact][0], name_pt=names[compact][1])
                    page.set_content(tpl.render(screen=False, **ctx), wait_until="load")
                    page.evaluate("document.fonts.ready")
                    problems = []
                    for what, js in d["checks"].items():
                        v = page.evaluate(js.replace("DRAWN()", DRAWN + "()"))
                        if v > 0.5:
                            problems.append(f"{what} by {v:.0f}px")
                    v = page.evaluate(FOOT_CHECK)
                    if v > 0.5:
                        problems.append(f"it runs off the page by {v:.0f}px")
                    if not problems:
                        break
                (OUT / f"{base}.html").write_text(tpl.render(screen=True, **ctx))
                page.pdf(path=str(OUT / f"{base}.pdf"), width="8.5in", height="11in", print_background=True, prefer_css_page_size=True)
                page.screenshot(path=str(OUT / f"{base}.png"), clip={"x": 0, "y": 0, "width": 816, "height": 1056})
                page.close()
                fitted = (f" (name {ctx['name_pt']}pt)" if kind == "pds" and ctx.get("name_pt") not in (34, 28) else "") + (" (wide name)" if kind == "pds" and ctx.get("name_w", 5.1) > 5.1 and ctx.get("name_pt") in (34, 28) else "") + (" (narrow column)" if ctx.get("narrow") else "") + (f" (claim at {ctx['claim']:.0%})" if ctx.get("claim", 1) < 1 else "") + {"wide": " (wide application)", "two": " (2 pages)"}.get(ctx["layout"], "") + (" (compact)" if ctx.get("compact") else "") + (f" (text at {ctx['scale']:.0%})" if ctx["scale"] < 1 else "")
                print(f"{base}: " + ("OK" + fitted if not problems else "FAIL: " + "; ".join(problems)))
                if problems:
                    failed.append(base)
        browser.close()
    if failed:
        sys.exit("Fix before release (shorten copy): " + ", ".join(failed))
    build_site(env)


def build_site(env):
    """Write web/: one library page per document type, from every product JSON and its built PDF."""
    from PIL import Image

    for sub in ("pdfs", "previews", "fonts"):
        (WEB / sub).mkdir(parents=True, exist_ok=True)
    products = [json.loads(p.read_text()) for p in sorted((ROOT / "products").glob("*.json"))]
    products = [p for p in products if p["item"] != TEMPLATE_ITEM]
    libraries, keep = [], set()
    for kind, d in DOCS.items():
        sections = {}
        for p in products:
            if not has(kind, p):
                continue
            file = file_base(kind, p)
            pdf, png = OUT / f"{file}.pdf", OUT / f"{file}.png"
            if not pdf.exists():
                sys.exit(f"Missing {pdf.name}: run python3 build.py {p['item']} first")
            shutil.copy2(pdf, WEB / "pdfs" / pdf.name)
            im = Image.open(png).convert("RGB")
            im.resize((720, round(720 * im.height / im.width)), Image.LANCZOS).save(WEB / "previews" / f"{file}.jpg", quality=86)
            keep.add(file)
            sections.setdefault(p.get("library_section", "Products"), []).append(dict(
                item=p["item"], name=p["name"], rev=d["rev"](p), file=file, code=d["code"],
                size=f"{round(pdf.stat().st_size / 1024)} KB"))
        order = lambda t: (SECTION_ORDER.index(t) if t in SECTION_ORDER else len(SECTION_ORDER), t)
        secs = [dict(id=slug(t).lower(), title=t, sheets=sorted(sections[t], key=lambda i: i["item"])) for t in sorted(sections, key=order)]
        libraries.append(dict(kind=kind, code=d["code"], label=d["label"], page=d["page"], sections=secs,
                              total=sum(len(s["sheets"]) for s in secs)))
    # Drop files for documents that no longer exist (renamed or a new revision).
    for sub, ext in (("pdfs", ".pdf"), ("previews", ".jpg")):
        for f in (WEB / sub).glob(f"*{ext}"):
            if f.stem not in keep:
                f.unlink()
    for w in ("Regular", "Bold", "Black"):
        shutil.copy2(ROOT / "assets/fonts" / f"Montserrat-{w}.woff2", WEB / "fonts")
    shutil.copy2(ROOT / "assets/fonts/Montserrat-OFL.txt", WEB / "fonts")
    shutil.copy2(ROOT / "assets/logos/moc-box-primary.svg", WEB / "logo.svg")
    shutil.copy2(ROOT / "assets/logos/icon.svg", WEB / "icon.svg")
    updated = datetime.date.today().strftime("%b %Y")
    tpl = env.get_template("web_template.html")
    for lib in libraries:
        (WEB / lib["page"]).write_text(tpl.render(lib=lib, libraries=libraries, noindex=NOINDEX, updated=updated))
    if NOINDEX:
        (WEB / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    elif (WEB / "robots.txt").exists():
        (WEB / "robots.txt").unlink()
    print("web/: " + ", ".join(f"{l['total']} {l['label'].lower()}" for l in libraries))


if __name__ == "__main__":
    main(set(sys.argv[1:]))
