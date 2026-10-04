#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shopee 競合店リサーチ：保存ページ読み取りスクリプト

ユーザーが普段のブラウザで開いて保存した（Ctrl+S）Shopee の店舗ページを読み取り、
売れ筋商品の一覧を作る。**Shopee へのアクセスは一切行わない**（手元のファイルを読むだけ）。

入力:  data/competitor/inbox/ に置かれた .html / .htm / .mhtml / .mht
出力:  data/competitor/YYYY-MM-DD/top_sales.csv  … 本日分（同じ日に何度実行しても追記・統合）
       data/competitor/last_run_status.json       … 実行結果
処理済みの保存ファイルは data/competitor/processed/YYYY-MM-DD/ へ移動する（削除はしない）。

各商品について、同じ店の前回の記録と比べて「販売数の増加」「新登場」を計算する。

使い方:
  python parse_saved_pages.py            … inbox を処理
  python parse_saved_pages.py --keep     … 処理後も inbox から移動しない（テスト用）
"""
import argparse
import csv
import email
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

JST = timezone(timedelta(hours=9))

SKILL_DIR = Path(__file__).resolve().parent.parent          # .claude/skills/competitor-research
PROJECT_ROOT = SKILL_DIR.parent.parent.parent                # ai-management
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "competitor"

DOMAINS = {"SG": "shopee.sg", "MY": "shopee.com.my", "TH": "shopee.co.th", "PH": "shopee.ph"}
DOMAIN_TO_COUNTRY = {v: k for k, v in DOMAINS.items()}
CURRENCY = {"SG": "SGD", "MY": "MYR", "TH": "THB", "PH": "PHP"}
SYMBOL_TO_COUNTRY = {"RM": "MY", "฿": "TH", "₱": "PH", "S$": "SG", "$": "SG"}
EXTS = {".html", ".htm", ".mhtml", ".mht"}

CSV_COLUMNS = [
    "date_jst", "saved_file", "country", "shop_username", "shop_title", "shopid", "rank",
    "itemid", "name", "price", "price_min", "price_max", "currency",
    "sold_display", "sold", "prev_date", "prev_sold", "sold_change", "is_new",
    "item_url", "image_url",
]

SOLD_PATTERNS = [
    r"([\d.,]+\s*[kKmM]?\+?)\s*sold",                                   # 1.2k sold
    r"([\d.,]+\s*[kKmM]?\+?)\s*terjual",                                # MY
    r"ขายแล้ว\s*([\d.,]+\s*(?:[kKmM]|พัน|หมื่น|แสน|ล้าน)?\+?)",          # TH
]
PRICE_PATTERN = r"(S\$|RM|฿|₱|\$)\s*([\d,]+(?:\.\d+)?)"
NOISE_LINE = re.compile(r"^(-?\d+%|Ad|Mall|Preferred\+?|Preferred|Sold out|Free shipping|COD|"
                        r"Overseas|Japan|ส่งจากต่างประเทศ|[\d.]+)$", re.I)


def now_jst():
    return datetime.now(JST)


def log(msg):
    print(f"[{now_jst():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def parse_count(text):
    """'1.2k' '10K+' '1,234' '1.2พัน' -> int"""
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace("+", "")
    m = re.search(r"([\d.]+)\s*([kKmM]|พัน|หมื่น|แสน|ล้าน)?", s)
    if not m:
        return None
    try:
        num = float(m.group(1))
    except ValueError:
        return None
    mult = {"k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6, "พัน": 1e3, "หมื่น": 1e4,
            "แสน": 1e5, "ล้าน": 1e6}.get(m.group(2) or "", 1)
    return int(round(num * mult))


# ---------------------------------------------------------------- 保存ファイルの読み込み
def read_saved_file(path):
    """(html文字列, 保存元URL or None) を返す。MHTML にも対応"""
    raw = path.read_bytes()
    if path.suffix.lower() in (".mhtml", ".mht"):
        msg = email.message_from_bytes(raw)
        src = msg.get("Snapshot-Content-Location")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                html = part.get_payload(decode=True).decode(charset, errors="replace")
                return html, src or part.get("Content-Location")
        return "", src
    for enc in ("utf-8", "cp932", "latin-1"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), None


class ShopPageParser(HTMLParser):
    """リンク(<a>)ごとに中のテキストと画像を集める。ページのURL手がかりも拾う"""
    BLOCK = {"div", "p", "br", "li", "section", "h1", "h2", "h3", "h4", "span"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []          # {"href","text","img"}
        self.stack = []            # 開いている <a> のインデックス
        self.skip = 0
        self.title = ""
        self.in_title = False
        self.url_hints = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical" and a.get("href"):
            self.url_hints.insert(0, a["href"])
        elif tag == "meta" and (a.get("property") or a.get("name")) == "og:url" and a.get("content"):
            self.url_hints.insert(0, a["content"])
        elif tag == "base" and a.get("href"):
            self.url_hints.append(a["href"])
        elif tag == "a":
            self.anchors.append({"href": a.get("href") or "", "text": "", "img": ""})
            self.stack.append(len(self.anchors) - 1)
        elif tag == "img" and self.stack:
            cur = self.anchors[self.stack[-1]]
            if not cur["img"]:
                cur["img"] = a.get("src") or a.get("data-src") or ""
        if tag in self.BLOCK and self.stack:
            self.anchors[self.stack[-1]]["text"] += "\n"

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        elif tag == "a" and self.stack:
            self.stack.pop()
        if tag in self.BLOCK and self.stack:
            self.anchors[self.stack[-1]]["text"] += "\n"

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_title:
            self.title += data
        if self.stack:
            self.anchors[self.stack[-1]]["text"] += data

    def handle_comment(self, data):
        m = re.search(r"saved from url=\(\d+\)(\S+)", data)
        if m:
            self.url_hints.insert(0, m.group(1))


PRODUCT_HREF = [re.compile(r"-i\.(\d+)\.(\d+)"), re.compile(r"/product/(\d+)/(\d+)")]


def parse_card(text, img):
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    joined = "\n".join(lines)
    sold_re = "|".join(SOLD_PATTERNS)
    cands = [l for l in lines if not re.search(PRICE_PATTERN, l) and not re.search(sold_re, l, re.I)
             and not NOISE_LINE.match(l) and len(l) > 5]
    name = max(cands, key=len) if cands else (lines[0] if lines else "")
    name = re.sub(PRICE_PATTERN, " ", name)
    for pat in SOLD_PATTERNS:
        name = re.sub(pat, " ", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" -")

    # 価格は通貨記号の直後の数字。"$" と "12.90" が別行に分かれている場合にも対応
    flat = re.sub(r"(S\$|RM|฿|₱|\$)\s*\n\s*", r"\1", joined)
    prices = [float(p.replace(",", "")) for _, p in re.findall(PRICE_PATTERN, flat)]
    symbols = [s for s, _ in re.findall(PRICE_PATTERN, flat)]
    sold_display, sold = "", None
    for pat in SOLD_PATTERNS:
        m = re.search(pat, joined, re.I)
        if m:
            sold_display = m.group(0).strip()
            sold = parse_count(m.group(1))
            break
    return {"name": name, "price": prices[0] if prices else None,
            "price_min": min(prices) if prices else None, "price_max": max(prices) if prices else None,
            "sold_display": sold_display, "sold": sold, "image_url": img,
            "symbol": symbols[0] if symbols else None}


def detect_page(url_hints, anchors_hrefs, symbols):
    """(country, shop_username) を推定"""
    country, user = None, None
    for u in url_hints:
        m = re.match(r"https?://(?:www\.)?([^/]+)/([^/?#]+)?", u)
        if m and m.group(1) in DOMAIN_TO_COUNTRY:
            country = DOMAIN_TO_COUNTRY[m.group(1)]
            seg = m.group(2)
            if seg and not seg.startswith(("search", "product", "shop", "buyer", "mall")) and "-i." not in seg:
                user = seg
            break
    if not country:
        doms = Counter()
        for h in anchors_hrefs:
            m = re.match(r"https?://(?:www\.)?([^/]+)/", h)
            if m and m.group(1) in DOMAIN_TO_COUNTRY:
                doms[m.group(1)] += 1
        if doms:
            country = DOMAIN_TO_COUNTRY[doms.most_common(1)[0][0]]
    if not country and symbols:
        country = SYMBOL_TO_COUNTRY.get(Counter(symbols).most_common(1)[0][0])
    return country, user


def parse_shop_page(path, shops_by_id):
    html, mhtml_src = read_saved_file(path)
    p = ShopPageParser()
    p.feed(html)
    hints = ([mhtml_src] if mhtml_src else []) + p.url_hints

    cards = {}
    for a in p.anchors:
        for rx in PRODUCT_HREF:
            m = rx.search(a["href"])
            if m:
                key = (m.group(1), m.group(2))
                if key not in cards and a["text"].strip():
                    cards[key] = a
                break
    if not cards:
        return None, "商品リンクが見つかりません（「ウェブページ、完全」で保存されているか確認してください）"

    shopid = Counter(k[0] for k in cards).most_common(1)[0][0]   # 店のshopid = 最も多いshopid
    items = []
    for (sid, iid), a in cards.items():
        if sid != shopid:
            continue                                              # おすすめ欄などの他店商品は除外
        c = parse_card(a["text"], a["img"])
        if not c["name"]:
            continue
        c.update(shopid=sid, itemid=iid)
        items.append(c)

    country, user = detect_page(hints, [a["href"] for a in p.anchors], [i["symbol"] for i in items if i["symbol"]])
    known = shops_by_id.get(shopid)
    if known:
        country = country or known["country"]
        user = user or known["shop_username"]
    if not country:
        return None, "国(SG/MY/TH/PH)を判定できません"
    user = user or f"shop_{shopid}"
    title = re.sub(r"\s+", " ", p.title).strip()
    for it in items:
        it["item_url"] = f"https://{DOMAINS[country]}/product/{shopid}/{it['itemid']}"
    return {"country": country, "shop_username": user, "shop_title": title, "shopid": shopid,
            "items": items}, None


# ---------------------------------------------------------------- 前回比
def load_previous(data_dir, today):
    """{(country, shop, itemid): (date, sold)} 今日より前で最新の記録"""
    prev = {}
    days = sorted(d.name for d in data_dir.iterdir()
                  if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name) and d.name < today)
    for day in days:                       # 古い順に読み、新しい日で上書き
        f = data_dir / day / "top_sales.csv"
        if not f.exists():
            continue
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                key = (r["country"], r["shopid"], r["itemid"])
                sold = int(r["sold"]) if r.get("sold") not in (None, "") else None
                prev[key] = (day, sold)
    seen_shops = {(k[0], k[1]) for k in prev}
    return prev, seen_shops


def load_history_csv(path, today, prev):
    """Google Sheets「競合店_売れ筋」から書き出した履歴CSVを読む（クラウド実行用）。
    列名は英語(date_jst,country,shopid,itemid,sold) または 日本語(記録日,国,shopid,itemid,販売数) のどちらでもよい。"""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    def g(r, *names):
        for n in names:
            if r.get(n) not in (None, ""):
                return str(r[n]).strip()
        return ""
    rows.sort(key=lambda r: g(r, "date_jst", "記録日"))       # 古い順 → 新しい日で上書き
    for r in rows:
        day = g(r, "date_jst", "記録日")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or day >= today:
            continue
        key = (g(r, "country", "国"), g(r, "shopid"), g(r, "itemid"))
        if not all(key):
            continue
        sold_s = g(r, "sold", "販売数").replace(",", "")
        sold = int(float(sold_s)) if re.fullmatch(r"[\d.]+", sold_s or "x") else None
        prev[key] = (day, sold)
    return prev


def load_shops(path):
    by_id, rows = {}, []
    if not path.exists():
        return by_id, rows
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            r = {k: (v or "").strip() for k, v in r.items() if k}
            rows.append(r)
            if r.get("shopid"):
                by_id[r["shopid"]] = r
    return by_id, rows


# ---------------------------------------------------------------- メイン
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    ap.add_argument("--shops", default=str(SKILL_DIR / "shops.csv"))
    ap.add_argument("--keep", action="store_true", help="処理後も inbox から移動しない")
    ap.add_argument("--inbox-dir", default=None, help="保存ページの置き場所（既定: data-dir/inbox）")
    ap.add_argument("--date", default=None, help="記録日 YYYY-MM-DD（既定: 今日のJST日付）")
    ap.add_argument("--history-csv", default=None, help="前回比に使う履歴CSV（Sheetsから書き出したもの）")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    inbox = Path(args.inbox_dir) if args.inbox_dir else data_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    today = args.date or now_jst().strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", today):
        log(f"--date の形式が不正です: {today}")
        return 1
    day_dir = data_dir / today
    status_path = data_dir / "last_run_status.json"

    files = sorted(f for f in inbox.iterdir() if f.is_file() and f.suffix.lower() in EXTS)
    status = {"date_jst": today, "run_at": now_jst().isoformat(timespec="seconds"),
              "files": [], "overall": None, "total_items": 0}
    if not files:
        # 本日すでに読み取り済みなら、その結果を残す（bat で先に読み取った後に再実行された場合など）
        if status_path.exists():
            try:
                st = json.loads(status_path.read_text(encoding="utf-8"))
            except Exception:
                st = {}
            if st.get("date_jst") == today and st.get("overall") in ("ok", "partial"):
                log(f"inbox は空ですが、本日分は読み取り済みです（{st.get('total_items')}件）→ {day_dir / 'top_sales.csv'}")
                return 0
        status["overall"] = "no_files"
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"inbox に保存ページがありません: {inbox}")
        return 3

    shops_by_id, _ = load_shops(Path(args.shops))
    prev, _ = load_previous(data_dir, today)
    if args.history_csv:
        prev = load_history_csv(Path(args.history_csv), today, prev)

    # 本日分の既存データ（同じ日に複数回実行した場合は統合）
    out_csv = day_dir / "top_sales.csv"
    rows = {}
    if out_csv.exists():
        with open(out_csv, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                rows[(r["country"], r["shopid"], r["itemid"])] = r

    processed_dir = data_dir / "processed" / today
    for f in files:
        entry = {"file": f.name, "status": None, "country": "", "shop_username": "", "count": 0, "error": ""}
        try:
            page, err = parse_shop_page(f, shops_by_id)
            if err:
                entry.update(status="error", error=err)
            else:
                entry.update(status="ok", country=page["country"], shop_username=page["shop_username"],
                             shopid=page["shopid"], count=len(page["items"]))
                for it in page["items"]:
                    key = (page["country"], page["shopid"], it["itemid"])
                    p_day, p_sold = prev.get(key, (None, None))
                    old = rows.get(key)
                    if old and old.get("sold") not in (None, "") and it["sold"] is not None \
                            and int(old["sold"]) > it["sold"]:
                        continue                     # 同日に複数ページ保存した場合は大きい方を残す
                    rows[key] = {
                        "date_jst": today, "saved_file": f.name, "country": page["country"],
                        "shop_username": page["shop_username"], "shop_title": page["shop_title"],
                        "shopid": page["shopid"], "itemid": it["itemid"], "name": it["name"],
                        "price": it["price"], "price_min": it["price_min"], "price_max": it["price_max"],
                        "currency": CURRENCY[page["country"]], "sold_display": it["sold_display"],
                        "sold": it["sold"], "prev_date": p_day or "", "prev_sold": "" if p_sold is None else p_sold,
                        "sold_change": (it["sold"] - p_sold) if (it["sold"] is not None and p_sold is not None) else "",
                        "is_new": 1 if p_day is None else 0,
                        "item_url": it["item_url"], "image_url": it["image_url"],
                    }
            log(f"{f.name}: {entry['status']} {entry['country']} {entry['shop_username']} {entry['count']}件 {entry['error']}")
        except Exception as e:
            entry.update(status="error", error=f"{e.__class__.__name__}: {e}"[:300])
            log(f"{f.name}: エラー {entry['error']}")
        status["files"].append(entry)
        if not args.keep:
            processed_dir.mkdir(parents=True, exist_ok=True)
            dest = processed_dir / f.name
            n = 1
            while dest.exists():
                dest = processed_dir / f"{f.stem}_{n}{f.suffix}"
                n += 1
            shutil.move(str(f), str(dest))
            # 「ウェブページ、完全」で一緒に保存される _files フォルダも移動
            side = f.with_name(f.stem + "_files")
            if side.is_dir():
                shutil.move(str(side), str(dest.with_name(dest.stem + "_files")))

    # 店ごとに販売数順で順位を振り直して保存
    all_rows = list(rows.values())
    by_shop = {}
    for r in all_rows:
        by_shop.setdefault((r["country"], r["shopid"]), []).append(r)
    final = []
    for _, lst in sorted(by_shop.items()):
        lst.sort(key=lambda r: (r["sold"] in (None, ""), -int(r["sold"] or 0)))
        for n, r in enumerate(lst, 1):
            r["rank"] = n
        final.extend(lst)
    if final:
        day_dir.mkdir(parents=True, exist_ok=True)
        with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(final)

    oks = sum(1 for e in status["files"] if e["status"] == "ok")
    status["overall"] = "ok" if oks == len(files) else ("partial" if oks else "failed")
    status["total_items"] = len(final)
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"完了: {status['overall']}（{oks}/{len(files)}ファイル、本日分 合計{len(final)}件）→ {out_csv}")
    return 0 if oks else 2


if __name__ == "__main__":
    sys.exit(main())
