#!/usr/bin/env bash
# face-retention.sh —— 抓拍留存策略（2026-11-07 主公批准 #117：7 天自动删）
# hits/ 与 candidates/ 下的日期目录保留 7 天；collected/ 原图保留 30 天；特征库 npz 不动
set -uo pipefail
F=/home/j/.openclaw/workspace/state/faces
LOG=/home/j/.openclaw/workspace/state/work/face-retention.log
mkdir -p "$(dirname "$LOG")"
D1=0; D2=0
for base in hits candidates; do
  [ -d "$F/$base" ] || continue
  for d in "$F/$base"/*; do
    [ -d "$d" ] || continue
    case "$(basename "$d")" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) continue;; esac
    if [ -n "$(find "$d" -maxdepth 0 -mtime +7 2>/dev/null)" ]; then rm -rf "$d"; D1=$((D1+1)); fi
  done
done
if [ -d "$F/collected" ]; then
  D2=$(find "$F/collected" -maxdepth 1 -type f -mtime +30 2>/dev/null | wc -l)
  find "$F/collected" -maxdepth 1 -type f -mtime +30 -delete 2>/dev/null || true
fi
echo "$(date "+%F %T") 清理 日期目录=$D1 collected文件=$D2" >> "$LOG"
