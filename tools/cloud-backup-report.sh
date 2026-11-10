#!/bin/bash
# cloud-backup-report.sh —— 汇总最近一次云端加密备份结果并发飞书（幂等：只在有新结果时发）
LOG=/home/j/.openclaw/workspace/state/work/cloud-backup.log
STATE=/home/j/.openclaw/workspace/state/work/cloud-backup-report.last
last=$(grep -E '✅|❌|完成|移到|分片' "$LOG" | tail -12)
[ -z "$last" ] && exit 0
h=$(printf '%s' "$last" | md5sum | cut -d' ' -f1)
[ -f "$STATE" ] && [ "$(cat "$STATE")" = "$h" ] && exit 0
echo "$h" > "$STATE"
enc_dir='/mnt/e/openclaw-cloud-backup/备份归档-加密'
parts=$(ls "$enc_dir"/*.enc.part* 2>/dev/null | wc -l)
size=$(du -sh "$enc_dir" 2>/dev/null | cut -f1)
msg="☁️ 云端加密备份：产物分片 $parts 个，合计 $size
$(printf '%s' "$last" | tail -6)"
timeout 30 sh /home/j/.openclaw/workspace/tools/notify.sh "$msg" >/dev/null 2>&1 || true
