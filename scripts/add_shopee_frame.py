"""
add_shopee_frame.py

Shopee出品用Cover画像に、指定のフレーム画像(scripts/shopee_frame.png)を重ねて加工するスクリプト。

フレーム画像は500x500の透過PNG。中央の白枠部分(x 22-478 / y 46-474)が透明になっており、
そこに商品画像を白背景で収めてから、フレームを上に重ねる。
デザイン(パステルイエロー背景・左上ピンクの「Direct From JAPAN」・右上の十字・左下のストライプ)は
すべてフレーム画像側に含まれているため、このスクリプトでは描画しない。

使い方:
    from add_shopee_frame import add_frame
    add_frame("input.jpg", "output.jpg")

依存:
    pip install pillow
"""

from PIL import Image
import os

FRAME_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shopee_frame.png")
CANVAS_SIZE = 1200               # 出力画像は正方形(Shopee推奨)
WINDOW = (22, 46, 478, 474)      # フレーム(500px)上の透明窓 (x0, y0, x1, y1)。x1/y1は窓に含まれる最終ピクセル
INNER_PAD = 22                   # 窓内の商品画像パディング(出力px)
WHITE = (255, 255, 255)


def add_frame(input_path: str, output_path: str, banner_text: str = "Direct From JAPAN"):
    """
    input_path の商品画像をフレームの白枠内に収め、output_path にJPEGで保存する。
    banner_text は互換性のために残している引数で、文言はフレーム画像に焼き込み済みのため使用しない。
    """
    frame = Image.open(FRAME_PATH).convert("RGBA")
    scale = CANVAS_SIZE / frame.width
    frame = frame.resize((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)

    wx0, wy0 = round(WINDOW[0] * scale), round(WINDOW[1] * scale)
    wx1, wy1 = round((WINDOW[2] + 1) * scale), round((WINDOW[3] + 1) * scale)

    base = Image.open(input_path).convert("RGBA")
    flat = Image.new("RGBA", base.size, WHITE + (255,))
    flat.alpha_composite(base)
    base = flat.convert("RGB")

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), WHITE)
    inner_w = (wx1 - wx0) - 2 * INNER_PAD
    inner_h = (wy1 - wy0) - 2 * INNER_PAD
    ratio = min(inner_w / base.width, inner_h / base.height)
    new_w, new_h = int(base.width * ratio), int(base.height * ratio)
    resized = base.resize((new_w, new_h), Image.LANCZOS)
    canvas.paste(resized, (wx0 + INNER_PAD + (inner_w - new_w) // 2,
                           wy0 + INNER_PAD + (inner_h - new_h) // 2))

    out = canvas.convert("RGBA")
    out.alpha_composite(frame)
    out.convert("RGB").save(output_path, "JPEG", quality=92)
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python add_shopee_frame.py <input> <output>")
        sys.exit(1)
    add_frame(sys.argv[1], sys.argv[2])
    print(f"Saved: {sys.argv[2]}")
