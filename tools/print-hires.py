#!/usr/bin/env python3
"""print-hires.py —— 乐谱/线稿最高清晰度 PS（1200dpi 二值 + 无损 Flate）· 多页并行（线程池）
用法: print-hires.py <输入.pdf|图片> [--dpi 1200] [--paper a4|a3] [--jobs N] --out x.ps
"""
import argparse, zlib, os, time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

PAPERS = {"a4": (595.0, 842.0), "a3": (842.0, 1191.0)}

def page_ps(im, W, H):
    im = im.point(lambda x: 255 if x > 160 else 0, mode="1")
    w, h = im.size
    hexs = zlib.compress(im.tobytes(), 6).hex().upper()
    sc = min(W / w, H / h)
    dw, dh = w * sc, h * sc
    ox, oy = (W - dw) / 2.0, (H - dh) / 2.0
    # CTM 只负责把 ImageMatrix 映射出的 w x h 区域缩放到目标 dw x dh（比例 sc），
    # 不能再用绝对尺寸 dw/dh 做 scale，否则会与 ImageMatrix 的 w/h 叠加放大约 w 倍。
    out = ["gsave", f"{ox:.2f} {oy:.2f} translate {dw / w:.6f} {dh / h:.6f} scale",
           "/DeviceGray setcolorspace",
           f"<< /ImageType 1 /Width {w} /Height {h} /BitsPerComponent 1 /Decode [0 1]",
           f"   /ImageMatrix [{w} 0 0 -{h} 0 {h}] /DataSource currentfile /ASCIIHexDecode filter /FlateDecode filter >> image"]
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
a = ap.parse_args()
W, H = PAPERS[a.paper]
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
# 2026-10-01 铁证：本机 PS 解释器对 `<< /PageSize .. >> setpagedevice` 报 `undefined`（PJL-free 的 #17/#18 实物即此症状）。
# 纸型交给纸盒/面板；如需声明，用下面的 DSC %%BoundingBox 注释即可。
head = ["%!PS-Adobe-3.0", f"%%Pages: {n}", f"%%BoundingBox: 0 0 {int(W)} {int(H)}",
        "%%Creator: OpenClaw print-hires", "%%EndComments"]
_pages = []
for _i in range(n):
    _pages.append(f"%%Page: {_i+1} {_i+1}")
    _pages.append(res[_i])
open(a.out, "w", encoding="ascii", errors="ignore").write("\n".join(head + _pages) + "\n%%EOF\n")
print(f"OK {a.paper.upper()} | {n} 页 | 1-bit {a.dpi}dpi | 并行{jobs}线程 | 耗时{time.time()-t0:.1f}s -> {a.out}")