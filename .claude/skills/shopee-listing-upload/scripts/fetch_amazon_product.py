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
    "シール": {"weight": 0.02, "length": 15, "width": 11, "height": 1},
    "タオル": {"weight": 0.12, "length": 20, "width": 15, "height": 3},
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


PRICE_SEARCH_WINDOW = 700000  # productTitle位置からこの範囲内のみ価格候補として認める
YEN_FALLBACK_WINDOW = 15000   # 「￥X,XXX」フォールバックはタイトルのごく近くのみ許可

# 地域誤判定時にUSD表示された価格からJPY推定値を逆算するためのレート。
# 2026-09-15、本セッションで同時に地域誤判定していた3商品(実際のJPY価格を
# ユーザーがAmazon画面で確認済み)について、表示されたUSD金額から逆算した
# implied rateがいずれも153.37423312883436(小数点以下まで完全一致)だった
# ことから採用。この値はAmazonが内部的に使っている当日のUSD/JPY換算レートの
# 実測値であり、恣意的な仮値ではない(このセッションの実行環境からは、
# 外部の為替APIへの直接アクセスがネットワークポリシーでブロックされている
# ため、この逆算が唯一の実測手段)。
# 為替レートは日々変動するため、このレートを使って算出した価格はあくまで
# **推定値**として扱い、人による確認なしに確定価格として採用しないこと
# (別の商品では約1%のズレが見られたが、これはレート誤差ではなく実際の
# JPY価格自体が変動した可能性が高いと判断した。差異が大きい場合は
# このレート自体の再検証が必要)。新しい既知価格ペアが得られた場合は、
# このレートを再calibrationして更新すること。
USD_JPY_RATE = 153.374233


def _extract_price_from_buybox(desktop_html: str, asin: str) -> dict:
    """デスクトップ版ページの、対象ASINに紐づくことが明示された購入フォーム
    (`data-csa-c-asin="{asin}"`を持つ`qualifiedBuybox`ウィジェット内の
    `items[0.base][customerVisiblePrice]`隠しフィールド)から価格を取得する。

    2026-09-15追加。それまでの実装(`data-testid="price"`の全文検索、
    のちに#productTitleからの距離で絞り込み)は、同じ`data-testid`が
    レコメンド/タイムセールのカルーセルにも使われているため、2回にわたって
    **全く無関係な別商品の価格**を誤って採用する事故を起こした
    (SALONIAドライヤーの価格、タイムセール商品の価格をそれぞれ誤取得。
    いずれもユーザーが実際のAmazon画面のスクリーンショットで指摘して発覚)。

    この関数が使う`data-csa-c-asin="{asin}"`は、Amazon側がその購入フォームが
    *まさにこのASINのもの*であることを明示するために付与している属性であり、
    プロキシ的な位置関係ではなく構造的な裏付けがある。またこの過程で、
    本セッションのAmazonアクセスが地域誤判定を起こしている場合、この購入
    フォームの通貨が`JPY`ではなく`USD`等になっていることも合わせて検出できる
    (2026-09-15判明: セッション全体で複数商品が同時にUSD表示になっていた回が
    あった)。

    地域誤判定時、通貨がUSDの場合は`price_jpy_estimated`にJPY推定値も返す
    (`USD_JPY_RATE`参照。あくまで推定であり、`price_jpy`(確定値)には入れない
    ので、呼び出し側は必ず人に確認を仰いだ上で採用すること)。

    戻り値: {"price_jpy": int|None, "currency": str|None, "region_mismatch": bool,
             "price_jpy_estimated": int|None}
    """
    result = {"price_jpy": None, "currency": None, "region_mismatch": False, "price_jpy_estimated": None}
    marker = f'data-csa-c-asin="{asin}"'
    i = desktop_html.find(marker)
    if i == -1:
        return result
    segment = desktop_html[i:i + 4000]
    cm = re.search(r'customerVisiblePrice\]\[currencyCode\]"\s*value="([^"]+)"', segment)
    am = re.search(r'customerVisiblePrice\]\[amount\]"\s*value="([^"]+)"', segment)
    if not cm or not am:
        # 2026-09-15追加: このASINの`data-csa-c-asin`マーカーが指すウィジェットが
        # `qualifiedBuybox`(価格を持つ正常な購入フォーム)ではなく
        # `outOfStockBuyBox`(「この商品は選択したお届け先には発送できません。
        # 別のお届け先を選択してください。」というアメリカ合衆国宛て地域誤判定の
        # 文言を持つウィジェット)である場合、customerVisiblePriceフィールドが
        # 存在しないため単にNoneを返すだけでは不十分だった。その状態のまま
        # `fetch_product`が信頼度の低い旧方式(`_extract_price_jpy_legacy`)に
        # フォールバックし、ページ内の無関係な価格表示を拾ってしまう事故が
        # 6件中2件で発生した(qualifiedBuybox自体がページに存在せず、
        # outOfStockBuyBoxのみが描画されていたことを確認済み)。
        # このブロック文言がこのASINの購入フォーム内に見つかった場合は、
        # 地域誤判定として明示的にフラグを立て、旧方式へのフォールバックを防ぐ。
        if "この商品は選択したお届け先には発送できません" in segment:
            result["region_mismatch"] = True
        return result
    currency = cm.group(1)
    result["currency"] = currency
    try:
        amount = float(am.group(1))
    except ValueError:
        return result
    if currency == "JPY":
        result["price_jpy"] = int(round(amount))
    else:
        result["region_mismatch"] = True
        if currency == "USD":
            result["price_jpy_estimated"] = int(round(amount * USD_JPY_RATE))
    return result


def _extract_price_jpy_legacy(mobile_html: str) -> int | None:
    """`_extract_price_from_buybox`でASIN紐付きの価格が見つからない場合の
    フォールバック(旧実装)。位置的な絞り込みしかできないため、
    `_extract_price_from_buybox`より信頼度が低い(上記docstring参照)。
    """
    title_pos = mobile_html.find('id="productTitle"')
    if title_pos == -1:
        title_pos = mobile_html.find("productTitle")
    search_area = (
        mobile_html[title_pos:title_pos + PRICE_SEARCH_WINDOW]
        if title_pos != -1
        else mobile_html[:PRICE_SEARCH_WINDOW]
    )
    m = PRICE_PATTERN.search(search_area)
    if m:
        return int(m.group(1).replace(",", ""))

    if title_pos != -1:
        yen_area_start = max(0, title_pos - YEN_FALLBACK_WINDOW)
        yen_area = mobile_html[yen_area_start:title_pos + YEN_FALLBACK_WINDOW]
        ym = re.search(r"[￥¥]([\d,]+)", yen_area)
        if ym:
            return int(ym.group(1).replace(",", ""))
    return None


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
    # パターン(a): "colorImages":{"色名":[...]}の、現在表示中のASIN自身の色
    # (landingAsinColor)に対応する画像セット(色をまたいで混在させない)。
    # このJSONは色ごとに1枚(スウォッチ代表カット)しか持たないことがある。
    color_images = _extract_color_images(html)
    own_color = None
    lm = re.search(r'"landingAsinColor":"([^"]+)"', html)
    if lm:
        own_color = lm.group(1)
    images_a: list[str] = []
    if own_color and own_color in color_images:
        images_a = list(color_images[own_color])
    elif len(color_images) == 1:
        images_a = list(next(iter(color_images.values())))

    # パターン(b): 'colorImages': { 'initial': A.$.parseJSON('[...]') }
    # ページの初期表示(=現在のASIN/色)についての、メイン+複数アングル
    # (MAIN/PT01/PT02...)を含むフルセット。パターン(a)が1枚しか持たない
    # 商品でも、こちらには同じ色の別アングル写真が入っていることがある
    # (2026-09-15判明: 3色バリエーション商品で、パターン(a)が各色1枚しか
    # 返さないためパターン(b)を一切試さず、結果的に2〜3枚しか取得できて
    # いなかった)。したがって両方を試し、より多く取得できた方を採用する。
    images_b: list[str] = []
    m = re.search(r"'colorImages':\s*\{\s*'initial':\s*A\.\$\.parseJSON\('(\[.*?\])'\)", html, re.S)
    if m:
        try:
            arr = json.loads(m.group(1))
            for item in arr:
                hires = item.get("hiRes") or item.get("large")
                if hires and hires not in images_b:
                    images_b.append(hires)
        except Exception:
            pass

    images = images_b if len(images_b) >= len(images_a) else images_a

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

    buybox = _extract_price_from_buybox(html, asin)
    result["price_jpy"] = buybox["price_jpy"]
    result["price_currency"] = buybox["currency"]
    result["price_region_mismatch"] = buybox["region_mismatch"]
    result["price_jpy_estimated"] = buybox["price_jpy_estimated"]
    if result["price_jpy"] is None and not buybox["region_mismatch"]:
        # ASIN紐付きの購入フォームが見つからなかった場合のみ、信頼度の低い
        # 旧方式(位置的な絞り込み)にフォールバックする。region_mismatchが
        # 真の場合(USD等で表示されていた場合)はフォールバックしない: 誤った
        # 通貨の商品ページ全体が地域誤判定を起こしている可能性が高く、
        # 旧方式で見つかる価格も同様に信用できないため。
        mobile_html = _curl_get(url, user_agent=MOBILE_USER_AGENT)
        result["price_jpy"] = _extract_price_jpy_legacy(mobile_html)

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
    breadcrumbsの階層名にキーワードが部分一致した値を採用する。
    一致しなければNoneを返す(呼び出し側で要確認フラグを立てた上で汎用値を使うこと)。

    2026-09-15判明: 以前は`breadcrumbs`を1本の文字列に結合してから先頭一致の
    キーワードを探していたため、末尾(より具体的)の階層名にキーワードが
    あっても、先頭(より大まかな)階層名にたまたま含まれる無関係なキーワードが
    先に一致してしまう不具合があった(例:「ホーム＆キッチン / バス・トイレ・
    洗面用品 / タオル / フェイスタオル」で、末尾の「タオル」より先に先頭の
    「ホーム＆キッチン」に含まれる「キッチン」が誤って一致し、台所用品の
    仮値が採用されてしまっていた)。breadcrumbsは先頭ほど大分類・末尾ほど
    具体的な小分類になっているため、末尾から順に1階層ずつキーワードを
    探すことで、より具体的な階層名を優先する。
    """
    for segment in reversed(breadcrumbs):
        for keyword, dims in DEFAULT_DIMENSIONS_BY_CATEGORY_KEYWORD.items():
            if keyword in segment:
                return dims
    return None


if __name__ == "__main__":
    import sys
    out = [fetch_product(a) for a in sys.argv[1:]]
    print(json.dumps(out, ensure_ascii=False, indent=2))
