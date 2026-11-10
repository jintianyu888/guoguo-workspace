#!/usr/bin/env python3
"""print-vec.py —— 把单页乐谱/线稿画成 **纯矢量矩形** 的 PostScript（完全不使用 image）。

背景（2026-10-01 实测）：这台 TOSHIBA e-STUDIO 在 9100 裸推 PS 时，文字/线条/矩形都能正常出，
但任何 `image` / `imagemask`（无论滤镜、压缩与否）都不出图 ⇒ 乐谱永远白纸。
对策：把黑色像素行程转成 `x y w h rectfill`，用最原始的矢量算子画出来。

用法: print-vec.py <输入.pdf|图片> [--dpi 200] [--paper a4|a3] --out x.ps
"""
import argparse, sys
from PIL import Image

PAPERS = {'a4': (595.0, 842.0), 'a3': (841.0, 1191.0)}

def load_page(src, index, dpi):
    if src.lower().endswith('.pdf'):
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(src)
        page = doc[index]
        scale = dpi / 72.0
        pil = page.render(scale=scale).to_pil()
    else:
        pil = Image.open(src)
    return pil.convert('L')

def runs_of_row(row_bytes, width):
    runs = []
    start = None
    for x in range(width):
        black = row_bytes[x >> 3] & (0x80 >> (x & 7))
        if black and start is None:
            start = x
        elif not black and start is not None:
            runs.append((start, x)); start = None
    if start is not None:
        runs.append((start, width))
    return runs

def page_ops(im, W, H):
    w, h = im.size
    sc = min(W / w, H / h)
    dw, dh = w * sc, h * sc
    ox, oy = (W - dw) / 2.0, (H - dh) / 2.0
    bits = im.point(lambda v: 255 if v > 160 else 0, mode='1')
    px = bits.load()
    ops = []
    ops.append('gsave')
    ops.append('%.4f %.4f translate %.6f %.6f scale' % (ox, oy, sc, sc))
    ops.append('0 setgray')
    rows = []
    for y in range(h):
        b = bytearray((w + 7) // 8)
        for x in range(w):
            if px[x, y]:
                b[x >> 3] |= 0x80 >> (x & 7)
        rows.append((b, runs_of_row(b, w)))
    i = 0
    while i < h:
        row = rows[i]
        j = i + 1
        while j < h and rows[j][1] == row[1] and rows[j][1]:
            j += 1
        for (x0, x1) in row[1]:
            ops.append('%d %d %d %d rectfill' % (x0, h - j, x1 - x0, j - i))
        i = j if j > i + 1 else i + 1
    ops.append('grestore showpage')
    return '\n'.join(ops)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--dpi', type=int, default=200)
    ap.add_argument('--paper', choices=['a4', 'a3'], default='a4')
    ap.add_argument('--page', type=int, default=0)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    W, H = PAPERS[a.paper]
    im = load_page(a.src, a.page, a.dpi)
    body = page_ops(im, W, H)
    head = ['%!PS-Adobe-3.0', '%%Pages: 1', '%%BoundingBox: 0 0 ' + str(int(W)) + ' ' + str(int(H)),
            '%%Creator: OpenClaw print-vec (pure vector, no image)', '%%EndComments', '%%Page: 1 1']
    open(a.out, 'w', encoding='ascii', errors='ignore').write('\n'.join(head) + '\n' + body + '\n%%EOF\n')
    print('OK %s | %d x %d px @ %ddpi | %s' % (a.paper.upper(), im.size[0], im.size[1], a.dpi, a.out))

if __name__ == '__main__':
    main()