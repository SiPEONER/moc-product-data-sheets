"""Technical Service Bulletins: tsb/<id>.json -> a one-page PDF (tsb_template.html) + a web page and the /tsb/ index.

    python3 tools/tsb.py           # every bulletin and the index
    python3 tools/tsb.py 26-04     # one bulletin (the index is rebuilt too)

Source PDFs: OneDrive "MOC Support - Technical Service Bulletins/<year>/" (Machine & Equipment Department).
Figures in tsb/img/ were cropped from 400 dpi renders of those PDFs, so arrows and labels drawn over the
photos are kept. Copy is a light brand edit of the originals (Andy, 2026-11-23): same facts, part numbers
and steps; "NEW!!" becomes the NEW tag; stock openers trimmed; typos fixed.
Pages live at /tsb/<id> and PDFs at /tsb/pdf/ (outside web/pdfs, which build.py prunes).
"""
import datetime, json, pathlib, re, shutil, sys
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright
from PIL import Image
from markupsafe import Markup

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

SRC = ROOT / "tsb"
WEB = ROOT / "web"
OUT = WEB / "tsb"
BASE = "https://datasheets.mocproducts.app"
INDEXABLE = False   # the whole library is noindex for now


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")


def prepare(t):
    t = dict(t)
    vol, no = t["id"].split("-")
    d = datetime.date.fromisoformat(t["date"])
    t.update(vol=vol, no=no, docno=f"MOC-TSB-{t['id']}", year=d.year,
             date_long=f"{d.strftime('%B')} {d.day}, {d.year}", date_short=f"{d.strftime('%b')} {d.day}, {d.year}")
    t["pdf"] = f"{t['docno']}_{slugify(t['title'])}_REV-{t['rev']}.pdf"
    for k in ("body", "steps", "benefits", "figures", "parts"):
        t.setdefault(k, [])
    return t


def figures(t, inline):
    """Figure list for a template. inline=True embeds images (PDF); False uses web paths."""
    figs, cut = [], None
    for f in t["figures"]:
        path = SRC / "img" / f["img"]
        w, h = Image.open(path).size
        src = build.data_uri(str(path.relative_to(ROOT))) if inline else f"img/{f['img']}"
        item = dict(f, src=src, ar=w / h)
        if f.get("cutout"):
            cut = item
        else:
            figs.append(item)
    total = sum(f["ar"] for f in figs) or 1
    for f in figs:
        f["basis"] = round(100 * f["ar"] / total, 1)
    return figs, cut


def render_pdfs(env, bulletins, only):
    tpl = env.get_template("tsb_template.html")
    fonts = {w: build.data_uri(f"assets/fonts/Montserrat-{w.capitalize()}.woff2") for w in ("regular", "bold", "black")}
    logo = build.data_uri("assets/logos/moc-box-knockout.svg")
    (OUT / "pdf").mkdir(parents=True, exist_ok=True)
    (OUT / "previews").mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "out" / "tsb"
    tmp.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 816, "height": 1056})
        for t in bulletins:
            if only and t["id"] not in only:
                continue
            figs, cut = figures(t, True)
            name_pt = 34 if len(t["title"]) <= 26 else 30
            fit = None
            # Fit to one page: shrink the photo row first, then the running text.
            for scale in (1, 0.95, 0.9, 0.86):
                for fig_h in (3.2, 3.0, 2.8, 2.6, 2.4, 2.2, 2.0, 1.8, 1.6):
                    html = tmp / f"{t['id']}.html"
                    html.write_text(tpl.render(t=t, figs=figs, cut=cut, fonts=fonts, logo=logo, scale=scale, fig_h=fig_h, name_pt=name_pt))
                    page.goto(html.as_uri())
                    page.wait_for_load_state("networkidle")
                    page.evaluate("document.fonts.ready")
                    over = page.evaluate("(() => { const p = document.querySelector('.page').getBoundingClientRect(), f = document.querySelector('.foot').getBoundingClientRect(); return f.bottom - p.bottom; })()")
                    if over <= 0:
                        fit = (scale, fig_h)
                        break
                if fit:
                    break
            if not fit:
                sys.exit(f"{t['id']} does not fit on one page")
            for old in (OUT / "pdf").glob(f"{t['docno']}_*.pdf"):
                old.unlink()
            page.pdf(path=str(OUT / "pdf" / t["pdf"]), width="8.5in", height="11in", print_background=True)
            page.screenshot(path=str(tmp / f"{t['id']}.png"), full_page=False)
            im = Image.open(tmp / f"{t['id']}.png").convert("RGB")
            im.resize((540, round(540 * im.height / im.width)), Image.LANCZOS).save(OUT / "previews" / f"{t['id']}.jpg", quality=86)
            print(f"{t['id']}: scale {fit[0]}, photos {fit[1]} in, {t['pdf']}")
        browser.close()


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{{ t.title }} // {{ t.docno }} // MOC Products</title><meta name="description" content="{{ t.lead }}">
{% if not indexable %}<meta name="robots" content="noindex, nofollow">{% endif %}<link rel="canonical" href="{{ base }}/tsb/{{ t.id }}">
<meta property="og:title" content="{{ t.title }} // MOC Technical Service Bulletin"><meta property="og:description" content="{{ t.lead }}"><meta property="og:image" content="{{ base }}/og-logo.png"><meta name="twitter:card" content="summary">
<link rel="icon" href="../icon.svg" type="image/svg+xml"><link rel="stylesheet" href="tsb.css"></head><body>
<div class="page"><div class="sheet">
{{ masthead }}
<main><header class="hero in"><p class="micro kicker">Doc no. {{ t.docno }} // Vol. {{ t.vol }} No. {{ t.no }} // {{ t.date_short }} // {{ t.category }}</p>
<h1 class="title">{{ t.title }}</h1>
<div class="product">{% if t.tag %}<span class="stamp tagw">{{ t.tag }}</span>{% endif %}{% for n in t.pn %}<span class="stamp">{{ n }}</span>{% endfor %}</div>
<p class="lead">{{ t.lead }}</p>
<div class="actions"><a class="btn btn-solid" href="pdf/{{ t.pdf }}" download>Download PDF</a><a class="btn" href="pdf/{{ t.pdf }}">View PDF</a><a class="btn" href="./">All bulletins</a></div></header>
<div class="facts">
<div class="in"><h2>What's new</h2>{% if t.steps %}<ol>{% for s in t.steps %}<li>{{ s }}</li>{% endfor %}</ol>{% endif %}{% for b in t.body %}<p>{{ b }}</p>{% endfor %}{% if t.upgrade %}<p><b>Upgrade:</b> {{ t.upgrade }}</p>{% endif %}{% if t.note %}<p class="note">{{ t.note }}</p>{% endif %}</div>
<div class="in">{% if t.benefits %}<h2>Key benefits</h2><ul class="plus">{% for b in t.benefits %}<li>{{ b }}</li>{% endfor %}</ul>{% endif %}
<h2{% if t.benefits %} class="gap"{% endif %}>Contact</h2><p>For more information, contact the {{ t.dept }} Department at <a href="tel:+18662446621"><b>866.244.6621</b></a>.</p></div>
</div>
<div class="figs in">{% for f in figs + ([cut] if cut else []) %}<figure><img src="{{ f.src }}" alt="{{ f.caption }}" loading="lazy"><figcaption>{% if f.pn %}<b>{{ f.pn }}</b> {% endif %}{{ f.caption }}</figcaption></figure>{% endfor %}</div>
<div class="in parts"><h2>Part numbers</h2><table><thead><tr><th>Part No.</th><th>Description</th><th>Notes</th></tr></thead><tbody>{% for p, d, n in t.parts %}<tr><td>{{ p }}</td><td>{{ d }}</td><td>{{ n }}</td></tr>{% endfor %}</tbody></table></div>
</main>
{{ footer }}
</div></div></body></html>"""

INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Technical Service Bulletins // MOC Products</title><meta name="description" content="MOC Products Technical Service Bulletins: new adapters, tools and machine upgrades from the Machine & Equipment Department.">
{% if not indexable %}<meta name="robots" content="noindex, nofollow">{% endif %}<link rel="canonical" href="{{ base }}/tsb/">
<meta property="og:title" content="Technical Service Bulletins // MOC Products"><meta property="og:image" content="{{ base }}/og-logo.png"><meta name="twitter:card" content="summary">
<link rel="icon" href="../icon.svg" type="image/svg+xml"><link rel="stylesheet" href="tsb.css"></head><body>
<div class="page"><div class="sheet">
{{ masthead }}
<main><header class="hero in"><p class="micro kicker">Doc no. MOC-TSB // Technical service bulletins // {{ bulletins|length }} bulletins</p><h1 class="title">Technical Service Bulletins</h1>
<p class="lead">New adapters, tools and machine upgrades from the MOC Machine &amp; Equipment Department, newest first. Each bulletin is one page with the part numbers to order.</p>
<form class="search" role="search" onsubmit="return false"><label class="sr-only" for="q">Search bulletins</label><input class="field" id="q" type="search" placeholder="Search by part number, vehicle or tool" autocomplete="off"></form></header>
{% for year, items in years %}<section class="group" data-year><div class="sec-head in"><h2 class="sec-title">{{ year }}</h2><span class="micro">{{ items|length }} {{ "bulletin" if items|length == 1 else "bulletins" }}</span></div>
<div class="cards">{% for t in items %}<a class="card" href="{{ t.id }}" data-search="{{ (t.title ~ ' ' ~ t.category ~ ' ' ~ t.docno ~ ' ' ~ (t.parts|map('first')|join(' ')) ~ ' ' ~ (t.supersedes or [])|join(' ') ~ ' ' ~ t.lead)|lower }}">
<img src="previews/{{ t.id }}.jpg" alt="" width="540" height="699" loading="lazy"><span class="micro">{{ t.docno }} // {{ t.date_short }} // {{ t.category }}</span><span class="cname">{{ t.title }}</span><span class="cprod">{{ t.pn|join(' // ') }}</span></a>{% endfor %}</div></section>{% endfor %}
<p class="empty" id="none" hidden>No bulletin matches that search.</p>
</main>
{{ footer }}
</div></div>
<script>
const q=document.getElementById('q'),cards=[...document.querySelectorAll('.card')],groups=[...document.querySelectorAll('[data-year]')];
q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();let n=0;cards.forEach(c=>{const s=!v||c.dataset.search.includes(v)||c.dataset.search.replace(/[^a-z0-9 ]/g,'').includes(v.replace(/[^a-z0-9 ]/g,''));c.hidden=!s;if(s)n++;});groups.forEach(g=>g.hidden=![...g.querySelectorAll('.card')].some(c=>!c.hidden));document.getElementById('none').hidden=n>0;});
</script></body></html>"""

MAST = """<header class="masthead in"><a class="brand" href="../"><img src="../logo.svg" alt="MOC Products" width="40" height="41"><span class="micro">Resource Library</span></a>
<nav class="libs" aria-label="Libraries"><a href="../">Data Sheets</a><a href="../ads">Ad Sheets</a><a href="./"{cur}>Service Bulletins</a><a href="../images/">Product Images</a></nav></header>"""
FOOT = """<footer class="foot in"><p class="micro micro-reg">MOC Products // Machine &amp; Equipment Department // 866.244.6621</p><p class="micro">MOC-TSB // Rev 1.0</p></footer>"""

EXTRA = """
.product { margin-top: 24px; }
.tagw { background: #ffffff; color: #000000; }
.facts p, .facts li { font-size: 16px; }
.facts ol { margin: 0 0 12px; padding-left: 22px; }
.facts h2.gap { margin-top: 24px; }
.facts a { color: inherit; }
ul.plus { list-style: none; margin: 0; padding: 0; }
ul.plus li { position: relative; padding-left: 20px; margin-bottom: 6px; }
ul.plus li::before { content: "+"; position: absolute; left: 0; font-weight: 900; }
.note { border: 2px dashed #000000; padding: 10px 12px 8px; font-weight: 700; margin-top: 12px; }
.figs { display: flex; flex-wrap: wrap; gap: 24px; padding-top: 32px; padding-bottom: 32px; border-bottom: 2px solid #000000; align-items: flex-end; }
.figs figure { margin: 0; flex: 0 1 auto; max-width: 100%; display: flex; flex-direction: column; }
.figs img { display: block; width: auto; max-width: 100%; height: auto; max-height: 420px; }
.figs figcaption { border-top: 2px solid #000000; margin-top: 10px; padding-top: 8px; font-size: 14px; }
.parts { padding-top: 28px; padding-bottom: 36px; }
.parts h2 { font-weight: 900; font-size: 14px; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 10px; }
.parts table { width: 100%; border-collapse: collapse; font-size: 15px; }
.parts th { text-align: left; font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; border-bottom: 2px solid #000000; padding: 0 12px 8px 0; }
.parts td { border-bottom: 1px solid #000000; padding: 10px 12px 9px 0; vertical-align: top; }
.parts tr:last-child td { border-bottom: 2px solid #000000; }
.parts td:first-child { font-weight: 900; white-space: nowrap; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
.card { display: flex; flex-direction: column; gap: 8px; padding: 20px var(--pad) 26px; border-bottom: 1px solid #000000; border-right: 1px solid #000000; color: #000000; text-decoration: none; }
.card img { width: 100%; height: auto; display: block; outline: 1px solid #000000; margin-bottom: 8px; }
.card:hover { background: #000000; color: #ffffff; }
.cname { font-weight: 900; font-size: 20px; line-height: 1.08; letter-spacing: -0.01em; text-transform: uppercase; }
.cprod { font-size: 14px; font-weight: 700; letter-spacing: 0.06em; }
"""


def write_site(env, bulletins):
    css = re.search(r"<style>(.*?)</style>", (ROOT / "chart_template.html").read_text(), re.S).group(1)
    css = re.sub(r"\{[%#].*?[%#]\}", "", css).replace("../fonts/", "../fonts/")
    (OUT / "tsb.css").write_text(css + EXTRA)
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    for f in (SRC / "img").iterdir():
        shutil.copy2(f, OUT / "img" / f.name)
    page = env.from_string(PAGE)
    for t in bulletins:
        figs, cut = figures(t, False)
        (OUT / f"{t['id']}.html").write_text(page.render(t=t, figs=figs, cut=cut, base=BASE, indexable=INDEXABLE,
                                                          masthead=Markup(MAST.format(cur="")), footer=Markup(FOOT)))
    years = {}
    for t in sorted(bulletins, key=lambda t: t["id"], reverse=True):
        years.setdefault(t["year"], []).append(t)
    (OUT / "index.html").write_text(env.from_string(INDEX).render(bulletins=bulletins, years=list(years.items()), base=BASE, indexable=INDEXABLE,
                                                                  masthead=Markup(MAST.format(cur=' aria-current="page"')), footer=Markup(FOOT)))
    print(f"web/tsb/: {len(bulletins)} bulletins")


def main(only):
    env = Environment(loader=FileSystemLoader(ROOT), autoescape=select_autoescape())
    bulletins = [prepare(json.loads(f.read_text())) for f in sorted(SRC.glob("*.json"))]
    render_pdfs(env, bulletins, only)
    write_site(env, bulletins)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
