#!/usr/bin/env python3
"""host-footer.py —— 页脚用：本机占用 + 我(网关)自己的占用 + GPU"""
import os, shutil, subprocess, glob

def line_cpu():
    la = os.getloadavg()[0]
    cores = os.cpu_count() or 0
    return la, cores

def mem_pct():
    d = {}
    with open("/proc/meminfo") as f:
        for l in f:
            k, _, v = l.partition(":")
            d[k] = int(v.strip().split()[0])
    total = d.get("MemTotal", 1); avail = d.get("MemAvailable", 0)
    return round((total - avail) * 100 / total)

def disk():
    u = shutil.disk_usage("/")
    return f"{u.used//2**30}/{u.total//2**30} GB ({round(u.used*100/u.total)}%)"

def gateway_proc():
    try:
        pid = subprocess.run(["pgrep", "-f", "openclaw/dist/index.js gateway"], capture_output=True, text=True).stdout.split()[0]
        out = subprocess.run(["ps", "-o", "%cpu=,%mem=,rss=", "-p", pid], capture_output=True, text=True).stdout.split()
        return f"CPU {out[0]}% · 内存 {out[1]}% · RSS {int(out[2])//1024} MB", pid
    except Exception:
        return "n/a", "n/a"

def gpu():
    exe = "/mnt/c/Windows/System32/nvidia-smi.exe"
    if not os.path.exists(exe): return "GPU: n/a"
    try:
        q = subprocess.run([exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=10).stdout.strip().replace("\r", "")
        return "🎮 " + q
    except Exception:
        return "GPU: 查询失败"

la, cores = line_cpu()
print(f"🖥 CPU：{la:.2f}/{cores} 线程 · 内存 {mem_pct()}% · 磁盘 {disk()}")
me, pid = gateway_proc()
print(f"🧠 网关进程（我自己）：{me} · PID {pid}")
print(gpu())