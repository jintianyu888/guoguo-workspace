#!/usr/bin/env bash
# vhdx-status.sh — 只读：X 盘 WSL 镜像占用 / 实际用量 / 膨胀比
set -u
V=/mnt/x/WSL/Ubuntu/ext4.vhdx
if [ ! -e "$V" ]; then echo "找不到镜像: $V"; exit 1; fi
apparent=$(stat -c %s "$V" 2>/dev/null || echo 0)
alloc=$(du -B1 "$V" 2>/dev/null | awk '{print $1}')
usedk=$(df -B1 / | awk 'NR==2{print $3}')
totk=$(df -B1 / | awk 'NR==2{print $2}')
xfree=$(df -B1 /mnt/x | awk 'NR==2{print $4}')
g(){ awk -v b="$1" 'BEGIN{printf "%.0f", b/1073741824}'; }
a=$(g "$apparent"); al=$(g "${alloc:-0}"); u=$(g "$usedk"); t=$(g "$totk"); xf=$(g "$xfree")
echo "镜像逻辑大小 : ${a} G"
echo "镜像实际占用 : ${al} G   (稀疏后真实占盘)"
echo "WSL 内已用   : ${u} G / ${t} G"
echo "X 盘可用     : ${xf} G"
if [ "$u" -gt 0 ]; then
  echo "膨胀比       : $(awk -v a="$al" -v u="$u" 'BEGIN{printf "%.0f%%", a*100/u}')  (告警线 125%)"
fi
if [ -f /home/j/.openclaw/workspace/state/vhdx-watch.log ]; then
  echo "上次监控     : $(tail -1 /home/j/.openclaw/workspace/state/vhdx-watch.log)"
fi
exit 0
