"""
add_shopee_frame.py

Shopee出品用Cover画像に「パステルイエロー背景＋白抜き商品枠＋左上ピンクDirect From JAPANテキスト
＋右上ピンク十字クラスター＋左下ピンク斜めストライプ」を自動で加工するスクリプト。

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
CANVAS_SIZE = 1200               # 出力画像は正方形(Shopee推奨)
BG_COLOR = (255, 224, 140)       # パステルイエロー背景
WHITE = (255, 255, 255)
PINK = (255, 105, 150)           # テキスト/十字/ストライプのピンク
INNER_PAD = 22                   # 白枠内の商品画像パディング

TOP_BAND = 108                   # 上部(テキスト/十字用)の余白高さ
SIDE_MARGIN = 48                 # 左右の黄色マージン
BOTTOM_MARGIN = 60                # 下部の黄色マージン

CROSS_SIZE = 26
CROSS_THICKNESS = 6
STRIPE_WIDTH = 22
STRIPE_TRIANGLE = 170


def _load_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_cross(draw, cx, cy, size, color, thickness):
    half = size // 2
    draw.line([(cx - half, cy), (cx + half, cy)], fill=color, width=thickness)
    draw.line([(cx, cy - half), (cx, cy + half)], fill=color, width=thickness)


def add_frame(input_path: str, output_path: str, banner_text: str = "Direct From JAPAN"):
    """
    input_path の商品画像に、パステルイエロー背景＋白抜き商品枠＋左上ピンクテキスト
    ＋右上ピンク十字クラスター＋左下ピンク斜めストライプを加工し、output_path に保存する。
    """
    base = Image.open(input_path).convert("RGB")

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    sq_x0 = SIDE_MARGIN
    sq_y0 = TOP_BAND
    sq_x1 = CANVAS_SIZE - SIDE_MARGIN
    sq_y1 = CANVAS_SIZE - BOTTOM_MARGIN
    draw.rectangle([sq_x0, sq_y0, sq_x1, sq_y1], fill=WHITE)

    inner_w = (sq_x1 - sq_x0) - 2 * INNER_PAD
    inner_h = (sq_y1 - sq_y0) - 2 * INNER_PAD
    ratio = min(inner_w / base.width, inner_h / base.height)
    new_w, new_h = int(base.width * ratio), int(base.height * ratio)
    resized = base.resize((new_w, new_h), Image.LANCZOS)
    paste_x = sq_x0 + INNER_PAD + (inner_w - new_w) // 2
    paste_y = sq_y0 + INNER_PAD + (inner_h - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))

    draw = ImageDraw.Draw(canvas)

    # 左上: "Direct From JAPAN" テキスト
    font = _load_font(52)
    draw.text((28, 18), banner_text, fill=PINK, font=font)

    # 右上: ピンク十字クラスター
    cross_positions = [
        (CANVAS_SIZE - 90, 55), (CANVAS_SIZE - 40, 55), (CANVAS_SIZE - 15, 80),
        (CANVAS_SIZE - 90, 100), (CANVAS_SIZE - 40, 100),
    ]
    for (cx, cy) in cross_positions:
        _draw_cross(draw, cx, cy, CROSS_SIZE, PINK, CROSS_THICKNESS)

    # 左下: ピンク/白の斜めストライプ(三角形にマスク)
    stripe_overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(stripe_overlay)
    toggle = False
    total = CANVAS_SIZE + STRIPE_TRIANGLE
    x = -total
    while x < STRIPE_TRIANGLE:
        color = PINK + (255,) if toggle else WHITE + (255,)
        sdraw.line([(x, CANVAS_SIZE), (x + total, CANVAS_SIZE - total)], fill=color, width=STRIPE_WIDTH)
        x += STRIPE_WIDTH * 2
        toggle = not toggle

    mask = Image.new("L", canvas.size, 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.polygon(
        [(0, CANVAS_SIZE - STRIPE_TRIANGLE), (0, CANVAS_SIZE), (STRIPE_TRIANGLE, CANVAS_SIZE)],
        fill=255,
    )
    stripe_alpha = Image.composite(stripe_overlay.split()[3], Image.new("L", canvas.size, 0), mask)
    stripe_overlay.putalpha(stripe_alpha)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), stripe_overlay).convert("RGB")

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
