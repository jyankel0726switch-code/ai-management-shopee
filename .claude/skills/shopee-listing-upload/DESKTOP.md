# デスクトップ版(Windows PC)で実行する場合の差分

クラウド版の SKILL.md との違いだけをここに書く。ここに書いていない部分は SKILL.md のとおり。

## 実行場所と日付
- このPC(日本)で実行する。日付・曜日は引き続き **JST** で判定する。
- 実行の最初に `python scripts/desktop/should_run_today.py` を実行する。終了コード 1(本日分が4か国とも作成済み)なら、何もせず「作成済み」と報告して終了する。

## Amazon 商品ページの読み取り(SKILL.md の Playwright / Composio ブラウザの代わり)
- **Claude in Chrome** で `https://www.amazon.co.jp/dp/{ASIN}` を開く。このPCの日本のネットワークなので、価格・在庫・配送日が通常どおり表示される。
- 読み取る項目はクラウド版と同じ(在庫表示・価格・JAN・重量・寸法・商品画像URL最大7枚・バリエーション選択肢)。
- 「アメリカ合衆国にお届け」と表示された場合は、お届け先が日本になっていない。日本の住所(郵便番号)に切り替えてから読み直す。切り替えられなければ、その商品は「要確認:Amazon地域誤判定」とする。
- ボット確認(CAPTCHA)が出たら処理を止めて、ユーザーに画面で解いてもらう。自動で突破しようとしない。
- 取得できない項目は推測しない(JANは固定プレースホルダー、重量・寸法は仮値+要確認、はクラウド版と同じ)。

## 保存先
- 生成した xlsx は、リポジトリ直下の `output/` フォルダに保存する(git の管理対象外)。ファイル名は `Shopee_upload_{国コード}_{YYYY-MM-DD}.xlsx`。
- Google Drive への自動アップロードは行わない(クラウド版と同じ)。

## Cover画像のフレーム加工(5.6)
- クラウド版と同じ手順。このPCで `scripts/add_shopee_frame.py` を実行し、`claude/framed-images-{JST日付}` ブランチに画像だけをコミットして push、PRを作る。
- GitHub への push は、このPCの GitHub ログイン(Git for Windows / GitHub Desktop の認証)を使う。
- push やPR作成ができない場合は、元のAmazon画像URLを使い「要確認:フレーム加工未実施」と報告する(クラウド版と同じ)。

## 必要なもの(Python)
`pip install pillow openpyxl`
