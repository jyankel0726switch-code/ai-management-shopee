"""
add_shopee_frame.py

Shopee出品用Cover画像に「黄色背景＋左上ピンク文字＋右上十字模様＋左下斜めストライプ」の
フレームを自動で加工するスクリプト(従来Canvaで手作業していた加工の自動化版)。

2026-09-15更新: デザインを一新(黄色枠+下部バナー方式 → 全面黄色背景+左上テキスト+
右上十字ブロック+左下斜めストライプのリボン方式)。ユーザーから共有された参考画像に
合わせている。バリエーション画像(Image per Variation列)にはこのフレームを使わないこと
(Cover image列のみに使う)。

使い方:
    from add_shopee_frame import add_frame
    add_frame("input.jpg", "output.jpg")
    add_frame("input.jpg", "output.jpg", banner_text="Direct From JAPAN")

依存:
    pip install pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ---- デザイン設定(参考画像に合わせて調整可能) ----
CANVAS_SIZE = 1200
BG_COLOR = (255, 224, 140)        # 黄色背景
TITLE_COLOR = (255, 68, 102)      # 左上テキストのピンク/コーラルレッド
TITLE_MARGIN_X = 28
TITLE_MARGIN_Y = 20
TITLE_FONT_SIZE = 66

PHOTO_MARGIN_LEFT = 46
PHOTO_MARGIN_RIGHT = 52
PHOTO_MARGIN_BOTTOM = 46
PHOTO_MARGIN_TOP = 112             # タイトル文字の下に十分な余白を確保

CROSS_COLOR = (255, 137, 176)
CROSS_BLOCK = (CANVAS_SIZE - 52, 0, CANVAS_SIZE, 232)  # 右上の十字模様ブロック(x0,y0,x1,y1)
CROSS_SPACING = 34
CROSS_SIZE = 12
CROSS_THICKNESS = 4

STRIPE_COLORS = [(255, 137, 176), (255, 224, 140)]  # ピンク / 背景と同系の淡黄
STRIPE_WIDTH = 42
STRIPE_CORNER_Y_RATIO = 0.56   # 左下ストライプ三角形の開始位置(高さに対する比率)
STRIPE_CORNER_X_RATIO = 0.30   # 左下ストライプ三角形の底辺の広がり(幅に対する比率)


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
            draw.line([(x - half, y), (x + half, y)], fill=CROSS_COLOR, width=CROSS_THICKNESS)
            draw.line([(x, y - half), (x, y + half)], fill=CROSS_COLOR, width=CROSS_THICKNESS)
            x += spacing
        y += spacing
        row += 1


def _diagonal_stripes(size, colors, stripe_width=STRIPE_WIDTH):
    """45度の斜めストライプ模様を敷き詰めた画像を返す"""
    w, h = size
    img = Image.new("RGB", (w, h), colors[0])
    draw = ImageDraw.Draw(img)
    x = -h
    i = 0
    while x < w + h:
        color = colors[i % len(colors)]
        draw.polygon(
            [(x, 0), (x + stripe_width, 0), (x + stripe_width - h, h), (x - h, h)],
            fill=color,
        )
        x += stripe_width
        i += 1
    return img


def _paste_bottom_left_stripes(canvas: Image.Image):
    """左下角に斜めストライプの三角形リボンを合成する"""
    w, h = canvas.size
    stripes = _diagonal_stripes((w, h), STRIPE_COLORS)

    mask = Image.new("L", (w, h), 0)
    mdraw = ImageDraw.Draw(mask)
    corner_y = int(h * STRIPE_CORNER_Y_RATIO)
    corner_x = int(w * STRIPE_CORNER_X_RATIO)
    mdraw.polygon([(0, corner_y), (0, h), (corner_x, h)], fill=255)

    canvas.paste(stripes, (0, 0), mask)


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
    input_path の商品画像に、黄色背景+左上ピンク文字+右上十字模様+左下斜めストライプの
    フレームを加工し、output_path に保存する。
    """
    base = Image.open(input_path).convert("RGB")

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BG_COLOR)

    # 左下の斜めストライプリボンを先に合成(写真より下のレイヤー)
    _paste_bottom_left_stripes(canvas)

    # 右上の十字模様ブロック
    draw = ImageDraw.Draw(canvas)
    _draw_cross_pattern(draw, CROSS_BLOCK)

    # 中央〜右下寄りに白背景の正方形フォトエリアを配置(アスペクト比維持)
    photo_w = CANVAS_SIZE - PHOTO_MARGIN_LEFT - PHOTO_MARGIN_RIGHT
    photo_h = CANVAS_SIZE - PHOTO_MARGIN_TOP - PHOTO_MARGIN_BOTTOM
    ratio = min(photo_w / base.width, photo_h / base.height)
    new_w, new_h = int(base.width * ratio), int(base.height * ratio)
    resized = base.resize((new_w, new_h), Image.LANCZOS)

    white_bg = Image.new("RGB", (photo_w, photo_h), (255, 255, 255))
    paste_x = (photo_w - new_w) // 2
    paste_y = (photo_h - new_h) // 2
    white_bg.paste(resized, (paste_x, paste_y))
    canvas.paste(white_bg, (PHOTO_MARGIN_LEFT, PHOTO_MARGIN_TOP))

    # 左上に「Direct From JAPAN」テキスト(バナー背景なし、黄色地に直接)
    font = _load_font(TITLE_FONT_SIZE)
    draw.text((TITLE_MARGIN_X, TITLE_MARGIN_Y), banner_text, fill=TITLE_COLOR, font=font)

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
