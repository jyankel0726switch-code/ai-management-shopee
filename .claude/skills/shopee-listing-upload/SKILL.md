---
name: shopee-listing-upload
description: "shopee-sourcingスキルがGoogle Sheetsに記録した本日分のリサーチ候補商品を読み込み、Shopee一括出品テンプレート形式に変換して、国ごと(SG/MY/TH/PH等)に出品ファイル(xlsx)を生成する。「出品ファイル作って」「本日の出品ファイル作成」「Shopeeアップロード用ファイル」という依頼で起動する。"
---

# Shopee 出品ファイル生成

## 目的

`shopee-sourcing`スキルがGoogle Sheetsに記録した本日分の商品リサーチ結果を読み込み、
Shopeeの一括出品用テンプレート(`template/fixed_template.xlsx`)の形式に変換して、
国ごとに出品ファイル(xlsx)を生成する。

このスキルは`shopee-sourcing`の**後工程**にあたる。先にリサーチが実行され、
Google Sheetsに当日分のデータが記録済みであることを前提とする。

## 入力

- Google Sheets(shopee-sourcingスキルが書き込んでいるシート)
  列構成: 日付 / 国 / Shopee商品名 / Shopee価格 / Shopeeリンク / トレンド根拠 /
          Amazon商品名 / ASIN / Amazon価格 / Amazonリンク / 出品者数目安 / メモ
- `template/fixed_template.xlsx`(Shopee公式の一括出品テンプレート・基本版。ヘッダー構成・列順は変更しない)
- `template/Shopee_mass_upload_template_MY.xlsx`(マレーシア専用テンプレート。基本版と列構成が一部異なるため、MY向け出品ファイルは必ずこちらを使う)
- `pricing_calc.py`(価格計算ロジック)

### 国別テンプレートの使い分け

Shopeeは国ごとに配送チャネル列や価格倍率上限、商品名の文字数制限などが異なる
専用テンプレートを配布している場合がある。

| 国 | 使用テンプレート | 主な違い |
|---|---|---|
| MY | `template/Shopee_mass_upload_template_MY.xlsx` | 配送チャネル列が「Doorstep Delivery - Japan」「SPX Express Lockers (Overseas)」の2列。価格倍率上限7倍(基本版は5倍)。商品名は10〜255文字 |
| SG | `template/Shopee_mass_upload_template_SG.xlsx` | 配送チャネル列が4列(Doorstep Delivery/5-Day Delivery/Collection Points/SPX Express Lockers)。商品名は10〜255文字。価格0.10〜999999.00 |
| TH | `template/Shopee_mass_upload_template_TH.xlsx` | 配送チャネル列が「International Express (Japan)」の1列。商品名は20〜255文字。価格1〜500000 |
| PH | `template/Shopee_mass_upload_template_PH.xlsx` | 配送チャネル列が「Standard International」の1列。商品名は20〜255文字。価格5〜100000 |
| その他(VN/TW/BR) | `template/fixed_template.xlsx`(基本版) | 専用テンプレート未入手。入手次第追加する |

他国の専用テンプレートが提供された場合も、同様に`template/`配下に追加し、
この表を更新すること。基本版と列数・列順が異なる場合があるため、
書き込み前に必ずヘッダー行(1〜3行目)を確認してから該当列にマッピングする。

## 処理手順

### 1. 当日分の対象行を取得
Google Sheetsから「日付」列が本日日付の行を取得する。

### 2. 国ごとにグループ化
対応国: SG / MY / TH / PH / VN / TW / BR。未対応の国コードはエラーリストに記録し、
その行はスキップする。

### 3. 価格算出
`pricing_calc.py`の`calc_local_price()`を使用する。

- 原価(JPY) = 「Amazon価格」列の値
- 想定国内送料: 200円
- 利益率: 50%
- 計算根拠: http://calc.shopee-academy.jp/ の為替・手数料表(2026-08-01時点)を反映。
  数%の誤差は許容前提。相場が動いたら本ページを再取得して`pricing_calc.py`を更新する。
- 「Shopee価格」列がすでに具体的な数値で確定している場合は、そちらを優先し
  自動計算値で上書きしない(「未取得」等のプレースホルダの場合のみ自動計算する)。

### 4. 商品タイトル・商品説明の草案作成

「Shopee商品名」「Amazon商品名」「ASIN」「トレンド根拠」を元に、クレイトン・メイクピース
(著名なダイレクトレスポンス・コピーライター)のペルソナで、SEOと購買喚起を意識した
**オリジナルな**商品タイトル・商品説明文を新規に英語で執筆する。Amazon商品ページの
説明文・レビュー文をそのまま転記・要約転載しない。

#### 4-1. 商品タイトルの生成

「ASIN」から商品内容を判断し、Shopeeの検索上位を狙えるベストな商品タイトルを作成する。

- 英語で作成する
- スペースを含め90文字以内に収める
- 商品に関するビッグワード(検索されやすい一般語)を含める
- "JAPAN"を含める
- 以下の単語をタイトルに含めない:
  Hemp, GABA, Gamma-Aminobutyric, Ryukakusan, ZIPPO, CBD, Poppy, seed, Papaver,
  Azelaic, Minoxidil, Dior, Chanel, Nike, Adidas, Amazon, Shark fin, slingshot, Gambir
- サイズ・容量・重量の情報はタイトルに含めない

#### 4-2. 商品説明文の生成

商品タイトル・「Amazon商品名」「トレンド根拠」を踏まえ、英語で商品説明文を作成する。

- 説明文の冒頭に、疑問文形式のプロモーション用キャッチコピーを入れる
- 商品の機能を説明する
- 以下の単語を説明文中で使用しない:
  Hemp, GABA, Gamma-Aminobutyric, Ryukakusan, ZIPPO, CBD, Poppy, seed, Papaver,
  Azelaic, Minoxidil, Dior, Chanel, Nike, Adidas, Amazon, Shark fin, slingshot, Gambir
- 分かる場合は商品のサイズ・容量を説明する
- USP(独自の強み)を重点的に説明する
- 説明文は1500文字以内に収める
- 発送情報を記載する: 注文から発送まで3〜5営業日、注文からお届けまで1〜2週間程度、
  商品は日本から発送する旨
- 説明文の最後にJANコードを記載する(詳細は下記「JANコードの追記」ルールに従う)

**JANコードの追記**: 説明文の最後に、改行して「JAN: {JANコード}」の形式で追記する。
- 「ASIN」列の値をもとに、JAN⇔ASIN変換サービス(jan2asin.kozo.info)のAPIでJANコードを調査する:
  `GET https://jan2asin.kozo.info/api/v1/asin/{ASIN}`
  レスポンスJSONの `found` が `true` の場合、`jan` の値をJANコードとして採用する。
- レート制限(1IPあたり1分間20リクエストまで)に注意し、商品ごとに順番に問い合わせる。
  超過時(HTTP 429)は少し間隔をあけて再試行する。
- `found` が `false`、またはAPIに接続できない場合は、必ず固定のプレースホルダー
  「JAN: 0000000000000(仮)」を記載し、要確認フラグを立てる。
- このサービスは非公式のデータベースであり、正確性・完全性は保証されていない。
  取得したJANコードは参考情報として扱う。
- 実在しそうな13桁の数字をそれらしく生成・推測してはならない(他社の実在商品の
  JANコードと偶然一致し得るため)。API上見つからない場合は必ず上記の固定プレースホルダー
  のみを使う。

### 5. 商品画像(仮画像)の生成
商品名・特徴からAI画像生成で仮のカバー画像を作成する。
Amazon商品画像の複製・トレースは行わない。ファイル名に`_DRAFT`を付け、
「仮画像・公開前に差し替え必須」であることをレポートに明記する。
※画像生成MCPの接続が別途必要(未接続の場合はこのステップをスキップし、
画像URL欄は空欄で出力してレポートに記載する)。

### 6. 重量・サイズの仮設定
商品カテゴリから一般的な重量帯を推定し仮値を入力する(要確認フラグ付き)。

### 7. カテゴリIDの推定
商品名からShopeeカテゴリツリーに近いカテゴリIDを推定する。確信度が低ければ
空欄のまま要確認フラグを立てる。

### 8. テンプレートへの書き込み
国別テンプレートの使い分け表に従い、該当する`template/*.xlsx`をコピーし、
Templateシートの4行目以降に1商品1行(variationがある場合は複数行)で書き込む。
ヘッダー行(1〜3行目)・シート名・列順は変更しない。

**SKU列**: Google Sheetsの「ASIN」列の値をそのままSKU列に入れる
(全国共通のルール)。ASINが空の商品は、SKU列も空欄のままにし要確認フラグを立てる。

**Parent SKU列**: SKU列と同様に、Google Sheetsの「ASIN」列の値をそのまま
Parent SKU列に入れる(全国共通のルール)。従来の自動採番形式(例: MY-20260802-01)
は使用しない。ASINが空の商品は、Parent SKU列も空欄のままにし要確認フラグを立てる。

### 9. 出力
- ファイル名: `Shopee_upload_{国コード}_{YYYY-MM-DD}.xlsx`
- 保存先: Google Driveの指定フォルダ
- 国ごとに、その国の商品行のみを含める

### 10. サマリーレポート
生成件数、要確認フラグの件数・内訳(JANコードにプレースホルダー
「JAN: 0000000000000(仮)」を使用した件数を含む)、処理できなかった行を報告する。

## 絶対に守ること

- Amazon商品ページの画像・説明文をそのまま複製・転載しない。
- ASINからJANコードを調査する際、jan2asin.kozo.infoのデータは無保証の非公式データである
  ことを踏まえ、取得結果を鵜呑みにせず「参考情報」として扱う。
- 「要確認」フラグが立った項目(仮画像・仮重量・推定カテゴリ・自動計算価格)を含む
  商品は、人による最終確認前にShopeeへ実際にアップロードしない。
  このスキルは「出品ファイルの下書き作成」までを担当する。
