#!/usr/bin/env python3
"""群晖 NAS 存储 & OpenClaw 备份占用。用法: python3 nas-storage.py"""
import subprocess, sys

HOST = "nas"
REMOTE = (
    "df -h /volume1 | tail -1; echo '@@@'; "
    "du -sk ~/archive/jinyu/migrated-20261102/openclaw-backup.git 2>/dev/null | awk '{print $1}'; echo '@@@'; "
    "du -sk ~/archive/jinyu/migrated-20261102/ws-*.git 2>/dev/null | awk '{s+=$1} END {print s+0}'; echo '@@@'; "
    "du -sk ~/archive/jinyu/openclaw-archives 2>/dev/null | awk '{print $1}'; echo '@@@'; "
    "ls -t ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null | head -1"
)

def human(kb):
    kb = float(kb or 0)
    for u in ("KB", "MB", "GB", "TB"):
        if kb < 1024: return f"{kb:.1f}{u}"
        kb /= 1024
    return f"{kb:.1f}PB"

try:
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST, REMOTE],
                       capture_output=True, text=True, timeout=60)
    parts = [p.strip() for p in (r.stdout or "").split("@@@")]
    if len(parts) < 4:
        print("群晖：连接失败或输出异常（暂不可用）"); sys.exit(0)
    df = parts[0].split()
    size, used, avail, pct = (df[1], df[2], df[3], df[4]) if len(df) >= 5 else ("?", "?", "?", "?")
    db = human(parts[1]); ws = human(parts[2]); ar = human(parts[3])
    last = parts[4].split("/")[-1] if len(parts) > 4 and parts[4] else "（无）"
    print(f"群晖 NAS (/volume1)：共 {size} · 已用 {used} · 可用 {avail} · **使用率 {pct}**")
    print(f"OpenClaw 备份占用：数据库 {db} · 工作区 {ws} · 全量归档 {ar}")
    print(f"最新归档：{last}")
except Exception as e:
    print(f"群晖：暂不可用（{type(e).__name__}）")
