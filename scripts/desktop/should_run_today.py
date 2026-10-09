"""本日(JST)分の出品ファイルが4か国ぶんそろっているか確認する。

使い方:  python scripts/desktop/should_run_today.py
終了コード: 0 = まだ作っていない(実行してよい) / 1 = 本日分はすでに作成済み(実行不要)
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

COUNTRIES = ("SG", "PH", "MY", "TH")
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


def jst_today() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def main() -> int:
    today = jst_today()
    missing = [c for c in COUNTRIES if not (OUTPUT_DIR / f"Shopee_upload_{c}_{today}.xlsx").exists()]
    if not missing:
        print(f"[skip] {today}(JST)分は4か国とも作成済みです。実行しません。")
        return 1
    print(f"[run] {today}(JST)分が未作成です: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
