---
name: shopee-listing-upload
description: "shopee-sourcingスキルがGoogle Sheetsに記録した本日分のリサーチ候補商品、または人が直接指定したAmazon ASINを読み込み、Shopee一括出品テンプレート形式に変換して、国ごと(SG/MY/TH/PH等)に出品ファイル(xlsx)を生成する。「出品ファイル作って」「本日の出品ファイル作成」「Shopeeアップロード用ファイル」「このASINで出品ファイル作って」という依頼で起動する。"
---

# Shopee 出品ファイル生成

## 目的

以下いずれかの方法で対象商品を集め、Shopeeの一括出品用テンプレートの形式に変換して、
国ごとに出品ファイル(xlsx)を生成する。

- **A. 日次リサーチ経由**: `shopee-sourcing`スキルがGoogle Sheetsに記録した本日分の商品リサーチ結果を読み込む(このスキルの従来の後工程モード)
- **B. ASIN直接投入**: 人がAmazon ASIN(1件〜複数件)と対象国を直接指定する(新規追加モード)

いずれのモードでも、4〜10のテンプレート生成ロジックは共通。

## 起動モードの判定

- 「本日の出品ファイル作成」「出品ファイル作って」など日付・当日を前提にした依頼 → **A. 日次リサーチ経由**
- 「この ASIN で出品ファイル作って」「B0XXXXXXXX を SG 向けに出品したい」のように
  ASINコードが依頼文中に明示されている場合 → **B. ASIN直接投入**
- 両方の要素が混在する場合(例:「今日の分に加えてこのASINも」)は、両モードの対象行を
  合算してから4以降の処理を行う。

## 日付・タイムゾーンに関する重要ルール

本スキル内で「今日」「本日」「当日」を判定する際は、**必ず日本時間（JST, UTC+9）を基準とすること**。

実行環境のシステム時刻やツールが返す日時がUTC等JST以外のタイムゾーンである場合でも、そのまま使わず、必ずJSTに変換してから「今日の日付」を求めること（例：UTCの日時に9時間を加算してJSTの日付を算出する）。特に日本時間の深夜0時〜早朝9時台に実行される場合、UTCとJSTで日付が1日ズレるため注意が必要（このズレにより、実際にはJSTで本日分のGoogle Sheets行が存在するにもかかわらず、UTC基準では前日と誤認識し、本日分の行を取得できない、または前日分を「本日分」として誤って処理してしまう不具合が過去に発生した）。

モードAでGoogle Sheetsから「日付」列が本日日付の行を抽出する際（後述「入力」「1. 対象行を取得」）、および出力ファイル名`Shopee_upload_{国コード}_{YYYY-MM-DD}.xlsx`の日付を決定する際（後述「10. 出力」）は、いずれも上記ルールに従い**JSTの日付**を用いること。UTC基準で判定しないこと。

## ASINの有効性確認に関する重要ルール

Amazon商品情報をGoogle Sheets等に記録する前に、必ず以下を確認すること。

- 記録しようとしているASINについて、`https://www.amazon.co.jp/dp/{ASIN}` に実際にアクセスし、商品ページが正常に表示されることを確認する。
- 「お探しの商品が見つかりません」「現在このページは利用できません」等のエラーページが表示された場合、そのASINは無効（廃止・統合済み等）とみなし、記録してはならない。
- ページ内で別のASINにリダイレクトされた場合は、リダイレクト後の実際のURLに含まれるASINを正として記録する。当初アクセスしようとしたASINをそのまま記録してはならない。
- 本セッション環境（海外IP等）からのアクセスによりページ内容やリダイレクト挙動が日本国内からのアクセスと異なる可能性がある場合は、メモ欄にその旨を明記し、出品前の人手確認を促す一文を残す。

## 入力

### モードA: 日次リサーチ経由

- Google Sheets(shopee-sourcingスキルが書き込んでいるシート)
  列構成: 日付 / 国 / Shopee商品名 / Shopee価格 / Shopeeリンク / トレンド根拠 /
          Amazon商品名 / ASIN / Amazon価格 / Amazonリンク / 出品者数目安 / メモ
- Google Sheetsから「日付」列が本日日付(**JST基準**。上記「日付・タイムゾーンに関する重要ルール」参照)の行を取得する。

### モードB: ASIN直接投入

- 人から提示されたASINのリスト(例: `B006OIZPGG, B009HQZW6K`)と対象国(例: `SG`。
  未指定の場合は対応国すべて(SG/MY/TH/PH/VN/TW/BR)に展開せず、必ず対象国を確認してから進める)。
- ASINごとにAmazon.co.jpの商品ページ(`https://www.amazon.co.jp/dp/{ASIN}`)を実際にFetchし、
  以下を読み取る(API・スクレイピングツールは使わず、`amazon-stock-check`スキルと同じ方式で
  ページを直接読む):
  - 商品名(原題。そのままコピーはせず4-1でのタイトル生成の参考情報として使う)
  - 価格(JPY)。取得できない場合は要確認フラグを立てて空欄扱いにする
  - 在庫有無の表示。在庫なしと判断した場合はその旨をレポートし、その商品は
    出品ファイル生成の対象から除外する(在庫が不明瞭な場合は要確認フラグを立てて続行する)
  - 商品カテゴリの手がかり(パンくずリスト等)
  - トレンド根拠にあたる情報はないため、この項目は空欄とする
- 取得した情報を、モードAと同じ内部フォーマット(日付/国/Shopee商品名/Shopee価格/
  Shopeeリンク/トレンド根拠/Amazon商品名/ASIN/Amazon価格/Amazonリンク/出品者数目安/メモ)
  に変換してから、4以降の共通処理に渡す。「Shopee価格」は未確定として扱い、3で自動計算する。

### 共通

- `template/Shopee_mass_upload_basic_template.xlsx`
  (Shopee公式の一括出品テンプレート・基本版。2026-08-11時点でダウンロードした最新版。
  ヘッダー構成・列順は変更しない。詳細な列定義は下記「基本テンプレートの列定義」を参照)
- `template/Shopee_mass_upload_template_MY.xlsx`(マレーシア専用テンプレート。基本版と列構成が一部異なるため、MY向け出品ファイルは必ずこちらを使う)
- `pricing_calc.py`(価格計算ロジック)

### 国別テンプレートの使い分け

Shopeeは国ごとに配送チャネル列や価格倍率上限、商品名の文字数制限などが異なる
専用テンプレートを配布している場合がある。

| 国 | 使用テンプレート | 主な違い |
|---|---|---|
| MY | `template/Shopee_mass_upload_template_MY.xlsx` | 配送チャネル列が「Doorstep Delivery - Japan」「SPX Express Lockers (Overseas)」の2列。価格倍率上限7倍(基本版は5倍)。商品名は10〜255文字 |
| SG | `template/Shopee_mass_upload_template_SG.xlsx` | 配送チャネル列が3列(Doorstep Delivery/Collection Points/SPX Express Lockers)。商品名は10〜255文字。価格0.10〜999999.00(2026-08-20更新: 従来あった「5-Day Delivery」列がShopee側で廃止されたため、最新の公式テンプレートに差し替え済み) |
| TH | `template/Shopee_mass_upload_template_TH.xlsx` | 配送チャネル列が「International Express (Japan)」の1列。商品名は20〜255文字。価格1〜500000 |
| PH | `template/Shopee_mass_upload_template_PH.xlsx` | 配送チャネル列が「Standard International」の1列。商品名は20〜255文字。価格5〜100000 |
| その他(VN/TW/BR) | `template/Shopee_mass_upload_basic_template.xlsx`(基本版) | 専用テンプレート未入手。入手次第追加する |

他国の専用テンプレートが提供された場合も、同様に`template/`配下に追加し、
この表を更新すること。基本版と列数・列順が異なる場合があるため、
書き込み前に必ずヘッダー行(1〜3行目)を確認してから該当列にマッピングする。

### 基本テンプレートの列定義(Shopee_mass_upload_basic_template.xlsx)

`Template`シートは1〜3行目がヘッダー(1行目:内部キー、3行目:表示名)、
4行目以降が必須区分・入力ガイド、実データは**4行目以降**に1商品1行で書き込む
(既存ファイルの4〜6行目はガイド文なので、それを踏まえた上で実データは
必ずガイド行より下の行、またはガイド行を上書きせずデータ専用行として追記する。
既存の運用ではデータは4行目以降に直接書き込んでいるため、その慣習を踏襲する)。

| 列 | 表示名 | 必須区分 | 備考 |
|---|---|---|---|
| A | Category | Optional | 7の「Pre-order DTS Range」シート参照により設定。該当なしなら空欄で要確認フラグ |
| B | Product Name | Mandatory | 4-1で生成 |
| C | Product Description | Mandatory | 4-2で生成(末尾にJANコード) |
| D | Maximum Purchase Quantity | Optional | 空欄でよい |
| E | Max Purchase Qty - Start Date | Conditional Mandatory | 空欄でよい |
| F | Max Purchase Qty - Time Period | Conditional Mandatory | 空欄でよい |
| G | Max Purchase Qty - End Date | Conditional Mandatory | 空欄でよい |
| H | Minimum Purchase Quantity | Optional | 空欄でよい |
| I | Parent SKU | Optional | ASINをそのまま入れる(下記ルール) |
| J | Variation Integration No. | Conditional Mandatory | バリエーションがない商品は空欄 |
| K | Variation Name1 | Conditional Mandatory | バリエーションがない商品は空欄 |
| L | Option for Variation 1 | Conditional Mandatory | 同上 |
| M | Image per Variation | Conditional Mandatory | 同上 |
| N | Variation Name2 | Conditional Mandatory | 同上 |
| O | Option for Variation 2 | Conditional Mandatory | 同上 |
| P | Price | Mandatory | 3で算出 |
| Q | Stock | Conditional Mandatory | 5.5のルールに従って設定(要確認フラグは立てない) |
| R | SKU | Optional | ASINをそのまま入れる(下記ルール) |
| S | Size Chart Template | Conditional Mandatory | 空欄でよい |
| T | Size Chart Image | Conditional Mandatory | 空欄でよい |
| U | Cover image | Optional | 5で取得したAmazon商品ページのメイン画像(取得失敗時は空欄) |
| V〜AC | Item Image 1〜8 | Optional | 同上、未使用なら空欄 |
| AD | Weight | Mandatory | 6で推定 |
| AE | Length | Conditional Mandatory | 6で推定(不明なら要確認フラグを立てて一般的な仮値) |
| AF | Width | Conditional Mandatory | 同上 |
| AG | Height | Conditional Mandatory | 同上 |
| AH | Doorstep Delivery (Overseas) | Conditional Mandatory | On/Off。少なくとも1チャネルはOnにする必要あり(Shopee側の必須ルール) |
| AI | Collection Points (Overseas) | Conditional Mandatory | 同上 |
| AJ | SPX Express Lockers (Overseas) | Conditional Mandatory | 同上 |
| AK | Pre-order DTS | Optional | 空欄でよい(`Pre-order DTS Range`シートに有効値の一覧あり) |
| AL | Fail Reason | — | Shopee側が出力に使う列。書き込み対象外(空欄のまま) |

**配送チャネルのデフォルト方針**: AH/AI/AJの少なくとも1つをOnにしないとShopee側で
アップロードエラーになる。方針が別途指定されない限り、基本版では3チャネルすべて
Onにする(過去の国別テンプレートでの運用にならい、配送手段を絞る必要が出てきたら
このデフォルトを見直す)。

## 処理手順

### 1. 対象行を取得
モードAはGoogle Sheetsから当日分(**JST基準**。上記「日付・タイムゾーンに関する重要ルール」参照)の行、
モードBはASIN直接投入時にAmazon商品ページから取得した情報を、共通フォーマットの行として用意する。

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

「Shopee商品名」「Amazon商品名」「ASIN」「トレンド根拠」(モードBの場合は
Amazon商品ページから読み取った商品名等)を元に、以下のペルソナ・制約条件に従って
**オリジナルな**商品タイトル・商品説明文を新規に英語で執筆する。
Amazon商品ページの説明文・レビュー文をそのまま転記・要約転載しない。

#### ペルソナ

あなたはクレイトン・メイクピースです。

- 感情に訴えかけることを優先し、論理はその後に補強として使う
- USP(独自の売り)を軸に構成する
- 会話的で読者の心を動かす文体を使う
- 定型的・事務的な言い回しは避ける

#### 4-1. 商品タイトルの生成

「ASIN」から商品内容を判断し、商品名を作成する。

##### 制約条件

- タイトルは英語で作成すること
- タイトルの文字数はスペースを含め90文字以内に収めること
- タイトルに商品に関するビッグワードを含めること
- タイトルの最後に「JAPAN」を付けること
- タイトルに以下の単語を含めないこと:
  Hemp, GABA, Gamma-Aminobutyric, Ryukakusan, ZIPPO, CBD, Poppy, seed, Papaver,
  Azelaic, Minoxidil, Dior, Chanel, Nike, Adidas, Amazon, Shark fin, slingshot, Gambir
- タイトルにサイズ・容量・重量情報を乗せないこと
- SEO検索上位を狙えるベストな商品名にすること

#### 4-2. 商品説明文の生成

商品タイトル・「Amazon商品名」「トレンド根拠」を踏まえ、英語で商品説明文を作成する。

##### 制約条件

- 説明文の最初に疑問文でプロモーション用キャッチコピーを入れること
- 商品の機能を説明すること
- 説明文に以下の単語を使わないこと:
  Hemp, GABA, Gamma-Aminobutyric, Ryukakusan, ZIPPO, CBD, Poppy, seed, Papaver,
  Azelaic, Minoxidil, Dior, Chanel, Nike, Adidas, Amazon, Shark fin, slingshot, Gambir
- (わかれば)商品のサイズ、容量を説明すること
- USPに重点を置くこと
- 説明文は1500文字以内に収めること
- 発送について、注文から発送まで3〜5営業日、注文からお届けまで1〜2週間ほどかかることを
  記載すること
- 商品は日本から発送する旨を記載すること
- 説明文の最後にJANコードを記載すること(詳細は下記「JANコードの追記」ルールに従う)

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

#### 4-3. 画像用USPの生成
商品画像に追記するUSPを英語で20文字以内で考える。商品の一番強いUSP(独自の強み)を
短く際立つキャッチコピーとして表現する。このテキストはステップ5の画像生成時に
オーバーレイ候補として使用する。

### 5. カバー画像の取得
対象ASINのAmazon商品ページから、メイン商品画像(最初に表示される商品画像)をダウンロードし、
Cover image欄(U列)にその画像を使用する。
ダウンロードできない場合(画像取得に失敗した、該当ASINが存在しない等)のみ、
画像URL欄は空欄で出力し、要確認フラグを立ててその旨をレポートに記載する。

### 5.5 在庫数の設定
Amazon商品ページに「残り○点」「在庫わずか」等の具体的な残数表示がある場合、その数値を
Stock列の値として採用する。
明確な残数表示がない場合(「在庫あり」のみ等)は、デフォルト値10を使用する。
どちらの場合も「要確認」フラグは立てない(残数表示なしの場合のデフォルト10は正常動作として扱う)。

### 6. 重量・サイズの設定
Amazon商品ページの「商品情報」「詳細情報」「追加情報」欄等に梱包重量・サイズ(縦横高さ)の
記載がある場合、その値をテンプレートの重量欄・Length/Width/Height欄へ入力する。この場合は
要確認フラグを立てない。
Amazon商品ページに記載がない場合のみ、「ASIN」や商品カテゴリから判断できる重量・サイズを
推定し、一般的な仮値を入力した上で要確認フラグを立てる。

### 7. カテゴリIDの設定
`template/Shopee_mass_upload_basic_template.xlsx`内の「Pre-order DTS Range」シート
(A列: Category name、B列: Category ID)を、Shopeeの正式なカテゴリ一覧として使用する。

商品名・商品内容から最も近いCategory nameを同シートから探し、対応するCategory ID(B列)を
Templateシートの該当行のCategory列(A列)に入力する。
判断に迷う場合は、より上位の階層(親カテゴリ)まで絞り込めた時点で、その中から最も近い
末端カテゴリを選ぶ。

明確に対応するカテゴリが見つからない場合のみ、Category列を空欄のままにして
要確認フラグを立てる(推測でIDを入力しない)。

### 8. 配送チャネルの設定
基本テンプレートの場合、AH(Doorstep Delivery)/AI(Collection Points)/AJ(SPX Express
Lockers)の3列に「On」を入れる(上記「配送チャネルのデフォルト方針」を参照)。
国別専用テンプレートを使う場合は、そのテンプレートのチャネル列構成に従う。

### 9. テンプレートへの書き込み
国別テンプレートの使い分け表に従い、該当する`template/*.xlsx`をコピーし、
Templateシートの4行目以降に1商品1行(variationがある場合は複数行)で書き込む。
ヘッダー行(1〜3行目)・シート名・列順は変更しない。
**SKU列**: Google Sheetsの「ASIN」列(またはモードBで指定されたASIN)の値を
そのままSKU列に入れる(全国共通のルール)。ASINが空の商品は、SKU列も空欄のままにし
要確認フラグを立てる。
**Parent SKU列**: SKU列と同様に、ASINの値をそのままParent SKU列に入れる
(全国共通のルール)。従来の自動採番形式(例: MY-20260802-01)は使用しない。
ASINが空の商品は、Parent SKU列も空欄のままにし要確認フラグを立てる。

### 10. 出力
- ファイル名: `Shopee_upload_{国コード}_{YYYY-MM-DD}.xlsx`(YYYY-MM-DDは上記「日付・タイムゾーンに関する重要ルール」に従い**JST基準**の日付とする)
- 保存先: なし（チャット添付のみ）
- 国ごとに、その国の商品行のみを含める
- 保存方法: Google Driveへの自動アップロードは行わない。生成したxlsxファイルはチャット上に添付ファイルとして提示するのみとし、Google Driveへの保存はユーザーが手動で行う。

### 11. サマリーレポート
生成件数、要確認フラグの件数・内訳(JANコードにプレースホルダー
「JAN: 0000000000000(仮)」を使用した件数、在庫なしで除外した件数を含む)、
処理できなかった行を報告する。

## 絶対に守ること

- Amazon商品ページの説明文をそのまま複製・転載しない(商品説明文は4-2のルールに従いオリジナルで執筆する)。カバー画像については、5のルールに従いAmazon商品ページのメイン画像をダウンロードして使用してよい(この用途に限り複製を許可する)。
- ASINからJANコードを調査する際、jan2asin.kozo.infoのデータは無保証の非公式データである
  ことを踏まえ、取得結果を鵜呑みにせず「参考情報」として扱う。
- 「要確認」フラグが立った項目(仮画像・仮重量・推定カテゴリ・自動計算価格)を含む
  商品は、人による最終確認前にShopeeへ実際にアップロードしない。
  このスキルは「出品ファイルの下書き作成」までを担当する。
- モードB(ASIN直接投入)でAmazon商品ページの在庫が「なし」と判明した商品は、
  出品ファイルの対象に含めない。
