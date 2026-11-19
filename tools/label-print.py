#!/usr/bin/env python3
# label-print.py -- 给样张顶部加一条文字标签带（A/B 对比用），输出 JPG
# 用法: label-print.py <src.jpg|png> --label "A: DIRECT" --out /tmp/A.jpg
import argparse
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--label", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--font", default="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
ap.add_argument("--size", type=int, default=0)
a = ap.parse_args()

im = Image.open(a.src).convert("L")
W, H = im.size
fs = a.size or max(26, int(W * 0.030))
try:
    font = ImageFont.truetype(a.font, fs)
except Exception:
    font = ImageFont.load_default()

band = int(fs * 2.0) + 14
canvas = Image.new("L", (W, H + band), 255)
canvas.paste(im, (0, band))
d = ImageDraw.Draw(canvas)
bbox = d.textbbox((0, 0), a.label, font=font)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]
d.text(((W - tw) // 2, (band - th) // 2 - bbox[1]), a.label, fill=0, font=font)
d.line([(0, band - 3), (W, band - 3)], fill=0, width=4)
canvas.save(a.out, "JPEG", quality=95)
print("OK", a.out, canvas.size)
