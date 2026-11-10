#!/usr/bin/env python3
"""booklet-a3.py —— A3 骑马钉拼版（A3 对折一次 → A4 成品）

用法:
  python3 booklet-a3.py 输入.pdf 输出.pdf [--flip short|long]

原理（A3 一张 = 2 个 A4 面，对折成 A4 成品）:
  n 页补足 4 的倍数；第 k 张纸:
    正面: 左=n-2k+2  右=2k-1
    背面: 左=2k      右=n-2k+1
  例 8 页: 纸1 正=8,1 背=2,7 ; 纸2 正=6,3 背=4,5
"""
import sys
import pikepdf
from pikepdf import Pdf, Rectangle

A3W, A3H = 1190.55, 841.89   # A3 横向 (420x297mm) in pt
A4W, A4H = 595.28, 841.89    # A4 纵向

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flip = "short"
    if "--flip" in sys.argv:
        i = sys.argv.index("--flip")
        if i + 1 < len(sys.argv): flip = sys.argv[i+1]
    rot_back = "--rotate-back" in sys.argv   # 2026-10-07：背面整页转 180°
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    inp, outp = args[0], args[1]
    src = Pdf.open(inp)
    n = len(src.pages)
    pad = (4 - n % 4) % 4
    total = n + pad
    out = Pdf.new()
    for k in range(1, total // 4 + 1):
        fr_left, fr_right = total - 2*k + 2, 2*k - 1
        bk_left, bk_right = 2*k, total - 2*k + 1
        # 正面
        p = out.add_blank_page(page_size=(A3W, A3H))
        place(p, src, fr_left, (0, 0))
        place(p, src, fr_right, (A4W, 0))
        # 背面（短边翻转时左右对调）
        b = out.add_blank_page(page_size=(A3W, A3H))
        if rot_back:
            # 2026-10-07 修（背面倒置）：左右摆 flip=long 位，再整页 180°（同 PS 定版）
            place(b, src, bk_left, (0, 0))
            place(b, src, bk_right, (A4W, 0))
            b.contents_add(b"q -1 0 0 -1 %.1f %.1f cm\n" % (A3W, A3H), prepend=True)
            b.contents_add(b"\nQ\n", prepend=False)
        elif flip == "short":
            place(b, src, bk_left, (A4W, 0))
            place(b, src, bk_right, (0, 0))
        else:
            place(b, src, bk_left, (0, 0))
            place(b, src, bk_right, (A4W, 0))
    out.save(outp)
    print(f"✅ 完成: {n} 页(补 {pad} 白页) -> {total//4} 张 A3 双面 -> {outp}")
    print(f"   翻页方式: {flip}（若试样页序不对，换 --flip long 再试一次）")

def place(page, src, num, xy):
    """把第 num 页(1-based)放到 A3 的指定位置；num 超出原文件则留白"""
    if num < 1 or num > len(src.pages):
        return
    page.add_overlay(src.pages[num-1], Rectangle(xy[0], xy[1], xy[0]+A4W, xy[1]+A4H))

if __name__ == "__main__":
    main()