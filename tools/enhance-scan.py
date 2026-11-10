#!/usr/bin/env python3
"""enhance-scan.py —— 扫描件/照片增强：去噪 → 纠偏 → 自适应二值化（CPU/OpenCV）
用法: enhance-scan.py <in.jpg> --out <out.png> [--no-deskew] [--dpi 300]
"""
import argparse, sys
import cv2, numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("--out", required=True)
ap.add_argument("--no-deskew", action="store_true")
a = ap.parse_args()

img = cv2.imread(a.src, cv2.IMREAD_GRAYSCALE)
if img is None:
    print("读不到:", a.src); sys.exit(1)
h0, w0 = img.shape[:2]

# 1) 去噪（保留笔画）
den = cv2.fastNlMeansDenoising(img, None, 10, 7, 21)

# 2) 纠偏（用小角度霍夫/最小外接矩形估计倾角）
if not a.no_deskew:
    thr = cv2.threshold(den, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(thr)
    ang = 0.0
    if coords is not None:
        rect = cv2.minAreaRect(coords)
        ang = rect[-1]
        if ang < -45: ang += 90
        elif ang > 45: ang -= 90
    if abs(ang) > 0.3 and abs(ang) < 15:
        M = cv2.getRotationMatrix2D((w0 / 2, h0 / 2), ang, 1.0)
        den = cv2.warpAffine(den, M, (w0, h0), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        print(f"纠偏 {ang:.2f}°")

# 3) 自动判断：只有"浅底深字"的扫描件才二值化；截图/照片只去噪（二值化会毁掉 UI/彩色内容）
mean, std = float(den.mean()), float(den.std())
is_scan = mean > 165 and std < 70
if is_scan:
    bw = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    bw = cv2.medianBlur(bw, 3)
    cv2.imwrite(a.out, bw)
    print(f"OK -> {a.out}  {w0}x{h0}  (去噪+纠偏+二值 [扫描件])")
else:
    cv2.imwrite(a.out, den)
    print(f"OK -> {a.out}  {w0}x{h0}  (仅去噪 [截图/照片] mean={mean:.0f} std={std:.0f})")