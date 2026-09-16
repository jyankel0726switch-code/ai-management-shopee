# -*- coding: utf-8 -*-
import sys, os, io, zipfile
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/home/user/ai-management-shopee/.claude/skills/shopee-listing-upload")

import openpyxl
from openpyxl.utils import get_column_letter
from lxml import etree

from pricing_calc import calc_local_price

# NOTE: this is a reference implementation kept from the 2026-09-16 daily run.
# PRODUCTS below is imported from that day's product-data module; for a new
# run, write a new products_<date>.py (same PRODUCTS list shape) and change
# this import accordingly.
from products_2026_09_16 import PRODUCTS

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_DIR = os.path.join(REPO_ROOT, ".claude/skills/shopee-listing-upload/template")
OUT_DIR = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT_DIR, exist_ok=True)

DATE_JST = "2026-09-16"

CHANNEL_COLS = {
    "SG": ["Doorstep Delivery (Overseas)", "Collection Points (Overseas)", "SPX Express Lockers (Overseas)"],
    "MY": ["Doorstep Delivery - Japan", "SPX Express Lockers (Overseas)"],
    "TH": ["International Express - ส่งจากต่างประเทศ (Japan)"],
    "PH": ["Standard International"],
}


def fix_and_load(src_path):
    with zipfile.ZipFile(src_path, 'r') as zin:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name in zin.namelist():
                data = zin.read(name)
                if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
                    data = data.replace(b'bottom_left', b'bottomLeft')
                zout.writestr(name, data)
    buf.seek(0)
    return openpyxl.load_workbook(buf)


def find_channel_col_index(ws, label):
    for col in range(1, ws.max_column + 1):
        if ws.cell(row=3, column=col).value == label:
            return col
    raise ValueError(f"channel column not found: {label}")


def build_country_file(country):
    items = [p for p in PRODUCTS if p['country'] == country]
    src = os.path.join(TEMPLATE_DIR, f"Shopee_mass_upload_template_{country}.xlsx")
    wb = fix_and_load(src)
    ws = wb['Template']
    assert ws.max_row == 6, f"{country}: max_row != 6 before writing ({ws.max_row})"

    channel_cols = [find_channel_col_index(ws, lbl) for lbl in CHANNEL_COLS[country]]

    row_cursor = 7
    for p in items:
        asin = p['asin']
        price = calc_local_price(p['cost_jpy'], country)['price_local']
        ws.cell(row=row_cursor, column=1, value=int(p['category']))          # A Category
        ws.cell(row=row_cursor, column=2, value=p['title'])                  # B Product Name
        ws.cell(row=row_cursor, column=3, value=p['desc'])                   # C Product Description
        # D-H blank (max purchase qty)
        ws.cell(row=row_cursor, column=9, value=asin)                        # I Parent SKU
        # J-O blank (no variations)
        ws.cell(row=row_cursor, column=16, value=price)                      # P Price
        ws.cell(row=row_cursor, column=17, value=10)                         # Q Stock (default 10)
        ws.cell(row=row_cursor, column=18, value=asin)                       # R SKU
        # S,T blank
        # NOTE (2026-09-16 run): used the feature branch (not yet merged to main),
        # so this pointed at that branch instead of /main/ -- switch to /main/ once
        # framed-images/ is merged, per SKILL.md.
        # NOTE (cache lesson): Shopee's mass upload tool appears to cache a fetched
        # cover image by its source URL, so republishing new image content under an
        # already-used filename did not refresh on re-import. Always publish a
        # frame-processed cover image under a NEW filename whenever its content
        # changes (e.g. bump a _v2/_v3 suffix) rather than overwriting the old one.
        cover_url = f"https://raw.githubusercontent.com/jyankel0726switch-code/ai-management-shopee/main/framed-images/{asin}_cover_v2.jpg"
        ws.cell(row=row_cursor, column=21, value=cover_url)                  # U Cover image
        imgs = p['images'][1:]  # remaining go to Item Image 1..7 (V..AB), first was used as cover source
        for i, url in enumerate(imgs[:7]):
            ws.cell(row=row_cursor, column=22 + i, value=url)                # V.. Item Image 1-7
        ws.cell(row=row_cursor, column=30, value=round(p['weight_kg'], 4))   # AD Weight (kg)
        ws.cell(row=row_cursor, column=31, value=p['length'])                # AE Length
        ws.cell(row=row_cursor, column=32, value=p['width'])                 # AF Width
        ws.cell(row=row_cursor, column=33, value=p['height'])                # AG Height
        for c in channel_cols:
            ws.cell(row=row_cursor, column=c, value="On")
        row_cursor += 1

    out_path = os.path.join(OUT_DIR, f"Shopee_upload_{country}_{DATE_JST}.xlsx")
    wb.save(out_path)
    return out_path, items


def convert_inline_to_shared_strings(xlsx_path):
    """Post-process an openpyxl-saved xlsx: convert inlineStr cells to shared strings,
    matching the format of previously-successful Shopee upload files."""
    with zipfile.ZipFile(xlsx_path, 'r') as zin:
        names = zin.namelist()
        contents = {n: zin.read(n) for n in names}

    ns = {
        'm': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
        'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
        'r': 'http://schemas.openxmlformats.org/package/2006/relationships',
    }
    M = ns['m']

    shared = []
    shared_index = {}

    def get_index(text):
        if text not in shared_index:
            shared_index[text] = len(shared)
            shared.append(text)
        return shared_index[text]

    sheet_names = sorted([n for n in contents if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')])
    for sn in sheet_names:
        root = etree.fromstring(contents[sn])
        for c in root.iter(f'{{{M}}}c'):
            if c.get('t') == 'inlineStr':
                is_el = c.find(f'{{{M}}}is')
                if is_el is not None:
                    t_el = is_el.find(f'{{{M}}}t')
                    text = t_el.text if t_el is not None and t_el.text is not None else ""
                    idx = get_index(text)
                    c.remove(is_el)
                    c.set('t', 's')
                    v_el = etree.SubElement(c, f'{{{M}}}v')
                    v_el.text = str(idx)
                else:
                    # empty inlineStr cell with no <is> child: just an empty cell
                    del c.attrib['t']
        contents[sn] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # Build sharedStrings.xml
    sst = etree.Element(f'{{{M}}}sst', nsmap={None: M})
    sst.set('count', str(len(shared)))
    sst.set('uniqueCount', str(len(shared)))
    for text in shared:
        si = etree.SubElement(sst, f'{{{M}}}si')
        t = etree.SubElement(si, f'{{{M}}}t')
        t.text = text
        if text != text.strip() or '\n' in text:
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    contents['xl/sharedStrings.xml'] = etree.tostring(sst, xml_declaration=True, encoding='UTF-8', standalone=True)

    # Register relationship in xl/_rels/workbook.xml.rels
    rels_path = 'xl/_rels/workbook.xml.rels'
    rels_root = etree.fromstring(contents[rels_path])
    R = 'http://schemas.openxmlformats.org/package/2006/relationships'
    existing_ids = [el.get('Id') for el in rels_root]
    n = 1
    while f'rId{n}' in existing_ids:
        n += 1
    new_rel = etree.SubElement(rels_root, f'{{{R}}}Relationship')
    new_rel.set('Id', f'rId{n}')
    new_rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings')
    new_rel.set('Target', 'sharedStrings.xml')
    contents[rels_path] = etree.tostring(rels_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # Register override in [Content_Types].xml
    ct_path = '[Content_Types].xml'
    ct_root = etree.fromstring(contents[ct_path])
    CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
    override = etree.SubElement(ct_root, f'{{{CT}}}Override')
    override.set('PartName', '/xl/sharedStrings.xml')
    override.set('ContentType', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml')
    contents[ct_path] = etree.tostring(ct_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    with zipfile.ZipFile(xlsx_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name in names:
            if name == 'xl/sharedStrings.xml':
                continue
            zout.writestr(name, contents[name])
        zout.writestr('xl/sharedStrings.xml', contents['xl/sharedStrings.xml'])


if __name__ == "__main__":
    results = {}
    for country in ["SG", "PH", "MY", "TH"]:
        path, items = build_country_file(country)
        convert_inline_to_shared_strings(path)
        results[country] = (path, len(items))
        print(f"{country}: {path} ({len(items)} products)")
