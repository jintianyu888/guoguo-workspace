#!/usr/bin/env python3
"""print-hires-mask.py —— L1 安全 + 用 imagemask（经典 Level-1 画法）替代 image（无 setpagedevice / 无 setcolorspace）（1200dpi 二值 + 无损 Flate）· 多页并行（线程池）
用法: print-hires.py <输入.pdf|图片> [--dpi 1200] [--paper a4|a3] [--jobs N] --out x.ps
"""
import argparse, zlib, os, time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

INV = [False]
PAPERS = {"a4": (595.0, 842.0), "a3": (842.0, 1191.0)}

def _rle_hex(data):
    out=bytearray(); i=0; n=len(data)
    while i<n:
        j=i+1
        while j<n and data[j]==data[i] and j-i<128: j+=1
        if j-i>=3:
            out.append(257-(j-i)); out.append(data[i]); i=j
        else:
            k=i; lit=bytearray()
            while k<n and len(lit)<128 and not (k+2<n and data[k]==data[k+1]==data[k+2]):
                lit.append(data[k]); k+=1
            out.append(len(lit)-1); out.extend(lit); i=k
    out.append(128)
    return bytes(out).hex().upper()

def page_ps(im, W, H):
    im = im.point(lambda x: 255 if x > 160 else 0, mode="1")
    w, h = im.size
    b = im.tobytes()
    if INV[0]:
        b = bytes(0xFF ^ x for x in b)
    hexs = _rle_hex(b)
    sc = min(W / w, H / h)
    dw, dh = w * sc, h * sc
    ox, oy = (W - dw) / 2.0, (H - dh) / 2.0
    # CTM 只负责把 ImageMatrix 映射出的 w x h 区域缩放到目标 dw x dh（比例 sc），
    # 不能再用绝对尺寸 dw/dh 做 scale，否则会与 ImageMatrix 的 w/h 叠加放大约 w 倍。
    out = ["gsave", f"{ox:.2f} {oy:.2f} translate {dw / w:.6f} {dh / h:.6f} scale",
           "% Level-1 safe: 不用 setcolorspace（Level 2 运算符）",
           f"<< /ImageType 1 /Width {w} /Height {h} /BitsPerComponent 1 /Decode [0 1]",
           f"   /ImageMatrix [{w} 0 0 -{h} 0 {h}] /DataSource currentfile /ASCIIHexDecode filter /RunLengthDecode filter >> imagemask"]
    for i in range(0, len(hexs), 8000):
        out.append(hexs[i:i+8000])
    out += [">", "grestore showpage"]
    return "\n".join(out)

def render_index(args):
    src, idx, dpi, W, H = args
    if src.lower().endswith(".pdf"):
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(src)
        im = doc[idx].render(scale=dpi / 72.0).to_pil().convert("L")
    else:
        im = Image.open(src).convert("L")
    return idx, page_ps(im, W, H)

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("--dpi", type=int, default=1200)
ap.add_argument("--paper", choices=["a4", "a3"], default="a4")
ap.add_argument("--jobs", type=int, default=0)
ap.add_argument("--out", required=True)
ap.add_argument("--invert", action="store_true", help="imagemask 取反 1-bit 数据")
a = ap.parse_args()
W, H = PAPERS[a.paper]
INV[0] = bool(getattr(a, "invert", False))
if a.src.lower().endswith(".pdf"):
    import pypdfium2 as pdfium
    n = len(pdfium.PdfDocument(a.src))
else:
    n = 1
jobs = a.jobs or max(1, min(8, n, (os.cpu_count() or 4)))
t0 = time.time()
res = {}
with ThreadPoolExecutor(max_workers=jobs) as ex:
    for idx, ps in ex.map(render_index, [(a.src, i, a.dpi, W, H) for i in range(n)]):
        res[idx] = ps
head = ["%!PS-Adobe-3.0", f"%%Pages: {n}", f"%%BoundingBox: 0 0 {int(W)} {int(H)}", "% Level-1 safe: 不发送 setpagedevice（纸型交给打印机托盘/面板）", "%%Creator: OpenClaw print-hires", "%%EndComments"]
_pages = []
for _i in range(n):
    _pages.append(f"%%Page: {_i+1} {_i+1}")
    _pages.append(res[_i])
open(a.out, "w", encoding="ascii", errors="ignore").write("\n".join(head + _pages) + "\n%%EOF\n")
print(f"OK {a.paper.upper()} | {n} 页 | 1-bit {a.dpi}dpi | 并行{jobs}线程 | 耗时{time.time()-t0:.1f}s -> {a.out}")