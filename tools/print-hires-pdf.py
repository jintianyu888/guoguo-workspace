#!/usr/bin/env python3
"""print-hires-pdf.py —— 乐谱专用「高清 A4 PDF」（走 IPP 631 直投，替代模糊的直投原图）

目的：解决「打印出来的乐谱发虚/模糊」。
做法：把源（PDF/图片）渲染成 **高 DPI + 纯黑白(1-bit 无损)** 的 A4 满页 PDF：
  1) 目标 DPI 渲染（PDF 走 pypdfium2，图片直读）
  2) 轻度锐化（UnsharpMask）救一点软边
  3) 二值化：灰边变纯黑白，五线谱/音符边缘更利落，去掉 JPEG 发灰
  4) 四周留 --margin-mm 安全边（避开打印机不可打印边距，绝不裁切）
输出 PDF → 再用 print-ipp.py 投出（这台只吃 IPP 出的图，PS 里 image 不渲染）。

用法: print-hires-pdf.py <源.pdf|图片> [--dpi 600] [--paper a4|a3]
        [--margin-mm 6] [--threshold 160] [--no-fill] --out /home/j/.openclaw/workspace/state/tmp/x.pdf
"""
import argparse
from PIL import Image, ImageFilter

PAPERS = {"a4": (210.0, 297.0), "a3": (297.0, 420.0)}

def load_pages(path, dpi):
    if path.lower().endswith(".pdf"):
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(path)
        for i in range(len(doc)):
            yield doc[i].render(scale=dpi / 72.0).to_pil().convert("L")
    else:
        yield Image.open(path).convert("L")

def place(im, W, H, margin_px, fill):
    aw, ah = max(1, W - 2 * margin_px), max(1, H - 2 * margin_px)
    im2 = im.copy()
    if im2.width > aw or im2.height > ah:
        im2.thumbnail((aw, ah), Image.LANCZOS)          # 太大：只缩
    elif fill:
        im2 = im2.resize((aw, ah), Image.LANCZOS)       # 太小：等比放大铺满
    return im2

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--dpi", type=int, default=600)
    ap.add_argument("--paper", choices=["a4", "a3"], default="a4")
    ap.add_argument("--margin-mm", type=float, default=6.0)
    ap.add_argument("--threshold", type=int, default=160)
    ap.add_argument("--no-fill", dest="fill", action="store_false")
    ap.set_defaults(fill=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    w_mm, h_mm = PAPERS[a.paper]
    W = round(w_mm / 25.4 * a.dpi)
    H = round(h_mm / 25.4 * a.dpi)
    m = round(a.margin_mm / 25.4 * a.dpi)

    pages = []
    for im in load_pages(a.src, a.dpi):
        im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
        page = Image.new("L", (W, H), 255)
        f = place(im, W, H, m, a.fill)
        page.paste(f, ((W - f.width) // 2, (H - f.height) // 2))
        pages.append(page.point(lambda x: 255 if x > a.threshold else 0, mode="1"))

    pages[0].save(a.out, "PDF", resolution=a.dpi, save_all=True, append_images=pages[1:])
    print("OK %s | %d 页 | %d dpi 二值 | 边距 %.1fmm | %s -> %s"
          % (a.paper.upper(), len(pages), a.dpi, a.margin_mm,
             "铺满" if a.fill else "不放大", a.out))

if __name__ == "__main__":
    main()
