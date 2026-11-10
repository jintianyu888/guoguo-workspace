#!/usr/bin/env bash
# disk-watermark-guard.sh —— 磁盘水位硬闸（2026-11-07 主公批准 #222）
# 85%：清已知泄漏（.cache/openclaw 只读快照残留 >60 分钟）+ 记录
# 92%：再清 backup-stage 的 .part 残片与旧 tmp，仍高则置 .disk-critical
# 只删可再生成的临时物；不碰备份归档、不碰数据库
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/disk-watermark.log
FLAG=$W/state/work/.disk-critical
mkdir -p "$(dirname "$LOG")"
say(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
USE=$(df -Pk / | awk 'NR==2{gsub("%","",$5); print $5}')
say "root used=$USE%"
if [ "$USE" -lt 85 ]; then
  if [ -f "$FLAG" ]; then rm -f "$FLAG"; say "水位回落，解除 .disk-critical"; fi
  exit 0
fi
N1=0
if [ -d /home/j/.cache/openclaw ]; then
  N1=$(find /home/j/.cache/openclaw -mindepth 1 -maxdepth 1 -type d -mmin +60 2>/dev/null | wc -l)
  if [ "$N1" -gt 0 ]; then find /home/j/.cache/openclaw -mindepth 1 -maxdepth 1 -type d -mmin +60 -exec rm -rf {} + 2>/dev/null; fi
fi
say "清理 .cache/openclaw 快照残留目录: $N1"
if [ "$USE" -ge 92 ]; then
  N2=$(find /home/j/backup-stage -name "*.part" -mmin +30 2>/dev/null | wc -l)
  if [ "$N2" -gt 0 ]; then find /home/j/backup-stage -name "*.part" -mmin +30 -delete 2>/dev/null; fi
  N3=$(find /home/j/.openclaw/tmp -mindepth 1 \( -path "/home/j/.openclaw/tmp/plugin-captures" -o -path "/home/j/.openclaw/tmp/plugin-captures/*" \) -prune -o -mmin +1440 -print 2>/dev/null | wc -l)
  if [ "$N3" -gt 0 ]; then find /home/j/.openclaw/tmp -mindepth 1 \( -path "/home/j/.openclaw/tmp/plugin-captures" -o -path "/home/j/.openclaw/tmp/plugin-captures/*" \) -prune -o -mmin +1440 -exec rm -rf {} + 2>/dev/null; fi
  say "深度清理 .part=$N2 tmp=$N3"
  USE2=$(df -Pk / | awk 'NR==2{gsub("%","",$5); print $5}')
  if [ "$USE2" -ge 92 ]; then date "+%F %T" > "$FLAG"; say "水位仍 $USE2%，置 .disk-critical"; fi
fi
exit 0
