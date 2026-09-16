# -*- coding: utf-8 -*-
"""2026-09-16 (JST) 分の対象商品。
出典: Google Sheets「トレンドリサーチ」水曜タブ 2026-09-16 06:12 の行 →
      Amazon.co.jp 検索 (COMPOSIO_SEARCH_AMAZON, amazon.co.jp) → 商品ページ実読み取り。
価格・在庫・JAN・重量・寸法は商品ページに表示されていた値のみを記録し、
取得できなかった項目は None として要確認フラグを立てる(推測値は入れない)。
"""

CAT_ANIME = 101392   # Hobbies & Collections/Collectible Items/Anime & Manga Collectibles
CAT_ACTION = 101385  # Hobbies & Collections/Collectible Items/Action Figurines

# 取得できなかった重量・寸法に使う一般的な仮値(要確認フラグ対象)
EST_WEIGHT, EST_DIMS = 0.40, (15, 12, 20)

PRODUCTS = [
 # ---- SG ----
 dict(cc="SG", asin="B0CPDVGX5B", cost_jpy=5800, stock=1, category=CAT_ANIME,
      jp_title="POP UP PARADE STREET FIGHTER 6 春麗 SF6 Ver.",
      sheet_row="バンプレスト Grandista『ストリートファイター』春麗",
      avail="残り1点 ご注文はお早めに", jan=None, weight=None, dims=None),
 dict(cc="SG", asin="B0DCBK599S", cost_jpy=5980, stock=3, category=CAT_ACTION,
      jp_title="ねんどろいど アズールレーン フォーミダブル 軽装Ver.",
      sheet_row="Alter『アズールレーン』ニューオリンズ / WAVE『アズールレーン』アタゴ",
      avail="残り3点 ご注文はお早めに", jan="4580416927918", weight=0.25, dims=(5, 6, 10)),
 dict(cc="SG", asin="B09TK1HH6G", cost_jpy=7030, stock=1, category=CAT_ANIME,
      jp_title="ホロライブ #hololive IF Relax time 白上フブキ フィギュア バンプレスト",
      sheet_row="グッドスマイル figma 白上フブキ",
      avail="残り1点 ご注文はお早めに", jan=None, weight=None, dims=None),
 # ---- PH ----
 dict(cc="PH", asin="B0DY2PG486", cost_jpy=3300, stock=2, category=CAT_ANIME,
      jp_title="ストリートファイター6 ちょこのせ プレミアムフィギュア 春麗",
      sheet_row="バンプレスト Grandista『ストリートファイター』春麗",
      avail="残り2点 ご注文はお早めに", jan=None, weight=None, dims=(7.6, 15.2, 10.2)),
 dict(cc="PH", asin="B0F27VRKMG", cost_jpy=3780, stock=6, category=CAT_ANIME,
      jp_title="ファプタ フィギュア Coreful メイドインアビス 烈日の黄金郷",
      sheet_row="タイトー Coreful『メイドインアビス 烈日の黄金郷』ファプタ",
      avail="残り6点 ご注文はお早めに", jan=None, weight=None, dims=(13, 11, 20)),
 dict(cc="PH", asin="B0DW8HZR56", cost_jpy=5842, stock=2, category=CAT_ANIME,
      jp_title="星のカービィ SwingKirby ティンクルトラベラー",
      sheet_row="星のカービィ お座りぬいぐるみマスコット2",
      avail="残り2点（入荷予定あり）", jan="4521121208657", weight=0.11, dims=(21.5, 14.5, 13.5),
      note="Amazon表記は「0.25 ポンド」。kg換算 0.11kg で記載したが、箱サイズに対し軽すぎるため要確認。"),
 # ---- MY ----
 dict(cc="MY", asin="B0BWVN6RVY", cost_jpy=6580, stock=2, category=CAT_ANIME,
      jp_title="チェンソーマン ちょこのせ プレミアムフィギュア デンジ",
      sheet_row="バンプレスト グリグラ『チェンソーマン』デンジ(私服Ver.)",
      avail="残り2点 ご注文はお早めに", jan=None, weight=None, dims=None),
 dict(cc="MY", asin="B0F9DBGV4P", cost_jpy=5940, stock=14, category=CAT_ANIME,
      jp_title="ミートス(Myethos) Gift+ アズールレーン エンタープライズ ウィンド・キャッチャー",
      sheet_row="Alter『アズールレーン』ニューオリンズ / WAVE『アズールレーン』アタゴ",
      avail="残り14点 ご注文はお早めに", jan=None, weight=None, dims=(10, 10, 23)),
 dict(cc="MY", asin="B0CX12KCGQ", cost_jpy=3800, stock=1, category=CAT_ACTION,
      jp_title="壽屋(KOTOBUKIYA) フレームアームズ・ガール アーキテクト Black Ver.",
      sheet_row="コトブキヤ フレームアームズ・ガール ミヅキ School Swimsuits Ver.",
      avail="残り1点 ご注文はお早めに", jan=None, weight=0.37, dims=(10, 10, 15)),
 # ---- TH ----
 dict(cc="TH", asin="B0BM43SSXY", cost_jpy=3700, stock=2, category=CAT_ANIME,
      jp_title="セガ チェンソーマン Luminasta チェンソーの悪魔",
      sheet_row="セガプライズ 2026年10月新作(Grandista等)",
      avail="残り2点 ご注文はお早めに", jan=None, weight=None, dims=None),
 dict(cc="TH", asin="B0DK7MXCZ2", cost_jpy=8600, stock=1, category=CAT_ANIME,
      jp_title="TENITOL TALL オーバーロード シャルティア 完成品フィギュア",
      sheet_row="ユニオンクリエイティブ『オーバーロード』シズ・デルタ",
      avail="残り1点 ご注文はお早めに", jan="4580736407114", weight=0.661, dims=(33, 25.4, 20.3)),
 dict(cc="TH", asin="B0GGNWHPRL", cost_jpy=3670, stock=4, category=CAT_ANIME,
      jp_title="ホロライブプロダクション ひっかけフィギュア Vol.8 白上フブキ",
      sheet_row="グッドスマイル figma 白上フブキ",
      avail="残り4点 ご注文はお早めに", jan=None, weight=None, dims=(10, 10, 10)),
]

# 在庫なし・予約のみで今回除外した商品(レポート用)
EXCLUDED = [
 dict(asin="B0H8GFZXZT", jp_title="Grandista 春麗（Outfit2）", reason="商品ページが「ただいま予約受付中です」(予約のみ・在庫なし)のため除外"),
 dict(asin="B0BXB8FB8X", jp_title="バンプレスト チェンソーマン Break time collection vol.1 デンジ＆ポチタ",
      reason="色バリエーション(ホワイト/赤)ありだが各色の個別ASINを確実に取得できず、「要確認:バリエーション検出不十分」として除外"),
]
