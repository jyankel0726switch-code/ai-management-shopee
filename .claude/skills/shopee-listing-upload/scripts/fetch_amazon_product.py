"""
fetch_amazon_product.py

Amazon.co.jp商品ページを取得し、Shopee出品ファイル生成に必要な情報
(商品名/在庫/画像URL/商品詳細テーブル/バリエーション候補)を抽出する。

## このスクリプトを作った理由(2026-09-15の失敗を踏まえた改修)

- 汎用のWebFetchツール(HTML→Markdown変換+要約)経由でAmazon商品ページを取得すると、
  `<head>`部分のみしか渡らず本文(商品名・価格・画像等)が一切抽出できないことがあった。
  → 本スクリプトは`curl`で生HTMLを取得し、そのHTMLを直接パースする。
- Amazon側の商品ページは、ギャラリー画像のJSON構造が商品によって2パターンある:
    (a) `"colorImages":{"色名":[{"hiRes":...}, ...]}` (バリエーションあり商品)
    (b) `'colorImages': { 'initial': A.$.parseJSON('[{"hiRes":...}, ...]') }` (バリエーションなし商品)
  片方のパターンだけに対応した実装だと、商品によって同じ画像の解像度違いを7枚取得する
  だけになってしまう(実際に複数商品で発生した)。本スクリプトは両方に対応し、
  取得したURLを画像ID単位で重複排除する。
- 在庫表示の文言はHTML内で`\\&quot;`にエスケープされており、素直な
  `"displayString":"..."` 形式の正規表現では一致しない。また「在庫あり」以外にも
  複数のレンダリングパターンがあるため、パターンを増やして拾う。

依存:
    pip install beautifulsoup4 lxml

使い方:
    from fetch_amazon_product import fetch_product
    data = fetch_product("B0XXXXXXXX")
"""
import json
import re
import subprocess

from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# 在庫表示のバリエーション。上から順に試す。
# (2026-09-15時点で確認できたパターン。新しい表示形式を見つけたら追記すること)
AVAILABILITY_PATTERNS = [
    r"残り\s*\d+\s*点[^&<\\\"]{0,20}",
    r"在庫あり[^&<\\\"]{0,20}",
    r"在庫切れ",
    r"一時的に在庫切れ",
    r"入荷時期は未定",
    r"通常\d+[〜~]\d+日以内に発送",
]

# Amazon商品ページに重量・サイズの記載がない場合の最終手段の仮値。
# カテゴリ名(breadcrumbsの一部と部分一致)ごとに、実測に基づき更新すること。
# 「一般的な仮値」を都度その場で考えるのではなく、ここに集約して再利用・検証可能にする。
DEFAULT_DIMENSIONS_BY_CATEGORY_KEYWORD = {
    "キッチン": {"weight": 0.3, "length": 20, "width": 15, "height": 10},
    "ビューティー": {"weight": 0.1, "length": 15, "width": 8, "height": 5},
    "ファッション": {"weight": 0.3, "length": 25, "width": 20, "height": 8},
    "カーテン": {"weight": 0.5, "length": 150, "width": 150, "height": 5},
    "文房具": {"weight": 0.5, "length": 20, "width": 15, "height": 10},
}


MOBILE_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

# 現在価格を示すdata-testid="price"直後の、取り消し線なしのdata-testid="price-text"を
# 拾う(fullprice側は取り消し線付きの旧価格なので除外される)。
PRICE_PATTERN = re.compile(
    r'data-testid=\\&quot;price\\&quot;[\s\S]{0,400}?'
    r'data-testid=\\&quot;price-text\\&quot;[\s\S]{0,300}?&gt;([\d,]+)&lt;'
)


def _curl_get(url: str, user_agent: str = USER_AGENT) -> str:
    cmd = [
        "curl", "-sS", "-L",
        "-A", user_agent,
        "-H", "Accept-Language: ja-JP,ja;q=0.9",
        url,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout


def _extract_price_jpy(mobile_html: str) -> int | None:
    """モバイル版(iPhone UA)のページからJPY価格(円)を取得する。

    デスクトップ版ページ(`_curl_get`のデフォルトUA)は、この価格ウィジェットが
    サーバー側HTMLに含まれず(クライアント側JSでのみ描画される)商品が多く、
    円建て価格が1つも見つからないことがある。一方モバイル版ページは同じ内容を
    `data-testid="price"`/`"price-text"`としてHTML内に(二重にHTMLエスケープされた
    形で)埋め込んでいるため、価格取得にはこちらを使う。
    """
    m = PRICE_PATTERN.search(mobile_html)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def _base_image_id(url: str) -> str:
    m = re.search(r"/I/([^./]+)\.", url)
    return m.group(1) if m else url


def _find_balanced_object(html: str, start: int) -> str:
    """`start`が指す `{` から、対応する `}` までの中身(内側)を波括弧の深さを数えて
    切り出す。`[^}]*`系の正規表現は`{`をスキップしないため、複数エントリを持つ
    オブジェクト(例: バリエーションが3つ以上ある商品のcolorToAsin)を1エントリ目で
    取りこぼす不具合があった(2026-09-15判明)。この関数はその代替。
    """
    assert html[start] == "{"
    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start + 1:i]
    return html[start + 1:]


def _extract_color_to_asin(html: str) -> dict[str, str]:
    """`"colorToAsin":{"色名":{"asin":"B0..."}, ...}` を色名→ASINの辞書で返す。"""
    mapping: dict[str, str] = {}
    m = re.search(r'"colorToAsin":\{', html)
    if not m:
        return mapping
    body = _find_balanced_object(html, m.end() - 1)
    for em in re.finditer(r'"([^"]+)":\{"asin":"([A-Z0-9]{10})"', body):
        mapping[em.group(1)] = em.group(2)
    return mapping


def _top_level_array_entries(body: str) -> list[tuple[str, int, int]]:
    """`body`(あるオブジェクトの中身)直下にある `"key":[ ... ]` 形式のエントリを、
    ネストの深さを追跡しながら列挙する。(key, array_start, array_end)のリストを返す
    (array_start/array_endは`[`と`]`のインデックス、endは`]`の次の位置)。

    単純な正規表現`"([^"]+)":\\[`だと、配列の中に入れ子で現れる別の`"key":[...]`
    (例: 画像サイズ別URLのマップ`"main":{"https://...jpg":["569","569"]}`)にも
    誤ってマッチしてしまい、本来1つの色に属する画像リストが途中で分断される
    不具合があった(2026-09-15判明)。ここでは深さ0の位置に現れるキーだけを対象にする。
    """
    entries: list[tuple[str, int, int]] = []
    depth = 0
    i = 0
    n = len(body)
    key_pattern = re.compile(r'"([^"]*)"\s*:\s*\[')
    while i < n:
        ch = body[i]
        if depth == 0:
            m = key_pattern.match(body, i)
            if m:
                array_start = m.end() - 1  # index of the '['
                array_end = _find_matching_bracket(body, array_start)
                entries.append((m.group(1), array_start, array_end))
                i = array_end
                depth = 0
                continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        i += 1
    return entries


def _find_matching_bracket(s: str, start: int) -> int:
    """s[start]が'['である前提で、対応する']'の次の位置を返す。"""
    assert s[start] == "["
    depth = 0
    for i in range(start, len(s)):
        if s[i] in "{[":
            depth += 1
        elif s[i] in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(s)


def _extract_color_images(html: str) -> dict[str, list[str]]:
    """`"colorImages":{"色名":[{...,"hiRes":"URL"}, ...], ...}` を
    色名→hiRes画像URLのリストの辞書で返す。バリエーション商品では色ごとに
    別々の画像セットを持つため、色を横断して1つのリストにまとめて返す
    (`_extract_images`の旧実装)とバリエーション違いの写真が混ざってしまう
    (2026-09-15判明: 3色バリエーション商品で、実際には別の色の写真を
    Item Imageに書いてしまっていた)。
    """
    result: dict[str, list[str]] = {}
    m = re.search(r'"colorImages":\{', html)
    if not m:
        return result
    body = _find_balanced_object(html, m.end() - 1)
    for color, array_start, array_end in _top_level_array_entries(body):
        segment = body[array_start:array_end]
        urls = [hm.group(1) for hm in re.finditer(r'"hiRes":"(https:[^"]+\.jpg)"', segment)]
        if not urls:
            urls = [hm.group(1) for hm in re.finditer(r'"large":"(https:[^"]+\.jpg)"', segment)]
        result[color] = urls
    return result


def _extract_images(html: str, asin: str) -> list[str]:
    images: list[str] = []

    # パターン(a): バリエーション商品。現在表示中のASIN自身の色(landingAsinColor)に
    # 対応する画像セットのみを使う(色をまたいで混在させない)。
    color_images = _extract_color_images(html)
    if color_images:
        lm = re.search(r'"landingAsinColor":"([^"]+)"', html)
        own_color = lm.group(1) if lm else None
        if own_color and own_color in color_images:
            images = list(color_images[own_color])
        elif len(color_images) == 1:
            images = list(next(iter(color_images.values())))

    # パターン(b): 'colorImages': { 'initial': A.$.parseJSON('[...]') } (バリエーションなし商品)
    if not images:
        m = re.search(r"'colorImages':\s*\{\s*'initial':\s*A\.\$\.parseJSON\('(\[.*?\])'\)", html, re.S)
        if m:
            try:
                arr = json.loads(m.group(1))
                for item in arr:
                    hires = item.get("hiRes") or item.get("large")
                    if hires and hires not in images:
                        images.append(hires)
            except Exception:
                pass

    # 重複排除(画像ID単位。同じ写真の解像度違いを別画像として数えない)
    seen: dict[str, str] = {}
    deduped: list[str] = []
    for u in images:
        b = _base_image_id(u)
        if b not in seen:
            seen[b] = u
            deduped.append(u)
    images = deduped

    # 最終フォールバック: メイン画像のdata-a-dynamic-image (1枚のみでも取得できるようにする)
    if not images:
        soup = BeautifulSoup(html, "lxml")
        main_img = soup.select_one("#landingImage, #imgBlkFront")
        if main_img:
            dyn = main_img.get("data-a-dynamic-image")
            if dyn:
                try:
                    d = json.loads(dyn)
                    images = list(d.keys())
                except Exception:
                    pass
            elif main_img.get("src"):
                images = [main_img.get("src")]

    return images[:7]


def _extract_availability(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    avail_el = soup.select_one("#availability span")
    text = avail_el.get_text(strip=True) if avail_el else None
    if text:
        return text
    for pattern in AVAILABILITY_PATTERNS:
        m = re.search(pattern, html)
        if m:
            return m.group(0)
    return None


def fetch_product(asin: str) -> dict:
    url = f"https://www.amazon.co.jp/dp/{asin}"
    html = _curl_get(url)
    soup = BeautifulSoup(html, "lxml")

    result: dict = {"asin": asin, "url": url}
    result["not_found"] = (
        any(s in html for s in ["お探しの商品が見つかりません", "現在このページは利用できません", "申し訳ございません"])
        and "productTitle" not in html
    )

    title_el = soup.select_one("#productTitle")
    result["title"] = title_el.get_text(strip=True) if title_el else None

    result["availability"] = _extract_availability(html)
    result["images"] = _extract_images(html, asin)
    result["breadcrumbs"] = [a.get_text(strip=True) for a in soup.select("#wayfinding-breadcrumbs_feature_div a")]
    # 他の選択肢(色/柄等)のASIN一覧。現在表示中のASIN自身は含まれないことがある
    # (`landingAsinColor`が現在の値)。バリエーションのクロスチェックに使う。
    result["sibling_asins"] = _extract_color_to_asin(html)
    lm = re.search(r'"landingAsinColor":"([^"]+)"', html)
    result["own_variation_value"] = lm.group(1) if lm else None

    mobile_html = _curl_get(url, user_agent=MOBILE_USER_AGENT)
    result["price_jpy"] = _extract_price_jpy(mobile_html)

    details: dict[str, str] = {}
    for row in soup.select("#productDetails_detailBullets_sections1 tr, #productDetails_techSpec_section_1 tr, .prodDetTable tr"):
        th = row.select_one("th")
        td = row.select_one("td")
        if th and td:
            details[th.get_text(strip=True)] = td.get_text(" ", strip=True)
    for li in soup.select("#detailBulletsWrapper_feature_div li"):
        txt = li.get_text(" ", strip=True)
        parts = re.split(r"[:：]", txt, maxsplit=1)
        if len(parts) == 2:
            details[parts[0].strip()] = parts[1].strip()
    result["details"] = details

    return result


def default_dimensions_for(breadcrumbs: list[str]) -> dict | None:
    """商品ページに重量・サイズの記載が無い場合の最終フォールバック値を返す。
    breadcrumbsのいずれかの階層名にキーワードが部分一致した最初の値を採用する。
    一致しなければNoneを返す(呼び出し側で要確認フラグを立てた上で汎用値を使うこと)。
    """
    joined = " / ".join(breadcrumbs)
    for keyword, dims in DEFAULT_DIMENSIONS_BY_CATEGORY_KEYWORD.items():
        if keyword in joined:
            return dims
    return None


if __name__ == "__main__":
    import sys
    out = [fetch_product(a) for a in sys.argv[1:]]
    print(json.dumps(out, ensure_ascii=False, indent=2))
