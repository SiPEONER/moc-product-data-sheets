"""Build MOC Product Data Sheets from products/*.json.

For each product: a self-contained HTML (fonts, logo and photo inlined),
a US Letter PDF and a PNG preview, all in out/. Then the public library
site in web/ (the subdomain deploys that folder), listing every product
except the master template (item 00000).

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


def data_uri(path):
    path = ROOT / path
    mime = mimetypes.guess_type(path.name)[0] or ("font/woff2" if path.suffix == ".woff2" else "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")


def main(only):
    env = Environment(loader=FileSystemLoader(ROOT), autoescape=select_autoescape())
    tpl = env.get_template("template.html")
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
            docno = f"MOC-PDS-{p['item']}"
            base = f"{docno}_{slug(p.get('file_label') or p['name'])}_REV-{p['rev']}"
            ctx = dict(p=p, docno=docno, fonts=fonts, logo=logo)
            html = tpl.render(screen=False, **ctx)
            (OUT / f"{base}.html").write_text(tpl.render(screen=True, **ctx))
            page = browser.new_page(viewport={"width": 816, "height": 1056}, device_scale_factor=2)
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            clash = page.evaluate(
                "(() => { const ph = document.querySelector('.photo').getBoundingClientRect(); const d = document.querySelectorAll('.h')[1].getBoundingClientRect(); return ph.bottom - d.top; })()"
            )
            if clash > 0.5:
                print(f"  FAIL: description runs under the photo by {clash:.1f}px")
                failed.append(path.stem)
            overflow = page.evaluate(
                "(() => { const f = document.querySelector('.foot'); const r = f.getBoundingClientRect(); const pad = parseFloat(getComputedStyle(f).paddingRight); let side = 0; for (const c of f.querySelectorAll('p')) { const range = document.createRange(); range.selectNodeContents(c); side = Math.max(side, range.getBoundingClientRect().right - (r.right - pad)); } return Math.max(r.bottom - 1056, side); })()"
            )
            page.pdf(path=str(OUT / f"{base}.pdf"), width="8.5in", height="11in", print_background=True, prefer_css_page_size=True)
            page.screenshot(path=str(OUT / f"{base}.png"), clip={"x": 0, "y": 0, "width": 816, "height": 1056})
            page.close()
            print(f"{base}: {'OK' if overflow <= 0.5 else f'FAIL: runs off the page by {overflow:.0f}px'}")
            if overflow > 0.5:
                failed.append(path.stem)
        browser.close()
    if failed:
        sys.exit(f"Fix before release (shorten copy): {', '.join(failed)}")
    build_site(env)


def build_site(env):
    """Write web/ from every product JSON and its built PDF."""
    from PIL import Image

    for sub in ("pdfs", "previews", "fonts"):
        (WEB / sub).mkdir(parents=True, exist_ok=True)
    sections = {}
    for path in sorted((ROOT / "products").glob("*.json")):
        p = json.loads(path.read_text())
        if p["item"] == TEMPLATE_ITEM:
            continue
        file = f"MOC-PDS-{p['item']}_{slug(p.get('file_label') or p['name'])}_REV-{p['rev']}"
        pdf, png = OUT / f"{file}.pdf", OUT / f"{file}.png"
        if not pdf.exists():
            sys.exit(f"Missing {pdf.name}: run python3 build.py {p['item']} first")
        shutil.copy2(pdf, WEB / "pdfs" / pdf.name)
        im = Image.open(png).convert("RGB")
        im.resize((720, round(720 * im.height / im.width)), Image.LANCZOS).save(WEB / "previews" / f"{file}.jpg", quality=86)
        title = p.get("library_section", "Products")
        sections.setdefault(title, []).append(dict(item=p["item"], name=p["name"], rev=p["rev"], file=file, size=f"{round(pdf.stat().st_size / 1024)} KB"))
    # Drop files for sheets that no longer exist (renamed or a new revision).
    keep = {i["file"] for items in sections.values() for i in items}
    for sub, ext in (("pdfs", ".pdf"), ("previews", ".jpg")):
        for f in (WEB / sub).glob(f"*{ext}"):
            if f.stem not in keep:
                f.unlink()
    for w in ("Regular", "Bold", "Black"):
        shutil.copy2(ROOT / "assets/fonts" / f"Montserrat-{w}.woff2", WEB / "fonts")
    shutil.copy2(ROOT / "assets/fonts/Montserrat-OFL.txt", WEB / "fonts")
    shutil.copy2(ROOT / "assets/logos/moc-box-primary.svg", WEB / "logo.svg")
    shutil.copy2(ROOT / "assets/logos/icon.svg", WEB / "icon.svg")
    secs = [dict(id=slug(t).lower(), title=t, sheets=sorted(items, key=lambda i: i["item"])) for t, items in sections.items()]
    html = env.get_template("web_template.html").render(
        sections=secs, total=sum(len(s["sheets"]) for s in secs), noindex=NOINDEX,
        updated=datetime.date.today().strftime("%b %Y"),
    )
    (WEB / "index.html").write_text(html)
    if NOINDEX:
        (WEB / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    elif (WEB / "robots.txt").exists():
        (WEB / "robots.txt").unlink()
    print(f"web/: {sum(len(s["sheets"]) for s in secs)} sheets in {len(secs)} section(s)")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
