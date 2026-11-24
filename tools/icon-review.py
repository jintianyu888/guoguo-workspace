# -*- coding: utf-8 -*-
"""icon-review.py —— 图标审美自检：32px 可读性 / 色相区分度 / 主体占比 / 与现有图标重复度"""
import sys, os, glob, colorsys, json
from PIL import Image, ImageFilter

W = "/home/j/.openclaw/workspace"

def stats(p):
    im = Image.open(p).convert("RGB")
    small = im.resize((32, 32))
    # 32px 亮度对比（前景白 vs 背景）
    px = list(small.getdata())
    lum = [0.299*r + 0.587*g + 0.114*b for r, g, b in px]
    lum.sort()
    contrast = (lum[-1] - lum[0]) / 255.0
    # 主体占比：接近白色像素比例
    whiteish = sum(1 for r, g, b in px if r > 200 and g > 200 and b > 200) / len(px)
    # 锐度：拉普拉斯方差
    lap = small.filter(ImageFilter.FIND_EDGES)
    lp = list(lap.convert("L").getdata())
    sharp = sum(lp) / len(lp)
    # 主色相（背景四角）
    corners = [im.getpixel((3, 3)), im.getpixel((236, 3)), im.getpixel((3, 236)), im.getpixel((236, 236))]
    hs = [colorsys.rgb_to_hsv(r/255, g/255, b/255)[0] * 360 for r, g, b in corners]
    return {"contrast": round(contrast, 2), "white": round(whiteish, 2), "sharp": round(sharp, 1), "hue": round(sum(hs)/4, 1)}

def hue_dist(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)

if __name__ == "__main__":
    targets = sys.argv[1:] or sorted(glob.glob(W + "/state/icons/new/*.png"))
    REDESIGNED = {"剪辑管家","3D打印管家","信息板管家","安保管家","维护管家","法律管家","格格","健康管家","健康豆豆管家","健康媳妇管家","健康妈妈管家","公司1管家","公司2管家","公司3管家","排课管家","Agant老师","干活管家","Hermess"}
    base = []
    for f in glob.glob(W + "/state/icons/current/*.png"):
        nm = os.path.basename(f)[:-4]
        if nm in REDESIGNED or nm.startswith("montage"): continue
        base.append((nm, stats(f)["hue"]))
    bad = 0
    for t in targets:
        if not os.path.exists(t): continue
        n = t.replace(".svg", ".png")
        s = stats(n)
        near = min(((nm, hue_dist(s["hue"], h)) for nm, h in base if nm != os.path.basename(n)[:-4]), default=("", 999), key=lambda x: x[1])
        flags = []
        if s["contrast"] < 0.55: flags.append("对比偏低")
        if s["white"] < 0.10: flags.append("主体太小")
        if s["sharp"] < 6: flags.append("32px发糊")
        hue_note = "" if near[1] >= 18 else " 色相接近%s(%.0f°)但图形不同" % (near[0], near[1])
        ok = not flags
        if not ok: bad += 1
        print("%-14s 对比%.2f 主体%.2f 锐度%5.1f 色相%5.1f 最近%s(%.0f°) %s" % (
            os.path.basename(n)[:-4], s["contrast"], s["white"], s["sharp"], s["hue"], near[0][:10], near[1],
            ("OK" if ok else "WARN " + ",".join(flags)) + hue_note))
    print("RESULT", "GREEN" if bad == 0 else "WARN %d 个待看" % bad)
