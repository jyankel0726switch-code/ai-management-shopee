"""
add_shopee_frame.py

Shopee出品用Cover画像に「黄色枠＋左上のDirect From JAPANロゴ＋
右上のピンク十字模様コーナー＋左下のピンク斜めストライプコーナー」を
自動で加工するスクリプト（従来Canvaで手作業していた加工の自動化版）。

使い方:
    from add_shopee_frame import add_frame
    add_frame("input.jpg", "output.jpg")
    add_frame("input.jpg", "output.jpg", banner_text="Direct From JAPAN")

依存:
    pip install pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ---- デザイン設定（参考デザインの見た目に合わせて調整可能） ----
CANVAS_SIZE = 1200                  # 出力画像は正方形(Shopee推奨)
BORDER_COLOR = (254, 226, 140)      # 淡い黄色
SIDE_MARGIN = int(CANVAS_SIZE * 0.04)     # 左・右・下の黄色余白
TOP_MARGIN = int(CANVAS_SIZE * 0.096)     # 上の黄色余白（ロゴテキスト用）

PINK = (250, 108, 138)               # ピンク（テキスト用, RGB）
PINK_RGBA = PINK + (255,)            # ピンク（RGBAレイヤー描画用、不透明）

# 右上コーナー：ピンク十字模様
CORNER_SIZE = int(CANVAS_SIZE * 0.20)
CROSS_SPACING = int(CANVAS_SIZE * 0.045)
CROSS_ARM = int(CANVAS_SIZE * 0.012)
CROSS_THICKNESS = max(2, int(CANVAS_SIZE * 0.004))

# 左下コーナー：斜めストライプ
STRIPE_WIDTH = int(CANVAS_SIZE * 0.035)

# ロゴテキスト
TEXT_MARGIN_X = int(CANVAS_SIZE * 0.018)
FONT_SIZE = int(CANVAS_SIZE * 0.052)


def _load_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _top_right_cross_layer(size):
    """右上の直角三角形コーナーにピンクの十字模様を敷き詰めたRGBAレイヤーを返す"""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    y = CROSS_SPACING // 2
    row = 0
    while y < CORNER_SIZE:
        offset = (CROSS_SPACING // 2) if row % 2 else 0
        x = size - CORNER_SIZE + offset
        while x < size:
            half = CROSS_ARM // 2
            draw.line([(x - half, y), (x + half, y)], fill=PINK_RGBA, width=CROSS_THICKNESS)
            draw.line([(x, y - half), (x, y + half)], fill=PINK_RGBA, width=CROSS_THICKNESS)
            x += CROSS_SPACING
        y += CROSS_SPACING
        row += 1

    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.polygon(
        [(size - CORNER_SIZE, 0), (size, 0), (size, CORNER_SIZE)],
        fill=255,
    )
    layer.putalpha(Image.composite(layer.split()[3], Image.new("L", (size, size), 0), mask))
    return layer


def _bottom_left_stripe_layer(size):
    """左下の直角三角形コーナーにピンク×白の斜めストライプを敷き詰めたRGBAレイヤーを返す"""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    # 45度の斜めストライプを左下コーナー全体に描画してから三角形でマスクする
    diag = CORNER_SIZE * 2
    x = -diag
    while x < diag:
        draw.polygon(
            [
                (x, size),
                (x + STRIPE_WIDTH, size),
                (x + STRIPE_WIDTH + diag, size - diag),
                (x + diag, size - diag),
            ],
            fill=PINK_RGBA,
        )
        x += STRIPE_WIDTH * 2

    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.polygon(
        [(0, size - CORNER_SIZE), (0, size), (CORNER_SIZE, size)],
        fill=255,
    )
    layer.putalpha(Image.composite(layer.split()[3], Image.new("L", (size, size), 0), mask))
    return layer


def add_frame(input_path: str, output_path: str, banner_text: str = "Direct From JAPAN"):
    """
    input_path の商品画像に黄色枠＋左上ロゴ＋右上十字模様＋左下斜めストライプを
    加工し、output_path に保存する。
    """
    base = Image.open(input_path).convert("RGB")

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BORDER_COLOR)

    photo_x0, photo_y0 = SIDE_MARGIN, TOP_MARGIN
    photo_x1, photo_y1 = CANVAS_SIZE - SIDE_MARGIN, CANVAS_SIZE - SIDE_MARGIN
    photo_w, photo_h = photo_x1 - photo_x0, photo_y1 - photo_y0

    ratio = min(photo_w / base.width, photo_h / base.height)
    new_w, new_h = int(base.width * ratio), int(base.height * ratio)
    resized = base.resize((new_w, new_h), Image.LANCZOS)

    white_bg = Image.new("RGB", (photo_w, photo_h), (255, 255, 255))
    paste_x = (photo_w - new_w) // 2
    paste_y = (photo_h - new_h) // 2
    white_bg.paste(resized, (paste_x, paste_y))
    canvas.paste(white_bg, (photo_x0, photo_y0))

    canvas = canvas.convert("RGBA")
    canvas = Image.alpha_composite(canvas, _top_right_cross_layer(CANVAS_SIZE))
    canvas = Image.alpha_composite(canvas, _bottom_left_stripe_layer(CANVAS_SIZE))
    canvas = canvas.convert("RGB")

    # 左上に「Direct From JAPAN」ロゴテキスト（黄色地に直接、バナー枠なし）
    draw = ImageDraw.Draw(canvas)
    font = _load_font(FONT_SIZE)
    bbox = draw.textbbox((0, 0), banner_text, font=font)
    th = bbox[3] - bbox[1]
    tx = TEXT_MARGIN_X
    ty = (TOP_MARGIN - th) // 2 - bbox[1]
    draw.text((tx, ty), banner_text, fill=PINK, font=font)

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
