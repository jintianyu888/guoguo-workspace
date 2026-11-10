#!/usr/bin/env python3
"""pdf2ps.py v3 - PDF -> PostScript（1-bit 黑白 + 分条带，适配东芝 PS3）"""
import argparse, base64, pypdfium2 as pdfium
A4W, A4H = 595.28, 841.89
A3W, A3H = 1190.55, 841.89
BAND = 64

def render(page, dpi, rot=0):
    b = page.render(scale=dpi / 72.0, grayscale=True, rotation=rot)
    w, h = b.width, b.height
    g = bytes(b.buffer)
    rb = (w + 7) // 8
    out = bytearray(rb * h)
    for y in range(h):
        base = y * w; o = y * rb; row = g[base:base + w]
        for i in range(w):
            if row[i] >= 160:
                out[o + (i >> 3)] |= (0x80 >> (i & 7))
    return w, h, bytes(out)

def emit(ps, w, h, data, x0, y0, bw, bh):
    rb = (w + 7) // 8
    for top0 in range(0, h, BAND):
        n = min(BAND, h - top0)
        seg = data[top0 * rb: top0 * rb + rb * n]
        a85 = base64.a85encode(seg).decode()
        frac_top = top0 / h; frac_h = n / h
        ps.append('gsave')
        ps.append('%.2f %.2f translate' % (x0, y0 + bh * (1 - frac_top - frac_h)))
        ps.append('%.2f %.2f scale' % (bw, bh * frac_h))
        ps.append('/DeviceGray setcolorspace')
        ps.append('<< /ImageType 1 /Width %d /Height %d /BitsPerComponent 1' % (w, n))
        ps.append('   /Decode [0 1] /ImageMatrix [%d 0 0 -%d 0 %d]' % (w, n, n))
        ps.append('   /DataSource currentfile /ASCII85Decode filter >> image')
        for i in range(0, len(a85), 100):
            ps.append(a85[i:i+100])
        ps.append('~>')
        ps.append('grestore')

def fit(bw, bh, W, H):
    s = min(W / bw, H / bh)
    return bw * s, bh * s

def build(pdf, dpi, paper, booklet, maxp):
    n = min(len(pdf), maxp) if maxp else len(pdf)
    W, H = (A3W, A3H) if booklet else ((A4W, A4H) if paper == 'a4' else (A3W, A3H))
    ps = ['%!PS-Adobe-3.0', '<< /PageSize [%.2f %.2f] >> setpagedevice' % (W, H)]
    if not booklet:
        for i in range(n):
            w, h, d = render(pdf[i], dpi)
            dw, dh = fit(w, h, W, H)
            emit(ps, w, h, d, (W - dw) / 2, (H - dh) / 2, dw, dh)
            ps.append('showpage')
        return ps
    total = n + (4 - n % 4) % 4
    for k in range(1, total // 4 + 1):
        for a, bb, back in ((total - 2*k + 2, 2*k - 1, False), (2*k, total - 2*k + 1, True)):
            # ★ 背面左右对调（2026-09-27 主公实测：本机 A3 双面长边会把背面左右镜像）
            order = ((bb, 0.0), (a, A4W)) if back else ((a, 0.0), (bb, A4W))
            for num, x0 in order:
                if 1 <= num <= n:
                    w, h, d = render(pdf[num - 1], dpi, 180 if back else 0)
                    dw, dh = fit(w, h, A4W, A4H)
                    emit(ps, w, h, d, x0 + (A4W - dw) / 2, (A4H - dh) / 2, dw, dh)
            ps.append('showpage')
    return ps

def wrap(lines, paper, duplex):
    U = b'\x1b%-12345X'
    h = U + b'@PJL JOB NAME="pdf2ps"\r\n'
    h += ('@PJL SET PAPER=%s\r\n' % paper.upper()).encode()
    if duplex:
        h += b'@PJL SET DUPLEX=ON\r\n'
        h += ('@PJL SET BINDING=%s\r\n' % ('LONGEDGE' if duplex == 'long' else 'SHORTEDGE')).encode()
    h += b'@PJL ENTER LANGUAGE=POSTSCRIPT\r\n'
    return h + ('\n'.join(lines)).encode() + b'\n' + U + b'@PJL EOJ\r\n'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inp'); ap.add_argument('outp')
    ap.add_argument('--dpi', type=int, default=150)
    ap.add_argument('--paper', default='a4')
    ap.add_argument('--duplex', default=None)
    ap.add_argument('--booklet', action='store_true')
    ap.add_argument('--pages', type=int, default=0)
    a = ap.parse_args()
    pdf = pdfium.PdfDocument(a.inp)
    lines = build(pdf, a.dpi, a.paper, a.booklet, a.pages)
    data = wrap(lines, a.paper, a.duplex)
    open(a.outp, 'wb').write(data)
    print('OK %s -> %s (%d pages, %d KB)' % (a.inp, a.outp, len(pdf), len(data) // 1024))

if __name__ == '__main__':
    main()