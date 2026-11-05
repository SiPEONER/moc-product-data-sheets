# MOC Product Data Sheets (MOC-PDS)

Master template and build kit for every MOC Products data sheet. Started 2026-11-05 from the designer's concept (Rev003 layout) with the MOC-BSM-001 brand fixes applied.

## How it works

One layout (`template.html`) plus one data file per product (`products/<item>.json`). `build.py` fills the layout with each data file and writes three files per product to `out/`:

- `MOC-PDS-<item>_<Name>_REV-<x.y>.pdf`: the US Letter sheet to print or send
- `.png`: a preview image
- `.html`: the same sheet as a self-contained web page

```
pip install jinja2 playwright
python3 -m playwright install chromium
python3 build.py          # every product
python3 build.py 01011    # one product
```

The build stops with "Fix before release" when a sheet runs off the page or its description slides under the product photo. Shorten the copy and build again.

After the sheets, the build writes the public library site to `web/`: one card per product (every data file except the master template, `00000`), grouped by `library_section`. Commit `web/` with the sheets; the subdomain's Vercel project deploys that folder as-is (Root Directory `web`, no build command). `NOINDEX` at the top of `build.py` keeps search engines out until launch is approved.

## Adding a product

1. Copy `products/00000.json` (the master template) to `products/<item>.json`.
2. Fill in the fields, following the rules below.
3. Put the bottle render in `img/<item>.png`: a rendered bottle with the current label art, transparent PNG, at least 1,200 px tall. Leave `image` empty to show the placeholder frame.
4. Run `python3 build.py <item>`.

## Fields

| Field | What goes in it |
| --- | --- |
| `item` | Five-digit item number, without the # |
| `name` | Product name, title case (the sheet sets it in capitals) |
| `category` | Top label in the band, e.g. Automotive Additives & Lubricants |
| `library_section` | Group on the library site, e.g. Engine Treatments |
| `rev`, `issued` | Decimal revision (3.0) and year |
| `image` | Path to the photo cutout, or empty |
| `features` | 5 to 7 items. `{ "lead": "...", "text": "..." }` for a bold lead-in, or `{ "text": "..." }` |
| `description` | One paragraph, about 80 words |
| `specs` | Rows of `[test, ASTM method, typical result]`; leave the method empty for N/A; 8 rows at most |
| `application` | One or two sentences |
| `packaging` | Rows of `[label, value]`: Fill, Case Quantity, Case Weight |

## Files

- `assets/fonts/`: Montserrat 400/700/900 (OFL licence included)
- `assets/logos/`: box logo, knockout (used on the sheet) and primary
- `img/`: bottle images. The two current ones are stand-ins cut from the concept PDF (about 390 px wide); they will be replaced by rendered bottles with the label art applied.
- `web/`: the public library site (generated; Vercel deploys this folder)

`out/` (working files) and `site/` (the internal review page) are kept out of git; both live in the build kit in Andy's MOC-BRAND-STYLE-GUIDE folder.

## Template rules

- **Page:** US Letter, one page, 0.7 in side margins. Black band at the top, black footer band.
- **Type:** Montserrat 400, 700 and 900 only. Product name 34 pt Black, uppercase, -0.01em. Caps labels 0.10em. Body 9.25 pt, tracking 0.
- **Color:** #000000 and #FFFFFF only. The bottle render is the one full-color element.
- **Logo:** box logo, knockout, 0.5 in wide, 0.25 in from the top and right edges.
- **Doc number:** `MOC-PDS-<item> // REV x.y` in the footer. Revisions continue the old count (Rev003 = REV 3.0).
- **Sections, in this order:** 01 // Outstanding Features, 02 // Description, 03 // Specifications, 04 // Application, 05 // Packaging.
- **Features:** 5 to 7, nine lines at most. Optional bold lead-in, then `//` and the benefit; one style per sheet. Any number cites its test.
- **Description:** one paragraph, about 80 words. Name the product in full once (MOC® Motor Oil Conditioner).
- **Specifications:** Test, ASTM Method, Typical Results; 8 rows at most; N/A where no method applies.
- **Packaging:** Fill in fl. oz. with mL, matching the label; then Case Quantity and Case Weight.
- **Bottle:** a rendered bottle with the current label art, transparent PNG, at least 1,200 px tall, same camera and lighting on every sheet.
- **Copy:** no em dashes; `//` between parts of a label or address; MOC is a partner, never a vendor.

## Deploy

Push to `main`; Vercel deploys `web/` to https://datasheets.mocproducts.app (Vercel project `moc-product-data-sheets-web`, Root Directory `web`, no build command). The project's `.vercel.app` addresses redirect to the custom domain (`web/vercel.json`). Run `python3 build.py` and commit `web/` together with any product change, so the live site always matches the data files.
