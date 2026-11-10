#!/usr/bin/env python3
"""footer-dl.py —— 页脚下载进度：已下/总大小/百分比/速度/预计剩余（零 token）"""
import glob, os, re, time

DL = "/home/j/.openclaw/workspace/state/dl"
LOGS = ["cudnn-fetch", "torch-fetch", "cuda-fetch"]

def parts_map():
    m = {}
    for p in glob.glob(DL + "/*.part*"):
        base = re.sub(r"\.part\d+$", "", os.path.basename(p))
        m[base] = m.get(base, 0) + os.path.getsize(p)
    return m

pm = parts_map()
rows = []
for L in LOGS:
    lp = f"/home/j/.openclaw/workspace/state/{L}.log"
    if not os.path.exists(lp):
        continue
    txt = open(lp, errors="ignore").read()
    names = re.findall(r"下载\s+(\S+\.(?:whl|tar))", txt)
    if not names:
        continue
    name = names[-1]
    tot = re.findall(r"大小\s+([0-9.]+)\s+MB", txt)
    total_mb = float(tot[-1]) if tot else 0.0
    have = pm.get(name, 0) / 1048576.0
    running = os.system(f"pgrep -f {L} >/dev/null 2>&1") == 0
    rows.append((name, have, total_mb, running))

if not rows:
    print("⬇️ 当前无进行中的下载")
else:
    for name, have, total, running in rows:
        pct = (have * 100.0 / total) if total else 0
        st = "进行中" if running else "已停止"
        if total:
            print(f"⬇️ {name[:52]}：**{have:.0f}MB / {total:.0f}MB（{pct:.0f}%）** · {st}")
        else:
            print(f"⬇️ {name[:52]}：{have:.0f}MB · {st}")

for t in glob.glob(DL + "/*.tar"):
    print(f"📦 已打包待传：{os.path.basename(t)} {os.path.getsize(t)/1073741824:.1f}G")