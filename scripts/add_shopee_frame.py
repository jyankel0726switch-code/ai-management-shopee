"""
add_shopee_frame.py

これまでCanvaで手作業していた「黄色の枠＋ピンクの十字模様＋
'Direct From JAPAN'バナー」のフレーム加工を自動化するスクリプト。

使い方:
    python add_shopee_frame.py 入力画像.jpg 出力画像.jpg
    python add_shopee_frame.py 入力画像.jpg 出力画像.jpg --text "Direct From JAPAN"

shopee-listing-uploadスキルに組み込む場合:
    from add_shopee_frame import add_frame
    add_frame("amazon_cover_downloaded.jpg", f"framed-images/{asin}_cover.jpg")
"""

import argparse
from PIL import Image, ImageDraw, ImageFont

# ---- サンプル画像から実測した比率（1080x1080基準） ----
BORDER_COLOR = (255, 228, 148)   # #FFE494 黄色い枠
CROSS_COLOR = (255, 173, 244)    # #FFADF4 ピンクの十字
TEXT_COLOR = (255, 83, 125)      # #FF537D バナー文字

# 枠の太さ（画像幅に対する比率。1080px基準で 左右46px・上74px・下55px）
LEFT_RATIO = 46 / 1080
RIGHT_RATIO = 45 / 1080
TOP_RATIO = 74 / 1080
BOTTOM_RATIO = 55 / 1080

# 十字パターン（右側の枠内、上から約20%の高さまで繰り返し）
CROSS_SPACING_RATIO = 32 / 1080      # 十字の縦の間隔
CROSS_ARM_RATIO = 11 / 1080          # 十字の腕の半径
CROSS_THICKNESS_RATIO = 4 / 1080     # 十字の線の太さ
CROSS_ZONE_HEIGHT_RATIO = 213 / 1080  # 十字模様が入る縦方向の範囲

# バナー文字
TEXT_LEFT_MARGIN_RATIO = 54 / 1080
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _draw_cross(draw, cx, cy, arm, thickness, color):
    draw.line([(cx - arm, cy), (cx + arm, cy)], fill=color, width=thickness)
    draw.line([(cx, cy - arm), (cx, cy + arm)], fill=color, width=thickness)


def add_frame(input_path: str, output_path: str, text: str = "Direct From JAPAN") -> None:
    photo = Image.open(input_path).convert("RGB")
    w, h = photo.size

    left = round(w * LEFT_RATIO)
    right = round(w * RIGHT_RATIO)
    top = round(w * TOP_RATIO)
    bottom = round(w * BOTTOM_RATIO)

    out_w, out_h = w + left + right, h + top + bottom
    canvas = Image.new("RGB", (out_w, out_h), BORDER_COLOR)
    canvas.paste(photo, (left, top))
    draw = ImageDraw.Draw(canvas)

    # --- 右側の十字模様（元画像の実測パターンを再現） ---
    arm = max(3, round(w * CROSS_ARM_RATIO))
    thickness = max(2, round(w * CROSS_THICKNESS_RATIO))
    spacing = max(10, round(w * CROSS_SPACING_RATIO))
    zone_height = round(w * CROSS_ZONE_HEIGHT_RATIO)

    inner_x = out_w - right + round(right * 0.2)   # 枠の内側寄りの列
    outer_x = out_w - round(right * 0.15)           # 枠の外側寄りの列
    y = arm + 2
    while y < zone_height:
        _draw_cross(draw, inner_x, y, arm, thickness, CROSS_COLOR)
        _draw_cross(draw, outer_x, y, arm, thickness, CROSS_COLOR)
        y += spacing

    # --- 上部バナー文字 ---
    font_size = max(18, round(top * 0.52))
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except OSError:
        font = ImageFont.load_default()
    text_x = round(w * TEXT_LEFT_MARGIN_RATIO)
    text_y = round(top * 0.18)
    draw.text((text_x, text_y), text, fill=TEXT_COLOR, font=font)

    canvas.save(output_path, quality=92)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--text", default="Direct From JAPAN")
    args = parser.parse_args()
    add_frame(args.input, args.output, args.text)
    print(f"saved: {args.output}")
