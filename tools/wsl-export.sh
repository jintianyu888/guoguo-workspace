#!/bin/bash
# wsl-export.sh —— 导出 WSL 整机镜像到 E 盘（2026-10-15 主公令：镜像做，不搬盘）
W=/mnt/c/Windows/System32/wsl.exe
TS=$(date +%Y%m%d-%H%M)
LOG=/home/j/.openclaw/workspace/state/wsl-export.log
mkdir -p /mnt/e/wsl-backup
echo "=== START $(date '+%F %T') ===" >> "$LOG"
"$W" --export Ubuntu "E:\\wsl-backup\\ubuntu-$TS.tar" >> "$LOG" 2>&1
RC=$?
echo "rc=$RC" >> "$LOG"
ls -la /mnt/e/wsl-backup/ >> "$LOG" 2>&1
echo "=== DONE $(date '+%F %T') ===" >> "$LOG"
exit $RC
