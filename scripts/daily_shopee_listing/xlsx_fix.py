"""Shopee公式テンプレートのbottom_left非標準値を正規化して開くためのヘルパー"""
import zipfile
import shutil
import re


def load_fixed_copy(src_path: str, tmp_path: str):
    """src_pathをtmp_pathにコピーし、sheetXX.xmlのbottom_leftをbottomLeftに正規化する"""
    shutil.copyfile(src_path, tmp_path)
    _patch_zip_bottom_left(tmp_path)


def _patch_zip_bottom_left(path: str):
    with zipfile.ZipFile(path, 'r') as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}
    changed = False
    for n in names:
        if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'):
            content = data[n]
            if b'bottom_left' in content:
                data[n] = content.replace(b'bottom_left', b'bottomLeft')
                changed = True
    if changed:
        tmp2 = path + '.tmp'
        with zipfile.ZipFile(tmp2, 'w', zipfile.ZIP_DEFLATED) as zout:
            for n in names:
                zout.writestr(n, data[n])
        shutil.move(tmp2, path)


_INLINE_CELL_RE = re.compile(
    rb'<c ([^>]*?)t="inlineStr"([^>]*)><is><t(?:\s+xml:space="preserve")?>(.*?)</t></is></c>',
    re.DOTALL,
)


def convert_to_shared_strings(path: str):
    """openpyxlが書き出すinlineStr形式を、Shopee登録実績ファイルと同じ
    共有文字列(xl/sharedStrings.xml)形式に変換する。"""
    with zipfile.ZipFile(path, 'r') as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}

    shared_strings = []
    shared_index = {}

    def _replace(m):
        attrs_before, attrs_after, text = m.group(1), m.group(2), m.group(3)
        if text not in shared_index:
            shared_index[text] = len(shared_strings)
            shared_strings.append(text)
        idx = shared_index[text]
        attrs = (attrs_before + attrs_after).strip()
        attrs = re.sub(rb'\s+', b' ', attrs).strip()
        prefix = b'<c ' + attrs if attrs else b'<c'
        return prefix + b' t="s"><v>' + str(idx).encode() + b'</v></c>'

    changed = False
    for n in names:
        if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'):
            content = data[n]
            new_content, count = _INLINE_CELL_RE.subn(_replace, content)
            if count:
                data[n] = new_content
                changed = True

    if not changed:
        return

    sst_items = b''.join(
        b'<si><t xml:space="preserve">' + t + b'</t></si>' for t in shared_strings
    )
    sst_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        b'count="' + str(len(shared_strings)).encode() + b'" '
        b'uniqueCount="' + str(len(shared_strings)).encode() + b'">' + sst_items + b'</sst>'
    )
    data['xl/sharedStrings.xml'] = sst_xml
    if 'xl/sharedStrings.xml' not in names:
        names.append('xl/sharedStrings.xml')

    # [Content_Types].xml に登録
    ct = data['[Content_Types].xml']
    if b'sharedStrings.xml' not in ct:
        override = (
            b'<Override PartName="/xl/sharedStrings.xml" '
            b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        )
        ct = ct.replace(b'</Types>', override + b'</Types>')
        data['[Content_Types].xml'] = ct

    # xl/_rels/workbook.xml.rels に関係を登録
    rels = data['xl/_rels/workbook.xml.rels']
    if b'sharedStrings.xml' not in rels:
        existing_ids = [int(x) for x in re.findall(rb'Id="rId(\d+)"', rels)]
        new_id = max(existing_ids, default=0) + 1
        rel = (
            b'<Relationship Id="rId' + str(new_id).encode() + b'" '
            b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
            b'Target="sharedStrings.xml"/>'
        )
        rels = rels.replace(b'</Relationships>', rel + b'</Relationships>')
        data['xl/_rels/workbook.xml.rels'] = rels

    tmp2 = path + '.tmp'
    with zipfile.ZipFile(tmp2, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    shutil.move(tmp2, path)
