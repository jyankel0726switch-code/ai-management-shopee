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


def _curl_get(url: str) -> str:
    cmd = [
        "curl", "-sS", "-L",
        "-A", USER_AGENT,
        "-H", "Accept-Language: ja-JP,ja;q=0.9",
        url,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout


def _base_image_id(url: str) -> str:
    m = re.search(r"/I/([^./]+)\.", url)
    return m.group(1) if m else url


def _extract_images(html: str, asin: str) -> list[str]:
    images: list[str] = []

    # パターン(a): "colorToAsin":{"色名":{"asin":"B0..."}} の近傍にある "colorImages" ブロック
    for cm in re.finditer(r'"colorToAsin":\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', html):
        if asin not in cm.group(1):
            continue
        ci_start = html.find('"colorImages"', max(0, cm.start() - 40000), cm.start())
        if ci_start == -1:
            ci_start = html.find('"colorImages"', cm.end(), cm.end() + 40000)
        if ci_start != -1:
            segment = html[ci_start:ci_start + 40000]
            for hm in re.finditer(r'"hiRes":"(https:[^"]+\.jpg)"', segment):
                if hm.group(1) not in images:
                    images.append(hm.group(1))
            if not images:
                for hm in re.finditer(r'"large":"(https:[^"]+\.jpg)"', segment):
                    if hm.group(1) not in images:
                        images.append(hm.group(1))
        break

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
