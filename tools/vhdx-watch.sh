#!/bin/bash
# vhdx-watch.sh —— WSL 镜像体积监控（只读，2026-11-04 主公令：防止无限增长）
# 判据：宿主 vhdx 大小 vs WSL 内实际用量，偏差 >25% 或 vhdx >950G 时告警
set -u
VHDX=/mnt/x/WSL/Ubuntu/ext4.vhdx
LOG=/home/j/.openclaw/workspace/state/vhdx-watch.log
ST=/home/j/.openclaw/workspace/state/vhdx-watch.json
ts=$(date "+%F %T")
host=$(stat -c%s "$VHDX" 2>/dev/null || echo 0)
used=$(df -B1 / | awk "NR==2{print \$3}")
free=$(df -B1 / | awk "NR==2{print \$4}")
sparse=$(stat -c%b "$VHDX" 2>/dev/null || echo 0)
hostg=$((host/1024/1024/1024))
usedg=$((used/1024/1024/1024))
ratio=0
[ "$used" -gt 0 ] && ratio=$(( host*100/used ))
printf "{\"ts\":\"%s\",\"vhdx_bytes\":%s,\"vhdx_gb\":%s,\"used_bytes\":%s,\"used_gb\":%s,\"ratio_pct\":%s}\n" "$ts" "$host" "$hostg" "$used" "$usedg" "$ratio" > "$ST"
echo "$ts vhdx=${hostg}G used=${usedg}G ratio=${ratio}%" >> "$LOG"
msg=""
if [ "$host" -gt $((950*1024*1024*1024)) ]; then msg="vhdx 已 ${hostg}G，超过 950G 阈值"; fi
if [ "$ratio" -gt 125 ]; then msg="${msg:+$msg；}宿主占用是实际用量的 $((ratio/100)).$((ratio%100)) 倍，疑似只增不减，建议压缩+fstrim"; fi
if [ -n "$msg" ]; then
  bash /home/j/.openclaw/workspace/tools/notify.sh --alert "【WSL镜像膨胀】$msg" >/dev/null 2>&1 || true
  echo "$ts ALERT $msg" >> "$LOG"
fi
exit 0
