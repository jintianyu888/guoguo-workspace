#!/usr/bin/env python3
"""OCR GPU/CPU 对比基准。用法：python3 tools/ocr-gpu-bench.py [图片] [次数]
默认图片 tools/ocr-test.png，默认 3 次（先预热 1 次）。环境变量 OCR_FORCE_CPU=1 强制 CPU。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocr

img = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ocr-test.png")
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

eng = ocr.get_engine()
prov = ocr.engine_provider()
ocr.ocr_image(img)  # warmup
times = []
for _ in range(n):
    t = time.perf_counter()
    lines, text = ocr.ocr_image(img)
    times.append(time.perf_counter() - t)
print(f"provider={prov} img={os.path.basename(img)} runs={n}")
print(f"times={[round(x, 3) for x in times]} min={min(times):.3f}s mean={sum(times)/n:.3f}s")
print(f"chars={len(text)}")
