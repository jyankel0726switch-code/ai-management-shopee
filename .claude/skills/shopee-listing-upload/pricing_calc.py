"""
Shopee 現地販売価格 計算スクリプト
参照元: http://calc.shopee-academy.jp/ (為替・手数料表, 2026-08-01時点)
式: 売価(現地通貨) = { (原価+送料) / (1 - 手数料率合計 - 利益率) - 固定手数料(円換算) } / 為替レート

※ PH/MY/TH/VNの上限付き%手数料・1件固定手数料は簡略化して反映。
  実際のcalc.shopee-academy.jpとは数%の誤差が生じ得る前提で運用。
  レート・手数料率は変更されるため、定期的に本ページを再取得して更新すること。
"""

DOMESTIC_SHIPPING_JPY = 200      # 想定国内送料
MARGIN_RATE = 0.50               # 利益率 50%

# 2026-08-01 時点の参考値。運用時は calc.shopee-academy.jp を再取得して更新する。
FX_RATES = {
    "SG": 123.6858,  # 1 SGD = ? JPY
    "TW": 4.9145,    # 1 TWD
    "MY": 38.9029,   # 1 MYR
    "TH": 4.7522,    # 1 THB
    "PH": 2.595,     # 1 PHP
    "VN": 0.006,     # 1 VND
    "BR": 31.3765,   # 1 BRL
}

# 手数料率合計(販売手数料+決済手数料+その他%手数料)。上限付き手数料は上限より低く出やすいため、
# 保守的に「上限に達した場合の率」を採用(誤差数%は許容前提)。
FEE_RATE = {
    "SG": 0.1375 + 0.0300,                     # 16.75%
    "TW": 0.1275 + 0.0250 + 0.0300,             # 18.25% (CCB込み)
    "MY": 0.1917 + 0.0378,                      # 22.95%
    "TH": 0.2113 + 0.0321,                      # 24.34%
    "PH": 0.1073 + 0.0224 + 0.0336 + 0.0300 + 0.0560,  # 24.93%
    "VN": 0.1600 + 0.0600 + 0.0216,             # 24.16%
    "BR": 0.1375 + 0.0200,                      # 15.75%
}

# 1件あたり固定手数料(現地通貨)。円換算して式に加算する。
FIXED_FEE_LOCAL = {
    "SG": 0.0,
    "TW": 0.0,
    "MY": 0.5,      # MYR/件
    "TH": 1.07,     # THB/件
    "PH": 5.0,      # PHP/件
    "VN": 3000.0,   # VND/件
    "BR": 0.0,
}


def calc_local_price(cost_jpy: float, country: str,
                      domestic_shipping_jpy: float = DOMESTIC_SHIPPING_JPY,
                      margin_rate: float = MARGIN_RATE) -> dict:
    """商品原価(JPY)から、指定国の推奨現地販売価格を計算する"""
    if country not in FX_RATES:
        raise ValueError(f"未対応の国コード: {country}")

    fx = FX_RATES[country]
    fee_rate = FEE_RATE[country]
    fixed_fee_jpy = FIXED_FEE_LOCAL[country] * fx

    base_cost = cost_jpy + domestic_shipping_jpy
    denom = 1 - fee_rate - margin_rate
    if denom <= 0:
        raise ValueError(
            f"{country}: 手数料率+利益率が100%を超えています(要見直し)"
        )

    price_jpy = base_cost / denom + fixed_fee_jpy
    price_local = price_jpy / fx

    return {
        "country": country,
        "cost_jpy": cost_jpy,
        "domestic_shipping_jpy": domestic_shipping_jpy,
        "margin_rate": margin_rate,
        "fee_rate": fee_rate,
        "fx_rate": fx,
        "price_local": round(price_local, 2),
        "price_jpy_equivalent": round(price_jpy, 0),
    }


if __name__ == "__main__":
    # 動作確認用サンプル(原価1,000円の場合)
    for c in FX_RATES:
        result = calc_local_price(1000, c)
        print(f"{c}: {result['price_local']} (現地通貨) "
              f"/ 換算 {result['price_jpy_equivalent']} 円相当")
