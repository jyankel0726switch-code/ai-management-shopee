"""
add_shopee_frame.py

Shopee出品用Cover画像に「黄色地＋左上バナー文字＋右上ピンク十字模様＋
左下ピンク斜めストライプ」を自動で加工するスクリプト。

使い方:
    from add_shopee_frame import add_frame
    add_frame("input.jpg", "output.jpg")
    add_frame("input.jpg", "output.jpg", banner_text="Direct From JAPAN")

依存:
    pip install pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ---- デザイン設定 ----
CANVAS_SIZE = 1200                 # 出力画像は正方形(Shopee推奨)
BG_COLOR = (255, 224, 138)         # 背景の黄色
ACCENT_COLOR = (255, 175, 205)     # 十字・ストライプ模様のピンク
BANNER_TEXT_COLOR = (235, 75, 115)  # 左上バナー文字のクリムゾンピンク

# 白い商品写真エリア(左・上に余白を残し、右・下は縁ギリギリまで)
PHOTO_LEFT = 48
PHOTO_TOP = 140
PHOTO_RIGHT = CANVAS_SIZE - 48
PHOTO_BOTTOM = CANVAS_SIZE - 24

# 右上の十字模様ブロック(写真エリアの右・上の余白部分)
CROSS_BLOCK = (PHOTO_RIGHT, 0, CANVAS_SIZE, PHOTO_TOP)
CROSS_SPACING = 34
CROSS_SIZE = 16
CROSS_THICKNESS = 5

# 左下の斜めストライプブロック(写真エリアの左・下の余白部分)
STRIPE_BLOCK = (0, int(CANVAS_SIZE * 0.56), PHOTO_LEFT, CANVAS_SIZE)
STRIPE_WIDTH = 14
STRIPE_GAP = 14


def _draw_cross_pattern(draw: ImageDraw.ImageDraw, box, spacing=CROSS_SPACING):
    """box=(x0,y0,x1,y1) の範囲にピンクの十字模様を敷き詰める"""
    x0, y0, x1, y1 = box
    y = y0 + spacing // 2
    row = 0
    while y < y1:
        offset = (spacing // 2) if row % 2 else 0
        x = x0 + offset
        while x < x1:
            half = CROSS_SIZE // 2
            draw.line([(x - half, y), (x + half, y)], fill=ACCENT_COLOR, width=CROSS_THICKNESS)
            draw.line([(x, y - half), (x, y + half)], fill=ACCENT_COLOR, width=CROSS_THICKNESS)
            x += spacing
        y += spacing
        row += 1


def _draw_diagonal_stripes(draw: ImageDraw.ImageDraw, box, stripe_width=STRIPE_WIDTH, gap=STRIPE_GAP):
    """box=(x0,y0,x1,y1) の範囲にピンクの斜めストライプ模様を敷き詰める(45度)"""
    x0, y0, x1, y1 = box
    span = (x1 - x0) + (y1 - y0)
    period = stripe_width + gap
    offset = -span
    while offset < span:
        # 各ストライプは左下から右上へ向かう平行四辺形として描画
        p1 = (x0 + offset, y1)
        p2 = (x0 + offset + (y1 - y0), y0)
        p3 = (x0 + offset + (y1 - y0) + stripe_width, y0)
        p4 = (x0 + offset + stripe_width, y1)
        draw.polygon([p1, p2, p3, p4], fill=ACCENT_COLOR)
        offset += period


def _load_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def add_frame(input_path: str, output_path: str, banner_text: str = "Direct From JAPAN"):
    """
    input_path の商品画像に、黄色背景＋左上バナー文字＋右上ピンク十字模様＋
    左下ピンク斜めストライプの加工を施し、output_path に保存する。
    """
    base = Image.open(input_path).convert("RGB")

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # 右上: ピンク十字模様
    _draw_cross_pattern(draw, CROSS_BLOCK)

    # 左下: ピンク斜めストライプ(はみ出し防止のためクリップ領域内で描画)
    clip = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BG_COLOR)
    clip_draw = ImageDraw.Draw(clip)
    _draw_diagonal_stripes(clip_draw, STRIPE_BLOCK)
    x0, y0, x1, y1 = STRIPE_BLOCK
    canvas.paste(clip.crop((x0, y0, x1, y1)), (x0, y0))

    # 左上: バナー文字(背景ボックスなし、黄色地に直接テキスト)
    font = _load_font(56)
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 22), banner_text, fill=BANNER_TEXT_COLOR, font=font)

    # 中央〜右下: 白い商品写真エリア(アスペクト比維持・余白は白)
    photo_w = PHOTO_RIGHT - PHOTO_LEFT
    photo_h = PHOTO_BOTTOM - PHOTO_TOP
    white_bg = Image.new("RGB", (photo_w, photo_h), (255, 255, 255))

    ratio = min(photo_w / base.width, photo_h / base.height)
    new_w, new_h = int(base.width * ratio), int(base.height * ratio)
    resized = base.resize((new_w, new_h), Image.LANCZOS)
    paste_x = (photo_w - new_w) // 2
    paste_y = (photo_h - new_h) // 2
    white_bg.paste(resized, (paste_x, paste_y))
    canvas.paste(white_bg, (PHOTO_LEFT, PHOTO_TOP))

    canvas.save(output_path, quality=92)
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python add_shopee_frame.py <input> <output> [banner_text]")
        sys.exit(1)
    banner = sys.argv[3] if len(sys.argv) > 3 else "Direct From JAPAN"
    add_frame(sys.argv[1], sys.argv[2], banner)
    print(f"Saved: {sys.argv[2]}")
