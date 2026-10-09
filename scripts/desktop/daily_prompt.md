shopee-listing-uploadスキルを使って、本日(JST)分の Shopee 出品ファイルを作成してください。
.claude/skills/shopee-listing-upload/SKILL.md と、同じフォルダの DESKTOP.md(デスクトップ版の差分)に従うこと。

最初に `python scripts/desktop/should_run_today.py` を実行し、終了コードが 1 なら「本日分は作成済み」と報告して終了する。

- Google Sheets「トレンドリサーチ」(spreadsheet_id: 1dCWFhLZFphcjpvqsGb4H5gC6OcO805ML322pnxpURBg)の本日の曜日タブと「毎日アニメ」タブから、更新日時が本日(JST)の行を使う。
- Amazon の商品ページは Claude in Chrome(このPCの Chrome)で開いて読み取る。
- 生成した4ファイルは output/ フォルダに保存する。
- 最後にサマリーレポート(生成件数・要確認フラグの内訳・除外商品と理由)を報告する。
