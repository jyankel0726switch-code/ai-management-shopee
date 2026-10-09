# Windows PC で出品ファイル作成を動かす手順(初心者向け)

クラウド版では Amazon が「アメリカからのアクセス」と判定して価格・在庫が読めませんでした。
自分のPC(日本)で動かすと、この問題が起きません。

## 0. 用意するもの(最初の1回だけ)
1. **Claude Code デスクトップ**(インストール済みならそのまま)
2. **Git for Windows**(https://git-scm.com/download/win)… 「次へ」を押し続けてOK
3. **Python**(https://www.python.org/downloads/)… インストール画面で **「Add python.exe to PATH」にチェック** を入れる
4. **Chrome に「Claude in Chrome」拡張機能** を入れ、Claude にログインする

## 1. リポジトリをPCに取り込む
1. 「スタート」→「PowerShell」を開く
2. 次を1行ずつ実行(`C:\work` は好きな場所でよい)
   ```
   mkdir C:\work
   cd C:\work
   git clone https://github.com/jyankel0726switch-code/ai-management-shopee.git
   cd ai-management-shopee
   pip install pillow openpyxl
   ```

## 2. Claude Code デスクトップで開く
1. Claude Code デスクトップを起動し、フォルダ `C:\work\ai-management-shopee` を開く
2. コネクタ(Google Drive / Google Sheets)が使えるか確認する(使えなければ設定→コネクタで接続)

## 3. まず手動で1回動かす(ここが一番大事)
Chrome を開いた状態で、Claude に次のように送る。
> shopee-listing-upload スキルを使って、本日分の出品ファイルを作成して。DESKTOP.md に従って。

- Amazon のページが開いて、価格と在庫が読めれば成功。
- 「アメリカ合衆国にお届け」と出たら、Amazon のお届け先を日本の住所に変える。
- 結果の xlsx は `output` フォルダに保存される。

## 4. PCを起動したら自動で実行する(任意)
手動で成功してから設定する。
1. PowerShell で次を実行
   ```
   cd C:\work\ai-management-shopee
   powershell -ExecutionPolicy Bypass -File scripts\desktop\register_logon_task.ps1
   ```
2. 「スタート」→「タスクスケジューラ」を開き、`ShopeeDailyListing` を右クリック→「実行」で試す。
- ログオンの2分後に実行される。**本日分が作成済みなら何もしない**(1日1回だけ)。
- やめるとき: `Unregister-ScheduledTask -TaskName "ShopeeDailyListing" -Confirm:$false`
- 自動実行では、Chrome を開いていないと Amazon を読めない可能性がある。うまくいかなければ、手動(手順3)のほうが確実。
- ※ このタスクの登録スクリプトは、作成者の環境では未テスト。

## 困ったとき
- `python` が見つからない → Python を入れ直し、「Add python.exe to PATH」にチェック
- Amazon でボット確認(画像の選択など)が出る → 画面で自分で解いてから続きを依頼
- push できない → `git config --global user.name` / `user.email` を設定し、GitHub にログイン
