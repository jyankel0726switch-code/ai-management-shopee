"""
add_shopee_frame.py

Shopee出品用Cover画像に「パステルイエロー背景＋白抜き商品枠＋左上ピンクDirect From JAPANテキスト
＋右端の薄ピンク十字＋左端の薄ピンク斜めストライプ」を自動で加工するスクリプト。

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
BG_COLOR = (255, 228, 147)       # パステルイエロー背景(見本 #FFE493)
WHITE = (255, 255, 255)
PINK = (254, 86, 122)            # テキストのピンク(見本 #FE567A)
CROSS_PINK = (255, 177, 232)     # 十字のピンク(見本 #FFB1E8)
STRIPE_PINK = (255, 183, 226)    # ストライプのピンク(見本 #FFB7E2)
INNER_PAD = 22                   # 白枠内の商品画像パディング

TOP_BAND = 113                   # 上部(テキスト/十字用)の余白高さ
SIDE_MARGIN = 55                 # 左右の黄色マージン
BOTTOM_MARGIN = 64                # 下部の黄色マージン

# 見本(500px)を1200pxに拡大(x2.4)した寸法
CROSS_SIZE = 22                  # 十字の全幅
CROSS_THICKNESS = 6
CROSS_COLS = (1157, 1193)        # 右端の2列(x中心)
CROSS_ROW0, CROSS_PITCH, CROSS_ROWS = 12, 35.5, 7
STRIPE_BAND = 22                 # ストライプ(ピンク)の縦幅
STRIPE_PERIOD = 52               # ストライプの周期(縦方向)
STRIPE_START = 691               # ストライプ開始位置(x=0でのy)
STRIPE_STRIP_W = SIDE_MARGIN     # ストライプは左端の細い帯(白枠の手前)だけ


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
    ＋右端の薄ピンク十字＋左端の薄ピンク斜めストライプを加工し、output_path に保存する。
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
    font = _load_font(62)
    draw.text((10, 12), banner_text, fill=PINK, font=font)

    # 右端: 薄ピンクの十字(2列x7段。右列は画像端で少し切れる)
    for cx in CROSS_COLS:
        for i in range(CROSS_ROWS):
            _draw_cross(draw, cx, round(CROSS_ROW0 + CROSS_PITCH * i), CROSS_SIZE, CROSS_PINK, CROSS_THICKNESS)

    # 左端: 薄ピンクの斜めストライプ(左端の細い帯の中だけ、下端まで)
    SS = 3
    layer = Image.new("L", (STRIPE_STRIP_W * SS, (CANVAS_SIZE - STRIPE_START) * SS), 0)
    ldraw = ImageDraw.Draw(layer)
    h = layer.height
    k = -2
    while True:
        y0 = k * STRIPE_PERIOD * SS
        if y0 > h + STRIPE_STRIP_W * SS:
            break
        # 右下がりの平行四辺形(x=0で縦幅STRIPE_BAND、45度)
        w = STRIPE_STRIP_W * SS
        ldraw.polygon([(0, y0), (0, y0 + STRIPE_BAND * SS), (w, y0 + STRIPE_BAND * SS + w), (w, y0 + w)], fill=255)
        k += 1
    layer = layer.resize((STRIPE_STRIP_W, CANVAS_SIZE - STRIPE_START), Image.LANCZOS)
    canvas.paste(Image.new("RGB", layer.size, STRIPE_PINK), (0, STRIPE_START), layer)

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
