#!/usr/bin/env python3
"""nup2-a3.py -- A3 横版两页并排（2-up，不做骑马钉装订序）"""
import sys
from pikepdf import Pdf, Rectangle
A3W, A3H = 1190.55, 841.89
A4W, A4H = 595.28, 841.89
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rot_back = "--rotate-back" in sys.argv
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    inp, outp = args[0], args[1]
    src = Pdf.open(inp); n = len(src.pages); out = Pdf.new(); i = 0
    while i < n:
        p = out.add_blank_page(page_size=(A3W, A3H))
        if i < n: p.add_overlay(src.pages[i], Rectangle(0, 0, A4W, A4H))
        if i + 1 < n: p.add_overlay(src.pages[i+1], Rectangle(A4W, 0, A4W*2, A4H))
        b = out.add_blank_page(page_size=(A3W, A3H))
        if i + 2 < n: b.add_overlay(src.pages[i+2], Rectangle(0, 0, A4W, A4H))
        if i + 3 < n: b.add_overlay(src.pages[i+3], Rectangle(A4W, 0, A4W*2, A4H))
        if rot_back:
            b.contents_add(b"q -1 0 0 -1 %.1f %.1f cm\n" % (A3W, A3H), prepend=True)
            b.contents_add(b"\nQ\n", prepend=False)
        i += 4
    out.save(outp)
    print("OK: %d 页 -> %d 张 A3 (2-up, rotate_back=%s)" % (n, len(out.pages)//2, rot_back))
if __name__ == "__main__":
    main()
