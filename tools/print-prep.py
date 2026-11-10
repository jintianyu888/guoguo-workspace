#!/usr/bin/env python3
"""送印前处理 v4c：统一纸型（A4/A3）· 缩放适配绝不裁切 · 产 PS 直推文件

背景：东芝 e-STUDIO PS3 不吃 PDF（静默忽略，2026-09-27 实测）。
送印一律用本工具 --ps 产物，配合 print.py --ps-file 直推（PS 路线）。
v4c：JPEG 内嵌 PS（ASCII85+DCTDecode，纯 stdlib+PIL），图片输入零依赖；
     PDF 输入需 pypdfium2（系统 python3 暂无 → 此类输入会明确报错，勿静默）。
"""
import argparse, base64, io, os
from PIL import Image, ImageFilter

PAPERS = {'a4': (210.0, 297.0), 'a3': (297.0, 420.0)}
PT = {'a4': (595.0, 842.0), 'a3': (842.0, 1191.0)}   # PS 点（纵向纸面）

def load_pages(path):
    if path.lower().endswith('.pdf'):
        import pypdfium2 as pdfium   # 缺依赖时会明确抛错
        pdf = pdfium.PdfDocument(path)
        for i in range(len(pdf)):
            yield pdf[i].render(scale=4.0).to_pil().convert('RGB')
    else:
        yield Image.open(path).convert('RGB')

def prep(im, w_mm, h_mm):
    dpi = min(im.width / (w_mm/25.4), im.height / (h_mm/25.4))
    dpi = min(dpi, 400.0)
    cw, ch = round(w_mm/25.4*dpi), round(h_mm/25.4*dpi)
    canvas = Image.new('RGB', (cw, ch), 'white')
    im2 = im.copy()
    if im2.width > cw or im2.height > ch:
        im2.thumbnail((cw, ch), Image.LANCZOS)   # 只缩小：绝不裁切
    else:
        im2 = im2.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))
    canvas.paste(im2, ((cw-im2.width)//2, (ch-im2.height)//2))
    return canvas, dpi

def ps_string(data: bytes) -> str:
    s = base64.a85encode(data).decode('ascii')
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

def render_ps(im, w_pt, h_pt):
    """一张满页：JPEG 数据以 ASCII85 内嵌，DCTDecode 解出后铺满 w_pt×h_pt"""
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=88)
    raw = buf.getvalue()
    w, h = im.size
    hdr = ('<< /ImageType 1 /Width %d /Height %d /ImageMatrix [%d 0 0 %d 0 %d] '
           '/BitsPerComponent 8 /Decode [0 1 0 1 0 1] /Length %d >>'
           % (w, h, w, -h, h, len(raw)))
    stream = '(%s~>) /ASCII85Decode filter /DCTDecode filter' % ps_string(raw)
    return "%s\n%s\n%.0f %.0f image\nshowpage\n" % (hdr, stream, w_pt, h_pt)

def make_ps(pages, paper, duplex=None):
    W, H = PT[paper]
    body = "%!PS-Adobe-3.0\n" + "".join(render_ps(im, W, H) for im in pages)
    # 2026-10-01 铁证（老板拍照）：这台 e-STUDIO 不吃 PJL 包裹——
    # 一旦带上 @PJL JOB/@PJL ENTER LANGUAGE，它就把整份作业源码当文本打出来。
    # → 一律输出【纯 PS】：靠打印机自动识别语言；纸型交给纸盒/面板（不发 setpagedevice，
    #   2026-10-01 实测本机对 `<< /PageSize .. >> setpagedevice` 报 undefined）。
    return body.encode()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--paper', default='a4', choices=sorted(PAPERS.keys()))
    ap.add_argument('--out', default=None)
    ap.add_argument('--ps', action='store_true', help='产出 PS 直推文件（送印用这个）')
    ap.add_argument('--dpi', type=float, default=200.0, help='兼容参数（PS 用源图原生分辨率）')
    ap.add_argument('--duplex', choices=['long', 'short'], default=None)
    a = ap.parse_args()
    paper = a.paper.lower()
    w_mm, h_mm = PAPERS[paper]
    src = a.files[0]
    out = a.out or (os.path.splitext(src)[0] + '_print_%s' % paper.upper())
    pages, dpis = [], []
    for p in load_pages(src):
        t, d = prep(p, w_mm, h_mm); pages.append(t); dpis.append(d)
    if a.ps:
        psout = out + '.ps'
        data = make_ps(pages, paper, a.duplex)
        with open(psout, 'wb') as f:
            f.write(data)
        print('OK %s | %d 页 | PS %.0fKB -> %s' % (paper.upper(), len(pages), len(data)/1024, psout))
    else:
        pdfout = out + '.pdf'
        pages[0].save(pdfout, 'PDF', resolution=dpis[0], save_all=True, append_images=pages[1:])
        print('OK %s | %d 页 | 等效 %.0f DPI | 已锐化 -> %s（注意：本机不吃 PDF，别直推）'
              % (paper.upper(), len(pages), dpis[0], pdfout))

if __name__ == '__main__':
    main()
