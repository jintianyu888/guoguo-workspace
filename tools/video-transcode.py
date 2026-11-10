#!/usr/bin/env python3
"""video-transcode.py —— 用 NVENC 硬件编码转码视频（PyAV，无需系统 ffmpeg）
用法: video-transcode.py <in> <out.mp4> [--codec h264|hevc] [--cpu]
"""
import argparse, time, av

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--codec", choices=["h264", "hevc"], default="h264")
ap.add_argument("--cpu", action="store_true", help="用 CPU(x264) 做对照")
a = ap.parse_args()
agpu = f"{a.codec}_nvenc"
acpu = "libx264" if a.codec == "h264" else "libx265"
codec = acpu if a.cpu else agpu

inp = av.open(a.src)
out = av.open(a.out, mode="w")
ist = inp.streams.video[0]
ost = out.add_stream(codec, rate=ist.average_rate)
ost.width, ost.height = ist.codec_context.width, ist.codec_context.height
t0 = time.time(); n = 0
for frame in inp.decode(ist):
    for pkt in ost.encode(frame):
        out.mux(pkt)
    n += 1
for pkt in ost.encode():
    out.mux(pkt)
out.close(); inp.close()
dt = time.time() - t0
print(f"{codec}: {n} 帧 / {dt:.2f}s = {n/dt:.1f} fps -> {a.out}")