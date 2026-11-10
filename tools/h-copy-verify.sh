#!/bin/bash
# h-copy-verify.sh —— H:wsl-backup 与 E:wsl-backup 一致性核验（只读，有差异才告警，同一结果只发一次）
set -uo pipefail
LOG=/home/j/.openclaw/workspace/state/work/h-copy-verify.log
STATE=/home/j/.openclaw/workspace/state/work/h-copy-verify.last
exec >> "$LOG" 2>&1
echo "=== $(date '+%F %T') ==="
if pgrep -x Robocopy.exe >/dev/null || pgrep -x Robocopy >/dev/null; then echo "robocopy 仍在跑，跳过"; exit 0; fi
diffs=""
for f in ubuntu-20261016-1236.tar ubuntu-20261022.tar pre-migration-20261022.tar.gz; do
  E="/mnt/e/wsl-backup/$f"; H="/mnt/h/wsl-backup/$f"
  [ -f "$E" ] || { echo "缺E:$f"; continue; }
  [ -f "$H" ] || { diffs="$diffs\n• $f：H 缺失"; continue; }
  se=$(stat -c%s "$E"); sh_=$(stat -c%s "$H")
  if [ "$se" != "$sh_" ]; then diffs="$diffs\n• $f：大小不一致 E=$se H=$sh_"; continue; fi
  me=$( (head -c 1048576 "$E"; tail -c 1048576 "$E") | md5sum | cut -d' ' -f1)
  mh=$( (head -c 1048576 "$H"; tail -c 1048576 "$H") | md5sum | cut -d' ' -f1)
  if [ "$me" != "$mh" ]; then diffs="$diffs\n• $f：首尾 md5 不一致"; else echo "OK $f $se"; fi
done
if [ -n "$diffs" ]; then
  h=$(printf '%s' "$diffs" | md5sum | cut -d' ' -f1)
  [ -f "$STATE" ] && [ "$(cat "$STATE")" = "$h" ] && exit 0
  echo "$h" > "$STATE"
  timeout 30 sh /home/j/.openclaw/workspace/tools/notify.sh "⚠️ E/H 整机镜像不一致：$diffs" >/dev/null 2>&1 || true
else
  echo "ALL_OK"
  [ -f "$STATE" ] && [ "$(cat "$STATE")" = "ALL_OK" ] && exit 0
  echo "ALL_OK" > "$STATE"
  timeout 30 sh /home/j/.openclaw/workspace/tools/notify.sh "✅ E/H 整机镜像三件已全部一致（大小+首尾 md5）" >/dev/null 2>&1 || true
fi
