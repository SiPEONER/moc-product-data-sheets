"""Compatibility charts: charts/<slug>.json -> web/charts/<slug>.html (a real page, every spec as text) + a branded PDF.

    python3 tools/charts.py            # build every chart and the charts index
    python3 tools/charts.py atf-0411   # one chart

Pages live at /charts/<slug> (cleanUrls) and PDFs at /charts/pdf/. They sit outside web/pdfs on purpose:
build.py prunes web/pdfs to the data and ad sheets it knows about.
Drafts ("status": "draft") carry a draft bar and stay noindex. A chart becomes indexable only when it is
approved ("status": "approved") AND INDEXABLE_HOST is the live library host (Andy, 2026-11-17: index the
charts on the new library address).
"""
import json, pathlib, re, shutil, sys
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

WEB = ROOT / "web"
OUT = WEB / "charts"
BASE = "https://datasheets.mocproducts.app"   # switch to the library.mocproducts.com address when it is live
INDEXABLE_HOST = False                        # True once BASE is the new library host
EXAMPLES = {"atf-0411": "JWS 3324 or DEXRON-III", "atf-0413": "MERCON LV or DEXRON-VI", "cvt": "NS-2 or SP-CVT1",
            "dct-dsg": "BOT 341 or G 052 182", "coolant": ""}


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")


def spans(values, years):
    out, i = [], 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        v = values[i]
        first, last = years[i], years[j]
        if i == 0 and j == 0:
            rng = first
        elif i == 0:
            rng = f"{first} to {last}"
        elif j == len(values) - 1:
            rng = f"{first.split('-')[0]} and newer"
        else:
            rng = f"{first.split('-')[0]}-{last.split('-')[-1]}"
        cls = {"DEX-COOL": "t-dex", "G05": "t-g05", "G40": "t-g40", "G48": "t-g48", "G30": "t-g30", "N/A": "na"}.get(v, "t-hoat")
        out.append(dict(label=v, n=j - i + 1, cls=cls, years=rng))
        i = j + 1
    return out


def prepare(c, products):
    c = dict(c)
    c["docno"] = "MOC-CHT-" + c["slug"].upper()
    c["pdf"] = f"{c['docno']}_{slugify(c['title'])}_REV-{c['rev']}.pdf"
    c["example"] = EXAMPLES.get(c["slug"], "")
    c["datasheets"] = []
    for i in c["items"]:
        p = products.get(i)
        if p and build.has("pds", p):
            c["datasheets"].append(dict(item=i, file=build.file_base("pds", p)))
    if c["type"] == "list":
        oems = [r["oem"].title() for g in c["groups"] for r in g["rows"]]
        who = f"MOC {', '.join(c['items'])} {c['product']}" if c["items"] else c["product"]
        c["description"] = f"{c['title']} for {who}: the OEM fluid specifications and part numbers it replaces, for " + ", ".join(oems[:8]) + f" and {max(len(oems) - 8, 0)} more makes."
    else:
        c["grid_spans"] = [(region, [(make, spans(v, c["years"])) for make, v in makes.items()]) for region, makes in c["grid"].items()]
        c["makes"] = sum(len(m) for m in c["grid"].values())
        c["description"] = "Coolant compatibility chart: the factory coolant type (OG, DEX-COOL, G05, G30, G40, G48, P-HOAT) for domestic, European and Asian makes by model year."
    return c


def main(only):
    env = Environment(loader=FileSystemLoader(ROOT), autoescape=select_autoescape())
    tpl = env.get_template("chart_template.html")
    products = {json.loads(p.read_text())["item"]: json.loads(p.read_text()) for p in (ROOT / "products").glob("*.json")}
    (OUT / "pdf").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "assets/logos/moc-box-knockout.svg", WEB / "logo-knockout.svg")
    charts = [prepare(json.loads(f.read_text()), products) for f in sorted((ROOT / "charts").glob("*.json")) if not f.name.endswith(".source.json")]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for c in charts:
            if only and c["slug"] not in only:
                continue
            indexable = c["status"] == "approved" and INDEXABLE_HOST
            jsonld = json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": c["title"], "description": c["description"],
                                 "url": f"{BASE}/charts/{c['slug']}", "publisher": {"@type": "Organization", "name": "MOC Products"}})
            html = OUT / f"{c['slug']}.html"
            html.write_text(tpl.render(c=c, base=BASE, indexable=indexable, jsonld=jsonld))
            page.goto(html.as_uri())
            page.wait_for_load_state("networkidle")
            for old in (OUT / "pdf").glob(f"{c['docno']}_*.pdf"):
                old.unlink()
            page.pdf(path=str(OUT / "pdf" / c["pdf"]), prefer_css_page_size=True, print_background=True)
            n = sum(len(g["rows"]) for g in c["groups"]) if c["type"] == "list" else c["makes"]
            print(f"{c['slug']}: {n} rows, {c['status']}, {c['pdf']}")
        browser.close()
    write_index(env, charts)


INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compatibility Charts // MOC Products</title><meta name="description" content="Fluid and coolant compatibility charts for MOC Products: ATF, CVT, DCT/DSG and coolant.">
{% if not indexable %}<meta name="robots" content="noindex, nofollow">{% endif %}<link rel="canonical" href="{{ base }}/charts/">
<meta property="og:title" content="Compatibility Charts // MOC Products"><meta property="og:image" content="{{ base }}/og-logo.png"><meta name="twitter:card" content="summary">
<link rel="icon" href="../icon.svg" type="image/svg+xml"><link rel="stylesheet" href="chart.css"></head><body>
<div class="page"><div class="sheet">
<header class="masthead in"><a class="brand" href="../"><img src="../logo.svg" alt="MOC Products" width="40" height="41"><span class="micro">Product Library</span></a>
<nav class="libs" aria-label="Libraries"><a href="../">Data Sheets</a><a href="../ads">Ad Sheets</a><a href="./" aria-current="page">Compatibility Charts</a><a href="../images/">Product Images</a></nav></header>
{% if drafts %}<p class="draft micro">Drafts // Pending product expert review // Not for distribution</p>{% endif %}
<main><header class="hero in"><p class="micro kicker">Doc no. MOC-CHT // Compatibility charts</p><h1 class="title">Compatibility Charts</h1>
<p class="lead">Find the MOC fluid that matches an OEM specification. Each chart lists the factory fluid specs and part numbers a product replaces.</p></header>
<div class="cards">{% for c in charts %}<a class="card" href="{{ c.slug }}"><span class="micro">{{ c.docno }}{% if c.status == 'draft' %} // Draft{% endif %}</span><span class="cname">{{ c.title }}</span><span class="cprod">{% for i in c['items'] %}{{ i }} {% endfor %}{{ c.product }}</span></a>{% endfor %}</div></main>
<footer class="foot in"><p class="micro micro-reg">MOC Products // 12306 Montague Street // Pacoima, CA 91331-2279 // 800.266.9226</p><p class="micro">MOC-CHT // Rev 1.0</p></footer>
</div></div></body></html>"""


def write_index(env, charts):
    css = re.search(r"<style>(.*?)</style>", (ROOT / "chart_template.html").read_text(), re.S).group(1)
    css = re.sub(r"\{[%#].*?[%#]\}", "", css)
    css += """
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
.card { display: flex; flex-direction: column; gap: 10px; padding: 24px var(--pad) 28px; border-bottom: 1px solid #000000; border-right: 1px solid #000000; color: #000000; text-decoration: none; }
.card:hover { background: #000000; color: #ffffff; }
.cname { font-weight: 900; font-size: 24px; line-height: 1.05; letter-spacing: -0.01em; text-transform: uppercase; }
.cprod { font-size: 15px; }
"""
    (OUT / "chart.css").write_text(css)
    html = env.from_string(INDEX).render(charts=charts, base=BASE, indexable=INDEXABLE_HOST and all(c["status"] == "approved" for c in charts),
                                        drafts=any(c["status"] == "draft" for c in charts))
    (OUT / "index.html").write_text(html)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
