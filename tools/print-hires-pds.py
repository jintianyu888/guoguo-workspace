#!/usr/bin/env python3
"""print-hires-pds.py — L1 安全 + 【过程数据源】(procedure data source)，避开 currentfile+filter
用法: print-hires-pds.py <pdf|img> [--dpi 600] [--paper a4|a3] [--mask] [--invert] --out x.ps
"""
import argparse, time, math
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

PAPERS = {"a4": (595.0, 842.0), "a3": (842.0, 1191.0)}
CHUNK = 8192          # 每块二进制字节数（hex 后 16K 字符，稳）


def page_ps(im, W, H, mask=False, invert=False):
    im = im.point(lambda x: 255 if x > 160 else 0, mode="1")
    w, h = im.size
    data = im.tobytes()
    if invert:
        data = bytes(0xFF ^ b for b in data)
    chunks = [data[i:i + CHUNK] for i in range(0, len(data), CHUNK)]
    sc = min(W / w, H / h)
    dw, dh = w * sc, h * sc
    ox, oy = (W - dw) / 2.0, (H - dh) / 2.0
    hexl = " ".join("<%s>" % c.hex().upper() for c in chunks)
    op = "imagemask" if mask else "image"
    return "\n".join([
        "gsave",
        "%.4f %.4f translate" % (ox, oy),
        "%.6f %.6f scale" % (sc, sc),
        "/chunks [%s ()] def" % hexl,
        "/ci 0 def",
        "/datasrc { ci chunks length ge { () } { chunks ci get /ci ci 1 add def } ifelse } def",
        "<< /ImageType 1 /Width %d /Height %d /BitsPerComponent 1 /Decode [0 1]" % (w, h),
        "   /ImageMatrix [%d 0 0 -%d 0 %d] /DataSource datasrc >> %s" % (w, h, h, op),
        "grestore",
        "showpage",
    ])


def one(args):
    src, idx, dpi, W, H, mask, invert = args
    if src.lower().endswith(".pdf"):
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(src)
        im = doc[idx].render(scale=dpi / 72.0).to_pil().convert("L")
    else:
        im = Image.open(src).convert("L")
    return idx, page_ps(im, W, H, mask, invert)


ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--dpi", type=int, default=600)
ap.add_argument("--paper", choices=["a4", "a3"], default="a4")
ap.add_argument("--jobs", type=int, default=0)
ap.add_argument("--mask", action="store_true", help="用 imagemask")
ap.add_argument("--invert", action="store_true", help="取反 1-bit 数据")
ap.add_argument("--out", required=True)
a = ap.parse_args()
W, H = PAPERS[a.paper]
t0 = time.time()
if a.src.lower().endswith(".pdf"):
    import pypdfium2 as pdfium
    n = len(pdfium.PdfDocument(a.src))
else:
    n = 1
jobs = a.jobs or min(7, max(1, n))
with ThreadPoolExecutor(max_workers=jobs) as ex:
    res = sorted(ex.map(one, [(a.src, i, a.dpi, W, H, a.mask, a.invert) for i in range(n)]))
head = ["%!PS-Adobe-3.0", f"%%Pages: {n}",
        f"%%BoundingBox: 0 0 {int(W)} {int(H)}",
        "% Level-1 safe / procedure data source / no PJL",
        "%%Creator: OpenClaw print-hires-pds", "%%EndComments"]
pages = []
for i, body in res:
    pages.append(f"%%Page: {i + 1} {i + 1}")
    pages.append(body)
open(a.out, "w", encoding="ascii", errors="ignore").write("\n".join(head + pages) + "\n%%EOF\n")
print("OK %s | %d 页 | 1-bit %ddpi | pds | mask=%s invert=%s | %.1fs -> %s"
      % (a.paper.upper(), n, a.dpi, a.mask, a.invert, time.time() - t0, a.out))
