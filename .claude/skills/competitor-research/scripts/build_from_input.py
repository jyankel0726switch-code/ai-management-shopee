#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shopee 競合店リサーチ（クラウド版）：入力タブ → 売れ筋データ

ブックマークレットでコピーして Google Sheets「競合店_入力」タブに貼り付けられた行（を CSV に書き出したもの）と、
「競合店_売れ筋」タブの履歴 CSV を読み、まだ記録していない分について
店×記録日ごとに販売数順の順位・前回比（販売数の増加・新登場）を計算して CSV に出力する。

入力 CSV（--input）の列（見出し行あり、順番どおり）:
  取得日時, 国, 店舗, shopid, itemid, 商品名, 価格, 価格(最小), 価格(最大), 販売数(表示), 販売数, 商品URL, 画像URL
履歴 CSV（--history）の列: date_jst, country, shopid, itemid, sold

出力（--out）: parse_saved_pages.py と同じ列の CSV（競合店_売れ筋 に追記する分だけ）
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_saved_pages import CSV_COLUMNS, CURRENCY, parse_count  # noqa: E402

IN_COLS = ["取得日時", "国", "店舗", "shopid", "itemid", "商品名", "価格", "価格(最小)", "価格(最大)",
           "販売数(表示)", "販売数", "商品URL", "画像URL"]


def num(s):
    s = str(s or "").replace(",", "").strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def to_int(s):
    s = str(s or "").replace(",", "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return int(float(s))
    return parse_count(s)


def to_date(s):
    """'2026-10-04 11:52:02' / '2026/10/4 11:52' / Sheets のシリアル値 → '2026-10-04'"""
    s = str(s or "").strip()
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if re.fullmatch(r"\d{5}(\.\d+)?", s):                 # シリアル値（1899-12-30 起点）
        from datetime import date, timedelta
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).isoformat()
    return ""


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # ---- 入力（見出し行があれば飛ばす。列は位置で読む）
    raw = read_csv(args.input)
    inputs, skipped = [], 0
    for r in raw:
        if not r or not any(c.strip() for c in r):
            continue
        if r[0].strip() == "取得日時":
            continue
        r = (r + [""] * len(IN_COLS))[:len(IN_COLS)]
        d = dict(zip(IN_COLS, [c.strip() for c in r]))
        date = to_date(d["取得日時"])
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or d["国"] not in CURRENCY or not d["shopid"] or not d["itemid"]:
            skipped += 1
            continue
        d["date"] = date
        inputs.append(d)

    # ---- 履歴
    hist = defaultdict(list)       # (country, shopid, itemid) -> [(date, sold)]
    recorded = set()               # (date, country, shopid, itemid)
    hrows = read_csv(args.history)
    if hrows:
        head = [h.strip() for h in hrows[0]]
        idx = {h: i for i, h in enumerate(head)}
        for r in hrows[1:]:
            try:
                date = to_date(r[idx["date_jst"]])
                key = (r[idx["country"]].strip(), r[idx["shopid"]].strip(), r[idx["itemid"]].strip())
                sold = to_int(r[idx["sold"]])
            except (KeyError, IndexError):
                continue
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or not all(key):
                continue
            hist[key].append((date, sold))
            recorded.add((date,) + key)

    # ---- 未記録分を 記録日×国×shopid でまとめる（同じ商品が複数回貼られたら販売数の大きい方）
    groups = defaultdict(dict)
    already = 0
    for d in inputs:
        key = (d["国"], d["shopid"], d["itemid"])
        if (d["date"],) + key in recorded:
            already += 1
            continue
        g = groups[(d["date"], d["国"], d["shopid"])]
        old = g.get(d["itemid"])
        if old is None or (to_int(d["販売数"]) or 0) > (to_int(old["販売数"]) or 0):
            g[d["itemid"]] = d

    out_rows = []
    for (date, country, shopid) in sorted(groups):          # 古い日から順に（同じ実行内の前回比も正しく）
        items = list(groups[(date, country, shopid)].values())
        items.sort(key=lambda d: (to_int(d["販売数"]) is None, -(to_int(d["販売数"]) or 0)))
        for rank, d in enumerate(items, 1):
            key = (country, shopid, d["itemid"])
            past = [x for x in hist[key] if x[0] < date]
            p_date, p_sold = max(past) if past else (None, None)
            sold = to_int(d["販売数"])
            out_rows.append({
                "date_jst": date, "saved_file": "ブックマーク " + d["取得日時"], "country": country,
                "shop_username": d["店舗"], "shop_title": "", "shopid": shopid, "rank": rank,
                "itemid": d["itemid"], "name": d["商品名"],
                "price": num(d["価格"]), "price_min": num(d["価格(最小)"]), "price_max": num(d["価格(最大)"]),
                "currency": CURRENCY[country], "sold_display": d["販売数(表示)"], "sold": sold,
                "prev_date": p_date or "", "prev_sold": "" if p_sold is None else p_sold,
                "sold_change": (sold - p_sold) if (sold is not None and p_sold is not None) else "",
                "is_new": 1 if p_date is None else 0,
                "item_url": d["商品URL"], "image_url": d["画像URL"],
            })
        for d in items:                                       # 次の日付の前回比に使う
            hist[(country, shopid, d["itemid"])].append((date, to_int(d["販売数"])))

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    shops = sorted({(r["date_jst"], r["country"], r["shop_username"]) for r in out_rows})
    print(f"入力 {len(inputs)}行（不正 {skipped}行・記録済み {already}行を除外）→ 新規 {len(out_rows)}行 / {len(shops)}店×日")
    for s in shops:
        n = sum(1 for r in out_rows if (r["date_jst"], r["country"], r["shop_username"]) == s)
        print(f"  {s[0]} {s[1]} {s[2]}: {n}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
