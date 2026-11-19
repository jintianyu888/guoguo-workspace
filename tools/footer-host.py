#!/usr/bin/env python3
"""footer-host.py —— 页脚机器状态（零 token）"""
import os, subprocess, glob

def rd(p, default=""):
    try: return open(p).read()
    except Exception: return default

gw = 0
for d in glob.glob("/proc/[0-9]*"):
    c = rd(d + "/cmdline").replace("\0", " ")
    if "openclaw" in c and "gateway" in c:
        gw = int(os.path.basename(d)); break
if not gw:
    for d in glob.glob("/proc/[0-9]*"):
        if "openclaw" in rd(d + "/cmdline").replace("\0", " "):
            gw = int(os.path.basename(d)); break

load = rd("/proc/loadavg").split()[0] if rd("/proc/loadavg") else "?"
mi = rd("/proc/meminfo")
tot = avail = 0
for ln in mi.splitlines():
    if ln.startswith("MemTotal:"): tot = int(ln.split()[1])
    if ln.startswith("MemAvailable:"): avail = int(ln.split()[1])
mem = f"{(tot-avail)*100//tot}%({(tot-avail)/1048576:.1f}/{(tot)/1048576:.1f}GB)" if tot else "?"
try:
    disk = subprocess.run(["df", "-h", "/"], capture_output=True, text=True).stdout.splitlines()[1].split()[4]
except Exception: disk = "?"
rss = "?"
for ln in rd(f"/proc/{gw}/status").splitlines():
    if ln.startswith("VmRSS:"): rss = f"{int(ln.split()[1])/1048576:.1f}GB"
print(f"🖥 主机：负载 {load} / {os.cpu_count()} 核 · 内存 {mem} · 磁盘 {disk}")
if gw: print(f"🧠 网关(PID {gw})：内存 {rss}")
nvs = "/usr/lib/wsl/lib/nvidia-smi"
if os.path.exists(nvs):
    try:
        o = subprocess.run([nvs, "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=12).stdout.strip()
        if o: print("🎮 GPU：" + o)
    except Exception: pass
else:
    print("🎮 GPU：nvidia-smi 不可用")