"""
add_shopee_frame.py

Shopee出品用Cover画像に「黄色枠＋ピンク十字模様＋Direct From JAPANバナー」を
自動で加工するスクリプト（従来Canvaで手作業していた加工の自動化版）。

使い方:
    from add_shopee_frame import add_frame
    add_frame("input.jpg", "output.jpg")
    add_frame("input.jpg", "output.jpg", banner_text="Direct From JAPAN")

依存:
    pip install pillow
"""

from PIL import Image, ImageDraw, ImageFont
import math
import os

# ---- デザイン設定（Canva手作業版の見た目に合わせて調整可能） ----
CANVAS_SIZE = 1200          # 出力画像は正方形(Shopee推奨)
BORDER_WIDTH = 60           # 黄色枠の太さ(px)
BORDER_COLOR = (255, 200, 0)      # 黄色
CROSS_COLOR = (255, 105, 180, 110)  # ピンク十字模様(半透明)
CROSS_SPACING = 70          # 十字模様の間隔(px)
CROSS_SIZE = 14             # 十字1つのサイズ(px)
CROSS_THICKNESS = 4
BANNER_HEIGHT = 90
BANNER_BG = (220, 20, 60)   # バナー背景(クリムゾン)
BANNER_TEXT_COLOR = (255, 255, 255)


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
    input_path の商品画像に黄色枠＋ピンク十字模様＋バナーを加工し、output_path に保存する。
    """
    base = Image.open(input_path).convert("RGB")

    # 正方形キャンバスの中央に商品画像を配置(アスペクト比維持・余白は白)
    inner = CANVAS_SIZE - 2 * BORDER_WIDTH
    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BORDER_COLOR)

    photo_area = inner - BANNER_HEIGHT
    ratio = min(inner / base.width, photo_area / base.height)
    new_w, new_h = int(base.width * ratio), int(base.height * ratio)
    resized = base.resize((new_w, new_h), Image.LANCZOS)

    white_bg = Image.new("RGB", (inner, photo_area), (255, 255, 255))
    paste_x = (inner - new_w) // 2
    paste_y = (photo_area - new_h) // 2
    white_bg.paste(resized, (paste_x, paste_y))
    canvas.paste(white_bg, (BORDER_WIDTH, BORDER_WIDTH))

    # ピンク十字模様を黄色枠の上に重ねる(半透明合成)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    # 上枠・下枠・左枠・右枠それぞれに模様を敷く
    _draw_cross_pattern(odraw, (0, 0, CANVAS_SIZE, BORDER_WIDTH))
    _draw_cross_pattern(odraw, (0, CANVAS_SIZE - BORDER_WIDTH, CANVAS_SIZE, CANVAS_SIZE))
    _draw_cross_pattern(odraw, (0, 0, BORDER_WIDTH, CANVAS_SIZE))
    _draw_cross_pattern(odraw, (CANVAS_SIZE - BORDER_WIDTH, 0, CANVAS_SIZE, CANVAS_SIZE))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    # 下部に「Direct From JAPAN」バナー
    draw = ImageDraw.Draw(canvas)
    banner_y0 = BORDER_WIDTH + photo_area
    banner_y1 = banner_y0 + BANNER_HEIGHT
    draw.rectangle([BORDER_WIDTH, banner_y0, CANVAS_SIZE - BORDER_WIDTH, banner_y1], fill=BANNER_BG)

    font = _load_font(40)
    bbox = draw.textbbox((0, 0), banner_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (CANVAS_SIZE - tw) // 2
    ty = banner_y0 + (BANNER_HEIGHT - th) // 2 - bbox[1]
    draw.text((tx, ty), banner_text, fill=BANNER_TEXT_COLOR, font=font)

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
